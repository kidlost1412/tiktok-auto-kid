"""Chặng 3 — hiệu ứng âm thanh (SFX) chọn THEO NGHĨA của hình, không rải ngẫu nhiên.

Luồng: len_lich(...) → danh sách sự kiện [{"nhom","file","t","db","dai","gain",...}]; tron_lenh/tron_am(...) trộn dưới giọng;
kiem_am.py đo lại bản trộn + chấm lịch (để người nghe biết nghe chỗ nào).

KHO ÂM
- Kho cũ (KHO_MAC_DINH, gói Mixkit trong tai-nguyen/sfx — tải về), kho MỚI đóng gói theo mã ở xuong-video/mau/sfx-moi
  (38 file + danh-muc.json đã đo sẵn; có ngay khi cài, không cần mạng) và file người dùng thêm (kho_nhac.sfx_phu).
- Mỗi nhóm âm: nếu có file mới/người dùng thì CHỈ dùng chúng; nhóm chỉ có file cũ thì dùng file cũ.
- Danh mục: danh_muc() → {file: {nhom, vai, mo_ta, dai, dinh_db, t_dinh, t_bat, tan_cong, goc}}; đo bằng ffmpeg 1 lần, nhớ ở
  tai-nguyen/sfx/_kho-am.json (file mới thì đã đo sẵn trong danh-muc.json). mo_ta_am() → mô tả 1 dòng mỗi nhóm cho prompt đạo diễn.

LỊCH
- Mỗi loại khối chữ có âm mặc định hợp nghĩa (xem _khoi); khối có thể ghi đè bằng b["am"] = tên nhóm | "khong".
- Không nổ ở giây 0. Âm mở đầu chỉ khi am_mo (tên nhóm) hoặc khi chính khối đầu có ánh xạ ra tiếng đó.
- Vút chuyển cảnh chỉ khi cảnh chuyển có chuyển động (slide/zoom/smooth/push), không bao giờ theo xác suất.
- Lật trang (montage ảnh): phần tử trong `pops` có thể là dict {"lat": [giây, ...]} (hoặc tham số lat_trang=[[...], ...]);
  mỗi cụm lật = 1 "cử chỉ" gồm vài tiếng tick nhẹ (tối đa 8, cách nhau ≥ 0,16 s).
- Một họ UI mỗi video (tick hoặc bop, chọn 1 lần bằng rng), 1 file tối đa 2 lần (trừ tiếng gõ/tick hàng lặp), nhát nặng ≤ 1/3 số
  cử chỉ, mật độ ≤ 4/6/8 cử chỉ mỗi 10 s theo mức; tiếng ưu tiên thấp bị bỏ trước.
- Mức (gon/vua/soi_dong/mo_dau_am) chỉ chỉnh số lượng + âm lượng chung một chút, không đổi âm nào đi với hình nào."""
import json, math, re, subprocess
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
CFG = cfg_hub()
ROOT = Path(CFG["duong_dan"].get("sfx") or (HUB / "tai-nguyen" / "sfx"))
FPS = 30

# Kho đã lọc: chỉ giữ âm hợp video bán hàng nông nghiệp (bỏ tiếng cười, la ó, violin buồn, "bruh"...)
KHO_MAC_DINH = {
    "vut_nhe":  ["whoosh/mixkit-1461-short-wind-swoosh.wav", "whoosh/mixkit-1471-cinematic-wind-swoosh.wav", "whoosh/mixkit-174-fast-sweep-transition.wav"],
    "vut_manh": ["whoosh/mixkit-1469-flying-fast-swoosh.wav", "whoosh/mixkit-1465-vacuum-swoosh-transition.wav", "whoosh/mixkit-174-fast-sweep-transition.wav"],
    "roi_phep": ["whoosh/mixkit-1516-magic-whip-swell.wav"],
    "dap":      ["impact/mixkit-2299-short-bass-hit.wav", "impact/mixkit-2303-futuristic-bass-hit.wav", "opener/bass-impact.mp3"],
    "no_lon":   ["opener/cinematic-boom-hq.mp3", "opener/vine-boom.mp3", "impact/mixkit-2782-epic-impact-afar-explosion.wav",
                 "opener/capcut-explosion.mp3", "impact/mixkit-1687-dramatic-metal-explosion-impact.wav"],
    "keo_len":  ["riser/mixkit-2669-short-sci-fi-swell.wav"],
    "bop":      ["ui/mixkit-1124-plastic-bubble-click.wav", "foley/mixkit-3000-liquid-bubble.wav", "ui/mixkit-1109-select-click.wav"],
    "go_phim":  ["ui/mixkit-1119-hard-typewriter-click.wav", "ui/mixkit-1125-typewriter-soft-click.wav"],
    "chup":     ["ui/mixkit-1133-camera-shutter-click.wav", "ui/mixkit-1440-classic-camera-click.wav"],
    "ting":     ["ding/mixkit-586-attention-bell-ding.wav", "ding/mixkit-3108-crystal-chime.wav", "opener/apple-pay-ding.mp3"],
    "lap_lanh": ["ding/mixkit-3060-sparkle-hybrid-transition.wav", "ding/mixkit-866-fairy-arcade-sparkle.wav"],
    "dung":     ["meme/mixkit-947-correct-answer-notification.wav", "meme/myinstants-correct-answer.mp3"],
    "sai":      ["meme/mixkit-950-game-show-wrong-answer-buzz.wav", "meme/myinstants-wrong-answer-buzzer.mp3"],
    "tien":     ["money/mixkit-1992-coin-win-notification.wav", "money/mixkit-1999-gold-coin-prize.wav", "money/mixkit-1993-clinking-coins.wav"],
    "tui_qua":  ["money/mixkit-1989-money-bag-drop.wav"],
    "vo_tay":   ["meme/mixkit-517-small-group-light-applause.wav"],
    "nen_vuon": ["ambience/mixkit-2464-morning-sound-in-a-garden.wav", "ambience/mixkit-1210-forest-birds-ambience.wav",
                 "ambience/mixkit-1238-windy-humming-forest-with-birds.wav"],
}

# Vai của từng nhóm → đỉnh dBFS trước khi trộn (EditAtlas, tham khảo không phải luật cứng)
VAI = {"vut_nhe": "whoosh", "vut_manh": "whoosh", "roi_phep": "whoosh", "dap": "hit", "no_lon": "hit", "keo_len": "riser",
       "bop": "ui", "tick": "ui", "thong_bao": "ui", "go_phim": "typing", "chup": "foley", "ting": "bell", "lap_lanh": "magic",
       "dung": "bell", "sai": "alert", "tien": "money", "tui_qua": "foley", "vo_tay": "crowd", "nen_vuon": "ambience",
       "con_dau": "foley", "but_viet": "foley", "phun_suong": "foley", "nuoc": "foley"}
VAI_DB = {"hit": -6.0, "whoosh": -12.0, "foley": -14.0, "riser": -14.0, "bell": -15.0, "magic": -15.0, "ui": -16.0, "typing": -18.0,
          "money": -14.0, "alert": -16.0, "crowd": -18.0, "ambience": -24.0}
NEO_DINH = ("hit", "whoosh", "riser")        # các vai canh theo ĐỈNH to nhất (còn lại canh theo lúc bắt đầu nghe thấy)
HO_UI = ("tick", "bop")                      # họ âm UI để chọn 1 lần mỗi video

MO_TA_NHOM = {   # 1 dòng: nghe như thế nào + hợp khi nào (prompt đạo diễn sinh từ đây qua mo_ta_am())
    "dap": "Nhát nhấn trầm, gọn, như vật nặng đặt xuống; hợp chữ to đập vào màn hình / khoảnh khắc lớn, dùng rất ít.",
    "no_lon": "Tiếng nổ/boom điện ảnh rất nặng; gần như không dùng, chỉ khi hình thật sự bùng nổ.",
    "vut_nhe": "Tiếng lướt gió ngắn, nhẹ; hợp thẻ/băng chữ trượt vào hoặc chuyển cảnh trượt.",
    "vut_manh": "Tiếng vút nhanh, mạnh hơn; hợp chữ quét ra dứt khoát hoặc chuyển cảnh zoom/trượt nhanh.",
    "roi_phep": "Tiếng vút ma thuật dâng lên; hợp hé lộ điều bất ngờ.",
    "keo_len": "Tiếng gió dâng dần tới đỉnh rồi dứt; hợp dồn vào khoảnh khắc chốt (đỉnh rơi đúng lúc hiện chữ).",
    "bop": "Tiếng bật/bấm nhẹ như bong bóng hoặc nút bấm; hợp ô hình hiện ra, bong bóng câu hỏi, nhãn dán.",
    "tick": "Tiếng tách giao diện rất ngắn, sạch; hợp từng dòng danh sách, số bắt đầu đếm, ô hiện ra.",
    "thong_bao": "Tiếng báo tin nhắn ứng dụng; hợp câu mở kiểu 'có tin mới', bình luận, thông báo đơn.",
    "go_phim": "Tiếng gõ phím cơ lách tách; CHỈ hợp chữ gõ máy hiện dần (rải đều suốt lúc gõ).",
    "chup": "Màn trập máy ảnh; hợp khoảnh khắc chụp ảnh / khoe ảnh thật.",
    "ting": "Tiếng chuông 'ting' sáng, ngắn; hợp số vừa dừng, ý chính vừa hiện, điểm nhấn tích cực.",
    "lap_lanh": "Tiếng lấp lánh; hợp hé lộ sản phẩm, quà tặng, chữ nổ kèm sao.",
    "dung": "Chuông lên dần cao độ báo 'đúng/được'; hợp cột ✓ hiện ra, bước hoàn thành.",
    "sai": "Âm báo lỗi trầm, ngắn; hợp băng cảnh báo / lỗi thường gặp (KHÔNG dùng cho chuông thanh toán).",
    "tien": "Tiếng tính tiền / đồng xu leng keng; hợp nút giỏ hàng, bảng quà, giá — đúng lúc nói từ chốt.",
    "tui_qua": "Tiếng túi tiền rơi; hợp khoảnh khắc nhận quà, giảm giá lớn.",
    "vo_tay": "Tiếng vỗ tay nhỏ; hợp chốt thắng lợi, dùng rất ít.",
    "nen_vuon": "Tiếng nền vườn, chim, gió; chỉ làm nền êm, không làm điểm nhấn.",
    "con_dau": "Tiếng đóng dấu cao su gọn, chắc; hợp tem/dấu xác nhận hiện ra.",
    "but_viet": "Tiếng bút viết nguệch ngoạc ngắn; hợp vòng khoanh, gạch chân, bút dạ quang vẽ trên hình.",
    "phun_suong": "Tiếng xì phun sương; hợp cảnh phun thuốc/nước lên cây, tay đang xịt.",
    "nuoc": "Giọt nước nhỏ; hợp cảnh giọt nước, tưới, nhỏ thuốc.",
}

KHO = {k: list(v) for k, v in KHO_MAC_DINH.items()}
GOC = {}                 # file -> "cu" | "moi" | "nguoi_dung"
_TRONG_GOI = {}          # file tuyệt đối -> dòng danh-muc.json (đã đo sẵn)
_KHO_XONG = False
_DT = {}                 # đặc tính đã biết trong bộ nhớ: file -> dict | None (đo lỗi)
_CACHE = None            # nội dung _kho-am.json
_BAN = False             # cache cần ghi lại


def _duong(f):
    """Đường dẫn thật của file trong lịch: tuyệt đối (kho mới/người dùng) hoặc tương đối so với thư mục SFX."""
    return ROOT / f


def dung_lai():
    """Xoá bộ nhớ kho/đo (dùng khi đổi thư mục hoặc trong test)."""
    global KHO, GOC, _TRONG_GOI, _KHO_XONG, _DT, _CACHE, _BAN
    KHO, GOC, _TRONG_GOI, _KHO_XONG, _DT, _CACHE, _BAN = {k: list(v) for k, v in KHO_MAC_DINH.items()}, {}, {}, False, {}, None, False


def _dung_kho():
    """Kho thật = file cũ còn tồn tại + file đóng gói theo mã (mau/sfx-moi) + file người dùng thêm (kho_nhac.py)."""
    global KHO, _KHO_XONG
    if _KHO_XONG:
        return
    kho = {}
    GOC.clear()
    _TRONG_GOI.clear()
    for k, v in KHO_MAC_DINH.items():
        for r in v:
            if (ROOT / r).exists():
                kho.setdefault(k, []).append(r)
                GOC[r] = "cu"
    try:
        import kho_nhac
        g = kho_nhac.goc_sfx_moi()
        j = g / "danh-muc.json"
        if j.exists():
            for row in json.loads(j.read_text(encoding="utf-8")):
                try:
                    p = g / row["file"]
                    if not p.exists():
                        continue
                    f = str(p)
                    _TRONG_GOI[f] = row
                    kho.setdefault(row["nhom"], []).append(f)
                    GOC[f] = "moi"
                except (KeyError, TypeError):
                    continue
        for f, nhoms in kho_nhac.sfx_phu():
            for n in nhoms:
                kho.setdefault(n, []).append(f)
                GOC[f] = "nguoi_dung"
    except Exception as e:
        print("  SFX thêm lỗi:", str(e)[:120])
    KHO, _KHO_XONG = kho, True


# ---------------------------------------------------------------- ĐO + DANH MỤC
def _doc_cache():
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads((ROOT / "_kho-am.json").read_text(encoding="utf-8"))
        except Exception:
            _CACHE = {}
    return _CACHE


def luu_cache():
    """Ghi _kho-am.json nếu có đo mới (lỗi ghi thì bỏ qua)."""
    global _BAN
    if _BAN and _CACHE is not None:
        try:
            ROOT.mkdir(parents=True, exist_ok=True)
            (ROOT / "_kho-am.json").write_text(json.dumps(_CACHE, ensure_ascii=False, indent=1), encoding="utf-8")
            _BAN = False
        except OSError:
            pass


def dac_tinh(f):
    """Đặc tính đo của 1 file: {dai, dinh_db, t_dinh, t_bat, tan_cong} hoặc None nếu file không đọc được. Đo 1 lần rồi nhớ."""
    global _BAN
    _dung_kho()
    if f in _DT:
        return _DT[f]
    row = _TRONG_GOI.get(f)
    if row and all(k in row for k in ("dai", "dinh_db", "t_dinh", "t_bat")):
        _DT[f] = {k: row[k] for k in ("dai", "dinh_db", "t_dinh", "t_bat", "tan_cong") if k in row}
        _DT[f].setdefault("tan_cong", round(max(0.0, row["t_dinh"] - row["t_bat"]), 3))
        return _DT[f]
    p = _duong(f)
    try:
        st = p.stat()
    except OSError:
        _DT[f] = None
        return None
    sig = [st.st_size, int(st.st_mtime)]
    c = _doc_cache().get(f)
    if c and c.get("sig") == sig and "t_dinh" in c:
        _DT[f] = {k: c[k] for k in ("dai", "dinh_db", "t_dinh", "t_bat", "tan_cong")}
        return _DT[f]
    import kho_nhac
    m = kho_nhac.do_am(p)
    _DT[f] = m
    if m:
        _doc_cache()[f] = {**m, "sig": sig}
        _BAN = True
    return m


def danh_muc(do_het=False):
    """Danh mục mọi âm dùng được: {file: {file, nhom, vai, mo_ta, goc, [dai, dinh_db, t_dinh, t_bat, tan_cong]}}.
    Chỉ gồm file thật sự tồn tại. do_het=True: đo luôn mọi file chưa có số đo (lâu lần đầu, rồi nhớ); file đo lỗi bị loại."""
    _dung_kho()
    out = {}
    for nhom, files in KHO.items():
        for f in files:
            row = _TRONG_GOI.get(f) or {}
            e = {"file": f, "nhom": nhom, "vai": VAI.get(nhom, "ui"), "goc": GOC.get(f, "cu"),
                 "mo_ta": row.get("mo_ta") or MO_TA_NHOM.get(nhom, ""), "ten": row.get("ten") or Path(f).stem}
            m = dac_tinh(f) if (do_het or f in _TRONG_GOI or f in _DT) else _DT.get(f)
            if do_het and m is None:
                continue
            if m:
                e.update(m)
            out[f"{nhom}|{f}"] = e
    if do_het:
        luu_cache()
    return out


def mo_ta_am():
    """{nhóm: mô tả 1 dòng tiếng Việt} cho các nhóm đang có file — prompt đạo diễn sinh từ đây. Thêm 'khong' = không có âm."""
    _dung_kho()
    out = {}
    for nhom in MO_TA_NHOM:
        files = KHO.get(nhom) or []
        if not files:
            continue
        moi = [f for f in files if GOC.get(f) != "cu"] or files
        durs = [(_TRONG_GOI.get(f) or _DT.get(f) or {}).get("dai") for f in moi]
        durs = [d for d in durs if d]
        out[nhom] = f"{MO_TA_NHOM[nhom]} [vai: {VAI.get(nhom, 'ui')}; {len(moi)} file" + (f", ~{sum(durs) / len(durs):.1f}s" if durs else "") + "]"
    out["khong"] = "Không có âm cho khối này (để thở)."
    return out


# ---------------------------------------------------------------- MỨC TỔNG + HẰNG SỐ LỊCH
# mức → (chỉnh âm lượng chung dB, số cử chỉ tối đa mỗi 10 s dưới giọng). Mức không đổi âm nào đi với hình nào.
MUC = {
    "gon":       (-2.0, 4),
    "vua":       (0.0, 6),
    "soi_dong":  (1.5, 8),
    "mo_dau_am": (1.0, 7),
}
ALIAS = {"em": "gon"}
KHOANG = 0.30       # 2 tiếng khác nhau gần hơn mức này thì bỏ tiếng ưu tiên thấp (kiem_am báo ngưỡng 0,25 s)
DONG_HO = 0.08      # tiếng trong 80 ms = 1 cử chỉ
TOI_DA_FILE = 2     # 1 file dùng tối đa 2 lần mỗi video (trừ tiếng gõ/tick hàng lặp)
CUM_NANG = 3        # nhát nặng ≤ 1/3 số cử chỉ
DONG_NHO = ("slide", "zoom", "smooth", "push", "wipe", "cover", "reveal")   # chuyển cảnh có chuyển động
GOC_NANG = ("hit",)


def la_chuyen_dong(ten):
    return bool(ten) and str(ten).lower().startswith(DONG_NHO)


def _sp(nhom, t, uu=2, ddb=0.0, ly="", neo=None, cum=None, lap=False, chinh=False, dai_max=None, nguon="khoi", ngan=False, cung=None):
    """1 âm dự kiến (chưa chọn file): t = giây mà ĐỈNH (nhát/vút) hoặc LÚC BẮT ĐẦU NGHE (tick/chuông...) phải rơi vào.
    cum: cả cụm tính 1 cử chỉ; lap: được dùng lại 1 file quá 2 lần; ngan: chỉ file ngắn (≤0,4 s); cung: các âm cùng khoá dùng CÙNG 1 file."""
    return {"nhom": [nhom] if isinstance(nhom, str) else list(nhom), "t": float(t), "uu": uu, "ddb": ddb, "ly_do": ly, "neo": neo,
            "cum": cum, "lap_ok": lap, "chinh": chinh, "dai_max": dai_max, "nguon": nguon, "ngan": ngan, "cung": cung}


def _go_may(b, t0, d, ctx, uu=1):
    """Tiếng gõ phím rải suốt lúc chữ hiện dần (không bao giờ nhát nặng)."""
    text = str(b.get("text") or "")
    cps = float(b.get("cps") or 48.0)                      # số chữ/giây của hiệu ứng gõ (Blocks.tsx: 1,6 chữ/khung)
    td = min(max(0.3, len(text) / cps if text else 0.8), max(0.3, d - 0.2), 3.0)
    n = max(3, min(14, round(td / 0.1) + 1))
    rng, out, t = ctx["rng"], [], t0 + 0.04
    cum = f"go{round(t0 * 100)}"
    for k in range(n):
        out.append(_sp("go_phim", t, uu, -1.5 * rng.random(), "chữ gõ máy → tiếng gõ phím rải suốt lúc gõ", "bat", cum, True, k == 0, 0.4, ngan=True))
        t += td / (n - 1) * (0.85 + 0.3 * rng.random())
    return out


def _khoi(b, ctx):
    """Âm DỰ KIẾN cho 1 khối chữ, theo nghĩa của khối (canh theo nhịp hoạt hình trong Blocks.tsx). Trả list _sp.
    b["am"] (tên nhóm | "khong") ghi đè; loại lạ → 1 tiếng bật rất nhẹ."""
    L = str(b.get("loai") or "")
    t0 = float(b["f0"]) / FPS
    d = max(0.1, (float(b.get("f1", b["f0"])) - float(b["f0"])) / FPS)
    ui = ctx.get("ui")
    S = lambda nhom, dt=0.0, **kw: _sp(nhom, t0 + dt, **kw)
    if "am" in b and b.get("am") is not None:
        am = str(b["am"]).strip().lower()
        if am in ("", "khong", "none", "im"):
            return []
        if am in KHO and KHO[am]:
            vai = VAI.get(am, "ui")
            if vai == "typing":
                return _go_may(b, t0, d, ctx)
            if vai == "riser":
                return [S(am, 0.0, uu=1, chinh=True, ly="đạo diễn chọn âm dâng dẫn vào khối")]
            return [S(am, 0.08 if vai in NEO_DINH else 0.05, uu=1, chinh=True, ly=f"đạo diễn chọn âm «{am}» cho khối")]
    if L == "hook_dap":
        return [S("dap", 0.08, uu=1, chinh=True, ly="chữ to đập vào màn hình → một nhát trầm đúng lúc chạm")]
    if L == "hook_tung_tu":
        return [S("vut_nhe", 0.12, uu=2, chinh=True, ly="từng chữ trượt vào → một tiếng lướt nhẹ")]
    if L == "hook_go_may":
        return _go_may(b, t0, d, ctx)
    if L == "hook_mat_na":
        return [S("vut_nhe", 0.15, uu=2, chinh=True, ly="thanh màu quét lộ chữ → lướt nhẹ, đỉnh lúc chữ lộ")]
    if L in ("hook_bang", "lower_third", "dai_chay", "mui_ten_chi"):
        return [S("vut_nhe", 0.15, uu=2, chinh=True, ly="thẻ/băng trượt vào → lướt nhẹ, đỉnh lúc tới nơi")]
    if L == "hook_tem":
        return [S(["con_dau", "dap"], 0.12, uu=1, chinh=True, neo="dinh", ly="tem đóng xuống → tiếng đóng dấu/thịch, không phải màn trập")]
    if L == "hook_hoi":
        return [S(ui, 0.05, uu=2, chinh=True, ly="bong bóng câu hỏi hiện → một tiếng bật nhẹ")] if ui else []
    if L == "checklist":
        n = int(b.get("n") or 3)
        gap = max(6, int(d * FPS * 0.7 / max(1, n))) / FPS
        cum = f"hang{round(t0 * 100)}"
        return [S(ui, 4 / FPS + k * gap, uu=2, lap=True, chinh=(k == 0), cum=cum, cung=cum, ly="mỗi dòng danh sách hiện → cùng một tiếng tách")
                for k in range(min(4, n))] if ui else []
    if L == "so_dem":
        out = [S("ting", 26 / FPS, uu=1, chinh=True, neo="bat", ly="số đếm dừng → một tiếng ting")]
        if ui:
            out.insert(0, S(ui, 4 / FPS, uu=2, ly="số bắt đầu đếm → một tiếng tách"))
        return out
    if L == "so_sanh":
        out = [S("dung", 0.40, uu=1, chinh=True, ly="cột ✓ hiện → chuông lên nhẹ")]
        if ui:
            out.insert(0, S(ui, 0.06, uu=2, ly="cột ✗ hiện → một tiếng tách"))
        return out
    if L == "vong_tron":
        return [S(["but_viet", "vut_nhe"], 0.0, uu=2, chinh=True, dai_max=0.7, ly="vẽ vòng quanh sản phẩm → tiếng bút khoanh")]
    if L == "da_quang":
        return [S(["but_viet", "vut_nhe"], 0.05, uu=2, chinh=True, dai_max=0.5, ddb=-2, ly="bút dạ quang kéo qua chữ → tiếng bút")]
    if L == "nhan_dan":
        return [S(ui, 0.05, uu=2, chinh=True, ly="nhãn dán bật ra → một tiếng bật nhẹ")] if ui else []
    if L == "bong_chu":
        return [S("lap_lanh", 0.10, uu=2, chinh=True, ly="chữ nổ kèm sao → một tiếng lấp lánh")]
    if L == "canh_bao":
        return [S("sai", 0.05, uu=1, chinh=True, ly="băng cảnh báo → âm báo trầm, không phải chuông thanh toán")]
    if L == "hop_qua":
        return [S("lap_lanh", 0.20, uu=1, chinh=True, ly="hộp quà bật nắp → MỘT tiếng lấp lánh")]
    if L == "bang_qua":
        return [S("vut_nhe", 0.10, uu=2, chinh=True, ly="bảng quà trượt xuống → lướt nhẹ")]
    if L == "the_qua":
        return [S("ting", 0.05, uu=1, chinh=True, neo="bat", ly="thẻ quà hiện → MỘT tiếng ting")]
    if L == "nut_gio_hang":
        return [_sp("tien", float(b.get("t_am") or t0 + 0.02), 1, 1.0, "nút giỏ hàng → tiếng tính tiền đúng lúc nói từ chốt", "bat", chinh=True)]
    # Loại lạ (khối mới chưa có ánh xạ): một tiếng bật rất nhẹ, ưu tiên thấp (bị bỏ đầu tiên khi dày), không bao giờ lỗi.
    if re.search(r"go_may|go_chu|typewriter|typing", L):
        return _go_may(b, t0, d, ctx)
    return [S(ui, 0.05, uu=4, ddb=-2.0, chinh=True, ly=f"khối «{L or '?'}» chưa có ánh xạ riêng → tiếng bật rất nhẹ")] if ui else []


# ---------------------------------------------------------------- LỌC
def _don_vi(sp):
    return sp["cum"] if sp.get("cum") else id(sp)


def _cu_chi(ev):
    """Gộp thành cử chỉ: cùng cum = 1; tiếng cách nhau ≤ DONG_HO = 1. Trả list (t, [sp...])."""
    nhom = {}
    for x in sorted(ev, key=lambda x: x["t"]):
        nhom.setdefault(_don_vi(x), []).append(x)
    gs = sorted(((v[0]["t"], v) for v in nhom.values()), key=lambda g: g[0])
    out = []
    for t, v in gs:
        if out and t - out[-1][0] <= DONG_HO:
            out[-1][1].extend(v)
        else:
            out.append((t, list(v)))
    return out


def _loc_khoang(ev):
    """Tiếng ưu tiên thấp nằm sát tiếng ưu tiên cao hơn (khác họ, < KHOANG) thì bỏ. Cùng cum (gõ/lật) thì không tính với nhau."""
    keep = []
    for x in sorted(ev, key=lambda x: (x["uu"], x["t"])):
        if any(abs(x["t"] - y["t"]) < KHOANG and not (x["cum"] and x["cum"] == y["cum"]) for y in keep):
            continue
        keep.append(x)
    return keep


def _loc_mat_do(ev, toi_da, cua_so=10.0):
    """Mật độ cử chỉ: mỗi cửa sổ cua_so s có tối đa `toi_da` cử chỉ; bỏ cử chỉ ưu tiên thấp nhất (rồi muộn nhất) trước."""
    ev = list(ev)
    while True:
        gs = _cu_chi(ev)
        xau = None
        for t, _ in gs:
            trong = [g for g in gs if t <= g[0] < t + cua_so]
            if len(trong) > toi_da:
                xau = trong
                break
        if not xau:
            return ev
        dich = max(xau, key=lambda g: (max(x["uu"] for x in g[1]), g[0]))
        gone = {id(x) for x in dich[1]}
        ev = [x for x in ev if id(x) not in gone]


def _loc_nang(ev):
    """Nhát nặng (vai hit) ≤ 1/3 số cử chỉ (tối thiểu 1): bỏ nhát ưu tiên thấp/muộn dư ra."""
    ev = list(ev)
    while True:
        gs = _cu_chi(ev)
        nang = [x for x in ev if VAI.get(x["nhom"][0]) in GOC_NANG]
        if len(nang) <= max(1, len(gs) // CUM_NANG):
            return ev
        x = max(nang, key=lambda x: (x["uu"], x["t"]))
        ev = [y for y in ev if y is not x]


# ---------------------------------------------------------------- CHỌN FILE
def _chon_file(nhoms, used, rng, lap=False, ngan=False, tranh=None, giu=None):
    """Chọn (nhóm, file) theo thứ tự nhóm ưu tiên: file mới/người dùng trước (nhóm có file mới thì không dùng file cũ);
    file dùng ít nhất trước; mỗi file tối đa TOI_DA_FILE lần (trừ lap). Hết thì thử nhóm kế, không còn thì (None, None)."""
    for nhom in nhoms:
        pool = KHO.get(nhom) or []
        cands = [f for f in pool if GOC.get(f) != "cu"] or pool
        if giu and giu in pool:
            return nhom, giu
        if ngan:
            ng = [f for f in cands if (dac_tinh(f) or {}).get("dai", 9) <= 0.4]
            cands = ng or cands
        if not lap:
            cands = [f for f in cands if used.get(f, 0) < TOI_DA_FILE]
        if tranh and len(cands) > 1:
            cands = [f for f in cands if f != tranh] or cands
        if cands:
            m = min(used.get(f, 0) for f in cands)
            return nhom, rng.choice([f for f in cands if used.get(f, 0) == m])
    return None, None


def _lat_trang(lat, uu=4):
    """Cụm lật trang: tick nhẹ, tối đa 8, cách nhau ≥ 0,16 s; cả cụm = 1 cử chỉ (cùng cum)."""
    ts = sorted(float(t) for t in lat if t is not None)
    cum, out, last = f"lat{round(ts[0] * 100)}" if ts else "lat", [], -9.0
    for t in ts:
        if t - last >= 0.16 and len(out) < 8:
            out.append(t)
            last = t
    return out, cum


def len_lich(muc, blocks, cuts, total, rng, pops=None, trans="fade", *, am_mo=None, st=None, chuyen_tung_cat=None, lat_trang=None):
    """Lịch SFX theo nghĩa. Tham số vị trí giữ nguyên như trước.
    am_mo: tên nhóm âm mở đầu do đạo diễn chọn | "khong" (cũng đọc từ st["am_mo"] nếu truyền st).
    chuyen_tung_cat: tên chuyển cảnh TỪNG điểm cắt (cùng thứ tự cuts) — cần khi trans == "hon_hop" (không có thì hon_hop im lặng).
    lat_trang: [[giây lật, ...], ...] các cụm lật trang montage (hoặc phần tử {"lat": [...]} trong pops).
    Mỗi khối trong blocks có thể thêm: "am" (nhóm | "khong"), "text", "cps", "t_am" (giây từ chốt)."""
    _dung_kho()
    muc = ALIAS.get(muc, muc)
    muc = muc if muc in MUC else "vua"
    off_db, toi_da10 = MUC[muc]
    if am_mo is None and st:
        am_mo = st.get("am_mo")
    am_mo = str(am_mo).strip().lower() if am_mo else None
    total = float(total or 0)
    # 1 họ UI cho cả video (chọn 1 lần), hàng danh sách dùng 1 file
    ui_ds = [f for f in HO_UI if KHO.get(f)] or [f for f in ("thong_bao",) if KHO.get(f)]
    ui = rng.choice(ui_ds) if ui_ds else None
    ctx = {"rng": rng, "ui": ui}
    sp = []
    # --- âm mở đầu do đạo diễn chọn
    bl = []
    for b in blocks or []:
        try:
            float(b["f0"]); bl.append(b)
        except (KeyError, TypeError, ValueError):
            continue
    t_mo = 0.10 if not bl or bl[0]["f0"] / FPS < 0.5 else bl[0]["f0"] / FPS + 0.08
    if am_mo and am_mo != "khong" and KHO.get(am_mo):
        vai = VAI.get(am_mo, "ui")
        sp.append(_sp(am_mo, t_mo + (0.0 if vai in NEO_DINH else -0.05), 0, 0.0, f"đạo diễn chọn âm mở «{am_mo}»", chinh=True, nguon="mo"))
    # --- khối chữ
    for i, b in enumerate(bl):
        try:
            xs = _khoi(b, ctx)
        except Exception as e:                                     # khối hỏng không được làm sập cả lịch
            print("  SFX khối lỗi:", b.get("loai"), str(e)[:80])
            xs = []
        for x in xs:
            x["khoi"] = i
            x["tu_dong"] = "am" not in b or b.get("am") is None
            if x["chinh"] and i in (0, len(bl) - 1):
                x["uu"] = 0
        if i == 0 and am_mo:                                      # đạo diễn đã quyết âm mở (hoặc "khong") → bỏ nhát/vút TỰ ĐỘNG sát đầu khối đầu
            xs = [x for x in xs if not (x["tu_dong"] and x["t"] < 1.0 and VAI.get(x["nhom"][0]) in NEO_DINH)]
        sp += xs
    # --- ô hình bật vào + lật trang
    lats = [list(p["lat"]) for p in (pops or []) if isinstance(p, dict) and p.get("lat")] + [list(l) for l in (lat_trang or []) if l]
    flat = sorted(float(p) for p in (pops or []) if isinstance(p, (int, float)))
    gop = []
    for t in flat:
        if not gop or t - gop[-1] > 0.12:                           # ô cùng bố cục vào cùng lúc = 1 tiếng
            gop.append(t)
    if ui:
        for t in gop:
            sp.append(_sp(ui, t, 4, -1.0, "ô hình bật vào → một tiếng tách nhẹ", nguon="pop"))
        for lat in lats:
            ts, cum = _lat_trang(lat)
            for k, t in enumerate(ts):
                sp.append(_sp(ui, t, 4, -2.0, "lật trang montage → tick nhẹ từng trang", "bat", cum, True, k == 0, 0.3, "lat", ngan=True))
    # --- chuyển cảnh: chỉ khi thật sự chuyển động
    for k, c in enumerate(cuts or []):
        ten = chuyen_tung_cat[k] if chuyen_tung_cat and k < len(chuyen_tung_cat) else trans
        if la_chuyen_dong(ten) and 0.3 < c < total - 1.0:
            sp.append(_sp("vut_nhe", c + 0.14, 3, 0.0, f"chuyển cảnh «{ten}» có chuyển động → lướt nhẹ, đỉnh giữa lúc chuyển", nguon="chuyen"))
    # --- lọc theo ưu tiên
    for x in sp:                                                  # chỉ giữ nhóm đang có file; không nhóm nào có thì bỏ tiếng đó trước khi lọc
        x["nhom"] = [n for n in x["nhom"] if n and KHO.get(n)]
    sp = [x for x in sp if x["nhom"] and 0 <= x["t"] < max(total, 0.1)]
    sp = _loc_khoang(sp)
    sp = _loc_mat_do(sp, max(2, math.ceil(toi_da10 * min(10.0, max(total, 1.0)) / 10.0)))
    sp = _loc_nang(sp)
    # --- chọn file, đặt đúng mốc, đưa về mức theo vai
    used, ev, truoc, cung = {}, [], {}, {}
    for x in sorted(sp, key=lambda x: (x["uu"], x["t"])):
        lap = x["lap_ok"]
        fam, f = _chon_file(x["nhom"], used, rng, lap, x["ngan"], truoc.get(x["cum"]) if x["cum"] and not x["cung"] else None,
                            cung.get(x["cung"]) if x["cung"] else None)
        if not f:
            continue
        m = dac_tinh(f)
        if not m:
            continue
        used[f] = used.get(f, 0) + 1
        if x["cum"]:
            truoc[x["cum"]] = f
        if x["cung"]:
            cung[x["cung"]] = f
        vai = VAI.get(fam, "ui")
        neo = x["neo"] or ("dinh" if vai in NEO_DINH else "bat")
        lech = m["t_dinh"] if neo == "dinh" else m["t_bat"]
        t_phat = max(0.0, x["t"] - lech)
        db = VAI_DB.get(vai, -16.0) + off_db + x["ddb"]
        dai = min(2.0, m["dai"] + 0.05)
        if x["dai_max"]:
            dai = min(dai, x["dai_max"])
        e = {"nhom": fam, "file": f, "t": round(t_phat, 3), "db": round(db, 2), "dai": round(dai, 3), "uu": x["uu"],
             "gain": round(db - m["dinh_db"], 2), "vai": vai, "t_neo": round(x["t"], 3), "ly_do": x["ly_do"], "lap_ok": lap,
             "nguon": x["nguon"]}
        if x["cum"]:
            e["cum"] = x["cum"]
        ev.append(e)
    luu_cache()
    return sorted(ev, key=lambda e: e["t"])


def tom_tat(ev):
    return ", ".join(f"{x['nhom']}@{x['t']:.1f}" for x in ev)


def tron_lenh(ev, first_input, voice_label, out_label, total):
    """Trả (đối số -i, các đoạn filter) để trộn SFX vào nhãn âm [voice_label] → [out_label]."""
    args, fc, labels = [], [], []
    for k, x in enumerate(ev):
        idx = first_input + k
        if x.get("start"):
            args += ["-ss", str(x["start"])]
        args += ["-i", str(ROOT / x["file"])]
        ms = int(x["t"] * 1000)
        dai = max(0.05, min(x["dai"], total - x["t"]))
        fin = f"afade=t=in:d={x['fade_in']}," if x.get("fade_in") else ""
        fo = min(0.25, dai * 0.4)                                   # tiếng ngắn (tick) thì tắt nhanh theo độ dài, không nuốt mất đỉnh
        fc.append(f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:{dai:.3f},asetpts=PTS-STARTPTS,{fin}"
                  f"afade=t=out:st={max(0.0, dai - fo):.3f}:d={fo:.3f},volume={x['gain']}dB,adelay={ms}|{ms}[s{k}]")
        labels.append(f"[s{k}]")
    if not ev:
        fc.append(f"[{voice_label}]anull[{out_label}]")
        return args, fc
    fc.append(f"[{voice_label}]aformat=sample_rates=44100:channel_layouts=stereo[vv]")
    fc.append(f"[vv]{''.join(labels)}amix=inputs={len(ev) + 1}:duration=first:normalize=0,alimiter=limit=0.84:level=0[{out_label}]")
    return args, fc


def tron_am(base, ev, out_audio, total):
    """Trộn SFX vào tiếng của video nền → 1 file âm riêng (tách khỏi bước ghép hình để FFmpeg nhẹ, không sập)."""
    a_args, a_fc = tron_lenh(ev, 1, "0:a", "a", total)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base), *a_args, "-filter_complex", ";".join(a_fc), "-map", "[a]",
                    "-c:a", "aac", "-b:a", "192k", str(out_audio)], check=True)
    return out_audio

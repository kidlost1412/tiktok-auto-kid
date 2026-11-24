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
       "con_dau": "foley", "but_viet": "foley", "phun_suong": "foley", "nuoc": "foley", "rit_dia": "scratch"}
# 23/11 (bọ trĩ v10 Kid duyệt): tiếng nhấn phải NGHE RÕ trên giọng (v6 "gần như không nghe"), nhưng không trầm đè thoại.
# Mức cũ (ui −16, gõ −18, foley −14…) chìm dưới giọng −14 LUFS → nâng ~3 dB; nhát trầm "hit" hạ vì chữ đập giờ dùng flash máy ảnh.
# 23/11 bản mẫu edit chính → Kid: "tiếng vẫn hơi nhỏ, bị nhạc nền đè" → +2 dB nữa; nhạc nền tự né khi có tiếng (tron_am).
# Tầng: nhấn mạnh (hook, chữ đập, số, giỏ hàng) to; tách/gõ vừa; tiếng lấp chỗ (từ nhấn trong phụ đề) nhỏ hơn 3 dB (_lap_cho).
VAI_DB = {"hit": -6.0, "whoosh": -9.0, "foley": -8.0, "riser": -11.0, "bell": -10.0, "magic": -10.0, "ui": -11.0, "typing": -13.0,
          "money": -7.0, "alert": -10.0, "crowd": -16.0, "ambience": -24.0, "scratch": -6.0}
NEO_DINH = ("hit", "whoosh", "riser")        # các vai canh theo ĐỈNH to nhất (còn lại canh theo lúc bắt đầu nghe thấy)
HO_UI = ("tick", "bop")                      # họ âm UI để chọn 1 lần mỗi video

MO_TA_NHOM = {   # 1 dòng: nghe như thế nào + hợp khi nào (prompt đạo diễn sinh từ đây qua mo_ta_am())
    "rit_dia": "Rít đĩa than ngắn, khô, giật tai; CHỈ khi lời mở là tương phản / bất ngờ / câu hỏi ('Cùng là…', 'Tưởng…', 'Ai ngờ…').",
    "dap": "Nhát trầm như vật nặng đặt xuống; RẤT ít, chỉ ở khoảng lặng không có lời (trầm đè lên lời thì nghe không rõ thoại).",
    "no_lon": "Tiếng nổ/boom điện ảnh rất nặng; gần như không dùng, chỉ khi hình thật sự bùng nổ.",
    "vut_nhe": "Tiếng lướt gió ngắn, nhẹ; hợp thẻ/băng chữ trượt vào hoặc chuyển cảnh trượt.",
    "vut_manh": "Tiếng vút nhanh, mạnh hơn; hợp chữ quét ra dứt khoát hoặc chuyển cảnh zoom/trượt nhanh.",
    "roi_phep": "Tiếng vút ma thuật dâng lên; hợp hé lộ điều bất ngờ.",
    "keo_len": "Tiếng gió dâng dần tới đỉnh rồi dứt; hợp dồn vào khoảnh khắc chốt (đỉnh rơi đúng lúc hiện chữ).",
    "bop": "Tiếng bật/bấm nhẹ như bong bóng hoặc nút bấm; hợp ô hình hiện ra, bong bóng câu hỏi, nhãn dán.",
    "tick": "Tiếng tách giao diện rất ngắn, sạch; hợp từng dòng danh sách, số bắt đầu đếm, ô hiện ra.",
    "thong_bao": "Tiếng báo tin nhắn ứng dụng; hợp câu mở kiểu 'có tin mới', bình luận, thông báo đơn.",
    "go_phim": "Tiếng gõ phím (phím cơ, máy đánh chữ — nhiều chất); hợp chữ gõ máy hiện dần (rải đều suốt lúc gõ).",
    "chup": "Flash / màn trập máy ảnh; CHỈ khi hình thật sự lóe trắng, chụp ảnh, ảnh lật ra (hook flash, trước/sau).",
    "ting": "Tiếng chuông 'ting' sáng, ngắn; hợp số vừa dừng, ý chính vừa hiện, điểm nhấn tích cực.",
    "lap_lanh": "Tiếng lấp lánh; hợp hé lộ sản phẩm, quà tặng, chữ nổ kèm sao.",
    "dung": "Chuông lên dần cao độ báo 'đúng/được'; hợp cột ✓ hiện ra, bước hoàn thành.",
    "sai": "Còi báo sai; CHỈ khi lời nêu rõ cái sai / cách làm sai ('sai', 'lỗi', 'đừng', 'nhầm', 'phí'), tối đa 1 lần mỗi video.",
    "tien": "Tiếng tính tiền / đồng xu leng keng; hợp nút giỏ hàng, bảng quà, giá — đúng lúc nói từ chốt.",
    "tui_qua": "Tiếng túi tiền rơi; hợp khoảnh khắc nhận quà, giảm giá lớn.",
    "vo_tay": "Tiếng vỗ tay nhỏ; hợp chốt thắng lợi, dùng rất ít.",
    "nen_vuon": "Tiếng nền vườn, chim, gió; chỉ làm nền êm, không làm điểm nhấn.",
    "con_dau": "Tiếng đóng dấu cao su gọn, chắc; hợp tem/dấu xác nhận hiện ra.",
    "but_viet": "Tiếng bút viết nguệch ngoạc ngắn; hợp vòng khoanh, gạch chân, bút dạ quang vẽ trên hình.",
    "phun_suong": "Tiếng xì phun sương; hợp cảnh phun thuốc/nước lên cây, tay đang xịt.",
    "nuoc": "Giọt nước nhỏ; hợp cảnh giọt nước, tưới, nhỏ thuốc.",
}

def _bi_cam(f):
    return any(c in str(f).replace("\\", "/") for c in CAM)


KHO = {k: list(v) for k, v in KHO_MAC_DINH.items()}     # _dung_kho()/dung_lai() lọc CAM
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
    KHO, GOC, _TRONG_GOI, _KHO_XONG, _DT, _CACHE, _BAN = {k: [f for f in v if not _bi_cam(f)] for k, v in KHO_MAC_DINH.items()}, {}, {}, False, {}, None, False


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
            if not _bi_cam(r) and (ROOT / r).exists():
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
                    if _bi_cam(p) or not p.exists():
                        continue
                    f = str(p)
                    _TRONG_GOI[f] = row
                    kho.setdefault(row["nhom"], []).append(f)
                    GOC[f] = "moi"
                except (KeyError, TypeError):
                    continue
        for f, nhoms in kho_nhac.sfx_phu():
            if _bi_cam(f):
                continue
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
        if not files or nhom in AN_KHOI_DAO_DIEN:
            continue
        moi = [f for f in files if GOC.get(f) != "cu"] or files
        durs = [(_TRONG_GOI.get(f) or _DT.get(f) or {}).get("dai") for f in moi]
        durs = [d for d in durs if d]
        out[nhom] = f"{MO_TA_NHOM[nhom]} [vai: {VAI.get(nhom, 'ui')}; {len(moi)} file" + (f", ~{sum(durs) / len(durs):.1f}s" if durs else "") + "]"
    out["khong"] = "Không có âm cho khối này (để thở)."
    return out


# ---------------------------------------------------------------- MỨC TỔNG + HẰNG SỐ LỊCH
# mức → (chỉnh âm lượng chung dB, số cử chỉ tối đa mỗi 10 s dưới giọng). Mức không đổi âm nào đi với hình nào.
# 23/11 Kid: "chữ mạnh, chữ dậm phải có tiếng; tầm 20, 25 vẫn được" (video ~20 s) → trần cũ 4/6/8 bỏ mất nhiều tiếng chữ.
MUC = {
    "gon":       (-2.0, 6),
    "vua":       (0.0, 10),     # 23/11 Kid "ép dày gần v10" (v10: 20 tiếng / 21 s)
    "soi_dong":  (1.5, 12),
    "mo_dau_am": (1.0, 10),
}
NANG = ("dap", "no_lon", "ting", "lap_lanh", "tien", "chup", "sai")   # chỉ file đóng gói mới (file cũ: màn trập 9 kHz, còi meme)   # nhóm trầm/nổ: chỉ dùng file đóng gói mới (kho cũ nhiều boom); nhóm khác trộn cả kho cũ để đa dạng
CAM = (   # file KHÔNG BAO GIỜ vào kho (đo 24/11: tâm phổ = Hz, hf = % năng lượng trên 4 kHz)
    "anvil", "transition-windy",   # Kid nghe và chê (đe kim loại chỉ có 1 kênh chói tai; vút gió "rất khó chịu")
    "meme/",                       # còi sai, vỗ tay, đáp án đúng kiểu game show: sai giọng quảng cáo nông sản
    "vine-boom", "capcut-explosion", "metal-explosion",          # boom meme / nổ phim hành động
    "typewriter",                  # máy đánh chữ 5,6–6,8 kHz chói (tick phím cơ 2,7–4,2 kHz thay)
    "fast-sweep-transition", "flying-fast-swoosh",               # vút 6,4–7,2 kHz, flatness 0,45–0,55 = "rè rè"
    "crystal-chime", "fairy-arcade-sparkle", "sparkle-hybrid",   # lấp lánh/chuông 8–11 kHz the thé
    "magic-sparkle-shine-ding", "bell-change-money-ding",        # ting/xèng 8,5–9 kHz, 97–100% năng lượng trên 4 kHz
    "clinking-coins", "gold-coin-prize", "money-bag-drop",       # tiền xu 10–12 kHz
    "ui-flint-twin-tick",          # tách bật lửa 8,6 kHz, flatness 0,7
    "short-sci-fi-swell",          # swell 11,6 kHz, lệch kênh 7 dB
)
# Nhóm âm bị cấm tự động (màn trập / còi sai / nổ meme) → âm thay thế khi đạo diễn hay dữ liệu cũ vẫn gọi tên nhóm đó
THAY = {"no_lon": "dap", "vo_tay": ""}     # "" = bỏ lời gọi, quay về ánh xạ mặc định theo loại khối
AN_KHOI_DAO_DIEN = ("no_lon", "vo_tay")                                   # không mời đạo diễn chọn những nhóm này nữa
# 24/11 chủ hàng: màn trập / còi sai KHÔNG tệ, chỉ dùng sai chỗ → trả lại nhưng chỉ ở đúng nghĩa (xem _khoi: flash trắng, lỗi nêu rõ)
SAI_LOI = re.compile(r"(?<!\w)(sai|lỗi|đừng|không nên|nhầm|phí|tốn)(?!\w)", re.I)   # lời nêu cái sai/cách làm sai → mới được còi sai
TUONG_PHAN = re.compile(r"(?<!\w)(cùng là|tưởng|ai ngờ|vậy mà|thế mà|hóa ra|không ngờ)(?!\w)|\?", re.I)   # lời mở tương phản / bất ngờ / câu hỏi
CO_SO = re.compile(r"\d|(?<!\w)(nghìn|ngàn|triệu|giá|đồng)(?!\w)", re.I)         # lời mở bằng con số / giá
GIONG_MAC_DINH = 0.20           # không biết giờ từ đầu tiên: giả định giọng vào ~0,2 s


def _mo_dau(loi_dau, rng, co):
    """Âm mở video khi đạo diễn không chọn: chọn từ thực đơn nhỏ THEO NGHĨA lời mở + rng (không một âm cố định cho mọi video).
    Trả (nhóm|None, t_đỉnh, ddb, dinh_max). co(nhóm) → còn file không."""
    t = (loi_dau or "").lower()[:80]
    if TUONG_PHAN.search(t):
        menu = [("rit_dia", 3), ("dap", 2), ("vut_nhe", 1)]        # rít đĩa CHỈ khi lời mở là tương phản / bất ngờ / câu hỏi
    elif CO_SO.search(t):
        menu = [("ting", 3), ("dap", 2), ("khong", 1)]             # mở bằng số/giá → chuông
    else:
        menu = [("dap", 3), ("vut_nhe", 2), ("khong", 2)]          # boom trầm nhẹ / lướt vào / đôi khi im
    menu = [(n, w) for n, w in menu if n == "khong" or co(n)]
    if not menu:
        return None, 0.05, 0.0, None
    nhom = rng.choices([n for n, _ in menu], [w for _, w in menu])[0]
    if nhom == "khong":
        return None, 0.05, 0.0, None
    if nhom == "dap":
        return nhom, 0.05, -5.0, 0.2           # boom: file đuôi ngắn, hạ ~5 dB (thêm nữa nếu đuôi chạm lời, xem len_lich)
    if nhom == "vut_nhe":
        return nhom, 0.30, 0.0, None
    return nhom, 0.05, 0.0, None
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

    def sai_duoc(can_warn=True):     # còi sai: chỉ lời nêu cái sai, tối đa 1 lần/video, có sẵn file
        if (can_warn and SAI_LOI.search(str(b.get("text") or ""))) and ctx.get("n_sai", 0) < 1 and KHO.get("sai"):
            ctx["n_sai"] = ctx.get("n_sai", 0) + 1
            return True
        return False
    if "am" in b and b.get("am") is not None:
        am = str(b["am"]).strip().lower()
        if am in ("", "khong", "none", "im"):
            return []
        am = THAY.get(am, am) or "?"
        if am in KHO and KHO[am]:
            vai = VAI.get(am, "ui")
            if vai == "typing":
                return _go_may(b, t0, d, ctx)
            if vai == "riser":
                return [S(am, 0.0, uu=1, chinh=True, ly="đạo diễn chọn âm dâng dẫn vào khối")]
            return [S(am, 0.08 if vai in NEO_DINH else 0.05, uu=1, chinh=True, ly=f"đạo diễn chọn âm «{am}» cho khối")]
    if L == "hook_dap":   # 23/11 Kid (v4→v10): nhát trầm đè lời nghe không rõ thoại → chữ đập = flash máy ảnh gọn, giòn
        return [S(["dap", "bop"], 0.08, uu=1, ddb=-3, chinh=True, neo="bat", dai_max=0.5, ly="chữ to đập vào màn hình → một nhát trầm nhẹ, ngắn đúng lúc chạm")]
    if L == "hook_tung_tu":
        return [S("vut_nhe", 0.12, uu=2, chinh=True, ly="từng chữ trượt vào → một tiếng lướt nhẹ")]
    if L == "hook_go_may":
        return _go_may(b, t0, d, ctx)
    if L == "hook_mat_na":
        return [S("vut_nhe", 0.15, uu=2, chinh=True, ly="thanh màu quét lộ chữ → lướt nhẹ, đỉnh lúc chữ lộ")]
    if L in ("hook_bang", "lower_third", "dai_chay", "mui_ten_chi"):
        return [S("vut_nhe", 0.15, uu=2, chinh=True, ly="thẻ/băng trượt vào → lướt nhẹ, đỉnh lúc tới nơi")]
    if L in ("anh_chup", "polaroid", "truoc_sau"):
        return [S("chup", 0.05, uu=1, chinh=True, neo="bat", ly="ảnh chụp / trước-sau lật ra → flash máy ảnh")]
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
        if sai_duoc():
            return [S("sai", 0.05, uu=1, chinh=True, dai_max=0.7, ly="băng cảnh báo nêu cái sai → còi sai (1 lần/video)")]
        return [S(["dap", "thong_bao"], 0.05, uu=1, ddb=-3, chinh=True, dai_max=0.5, ly="băng cảnh báo → nhát trầm nhẹ (không còi sai, không chuông thanh toán)")]
    if L == "hop_qua":
        return [S("lap_lanh", 0.20, uu=1, chinh=True, ly="hộp quà bật nắp → MỘT tiếng lấp lánh")]
    if L == "bang_qua":
        return [S("vut_nhe", 0.10, uu=2, chinh=True, ly="bảng quà trượt xuống → lướt nhẹ")]
    if L == "the_qua":
        return [S("ting", 0.05, uu=1, chinh=True, neo="bat", ly="thẻ quà hiện → MỘT tiếng ting")]
    if L == "nut_gio_hang":
        return [_sp("tien", float(b.get("t_am") or t0 + 0.02), 1, 1.0, "nút giỏ hàng → tiếng tính tiền đúng lúc nói từ chốt", "bat", chinh=True)]
    if L.startswith("loi_"):     # khung "chữ theo lời" (v10 Kid duyệt): tiếng theo NGHĨA + kiểu hiện, mốc = lúc từ chính hiện
        vai, deco, so = b.get("vai"), b.get("deco"), bool(re.search(r"\d", str(b.get("text") or "")))
        if L.startswith("loi_hook_"):            # rít đĩa mở ở 0 s → tiếng chữ khổng lồ rơi đúng lúc chữ đứng hẳn
            if L.endswith("flicker"):
                return [S(["dap", "lap_lanh"], 0.30, uu=0, ddb=-3, chinh=True, neo="bat", dai_max=0.5, ly="chữ khổng lồ chớp xong, đứng hẳn → nhát trầm nhẹ")]
            if L.endswith("flash"):
                return [S(["chup", "lap_lanh", "ting"], 0.07, uu=0, chinh=True, neo="bat", ly="chữ hook bật kèm nháy trắng → flash máy ảnh đúng lúc chớp")]
            return [S(["lap_lanh", "ting"] if L.endswith("flash") else ["dap", "con_dau"], 0.07, uu=0, ddb=0 if L.endswith("flash") else -3, chinh=True, neo="bat",
                      dai_max=None if L.endswith("flash") else 0.5,
                      ly="chữ khổng lồ hook bật ra → một tiếng đúng lúc chữ chạm")]
        if L == "loi_khep":
            return [S(["ting", "lap_lanh"], 0.05, uu=2, chinh=True, neo="bat", ly="hết lời → chuông khép video")]
        if vai == "brand":
            return [S("roi_phep", 0.0, uu=1, chinh=True, ly="tên hàng hiện → vút phép dâng (chỉ ở tên hàng)")]
        if L == "loi_type":                      # 23/11 Kid: gõ chữ phải là tiếng GÕ PHÍM rải theo từng chữ cái, không phải một tiếng click
            return _go_may(dict(b, cps=30.0), t0, d, ctx, uu=1 if so else 2)
        if deco == "shake":
            if sai_duoc():
                return [S("sai", 0.25, uu=1, chinh=True, dai_max=0.7, ly="chữ nêu cái sai lắc → còi sai (1 lần/video)")]
            return [S("dap", 0.25, uu=1, ddb=-3, chinh=True, dai_max=0.5, ly="cái xấu lắc chữ → nhát trầm nhẹ (không còi sai)")]
        con_ding = ctx.get("n_dung", 0) < 2         # ding báo đúng ≤ 2 lần/video (lặp nhiều thành quê — Kid 23/11)
        if deco == "under" and con_ding:
            ctx["n_dung"] = ctx.get("n_dung", 0) + 1
            return [S(["dung", "ting"], 0.22, uu=1, chinh=True, neo="bat", ly="gạch chân giá trị vẽ xong → ding báo đúng")]
        if L == "loi_slam":
            if vai == "res" and con_ding:
                ctx["n_dung"] = ctx.get("n_dung", 0) + 1
                return [S(["dung", "ting"], 0.04, uu=1, chinh=True, neo="bat", ly="kết quả tốt đập vào → ding báo đúng")]
            if vai == "warn" and sai_duoc():
                return [S("sai", 0.04, uu=1, chinh=True, neo="bat", dai_max=0.7, ly="chữ cảnh báo nêu cái sai / cách làm sai đập vào → còi sai (1 lần/video)")]
            if so or vai == "warn":     # con số / cái xấu đập vào: nhát trầm nhẹ (≤ 1/3 số cử chỉ)
                return [S(["dap", ui or "tick"], 0.04, uu=1, ddb=-3, chinh=True, neo="bat", dai_max=0.5, ly="con số / cái xấu đập vào → nhát trầm nhẹ đúng lúc chạm")]
            return [S([ui or "tick", "bop"], 0.04, uu=2, ddb=-1, chinh=True, neo="bat", ly="từ chính đập vào → một tiếng tách nhẹ (ưu tiên thấp)")]
        return []                                # trồi lên (fade): để im cho có nhịp thở — v10 không gắn tiếng cho chữ trồi
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
    """Nhát nặng (vai hit) ≤ 1/3 số cử chỉ (tối thiểu 1): nhát ưu tiên thấp/muộn dư ra thì hạ xuống âm nhẹ dự phòng (không có thì bỏ)."""
    ev = list(ev)
    while True:
        gs = _cu_chi(ev)
        nang = [x for x in ev if VAI.get(x["nhom"][0]) in GOC_NANG]
        if len(nang) <= max(1, len(gs) // CUM_NANG):
            return ev
        x = max(nang, key=lambda x: (x["uu"], x["t"]))
        nhe = [n for n in x["nhom"] if VAI.get(n) not in GOC_NANG]
        if nhe:                                   # nhát nặng dư → hạ xuống tiếng nhẹ dự phòng (tách/chuông...) thay vì im hẳn
            x["nhom"], x["dai_max"] = nhe, None
        else:
            ev = [y for y in ev if y is not x]


# ---------------------------------------------------------------- CHỌN FILE
def _chon_file(nhoms, used, rng, lap=False, ngan=False, tranh=None, giu=None, dinh_max=None):
    """Chọn (nhóm, file) theo thứ tự nhóm ưu tiên: file mới/người dùng trước (nhóm có file mới thì không dùng file cũ);
    file dùng ít nhất trước; mỗi file tối đa TOI_DA_FILE lần (trừ lap). Hết thì thử nhóm kế, không còn thì (None, None)."""
    for nhom in nhoms:
        pool = [f for f in (KHO.get(nhom) or []) if not _bi_cam(f)]
        cands = ([f for f in pool if GOC.get(f) != "cu"] or pool) if nhom in NANG else pool   # 23/11 Kid "đa dạng lên": máy đánh chữ, màn trập, đồng xu cũ vẫn ok
        if giu and giu in pool:
            return nhom, giu
        if ngan:
            ng = [f for f in cands if (dac_tinh(f) or {}).get("dai", 9) <= 0.4]
            cands = ng or cands
        if dinh_max is not None:      # tiếng lót: đoạn dâng trước đỉnh ngắn (không "xì xì" kéo dài trước mốc)
            cands = [f for f in cands if (dac_tinh(f) or {}).get("t_dinh", 9) <= dinh_max]
        if not lap:
            cands = [f for f in cands if used.get(f, 0) < TOI_DA_FILE]
        if tranh and len(cands) > 1:
            cands = [f for f in cands if f != tranh] or cands
        if cands:
            m = min(used.get(f, 0) for f in cands)
            return nhom, rng.choice([f for f in cands if used.get(f, 0) == m])
    return None, None


SO_DOC = re.compile(r"\d|^(hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|trăm|nghìn|ngàn|triệu)$", re.I)


VUT_TOI_DA = 3


def _lap_cho(nhan, cau, cuts, total, ctx, dong=None, moc=None):
    """23/11 Kid "ép dày gần v10": tiếng phụ ưu tiên thấp nhất, lọc mật độ bỏ trước tiếng của khối chữ.
    nhan: [{"t","w"}] từ nhấn trong lời (phụ đề tô màu) → số = flash máy ảnh, chữ = tách/gõ xoay vòng cho đa dạng;
    cau: giây bắt đầu các câu sau câu đầu → có nhát cắt sát đó = đổi ý → lướt nhẹ, không thì một tiếng bật nhỏ lúc dòng mới hiện."""
    ui = ctx.get("ui")
    xoay = [g for g in ("go_phim", ui, "bop" if ui != "bop" else "tick", "tick" if ui != "tick" else "thong_bao") if g]
    du = ["tick", "bop", "go_phim"]
    out = []
    moc = sorted(float(m) for m in (moc if moc is not None else cuts or []))
    for k, x in enumerate(nhan or []):
        t, w = float(x["t"]), str(x.get("w") or "").strip(".,!?…:;")
        m = min(moc, key=lambda m: abs(m - t), default=None)       # 23/11 Kid: tiếng phải có LÝ DO hình (cắt cảnh / chữ hiện) → từ nhấn chỉ kêu khi trùng mốc hình
        if m is None or abs(m - t) > 0.3:
            continue
        t = m
        if not 0.6 < t < total - 0.3:
            continue
        if SO_DOC.search((w.split() or [""])[0]):                  # số: chuông sáng, KHÔNG màn trập (không màn trập: không có hình chụp ảnh)
            out.append(_sp(["ting", "tick"], t + 0.02, 3, -2.0, f"từ nhấn có số «{w}» trùng mốc hình → ting", "bat", nguon="nhan"))
        else:
            g = xoay[k % len(xoay)]
            out.append(_sp([g] + [x for x in du if x != g], t + 0.02, 4, -3.0, f"từ nhấn «{w}» → một tiếng {g} nhẹ", "bat", nguon="nhan", ngan=True))
    vut = []
    for t in cau or []:          # câu mới đúng nhát cắt = đổi ý → lướt; tối đa VUT_TOI_DA (bản 2: 7/20 tiếng là vút → đều đều)
        c = min(cuts or [], key=lambda c: abs(c - t), default=None)
        if c is not None and abs(c - t) < 0.35 and 0.6 < c < total - 1.0 and len(vut) < VUT_TOI_DA and all(c - v > 3.0 for v in vut):
            vut.append(c)
            x = _sp(["vut_nhe", "vut_manh"][len(vut) % 2:] + ["vut_nhe"], c + 0.05, 3, -1.0, "câu mới ở nhát cắt = đổi ý → lướt", nguon="doi_y")
            x["dinh_max"] = 0.35           # 23/11 Kid: "xì xì vút vút" 3–5 s = vút phép dâng 1,3 s trước mốc → lướt lót chỉ dùng tiếng ngắn
            out.append(x)
    for k, t in enumerate(dong if dong is not None else cau or []):     # dòng chữ mới hiện → tiếng bật nhỏ (không vút)
        if 0.6 < t < total - 0.5 and all(abs(t - v) > 0.4 for v in vut):
            g = du[k % len(du)]
            out.append(_sp([g] + [x for x in du if x != g], t, 4, -4.0, "dòng chữ mới hiện → một tiếng bật nhỏ", "bat", nguon="cau", ngan=True))
    return out


def _lat_trang(lat, uu=4):
    """Cụm lật trang: tick nhẹ, tối đa 8, cách nhau ≥ 0,16 s; cả cụm = 1 cử chỉ (cùng cum)."""
    ts = sorted(float(t) for t in lat if t is not None)
    cum, out, last = f"lat{round(ts[0] * 100)}" if ts else "lat", [], -9.0
    for t in ts:
        if t - last >= 0.16 and len(out) < 8:
            out.append(t)
            last = t
    return out, cum


def len_lich(muc, blocks, cuts, total, rng, pops=None, trans="fade", *, am_mo=None, st=None, chuyen_tung_cat=None, lat_trang=None,
             nhan=None, cau=None, dong=None, giong_t0=None, loi_dau=None):
    """Lịch SFX theo nghĩa. Tham số vị trí giữ nguyên như trước.
    am_mo: tên nhóm âm mở đầu do đạo diễn chọn | "khong" (cũng đọc từ st["am_mo"] nếu truyền st); không có thì chọn từ thực đơn theo lời mở.
    loi_dau: câu đầu của lời (chọn âm mở theo nghĩa; thiếu thì dùng chữ khối đầu); giong_t0: giây từ đầu tiên bắt đầu nói (boom không đè lời).
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
    if am_mo in THAY:
        am_mo = THAY[am_mo] or None
    total = float(total or 0)
    # 1 họ UI cho cả video (chọn 1 lần), hàng danh sách dùng 1 file
    ui_ds = [f for f in HO_UI if KHO.get(f)] or [f for f in ("thong_bao",) if KHO.get(f)]
    ui = rng.choice(ui_ds) if ui_ds else None
    ctx = {"rng": rng, "ui": ui, "n_dung": 0}
    sp = []
    # --- âm mở đầu do đạo diễn chọn
    bl = []
    for b in blocks or []:
        try:
            float(b["f0"]); bl.append(b)
        except (KeyError, TypeError, ValueError):
            continue
    t_mo = 0.10 if not bl or bl[0]["f0"] / FPS < 0.5 else bl[0]["f0"] / FPS + 0.08
    mac_dinh, ddb_mo, dmax_mo = am_mo is None, 0.0, None
    if mac_dinh:        # 24/11 chủ hàng: không một âm mở cố định → chọn theo nghĩa lời mở + rng
        am_mo, t_mo, ddb_mo, dmax_mo = _mo_dau(loi_dau if loi_dau is not None else (bl[0].get("text") if bl else ""), rng, lambda n: bool(KHO.get(n)))
    if am_mo and am_mo != "khong" and KHO.get(am_mo):
        vai = VAI.get(am_mo, "ui")
        x_mo = _sp(am_mo, t_mo + (0.0 if vai in NEO_DINH else -0.05), 0, ddb_mo,
                   f"âm mở «{am_mo}» " + ("chọn theo lời mở" if mac_dinh else "do đạo diễn chọn"), chinh=True, nguon="mo")
        x_mo["dinh_max"] = dmax_mo
        x_mo["giong"] = float(giong_t0) if giong_t0 is not None else GIONG_MAC_DINH
        sp.append(x_mo)
    # --- khối chữ
    for i, b in enumerate(bl):
        try:
            xs = _khoi(b, ctx)
        except Exception as e:                                     # khối hỏng không được làm sập cả lịch
            print("  SFX khối lỗi:", b.get("loai"), str(e)[:80])
            xs = []
        if b.get("tien_t") is not None and KHO.get("tien"):     # lời nói từ chốt đơn → xèng đúng chữ (dung_remotion.gio_xeng chọn có/không)
            xs.append(_sp("tien", float(b["tien_t"]) + 0.02, 1, 0.0, "lời nói từ chốt đơn → tiếng xèng tính tiền", "bat", chinh=True))
        for x in xs:
            x["khoi"] = i
            x["tu_dong"] = "am" not in b or b.get("am") is None
            if x["chinh"] and i in (0, len(bl) - 1):
                x["uu"] = 0
        if i == 0 and am_mo and not mac_dinh:                     # đạo diễn đã quyết âm mở (hoặc "khong") → bỏ nhát/vút TỰ ĐỘNG sát đầu khối đầu
            xs = [x for x in xs if not (x["tu_dong"] and x["t"] < 1.0 and VAI.get(x["nhom"][0]) in NEO_DINH)]
        if i == 0 and mac_dinh and any(x["chinh"] and x["t"] < 0.45 for x in xs):   # khối đầu tự có tiếng ngay giây đầu → đó là tiếng hook, bỏ rít đĩa
            sp = [x for x in sp if x["nguon"] != "mo"]
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
    sp += _lap_cho(nhan, cau, cuts, total, ctx, dong, list(cuts or []) + [b["f0"] / FPS for b in bl] + gop)
    # --- lọc theo ưu tiên
    for x in sp:                                                  # chỉ giữ nhóm đang có file; không nhóm nào có thì bỏ tiếng đó trước khi lọc
        x["nhom"] = [n for n in x["nhom"] if n and KHO.get(n)]
    sp = [x for x in sp if x["nhom"] and 0 <= x["t"] < max(total, 0.1)]
    sp = _loc_khoang(sp)
    sp = _loc_mat_do(sp, max(2, math.ceil(toi_da10 * min(10.0, max(total, 1.0)) / 10.0)))
    sp = _loc_nang(sp)
    # --- chọn file, đặt đúng mốc, đưa về mức theo vai
    used, ev, truoc, cung, chiem = {}, [], {}, {}, []
    for x in sorted(sp, key=lambda x: (x["uu"], x["t"])):
        lap = x["lap_ok"]
        fam, f = _chon_file(x["nhom"], used, rng, lap, x["ngan"], truoc.get(x["cum"]) if x["cum"] and not x["cung"] else None,
                            cung.get(x["cung"]) if x["cung"] else None, x.get("dinh_max"))
        if not f:
            continue
        m = dac_tinh(f)
        if not m:
            continue
        vai = VAI.get(fam, "ui")
        neo = x["neo"] or ("dinh" if vai in NEO_DINH else "bat")
        t_phat = max(0.0, x["t"] - (m["t_dinh"] if neo == "dinh" else m["t_bat"]))
        khoang = (t_phat, max(x["t"], t_phat) + 0.22)             # phần nghe rõ: đoạn dâng (vút) + 0,22 s sau mốc
        if any(min(khoang[1], b) - max(khoang[0], a) > 0.05 and not (x["cum"] and x["cum"] == c) and not (x.get("khoi") is not None and x.get("khoi") == k)
               for a, b, c, k in chiem):                         # 23/11 Kid "xì xì vút vút": sau khi canh đỉnh, hai tiếng khác lý do chồng nhau → bỏ tiếng ưu tiên thấp
            continue
        chiem.append((*khoang, x["cum"], x.get("khoi")))
        used[f] = used.get(f, 0) + 1
        if x["cum"]:
            truoc[x["cum"]] = f
        if x["cung"]:
            cung[x["cung"]] = f
        # thứ bậc (học video mẫu 23/11): tiếng CHÍNH ưu tiên cao (hook, khối đầu/cuối, chữ đập) +1 dB; tiếng lót đã −3/−4 dB → chênh rõ ~5 dB
        db = VAI_DB.get(vai, -16.0) + off_db + x["ddb"] + (1.0 if x["chinh"] and x["uu"] <= 1 else 0.0)
        dai = min(2.0, m["dai"] + 0.05)
        if x["nguon"] == "mo" and vai in ("hit", "scratch") and x.get("giong") is not None:    # boom/rít mở không đè lời: đỉnh trước giọng, đuôi chạm lời thì cắt + hạ thêm
            gh = x["giong"] + 0.10
            if t_phat + dai > gh:
                dai = max(0.3, gh - t_phat)
                if t_phat + min(2.0, m["dai"]) > gh + 0.15:
                    db -= 3.0
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


_LECH = {}


def lech_kenh(p):
    """Độ lệch trái − phải (dB, RMS) của 1 file; file mono / đo lỗi → 0. Nhớ trong bộ nhớ."""
    p = str(p)
    if p not in _LECH:
        try:
            r = subprocess.run(["ffmpeg", "-v", "info", "-t", "8", "-i", p, "-vn", "-af", "astats=measure_overall=none:measure_perchannel=RMS_level",
                                "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stderr
            ch = [float(v) for v in re.findall(r"RMS level dB:\s*(-?[\d.]+|-inf)", r.replace("-inf", "-120"))]
            _LECH[p] = round(ch[0] - ch[1], 1) if len(ch) >= 2 else 0.0
        except Exception:
            _LECH[p] = 0.0
    return _LECH[p]


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
        # 23/11: file lệch hẳn 1 kênh (vd đe kim loại chỉ có kênh trái → Kid "chói tai") đưa về giữa; dìm nhẹ dải xì trên 7 kHz
        giua = "aformat=channel_layouts=mono,pan=stereo|c0=c0|c1=c0," if abs(lech_kenh(ROOT / x["file"])) > 3 else ""
        fc.append(f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,{giua}atrim=0:{dai:.3f},asetpts=PTS-STARTPTS,{fin}"
                  f"afade=t=out:st={max(0.0, dai - fo):.3f}:d={fo:.3f},highshelf=f=7000:g=-3,volume={x['gain']}dB,adelay={ms}|{ms}[s{k}]")
        labels.append(f"[s{k}]")
    if not ev:
        fc.append(f"[{voice_label}]anull[{out_label}]")
        return args, fc
    fc.append(f"[{voice_label}]aformat=sample_rates=44100:channel_layouts=stereo[vv]")
    fc.append(f"[vv]{''.join(labels)}amix=inputs={len(ev) + 1}:duration=first:normalize=0,alimiter=limit=0.84:level=0[{out_label}]")
    return args, fc


def tron_am(base, ev, out_audio, total):
    """Trộn SFX vào tiếng của video nền → 1 file âm riêng (tách khỏi bước ghép hình để FFmpeg nhẹ, không sập).
    Có file giọng/nhạc riêng cạnh nền (dung.render khi dựng cho Remotion) → nhạc nền né cả tiếng hiệu ứng (23/11 Kid: "bị nhạc nền đè")."""
    b = Path(base)
    g, n = b.with_name(b.stem + ".giong.wav"), b.with_name(b.stem + ".nhac.wav")
    if ev and g.exists() and n.exists():
        a_args, a_fc = tron_lenh(ev, 2, "sx_in", "sx", total)
        a_fc.insert(0, f"anullsrc=r=44100:cl=stereo,atrim=0:{total}[sx_in]")    # nền im cho bus SFX
        a_fc += ["[sx]asplit=2[sxa][sxk]",
                 "[1:a]aformat=sample_rates=44100:channel_layouts=stereo[mm]",
                 "[mm][sxk]sidechaincompress=threshold=0.03:ratio=4:attack=3:release=220[md]",
                 "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[gg]",
                 "[gg][md][sxa]amix=inputs=3:duration=first:normalize=0,volume=1dB,alimiter=limit=0.84:level=0[a]"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(g), "-i", str(n), *a_args, "-filter_complex", ";".join(a_fc), "-map", "[a]",
                        "-c:a", "aac", "-b:a", "192k", str(out_audio)], check=True)
        return out_audio
    a_args, a_fc = tron_lenh(ev, 1, "0:a", "a", total)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base), *a_args, "-filter_complex", ";".join(a_fc), "-map", "[a]",
                    "-c:a", "aac", "-b:a", "192k", str(out_audio)], check=True)
    return out_audio

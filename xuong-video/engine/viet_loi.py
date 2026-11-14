"""Viết lời + phương án dựng bằng Claude CLI headless (mỗi lần gọi là phiên MỚI, không lịch sử chat).
viet(ma_sp, so_ban) -> list kịch bản đã qua kiểm.
Mỗi kịch bản được giao một tổ hợp 5 trục xoay vòng: góc bán · MO (kiểu câu mở) · THAN (kiểu thân bài) · CHOT (kiểu chốt) · VAI (người nói)."""
import json, os, random, re
from collections import Counter
from pathlib import Path


import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, khung_giay, khung_am_tiet, glob_kem
CFG = cfg_hub()
from ai import goi, lay_json, HetHanMuc  # noqa: E402
import prompt_mau  # noqa: E402

MIN_VIDEO_SO_LIEU, MIN_TRUNG_VI = 15, 200       # số liệu TikTok chỉ gửi/dùng khi nhóm ≥ 15 video và trung vị ≥ 200 view/24h (nhỏ hơn là nhiễu)


# ---------------------------------------------------------------- số liệu TikTok (chỉ khi đủ tin cậy)
def _cong_so_lieu(ma):
    """True khi nhóm số liệu (của sản phẩm nếu đủ video, không thì của mọi sản phẩm — giống hieu_qua.tom_tat) có ≥ 15 video và trung vị ≥ 200 view/24h.
    Đọc thẳng lich-su/hieu-qua.json (hieu_qua không công khai kích thước nhóm)."""
    try:
        c = CFG.get("hieu_qua") or {}
        if not c.get("bat", True):
            return False
        db = json.loads((HUB / "lich-su" / "hieu-qua.json").read_text(encoding="utf-8"))
        diem = lambda r: r.get("xem24") if r.get("xem24") is not None else r.get("xem72")
        tat_ca = [r for r in db.values() if isinstance(r, dict) and isinstance(diem(r), (int, float))]
        rieng = [r for r in tat_ca if r.get("ma") == ma]
        nguon = rieng if len(rieng) >= int(c.get("mau_tong", 6)) else tat_ca
        if len(nguon) < MIN_VIDEO_SO_LIEU:
            return False
        v = sorted(diem(r) for r in nguon)
        trung_vi = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
        return trung_vi >= MIN_TRUNG_VI
    except Exception:
        return False


def _he_so(ma, chieu):
    """Hệ số xoay vòng theo hiệu quả thật — chỉ khi số liệu đủ tin cậy (cổng _cong_so_lieu), không thì {} (xoay đều)."""
    try:
        if not _cong_so_lieu(ma):
            return {}
        from hieu_qua import he_so
        return he_so(ma, chieu)
    except Exception:
        return {}


def _tom_tat(ma, cho="bien_kich"):
    try:
        from hieu_qua import tom_tat
        return tom_tat(ma, cho)
    except Exception:
        return ""


def _so_lieu(ma):
    """Đoạn số liệu TikTok gửi biên kịch: "" nếu nhóm chưa đủ video / view quá nhỏ."""
    return _tom_tat(ma) if _cong_so_lieu(ma) else ""


BANNED = ["chữa khỏi", "khỏi hẳn", "100%", "số 1", "số một", "nhất thị trường", "duy nhất", "không độc", "ăn ngay",
          "tham khảo", "xem chi tiết", "tìm hiểu thêm", "đáng cân nhắc", "theo hướng dẫn của", "quy cách rõ ràng",
          "đúng nhu cầu", "giá chỉ", "nghìn đồng", "k/chai", "giải pháp toàn diện", "hiệu quả vượt trội", "chất lượng hàng đầu"]


def history_sentences(limit=400):
    f = HUB / "lich-su" / "cau-da-dung.txt"
    if not f.exists():
        return []
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()][-limit:]


def cau_cua_sp(ma, limit=150):
    """Câu đã dùng của RIÊNG sản phẩm này (máy chống trùng). Chưa có sổ riêng → dựng từ hồ sơ các video đã làm của sản phẩm."""
    f = HUB / "lich-su" / f"cau-da-dung-{ma}.txt"
    if not f.exists():
        ds = []
        for j in glob_kem(Path(CFG["duong_dan"]["ra"]), f"{ma}_*.json"):
            try:
                t = (json.loads(j.read_text(encoding="utf-8")).get("kich_ban") or {}).get("text") or ""
            except Exception:
                continue
            ds += [x.strip() for x in re.split(r"(?<=[.!?])\s+", re.sub(r"\[[^\]]*\]", "", t).strip()) if x.strip()]
        ds = list(dict.fromkeys(ds))
        if ds:
            f.write_text("".join(x + "\n" for x in ds), encoding="utf-8")
        return ds[-limit:]
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()][-limit:]


def recent_styles(limit=20):
    f = HUB / "lich-su" / "phong-cach.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()[-limit:] if l.strip()]


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", s.lower())).strip()


# ---------------------------------------------------------------- BỐN TRỤC (mỗi kịch bản một tổ hợp)
MO = {   # kiểu câu mở (hook): khoá → (mô tả gửi biên kịch, ví dụ CẤU TRÚC — không chép)
    'mat_mat': ('Mở bằng thứ người xem sắp mất hoặc vừa mất vì một việc nhỏ làm sai.', 'Nguyên một lứa cành giâm… chết vì đúng một bước.'),
    'nghich_ly': ('Một điều ngược đời nhưng đúng, khiến người ta khựng lại.', 'Tưới càng siêng, rễ càng thối.'),
    'dung_tay': ('Bảo người xem KHOAN làm việc họ sắp làm.', 'Khoan phun đã… xem trời hôm nay cái đã.'),
    'pha_niem_tin': ('Phủ nhận một điều ai cũng tin là đúng.', 'Lá vàng chưa chắc là thiếu phân.'),
    'hang_xom': ('Đặt vườn mình cạnh vườn bên: cùng đất, cùng giống, khác kết quả.', 'Cùng một bờ rào… bên kia bung đọt, bên này đứng im.'),
    'bi_mat_nghe': ('Điều người trong nghề biết mà ít nói ra.', 'Thợ giâm cành lâu năm… ít ai chỉ bước này.'),
    'ket_qua_truoc': ('Cho thấy kết quả trước, rồi mới kể đường đi tới đó.', 'Bộ rễ trắng này… ba tuần trước chưa có.'),
    'con_so': ('Một con số THẬT trong hồ sơ, nói cụt để gây tò mò.', 'Một chai. Hai trăm lít nước.'),
    'hoi_dung_noi_lo': ('Câu hỏi chạm đúng nỗi lo đang có ngoài vườn.', 'Rêu bám kín thân rồi… giờ tính sao?'),
    'dung_luc': ('Một thời điểm mùa vụ đang tới, lỡ là mất.', 'Mưa đầu mùa xuống… là nấm lên theo.'),
    'thu_nhan': ('Người nói tự nhận mình từng làm sai.', 'Năm ngoái tiếc một chai thuốc… mất luôn đợt tiêu.'),
    'goi_dung_nguoi': ('Gọi thẳng đúng nhóm người cần nghe.', 'Ai đang hái cà phê… nghe cái này.'),
    'thach_nhin': ('Thách người xem nhìn lại một chi tiết ở vườn nhà mình.', 'Ra vạch thử gốc cây nhà mình mà coi.'),
    'dang_xay_ra': ('Kéo người xem vào một khoảnh khắc đang diễn ra.', 'Sáng ra vườn… đọt xoăn hết một hàng.'),
    'qua_truoc': ('Mở thẳng bằng món quà đi kèm đơn.', 'Lấy ba chai… về tay bốn chai.'),
}
THAN = {   # kiểu thân bài (cũng là DANG_BAI: trường `dang` của kịch bản = khoá THAN, thống kê cũ còn chạy)
    'van_de_giai_phap': 'Vấn đề → một câu khoét hậu quả nếu để yên → sản phẩm vào → dùng thế nào.',
    'truoc_sau': 'Trước khi dùng ra sao → điều gì thay đổi → vì sao (đúng sự thật nhãn, không hứa chắc).',
    'chuyen_that_bai': 'Chuyện một nhà vườn làm sai, trả giá, rồi đổi cách (người và tình tiết được hư cấu).',
    'ba_sai_lam': 'Ba cái sai hay gặp, cái thứ ba dẫn thẳng tới sản phẩm.',
    'hoai_nghi': '"Hồi đầu không tin…" → một điều cụ thể trên nhãn/cách dùng làm đổi ý.',
    'phep_tinh': 'Một phép tính tiện/đỡ công bằng con số thật (một chai pha bao nhiêu, phun được bao nhiêu) — không nói giá.',
    'tung_buoc': 'Hai hoặc ba bước làm, bước nào cũng thấy được bằng hình.',
    'khach_hoi': 'Kể lại một câu khách hay hỏi rồi trả lời gọn như đang đứng ở quầy.',
    'soi_nhan': 'Cùng người xem đọc nhãn chai để nhận đúng hàng, đúng công dụng.',
    'dau_hieu': 'Hai ba dấu hiệu nhìn thấy ngoài vườn → cùng một chai xử lý.',
    'khang_dinh': 'Lời khẳng định thương hiệu gọn, chắc, kiểu TVC.',
}
DANG_BAI = THAN
CHOT = {   # kiểu câu chốt (bài nào cũng nhắc giỏ hàng MỘT lần, nói ngắn; quà chỉ nhắc khi kiểu chốt yêu cầu)
    'qua_cu_the': 'Giỏ hàng + đúng MỘT mức quà trong hồ sơ.',
    'thu_it': 'Giảm rủi ro: gợi ý lấy ít để thử trên một phần vườn trước.',
    'kip_luc': 'Nhắc thời điểm: làm trước khi mưa/đợt đọt/mùa bệnh tới.',
    'hoi_nguoc': 'Kết bằng một câu hỏi ngắn để người xem tự trả lời, rồi chỉ giỏ hàng.',
    'chot_nhe': 'Nói như người quen: chai nằm sẵn ở giỏ hàng, cần thì lấy.',
    'phep_tinh_chot': 'Nhắc lại con số tiện nhất rồi chỉ giỏ hàng.',
    'dong_hanh': 'Bên em gửi hàng từ kho, có gì cứ nhắn — rồi chỉ giỏ hàng (chỉ dùng khi hồ sơ cho phép nói "bên em").',
}
VAI = {   # người nói: một giọng đọc, đổi CÁCH NÓI (không dùng tag nhập vai)
    'chu_hang': 'Chủ hàng nói thẳng, xưng "bên em", gọi "bà con/anh chị". Chắc, gọn, có trách nhiệm với món mình bán.',
    'nha_vuon': 'Người làm vườn từng trải kể chuyện mình, xưng "tôi" hoặc "mình". Từ ngữ ngoài vườn, câu ngắn, có chỗ ngập ngừng. Chuyện kể được hư cấu; điều nói về sản phẩm phải đúng hồ sơ.',
    'ky_thuat': 'Người làm kỹ thuật giải thích cho dễ hiểu, không xưng hô nhiều. Mỗi câu một ý, có lý do "vì…".',
    'nguoi_ban_quay': 'Người đứng quầy vật tư kể chuyện khách, xưng "em". Nhanh, thực tế, hay nhắc "khách hỏi…".',
    'dan_chuyen': 'Giọng dẫn kiểu TVC, không xưng hô. Câu có lực, hình ảnh rõ.',
}
LUAT_CAU_MO = ('≤ 10 âm tiết thì tốt nhất; phải để lại một CHỖ HỞ khiến người ta muốn nghe câu sau; không mở bằng lời chào, '
               'không mở bằng tên sản phẩm (trừ kiểu qua_truoc, con_so); câu thứ hai trả ngay một phần chỗ hở, không vòng vo.')
_NHA_VUON_QUAY = {"nha_vuon", "nguoi_ban_quay", "chu_hang"}
_VAI_HOP = {   # ràng buộc tổ hợp: khoá (mo | than | chot) → các vai được phép
    "thu_nhan": _NHA_VUON_QUAY, "hoai_nghi": _NHA_VUON_QUAY, "chuyen_that_bai": _NHA_VUON_QUAY,
    "soi_nhan": {"chu_hang", "dan_chuyen", "ky_thuat"}, "khang_dinh": {"chu_hang", "dan_chuyen", "ky_thuat"},
    "dong_hanh": {"chu_hang", "nguoi_ban_quay"},
}
TRUC = {"mo": MO, "than": THAN, "chot": CHOT, "vai": VAI}
_CHIEU_HIEU_QUA = {"goc": "goc", "mo": "mo", "than": "dang", "chot": "chot", "vai": "vai"}


def dem_lich_su(ten, n=200):
    f = HUB / "lich-su" / ten
    try:
        return f.read_text(encoding="utf-8").splitlines()[-n:] if f.exists() else []
    except Exception:
        return []


def _them_so(ten, dong):
    """Ghi thêm 1 dòng vào sổ lịch sử. Lỗi ghi file không bao giờ làm hỏng dây chuyền."""
    try:
        f = HUB / "lich-su" / ten
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(str(dong).replace("\n", " ") + "\n")
    except Exception:
        pass


def _chon(khoa, dem, hs=None, rng=random, ok=None):
    """Chọn 1 khoá: ÍT DÙNG NHẤT trước (đếm chia hệ số hiệu quả 0.7–1.5 nếu có), cùng mức thì ngẫu nhiên (rng=None → theo thứ tự khai báo).
    ok(khoá) lọc ràng buộc; không khoá nào thoả thì bỏ ràng buộc."""
    hs = hs or {}
    ds = [k for k in khoa if ok is None or ok(k)] or list(khoa)
    return min(ds, key=lambda k: (dem.get(k, 0) / (hs.get(k) or 1.0), rng.random() if rng else 0))


def _co_ben_em(sp):
    return "bên em" in json.dumps(sp.get("su_that_duoc_noi") or [], ensure_ascii=False).lower()


def _vai_cho_phep(mo, than, chot):
    ok = set(VAI)
    for k in (mo, than, chot):
        if k in _VAI_HOP:
            ok &= _VAI_HOP[k]
    return ok


def moi_dem(ma=None):
    """Số lần đã dùng từng khoá của mỗi trục (từ sổ lịch sử của sản phẩm; ma=None → trống)."""
    ten = {"goc": "goc", "mo": "mo", "than": "than", "chot": "chot", "vai": "vai"}
    return {ax: Counter(dem_lich_su(f"{t}-{ma}.txt") if ma else []) for ax, t in ten.items()}


def lo_moi():
    return {"mo": set(), "qua": 0, "dan": 0}


def gan_truc(sp, goc, need, dem, hs=None, lo=None, tong=None, rng=random):
    """Giao cho `need` kịch bản mỗi bản một tổ hợp {goc, mo, than, chot, vai}.
    - mỗi trục xoay vòng: ít dùng nhất trước, có ngẫu nhiên, nhân hệ số hiệu quả `hs[trục]` nếu có (dem, lo được cập nhật tại chỗ);
    - trong MỘT lô (`lo`) không lặp mo cho tới khi dùng hết 15 kiểu; không quá 1/4 số bản (`tong`) chốt qua_cu_the (trừ góc qua-tang); vai dan_chuyen tối đa 1/5;
    - ràng buộc tổ hợp: qua_truoc ⇒ chot qua_cu_the; thu_nhan/hoai_nghi/chuyen_that_bai, soi_nhan/khang_dinh, dong_hanh giới hạn vai;
      dong_hanh cần hồ sơ có "bên em". Vi phạm → bốc lại trục đó (chỉ bốc trong các khoá hợp lệ)."""
    hs, lo = hs or {}, lo if lo is not None else lo_moi()
    tong = max(tong or need, 1)
    gioi_qua, gioi_dan = max(1, tong // 4), max(1, tong // 5)
    ben_em = _co_ben_em(sp)
    out = []
    for _ in range(need):
        g = _chon(goc, dem["goc"], hs.get("goc"), rng)
        qua_ok = g == "qua-tang" or lo["qua"] < gioi_qua
        if len(lo["mo"]) >= len(MO):
            lo["mo"].clear()
        mo = _chon(list(MO), dem["mo"], hs.get("mo"), rng, lambda k: k not in lo["mo"] and (k != "qua_truoc" or qua_ok))
        than = _chon(list(THAN), dem["than"], hs.get("than"), rng)
        chot = "qua_cu_the" if mo == "qua_truoc" else _chon(list(CHOT), dem["chot"], hs.get("chot"), rng,
                                                              lambda k: (k != "qua_cu_the" or qua_ok) and (k != "dong_hanh" or ben_em))
        cho = _vai_cho_phep(mo, than, chot)
        vai = _chon(list(VAI), dem["vai"], hs.get("vai"), rng, lambda k: k in cho and (k != "dan_chuyen" or lo["dan"] < gioi_dan))
        lo["mo"].add(mo)
        if chot == "qua_cu_the" and g != "qua-tang":
            lo["qua"] += 1
        if vai == "dan_chuyen":
            lo["dan"] += 1
        for ax, k in (("goc", g), ("mo", mo), ("than", than), ("chot", chot), ("vai", vai)):
            dem[ax][k] += 1
        out.append({"goc": g, "mo": mo, "than": than, "chot": chot, "vai": vai})
    return out


# ---------------------------------------------------------------- khối dữ liệu tuỳ chọn cho đề bài
def _mo_ta_goc(g):
    """Mô tả một góc bán trong hồ sơ (các trường chữ ngoài `ma`, nối lại)."""
    return " ".join(str(v).strip() for k, v in g.items() if k != "ma" and isinstance(v, str) and v.strip())


def _de_bai(sp, truc):
    """Mỗi bản một khối: góc + kiểu mở/thân/chốt + vai (chỉ gửi mô tả của khoá được giao; góc lấy mô tả trong goc_ban của hồ sơ)."""
    gm = {g["ma"]: _mo_ta_goc(g) for g in sp.get("goc_ban") or [] if isinstance(g, dict) and g.get("ma")}
    dong, co_mo = [], False
    for i, t in enumerate(truc):
        g = t.get("goc") or ""
        dong.append(f"bai[{i}]: góc = {g}" + (f" ({gm[g]})" if gm.get(g) else ""))
        if t.get("mo") in MO:
            co_mo = True
            dong.append(f'   kiểu mở = {t["mo"]} — {MO[t["mo"]][0]} (ví dụ cấu trúc, KHÔNG chép: "{MO[t["mo"]][1]}")')
        for ax, ten in (("than", "kiểu thân"), ("chot", "kiểu chốt"), ("vai", "vai")):
            k = t.get(ax)
            if k in TRUC[ax]:
                dong.append(f"   {ten} = {k} — {TRUC[ax][k]}")
    if co_mo:
        dong.append("Luật câu mở: " + LUAT_CAU_MO)
    return "\n".join(dong)


def _dd(p):
    """Đường dẫn dài trên Windows (> 260 ký tự): thêm tiền tố \\\\?\\."""
    s = str(p)
    if os.name != "nt" or s.startswith("\\\\?\\"):
        return s
    if s.startswith("\\\\"):
        return "\\\\?\\UNC\\" + s[2:]
    return "\\\\?\\" + os.path.abspath(s)


_GIONG_CACHE = {}


def _loi_hay_kho(kho):
    """Mọi `loi_hay` trong mô tả kiểu 2 (kieu == 2) của thư mục kho: <kho>/_mo-ta/**/*.mo-ta.json (bỏ thư mục con bắt đầu bằng _).
    Nhớ theo (thư mục kho, giờ sửa mới nhất) trong cả tiến trình."""
    try:
        if not kho:
            return []
        goc = _dd(Path(str(kho)) / "_mo-ta")
        if not os.path.isdir(goc):
            return []
        ds, mt = [], 0
        for d, con, files in os.walk(goc):
            con[:] = [x for x in con if not x.startswith("_")]
            for f in files:
                if f.endswith(".mo-ta.json"):
                    p = os.path.join(d, f); ds.append(p)
                    try:
                        mt = max(mt, os.stat(p).st_mtime_ns)
                    except OSError:
                        pass
        khoa = (str(kho), mt, len(ds))
        c = _GIONG_CACHE.get(str(kho))
        if c and c[0] == khoa:
            return c[1]
        out = []
        for p in sorted(ds):
            try:
                with open(p, encoding="utf-8-sig") as fh:
                    d = json.load(fh)
            except Exception:
                continue
            if isinstance(d, dict) and d.get("kieu") == 2:
                out += [s.strip() for s in (d.get("loi_hay") or []) if isinstance(s, str) and s.strip()] if isinstance(d.get("loi_hay"), list) else []
        _GIONG_CACHE[str(kho)] = (khoa, out)
        return out
    except Exception:
        return []


def _ten_sp_khac(sp):
    """Tên các sản phẩm KHÁC trong hub (câu thoại nhắc tên đó thì bỏ)."""
    ma, own = sp.get("ma"), [_chuan(x) for x in ten_phai_nhac(sp)]
    out = []
    try:
        for f in sorted((HUB / "san-pham").glob("*/san-pham.json")):
            if f.parent.name == ma:
                continue
            try:
                o = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if _la_kho_chung(o):
                continue
            for x in [o.get("ten_ngan"), o.get("ten_goi")] + list(o.get("ten_khac") or []):
                if isinstance(x, str) and len(x.strip()) >= 4:
                    c = _chuan(x)
                    if c not in out and not any(c in m for m in own):    # tên con của chính sản phẩm này thì không phân biệt được
                        out.append(c)
    except Exception:
        pass
    return out


def _la_kho_chung(o):
    return bool(o) and (o.get("loai") == "kho-chung" or bool(o.get("chi_la_kho_canh")))


def _kho_chung_dirs(ma):
    out = []
    try:
        for f in sorted((HUB / "san-pham").glob("*/san-pham.json")):
            o = json.loads(f.read_text(encoding="utf-8"))
            if f.parent.name != ma and _la_kho_chung(o) and o.get("kho_video"):
                out.append(o["kho_video"])
    except Exception:
        pass
    return out


def giong_that(sp, rng=random, toi_da=8):
    """Khối "GIỌNG NÓI THẬT NGOÀI VƯỜN": tối đa 8 `loi_hay` từ mô tả kiểu 2 của kho sản phẩm (thiếu thì thêm kho dùng chung),
    ưu tiên câu 8–30 từ, bỏ câu có chữ số và câu nhắc tên sản phẩm khác. Không có → ""."""
    try:
        khac = _ten_sp_khac(sp)
        thay, ds = set(), []
        def them(kho):
            for c in _loi_hay_kho(kho):
                n = norm(c)
                if n and n not in thay and not re.search(r"\d", c) and not any(x in _chuan(c) for x in khac):
                    thay.add(n); ds.append(c)
        them(sp.get("kho_video"))
        if len(ds) < toi_da:                                  # thiếu thì mượn lời hay của kho dùng chung
            for k in _kho_chung_dirs(sp.get("ma")):
                them(k)
        vua = [c for c in ds if 8 <= len(c.split()) <= 30]
        con = [c for c in ds if c not in vua]
        rng.shuffle(vua); rng.shuffle(con)
        chon = (vua + con)[:toi_da]
        if not chon:
            return ""
        return ("\n=== GIỌNG NÓI THẬT NGOÀI VƯỜN (người thật nói trong clip — học NHỊP và CÁCH DÙNG TỪ; không chép câu, không lấy số liệu hay công dụng từ đây) ===\n"
                + "\n".join(f'- "{c}"' for c in chon) + "\n")
    except Exception:
        return ""


_NHAN_VAI_TRO = [("chai_ro", "chai rõ nhãn"), ("nhan_can", "mặt sau nhãn"), ("pha_rot", "pha, rót"), ("phun", "phun, tưới"), ("re", "rễ, gốc"),
                 ("cay_con", "cây con"), ("van_de", "cây bệnh"), ("ket_qua", "cây khoẻ, kết quả"), ("vuon", "toàn cảnh vườn"), ("kho_hang", "kho hàng")]
_TEN_CAY = {"ca_phe": "cà phê", "ho_tieu": "hồ tiêu", "sau_rieng": "sầu riêng", "ot": "ớt", "rau_mau": "rau màu", "thanh_long": "thanh long"}


def _canh_bad(s):
    """Cảnh KHÔNG dùng (cùng luật soat_kho.bad): chữ chèn nhiều, hàng khác, quá xấu."""
    x = s.get("soat") or {}
    chu = x.get("chu_muc", 2 if x.get("chu") else 0)
    return bool(chu >= 2 or x.get("hang_khac") or (x.get("dep") or 3) <= 1)


def kho_canh(ma):
    """Khối "KHO CẢNH ĐANG CÓ" từ san-pham/<ma>/canh.json: số cảnh dùng được (không bad) theo vai trò, số cảnh người nói, cây trồng có trong kho. Chưa có → ""."""
    try:
        shots = json.loads((HUB / "san-pham" / ma / "canh.json").read_text(encoding="utf-8"))
        if not isinstance(shots, list):
            return ""
        ok = [s for s in shots if isinstance(s, dict) and not _canh_bad(s)]
        dem, cay = Counter(), []
        for s in ok:
            for v in s.get("vai_tro") or []:
                dem[v] += 1
            for c in s.get("cay") or []:
                if c in _TEN_CAY and _TEN_CAY[c] not in cay:
                    cay.append(_TEN_CAY[c])
        so = lambda n: f"{n}" + (" (ít)" if 0 < n <= 2 else "")
        noi = sum(1 for s in ok if ((s.get("soat") or {}).get("mat") or 0) >= 2)
        dong = " · ".join([f"{ten}: {so(dem[k])}" for k, ten in _NHAN_VAI_TRO] + [f"người nói: {so(noi)}"])
        return ("\n=== KHO CẢNH ĐANG CÓ (viết sao cho hình có thật; loại ghi 0 hoặc \"ít\" thì đừng viết câu cần đúng hình đó) ===\n" + dong + "\n"
                + (("Cây có trong kho: " + ", ".join(cay) + ".\n") if cay else ""))
    except Exception:
        return ""


# ---------------------------------------------------------------- đề bài
def ctx_bien_kich(sp, n, angles, used, styles, dang=None, mo_dau=None, qc=None, hieu_qua="", truc=None, loi_truoc=None, sp_day=None):
    """Dữ liệu điền vào mẫu prompt/bien-kich.md (chỗ nào cần logic/khối tuỳ chọn thì tính ở đây; khối rỗng → "").
    truc: [{goc, mo, than, chot, vai}] từng bản (None → chỉ có góc + dạng bài như đề bài cũ). sp_day: hồ sơ đầy đủ (có kho_video) cho khối giọng thật."""
    luat = prompt_mau.doc_luat("LUAT-SAN-XUAT.md")
    luat = luat.split("## Dựng")[0].rstrip()          # phần Dựng là việc của đạo diễn/máy dựng, biên kịch không cần
    so_gu_f = HUB / "lich-su" / "so-gu.md"
    so_gu = so_gu_f.read_text(encoding="utf-8")[-3000:].strip() if so_gu_f.exists() else ""
    so_gu = ("=== SỔ GU CỦA CHỦ HÀNG ===" + chr(10) + so_gu + chr(10)) if so_gu else ""
    kg, kat = khung_giay(sp), khung_am_tiet(sp)
    sp_day = sp_day or sp
    dang = list(dang or [])
    if truc is None:
        truc = [{"goc": angles[i] if i < len(angles) else "", "than": dang[i] if i < len(dang) else ""} for i in range(n)]
    else:
        dang = [t.get("than") or "" for t in truc]
        angles = [t.get("goc") or "" for t in truc]
    lt = [x for x in dict.fromkeys(loi_truoc or []) if str(x).strip()][-5:]
    return {
        "luat": luat,
        # mã nội bộ, tên giỏ hàng, mục rỗng và các khoá không giúp viết lời không gửi (goc_ban: chỉ phần góc được giao, nằm trong de_bai)
        "san_pham": json.dumps({k: v for k, v in sp.items() if k not in ("ma", "ten_gio", "goc_ban", "cat_khung_ly_do", "thoi_luong") and v not in ("", [], {}, None)},
                               ensure_ascii=False, indent=1),
        "so_gu": so_gu,
        "giong_that": giong_that(sp_day) if sp_day.get("kho_video") else "",
        "kho_canh": kho_canh(sp_day["ma"]) if sp_day.get("ma") else "",
        "so_lieu_tiktok": "" if not hieu_qua else chr(10) + "=== SỐ LIỆU THẬT TỪ TIKTOK (video đã đăng) ===" + chr(10) + hieu_qua + chr(10),
        "ten_phai_nhac": json.dumps(ten_phai_nhac(sp_day), ensure_ascii=False),
        "so_ban": n,
        "de_bai": _de_bai(sp_day, truc),
        "loi_truoc": ("BẢN TRƯỚC BỊ LOẠI VÌ:" + chr(10) + chr(10).join("- " + str(x) for x in lt) + chr(10) + chr(10)) if lt else "",
        # khoá của đề bài cũ (người đã tự sửa đề bài vẫn nhận giá trị hợp lý)
        "angles": json.dumps(angles, ensure_ascii=False),
        "dang": json.dumps([f"{d}: {THAN.get(d, '')}" for d in dang], ensure_ascii=False),
        "quy_cach": ("quy_cach = " + json.dumps(qc, ensure_ascii=False) + "  ← bản thứ i nói về QUY CÁCH qc[i] (dung tích/đóng gói), chỉ dùng mức quà của ĐÚNG quy cách đó.") if qc else "",
        "cau_mo_da_dung": json.dumps((mo_dau or [])[-30:], ensure_ascii=False),
        "giay_toi_thieu": f"{kg[0]:g}", "giay_toi_da": f"{kg[1]:g}",
        "am_tiet_toi_thieu": kat[0], "am_tiet_toi_da": kat[1], "am_tiet_muc_tieu": (kat[0] + kat[1]) // 2,
        "cau_toi_thieu": kat[4], "cau_toi_da": kat[5],
        "cau_da_dung": json.dumps(used[-150:], ensure_ascii=False),
        "giong": "|".join(CFG["giong"]["danh_sach"]),
    }


def build_prompt(sp, n, angles, used, styles, dang=None, mo_dau=None, qc=None, hieu_qua="", truc=None, loi_truoc=None, sp_day=None):
    return prompt_mau.dien("bien-kich", **ctx_bien_kich(sp, n, angles, used, styles, dang, mo_dau, qc, hieu_qua, truc, loi_truoc, sp_day))


def ctx_xem_thu(ma, sp, n=3):
    """Dữ liệu thật của sản phẩm cho nút "Xem thử" (chọn góc/kiểu đầu danh sách, không ngẫu nhiên, không ghi sổ trục)."""
    sp_ai = {k: v for k, v in sp.items() if k not in ("kho_video", "loai_tru", "vai_tro_rieng", "cat_khung", "doc_la", "mau_thuong_hieu", "kho_them", "shop_product_id")}
    goc = [g["ma"] for g in sp.get("goc_ban") or []] or ["cong-dung", "cach-dung", "thuong-hieu", "qua-tang"]
    truc = gan_truc(sp, goc, n, moi_dem(), None, lo_moi(), n, rng=None)
    qcs = [q["ten"] for q in sp.get("quy_cach") or []]
    qc = [qcs[i % len(qcs)] for i in range(n)] if qcs else None
    return ctx_bien_kich(sp_ai, n, [t["goc"] for t in truc], cau_cua_sp(ma), recent_styles(), [t["than"] for t in truc], dem_lich_su(f"mo-dau-{ma}.txt"), qc,
                         _so_lieu(ma), truc=truc, sp_day=sp)


# ---------------------------------------------------------------- kiểm bản viết
def _chuan(s):
    """So tên không phân biệt hoa thường / dấu câu / khoảng trắng: 'NPK 33-11-11' ~ 'npk 33 11 11'."""
    return " " + " ".join(re.findall(r"\w+", (s or "").lower())) + " "


def ten_phai_nhac(sp):
    """Các cách gọi hợp lệ của sản phẩm (lời đọc phải chứa ít nhất 1): tên ngắn, tên gọi, tên khác."""
    ds = [sp.get("ten_ngan"), sp.get("ten_goi")] + list(sp.get("ten_khac") or [])
    if sp.get("ma") == "nano-dong":
        ds.append("chai nano đồng này")
    return [x for x in ds if isinstance(x, str) and x.strip()]


TAG_OK = {"confident", "warm", "warm, confident", "serious", "matter-of-fact", "curious", "concerned", "surprised", "relieved", "proud", "satisfied",
          "excited", "upbeat", "urgent", "confident, slightly frustrated"}
_RE_DEM_CUOI = re.compile(r"(?<!\w)(?:đó nha|luôn nha|ạ|nha|nè|á|thiệt)\s*$")
_RE_DEM_VAI = re.compile(r"(?<!\w)(?:nha|nè|á)(?!\w)")
_MO_TEN_MUON = {"ket_qua_truoc", "dang_xay_ra"}       # mở bằng kết quả/khoảnh khắc: tên sản phẩm được lùi tới câu 3 (cùng kiểu thân chuyen_that_bai)


def check(item, sp, used_norm, log=None):
    """→ (lỗi[], các câu). Lỗi không rỗng = loại bản. log(msg): ghi các nhận xét không loại bản."""
    errs = []
    mo, than, chot, vai = (item.get(k) or "" for k in ("mo", "than", "chot", "vai"))
    than = than or item.get("dang") or ""
    # tag: tag ngoài danh sách cho phép → [confident] (không loại); phải có ≥ 3 tag khác nhau
    tags = []
    def _tag(m):
        t = re.sub(r"\s*,\s*", ", ", re.sub(r"\s+", " ", m.group(1).strip().lower()))
        t = t if t in TAG_OK else "confident"
        tags.append(t)
        return f"[{t}]"
    text = re.sub(r"\[([^\]]*)\]", _tag, item.get("text", ""))
    item["text"] = text
    if len(set(tags)) < 3:
        errs.append(f"chỉ {len(set(tags))} tag khác nhau (cần ít nhất 3)")
    plain = re.sub(r"\[[^\]]*\]", "", text)
    n = len(re.findall(r"\w+", plain))
    _lo, _hi, nho, lon, _c1, _c2 = khung_am_tiet(sp)
    if not nho <= n <= lon:
        errs.append(f"{n} âm tiết (cần {_lo}–{_hi})")
    low = " " + plain.lower() + " "
    errs += [f"từ cấm '{b.strip()}'" for b in BANNED
             if re.search(r"(?<!\w)" + re.escape(b.strip()) + r"(?!\w)", low)]   # khớp nguyên từ, không bắt "nha" trong "nhanh"
    sents = [s for s in re.split(r"(?<=[.!?])\s+", plain.strip()) if s.strip()]
    # tên sản phẩm: trong 2 câu đầu (3 câu nếu mở bằng kết quả/khoảnh khắc đang diễn ra hoặc kể chuyện)
    ten = [_chuan(nm) for nm in ten_phai_nhac(sp)]
    han = 3 if (mo in _MO_TEN_MUON or than == "chuyen_that_bai") else 2
    if not any(t in _chuan(plain) for t in ten):
        errs.append("thiếu tên thương hiệu")
    elif not any(t in _chuan(" ".join(sents[:han])) for t in ten):
        errs.append(f"tên sản phẩm chưa xuất hiện trong {han} câu đầu")
    if sents:
        n0 = len(re.findall(r"\w+", sents[0]))
        if n0 > 14:
            errs.append(f"câu mở dài ({n0} âm tiết, tối đa 14)")
        if mo not in ("qua_truoc", "con_so") and any(_chuan(sents[0]).startswith(t) for t in ten):
            errs.append("câu mở bắt đầu bằng tên sản phẩm")
    # tiếng đệm: tối đa 2 lần ở cuối vế; vai kỹ thuật/dẫn chuyện không dùng nha/nè/á
    dem_dem = sum(1 for v in re.split(r"[.!?…,;:]+", plain) if _RE_DEM_CUOI.search(v.strip().lower()))
    if dem_dem > 2:
        errs.append(f"quá nhiều tiếng đệm cuối vế ({dem_dem} lần, tối đa 2)")
    if vai in ("ky_thuat", "dan_chuyen") and _RE_DEM_VAI.search(plain.lower()):
        errs.append(f"vai {vai} không dùng nha/nè/á")
    # giỏ hàng nhắc đúng một lần
    gh = len(re.findall(r"giỏ hàng", plain.lower()))
    if gh == 0:
        errs.append("không nhắc giỏ hàng")
    elif gh >= 3:
        errs.append(f"nhắc giỏ hàng {gh} lần (chỉ một lần)")
    if chot and chot != "qua_cu_the" and log and any(re.search(r"(?<!\w)tặng(?!\w)", s.lower()) for s in sents[-2:]):
        log(f"  lưu ý: kiểu chốt {chot} nhưng hai câu cuối có chữ 'tặng'")
    errs += [f"lặp câu: {s[:30]}" for s in sents if norm(s) in used_norm and len(s.split()) >= 4]
    if item.get("giong") not in CFG["giong"]["danh_sach"]:
        item["giong"] = random.choice(list(CFG["giong"]["danh_sach"]))
    if len(item.get("canh", [])) < len(sents):
        item["canh"] = item.get("canh", []) + [{"vai_tro": ["chai_ro"]}] * (len(sents) - len(item.get("canh", [])))
    pcs = item.get("phong_cach") or [{}]
    item["phong_cach"] = pcs if isinstance(pcs, list) else [pcs]
    return errs, sents


def gon_chu_mo(c, n=30):
    """Chữ móc câu hiện lúc mở: gọn khoảng trắng, cắt ≤ 30 ký tự ở ranh giới từ."""
    c = re.sub(r"\s+", " ", str(c or "")).strip()
    if len(c) > n:
        c = c[:n].rsplit(" ", 1)[0] if " " in c[:n] else c[:n]
    return c.rstrip(" ,;:–-")


def viet(ma_sp, so_ban, log=print):
    sp = json.loads((HUB / "san-pham" / ma_sp / "san-pham.json").read_text(encoding="utf-8"))
    sp_for_ai = {k: v for k, v in sp.items() if k not in ("kho_video", "loai_tru", "vai_tro_rieng", "cat_khung", "doc_la", "mau_thuong_hieu", "kho_them", "shop_product_id")}
    used_norm = {norm(s) for s in history_sentences()}      # máy chống trùng: câu của mọi sản phẩm
    used = cau_cua_sp(ma_sp)                                 # chỉ để máy biết; đề bài mặc định không gửi 150 câu này nữa
    goc = [g["ma"] for g in sp.get("goc_ban") or []] or ["cong-dung", "cach-dung", "thuong-hieu", "qua-tang"]   # sản phẩm mới chưa có góc bán
    out, tries, loi_truoc = [], 0, []
    dem, lo = moi_dem(ma_sp), lo_moi()
    dem_q = Counter(dem_lich_su(f"qc-{ma_sp}.txt"))
    while len(out) < so_ban and tries < 4:
        tries += 1
        need = min(10, so_ban - len(out))
        hs = {ax: _he_so(ma_sp, ch) for ax, ch in _CHIEU_HIEU_QUA.items()}     # góc/kiểu từng ra nhiều view được xoay tới sớm hơn, chỉ khi số liệu đủ tin
        truc = gan_truc(sp, goc, need, dem, hs, lo, so_ban)
        qcs = [q["ten"] for q in sp.get("quy_cach") or []]
        qc = [_chon(qcs, dem_q, None, random) for _ in range(need)] if qcs else None
        for q in qc or []:
            dem_q[q] += 1
        log(f"  gọi Claude viết {need} bản (lần {tries})…")
        try:
            items = lay_json(goi("biên kịch", build_prompt(sp_for_ai, need, [t["goc"] for t in truc], used, recent_styles(), [t["than"] for t in truc],
                                                           dem_lich_su(f"mo-dau-{ma_sp}.txt"), qc, _so_lieu(ma_sp), truc, loi_truoc[-5:], sp))[0])
        except HetHanMuc:
            raise
        except Exception as e:
            log(f"  lỗi: {e}"); continue
        if isinstance(items, dict):                       # AI bọc mảng trong đối tượng → lấy mảng đầu tiên
            items = next((v for v in items.values() if isinstance(v, list)), [items])
        items = [x for x in (items or []) if isinstance(x, dict) and isinstance(x.get("text"), str)]
        for i_it, it in enumerate(items):
            if i_it >= len(truc):
                break
            t = truc[i_it]
            it.update({"goc": t["goc"], "mo": t["mo"], "than": t["than"], "chot": t["chot"], "vai": t["vai"]})   # trục do máy giao là chuẩn, không theo lời AI khai
            errs, sents = check(it, sp, used_norm, log)
            if errs:
                log(f"  loại 1 bản ({it.get('goc')}/{t['mo']}): {'; '.join(errs)}")
                loi_truoc = [x for x in loi_truoc if x not in errs] + errs      # lý do mới nhất ở cuối; gửi tối đa 5 lý do gần nhất
                continue
            for s in sents:
                used_norm.add(norm(s)); used.append(s)
            it["dang"] = t["than"]
            it["chu_mo"] = gon_chu_mo(it.get("chu_mo"))
            ten_qc = qc[i_it] if qc and i_it < len(qc) else None
            it["quy_cach"] = next((q["ma"] for q in sp.get("quy_cach") or [] if q["ten"] == ten_qc), None)
            if ten_qc:
                _them_so(f"qc-{ma_sp}.txt", ten_qc)
            def tag(h):                                # #khong dau, khong khoang trang
                import unicodedata
                h = unicodedata.normalize("NFD", str(h).replace("đ", "d").replace("Đ", "D"))
                h = "".join(ch for ch in h if unicodedata.category(ch) != "Mn")
                h = re.sub(r"[^0-9A-Za-z]", "", h).lower()
                return "#" + h if h else ""
            it["hashtag"] = [t_ for t_ in dict.fromkeys(tag(h) for h in (it.get("hashtag") or [])) if t_][:3]
            cap = it.get("caption") or []
            def gon(c, n=90):                          # luật caption ≤ 90 ký tự, cắt ở ranh giới từ
                c = re.sub(r"\s+", " ", str(c)).strip()
                return c if len(c) <= n else c[:n].rsplit(" ", 1)[0].rstrip(",;:–-") + "…"
            it["captions"] = [gon(c) for c in (cap if isinstance(cap, list) else [cap]) if str(c).strip()] or [""]
            it["caption"] = it["captions"][0]
            for ax in ("goc", "mo", "chot", "vai"):
                _them_so(f"{ax}-{ma_sp}.txt", t[ax])
            _them_so(f"than-{ma_sp}.txt", t["than"])
            _them_so(f"dang-{ma_sp}.txt", t["than"])
            _them_so(f"mo-dau-{ma_sp}.txt", sents[0] if sents else "")
            out.append(it)
            if len(out) >= so_ban:
                break
    return out

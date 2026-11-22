"""8 CÔNG THỨC DỰNG (Kid duyệt 10/11/2026) + xếp khối theo câu/vùng + kiểm nội dung khối + chống lặp trong ngày."""
import random, re, unicodedata

FPS = 30
RECIPES = {
    "tvc_sang": {"ten": "TVC sang", "mo": ["hook_mat_na", "hook_bang", "hook_go_may"], "giua": ["lower_third", "vong_tron", "da_quang", "nhan_dan"],
                 "chot": ["the_qua", "nut_gio_hang"], "phu_de": ["mo_sang", "to_dan", "quet_mau", "hop_mo"], "chuyen_canh": ["fade", "smoothleft", "smoothup"],
                 "chuyen_dong": ["zoom_vao", "zoom_ra"], "mau": ["am", "mat", "tu_nhien"], "nhac": ["tvc-doanh-nghiep", "piano-nhe", "tiktok"],
                 "sfx": ["gon", "vua"], "atmos": {"leak": 0.7, "vignette": 0.6, "grain": 0.3}, "nhip": "vua"},
    "soi_dong": {"ten": "Bán hàng sôi động", "mo": ["hook_dap", "hook_tem", "hook_tung_tu"], "giua": ["bong_chu", "dai_chay", "nhan_dan", "mui_ten_chi"],
                 "chot": ["hop_qua", "nut_gio_hang", "the_qua"], "phu_de": ["o_nhay", "vien_day", "nhich_len"], "chuyen_canh": ["slideleft", "slideup", "zoomin", "hon_hop"],
                 "chuyen_dong": ["hon_hop"], "mau": ["tuoi", "tuong_phan"], "nhac": ["vui-mua-sam", "tiktok"],
                 "sfx": ["soi_dong", "mo_dau_am"], "atmos": {"leak": 0.3, "vignette": 0.2, "grain": 0.0}, "nhip": "nhanh"},
    "danh_sach": {"ten": "Danh sách lý do", "mo": ["hook_bang", "hook_go_may", "hook_mat_na"], "giua": ["checklist"],
                  "chot": ["bang_qua", "the_qua"], "phu_de": ["to_dan", "gach_chay", "o_nhay"], "chuyen_canh": ["slideleft", "slideup", "smoothleft"],
                  "chuyen_dong": ["zoom_vao", "lia_trai", "lia_phai"], "mau": ["tuoi", "tu_nhien"], "nhac": ["tvc-doanh-nghiep", "vui-mua-sam", "tiktok"],
                  "sfx": ["vua"], "atmos": {"leak": 0.3, "vignette": 0.3, "grain": 0.0}, "nhip": "vua"},
    "con_so": {"ten": "Con số", "mo": ["hook_dap", "hook_tung_tu"], "giua": ["so_dem", "bong_chu", "da_quang"],
               "chot": ["nut_gio_hang", "the_qua"], "phu_de": ["vien_day", "to_dan", "nhich_len"], "chuyen_canh": ["zoomin", "slideup", "hon_hop"],
               "chuyen_dong": ["zoom_vao", "hon_hop"], "mau": ["tuong_phan", "tuoi"], "nhac": ["vui-mua-sam", "tvc-doanh-nghiep", "tiktok"],
               "sfx": ["vua", "soi_dong", "mo_dau_am"], "atmos": {"leak": 0.2, "vignette": 0.4, "grain": 0.0}, "nhip": "nhanh"},
    "so_sanh": {"ten": "So sánh", "mo": ["hook_hoi", "hook_tem", "hook_dap"], "giua": ["so_sanh", "vong_tron"],
                "chot": ["the_qua", "hop_qua"], "phu_de": ["o_nhay", "to_dan", "gach_chay"], "chuyen_canh": ["slideleft", "smoothleft", "hon_hop"],
                "chuyen_dong": ["zoom_vao", "zoom_ra"], "mau": ["tu_nhien", "tuoi"], "nhac": ["tvc-doanh-nghiep", "tiktok"],
                "sfx": ["vua", "mo_dau_am"], "atmos": {"leak": 0.2, "vignette": 0.3, "grain": 0.0}, "nhip": "vua"},
    "ke_chuyen": {"ten": "Kể chuyện nhà vườn", "mo": ["hook_go_may", "hook_hoi", "hook_mat_na"], "giua": ["lower_third", "da_quang"],
                  "chot": ["the_qua", "nut_gio_hang"], "phu_de": ["mo_sang", "hop_mo", "to_dan"], "chuyen_canh": ["fade", "smoothup"],
                  "chuyen_dong": ["zoom_vao", "lia_trai", "lia_phai"], "mau": ["am", "mat"], "nhac": ["que-acoustic", "tiktok"],
                  "sfx": ["gon", "vua"], "atmos": {"leak": 0.5, "vignette": 0.5, "grain": 0.4}, "nhip": "vua"},
    "tin_nhanh": {"ten": "Tin nhanh mùa vụ", "mo": ["hook_tem", "hook_bang"], "giua": ["canh_bao", "dai_chay", "mui_ten_chi"],
                  "chot": ["nut_gio_hang", "the_qua"], "phu_de": ["vien_day", "o_nhay", "gach_chay"], "chuyen_canh": ["slideleft", "slideup", "hon_hop"],
                  "chuyen_dong": ["hon_hop"], "mau": ["tuong_phan", "tuoi"], "nhac": ["vui-mua-sam", "tiktok"],
                  "sfx": ["soi_dong", "mo_dau_am"], "atmos": {"leak": 0.1, "vignette": 0.3, "grain": 0.0}, "nhip": "nhanh"},
    "qua_tang": {"ten": "Quà tặng là chính", "mo": ["hook_dap", "hook_tem", "hook_bang"], "giua": ["bong_chu", "nhan_dan"],
                 "chot": ["hop_qua", "bang_qua"], "phu_de": ["o_nhay", "nhich_len", "to_dan"], "chuyen_canh": ["slideup", "zoomin", "hon_hop"],
                 "chuyen_dong": ["hon_hop", "zoom_vao"], "mau": ["tuoi", "am"], "nhac": ["vui-mua-sam", "tet-le-hoi", "tiktok"],
                 "sfx": ["soi_dong", "mo_dau_am", "vua"], "atmos": {"leak": 0.4, "vignette": 0.2, "grain": 0.0}, "nhip": "vua"},
}
KHOI_MO = sorted({k for r in RECIPES.values() for k in r["mo"]})
KHOI_CHOT = sorted({k for r in RECIPES.values() for k in r["chot"]})
ZONE = {"lower_third": "LOWER"}           # còn lại đều ở vùng TOP (trừ hook_dap: CENTER, ngắn)
SO_HOP_LE = {1, 2, 3, 5, 10, 200, 250, 300, 500, 15000}   # CHỈ dự phòng khi sản phẩm không có sự thật/quà nào (xem so_cho_phep)


def _kd(s):
    """Không dấu, chữ thường, dấu câu → khoảng trắng (để so khớp lời với mức quà)."""
    s = unicodedata.normalize("NFD", str(s or "").replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.sub(r"[^\w%]+", " ", s).split())


# ---------------------------------------------------------------- SỐ HỢP LỆ (khối so_dem) — lấy từ sự thật/quà của chính sản phẩm, KÈM ĐƠN VỊ
_DON_VI = {"l": "lit", "nghin": "k", "ngan": "k"}


def _don_vi(u):
    u = _kd(u)
    return _DON_VI.get(u, u)


def _so(s):
    """Chuỗi số → (giá trị, là_số_nguyên) hoặc None. '15.000' = 15000 (nhóm 3 chữ số); '1,12' / '1.5' = thập phân (KHÔNG thành 112)."""
    s = str(s if s is not None else "").strip()
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        return float(re.sub(r"[.,]", "", s)), True
    if re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        return float(s.replace(",", ".")), not re.search(r"[.,]", s)
    return None


_RE_SO = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)*)\s*(%|[^\W\d_]+)?")


def so_cho_phep(st):
    """Tập (giá trị, đơn vị) rút từ sự thật được nói (st['_so_that']) + quà (st['_qua']) của sản phẩm; None = sản phẩm không có dữ kiện nào → dùng SO_HOP_LE."""
    ds = [str(x) for k in ("_so_that", "_qua") for x in (st.get(k) or [])]
    if not ds:
        return None
    out = set()
    for t in ds:
        for m in _RE_SO.finditer(t):
            n = _so(m.group(1))
            if n:
                out.add((n[0], _don_vi(m.group(2) or "")))
    return out


def _so_ok(v, don_vi, hop):
    if hop is None:
        return v in SO_HOP_LE
    dv = _don_vi(don_vi)
    return any(x == v and (not dv or u == dv) for x, u in hop)


# ---------------------------------------------------------------- QUÀ CHỐT: mỗi video chốt bằng MỘT mức quà thật trong hồ sơ, chữ/kiểu thẻ đổi theo video
CHOT_QUA = ("the_qua", "hop_qua", "bang_qua")
HEADER_QUA = ("QUÀ TẶNG", "TẶNG KÈM", "QUÀ CHO BÀ CON", "ƯU ĐÃI QUÀ")
CTA_QUA = ("BẤM GIỎ HÀNG", "ĐẶT NGAY TRONG GIỎ", "BẤM GIỎ NHẬN QUÀ")
_SO_CHU = {"mot": "1", "hai": "2", "ba": "3", "bon": "4", "nam": "5", "sau": "6", "bay": "7", "tam": "8", "chin": "9", "muoi": "10"}
_CHUNG = {"kem", "chai", "goi", "can", "binh", "hop", "tui", "lon", "phan", "cho", "va", "mot", "them"}


def _muc_qua(e):
    """Mức quà → (số lượng mua hoặc None, [từ khoá món quà không dấu])."""
    t = _kd(e)
    m = re.search(r"\bmua (\d+)", t)
    sau = (re.split(r"\b(?:tang|bieu)\b", t, maxsplit=1) + [t])[1]
    sau = re.split(r"\b(?:tri gia|gia tri)\b", sau)[0]
    tu = [w for w in re.findall(r"[a-z0-9]+", sau) if not w.isdigit()]
    return (m.group(1) if m else None), ([w for w in tu if w not in _CHUNG] or tu)


def qua_that_trong(chu, ds_qua):
    """Chữ thẻ chốt có nhắc tên một món quà thật trong hồ sơ (so không dấu, theo từ khoá món quà)?"""
    t = _kd(chu)
    return any(re.search(rf"\b{w}\b", t) for e in ds_qua or [] for w in _muc_qua(e)[1])


def chon_qua(st, text_loi="", rng=None):
    """Mức quà dùng cho CẢ video: lời nhắc mức nào (số lượng mua + tên món quà) → mức đó; không thì cảnh quà ở đoạn chốt (st['_qua_canh']: từ khoá kho quà); không thì rng bốc MỘT lần.
    Lưu st['_qua_chon'] để mọi bước sau dùng lại. Hồ sơ không có quà → ''."""
    if st.get("_qua_chon"):
        return st["_qua_chon"]
    ds = [str(x).strip() for x in (st.get("_qua") or []) if str(x).strip()]
    if not ds:
        return ""
    t = re.sub(r"\bmua (" + "|".join(_SO_CHU) + r")\b", lambda m: "mua " + _SO_CHU[m.group(1)], _kd(text_loi))
    best, diem = None, 0
    for e in ds:
        sl, tu = _muc_qua(e)
        hit = sum(1 for w in tu if re.search(rf"\b{w}\b", t))
        if hit and (sl is None or re.search(rf"\bmua {sl}\b", t)) and hit + (2 if sl else 0) > diem:
            best, diem = e, hit + (2 if sl else 0)
    if best is None:
        canh = [_kd(k) for k in (st.get("_qua_canh") or []) if _kd(k)]
        theo_canh = [e for e in ds if any(k in _kd(e) for k in canh)]
        best = (rng or random).choice(theo_canh or ds)
    st["_qua_chon"] = best
    return best


def dong_qua(e, rng):
    """Mức quà 'Mua 2 can tặng 1 chai TC01 trị giá 120k' → dòng 1 thẻ chốt ≤ 26 ký tự, IN HOA, GIỮ điều kiện mua + món quà; xoay 3 cách nói.
    Quá dài: bỏ giá trị trước, rồi bỏ '1 ' ở đầu món quà, rồi bỏ đơn vị ở điều kiện."""
    m = re.match(r"(?i)^(.*?)\b(?:tặng|biếu)\b[\s:]*(.*)$", str(e).strip())
    dk, mon = (m.group(1).strip(" ,:-–"), m.group(2).strip()) if m else ("", str(e).strip())
    mon = re.sub(r"(?i)^kèm\s+", "", mon)
    gia = re.search(r"(?i)\s*\(?(?:trị giá|giá trị)\b.*$", mon)
    gia_s, mon = (gia.group(0).strip(" ()"), mon[:gia.start()]) if gia else ("", mon)
    mon = mon.strip(" ,.)(")
    mon1 = re.sub(r"^1\s+", "", mon)
    mua = re.match(r"(?i)^mua\s+(.*)$", dk)
    sl = mua.group(1) if mua else ""
    sl2 = re.match(r"^\d+", sl).group(0) if re.match(r"^\d+", sl) else sl
    if mua:
        kieu = rng.choice((0, 1, 2))
        mau = [lambda it, c: f"MUA {c} TẶNG {it}", lambda it, c: f"TẶNG {it} KHI MUA {c}", lambda it, c: f"ĐẶT {c} – TẶNG {it}"][kieu]
        ds = [mau(mon + (" " + gia_s if gia_s else ""), sl), mau(mon, sl), mau(mon1, sl), mau(mon1, sl2), f"MUA {sl2} TẶNG {mon1}"]   # không bao giờ bỏ điều kiện mua (quá dài → cắt bớt đuôi tên quà)
    elif dk:
        ds = [f"{dk} TẶNG {mon}", f"{dk} TẶNG {mon1}"]
    else:
        ds = [f"TẶNG {mon}", f"TẶNG {mon1}"]
    ds = [x.upper() for x in ds]
    return next((x for x in ds if len(x) <= 26), None) or _cat_tu(ds[-1], 26)


def chot_qua(st, text_loi, rng):
    """Thẻ chốt quà của video: {'qua','dong1','dong2','loai','header'} hoặc None (hồ sơ không có quà). Chọn MỘT lần (rng) rồi lưu st['_qua_chot']."""
    if st.get("_qua_chot"):
        return st["_qua_chot"]
    e = chon_qua(st, text_loi, rng)
    if not e:
        return None
    c = {"qua": e, "dong1": dong_qua(e, rng), "dong2": rng.choice(CTA_QUA), "loai": rng.choice(CHOT_QUA), "header": rng.choice(HEADER_QUA)}
    st["_qua_chot"] = c
    return c

DATA_SPEC = """Nội dung khối (chữ IN HOA ngắn, đúng sự thật sản phẩm; mỗi dòng ≤ 26 ký tự):
- chu_dap|chu_mat_na|chu_nghieng|chu_tang|chu_gach (chữ phá cách): {"text": "≤28 ký tự, ≤14/dòng", "nhan": <chỉ số chữ nhấn>}; chu_so: {"so": "240", "don_vi": "ML", "nhan_tren": "tuỳ chọn"}
- mỗi mục khối có thể thêm "tu"/"den" (chỉ số từ đầu/cuối trong lời), "vi_tri": "tren"|"giua"|"duoi", "am": "<họ âm>"|"khong"
- hook_*: {"text": "<câu mở ≤ 28 ký tự>"}; hook_dap thêm "nhan": <chỉ số chữ cần tô, 0-based>; hook_bang thêm "mau": "do"|"xanh"
- checklist: {"tieu_de": "<tuỳ chọn>", "items": ["<2–4 ý ≤ 22 ký tự>"]}
- so_dem: {"nhan_trai": "1 CHAI", "so": <số có trong sự thật: 200, 300, 500, 15000…>, "don_vi": "LÍT"}
- so_sanh: {"trai_tieu_de": "LOẠI THƯỜNG", "trai": ["≤3 ý"], "phai_tieu_de": "<TÊN SẢN PHẨM>", "phai": ["≤3 ý"]}  (không nêu tên hãng khác)
- vong_tron: {"nhan": "..."} · lower_third: {"dong1": "<TÊN SẢN PHẨM IN HOA>", "dong2": "..."} · nhan_dan: {"text": "≤ 16 ký tự"}
- da_quang: {"text"} · canh_bao: {"tieu_de": "LƯU Ý", "text"} · dai_chay: {"text"} · bong_chu: {"text": "≤ 14 ký tự"} · mui_ten_chi: {"text"}
- hop_qua: {"dong1", "dong2"} · bang_qua: {"tieu_de", "cac_muc": ["Mua 1 chai: ...", ...]} · nut_gio_hang: {"dong1", "text"} · the_qua: {"dong1", "dong2", "kieu": "hop_do|hop_xanh|nhan_vang|the_trang"}"""


def fallback(ten):
    """Khối giữa dự phòng CHUNG cho mọi sản phẩm — chỉ dùng tên sản phẩm (lỗi rà soát #5: trước đây cứng chữ Nano Đồng)."""
    ten = (ten or "").upper()[:30]
    return {"lower_third": {"dong1": ten, "dong2": "Chính hãng Toàn Cầu"}, "nhan_dan": {"text": "CHÍNH HÃNG"},
            "vong_tron": {"nhan": ten[:22]}, "mui_ten_chi": {"text": ten[:22]}, "dai_chay": {"text": ten}}


def _txt(x, n=34):
    return re.sub(r"\s+", " ", str(x or "")).strip()[:n]


KHOI_CHU_LON_TAM = {"chu_dap", "chu_mat_na", "chu_nghieng", "chu_tang", "chu_so", "chu_gach"}


def clean_data(loai, d, hop=None):
    """Kiểm/cắt nội dung khối; trả None nếu khối không dùng được. hop = so_cho_phep(st) (None → SO_HOP_LE)."""
    d = dict(d or {})
    if loai.startswith("hook_"):
        if not d.get("text"):
            return None
        d["text"] = _txt(d["text"], 30)
    elif loai in KHOI_CHU_LON_TAM:
        if loai == "chu_so":
            so = re.sub(r"[^0-9.,–\-/ ]", "", str(d.get("so") if d.get("so") is not None else d.get("text") or "")).strip()[:8]
            if not so:
                return None
            d["so"] = so
            d["don_vi"] = _txt(d.get("don_vi"), 12); d["nhan_tren"] = _txt(d.get("nhan_tren"), 20)
        else:
            if not d.get("text"):
                return None
            d["text"] = _cat_tu(d["text"], 28)
        if d.get("nhan") is not None:
            d["nhan"] = _nguyen(d["nhan"], -1)
    elif loai == "checklist":
        items = [_txt(i, 24) for i in d.get("items", []) if i][:4]
        if len(items) < 2:
            return None
        d["items"] = items
    elif loai == "so_dem":
        n = _so(d.get("so"))
        if n is None or not n[1] or not _so_ok(n[0], d.get("don_vi"), hop):       # số thập phân: khối đếm chỉ nhận số nguyên → xep_khoi đổi sang chu_so
            return None
        d["so"] = int(n[0])
    elif loai == "so_sanh":
        if not d.get("trai") or not d.get("phai"):
            return None
    elif loai in ("hop_qua", "the_qua"):
        if not d.get("dong1"):
            return None
    elif loai == "bang_qua":
        if not d.get("cac_muc"):
            return None
    elif loai in ("vong_tron", "nhan_dan", "da_quang", "canh_bao", "dai_chay", "bong_chu", "mui_ten_chi", "lower_third", "nut_gio_hang"):
        if not any(d.get(k) for k in ("text", "nhan", "dong1")):
            return None
    return d


def _nguyen(v, mac=None):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return mac


def _cat_tu(x, n):
    """Cắt ở ranh giới từ, tối đa n ký tự."""
    t = _txt(x, 400)
    if len(t) <= n:
        return t
    c = t[:n]
    return c.rsplit(" ", 1)[0] if " " in c and t[n] != " " else c


def mo_ta_khoi():
    """Mô tả từng loại khối (đạo diễn đọc để chọn): {loai: {nhom, mo_ta, du_lieu, toi_da}}. Prompt đạo diễn sinh từ đây."""
    m = {}

    def them(loai, nhom, mo_ta, du_lieu, toi_da):
        m[loai] = {"nhom": nhom, "mo_ta": mo_ta, "du_lieu": du_lieu, "toi_da": toi_da}
    CL = "chữ rất to (khoảng 100–150 px), viền dày, 1–2 dòng, một chữ nhấn màu"
    them("chu_dap", "chu_lon", f"Chữ phá cách kiểu ĐẬP: {CL}; phóng to rồi đập vào màn, rung nhẹ. Hợp câu mở, lời khẳng định, cảnh báo mạnh; dùng được ở bất kỳ đâu.",
         {"text": "chữ chính", "nhan": "số thứ tự chữ tô ô vàng (0 là chữ đầu, -1 không tô)"}, "28 ký tự, ≤14 ký tự/dòng")
    them("chu_mat_na", "chu_lon", f"Chữ phá cách kiểu MẶT NẠ: {CL}; thanh màu quét ngang lộ chữ dần. Hợp ý chính sang trọng, tên riêng, ý mới bắt đầu.",
         {"text": "chữ chính", "nhan": "chữ tô màu nhấn"}, "28 ký tự, ≤14 ký tự/dòng")
    them("chu_nghieng", "chu_lon", f"Chữ phá cách kiểu NGHIÊNG: {CL}; cả cụm nghiêng nhẹ, chữ nhấn nằm trong ô màu nghiêng ngược. Hợp lời nhắn vui, nhắc nhở, 'đừng…'.",
         {"text": "chữ chính", "nhan": "chữ nằm trong ô màu"}, "28 ký tự, ≤14 ký tự/dòng")
    them("chu_tang", "chu_lon", "Chữ phá cách kiểu XẾP TẦNG: dòng trên nhỏ, dòng dưới rất to màu nhấn, hai dòng vào từ hai phía. Hợp cụm 'một việc + kết quả' (ĐỪNG ĐỂ / BÔNG RỤNG).",
         {"text": "2–4 từ; từ cuối thành dòng to"}, "28 ký tự, ≤14 ký tự/dòng")
    them("chu_so", "chu_lon", "Chữ phá cách kiểu SỐ + ĐƠN VỊ: con số cực to (~240 px) màu nhấn, đơn vị bên dưới, nhãn nhỏ phía trên tuỳ chọn. Hợp liều pha, số lượng, giá. Số phải có trong sự thật sản phẩm.",
         {"so": "240 | 3–5", "don_vi": "ML | CON / LÁ", "nhan_tren": "tuỳ chọn"}, "số ≤8 ký tự; đơn vị ≤12; nhãn ≤20")
    them("chu_gach", "chu_lon", f"Chữ phá cách kiểu GẠCH CHÂN: {CL}; nét gạch tô vẽ dần dưới chữ nhấn. Hợp điều cần ghi nhớ.",
         {"text": "chữ chính", "nhan": "chữ được gạch chân"}, "28 ký tự, ≤14 ký tự/dòng")
    them("hook_dap", "mo", "Câu mở 118 px đập vào giữa màn hình, chữ nhấn trong ô vàng. Hợp câu mở gây sốc.", {"text": "câu mở", "nhan": "chỉ số chữ tô"}, "30 ký tự")
    them("hook_tung_tu", "mo", "Câu mở từng chữ xếp tầng, so le trái phải (84–100 px). Hợp câu mở 2–4 chữ ngắn.", {"text": "câu mở"}, "30 ký tự")
    them("hook_go_may", "mo", "Câu mở gõ chữ trong ô trắng kiểu tin nhắn (64 px). Hợp câu hỏi, lời bí mật. Âm: tiếng phím.", {"text": "câu mở"}, "30 ký tự")
    them("hook_mat_na", "mo", "Câu mở 92 px lộ sau thanh màu quét. Hợp câu mở sang, kể chuyện.", {"text": "câu mở"}, "30 ký tự")
    them("hook_tem", "mo", "Câu mở trong con tem đỏ đóng dấu nghiêng (76 px). Hợp tin nhanh, cảnh báo.", {"text": "câu mở"}, "30 ký tự")
    them("hook_bang", "mo", "Câu mở trên dải băng đỏ/xanh chạy vào từ trái (70 px).", {"text": "câu mở", "mau": "do|xanh"}, "30 ký tự")
    them("hook_hoi", "mo", "Câu hỏi trong bong bóng thoại trắng viền vàng (66 px).", {"text": "câu hỏi"}, "30 ký tự")
    them("checklist", "giua", "Bảng tích xanh 2–4 ý hiện lần lượt (52 px). Hợp liệt kê lý do/bước.", {"tieu_de": "tuỳ chọn", "items": ["ý ngắn"]}, "4 ý, 24 ký tự/ý")
    them("so_dem", "giua", "Nhãn trái → số đếm chạy lên (132 px) + đơn vị. Số phải có trong sự thật sản phẩm.", {"nhan_trai": "1 CHAI", "so": "số", "don_vi": "LÍT"}, "số trong danh sách hợp lệ")
    them("so_sanh", "giua", "Bảng 2 cột ✗ thường / ✓ sản phẩm (40–44 px). Hợp so sánh; không nêu tên hãng khác.", {"trai_tieu_de": "", "trai": ["ý"], "phai_tieu_de": "", "phai": ["ý"]}, "3 ý/cột")
    them("vong_tron", "giua", "Vòng tròn vàng vẽ quanh sản phẩm giữa màn + nhãn nhỏ. Hợp khi sản phẩm đang ở giữa khung.", {"nhan": "nhãn"}, "22 ký tự")
    them("lower_third", "giua", "Thanh tên sản phẩm góc dưới trái (58 px, nền đỏ), cố định y≈1160.", {"dong1": "TÊN SẢN PHẨM", "dong2": "ý phụ"}, "26 ký tự")
    them("nhan_dan", "giua", "Nhãn dán răng cưa đỏ xoay, góc phải trên (44 px).", {"text": "ngắn"}, "16 ký tự")
    them("da_quang", "giua", "Bút dạ quang: dải vàng quét phủ cả dòng (84 px), chữ đen. Hợp câu nhấn dài hơn chữ phá cách.", {"text": "câu"}, "36 ký tự, 18/dòng")
    them("canh_bao", "giua", "Băng cảnh báo vàng-đen có tiêu đề + dòng chữ (58 px). Hợp lỗi sai/điều cấm.", {"tieu_de": "LƯU Ý", "text": "nội dung"}, "30 ký tự")
    them("dai_chay", "giua", "Dải chữ chạy ngang nền vàng nghiêng (56 px). Ít dùng — dễ rối.", {"text": "ngắn"}, "30 ký tự")
    them("bong_chu", "giua", "Chữ nổ trên ngôi sao vàng quay (84 px). Ít dùng.", {"text": "ngắn"}, "14 ký tự")
    them("mui_ten_chi", "giua", "Nhãn trắng + mũi tên vàng chỉ xuống sản phẩm.", {"text": "ngắn"}, "22 ký tự")
    them("hop_qua", "chot", "Hộp quà bật nắp + pháo giấy, bảng 2 dòng (60/42 px). Hợp chốt khi quà là chính.", {"dong1": "quà", "dong2": "điều kiện"}, "26 ký tự/dòng")
    them("bang_qua", "chot", "Bảng các mức quà 2–4 dòng (40 px) lấy từ hồ sơ sản phẩm.", {"tieu_de": "", "cac_muc": ["Mua 1 chai: …"]}, "4 mức")
    them("nut_gio_hang", "chot", "Nút giỏ hàng đỏ nhấp nháy (70 px) + dòng trên. Chốt gọn nhất.", {"dong1": "", "text": "BẤM GIỎ HÀNG"}, "26 ký tự")
    them("the_qua", "chot", "Thẻ quà 2 dòng (70/52 px), kiểu hop_do|hop_xanh|nhan_vang|the_trang.", {"dong1": "", "dong2": "", "kieu": "hop_do|hop_xanh|nhan_vang|the_trang"}, "26 ký tự/dòng")
    return m


KHOI_CHU_LON = ["chu_dap", "chu_mat_na", "chu_nghieng", "chu_tang", "chu_so", "chu_gach"]
KHOI_TAT_CA = sorted(mo_ta_khoi())                   # mọi loại khối Remotion đã đăng ký (REGISTRY trong Blocks.tsx)
KHOI_NOI_BAT = {"bong_chu", "da_quang", "so_dem", "canh_bao"} | set(KHOI_CHU_LON)   # cộng thêm mọi hook_* và khối chốt
MAX_KHOI = 8
VI_TRI_ZONE = {"tren": "TOP", "giua": "MID", "duoi": "LOWER"}
VI_TRI_TOP = {"tren": 250, "giua": 720, "duoi": 1060}


def _xung(a, b):
    return a == b or "CENTER" in (a, b)


def xep_khoi(recipe_key, khoi_ai, sents, total, st, rng, ten_thuong_hieu, words=None):
    """→ (blocks, cta_f0). Khối {loai,f0,f1,data,zone[,top,am,vi_tri,co_dinh]} đã xếp vùng, không đè nhau trong cùng vùng.
    Đạo diễn đặt tối đa MAX_KHOI khối; mỗi mục: {"loai","tu","den" (chỉ số TỪ trong lời, gồm cả "den"),"du_lieu",["vi_tri": tren|giua|duoi],["am"]}
    hoặc kiểu cũ {"loai","cau"}. Loại nào đã đăng ký cũng dùng được; danh sách trong công thức chỉ dùng cho dự phòng khi đạo diễn không nêu."""
    R = RECIPES[recipe_key]
    dur_f = int(round(total * FPS))
    S = lambda i: sents[max(0, min(i, len(sents) - 1))]
    nw = len(words or [])
    sach = []                                         # đạo diễn trả rác → bỏ/ép kiểu an toàn (lỗi rà soát #2)
    hop = so_cho_phep(st)
    for k in khoi_ai or []:
        if not isinstance(k, dict) or not isinstance(k.get("loai"), str) or k["loai"] not in KHOI_TAT_CA:
            continue
        loai_k, du = k["loai"], (k.get("du_lieu") if isinstance(k.get("du_lieu"), dict) else {})
        if loai_k == "so_dem":
            n = _so(du.get("so"))
            if n is None or not _so_ok(n[0], du.get("don_vi"), hop):
                continue
            if not n[1]:                              # thập phân (1,12): khối đếm chỉ có số nguyên → giữ thành chữ số to tĩnh
                loai_k, du = "chu_so", {"so": str(du["so"]), "don_vi": du.get("don_vi") or "", "nhan_tren": du.get("nhan_trai") or ""}
        d = clean_data(loai_k, du, hop)
        if d is None:
            continue
        it = {"loai": loai_k, "du_lieu": d, "cau": _nguyen(k.get("cau"), 1), "tu": None, "den": None,
              "vi_tri": k.get("vi_tri") if k.get("vi_tri") in VI_TRI_ZONE else None,
              "am": k.get("am") if isinstance(k.get("am"), str) and k.get("am") else None}
        tu = _nguyen(k.get("tu"))
        if tu is not None and nw:                     # mốc theo chỉ số từ của lời
            tu = max(0, min(tu, nw - 1))
            den = _nguyen(k.get("den"), tu + 3)
            den = max(tu, min(den, nw - 1))
            it["tu"], it["den"] = tu, den
        sach.append(it)
    sach = sach[:MAX_KHOI]
    toi_thieu = lambda loai: int((1.0 if loai.startswith("hook_") or loai in KHOI_NOI_BAT else 1.4) * FPS)

    def khung(it):                                    # (f0, f1) theo từ, None nếu kiểu cũ
        if it["tu"] is None:
            return None
        a = max(0, int(round(words[it["tu"]]["s"] * FPS)))
        b = int(round(words[it["den"]]["e"] * FPS)) + int(0.3 * FPS)
        return a, max(b, a + toi_thieu(it["loai"]))

    hook, cta, mids = None, None, []
    for it in sach:
        fr = khung(it)
        if hook is None and it["loai"] in KHOI_MO and (fr is None or fr[0] <= 3 * FPS):
            hook = (it, fr)
        elif cta is None and it["loai"] in KHOI_CHOT:
            cta = (it, fr)
        else:
            mids.append((it, fr))
    if not mids and not sach and len(sents) >= 4:    # đạo diễn không nêu gì → dự phòng theo công thức (luôn có 1 khối nhấn giữa bài)
        fb = fallback(ten_thuong_hieu)
        hop = [m for m in R["giua"] if m in fb]
        if hop:
            loai = rng.choice(hop)
            mids.append(({"loai": loai, "du_lieu": dict(fb[loai]), "cau": rng.choice(range(1, len(sents) - 1)), "tu": None, "den": None, "vi_tri": None, "am": None}, None))
    som = any(fr and fr[0] < int(1.5 * FPS) for _, fr in mids)         # đạo diễn đã đặt khối ngay đầu bài → không chèn câu mở dự phòng
    h_it = h_fr = hook_loai = hook_data = None
    if hook:
        h_it, h_fr = hook
        hook_loai, hook_data = h_it["loai"], h_it["du_lieu"]
    elif not som:
        h_it = {"vi_tri": None, "am": None}
        hook_data = {"text": _txt(st.get("chu_the_mo") or ten_thuong_hieu, 30), "nhan": 0}
        hook_loai = st.get("ep_mo") or rng.choice(R["mo"])
    ct_qua = chot_qua(st, " ".join(s.get("text") or " ".join(w.get("w", "") for w in s.get("words") or []) for s in sents), rng)   # mọi video chốt bằng một mức quà thật (None: hồ sơ không có quà)
    d1, d2 = st.get("chu_chot_1") or "QUÀ TẶNG THEO ĐƠN", st.get("chu_chot_2") or "BẤM GIỎ HÀNG"
    if ct_qua:
        d1, d2 = ct_qua["dong1"], st.get("chu_chot_2") or ct_qua["dong2"]
    c_it = cta[0] if cta else {"vi_tri": None, "am": None}
    if cta:
        loai_chot = cta[0]["loai"]
    elif ct_qua:                                        # có quà → luôn thẻ quà (không nút giỏ hàng trơn); giữ ep_chot nếu nó đã là thẻ quà
        loai_chot = st["ep_chot"] if st.get("ep_chot") in CHOT_QUA else ct_qua["loai"]
    else:
        loai_chot = st.get("ep_chot") or "the_qua"
    data = dict(cta[0]["du_lieu"]) if cta else {}
    data.setdefault("dong1", d1); data.setdefault("dong2", d2); data.setdefault("text", d2)
    if ct_qua and loai_chot != "bang_qua" and not qua_that_trong(f'{data.get("dong1", "")} {data.get("dong2", "")}', st.get("_qua")):
        data.update(dong1=d1, dong2=d2, text=d2)        # chữ quà đạo diễn ghi không nhắc món quà nào trong hồ sơ → dùng mức quà thật
    if "kieu" not in data:
        data["kieu"] = rng.choice(["hop_do", "hop_xanh", "nhan_vang", "the_trang"])
    if loai_chot == "bang_qua" and not data.get("cac_muc"):
        data["cac_muc"] = st.get("_qua") or []          # lấy đúng các mức quà trong hồ sơ sản phẩm
        if ct_qua:
            data.setdefault("tieu_de", ct_qua["header"])
        if not data["cac_muc"]:
            loai_chot = "hop_qua"
    cta_f0 = max(int(round((sents[-1]["s"] - 0.15) * FPS)), dur_f - 5 * FPS)
    if cta and cta[1]:                                  # đạo diễn nêu mốc chốt → tôn trọng, nhưng chốt không dài quá 7 s
        cta_f0 = max(dur_f - 7 * FPS, cta[1][0])
    blocks = []

    def gan(b, it):
        if it.get("am"):
            b["am"] = it["am"]
        if it.get("vi_tri"):
            b["vi_tri"] = it["vi_tri"]; b["zone"] = VI_TRI_ZONE[it["vi_tri"]]; b["top"] = VI_TRI_TOP[it["vi_tri"]]; b["co_dinh"] = True
        return b

    if h_it is not None:
        if h_fr:
            f0, f1 = max(2, h_fr[0]), h_fr[1]
        else:
            h_end = 1.5 if hook_loai == "hook_dap" else min(S(0)["e"] + 0.3, 3.2)
            f0, f1 = 2, int(h_end * FPS)
        zone = "CENTER" if hook_loai == "hook_dap" else "TOP"
        blocks.append(gan({"loai": hook_loai, "f0": f0, "f1": f1, "data": hook_data, "zone": zone}, h_it))
    ds = []
    for it, fr in mids:
        if fr is None:                                  # kiểu cũ: theo câu
            ci = it["cau"] if it["cau"] is not None else 1
            ci = max(1, min(ci, len(sents) - 2)) if len(sents) > 2 else 0
            a = int(S(ci)["s"] * FPS)
            b = int(min(S(ci)["e"] + 0.4, S(ci)["s"] + 4.2) * FPS)
            fr = (a, max(b, a + int(1.8 * FPS)))
        ds.append((fr[0], fr[1], it))
    ds.sort(key=lambda x: x[0])
    for a, b, it in ds:
        loai = it["loai"]
        zone = VI_TRI_ZONE.get(it["vi_tri"]) or ZONE.get(loai, "TOP")
        clash = [x for x in blocks if _xung(x["zone"], zone) and not (b <= x["f0"] or a >= x["f1"])]
        if clash:
            moi = max(x["f1"] for x in clash) + 3
            if moi - a > int(0.6 * FPS):               # phải chờ quá lâu → bỏ, không vẽ đè
                continue
            if it["tu"] is None:
                b = max(b, moi + int(1.6 * FPS))
            a = moi
        if b > cta_f0 - 3:
            b = cta_f0 - 3
        if b - a < min(toi_thieu(loai), int(1.4 * FPS)):
            continue
        blocks.append(gan({"loai": loai, "f0": a, "f1": b, "data": it["du_lieu"], "zone": zone}, it))
    blocks.sort(key=lambda x: x["f0"])
    c = {"loai": loai_chot, "f0": cta_f0, "f1": dur_f, "data": data, "zone": "TOP"}
    blocks.append(gan(c, c_it))
    return blocks, cta_f0


def khung_tron(doan, blocks, nguong=0.4, toi_thieu=1.2):
    """Đoạn hình 'trơ': bố cục toàn màn (day/day_zoom) dài ≥ toi_thieu giây mà khối nổi bật (câu mở, chữ phá cách, chốt, chữ to)
    phủ < nguong thời lượng. → [[t0, t1], ...] (giây). Chỉ báo, không tự thêm chữ."""
    nb = [(b["f0"] / FPS, b["f1"] / FPS) for b in blocks or []
          if b["loai"].startswith("hook_") or b["loai"] in KHOI_NOI_BAT or b["loai"] in KHOI_CHOT]
    out = []
    for d in doan or []:
        t0, t1 = float(d["t0"]), float(d["t1"])
        if d.get("bo_cuc") not in ("day", "day_zoom") or t1 - t0 < toi_thieu:
            continue
        ev = sorted((max(a, t0), min(b, t1)) for a, b in nb if b > t0 and a < t1)
        phu, cuoi = 0.0, t0
        for a, b in ev:                                  # hợp các khoảng (tránh tính trùng)
            a = max(a, cuoi)
            if b > a:
                phu += b - a; cuoi = b
        if phu / (t1 - t0) < nguong:
            out.append([round(t0, 2), round(t1, 2)])
    return out


def chon_atmos(recipe_key, rng, cuts_f):
    a = RECIPES[recipe_key]["atmos"]
    return {"vignette": rng.random() < a["vignette"], "grain": rng.random() < a["grain"], "leaks": [],
            "hue": rng.choice([0, 20, 40, 300, 330])}


def chu_ky(info):
    """Chữ ký phong cách để chống lặp trong ngày."""
    return "|".join(str(info.get(k)) for k in ("cong_thuc", "hook", "phu_de", "chot", "sfx"))


TAT_CA = {"phu_de": ["to_dan", "mo_sang", "o_nhay", "gach_chay", "nhich_len", "hop_mo", "quet_mau", "vien_day"],
          "sfx": ["gon", "vua", "soi_dong", "mo_dau_am"]}


CT_HOP = {   # dạng bài (THAN trong viet_loi.py) → các công thức hợp (tiện nhất đứng trước); không biết dạng → mọi công thức
    "van_de_giai_phap": ["tin_nhanh", "ke_chuyen", "soi_dong", "tvc_sang"], "ba_sai_lam": ["danh_sach", "tin_nhanh", "soi_dong"],
    "so_sanh": ["so_sanh", "con_so", "tvc_sang", "soi_dong"], "go_ngai": ["so_sanh", "ke_chuyen", "tvc_sang"],
    "phep_tinh": ["con_so", "danh_sach", "so_sanh"], "vi_sao": ["ke_chuyen", "tvc_sang", "so_sanh"],
    # khoá cũ (kịch bản/thống kê đã lưu trước khi đổi bộ THAN) — giữ để vẫn xếp được công thức
    "truoc_sau": ["so_sanh", "ke_chuyen", "tvc_sang", "soi_dong"], "chuyen_that_bai": ["ke_chuyen", "tin_nhanh", "soi_dong"],
    "hoai_nghi": ["so_sanh", "ke_chuyen", "tvc_sang"],
    "tung_buoc": ["danh_sach", "ke_chuyen", "tvc_sang"], "khach_hoi": ["ke_chuyen", "so_sanh", "tin_nhanh"],
    "soi_nhan": ["tvc_sang", "danh_sach", "so_sanh", "con_so"], "dau_hieu": ["danh_sach", "tin_nhanh", "ke_chuyen"],
    "khang_dinh": ["tvc_sang", "soi_dong", "qua_tang"],
}


def ct_hop(dang=None, goc=None):
    """Công thức hợp với kịch bản (dạng bài + góc bán). Góc nhắc quà → thêm qua_tang. Trống/không biết → tất cả."""
    ds = list(CT_HOP.get(str(dang or ""), []))
    if re.search(r"qua|tang|gift", str(goc or "").lower()) and "qua_tang" not in ds:
        ds.append("qua_tang")
    return ds or list(RECIPES)


def dem_cong_thuc(used_sigs):
    """Số chữ ký (≈ số video) đã dùng của từng công thức trong ngày."""
    counts = {k: 0 for k in RECIPES}
    for s in used_sigs:
        k = str(s).split("|")[0]
        if k in counts:
            counts[k] += 1
    return counts


def ct_cho_dao_dien(used_sigs, bo=2):
    """Danh sách công thức đưa đạo diễn chọn: bỏ `bo` công thức DÙNG NHIỀU NHẤT trong ngày (nếu thật sự nhiều hơn công thức ít nhất)."""
    c = dem_cong_thuc(used_sigs); low = min(c.values())
    nhieu = [k for k in sorted(c, key=lambda k: (-c[k], k))[:bo] if c[k] > low]
    return [k for k in RECIPES if k not in nhieu]


def chuan_hoa(st, rng, used_sigs, tu_do=False, dang=None, goc=None):
    """Ép phương án AI vào đúng công thức + chống trùng chữ ký trong ngày. Trả st mới (có ep_mo/ep_chot/sfx).
    tu_do=True (AI đạo diễn): tôn trọng công thức AI chọn CHỈ KHI nó không bị dùng quá tay hôm nay (số dùng ≤ ít nhất + 1);
    quá tay → đổi sang công thức ít dùng nhất hợp kịch bản (dang/goc: xem ct_hop) và các lựa chọn theo công thức cũ được bốc lại.
    Chống trùng chữ ký (mở/đóng/phụ đề/sfx) luôn chạy."""
    st = dict(st)
    hop = ct_hop(dang, goc)
    counts = dem_cong_thuc(used_sigs)
    low = min(counts.values())
    key0 = st.get("cong_thuc") if st.get("cong_thuc") in RECIPES else None
    ap_dung = (lambda ks: [k for k in ks if counts[k] == min(counts[x] for x in ks)])
    if key0 is None:
        key = rng.choice(ap_dung(hop))
    elif tu_do:
        key = key0
        if counts[key0] > low + 1:
            thay = ap_dung(hop)
            key = rng.choice(thay) if counts[thay[0]] < counts[key0] else key0
    else:
        key = key0
        if counts[key0] > low:
            thap = [k for k, v in counts.items() if v == low]
            key = rng.choice([k for k in thap if k in hop] or thap)
    doi = key != key0
    if doi:
        st["khoi"] = [k for k in st.get("khoi", []) if k.get("loai") in KHOI_TAT_CA]     # đổi công thức vẫn giữ khối đạo diễn đã nêu
    R = RECIPES[key]
    st["cong_thuc"] = key
    tu = tu_do and not doi                           # đổi công thức → các lựa chọn của AI thuộc công thức cũ, bốc lại theo công thức mới
    for k in ("phu_de", "chuyen_canh", "chuyen_dong", "mau", "nhac"):
        if tu and st.get(k) and (k != "phu_de" or st[k] in TAT_CA["phu_de"]):
            continue
        if st.get(k) not in R[k]:
            st[k] = rng.choice(R[k])
    st["nhip"] = R["nhip"]
    ok_sfx = TAT_CA["sfx"] if tu else R["sfx"]
    st["sfx"] = st.get("sfx") if st.get("sfx") in ok_sfx or st.get("sfx") == "em" else rng.choice(R["sfx"])
    ai_mo = [k.get("loai") for k in st.get("khoi", []) if k.get("loai") in KHOI_MO]
    ai_chot = [k.get("loai") for k in st.get("khoi", []) if k.get("loai") in KHOI_CHOT]
    st["ep_mo"] = ai_mo[0] if ai_mo else rng.choice(R["mo"])
    st["ep_chot"] = ai_chot[0] if ai_chot else rng.choice(R["chot"])
    for _ in range(12):                          # đổi dần cho tới khi không trùng video nào trong ngày (luôn chạy, kể cả tu_do)
        sig = chu_ky({"cong_thuc": key, "hook": st["ep_mo"], "phu_de": st["phu_de"], "chot": st["ep_chot"], "sfx": st["sfx"]})
        if sig not in used_sigs:
            break
        what = rng.choice(["phu_de", "mo", "chot", "sfx"])
        if what == "phu_de":
            st["phu_de"] = rng.choice(R["phu_de"])
        elif what == "mo":
            st["ep_mo"] = rng.choice(R["mo"])
        elif what == "chot":
            st["ep_chot"] = rng.choice(R["chot"])
        else:
            st["sfx"] = rng.choice(R["sfx"])
    sig = chu_ky({"cong_thuc": key, "hook": st["ep_mo"], "phu_de": st["phu_de"], "chot": st["ep_chot"], "sfx": st["sfx"]})
    used_sigs.add(sig)
    return st

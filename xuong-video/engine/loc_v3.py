"""BỘ LỌC ỨNG VIÊN CẢNH KIỂU 3 (phiếu v3.1) — bản CHẠY BÓNG: tính song song với bộ lọc cũ để so sánh, CHƯA dùng để chọn cảnh.
Nguồn gốc: máy thử P:\\_thu-dot1\\hoc-lai\\v3\\loc\\loc.py (Hit@6 79% so với 50% của bộ cũ, 0 cảnh cấm lọt so với 77), đã sửa theo SOAT.md mục 4:
  1. đặc trưng cảnh tính MỘT lần cho cả kho (dac_trung), chuẩn hóa câu một lần, luật cứng trước khi chấm, dưới sàn bỏ trước khi sắp xếp;
  2. đích (dich) chỉ tính trên CHÍNH việc được đòi, loài cây giữ hậu tố (cay_an_trai:xoai ≠ cay_an_trai:thanh_long), ĐÚNG chỉ khi đủ điều kiện bắt buộc;
  3. hệ số nét không vượt 1, tổng điểm chặn ở 100;
  4. câu thiếu y_hinh → yêu cầu tối thiểu dựng từ câu + y_canh, gắn suy=True (chỉ được MINH HỌA);
  6. nhãn đúng/minh họa thuộc cặp (câu, id).
Không gọi AI, không đọc file, không đụng bộ sinh số ngẫu nhiên của video (tự dựng Random theo seed)."""
import math, random, re, unicodedata
from pathlib import Path

import phieu_v3

MAC_DINH = (70, 50)          # (ngưỡng ĐÚNG, sàn MINH HỌA) — số báo cáo của máy thử
TOP = 6                      # số cảnh/câu
TOI_DA_MOI_FILE = 2          # đa dạng: ≤ 2 đoạn của cùng MỘT file nguồn cho mỗi câu
W_MET = 3.0                  # 1 đơn vị mệt = trừ 3 điểm khi XẾP (thang 100). Chỉ đổi thứ tự trong số cảnh đã qua sàn, không đổi nhãn/không kéo cảnh dưới sàn lên
NHOM_VIEC = {"rot": "pha", "khuay": "pha", "lac": "pha", "mo_nap": "pha", "cam_xem": "cam", "xoay_nhan": "cam", "noi_vao_may": "cam",
             "lat_la": "cay", "vuot_la": "cay", "dap_la": "cay", "lau_la": "cay", "chi_vao": "cay", "di_xem": "cay", "phun": "phun", "tuoi": "tuoi"}
VIEC_BO = {"khong", "khac"}  # "không có việc" / việc lạ: không dùng để khớp việc được đòi

# từ đệm tiếng Việt (không dấu) — không tính vào độ trùng nghĩa
_DEM = frozenset("""cac nhung mot cua cho voi nhu khi thi neu hay roi cung van con dang duoc bao nay kia day khong nao ban nguoi nhieu
nhat rat qua con vao ra tren duoi trong ngoai sau truoc den tai boi vi nen ma ten la co bi se da dang lai nua thoi luon chi
hon hoac nhung tung moi thay lam gi sao dau cung nhe nhin the giua phai can muon cua""".split())


# ---------------------------------------------------------------- chuẩn hóa chữ
def khong_dau(s):
    s = unicodedata.normalize("NFD", str(s or "").lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _ma_day(x):
    """Mã chuẩn hóa, GIỮ hậu tố ('cay_an_trai:xoai'); None nếu rỗng."""
    if x is None or isinstance(x, (dict, list, bool)):
        return None
    goc, _, hau = khong_dau(x).strip().partition(":")
    goc, hau = re.sub(r"\s+", "_", goc.strip()), re.sub(r"\s+", "_", hau.strip())
    return (goc + (":" + hau if hau else "")) or None


def _ma(x):
    """Mã gốc, BỎ hậu tố."""
    m = _ma_day(x)
    return m.split(":")[0] if m else None


def _ds_ma(x, day=False):
    if isinstance(x, str):
        x = [x]
    out = []
    for i in x if isinstance(x, (list, tuple)) else []:
        m = (_ma_day if day else _ma)(i)
        if m and m not in out:
            out.append(m)
    return out


def _tu(s):
    """Tập từ nghĩa (không dấu, > 2 ký tự, bỏ từ đệm)."""
    return {t for t in re.findall(r"[a-z0-9]+", khong_dau(s)) if len(t) > 2 and t not in _DEM}


def _chuoi(s):
    """Chuỗi từ liền nhau, bọc dấu cách hai đầu — để tìm cụm từ khóa theo ranh giới từ."""
    return " " + " ".join(re.findall(r"[a-z0-9]+", khong_dau(s))) + " "


def _so(x, mac=None):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else mac


def chuan_nguong(nguong):
    """(dung, minh_hoa) hợp lệ theo 0 ≤ mh < dung ≤ 100, sai bất kỳ chỗ nào → quay về mặc định (70, 50) cả cặp."""
    try:
        d, m = (_so(x) for x in nguong)
    except Exception:
        return MAC_DINH
    if d is None or m is None or not (0 <= m < d <= 100):
        return MAC_DINH
    return d, m


# ---------------------------------------------------------------- 1. đặc trưng cảnh (tính một lần)
def _dac_trung_mot(s):
    sid = s.get("id")
    v3 = s.get("v3") if isinstance(s.get("v3"), dict) else None
    f = {"id": sid, "file": Path(str(s.get("file") or "")).as_posix(), "tu": _so(s.get("tu"), 0.0), "den": _so(s.get("den"), 0.0),
         "kieu3": s.get("kieu") == 3 and v3 is not None, "cam": [str(x) for x in (s.get("cam") or [])]}
    f["dai"] = _so(s.get("dai"), None)
    if f["dai"] is None:
        f["dai"] = max(0.0, f["den"] - f["tu"])
    if not f["kieu3"]:
        return f
    vat = s.get("vat")
    V = {x["id"]: x for x in vat if isinstance(x, dict) and "id" in x} if isinstance(vat, list) else dict(vat or {})
    try:                                                 # luật cấm tính lại từ phiếu gốc (đai an toàn): cam của kho + cam tính lại, hợp hai bên
        f["cam"] = sorted(set(f["cam"]) | set(phieu_v3.cam(v3, V)))
    except Exception:
        pass
    # việc: mã đầy đủ (giữ 'khac:...'), mã gốc, đích CỦA CHÍNH việc đó
    viec = []
    for a in v3.get("viec") or []:
        if isinstance(a, dict) and _ma_day(a.get("ma")):
            dich = _ma(a.get("dich"))
            viec.append({"ma": _ma_day(a["ma"]), "goc": _ma(a["ma"]), "dich": None if dich in (None, "chua_thay") else dich})
    f["viec"] = viec
    c = v3.get("cay")
    f["co_cay"] = isinstance(c, dict) and bool(c)
    ten = _ma_day(c.get("ten")) if f["co_cay"] else None
    f["cay"] = None if (ten or "").split(":")[0] == "khac" else ten          # 'khac:...' = loài lạ → coi như chưa rõ loài
    f["bo_phan"] = _ds_ma(c.get("bo_phan")) if f["co_cay"] else []
    f["dau_hieu"] = {m for m in (_ma(h.get("ma")) for h in v3.get("dau_hieu") or [] if isinstance(h, dict)) if m}
    sp_thay = sp_doc = False
    for x in v3.get("vat_thay") or []:
        if isinstance(x, dict) and _ma((V.get(x.get("id")) or {}).get("la")) == "sp_chinh":
            sp_thay = True
            if isinstance(x.get("ten_doc"), str) and x["ten_doc"].strip():
                sp_doc = True
    f["sp_thay"], f["sp_doc"] = sp_thay, sp_doc
    n = v3.get("nguoi")
    f["noi_vao_may"] = isinstance(n, dict) and bool(n.get("noi_vao_may"))
    cd = [x for x in v3.get("chu_dan") or [] if isinstance(x, dict) and _ma(x.get("loai")) != "mui_ten_sticker"]
    f["chu"] = bool(cd)
    f["chu_che"] = any(x.get("che_chu_the") for x in cd)
    k = v3.get("khung") if isinstance(v3.get("khung"), dict) else {}
    net = _so(k.get("net"), 2.0)
    f["net"] = min(3.0, max(1.0, net))
    text = " ".join([str(v3.get("hinh") or ""), " ".join(a["ma"] for a in viec), str(c.get("ten") or "") if f["co_cay"] else "",
                     " ".join(f["bo_phan"]), " ".join(sorted(f["dau_hieu"])), str(v3.get("dich_thay") or "")])
    f["tok"], f["txt"] = _tu(text), _chuoi(text)
    return f


def dac_trung(shots, cache=None):
    """{id: đặc trưng} — mỗi cảnh tính đúng MỘT lần (id đã có trong cache thì bỏ qua). cache: dict dùng lại giữa nhiều lần gọi cùng một kho."""
    out = {} if cache is None else cache
    for s in shots or []:
        if isinstance(s, dict) and s.get("id") is not None and s["id"] not in out:
            out[s["id"]] = _dac_trung_mot(s)
    return out


# ---------------------------------------------------------------- 2. yêu cầu hình từ câu
# loài cây theo lời tiếng Việt CÓ DẤU (không bỏ dấu: "lúa" ≠ "lừa"). Mã khớp phiếu v3.1; cây ăn trái giữ hậu tố loài.
_CAY = [("ca_phe", r"cà phê|cà-phê"), ("tieu", r"(?<!mục )\btiêu\b(?! (?:chuẩn|hao|dùng|thụ|diệt|độc|biểu|chí|cực|điểm))"),
        ("sau_rieng", r"sầu riêng"), ("lua", r"\blúa\b"), ("ot", r"\bớt\b"), ("ca_chua", r"cà chua"), ("dua_leo", r"dưa leo|dưa chuột"),
        ("bau_bi", r"bầu bí|\bbí (?:đao|xanh|đỏ)\b|\bbầu\b"), ("bap_cai", r"bắp cải|cải bắp"),
        ("rau_an_la", r"\brau\b|\bcải\b(?! (?:thiện|tạo|tiến|cách))|xà lách|rau muống"),
        ("cay_an_trai:thanh_long", r"thanh long"), ("cay_an_trai:xoai", r"\bxoài\b"), ("cay_an_trai:mit", r"\bmít\b"),
        ("cay_an_trai:buoi", r"\bbưởi\b"), ("cay_an_trai:nhan", r"\bnhãn\b(?! (?:chai|mác|hiệu|thuốc|sản phẩm|mặt|sau|trước))"),
        ("cay_an_trai:cam", r"\bcam\b(?! (?:kết|đoan))"), ("cay_an_trai", r"cây ăn trái|cây ăn quả"), ("cay_canh", r"cây cảnh|mai vàng|hoa hồng|lan hồ điệp")]
_CAY_RE = [(m, re.compile(p)) for m, p in _CAY]
_VIEC = [("phun", r"phun|xịt|bình bơm"), ("tuoi", r"\btưới\b"), ("rot", r"\brót\b|\bđổ\b|\bđong\b|\bpha\b"), ("khuay", r"khuấy"), ("lac", r"\blắc\b"),
         ("mo_nap", r"mở nắp|vặn nắp"), ("rai", r"\brải\b|\bbón\b"), ("trong_cay", r"\btrồng\b"), ("giam_canh", r"giâm cành|giâm"),
         ("xoay_nhan", r"xoay (?:chai|nhãn)|xoay\b"), ("cam_xem", r"cầm chai|cầm can|cầm gói|cầm sản phẩm|cầm lên"), ("thu_hoach", r"thu hoạch|hái"),
         ("lat_la", r"lật lá"), ("xep_hang", r"xếp hàng|xếp chai|xếp thùng"), ("mo_thung", r"mở thùng"), ("noi_vao_may", r"nói vào máy|chia sẻ vào máy")]
_PHAN = [("re", r"\brễ\b|bộ rễ"), ("goc", r"\bgốc\b"), ("than", r"\bthân\b"), ("canh", r"\bcành\b"), ("dot", r"\bđọt\b|\bchồi\b"),
         ("la", r"\blá\b"), ("hoa", r"\bhoa\b|\bbông\b"), ("trai", r"\btrái\b|\bquả\b"), ("dat", r"\bđất\b")]
_DAU = [("la_vang", r"vàng lá|lá vàng|úa vàng"), ("la_xoan", r"xoăn lá|lá xoăn|quăn lá"), ("dot_xoan", r"xoăn đọt|đọt xoăn"), ("dom_la", r"đốm lá|lá đốm"),
        ("mep_la_nau_kho", r"cháy mép|mép lá"), ("heo", r"\bhéo\b"), ("rung", r"\brụng\b"), ("re_trang", r"rễ trắng"), ("re_den", r"rễ đen|thối rễ"),
        ("choi_moi", r"chồi mới|ra chồi"), ("la_non", r"lá non"), ("dat_kho_nut", r"đất (?:khô )?nứt|đất cứng")]
_VIEC, _PHAN, _DAU = [[(m, re.compile(p)) for m, p in b] for b in (_VIEC, _PHAN, _DAU)]
_BO_PHAN_CAY = re.compile(r"\b(?:rễ|gốc|đọt|lá|bông|hoa|trái|quả|cành|thân|mầm|chồi)\b")
_PHU_DINH = re.compile(r"\b(?:đừng|chớ|không nên|không cần|tránh|cấm|khỏi|đừng có)\b")
# câu ví von: "rẻ hơn một ly cà phê", "như một bữa ăn sáng" → phần so sánh không đòi hình thật; "ly cà phê" luôn là đồ uống, không phải cây
_LY_CA_PHE = re.compile(r"\b(?:ly|tách|cốc|chén|ly)\s+(?:cà phê|cà-phê|cafe|trà|sữa)\b")
_VI_VON = re.compile(r"\b(?:rẻ hơn|đắt hơn|hơn|như|bằng|giống|ngang)\b[^,.;!?]*\b(?:ly|tách|cốc|chén|bát|tô|đĩa|bữa|ổ|hộp|tờ|cuốn|gói mì)\b[^,.;!?]*")
_SP_DOC = re.compile(r"rõ nhãn|nhãn rõ|nhãn to|rõ tên|đọc được tên|chữ trên nhãn")
_SP_THAY = re.compile(r"\bchai\b|\bcan\b|\bgói\b|sản phẩm|\bnhãn\b|\bbao bì\b")


def _sach_vi_von(t):
    t = unicodedata.normalize("NFC", str(t or "").lower())
    t = _LY_CA_PHE.sub(" ", t)
    return _VI_VON.sub(" ", t)


def _tim(bang, t):
    out = []
    for m, p in bang:
        if p.search(t) and m not in out:
            out.append(m)
    return out


def _chuan_y_hinh(y):
    """Làm sạch y_hinh một câu → dict hoặc None nếu rỗng (thiếu, không phải dict, hoặc mọi trường đều trống → coi như vắng)."""
    if not isinstance(y, dict):
        return None
    r = {k: _ds_ma(y.get(k), day=(k == "cay")) for k in ("viec", "dich", "cay", "bo_phan", "dau_hieu")}
    r["viec"] = [m for m in r["viec"] if m not in VIEC_BO]
    r["tu_khoa"] = [str(x).strip() for x in (y.get("tu_khoa") if isinstance(y.get("tu_khoa"), list) else [y.get("tu_khoa")] if isinstance(y.get("tu_khoa"), str) else [])
                    if str(x).strip()]
    r["muc"] = _ma(y.get("muc")) if isinstance(y.get("muc"), str) else None
    r["can_sp"] = _ma(y.get("can_sp")) if isinstance(y.get("can_sp"), str) else None
    r["can_nguoi_noi"] = y["can_nguoi_noi"] if isinstance(y.get("can_nguoi_noi"), bool) else None
    r["giay"] = _so(y.get("giay"), None)
    co = any(r[k] for k in ("viec", "dich", "cay", "bo_phan", "dau_hieu", "tu_khoa")) or r["muc"] or r["can_sp"] or r["can_nguoi_noi"] is not None
    return r if co else None


def yeu_cau(cau, y_hinh_k=None, y_canh_k="", cay_truoc=()):
    """Yêu cầu hình của MỘT câu. y_hinh_k có nội dung → dùng (suy=False). Thiếu/rỗng → dựng tối thiểu từ câu + y_canh bằng từ khóa (không AI), suy=True:
    chỉ được nhãn MINH HỌA. cay_truoc: loài cây của câu liền trước — câu nối tiếp nói về BỘ PHẬN cây vẫn là cây đó.
    → dict {muc, viec, dich, cay, bo_phan, dau_hieu, can_sp, can_nguoi_noi, tu_khoa, giay, suy, cung, q}."""
    cau, y_canh_k = str(cau or ""), str(y_canh_k or "")
    y = _chuan_y_hinh(y_hinh_k)
    if y is not None:
        y["suy"] = False
        y["muc"] = y["muc"] or "truc_tiep"
        y["can_sp"] = y["can_sp"] if y["can_sp"] in ("doc_ten", "thay", "khong") else "khong"
        y["giay"] = y["giay"] if y["giay"] is not None else max(1.5, len(cau.split()) / 4)
    else:
        t_cau, t_canh = _sach_vi_von(cau), _sach_vi_von(y_canh_k)
        both = t_cau + " . " + t_canh
        cay = _tim(_CAY_RE, both)
        cay = [c for c in cay if c != "cay_an_trai"] if any(c.startswith("cay_an_trai:") for c in cay) else cay
        if not cay and cay_truoc and _BO_PHAN_CAY.search(t_cau):
            cay = list(cay_truoc)
        viec = _tim(_VIEC, t_canh) + ([] if _PHU_DINH.search(t_cau) else [m for m in _tim(_VIEC, t_cau) if m not in _tim(_VIEC, t_canh)])
        can_sp = "doc_ten" if _SP_DOC.search(t_canh) else "thay" if _SP_THAY.search(t_canh) else "khong"
        y = {"muc": "minh_hoa", "viec": viec, "dich": [], "cay": cay, "bo_phan": _tim(_PHAN, both), "dau_hieu": _tim(_DAU, both), "can_sp": can_sp,
             "can_nguoi_noi": None, "tu_khoa": [], "giay": max(1.5, len(cau.split()) / 4), "suy": True}
    y["cung"] = bool(y["viec"] or y["can_sp"] in ("doc_ten", "thay") or y["cay"] or y["bo_phan"] or y["dau_hieu"])    # có đòi gì CỤ THỂ không
    # nghĩa: y_canh + từ khóa (câu có y_hinh); dựng suy thì thêm chính câu (ví von đã bị cắt phần so sánh)
    y["q"] = _tu(y_canh_k + " " + " ".join(y["tu_khoa"]) + (" " + _sach_vi_von(cau) if y["suy"] else ""))
    y["kw"] = [k for k in (_chuoi(x).strip() for x in y["tu_khoa"]) if k]
    return y


# ---------------------------------------------------------------- 3. điểm 0–100
def _cay_khop(yc, ten):
    """Loài cây cảnh có khớp loài câu đòi: 'dung' | 'mo' (câu đòi loài cụ thể, cảnh chỉ biết họ) | 'chua_ro' (cảnh chưa rõ cây) | 'sai'."""
    if not ten:
        return "chua_ro"
    ket = "sai"
    gt, ht = ten.split(":")[0], ten.partition(":")[2]
    for y in yc:
        gy, _, hy = y.partition(":")
        if gy != gt:
            continue
        if not hy or hy == ht:
            return "dung"
        if not ht:
            ket = "mo"
    return ket


def _sai_cay(req, f):
    return bool(req["cay"]) and bool(f["cay"]) and _cay_khop(req["cay"], f["cay"]) == "sai"


def _cham(req, f):
    """→ (điểm 0–100, thông tin). Điểm chỉ tính trên những phần câu THẬT SỰ đòi (chia cho tổng trọng số đã dùng)."""
    kc = _cay_khop(req["cay"], f["cay"]) if req["cay"] else None
    if kc == "sai":
        return 0.0, {"loai": "sai_cay", "thieu_bb": ["cay"], "tp": {}, "he_so": []}
    tp, he_so, thieu = {}, [], []
    st = {"phan": 0.0, "tong": 0.0}

    def them(ten, w, s):
        st["phan"] += w * s; st["tong"] += w; tp[ten] = round(s, 2)

    cs = req["can_sp"]
    s_viec = None
    if req["viec"]:
        ac, yv = f["viec"], req["viec"]
        khop = lambda a: a["ma"] in yv or (a["goc"] in yv and a["goc"] not in VIEC_BO)
        nhom = lambda a: NHOM_VIEC.get(a["goc"]) if a["goc"] not in VIEC_BO else None
        ynhom = {NHOM_VIEC.get(m) for m in yv} - {None}
        dung_a = [a for a in ac if khop(a)]
        if ac and khop(ac[0]):
            s = 1.0
        elif dung_a:
            s = 0.7
        elif any(nhom(a) in ynhom for a in ac):
            s = 0.4
        else:
            s = 0.0
        if req["dich"] and s > 0:                      # đích chỉ tính trên CHÍNH việc được đòi (không lấy đích của việc phụ)
            chinh = dung_a or [a for a in ac if nhom(a) in ynhom]
            dich = [a["dich"] for a in chinh if a["dich"]]
            if set(dich) & set(req["dich"]):
                s = min(1.0, s + 0.2)
            elif dich:
                s *= 0.7; he_so.append("sai đích ×0.7")
        s_viec = s
        them("viec", 10 if cs == "doc_ten" else 30, s)     # câu nói về nhãn/SP: nặng danh tính, nhẹ việc
    obj = []
    if cs == "doc_ten":
        obj.append(1.0 if f["sp_doc"] else 0.4 if f["sp_thay"] else 0.0)
    elif cs == "thay":
        obj.append(1.0 if f["sp_thay"] else 0.0)
    if req["cay"]:
        obj.append(1.0 if kc == "dung" else 0.3 if f["co_cay"] else 0.0)      # chưa rõ loài / mới biết họ: một phần
    if obj:
        them("vat", 40 if cs == "doc_ten" else 20, sum(obj) / len(obj))
    bp = []
    if req["bo_phan"]:
        b0 = f["bo_phan"]
        bp.append(1.0 if b0[:1] and b0[0] in req["bo_phan"] else 0.5 if set(b0) & set(req["bo_phan"]) else 0.0)
    if req["dau_hieu"]:
        bp.append(1.0 if f["dau_hieu"] & set(req["dau_hieu"]) else 0.0)
    if bp:
        them("bo_phan_dau_hieu", 15, sum(bp) / len(bp))
    them("nghia", 15, len(req["q"] & f["tok"]) / len(req["q"]) if req["q"] else 0.0)
    if req["kw"]:
        them("tu_khoa", 8, sum(1 for k in req["kw"] if " " + k + " " in f["txt"]) / len(req["kw"]))
    # độ dài/nét: hệ số nét ∈ [0,6 ; 1] (bản thử cũ để 1,2 khi nét = 3 → tổng vượt 100)
    them("dai_net", 7, min(1.0, f["dai"] / max(1.5, min(req["giay"] or 3.0, 4.0))) * (0.4 + 0.2 * f["net"]))
    if req["can_nguoi_noi"] is True:
        them("nguoi_noi", 5, 1.0 if f["noi_vao_may"] else 0.0)
    s = 100 * st["phan"] / st["tong"] if st["tong"] else 0.0
    if req["can_nguoi_noi"] is not True and f["noi_vao_may"]:
        s *= 0.75; he_so.append("nói vào máy ×0.75")          # tắt tiếng gốc: môi mấp máy không khớp lời mới
    if f["chu"]:
        if f["chu_che"]:
            s *= 0.7; he_so.append("chữ che chủ thể ×0.7")
        else:
            s *= 0.85; he_so.append("chữ dính hình ×0.85")
    # điều kiện BẮT BUỘC cho nhãn ĐÚNG
    if cs == "doc_ten" and not f["sp_doc"]:
        thieu.append("chưa đọc được tên SP")
    if cs == "thay" and not f["sp_thay"]:
        thieu.append("chưa thấy SP")
    if req["cay"] and kc != "dung":
        thieu.append("chưa rõ đúng loài cây")
    if req["viec"] and cs != "doc_ten" and (s_viec or 0) < 0.4:
        thieu.append("việc không khớp")
    if not req["cung"]:
        thieu.append("câu không đòi gì cụ thể")
    return min(100.0, max(0.0, s)), {"tp": tp, "he_so": he_so, "thieu_bb": thieu}


def diem(req, f):
    """Điểm 0–100 của cảnh (đặc trưng f) cho yêu cầu req. Sai loài cây → 0."""
    return _cham(req, f)[0]


def _nhan(req, info, s, dung):
    """ĐÚNG chỉ khi: đủ điểm + đủ điều kiện bắt buộc + yêu cầu có thật (không phải dựng suy) + câu không phải ví von/minh họa."""
    if s >= dung and not (info or {}).get("thieu_bb") and not req["suy"] and req["muc"] != "minh_hoa":
        return "dung"
    return "minh_hoa"


def _ly_do(req, info, nhan):
    tp = " ".join(f"{k} {int(round(v * 100))}%" for k, v in (info or {}).get("tp", {}).items())
    ex = []
    if req["suy"]:
        ex.append("yêu cầu dựng suy từ câu")
    ex += (info or {}).get("he_so", [])
    if nhan != "dung" and (info or {}).get("thieu_bb"):
        ex.append("thiếu: " + ", ".join(info["thieu_bb"]))
    return (tp + ("; " if tp and ex else "") + "; ".join(ex)).strip()


# ---------------------------------------------------------------- 4. ứng viên theo câu
def _met(met, i):
    try:
        return max(0.0, float((met or {}).get(i) or 0))
    except (TypeError, ValueError):
        return 0.0


def ung_vien_v3(sents, y_hinh, y_canh, shots, met=None, nguong=MAC_DINH, k=TOP, seed=0, dt=None):
    """Ứng viên kiểu 3 cho từng câu → {chỉ số câu GỐC: [{id, diem, nhan: 'dung'|'minh_hoa', ly_do}] hoặc [{thieu: True, ly_do}]}.
    sents: mỗi phần tử là chuỗi hoặc {"text", "i"} — "i" = chỉ số câu GỐC (câu bị sentence_times bỏ làm mảng thưa: y_hinh/y_canh luôn tra theo i, KHÔNG nén).
    Thứ tự xử lý: luật cứng (cam, không phải kiểu 3, sai loài cây) → chấm → bỏ dưới sàn minh họa → sắp xếp (điểm − mệt, hòa bằng seed) →
    ≤ 2 đoạn / file nguồn → k cảnh. Mệt (met) chỉ đổi thứ tự trong số cảnh ĐÃ qua sàn; nhãn thuộc cặp (câu, id).
    dt: dict đặc trưng dùng lại giữa các lần gọi cùng một kho (mặc định tính mới)."""
    dung, mh = chuan_nguong(nguong)
    try:
        k = max(1, int(k))
    except (TypeError, ValueError):
        k = TOP
    dt = dac_trung(shots, dt)
    pool, thay = [], set()
    for s in shots or []:
        f = dt.get(s.get("id")) if isinstance(s, dict) else None
        if f is not None and f["id"] not in thay and f["kieu3"] and not f["cam"]:
            thay.add(f["id"]); pool.append(f)
    out, cay_truoc = {}, ()
    for p, st in enumerate(sents or []):
        text = st.get("text") if isinstance(st, dict) else st
        i = st.get("i", p) if isinstance(st, dict) else p
        i = i if isinstance(i, int) and not isinstance(i, bool) and i >= 0 else p
        yh = y_hinh[i] if isinstance(y_hinh, (list, tuple)) and i < len(y_hinh) else None
        yc = y_canh[i] if isinstance(y_canh, (list, tuple)) and i < len(y_canh) and isinstance(y_canh[i], str) else ""
        req = yeu_cau(text, yh, yc, cay_truoc)
        cay_truoc = tuple(req["cay"]) or (cay_truoc if _BO_PHAN_CAY.search(_sach_vi_von(text)) else ())
        ket, cao = [], 0.0
        for f in pool:
            if _sai_cay(req, f):
                continue
            if req["suy"] and not req["cung"] and len(req["q"] & f["tok"]) < 2:      # dựng suy mà chẳng có căn cứ gì: không đủ để gợi ý
                continue
            s, info = _cham(req, f)
            cao = max(cao, s)
            if s < mh:                                                                # dưới sàn: bỏ TRƯỚC khi sắp xếp
                continue
            ket.append((f, s, info))
        rng = random.Random(f"{seed}|{i}")
        rnd = {f["id"]: rng.random() for f, _s, _i in sorted(ket, key=lambda t: str(t[0]["id"]))}
        ket.sort(key=lambda t: (-(t[1] - W_MET * _met(met, t[0]["id"])), rnd[t[0]["id"]]))
        chon, dem = [], {}
        for f, s, info in ket:
            if len(chon) >= k:
                break
            if dem.get(f["file"], 0) >= TOI_DA_MOI_FILE:
                continue
            dem[f["file"]] = dem.get(f["file"], 0) + 1
            nh = _nhan(req, info, s, dung)
            chon.append({"id": f["id"], "diem": round(s, 2), "nhan": nh, "ly_do": _ly_do(req, info, nh)})
        out[i] = chon or [{"thieu": True, "ly_do": f"không cảnh nào đạt sàn {mh:g} (cao nhất {cao:.0f}, {len(pool)} cảnh kiểu 3 dùng được)"
                           + ("; yêu cầu dựng suy từ câu" if req["suy"] else "")}]
    return out


# ---------------------------------------------------------------- 5. chạy bóng: so với bộ lọc cũ, không đổi lựa chọn
def bong(sents, chi_so, y_hinh, y_canh, shots, per_cu, met=None, nguong=MAC_DINH, k=TOP, seed=0, ten=None):
    """Chạy ung_vien_v3 trên cùng các câu của đạo diễn, ghép với ứng viên của bộ lọc CŨ → dict ghi JSON.
    chi_so[j] = chỉ số câu gốc của câu thứ j trong sents (sents/per_cu theo chỉ số nén của sentence_times). Không sửa đầu vào."""
    import time
    dung, mh = chuan_nguong(nguong)
    t0 = time.perf_counter()
    dt = dac_trung(shots)
    t1 = time.perf_counter()
    kq = ung_vien_v3([{"text": s["text"] if isinstance(s, dict) else str(s), "i": chi_so[j]} for j, s in enumerate(sents)],
                     y_hinh, y_canh, shots, met=met, nguong=(dung, mh), k=k, seed=seed, dt=dt)
    t2 = time.perf_counter()
    cau = []
    for j, s in enumerate(sents):
        i = chi_so[j]
        cu = [str(x) for x in (per_cu[j] if j < len(per_cu or []) else [])]
        moi = kq.get(i) or []
        thieu = bool(moi) and bool(moi[0].get("thieu"))
        ids = {str(m["id"]) for m in moi if "id" in m}
        yh = y_hinh[i] if isinstance(y_hinh, (list, tuple)) and i < len(y_hinh) else None
        cau.append({"i": i, "text": s["text"] if isinstance(s, dict) else str(s), "co_y_hinh": _chuan_y_hinh(yh) is not None, "cu": cu,
                    "moi": [] if thieu else moi, "thieu": thieu, "giao": len(ids & set(cu)), **({"ly_do_thieu": moi[0]["ly_do"]} if thieu else {})})
    return {"ban": 1, "ten": ten, "nguong": {"dung": dung, "minh_hoa": mh}, "k": k, "seed": seed,
            "kho": {"tong": len(shots or []), "kieu3_dung_duoc": sum(1 for f in dt.values() if f["kieu3"] and not f["cam"])},
            "ms": round((t2 - t0) * 1000, 2), "ms_dac_trung": round((t1 - t0) * 1000, 2), "cau": cau}

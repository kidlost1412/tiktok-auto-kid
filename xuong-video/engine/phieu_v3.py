"""PHIẾU CẢNH v3.1 (học cảnh kiểu 3): Gemini tự chia đoạn và ghi phiếu theo mẫu prompt/dien-phieu-v3.md.
- kiem_video(v, dai) → [lỗi]  (rỗng = hợp lệ) — kiểm NGHIÊM theo mẫu: phủ liền video, id vật, mốc trong đoạn, null ≠ [].
- cam(doan, vat) → [lý do cấm]  — MỘT luật cấm dùng chung cho biên kịch, đạo diễn, máy dựng.
- shot_cu(doan, vat, sp) → các khóa cũ của canh.json (đúng nghĩa cũ) để phần dựng hiện tại chạy được.
- mo_ta(v, rel, dai, model) → nội dung file _mo-ta/<video>.mo-ta-v3.json.
File kiểu 3 có đuôi riêng (.mo-ta-v3.json): bộ đọc cũ (*.mo-ta.json) không thấy nó → mô tả v2/v1 còn nguyên để quay lui."""
import datetime, math

DUOI = ".mo-ta-v3.json"
BAN = "3.1"
MEP = 0.3                                   # dung sai mép đoạn (giây) — mẫu đòi chính xác ±0,3 s

LOAI_VAT = {"chai", "can", "goi", "bao", "thung_hang", "binh_phun", "phuy", "xo", "ly_nap", "voi_tuoi"}
VIEC = {"cam_xem", "xoay_nhan", "mo_nap", "rot", "khuay", "lac", "phun", "tuoi", "rai", "trong_cay", "giam_canh", "bung_cay", "cam_re",
        "chi_vao", "lat_la", "lau_la", "dap_la", "vuot_la", "di_xem", "noi_vao_may", "mo_thung", "xep_hang", "thu_hoach", "khong"}
VAT_CAY = {"la", "dot", "re", "canh"}
CHU_DAN = {"phu_de", "tieu_de", "gia", "qua_km", "lieu", "binh_luan", "mui_ten_sticker", "logo", "khung_chen", "khac"}
NGUON = {"quay_that", "anh_tinh", "do_hoa", "ghep", "khong_ro"}
CO_CANH = {"can", "trung", "toan"}
KHOA_DOAN = ("tu", "den", "hinh", "viec", "vat_thay", "cay", "dau_hieu", "sinh_vat", "so_sanh", "dich_thay", "nguoi", "loi", "chu_dan",
             "gia_qua", "nguon", "khung")
CAY_CU = {"tieu": "ho_tieu"}                # tên cây cũ mà biên kịch/kho đang đếm


def _so(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _mo(x, tap):
    """Enum mở: giá trị trong tập hoặc 'khac:<ghi rõ>'."""
    return isinstance(x, str) and (x in tap or x.startswith("khac:") and len(x) > 5)


def _la_vat(x):
    return isinstance(x, str) and (x in ("sp_chinh", "dung_cu", "khong_ro") or x.startswith("sp_khac:") and len(x) > 8)


def kiem_video(v, dai=None):
    """Lỗi của phiếu một video (rỗng = dùng được). dai = độ dài đo độc lập (ffprobe), None = bỏ kiểm phủ cuối."""
    if not isinstance(v, dict):
        return ["phiếu không phải đối tượng JSON"]
    loi = []
    for k, t in (("tom_tat", str), ("kieu_video", str), ("vat", list), ("bo_qua", list), ("doan", list)):
        if not isinstance(v.get(k), t):
            loi.append(f'thiếu/sai kiểu "{k}"')
    if loi:
        return loi
    ids = set()
    for x in v["vat"]:
        if not isinstance(x, dict) or not isinstance(x.get("id"), str) or not x["id"]:
            loi.append("vật thiếu id"); continue
        if x["id"] in ids:
            loi.append(f'id vật trùng "{x["id"]}"')
        ids.add(x["id"])
        if not _mo(x.get("loai"), LOAI_VAT):
            loi.append(f'vật {x["id"]}: loai lạ "{x.get("loai")}"')
        if not _la_vat(x.get("la")):                                   # quyết định cấm (SP khác) → không nhận giá trị lạ
            loi.append(f'vật {x["id"]}: la lạ "{x.get("la")}"')
        if x.get("chu_doc") is not None and not isinstance(x.get("chu_doc"), str):
            loi.append(f'vật {x["id"]}: chu_doc phải là chữ hoặc null')
    khoang = []
    for b in v["bo_qua"]:
        if not isinstance(b, dict) or not (_so(b.get("tu")) and _so(b.get("den"))) or b["tu"] >= b["den"]:
            loi.append(f"bo_qua sai mốc: {b}"); continue
        khoang.append((b["tu"], b["den"], "bỏ qua"))
    for i, d in enumerate(v["doan"], 1):
        if not isinstance(d, dict):
            loi.append(f"đoạn {i}: không phải đối tượng"); continue
        thieu = [k for k in KHOA_DOAN if k not in d]
        if thieu:
            loi.append(f"đoạn {i}: thiếu khóa {', '.join(thieu)}"); continue
        if not (_so(d["tu"]) and _so(d["den"])) or d["tu"] >= d["den"]:
            loi.append(f"đoạn {i}: mốc sai ({d.get('tu')}–{d.get('den')})"); continue
        a, b = d["tu"], d["den"]
        khoang.append((a, b, f"đoạn {i}"))
        loi += [f"đoạn {i}: {e}" for e in _kiem_doan(d, a, b, ids)]
    if not v["doan"] and not v["bo_qua"]:
        loi.append("không có đoạn nào")
    # phủ liền: mỗi giây thuộc đúng một khoảng (dung sai mép)
    khoang.sort()
    if khoang:
        if khoang[0][0] > MEP:
            loi.append(f"hở đầu video 0–{khoang[0][0]:g}s")
        for (a0, b0, t0), (a1, b1, t1) in zip(khoang, khoang[1:]):
            if a1 - b0 > MEP:
                loi.append(f"hở {b0:g}–{a1:g}s giữa {t0} và {t1}")
            elif b0 - a1 > MEP:
                loi.append(f"chồng {a1:g}–{b0:g}s giữa {t0} và {t1}")
        cuoi = max(b for _a, b, _t in khoang)
        if dai:
            if dai - cuoi > MEP:
                loi.append(f"hở cuối video {cuoi:g}–{dai:g}s")
            if cuoi - dai > MEP:
                loi.append(f"vượt độ dài video ({cuoi:g}s > {dai:g}s)")
    return loi


def _trong(t, a, b):
    return _so(t) and a - MEP <= t <= b + MEP


def _kiem_doan(d, a, b, ids):
    loi = []
    if not isinstance(d["hinh"], str):
        loi.append("hinh phải là chữ")
    if not isinstance(d["viec"], list) or not d["viec"]:
        loi.append("viec phải là mảng có ít nhất 1 việc")
    else:
        for x in d["viec"]:
            if not isinstance(x, dict) or not _mo(x.get("ma"), VIEC):
                loi.append(f"việc lạ {x}"); continue
            vt = x.get("vat")
            if vt is not None and vt not in ids and vt not in VAT_CAY:
                loi.append(f'việc {x["ma"]}: vat "{vt}" không có trong danh sách vật')
    if not isinstance(d["vat_thay"], list):
        loi.append("vat_thay phải là mảng")
    else:
        for x in d["vat_thay"]:
            if not isinstance(x, dict) or x.get("id") not in ids:
                loi.append(f"vat_thay id lạ {x.get('id') if isinstance(x, dict) else x}")
            elif x.get("ten_doc") is not None and not isinstance(x["ten_doc"], str):
                loi.append("ten_doc phải là chữ hoặc null")
    if d["cay"] is not None and (not isinstance(d["cay"], dict) or not isinstance(d["cay"].get("bo_phan", []), list)):
        loi.append("cay phải là null hoặc {ten, bo_phan[], giai_doan}")
    for k in ("dau_hieu", "sinh_vat"):
        if not isinstance(d[k], list):
            loi.append(f"{k} phải là mảng"); continue
        for x in d[k]:
            if not isinstance(x, dict) or not _trong(x.get("tai"), a, b):
                loi.append(f"{k}: mốc tai ngoài đoạn ({x.get('tai') if isinstance(x, dict) else x})")
    if d["loi"] is not None:
        if not isinstance(d["loi"], list):
            loi.append("loi phải là mảng hoặc null")
        else:
            for x in d["loi"]:
                if not isinstance(x, dict) or not (_trong(x.get("tu"), a, b) and _trong(x.get("den"), a, b)):
                    loi.append(f"lời: mốc ngoài đoạn {x}")
    if not isinstance(d["chu_dan"], list):
        loi.append("chu_dan phải là mảng")
    else:
        for x in d["chu_dan"]:
            if not isinstance(x, dict) or x.get("loai") not in CHU_DAN:      # quyết định cấm (giá/quà) → không nhận loại lạ
                loi.append(f"chữ dán loại lạ {x.get('loai') if isinstance(x, dict) else x}")
            elif not isinstance(x.get("che_chu_the"), bool):
                loi.append("chữ dán: che_chu_the phải true/false")
    gq = d["gia_qua"]
    if not isinstance(gq, dict) or set(gq) != {"chu_dan", "tren_vat", "loi"}:
        loi.append("gia_qua phải có đúng 3 kênh chu_dan/tren_vat/loi")
    else:
        for kenh, ds in gq.items():
            if ds is None:
                continue
            if not isinstance(ds, list):
                loi.append(f"gia_qua.{kenh} phải là mảng hoặc null"); continue
            for x in ds:
                if not isinstance(x, dict) or not (_trong(x.get("tu"), a, b) and _trong(x.get("den"), a, b)):
                    loi.append(f"gia_qua.{kenh}: mốc ngoài đoạn {x}")
    if d["nguon"] not in NGUON:
        loi.append(f'nguon lạ "{d["nguon"]}"')
    k = d["khung"]
    if not isinstance(k, dict) or k.get("net") not in (1, 2, 3) or k.get("dep") not in (1, 2, 3) or k.get("co_canh") not in CO_CANH:
        loi.append("khung thiếu/sai net, dep (1–3) hoặc co_canh")
    if d["nguoi"] is not None and not isinstance(d["nguoi"], dict):
        loi.append("nguoi phải là null hoặc đối tượng")
    return loi


# ----------------------------------------------------------------------------------------------- luật cấm dùng chung
def _vat(vat):
    return {x["id"]: x for x in vat if isinstance(x, dict) and "id" in x} if isinstance(vat, list) else dict(vat or {})


def cam(doan, vat):
    """Lý do KHÔNG dùng đoạn làm cảnh hình (rỗng = dùng được). vat: danh sách vật của video.
    Giá/quà HIỆN trên hình (kể cả số mờ, trich null) bị cấm; giá chỉ nói bằng lời thì không (video mới tắt tiếng gốc)."""
    vat = _vat(vat)
    ly = []
    gq = doan.get("gia_qua") or {}
    if gq.get("chu_dan") or gq.get("tren_vat") or gq.get("chu_dan", []) is None or gq.get("tren_vat", []) is None or any(x.get("loai") in ("gia", "qua_km") for x in doan.get("chu_dan") or []):
        ly.append("gia_qua")
    if any((vat.get(x.get("id")) or {}).get("la", "").startswith("sp_khac") and x.get("ten_doc") for x in doan.get("vat_thay") or []):
        ly.append("sp_khac")
    if (doan.get("khung") or {}).get("net") == 1:
        ly.append("mo")
    if doan.get("nguon") != "quay_that" and any(x.get("che_chu_the") for x in doan.get("chu_dan") or []):
        ly.append("chu_che")
    return ly


# ----------------------------------------------------------------------------------------------- khóa cũ cho phần dựng hiện tại
def _vai_loai(d, vat):
    ma = [x.get("ma") for x in d.get("viec") or [] if isinstance(x, dict)]
    cay = d.get("cay") or {}
    bp = cay.get("bo_phan") or []
    nguoi = d.get("nguoi") or {}
    chinh_thay = [x for x in d.get("vat_thay") or [] if (vat.get(x.get("id")) or {}).get("la") == "sp_chinh"]
    vai = []
    if set(ma) & {"rot", "khuay", "lac", "mo_nap"}: vai.append("pha_rot")
    if set(ma) & {"phun", "tuoi"}: vai.append("phun")
    if chinh_thay and set(ma) & {"cam_xem", "xoay_nhan", "noi_vao_may", "chi_vao"}:
        vai.append("nhan_can" if all(x.get("mat") == "sau" for x in chinh_thay) else "chai_ro")
    if "re" in bp or "cam_re" in ma: vai.append("re")
    if cay.get("giai_doan") in ("cay_con", "canh_giam") or set(ma) & {"giam_canh", "trong_cay"}: vai.append("cay_con")
    if [x for x in d.get("dau_hieu") or [] if x.get("ma") not in ("la_non", "choi_moi", "re_trang")]: vai.append("van_de")
    if set(ma) & {"mo_thung", "xep_hang"} or any((vat.get(x.get("id")) or {}).get("loai") == "thung_hang" for x in d.get("vat_thay") or []):
        vai.append("kho_hang")
    if "ca_vuon" in bp or (cay and (d.get("khung") or {}).get("co_canh") == "toan"): vai.append("vuon")
    if "noi_vao_may" in ma and nguoi.get("noi_vao_may") is not False: loai = "nguoi_noi"
    elif "pha_rot" in vai: loai = "pha_rot"
    elif "phun" in vai: loai = "phun_tuoi"
    elif "chai_ro" in vai: loai = "chai_ro"
    elif "nhan_can" in vai: loai = "nhan_sau"
    elif "re" in vai: loai = "re_goc"
    elif "van_de" in vai: loai = "cay_benh"
    elif "kho_hang" in vai: loai = "kho_hang"
    elif nguoi.get("kieu") == "lam_viec": loai = "nguoi_lam"
    elif "vuon" in vai: loai = "vuon_rong"
    else: loai = "khac"
    if not vai and cay and loai != "nguoi_noi":
        vai = ["vuon"]
    return vai, loai, ma


def diem(d):
    """Điểm đẹp 1–5 kiểu cũ từ khung AI (máy đo lại nét ở bước học sẽ thay khi có)."""
    k = d.get("khung") or {}
    if k.get("net") == 1:
        return 2
    x = {3: 5, 2: 4, 1: 3}.get(k.get("dep"), 3)
    return min(x, 3) if k.get("rung") or k.get("toi") else x


def shot_cu(d, vat, sp=None):
    """Các khóa canh.json cũ, ĐÚNG NGHĨA cũ: dep = cặp giây khung đẹp, soat.dep = điểm, noi = chuỗi, mat 0/1/2 (chỉ thấy tay = 0)."""
    vat = _vat(vat)
    vai, loai, ma = _vai_loai(d, vat)
    nguoi = d.get("nguoi") or {}
    mat = 0 if not nguoi or nguoi.get("kieu") == "tay" else 2 if nguoi.get("noi_vao_may") else 1 if nguoi.get("mat_ro") else 0
    cd = d.get("chu_dan") or []
    chu = 2 if any(x.get("che_chu_the") for x in cd) and d.get("nguon") != "quay_that" else 1 if cd else 0
    a, b = d["tu"], d["den"]
    h = min(2.0, (b - a) / 2)
    m = (a + b) / 2
    cay = d.get("cay") or {}
    ten = cay.get("ten")
    lam_loi = d.get("loi") or []
    dm = diem(d)
    return {"loai": loai, "vai_tro": vai, "diem": dm, "co_canh": (d.get("khung") or {}).get("co_canh"), "mo_ta": str(d.get("hinh") or "")[:220],
            "the": list(dict.fromkeys(m_ for m_ in ma if m_)), "cay": [CAY_CU.get(ten, ten)] if isinstance(ten, str) and ":" not in ten else
            [ten.split(":", 1)[1]] if isinstance(ten, str) else [],
            "dep": [round(m - h, 2), round(m + h, 2)], "chu_ghi": bool(cd), "noi_ghi": mat == 2,
            "noi": " · ".join(str(x.get("tom") or "") for x in lam_loi if isinstance(x, dict)).strip(" ·"), "loi": "",
            "cam": cam(d, vat), "nhan_can_hop": any((vat.get(x.get("id")) or {}).get("la") == "sp_chinh" for x in d.get("vat_thay") or []),
            "soat": {"mat": mat, "chu_muc": chu, "hang_khac": "sp_khac" in cam(d, vat), "dep": dm, "nhan": None,
                     "ghi": str(d.get("hinh") or "")[:80]}}


# ----------------------------------------------------------------------------------------------- file mô tả kiểu 3
def mo_ta(v, rel, dai, model=None):
    """Nội dung _mo-ta/<rel>.mo-ta-v3.json. Giữ khóa cấp video cũ để hub/biên kịch đọc được; loi_hay = [] vì phiếu chỉ có TÓM TẮT lời
    (không được biến tóm tắt thành câu người thật nói)."""
    doan = sorted(v.get("doan") or [], key=lambda d: d["tu"])
    vat = v.get("vat") or []
    vm = _vat(vat)
    cay = []
    for d in doan:
        t = (d.get("cay") or {}).get("ten")
        if isinstance(t, str):
            t = CAY_CU.get(t, t.split(":", 1)[-1])
            if t not in cay:
                cay.append(t)
    khac = []
    for d in doan:
        for x in d.get("vat_thay") or []:
            la = (vm.get(x.get("id")) or {}).get("la", "")
            if la.startswith("sp_khac") and x.get("ten_doc"):
                khac.append({"ten": x["ten_doc"], "la_san_pham_khac": True, "tu_s": d["tu"], "den_s": d["den"]})
    loi = [d.get("loi") for d in doan]
    return {"kieu": 3, "ban_phieu": BAN, "video": rel, "thoi_luong_s": dai, "tom_tat": v.get("tom_tat") or "", "cay_trong": cay,
            "san_pham_thay": khac, "loi_hay": [], "nghe_duoc": None if all(x is None for x in loi) else any(x for x in loi),
            "model": model, "hoc_luc": datetime.datetime.now().isoformat(timespec="seconds"),
            "phieu_v3": {"vat": vat, "kieu_video": v.get("kieu_video"), "bo_qua": v.get("bo_qua") or []},
            "canh_quay": [{"tu_s": d["tu"], "den_s": d["den"], "hinh": d.get("hinh") or "", "v3": d} for d in doan]}

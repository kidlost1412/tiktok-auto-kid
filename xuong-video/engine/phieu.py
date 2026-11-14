"""PHIẾU CẢNH (học cảnh kiểu 2): máy đo mốc giây/độ nét/độ rung, AI chỉ điền phiếu cố định cho các cảnh máy đã cắt.
- kiem_phieu(obj, so_video, ds_so_canh) → (cảnh hợp lệ theo số, [(số cảnh, lý do)]) — kiểm NGHIÊM, bỏ qua lệch vô hại (số dạng chữ, "true"/"false", ``` bao quanh, trường thừa).
- doc_phieu_video(obj, so_video) → ô của từng video (nghe được, tóm tắt, cây trồng, lời hay); không bao giờ ném lỗi.
- dep_may(...) → điểm đẹp 1–5 do MÁY tính (AI không chấm điểm).
- mo_ta_tu_phieu(...) → file _mo-ta/<video>.mo-ta.json theo ĐÚNG khung cũ (kiem_mo_ta/kho_canh đọc được) + trường mới kieu=2, phieu…"""
import datetime, json, re, unicodedata

LOAI = ["chai_ro", "nhan_sau", "pha_rot", "phun_tuoi", "re_goc", "cay_benh", "ket_qua", "vuon_rong", "nguoi_lam", "nguoi_noi", "kho_hang", "khac"]
CO_CANH = ["toan", "trung", "can"]
GIOI_HAN = {"ta": 120, "dang_noi_ve": 80, "loi": 60, "nhan_doc": 80, "loi_hay": 220, "tom_tat": 200, "cay_trong": 60}
NO_RONG = 0.06                    # nới khung nhãn mỗi phía 6% cạnh của chính khung (AI khoanh chưa chuẩn)

# loại cảnh → vai trò kho_canh đang dùng
VAI_TU_LOAI = {"chai_ro": ["chai_ro"], "nhan_sau": ["nhan_can"], "pha_rot": ["pha_rot"], "phun_tuoi": ["phun"], "re_goc": ["re"], "cay_benh": ["van_de"],
               "ket_qua": ["ket_qua"], "vuon_rong": ["vuon"], "kho_hang": ["kho_hang"], "nguoi_lam": ["vuon"], "nguoi_noi": [], "khac": []}
# loại cảnh → thẻ cũ của khung mô tả
THE_TU_LOAI = {"chai_ro": ["cam_chai"], "nhan_sau": ["nhan_mat_sau"], "pha_rot": ["pha_thuoc"], "phun_tuoi": ["phun_xit"], "re_goc": ["re_cay"],
               "cay_benh": ["la_benh"], "ket_qua": ["cay_xanh_sung"], "vuon_rong": ["canh_vuon_rong"], "kho_hang": ["kho_hang"],
               "nguoi_lam": ["nguoi_lam_vuon"], "nguoi_noi": ["nguoi_noi_vao_may"], "khac": []}
CAY_TU_KHOA = [("ca_phe", r"\bca phe\b|\bcaphe\b|\bcafe\b|\bcoffee\b"), ("ho_tieu", r"\bho tieu\b|\btieu\b"), ("sau_rieng", r"\bsau rieng\b"),
               ("ot", r"\bot\b"), ("thanh_long", r"\bthanh long\b"), ("rau_mau", r"\brau\b|\bcai\b|\bbap cai\b|\bca chua\b|\bdua leo\b")]


def _bo_dau(s):
    s = unicodedata.normalize("NFD", str(s).replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# ----------------------------------------------------------------------------------------------- điểm đẹp do máy tính
def dep_may(net, chuyen_dong, loi="", chu_chen=0, hang_khac=False):
    """Điểm 1–5. 1 chỉ khi chữ chèn nhiều (chu_chen 2) hoặc hàng khác; 2 khi hình mờ (net < 0.4);
    AI ghi khuyết điểm (thường nhỏ: "có dây chắn ngang") → tối đa 3, vẫn dùng được; 5 khi nét (≥ 1.0); 4 khi khá nét (≥ 0.7); còn lại 3.
    chuyen_dong KHÔNG tính vào điểm: phép đo rung chỉ đủ tin để chọn đoạn êm nhất trong cùng một cú máy (thử thật 14/11: gần như cảnh cầm tay nào cũng ra "rung")."""
    loi = str(loi or "").strip()
    try:
        net = float(net)
    except Exception:
        net = 0.0
    if chu_chen == 2 or hang_khac:
        return 1
    if net < 0.4:
        return 2
    if loi:
        return 3
    if net >= 1.0:
        return 5
    if net >= 0.7:
        return 4
    return 3


# ----------------------------------------------------------------------------------------------- đọc + kiểm phiếu
def _doc_json(x):
    if isinstance(x, (dict, list)):
        return x
    if isinstance(x, bytes):
        x = x.decode("utf-8-sig", errors="replace")
    t = str(x).lstrip("﻿").strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    import kiem_mo_ta as km                                     # đọc dễ tính: ``` bao quanh, chữ thừa, phẩy thừa…
    try:
        return km.doc_json_long(t)[0]
    except ValueError as e:
        raise ValueError(str(e))


def _so_nguyen(x):
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return int(x) if x == int(x) else None
    if isinstance(x, str) and re.fullmatch(r"\s*-?\d+(?:[.,]0+)?\s*", x):
        return int(float(x.strip().replace(",", ".")))
    return None


def _so_thuc(x):
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(str(x).strip().replace(",", ".")) if isinstance(x, str) else float(x)
    except Exception:
        return None
    return v if v == v and abs(v) != float("inf") else None


def _bool(x):
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)) and x in (0, 1):
        return bool(x)
    if isinstance(x, str):
        t = _bo_dau(x.strip().lower())
        if t in ("true", "co", "yes", "1"):
            return True
        if t in ("false", "khong", "no", "0", ""):
            return False
    return None


def _chu(x, toi_da):
    if x is None:
        return ""
    if isinstance(x, (list, tuple)):
        x = "; ".join(str(i) for i in x)
    return re.sub(r"\s+", " ", str(x)).strip()[:toi_da].rstrip()


def _tag(x):
    return re.sub(r"\s+", "_", str(x).strip().lower())


def _nhan(x):
    """→ (khung đã nới | None, lỗi | None)."""
    if x is None or (isinstance(x, str) and x.strip().lower() in ("", "null", "none")) or x == []:
        return None, None
    if isinstance(x, str):
        try:
            x = json.loads(x)
        except Exception:
            return None, "nhan không phải 4 số"
    if not isinstance(x, (list, tuple)) or len(x) != 4:
        return None, "nhan không phải 4 số"
    v = [_so_thuc(i) for i in x]
    if any(i is None for i in v):
        return None, "nhan không phải 4 số"
    if any(i < 0 or i > 1 for i in v):
        return None, "nhan có số ngoài 0–1"
    x0, y0, x1, y1 = v
    if not (x0 < x1 and y0 < y1):
        return None, "nhan sai thứ tự (cần x0<x1, y0<y1)"
    w, h = (x1 - x0) * NO_RONG, (y1 - y0) * NO_RONG
    return [round(max(0.0, x0 - w), 3), round(max(0.0, y0 - h), 3), round(min(1.0, x1 + w), 3), round(min(1.0, y1 + h), 3)], None


def _kiem_canh(c):
    """1 phần tử "canh" → (cảnh chuẩn, None) hoặc (None, lý do)."""
    loai = _tag(c.get("loai", ""))
    if loai not in LOAI:
        return None, f'loai "{str(c.get("loai"))[:30]}" không thuộc danh sách'
    cc = _tag(c.get("co_canh", ""))
    cc = {"can_canh": "can", "toan_canh": "toan", "trung_canh": "trung"}.get(cc, cc)
    if cc not in CO_CANH:
        return None, f'co_canh "{str(c.get("co_canh"))[:30]}" không thuộc toan/trung/can'
    mat, chu = _so_nguyen(c.get("mat")), _so_nguyen(c.get("chu_chen"))
    if mat not in (0, 1, 2):
        return None, "mat phải là 0, 1 hoặc 2"
    if chu not in (0, 1, 2):
        return None, "chu_chen phải là 0, 1 hoặc 2"
    hk = _bool(c.get("hang_khac"))
    if hk is None:
        return None, "hang_khac phải là true/false"
    nhan, loi_nhan = _nhan(c.get("nhan"))
    if loi_nhan:
        return None, loi_nhan
    ta = _chu(c.get("ta"), GIOI_HAN["ta"])
    if not ta:
        return None, "thiếu mô tả (ta)"
    return {"loai": loai, "co_canh": cc, "mat": mat, "chu_chen": chu, "hang_khac": hk, "nhan_doc": _chu(c.get("nhan_doc"), GIOI_HAN["nhan_doc"]),
            "nhan": nhan, "ta": ta, "dang_noi_ve": _chu(c.get("dang_noi_ve"), GIOI_HAN["dang_noi_ve"]), "loi": _chu(c.get("loi"), GIOI_HAN["loi"])}, None


def kiem_phieu(obj, so_video, ds_so_canh):
    """obj: đối tượng/chữ JSON AI ghi. ds_so_canh: các số cảnh PHẢI có. → ({số cảnh: cảnh chuẩn}, [(số cảnh, lý do)]).
    Phiếu không đọc được → mọi cảnh đều lỗi (lý do giống nhau). Số cảnh ngoài danh sách bị bỏ qua; số trùng lấy bản đầu."""
    ds = [int(i) for i in ds_so_canh]
    try:
        d = _doc_json(obj)
    except ValueError as e:
        return {}, [(i, "phiếu không đọc được: " + str(e)[:80]) for i in ds]
    lst = d.get("canh") if isinstance(d, dict) else d
    if not isinstance(lst, list):
        return {}, [(i, 'phiếu không có mảng "canh"') for i in ds]
    tho = {}
    for c in lst:
        if isinstance(c, dict):
            n = _so_nguyen(c.get("so"))
            if n is not None:
                tho.setdefault(n, c)
    ok, loi = {}, []
    for n in ds:
        if n not in tho:
            loi.append((n, "thiếu cảnh trong phiếu")); continue
        v, ly = _kiem_canh(tho[n])
        if ly:
            loi.append((n, ly))
        else:
            ok[n] = v
    return ok, loi


def doc_phieu_video(obj, so_video):
    """→ {thu_tu (1..so_video): {nghe_duoc, tom_tat, cay_trong, loi_hay}}; thiếu/hỏng thì để mặc định (không làm hỏng cảnh)."""
    mac = lambda: {"nghe_duoc": False, "tom_tat": "", "cay_trong": "", "loi_hay": []}
    ra = {i: mac() for i in range(1, so_video + 1)}
    try:
        d = _doc_json(obj)
        lst = d.get("video") if isinstance(d, dict) else None
    except ValueError:
        return ra
    if not isinstance(lst, list):
        return ra
    for k, v in enumerate(lst, 1):
        if not isinstance(v, dict):
            continue
        n = _so_nguyen(v.get("thu_tu"))
        n = n if n in ra else k
        if n not in ra:
            continue
        nd = _bool(v.get("nghe_duoc"))
        lh = v.get("loi_hay")
        lh = [lh] if isinstance(lh, str) else (lh if isinstance(lh, list) else [])
        ra[n] = {"nghe_duoc": bool(nd), "tom_tat": _chu(v.get("tom_tat"), GIOI_HAN["tom_tat"]), "cay_trong": _chu(v.get("cay_trong"), GIOI_HAN["cay_trong"]),
                 "loi_hay": [t for t in (_chu(i, GIOI_HAN["loi_hay"]) for i in lh[:2]) if t]}
    return ra


# ----------------------------------------------------------------------------------------------- phiếu → file mô tả kiểu cũ + trường mới
def cay_tu_chu(txt):
    """Chữ tự do của AI ("ớt", "cà phê, tiêu") → mã trong khung cũ. Rỗng → ["khong_ro"]; có chữ mà không khớp → ["cay_khac"]."""
    t = _bo_dau(str(txt or "").lower()).strip()
    if not t:
        return ["khong_ro"]
    ra = [ma for ma, rx in CAY_TU_KHOA if re.search(rx, t)]
    return ra or ["cay_khac"]


def mo_ta_tu_phieu(rel, dai, canh_may, canh_phieu, thong_tin, model, luc=None):
    """canh_may: [{tu, den, net, chuyen_dong}] (máy đo); canh_phieu: [cảnh chuẩn từ kiem_phieu] CÙNG thứ tự; thong_tin: ô video từ doc_phieu_video.
    → đối tượng mô tả đúng khung kiem_mo_ta (giữ nguyên qua chuan_hoa_noi_dung) + kieu=2."""
    luc = luc or datetime.datetime.now().isoformat(timespec="seconds")
    canh, sp = [], []
    for m, p in zip(canh_may, canh_phieu):
        a, b = float(m["tu"]), float(m["den"])
        dep = dep_may(m.get("net"), m.get("chuyen_dong"), p["loi"], p["chu_chen"], p["hang_khac"])
        if p["nhan_doc"]:
            san_pham = f"doc_ro: {p['nhan_doc']}"
        elif p["nhan"]:
            san_pham = "thay_khong_doc_ro"
        else:
            san_pham = "khong_co"
        the = list(THE_TU_LOAI.get(p["loai"], [])) + (["nhan_doc_ro"] if p["nhan_doc"] else [])
        canh.append({"tu_s": a, "den_s": b, "khung_dep_nhat": [a, b], "hinh": p["ta"], "co_canh": "can_canh" if p["co_canh"] == "can" else p["co_canh"],
                     "may_quay": "rung_tay" if m.get("chuyen_dong") == "rung" else "dung_yen", "san_pham": san_pham,
                     "chu_chen_san": "co" if p["chu_chen"] else "khong", "the": the, "diem": dep, "chac_chan": "cao",
                     "phieu": {"loai": p["loai"], "mat": p["mat"], "chu_chen": p["chu_chen"], "hang_khac": p["hang_khac"], "nhan": p["nhan"], "loi": p["loi"],
                               "dang_noi_ve": p["dang_noi_ve"], "net": m.get("net"), "chuyen_dong": m.get("chuyen_dong")}})
        if p["nhan_doc"] or p["hang_khac"]:
            sp.append({"ten_tren_nhan": p["nhan_doc"] or "không đọc rõ", "tu_s": a, "den_s": b, "la_san_pham_khac": bool(p["hang_khac"])})
    tom_tat = thong_tin.get("tom_tat", "")
    co_loi = bool(thong_tin.get("nghe_duoc")) and bool(thong_tin.get("loi_hay") or any(p["dang_noi_ve"] for p in canh_phieu))
    return {"video": rel, "thoi_luong_s": round(float(dai), 2), "tom_tat": tom_tat, "nguoi": "", "boi_canh": "",
            "cay_trong": cay_tu_chu(thong_tin.get("cay_trong")),
            "loi_noi_tom_tat": tom_tat if co_loi and tom_tat else ("không nghe được" if not thong_tin.get("nghe_duoc") else "không có lời"),
            "san_pham_thay": sp, "canh_quay": canh, "van_de": [], "dung_lam_bang_chung": True,
            "kieu": 2, "model": model, "hoc_luc": luc, "loi_hay": list(thong_tin.get("loi_hay") or []), "nghe_duoc": bool(thong_tin.get("nghe_duoc"))}

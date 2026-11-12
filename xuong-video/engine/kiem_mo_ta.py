"""KIỂM ĐỊNH DẠNG mô tả cảnh (_mo-ta/*.mo-ta.json) của kho video.
Khung chuẩn lấy từ luat/MO-TA-VIDEO-GEMINI.md; nguồn sự thật là cách engine/kho_canh.py ĐỌC file
(video, canh_quay[].tu_s/den_s/diem/the/khung_dep_nhat/hinh/san_pham/chu_chen_san/co_canh, san_pham_thay[].la_san_pham_khac/tu_s/den_s,
van_de[].loai/tu_s/den_s, cay_trong; cờ is_duplicate / ban_trung_cua do người thêm → luôn GIỮ NGUYÊN).

Dùng:
  python kiem_mo_ta.py <ma-san-pham> [--sua]       (mặc định chạy THỬ: không ghi gì)
  thêm --ffprobe: đo lại độ dài MỌI video (mặc định chỉ đo khi file thiếu thoi_luong_s hoặc có cảnh vượt quá)
  from kiem_mo_ta import kiem_kho, chuan_hoa_noi_dung, KHUNG_JSON_GEMINI

Quy tắc an toàn: file gốc luôn được giữ ở _mo-ta/<thư mục con>/_goc-kiem/ TRƯỚC khi ghi lại (kho_canh.py bỏ qua mọi thư mục
con bắt đầu bằng "_" trong _mo-ta, nên bản gốc không bị nạp 2 lần). Không bao giờ xoá/di chuyển video hay file mô tả."""
import ast, copy, json, re, subprocess, sys, time
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm")
THU_GOC = "_goc-kiem"

CO_CANH = ["can_canh", "trung", "toan", "tu_tren_xuong"]
MAY_QUAY = ["dung_yen", "lia", "zoom", "rung_tay"]
CHAC_CHAN = ["cao", "vua", "thap"]
LOAI_VAN_DE = ["nghi_AI", "watermark", "lat_guong", "chu_chen_san", "anh_ghep", "logo_kenh", "mo_nhoe", "rung_manh", "vien_den", "cat_mat"]
CAY = ["ca_phe", "ho_tieu", "sau_rieng", "ot", "rau_mau", "thanh_long", "cay_khac", "khong_ro", "khong_co"]
THE = ["cam_chai", "can_san_pham", "nhan_doc_ro", "nhan_mat_sau", "combo_san_pham", "pha_thuoc", "phun_xit", "tuoi_goc", "re_cay",
       "dot_non", "la_xanh", "cay_xanh_sung", "cay_suy_yeu", "la_benh", "cay_con", "cay_lon", "trai", "hoa", "truoc_sau",
       "nguoi_noi_vao_may", "nguoi_lam_vuon", "cua_hang", "kho_hang", "canh_vuon_rong"]

# --- tên trường lạc đường → tên chuẩn -------------------------------------------------------------------------------------
BI_DANH_GOC = {
    "video": ["video_path", "ten_video", "file", "filename", "file_name", "ten_file", "duong_dan", "path", "video_file"],
    "thoi_luong_s": ["thoi_luong", "duration", "duration_s", "duration_seconds", "do_dai_s", "do_dai", "length_s"],
    "tom_tat": ["summary", "tomtat", "tom_tat_video", "mo_ta_chung"],
    "nguoi": ["people", "person", "nguoi_trong_video"],
    "boi_canh": ["setting", "background", "scene_context", "boi_canh_chung"],
    "cay_trong": ["cay", "crops", "crop", "loai_cay"],
    "loi_noi_tom_tat": ["loi_noi", "speech", "speech_summary", "transcript_summary"],
    "san_pham_thay": ["san_pham", "products", "products_seen", "san_pham_xuat_hien", "san_pham_thay_duoc"],
    "canh_quay": ["canh", "cac_canh", "scenes", "shots", "canh_quay_chi_tiet", "danh_sach_canh", "segments", "scene_list"],
    "van_de": ["issues", "problems", "van_de_phat_hien", "van_de_chat_luong", "flags"],
    "dung_lam_bang_chung": ["dung_lam_bang_chung_duoc", "can_use_as_proof", "use_as_proof", "dung_duoc_lam_bang_chung"],
}
BI_DANH_CANH = {
    "tu_s": ["start", "start_s", "start_time", "bat_dau", "bat_dau_s", "tu", "tu_giay", "t_start", "from", "begin", "tu_s_"],
    "den_s": ["end", "end_s", "end_time", "ket_thuc", "ket_thuc_s", "den", "den_giay", "t_end", "to", "until"],
    "khung_dep_nhat": ["khung_dep", "best_window", "best_frame", "khung_dep_nhat_s", "khoang_dep_nhat", "best_range", "khung_tot_nhat"],
    "hinh": ["mo_ta", "description", "desc", "noi_dung", "visual", "hinh_anh", "mo_ta_canh"],
    "co_canh": ["shot_size", "kich_co_canh", "co_canh_quay", "framing"],
    "may_quay": ["camera", "camera_motion", "chuyen_dong_may", "kieu_may"],
    "san_pham": ["product", "san_pham_trong_canh"],
    "chu_chen_san": ["chu_chen", "text_overlay", "overlay_text", "chu_tren_hinh", "sticker"],
    "the": ["tags", "tag", "nhan", "the_tag", "labels", "the_canh"],
    "diem": ["score", "rating", "diem_so", "diem_chat_luong", "quality", "quality_score"],
    "chac_chan": ["confidence", "do_tin_cay", "do_chac_chan"],
}
BI_DANH_SP = {
    "ten_tren_nhan": ["ten", "name", "label", "ten_san_pham", "nhan", "ten_nhan"],
    "tu_s": BI_DANH_CANH["tu_s"], "den_s": BI_DANH_CANH["den_s"],
    "la_san_pham_khac": ["san_pham_khac", "is_other_product", "la_hang_khac", "hang_khac", "other_brand"],
}
BI_DANH_VD = {
    "loai": ["type", "kind", "loai_van_de", "category"],
    "mo_ta": ["description", "desc", "chi_tiet", "ghi_chu", "note"],
    "tu_s": BI_DANH_CANH["tu_s"], "den_s": BI_DANH_CANH["den_s"],
}
KHUNG_BAO_BOC = ["mo_ta", "data", "result", "ket_qua", "output", "video_description", "mo_ta_video", "response", "json"]


# --- đọc JSON "lỏng" ------------------------------------------------------------------------------------------------------
def _bo_phay_thua(s):
    """Bỏ dấu phẩy thừa trước } hoặc ] (không đụng nội dung chuỗi)."""
    out, i, n, in_str, esc = [], 0, len(s), False, False
    while i < n:
        c = s[i]
        if in_str:
            out.append(c)
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': in_str = False
        elif c == '"':
            in_str = True; out.append(c)
        elif c == ",":
            j = i + 1
            while j < n and s[j] in " \t\r\n":
                j += 1
            if j < n and s[j] in "}]":
                pass                                     # bỏ phẩy
            else:
                out.append(c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def doc_json_long(text):
    """→ (đối tượng, [ghi chú đã làm]). Ném ValueError nếu không đọc nổi."""
    ghi = []
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig", errors="replace")
    if text.startswith("﻿"):
        text = text[1:]; ghi.append("bỏ dấu BOM")
    try:
        return json.loads(text), ghi
    except Exception:
        pass
    t = text.strip()
    m = re.search(r"```(?:json|JSON)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip(); ghi.append("bỏ khung ```")
    else:
        t = re.sub(r"^```(?:json|JSON)?\s*", "", t); t = re.sub(r"\s*```\s*$", "", t)
    a = min([i for i in (t.find("{"), t.find("[")) if i >= 0], default=-1)
    b = max(t.rfind("}"), t.rfind("]"))
    if a < 0 or b <= a:
        raise ValueError("không thấy JSON trong file")
    if a > 0 or b < len(t) - 1:
        ghi.append("bỏ chữ thừa ngoài JSON")
    t = t[a:b + 1]
    for thu, mo_ta in ((lambda x: x, None), (_bo_phay_thua, "bỏ dấu phẩy thừa")):
        s = thu(t)
        try:
            d = json.loads(s)
            if mo_ta: ghi.append(mo_ta)
            return d, ghi
        except Exception:
            pass
    s = _bo_phay_thua(t)
    try:                                                    # nháy đơn / True / None kiểu Python
        d = ast.literal_eval(s)
        if isinstance(d, (dict, list)):
            ghi.append("sửa nháy đơn/kiểu Python")
            return d, ghi
    except Exception:
        pass
    raise ValueError("JSON hỏng (không đọc được, có thể bị cắt giữa chừng)")


# --- chuẩn hoá giá trị ----------------------------------------------------------------------------------------------------
def _so(x):
    """Số giây từ số / chuỗi '5.2', '5,2s', '0:05', '00:01:02.5', '5 giây'. None nếu không hiểu."""
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if x == x and abs(x) != float("inf") else None
    if not isinstance(x, str):
        return None
    s = x.strip().lower().replace(",", ".")
    if not s:
        return None
    m = re.fullmatch(r"(\d+):(\d{1,2})(?::(\d{1,2}))?(?:\.(\d+))?", s)
    if m:
        a, b, c, f = m.groups()
        sec = (int(a) * 3600 + int(b) * 60 + int(c)) if c is not None else (int(a) * 60 + int(b))
        return sec + (float("0." + f) if f else 0.0)
    m = re.fullmatch(r"(?:(\d+)\s*(?:m|phut|phút|min)\s*)?(\d+(?:\.\d+)?)\s*(?:s|sec|giay|giây|gi)?", s)
    if m and (m.group(1) or re.search(r"\d", s)):
        return (int(m.group(1)) * 60 if m.group(1) else 0) + float(m.group(2))
    return None


def _la_chuoi_gio(x):
    return isinstance(x, str) and not re.fullmatch(r"\s*-?\d+(?:\.\d+)?\s*", x)


def _lay(d, ten, bi_danh):
    """Lấy giá trị theo tên chuẩn hoặc bí danh (không phân biệt hoa/thường). → (có?, giá trị, tên_đã_dùng)."""
    if ten in d:
        return True, d[ten], ten
    thap = {str(k).lower().strip().replace(" ", "_"): k for k in d}
    for ten_k in [ten] + bi_danh:
        if ten_k in thap:
            return True, d[thap[ten_k]], thap[ten_k]
    return False, None, None


def _chuoi(x):
    if x is None: return ""
    if isinstance(x, str): return x
    if isinstance(x, (list, tuple)): return "; ".join(_chuoi(i) for i in x)
    if isinstance(x, dict): return json.dumps(x, ensure_ascii=False)
    return str(x)


def _ds_chuoi(x):
    if x is None: return []
    if isinstance(x, str):
        return [p.strip() for p in re.split(r"[,;|/]", x) if p.strip()]
    if isinstance(x, (list, tuple, set)):
        return [str(i).strip() for i in x if str(i).strip()]
    return [str(x)]


def _tag(x):
    return re.sub(r"\s+", "_", str(x).strip().lower())


def _bool(x):
    if isinstance(x, bool): return x
    if isinstance(x, (int, float)): return bool(x)
    if isinstance(x, str): return x.strip().lower() in ("true", "co", "có", "yes", "y", "1", "đúng", "dung")
    return False


def _enum(x, ds, khop_mem=None):
    """Đưa 1 giá trị về đúng từ trong ds nếu nhìn là biết (hoa/thường, khoảng trắng, dấu); không thì giữ nguyên dạng tag."""
    if x is None: return None
    t = _tag(x)
    low = {d.lower(): d for d in ds}
    if t in low: return low[t]
    t2 = _bo_dau(t)
    for d in ds:
        if _bo_dau(d.lower()) == t2: return d
    if khop_mem:
        return khop_mem.get(t2, t)
    return t


def _bo_dau(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


KHOP_CHAC = {"high": "cao", "medium": "vua", "med": "vua", "mid": "vua", "low": "thap", "trung_binh": "vua", "tb": "vua", "thap": "thap",
             "cao": "cao", "vua": "vua"}
KHOP_MAY = {"static": "dung_yen", "still": "dung_yen", "pan": "lia", "zoom_in": "zoom", "zoom_out": "zoom", "handheld": "rung_tay",
            "dung_im": "dung_yen", "tinh": "dung_yen"}
KHOP_CO = {"close_up": "can_canh", "closeup": "can_canh", "close": "can_canh", "medium": "trung", "wide": "toan", "full": "toan",
           "top_down": "tu_tren_xuong", "overhead": "tu_tren_xuong", "can": "can_canh", "trung_canh": "trung", "toan_canh": "toan"}


# --- chuẩn hoá cả file ----------------------------------------------------------------------------------------------------
class Hong(Exception):
    pass


def _boc_goi(d, ghi):
    """Gỡ lớp bọc thừa: [ {...} ], {"mo_ta": {...}}, hoặc mảng cảnh trần."""
    for _ in range(4):
        if isinstance(d, list):
            if len(d) == 1 and isinstance(d[0], dict):
                d = d[0]; ghi.append("gỡ lớp mảng bọc ngoài"); continue
            if d and all(isinstance(i, dict) for i in d) and any(("tu_s" in i or "start" in i or "start_s" in i) for i in d):
                ghi.append("file chỉ là danh sách cảnh → đóng khung chuẩn")
                d = {"canh_quay": d}; break
            raise Hong("không phải đối tượng JSON mô tả video")
        if not isinstance(d, dict):
            raise Hong("không phải đối tượng JSON mô tả video")
        if not _lay(d, "canh_quay", BI_DANH_GOC["canh_quay"])[0]:
            for k in d:
                if str(k).lower() in KHUNG_BAO_BOC and isinstance(d[k], (dict, list)):
                    ghi.append(f'gỡ lớp bọc thừa "{k}"'); d = d[k]; break
            else:
                break
            continue
        break
    return d


def _thoi_gian(v, ten, ghi, dai, moc):
    """Giây (float) từ mọi dạng; None nếu không hiểu."""
    if _la_chuoi_gio(v):
        s = _so(v)
        if s is not None:
            moc[ten] = True
        return s
    return _so(v)


def chuan_hoa_noi_dung(duoi, dai_video=None, video_rel=None, la_obj=False):
    """Nhận text (hoặc đối tượng đã đọc) → (đối tượng chuẩn, [đã sửa gì], [cảnh báo]).
    dai_video: giây thật từ ffprobe (None = tin thoi_luong_s trong file). Ném Hong nếu không cứu được."""
    ghi, canh_bao = [], []
    if la_obj:
        d = copy.deepcopy(duoi)
    else:
        try:
            d, g = doc_json_long(duoi)
        except ValueError as e:
            raise Hong(str(e))
        ghi += g
    d = _boc_goi(d, ghi)
    out = {}
    da_dung_ten = set()

    def cu(ten):
        c, v, k = _lay(d, ten, BI_DANH_GOC.get(ten, []))
        if c and k != ten:
            ghi.append(f'đổi tên trường "{k}" → "{ten}"')
        if k: da_dung_ten.add(k)
        return c, v

    # thoi_luong_s
    c, v = cu("thoi_luong_s")
    dai_file = _so(v) if c else None
    if c and dai_file is not None and _la_chuoi_gio(v):
        ghi.append(f'thoi_luong_s "{v}" → {round(dai_file, 2)} giây')
    if dai_video and dai_video > 0:
        if dai_file is None or abs(dai_file - dai_video) > 1.0:
            ghi.append(f"thoi_luong_s {'thiếu' if dai_file is None else round(dai_file, 2)} → {round(dai_video, 2)} (đo bằng ffprobe)")
            dai_file = round(dai_video, 2)
        elif dai_file != dai_video and abs(dai_file - dai_video) > 0.05:
            dai_file = dai_file
    dai = dai_video if dai_video and dai_video > 0 else dai_file
    if dai_file is None and dai:
        dai_file = round(dai, 2)
    out["thoi_luong_s"] = dai_file if dai_file is not None else 0.0

    # video
    c, v = cu("video")
    out["video"] = v if isinstance(v, str) and v.strip() else (video_rel or "")
    if not (isinstance(v, str) and v.strip()) and video_rel:
        ghi.append(f'thiếu "video" → điền "{video_rel}"')
    elif isinstance(v, str) and "\\" in v and video_rel and video_rel.replace("\\", "/") != v:
        pass

    # các trường văn bản
    for k in ("tom_tat", "nguoi", "boi_canh", "loi_noi_tom_tat"):
        c, v = cu(k)
        if not c:
            ghi.append(f'thiếu "{k}" → để trống'); out[k] = ""
        elif not isinstance(v, str):
            ghi.append(f'"{k}" không phải chữ → đổi thành chữ'); out[k] = _chuoi(v)
        else:
            out[k] = v

    # cay_trong
    c, v = cu("cay_trong")
    if not c:
        ghi.append('thiếu "cay_trong" → []'); out["cay_trong"] = []
    else:
        ds = _ds_chuoi(v)
        if not isinstance(v, list):
            ghi.append('"cay_trong" phải là mảng → tách thành mảng')
        moi = []
        for x in ds:
            e = _enum(x, CAY)
            if e != x: ghi.append(f'cay_trong "{x}" → "{e}"') if _tag(x) != e else None
            moi.append(e)
        out["cay_trong"] = moi

    # dung_lam_bang_chung
    c, v = cu("dung_lam_bang_chung")
    if not c:
        out["dung_lam_bang_chung"] = True; ghi.append('thiếu "dung_lam_bang_chung" → true (mặc định)')
    elif not isinstance(v, bool):
        out["dung_lam_bang_chung"] = _bool(v); ghi.append('"dung_lam_bang_chung" → true/false')
    else:
        out["dung_lam_bang_chung"] = v

    # --- canh_quay
    c, cq = cu("canh_quay")
    if not c or not isinstance(cq, list):
        if c and isinstance(cq, dict):
            cq = [cq]; ghi.append('"canh_quay" là 1 đối tượng → bọc thành mảng')
        else:
            raise Hong('không có mục "canh_quay"')
    # có thang mili-giây không? (cảnh báo bằng tỉ lệ so với thời lượng)
    tho = []
    for s in cq:
        if isinstance(s, dict):
            a = _so(_lay(s, "tu_s", BI_DANH_CANH["tu_s"])[1]); b = _so(_lay(s, "den_s", BI_DANH_CANH["den_s"])[1])
            if a is not None and b is not None: tho.append((a, b))
    he_so = 1.0
    if dai and tho and max(b for _, b in tho) > max(dai * 3, 100) and max(b for _, b in tho) / 1000.0 <= dai * 1.1 and all(a == int(a) or True for a, _ in tho):
        he_so = 0.001; ghi.append("thời gian cảnh tính bằng mili-giây → đổi sang giây")
    # thang điểm
    diems = []
    for s in cq:
        if isinstance(s, dict):
            c2, dv, _k = _lay(s, "diem", BI_DANH_CANH["diem"])
            if c2:
                x = _diem_tho(dv)
                if x is not None: diems.append(x)
    hs_diem, ten_thang = 1.0, None
    if diems:
        mx = max(x[0] / x[1] * 5 if x[1] else x[0] for x in diems)    # quy về thang 0–5 theo mẫu số nếu có "x/10"
        co_mau = any(x[1] for x in diems)
        if co_mau:
            ten_thang = "mẫu số riêng"
        else:
            m0 = max(x[0] for x in diems)
            if m0 > 100: hs_diem, ten_thang = 5 / m0, f"0–{m0:g}"
            elif m0 > 10: hs_diem, ten_thang = 5 / 100, "0–100"
            elif m0 > 5: hs_diem, ten_thang = 5 / 10, "0–10"
            elif m0 <= 1.0 and any(0 < x[0] < 1 for x in diems): hs_diem, ten_thang = 5.0, "0–1"
        if ten_thang:
            ghi.append(f"điểm chấm theo thang {ten_thang} → quy về 0–5")

    canh_moi, bo_hop_le, kep, bo_ngoai = [], 0, 0, 0
    bo_ly_do = []
    for i, s in enumerate(cq):
        if not isinstance(s, dict):
            bo_ly_do.append(f"cảnh {i + 1}: không phải đối tượng"); continue
        e = {}
        cc, v, k = _lay(s, "tu_s", BI_DANH_CANH["tu_s"])
        a = _so(v) if cc else None
        cc2, v2, k2 = _lay(s, "den_s", BI_DANH_CANH["den_s"])
        b = _so(v2) if cc2 else None
        if (cc and k != "tu_s") or (cc2 and k2 != "den_s"):
            ghi.append(f'cảnh: đổi tên "{k}/{k2}" → "tu_s/den_s"') if f"{k}/{k2}" not in " ".join(ghi) else None
        if a is None or b is None:
            bo_ly_do.append(f"cảnh {i + 1}: thiếu/sai mốc giây"); continue
        if _la_chuoi_gio(v) or _la_chuoi_gio(v2):
            ghi.append(f'mốc giờ dạng chữ ("{v}"→{round(a, 2)}) đổi sang giây') if "mốc giờ dạng chữ" not in " ".join(ghi) else None
        a, b = a * he_so, b * he_so
        if a < 0: a = 0.0
        if b <= a:
            bo_hop_le += 1; bo_ly_do.append(f"cảnh {i + 1}: den_s ≤ tu_s ({a:g}–{b:g})"); continue
        if dai:
            if a >= dai - 0.05:
                bo_ngoai += 1; bo_ly_do.append(f"cảnh {i + 1}: bắt đầu {a:g}s ≥ độ dài video {dai:.1f}s"); continue
            if b > dai + 1.0:                      # vượt ≤ 1 s: coi là sai số, giữ nguyên (không đáng sửa file)
                kep += 1; b = dai
        e["tu_s"], e["den_s"] = round(a, 2) if a != int(a) else a, round(b, 2) if b != int(b) else b
        # khung đẹp nhất
        _c, kd, _k = _lay(s, "khung_dep_nhat", BI_DANH_CANH["khung_dep_nhat"])
        pair = _cap_khung(kd, he_so)
        # điểm
        cd, dv, _k = _lay(s, "diem", BI_DANH_CANH["diem"])
        diem = None
        if cd:
            x = _diem_tho(dv)
            if x is not None:
                val = x[0] / x[1] * 5 if x[1] else x[0] * hs_diem
                diem = int(max(0, min(5, round(val + 1e-9))))
        if diem is None:
            diem = 1; ghi.append("cảnh thiếu/sai điểm → 1") if "cảnh thiếu/sai điểm" not in " ".join(ghi) else None
        e["diem"] = diem
        if diem == 0:
            e["khung_dep_nhat"] = None
        else:
            ok = pair and e["tu_s"] <= pair[0] < pair[1] <= e["den_s"] + 1e-6
            if pair and not ok:
                # kẹp vào trong cảnh
                p0, p1 = max(e["tu_s"], pair[0]), min(e["den_s"], pair[1])
                pair = [p0, p1] if p1 > p0 else None
            if not pair and kd is not None:
                pair = None
            if pair is None and kd is not None or (not _c):
                mid = (e["tu_s"] + e["den_s"]) / 2; h = min(2.0, (e["den_s"] - e["tu_s"]) / 2)
                pair = [round(mid - h, 2), round(mid + h, 2)]
            e["khung_dep_nhat"] = [round(x, 2) for x in pair] if pair else None
        # chữ
        for kk, dflt in (("hinh", ""), ("san_pham", "khong_co"), ("chu_chen_san", "khong")):
            cc3, v3, k3 = _lay(s, kk, BI_DANH_CANH.get(kk, []))
            e[kk] = _chuoi(v3) if cc3 and v3 is not None else dflt
        e["co_canh"] = _enum(_lay(s, "co_canh", BI_DANH_CANH["co_canh"])[1], CO_CANH, KHOP_CO) or ""
        e["may_quay"] = _enum(_lay(s, "may_quay", BI_DANH_CANH["may_quay"])[1], MAY_QUAY, KHOP_MAY) or ""
        # thẻ
        cc4, v4, k4 = _lay(s, "the", BI_DANH_CANH["the"])
        if cc4 and not isinstance(v4, list):
            ghi.append('"the" không phải mảng → tách thành mảng') if '"the" không phải mảng' not in " ".join(ghi) else None
        e["the"] = [_enum(x, THE) for x in _ds_chuoi(v4)] if cc4 else []
        e["chac_chan"] = _enum(_lay(s, "chac_chan", BI_DANH_CANH["chac_chan"])[1], CHAC_CHAN, KHOP_CHAC) or "vua"
        for kx, vx in s.items():                                    # giữ trường lạ (có thể do người thêm)
            if kx not in e and _lay({kx: 1}, "x", [])[0] is False and all(kx != al for al in sum(BI_DANH_CANH.values(), [])):
                e[kx] = vx
        canh_moi.append(e)
    canh_moi.sort(key=lambda x: (x["tu_s"], x["den_s"]))
    if [json.dumps(x, sort_keys=True, default=str) for x in canh_moi] != [json.dumps(x, sort_keys=True, default=str) for x in
            sorted(canh_moi, key=lambda x: x["tu_s"])] or False:
        pass
    # thứ tự gốc có đúng không?
    goc_a = []
    for s in cq:
        if isinstance(s, dict):
            a = _so(_lay(s, "tu_s", BI_DANH_CANH["tu_s"])[1])
            if a is not None: goc_a.append(a * he_so)
    if goc_a != sorted(goc_a):
        ghi.append("sắp lại cảnh theo thời gian")
    if kep: ghi.append(f"{kep} cảnh vượt quá độ dài video → cắt cuối cảnh bằng độ dài video")
    if bo_hop_le: ghi.append(f"bỏ {bo_hop_le} cảnh có den_s ≤ tu_s")
    if bo_ngoai: ghi.append(f"bỏ {bo_ngoai} cảnh nằm ngoài độ dài video")
    nho_khac = [x for x in bo_ly_do if "den_s ≤" not in x and "độ dài video" not in x]
    if nho_khac: ghi.append(f"bỏ {len(nho_khac)} cảnh hỏng ({'; '.join(nho_khac[:3])})")
    out["canh_quay"] = canh_moi
    if not canh_moi:
        raise Hong("không còn cảnh hợp lệ nào" + (": " + "; ".join(bo_ly_do[:3]) if bo_ly_do else ""))

    # --- san_pham_thay
    c, sp = cu("san_pham_thay")
    out_sp = []
    if c and isinstance(sp, dict):
        sp = [sp]; ghi.append('"san_pham_thay" là 1 đối tượng → bọc thành mảng')
    for s in (sp if c and isinstance(sp, list) else []):
        if isinstance(s, str):
            s = {"ten_tren_nhan": s}
            ghi.append("san_pham_thay là danh sách chữ → đổi thành đối tượng (cả video)")
        if not isinstance(s, dict): continue
        e = {"ten_tren_nhan": _chuoi(_lay(s, "ten_tren_nhan", BI_DANH_SP["ten_tren_nhan"])[1]) or "không đọc rõ"}
        a = _so(_lay(s, "tu_s", BI_DANH_SP["tu_s"])[1]); b = _so(_lay(s, "den_s", BI_DANH_SP["den_s"])[1])
        a = 0.0 if a is None else a * he_so; b = (dai or a) if b is None else b * he_so
        if dai and b > dai + 1.0: b = dai
        e["tu_s"], e["den_s"] = a, max(a, b)
        kk = _lay(s, "la_san_pham_khac", BI_DANH_SP["la_san_pham_khac"])
        e["la_san_pham_khac"] = _bool(kk[1]) if kk[0] else False
        if kk[0] and not isinstance(kk[1], bool):
            ghi.append('"la_san_pham_khac" → true/false') if '"la_san_pham_khac"' not in " ".join(ghi) else None
        if e not in out_sp:
            out_sp.append(e)
    if not c:
        ghi.append('thiếu "san_pham_thay" → []')
    out["san_pham_thay"] = out_sp

    # --- van_de
    c, vd = cu("van_de")
    out_vd = []
    for s in (vd if c and isinstance(vd, list) else []):
        if isinstance(s, str):
            s = {"mo_ta": s}
        if not isinstance(s, dict): continue
        loai = _lay(s, "loai", BI_DANH_VD["loai"])[1]
        mo_ta = _chuoi(_lay(s, "mo_ta", BI_DANH_VD["mo_ta"])[1])
        loai_c = _enum(loai, LOAI_VAN_DE) if loai else None
        if loai_c is not None and loai_c not in LOAI_VAN_DE:
            doan = _doan_loai(str(loai))               # chỉ đoán từ chính chữ "loai" (không đoán từ mô tả: tránh vô tình thành loại NẶNG làm mất cảnh)
            if doan: ghi.append(f'van_de loai "{loai}" → "{doan}"'); loai_c = doan
            else: canh_bao.append(f'van_de loai lạ "{loai}" — giữ nguyên')
        a = _so(_lay(s, "tu_s", BI_DANH_VD["tu_s"])[1]); b = _so(_lay(s, "den_s", BI_DANH_VD["den_s"])[1])
        a = 0.0 if a is None else a * he_so; b = (dai or a) if b is None else b * he_so
        if dai and b > dai + 1.0: b = dai
        e = {"tu_s": a, "den_s": max(a, b)}
        if loai_c is not None: e["loai"] = loai_c      # không có loai → để nguyên không có (không bịa)
        e["mo_ta"] = mo_ta
        out_vd.append(e)
    if not c:
        ghi.append('thiếu "van_de" → []')
    elif not isinstance(vd, list):
        ghi.append('"van_de" không phải mảng → []')
    out["van_de"] = out_vd

    # giữ trường lạ ở cấp trên (is_duplicate, ban_trung_cua, duplicate_of... do người/AI khác thêm)
    tat_ca_bd = {a for v in BI_DANH_GOC.values() for a in v}
    for k, v in d.items():
        if k not in out and k not in da_dung_ten and str(k).lower() not in tat_ca_bd:
            out[k] = v
    for k in ("video", "thoi_luong_s", "tom_tat", "nguoi", "boi_canh", "cay_trong", "loi_noi_tom_tat", "san_pham_thay", "canh_quay", "van_de",
              "dung_lam_bang_chung"):
        out[k] = out.pop(k)                                         # đưa khung chuẩn xuống cuối → thứ tự gọn; cờ lạ lên đầu
    return out, _gon(ghi), canh_bao


def _gon(ghi):
    seen, r = set(), []
    for g in ghi:
        if g not in seen:
            seen.add(g); r.append(g)
    return r


def _diem_tho(v):
    """→ (giá trị, mẫu số|None) hoặc None. Hiểu 4, 4.5, '4', '4/5', '8/10', '80%'."""
    if isinstance(v, bool) or v is None: return None
    if isinstance(v, (int, float)): return (float(v), None)
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(?:/\s*(\d+(?:[.,]\d+)?))?\s*(%)?\s*", v)
        if not m: return None
        x = float(m.group(1).replace(",", "."))
        if m.group(3): return (x, 100.0)
        return (x, float(m.group(2).replace(",", ".")) if m.group(2) else None)
    return None


def _cap_khung(kd, he_so):
    """khung_dep_nhat → [a, b] giây hoặc None (null/hỏng)."""
    if kd is None: return None
    a = b = None
    if isinstance(kd, (list, tuple)) and len(kd) == 2:
        a, b = _so(kd[0]), _so(kd[1])
    elif isinstance(kd, dict):
        a = _so(_lay(kd, "tu_s", BI_DANH_CANH["tu_s"])[1]); b = _so(_lay(kd, "den_s", BI_DANH_CANH["den_s"])[1])
    elif isinstance(kd, str):
        p = re.split(r"\s*(?:-|–|—|->|→|den|đến|to)\s*", kd.strip(), maxsplit=1)
        if len(p) == 2: a, b = _so(p[0]), _so(p[1])
    if a is None or b is None: return None
    a, b = a * he_so, b * he_so
    if b < a: a, b = b, a
    return [a, b] if b > a else None


def _doan_loai(t):
    t = _bo_dau(t.lower())
    for k, kws in (("nghi_AI", ["ai tao", "nghi ai", "ai-generated", "veo", "sora", "gemini"]), ("watermark", ["watermark", "bieu tuong"]),
                   ("lat_guong", ["guong", "nguoc", "mirror"]), ("chu_chen_san", ["chu chen", "sticker", "binh luan", "text", "overlay"]),
                   ("anh_ghep", ["ghep", "composite"]), ("logo_kenh", ["logo"]), ("mo_nhoe", ["mo", "nhoe", "blur"]),
                   ("rung_manh", ["rung", "shake"]), ("vien_den", ["vien den", "black bar"]), ("cat_mat", ["cat mat", "mat nguoi"])):
        if any(w in t for w in kws): return k
    return None


# --- ffprobe (cùng lệnh engine dùng: anh_bia.py / bang_soat_lo.py) ----------------------------------------------------------
def do_dai_video(v):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                           capture_output=True, text=True, timeout=60)
        x = float(r.stdout.strip().splitlines()[0])
        return x if x > 0 else None
    except Exception:
        return None


# --- quét kho --------------------------------------------------------------------------------------------------------------
def _kho_cua(ma):
    sp = json.loads((HUB / "san-pham" / ma / "san-pham.json").read_text(encoding="utf-8"))
    return Path(sp["kho_video"])


def liet_ke_video(kho):
    """Mọi video trong kho (bỏ thư mục bắt đầu bằng _ như _tam, _mo-ta). → {đường dẫn tương đối (dấu /): Path}."""
    import os
    kq = {}
    for g, dirs, files in os.walk(kho, onerror=lambda e: None):
        dirs[:] = [n for n in dirs if not n.startswith("_")]
        for n in files:
            if n.lower().endswith(VIDEO_EXT):
                p = Path(g) / n
                kq[p.relative_to(kho).as_posix()] = p
    return kq


def liet_ke_mo_ta(kho):
    """Các file mô tả mà kho_canh.py SẼ đọc (bỏ mọi thư mục con bắt đầu bằng _ như _goc-gemini, _goc-kiem)."""
    md = kho / "_mo-ta"
    if not md.exists(): return []
    return sorted(x for x in md.rglob("*.mo-ta.json") if not any(p.startswith("_") for p in x.relative_to(md).parts[:-1]))


def _video_cua_file(kho, mt, d_thô, videos):
    """Tìm video mà file mô tả này ứng với. → (rel|None, dùng_trường_video: bool)."""
    md = kho / "_mo-ta"
    f = None
    if isinstance(d_thô, dict) and isinstance(d_thô.get("video"), str) and d_thô["video"].strip():
        f = d_thô["video"].strip().replace("\\", "/")
        if f in videos: return f, True
        parts = Path(f).parts
        alt = "/".join(parts[1:]) if len(parts) > 1 else None          # giống kho_canh.py: bỏ phần đầu
        if alt and alt in videos: return alt, True
        thap = {k.lower(): k for k in videos}
        if f.lower() in thap: return thap[f.lower()], False
    rel_dir = mt.parent.relative_to(md).as_posix()
    ten = mt.name[:-len(".mo-ta.json")]
    for cand in ([ten] if ten.lower().endswith(VIDEO_EXT) else [ten + e for e in VIDEO_EXT]):
        r = f"{rel_dir}/{cand}" if rel_dir != "." else cand
        if r in videos: return r, False
    thap = {k.lower(): k for k in videos}
    for cand in ([ten] if ten.lower().endswith(VIDEO_EXT) else [ten + e for e in VIDEO_EXT]):
        r = f"{rel_dir}/{cand}" if rel_dir != "." else cand
        if r.lower() in thap: return thap[r.lower()], False
    return None, False


def _dai(p):
    """Đường dẫn tiền tố dài (extended-length) để mở được file có tên rất dài trên Windows."""
    pre = "\\\\?\\"
    s = str(p)
    if sys.platform != "win32" or s.startswith(pre):
        return Path(s)
    return Path(pre + str(Path(s).resolve()))


def _doc_byte(mt):
    """→ (bytes, đường_dẫn_quá_dài?)"""
    try:
        return Path(mt).read_bytes(), False
    except OSError:
        return _dai(mt).read_bytes(), True


def _luu_goc(mt, noi_dung_goc):
    """Giữ bản gốc ở <thư mục file>/_goc-kiem/<tên> (không ghi đè bản đã có: thêm số)."""
    g = _dai(mt.parent) / THU_GOC
    g.mkdir(exist_ok=True)
    dich = g / mt.name
    n = 1
    while dich.exists():
        dich = g / f"{mt.name}.{n}"; n += 1
    dich.write_bytes(noi_dung_goc)
    return dich


def ghi_mo_ta(mt, obj, goc_bytes=None):
    """Ghi file mô tả (có giữ bản gốc nếu file đã tồn tại và có nội dung gốc)."""
    if goc_bytes is not None:
        _luu_goc(mt, goc_bytes)
    mt = _dai(mt)
    tmp = mt.with_name(mt.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(mt)


def _can_ffprobe(d):
    """File mô tả đã có thoi_luong_s > 0 và mọi cảnh kết thúc ≤ thoi_luong_s + 1 → tin số trong file, khỏi chạy ffprobe."""
    try:
        if not isinstance(d, dict):
            return True
        c, v, _k = _lay(d, "thoi_luong_s", BI_DANH_GOC["thoi_luong_s"])
        dai = _so(v) if c else None
        if not dai or dai <= 0:
            return True
        c, cq, _k = _lay(d, "canh_quay", BI_DANH_GOC["canh_quay"])
        if c and isinstance(cq, dict):
            cq = [cq]
        if not c or not isinstance(cq, list):
            return True
        for sc in cq:
            if not isinstance(sc, dict):
                continue
            c2, v2, _k2 = _lay(sc, "den_s", BI_DANH_CANH["den_s"])
            b = _so(v2) if c2 else None
            if b is not None and b > dai + 1.0:
                return True
        return False
    except Exception:
        return True


def kiem_kho(ma_hoac_kho, sua=False, tien_do=None, do_dai=do_dai_video, chi_ffprobe_khi_can=True):
    """Kiểm định kho. sua=False → CHẠY THỬ (không ghi gì). Trả báo cáo:
    {da_dung: số file đúng sẵn, da_sua: [{file, sua:[..]}], hong: [{file, loi}], thieu_mo_ta: [video...], mo_coi: [file mô tả không còn video],
     trung: [{video, files}], canh_bao: [...], tong_video, tong_mo_ta, che_do}
    chi_ffprobe_khi_can=True: chỉ đo độ dài video (ffprobe) khi file mô tả thiếu thoi_luong_s hoặc có cảnh vượt quá nó."""
    kho = Path(ma_hoac_kho) if (isinstance(ma_hoac_kho, Path) or Path(str(ma_hoac_kho)).is_absolute()) else _kho_cua(ma_hoac_kho)
    rep = {"che_do": "that" if sua else "thu", "kho": str(kho), "da_dung": 0, "da_sua": [], "hong": [], "thieu_mo_ta": [], "mo_coi": [],
           "trung": [], "canh_bao": [], "tong_video": 0, "tong_mo_ta": 0, "bo_canh": 0, "da_ghi": 0}
    if not kho.exists():
        rep["loi"] = "Không tìm thấy thư mục kho."; return rep
    videos = liet_ke_video(kho)
    files = liet_ke_mo_ta(kho)
    rep["tong_video"], rep["tong_mo_ta"] = len(videos), len(files)
    cua_video = {}                                           # rel video → [file mô tả]
    xu_ly = []
    for i, mt in enumerate(files):
        if tien_do: tien_do(i, len(files), mt.name)
        goc, dai_qua = _doc_byte(mt)
        if dai_qua:
            rep["canh_bao"].append({"file": mt.relative_to(kho / "_mo-ta").as_posix()[:80] + "…", "ghi_chu": "đường dẫn dài hơn 260 ký tự — bộ nạp kho (kho_canh.py) KHÔNG đọc được file này; nên đổi tên ngắn lại"})
        rel_mt = mt.relative_to(kho / "_mo-ta").as_posix()
        try:
            d_tho, g0 = doc_json_long(goc)
        except ValueError as e:
            rep["hong"].append({"file": rel_mt, "loi": str(e), "video": None}); continue
        try:
            d_tho = _boc_goi(copy.deepcopy(d_tho), [])
        except Hong:
            pass
        rel, theo_truong = _video_cua_file(kho, mt, d_tho, videos)
        if rel is None:
            rep["mo_coi"].append(rel_mt); continue
        cua_video.setdefault(rel, []).append(rel_mt)
        xu_ly.append((mt, rel, theo_truong, goc, rel_mt, d_tho))
    for mt, rel, theo_truong, goc, rel_mt, d_tho in xu_ly:
        vp = videos[rel]
        dai = do_dai(vp) if (not chi_ffprobe_khi_can or _can_ffprobe(d_tho)) else None
        try:
            obj, ghi, cb = chuan_hoa_noi_dung(goc, dai, rel if not theo_truong else None)
        except Hong as e:
            rep["hong"].append({"file": rel_mt, "loi": str(e), "video": rel}); continue
        for c in cb: rep["canh_bao"].append({"file": rel_mt, "ghi_chu": c})
        # so với bản đọc được gốc: có đổi thật sự không?
        try:
            goc_obj, _ = doc_json_long(goc)
        except ValueError:
            goc_obj = None
        doi = (goc_obj != obj) or any(g.startswith(("bỏ dấu BOM", "bỏ khung", "bỏ chữ", "bỏ dấu phẩy", "sửa nháy")) for g in ghi)
        if not doi:
            rep["da_dung"] += 1; continue
        if not ghi:
            ghi = ["chuẩn hoá nhẹ (thứ tự/kiểu số)"]
        n_bo = sum(int(m.group(1)) for g in ghi for m in [re.match(r"bỏ (\d+) cảnh", g)] if m)
        rep["bo_canh"] += n_bo
        rep["da_sua"].append({"file": rel_mt, "sua": ghi})
        if sua:
            ghi_mo_ta(mt, obj, goc)
            rep["da_ghi"] += 1
    for rel, ds in cua_video.items():
        if len(ds) > 1:
            rep["trung"].append({"video": rel, "files": ds})
    co_mt = set(cua_video)
    for rel in sorted(videos):
        if rel not in co_mt:
            ghi_chu = None
            loi = (kho / "_mo-ta" / Path(rel).parent / (Path(rel).name + ".loi.txt"))
            if loi.exists():
                try: ghi_chu = loi.read_text(encoding="utf-8", errors="replace").strip()[:120]
                except Exception: pass
            rep["thieu_mo_ta"].append({"video": rel, "ghi_chu": ghi_chu} if ghi_chu else rel)
    rep["so_thieu"] = len(rep["thieu_mo_ta"])
    return rep


def tom_tat(rep):
    return (f"{rep['kho']}: {rep['tong_video']} video, {rep['tong_mo_ta']} mô tả — đúng sẵn {rep['da_dung']}, "
            f"{'đã sửa' if rep['che_do'] == 'that' else 'sẽ sửa'} {len(rep['da_sua'])} (bỏ {rep['bo_canh']} cảnh), hỏng {len(rep['hong'])}, "
            f"thiếu mô tả {len(rep['thieu_mo_ta'])}, mô tả mồ côi {len(rep['mo_coi'])}, trùng {len(rep['trung'])}")


# --- khung JSON cho Gemini (response schema) --------------------------------------------------------------------------------
def _s(t, **k): return {"type": t, **k}


KHUNG_JSON_GEMINI = {
    "type": "object",
    "properties": {
        "video": _s("string"), "thoi_luong_s": _s("number"), "tom_tat": _s("string"), "nguoi": _s("string"), "boi_canh": _s("string"),
        "cay_trong": _s("array", items=_s("string", enum=CAY)),
        "loi_noi_tom_tat": _s("string"),
        "san_pham_thay": _s("array", items={"type": "object", "properties": {
            "ten_tren_nhan": _s("string"), "tu_s": _s("number"), "den_s": _s("number"), "la_san_pham_khac": _s("boolean")},
            "required": ["ten_tren_nhan", "tu_s", "den_s", "la_san_pham_khac"]}),
        "canh_quay": _s("array", items={"type": "object", "properties": {
            "tu_s": _s("number"), "den_s": _s("number"),
            "khung_dep_nhat": _s("array", items=_s("number"), nullable=True),
            "hinh": _s("string"), "co_canh": _s("string", enum=CO_CANH), "may_quay": _s("string", enum=MAY_QUAY),
            "san_pham": _s("string"), "chu_chen_san": _s("string"),
            "the": _s("array", items=_s("string", enum=THE)),
            "diem": _s("integer"), "chac_chan": _s("string", enum=CHAC_CHAN)},
            "required": ["tu_s", "den_s", "khung_dep_nhat", "hinh", "co_canh", "may_quay", "san_pham", "chu_chen_san", "the", "diem", "chac_chan"]}),
        "van_de": _s("array", items={"type": "object", "properties": {
            "tu_s": _s("number"), "den_s": _s("number"), "loai": _s("string", enum=LOAI_VAN_DE), "mo_ta": _s("string")},
            "required": ["tu_s", "den_s", "loai", "mo_ta"]}),
        "dung_lam_bang_chung": _s("boolean"),
    },
    "required": ["video", "thoi_luong_s", "tom_tat", "nguoi", "boi_canh", "cay_trong", "loi_noi_tom_tat", "san_pham_thay", "canh_quay",
                 "van_de", "dung_lam_bang_chung"],
}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__); sys.exit(1)
    r = kiem_kho(args[0], sua="--sua" in sys.argv, chi_ffprobe_khi_can="--ffprobe" not in sys.argv)
    print(tom_tat(r))
    if "--chi-tiet" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))

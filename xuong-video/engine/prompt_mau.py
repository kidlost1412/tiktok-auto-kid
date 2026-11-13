"""ĐỀ BÀI CHO AI (prompt) — MỘT bộ mẫu dùng chung cho mọi sản phẩm, ai cũng chỉnh được trong tab "Prompt AI".

- Mẫu gốc nằm trong repo:  xuong-video/prompt/<tên>.md   (3 tài liệu luật: xuong-video/luat/<tên>.md).
- Bản người dùng chỉnh nằm ở: <DATA>/prompt/<cùng tên>   → nếu có thì dùng bản này thay mẫu gốc. Xoá = về mặc định.
- Chỗ cần dữ liệu viết {{ten_bien}} (2 ngoặc nhọn, tên ASCII). Máy điền dữ liệu thật của sản phẩm lúc chạy.
  Ngoặc nhọn đơn { } là chữ thường (vd. mẫu JSON trong đề bài).
- dien(key, **ctx): chỉ thay các {{tên}} đã đăng ký trong VAI[key]["bien"]; {{x}} lạ để nguyên (kiem() báo ra).
- Mỗi lần lưu, bản cũ được cất ở <DATA>/prompt/_cu/<key>-YYYYmmdd-HHMMSS.md (giữ 20 bản gần nhất mỗi vai)."""
import datetime, re, shutil
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA, glob_kem

GIU_BAN_CU = 20
_RE_BIEN = re.compile(r"\{\{([A-Za-z][A-Za-z0-9_]*)\}\}")

VAI = {
    "he-thong": {
        "ten": "Lời dặn chung (system prompt)",
        "mo_ta": "Câu dặn đầu tiên gửi cho MỌI vai AI (biên kịch, đạo diễn, giám khảo…): nói AI là ai và phải trả lời gọn, không trò chuyện.",
        "file": "he-thong.md",
        "bien": {"vai": "Tên vai đang làm việc (vd. biên kịch, giám khảo, đạo diễn tvc_cao_cap)"},
        "bat_buoc": [],
    },
    "bien-kich": {
        "ten": "Biên kịch — viết lời đọc",
        "mo_ta": "AI viết nhiều kịch bản lời đọc + caption + hashtag cho một sản phẩm. Máy kiểm số âm tiết, từ cấm, câu lặp sau khi AI trả về.",
        "file": "bien-kich.md",
        "bien": {
            "luat": "Luật sản xuất (tài liệu \"Luật sản xuất\" bên dưới, bỏ phần Dựng)",
            "san_pham": "Hồ sơ sản phẩm (sự thật được nói, quà tặng, điều cấm…) dạng JSON",
            "so_gu": "Sổ gu của chủ hàng (cả tiêu đề) — để trống nếu chưa có sổ gu",
            "so_lieu_tiktok": "Số liệu thật từ TikTok (cả tiêu đề) — để trống nếu chưa đủ số liệu",
            "ten_phai_nhac": "Các cách gọi tên sản phẩm hợp lệ (lời đọc phải có ít nhất 1)",
            "so_ban": "Số kịch bản cần viết trong lượt này",
            "angles": "Danh sách góc bán, theo thứ tự từng bản",
            "dang": "Danh sách dạng bài, theo thứ tự từng bản",
            "quy_cach": "Dòng quy cách (dung tích/đóng gói) từng bản — để trống nếu sản phẩm chỉ có một quy cách",
            "cau_mo_da_dung": "Các câu mở bài đã dùng gần đây (để không lặp)",
            "giay_toi_thieu": "Độ dài video đích — thấp nhất (giây)",
            "giay_toi_da": "Độ dài video đích — cao nhất (giây)",
            "am_tiet_toi_thieu": "Số âm tiết tối thiểu mỗi bản",
            "am_tiet_toi_da": "Số âm tiết tối đa mỗi bản",
            "am_tiet_muc_tieu": "Số âm tiết nên nhắm tới",
            "cau_toi_thieu": "Số câu tối thiểu mỗi bản",
            "cau_toi_da": "Số câu tối đa mỗi bản",
            "cau_da_dung": "Các câu đã dùng của sản phẩm (cấm lặp nguyên văn)",
            "giong": "Danh sách tên giọng đọc, cách nhau bằng dấu |",
        },
        "bat_buoc": ["san_pham", "so_ban", "angles", "dang", "ten_phai_nhac", "giong"],
    },
    "dao-dien": {
        "ten": "Đạo diễn — lên bảng dựng",
        "mo_ta": "AI nhìn tờ ảnh cảnh ứng viên + lời đọc rồi lên bảng dựng từng câu (cảnh nào, bố cục nào, chữ nhấn, nhạc…). Máy kiểm lại mọi lựa chọn.",
        "file": "dao-dien.md",
        "bien": {
            "so_tay": "Sổ tay editor cao cấp (tài liệu bên dưới)",
            "gu": "Gu của đạo diễn lượt này (TVC cao cấp, viral…)",
            "so_gu": "Sổ gu của chủ hàng (cả tiêu đề) — để trống nếu chưa có",
            "bai_hoc": "Bài học giám khảo từ các video trước (chung + riêng sản phẩm)",
            "sp": "Hồ sơ rút gọn của sản phẩm (JSON)",
            "cau": "Lời đọc chia câu, có mốc thời gian từng câu",
            "total": "Tổng thời lượng video (giây)",
            "nhan": "Chữ nhấn do biên kịch đề xuất",
            "ds": "Danh sách cảnh ứng viên (id | vai trò | mô tả | độ dài)",
            "goi_y": "Gợi ý cảnh theo từng câu",
            "bo_cuc": "Danh sách bố cục + mô tả",
            "ct": "Các công thức dựng để chọn (JSON)",
            "data_spec": "Quy định dữ liệu của từng khối chữ",
            "phu_de": "Các kiểu phụ đề được chọn",
            "mau_nhan": "Các màu chữ nhấn được chọn",
            "chuyen_canh": "Các kiểu chuyển cảnh được chọn",
            "chuyen_dong": "Các kiểu chuyển động được chọn",
            "mau": "Các tông màu video được chọn",
            "sfx": "Các mức hiệu ứng âm thanh được chọn",
            "nhac": "Các bài nhạc nền được chọn",
            "cuoi": "Số thứ tự câu cuối (câu chốt)",
            "n": "Tổng số câu",
            "so_lieu_tiktok": "Số liệu thật TikTok về gu/công thức dựng (cả tiêu đề, bắt đầu bằng 2 dòng trống) — để trống nếu chưa có",
            "gop_y_giam_khao": "Giám khảo yêu cầu sửa bản trước (cả tiêu đề, bắt đầu bằng 2 dòng trống) — để trống ở lần dựng đầu",
        },
        "bat_buoc": ["cau", "ds", "bo_cuc", "ct", "n"],
    },
    "giam-khao": {
        "ten": "Giám khảo — chấm bản dựng",
        "mo_ta": "AI xem tờ ảnh các khung của video đã dựng, chấm điểm 1–10 và nói cần sửa gì. Điểm đạt (≥ 7) quyết định có dựng lại hay không.",
        "file": "giam-khao.md",
        "bien": {
            "ten": "Tên sản phẩm (tên ngắn)",
            "so_tay": "Sổ tay editor cao cấp (tài liệu bên dưới)",
            "cau": "Lời đọc theo thời gian",
            "tom": "Tóm tắt bảng dựng đạo diễn đã làm (JSON)",
            "so_gu": "Sổ gu của chủ hàng (cả tiêu đề, 1 dòng) — để trống nếu chưa có",
        },
        "bat_buoc": ["ten", "cau"],
    },
    "soat-kho": {
        "ten": "Soát kho cảnh",
        "mo_ta": "AI xem từng cảnh quay trong kho (ảnh lưới) và đánh dấu: có mặt người, chữ chèn, hàng khác, độ đẹp, vị trí nhãn chai. Cảnh lỗi nặng bị loại khi dựng.",
        "file": "soat-kho.md",
        "bien": {
            "ten": "Tên sản phẩm",
            "ids": "Danh sách id cảnh có trong tờ ảnh",
            "nhan": "Nhãn của chính sản phẩm (để phân biệt hàng khác)",
        },
        "bat_buoc": ["ten", "ids"],
    },
    "doc-nhan": {
        "ten": "Đọc nhãn sản phẩm",
        "mo_ta": "AI đọc chữ in trên nhãn/bao bì trong ảnh và gợi ý \"sự thật sản phẩm\". Chỉ là gợi ý — chủ hàng kiểm rồi mới lưu.",
        "file": "doc-nhan.md",
        "bien": {"ten": "Tên sản phẩm"},
        "bat_buoc": ["ten"],
    },
    "gom-bai-hoc": {
        "ten": "Gom bài học giám khảo",
        "mo_ta": "Khi sổ lỗi của sản phẩm dài quá, AI gom thành luật CHUNG (cho mọi sản phẩm) và bài học RIÊNG (của sản phẩm). Máy đọc 2 phần CHUNG:/RIENG: nên giữ nguyên 2 tiêu đề này.",
        "file": "gom-bai-hoc.md",
        "bien": {
            "luat_chung": "Sổ luật chung hiện có (hoặc \"(chưa có)\")",
            "loi_san_pham": "Các lỗi giám khảo đã ghi cho sản phẩm này",
        },
        "bat_buoc": ["luat_chung", "loi_san_pham"],
    },
    "hoc-canh": {
        "ten": "Học cảnh — nhờ Antigravity xem video kho",
        "mo_ta": "Lời nhắc gửi Antigravity/Gemini để xem từng video trong kho và ghi file mô tả cảnh (JSON). Phần \"Bối cảnh\" và \"Quy tắc\" lấy từ tài liệu Mô tả video bên dưới.",
        "file": "hoc-canh.md",
        "bien": {
            "so_video": "Số video trong lô",
            "boi_canh": "Đoạn \"Bối cảnh\" cắt từ tài liệu Mô tả video",
            "ds_video": "Danh sách video + file đầu ra từng video",
            "quy_tac": "Phần \"Quy tắc\" và khung JSON cắt từ tài liệu Mô tả video",
        },
        "bat_buoc": ["ds_video", "quy_tac"],
    },
    "lenh-gemini": {
        "ten": "Lệnh dán cho Gemini (kho video)",
        "mo_ta": "Câu lệnh để anh dán vào Gemini khi muốn nó tự xem cả thư mục kho video và ghi mô tả cảnh theo đúng mẫu hub đang đọc.",
        "file": "lenh-gemini.md",
        "bien": {
            "kho_video": "Thư mục kho video của sản phẩm",
            "duong_dan_mo_ta": "Đường dẫn file tài liệu Mô tả video (bản đang dùng)",
        },
        "bat_buoc": ["duong_dan_mo_ta"],
    },
    "luat-san-xuat": {
        "ten": "Tài liệu: Luật sản xuất",
        "mo_ta": "Luật viết lời của biên kịch (giọng, từ cấm, quà, câu chốt…). Phần từ dòng \"## Dựng\" trở xuống biên kịch không đọc. Tài liệu thường, không có chỗ điền {{...}}.",
        "file": "luat/LUAT-SAN-XUAT.md",
        "bien": {},
        "bat_buoc": [],
    },
    "so-tay-editor": {
        "ten": "Tài liệu: Sổ tay editor cao cấp",
        "mo_ta": "Sổ tay kinh nghiệm dựng video — đạo diễn và giám khảo đều đọc. Tài liệu thường, không có chỗ điền {{...}}.",
        "file": "luat/SO-TAY-EDITOR.md",
        "bien": {},
        "bat_buoc": [],
    },
    "mo-ta-gemini": {
        "ten": "Tài liệu: Mô tả video (Gemini/Antigravity)",
        "mo_ta": "Hướng dẫn + khung JSON cho AI mô tả từng cảnh trong kho video. Máy đọc đúng khung này nên đừng đổi tên trường JSON. Tài liệu thường, không có chỗ điền {{...}}.",
        "file": "luat/MO-TA-VIDEO-GEMINI.md",
        "bien": {},
        "bat_buoc": [],
    },
}


# ---------------------------------------------------------------- đường dẫn
def _tt(key):
    if key not in VAI:
        raise KeyError(f"Không có đề bài tên '{key}'")
    return VAI[key]


def _thu_muc_sua():
    return DATA / "prompt"


def duong_dan_goc(key):
    f = _tt(key)["file"]
    return CODE / f if f.startswith("luat/") else CODE / "prompt" / f


def duong_dan_sua(key):
    return _thu_muc_sua() / _tt(key)["file"]


def duong_dan_hieu_luc(key):
    """File đang được dùng thật (bản sửa nếu có, không thì mẫu gốc) — cho lệnh cần đưa ĐƯỜNG DẪN file cho AI ngoài."""
    p = duong_dan_sua(key)
    return p if p.is_file() else duong_dan_goc(key)


def _doc_file(p):
    return p.read_text(encoding="utf-8-sig")


# ---------------------------------------------------------------- đọc / ghi
def mac_dinh(key):
    return _doc_file(duong_dan_goc(key))


def doc(key):
    """→ (nội dung đang dùng, la_ban_sua)."""
    p = duong_dan_sua(key)
    if p.is_file():
        try:
            return _doc_file(p), True
        except Exception:
            pass                       # bản sửa hỏng/không đọc được → quay về mẫu gốc, không làm sập lô
    return mac_dinh(key), False


def _cu_dir():
    return _thu_muc_sua() / "_cu"


def _cat_ban_cu(key):
    """Chép bản sửa hiện tại sang _cu/ (nếu có), giữ GIU_BAN_CU bản mới nhất mỗi vai."""
    p = duong_dan_sua(key)
    if not p.is_file():
        return None
    d = _cu_dir(); d.mkdir(parents=True, exist_ok=True)
    t = datetime.datetime.now()
    dich = d / f"{key}-{t:%Y%m%d-%H%M%S}.md"
    k = 1
    while dich.exists():
        dich = d / f"{key}-{t:%Y%m%d-%H%M%S}-{k}.md"; k += 1
    shutil.copyfile(p, dich)
    for f in sorted(d.glob(f"{key}-*.md"), key=lambda x: x.name)[:-GIU_BAN_CU]:
        try:
            f.unlink()
        except OSError:
            pass
    return dich


def luu(key, text):
    """Lưu bản sửa (cất bản sửa trước vào _cu/). Giống hệt mẫu gốc → coi như khôi phục mặc định (không giữ bản sửa thừa)."""
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    if text == mac_dinh(key):
        khoi_phuc(key)
        return
    _cat_ban_cu(key)
    p = duong_dan_sua(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(p)


def khoi_phuc(key):
    """Xoá bản sửa (cất vào _cu/ trước) → dùng lại mẫu gốc."""
    p = duong_dan_sua(key)
    if p.is_file():
        _cat_ban_cu(key)
        p.unlink()


def ds_ban_cu(key):
    """[{id, luc, ky_tu, text}] mới nhất trước."""
    _tt(key)
    d = _cu_dir()
    out = []
    for f in sorted(d.glob(f"{key}-*.md"), key=lambda x: x.name, reverse=True) if d.is_dir() else []:
        m = re.fullmatch(re.escape(key) + r"-(\d{8})-(\d{6})(?:-\d+)?", f.stem)
        if not m:
            continue
        try:
            t = _doc_file(f)
        except Exception:
            continue
        luc = datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").isoformat(sep=" ")
        out.append({"id": f.stem, "luc": luc, "ky_tu": len(t), "text": t})
    return out


# ---------------------------------------------------------------- điền dữ liệu + kiểm
def thay(key, text, ctx):
    """Thay {{tên}} đã đăng ký bằng ctx[tên] (str). Tên lạ, hoặc tên đã đăng ký nhưng ctx không có → để nguyên. Một lượt → giá trị chứa {{x}} không bị thay lại."""
    biet = _tt(key)["bien"]
    return _RE_BIEN.sub(lambda m: str(ctx[m.group(1)]) if m.group(1) in biet and m.group(1) in ctx else m.group(0), text)


def dien(key, **ctx):
    return thay(key, doc(key)[0], ctx)


def kiem(key, text):
    """{thieu: [biến bắt buộc không có trong text], la: [{{x}} không thuộc vai này]}."""
    t = _tt(key)
    co = list(dict.fromkeys(_RE_BIEN.findall(text)))
    return {"thieu": [b for b in t["bat_buoc"] if b not in co], "la": [b for b in co if b not in t["bien"]]}


def doc_luat(ten_file):
    """Đọc 1 tài liệu luật/sổ tay (bản sửa nếu có). ten_file: 'LUAT-SAN-XUAT.md' …"""
    for k, v in VAI.items():
        if v["file"] == "luat/" + ten_file:
            return doc(k)[0]
    raise KeyError(ten_file)


# ---------------------------------------------------------------- xem thử với sản phẩm thật (KHÔNG gọi AI)
def _sidecar_moi(ma):
    """Hồ sơ video MỚI NHẤT của sản phẩm trong <DATA>/ra/*/<ma>_*.json."""
    from duong_dan import cfg
    try:
        ra = Path(cfg()["duong_dan"]["ra"])
    except Exception:
        ra = DATA / "ra"
    ds = glob_kem(ra, f"{ma}_*.json")
    return max(ds, key=lambda f: f.stat().st_mtime) if ds else None


def xem_thu(key, ma_sp, text=None):
    """Dựng đúng đề bài như lúc chạy thật với dữ liệu của sản phẩm `ma_sp` (text=None → bản đang dùng; có text → thử bản đang gõ).
    → {text, ky_tu, canh_bao[]}. Không gọi AI; không ghi file nào."""
    _tt(key)
    canh_bao = []
    if text is None:
        text = doc(key)[0]
    kq = kiem(key, text)
    for b in kq["thieu"]:
        canh_bao.append(f"Thiếu chỗ điền bắt buộc {{{{{b}}}}} — AI sẽ không nhận được dữ liệu này.")
    for b in kq["la"]:
        canh_bao.append(f"{{{{{b}}}}} không phải chỗ điền hợp lệ của vai này — sẽ gửi nguyên chữ đó cho AI.")
    ctx, ghi_chu = None, ""
    try:
        ctx, ghi_chu = _ctx_xem_thu(key, ma_sp)
    except _ThieuDuLieu as e:
        return {"text": "", "ky_tu": 0, "canh_bao": canh_bao + [str(e)], "thieu_du_lieu": True}
    out = thay(key, text, ctx)
    if ghi_chu:
        canh_bao.append(ghi_chu)
    return {"text": out, "ky_tu": len(out), "canh_bao": canh_bao}


class _ThieuDuLieu(Exception):
    pass


def _ctx_xem_thu(key, ma):
    import json, random
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", str(ma or "")):
        raise _ThieuDuLieu("Chưa chọn sản phẩm để xem thử.")
    d = DATA / "san-pham" / ma
    if not (d / "san-pham.json").is_file():
        raise _ThieuDuLieu(f"Không tìm thấy sản phẩm '{ma}'.")
    sp = json.loads((d / "san-pham.json").read_text(encoding="utf-8"))
    if key == "he-thong":
        return {"vai": "biên kịch"}, "Ví dụ với vai \"biên kịch\" — mỗi vai AI sẽ điền tên vai của nó."
    if key in ("luat-san-xuat", "so-tay-editor", "mo-ta-gemini"):
        return {}, ""
    if key == "bien-kich":
        import viet_loi
        return viet_loi.ctx_xem_thu(ma, sp), "Xem thử chọn 3 bản đầu tiên theo thứ tự mặc định (lúc chạy thật, máy xoay góc/dạng bài khác nhau)."
    if key == "doc-nhan":
        import doc_nhan
        return doc_nhan.ctx(sp, ma), ""
    if key == "soat-kho":
        import soat_kho
        shots = json.loads((d / "canh.json").read_text(encoding="utf-8")) if (d / "canh.json").is_file() else []
        ids = [s["id"] for s in shots[:40]] or [f"{i:04d}" for i in range(40)]
        return soat_kho.ctx(sp, ids), ("" if shots else "Sản phẩm chưa có kho cảnh — dùng id mẫu.")
    if key == "gom-bai-hoc":
        import ekip
        f, fc = DATA / "lich-su" / f"bai-hoc-{ma}.txt", DATA / "lich-su" / "bai-hoc.txt"
        dong = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.is_file() else []
        chung = [l for l in fc.read_text(encoding="utf-8").splitlines() if l.strip()] if fc.is_file() else []
        return ekip.ctx_gom(chung, dong), ("" if dong else "Sản phẩm này chưa có sổ lỗi giám khảo nên phần \"lỗi của sản phẩm\" đang trống.")
    if key == "hoc-canh":
        import hoc_canh
        viec = [{"rel": "ten-video-1.mp4", "dai": 12.5, "src": str(Path(sp.get("kho_video", "D:\\kho")) / "ten-video-1.mp4"),
                 "ra": str(Path(sp.get("kho_video", "D:\\kho")) / "_mo-ta" / "ten-video-1.mo-ta.json")},
                {"rel": "ten-video-2.mp4", "dai": 7.0, "src": str(Path(sp.get("kho_video", "D:\\kho")) / "ten-video-2.mp4"),
                 "ra": str(Path(sp.get("kho_video", "D:\\kho")) / "_mo-ta" / "ten-video-2.mo-ta.json")}]
        return hoc_canh.ctx_loi_nhac(viec), "Xem thử dùng 2 video mẫu."
    if key == "lenh-gemini":
        return {"kho_video": sp.get("kho_video", "<thư mục kho>"),
                "duong_dan_mo_ta": str(duong_dan_hieu_luc("mo-ta-gemini"))}, ""
    if key in ("dao-dien", "giam-khao"):
        side = _sidecar_moi(ma)
        if not side:
            raise _ThieuDuLieu("Sản phẩm này chưa có video nào được làm nên chưa có dữ liệu để xem thử đạo diễn/giám khảo. Hãy chạy sản xuất 1 video trước.")
        meta = json.loads(side.read_text(encoding="utf-8"))
        gf = Path(meta.get("giong_file") or "")
        canh_f = d / "canh.json"
        if not gf.is_file():
            raise _ThieuDuLieu(f"Video mới nhất của sản phẩm ({side.name}) đã bị dọn nên không còn file giọng đọc để xem thử. Hãy làm 1 video mới.")
        voice = json.loads(gf.read_text(encoding="utf-8"))
        gu = meta.get("dao_dien") or "tvc_cao_cap"
        import dao_dien
        if gu not in dao_dien.GU:
            gu = "tvc_cao_cap"
        if key == "giam-khao":
            from dung import sentence_times
            sents = sentence_times(voice["text"], voice["words"])
            edl = {"cong_thuc": meta.get("cong_thuc"), "gu": gu, "khoi": [], "ly_do": meta.get("y_tuong") or meta.get("ly_do")}
            return dao_dien.ctx_giam_khao(sp, sents, edl), f"Lấy từ video mới nhất: {side.name}. Bảng dựng chỉ có phần tóm tắt trong hồ sơ video."
        if not canh_f.is_file():
            raise _ThieuDuLieu("Sản phẩm chưa có kho cảnh (canh.json) — hãy bấm \"Chuẩn bị kho\" trước.")
        shots = json.loads(canh_f.read_text(encoding="utf-8"))
        for x in shots:
            x.setdefault("dep", [x["tu"], x.get("den", x["tu"] + x["dai"])]); x.setdefault("den", x["tu"] + x["dai"]); x.setdefault("mo_ta", ""); x.setdefault("the", [])
        from kho_chung import kho_them_cua, la_kho_chung
        from duong_dan import cfg
        ds_them = [] if la_kho_chung(sp) else kho_them_cua(ma, sp)
        chung = dao_dien.canh_them(ds_them)
        qua = dao_dien.canh_qua(ma, cfg().get("kho_qua"))
        c, _s, _t, _ids = dao_dien.ctx_dao_dien(ma, sp, voice, meta.get("kich_ban") or {}, shots, gu, random.Random(1), qua=qua, chung=chung)
        return c, f"Lấy từ video mới nhất: {side.name} (gu {gu}). Danh sách cảnh ứng viên là một lần chọn thử."
    raise _ThieuDuLieu("Vai này chưa hỗ trợ xem thử.")

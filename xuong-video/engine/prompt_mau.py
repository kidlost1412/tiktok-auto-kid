"""ĐỀ BÀI CHO AI (prompt) — MỘT bộ mẫu dùng chung cho mọi sản phẩm, ai cũng chỉnh được trong tab "Prompt AI".

- Mẫu gốc nằm trong repo:  xuong-video/prompt/<tên>.md   (3 tài liệu luật: xuong-video/luat/<tên>.md).
- Bản người dùng chỉnh nằm ở: <DATA>/prompt/<cùng tên>   → nếu có thì dùng bản này. Không có thì dùng BẢN GỐC ĐÃ GHIM <DATA>/prompt/_goc/<key>.md
  (= bản mặc định người dùng đang đứng trên, ghim lúc cài mới / lần đầu sau nâng cấp). KHÔNG dùng thẳng mẫu đi kèm app → cập nhật app không bao giờ tự đổi "gu".
  Mẫu đi kèm khác bản ghim → giao diện báo "Có bản cập nhật" (diff + ghi chú prompt/_ghi-chu-cap-nhat.json); người dùng chọn Áp dụng / Giữ bản của tôi.
- Phần máy bắt buộc cần (định dạng trả về, luật an toàn) nằm trong mã: HOP_DONG, tự gắn nếu đề bài thiếu.
- Chỗ cần dữ liệu viết {{ten_bien}} (2 ngoặc nhọn, tên ASCII). Máy điền dữ liệu thật của sản phẩm lúc chạy.
  Ngoặc nhọn đơn { } là chữ thường (vd. mẫu JSON trong đề bài).
- dien(key, **ctx): chỉ thay các {{tên}} đã đăng ký trong VAI[key]["bien"]; {{x}} lạ để nguyên (kiem() báo ra).
- Mỗi lần lưu, bản cũ được cất ở <DATA>/prompt/_cu/<key>-YYYYmmdd-HHMMSS.md (giữ 20 bản gần nhất mỗi vai)."""
import datetime, difflib, hashlib, json, os, re, shutil
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


# ---------------------------------------------------------------- HỢP ĐỒNG CHỨC NĂNG (nằm trong mã, KHÔNG thuộc "gu")
# Phần máy bắt buộc cần (định dạng trả về, luật an toàn không dùng terminal...) được máy TỰ GẮN vào cuối đề bài nếu bản đang dùng
# (bản người dùng chỉnh, hoặc bản gốc cũ đã ghim) chưa có. Mỗi mục: "khi_thieu" = đoạn chữ dấu hiệu; có rồi thì không gắn nữa.
# Nhờ vậy người giữ đề bài cũ cũng không làm hỏng app. Sửa phần này = sửa mã (không phải sửa gu).
HOP_DONG = {
    "hoc-canh": [
        {"khi_thieu": "KHÔNG chạy lệnh terminal",
         "noi_dung": "AN TOÀN (bắt buộc): CHỈ dùng công cụ ĐỌC/XEM file (các video đã cho) và công cụ GHI file (các file đầu ra liệt kê trong danh sách). "
                     "TUYỆT ĐỐI KHÔNG chạy lệnh terminal/PowerShell/script, không mở trình duyệt, không tìm kiếm web, không cài gì, không tạo kế hoạch/tài liệu/artifact/ghi chú, "
                     "không đọc/ghi/sửa/xoá file nào khác (kể cả tạo thư mục), không hỏi lại — cứ làm thẳng, không đợi ai duyệt. Một video lỗi thì bỏ qua (không ghi file) và làm tiếp video sau."},
        {"khi_thieu": "chỉ JSON thuần",
         "noi_dung": "ĐỊNH DẠNG FILE (bắt buộc): mỗi file đầu ra chỉ chứa JSON thuần (bắt đầu bằng { kết thúc bằng }), UTF-8, không ```, không giải thích. "
                     "Mọi tu_s/den_s là SỐ GIÂY (số thực), diem là SỐ NGUYÊN 0–5. Giữ ĐÚNG tên trường theo khung."},
    ],
    "gom-bai-hoc": [
        {"khi_thieu": "RIENG:",
         "noi_dung": "ĐỊNH DẠNG TRẢ VỀ (bắt buộc): đúng 2 phần, mỗi phần mở bằng dòng tiêu đề 'CHUNG:' và 'RIENG:' (viết đúng như vậy); dưới mỗi tiêu đề là các dòng bắt đầu bằng '- '. "
                     "CHUNG: tối đa 15 dòng, KHÔNG nêu tên sản phẩm. RIENG: tối đa 10 dòng. Không chữ nào khác."},
    ],
    "giam-khao": [
        {"khi_thieu": '"diem"',
         "noi_dung": 'ĐỊNH DẠNG TRẢ VỀ (bắt buộc): DUY NHẤT JSON {"diem": 1-10, "dat": true|false (đạt khi ≥ 7 và không lỗi nặng), '
                     '"loi": ["tối đa 3 lỗi nặng nhất, mỗi lỗi ≤ 12 từ, có giây"], "sua": "≤ 35 từ chỉ dẫn đổi cảnh/bố cục; rỗng nếu đạt"}'},
    ],
    "doc-nhan": [
        {"khi_thieu": '"su_that"',
         "noi_dung": 'ĐỊNH DẠNG TRẢ VỀ (bắt buộc): DUY NHẤT JSON {"su_that": ["mỗi dòng 1 ý ngắn, ghi rõ đọc ở đâu"], "chua_ro": ["điều thấy một phần nhưng chưa đọc chắc"]}'},
    ],
    "soat-kho": [
        {"khi_thieu": '"chu_muc"',
         "noi_dung": 'ĐỊNH DẠNG TRẢ VỀ (bắt buộc): MỘT mảng JSON, mỗi phần tử một ô: {"id":"<id>","mat":0|1|2,"chu_muc":0|1|2,"hang_khac":true|false,"dep":1-5,'
                     '"nhan":[x0,y0,x1,y1] hoặc null,"ghi":"<≤12 từ mô tả hình>"}. mat: 0 không thấy mặt người, 1 người nhỏ/xa, 2 mặt rõ. '
                     'chu_muc: chữ chèn sau khi quay (0 không có, 1 ít, 2 nhiều/che hình; không tính chữ in trên nhãn chai). '
                     'nhan: khung bao chai/gói sản phẩm, toạ độ tỉ lệ 0–1 theo ô. Ids trong tờ: {{ids}}'},
    ],
    "bien-kich": [
        {"khi_thieu": '"y_canh"',
         "noi_dung": 'ĐỊNH DẠNG MỖI PHẦN TỬ (bắt buộc): {"goc": "<mã góc>", "giong": "{{giong}}", "text": "<lời đọc có tag [..], mỗi câu kết thúc bằng . ! hoặc ?>", '
                     '"dong": ["<dòng phụ đề>", ...] (chia lời đọc bỏ tag thành cụm ý 5–10 từ, ghép lại đúng y lời đọc), '
                     '"y_canh": ["<câu 1 nên thấy hình gì, ≤12 từ>", ... đúng bằng số câu], "nhan_tu": ["<2–4 từ cần phóng to>"], '
                     '"caption": ["3 caption khác nhau, mỗi cái ≤ 90 ký tự"], "hashtag": ["đúng 3 hashtag tiếng Việt không dấu"]}. Trả về một mảng JSON các phần tử này.'},
    ],
    "dao-dien": [
        {"khi_thieu": '"doan"',
         "noi_dung": 'ĐỊNH DẠNG TRẢ VỀ (bắt buộc): DUY NHẤT 1 đối tượng JSON {"cong_thuc":"..","phu_de":"..","mau_nhan":"..","chuyen_canh":"..","chuyen_dong":"..","mau":"..","sfx":"..","nhac":"..",'
                     '"nhan_tu":["2–4 từ cần phóng to"],"khoi":[{"loai":"<khối>","cau":0,"du_lieu":{..}}, ...],'
                     '"doan":[{"cau":0,"canh":[{"id":"<id>","bo_cuc":"<bố cục>","phu":["<id ô phụ nếu cần>"]}]}, ... đủ {{n}} câu],"ly_do":"≤12 từ"}'},
    ],
}


# ---------------------------------------------------------------- đường dẫn
def _tt(key):
    if key not in VAI:
        raise KeyError(f"Không có đề bài tên '{key}'")
    return VAI[key]


def _chuan(t):
    """Chuẩn hoá để so sánh/băm: xuống dòng LF, bỏ BOM."""
    return str(t).replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")


def bam(t):
    return hashlib.sha256(_chuan(t).encode("utf-8")).hexdigest()[:16]


def _thu_muc_sua():
    return DATA / "prompt"


def duong_dan_goc(key):
    f = _tt(key)["file"]
    return CODE / f if f.startswith("luat/") else CODE / "prompt" / f


def duong_dan_sua(key):
    return _thu_muc_sua() / _tt(key)["file"]


def _goc_dir():
    return _thu_muc_sua() / "_goc"


def duong_dan_ghim(key):
    _tt(key)
    return _goc_dir() / f"{key}.md"


def duong_dan_hieu_luc(key):
    """File đang được dùng thật (bản sửa nếu có, không thì bản gốc ĐÃ GHIM) — cho lệnh cần đưa ĐƯỜNG DẪN file cho AI ngoài."""
    p = duong_dan_sua(key)
    if p.is_file():
        return p
    ghim(key)
    g = duong_dan_ghim(key)
    return g if g.is_file() else duong_dan_goc(key)


def _doc_file(p):
    return p.read_text(encoding="utf-8-sig")


def _ghi_nguyen_tu(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(p)


# ---------------------------------------------------------------- bản gốc đã ghim (để bản cập nhật KHÔNG tự đổi gu)
def phien_ban_app():
    try:
        return (CODE.parent / "VERSION").read_text(encoding="utf-8").strip() or "0"
    except Exception:
        return "0"


def _vt(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)


def mac_dinh(key):
    """Bản gốc đang đi kèm app (bản MỚI NHẤT của nhà phát triển)."""
    return _chuan(_doc_file(duong_dan_goc(key)))


def ghim(key, ep=False):
    """Bảo đảm có bản gốc đã ghim = phiên bản mặc định người dùng đang dùng. Chưa có (cài mới, hoặc lần đầu sau khi nâng cấp lên bản có tính năng này)
    → ghim bản đi kèm lúc này. ep=True → ghim lại bằng bản đi kèm hiện hành (chỉ gọi khi người dùng chủ động chấp nhận)."""
    p = duong_dan_ghim(key); m = p.with_suffix(".json")
    if not ep and p.is_file():
        try:
            _doc_file(p)
            if not m.is_file():
                _ghi_nguyen_tu(m, json.dumps({"hash": bam(_doc_file(p)), "ver": "?", "luc": datetime.datetime.now().isoformat(timespec="seconds")}))
            return
        except Exception:
            pass
    text = mac_dinh(key)
    if ep and p.is_file():
        try:
            if bam(_doc_file(p)) == bam(text):
                return
        except Exception:
            pass
    _ghi_nguyen_tu(p, text)
    _ghi_nguyen_tu(m, json.dumps({"hash": bam(text), "ver": phien_ban_app(), "luc": datetime.datetime.now().isoformat(timespec="seconds")}))


def ghim_tat_ca():
    for k in VAI:
        try:
            ghim(k)
        except Exception:
            pass


def goc(key):
    """Bản gốc người dùng đang đứng trên (đã ghim)."""
    ghim(key)
    try:
        return _chuan(_doc_file(duong_dan_ghim(key)))
    except Exception:
        return mac_dinh(key)


def ver_ghim(key):
    try:
        return json.loads(duong_dan_ghim(key).with_suffix(".json").read_text(encoding="utf-8")).get("ver", "?")
    except Exception:
        return "?"


# ---------------------------------------------------------------- đọc / ghi
def doc(key):
    """→ (nội dung đang dùng, la_ban_sua). Hiệu lực = bản người dùng sửa nếu có, không thì bản gốc ĐÃ GHIM (không phải bản mới đi kèm app)."""
    p = duong_dan_sua(key)
    if p.is_file():
        try:
            return _chuan(_doc_file(p)), True
        except Exception:
            pass                       # bản sửa hỏng/không đọc được → quay về bản gốc đã ghim, không làm sập lô
    return goc(key), False


def _cu_dir():
    return _thu_muc_sua() / "_cu"


def _cat_text_cu(key, text):
    d = _cu_dir(); d.mkdir(parents=True, exist_ok=True)
    t = datetime.datetime.now()
    dich = d / f"{key}-{t:%Y%m%d-%H%M%S}.md"
    k = 1
    while dich.exists():
        dich = d / f"{key}-{t:%Y%m%d-%H%M%S}-{k}.md"; k += 1
    _ghi_nguyen_tu(dich, _chuan(text))
    for f in sorted(d.glob(f"{key}-*.md"), key=lambda x: x.name)[:-GIU_BAN_CU]:
        try:
            f.unlink()
        except OSError:
            pass
    return dich


def _cat_ban_cu(key):
    """Chép bản sửa hiện tại sang _cu/ (nếu có), giữ GIU_BAN_CU bản mới nhất mỗi vai."""
    p = duong_dan_sua(key)
    if not p.is_file():
        return None
    return _cat_text_cu(key, _doc_file(p))


def _bo_ban_sua(key):
    p = duong_dan_sua(key)
    if p.is_file():
        _cat_ban_cu(key)
        p.unlink()


def luu(key, text):
    """Lưu bản sửa (cất bản sửa trước vào _cu/).
    Giống bản gốc mới → chấp nhận bản mới (ghim lại). Giống bản gốc đã ghim → không cần giữ bản sửa riêng."""
    text = _chuan(text)
    if text == mac_dinh(key):
        khoi_phuc(key)
        return
    if text == goc(key):
        _bo_ban_sua(key)
        return
    _cat_ban_cu(key)
    _ghi_nguyen_tu(duong_dan_sua(key), text)


def khoi_phuc(key):
    """Về bản gốc MỚI NHẤT đi kèm app (người dùng chủ động bấm). Bản đang dùng cất vào _cu/; ghim lại bản gốc."""
    if not duong_dan_sua(key).is_file():
        ghim(key); old = goc(key)
        if bam(old) != bam(mac_dinh(key)):
            _cat_text_cu(key, old)
    ghim(key, ep=True)
    _bo_ban_sua(key)


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


# ---------------------------------------------------------------- "Có bản cập nhật": bản đi kèm app khác bản đã ghim
def co_ban_moi(key):
    return bam(goc(key)) != bam(mac_dinh(key))


def ds_ban_moi():
    return [k for k in VAI if co_ban_moi(k)]


def _ghi_chu_file():
    return CODE / "prompt" / "_ghi-chu-cap-nhat.json"


def doc_ghi_chu():
    try:
        return json.loads(_ghi_chu_file().read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def ghi_chu(key, tu_ver=None, den_ver=None):
    """[{ver, text}] các ghi chú 'vì sao đổi' của nhà phát triển cho bản đi kèm mới hơn bản đã ghim (cũ → mới)."""
    tu = ver_ghim(key) if tu_ver is None else tu_ver
    den = phien_ban_app() if den_ver is None else den_ver
    out = []
    for v, t in (doc_ghi_chu().get(key) or {}).items():
        if (tu == "?" or _vt(v) > _vt(tu)) and _vt(v) <= _vt(den):
            out.append({"ver": v, "text": str(t)})
    return sorted(out, key=lambda x: _vt(x["ver"]))


def diff_dong(a, b, ngu_canh=3):
    """So hai bản theo dòng → [[kiểu, chữ]]; kiểu '=' giữ nguyên, '-' bị bỏ, '+' thêm vào, '…' đoạn giống nhau đã gấp (chữ = số dòng)."""
    al, bl = _chuan(a).split("\n"), _chuan(b).split("\n")
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, al, bl, autojunk=False).get_opcodes():
        if tag == "equal":
            ops += [["=", x] for x in al[i1:i2]]
        else:
            ops += [["-", x] for x in al[i1:i2]] + [["+", x] for x in bl[j1:j2]]
    out, i, n = [], 0, len(ops)
    while i < n:
        if ops[i][0] != "=":
            out.append(ops[i]); i += 1; continue
        j = i
        while j < n and ops[j][0] == "=":
            j += 1
        dau, cuoi = (0 if i == 0 else ngu_canh), (0 if j == n else ngu_canh)
        if j - i <= dau + cuoi + 1:
            out += ops[i:j]
        else:
            out += ops[i:i + dau] + [["…", str(j - i - dau - cuoi)]] + ops[j - cuoi:j]
        i = j
    return out


def chi_tiet_cap_nhat(key):
    g, m = goc(key), mac_dinh(key)
    sua = duong_dan_sua(key).is_file()
    mine = doc(key)[0] if sua else None
    return {"co": bam(g) != bam(m), "ver_goc": ver_ghim(key), "ver_moi": phien_ban_app(), "ghi_chu": ghi_chu(key),
            "diff_moi": diff_dong(g, m), "co_ban_sua": sua, "ban_sua": mine,
            "diff_ban_sua": diff_dong(g, mine) if sua else [], "ban_sua_giong_moi": bool(sua and bam(mine) == bam(m)),
            "ban_moi": m}


def ap_dung_ban_moi(key):
    """Người dùng chọn 'Áp dụng bản mới': dùng bản gốc mới; bản đang dùng (bản sửa, hoặc bản gốc cũ) được cất vào _cu/ trước."""
    _tt(key)
    if not duong_dan_sua(key).is_file():
        _cat_text_cu(key, goc(key))
    ghim(key, ep=True)
    _bo_ban_sua(key)


def giu_ban_cua_toi(key):
    """Người dùng chọn 'Giữ bản của tôi': chữ đang dùng KHÔNG đổi; ghim bản gốc mới để thôi nhắc."""
    _tt(key)
    if not duong_dan_sua(key).is_file():
        _ghi_nguyen_tu(duong_dan_sua(key), goc(key))        # đang dùng bản gốc cũ → giữ nguyên nó thành bản sửa của người dùng
    ghim(key, ep=True)


# ---------------------------------------------------------------- điền dữ liệu + kiểm
def thay(key, text, ctx):
    """Thay {{tên}} đã đăng ký bằng ctx[tên] (str). Tên lạ, hoặc tên đã đăng ký nhưng ctx không có → để nguyên. Một lượt → giá trị chứa {{x}} không bị thay lại."""
    biet = _tt(key)["bien"]
    return _RE_BIEN.sub(lambda m: str(ctx[m.group(1)]) if m.group(1) in biet and m.group(1) in ctx else m.group(0), text)


def dung(key, text, ctx):
    """Dựng đề bài cuối: gắn phần HỢP ĐỒNG chức năng còn thiếu, điền {{...}}, và gắn dữ liệu bắt buộc mà bản cũ không có chỗ điền."""
    t = _tt(key)
    text = _chuan(text)
    for h in HOP_DONG.get(key, []):
        if h["khi_thieu"] not in text:
            text = text.rstrip("\n") + "\n\n" + h["noi_dung"]
    co = set(_RE_BIEN.findall(text))
    them = [b for b in t["bat_buoc"] if b not in co and b in ctx]
    out = thay(key, text, ctx)
    for b in them:
        out += f"\n\n[{t['bien'].get(b, b)}]\n{ctx[b]}"
    return out


def dien(key, **ctx):
    return dung(key, doc(key)[0], ctx)


def kiem(key, text):
    """{thieu: [biến bắt buộc không có trong text], la: [{{x}} không thuộc vai này]}."""
    t = _tt(key)
    co = list(dict.fromkeys(_RE_BIEN.findall(text)))
    return {"thieu": [b for b in t["bat_buoc"] if b not in co], "la": [b for b in co if b not in t["bien"]]}


def doc_luat(ten_file):
    """Đọc 1 tài liệu luật/sổ tay (bản sửa nếu có, không thì bản đã ghim). ten_file: 'LUAT-SAN-XUAT.md' …"""
    for k, v in VAI.items():
        if v["file"] == "luat/" + ten_file:
            return doc(k)[0]
    raise KeyError(ten_file)


def manifest_f():
    return CODE / "prompt" / "_ban-phat-hanh.json"


def ghi_manifest():
    """Nhà phát triển chạy sau khi sửa gu mặc định: ghi lại băm các bản gốc. Bản nào đổi mà chưa có ghi chú cho VERSION hiện tại → từ chối."""
    cu = {}
    try:
        cu = json.loads(manifest_f().read_text(encoding="utf-8"))
    except Exception:
        pass
    v = phien_ban_app(); moi = {}; thieu = []
    for k in VAI:
        h = bam(mac_dinh(k))
        if cu.get(k, {}).get("hash") == h:
            moi[k] = cu[k]
        else:
            moi[k] = {"hash": h, "ver": v}
            if k in cu and not (doc_ghi_chu().get(k) or {}).get(v):
                thieu.append(k)
    if thieu:
        raise SystemExit("Đã đổi gu mặc định nhưng thiếu ghi chú cho bản " + v + " trong prompt/_ghi-chu-cap-nhat.json: " + ", ".join(thieu))
    manifest_f().write_text(json.dumps(moi, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


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
        canh_bao.append(f"Thiếu chỗ điền bắt buộc {{{{{b}}}}} — máy sẽ tự gắn dữ liệu này vào cuối đề bài, nhưng nên thêm lại cho đúng chỗ.")
    for b in kq["la"]:
        canh_bao.append(f"{{{{{b}}}}} không phải chỗ điền hợp lệ của vai này — sẽ gửi nguyên chữ đó cho AI.")
    ctx, ghi_chu = None, ""
    try:
        ctx, ghi_chu = _ctx_xem_thu(key, ma_sp)
    except _ThieuDuLieu as e:
        return {"text": "", "ky_tu": 0, "canh_bao": canh_bao + [str(e)], "thieu_du_lieu": True}
    out = dung(key, text, ctx)
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


if __name__ == "__main__":
    if _s0.argv[1:2] == ["ghi-manifest"]:
        ghi_manifest(); print("Đã ghi", manifest_f())
    else:
        print("Dùng: python prompt_mau.py ghi-manifest   (sau khi sửa gu mặc định + thêm ghi chú)")

=== SỔ TAY EDITOR CAO CẤP (bắt buộc) ===
{{so_tay}}

=== GU CỦA BẠN ===
{{gu}}

{{so_gu}}=== BÀI HỌC TỪ GIÁM KHẢO (lỗi các bản trước — TRÁNH lặp lại) ===
{{bai_hoc}}
- Khối chữ/phụ đề không được che chữ trên nhãn chai: câu có khối chữ giữa bài nên dùng cảnh vườn/rễ/phun, hoặc bố cục khung_nho.
- Lời nói tới thứ gì (rễ, nhãn thành phần, cây con, phun…) thì hình PHẢI thấy đúng thứ đó.

=== SẢN PHẨM ===
{{sp}}

=== LỜI ĐỌC (đã có giọng, mốc thời gian từng câu, đơn vị giây) ===
{{cau}}
Tổng thời lượng video: {{total}} s. Chữ nhấn do biên kịch đề xuất: {{nhan}}

=== CẢNH ỨNG VIÊN ===
Xem tờ ảnh (số vàng = id). Danh sách: id | vai trò | mô tả | dài (s).
id bắt đầu "Q-" = QUÀ TẶNG THẬT (dùng ở câu nhắc quà); id bắt đầu "V-" = KHO PHỤ (b-roll, chỉ làm cảnh phụ/chuyển ý, không quá ~30% số cảnh).
{{ds}}
Gợi ý theo câu (không bắt buộc): {{goi_y}}{{so_lieu_tiktok}}

=== VIỆC CẦN LÀM ===
Lên BẢNG DỰNG cho video này theo gu của bạn. Chọn cảnh NHÌN ĐÚNG ý từng câu (đọc tới đâu, hình tới đó), mở đầu phải giật mắt,
câu chốt phải có cảnh chai sản phẩm rõ nhãn. Không dùng 1 cảnh 2 lần. Mỗi câu 1–2 cảnh; mỗi cảnh ≥ 1,8 s (thường 2–3,5 s) — Kid: không chuyển cảnh quá nhanh, để người xem kịp nhìn.
Chống reup: không để cảnh nguyên khung toàn màn quá 2,8 s — đổi bố cục.
ĐA DẠNG BỐ CỤC (bắt buộc): ít nhất 1/3 số đoạn dùng khung/ô/chia (khung_mo, khung_nho, pip_troi, pip_giua, chia_doi, chia_ngang, luoi_4);
mỗi video có ≥ 1 lần chia_doi/chia_ngang/luoi_4 (ô phụ lấy cảnh khác: người dùng sản phẩm, vườn, rễ…) và ≥ 1 ô trời (pip_troi/pip_giua)
trên cảnh vườn có trời. Cảnh NGƯỜI NÓI (AFF dùng sản phẩm) rất nên dùng làm ô phụ hoặc trong khung — tăng chân thật.

BỐ CỤC: {{bo_cuc}}
CÔNG THỨC DỰNG (chọn 1): {{ct}}
{{data_spec}}
MENU: phu_de={{phu_de}}; mau_nhan={{mau_nhan}}; chuyen_canh={{chuyen_canh}}; chuyen_dong={{chuyen_dong}}; mau={{mau}}; sfx={{sfx}}; nhac={{nhac}}

Trả về DUY NHẤT 1 đối tượng JSON:
{"cong_thuc":"..","phu_de":"..","mau_nhan":"..","chuyen_canh":"..","chuyen_dong":"..","mau":"..","sfx":"..","nhac":"..",
 "nhan_tu":["2–4 từ cần phóng to"],
 "khoi":[{"loai":"<khối mở của công thức>","cau":0,"du_lieu":{..}}, {"loai":"<0–2 khối giữa>","cau":<k>,"du_lieu":{..}}, {"loai":"<khối chốt>","cau":{{cuoi}},"du_lieu":{..}}],
 "doan":[{"cau":0,"canh":[{"id":"<id>","bo_cuc":"<bố cục>","phu":["<id ô phụ nếu bố cục cần>"]}]}, ... đủ {{n}} câu],
 "ly_do":"≤12 từ: ý tưởng dựng"}{{gop_y_giam_khao}}
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
MỘT Ý DỰNG CHỦ ĐẠO cho cả video (ghi vào ly_do): chọn đúng một cách kể bằng hình hợp với lời — vd. đi từ gần ra xa, đối chiếu hai nửa, theo một bàn tay làm việc,
dồn nhịp về chốt, mở bằng kết quả rồi quay lại — và để mọi lựa chọn cảnh, bố cục, chữ phục vụ ý đó. Hai video cùng lời phải có ý dựng KHÁC nhau.
NHỊP CỠ CẢNH: đổi cỡ cảnh giữa hai đoạn liền nhau (toàn → trung → cận hoặc ngược lại); không đặt hai cảnh cận na ná cạnh nhau.
CẢNH TOÀN MÀN LÀ CHÍNH (máy tự phóng, cúp, đổi tốc độ nhẹ để chống trùng): khung/ô/chia chỉ dùng khi có lý do — cần chỗ cho chữ, đối chiếu hai thứ,
hoặc đặt cảnh NGƯỜI NÓI (bắt buộc trong khung/ô). Không quá 1/3 số đoạn dùng khung/ô/chia; không dùng cùng một bố cục ba đoạn liền.
KHOẢNG THỞ: mỗi lúc chỉ một điểm nhấn. Tối đa một khối chữ giữa bài (0–1 khối, không phải lúc nào cũng cần); để ít nhất một đoạn hình sạch,
không khối chữ, cho người xem nhìn. Chữ mở ≤ 6 từ và KHÔNG lặp nguyên câu mở của lời đọc — nói điều lời chưa nói hết.
Cột "nói:" trong danh sách cảnh là lời người trong clip lúc quay — chỉ để hiểu cảnh đó nói về chuyện gì, không phải lời đọc.

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
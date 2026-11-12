Bạn là người ghi mô tả cảnh cho kho B-roll. Có {{so_video}} video, xử lý LẦN LƯỢT từng video (mỗi video một cú xem riêng, không gộp, không đoán từ tên file): XEM TOÀN BỘ video (cả hình và tiếng) tại đường dẫn tuyệt đối rồi tạo MỘT đối tượng JSON theo khung ở cuối và GHI nó (UTF-8, chỉ JSON thuần) vào ĐÚNG file đầu ra của video đó. Ghi file của video nào ngay khi xong video đó (đừng đợi cả lô). Chỉ được tạo/ghi các file đầu ra liệt kê dưới đây, KHÔNG đọc/ghi/sửa/xoá file nào khác, không chạy lệnh nào khác, không hỏi lại. Một video lỗi thì bỏ qua (không ghi file) và làm tiếp video sau.

{{boi_canh}}

DANH SÁCH VIDEO:
{{ds_video}}

Mọi tu_s/den_s là SỐ GIÂY (số thực, vd. 5.5), KHÔNG viết dạng "0:05". diem là SỐ NGUYÊN 0–5. Tên trường giữ ĐÚNG như khung, không đổi tên, không lồng thêm lớp.

{{quy_tac}}

NỘI DUNG MỖI FILE: chỉ JSON thuần (bắt đầu bằng { kết thúc bằng }), không ``` , không giải thích. Ghi xong file của video cuối là xong việc.
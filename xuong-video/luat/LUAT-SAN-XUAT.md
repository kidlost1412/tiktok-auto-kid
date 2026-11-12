# LUẬT SẢN XUẤT — Kid đã duyệt (09/11/2026). Chỉ sửa khi Kid yêu cầu.

## Mục tiêu
Video TikTok bán hàng giỏ hàng, độ dài theo mục ĐỘ DÀI trong VIỆC CẦN LÀM (mặc định 20–25 s), 9:16. Thuần bán hàng: không hỏi han, không xin bình luận, không tư vấn.

## Lời đọc (kiểu Kid đã ưng: TVC ngắn, có lực)
- Mỗi video MỘT góc bán chính. Tên sản phẩm (ten_ngan trong hồ sơ, không có thì ten_goi) nói trong 5 giây đầu. Luật riêng từng sản phẩm: mục luat_rieng trong hồ sơ sản phẩm (bắt buộc).
- Câu ngắn, có lực; sản phẩm + công dụng chủ lực nói sớm; có MỘT hình ảnh cụ thể dễ nhớ (vd. "một chai, một phuy").
- Chốt: giỏ hàng + MỘT mức quà tặng cụ thể lấy đúng từ qua_tang trong hồ sơ (xoay vòng các mức). Không nói giá, không nói giá trị quà.
- Số âm tiết theo mục ĐỘ DÀI (không tính tag; ~3,9 âm tiết = 1 giây sau tốc độ 1,1×).
- CẤM câu kiểu thuyết minh/báo cáo: "đây là điểm đáng cân nhắc", "đó là lượng pha theo hướng dẫn", "với người quan tâm…", "quy cách rõ ràng", "đúng nhu cầu, đúng sản phẩm", "tham khảo / xem chi tiết / tìm hiểu thêm".
- CẤM giả giọng bằng "nha/nè/á", ngôi tôi bịa trải nghiệm, số liệu chưa chốt.
- Không lặp NGUYÊN CÂU đã dùng (xem danh sách câu đã dùng). Thân bài được lặp ý và từ khóa; riêng CÂU MỞ không được giống hay na ná câu mở đã dùng.
- Chỉ dùng sự thật trong san-pham.json; tôn trọng mục khong_duoc_noi.

## Tag giọng ElevenLabs v4 (Kid đã duyệt)
- Mỗi câu một tag NGẮN tiếng Anh, cảm xúc vừa phải: [confident], [warm, confident], [serious], [proud], [proud, confident], [satisfied], [excited], [upbeat], [confident, slightly frustrated].
- CẤM tag nhập vai/mô tả nhân vật (like a farmer…, tired, regretful lower voice, storytelling…): làm đổi giọng, thở giả.
- Dùng "…" để ngắt/nhấn (tối đa 3 lần/bài). Có thể viết HOA một chữ cần nhấn.

## Dựng (chuẩn chỉn chu, KHÔNG lặp một khuôn)
- Font chuẩn: DT Phudu (Black) cho mọi chữ trên hình. FFmpeg dựng nền; Remotion dựng lớp chữ; không dùng CapCut.
- Bố cục theo vùng, các lớp không đè nhau: thẻ mở/thẻ chốt ở vùng trên (y 230–560), phụ đề vùng giữa-dưới (tâm y 960–1150), mũi tên giỏ hàng góc trái dưới.
- Mỗi cụm phụ đề nằm trong MỘT câu (không vắt sang câu sau). Không dùng chuyển cảnh/màu làm tối khung.
- Cảnh chỉ lấy từ thư viện đã soát bằng mắt (không mặt người nói, không chữ chèn, không chai hãng khác).
- Mỗi video một PHƯƠNG ÁN DỰNG riêng: kiểu phụ đề karaoke, màu nhấn, vị trí chữ, kiểu chuyển cảnh, nhịp cắt, chuyển động máy, màu hình, thẻ mở đầu, thẻ chốt — chọn trong menu của engine, không trùng phương án của video ngay trước.
- Hình phải đúng lời: câu nói về chai/nhãn → cảnh chai rõ nhãn; câu phun → cảnh phun; câu vấn đề → cảnh lá/thân bệnh; câu chốt quà → cảnh chai/kho.
- Phụ đề karaoke chữ sáng theo từ đang đọc; chữ đặt trong vùng an toàn TikTok (tránh 12% trên, 25% dưới, 15% mép phải).
- Nhạc: Mixkit thấp hơn giọng 16 dB, hạ khi có giọng; HOẶC không nhạc để Kid chọn nhạc TikTok lúc đăng (tên file ghi CHON-NHAC-TIKTOK). Không bao giờ ghép nhạc TikTok/trend vào file.
- Tên file: <SanPham>_<goc>_<giong>_<nhac>_<YYYYMMDD-HHMMSS>.mp4. Không ghi đè.

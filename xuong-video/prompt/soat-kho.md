Xem tờ ảnh: mỗi ô là 1 cảnh quay (số vàng góc trên trái = id). Các cảnh sẽ được ghép làm hình nền cho video bán sản phẩm {{ten}}
có giọng đọc thuyết minh (không dùng tiếng gốc). Đánh giá TỪNG ô, trả về MỘT mảng JSON, mỗi phần tử:
{"id":"<id>","mat":0|1|2,"chu_muc":0|1|2,"hang_khac":true|false,"dep":1-5,"nhan":[x0,y0,x1,y1] hoặc null,"ghi":"<≤12 từ mô tả hình>"}
- mat: 0 = không thấy mặt người (chỉ tay/cây/chai); 1 = có người nhưng nhỏ/xa/không nhìn máy; 2 = mặt người rõ, nhìn máy hoặc đang nói (lời đọc sẽ lệch khẩu hình).
- chu_muc: chữ chèn sau khi quay (bình luận TikTok, tiêu đề, phụ đề, logo kênh, mũi tên) — KHÔNG tính chữ in trên nhãn chai.
  0 = không có; 1 = ít/nhỏ hoặc nằm sát mép (vẫn dùng được); 2 = nhiều/to, che giữa hình (không dùng được).
- hang_khac: thấy chai/gói sản phẩm KHÁC {{ten}} (nhãn khác) là chủ thể.
- nhan: khung chữ nhật bao CHAI/GÓI SẢN PHẨM (gồm nhãn) trong ô đó, toạ độ tỉ lệ 0–1 theo ô (x0,y0 góc trên trái; x1,y1 góc dưới phải),
  ước lượng đủ rộng để chữ chèn sau này không đè lên; không thấy sản phẩm → null.
- dep: 5 = nét, sáng, bố cục đẹp, đúng chủ đề nông nghiệp; 1 = mờ, tối, rung, xấu.
Lưu ý nhãn của chính sản phẩm: {{nhan}}
Ids trong tờ: {{ids}}
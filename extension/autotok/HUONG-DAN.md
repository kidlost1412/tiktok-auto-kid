# TikTok Auto Kid: hướng dẫn cài tiện ích Chrome

Tiện ích này đăng bài TikTok thay app TikTok Auto Kid, từ chính profile Chrome đang đăng nhập TikTok của bạn.

## Cài đặt (dạng unpacked)

1. Mở `chrome://extensions`.
2. Bật **Developer mode** (góc trên bên phải).
3. Bấm **Load unpacked**, chọn thư mục `extension\autotok` trong thư mục cài TikTok Auto Kid (ví dụ `D:\TikTokAutoKid\extension\autotok`).
4. Ghim biểu tượng TikTok Auto Kid lên thanh công cụ cho dễ mở.

## Ghép nối với TikTok Auto Kid

1. Trong TikTok Auto Kid vào **Cài đặt → Kết nối Chrome**, bấm tạo mã. Mã gồm 6 số, có hiệu lực 5 phút.
2. Bấm biểu tượng TikTok Auto Kid, nhập mã 6 số. Địa chỉ máy chủ là `http://localhost:8010` (nếu ô đang khác thì sửa ở ô Địa chỉ máy chủ rồi bấm Lưu). Từ bản 1.2.0 tiện ích được phép nói chuyện với `localhost` và `127.0.0.1` ở mọi cổng.
3. Trong chính profile Chrome đó, đăng nhập TikTok (www.tiktok.com), để tiện ích nhận ra tài khoản.
4. Quay lại trang Kết nối Chrome, bật đăng qua Chrome cho tài khoản TikTok tương ứng.

## Gắn giỏ hàng (TikTok Shop)

- **Học mẫu giỏ (tuỳ chọn):** mặc định tiện ích dựng giỏ đúng hình mẫu thật của TikTok. Nếu bạn đăng tay 1 bài có gắn giỏ trong TikTok Studio, tiện ích học lại mẫu đó (chỉ nhìn, không chặn, không sửa bài của bạn) để theo kịp khi TikTok đổi hình.
- **Lấy sản phẩm:** bấm "Lấy sản phẩm từ shop" trong TikTok Auto Kid, tiện ích tự mở một tab Studio thu nhỏ, đọc danh sách sản phẩm rồi đóng lại. Không đăng gì.
- Sản phẩm hết hàng/không còn trong shop thì video không được đăng, TikTok Auto Kid báo lỗi rõ ràng.
- Bản 1.1.0 xin thêm quyền đọc `shop.tiktok.com`. Sau khi cập nhật hãy bấm **⟳** trên thẻ TikTok Auto Kid.

## Sau khi cập nhật tiện ích

Mở `chrome://extensions` và bấm nút **⟳** (tải lại) trên thẻ TikTok Auto Kid. Nếu quên, TikTok Auto Kid sẽ báo Chrome cần tải lại.

## Ghi chú

- Quyền `background` giữ tiện ích chạy nền, kể cả khi đóng hết cửa sổ Chrome (với điều kiện Chrome được cấu hình tiếp tục chạy nền, hoặc có trợ lý mở Chrome).
- Mỗi profile Chrome ghép nối một lần. Muốn đăng cho nhiều tài khoản TikTok, dùng mỗi tài khoản một profile.
- Tiện ích chỉ đăng đúng một lần cho mỗi bài. Nếu không chắc kết quả, bài được đánh dấu "không chắc chắn" và không tự đăng lại.
- ID tiện ích: `poffpbdhahodnkoandkagilkbhaipolo` (đặt vào `FORK_CHROME_EXTENSION_ID` trong `.env`).

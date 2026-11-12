# Trợ lý mở Chrome (Windows)

Khi một bài cần đăng qua tiện ích TikTok Auto Kid mà Chrome của tài khoản đó đang tắt, trợ lý này cứ 30 giây hỏi app TikTok Auto Kid và mở đúng profile Chrome, **không hiện cửa sổ** (`--no-startup-window`); tiện ích có quyền `background` vẫn chạy.

Nó cũng báo danh sách profile Chrome (tên, đã cài tiện ích chưa) để trang **Cài đặt, Kết nối Chrome** cho chọn profile.

## Giữ Chrome luôn chạy nền

Mỗi Chrome đã ghép nối và đã chọn profile có công tắc "Giữ Chrome luôn chạy nền" (mặc định bật). Khi tiện ích im lặng quá 3 phút (dùng `last_seen_at`), app đưa profile đó vào danh sách `keepalive` của `launch-requests` và trợ lý mở nó bằng `--profile-directory=X --no-startup-window` (không cửa sổ, không cướp tiêu điểm). App chờ tối thiểu 5 phút giữa hai lần mở cùng profile, dừng sau 5 lần mở mà tiện ích không báo về và hiện lỗi ở trang Kết nối Chrome (nút "Mở Chrome nền ngay" thử lại). Trợ lý báo kết quả qua `POST /api/fork/chrome/keepalive-result`.

Trợ lý chỉ ĐỌC `Local State` (`background_mode.enabled`) và báo cho trang cài đặt; không bao giờ ghi vào cấu hình của Chrome.

Thử không cần app: `-DryRun -FakeResponse file.json` (file giả phản hồi `launch-requests`).

## Chạy

Không cần cài riêng: launcher (`TikTokAuto.exe`) chạy nó như dịch vụ `chrome-launcher` (xem `scripts/native/services.json`). Cấu hình lấy từ `.env` (`APP_URL`, `FORK_CHROME_LAUNCHER_SECRET`, do `scripts\native\setup.ps1` tạo). Log ở `chrome-launcher.log` cạnh script.

## Thử không mở Chrome thật

```powershell
powershell -ExecutionPolicy Bypass -File .\chrome-launcher.ps1 -DryRun
```

Chỉ quét profile và in ra việc sẽ làm; không mở Chrome, không gửi POST.

## Lưu ý

- Bật "Tiếp tục chạy ứng dụng nền khi đóng Google Chrome" trong `chrome://settings/system` để tiện ích còn chạy khi không có cửa sổ.
- **Chưa kiểm chứng**: mở bằng `--profile-directory` khi Chrome đang chạy một profile khác (Chrome có thể chỉ mở thêm cửa sổ cho profile kia). Nếu gặp lỗi, mở Chrome profile đó bằng tay.
- Tiện ích cài dạng unpacked không có thư mục `Extensions\<id>`; trợ lý nhận ra nó qua `Secure Preferences`.
- Trợ lý chỉ mở Chrome cho profile mà bạn đã chọn trong trang Kết nối Chrome.

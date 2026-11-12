# TikTok Auto Kid

Bộ công cụ tự động sản xuất và đăng video TikTok (kèm giỏ hàng TikTok Shop), chạy trực tiếp trên Windows 10 (64-bit, bản 1809 trở lên) hoặc Windows 11, dùng một mình trên máy cá nhân.

Luồng: **Xưởng Video** (làm video bằng AI) -> **Kho video** -> **Giỏ hàng** -> **xếp lịch** -> **tiện ích Chrome** đăng hẹn giờ -> **Số liệu** và cảnh báo **Telegram**.

## Cài đặt

1. Vào trang **Releases** của kho này, tải file **`TikTokAutoKid-Setup.exe`** và bấm đúp để chạy. Nếu Windows SmartScreen chặn: bấm **Thêm thông tin** rồi **Vẫn chạy**.
2. Chọn thư mục cài (mặc định `%LOCALAPPDATA%\TikTok Auto Kid`, có thể đổi sang ổ khác như `D:\TikTok Auto Kid`) và thư mục dữ liệu video.
3. Chờ trình cài làm tự động: tải bản mới nhất (kiểm SHA256), cài Python 3.11, Node.js, ffmpeg, Claude Code CLI bằng winget nếu thiếu, dựng PHP/PostgreSQL/Caddy, tạo cơ sở dữ liệu, tạo lối tắt **TikTok Auto Kid** ở Desktop và Start Menu, rồi mở app tại http://localhost:8010.

Cần: Windows 10 (64-bit, bản 1809 trở lên) hoặc Windows 11, Internet (lần đầu, khoảng 400 MB), khoảng 10 GB trống. Không cần quyền quản trị (Windows có thể tự hỏi nếu một gói bắt buộc). Máy chưa có winget (Windows 10 cũ) vẫn cài được: trình cài tự tải Python, Node.js, ffmpeg từ trang chính thức. Chạy lại `TikTokAutoKid-Setup.exe` (hoặc `CAI-DAT.bat` trong thư mục cài) bất cứ lúc nào để **sửa chữa**; nhật ký ở `runtime\logs\cai-dat.log`.

Việc làm tay một lần:
- **Chrome**: `chrome://extensions` > bật Chế độ nhà phát triển > *Tải tiện ích đã giải nén* > chọn thư mục `extension\autotok` trong thư mục cài. Ghép nối ở app: Cài đặt > Kết nối Chrome (xem `extension\autotok\HUONG-DAN.md`).
- **Xưởng Video**: đăng nhập tài khoản Claude (Claude Code CLI) và điền khoá ElevenLabs trong phần cài đặt của hub.
- **Học cảnh** (tuỳ chọn): tự cài [Google Antigravity](https://antigravity.google), đăng nhập và để ứng dụng đang mở khi học cảnh.

## Cập nhật

Dùng nút **Cập nhật** trong app (Cài đặt > Cập nhật): app tìm bản mới trên GitHub, tải, kiểm SHA256, sao lưu cơ sở dữ liệu rồi cập nhật; có thể quay lại bản trước.

## Dữ liệu của bạn nằm đâu

Bản cập nhật **không bao giờ ghi đè** dữ liệu của bạn:
- `.env` (cấu hình và khoá), `runtime\` (cơ sở dữ liệu, log, sao lưu), `storage\`, `du-lieu\` (dữ liệu Xưởng Video: sản phẩm, lịch sử, video ra, tài khoản Claude, nhạc/SFX).
- Muốn đặt dữ liệu Xưởng Video ở ổ khác: đặt `XUONG_DATA` (và `FORK_HUB_PATH` cùng giá trị) trong `.env`, hoặc chạy trình cài với `-ThuMucDuLieu "D:\Video\xuong-video"`.

## Gỡ cài đặt

Thoát TikTok Auto Kid (khay hệ thống > Thoát), xoá thư mục cài, xoá lối tắt trong Desktop / Start Menu / Startup. Gỡ tiện ích trong `chrome://extensions`. Python, Node.js, ffmpeg cài qua winget gỡ ở Cài đặt > Ứng dụng nếu không cần nữa.

## Kiểm tra và gỡ lỗi

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install\cai-dat.ps1 -KiemTra
```
Kiểm phần mềm cần có, tệp, `.env`, dịch vụ, cổng, hub và gợi ý ghép tiện ích. Thêm `-ThuKhong` để chạy thử trình cài mà không thay đổi gì.

## Prompt khởi đầu (dán cho Claude / Codex / Antigravity)

Mở AI ở thư mục cài đặt rồi dán:

```
Đọc AGENTS.md trong thư mục này, kiểm tra cài đặt (chạy scripts/install/cai-dat.ps1 -KiemTra), sửa lỗi nếu có và báo lại bằng tiếng Việt.
```

## Phát triển

- Sổ tay kiến trúc, quy ước, cách chạy test an toàn, đóng gói và phát hành: **`AGENTS.md`**.
- Test: `scripts\native\test.ps1 tests/Feature/Fork`; launcher: `go test -p 1 -count=1 -timeout 150s .` trong `launcher\`.
- Đóng gói bản phát hành: `scripts\release\build.ps1` (kết quả ở `dist\`).

## Nguồn gốc và giấy phép

Dựa trên mã nguồn mở [TryPost](https://github.com/trypost-it/trypost), giấy phép **AGPL-3.0** (xem `LICENSE.md`). Bản này đã lược bỏ phần mạng xã hội và thêm phần tự động đăng TikTok qua tiện ích Chrome, Xưởng Video và trình cài/cập nhật cho Windows. Toàn bộ mã nguồn của dự án phát hành theo cùng giấy phép AGPL-3.0.

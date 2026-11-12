# AGENTS.md - sổ tay cho AI làm việc trên dự án TikTok Auto Kid

Đọc hết file này trước khi sửa bất cứ thứ gì. Nói chuyện với chủ app bằng **tiếng Việt**. Tên mã (biến, hàm, lớp, tên file kỹ thuật) giữ tiếng Anh/không dấu như đang có.

## 1. App làm gì (luồng đầu-cuối)

TikTok Auto Kid là bộ công cụ **chạy trên Windows 10 (64-bit, 1809+) và Windows 11, một người dùng; chỉ có Windows PowerShell 5.1 (không giả định `pwsh`, không dùng cú pháp PowerShell 7)**, tự động hoá chuỗi: sản xuất video ngắn -> xếp lịch -> đăng TikTok kèm giỏ hàng TikTok Shop -> thu số liệu/bình luận -> báo Telegram.

1. **Hub "Xưởng Video"** (`xuong-video/`, Python + FFmpeg + Remotion, cổng 8765) sản xuất video: biên kịch -> giọng ElevenLabs -> đạo diễn (nhìn ảnh cảnh, lên bảng dựng) -> máy dựng -> giám khảo chấm điểm. Học cảnh từ kho video có sẵn bằng ứng dụng **Google Antigravity** (người dùng tự cài và đăng nhập; phải ĐANG MỞ khi học). Sản xuất dùng **Claude Code CLI** (`claude`, mỗi tài khoản đăng nhập trong hub) và khoá ElevenLabs (trong `.env` của thư mục dữ liệu hub). Video xong, đạt "ưng", được bỏ vào `kho-dang/` của thư mục dữ liệu hub.
2. **App Laravel** (cổng 8010) kéo video từ hub qua cổng hub (8766, header `X-Key`), lệnh `fork:auto-ingest` (mỗi 5 phút) -> Kho (`AutoVideo`). Hub offline thì app **không xếp lịch** (cố ý, tránh đăng sai).
3. **Giỏ hàng**: tiện ích Chrome gửi danh sách sản phẩm TikTok Shop lên `/api/ext/products`; trang Giỏ hàng ghép video với sản phẩm.
4. **Planner** (`fork:auto-plan`, mỗi 5 phút) xếp lịch; `PostBuilder` tạo `Post` hẹn giờ + file media.
5. **Tiện ích Chrome** `extension/autotok` (Load unpacked) nhận job qua long-poll `/api/ext/next`, đăng hẹn giờ ngay trong TikTok Studio kèm giỏ hàng, báo kết quả. Không dùng API TikTok.
6. `HubReporter` báo kết quả về hub; `Stats/*` thu số liệu (`fork:auto-stats`), trang Số liệu; `Notify/*` gửi Telegram (token/chat id nhập ở Cài đặt > Telegram).

## 2. Kiến trúc và tiến trình

`TikTokAuto.exe` (launcher Go, khay hệ thống) đọc `runtime/services.json` và giám sát các dịch vụ:

| Dịch vụ | Cổng | Ghi chú |
|---|---|---|
| launcher (trạng thái + điều khiển) | 127.0.0.1:8009 | `/api/status`, `/api/restart?service=<tên>` (header `X-TTA-Token` = `runtime/control.token`), `/api/update/*` |
| postgres | 127.0.0.1:5433 | portable, dữ liệu `runtime/data/pg`, DB `tiktok_auto`, trust, chỉ loopback |
| php-cgi-1, php-cgi-2 | 9101, 9102 | FastCGI |
| web (Caddy) | 127.0.0.1:8010 | phát tĩnh `public/`, video/ảnh bìa (`FORK_ACCEL`), PHP chỉ kiểm quyền |
| queue-main, queue-social, scheduler | - | `queue:work` x2 (database queue), `schedule:work` |
| chrome-launcher | - | PowerShell, mở profile Chrome cho tiện ích (dùng `FORK_CHROME_LAUNCHER_SECRET`) |
| xuong-video (hub) | 8765 (+8766 cổng cho app) | tuỳ chọn; `runtime/xuong-venv` hoặc `XUONG_PYTHON` |

App một người dùng: không đăng nhập, `APP_SINGLE_USER=true`, chỉ nhận request từ loopback. Cổng đang **được viết cứng** ở nhiều nơi (Caddyfile, services.json, run-postgres.ps1, bootstrap.ps1, tiện ích, chrome-launcher, hub) - đổi cổng phải sửa tất cả.

## 3. Bản đồ thư mục

**Mã (đi cùng git/bản phát hành):**
- `app/Fork/{AutoPost,Chrome,Notify,SingleUser,Update,Xuong}`: gần như toàn bộ logic riêng. `routes/fork-*.php`, `database/migrations/fork`, `config/fork.php`, `config/fork-update.php`.
- `app/{Models,Jobs,Console,Actions,Enums}`: lõi tối thiểu còn lại từ TryPost (Post, Media, SocialAccount, AnalyticsPublication*...); giữ lịch đăng (`posts:process-scheduled`, `social:recover-stuck-posts`).
- `resources/js/pages/fork`, `resources/js/components/fork`: giao diện Inertia/Vue, chữ viết thẳng tiếng Việt, hỗ trợ sáng/tối.
- `extension/autotok/`: tiện ích Chrome (xem `HUONG-DAN.md`, `PROTOCOL.md`, `STUDIO-API.md`).
- `launcher/`: Go (`TikTokAuto.exe`), kèm bộ cập nhật (`update_*.go`).
- `xuong-video/`: `app/` (server + giao diện hub + `cong_trypost.py`), `engine/` (máy dựng, AI), `luat/` (luật và prompt), `remotion/` (lớp chữ), `mau/` (dữ liệu mẫu cho lần chạy đầu).
- `scripts/native/` (setup, start, stop, test, Caddyfile, services.json, env.template), `scripts/install/cai-dat.ps1` + `CAI-DAT.bat` (trình cài), `scripts/release/build.ps1` (đóng gói).
- `tools/fork/chrome-launcher/`, `tests/Feature/Fork` (Pest).

**Dữ liệu người dùng (KHÔNG vào git, KHÔNG bị bản cập nhật ghi đè):**
- `.env` (gốc repo), `runtime/` (PHP, Postgres, Caddy, venv, `services.json`, log, backup), `storage/`, `du-lieu/`.
- Thư mục dữ liệu hub = `XUONG_DATA` (= `FORK_HUB_PATH`), mặc định `du-lieu/xuong-video`: `config.json` (có khoá cổng hub `trypost.khoa`), `.env` (khoá ElevenLabs...), `san-pham/`, `lich-su/`, `ra/`, `kho-dang/`, `da-dang/`, `tai-khoan/` (đăng nhập Claude), `ho-so/`, `tai-nguyen/` (nhạc, SFX).

## 4. Cấu hình chính (`.env` ở gốc repo; mẫu `scripts/native/env.template`)

| Biến | Ý nghĩa |
|---|---|
| `APP_KEY` | khoá Laravel (setup tự sinh) |
| `APP_URL` | `http://localhost:8010` |
| `APP_SINGLE_USER` | chế độ một người dùng, loopback |
| `DB_*` | Postgres cổng 5433, user `postgres`, không mật khẩu |
| `FORK_HUB_PATH`, `XUONG_DATA` | thư mục dữ liệu hub, phải **cùng một thư mục** |
| `XUONG_PYTHON` | (tuỳ chọn) python.exe riêng; mặc định `runtime/xuong-venv` |
| `FORK_HUB_URL`, `FORK_HUB_KEY` | cổng hub (8766) và khoá; **khoá phải bằng `trypost.khoa` trong `config.json` của hub** |
| `FORK_HUB_MAY`, `FORK_HUB_REQUIRE_CLAIM` | mã máy / bắt buộc giữ chỗ khi nhiều máy dùng chung hub |
| `FORK_CHROME_LAUNCHER_SECRET` | bí mật cho chrome-launcher (setup tự sinh) |
| `FORK_CHROME_EXTENSION_ID` | tuỳ chọn; để trống thì suy từ `key` trong `extension/autotok/manifest.json` |
| `FORK_ACCEL` | Caddy phát media trực tiếp |
| `FORK_TELEGRAM_*` | tuỳ chọn (thường nhập trong giao diện) |
| `UPDATE_REPO` | `kidlost1412/tiktok-auto-kid`, kho GitHub cho nút Cập nhật |

Không bao giờ in giá trị khoá/token ra màn hình, log, commit hay câu trả lời.

## 5. Định dạng dữ liệu (đọc file gốc, không đoán)

- Mô tả cảnh video (Học cảnh / `*.mo-ta.json`): `xuong-video/luat/MO-TA-VIDEO-GEMINI.md`. Luật sản xuất: `xuong-video/luat/LUAT-SAN-XUAT.md`, `SO-TAY-EDITOR.md`.
- Kho video hub -> app (mp4 + json cùng tên trong `kho-dang/`): `app/Fork/AutoPost/KHO-CHUAN.md`.
- Hợp đồng cổng hub (`/trypost/videos`, `/giu`, `/nha`, `/da-dang`, `/loi`, `/so-lieu`, tải file; header `X-Key`): docstring đầu `xuong-video/app/cong_trypost.py`. (Tên "trypost" là tên cũ, giữ nguyên.)
- Giao thức tiện ích <-> app: `extension/autotok/PROTOCOL.md`; API Studio: `STUDIO-API.md`.

## 6. Chạy test an toàn

Máy có thể yếu/RAM thấp: **chạy từng bước một**, không song song; trước và sau khi chạy kiểm `(Get-Process).Count`.

- **Launcher (Go)**: trong `launcher/`: `go test -p 1 -count=1 -timeout 150s .`. **CẢNH BÁO BOM TIẾN TRÌNH:** launcher tự chạy lại chính exe (`--watch-pg`, `--send-break`, `--update`, `--after-swap`); trong test "chính exe" là file test, nếu con chạy lại bộ test sẽ đẻ ra hàng nghìn tiến trình và treo máy (đã xảy ra). `TestMain` trong `launcher/optional_test.go` chặn việc này - **tuyệt đối giữ nguyên**, và không bỏ `-p 1`, `-timeout`.
- **PHP (Pest)**: `powershell -ExecutionPolicy Bypass -File scripts\native\test.ps1 tests/Feature/Fork` (cần Postgres 5433, dùng DB `tiktok_auto_test`; tự bật/tắt Postgres nếu chưa chạy).
- **Giao diện**: `npm run build` (cần `runtime\php` trong PATH).
- **Tiện ích**: test Node trong `extension/autotok/tests`.
- Không chạy `fork:auto-plan`, không bật/tắt đăng bài, không huỷ bài đã hẹn trên máy thật của chủ app.

## 7. Đóng gói và phát hành

1. Sửa `VERSION` (semver, ví dụ `1.0.1`), commit mọi thứ (gói được tạo từ `git archive HEAD`).
2. Chạy test (mục 6), rồi: `powershell -ExecutionPolicy Bypass -File scripts\release\build.ps1`.
3. Kết quả trong `dist/` (đã .gitignore): `tiktok-auto-kid-<ver>.zip`, `.zip.sha256`, `CAI-DAT.bat`, `cai-dat.ps1`. Zip chứa mã, `vendor` (no-dev), `public/build`, `TikTokAuto.exe` (cài mới) và `TikTokAuto.new.exe` (cập nhật). Không chứa `.env`, `runtime/`, `du-lieu/`, `storage/*`, `node_modules`.
4. Chủ app tự đăng: `git tag v<ver>`, `git push`, rồi `gh release create v<ver> dist\tiktok-auto-kid-<ver>.zip dist\tiktok-auto-kid-<ver>.zip.sha256 dist\CAI-DAT.bat dist\cai-dat.ps1 --repo kidlost1412/tiktok-auto-kid`. Tên asset phải đúng `tiktok-auto-kid-<ver>.zip` và `.zip.sha256`.
5. **Trình cập nhật** (trong launcher + trang Cài đặt > Cập nhật): đọc `UPDATE_REPO`, hỏi GitHub Releases mới nhất, tải zip, kiểm SHA256, ghi đè mã nhưng **bảo vệ** `.env`, `runtime/`, `storage/`, `du-lieu/`, `TikTokAuto.exe`; sao lưu DB trước khi migrate; có quay lại bản trước. `TikTokAuto.new.exe` được launcher thay vào lần mở kế tiếp. Danh sách bảo vệ: `IsProtected` trong `launcher/update_core.go`.

## 8. Cài đặt và kiểm tra

- Người dùng chạy `CAI-DAT.bat` (-> `scripts/install/cai-dat.ps1`): hỏi thư mục, tải bản phát hành (kiểm SHA256), cài bằng winget (Visual C++, Python 3.11, Node LTS, ffmpeg; máy không có winget thì tải thẳng từ python.org / nodejs.org / gyan.dev, Node và ffmpeg giải vào `runtime/`), `npm i -g @anthropic-ai/claude-code`, chạy `scripts/native/setup.ps1` (PHP/Postgres/Caddy portable từ URL chính thức kèm SHA256, venv, Remotion, `.env`, CSDL), lối tắt Desktop/Start Menu, mở app. Chạy lại = sửa chữa. Nhật ký `runtime/logs/cai-dat.log`.
- `-ThuKhong`: chạy thử, không đổi gì. `-KiemTra`: kiểm sức khoẻ (phần mềm, tệp, `.env`, khoá hub khớp, dịch vụ, cổng, hub, gợi ý ghép tiện ích) - **dùng khi được yêu cầu "kiểm tra cài đặt"**, mã thoát 1 nếu có lỗi.

## 9. Lỗi thường gặp và cách xử lý

- **Treo máy / hết RAM / không dựng được video**: bật pagefile tự động (Cài đặt > Hệ thống > Giới thiệu > Cài đặt nâng cao > Hiệu suất > Nâng cao > Bộ nhớ ảo); đóng bớt ứng dụng; chạy test từng bước (mục 6).
- **Postgres mồ côi ở 5433** (launcher đã tắt nhưng `postgres.exe` còn): launcher không khởi động được DB. Thoát hẳn launcher, kết thúc `postgres.exe` mồ côi, mở lại; xoá `postmaster.pid` cũ chỉ khi chắc không còn tiến trình.
- **cacert**: PHP gọi HTTPS lỗi chứng chỉ -> `runtime/php/php.ini` phải trỏ `curl.cainfo`/`openssl.cafile` tới `runtime/php/cacert.pem` (đường dẫn tuyệt đối dùng `/`); chạy lại `setup.ps1` để sinh lại.
- **Hub offline thì không xếp lịch**: Kho báo hub không hoạt động. Kiểm `http://127.0.0.1:8765/health`, dịch vụ `xuong-video` ở trang 8009, `runtime/logs/xuong-video.err.log`; khoá `FORK_HUB_KEY` phải trùng `trypost.khoa`. Khởi động lại hub: `POST http://127.0.0.1:8009/api/restart?service=xuong-video` kèm `X-TTA-Token`.
- **Tiện ích Chrome không ghép được**: địa chỉ máy chủ trong tiện ích phải là `http://localhost:8010`; lấy mã 6 số ở Cài đặt > Kết nối Chrome (hiệu lực 5 phút); sau khi cập nhật tiện ích bấm tải lại ở `chrome://extensions`; phải đăng nhập TikTok trong đúng profile.
- **"Học cảnh" không chạy**: Google Antigravity phải **đang mở** và đã đăng nhập (hub dùng daemon cục bộ của nó). **Gemini CLI không còn dùng được cho tài khoản miễn phí** - đừng quay lại hướng đó.
- **Claude hết hạn mức**: hub báo đỏ; đăng nhập/đổi tài khoản trong tab Cài đặt của Xưởng Video rồi chạy tiếp.
- **`php artisan` báo thiếu thư viện/cấu hình cũ**: `runtime\php\php.exe artisan config:clear`.
- **Cập nhật báo chưa cấu hình kho**: đặt `UPDATE_REPO=kidlost1412/tiktok-auto-kid` trong `.env`.

## 10. Quy ước

- Giao diện, thông báo, tài liệu: **tiếng Việt**; hỗ trợ sáng/tối. Không i18n.
- App **một người dùng, loopback**: đừng thêm đăng nhập/đăng ký/thanh toán/MCP/API key/webhook, đừng mở cổng ra LAN, nếu không hỏi chủ app.
- Không đăng qua API TikTok; chỉ đi qua tiện ích Chrome. Không thêm mạng xã hội khác.
- **Không bao giờ commit bí mật**: `.env`, khoá hub, token Telegram, khoá ElevenLabs, dữ liệu trong `du-lieu/`, đường dẫn máy cá nhân, tên kênh/tài khoản thật. `.gitignore` đã loại các thư mục dữ liệu; kiểm lại trước khi commit/phát hành.
- Migration cũ giữ nguyên (DB cũ và mới đều dựng được).
- Sửa nhỏ, có test (`tests/Feature/Fork`); không đụng dữ liệu của người dùng khi sửa lỗi; chạy lại `-KiemTra` sau khi sửa cài đặt.
- Commit: tiếng Việt hoặc không dấu, mô tả ngắn gọn thay đổi.

# TikTok Auto Kid Launcher

Chương trình Windows nhỏ (1 file `TikTokAuto.exe`, viết bằng Go) biến bộ ứng dụng Laravel thành "ứng dụng một cú nhấp": chạy các dịch vụ nền (PHP, Postgres, queue...), giám sát, tự khởi động lại khi lỗi, có biểu tượng ở khay hệ thống.

## Build

Cần Go (`winget install -e --id GoLang.Go`). Trong thư mục `launcher`:

```
build.bat
```

Script chạy `go vet`, `go test`, rồi tạo `dist\TikTokAuto.exe` (không có cửa sổ console, đã nhúng icon) và `testdata\bin\dummysvc.exe` (tiến trình giả để thử). Sau đó copy `TikTokAuto.exe` vào thư mục gốc của bundle (cạnh `runtime\`).

## Cách hoạt động

1. Tìm thư mục gốc bundle = thư mục chứa exe (nếu không có `runtime\services.json` thì tìm ở thư mục cha).
2. Đọc `runtime\services.json`, kiểm tra các cổng (`app_url` + cổng health). Cổng bị chiếm: báo "Cổng 8010 đang bị chiếm bởi ..." và không khởi động.
3. Chạy `first_run` theo thứ tự (bước có `only_if_missing` chỉ chạy khi đường dẫn đó chưa tồn tại; bước không có thì chạy mỗi lần, vd `migrate`).
4. Khởi động từng dịch vụ theo `depends_on`, chờ health (tcp/http) xong mới tới dịch vụ sau; quá hạn (mặc định 90 giây, đổi bằng `health.timeout_sec`) thì báo lỗi.
5. Giám sát: dịch vụ chết thì tự chạy lại, chờ 1s → 2s → 4s ... tối đa 60s (về 1s nếu chạy ổn định > 60s).
6. Màn hình chào (splash, WebView2) hiện tiến độ thật rồi mở trình duyệt tới `app_url` (xem mục "Màn hình chào"). Không mở/không splash khi chạy từ "Chạy cùng Windows". Chạy lần 2 chỉ hiện splash ngắn (~0,8 giây) rồi mở trình duyệt, không chạy thêm bản nữa.
7. Menu khay: Mở TikTok Auto Kid, trạng thái từng dịch vụ, Khởi động lại, Mở thư mục log, Sao lưu dữ liệu ngay, Chạy cùng Windows (ghi `HKCU\...\Run`, chỉ người dùng hiện tại), Thoát.
8. Thoát: dừng ngược thứ tự phụ thuộc. Mỗi dịch vụ: chạy lệnh `stop` nếu có, nếu không thì gửi CTRL_BREAK; chờ (`stop_timeout_sec`, mặc định 8s, có `stop` thì 30s); quá hạn thì kill cả cây tiến trình. Tiến trình con nằm trong Job Object: launcher bị tắt đột ngột thì tất cả bị tắt theo (Postgres sẽ tự phục hồi lần chạy sau).

Khuyến nghị: dịch vụ Postgres nên khai báo `stop` (`pg_ctl stop -m fast`) để tắt sạch.

## Màn hình chào (splash)

- Cửa sổ không khung 760x460, bo góc, nền tím, logo có hiệu ứng, thanh tiến độ mượt (không bao giờ lùi), một dòng trạng thái: "Đang mở kho dữ liệu…" (postgres), "Đang bật máy chủ…" (php/web), "Đang đánh thức Xưởng Video…", "Sắp xong…", "Sẵn sàng!". Tiến độ tính có trọng số từ trạng thái thật của các dịch vụ (`splash.go`); phần "bò nhẹ" do trang HTML (`assets/splash.html`) làm để không bao giờ trông như đứng yên.
- Lỗi khởi động (cổng bị chiếm, dịch vụ quá hạn health, bước chuẩn bị hỏng) => thẻ lỗi tiếng Việt với nút "Thử lại" (dừng sạch rồi chạy lại ngay trên splash), "Xem chi tiết" (mở trang trạng thái cổng 8009, có log) và "Đóng" (app vẫn chạy ở khay).
- Không tạo được WebView2 (máy thiếu runtime...) => im lặng quay về cách cũ (mở trang trạng thái, báo lỗi bằng hộp thoại), không chặn khởi động. Đặt biến môi trường `TTA_NO_SPLASH=1` để tắt splash.
- Khi khởi động không còn thông báo/hộp thoại từng dịch vụ; chỉ có cảnh báo khi một dịch vụ chính chết bất ngờ SAU khi đã khởi động xong (mỗi dịch vụ tối đa 1 lần/10 phút).
- Xem trước khi app thật đang chạy: `TikTokAuto.exe -splash-demo` (mô phỏng thành công), `-splash-demo=loi` (thẻ lỗi, bấm Thử lại thì chạy tiếp thành công), `-splash-demo=nhanh` (splash của lần chạy thứ hai). Các chế độ này không chạy dịch vụ và không đụng khoá single-instance.
- WebView2 dùng bản chỉnh nhẹ của `github.com/jchv/go-webview2` (thuần Go, không cgo) đặt ở `third_party/go-webview2` (cửa sổ popup ẩn khỏi taskbar, không Fatal khi lỗi). Dữ liệu WebView2 nằm ở `%LOCALAPPDATA%\TikTokAutoKid\WebView2`. Gỡ lỗi: đặt `TTA_SPLASH_DEBUG=<đường dẫn tệp>` để ghi log của thư viện.

## API điều khiển (127.0.0.1:8009)

Các endpoint POST cần header `X-TTA-Token` = nội dung `runtime/control.token` (token mới mỗi lần chạy) và chỉ nhận Host loopback:

- `POST /api/restart?service=<tên>`: khởi động lại một dịch vụ tuỳ chọn.
- `POST /api/quit`: thoát êm (dừng dịch vụ theo thứ tự ngược rồi thoát, gỡ biểu tượng khay); trả 202 ngay, 409 nếu đang cập nhật. Trình gỡ cài đặt dùng endpoint này.

## Định dạng `runtime/services.json`

```json
{
  "app_url": "http://localhost:8010",
  "services": [{
    "name": "postgres",
    "cmd": "runtime/pgsql/bin/postgres.exe",
    "args": ["-D", "runtime/data/pg"],
    "cwd": ".",
    "env": {},
    "health": {"type": "tcp", "port": 5433},
    "depends_on": [],
    "restart": "always",
    "stop": {"cmd": "runtime/pgsql/bin/pg_ctl.exe", "args": ["stop", "-D", "runtime/data/pg", "-m", "fast"]},
    "stop_timeout_sec": 30
  }],
  "first_run": [{"name": "initdb", "cmd": "...", "args": [], "only_if_missing": "runtime/data/pg"}],
  "backup": {"cmd": "runtime/pgsql/bin/pg_dump.exe", "args": ["-h", "127.0.0.1", "-p", "5433", "app"]}
}
```

- Đường dẫn là tương đối với thư mục gốc bundle; `cmd` không có `/` hay `\` (vd `cmd`) được tìm trong PATH. Có thể dùng `${ROOT}` trong `cmd`, `args`, `cwd`, `env`.
- `health`: `{"type":"tcp","port":N}` hoặc `{"type":"http","url":"..."}` (mã < 500 là sẵn sàng); `null`/bỏ trống = coi là sẵn sàng sau 1 giây còn sống. Tuỳ chọn `timeout_sec`.
- `restart`: `always` (mặc định) | `on-failure` | `never`.
- `stop` (tuỳ chọn): `{"cmd","args","cwd","env"}` chạy khi dừng dịch vụ.
- `backup`: kết quả ghi vào `runtime/backups/<yyyyMMdd-HHmm>.sql`. Mặc định lấy stdout của lệnh; nếu một đối số chứa `{out}` thì được thay bằng đường dẫn file đích (vd `["-f","{out}"]`). Giữ 14 bản mới nhất. Tự sao lưu một lần mỗi ngày (lúc khởi động đầu tiên trong ngày; launcher chạy qua đêm cũng kiểm tra mỗi giờ).

## Log và sao lưu

- Log: `runtime\logs\<tên>.log` (mỗi dịch vụ, `launcher.log` cho launcher, các bước first_run cũng có log riêng). Xoay vòng 5 MB × 3 file (`.log`, `.log.1`, `.log.2`).
- Sao lưu: `runtime\backups\`.

## Dòng lệnh (gỡ lỗi)

- `TikTokAuto.exe --check` : kiểm tra `services.json` (cú pháp, phụ thuộc vòng, file thực thi có tồn tại) rồi thoát (mã 0 = ổn).
- `TikTokAuto.exe --console` : chạy không có khay, log ra màn hình, Ctrl+C để dừng. Thêm `--exit-after N` để tự thoát sau N giây.
- `--root <thư mục>` và `--config <file>` để chỉ định bundle/cấu hình khác. Ví dụ thử với dữ liệu giả:

```
dist\TikTokAuto.exe --console --root testdata --config testdata\services.json --exit-after 10
```

## Kiểm thử

`go test ./...` (cấu hình, sắp xếp phụ thuộc/phát hiện vòng, backoff, xoay log, kiểm tra cổng, sao lưu). Dữ liệu thử ở `testdata\services.json` dùng `tools\dummysvc` làm dịch vụ giả.

## Hạn chế

- Cảnh báo lỗi (vd cổng bị chiếm) hiện bằng hộp thoại và tooltip của biểu tượng khay, không phải bong bóng thông báo Windows.
- Khi Windows tắt máy/đăng xuất, launcher có thể không kịp dừng sạch Postgres (Postgres tự phục hồi lần chạy sau). Nên chọn "Thoát" trước khi tắt máy.

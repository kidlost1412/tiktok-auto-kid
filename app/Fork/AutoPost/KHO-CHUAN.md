# Chuẩn kho video (hub → app)

Dành cho người viết hub (thư mục `xuong-video\` trong repo; dữ liệu ở thư mục dữ liệu `XUONG_DATA`).

## 1. Hub bỏ video vào đâu

`<hub>/kho-dang/` (thẳng trong thư mục, hoặc `kho-dang/<ma>/`). Chỉ bỏ video **đã hoàn chỉnh, sẵn sàng đăng** (đã có nhạc). Mỗi video gồm **hai file cùng tên**:

```
kho-dang/nano-dong/NanoDong_chu-hang_XuanLuong_20261110-101500.mp4
kho-dang/nano-dong/NanoDong_chu-hang_XuanLuong_20261110-101500.json
```

```json
{
  "ma": "dam-ca",
  "quy_cach": "1l",
  "caption": "Kích rễ TC01 của Toàn Cầu: ... Bấm giỏ hàng để nhận quà theo đơn!",
  "hashtag": "#kichre #kichretc01 #tc01 #nongduoctoancau",
  "ten_gio": "KÍCH RỄ TC01",
  "danh_gia": "ung",
  "goc": "chu-hang",
  "giong": "XuanLuong",
  "loi_thoai": "Lời thoại đầy đủ...",
  "ngay_lam": "2026-11-10",
  "phien_ban": 1,
  "nhac": "...", "font": "...", "mau": "..."
}
```

- Bắt buộc: `ma` (khớp `san-pham/<ma>`), `quy_cach` (chuỗi hoặc `null`). Nên có: `goc`, `giong`, `loi_thoai`, `ngay_lam` (YYYY-MM-DD), `phien_ban`.
- **Caption do hub viết, app dùng nguyên văn (không gọi AI):** `caption` (chuỗi, bắt buộc), `hashtag` (chuỗi cách nhau bằng dấu cách, hoặc list; tuỳ chọn), `ten_gio` (tên hiển thị trong giỏ hàng, 1..30 ký tự; tuỳ chọn, không hợp lệ hoặc không có thì dùng tên của liên kết giỏ hàng), `danh_gia` (`"ung"`, chỉ để tham khảo, giữ trong `meta`). Bài đăng = `caption` + dòng trống + `hashtag`, tối đa 2200 ký tự.
- Không có `caption` trong json thì app đọc `X.txt` cạnh video (dòng 1 caption, dòng 2 hashtag), rồi hàng của video trong `bang-ghi-ekip.csv` cùng thư mục (cột `file`, `caption`, `hashtag`). Vẫn không có thì video **chờ** (không bị đưa vào `_loi`, không được đăng) cho tới khi caption xuất hiện, lần ingest sau tự nhận.
- `nhac`, `font`, `phu_de`, `chuyen_canh`, `chuyen_dong`, `mau`, `thoi_luong` được app đọc. Mọi khoá khác giữ nguyên trong `meta`, không mất.
- **Ghi json trước hoặc cùng lúc, ghi mp4 sau cùng** (tốt nhất ghi tên tạm rồi đổi tên). App chỉ nhặt khi cả hai file có đủ, json hợp lệ, và kích thước mp4 và json không đổi suốt `settle_seconds` (mặc định 20 giây).
- Tên file không còn mang ý nghĩa gì (không cần `MIXKIT`); thông tin lấy từ json.

## 2. Quy cách sản phẩm

`<hub>/san-pham/<ma>/san-pham.json` thêm (không có hoặc rỗng = sản phẩm chỉ một quy cách, video ghi `"quy_cach": null`):

```json
"quy_cach": [ {"ma": "1l", "ten": "Chai 1L"}, {"ma": "5l", "ten": "Can 5L"} ]
```

Sản phẩm có quy cách thì `quy_cach` của video bắt buộc nằm trong danh sách. Sản phẩm không có thì phải là `null`.

## 3. App làm gì

- Video hợp lệ → vào kho, trạng thái mới. Trùng nội dung (sha256) với video đã có → vào `_loi`.
- Video sai (json hỏng, thiếu `ma`, mã lạ, quy cách sai, trùng, hoặc mp4 quá 120 phút không có json) → `<hub>/kho-dang/_loi/` cùng file `<tên>.loi.txt` ghi lý do. Thư mục bắt đầu bằng `_` không bao giờ bị quét.
- Sau khi đăng xong → `<hub>/da-dang/<YYYY-MM-DD ngày đăng>/` gồm mp4 + json + `<tên>.ket-qua.json` (link và id TikTok, kênh, giờ đăng, sản phẩm, quy cách). Nếu cài đặt lưu giữ là "xoá ngay" thì mp4 + json bị xoá, chỉ còn `.ket-qua.json`.
- Lưu giữ chỉnh trên trang `/auto/kho`: `xoa_ngay`, `7`, `30` (mặc định), `vinh_vien`. Lệnh `fork:auto-cleanup` chạy hằng ngày, xoá mp4 + json quá hạn trong `da-dang`, **không bao giờ xoá `.ket-qua.json`**.
- `so-lieu.csv` (lượt xem 24h/72h) được ghi cạnh `.ket-qua.json` trong `da-dang/<ngày>/`.
- Kiểu cũ `ra/<ngày>/X.mp4` + `X.txt` (+ `bang-ghi.csv`, `bang-ghi-ekip.csv`) vẫn được nhặt khi `fork.auto.legacy_ra = true` (mặc định); video cũ không có quy cách và vẫn chuyển sang `ra/_da-dang/` sau khi đăng. Tắt khi hub đã chuyển hẳn sang `kho-dang`.

## 4. Chế độ API (chính)

Khi có `FORK_HUB_KEY` (`.env`), app hỏi hub "Xưởng Video" qua HTTP (`fork.auto.hub_api.url`, mặc định `http://127.0.0.1:8766`, header `X-Key`) và **không đọc** `kho-dang/`, `ra/`, `.txt`, csv. Các mục 1 và 3 ở trên chỉ còn là chế độ dự phòng khi không có khoá.

- `fork:auto-ingest` lấy `GET /trypost/videos?status=ung` (video chủ đã duyệt, chưa đăng) và upsert theo `id` hub (cột `hub_id`): file `<hub>/<file>`, `sha256`, `ma`, `quy_cach`, caption + hashtag (nối bằng dấu cách) làm chữ của hub, `ten_gio` hợp lệ làm tên giỏ hàng. Thiếu file mp4 trong `/hub` thì chưa được giữ chỗ (cảnh báo). Video biến mất khỏi `ung` khi còn `new` thì bị bỏ qua với lý do "hub bỏ duyệt" (duyệt lại thì nhận lại). Không bao giờ nạp lại video đã giữ chỗ/xếp lịch/đăng.
- Đăng xong: `POST /trypost/videos/{id}/da-dang`; lỗi chắc chắn hoặc giỏ hàng bị chặn: `POST .../loi`; số liệu 24h/72h: `POST /trypost/so-lieu`. Mọi lời báo ghi vào bảng `fork_hub_outbox` rồi gửi, hub tắt thì thử lại (backoff tới 1 giờ) ở mỗi lượt ingest 5 phút; 404/4xx thì bỏ.
- Hub tắt (lỗi kết nối): giữ nguyên dữ liệu, lượt sau thử lại. TikTok Auto Kid không chuyển/xoá file của hub; hub tự dọn sau 30 ngày. `fork:auto-cleanup` và `so-lieu.csv` tắt trong chế độ này.
- Trang `/auto/kho` hiện trạng thái kết nối (đệm 1 phút) và nút "Kiểm tra kết nối hub".

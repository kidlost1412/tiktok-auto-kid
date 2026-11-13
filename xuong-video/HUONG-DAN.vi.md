# XƯỞNG VIDEO — hướng dẫn (chốt 10/11/2026)

## Mở app
Xưởng Video chạy cùng **TikTok Auto Kid** (dịch vụ `xuong-video`, cổng 8765) và nhúng ở mục "Xưởng" của app. Mở riêng: http://127.0.0.1:8765.

## Làm video hằng ngày
🎬 **Sản xuất** → chọn sản phẩm + số video → **Bắt đầu làm**. Xem tiến độ, nhật ký ê-kíp AI; có nút Dừng.
Video ra ở `ra\<ngày>\`: chỉ có các file `.mp4` thành phẩm (đã làm sạch metadata); ảnh bìa `.jpg`, caption `.txt`, hồ sơ `.json`, bảng ghi `.csv` nằm trong `ra\<ngày>\_kem\`.

📺 **Kho video** → xem to, điểm giám khảo, chép caption, tải bìa; ✅ Ưng / ❌ Bỏ + 1 dòng góp ý → vào sổ gu.

## Thêm sản phẩm / kho mới (tab 🎁)
1. **➕ Thêm sản phẩm** (tên, cách đọc tên nếu khó đọc, thư mục kho video).
2. **📋 Chép lệnh cho Gemini** → dán cho Gemini: nó xem từng video, ghi mô tả từng cảnh (video mới thì chỉ làm phần mới).
3. **🧩 Chuẩn bị kho** → hub nạp cảnh, cắt ảnh khung, AI soát bằng mắt.
4. **🔍 AI đọc nhãn** → gợi ý sự thật sản phẩm → anh kiểm, sửa → điền quà tặng → **Lưu**.
Đủ sự thật + quà + kho cảnh thì màn Sản xuất tự mở khoá sản phẩm.

## Cài đặt (tab ⚙️)
- Hết hạn mức Claude: app báo đỏ → **Đăng nhập / Đổi tài khoản** → Bắt đầu làm tiếp (video đã xong vẫn giữ).
- Model Opus/Sonnet, mức suy nghĩ, 1 lời đọc dùng cho mấy video.
- Ổ đĩa: hub tự dọn file tạm; video thành phẩm không bao giờ tự xoá.

## Ê-kíp AI làm gì
Biên kịch (12 dạng bài xoay vòng, nhớ câu mở đã dùng) → Giọng ElevenLabs → Đạo diễn (nhìn ảnh cảnh, lên bảng dựng từng câu,
≥ 1/3 đoạn chia khung/ô/khung mờ) → Máy dựng (FFmpeg + Remotion, SFX, nhạc Mixkit, chống reup, làm sạch metadata, ảnh bìa)
→ Giám khảo (chấm điểm, ghi bài học; KHÔNG dựng lại hàng loạt). Sổ bài học tự gom gọn khi dài.

## Thư mục
- `app\` giao diện · `engine\` máy · `luat\` luật sản xuất + mẫu mô tả Gemini · `san-pham\<mã>\` hồ sơ + kho cảnh
- `lich-su\` nhật ký, token, sổ gu, bài học, câu/cảnh đã dùng · `ra\<ngày>\` video thành phẩm
- **Mã** nằm trong repo (`xuong-video\`: `app` · `engine` · `luat` · `remotion` · `mau`). **Dữ liệu của bạn** nằm ở thư mục dữ liệu:
  biến môi trường `XUONG_DATA`, mặc định `du-lieu\xuong-video\` trong thư mục repo (lần đầu tự tạo từ `mau\`):
  `config.json` · `.env` (khoá API) · `san-pham` · `lich-su` · `ra` · `tai-khoan` · `ho-so` ·
  `tai-nguyen/nhac-mixkit` (kho nhạc) · `tai-nguyen/sfx` (hiệu ứng âm thanh). Python venv: `runtime\xuong-venv`.`

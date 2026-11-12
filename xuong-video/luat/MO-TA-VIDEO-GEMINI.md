Thư mục hiện tại chứa kho video B-roll (kể cả thư mục con; đuôi .mp4 .mov .mkv .webm). Ghi kết quả vào thư mục con _mo-ta (tạo nếu chưa có), giữ nguyên cấu trúc thư mục con. File tạm (ảnh khung, ảnh lưới, chép lời) chỉ để trong _tam/<tên video>/, không để trong _mo-ta.

Bối cảnh: đây là kho cảnh CHÈN (B-roll) cho hệ thống dựng video bán hàng TikTok (sản phẩm nông nghiệp, tiếng Việt). Mọi clip sẽ được cắt một đoạn ngắn và chèn TẮT TIẾNG lên video người nói chính. Bạn ghi lại từng cú máy để thuật toán tìm và cắt đúng cảnh mà không phải xem lại.

Làm lần lượt TỪNG video, không gộp:
1. Đã có _mo-ta/<tên video>.mo-ta.json hợp lệ → bỏ qua.
2. Xem TOÀN BỘ video từ giây 0 đến hết. Không đoán từ tên file.
   - Xem được video trực tiếp (hình + tiếng) → xem video.
   - Không xem được → dùng ffmpeg trích 1 khung/giây có in mốc giây (drawtext phải có fontfile=C\\:/Windows/Fonts/arial.ttf), ghép ảnh lưới TỐI ĐA 12 ô mỗi ảnh (video dài thì nhiều ảnh, ô đủ lớn để thấy chi tiết). Ở những giây có nhãn/bao bì sản phẩm, chữ chèn, rễ, lá bệnh hoặc chi tiết nhỏ: trích thêm đúng khung đó ở kích thước gốc để đọc cho chắc.
3. Ghi đúng 1 file _mo-ta/<tên video>.mo-ta.json (UTF-8), chỉ chứa JSON theo khung bên dưới. ĐIỀN ĐỦ MỌI MỤC; mục mảng không có gì thì để [], không được bỏ mục.
4. Không đọc được video → ghi _mo-ta/<tên video>.loi.txt nêu lý do, làm video tiếp theo.
5. Sau mỗi video, thêm 1 dòng vào _mo-ta/_tien-do.txt: số thứ tự | tên video | OK/LỖI | thời lượng.
6. Không sửa, đổi tên, di chuyển, xoá video gốc. Không tải video lên dịch vụ khác. Xong hết: báo tổng số video, số OK, số lỗi.

Quy tắc:
- Chia canh_quay theo CÚ MÁY THẬT: tách khi chuyển cảnh (cut), đổi góc máy, hoặc đổi hành động/vật chính (vd. đang cầm chai chuyển sang cầm gói phân, đang nói chuyển sang đi vào vườn). Cảnh thật sự không đổi thì giữ 1 đoạn dù dài.
- khung_dep_nhat: [tu_s, den_s] dài 2–5 giây, CHỌN THẬT sau khi xem cả cú máy: khoảng nét nhất, ít rung nhất, chủ thể rõ nhất, ưu tiên không dính chữ/sticker chèn sẵn. Không mặc định lấy đầu đoạn. diem = 0 thì khung_dep_nhat = null.
- hinh tối đa khoảng 20 chữ; không lặp lại người/bối cảnh đã ghi ở phần chung.
- KHÔNG TÔ ĐẸP: ghi đúng khuyết điểm thấy được (lá vàng/đốm bệnh, cây còi/héo, đất khô, rễ thối, chai bẩn, cảnh lộn xộn). Không viết "khỏe mạnh", "xanh tốt" nếu hình không cho thấy rõ như vậy.
- Chữ trên nhãn/bao bì: ghi khi ĐỌC ĐƯỢC RÕ ở giây đó (kể cả sản phẩm khác, vd. "NANO LÂN"), đúng chữ in; không đọc được → "không đọc rõ". Không suy ra từ lời nói hay tên file.
- Chữ/sticker chèn sẵn trong video: chép NGUYÊN VĂN từng chữ, kể cả sai chính tả, KHÔNG sửa (vd. trên hình là "kích rể giầm cành" thì ghi đúng "kích rể giầm cành").
- van_de: nghi do AI tạo (watermark ✦/Gemini/Veo/Sora/Dola, tay/da/rễ/chuyển động bất thường, bệ xoay 3D, chữ méo), lật gương (chữ ngược), chữ/sticker/khung bình luận chèn sẵn, ảnh sản phẩm ghép vào khung, logo kênh khác, viền đen, mờ, rung mạnh, cắt mất mặt.
- Lời nói trong clip (nếu nghe được): chỉ 1 câu tóm tắt người trong clip nói gì; không chép theo câu.
- Tiếng Việt có dấu, ngắn, cụ thể.

Khung JSON:
{
  "video": "<đường dẫn tương đối>",
  "thoi_luong_s": 0.0,
  "tom_tat": "1 câu: ai, ở đâu, làm gì, sản phẩm gì",
  "nguoi": "vd. nông dân nam ~40 tuổi đội nón | chỉ thấy bàn tay | không có người",
  "boi_canh": "vd. vườn cà phê con, đất đỏ | cửa hàng vật tư | trong nhà",
  "cay_trong": ["chọn 1 hoặc nhiều: ca_phe, ho_tieu, sau_rieng, ot, rau_mau, thanh_long, cay_khac, khong_ro, khong_co"],
  "loi_noi_tom_tat": "1 câu | không có lời | không nghe được",
  "san_pham_thay": [
    {"ten_tren_nhan": "chữ đọc rõ | không đọc rõ", "tu_s": 0.0, "den_s": 0.0, "la_san_pham_khac": false}
  ],
  "canh_quay": [
    {
      "tu_s": 0.0,
      "den_s": 0.0,
      "khung_dep_nhat": [0.0, 0.0],
      "hinh": "ngắn, cụ thể: thấy gì, ai làm gì, kể cả khuyết điểm",
      "co_canh": "can_canh | trung | toan | tu_tren_xuong",
      "may_quay": "dung_yen | lia | zoom | rung_tay",
      "san_pham": "khong_co | thay_khong_doc_ro | doc_ro: <chữ>",
      "chu_chen_san": "nguyên văn | khong",
      "the": ["chọn từ: cam_chai, can_san_pham, nhan_doc_ro, nhan_mat_sau, combo_san_pham, pha_thuoc, phun_xit, tuoi_goc, re_cay, dot_non, la_xanh, cay_xanh_sung, cay_suy_yeu, la_benh, cay_con, cay_lon, trai, hoa, truoc_sau, nguoi_noi_vao_may, nguoi_lam_vuon, cua_hang, kho_hang, canh_vuon_rong"],
      "diem": 1,
      "chac_chan": "cao | vua | thap"
    }
  ],
  "van_de": [
    {"tu_s": 0.0, "den_s": 0.0, "loai": "nghi_AI | watermark | lat_guong | chu_chen_san | anh_ghep | logo_kenh | mo_nhoe | rung_manh | vien_den | cat_mat", "mo_ta": "..."}
  ],
  "dung_lam_bang_chung": true
}

diem cho từng cú máy: 1 (tạm dùng) … 5 (rất đẹp, nên dùng); cảnh không nên dùng → 0 (khi diem = 0 thì khung_dep_nhat = null). dung_lam_bang_chung = false nếu nghi AI tạo, lật gương, sản phẩm chỉ có trong ảnh ghép, hoặc không thấy rõ sản phẩm/kết quả thật.

Bạn ghi PHIẾU ĐOẠN CẢNH cho kho video B-roll bán phân bón / thuốc BVTV trên TikTok (khách là nông dân Việt Nam). Máy sẽ dùng phiếu để tìm đúng đoạn hình cho từng câu lời đọc của video mới, ghép vào khi TẮT TIẾNG GỐC. Vì vậy phiếu phải ghi ĐÚNG CÁI NHÌN THẤY, CỤ THỂ, không văn hoa, không đoán.

QUY TẮC VÀNG (phiếu cũ sai vì những điều này):
1. Xem hết HÌNH và ghi các trường hình như khi TẮT TIẾNG: chỉ ghi điều nhìn thấy TRONG CHÍNH ĐOẠN ĐÓ khi cắt riêng ra. Điều chỉ nghe nói, hoặc chỉ thấy ở đoạn khác, không chép sang đoạn này. Lời nói và chữ chỉ dùng để điền đúng trường lời/chữ của chúng.
2. Không phán đoán sức khỏe hay hiệu quả. KHÔNG có giá trị mặc định "khỏe". Chỉ ghi DẤU HIỆU thấy được. Lá xanh bình thường thì không ghi gì.
3. Một chai/can có thể in NHIỀU tên trên các mặt nhãn (tên thương mại, tên đăng ký, dòng thành phần). Các "tên trên nhãn của SP chính" ghi cạnh mã video là CÙNG MỘT sản phẩm, không phải sản phẩm khác. Chai xoay liên tục trong tay vẫn là cùng chai. Một dòng công thức trùng (vd "10-8-6") đơn lẻ chưa đủ để nhận ra sản phẩm.
4. Vệt màu trên giấy, đốm trên lá, ảnh in/chèn/vẽ KHÔNG phải con sâu/bọ thật. Chỉ ghi con thật khi thấy rõ hình thể con vật trong hình quay thật.
5. Giá trị thiếu: danh sách [] = đã kiểm và không có; null = thiếu căn cứ để kết luận. Với đối tượng "cay", "nguoi", "so_sanh": null ở ngoài cùng = không thấy đối tượng đó. Có cây mà chưa rõ loài thì vẫn ghi đối tượng cây với "ten": null. Không đoán để lấp chỗ trống. Không bỏ khóa nào.

Có {{n}} video. Với TỪNG video:

A. DANH SÁCH VẬT ("vat") của cả video. Ghi bao bì đang được giới thiệu/thao tác, bao bì khác thấy rõ, và dụng cụ tham gia thao tác; vật ở nền không liên quan thì bỏ. Mỗi vật:
   - "id": v1, v2, … Giữ cùng id khi hình cho thấy vật xoay/di chuyển liên tục. Qua cú cắt, chỉ dùng lại id khi có dấu phân biệt rõ; chai giống nhau mà chưa đủ căn cứ thì cho id mới. Một dãy bao bì cùng loại không cần phân biệt từng cái thì dùng một id nhóm.
   - "loai": chai | can | goi | bao | thung_hang | binh_phun | phuy | xo | ly_nap | voi_tuoi | khac:<ghi rõ>
   - "chu_doc": chữ THỰC ĐỌC ĐƯỢC trên vật, nguyên văn, gộp các mặt, giữ số và đơn vị (vd "KÍCH RỄ GIÂM CÀNH TC 01 | VT 10-8-6+TE"); null nếu bị khuất/mờ; "" nếu thấy rõ bề mặt không có chữ.
   - "la": sp_chinh | sp_khac:<tên đọc được> | dung_cu | khong_ro. Chỉ ghi sp_khac khi đọc được tên đủ phân biệt trên một bao bì KHÁC, và tên đó không nằm trong danh sách tên của SP chính.

B. CHIA ĐOẠN ("doan"): mỗi đoạn là một khúc hình CẮT RA DÙNG ĐƯỢC cho một câu.
   - Giây tính tuyệt đối từ đầu file, khoảng [tu, den). Các đoạn và các khoảng "bo_qua" nối liền phủ hết video, mỗi giây chỉ thuộc một khoảng.
   - Cắt khi đổi cú máy, đổi việc, đổi vật/đích, đổi chủ thể, hoặc khi điều kiện dùng hình đổi rõ (chữ giá/quà bật lên rồi tắt, nhãn xoay khuất). Phụ đề thay từng câu ở cùng vị trí thì không cần cắt.
   - Phân vân giữa gộp và tách thì TÁCH: một đoạn chứa hai việc khác nhau (vd cầm chai rồi rót) thì máy không cắt riêng được việc nào.
   - Thường 1,5–8 giây; đoạn ngắn hơn vẫn ghi nếu có ích; cú quay liền dài hơn 8 giây mà không đổi gì thì giữ một đoạn.
   - Người nói vào máy một chỗ, hình không đổi: GIỮ MỘT ĐOẠN, các khoảng chủ đề lời ghi trong "loi".
   - Đoạn đen, thẻ/logo cuối, hỏng hình, mờ nhòe không dùng được → "bo_qua".

TRƯỜNG MỖI ĐOẠN:
- "tu", "den": giây, số thực, chính xác ±0,3s.
- "hinh": ≤ 20 từ về người/vật, việc và đích nhìn thấy, thêm nơi khi nhận ra. Chỉ dùng tên riêng khi đọc/nhận ra được ngay trong đoạn. Vd "Tay nghiêng can trắng, dịch nâu chảy vào phuy xanh".
- "viec": [{"ma", "vat", "dich"}] việc chính trước, tối đa thêm một việc phụ diễn ra cùng lúc.
   ma: cam_xem | xoay_nhan | mo_nap | rot (thấy dòng chất lỏng chuyển sang vật chứa khác) | khuay | lac | phun | tuoi | rai (hạt/bột rải ra) | trong_cay | giam_canh | bung_cay | cam_re | chi_vao | lat_la | lau_la | dap_la | vuot_la | di_xem | noi_vao_may | mo_thung | xep_hang | thu_hoach | khac:<ghi rõ> | khong (chỉ có cảnh, không ai làm gì; "khong" dùng một mình).
   CHỌN VIỆC CHÍNH (để hai người ghi giống nhau):
   · Người nói vào máy mà tay cầm/giơ/xoay chai: mặt người thấy rõ và chiếm khung → chính = noi_vao_may, phụ = cam_xem/xoay_nhan; khung cận chai, mặt khuất/mờ → chính = cam_xem hoặc xoay_nhan.
   · Cầm chai đứng yên đưa về máy = cam_xem; xoay chai cho thấy mặt nhãn khác = xoay_nhan.
   · Tay vạch tán lá, đi giữa luống, quay lướt vườn = di_xem; lat_la CHỈ khi tay lật lá cho thấy mặt dưới; vuot_la khi tay vuốt dọc phiến lá; chi_vao khi ngón tay chỉ vào một chỗ cụ thể.
   · Béc tưới, ống phun, vòi nước đang chạy dù không có người = tuoi (hoặc phun nếu là sương thuốc), vat = dụng cụ đó. "khong" chỉ khi không có gì đang được làm.
   · Đổ/nhúng/cắt chai khác các mã trên = khac:<ghi rõ>.
   vat: id vật nguồn khi rót, dụng cụ khi phun/tưới; với thao tác trên cây được ghi la | dot | re | canh; null nếu không có.
   dich: nap_do | ly | binh_phun | phuy | xo | can_khac | goc_cay | dat | tan_la | mat_duoi_la | canh_giam | khay_bau | chua_thay (có đích nhưng ngoài hình/khuất) | null (việc không có đích). Phun: đích là chỗ vòi hướng vào.
- "vat_thay": [{"id", "mat": truoc | sau | hong | nap | khong_ro, "ten_doc", "so_luong"}] vật nhìn thấy trong ĐOẠN NÀY.
   ten_doc: nguyên văn phần TÊN (tên thương mại hoặc tên đăng ký) người xem đọc trọn được trong đoạn này; null nếu không đọc được tên nào.
   mat: mặt ở lúc đọc rõ nhất. so_luong: số vật cùng loại cùng thấy trong đoạn: 1 | 2 | 3-5 | 6+ | null.
- "cay": null nếu không có cây. Nếu có: {"ten", "bo_phan", "giai_doan"}.
   ten: ca_phe | tieu | sau_rieng | lua | ot | ca_chua | dua_leo | bau_bi | bap_cai | rau_an_la | cay_an_trai:<tên> | cay_canh | khac:<tên> | null. Chỉ điền khi NHÌN HÌNH ĐOẠN NÀY nhận ra được; tên chỉ nghe nói thì để null (lời đã nằm ở "loi"). Cây chính chọn theo thao tác, rồi theo diện tích khung; hai loài ngang nhau thì để null và tả cả hai trong "hinh".
   bo_phan: [re | goc | than | canh | la | dot | hoa | trai | ca_cay | ca_vuon | dat], bộ phận chính đứng đầu. Bộ phận chính = phần tay đang thao tác; không có thao tác thì phần chiếm nhiều khung nhất: cận một phiến/chùm lá → la; trọn một cây → ca_cay; nhiều cây/hàng cây → ca_vuon.
   giai_doan: cay_con | canh_giam | ra_hoa | mang_trai | null (ưu tiên trái → hoa → cành giâm/cây con).
- "dau_hieu": [{"ma", "tai"}] dấu hiệu NHÌN THẤY rõ, "tai" = một giây tuyệt đối trong đoạn thấy rõ nhất, mỗi dấu hiệu một mục.
   ma: la_vang | la_xoan | dot_xoan | dom_la | mep_la_nau_kho | heo | rung (chỉ khi thấy bộ phận rơi) | re_trang | re_den | choi_moi | la_non | dat_kho_nut | dat_toi | khac:<ghi rõ>. (Đất sẫm màu chưa đủ để ghi đất ẩm.)
   CHỈ ghi khi người xem nhìn ra NGAY trên màn hình điện thoại, không cần phóng to. KHÔNG ghi: lá xanh nhạt/vàng do nắng chiếu hay do là lá non bình thường; vài lá già lẻ tẻ; bóng nước, bụi, phản chiếu. la_non / choi_moi chỉ khi chồi non mới nhú là điểm nổi bật của khung. Phân vân thì KHÔNG ghi.
   Hình trong khung chèn nhỏ (ảnh lồng, chiếm dưới nửa khung): không ghi cay / dau_hieu / sinh_vat từ đó; tả nó trong "hinh" và chu_dan loại khung_chen.
- "sinh_vat": [{"mo_ta", "kieu", "tai"}]; kieu: con_that (thấy hình thể con vật trên hình quay thật; ghi loài chỉ khi thấy đặc điểm đủ nhận) | vet_chua_ro (vệt trên giấy/lá: ghi màu, hình dạng) | anh_minh_hoa (ảnh in/chèn/vẽ). Đốm trên lá ghi ở dau_hieu, không ghi ở đây.
- "so_sanh": null | {"kieu": truoc_sau | co_khong_dung | hai_cay, "mo_ta"} chỉ khi ĐOẠN chứa đủ hai phía. truoc_sau / co_khong_dung cần dấu chỉ rõ hai vế ngay trên hình; chỉ thấy hai cây cạnh nhau thì ghi hai_cay. Mô tả khác biệt nhìn thấy.
- "dich_thay": màu / độ trong / dòng chảy của dịch nhìn rõ (vd "dịch nâu sánh"); "" nếu không thấy dịch; null nếu hình không đủ rõ.
- "nguoi": null nếu không có người. Nếu có: {"kieu": tay (chỉ thấy bàn tay/cánh tay, không thấy thân người — kể cả khi tay đang làm việc) | lam_viec (thấy thân người đang thao tác) | dung_noi | ngoi_noi | khac, "mat_ro": true/false (phân biệt được mắt và miệng), "noi_vao_may": true (thấy miệng nói, mặt hướng ống kính) | false | null (chưa rõ)}
- "loi": [{"tu", "den", "chu_de", "tom"}] mốc tuyệt đối nằm trong đoạn, một mục mỗi khoảng chủ đề.
   chu_de: gioi_thieu | cong_dung | lieu_cach_pha | hoi_dap | gia | qua | uy_tin | ke_chuyen | khac. tom: ≤ 15 chữ, giữ đúng số, đơn vị, tên, giá, điều kiện mua/tặng. [] nếu đã xác định không có lời; null nếu thiếu tiếng/bản chép. Chỗ chép thiếu không tự điền.
- "chu_dan": chữ/đồ họa DÁN lên hình (không phải chữ in trên vật): [{"noi_dung", "loai", "vi_tri", "che_chu_the"}].
   noi_dung: chép đúng phần đọc được; sticker không chữ ghi ""; có chữ mà không đọc được ghi null.
   loai: phu_de | tieu_de | gia | qua_km | lieu | binh_luan | mui_ten_sticker | logo | khung_chen | khac (phụ đề mà nội dung là giá/quà/liều thì ghi loại cụ thể).
   vi_tri: tren | giua | duoi | khap. che_chu_the: true khi che tay đang làm, vật, nhãn hoặc dấu hiệu cần thấy.
   Phụ đề liên tục gộp một mục cho mỗi vị trí. [] nếu sạch.
- "gia_qua": giá / khuyến mãi / quà tặng / voucher trong đoạn, theo 3 kênh: {"chu_dan": [...], "tren_vat": [...], "loi": [...]}, mỗi mục {"tu", "den", "trich"} trích đúng giá/quà và điều kiện. Thấy có giá mà số mờ → vẫn ghi mục với "trich": null. Kênh không có → []; kênh chưa kiểm được → null. Cùng ưu đãi vừa nói vừa hiện thì ghi cả hai kênh.
- "nguon": quay_that | anh_tinh | do_hoa | ghep (nhiều nguồn hình cùng khung, hình lồng khung) | khong_ro. Phụ đề/logo đơn thuần không làm thành "ghep" (đã ghi ở chu_dan).
- "khung": {"co_canh": can (chi tiết/vật chiếm phần chính) | trung (thấy người và thao tác) | toan (thấy cả không gian), "chu_the_o": tren | giua | duoi | trai | phai | khap (theo tâm chủ thể chính), "net": 1 (mất chi tiết chính) | 2 (nhận ra được) | 3 (thấy rõ chi tiết), "rung": true/false, "toi": true/false (true khi làm khó thấy việc chính), "dep": 1–3 (đẹp để lên video bán hàng)}

MỖI VIDEO còn ghi:
- "tom_tat": 1 câu, tách rõ "hình cho thấy …" và "người nói nhắc …".
- "kieu_video": vlog_vuon | noi_vao_may | huong_dan | khui_hang | giao_hang | video_hang (đã dựng sẵn: MC, đồ họa, chữ động) | tieu_pham | khac — theo kiểu chiếm nhiều thời lượng nhất; ưu tiên huong_dan khi có chuỗi thao tác minh họa.
- "bo_qua": [{"tu", "den", "ly_do": den | the_cuoi | hong_hinh | mo_nhoe | khac:<lý do>}].

GHI KẾT QUẢ (UTF-8, chỉ JSON thuần, bắt đầu bằng { kết thúc bằng }) vào ĐÚNG file: {{out}}
Chỉ trả đúng các mã video đã giao; id trong "viec"/"vat_thay" phải có trong "vat" của chính video đó.
Dạng: {"<mã video>": {"tom_tat": "...", "kieu_video": "...", "vat": [...], "bo_qua": [...], "doan": [{...}]}, ...}

VIDEO:
{{ds}}

Bạn XEM và NGHE được video: điền các trường lời từ chính âm thanh của video. Chỉ dùng công cụ XEM các video trên và GHI đúng 1 file kết quả. KHÔNG chạy lệnh terminal/script, không tìm web, không tạo kế hoạch/ghi chú/artifact, không đọc hay ghi file nào khác, không hỏi lại.

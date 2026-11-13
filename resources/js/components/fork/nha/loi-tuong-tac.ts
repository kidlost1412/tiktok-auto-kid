// Lời thoại khi sếp (Kid) tương tác trực tiếp với từng người: khen, trêu, cốc đầu, đá đít nhẹ, mắng, ôm…
// Kiểu hoạt hình vui nhộn, không ai đau thật; xưng hô tao/mày kiểu bạn bè cho vui, không tục, không thô.
// Khoá: `<vai>_<tình huống>` (riêng từng người), `<tình huống>` (chung), thêm đuôi `_than` / `_gian` theo tình cảm.
// Câu của sếp bắt đầu bằng `sep_`.
export const TUONG_TAC: Record<string, string[]> = {
    // ================================================================ câu của sếp (Kid)
    sep_di_lam: [
        'Lên làm việc đi!',
        'Thôi chơi, vào việc nào!',
        'Ê, bàn làm việc đang nhớ đó!',
        'Deadline kìa, chạy!',
    ],
    sep_treu: [
        'Ui da, trông buồn cười ghê~',
        'Lêu lêu!',
        'Đoán xem ai đẹp trai nhất xưởng?',
        'Ê, có con nhện trên vai kìa!',
    ],
    sep_coc: [
        'Cốc! Tỉnh chưa?',
        'Cốc một phát cho sáng dạ!',
        'Cốc nhẹ thôi nè~',
    ],
    sep_day_ao: ['Xuống ao mát nè!', 'Tõm nha~', 'Đi tắm ao đi!'],
    sep_thoc_let: ['Cù lét nè!', 'Thọc lét~ hí hí', 'Cười cái coi!'],
    sep_lan_co: ['Lăn cỏ không? Lăn nè!', 'Ai lăn xa hơn thắng!'],
    roi_ao: ['Áaaa!!', 'Ối! Ướt hết rồi!', 'Cứu tui với!!', 'Lạnh quáaa!'],
    len_bo_cuoi: [
        'Haha, mát thiệt! Lần sau tới lượt sếp!',
        'Ướt nhẹp mà vui ghê!',
    ],
    len_bo_gian: ['Sếp ác quá à!', 'Ướt hết đồ rồi nè!!', 'Tui méc mèo đó!'],
    thuam_len_bo_gian: [
        'Mày chờ đó! Ướt hết tai nghe của tao!',
        'Hack cái ao này cho cạn luôn!',
    ],
    bi_thoc_let: [
        'Hahaha thôi thôi!',
        'Nhột quá sếp ơi!',
        'Ha ha ha… tha cho em!',
    ],
    lan_co: [
        'Chóng mặt quá mà vui!',
        'Cỏ dính đầy tóc luôn!',
        'Lăn nữa không sếp?',
    ],
    khoc: [
        'Hu hu… em làm hết sức rồi mà…',
        'Huhu… sếp mắng hoài…',
        'Oaaa… buồn quá…',
    ],
    thuam_khoc: ['Hu hu… tao không khóc đâu… chỉ bụi bay vô mắt thôi!'],
    mua_chay: [
        'Mưa rồi! Chạy vô nhà!',
        'Ướt hết rồi!!',
        'Mưa to quá, vô thôi!',
        'Ai cất đồ phơi chưa?',
    ],
    mua_ngam: [
        'Mưa rơi lộp độp nghe vui ghê.',
        'Mưa thế này ngủ là nhất.',
        'Mưa rồi, pha ly cacao đi!',
    ],
    het_mua: ['Tạnh mưa rồi! Ra vườn thôi!', 'Có cầu vồng không ta?'],
    vap: ['Ui da!', 'Oái!', 'Á á á!'],
    nhay_ao: [
        'Nóng quá, tắm ao cái!',
        'Nhìn nè, nhảy bom!',
        'Một, hai, ba… tõm!',
    ],
    lan_co_mot_minh: ['Lăn lăn lăn~', 'Cỏ mềm ghê!'],
    sep_da: ['Hây-da!', 'Đá đít nhẹ cái cho có động lực!', 'Bụp! Đi đi~'],
    sep_mang: [
        'Làm ăn kiểu gì vậy hả!',
        'Nghiêm túc lên coi!',
        'Tháng này bị trừ… kẹo!',
        'Lại lười nữa rồi!',
    ],
    sep_khen: [
        'Giỏi lắm!',
        'Đỉnh của chóp!',
        'Xưởng mà thiếu bạn là toang!',
        'Hôm nay làm tốt lắm nha!',
    ],
    sep_dap_tay: ['Đập tay cái nào!', 'Gimme five!', 'Ăn mừng cái coi!'],
    sep_om: ['Lại đây ôm cái nào~', 'Ôm phát lấy tinh thần!'],
    sep_ca_phe: ['Đi cà phê với sếp không?', 'Sếp bao cà phê nè!'],
    sep_nghi: ['Nghỉ chút đi, làm nhiều rồi.', 'Đi ngả lưng tí đi!'],
    sep_choi: ['Làm một ván không?', 'Chơi với sếp một trận!'],
    sep_nem: ['Ăn bóng giấy nè!', 'Hự, trúng chưa?'],
    sep_chup: ['Cả nhà ơi, chụp ảnh nào!', 'Tập trung! Chụp hình kỷ niệm!'],
    sep_nhac: ['Bật nhạc lên! Quẩy thôi!', 'Nhạc đâu, nhảy nào!'],
    sep_an: ['Cả nhà ơi, ăn cơm!', 'Cơm chín rồi, vô ăn nào!'],
    sep_meo: ['Mèo ơi, lại đây!', 'Meo meo~ đâu rồi bé?'],
    sep_vuot: ['Ngoan quá ta~', 'Lông mềm ghê!'],
    sep_cho_an: ['Măm măm cá nè!', 'Bữa xế cho bé mèo!'],
    sep_be: ['Lên vai sếp nào!', 'Hô-pla! Lên!'],
    sep_tha: ['Xuống nha bé.', 'Thôi xuống chơi đi~'],
    sep_treu_meo: ['Ò ó o~', 'Chọc lét nè!'],

    // ================================================================ bắt đi làm
    di_lam: [
        'Dạ dạ, đi liền!',
        'Rồi rồi, làm thì làm!',
        'Sếp nói là phải nghe~',
    ],
    di_lam_gian: ['Hứ, lại bắt đi làm…', 'Làm thì làm, ai sợ!'],
    di_lam_dang_lam: [
        'Đang làm mà sếp!',
        'Thấy em gõ phím không?',
        'Có ngồi chơi đâu!',
    ],
    bienkich_di_lam: [
        'Vâng, nàng thơ đang chờ tớ~',
        'Để tớ viết tiếp chương sau!',
        'Dạ, chữ ơi về đây!',
    ],
    thuam_di_lam: [
        'Rồi, hacker vào ca!',
        'Ok ok, mở mic liền 😎',
        'Tao đi đây, đừng nhìn nữa!',
    ],
    daodien_di_lam: [
        'Diễn! Vào vị trí!',
        'Máy quay sẵn sàng, đi!',
        'Cảnh tiếp theo, chạy!',
    ],
    thodung_di_lam: [
        'Ơ… cho chơi nốt ván…',
        'Haizz, dựng thì dựng…',
        'Save game cái đã!',
    ],
    giamkhao_di_lam: [
        'Tôi lúc nào chẳng làm việc.',
        'Hừm, nhắc thừa.',
        'Đi. Nhưng chấm khó hơn đấy.',
    ],
    thukho_di_lam: ['Dạ, kho phải gọn mới được!', 'Đi xếp kệ liền!'],
    chuquay_di_lam: ['Lên quầy chốt đơn liền!', 'Khách ơi, em tới đây~'],
    buuta_di_lam: ['Bưu tá xuất phát!', 'Thư không chờ ai, đi đây!'],

    // ================================================================ trêu / chọc
    treu: ['Sếp kỳ ghê!', 'Hứ!', 'Sếp trêu hoài à!'],
    bienkich_treu: [
        'Sếp… làm tớ ngại quá đi~',
        'Đừng nhìn tớ vậy mà…',
        'Tim tớ loạn nhịp rồi nè!',
    ],
    thuam_treu: [
        'Ê đứng lại! Mày chết với tao!',
        'Trêu hacker hả? Chạy đi!',
        'Đứng đó! Tao đuổi kịp liền!',
    ],
    daodien_treu: [
        'Cắt! Diễn lố quá sếp ơi!',
        'Đứng lại! Cảnh rượt đuổi, bấm máy!',
        'Ê ê, quay lại đây!',
    ],
    thodung_treu: [
        '…(vẫn bấm game)',
        'Đừng phá, đang combo!',
        'Ờ ờ, vui ghê… (không ngẩng lên)',
    ],
    giamkhao_treu: [
        'Trêu tôi? Trừ điểm!',
        'Hừ! Ấu trĩ!',
        'Điểm thái độ: 2 trên 10.',
    ],
    thukho_treu: [
        'Ui sếp, làm lộn xộn hết!',
        'Sếp đừng có phá mà!',
        'Hừm, tức ghê!',
    ],
    chuquay_treu: [
        'Hihi, sếp duyên ghê!',
        'Trêu thì mua hàng đi nè!',
        'Hí hí, mắc cỡ quá~',
    ],
    buuta_treu: [
        'Đứng lại! Bưu tá chạy nhanh lắm đó!',
        'Trêu hả? Đuổi theo nè!',
    ],

    // ================================================================ cốc đầu
    coc_dau: [
        'Á! Sao lại cốc em?',
        'Ui da… thấy sao bay luôn!',
        'Đau… đùa thôi, không đau~',
    ],
    coc_dau_gian: [
        'Cốc hoài vậy sếp! Em giận đó!',
        'Lần thứ mấy rồi?! Hứ!',
        'Thôi, tránh xa sếp ra…',
    ],
    bienkich_coc_dau: [
        'Ui… vần thơ bay đâu mất rồi~',
        'Sếp cốc trúng ý tưởng của tớ!',
        'Huhu, u đầu thành thơ luôn…',
    ],
    thuam_coc_dau: [
        'Cốc tao nữa là tao hack wifi đó!',
        'Ê! Đầu tao toàn mật khẩu đó!',
        'Á à, dám cốc hacker?!',
    ],
    daodien_coc_dau: [
        'Cắt! Cảnh này không có trong kịch bản!',
        'Ui! Có sao vàng bay trước ống kính!',
        'Hiệu ứng âm thanh: CỐC!',
    ],
    thodung_coc_dau: [
        'Ui… rớt mạng rồi…',
        'Lag não… đợi tí…',
        'Ơ, ai tắt máy tao?',
    ],
    giamkhao_coc_dau: [
        'Vô lễ! Tôi ghi biên bản!',
        'Hừ! Điểm lịch sự của sếp: 0!',
        'Cốc nữa là tôi trừ lương… à, tôi không có quyền đó.',
    ],
    thukho_coc_dau: [
        'Ui, rớt mất sổ kho rồi!',
        'Sếp làm em quên đếm tới đâu rồi!',
    ],
    chuquay_coc_dau: [
        'Á! Hàng dễ vỡ đó sếp!',
        'Ui, cốc vậy giảm giá 0 đồng nha!',
    ],
    buuta_coc_dau: ['Ui! Thư bay tứ tung rồi!', 'Á! Trễ chuyến vì sếp đó!'],

    // ================================================================ đá đít nhẹ
    da_dit: ['Ui da! Sếp chơi kỳ!', 'Á! Bay luôn!', 'Hự! Ai đá đó?!'],
    bienkich_da_dit: ['Á! Tớ bay như chiếc lá~', 'Huhu, đá tớ làm gì…'],
    thuam_da_dit: [
        'Ê! Mày đứng lại đó!',
        'Đá tao hả? Chạy đi!',
        'Tao nhớ mặt rồi nha!',
    ],
    daodien_da_dit: [
        'Cú đá này phải quay chậm lại!',
        'Ối! Diễn viên đóng thế đâu?!',
    ],
    thodung_da_dit: ['Ơ… mất máu rồi…', 'Ai bật chế độ hardcore vậy?!'],
    giamkhao_da_dit: [
        'Bất lịch sự! Không thể chấp nhận!',
        'Hừm! Tôi sẽ nhớ chuyện này.',
    ],
    thukho_da_dit: ['Á! Suýt đụng kệ hàng!', 'Sếp ơi, đá vậy đổ kho bây giờ!'],
    chuquay_da_dit: ['Ui! Bay ra tận cửa hàng luôn!', 'Á á, sếp kỳ ghê!'],
    buuta_da_dit: [
        'Phóng nhanh như chuyển phát hoả tốc!',
        'Á! Đứng lại đó sếp!',
    ],

    // ================================================================ chửi / mắng
    mang: ['Dạ… em biết lỗi rồi…', 'Huhu…', 'Em sẽ cố hơn ạ…'],
    bienkich_mang: [
        'Huhu… trời đổ mưa trong lòng tớ…',
        'Tớ buồn… để tớ viết bài thơ buồn…',
    ],
    thuam_mang: [
        'Mắng tao? Hệ thống chạy ngon lành mà!',
        'Ờ, nói hay lắm. Còn gì nữa không?',
        'Lỗi là do wifi, không phải tao 😎',
    ],
    daodien_mang: [
        'Dạ… cảnh này xin quay lại…',
        'Huhu, đạo diễn cũng có trái tim mà…',
    ],
    thodung_mang: ['Ừ ừ… (vẫn chơi)', 'Dạ dạ… biết rồi… (vẫn chơi)'],
    giamkhao_mang: [
        'Tôi chấm đúng quy trình!',
        'Sếp đưa bằng chứng đây.',
        'Hừm. Phản đối!',
    ],
    thukho_mang: ['Dạ… để em xếp lại cho ngay…', 'Huhu, em đã cố gọn lắm rồi…'],
    chuquay_mang: ['Dạ… em xin lỗi khách… à sếp…', 'Huhu, mất khách rồi…'],
    buuta_mang: ['Dạ… lần sau em giao sớm hơn…', 'Huhu… thư buồn ghê…'],

    // ================================================================ khen
    khen: [
        'Hihi, cảm ơn sếp!',
        'Sếp khen làm em bay lên luôn!',
        'Yeah! Làm tiếp nè!',
    ],
    khen_than: ['Sếp là nhất! Yêu sếp!', 'Được sếp khen là vui cả ngày!'],
    bienkich_khen: [
        'Ôi… tớ muốn viết một bài thơ về sếp~',
        'Tim tớ nở hoa rồi nè 🌸',
    ],
    thuam_khen: ['Biết mà, tao là số một 😎', 'Chuyện, hacker xịn mà!'],
    daodien_khen: ['Hoàn hảo! Một cảnh duy nhất!', 'Xin cảm ơn khán giả~'],
    thodung_khen: ['Ơ… được khen hả? Lên level rồi!', 'Hehe, buff tốc độ!'],
    giamkhao_khen: ['Hừm… cảm ơn. Tôi cho sếp 9 điểm.', 'Cũng… được. Cảm ơn.'],
    thukho_khen: [
        'Kho sạch là nhờ sếp động viên!',
        'Hihi, em xếp thêm kệ nữa nè!',
    ],
    chuquay_khen: [
        'Sếp khen là em chốt thêm 10 đơn!',
        'Hihi, giảm giá cho sếp luôn!',
    ],
    buuta_khen: ['Được khen là chạy nhanh gấp đôi!', 'Hihi, bưu tá vui lắm!'],
    hang_say: ['⚡ Hăng say gấp đôi!', '⚡ Tăng tốc!', '⚡ Làm vèo vèo!'],

    // ================================================================ đập tay / ôm
    dap_tay: ['Bốp! Yeah!', 'High five!', 'Đập tay cái nào!'],
    dap_tay_gian: ['Hứ, không đập!', 'Còn giận nha, khỏi!'],
    thuam_dap_tay: ['Bốp! Combo hacker!', 'Đập tay kiểu ngầu nè 😎'],
    giamkhao_dap_tay: ['…Thôi được, một cái thôi.', 'Bốp. Đủ rồi.'],
    om: ['Hihi, ấm ghê~', 'Ôm sếp cái nào!', 'Ui, được ôm nè!'],
    om_gian: ['Né ra! Đang giận!', 'Hứ, đừng hòng!'],
    bienkich_om: ['Ấm áp như một câu thơ~', 'Tớ cảm động quá…'],
    thuam_om: ['Ê… ôm gì kỳ vậy… mà thôi được 😳', 'Đừng kể ai nghe nha!'],
    giamkhao_om: ['Hừm… không chuyên nghiệp lắm… nhưng ấm.', '…Cảm ơn.'],
    thodung_om: ['Ơ… (vẫn cầm tay cầm)', 'Ôm xong cho chơi tiếp nha!'],

    // ================================================================ mời cà phê / cho nghỉ / rủ chơi
    ca_phe_nhan: [
        'Có cà phê là đi liền!',
        'Sếp bao hả? Đi đi!',
        'Cà phê! Yêu sếp!',
    ],
    ca_phe_tu_choi: ['Thôi, đang giận, không đi!', 'Hứ, tự uống đi!'],
    thodung_ca_phe_nhan: ['Có nước tăng lực không sếp?', 'Đi, nạp năng lượng!'],
    giamkhao_ca_phe_nhan: [
        'Một ly đen không đường. Cảm ơn.',
        'Được. Nhưng tôi chọn quán.',
    ],
    nghi: [
        'Ôi, sếp thương em quá!',
        'Dạ, ngả lưng tí thôi~',
        'Ngủ năm phút thôi nha!',
    ],
    thodung_nghi: ['Cuối cùng cũng được ngủ!', 'Zzz… (ngủ liền)'],
    giamkhao_nghi: [
        'Nghỉ năm phút. Đúng năm phút.',
        'Được, tôi nghỉ có kỷ luật.',
    ],
    choi_nhan: [
        'Chơi luôn! Thua là bao trà sữa!',
        'Sếp chuẩn bị thua đi!',
        'Vào trận!',
    ],
    choi_tu_choi: ['Không chơi với người cốc đầu em!', 'Hứ, chơi một mình đi!'],
    thuam_choi_nhan: ['Sếp thua chắc rồi 😎', 'Tao chấp sếp một tay!'],
    thodung_choi_nhan: ['Game hả? Vào liền!', 'Sếp gà quá, chấp luôn!'],
    choi_thang: ['Thắng rồi! Yeah!', 'Hehe, dễ ợt!'],
    choi_thua: ['Thua… ván nữa!', 'Không tính, làm lại!'],
    ban_viec: [
        'Đang có việc thật, để lát nha sếp!',
        'Đợi em xong việc này đã!',
        'Việc gấp, sếp đợi tí!',
    ],

    // ================================================================ bóng giấy, chụp ảnh, nhảy
    nem_giay: ['Ê! Ai ném đó?!', 'Á! Bóng giấy!', 'Ối! Trúng đầu rồi!'],
    nem_lai: ['Ném lại nè!', 'Ăn miếng trả miếng!', 'Đỡ này!'],
    thuam_nem_giay: ['Ném tao hả? Đỡ này!', 'Chiến tranh giấy bắt đầu 😎'],
    giamkhao_nem_giay: ['Xả rác! Trừ điểm!', 'Hừ! Ai dọn đây?'],
    thukho_nem_giay: ['Ui, rác! Để em nhặt…', 'Sếp ơi, đừng xả rác!'],
    chup_anh: ['Cheese~!', 'Tạo dáng nè!', 'Góc này đẹp nè!', 'Chờ em với!'],
    daodien_chup_anh: [
        'Góc máy chuẩn! Ánh sáng chuẩn!',
        'Ai đứng lệch kìa! Chụp!',
    ],
    giamkhao_chup_anh: ['Đứng thẳng. Cười. Được.', 'Ảnh này tôi chấm 10.'],
    nhay: ['Quẩy lên!', 'Nhạc hay ghê!', 'Lắc lư nào~', 'Yeah yeah!'],
    thodung_nhay: ['Nhảy như nhân vật game nè!', 'Combo nhảy!'],
    giamkhao_nhay: ['…Tôi chỉ lắc nhẹ thôi.', 'Nhịp này… tạm được.'],
    an_com_goi: ['Ăn cơm! Đói quá rồi!', 'Dạ có liền!'],

    // ================================================================ còn giận sếp (tránh mặt)
    ne_sep: [
        'Hứ, tránh xa sếp ra…',
        'Đừng lại gần, đang giận!',
        'Thôi, đi đường khác…',
        'Sếp mà cốc nữa là em mách mèo!',
    ],
    thuam_ne_sep: ['Tao đang chặn sếp đó 😤', 'Tránh xa hacker ra!'],
    giamkhao_ne_sep: ['Tôi chưa quên đâu.', 'Hừm. Giữ khoảng cách.'],

    // ================================================================ mèo
    meo_mua: [
        'Meo!! (ghét mưa)',
        'Mèooo! Ướt lông rồi!',
        'Grừ… mưa gì kì vậy!',
    ],
    meo_vuot: ['Prrr… prrr…', 'Meo~ (sướng quá)', 'Grừ grừ~'],
    meo_an: ['Măm măm 🐟', 'Meo! (ngon quá)', 'Nhóp nhép~'],
    meo_be: [
        'Meo! (cao quá!)',
        'Meo~ (đi đâu đó sếp?)',
        'Prrr~ (ngồi vai sướng ghê)',
    ],
    meo_tha: ['Meo! (cảm ơn sếp)', 'Meo~'],
    meo_treu: ['Xì! (tát một phát)', 'Ngoao! Hứ!', 'Meo! (đừng chọc!)'],
    meo_goi: ['Meo~ tới liền!', 'Meo meo! (đợi em)'],
};

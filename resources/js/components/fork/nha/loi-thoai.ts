// Lời thoại của từng nhân vật theo tình huống, dễ sửa tại một chỗ. Mỗi tình huống 3-6 câu, chọn ngẫu nhiên.
// Chỗ có {diem}, {loi}... sẽ được thay bằng số liệu thật. Giữ vui, hơi tinh nghịch, không chửi thề.
export const LOI_THOAI: Record<string, string[]> = {
    // Biên kịch: nhà thơ mơ mộng
    bienkich_giao: [
        'Câu này hay quá trời…',
        'Mực còn ướt, cầm nhẹ thôi nha.',
        'Giao hàng văn chương đây ✍️',
        'Viết xong rồi, lòng nhẹ hẫng…',
        'Mỗi con chữ là một giấc mơ nhỏ.',
    ],
    bienkich_nhan: [
        'Gửi bạn một bài thơ… à, lời đọc!',
        'Đọc cho có hồn nha.',
        'Vần điệu ổn chưa nhỉ?',
        'Tôi viết cả đêm đó.',
    ],
    // Thu âm: hacker DJ tự tin quá mức
    thuam_nhan: [
        'Để đó, hacker lo.',
        'Nhận kịch bản. Bắt đầu “xâm nhập” giọng!',
        'Mic sẵn sàng 🎤',
        'Chữ đẹp đó nha, ghi âm liền.',
    ],
    thuam_hack: [
        'Hacker đây, nhận tín hiệu đi!',
        'Tải giọng xong, 0,3 giây thôi 😎',
        'Bíp bíp… truyền xong!',
        'Đã xâm nhập kho âm thanh. Thành công!',
        'Gõ phím cái là xong.',
    ],
    // Đạo diễn: hai nghệ sĩ cãi nhau rồi đập tay
    daodien_cai_a: [
        'Phải cận cảnh!',
        'Cảnh này phải chậm lại!',
        'Màu ấm mới đúng!',
    ],
    daodien_cai_b: [
        'Không, toàn cảnh!',
        'Nhanh mới cuốn!',
        'Màu lạnh mới sang!',
    ],
    daodien_hoa: [
        'Thôi được, hoà! 🙌',
        'Lần này tôi nhường.',
        'Đồng ý! Đập tay nào!',
    ],
    daodien_giao: [
        'Bảng dựng nóng hổi, nhận đi!',
        'Cận cảnh nha, nhớ đó!',
        'Nghệ thuật là phải đau khổ… giao đây.',
        'Cắt sai là tôi khóc đó.',
    ],
    daodien_nhan_lai: [
        'Hả?! Lại nữa à…',
        'Ghi nhận phê bình. Sửa liền.',
        'Dựng lại… nhưng tôi vẫn thấy mình đúng.',
    ],
    // Thợ dựng: game thủ buồn ngủ nhưng nhanh
    thodung_nhan: [
        'Render… 99%… xong!',
        'Nhận! Để tôi nốc ly tăng lực đã ⚡',
        'Hơi buồn ngủ nhưng tay vẫn nhanh!',
        'Dựng liền, một nốt nhạc.',
    ],
    thodung_giao: [
        'Render… 99%… xong!',
        'Cuộn phim ra lò, nóng hổi!',
        'Gửi kho nha, xong lô này tôi ngủ bù.',
        'Lưu kho! Cho tôi chợp mắt xíu.',
    ],
    // Giám khảo: nghiêm nhưng công bằng
    giamkhao_dat: [
        'Hừm… {diem} điểm. Tạm được.',
        '{diem} điểm. Đạt, đừng tự mãn.',
        'Ổn đó, {diem}/10. Lần sau cố hơn.',
        'Công bằng mà nói: {diem} điểm.',
    ],
    giamkhao_hong: [
        'Làm lại! Chỗ giây 3 sai rồi.',
        'Chưa đạt. Tôi không nhượng bộ đâu.',
        'Hừm… chưa ổn, đi dựng lại!',
        'Phải làm lại. Tôi nói thẳng.',
    ],
    giamkhao_dung_lai: ['Dựng lại: {loi}', 'Dựng lại nha: {loi}'],
    // Thủ kho: sạch sẽ, ngăn nắp
    thukho_nhan: [
        'Xếp ngay ngắn nè.',
        'Lau cái đã, rồi mới xếp.',
        'Đúng chỗ, đúng giờ, đúng hàng.',
        'Ai xếp lệch là tôi biết liền!',
    ],
    // Chủ quầy, Cú, Bưu tá, Mèo
    chuquay_idle: [
        'Chốt đơn!',
        'Mua 1 tặng 1 nha!',
        'Giỏ hàng đầy là tôi vui.',
        'Còn hàng! Còn hàng!',
        'Hàng mới về nè!',
        'Cảm ơn quý khách ❤️',
    ],
    cu_idle: [
        'Số liệu nói rằng… ngủ sớm tốt cho video.',
        'Hú! Lượt xem hôm nay nhích lên đó.',
        'Cú nhìn là biết…',
        'Biểu đồ đẹp thì Cú mới vui.',
    ],
    buuta_den: [
        'Thư tới đây!',
        'Thư tới! Ký nhận nha!',
        'Chạy chạy chạy, trễ giờ rồi!',
        'Bài đã vào hòm!',
    ],
    meo: ['Meo~', 'Meo meo!', 'Gừ… đang bận ngủ.', 'Meo? (xin cá)', 'Mrrr…'],
    // Lúc rảnh rỗi (ngôi nhà 3D)
    bienkich_idle: [
        'Mây hôm nay giống câu mở đầu…',
        'Để tôi ngắm trời chút, ý tứ sẽ tới.',
        'Một vần thơ vừa bay qua cửa sổ!',
        'Cây ơi, uống nước rồi lớn nha.',
        'Chữ hay thì phải chờ nó chín.',
    ],
    thuam_idle: [
        'Bass này nghe đã tai chưa? 🎧',
        'Hacker không bao giờ ngủ… chỉ chợp mắt.',
        'Bàn phím kêu lách cách mới là nhạc!',
        'Ai cần mạng? Tôi tự phát sóng.',
        'Bíp bùm bíp… remix nè!',
    ],
    daodien_chat: [
        'Cảnh sau nên quay ngược sáng!',
        'Không, phải thật ấm áp!',
        'Để tôi phác thử…',
        'Ý hay đó, nhưng của tôi hay hơn.',
    ],
    thodung_idle: [
        'Xoay ghế 10 vòng, tăng tốc dựng 10%!',
        'GG! Làm ván nữa không?',
        'Ực… tỉnh cả người ⚡',
        'Combo phím tắt thần sầu!',
    ],
    thodung_render: [
        'Render… 99%… xong!',
        'Phim ra lò nè!',
        'Dựng xong, mượt như bơ!',
        'Xong một cái, nhẹ cả người!',
    ],
    giamkhao_idle: [
        'Hừm… chỉnh kính cái đã.',
        'Tôi vẫn đang để mắt đấy.',
        'Tiêu chuẩn là tiêu chuẩn.',
        'Cúp này phải giữ cho bóng.',
    ],
    thukho_idle: [
        'Lau cho bóng loáng!',
        'Ngăn nắp là hạnh phúc.',
        'Cuộn phim phải thẳng hàng!',
        'Không một hạt bụi!',
    ],
    buuta_idle: [
        'Nghỉ chân chút đã…',
        'Hòm thư sạch bong!',
        'Hôm nay trời đẹp ghê.',
        'Có thư nào chưa ta?',
    ],
    ca_phe: ['Cà phê cái đã ☕', 'Ực… tỉnh hẳn!', 'Một ngụm cho tươi tỉnh.'],
    dao_choi: [
        'Đi dạo chút cho thoáng.',
        'Ra vườn hít thở nè.',
        'Duỗi chân tí!',
    ],
    meo_thich: ['Meo~ (thích bạn nhất)', 'Prrr… ấm quá.', 'Meo meo ❤️'],
    // Cả xưởng
    het_han_muc: [
        'Hết hạn mức rồi… ngáp… ngủ thôi.',
        'Claude đòi nghỉ, mình cũng nghỉ…',
        'Hạn mức cạn rồi. Zzz…',
    ],
    thuc_day: [
        'Dậy thôi! Lô mới nè ☀️',
        'Vươn vai… làm tiếp!',
        'Chào buổi làm việc!',
    ],
    xong_lo: [
        'Xong lô rồi! 🎉',
        'Hoan hô!',
        'Mệt nhưng vui!',
        'Cả xưởng giỏi quá!',
    ],
    loi: ['!', 'Ối, có lỗi rồi!', 'Hỏng gì đó rồi…'],
    // Có việc giữa lúc đang chơi: lật đật chạy về bàn
    co_viec: [
        'Ối, có việc rồi!',
        'Ấy chết, việc tới!',
        'Về bàn thôi, việc gọi!',
        'Đợi tao chút, có việc!',
        'Chạy chạy chạy!',
    ],

    // Va nhau trên đường: dung_<ai> = người đụng nói trước, bi_dung_<ai> = người bị đụng đáp lại
    dung_bienkich: [
        'Xin lỗi xin lỗi…',
        'Ấy chết, tớ mải nghĩ thơ…',
        'Xin lỗi nha, tớ không thấy.',
        'Ôi, va phải một vần thơ!',
    ],
    bi_dung_bienkich: [
        'Không sao, không sao đâu…',
        'Ui… tớ cũng xin lỗi!',
        'Nhẹ nhàng thôi bạn ơi~',
        'Câu thơ của tớ rơi mất rồi…',
    ],
    dung_thuam: [
        'Ê, mày đụng tao à? 😎',
        'Né đi, hacker đang lướt!',
        'Tránh ra, tao đang gấp!',
        'Va hacker là mất sóng đó nha.',
    ],
    bi_dung_thuam: [
        'Thích chạm hả? 😏',
        'Đụng hacker là bị hack ngược đó!',
        'Ủa, mày không thấy tao à?',
        'Chạm nhẹ thôi, tao dễ vỡ… đùa đó 😎',
    ],
    dung_daodien: [
        'Cắt! Ai cho mày lọt khung hình?',
        'Ê, cảnh này không có mày!',
        'Tránh ra, tao đang tìm góc máy!',
        'Diễn sai vị trí rồi nha!',
    ],
    bi_dung_daodien: [
        'Ê, mày đụng tao à?',
        'Cắt! Quay lại từ đầu!',
        'Va kiểu này phải quay chậm mới đẹp.',
        'Thích chạm hả? Đóng cảnh ôm luôn không?',
    ],
    dung_thodung: [
        '…',
        '(mắt vẫn dán vào máy) Ừ ừ…',
        'Lag rồi, xin lỗi…',
        'Hửm? Ai đó?',
    ],
    bi_dung_thodung: [
        '…(không ngẩng lên)',
        'Ừ… để tao combo xong đã.',
        'Afk tí, đừng đụng!',
        'Sắp lên level, đừng phá!',
    ],
    dung_giamkhao: [
        'Đi đứng cho đàng hoàng!',
        'Trừ một điểm vì tội va chạm!',
        'Mắt để đâu đấy hả?',
        'Hừm! Đi thẳng hàng vào.',
    ],
    bi_dung_giamkhao: [
        'Hừm! Đi đứng thế à?',
        'Ê, mày đụng tao à? Trừ điểm!',
        'Lần sau nhìn đường giùm!',
        'Tôi ghi sổ vụ này đấy.',
    ],
    dung_thukho: [
        'Ê, coi chừng làm rơi đồ!',
        'Tránh ra, tao đang gấp!',
        'Đi ngay hàng thẳng lối giùm!',
        'Dẫm bẩn sàn tao lau rồi!',
    ],
    bi_dung_thukho: [
        'Ê, mày đụng tao à?',
        'Sàn mới lau đó nha!',
        'Đi cẩn thận, đồ dễ vỡ!',
        'Lệch hàng rồi kìa!',
    ],
    dung_chuquay: [
        'Ối, xin lỗi quý khách!',
        'Va nhau là có duyên, mua gì không?',
        'Tránh ra, tao đang gấp!',
        'Ê, nhường đường cái nào!',
    ],
    bi_dung_chuquay: [
        'Thích chạm hả? Mua hàng đi rồi chạm!',
        'Ê, mày đụng tao à? 😤',
        'Đụng là phải mua một món nha!',
        'Hì, không sao đâu~',
    ],
    dung_buuta: [
        'Tránh ra, tao đang gấp!',
        'Thư hoả tốc, nhường đường!',
        'Xin lỗi nha, trễ giờ rồi!',
        'Bíp bíp, bưu tá qua!',
    ],
    bi_dung_buuta: [
        'Ê, mày đụng tao à?',
        'Coi chừng rớt thư!',
        'Cẩn thận chứ bạn ơi!',
        'Thích chạm hả? Ký nhận đi đã!',
    ],
    bump_xong: [
        'Thôi hoà nha!',
        'Đi tiếp đi đi!',
        'Lần sau tránh nha!',
        'Hứ!',
        'Hì hì.',
    ],
    meo_xi: ['Xììì! 😾', 'Gừừừ!', 'Mèo không thích bị đụng!'],
    meo_tha: [
        'Meo~ (thôi tha cho)',
        'Mrrr… lần này thôi đó.',
        'Meo! (hết giận rồi)',
    ],

    // Giờ ăn, giờ cà phê, giờ chơi
    nau_an: [
        'Mì tôm thần thánh sắp xong!',
        'Lật chảo nè! 🍳',
        'Ai ăn trứng ốp la giơ tay!',
        'Thơm chưa? Thơm chưa?',
    ],
    goi_an: [
        'Cơm chín rồi, vào ăn thôi! 🍚',
        'Cả nhà ơi, ăn trưa nè!',
        'Ăn tối thôi mọi người ơi!',
    ],
    an: [
        'Ngon quá trời!',
        'Măm măm…',
        'Cho xin thêm bát nữa!',
        'Ai nấu mà ngon dữ vậy?',
        'No căng bụng rồi…',
    ],
    xep_hang_ca_phe: [
        'Xếp hàng nha, đừng chen!',
        'Một ly sữa đá, cảm ơn!',
        'Cho tao ly đậm nhất!',
        'Đợi xíu, máy đang pha…',
    ],
    ca_phe_cai_a: [
        'Cà phê phải đắng mới có hồn!',
        'Ly này là của tao!',
        'Đen đá không đường mới chất!',
        'Mày pha nhạt quá trời!',
    ],
    ca_phe_cai_b: [
        'Không, ngọt mới là chân ái!',
        'Ly đậm là của tao, trả đây!',
        'Sữa đá mới đúng bài!',
        'Đắng gì mà đắng, thêm đường đi!',
    ],
    ca_phe_hoa: [
        'Thôi, hoà. Uống đi.',
        'Ờ thì… mỗi đứa một ly.',
        'Cạn ly! ☕',
        'Mai tao pha cho mày.',
    ],
    choi_game: [
        'Combo! Combo!',
        'GG ez 😎',
        'Một ván nữa thôi…',
        'Ai vào solo không?',
    ],
    doc_sach: [
        'Trang này hay quá…',
        'Đọc chút thơ cho dịu lòng.',
        'Suỵt, đang tới đoạn hay.',
    ],
    ngu_trua: [
        'Ngáp… chợp mắt xíu…',
        'Mười phút thôi… Zzz',
        'Ăn no buồn ngủ ghê…',
    ],
    bi_lac: [
        'Sút! Vàoooo!',
        'Gian lận! Mày xoay cần!',
        'Tỉ số 3–2 nha!',
        'Ván nữa! Ván nữa!',
    ],
    bong_ban: [
        'Bóp nè!',
        'Đỡ được không?',
        'Ăn điểm! 🏓',
        'Ê, bóng chạm lưới mà!',
    ],
    tuoi_rau: [
        'Rau ơi, lớn nhanh nha 🥬',
        'Cà chua đỏ rồi kìa!',
        'Tưới tí cho mát.',
    ],
    nam_vong: ['Gió mát quá…', 'Võng ơi đung đưa…', 'Ở đây cả ngày cũng được.'],
    don_bep: [
        'Bếp phải sạch bong!',
        'Ai để bát chưa rửa đây?',
        'Lau xong là sáng loáng!',
    ],
};

const lastPick: Record<string, number> = {};

/** Chọn ngẫu nhiên một câu cho tình huống `key` (không lặp câu vừa nói), thay các {tham_số}. */
export const noi = (
    key: string,
    vars: Record<string, string | number | null | undefined> = {},
): string => {
    const pool = LOI_THOAI[key] ?? [];
    if (pool.length === 0) {
        return '';
    }
    let i = Math.floor(Math.random() * pool.length);
    if (pool.length > 1 && i === lastPick[key]) {
        i = (i + 1) % pool.length;
    }
    lastPick[key] = i;

    return pool[i].replace(/\{(\w+)\}/g, (_, k: string) =>
        String(vars[k] ?? ''),
    );
};

// ---------------------------------------------------------------------------------------------
// Lời thoại theo NGỮ CẢNH: giờ trong ngày (sang/trua/chieu/toi/dem), tâm trạng (vui/buon), sức (met),
// đang gặp ai (voi_<ai>), cùng các biến {sanpham} {diem} {so} {gio} {ten}.
// Khoá: <ai>_<tình huống>[_<biến thể>] hoặc <tình huống>[_<biến thể>] (dùng chung).
export const NGU_CANH: Record<string, string[]> = {
    // ---- lúc rảnh, theo giờ
    bienkich_idle_sang: [
        'Nắng sớm đẹp như câu mở bài…',
        'Sáng nay tớ nghĩ ra ba vần rồi!',
        'Trà sáng, gió sáng, chữ cũng sáng~',
        'Buổi sáng là lúc chữ ngoan nhất.',
    ],
    bienkich_idle_trua: [
        'Trưa rồi, chữ cũng muốn ngủ…',
        'Nắng trưa gay gắt như lời phê của Giám khảo.',
        'Ăn gì để viết cho hay đây ta?',
    ],
    bienkich_idle_chieu: [
        'Chiều tím, lòng cũng tím…',
        'Hoàng hôn này phải viết thành thơ.',
        'Chiều nay ai đọc thơ với tớ không?',
    ],
    bienkich_idle_toi: [
        'Đêm xuống, ý tưởng mới lên.',
        'Đèn vàng, giấy trắng, mực tím…',
        'Tối rồi, viết thêm một đoạn nữa thôi.',
    ],
    bienkich_idle_dem: [
        'Khuya rồi… nhưng câu này chưa xong.',
        'Trăng đẹp quá, ai ngủ được chứ.',
        'Đêm khuya, chữ thì thầm với tớ.',
    ],
    bienkich_idle_met: [
        'Viết nhiều quá, tay mỏi rồi…',
        'Chữ chạy hết đâu rồi ta…',
        'Cho tớ nghỉ một vần thôi.',
    ],
    bienkich_idle_vui: [
        'Video đạt rồi! Lời của tớ có công nha~',
        'Vui quá, muốn làm thêm bài thơ!',
        'Hôm nay chữ nào cũng đẹp!',
    ],
    bienkich_idle_buon: [
        'Bị chê rồi… thôi viết lại cho hay hơn.',
        'Buồn một chút rồi thôi nha.',
    ],

    thuam_idle_sang: [
        'Sáng sớm mic còn ấm 🎤',
        'Hacker dậy sớm, tín hiệu mạnh!',
        'Giọng buổi sáng trầm ấm nhất đó.',
    ],
    thuam_idle_trua: [
        'Trưa rồi, bass xuống, cơm lên.',
        'Đói quá, hack tủ lạnh thôi.',
        'Remix tiếng nồi cơm điện nè 😎',
    ],
    thuam_idle_chieu: [
        'Chiều chill, bật lo-fi nào.',
        'Tai nghe này nghe hoàng hôn rõ lắm.',
        'Ai cần beat cho video chiều không?',
    ],
    thuam_idle_toi: [
        'Tối là giờ hacker lên sóng 😎',
        'Đèn tắt, màn hình sáng, ngon.',
        'Bíp bíp… mạng đêm mượt ghê.',
    ],
    thuam_idle_dem: [
        'Khuya rồi mà tai vẫn tỉnh.',
        'Đêm nay tao trực, cả nhà ngủ đi.',
        'Hacker không ngủ, chỉ chờ lô mới.',
    ],
    thuam_idle_met: [
        'Thu nhiều quá, khàn giọng rồi…',
        'Cho tao ly trà chanh mật ong.',
        'Mic ơi, nghỉ tí nha.',
    ],
    thuam_idle_vui: [
        'Đạt! Giọng tao chuẩn mà 😎',
        'Ê, nghe lại bản thu chưa? Đỉnh!',
        'Hôm nay hacker thắng lớn!',
    ],

    daodien_idle_sang: [
        'Ánh sáng sáng nay hoàn hảo!',
        'Cảnh mở đầu phải có nắng sớm.',
        'Sáng ra là phải có ý tưởng!',
    ],
    daodien_idle_trua: [
        'Ăn trưa xong mới có cảm hứng.',
        'Trưa nắng quá, quay trong nhà thôi.',
    ],
    daodien_idle_chieu: [
        'Giờ vàng! Quay đẹp nhất là lúc này!',
        'Hoàng hôn kìa, cắt cảnh nào!',
    ],
    daodien_idle_toi: [
        'Đêm nay dựng phim kiểu điện ảnh.',
        'Đèn đường đẹp như phim Pháp.',
    ],
    daodien_idle_dem: [
        'Khuya rồi mà vẫn mơ cảnh quay.',
        'Ngủ đi… mai cãi tiếp.',
    ],
    daodien_idle_met: [
        'Cãi nhau nhiều quá, khô họng rồi.',
        'Cho tôi ngồi một xíu…',
    ],
    daodien_idle_vui: [
        'Thấy chưa, cảnh của tôi đúng mà!',
        'Đạt rồi! Hai đứa mình giỏi ghê!',
    ],

    thodung_idle_sang: [
        'Sáng… ngáp… ai thấy kính tôi đâu?',
        'Cà phê chưa? Chưa thì tôi chưa dậy.',
        'Sáng sớm render chậm như tôi vậy.',
    ],
    thodung_idle_trua: [
        'Ăn xong là buồn ngủ, quy luật rồi.',
        'Trưa rồi, cho tôi một ván game thôi.',
    ],
    thodung_idle_chieu: [
        'Chiều nay combo phím tắt mượt lắm.',
        'GG, video chiều nay xịn đó!',
    ],
    thodung_idle_toi: [
        'Tối là giờ vàng của game thủ.',
        'Đêm nay leo rank không ai cản!',
    ],
    thodung_idle_dem: [
        'Khuya rồi… một ván nữa thôi…',
        'Zzz… à không, tôi vẫn thức!',
    ],
    thodung_idle_met: [
        'Mắt díp lại rồi…',
        'Render xong mà người chưa xong…',
        'Cho tôi chợp mắt năm phút.',
    ],
    thodung_idle_vui: ['Video mượt như bơ, đạt luôn!', 'Level up! 🎮'],

    giamkhao_idle_sang: [
        'Buổi sáng là lúc chấm công bằng nhất.',
        'Kính lau rồi, sẵn sàng.',
        'Sáng nay tôi sẽ khó tính hơn.',
    ],
    giamkhao_idle_trua: [
        'Ăn trưa đúng giờ, chấm điểm đúng chuẩn.',
        'Không ngủ trưa. Tôi đang để mắt.',
    ],
    giamkhao_idle_chieu: [
        'Chiều rồi, tiêu chuẩn vẫn vậy.',
        'Đừng tưởng chiều là tôi dễ.',
    ],
    giamkhao_idle_toi: [
        'Tối rồi, ai chưa xong việc?',
        'Tôi sẽ xem lại video ban ngày.',
    ],
    giamkhao_idle_dem: [
        'Khuya rồi, đi ngủ đúng giờ đi!',
        'Ngủ sớm cũng là một tiêu chuẩn.',
    ],
    giamkhao_idle_vui: [
        'Hừm… lô này khá đấy.',
        'Tôi hài lòng. Đừng nói ai biết.',
    ],
    giamkhao_idle_buon: [
        'Lần sau phải tốt hơn.',
        'Tôi không vui. Nhưng công bằng.',
    ],

    thukho_idle_sang: [
        'Sáng ra là phải quét kho!',
        'Đếm lại cuộn phim cái đã.',
        'Một ngày ngăn nắp bắt đầu!',
    ],
    thukho_idle_trua: [
        'Ăn xong nhớ rửa bát nha cả nhà!',
        'Trưa rồi, kho vẫn sạch bong.',
    ],
    thukho_idle_chieu: [
        'Chiều rồi, lau kệ lần hai.',
        'Bụi chiều cũng phải đuổi đi!',
    ],
    thukho_idle_toi: [
        'Khoá kho, kiểm tra lần cuối.',
        'Tối rồi, xếp lại cho mai.',
    ],
    thukho_idle_dem: [
        'Kho ngủ rồi, tôi cũng ngủ.',
        'Đêm yên tĩnh, kệ thẳng hàng.',
    ],
    thukho_idle_vui: ['Thêm một cuộn phim lên kệ!', 'Kệ đầy dần rồi, vui ghê!'],

    chuquay_idle_sang: [
        'Mở hàng! Chào buổi sáng!',
        'Sáng nay giảm giá cho người dậy sớm!',
        'Hàng mới về sáng nay nè!',
    ],
    chuquay_idle_trua: [
        'Trưa rồi, khách nghỉ, tôi cũng nghỉ.',
        'Bán hàng xong mới ăn cơm!',
    ],
    chuquay_idle_chieu: [
        'Chiều là giờ chốt đơn đẹp nhất!',
        'Ai mua {sanpham} không nè?',
    ],
    chuquay_idle_toi: ['Tối rồi, livestream thôi!', 'Đơn tối nay nhiều ghê!'],
    chuquay_idle_dem: [
        'Khuya rồi, mai bán tiếp nha.',
        'Đóng quầy, đếm tiền… à đếm đơn.',
    ],
    chuquay_idle_vui: [
        'Video đẹp vậy là bán đắt rồi!',
        'Có video mới, chốt đơn liền!',
    ],

    buuta_idle_sang: [
        'Chuyến thư sáng sớm!',
        'Sáng nay trời mát, chạy thư vui ghê.',
    ],
    buuta_idle_trua: [
        'Trưa nắng, đứng bóng cây chút.',
        'Ăn trưa rồi giao tiếp.',
    ],
    buuta_idle_chieu: [
        'Chiều rồi, còn thư nào không ta?',
        'Chạy thư chiều mát chân ghê.',
    ],
    buuta_idle_toi: ['Tối rồi, hòm thư khoá nha.', 'Mai giao thư sớm!'],
    buuta_idle_dem: ['Khuya rồi, bưu tá cũng phải ngủ.'],

    // ---- chào sếp (Kid đi dạo trong xưởng)
    chao_sep: [
        'Chào sếp!',
        'Sếp tới chơi hả?',
        'A, sếp kìa!',
        'Sếp khoẻ không?',
    ],
    chao_sep_sang: ['Chào buổi sáng sếp!', 'Sếp dậy sớm ghê!'],
    chao_sep_trua: ['Sếp ăn trưa chưa?', 'Trưa rồi, sếp nghỉ chút đi!'],
    chao_sep_chieu: ['Chiều vui nha sếp!', 'Sếp uống cà phê chiều không?'],
    chao_sep_toi: ['Tối rồi sếp còn ghé!', 'Sếp ơi, tối nay ăn gì?'],
    chao_sep_dem: [
        'Khuya rồi sếp ơi, đi ngủ đi!',
        'Sếp còn thức à? Giữ sức nha!',
    ],
    bienkich_chao_sep: [
        'Chào sếp, hôm nay sếp như một bài thơ~',
        'Sếp ơi, nghe tớ đọc câu mở bài nè!',
        'Sếp tới là chữ tự chạy ra luôn.',
    ],
    thuam_chao_sep: [
        'Sếp tới kiểm tra hả? 😎',
        'Hệ thống ổn định, sếp yên tâm!',
        'Sếp nghe thử giọng mới không?',
        'Hacker chào sếp!',
    ],
    daodien_chao_sep: [
        'Sếp! Đứng yên đó, góc này đẹp lắm!',
        'Sếp duyệt cảnh này giùm!',
        'Sếp đứng vào khung hình đi!',
    ],
    thodung_chao_sep: [
        '(không ngẩng lên) Chào sếp…',
        'Sếp ơi, render sắp xong rồi!',
        'Sếp chơi một ván không?',
    ],
    giamkhao_chao_sep: [
        'Chào sếp. Hôm nay tôi chấm khó đấy.',
        'Sếp yên tâm, chất lượng có tôi lo.',
        'Hừm, sếp tới. Ngồi thẳng lưng nào.',
    ],
    thukho_chao_sep: [
        'Sếp ơi, kho gọn gàng lắm nè!',
        'Sếp coi kệ phim thẳng chưa?',
        'Chào sếp! Đừng dẫm sàn ướt nha.',
    ],
    chuquay_chao_sep: [
        'Sếp tới! Hôm nay chốt đơn đẹp lắm!',
        'Chào sếp! Mua gì không, giảm giá cho sếp nè!',
        'Sếp ơi, {sanpham} đang hot đó!',
    ],
    buuta_chao_sep: [
        'Thư cho sếp nè! À… chưa có.',
        'Chào sếp! Bưu tá luôn đúng giờ!',
        'Sếp ơi, hòm thư sạch bong rồi!',
    ],
    meo_chao_sep: [
        'Meo~ (sếp về rồi!)',
        'Prrr… (dụi dụi)',
        'Meo meo! (bế em đi)',
    ],
    // sếp lỡ va phải
    bi_sep_dung: [
        'Ối sếp! Không sao ạ!',
        'Sếp đi cẩn thận nha!',
        'Hì, sếp vội đi đâu đó?',
    ],
    thuam_bi_sep_dung: [
        'Sếp đụng hacker là bị hack đó nha 😎',
        'Ê… à, sếp! Không sao!',
    ],
    giamkhao_bi_sep_dung: [
        'Sếp đi đứng cẩn thận chứ!',
        'Hừm! Sếp cũng phải nhìn đường.',
    ],
    thodung_bi_sep_dung: ['…(vẫn không ngẩng lên)', 'Lag tí… à, sếp hả?'],
    bienkich_bi_sep_dung: [
        'Ôi, sếp làm rơi vần thơ của tớ rồi~',
        'Không sao đâu sếp ơi!',
    ],

    // ---- có việc giữa giờ chơi, theo sức
    co_viec_met: [
        'Ối… lại có việc rồi…',
        'Mệt mà vẫn phải chạy!',
        'Thôi được, làm nốt lô này!',
    ],
    co_viec_vui: ['Có việc! Tuyệt!', 'Việc tới rồi, xông lên!'],
    co_viec_dem: ['Khuya rồi mà vẫn có việc à!', 'Làm nốt rồi ngủ nha!'],

    // ---- giờ cơm, cà phê, đi dạo theo giờ
    an_trua: [
        'Cơm trưa ngon quá!',
        'Ăn no rồi mới làm tiếp!',
        'Trưa nay có canh chua nè!',
    ],
    an_toi: [
        'Cơm tối ấm bụng ghê!',
        'Ăn tối cùng cả nhà vui nhất!',
        'Tối nay ai rửa bát?',
    ],
    ca_phe_sang: ['Ly cà phê sáng là chân ái ☕', 'Không cà phê là chưa dậy!'],
    ca_phe_chieu: [
        'Cà phê chiều cho tỉnh táo!',
        'Một ly nữa thôi, chiều dài quá.',
    ],
    ca_phe_toi: [
        'Tối rồi… uống cacao thôi.',
        'Cà phê giờ này là thức tới sáng mất.',
    ],
    ca_phe_met: ['Cần cà phê gấp…', 'Hai shot espresso giùm!'],
    dao_choi_sang: [
        'Đi dạo buổi sáng cho khoẻ!',
        'Ra vườn hít khí trời sớm nè.',
    ],
    dao_choi_chieu: ['Chiều mát, đi dạo thôi!', 'Ra ngắm hoàng hôn chút.'],
    dao_choi_toi: ['Đi dạo dưới đèn vườn~', 'Đom đóm ra rồi kìa!'],
    dao_choi_met: ['Đi dạo cho đỡ mỏi lưng.', 'Duỗi chân cái, ngồi lâu quá.'],
};

const TOD = (h: number) =>
    h < 5
        ? 'dem'
        : h < 11
          ? 'sang'
          : h < 14
            ? 'trua'
            : h < 18
              ? 'chieu'
              : h < 22
                ? 'toi'
                : 'dem';

/** Ngữ cảnh để chọn câu. */
export interface LineCtx {
    /** Tình huống: idle, chao_sep, co_viec, ca_phe, dao_choi, dung, bi_dung… */
    situation: string;
    hour?: number;
    mood?: 'vui' | 'buon' | null;
    tired?: boolean;
    /** Đang nói với ai (khoá nhân vật). */
    with?: string | null;
    vars?: Record<string, string | number | null | undefined>;
}

const lastBy: Record<string, string> = {};
const pool = (k: string) => NGU_CANH[k] ?? LOI_THOAI[k] ?? [];

/**
 * Chọn một câu cho nhân vật `who` theo ngữ cảnh (chỉ dùng mẫu câu soạn sẵn).
 * Ưu tiên câu riêng của nhân vật và câu hợp giờ/tâm trạng/sức; không lặp câu vừa nói của chính người đó.
 */
export const lineFor = (who: string, c: LineCtx): string => {
    const role = who.startsWith('daodien') ? 'daodien' : who;
    const h = c.hour ?? new Date().getHours() + new Date().getMinutes() / 60;
    const s = c.situation;
    const variants = [
        c.tired ? 'met' : null,
        c.mood ?? null,
        TOD(h),
        c.with ? `voi_${c.with}` : null,
    ].filter(Boolean) as string[];
    const special: string[] = [];
    const general: string[] = [];
    for (const v of variants) {
        special.push(...pool(`${role}_${s}_${v}`), ...pool(`${s}_${v}`));
    }
    general.push(...pool(`${role}_${s}`), ...pool(`${s}_${role}`));
    if (general.length === 0 || Math.random() < 0.25) {
        general.push(...pool(s));
    }
    const pickFrom =
        special.length && Math.random() < 0.55
            ? special
            : general.length
              ? general
              : special;
    const opts = pickFrom.filter((x) => x !== lastBy[who]);
    const list = opts.length ? opts : pickFrom;
    if (!list.length) {
        return '';
    }
    const line = list[Math.floor(Math.random() * list.length)];
    lastBy[who] = line;
    const vars: Record<string, string | number | null | undefined> = {
        gio: `${Math.floor(h)} giờ`,
        sanpham: 'hàng mới',
        ...c.vars,
    };
    if (!vars.sanpham) {
        vars.sanpham = 'hàng mới';
    }

    return line
        .replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ''))
        .replace(/\s{2,}/g, ' ');
};

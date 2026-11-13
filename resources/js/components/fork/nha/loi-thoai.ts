// Lời thoại của từng nhân vật theo tình huống, dễ sửa tại một chỗ. Mỗi tình huống 3-6 câu, chọn ngẫu nhiên.
// Chỗ có {diem}, {loi}... sẽ được thay bằng số liệu thật. Giữ vui, hơi tinh nghịch, không chửi thề.
export const LOI_THOAI: Record<string, string[]> = {
    // Biên kịch: nhà thơ mơ mộng
    bienkich_giao: ['Câu này hay quá trời…', 'Mực còn ướt, cầm nhẹ thôi nha.', 'Giao hàng văn chương đây ✍️', 'Viết xong rồi, lòng nhẹ hẫng…', 'Mỗi con chữ là một giấc mơ nhỏ.'],
    bienkich_nhan: ['Gửi bạn một bài thơ… à, lời đọc!', 'Đọc cho có hồn nha.', 'Vần điệu ổn chưa nhỉ?', 'Tôi viết cả đêm đó.'],
    // Thu âm: hacker DJ tự tin quá mức
    thuam_nhan: ['Để đó, hacker lo.', 'Nhận kịch bản. Bắt đầu “xâm nhập” giọng!', 'Mic sẵn sàng 🎤', 'Chữ đẹp đó nha, ghi âm liền.'],
    thuam_hack: ['Hacker đây, nhận tín hiệu đi!', 'Tải giọng xong, 0,3 giây thôi 😎', 'Bíp bíp… truyền xong!', 'Đã xâm nhập kho âm thanh. Thành công!', 'Gõ phím cái là xong.'],
    // Đạo diễn: hai nghệ sĩ cãi nhau rồi đập tay
    daodien_cai_a: ['Phải cận cảnh!', 'Cảnh này phải chậm lại!', 'Màu ấm mới đúng!'],
    daodien_cai_b: ['Không, toàn cảnh!', 'Nhanh mới cuốn!', 'Màu lạnh mới sang!'],
    daodien_hoa: ['Thôi được, hoà! 🙌', 'Lần này tôi nhường.', 'Đồng ý! Đập tay nào!'],
    daodien_giao: ['Bảng dựng nóng hổi, nhận đi!', 'Cận cảnh nha, nhớ đó!', 'Nghệ thuật là phải đau khổ… giao đây.', 'Cắt sai là tôi khóc đó.'],
    daodien_nhan_lai: ['Hả?! Lại nữa à…', 'Ghi nhận phê bình. Sửa liền.', 'Dựng lại… nhưng tôi vẫn thấy mình đúng.'],
    // Thợ dựng: game thủ buồn ngủ nhưng nhanh
    thodung_nhan: ['Render… 99%… xong!', 'Nhận! Để tôi nốc ly tăng lực đã ⚡', 'Hơi buồn ngủ nhưng tay vẫn nhanh!', 'Dựng liền, một nốt nhạc.'],
    thodung_giao: ['Render… 99%… xong!', 'Cuộn phim ra lò, nóng hổi!', 'Gửi kho nha, xong lô này tôi ngủ bù.', 'Lưu kho! Cho tôi chợp mắt xíu.'],
    // Giám khảo: nghiêm nhưng công bằng
    giamkhao_dat: ['Hừm… {diem} điểm. Tạm được.', '{diem} điểm. Đạt, đừng tự mãn.', 'Ổn đó, {diem}/10. Lần sau cố hơn.', 'Công bằng mà nói: {diem} điểm.'],
    giamkhao_hong: ['Làm lại! Chỗ giây 3 sai rồi.', 'Chưa đạt. Tôi không nhượng bộ đâu.', 'Hừm… chưa ổn, đi dựng lại!', 'Phải làm lại. Tôi nói thẳng.'],
    giamkhao_dung_lai: ['Dựng lại: {loi}', 'Dựng lại nha: {loi}'],
    // Thủ kho: sạch sẽ, ngăn nắp
    thukho_nhan: ['Xếp ngay ngắn nè.', 'Lau cái đã, rồi mới xếp.', 'Đúng chỗ, đúng giờ, đúng hàng.', 'Ai xếp lệch là tôi biết liền!'],
    // Chủ quầy, Cú, Bưu tá, Mèo
    chuquay_idle: ['Chốt đơn!', 'Mua 1 tặng 1 nha!', 'Giỏ hàng đầy là tôi vui.', 'Còn hàng! Còn hàng!'],
    cu_idle: ['Số liệu nói rằng… ngủ sớm tốt cho video.', 'Hú! Lượt xem hôm nay nhích lên đó.', 'Cú nhìn là biết…', 'Biểu đồ đẹp thì Cú mới vui.'],
    buuta_den: ['Thư tới đây!', 'Thư tới! Ký nhận nha!', 'Chạy chạy chạy, trễ giờ rồi!', 'Bài đã vào hòm!'],
    meo: ['Meo~', 'Meo meo!', 'Gừ… đang bận ngủ.', 'Meo? (xin cá)', 'Mrrr…'],
    // Cả xưởng
    het_han_muc: ['Hết hạn mức rồi… ngáp… ngủ thôi.', 'Claude đòi nghỉ, mình cũng nghỉ…', 'Hạn mức cạn rồi. Zzz…'],
    thuc_day: ['Dậy thôi! Lô mới nè ☀️', 'Vươn vai… làm tiếp!', 'Chào buổi làm việc!'],
    xong_lo: ['Xong lô rồi! 🎉', 'Hoan hô!', 'Mệt nhưng vui!', 'Cả xưởng giỏi quá!'],
    loi: ['!', 'Ối, có lỗi rồi!', 'Hỏng gì đó rồi…'],
};

const lastPick: Record<string, number> = {};

/** Chọn ngẫu nhiên một câu cho tình huống `key` (không lặp câu vừa nói), thay các {tham_số}. */
export const noi = (key: string, vars: Record<string, string | number | null | undefined> = {}): string => {
    const pool = LOI_THOAI[key] ?? [];
    if (pool.length === 0) {
        return '';
    }
    let i = Math.floor(Math.random() * pool.length);
    if (pool.length > 1 && i === lastPick[key]) {
        i = (i + 1) % pool.length;
    }
    lastPick[key] = i;

    return pool[i].replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ''));
};

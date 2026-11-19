// Chuẩn hoá chữ để tìm kiếm không phân biệt dấu và hoa thường ("Đạm cá" khớp "dam ca").
export const norm = (s: string): string =>
    s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').toLowerCase();

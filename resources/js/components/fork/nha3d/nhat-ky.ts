// "Nhật ký đang làm gì" của hai Đạo diễn, cho thẻ "Khu Tự Trị" ở trang Xưởng Video.
// KHÔNG gọi AI, KHÔNG bịa chữ: chỉ lọc + định dạng lại sự kiện thật của hub sản xuất
// (vai === "dao-dien" trong sổ sự kiện `/nha/trang-thai` → `events`, do xuong-video/engine/ekip.py
// ghi ra bằng SK.ghi(...) với "msg" đã là câu tiếng Việt dựng sẵn — xem các dòng
// SK.ghi("dao-dien", "bat-dau"|"xong"|"loi", "...", video=...) trong ekip.py).
// Việc của file này chỉ là: chọn đúng vai, bỏ trùng, tính "...phút trước", và dự phòng một câu
// khi hub cũ không gửi "msg" (mẫu câu cố định, không phải AI sinh chữ).

export interface SuKien {
    n?: number; // mốc thời gian hub (micro-giây)
    vai?: string;
    loai?: string;
    video?: string;
    msg?: string;
    so?: number;
    tong?: number;
}

export interface DongNhatKy {
    key: string;
    text: string;
    agoLabel: string;
}

const MAU: Record<string, (e: SuKien) => string> = {
    'bat-dau': () => 'Đang lên bảng dựng…',
    xong: () => 'Đã xong một bảng dựng',
    loi: () => 'Gặp lỗi khi lên bảng dựng, máy tự dựng thay',
};

const videoSo = (video?: string): string => {
    if (!video) {
        return '';
    }
    const m = video.match(/-(\d+)$/);

    return m ? ` · video ${m[1]}` : '';
};

const agoLabel = (ageSec: number): string => {
    if (ageSec < 0) {
        return 'vừa xong';
    }
    if (ageSec < 45) {
        return 'vừa xong';
    }
    if (ageSec < 3600) {
        return `${Math.max(1, Math.round(ageSec / 60))} phút trước`;
    }

    return `${Math.round(ageSec / 3600)} giờ trước`;
};

/**
 * Lấy tối đa `max` dòng hoạt động gần nhất của hai Đạo diễn, mới nhất trước.
 * `hubNow` = giây hiện tại theo đồng hồ hub (trường `bay_gio` của `/nha/trang-thai`).
 */
export const daoDienLog = (
    events: SuKien[],
    hubNow: number,
    max = 6,
): DongNhatKy[] => {
    const mine = events.filter((e) => e.vai === 'dao-dien');
    const out: DongNhatKy[] = [];
    for (let i = mine.length - 1; i >= 0 && out.length < max; i--) {
        const e = mine[i];
        const base = (e.msg && e.msg.trim()) || MAU[e.loai ?? '']?.(e) || 'Đang làm việc…';
        const ageSec = e.n != null ? hubNow - e.n / 1_000_000 : 0;
        out.push({
            key: `${e.n ?? i}-${i}`,
            text: base + (e.loai === 'bat-dau' ? videoSo(e.video) : ''),
            agoLabel: agoLabel(ageSec),
        });
    }

    return out;
};

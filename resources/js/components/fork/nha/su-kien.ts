// Diễn giải sổ sự kiện của hub Xưởng Video thành câu tiếng Việt ngắn (dùng cho "Hoạt động gần đây" ở trang Khu Tự Trị
// và ở bàn Sảnh). Sự kiện không có ý nghĩa với chủ app thì trả về null để bỏ qua.
import type { NhaEvent } from '@/components/fork/nha/types';

const VAI_TEN: Record<string, string> = {
    'bien-kich': 'Biên kịch',
    giong: 'Thu âm',
    'dao-dien': 'Đạo diễn',
    dung: 'Thợ dựng',
    'giam-khao': 'Giám khảo',
    kho: 'Thủ kho',
    'he-thong': 'Xưởng',
};

const videoNo = (e: NhaEvent) => {
    const m = /-(\d+)$/.exec(e.video ?? '');

    return m ? Number(m[1]) + 1 : null;
};

export const describeEvent = (e: NhaEvent): string | null => {
    const v = videoNo(e);
    const vid = v ? ` video ${v}` : '';

    switch (`${e.vai}|${e.loai}`) {
        case 'he-thong|bat-dau-lo':
            return `Bắt đầu lô ${e.ten ?? ''}${e.so_video ? ` · ${e.so_video} video` : ''}`.trim();
        case 'bien-kich|xong':
            return `Biên kịch viết xong ${e.so ?? ''} lời`;
        case 'giong|xong':
            return `Thu âm xong ${e.so ?? ''} giọng`;
        case 'dao-dien|xong':
            return `Đạo diễn xong bảng dựng${vid}`;
        case 'dung|xong':
            return e.buoc === 'chu'
                ? 'Thợ dựng xong lớp chữ'
                : `Thợ dựng dựng xong${vid}`;
        case 'giam-khao|diem':
            return e.diem == null
                ? `Giám khảo chưa chấm được${vid}`
                : `Giám khảo chấm${vid}: ${e.diem}/10 ${e.dat ? '✓' : '✗'}${!e.dat && e.loi ? ` · ${e.loi}` : ''}`;
        case 'kho|luu':
            return `Nhập kho video ${e.so ?? ''}/${e.tong ?? ''}`;
        case 'he-thong|het-han-muc':
            return 'Hết hạn mức Claude, xưởng nghỉ';
        case 'he-thong|ket-thuc-lo':
            return `Xong lô ${e.so ?? ''}/${e.tong ?? ''}${e.phut ? ` · ${String(e.phut).replace('.', ',')} phút` : ''}`;
        default:
            return e.loai === 'loi'
                ? `${VAI_TEN[e.vai] ?? 'Xưởng'} gặp lỗi${e.msg ? `: ${e.msg}` : ''}`
                : null;
    }
};

export interface SuKienDong {
    n: number;
    time: string;
    text: string;
    bad: boolean;
}

/** Các sự kiện mới nhất (mới nhất lên đầu), chỉ lấy những sự kiện có lời diễn giải. */
export const recentEvents = (
    events: NhaEvent[] | undefined,
    max = 8,
): SuKienDong[] => {
    const out: SuKienDong[] = [];

    for (const e of [...(events ?? [])].reverse()) {
        const text = describeEvent(e);

        if (text && out.length < max) {
            out.push({
                n: e.n,
                time: (e.t ?? '').slice(11, 16),
                text,
                bad:
                    e.loai === 'loi' ||
                    e.loai === 'het-han-muc' ||
                    (e.loai === 'diem' && e.dat === false),
            });
        }
    }

    return out;
};

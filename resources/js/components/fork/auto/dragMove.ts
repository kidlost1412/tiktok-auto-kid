// Kéo thả bài trên Lịch đăng: bài đang được kéo (dùng chung giữa các cột ngày) và giờ ở chỗ con trỏ đang kéo tới.
import { ref } from 'vue';

import type { ScheduleEntry } from '@/components/fork/auto/types';
import dayjs from '@/dayjs';

export const dragging = ref<ScheduleEntry | null>(null);

// Kéo sang tab ngày khác làm dòng đang kéo biến mất, nên "dragend" có thể không tới: chuột di chuyển lại
// (không xảy ra trong lúc kéo) nghĩa là đã thả / huỷ kéo.
if (typeof window !== 'undefined') {
    window.addEventListener('mousemove', () => {
        if (dragging.value) {
            dragging.value = null;
        }
    });
}

/** Giờ sớm nhất đổi được (app cũng chặn ở server). */
export const MIN_LEAD_MINUTES = 20;

const round5 = (d: dayjs.Dayjs) =>
    d
        .minute(Math.round(d.minute() / 5) * 5)
        .second(0)
        .millisecond(0);

export interface DropPoint {
    /** Giờ sẽ đăng (ISO). */
    at: string;
    /** Vị trí vạch thả, tính từ đầu khung danh sách (đã cộng phần cuộn). */
    y: number;
    /** Sớm hơn giờ đổi được (cách bây giờ chưa đủ MIN_LEAD_MINUTES phút). */
    tooSoon: boolean;
}

/**
 * Giờ ở chỗ con trỏ trong danh sách một ngày (`root` chứa các dòng có data-row-at):
 * - trên một giờ trống: đúng giờ đó;
 * - giữa hai dòng: chia theo vị trí con trỏ giữa hai dòng (làm tròn 5 phút);
 * - trên dòng đầu / dưới dòng cuối: lùi / thêm dần theo khoảng kéo (1 px ≈ 1 phút, ít nhất 15 phút);
 * - ngày chưa có dòng nào: theo vị trí trong khung, từ 06:00 tới 23:00.
 * Luôn nằm trong ngày `dayKey`.
 */
export function pointAt(
    root: HTMLElement,
    clientY: number,
    dayKey: string,
    skipKey: string,
): DropPoint {
    const box = root.getBoundingClientRect();
    const toY = (cy: number) => cy - box.top + root.scrollTop;
    const rows = [...root.querySelectorAll<HTMLElement>('[data-row-at]')]
        .filter((r) => r.dataset.rowKey !== skipKey)
        .map((r) => {
            const b = r.getBoundingClientRect();

            return {
                at: dayjs(r.dataset.rowAt),
                top: b.top,
                bottom: b.bottom,
                mid: (b.top + b.bottom) / 2,
                slot: r.dataset.slot === '1',
            };
        });

    let at: dayjs.Dayjs;
    let y = clientY;
    const slot = rows.find(
        (r) => r.slot && clientY >= r.top && clientY <= r.bottom,
    );

    if (slot) {
        at = slot.at;
        y = slot.mid;
    } else if (!rows.length) {
        const f = Math.min(
            1,
            Math.max(0, (clientY - box.top) / Math.max(1, box.height)),
        );
        at = dayjs(`${dayKey}T06:00`).add(Math.round(f * 17 * 60), 'minute');
    } else {
        const i = rows.findIndex((r) => r.mid > clientY);
        const above = i === -1 ? rows[rows.length - 1] : (rows[i - 1] ?? null);
        const below = i === -1 ? null : rows[i];

        if (above && below) {
            const f =
                (clientY - above.mid) / Math.max(1, below.mid - above.mid);
            at = dayjs(
                above.at.valueOf() +
                    f * (below.at.valueOf() - above.at.valueOf()),
            );
        } else if (above) {
            at = above.at.add(
                Math.max(15, Math.round(clientY - above.mid)),
                'minute',
            );
        } else {
            at = below!.at.subtract(
                Math.max(15, Math.round(below!.mid - clientY)),
                'minute',
            );
        }
    }

    at = round5(at);
    const start = dayjs(`${dayKey}T00:00`);
    const end = dayjs(`${dayKey}T23:55`);

    if (at.isBefore(start)) {
        at = start;
    } else if (at.isAfter(end)) {
        at = end;
    }

    return {
        at: at.toISOString(),
        y: toY(y),
        tooSoon: at.isBefore(dayjs().add(MIN_LEAD_MINUTES, 'minute')),
    };
}

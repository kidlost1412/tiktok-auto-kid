// Kéo thả bài trên Lịch đăng: bài đang được kéo (dùng chung giữa các cột ngày) và cách tính giờ gợi ý ở chỗ thả.
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

const round5 = (d: dayjs.Dayjs) =>
    d
        .minute(Math.round(d.minute() / 5) * 5)
        .second(0)
        .millisecond(0);

/**
 * Giờ gợi ý khi thả bài vào cột ngày `dayKey`:
 * - thả lên một giờ trống: đúng giờ đó;
 * - thả lên một bài: chen vào trước bài đó (giữa bài đó và bài liền trước trong cùng ngày, không có bài trước thì sớm hơn 30 phút);
 * - thả vào chỗ trống cuối cột: sau bài cuối 30 phút, cột chưa có bài thì giữ nguyên giờ cũ của bài sang ngày này.
 */
export function proposeTime(
    moving: ScheduleEntry,
    dayKey: string,
    list: ScheduleEntry[],
    target: ScheduleEntry | null,
): string {
    const others = list.filter((e) => e !== moving && e.id !== moving.id);

    if (target && target.state === 'projected' && !target.video_id) {
        return dayjs(target.at).second(0).toISOString();
    }

    if (target) {
        const i = others.indexOf(target);
        const prev = i > 0 ? others[i - 1] : null;
        const t = dayjs(target.at);

        if (prev) {
            const mid =
                dayjs(prev.at).valueOf() +
                (t.valueOf() - dayjs(prev.at).valueOf()) / 2;

            return round5(dayjs(mid)).toISOString();
        }

        return round5(t.subtract(30, 'minute')).toISOString();
    }

    const last = others[others.length - 1];

    if (last) {
        return round5(dayjs(last.at).add(30, 'minute')).toISOString();
    }

    const old = dayjs(moving.at);

    return dayjs(`${dayKey}T${old.format('HH:mm')}`)
        .second(0)
        .toISOString();
}

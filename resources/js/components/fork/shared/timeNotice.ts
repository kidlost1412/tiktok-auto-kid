// Thông báo (không chặn) khi chọn giờ đăng: còn bao lâu nữa, bài trước/sau của cùng kênh cách bao nhiêu phút.
import dayjs from '@/dayjs';

/** Dưới ngần này phút so với bài kênh khác thì báo màu cảnh báo (không chặn). */
export const TIGHT_MINUTES = 20;

/** "12 phút", "1 giờ 05 phút". */
export function humanMinutes(total: number): string {
    const m = Math.max(0, Math.round(total));

    if (m < 60) {
        return `${m} phút`;
    }

    const h = Math.floor(m / 60);
    const r = m % 60;

    return r === 0 ? `${h} giờ` : `${h} giờ ${String(r).padStart(2, '0')} phút`;
}

export interface TimeNotice {
    fromNow: string;
    before: string | null;
    after: string | null;
    tight: boolean;
}

/** `value` là giờ chọn (bất kỳ chuỗi dayjs đọc được); `times` là ISO các bài khác cùng kênh. */
export function timeNotice(value: string, times: string[], now: number = Date.now()): TimeNotice | null {
    const at = dayjs(value);

    if (!value || !at.isValid()) {
        return null;
    }

    const ms = at.valueOf();
    const mins = (a: number, b: number) => Math.round(Math.abs(a - b) / 60000);
    const stamps = times.map((t) => dayjs(t).valueOf()).filter((t) => Number.isFinite(t));
    const prev = stamps.filter((t) => t <= ms).sort((a, b) => b - a)[0];
    const next = stamps.filter((t) => t > ms).sort((a, b) => a - b)[0];
    const fmt = (t: number) => dayjs(t).format('HH:mm DD/MM');
    const dBefore = prev !== undefined ? mins(ms, prev) : null;
    const dAfter = next !== undefined ? mins(next, ms) : null;

    return {
        fromNow: `Giờ mới là ${humanMinutes((ms - now) / 60000)} nữa kể từ bây giờ`,
        before: prev !== undefined ? `Bài trước của kênh: ${fmt(prev)} (cách ${humanMinutes(dBefore ?? 0)})` : null,
        after: next !== undefined ? `Bài sau: ${fmt(next)} (sau ${humanMinutes(dAfter ?? 0)})` : null,
        tight: (dBefore !== null && dBefore < TIGHT_MINUTES) || (dAfter !== null && dAfter < TIGHT_MINUTES),
    };
}

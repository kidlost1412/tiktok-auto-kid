// Bảng trạng thái dùng chung cho cả khu "Tự động đăng": một trạng thái = một màu, một biểu tượng, một nhãn ở mọi trang.
import {
    IconAlertCircle,
    IconBookmark,
    IconCalendarCheck,
    IconCalendarTime,
    IconBrandTiktok,
    IconCircleCheck,
    IconClock,
    IconLoader2,
    IconPlayerSkipForward,
} from '@tabler/icons-vue';
import type { Component } from 'vue';

export type Tone =
    | 'neutral'
    | 'info'
    | 'violet'
    | 'success'
    | 'warn'
    | 'danger';

export interface ToneClasses {
    /** Nhãn / chip */
    chip: string;
    /** Chấm tròn */
    dot: string;
    /** Chữ màu */
    text: string;
    /** Khung nổi bật (hộp cảnh báo, thẻ) */
    box: string;
    /** Vạch màu mảnh / thanh */
    bar: string;
}

export const toneClasses: Record<Tone, ToneClasses> = {
    neutral: {
        chip: 'bg-muted text-muted-foreground',
        dot: 'bg-muted-foreground/50',
        text: 'text-muted-foreground',
        box: 'border-border bg-muted/50 text-foreground',
        bar: 'bg-muted-foreground/40',
    },
    info: {
        chip: 'bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300',
        dot: 'bg-sky-500',
        text: 'text-sky-700 dark:text-sky-300',
        box: 'border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-200',
        bar: 'bg-sky-500',
    },
    violet: {
        chip: 'bg-violet-50 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300',
        dot: 'bg-violet-500',
        text: 'text-violet-700 dark:text-violet-300',
        box: 'border-violet-200 bg-violet-50 text-violet-900 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-200',
        bar: 'bg-violet-500',
    },
    success: {
        chip: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
        dot: 'bg-emerald-500',
        text: 'text-emerald-700 dark:text-emerald-400',
        box: 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200',
        bar: 'bg-emerald-500',
    },
    warn: {
        chip: 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300',
        dot: 'bg-amber-500',
        text: 'text-amber-700 dark:text-amber-400',
        box: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200',
        bar: 'bg-amber-500',
    },
    danger: {
        chip: 'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300',
        dot: 'bg-red-500',
        text: 'text-red-600 dark:text-red-400',
        box: 'border-red-300 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200',
        bar: 'bg-red-500',
    },
};

/** Thẻ chuẩn của khu Tự động đăng (cùng kiểu Xưởng Video): bo 14px, viền 1px, bóng nhẹ nhiều lớp (sáng) / bề mặt nổi (tối). */
export const cardCls =
    'rounded-[14px] border bg-card text-card-foreground shadow-[0_1px_2px_rgba(28,25,23,.04),0_2px_6px_-1px_rgba(28,25,23,.06)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,.03),0_1px_2px_rgba(0,0,0,.35)]';

/** Bảng dữ liệu chuẩn: khung bo, đầu bảng dính, hàng rê chuột, số căn phải. */
export const tableWrapCls = 'overflow-auto rounded-xl border bg-card';
export const thCls =
    'sticky top-0 z-[1] whitespace-nowrap border-b bg-muted px-3.5 py-2.5 text-left text-xs font-medium tracking-[.01em] text-muted-foreground';
export const tdCls = 'border-b px-3.5 py-2.5 align-middle';

export interface StatusMeta {
    label: string;
    icon: Component;
    tone: Tone;
    /** Viền đứt cho trạng thái "dự kiến" */
    dashed?: boolean;
    spin?: boolean;
}

export const statusMeta: Record<string, StatusMeta> = {
    new: { label: 'Chờ đăng', icon: IconClock, tone: 'neutral' },
    reserved: { label: 'Giữ chỗ', icon: IconBookmark, tone: 'violet' },
    scheduled: { label: 'Đã xếp lịch', icon: IconCalendarCheck, tone: 'info' },
    publishing: {
        label: 'Đang đăng',
        icon: IconLoader2,
        tone: 'violet',
        spin: true,
    },
    tiktok_scheduled: {
        label: 'Đã hẹn trên TikTok',
        icon: IconBrandTiktok,
        tone: 'info',
    },
    posted: { label: 'Đã đăng', icon: IconCircleCheck, tone: 'success' },
    failed: { label: 'Lỗi', icon: IconAlertCircle, tone: 'danger' },
    skipped: { label: 'Bỏ qua', icon: IconPlayerSkipForward, tone: 'neutral' },
    projected: {
        label: 'Dự kiến',
        icon: IconCalendarTime,
        tone: 'neutral',
        dashed: true,
    },
};

export const statusOf = (key: string): StatusMeta =>
    statusMeta[key] ?? { label: key, icon: IconClock, tone: 'neutral' };

/** Mức độ sức khoẻ hệ thống → tông màu chung. */
export const healthTone: Record<'ok' | 'warn' | 'bad' | 'idle', Tone> = {
    ok: 'success',
    warn: 'warn',
    bad: 'danger',
    idle: 'neutral',
};

export const fmtNum = (n: number | null | undefined): string =>
    n === null || n === undefined ? '—' : n.toLocaleString('vi-VN');

/** 1234 → 1.234 ; 15000 → 15K ; 1500000 → 1,5M (cho số lớn trên thẻ / biểu đồ). */
export const fmtCompact = (n: number | null | undefined): string => {
    if (n === null || n === undefined) {
        return '—';
    }

    if (Math.abs(n) >= 1_000_000) {
        return `${(n / 1_000_000).toLocaleString('vi-VN', { maximumFractionDigits: 1 })}M`;
    }

    if (Math.abs(n) >= 10_000) {
        return `${(n / 1_000).toLocaleString('vi-VN', { maximumFractionDigits: 1 })}K`;
    }

    return n.toLocaleString('vi-VN', { maximumFractionDigits: 0 });
};

// Bảng trạng thái dùng chung cho cả khu "Tự động đăng": một trạng thái = một màu, một biểu tượng, một nhãn ở mọi trang.
import {
    IconAlertCircle,
    IconBolt,
    IconBookmark,
    IconBrandTiktok,
    IconCalendarCheck,
    IconCalendarTime,
    IconCircleCheck,
    IconClock,
    IconCloudUpload,
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
    // Hộp (box) mọi tông đều chữ thường trên nền gần trung tính; màu chỉ ở viền mảnh + biểu tượng/chữ khoá.
    info: {
        chip: 'bg-info-subtle text-info-text',
        dot: 'bg-info',
        text: 'text-info-text',
        box: 'border-info/30 bg-info/5 text-foreground',
        bar: 'bg-info',
    },
    violet: {
        chip: 'bg-primary-subtle text-primary-text',
        dot: 'bg-primary-strong',
        text: 'text-primary-text',
        box: 'border-primary-strong/30 bg-primary-strong/5 text-foreground',
        bar: 'bg-primary-strong',
    },
    success: {
        chip: 'bg-success-subtle text-success-text',
        dot: 'bg-success',
        text: 'text-success-text',
        box: 'border-success/30 bg-success/5 text-foreground',
        bar: 'bg-success',
    },
    warn: {
        chip: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
        dot: 'bg-amber-500',
        text: 'text-amber-700 dark:text-amber-400',
        box: 'border-amber-500/30 bg-amber-500/5 text-foreground',
        bar: 'bg-amber-500',
    },
    danger: {
        chip: 'bg-critical-subtle text-destructive-text',
        dot: 'bg-destructive',
        text: 'text-destructive-text',
        box: 'border-destructive/30 bg-destructive/5 text-foreground',
        bar: 'bg-destructive',
    },
};

/** Thẻ chuẩn của khu Tự động đăng (cùng kiểu Xưởng Video): bo 12px, viền 1px, bóng nhẹ (sáng) / bề mặt nổi (tối). */
export const cardCls = 'rounded-xl border bg-card text-card-foreground shadow-card';

/** Bảng dữ liệu chuẩn: khung bo, đầu bảng dính, hàng rê chuột, số căn phải. */
export const tableWrapCls = 'overflow-auto rounded-xl border bg-card';
export const thCls =
    'sticky top-0 z-[1] whitespace-nowrap border-b bg-muted px-4 py-2 text-left text-xs font-medium text-muted-foreground';
export const tdCls = 'border-b px-4 py-2 align-middle';

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
    scheduled: { label: 'Đã hẹn giờ', icon: IconCalendarCheck, tone: 'info' },
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
    // Lịch đăng: video đã xếp nhưng còn nằm trong app (sửa / xoá thoải mái).
    in_app: {
        label: 'Chưa lên TikTok',
        icon: IconClock,
        tone: 'neutral',
    },
    direct: { label: 'Đăng thẳng', icon: IconBolt, tone: 'violet' },
    uploading: {
        label: 'Đang gửi lên TikTok',
        icon: IconCloudUpload,
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

/**
 * Trạng thái hiển thị trên Lịch đăng: "scheduled" ở đây nghĩa là video đã xếp mà CHƯA gửi lên TikTok
 * (nơi khác "Đã hẹn giờ" vẫn giữ nghĩa cũ).
 */
export const lichStatus = (state: string): string =>
    state === 'scheduled' ? 'in_app' : state;

/** Video còn nằm trong app (chưa lên TikTok): sửa / xoá thoải mái. */
export const EDITABLE_STATES = ['scheduled', 'direct', 'reserved'];

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

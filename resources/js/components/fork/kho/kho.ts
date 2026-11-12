import { toast } from 'vue-sonner';

import type { Tone } from '@/components/fork/shared/status';
import dayjs from '@/dayjs';

export interface Readiness {
    code: string;
    severity: 'ok' | 'warn' | 'error' | 'muted';
    reason: string;
    next_slot: string | null;
}

export interface KhoVideo {
    id: number;
    file_name: string;
    product: string | null;
    product_code: string | null;
    quy_cach: string | null;
    goc: string | null;
    ngay_lam: string | null;
    status: string;
    legacy: boolean;
    caption: string | null;
    hashtags: string[];
    cart_name: string | null;
    channel: string | null;
    scheduled_for: string | null;
    posted_at: string | null;
    reason: string | null;
    /** Bài lỗi chắc chắn chưa lên TikTok: hiện nút "Thử lại". */
    can_retry?: boolean;
    readiness: Readiness | null;
    has_cover: boolean;
    duration: number | null;
    tiktok_link: string | null;
    can_preview: boolean;
    /** Bài đã hẹn sẵn trên TikTok : chưa tới giờ đăng. */
    on_tiktok_schedule?: boolean;
    product_image?: string | null;
    channel_avatar?: string | null;
    stats?: {
        views: number | null;
        likes: number | null;
        comments: number | null;
        shares: number | null;
        views_24h: number | null;
        saves?: number | null;
        views_72h?: number | null;
        avg_watch_s?: number | null;
        finish_rate?: number | null;
        new_followers?: number | null;
        traffic?: { key: string; value: number }[];
        collected_at?: string | null;
    } | null;
    comments?: {
        total: number;
        buy: number;
        rows: {
            id: number;
            text: string;
            author: string | null;
            likes: number;
            at: string | null;
            buy: boolean;
        }[];
    };
}

/** Mức độ của lý do sẵn sàng → tông màu chung của khu Tự động đăng. */
export const severityTone: Record<string, Tone> = {
    ok: 'success',
    warn: 'warn',
    error: 'danger',
    muted: 'neutral',
};

export const fmtTime = (iso: string | null): string =>
    iso ? dayjs(iso).format('HH:mm DD/MM') : '—';

export const fmtDuration = (s: number | null): string => {
    if (!s) {
        return '';
    }

    const total = Math.round(s);

    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
};

export const coverUrl = (id: number): string => `/auto/kho/video/${id}/cover`;
export const videoUrl = (id: number): string => `/auto/kho/video/${id}`;

/** Dòng tóm tắt hiện dưới thẻ video. */
export const cardLine = (v: KhoVideo): { text: string; tone: Tone } => {
    if (v.status === 'scheduled' || v.status === 'reserved') {
        return {
            text: v.scheduled_for
                ? `Đăng ${fmtTime(v.scheduled_for)}${v.channel ? ` · ${v.channel}` : ''}`
                : 'Đang giữ chỗ',
            tone: 'success',
        };
    }

    if (v.status === 'posted') {
        return { text: `Đã đăng ${fmtTime(v.posted_at)}`, tone: 'success' };
    }

    if (v.status === 'failed' || v.status === 'skipped') {
        return {
            text: v.reason ?? 'Không rõ lý do',
            tone: v.status === 'failed' ? 'danger' : 'warn',
        };
    }

    if (v.readiness) {
        return {
            text: v.readiness.reason,
            tone: severityTone[v.readiness.severity] ?? 'neutral',
        };
    }

    return { text: v.reason ?? 'Chờ xếp lịch', tone: 'neutral' };
};

/** Ngày dùng để gom nhóm: ngày đăng, ngày hẹn hoặc ngày làm video. */
export const dayKey = (v: KhoVideo): string => {
    const iso =
        v.status === 'posted'
            ? v.posted_at
            : v.status === 'scheduled' || v.status === 'reserved'
              ? v.scheduled_for
              : null;

    return iso ? dayjs(iso).format('YYYY-MM-DD') : (v.ngay_lam ?? '');
};

export const dayLabel = (key: string): string => {
    if (!key) {
        return 'Chưa rõ ngày';
    }

    const d = dayjs(key);
    const diff = d.startOf('day').diff(dayjs().startOf('day'), 'day');
    const text = d.format('DD/MM/YYYY');

    if (diff === 0) {
        return `Hôm nay · ${text}`;
    }

    if (diff === 1) {
        return `Ngày mai · ${text}`;
    }

    if (diff === -1) {
        return `Hôm qua · ${text}`;
    }

    return text;
};

export const captionText = (v: KhoVideo): string =>
    [v.caption, v.hashtags.join(' ')].filter(Boolean).join('\n\n');

/** Chép caption + hashtag vào bộ nhớ tạm và báo bằng thông báo (toast). */
export const copyCaption = async (v: KhoVideo): Promise<boolean> => {
    const text = captionText(v);

    if (!text) {
        toast.error('Video này chưa có caption để chép.');

        return false;
    }

    try {
        await navigator.clipboard.writeText(text);
        toast.success('Đã chép caption và hashtag.');

        return true;
    } catch {
        toast.error('Không chép được, hãy chép thủ công.');

        return false;
    }
};

// Kiểu dữ liệu dùng chung của trang "Lịch đăng" (/auto).

export interface Cart {
    sync_state: 'idle' | 'waiting' | 'error' | 'expired' | 'done';
    synced_at: string | null;
    products_count: number;
    linked_count: number;
}

export interface HourRec {
    hour: number;
    avg_views: number;
    samples: number;
    delta_pct: number;
}

export interface Recommendation {
    hours: HourRec[] | null;
    reason: string | null;
    videos: number;
    days: number;
    overall_avg: number;
}

export interface AccountRow {
    cart: Cart;
    id: string;
    username: string | null;
    display_name: string | null;
    timezone: string;
    avatar_url: string | null;
    chrome_enabled: boolean;
    enabled: boolean;
    daily_cap: number;
    /** Hẹn trước bao nhiêu ngày (1-9). Bản server cũ chưa gửi thì coi là 3. */
    schedule_ahead_days?: number;
    window_start: number;
    window_end: number;
    mode: 'explore' | 'optimized';
    preferred_hours: number[];
    explore_ratio: number;
    paused_reason: string | null;
    recommendation: Recommendation | null;
}

export interface HealthChannel {
    id: string;
    chrome_enabled: boolean;
    chrome_online: boolean;
    chrome_last_seen: string | null;
}

export interface Health {
    telegram: boolean;
    hub_api: boolean;
    channels: HealthChannel[];
}

export interface HubStatus {
    state: string;
    label: string;
}

export type SlotState =
    | 'posted'
    | 'scheduled'
    | 'tiktok_scheduled'
    | 'publishing'
    | 'reserved'
    | 'failed'
    | 'projected';

export interface LichItem {
    id: number | null;
    video_id?: number | null;
    state: SlotState;
    at: string;
    day: string;
    product_code: string | null;
    product_label: string | null;
    cart_name: string | null;
    product_image?: string | null;
    caption?: string | null;
    empty_reason?: string | null;
    link: string | null;
    error: string | null;
}

export interface BlockedGroup {
    code: string;
    quy_cach: string | null;
    label: string;
    count: number;
    image?: string | null;
}

export interface LichChannel {
    items: LichItem[];
    note: string | null;
    blocked: BlockedGroup[];
    warnings: string[];
    today: { planned: number; posted: number; cap: number };
}

export interface Lich {
    days: { key: string; label: string; date: string }[];
    channels: Record<string, LichChannel>;
}

export interface RecentRow {
    id: number;
    file_name: string;
    product_code: string | null;
    product_image?: string | null;
    cart_name?: string | null;
    caption?: string | null;
    username: string | null;
    posted_at: string | null;
    views: number | null;
    views_24h: number | null;
    link: string | null;
}

export interface ProductRow {
    code: string;
    name: string;
    short_name: string;
    image?: string | null;
    enabled: boolean;
    counts: {
        new: number;
        scheduled: number;
        posted: number;
        skipped: number;
        failed: number;
    };
}

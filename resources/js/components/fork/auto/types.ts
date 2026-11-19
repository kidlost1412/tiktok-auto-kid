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
    /** Nguồn video: Xưởng + Kho riêng / chỉ Kho riêng / chỉ Xưởng. */
    video_source?: 'both' | 'rieng' | 'hub';
    /** Tự trộn xen kẽ sản phẩm cho các bài chưa gửi lên TikTok. */
    mix_products?: boolean;
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
    /** Khung giờ đăng thẳng: nằm trong app tới giờ, Chrome đăng ngay lúc đó. */
    | 'direct'
    /** Chrome đang tải bài hẹn giờ lên TikTok (khoá tạm vài phút). */
    | 'uploading'
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
    /** Giờ dự kiến nằm trong khung đăng thẳng. */
    direct?: boolean;
    link: string | null;
    error: string | null;
    /** Lý do đầy đủ của bài không đăng được (hiện khi rê chuột vào dòng lỗi). */
    error_full?: string | null;
    /** Ghi chú cảnh báo (vd. bài đang giữ trong app vì kênh đã đủ số bài hẹn giờ trên TikTok). */
    note?: string | null;
    /** Kiểm giỏ trước giờ đăng: giỏ của bài đã hết hàng / không còn trong shop. */
    cart_warn?: string | null;
    /** Nguồn video: hub | rieng (Kho riêng) | ... */
    source?: string | null;
    /** Đổi giờ được không (bài đã xếp mà chưa đăng, Chrome không đang tải lên). */
    can_reschedule?: boolean;
    /** Yêu cầu đổi giờ gần nhất (trong 24 giờ). */
    reschedule?: RescheduleRequest | null;
}

export interface RescheduleRequest {
    id: string;
    state: 'pending' | 'claimed' | 'done' | 'failed' | 'expired' | 'unknown';
    open: boolean;
    message: string;
    new_at: string | null;
    old_at: string | null;
    at: string | null;
}

/** GET /auto/videos/{id}/doi-gio */
export interface RescheduleInfo {
    id: number;
    kind: 'local' | 'tiktok' | null;
    reason: string | null;
    current_at: string | null;
    rules: {
        timezone: string;
        min_lead_minutes: number;
        max_ahead_hours: number;
    };
    /** Giờ (ISO) các bài khác cùng kênh quanh bây giờ, để báo bài trước/sau. */
    channel_times?: string[];
    request: RescheduleRequest | null;
}

/** Một dòng của bảng lịch: bài trong lịch kèm kênh của nó. */
export interface ScheduleEntry extends LichItem {
    channelId: string;
    username: string;
    /** Chỉ số màu của kênh (channelColors.ts), cố định theo thứ tự kênh. */
    color?: number;
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
    /** Dữ liệu sản phẩm shop của kênh đã cũ: app chưa kiểm được giỏ của bài sắp đăng. */
    cart_stale?: string | null;
    blocked: BlockedGroup[];
    warnings: string[];
    today: { planned: number; posted: number; cap: number };
}

/** "Khung giờ đăng thẳng" (DirectWindow.php). */
export interface DirectWindow {
    enabled: boolean;
    start: string;
    end: string;
    days: number[];
    margin_minutes: number;
    catch_up_minutes: number;
    off_channels: string[];
}

export interface Lich {
    days: { key: string; label: string; date: string }[];
    channels: Record<string, LichChannel>;
}

export interface RecentRow {
    id: number;
    file_name: string;
    source?: string | null;
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

/** Một ngày trong 7 ngày gần nhất: số bài đã lên TikTok và tổng lượt xem mới nhất của chúng. */
export interface TrendDay {
    date: string;
    label: string;
    posts: number;
    views: number;
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

/** Bài lỗi gần đây (khu "Gần đây"), kèm cờ có thử lại an toàn hay không. */
export interface FailedRow {
    id: number;
    source?: string | null;
    product_code: string | null;
    product_image?: string | null;
    username: string | null;
    at: string | null;
    error: string | null;
    can_retry: boolean;
    retry_note: string | null;
    /** Chrome không rõ đã gửi: chủ app kiểm tra TikTok rồi xác nhận "chưa lên" để đăng lại. */
    can_confirm_retry?: boolean;
}

export interface OnboardingStep {
    key: 'xuong' | 'chrome' | 'stock' | 'auto';
    title: string;
    done: boolean;
    state: 'done' | 'todo' | 'waiting' | 'offline';
    detail: string;
    action: { label: string; href: string } | null;
}

/** Thẻ "Bắt đầu" cho máy mới cài; null = đã xong hoặc đã ẩn. */
export interface Onboarding {
    steps: OnboardingStep[];
    done: number;
    total: number;
}

/** Lý do một bài không đăng được, đã dịch sang tiếng Việt (máy chủ: FailureReasons). */
export interface PostFailure {
    code: string;
    /** Chuyện gì xảy ra, 1 câu. */
    title: string;
    /** Nhãn rất ngắn cho dòng trong Lịch ("Hết hàng"). */
    short: string;
    /** Việc nên làm. */
    fix: string;
    /** title + fix, 1 câu liền. */
    text: string;
    /** job: bài còn hẹn giờ, lượt Chrome lỗi (Đăng lại = giao lại Chrome). video: bài đã chốt lỗi (Thử lại = về kho). */
    kind: 'job' | 'video';
    state: 'failed' | 'uncertain';
    at: string | null;
    failed_at: string | null;
    can_retry: boolean;
    retry_note: string | null;
    can_confirm_retry: boolean;
}

/** Một dòng của khối "Bài không đăng được" ở Tổng quan. */
export interface FailedPostRow extends PostFailure {
    id: number;
    username: string | null;
    product_code: string | null;
    product_label: string | null;
    product_image?: string | null;
    source?: string | null;
    caption: string | null;
}

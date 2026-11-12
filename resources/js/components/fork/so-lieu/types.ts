// Kiểu dữ liệu của trang "Số liệu" (/auto/so-lieu).

export interface Kpi {
    value: number;
    prev: number;
    delta_pct: number | null;
}

export type KpiKey =
    | 'posts'
    | 'views'
    | 'avg_views'
    | 'likes'
    | 'comments'
    | 'shares'
    | 'saves'
    | 'avg_watch_s'
    | 'finish_rate'
    | 'engagement';

export interface StatVideo {
    id: number;
    file_name: string;
    posted_at: string;
    date: string;
    hour: number;
    social_account_id: string | null;
    channel: string | null;
    product_code: string | null;
    quy_cach: string | null;
    cart_name: string | null;
    product_image?: string | null;
    goc: string | null;
    giong: string | null;
    nhac: string | null;
    diem: string | number | null;
    thoi_luong: number | null;
    caption: string | null;
    has_metrics: boolean;
    views: number;
    likes: number;
    comments: number;
    shares: number;
    saves: number;
    interactions: number;
    engagement: number;
    views_24h: number | null;
    views_72h: number | null;
    link: string | null;
    avg_watch_s: number | null;
    /** Phần trăm xem hết (0-100) */
    finish_rate: number | null;
    new_followers: number | null;
    traffic: { key: string; value: number }[];
    collected_at: string | null;
}

export interface Group {
    key: string;
    label: string;
    posts: number;
    views: number;
    avg_views: number;
    engagement: number;
}

export interface DailyPoint {
    date: string;
    posts: number;
    views: number;
}

export interface Filters {
    range: 'today' | '7d' | '30d' | 'custom';
    from: string;
    to: string;
    channel: string;
    product: string;
    goc: string;
    giong: string;
    sort: 'moi' | 'view' | 'tuong-tac';
    cm: 'all' | 'mua';
}

export interface Options {
    channels: { id: string; name: string }[];
    products: { code: string; name: string }[];
    goc: string[];
    giong: string[];
}

export interface BarPoint {
    key: string;
    /** Nhãn trục ngang (có thể rỗng để ẩn bớt) */
    axis: string;
    /** Tiêu đề trong khung chú thích */
    title: string;
    value: number;
    sub?: string;
}

export interface Followers {
    current: number;
    change: number | null;
    series: { date: string; followers: number; gain: number | null }[];
    at: string | null;
}

export interface CommentRow {
    id: number;
    text: string;
    author: string | null;
    handle: string | null;
    likes: number;
    replies: number;
    at: string | null;
    buy: boolean;
    keywords: string | null;
    video_id: number | null;
    video_label: string | null;
    channel: string | null;
    link: string | null;
}

export interface CommentsData {
    counts: { total: number; buy: number; buy_24h: number };
    rows: CommentRow[];
}

export interface ExtensionInfo {
    connected: boolean;
    version: string | null;
    outdated: boolean;
    min: string;
    last_seen_at: string | null;
}

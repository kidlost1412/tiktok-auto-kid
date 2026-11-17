// Kiểu dữ liệu + hàm gọi máy chủ dùng chung của trang Kho riêng.

import type { BatchAccount } from '@/components/fork/kho/BatchDialog.vue';

/** Video trùng nội dung với một video đã có: `text` là câu hiển thị sẵn (do máy chủ ghép). */
export interface Folder {
    id: number;
    name: string;
    path: string;
    exists: boolean;
    count: number;
}

export interface Selectable {
    id: number;
    file_name: string;
    duration?: number | null;
    duplicate: string | null;
}

/** Bộ lọc đang xem của Kho riêng (dùng cho bàn Thủ kho). */
export interface RiengLoc {
    folder: number;
    status: string;
    day: string;
    page?: number;
}

/** Props của trang Kho riêng (và của KhoRiengBody dùng chung với bàn Thủ kho). */
export type RiengPageProps = {
    folders: Folder[];
    filters: { folder: number; status: string; day: string };
    counts: Record<string, number>;
    days: string[];
    videos: {
        data: RiengVideo[];
        current_page: number;
        last_page: number;
        total: number;
    };
    selectable: Selectable[];
    queue: QueueItem[];
    scan_sig: string;
    accounts: BatchAccount[];
    hashtag_suggestions?: { tag: string; uses: number }[];
    limits: {
        min_lead_minutes: number;
        gap_minutes: number;
        caption_max: number;
    };
    last_scan_at: string | null;
};

export interface Duplicate {
    id: number;
    where: 'hub' | 'rieng' | 'gone';
    state: string;
    text: string;
    link: string | null;
}

export interface RiengProduct {
    code: string;
    name: string;
    image: string | null;
}

export interface RiengVideo {
    id: number;
    file_name: string;
    folder: string;
    rel_path: string | null;
    file_date: string | null;
    file_time: string | null;
    duration: number | null;
    status: string;
    gone: boolean;
    channel: string | null;
    scheduled_for: string | null;
    posted_at: string | null;
    tiktok_link: string | null;
    reason: string | null;
    can_retry: boolean;
    selectable: boolean;
    can_preview: boolean;
    duplicate: Duplicate | null;
    product: RiengProduct | null;
    /** Kho riêng tự đăng theo khung (AI xem video, sản phẩm, caption, kênh). */
    auto?: RiengAuto | null;
}

export interface RiengAuto {
    ai_state: 'ok' | 'unsure' | 'error' | 'gave_up' | null;
    ai_product: string | null;
    ai_sure: 'cao' | 'vua' | 'thap' | null;
    ai_reason: string | null;
    ai_summary: string | null;
    ai_caption: string | null;
    ai_hashtags: string[];
    ai_error: string | null;
    ai_tries: number;
    ai_next_try_at: string | null;
    /** Hashtag chủ app tự sửa (null = dùng hashtag AI). */
    kid_hashtags: string[] | null;
    /** AI đang xem: bậc mấy / tổng, việc gì. */
    ai_progress: {
        buoc: number;
        tong: number;
        viec: string;
        tu: string;
        luc: string;
    } | null;
    /** Các bậc AI đã thử lần gần nhất. */
    ai_steps: { buoc: string; ket_qua: string }[];
    /** Lời nói app nghe được trong video. */
    ai_heard: string | null;
    ai_at: string | null;
    approved: boolean;
    product_by: 'kid' | 'ai' | null;
    product_code: string | null;
    quy_cach: string | null;
    kid_caption: string | null;
    final_caption: string | null;
    channels: string[];
    effective_channels: string[];
    dup_ok: boolean;
    auto_error: string | null;
    ready: boolean;
    blocker: string | null;
}

export interface AutoSettings {
    enabled: boolean;
    caption_mode: 'ai' | 'kid';
    empty_caption_ok: boolean;
    approve_first: boolean;
    duplicates: 'ask' | 'allow';
    model: string;
    effort: string;
    fast: boolean;
    folder_channels: Record<string, string[]>;
}

/** Một model ChatGPT trong Codex CLI. */
export interface AutoModel {
    name: string;
    note: string;
    efforts: string[];
    /** Có chế độ Fast (chỉ biết khi lấy từ tài khoản; gói free không có). */
    fast?: boolean;
}

/** Trạng thái cài ChatGPT CLI (Codex) của app. */
export interface CliStatus {
    installed: boolean;
    installing: boolean;
    node: boolean;
    error: string | null;
}

export interface ChatGptAccount {
    id: string;
    email: string | null;
    plan: string | null;
    ready: boolean;
    logging_in: boolean;
    cooldown_until: string | null;
    last_error: string | null;
    last_used_at: string | null;
    uses: number;
}

export interface AutoPayload {
    settings: AutoSettings;
    models: Record<string, AutoModel>;
    /** true: danh sách model lấy từ tài khoản ChatGPT thật của anh. */
    models_from_accounts: boolean;
    /** Model app thật sự dùng khi model đã chọn không có ở tài khoản nào. */
    model_effective: string | null;
    efforts: Record<string, string>;
    codex_installed: boolean;
    cli: CliStatus;
    /** Bộ nghe lời nói (Whisper trên máy). */
    speech: {
        python: boolean;
        installed: boolean;
        installing: boolean;
        error: string | null;
    };
    chatgpt: ChatGptAccount[];
    channels: {
        id: string;
        name: string;
        avatar_url: string | null;
        auto_enabled: boolean;
    }[];
    folders: { id: number; name: string }[];
    products: {
        code: string;
        name: string;
        quy_cach: { ma: string; ten: string }[];
    }[];
    counts: Record<string, number>;
}

/** Một mục trong "Giỏ chờ đăng". */
export interface QueueItem {
    id: number;
    file_name: string;
    duration: number | null;
    duplicate: string | null;
}

/** Video đưa vào hộp thoại đăng: kèm cờ trùng để hộp thoại cảnh báo. */
export interface BatchItem {
    id: number;
    file_name: string;
    /** Thời lượng (giây) để hiện trên hình nhỏ; không có cũng được. */
    duration?: number | null;
    duplicate?: string | null;
}

export const xsrf = (): string =>
    decodeURIComponent(document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '');

/**
 * Gọi JSON tới máy chủ với method bất kỳ; trả { ok, data } (data là JSON trả về kể cả khi máy chủ báo lỗi 422).
 */
export async function callJson<T = Record<string, unknown>>(
    method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
    url: string,
    body?: unknown,
): Promise<{ ok: boolean; data: T | null }> {
    try {
        const r = await fetch(url, {
            method,
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-XSRF-TOKEN': xsrf(),
            },
            credentials: 'same-origin',
            body: body === undefined ? undefined : JSON.stringify(body),
        });
        const data = (await r.json().catch(() => null)) as T | null;

        return { ok: r.ok, data };
    } catch {
        return { ok: false, data: null };
    }
}

/** POST JSON tới máy chủ; trả null nếu lỗi mạng hoặc máy chủ báo lỗi. */
export async function postJson<T = Record<string, unknown>>(
    url: string,
    body: unknown = {},
): Promise<T | null> {
    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-XSRF-TOKEN': xsrf(),
            },
            credentials: 'same-origin',
            body: JSON.stringify(body),
        });

        return r.ok ? ((await r.json()) as T) : null;
    } catch {
        return null;
    }
}

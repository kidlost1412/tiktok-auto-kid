// Kiểu dữ liệu + hàm gọi máy chủ dùng chung của trang Kho riêng.

/** Video trùng nội dung với một video đã có: `text` là câu hiển thị sẵn (do máy chủ ghép). */
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
    duplicate?: string | null;
}

export const xsrf = (): string =>
    decodeURIComponent(document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '');

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

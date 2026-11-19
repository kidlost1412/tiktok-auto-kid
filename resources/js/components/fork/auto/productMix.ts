// Gọi API "Trộn xen kẽ sản phẩm" (ProductMixController): xem trước, áp dụng, hoàn tác.

export interface MixRow {
    id: number;
    at: string;
    product: string;
    name: string;
    fixed: boolean;
}

export interface MixPreview {
    account_id: string;
    movable: number;
    changed: number;
    locked: number;
    pinned: number;
    products: number;
    before: MixRow[];
    after: MixRow[];
    message: string;
}

export interface MixUndoRow {
    id: number;
    at: string;
}

export interface MixResult {
    moved: number;
    undo: MixUndoRow[];
    message: string;
}

interface Res<T> {
    ok: boolean;
    data: T | null;
    error: string | null;
}

async function call<T>(
    method: 'GET' | 'POST',
    url: string,
    body?: unknown,
): Promise<Res<T>> {
    const xsrf = decodeURIComponent(
        document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '',
    );

    try {
        const r = await fetch(url, {
            method,
            headers: {
                Accept: 'application/json',
                'X-XSRF-TOKEN': xsrf,
                ...(body === undefined
                    ? {}
                    : { 'Content-Type': 'application/json' }),
            },
            credentials: 'same-origin',
            body: body === undefined ? undefined : JSON.stringify(body),
        });
        const data = (await r.json().catch(() => null)) as
            | (T & { ok?: boolean; error?: string; message?: string })
            | null;

        if (!r.ok || !data || data.ok === false) {
            return {
                ok: false,
                data: null,
                error:
                    data?.error ??
                    data?.message ??
                    (r.status === 429
                        ? 'Bấm hơi nhanh, chờ một chút rồi thử lại.'
                        : 'Có lỗi, hãy thử lại.'),
            };
        }

        return { ok: true, data, error: null };
    } catch {
        return {
            ok: false,
            data: null,
            error: 'Mất kết nối với app, hãy thử lại.',
        };
    }
}

const base = (id: string) =>
    `/auto/accounts/${encodeURIComponent(id)}/tron-san-pham`;

export const mixPreview = (id: string, includePinned: boolean) =>
    call<MixPreview>(
        'GET',
        `${base(id)}${includePinned ? '?include_pinned=1' : ''}`,
    );

export const mixApply = (id: string, includePinned: boolean) =>
    call<MixResult>('POST', base(id), { include_pinned: includePinned });

export const mixUndo = (id: string, undo: MixUndoRow[]) =>
    call<MixResult>('POST', `${base(id)}/hoan-tac`, { undo });

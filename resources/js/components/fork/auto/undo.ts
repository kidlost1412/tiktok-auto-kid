// "Hoàn tác" cho thao tác trên Lịch đăng (đổi giờ / kéo thả, bỏ xếp lịch, xoá): thao tác chỉ thật sự gửi đi sau vài giây.
// Trong lúc đó thông báo có nút "Hoàn tác" — bấm là coi như chưa làm gì, không cần gọi lại server.
import { reactive } from 'vue';
import { toast } from 'vue-sonner';

import { confirm } from '@/composables/useConfirm';
import dayjs from '@/dayjs';

const UNDO_SECONDS = 8;

/**
 * Video đang chờ thao tác (trong 8 giây "Hoàn tác" hoặc đang gửi): id -> nhãn hiện trên dòng lịch.
 * Dòng nào nằm trong đây thì mờ đi và không thao tác thêm được.
 */
export const pendingIds = reactive(new Map<number, string>());

export const PENDING_REMOVE = 'Đang chờ xoá…';
export const PENDING_MOVE = 'Đang chờ đổi giờ…';

// Thao tác đang chờ gửi: rời trang thì gửi luôn (không để mất thao tác anh đã chọn).
const pending = new Set<() => void>();

if (typeof window !== 'undefined') {
    window.addEventListener('pagehide', () => {
        for (const fire of [...pending]) {
            fire();
        }
    });
}

export function undoable(
    message: string,
    commit: () => void | Promise<void>,
    /** Video đang bị thao tác + nhãn hiện trên dòng lịch trong lúc chờ. */
    mark?: { id: number | null | undefined; label: string },
): void {
    let settled = false;
    const id = mark?.id ?? null;

    if (id !== null && mark) {
        pendingIds.set(id, mark.label);
    }

    const fire = () => {
        if (settled) {
            return;
        }

        settled = true;
        pending.delete(fire);
        void Promise.resolve(commit()).finally(() => {
            if (id !== null) {
                pendingIds.delete(id);
            }
        });
    };

    pending.add(fire);

    toast(message, {
        description: `Lỡ tay thì bấm "Hoàn tác" trong ${UNDO_SECONDS} giây.`,
        duration: UNDO_SECONDS * 1000,
        action: {
            label: 'Hoàn tác',
            onClick: () => {
                if (settled) {
                    return;
                }

                settled = true;
                pending.delete(fire);

                if (id !== null) {
                    pendingIds.delete(id);
                }

                toast.success('Đã hoàn tác, bài giữ nguyên.');
            },
        },
        onAutoClose: fire,
        onDismiss: fire,
    });
}

/** POST JSON tới app (giữ kết nối cả khi đang rời trang). */
export async function postJson(
    url: string,
    body: unknown = {},
): Promise<{
    ok: boolean;
    data: { ok?: boolean; state?: string; message?: string } | null;
}> {
    const xsrf = decodeURIComponent(
        document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '',
    );

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-XSRF-TOKEN': xsrf,
            },
            credentials: 'same-origin',
            keepalive: true,
            body: JSON.stringify(body),
        });
        const data = (await r.json().catch(() => null)) as {
            ok?: boolean;
            state?: string;
            message?: string;
        } | null;

        return { ok: r.ok && !!data?.ok, data };
    } catch {
        return {
            ok: false,
            data: { message: 'Mất kết nối với app, hãy thử lại.' },
        };
    }
}

/**
 * Ngày mới đã đủ số bài/ngày của kênh thì hỏi lại "Vẫn dời" / "Thôi" (app không tự chặn quyết định của chủ app).
 * Không kiểm được (mất mạng...) thì coi như cho dời, như trước.
 */
async function okForDay(id: number, at: string): Promise<boolean> {
    const { data } = await postJson(`/auto/videos/${id}/doi-gio/kiem`, { at });
    const load = data as { full?: boolean; message?: string | null } | null;

    if (!load?.full) {
        return true;
    }

    return confirm({
        title: 'Ngày này kênh đã đủ bài',
        description: `${load.message ?? ''} Vẫn dời bài sang ngày này?`,
        confirmText: 'Vẫn dời',
        cancelText: 'Thôi',
    });
}

/** Dời giờ một bài trên Lịch đăng, có "Hoàn tác". `at`: giờ mới (ISO). */
export async function moveWithUndo(
    entry: {
        id?: number | null;
        state?: string;
        product_label?: string | null;
        product_code?: string | null;
    },
    at: string,
    onDone?: () => void,
): Promise<void> {
    const id = entry.id;

    // Bài đang chờ một thao tác khác (xoá / đổi giờ): bỏ qua lần thả thứ hai.
    if (!id || pendingIds.has(id)) {
        return;
    }

    // Khoá dòng ngay từ lúc hỏi "ngày đã đủ bài", để không thả thêm lần nữa.
    pendingIds.set(id, PENDING_MOVE);

    if (!(await okForDay(id, at))) {
        pendingIds.delete(id);
        toast('Đã giữ nguyên giờ cũ.');
        onDone?.();

        return;
    }

    const url = `/auto/videos/${entry.id}/doi-gio`;
    const name = entry.product_label ?? entry.product_code ?? 'bài';
    const onTikTok = entry.state === 'tiktok_scheduled';

    undoable(
        `Dời ${name} sang ${dayjs(at).format('HH:mm DD/MM')}`,
        async () => {
            const { ok, data } = await postJson(url, { at });

            if (!ok) {
                toast.error(
                    data?.message ?? 'Không đổi được giờ, hãy thử lại.',
                );
            } else if (data?.state === 'pending' || onTikTok) {
                toast.info(
                    'Đang nhờ Chrome xoá bài hẹn cũ trên TikTok rồi hẹn lại giờ mới.',
                );
            } else {
                toast.success(data?.message ?? 'Đã đổi giờ.');
            }

            onDone?.();
        },
        { id, label: PENDING_MOVE },
    );
}

// "Hoàn tác" cho thao tác trên Lịch đăng (đổi giờ / kéo thả, bỏ xếp lịch, xoá): thao tác chỉ thật sự gửi đi sau vài giây.
// Trong lúc đó thông báo có nút "Hoàn tác" — bấm là coi như chưa làm gì, không cần gọi lại server.
import { toast } from 'vue-sonner';

const UNDO_SECONDS = 8;

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
): void {
    let settled = false;

    const fire = () => {
        if (settled) {
            return;
        }

        settled = true;
        pending.delete(fire);
        void commit();
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

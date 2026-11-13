// Khung xem video dùng chung: bấm bất kỳ video nào ở bất kỳ trang nào đều mở cùng một cửa sổ.
// Chỉ cần id; thông tin đầy đủ lấy từ /auto/kho/video/{id}/info (có bộ nhớ đệm), ←/→ chuyển trong danh sách đang xem.
import { reactive } from 'vue';

import type { KhoVideo } from '@/components/fork/kho/kho';

export const viewer = reactive<{
    open: boolean;
    ids: number[];
    index: number;
    cache: Record<number, KhoVideo | 'error'>;
}>({ open: false, ids: [], index: 0, cache: {} });

/**
 * Việc riêng của trang đang mở (Kho riêng đăng ký lúc mở trang, gỡ khi rời): khung xem video chỉ hiện nút
 * "Đăng / hẹn giờ" và "Thêm vào giỏ chờ" khi trang đã đăng ký.
 */
export const viewerActions = reactive<{
    post: ((id: number) => void) | null;
    toggleQueue: ((id: number) => void) | null;
    isQueued: ((id: number) => boolean) | null;
}>({ post: null, toggleQueue: null, isQueued: null });

const inflight = new Set<number>();

export const loadVideo = async (id: number, force = false): Promise<void> => {
    if ((!force && viewer.cache[id]) || inflight.has(id)) {
        return;
    }

    inflight.add(id);

    try {
        const res = await fetch(`/auto/kho/video/${id}/info`, {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });
        viewer.cache[id] = res.ok ? ((await res.json()) as KhoVideo) : 'error';
    } catch {
        viewer.cache[id] = 'error';
    } finally {
        inflight.delete(id);
    }
};

/** Mở khung xem. `ids` là danh sách đang hiển thị (để chuyển qua lại), `id` là video bấm vào. */
export const openVideo = (ids: number[], id: number, known?: KhoVideo[]) => {
    for (const v of known ?? []) {
        viewer.cache[v.id] = v;
    }

    const list = ids.includes(id) ? ids : [id];
    viewer.ids = list;
    viewer.index = list.indexOf(id);
    viewer.open = true;
    // Làm mới ngầm để thấy trạng thái mới nhất (ví dụ vừa đăng xong).
    void loadVideo(id, !known);
};

export const stepVideo = (delta: number) => {
    const next = viewer.index + delta;

    if (next >= 0 && next < viewer.ids.length) {
        viewer.index = next;
        void loadVideo(viewer.ids[next]);
        // Nạp trước video kề bên.
        [next - 1, next + 1].forEach((i) => {
            if (viewer.ids[i]) {
                void loadVideo(viewer.ids[i]);
            }
        });
    }
};

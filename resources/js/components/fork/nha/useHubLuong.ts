// Nghe luồng tin tức thì (SSE) của hub Xưởng Video: `${hub}/api/luong` đẩy `event: doi` mỗi khi có sự kiện sản xuất mới,
// số video chờ duyệt đổi hoặc lô bắt đầu/dừng. Trình duyệt nghe thẳng hub (hub cho phép đúng origin của app).
//
// - `ok` = true khi đang nối và đã nhận bản tin đầu → trang có thể hỏi thưa; false (chưa nối / rớt / hub cũ chưa có SSE)
//   → trang giữ nhịp hỏi nhanh như cũ.
// - Rớt thì tự nối lại với thời gian chờ tăng dần (1s → 30s). Tab ẩn thì đóng hẳn, hiện lại thì nối lại ngay.
import { onBeforeUnmount, ref, watch } from 'vue';

export interface HubDoi {
    n: number;
    cho_duyet: number | null;
    chay: boolean;
}

const CHO_TOI_DA = 30000;

/** @param url Địa chỉ hub (vd http://127.0.0.1:8765) hoặc null/'' khi chưa nên nối. */
export const useHubLuong = (url: () => string | null | undefined) => {
    const ok = ref(false);
    const cbs = new Set<(d: HubDoi) => void>();
    let es: EventSource | null = null;
    let retry: number | undefined;
    let cho = 1000;
    let alive = true;

    const dong = () => {
        window.clearTimeout(retry);
        es?.close();
        es = null;
        ok.value = false;
    };

    const noi = () => {
        dong();
        const base = (url() ?? '').replace(/\/+$/, '');

        if (
            !alive ||
            !base ||
            document.hidden ||
            typeof EventSource === 'undefined'
        ) {
            return;
        }
        const src = new EventSource(`${base}/api/luong`);
        es = src;
        src.addEventListener('doi', (ev) => {
            let d: HubDoi | null = null;

            try {
                d = JSON.parse((ev as MessageEvent).data) as HubDoi;
            } catch {
                d = null;
            }
            ok.value = true;
            cho = 1000;

            if (d) {
                cbs.forEach((f) => f(d));
            }
        });
        src.onerror = () => {
            // Tự quản việc nối lại (EventSource tự nối cố định 3s, không lùi dần).
            src.close();

            if (es === src) {
                es = null;
            }
            ok.value = false;
            window.clearTimeout(retry);

            if (alive && !document.hidden) {
                retry = window.setTimeout(noi, cho);
                cho = Math.min(cho * 2, CHO_TOI_DA);
            }
        };
    };

    const onVis = () => (document.hidden ? dong() : noi());

    watch(
        () => url() ?? '',
        () => {
            cho = 1000;
            noi();
        },
        { immediate: true },
    );
    document.addEventListener('visibilitychange', onVis);
    onBeforeUnmount(() => {
        alive = false;
        document.removeEventListener('visibilitychange', onVis);
        dong();
        cbs.clear();
    });

    return {
        ok,
        /** Đăng ký nghe; trả hàm huỷ. */
        onDoi: (cb: (d: HubDoi) => void) => {
            cbs.add(cb);

            return () => cbs.delete(cb);
        },
    };
};

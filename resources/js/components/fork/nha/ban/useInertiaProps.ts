// Đọc props của một trang Inertia CÓ SẴN (vd /auto, /auto/gio-hang) dưới dạng JSON để dùng trong popup,
// không phải viết thêm API. Gửi đúng header Inertia => máy chủ trả {component, props, ...} thay vì HTML.
// `only` = partial reload (chỉ lấy vài prop, nhanh hơn; cũng là cách lấy prop "defer").
import { usePage } from '@inertiajs/vue3';
import { onBeforeUnmount, ref, shallowRef } from 'vue';

export function useInertiaProps<T extends Record<string, unknown>>(
    url: string,
    component: string,
    only?: string[],
) {
    const page = usePage();
    const props = shallowRef<T | null>(null);
    const loading = ref(false);
    const error = ref<string | null>(null);
    let ctrl: AbortController | null = null;

    const reload = async (onlyNow: string[] | undefined = only) => {
        ctrl?.abort();
        ctrl = new AbortController();
        loading.value = true;
        error.value = null;
        try {
            const headers: Record<string, string> = {
                'X-Inertia': 'true',
                'X-Requested-With': 'XMLHttpRequest',
                Accept: 'text/html, application/xhtml+xml',
            };
            if (page.version) {
                headers['X-Inertia-Version'] = String(page.version);
            }
            if (onlyNow?.length) {
                headers['X-Inertia-Partial-Component'] = component;
                headers['X-Inertia-Partial-Data'] = onlyNow.join(',');
            }
            const r = await fetch(url, {
                headers,
                credentials: 'same-origin',
                signal: ctrl.signal,
            });
            if (r.status === 409) {
                // Bản app vừa cập nhật: tải lại trang cho đồng bộ.
                window.location.reload();

                return;
            }
            if (!r.ok) {
                throw new Error(String(r.status));
            }
            const j = (await r.json()) as { props?: T };
            const next = (j.props ?? {}) as T;
            // partial reload: gộp vào dữ liệu cũ
            props.value =
                onlyNow?.length && props.value
                    ? ({ ...props.value, ...next } as T)
                    : next;
        } catch (e) {
            if ((e as Error).name !== 'AbortError') {
                error.value = 'Chưa tải được dữ liệu, thử lại sau ít giây.';
            }
        } finally {
            loading.value = false;
        }
    };

    onBeforeUnmount(() => ctrl?.abort());

    return { props, loading, error, reload };
}

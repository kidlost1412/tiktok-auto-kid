// Đọc props của một trang Inertia CÓ SẴN (vd /auto, /auto/gio-hang) dưới dạng JSON để dùng trong popup,
// không phải viết thêm API. Gửi đúng header Inertia => máy chủ trả {component, props, ...} thay vì HTML.
// `only` = partial reload: máy chủ CHỈ tính các prop được xin (controller bọc prop nặng trong closure) nên mở bàn nhanh;
// đây cũng là cách lấy prop "defer".
//
// - `url` có thể là chuỗi, ref hoặc getter: đổi giá trị (bộ lọc, kênh, khoảng ngày...) thì tự tải lại, GIỮ dữ liệu cũ
//   trên màn hình (loading = true) thay vì dựng lại component.
// - Bộ nhớ đệm theo (url + only) trong ~30 giây: mở lại bàn / quay lại bộ lọc cũ hiện NGAY dữ liệu cũ rồi làm mới ngầm
//   (stale-while-revalidate). Chỉ lần tải đầu của mỗi bàn / mỗi lần đổi url dùng đệm; các lần tải lại sau thao tác luôn lấy mới.
// - Các request trùng (cùng url + only) đang bay được gộp làm một.
import { usePage } from '@inertiajs/vue3';
import {
    onBeforeUnmount,
    ref,
    shallowRef,
    toValue,
    watch,
    type MaybeRefOrGetter,
} from 'vue';

const TTL_MS = 30_000;

type Bag = Record<string, unknown>;

const cache = new Map<string, { at: number; data: Bag }>();
const inflight = new Map<string, Promise<Bag>>();

const keyOf = (url: string, only?: string[]) =>
    `${url}|${[...(only ?? [])].sort().join(',')}`;

class VersionChanged extends Error {}

async function fetchBag(
    url: string,
    component: string,
    only: string[] | undefined,
    version: string | null | undefined,
): Promise<Bag> {
    const key = keyOf(url, only);
    const running = inflight.get(key);

    if (running) {
        return running;
    }

    const p = (async (): Promise<Bag> => {
        const headers: Record<string, string> = {
            'X-Inertia': 'true',
            'X-Requested-With': 'XMLHttpRequest',
            Accept: 'text/html, application/xhtml+xml',
        };

        if (version) {
            headers['X-Inertia-Version'] = String(version);
        }

        if (only?.length) {
            headers['X-Inertia-Partial-Component'] = component;
            headers['X-Inertia-Partial-Data'] = only.join(',');
        }

        const r = await fetch(url, { headers, credentials: 'same-origin' });

        if (r.status === 409) {
            // Bản app vừa cập nhật: tải lại trang cho đồng bộ.
            window.location.reload();

            throw new VersionChanged();
        }

        if (!r.ok) {
            throw new Error(String(r.status));
        }

        const j = (await r.json()) as { props?: Bag };
        const data = (j.props ?? {}) as Bag;
        cache.set(key, { at: Date.now(), data });

        return data;
    })().finally(() => inflight.delete(key));

    inflight.set(key, p);

    return p;
}

export function useInertiaProps<T extends Record<string, unknown>>(
    url: MaybeRefOrGetter<string>,
    component: string,
    only?: string[],
) {
    const page = usePage();
    const props = shallowRef<T | null>(null);
    const loading = ref(false);
    const error = ref<string | null>(null);
    let seq = 0;
    let primed = false;
    let alive = true;

    const apply = (next: Bag, onlyNow: string[] | undefined) => {
        props.value =
            onlyNow?.length && props.value
                ? ({ ...props.value, ...next } as T)
                : (next as T);
    };

    const reload = async (onlyNow: string[] | undefined = only) => {
        const u = toValue(url);
        const mine = ++seq;
        error.value = null;

        // Lần tải đầu (hoặc vừa đổi url): có đệm còn hạn thì hiện ngay rồi làm mới ngầm.
        if (!primed) {
            primed = true;
            const hit = cache.get(keyOf(u, onlyNow));

            if (hit && Date.now() - hit.at < TTL_MS) {
                apply(hit.data, onlyNow);
            }
        }

        loading.value = true;

        try {
            const next = await fetchBag(u, component, onlyNow, page.version);

            if (alive && mine === seq) {
                apply(next, onlyNow);
            }
        } catch (e) {
            if (!(e instanceof VersionChanged) && alive && mine === seq) {
                error.value = 'Chưa tải được dữ liệu, thử lại sau ít giây.';
            }
        } finally {
            if (mine === seq) {
                loading.value = false;
            }
        }
    };

    // Đổi url (bộ lọc, kênh, khoảng ngày): tải lại ngay, dữ liệu cũ vẫn hiện trong lúc chờ.
    watch(
        () => toValue(url),
        (now, before) => {
            if (now !== before) {
                primed = false;
                void reload();
            }
        },
    );

    onBeforeUnmount(() => {
        alive = false;
    });

    return { props, loading, error, reload };
}

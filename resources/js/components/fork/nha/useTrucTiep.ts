// Kho "trực tiếp" của trang Khu Tự Trị: gom các việc đang chạy thật (LiveItem) từ hai đường rồi chia cho bong bóng / màn hình.
//   1) `data.truc_tiep` trong trạng thái /nha/trang-thai (Laravel: việc phía app + bản sao việc của hub, luôn có sẵn, hỏi mỗi vài giây);
//   2) hỏi thẳng hub `${hub}/api/truc-tiep` mỗi khi luồng SSE báo mốc `tt` mới (rẻ, gần như tức thì). Hỏng (CORS, hub cũ…) thì
//      im lặng dùng đường 1. Phần của hub (nguon === 'hub') lấy từ nguồn nào về SAU CÙNG.
// Một đồng hồ 1 giây duy nhất (tab ẩn thì dừng) vừa tính tuổi việc vừa chạy "đạo diễn lời thoại" (GiamDocLoi) đổi bong bóng.
// Không có gì render lại cả ngôi nhà mỗi giây: `loi` chỉ đổi khi có câu mới, `nowSec` chỉ các màn hình nhỏ đọc.
import {
    computed,
    inject,
    onBeforeUnmount,
    onMounted,
    provide,
    ref,
    shallowRef,
    watch,
    type ComputedRef,
    type InjectionKey,
    type Ref,
    type ShallowRef,
} from 'vue';

import {
    chuanHoaDs,
    conSong,
    GiamDocLoi,
    gop,
    nhanVatCua,
} from '@/components/fork/nha/truc-tiep';
import type { LiveItem, NhaData } from '@/components/fork/nha/types';
import type { HubDoi } from '@/components/fork/nha/useHubLuong';

export interface TrucTiep {
    /** Việc còn đáng hiện (đang chạy hoặc vừa xong), mới nhất lên đầu. */
    items: ShallowRef<LiveItem[]>;
    /** Câu bong bóng hiện tại theo khoá nhân vật ("daodien2" = Đạo diễn thứ hai); null/thiếu = để lời thoại cũ lo. */
    loi: ShallowRef<Record<string, string | null>>;
    /** Giây hiện tại (cập nhật mỗi giây khi tab hiện) — dùng tính "đã làm bao lâu". */
    nowSec: Ref<number>;
    /** Khoá nhân vật đang có việc chạy trực tiếp (chưa xong). */
    dangLam: ComputedRef<Set<string>>;
    /** Việc của một nhân vật (đang chạy trước, vừa xong sau). */
    cua: (nv: string) => LiveItem[];
    /**
     * true khi chữ trực tiếp đang phải trông vào lượt hỏi trạng thái của trang (việc phía app luôn như vậy; việc của hub khi
     * không hỏi thẳng được) → trang nên hỏi dày (3 giây) thay vì hỏi nền thưa.
     */
    nhanh: ComputedRef<boolean>;
}

const KEY: InjectionKey<TrucTiep> = Symbol('truc-tiep');

/** Lấy kho đã được trang Nha.vue cấp (null khi component được dùng ngoài trang đó). */
export const useTrucTiepKho = (): TrucTiep | null => inject(KEY, null);

interface Opts {
    data: () => NhaData | null;
    /** Địa chỉ hub để hỏi thẳng (null = không hỏi thẳng, chỉ dùng data.truc_tiep). */
    hubUrl: () => string | null | undefined;
    /** Đăng ký nghe tin của luồng SSE (useHubLuong.onDoi). */
    onDoi: (cb: (d: HubDoi) => void) => () => boolean;
}

const gianCach = (
    a: Record<string, string | null>,
    b: Record<string, string | null>,
) => {
    const ka = Object.keys(a);

    if (ka.length !== Object.keys(b).length) {
        return true;
    }

    return ka.some((k) => a[k] !== b[k]);
};

export const useTrucTiep = (o: Opts): TrucTiep => {
    const items = shallowRef<LiveItem[]>([]);
    const loi = shallowRef<Record<string, string | null>>({});
    const nowSec = ref(Date.now() / 1000);
    const giamDoc = new GiamDocLoi();

    let appPart: LiveItem[] = [];
    let hubTuTrangThai: LiveItem[] = [];
    let trangThaiLuc = 0;
    let hubTrucTiep: LiveItem[] | null = null;
    let hubTrucTiepLuc = 0;
    let alive = true;
    const hubHong = ref(false);

    const tinh = () => {
        const hub =
            hubTrucTiep !== null && hubTrucTiepLuc >= trangThaiLuc
                ? hubTrucTiep
                : hubTuTrangThai;
        const now = Date.now() / 1000;
        const ds = gop(appPart, hub).filter((i) => conSong(i, now));
        const cu = items.value;

        // Giữ nguyên mảng khi không có gì đổi (tránh render lại vô ích)
        if (cu.length !== ds.length || ds.some((d, i) => d !== cu[i])) {
            items.value = ds;
        }
    };

    const nhanDuLieu = (d: NhaData | null) => {
        const all = chuanHoaDs(d?.truc_tiep);
        appPart = all.filter((i) => i.nguon !== 'hub');
        hubTuTrangThai = all.filter((i) => i.nguon === 'hub');
        trangThaiLuc = Date.now();
        tinh();
    };
    watch(() => o.data(), nhanDuLieu, { immediate: true });

    // ---------------------------------------------------------- hỏi thẳng hub
    let dangHoi = false;
    let hoiLai = false;
    let hong = 0;
    let hongLuc = 0;
    let tt = 0;
    const hoiHub = async () => {
        const base = (o.hubUrl() ?? '').replace(/\/+$/, '');

        if (!alive || !base || document.hidden) {
            return;
        }

        if (hong >= 3 && Date.now() - hongLuc < 60000) {
            return; // hub cũ / bị chặn: thôi, dùng đường trạng thái (thử lại sau 1 phút)
        }

        if (dangHoi) {
            hoiLai = true;

            return;
        }
        dangHoi = true;
        const ac = new AbortController();
        const to = window.setTimeout(() => ac.abort(), 4000);

        try {
            const r = await fetch(`${base}/api/truc-tiep`, {
                signal: ac.signal,
                headers: { Accept: 'application/json' },
                cache: 'no-store',
            });

            if (!r.ok) {
                throw new Error(String(r.status));
            }
            const j = (await r.json()) as { ds?: unknown };

            if (!alive || (o.hubUrl() ?? '').replace(/\/+$/, '') !== base) {
                return; // trả lời của hub cũ (đã đổi địa chỉ / rời trang): bỏ
            }
            hubTrucTiep = chuanHoaDs(j.ds).map((i) => ({
                ...i,
                nguon: 'hub' as const,
            }));
            hubTrucTiepLuc = Date.now();
            hong = 0;
            hubHong.value = false;
            tinh();
        } catch {
            hong += 1;
            hongLuc = Date.now();
            hubHong.value = hong >= 2;
            hubTrucTiep = null; // quay về bản trong trạng thái
            tinh();
        } finally {
            window.clearTimeout(to);
            dangHoi = false;

            if (hoiLai && alive) {
                hoiLai = false;
                void hoiHub();
            }
        }
    };
    const offDoi = o.onDoi((d) => {
        const moi =
            typeof d.tt === 'number' && Number.isFinite(d.tt) ? d.tt : 0;

        if (moi !== tt) {
            tt = moi;
            void hoiHub();
        }
    });
    watch(
        () => o.hubUrl() ?? '',
        () => {
            hubTrucTiep = null;
            hong = 0;
            hubHong.value = false;
            tt = 0;
            tinh();
        },
    );

    // ---------------------------------------------------------- đồng hồ 1 giây
    let timer: number | undefined;
    const nhip = () => {
        if (document.hidden) {
            return;
        }
        const ms = Date.now();
        nowSec.value = ms / 1000;
        tinh();
        const kq = giamDoc.tick(items.value, ms);

        if (gianCach(loi.value, kq)) {
            loi.value = { ...kq };
        }
    };
    const onVis = () => {
        if (!document.hidden) {
            nhip();
        }
    };
    onMounted(() => {
        nhip();
        timer = window.setInterval(nhip, 1000);
        document.addEventListener('visibilitychange', onVis);
    });
    onBeforeUnmount(() => {
        alive = false;
        offDoi();
        window.clearInterval(timer);
        document.removeEventListener('visibilitychange', onVis);
    });

    const dangLam = computed(() => {
        const s = new Set<string>();

        for (const i of items.value) {
            const nv = nhanVatCua(i);

            if (nv && !i.xong) {
                s.add(nv);
            }
        }

        return s;
    });

    const nhanh = computed(() =>
        items.value.some(
            (i) => !i.xong && (i.nguon === 'app' || hubHong.value),
        ),
    );

    const kho: TrucTiep = {
        items,
        loi,
        nowSec,
        dangLam,
        nhanh,
        cua: (nv) =>
            items.value
                .filter((i) => nhanVatCua(i) === nv)
                .sort((a, b) => Number(!!a.xong) - Number(!!b.xong)),
    };
    provide(KEY, kho);

    return kho;
};

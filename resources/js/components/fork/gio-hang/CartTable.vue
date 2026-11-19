<script setup lang="ts">
// Phần thân của trang Giỏ hàng: chọn kênh + lấy sản phẩm shop, tóm tắt, bảng sản phẩm, các hộp thoại.
// Dùng chung cho trang /auto/gio-hang (GioHang.vue) và popup "Bàn làm việc" của Chủ quầy (`embedded`):
// ở chế độ embedded, mọi thao tác giữ nguyên trang đang mở (preserveState), việc chọn kênh / tải lại dữ liệu do bàn lo
// (emit `channel`, `refresh`) và mỗi thao tác xong báo qua `changed`.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en).
import { Link, router } from '@inertiajs/vue3';
import {
    IconCheck,
    IconCopy,
    IconPlugConnectedX,
    IconPlus,
    IconRefresh,
    IconSearch,
    IconX,
} from '@tabler/icons-vue';
import {
    computed,
    onBeforeUnmount,
    onMounted,
    reactive,
    ref,
    watch,
} from 'vue';
import { toast } from 'vue-sonner';

import CartRow from '@/components/fork/gio-hang/CartRow.vue';
import PersonaliseDialog from '@/components/fork/gio-hang/PersonaliseDialog.vue';
import ShopPickerDialog from '@/components/fork/gio-hang/ShopPickerDialog.vue';
import type {
    Persona,
    PersonaDefault,
    Row,
    ShopCard,
    ShopProduct,
    Sync,
} from '@/components/fork/gio-hang/types';
import { usePersonalise } from '@/components/fork/gio-hang/usePersonalise';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import { cardCls, toneClasses } from '@/components/fork/shared/status';
import { norm } from '@/components/fork/shared/text';
import { useVisitLoading } from '@/components/fork/shared/useVisitLoading';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { confirm } from '@/composables/useConfirm';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    channels: {
        id: string;
        username: string | null;
        display_name: string | null;
    }[];
    selected: string | null;
    sync: Sync | null;
    products: ShopProduct[];
    rows: Row[];
    name_max: number;
    sync_ttl_minutes: number;
    personalise?: Record<string, Persona>;
    personalise_default?: PersonaDefault;
    sample_hidden?: boolean;
    name_short_max?: number;
    /** Chạy trong popup "Bàn làm việc" (xem ghi chú đầu file). */
    embedded?: boolean;
    /** Embedded: dữ liệu của bàn đang tải lại (hiện khung chờ ở bảng). */
    reloading?: boolean;
}>();

const emit = defineEmits<{
    channel: [id: string];
    refresh: [only: string[]];
    changed: [viec: 'luu-gio' | 'lay-lai' | 'khac'];
}>();

const busy = ref<string | null>(null);

// Tuỳ chọn chung của mọi thao tác ghi. Embedded: ở yên trang đang mở và báo cho bàn sau khi xong.
const mk = (viec: 'luu-gio' | 'lay-lai' | 'khac', onSuccess?: () => void) => ({
    preserveScroll: true,
    ...(props.embedded ? { preserveState: true } : {}),
    onSuccess: () => {
        onSuccess?.();

        if (props.embedded) {
            emit('changed', viec);
        }
    },
    onFinish: () => {
        busy.value = null;
    },
});

// Tải lại một phần dữ liệu của trang (trang thật: router.reload; popup: bàn tự tải).
const refresh = (only: string[]) => {
    if (props.embedded) {
        emit('refresh', only);
    } else {
        router.reload({ only });
    }
};

const fmtTime = (iso: string | null | undefined) => {
    if (!iso) {
        return 'chưa lấy lần nào';
    }

    const d = dayjs(iso);

    return d.isSame(dayjs(), 'day')
        ? `lấy lúc ${d.format('HH:mm')} hôm nay`
        : `lấy lúc ${d.format('HH:mm DD/MM')}`;
};

// ---- Chọn kênh ----
const { loading: visiting, callbacks } = useVisitLoading();
const loading = computed(() => visiting.value || !!props.reloading);

// Tên kênh để hiện: @username, không có username thì tên hiển thị (tránh "@null").
const channelLabel = (c: {
    username: string | null;
    display_name: string | null;
}) => (c.username ? `@${c.username}` : c.display_name || 'Kênh chưa đặt tên');

// Cho phép một lần điều hướng đi qua cửa chặn "chưa lưu" (khi anh đã bấm "Bỏ và đổi kênh").
let allowLeave = false;

const chooseChannel = async (id: string) => {
    if (id === props.selected) {
        return;
    }

    if (!(await confirmDiscard('Bỏ và đổi kênh'))) {
        return;
    }

    if (props.embedded) {
        emit('channel', id);

        return;
    }

    allowLeave = true;

    try {
        router.get(
            '/auto/gio-hang',
            { kenh: id },
            { preserveScroll: false, ...callbacks },
        );
    } finally {
        allowLeave = false;
    }
};

// ---- Lấy sản phẩm từ shop ----
const syncState = computed(() => props.sync?.state ?? 'idle');
// "Vừa lấy xong" chỉ hiện khi lần lấy mới đây (trạng thái 'done' giữ mãi sau lần lấy cuối).
const justSynced = computed(
    () =>
        syncState.value === 'done' &&
        !!props.sync?.synced_at &&
        dayjs().diff(dayjs(props.sync.synced_at), 'minute') < 10,
);

const syncShop = () => {
    if (!props.selected) {
        return;
    }

    busy.value = 'sync';
    router.post(
        `/auto/accounts/${props.selected}/shop/sync`,
        {},
        mk('lay-lai'),
    );
};

// "Đã lấy 20/58…": tiện ích báo tiến độ khi đang lấy.
const syncProgress = computed(() => props.sync?.progress ?? null);
const syncPercent = computed(() => {
    const p = syncProgress.value;

    return p && p.total
        ? Math.min(100, Math.round((p.got / p.total) * 100))
        : null;
});
const syncProgressText = computed(() => {
    const p = syncProgress.value;

    if (!p) {
        return null;
    }

    return p.total ? `${p.got}/${p.total}` : `${p.got}`;
});

// Đang chờ tiện ích thì tự làm mới trạng thái mỗi 2 giây (chỉ phần trạng thái, nhẹ); lấy xong thì tải lại danh sách.
let timer: ReturnType<typeof setInterval> | null = null;
watch(
    syncState,
    (state, before) => {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }

        if (state === 'waiting') {
            // 4 giây, tab ẩn thì thôi; máy chủ tự hết hạn lượt đồng bộ sau 10 phút nên vòng hỏi cũng dừng theo.
            timer = setInterval(() => {
                if (document.visibilityState === 'visible') {
                    refresh(['sync']);
                }
            }, 4000);
        } else if (before === 'waiting') {
            refresh(['sync', 'products', 'rows', 'sample_hidden']);
        }
    },
    { immediate: true },
);
onBeforeUnmount(() => {
    if (timer) {
        clearInterval(timer);
    }
});

// ---- Ẩn / hiện sản phẩm shop ----
const setHidden = (p: ShopProduct, hidden: boolean) => {
    if (!props.selected) {
        return;
    }

    busy.value = `hide-${p.product_id}`;
    router.patch(
        `/auto/accounts/${props.selected}/shop-products/${p.product_id}`,
        { hidden },
        mk('khac', () => {
            // Sản phẩm đang được dùng thì máy chủ đã báo riêng (video sẽ được giữ trong kho); còn lại thì báo ở đây kèm "Hiện lại".
            if (hidden && !p.used_by.length) {
                toast(`Đã ẩn “${p.title}”`, {
                    action: {
                        label: 'Hiện lại',
                        onClick: () => setHidden(p, false),
                    },
                });
            }
        }),
    );
};

// ---- Dòng ghép: mỗi dòng = sản phẩm hub x quy cách ----
interface Draft {
    shop_product_id?: string;
    display_name?: string;
    edited?: boolean; // đã sửa tên tay thì đổi sản phẩm không ghi đè tên
}

const draft = reactive<Record<string, Draft>>({});
const picking = ref<string | null>(null); // khoá dòng đang chọn sản phẩm cho nó

const pickedId = (r: Row) =>
    draft[r.key]?.shop_product_id ?? r.link?.shop_product_id ?? '';

const nameOf = (r: Row) =>
    draft[r.key]?.display_name ?? r.link?.display_name ?? '';

const cardOf = (r: Row): ShopCard | null => {
    const id = pickedId(r);

    if (id === '') {
        return null;
    }

    return (
        props.products.find((p) => p.product_id === id) ??
        (r.link?.shop_product_id === id ? r.link.product : null)
    );
};

const isDirty = (r: Row) =>
    pickedId(r) !== '' &&
    (pickedId(r) !== (r.link?.shop_product_id ?? '') ||
        nameOf(r) !== (r.link?.display_name ?? '') ||
        r.link?.paused_reason != null);

const pickingRow = computed(
    () => props.rows.find((r) => r.key === picking.value) ?? null,
);

// Các dòng đã chọn giỏ (hoặc sửa tên giỏ) nhưng chưa bấm Lưu.
const dirtyRows = computed(() =>
    props.rows.filter((r) => !!draft[r.key] && isDirty(r)),
);

const discardDrafts = () => {
    for (const k of Object.keys(draft)) {
        delete draft[k];
    }
};

// Hỏi trước khi bỏ các lựa chọn chưa lưu (đổi kênh...). Không có gì chưa lưu thì đi tiếp luôn.
const confirmDiscard = async (
    confirmText: string,
    leaving = 'Đổi kênh',
): Promise<boolean> => {
    const n = dirtyRows.value.length;

    if (n === 0) {
        return true;
    }

    return confirm({
        title: 'Bỏ các thay đổi chưa lưu?',
        description: `Có ${n} dòng đã chọn giỏ nhưng chưa bấm Lưu. ${leaving} sẽ mất các lựa chọn này.`,
        confirmText,
        destructive: true,
    });
};

// Rời trang khi còn nháp: chặn điều hướng của Inertia (hỏi rồi mới đi) và việc đóng/tải lại tab.
let stopBefore: (() => void) | null = null;

const onBeforeUnload = (e: BeforeUnloadEvent) => {
    if (dirtyRows.value.length > 0) {
        e.preventDefault();
        e.returnValue = '';
    }
};

onMounted(() => {
    window.addEventListener('beforeunload', onBeforeUnload);

    if (props.embedded) {
        return;
    }

    stopBefore = router.on('before', (event) => {
        const visit = event.detail.visit;

        // Chỉ chặn việc ĐI sang trang/kênh khác; lưu, lấy shop, tải lại một phần... không phải rời trang.
        if (
            allowLeave ||
            dirtyRows.value.length === 0 ||
            visit.method !== 'get' ||
            visit.only.length > 0 ||
            visit.url.pathname === window.location.pathname
        ) {
            return;
        }

        const href = visit.url.href;

        void confirmDiscard('Bỏ và rời trang', 'Rời trang').then((ok) => {
            if (ok) {
                allowLeave = true;

                try {
                    router.visit(href);
                } finally {
                    allowLeave = false;
                }
            }
        });

        return false;
    });
});

onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', onBeforeUnload);
    stopBefore?.();
});

const pickFor = (p: ShopProduct) => {
    const r = pickingRow.value;

    if (!r) {
        return;
    }

    const d = (draft[r.key] ??= {});
    d.shop_product_id = p.product_id;

    if (!d.edited) {
        d.display_name = p.suggested_name;
    }

    picking.value = null;
};

const editName = (r: Row, value: string) => {
    const d = (draft[r.key] ??= {});
    d.display_name = [...value].slice(0, props.name_max).join('');
    d.edited = true;
};

const saveRow = (r: Row) => {
    if (!props.selected) {
        return;
    }

    busy.value = `row-${r.key}`;
    router.put(
        `/auto/accounts/${props.selected}/links/${r.code}`,
        {
            quy_cach: r.quy_cach,
            shop_product_id: pickedId(r),
            display_name: nameOf(r),
        },
        mk('luu-gio', () => {
            delete draft[r.key];
        }),
    );
};

const clearRow = async (r: Row) => {
    if (!props.selected) {
        return;
    }

    if (!r.link) {
        delete draft[r.key];

        return;
    }

    const ok = await confirm({
        title: `Bỏ giỏ hàng của “${r.label}”?`,
        description:
            r.new_videos > 0
                ? `${r.new_videos} video đang chờ sẽ được giữ trong kho, không đăng cho đến khi anh chọn giỏ lại.`
                : 'Video mới của sản phẩm này sẽ được giữ trong kho, không đăng cho đến khi anh chọn giỏ lại.',
        confirmText: 'Bỏ giỏ',
        destructive: true,
    });

    if (!ok) {
        return;
    }

    busy.value = `row-${r.key}`;
    router.delete(`/auto/accounts/${props.selected}/links/${r.code}`, {
        ...mk('luu-gio', () => {
            delete draft[r.key];
        }),
        data: { quy_cach: r.quy_cach },
    });
};

// ---- "Lưu tất cả": một lần lưu mọi dòng đang chờ (cùng luật với lưu từng dòng, máy chủ lưu trong một giao dịch) ----
const saveAll = () => {
    if (!props.selected || dirtyRows.value.length === 0) {
        return;
    }

    const rows = dirtyRows.value;
    const noName = rows.filter((r) => !nameOf(r).trim());

    if (noName.length > 0) {
        toast.error(
            `Còn ${noName.length} dòng chưa có tên giỏ (${noName[0].label}…). Anh nhập tên rồi lưu lại.`,
        );

        return;
    }

    busy.value = 'save-all';
    router.put(
        `/auto/accounts/${props.selected}/links`,
        {
            items: rows.map((r) => ({
                code: r.code,
                quy_cach: r.quy_cach,
                shop_product_id: pickedId(r),
                display_name: nameOf(r),
            })),
        },
        mk('luu-gio', () => {
            for (const r of rows) {
                delete draft[r.key];
            }
        }),
    );
};

// ---- "+ Thêm sản phẩm": chọn sản phẩm shop -> app tạo sản phẩm hub tương ứng và gắn giỏ một lần ----
const addOpen = ref(false);
const adding = ref(false);

const addProduct = (p: ShopProduct) => {
    if (!props.selected) {
        return;
    }

    adding.value = true;
    const base = mk('luu-gio', () => {
        addOpen.value = false;
    });
    router.post(
        `/auto/accounts/${props.selected}/hub-products`,
        { shop_product_id: p.product_id, display_name: p.suggested_name },
        {
            ...base,
            onFinish: () => {
                adding.value = false;
            },
        },
    );
};

// ---- Đổi tên / xoá sản phẩm hub ----
const renaming = ref<Row | null>(null);
const renameValue = ref('');

const openRename = (r: Row) => {
    renaming.value = r;
    renameValue.value = r.hub_name;
};

const saveRename = () => {
    const r = renaming.value;
    const name = renameValue.value.trim();

    if (!r || name === '') {
        return;
    }

    busy.value = `rename-${r.code}`;
    router.patch(
        `/auto/hub-products/${r.code}`,
        { name },
        mk('khac', () => {
            renaming.value = null;
        }),
    );
};

const removeProduct = async (r: Row) => {
    const ok = await confirm({
        title: `Xoá sản phẩm “${r.hub_name}”?`,
        description:
            'Hồ sơ sản phẩm được đưa vào Thùng rác của Windows; video gốc và video đã làm không bị xoá. Giỏ hàng đã chọn cho sản phẩm này cũng bị bỏ.',
        confirmText: 'Xoá sản phẩm',
        destructive: true,
    });

    if (!ok) {
        return;
    }

    busy.value = `remove-${r.code}`;
    router.delete(`/auto/hub-products/${r.code}`, mk('khac'));
};

const onlySample = computed(
    () => props.rows.length > 0 && props.rows.every((r) => r.is_sample),
);

// ---- Cá nhân hoá (ảnh bìa, hashtag) theo sản phẩm hub; 'default' = hashtag mặc định chung ----
const { personaOf, dialogProps, openProduct, openDefault, closePersonalise } =
    usePersonalise(() => props);

const onPersonaSaved = () => {
    if (props.embedded) {
        emit('changed', 'khac');
    }
};

// ---- Sắp xếp: dòng có video chờ mà chưa có giỏ lên đầu ----
// Một dòng đã chọn sản phẩm trong nháp (chưa lưu) vẫn tính là chưa có giỏ cho tới khi lưu.
const rank = (r: Row) => {
    if (!r.link && r.new_videos > 0) {
        return 0;
    }

    if (r.link && (r.link.paused_reason || r.link.problem)) {
        return 1;
    }

    return r.link ? 2 : 3;
};

const sortedRows = computed(() =>
    [...props.rows].sort(
        (a, b) =>
            rank(a) - rank(b) ||
            b.new_videos - a.new_videos ||
            a.label.localeCompare(b.label, 'vi'),
    ),
);

const needRows = computed(() => props.rows.filter((r) => rank(r) === 0));
const needVideos = computed(() =>
    needRows.value.reduce((s, r) => s + r.new_videos, 0),
);
const problemRows = computed(() => props.rows.filter((r) => rank(r) === 1));
const readyRows = computed(() => props.rows.filter((r) => rank(r) === 2));

const statTiles = computed(() => [
    {
        label: 'Sản phẩm',
        value: props.rows.length,
        dot: 'bg-muted-foreground/50',
    },
    {
        label: 'Sẵn sàng đăng',
        value: readyRows.value.length,
        dot: 'bg-emerald-500',
    },
    {
        label: `Chưa chọn giỏ · ${needVideos.value} video chờ`,
        value: needRows.value.length,
        dot: 'bg-amber-500',
    },
    {
        label: 'Có vấn đề / tạm dừng',
        value: problemRows.value.length,
        dot: 'bg-red-500',
    },
]);

// ---- Lọc theo trạng thái ----
type Filter = 'all' | 'need' | 'bad' | 'ok';
const filter = ref<Filter>('all');

const filters = computed(() => [
    {
        key: 'all' as const,
        label: 'Tất cả',
        count: props.rows.length,
        dot: null,
    },
    {
        key: 'need' as const,
        label: 'Chưa chọn giỏ',
        count: needRows.value.length,
        dot: 'bg-amber-500',
    },
    {
        key: 'bad' as const,
        label: 'Có vấn đề',
        count: problemRows.value.length,
        dot: 'bg-red-500',
    },
    {
        key: 'ok' as const,
        label: 'Sẵn sàng',
        count: readyRows.value.length,
        dot: 'bg-emerald-500',
    },
]);

// ---- Tìm trong bảng: theo tên sản phẩm hub, quy cách, tên giỏ và tên sản phẩm shop (không phân biệt dấu) ----
const search = ref('');
const searchText = computed(() => norm(search.value.trim()));

const matchesSearch = (r: Row) => {
    const q = searchText.value;

    if (q === '') {
        return true;
    }

    const hay = [
        r.label,
        r.hub_name,
        r.quy_cach_name ?? '',
        nameOf(r),
        cardOf(r)?.title ?? '',
    ].join(' ');

    return norm(hay).includes(q);
};

const visibleRows = computed(() => {
    const want = { all: null, need: 0, bad: 1, ok: 2 }[filter.value];
    const byStatus =
        want === null
            ? sortedRows.value
            : sortedRows.value.filter((r) => rank(r) === want);

    return byStatus.filter(matchesSearch);
});

watch(
    () => props.selected,
    () => {
        filter.value = 'all';
        search.value = '';

        // Nháp (sản phẩm shop / tên giỏ chưa lưu) thuộc về kênh cũ: bỏ khi đổi kênh.
        discardDrafts();
    },
);

// ---- Sao chép giỏ sang kênh khác ----
const copyOpen = ref(false);
const copyTo = ref<string[]>([]);
const copyOverwrite = ref(false);
const copyTargets = computed(() =>
    props.channels.filter((c) => c.id !== props.selected),
);
const copyRowCount = computed(() => props.rows.filter((r) => r.link).length);

const openCopy = () => {
    copyTo.value =
        copyTargets.value.length === 1 ? [copyTargets.value[0].id] : [];
    copyOverwrite.value = false;
    copyOpen.value = true;
};

const toggleCopyTarget = (id: string, on: boolean) => {
    copyTo.value = on
        ? [...new Set([...copyTo.value, id])]
        : copyTo.value.filter((x) => x !== id);
};

const doCopy = () => {
    if (!props.selected || copyTo.value.length === 0) {
        return;
    }

    busy.value = 'copy';
    router.post(
        `/auto/accounts/${props.selected}/links/copy`,
        { to: copyTo.value, overwrite: copyOverwrite.value },
        mk('khac', () => {
            copyOpen.value = false;
        }),
    );
};

// ---- Lỗi lấy sản phẩm: "câu dễ hiểu (mã gốc)" -> câu dễ hiểu to, mã gốc nhỏ và mờ ----
const syncReason = computed(() => {
    const raw = (props.sync?.reason ?? '').trim();
    const m = raw.match(/^(.*) \(([^()]*)\)$/s);

    if (m) {
        return { text: m[1], raw: m[2] };
    }

    // Mã kỹ thuật chưa được máy chủ dịch: dịch những kiểu hay gặp, còn lại giữ nguyên.
    const r = raw.toLowerCase();
    const known = /time ?out|timed out/.test(r)
        ? 'Chrome trả lời quá chậm'
        : /failed to fetch|network|err_/.test(r)
          ? 'mạng tới TikTok Shop bị lỗi'
          : null;

    return known ? { text: known, raw } : { text: raw, raw: '' };
});

const channel = computed(
    () => props.channels.find((c) => c.id === props.selected) ?? null,
);
const initial = (c: { username: string | null; display_name: string | null }) =>
    [...(c.display_name || c.username || '?').trim()][0]?.toUpperCase() ?? '?';

// Trang thật nhúng các nút "Hashtag mặc định" / "Thêm sản phẩm" ở đầu trang (qua ref); popup cũng gọi như vậy.
defineExpose({
    openDefault,
    openAdd: () => (addOpen.value = true),
    openCopy,
    canCopy: computed(() => props.channels.length > 1),
});
</script>

<template>
    <!-- Trang thật: "contents" để các khối nằm thẳng trong khung của trang; popup: cột dọc, dải tóm tắt lên đầu. -->
    <div :class="embedded ? 'flex flex-col gap-4' : 'contents'">
        <EmptyState
            v-if="!channels.length"
            :icon="IconPlugConnectedX"
            title="Chưa có kênh TikTok nào bật đăng qua Chrome"
            description="Bật đăng qua Chrome cho kênh trong phần Kết nối Chrome, rồi quay lại đây chọn giỏ hàng."
            data-testid="fork-gio-hang-empty"
        >
            <Button as-child size="sm">
                <Link href="/settings#chrome">Kết nối Chrome →</Link>
            </Button>
        </EmptyState>

        <template v-else>
            <!-- Kênh + sản phẩm shop -->
            <section :class="cn(cardCls, 'overflow-hidden')">
                <div
                    class="flex flex-wrap items-center justify-between gap-x-6 gap-y-4 px-5 py-4"
                >
                    <div
                        class="flex min-w-0 flex-wrap items-center gap-2"
                        role="tablist"
                        aria-label="Chọn kênh"
                        data-testid="fork-gio-hang-channel"
                    >
                        <button
                            v-for="c in channels"
                            :key="c.id"
                            type="button"
                            role="tab"
                            :aria-selected="c.id === selected"
                            :class="
                                cn(
                                    'flex h-10 items-center gap-2.5 rounded-full border py-1 pr-4 pl-1 text-[0.8438rem] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                                    c.id === selected
                                        ? 'border-primary bg-primary/[0.07] text-foreground dark:bg-primary/15'
                                        : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                                )
                            "
                            @click="chooseChannel(c.id)"
                        >
                            <span
                                :class="
                                    cn(
                                        'flex size-8 items-center justify-center rounded-full text-[0.8125rem] font-semibold',
                                        c.id === selected
                                            ? 'bg-primary text-primary-foreground'
                                            : 'bg-muted text-muted-foreground',
                                    )
                                "
                                >{{ initial(c) }}</span
                            >
                            {{ channelLabel(c) }}
                            <IconCheck
                                v-if="c.id === selected"
                                class="size-4 text-primary-text"
                            />
                        </button>
                    </div>

                    <div class="flex flex-wrap items-center gap-3">
                        <div
                            class="text-right text-[0.7812rem] leading-snug"
                            data-testid="fork-gio-hang-synced-at"
                        >
                            <div class="font-medium tabular-nums">
                                {{ products.length }} sản phẩm trong shop
                            </div>
                            <div class="text-muted-foreground">
                                <template v-if="justSynced"
                                    ><span
                                        :class="toneClasses.success.text"
                                        data-testid="fork-gio-hang-sync-done"
                                        >Vừa lấy xong</span
                                    >
                                    ·
                                </template>
                                {{ fmtTime(sync?.synced_at) }}
                            </div>
                        </div>
                        <Button
                            variant="outline"
                            :disabled="
                                busy === 'sync' || syncState === 'waiting'
                            "
                            data-testid="fork-gio-hang-sync"
                            @click="syncShop"
                        >
                            <Spinner
                                v-if="
                                    syncState === 'waiting' || busy === 'sync'
                                "
                                class="size-4"
                            />
                            <IconRefresh v-else class="size-4" />
                            {{
                                syncState === 'waiting'
                                    ? syncProgressText
                                        ? `Đang lấy… ${syncProgressText}`
                                        : 'Đang chờ Chrome…'
                                    : 'Lấy lại từ shop'
                            }}
                        </Button>
                    </div>
                </div>

                <div
                    v-if="syncState === 'waiting'"
                    class="border-t bg-sky-50/60 px-5 py-3 dark:bg-sky-950/20"
                    data-testid="fork-gio-hang-sync-waiting"
                >
                    <template v-if="syncProgress">
                        <div
                            class="flex items-center justify-between text-[0.8125rem] font-medium"
                            data-testid="fork-gio-hang-sync-progress"
                        >
                            <span>Đã lấy {{ syncProgressText }} sản phẩm…</span>
                            <span
                                v-if="syncPercent !== null"
                                class="text-muted-foreground tabular-nums"
                                >{{ syncPercent }}%</span
                            >
                        </div>
                        <Progress
                            v-if="syncPercent !== null"
                            class="mt-2 h-1.5"
                            :model-value="syncPercent"
                        />
                    </template>
                    <p
                        v-if="sync?.chrome"
                        class="mb-1.5 text-[0.8125rem] font-medium text-amber-800 dark:text-amber-300"
                        data-testid="fork-gio-hang-sync-chrome"
                    >
                        {{ sync.chrome }}
                    </p>
                    <p
                        v-if="!syncProgress"
                        class="text-[0.8125rem] text-muted-foreground"
                    >
                        Đang chờ tiện ích Chrome lấy sản phẩm từ shop — Chrome
                        cần đang mở và đã đăng nhập TikTok, thường mất vài giây.
                        Trang tự cập nhật; quá {{ sync_ttl_minutes }} phút thì
                        yêu cầu hết hạn.
                    </p>
                </div>
                <div
                    v-else-if="syncState === 'error' || syncState === 'expired'"
                    :class="
                        cn(
                            'border-t px-5 py-3 text-[0.8125rem]',
                            syncState === 'error'
                                ? toneClasses.danger.box
                                : toneClasses.warn.box,
                            'rounded-none border-x-0 border-b-0',
                        )
                    "
                    :data-testid="
                        syncState === 'error'
                            ? 'fork-gio-hang-sync-error'
                            : 'fork-gio-hang-sync-expired'
                    "
                >
                    <template v-if="syncState === 'error'">
                        Lấy sản phẩm bị lỗi<template v-if="syncReason.text"
                            >: {{ syncReason.text }}</template
                        >. Tiện ích có thể tự thử lại; nếu không được, bấm “Thử
                        lại”.
                        <span
                            v-if="syncReason.raw"
                            class="mt-0.5 block text-[0.7188rem] break-words text-muted-foreground"
                            data-testid="fork-gio-hang-sync-raw"
                            >Mã lỗi: {{ syncReason.raw }}</span
                        >
                    </template>
                    <template v-else>
                        Yêu cầu đã hết hạn sau {{ sync_ttl_minutes }} phút mà
                        tiện ích chưa lấy được. Kiểm tra Chrome đang mở rồi bấm
                        “Thử lại”.
                    </template>
                    <p
                        v-if="sync?.chrome"
                        class="mt-1 font-medium"
                        data-testid="fork-gio-hang-sync-chrome"
                    >
                        {{ sync.chrome }}
                    </p>
                    <div class="mt-2 flex flex-wrap items-center gap-2">
                        <Button
                            size="sm"
                            variant="outline"
                            :disabled="busy === 'sync'"
                            data-testid="fork-gio-hang-sync-retry"
                            @click="syncShop"
                        >
                            <Spinner v-if="busy === 'sync'" class="size-4" />
                            <IconRefresh v-else class="size-4" />
                            Thử lại
                        </Button>
                        <Button
                            as-child
                            size="sm"
                            variant="ghost"
                            data-testid="fork-gio-hang-sync-chrome-link"
                        >
                            <Link href="/settings#chrome"
                                >Mở phần Kết nối Chrome</Link
                            >
                        </Button>
                    </div>
                </div>
            </section>

            <Callout
                v-if="needRows.length"
                tone="warn"
                data-testid="fork-gio-hang-summary"
            >
                <b>{{ needVideos }} video</b> của
                <b>{{ needRows.length }} sản phẩm</b> đang chờ vì chưa chọn giỏ
                — chọn giỏ ở các dòng màu vàng để app bắt đầu đăng.
            </Callout>
            <Callout
                v-if="onlySample"
                tone="info"
                data-testid="fork-gio-hang-only-sample"
            >
                Hiện mới có <b>sản phẩm ví dụ</b>. Bấm <b>Thêm sản phẩm</b> và
                chọn sản phẩm thật trong shop: app tự tạo sản phẩm tương ứng và
                gắn giỏ hàng.
                {{
                    products.length
                        ? ''
                        : 'Nhớ bấm “Lấy lại từ shop” trước để có danh sách.'
                }}
            </Callout>

            <!-- Tóm tắt nhanh -->
            <div
                :class="
                    cn(
                        'grid grid-cols-2 gap-3 xl:grid-cols-4',
                        embedded && '-order-1',
                    )
                "
                data-testid="fork-gio-hang-stats"
            >
                <div
                    v-for="t in statTiles"
                    :key="t.label"
                    :class="cn(cardCls, 'flex items-center gap-3 px-4 py-3')"
                >
                    <span :class="cn('size-2.5 rounded-full', t.dot)" />
                    <div class="min-w-0">
                        <div
                            class="font-heading text-[1.375rem] leading-tight font-[650] tracking-[-0.02em] tabular-nums"
                        >
                            {{ t.value }}
                        </div>
                        <div
                            class="truncate text-[0.7812rem] text-muted-foreground"
                        >
                            {{ t.label }}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Bảng sản phẩm -->
            <section
                :class="cn(cardCls, 'overflow-hidden')"
                data-testid="fork-gio-hang-rows"
            >
                <header
                    class="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3.5"
                >
                    <div
                        class="flex flex-wrap items-center gap-1"
                        role="group"
                        aria-label="Lọc theo trạng thái"
                    >
                        <button
                            v-for="f in filters"
                            :key="f.key"
                            type="button"
                            :aria-pressed="filter === f.key"
                            :disabled="f.key !== 'all' && !f.count"
                            :class="
                                cn(
                                    'flex h-8 items-center gap-2 rounded-lg px-3 text-[0.8125rem] font-medium transition-colors disabled:opacity-40',
                                    filter === f.key
                                        ? 'bg-foreground text-background'
                                        : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                                )
                            "
                            @click="filter = f.key"
                        >
                            <span
                                v-if="f.dot"
                                :class="cn('size-1.5 rounded-full', f.dot)"
                            />
                            {{ f.label }}
                            <span
                                :class="
                                    cn(
                                        'tabular-nums',
                                        filter === f.key
                                            ? 'opacity-70'
                                            : 'text-muted-foreground/80',
                                    )
                                "
                                >{{ f.count }}</span
                            >
                        </button>
                    </div>
                    <div class="flex min-w-0 flex-wrap items-center gap-3">
                        <div class="relative w-full sm:w-64">
                            <IconSearch
                                class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
                            />
                            <Input
                                v-model="search"
                                class="h-8 pr-8 pl-8 text-[0.8125rem]"
                                placeholder="Tìm sản phẩm hoặc tên giỏ…"
                                aria-label="Tìm sản phẩm hoặc tên giỏ"
                                data-testid="fork-gio-hang-table-search"
                                @keydown.esc="search = ''"
                            />
                            <button
                                v-if="search"
                                type="button"
                                class="absolute top-1/2 right-1.5 flex size-5 -translate-y-1/2 items-center justify-center rounded text-muted-foreground hover:text-foreground"
                                aria-label="Xoá tìm kiếm"
                                title="Xoá tìm kiếm"
                                @click="search = ''"
                            >
                                <IconX class="size-3.5" />
                            </button>
                        </div>
                        <Button
                            v-if="embedded && channels.length > 1"
                            size="sm"
                            variant="outline"
                            data-testid="fork-gio-hang-copy-open"
                            @click="openCopy"
                        >
                            <IconCopy class="size-4" />
                            Sao chép giỏ sang kênh khác…
                        </Button>
                        <span
                            v-if="channel"
                            class="text-[0.7812rem] text-muted-foreground"
                            >Giỏ hàng của
                            <b class="font-medium text-foreground">{{
                                channelLabel(channel)
                            }}</b></span
                        >
                    </div>
                </header>

                <div
                    :class="
                        cn(
                            'hidden border-b bg-muted/40 py-2 text-[0.7188rem] font-medium tracking-[0.04em] text-muted-foreground uppercase lg:grid',
                            embedded
                                ? 'gap-x-3 px-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,0.75fr)_76px]'
                                : 'px-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,0.75fr)_84px] lg:gap-x-3 xl:grid-cols-[minmax(220px,1fr)_minmax(280px,1.4fr)_minmax(220px,1fr)_minmax(170px,0.7fr)_84px] xl:gap-x-5',
                        )
                    "
                    aria-hidden="true"
                >
                    <span class="pl-5">Sản phẩm</span>
                    <span class="pl-1.5">Sản phẩm TikTok Shop</span>
                    <span>Tên giỏ trên video</span>
                    <span class="pl-1.5">Bìa &amp; hashtag</span>
                    <span />
                </div>

                <div v-if="loading" class="divide-y">
                    <div
                        v-for="i in 5"
                        :key="i"
                        class="flex items-center gap-5 px-5 py-4"
                    >
                        <Skeleton class="h-10 w-40" />
                        <Skeleton class="h-12 flex-1" />
                        <Skeleton class="h-10 w-56" />
                    </div>
                </div>
                <div v-else-if="visibleRows.length" class="divide-y">
                    <CartRow
                        v-for="r in visibleRows"
                        :key="r.key"
                        :row="r"
                        :card="cardOf(r)"
                        :name="nameOf(r)"
                        :name-max="name_max"
                        :dirty="isDirty(r)"
                        :has-draft="!!draft[r.key]"
                        :busy="busy === `row-${r.key}`"
                        :persona="personaOf(r.code)"
                        :compact="embedded"
                        @personalise="openProduct(r.code, r.hub_name)"
                        @rename="openRename(r)"
                        @remove="removeProduct(r)"
                        @pick="picking = r.key"
                        @update:name="(v: string) => editName(r, v)"
                        @save="saveRow(r)"
                        @clear="clearRow(r)"
                    />
                </div>
                <EmptyState
                    v-else-if="!rows.length"
                    class="border-0 shadow-none"
                    title="Chưa có sản phẩm nào"
                    description="Bấm “Thêm sản phẩm”, chọn một sản phẩm trong shop TikTok: app tạo sản phẩm trong Xưởng Video và gắn giỏ hàng luôn."
                >
                    <Button size="sm" @click="addOpen = true">
                        <IconPlus class="size-4" />
                        Thêm sản phẩm
                    </Button>
                </EmptyState>
                <div
                    v-else-if="search.trim()"
                    class="flex flex-col items-center gap-3 px-5 py-10 text-center text-[0.8125rem] text-muted-foreground"
                    data-testid="fork-gio-hang-search-empty"
                >
                    <p>Không có sản phẩm nào khớp “{{ search.trim() }}”.</p>
                    <Button size="sm" variant="outline" @click="search = ''"
                        >Xoá tìm kiếm</Button
                    >
                </div>
                <p
                    v-else
                    class="px-5 py-10 text-center text-[0.8125rem] text-muted-foreground"
                >
                    Không có sản phẩm nào ở mục này.
                </p>

                <p
                    v-if="sample_hidden"
                    class="border-t px-5 py-3 text-[0.7812rem] text-muted-foreground"
                    data-testid="fork-gio-hang-sample-hidden"
                >
                    Sản phẩm ví dụ đã được ẩn vì đã có sản phẩm thật.
                </p>
            </section>

            <!-- Thanh "Lưu tất cả": hiện khi còn dòng đã chọn giỏ mà chưa lưu -->
            <div
                v-if="dirtyRows.length"
                :class="
                    cn(
                        'sticky bottom-4 z-20 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-xl border bg-card px-4 py-3 shadow-[0_12px_32px_-8px_rgba(0,0,0,.28)]',
                        embedded && 'bottom-0',
                    )
                "
                role="region"
                aria-label="Thay đổi chưa lưu"
                data-testid="fork-gio-hang-save-bar"
            >
                <span class="text-[0.875rem] font-medium"
                    >{{ dirtyRows.length }} dòng chưa lưu</span
                >
                <div class="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        :disabled="busy === 'save-all'"
                        data-testid="fork-gio-hang-discard-all"
                        @click="discardDrafts"
                        >Bỏ thay đổi</Button
                    >
                    <Button
                        size="sm"
                        :disabled="busy !== null"
                        data-testid="fork-gio-hang-save-all"
                        @click="saveAll"
                    >
                        <Spinner v-if="busy === 'save-all'" class="size-4" />
                        Lưu tất cả
                    </Button>
                </div>
            </div>
        </template>

        <PersonaliseDialog
            v-bind="dialogProps"
            :in-place="embedded"
            @update:open="closePersonalise"
            @saved="onPersonaSaved"
        />

        <ShopPickerDialog
            mode="add"
            :open="addOpen"
            row-label=""
            :products="products"
            current-id=""
            :busy-id="
                busy?.startsWith('hide-') ? busy.slice('hide-'.length) : null
            "
            :adding="adding"
            :syncing="busy === 'sync' || syncState === 'waiting'"
            @update:open="(v: boolean) => (addOpen = v)"
            @select="addProduct"
            @toggle-hidden="setHidden"
            @sync="syncShop"
        />

        <Dialog
            :open="renaming !== null"
            @update:open="(v: boolean) => !v && (renaming = null)"
        >
            <DialogContent
                class="sm:max-w-md"
                data-testid="fork-gio-hang-rename"
            >
                <DialogHeader>
                    <DialogTitle>Đổi tên sản phẩm</DialogTitle>
                    <DialogDescription
                        >Tên gọi ngắn hiện trong app và được đọc trong video. Mã
                        sản phẩm không đổi.</DialogDescription
                    >
                </DialogHeader>
                <Input
                    v-model="renameValue"
                    class="h-11"
                    :maxlength="name_short_max ?? 40"
                    data-testid="fork-gio-hang-rename-input"
                    @keyup.enter="saveRename"
                />
                <DialogFooter>
                    <Button variant="outline" @click="renaming = null"
                        >Huỷ</Button
                    >
                    <Button
                        :disabled="!renameValue.trim() || busy !== null"
                        @click="saveRename"
                        >Lưu tên</Button
                    >
                </DialogFooter>
            </DialogContent>
        </Dialog>

        <Dialog :open="copyOpen" @update:open="(v: boolean) => (copyOpen = v)">
            <DialogContent
                class="sm:max-w-md"
                data-testid="fork-gio-hang-copy-dialog"
            >
                <DialogHeader>
                    <DialogTitle>Sao chép giỏ sang kênh khác</DialogTitle>
                    <DialogDescription
                        >Chép giỏ đã chọn của
                        <b>{{ channel ? channelLabel(channel) : '' }}</b>
                        ({{ copyRowCount }} dòng) sang các kênh anh tick dưới
                        đây.</DialogDescription
                    >
                </DialogHeader>
                <ul class="flex flex-col gap-1.5">
                    <li v-for="c in copyTargets" :key="c.id">
                        <label
                            class="flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-[0.875rem] hover:bg-accent/50"
                        >
                            <input
                                type="checkbox"
                                class="size-4 accent-primary"
                                :checked="copyTo.includes(c.id)"
                                :data-testid="`fork-gio-hang-copy-to-${c.id}`"
                                @change="
                                    toggleCopyTarget(
                                        c.id,
                                        ($event.target as HTMLInputElement)
                                            .checked,
                                    )
                                "
                            />
                            <span class="font-medium">{{
                                channelLabel(c)
                            }}</span>
                        </label>
                    </li>
                </ul>
                <p class="text-[0.8125rem] text-muted-foreground">
                    Chỉ sao chép các dòng đã có giỏ. Dòng đã có giỏ ở kênh đích
                    được giữ nguyên.
                </p>
                <label
                    class="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-[0.875rem]"
                >
                    Ghi đè cả những dòng đã có
                    <Switch
                        :model-value="copyOverwrite"
                        aria-label="Ghi đè cả những dòng đã có"
                        data-testid="fork-gio-hang-copy-overwrite"
                        @update:model-value="
                            (v: boolean) => (copyOverwrite = v)
                        "
                    />
                </label>
                <DialogFooter>
                    <Button variant="outline" @click="copyOpen = false"
                        >Huỷ</Button
                    >
                    <Button
                        :disabled="copyTo.length === 0 || busy !== null"
                        data-testid="fork-gio-hang-copy-submit"
                        @click="doCopy"
                    >
                        <Spinner v-if="busy === 'copy'" class="size-4" />
                        Sao chép
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>

        <ShopPickerDialog
            :open="picking !== null"
            :row-label="pickingRow?.label ?? ''"
            :products="products"
            :current-id="pickingRow ? pickedId(pickingRow) : ''"
            :search-hint="pickingRow?.hub_name ?? ''"
            :syncing="busy === 'sync' || syncState === 'waiting'"
            :busy-id="
                busy?.startsWith('hide-') ? busy.slice('hide-'.length) : null
            "
            @update:open="(v: boolean) => !v && (picking = null)"
            @select="pickFor"
            @toggle-hidden="setHidden"
            @sync="syncShop"
        />
    </div>
</template>

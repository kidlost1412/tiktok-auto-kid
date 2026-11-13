<script setup lang="ts">
// Trang riêng của bản Việt hoá: chọn sản phẩm TikTok Shop cho từng sản phẩm của hub, từng quy cách, trên từng kênh.
// Bố cục: thanh kênh + lấy sản phẩm shop ở trên, bộ lọc theo trạng thái, rồi một bảng gọn — mỗi dòng một sản phẩm.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en).
import { Link, router } from '@inertiajs/vue3';
import {
    IconCheck,
    IconHash,
    IconPlugConnectedX,
    IconPlus,
    IconRefresh,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';

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
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import { cardCls, toneClasses } from '@/components/fork/shared/status';
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
}>();

const busy = ref<string | null>(null);
const opts = {
    preserveScroll: true,
    onFinish: () => {
        busy.value = null;
    },
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
const { loading, callbacks } = useVisitLoading();

const chooseChannel = (id: string) => {
    if (id === props.selected) {
        return;
    }

    router.get(
        '/auto/gio-hang',
        { kenh: id },
        { preserveScroll: false, ...callbacks },
    );
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
    router.post(`/auto/accounts/${props.selected}/shop/sync`, {}, opts);
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
            timer = setInterval(() => {
                router.reload({ only: ['sync'] });
            }, 2000);
        } else if (before === 'waiting') {
            router.reload({
                only: ['sync', 'products', 'rows', 'sample_hidden'],
            });
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
        opts,
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
        {
            ...opts,
            onSuccess: () => {
                delete draft[r.key];
            },
        },
    );
};

const clearRow = (r: Row) => {
    if (!props.selected) {
        return;
    }

    if (!r.link) {
        delete draft[r.key];

        return;
    }

    busy.value = `row-${r.key}`;
    router.delete(`/auto/accounts/${props.selected}/links/${r.code}`, {
        ...opts,
        data: { quy_cach: r.quy_cach },
        onSuccess: () => {
            delete draft[r.key];
        },
    });
};

// ---- "+ Thêm sản phẩm": chọn sản phẩm shop -> app tạo sản phẩm hub tương ứng và gắn giỏ một lần ----
const addOpen = ref(false);
const adding = ref(false);

const addProduct = (p: ShopProduct) => {
    if (!props.selected) {
        return;
    }

    adding.value = true;
    router.post(
        `/auto/accounts/${props.selected}/hub-products`,
        { shop_product_id: p.product_id, display_name: p.suggested_name },
        {
            preserveScroll: true,
            onSuccess: () => {
                addOpen.value = false;
            },
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
        {
            ...opts,
            onSuccess: () => {
                renaming.value = null;
            },
        },
    );
};

const removing = ref<Row | null>(null);

const confirmRemove = () => {
    const r = removing.value;

    if (!r) {
        return;
    }

    busy.value = `rename-${r.code}`;
    router.delete(`/auto/hub-products/${r.code}`, {
        ...opts,
        onSuccess: () => {
            removing.value = null;
        },
    });
};

const onlySample = computed(
    () => props.rows.length > 0 && props.rows.every((r) => r.is_sample),
);

// ---- Cá nhân hoá (ảnh bìa, hashtag) theo sản phẩm hub; 'default' = hashtag mặc định chung ----
const { personaOf, dialogProps, openProduct, openDefault, closePersonalise } =
    usePersonalise(() => props);

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

const visibleRows = computed(() => {
    const want = { all: null, need: 0, bad: 1, ok: 2 }[filter.value];

    return want === null
        ? sortedRows.value
        : sortedRows.value.filter((r) => rank(r) === want);
});

watch(
    () => props.selected,
    () => {
        filter.value = 'all';
    },
);

const channel = computed(
    () => props.channels.find((c) => c.id === props.selected) ?? null,
);
const initial = (c: { username: string | null; display_name: string | null }) =>
    [...(c.display_name || c.username || '?').trim()][0]?.toUpperCase() ?? '?';
</script>

<template>
    <AutoShell
        title="Giỏ hàng"
        description="Gắn sản phẩm TikTok Shop cho video của từng sản phẩm, theo từng kênh. Sản phẩm chưa chọn giỏ thì video được giữ trong kho."
        testid="fork-gio-hang-page"
    >
        <template v-if="channels.length" #actions>
            <Button
                variant="outline"
                data-testid="fork-personalise-default"
                @click="openDefault"
            >
                <IconHash class="size-4" />
                Hashtag mặc định{{
                    personalise_default?.tags.length
                        ? ` (${personalise_default.tags.length})`
                        : ''
                }}
            </Button>
            <Button data-testid="fork-gio-hang-add" @click="addOpen = true">
                <IconPlus class="size-4" />
                Thêm sản phẩm
            </Button>
        </template>

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
                                    'flex h-10 items-center gap-2.5 rounded-full border py-1 pr-4 pl-1 text-[13.5px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
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
                                        'flex size-8 items-center justify-center rounded-full text-[13px] font-semibold',
                                        c.id === selected
                                            ? 'bg-primary text-primary-foreground'
                                            : 'bg-muted text-muted-foreground',
                                    )
                                "
                                >{{ initial(c) }}</span
                            >
                            @{{ c.username }}
                            <IconCheck
                                v-if="c.id === selected"
                                class="size-4 text-primary-text"
                            />
                        </button>
                    </div>

                    <div class="flex flex-wrap items-center gap-3">
                        <div
                            class="text-right text-[12.5px] leading-snug"
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
                            class="flex items-center justify-between text-[13px] font-medium"
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
                    <p v-else class="text-[13px] text-muted-foreground">
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
                            'border-t px-5 py-3 text-[13px]',
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
                        Lấy sản phẩm bị lỗi: {{ sync?.reason }}. Tiện ích có thể
                        tự thử lại; nếu không được, bấm “Lấy lại từ shop”.
                    </template>
                    <template v-else>
                        Yêu cầu đã hết hạn sau {{ sync_ttl_minutes }} phút mà
                        tiện ích chưa lấy được. Kiểm tra Chrome đang mở rồi bấm
                        lại.
                    </template>
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
                class="grid grid-cols-2 gap-3 xl:grid-cols-4"
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
                            class="font-heading text-[22px] leading-tight font-[650] tracking-[-0.02em] tabular-nums"
                        >
                            {{ t.value }}
                        </div>
                        <div
                            class="truncate text-[12.5px] text-muted-foreground"
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
                        role="tablist"
                        aria-label="Lọc theo trạng thái"
                    >
                        <button
                            v-for="f in filters"
                            :key="f.key"
                            type="button"
                            role="tab"
                            :aria-selected="filter === f.key"
                            :disabled="f.key !== 'all' && !f.count"
                            :class="
                                cn(
                                    'flex h-8 items-center gap-2 rounded-lg px-3 text-[13px] font-medium transition-colors disabled:opacity-40',
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
                    <span
                        v-if="channel"
                        class="text-[12.5px] text-muted-foreground"
                        >Giỏ hàng của
                        <b class="font-medium text-foreground"
                            >@{{ channel.username }}</b
                        ></span
                    >
                </header>

                <div
                    class="hidden border-b bg-muted/40 px-5 py-2 text-[11.5px] font-medium tracking-[0.04em] text-muted-foreground uppercase lg:grid lg:grid-cols-[minmax(220px,1fr)_minmax(280px,1.4fr)_minmax(220px,1fr)_minmax(170px,0.7fr)_84px] lg:gap-x-5"
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
                        @personalise="openProduct(r.code, r.hub_name)"
                        @rename="openRename(r)"
                        @remove="removing = r"
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
                <p
                    v-else
                    class="px-5 py-10 text-center text-[13px] text-muted-foreground"
                >
                    Không có sản phẩm nào ở mục này.
                </p>

                <p
                    v-if="sample_hidden"
                    class="border-t px-5 py-3 text-[12.5px] text-muted-foreground"
                    data-testid="fork-gio-hang-sample-hidden"
                >
                    Sản phẩm ví dụ đã được ẩn vì đã có sản phẩm thật.
                </p>
            </section>
        </template>

        <PersonaliseDialog
            v-bind="dialogProps"
            @update:open="closePersonalise"
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
            @update:open="(v: boolean) => (addOpen = v)"
            @select="addProduct"
            @toggle-hidden="setHidden"
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

        <Dialog
            :open="removing !== null"
            @update:open="(v: boolean) => !v && (removing = null)"
        >
            <DialogContent
                class="sm:max-w-md"
                data-testid="fork-gio-hang-remove-confirm"
            >
                <DialogHeader>
                    <DialogTitle
                        >Xoá sản phẩm “{{ removing?.hub_name }}”?</DialogTitle
                    >
                    <DialogDescription>
                        Hồ sơ sản phẩm được đưa vào Thùng rác của Windows; video
                        gốc và video đã làm không bị xoá. Giỏ hàng đã chọn cho
                        sản phẩm này cũng bị bỏ.
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="outline" @click="removing = null"
                        >Huỷ</Button
                    >
                    <Button
                        variant="destructive"
                        :disabled="busy !== null"
                        @click="confirmRemove"
                    >
                        <Spinner
                            v-if="busy?.startsWith('rename-')"
                            class="size-4"
                        />
                        Xoá sản phẩm
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>

        <ShopPickerDialog
            :open="picking !== null"
            :row-label="pickingRow?.label ?? ''"
            :products="products"
            :current-id="pickingRow ? pickedId(pickingRow) : ''"
            :busy-id="
                busy?.startsWith('hide-') ? busy.slice('hide-'.length) : null
            "
            @update:open="(v: boolean) => !v && (picking = null)"
            @select="pickFor"
            @toggle-hidden="setHidden"
        />
    </AutoShell>
</template>

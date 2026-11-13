<script setup lang="ts">
// Trang riêng của bản Việt hoá: thư viện video (Xưởng Video) sẵn sàng đăng.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en).
import { Link, router } from '@inertiajs/vue3';
import {
    IconArchive,
    IconChevronDown,
    IconFolder,
    IconLayoutList,
    IconRefresh,
    IconSearch,
    IconTable,
    IconVideoOff,
    IconX,
} from '@tabler/icons-vue';
import { useDebounceFn } from '@vueuse/core';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { dayKey, dayLabel, type KhoVideo } from '@/components/fork/kho/kho';
import KhoSwitch from '@/components/fork/kho/KhoSwitch.vue';
import VideoCard from '@/components/fork/kho/VideoCard.vue';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { openVideo as openViewer } from '@/components/fork/viewer';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import {
    cardCls,
    tableWrapCls,
    tdCls,
    thCls,
    toneClasses,
} from '@/components/fork/shared/status';
import { useVisitLoading } from '@/components/fork/shared/useVisitLoading';
import { Button } from '@/components/ui/button';
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

interface MatrixRow {
    code: string | null;
    name: string;
    image?: string | null;
    quy_cach: string | null;
    quy_cach_name: string | null;
    new: number;
    scheduled: number;
    posted: number;
    failed: number;
    skipped: number;
}

interface Blocker {
    code: string;
    severity: string;
    count: number;
    message: string;
    action: string;
    href: string | null;
}

const props = defineProps<{
    kho: {
        path: string;
        done_path: string;
        error_path: string;
        exists: boolean;
        legacy_ra: boolean;
        waiting: number;
        error: number;
    };
    hub: {
        enabled: boolean;
        url: string;
        state: string;
        label: string;
        pending: number;
    };
    retention: { value: string; options: { value: string; label: string }[] };
    matrix: MatrixRow[];
    products: {
        code: string;
        name: string;
        image?: string | null;
        count: number;
    }[];
    filters: {
        tab: string;
        product: string;
        legacy: boolean;
        sort?: string;
        q?: string;
        day?: string;
    };
    days: string[];
    counts: Record<string, number>;
    legacy_count: number;
    blockers: Blocker[];
    videos: {
        data: KhoVideo[];
        current_page: number;
        last_page: number;
        total: number;
    };
    updated_at: string;
    last_ingest_at: string | null;
}>();

const busy = ref('');
const advancedOpen = ref(false);
const { loading, callbacks } = useVisitLoading();

const tabs = [
    { key: 'cho', label: 'Chờ đăng' },
    { key: 'xep', label: 'Đã xếp lịch' },
    { key: 'dang', label: 'Đã đăng' },
    { key: 'loi', label: 'Lỗi và bỏ qua' },
    { key: 'all', label: 'Tất cả' },
];

const fmtClock = (iso: string | null) =>
    iso ? dayjs(iso).format('HH:mm DD/MM') : '—';

const opts = {
    preserveScroll: true,
    onFinish: () => (busy.value = ''),
};

const saveRetention = (value: string) => {
    busy.value = 'retention';
    router.patch('/auto/kho/settings', { retention: value }, opts);
};

const ping = () => {
    busy.value = 'ping';
    router.post('/auto/kho/ping', {}, opts);
};

const scan = () => {
    busy.value = 'scan';
    router.post('/auto/kho/scan', {}, opts);
};

type Patch = Partial<{
    tab: string;
    product: string;
    legacy: boolean;
    page: number;
    sort: string;
    q: string;
    day: string;
}>;

// Lần tự làm mới đang bay: phải huỷ ngay khi người dùng đổi bộ lọc, kẻo dữ liệu của bộ lọc cũ ghi đè lưới mới.
let pollCancel: { cancel: () => void } | null = null;
let visiting = false;

// Chip sản phẩm sáng lên ngay khi bấm (không chờ máy chủ trả lưới mới); khi dữ liệu về thì theo filters thật.
const pickedProduct = ref<string | null>(null);

watch(
    () => props.filters.product,
    () => (pickedProduct.value = null),
);

const activeProduct = computed(() => pickedProduct.value ?? props.filters.product);

const pickProduct = (code: string) => {
    go({ product: activeProduct.value === code ? '' : code });
};

const go = (patch: Patch) => {
    if ('product' in patch) {
        pickedProduct.value = patch.product ?? '';
    }

    pollCancel?.cancel();
    pollCancel = null;
    const next = {
        tab: props.filters.tab,
        product: props.filters.product,
        legacy: props.filters.legacy,
        sort: props.filters.sort ?? 'moi',
        q: props.filters.q ?? '',
        day: props.filters.day ?? '',
        // Đổi tab thì ngày đang chọn không còn ý nghĩa (mỗi tab tính ngày theo cách khác).
        ...('tab' in patch && !('day' in patch) ? { day: '' } : {}),
        ...patch,
    };
    const query: Record<string, string | number> = { tab: next.tab };

    if (next.product) {
        query.product = next.product;
    }

    if (next.legacy) {
        query.legacy = 1;
    }

    if (next.sort && next.sort !== 'moi') {
        query.sort = next.sort;
    }

    if (next.q) {
        query.q = next.q;
    }

    if (next.day) {
        query.day = next.day;
    }

    if (patch.page) {
        query.page = patch.page;
    }

    router.get('/auto/kho', query, {
        preserveScroll: true,
        preserveState: true,
        onStart: () => {
            visiting = true;
            callbacks.onStart();
        },
        onFinish: () => {
            visiting = false;
            pickedProduct.value = null;
            callbacks.onFinish();
        },
    });
};

// ----- Tìm kiếm trong caption / tên file (chờ người dùng gõ xong mới tải).
const search = ref(props.filters.q ?? '');
const runSearch = useDebounceFn((v: string) => go({ q: v.trim() }), 350);

watch(search, (v) => {
    if (v.trim() !== (props.filters.q ?? '')) {
        runSearch(v);
    }
});

const sort = computed(() => props.filters.sort ?? 'moi');

const filtered = computed(
    () =>
        props.filters.product !== '' ||
        (props.filters.q ?? '') !== '' ||
        (props.filters.day ?? '') !== '' ||
        props.filters.legacy,
);

const clearFilters = () => {
    search.value = '';
    go({ product: '', q: '', legacy: false, day: '' });
};

// ----- Nhóm theo ngày (nhớ lựa chọn của người dùng).
const grouped = ref(false);

onMounted(() => {
    try {
        grouped.value = localStorage.getItem('fork-kho-grouped') === '1';
    } catch {
        grouped.value = false;
    }
});

watch(grouped, (v) => {
    try {
        localStorage.setItem('fork-kho-grouped', v ? '1' : '0');
    } catch {
        // Trình duyệt chặn lưu trữ: bỏ qua, chỉ không nhớ được lựa chọn.
    }
});

const groups = computed(() => {
    if (!grouped.value) {
        return [{ key: '', label: '', items: props.videos.data }];
    }

    const out: { key: string; label: string; items: KhoVideo[] }[] = [];

    for (const v of props.videos.data) {
        const key = dayKey(v);
        const last = out[out.length - 1];

        if (last && last.key === key) {
            last.items.push(v);
        } else {
            out.push({ key, label: dayLabel(key), items: [v] });
        }
    }

    return out;
});

// Bấm thẻ video: mở khung xem dùng chung, ←/→ chuyển trong danh sách đang hiển thị.
const openVideo = (v: KhoVideo) =>
    openViewer(
        props.videos.data.map((x) => x.id),
        v.id,
        props.videos.data,
    );

// Không đọc số cũ: tự làm mới mỗi 30 giây khi tab đang mở (chỉ tải lại dữ liệu, không đặt lại bộ lọc hay hộp thoại).
let timer: ReturnType<typeof setInterval> | undefined;

onMounted(() => {
    // Liên kết từ tin Telegram: /auto/kho?video=<id> mở thẳng khung xem video đó.
    const wanted = Number(new URLSearchParams(window.location.search).get('video'));

    if (Number.isInteger(wanted) && wanted > 0) {
        openViewer([wanted], wanted);
    }

    timer = setInterval(() => {
        // Bỏ qua nếu đang chuyển bộ lọc / đang có lần làm mới khác; luôn tải đúng bộ lọc hiện tại (không dựa vào URL cũ).
        if (
            document.visibilityState !== 'visible' ||
            visiting ||
            pollCancel
        ) {
            return;
        }

        const f = props.filters;
        const query: Record<string, string | number> = { tab: f.tab };

        if (f.product) {
            query.product = f.product;
        }

        if (f.legacy) {
            query.legacy = 1;
        }

        if (f.sort && f.sort !== 'moi') {
            query.sort = f.sort;
        }

        if (f.q) {
            query.q = f.q;
        }

        if (f.day) {
            query.day = f.day;
        }

        if (props.videos.current_page > 1) {
            query.page = props.videos.current_page;
        }

        router.get('/auto/kho', query, {
            preserveScroll: true,
            preserveState: true,
            replace: true,
            only: [
                'filters',
                'kho',
                'matrix',
                'videos',
                'counts',
                'products',
                'blockers',
                'legacy_count',
                'days',
                'hub',
                'updated_at',
                'last_ingest_at',
            ],
            onCancelToken: (t) => (pollCancel = t),
            onFinish: () => (pollCancel = null),
        });
    }, 30000);
});

onBeforeUnmount(() => clearInterval(timer));

const hubOk = computed(() => !props.hub.enabled || props.hub.state === 'ok');

const description = computed(
    () =>
        `Video từ Xưởng Video chờ đăng. Cập nhật ${fmtClock(props.updated_at)} · quét kho lần cuối ${fmtClock(props.last_ingest_at)}.`,
);
</script>

<template>
    <AutoShell
        title="Kho video"
        :description="description"
        testid="fork-kho-page"
    >
        <template #actions>
            <span
                id="hub"
                class="inline-flex h-8 scroll-mt-24 items-center gap-2 rounded-full border bg-card px-3 text-[12.5px] font-medium text-muted-foreground shadow-xs"
                data-testid="fork-kho-hub-status"
            >
                <span
                    :class="
                        cn(
                            'size-2 rounded-full',
                            toneClasses[hubOk ? 'success' : 'danger'].dot,
                        )
                    "
                />
                <template v-if="hub.enabled">Hub {{ hub.label }}</template>
                <template v-else>{{ hub.label }}</template>
                <template v-if="hub.pending">
                    · {{ hub.pending }} báo cáo chờ gửi</template
                >
            </span>
            <Button
                v-if="hub.enabled"
                size="sm"
                variant="outline"
                :disabled="busy === 'ping'"
                @click="ping"
            >
                {{ busy === 'ping' ? 'Đang kiểm tra…' : 'Kiểm tra kết nối' }}
            </Button>
            <Button size="sm" :disabled="busy === 'scan'" @click="scan">
                <IconRefresh
                    class="size-4"
                    :class="{ 'animate-spin': busy === 'scan' }"
                />
                {{ busy === 'scan' ? 'Đang quét…' : 'Quét kho ngay' }}
            </Button>
        </template>

        <KhoSwitch active="hub" />

        <!-- Vấn đề đang chặn video -->
        <Callout
            v-if="blockers.length"
            tone="warn"
            data-testid="fork-kho-blockers"
        >
            <div class="mb-1.5 font-semibold">
                Có video đang chờ vì chưa đủ điều kiện đăng
            </div>
            <ul class="flex flex-col gap-1.5">
                <li
                    v-for="b in blockers"
                    :key="b.code + b.message"
                    class="flex flex-wrap items-center justify-between gap-2"
                >
                    <span>{{ b.message }}</span>
                    <Button
                        v-if="b.href"
                        as-child
                        size="sm"
                        variant="outline"
                        class="bg-background"
                    >
                        <Link :href="b.href">{{ b.action }} →</Link>
                    </Button>
                    <span v-else class="text-xs opacity-80">{{
                        b.action
                    }}</span>
                </li>
            </ul>
        </Callout>

        <!-- Thanh lọc dính trên cùng khi cuộn -->
        <section
            :class="cn(cardCls, 'sticky top-2 z-20 flex flex-col gap-3.5 bg-card/95 p-4 backdrop-blur supports-[backdrop-filter]:bg-card/85')"
            data-testid="fork-kho-filters"
        >
            <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
                <div class="max-w-full overflow-x-auto">
                    <Tabs
                        :model-value="filters.tab"
                        @update:model-value="go({ tab: String($event) })"
                    >
                        <TabsList data-testid="fork-kho-tabs">
                            <TabsTrigger
                                v-for="t in tabs"
                                :key="t.key"
                                :value="t.key"
                            >
                                {{ t.label }}
                                <span
                                    class="rounded-full bg-foreground/10 px-1.5 text-xs tabular-nums"
                                >
                                    {{ counts[t.key] ?? 0 }}
                                </span>
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                </div>

                <div class="ml-auto flex flex-wrap items-center gap-2">
                    <div class="relative">
                        <IconSearch
                            class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
                        />
                        <Input
                            v-model="search"
                            type="search"
                            placeholder="Tìm trong caption, tên file…"
                            class="h-10 w-64 pl-9"
                            aria-label="Tìm video theo caption hoặc tên file"
                            data-testid="fork-kho-search"
                        />
                    </div>
                    <NativeSelect
                        :model-value="filters.day ?? ''"
                        aria-label="Lọc theo ngày"
                        data-testid="fork-kho-day"
                        @update:model-value="go({ day: String($event) })"
                    >
                        <option value="">Tất cả ngày</option>
                        <option v-for="d in days" :key="d" :value="d">
                            {{ dayjs(d).format('DD/MM/YYYY') }}
                        </option>
                    </NativeSelect>
                    <NativeSelect
                        :model-value="sort"
                        aria-label="Sắp xếp"
                        data-testid="fork-kho-sort"
                        @update:model-value="go({ sort: String($event) })"
                    >
                        <option value="moi">Mới nhất</option>
                        <option value="sap-dang">Sắp đăng</option>
                    </NativeSelect>
                    <Button
                        :variant="grouped ? 'secondary' : 'outline'"
                        :aria-pressed="grouped"
                        title="Gom video theo ngày"
                        @click="grouped = !grouped"
                    >
                        <IconLayoutList class="size-4" />
                        Nhóm theo ngày
                    </Button>
                </div>
            </div>

            <div
                class="-mx-1 flex items-center gap-2 overflow-x-auto px-1 pb-0.5"
                data-testid="fork-kho-products"
            >
                <Button
                    size="sm"
                    :variant="activeProduct === '' ? 'default' : 'outline'"
                    :aria-pressed="activeProduct === ''"
                    class="h-9 shrink-0 rounded-full"
                    @click="go({ product: '' })"
                >
                    Mọi sản phẩm
                    <span class="tabular-nums opacity-70">{{
                        counts[filters.tab] ?? 0
                    }}</span>
                </Button>
                <Button
                    v-for="p in products.filter(
                        (x) => x.count > 0 || x.code === filters.product,
                    )"
                    :key="p.code"
                    size="sm"
                    :variant="activeProduct === p.code ? 'default' : 'outline'"
                    :aria-pressed="activeProduct === p.code"
                    class="h-9 shrink-0 rounded-full"
                    @click="pickProduct(p.code)"
                >
                    <ProductThumb :src="p.image" class="size-5 rounded" />
                    {{ p.name }}
                    <span class="tabular-nums opacity-70">{{ p.count }}</span>
                </Button>
                <label
                    v-if="legacy_count > 0"
                    class="ml-auto flex shrink-0 cursor-pointer items-center gap-2 pl-3 text-xs text-muted-foreground"
                >
                    <input
                        type="checkbox"
                        :checked="filters.legacy"
                        @change="
                            go({
                                legacy: ($event.target as HTMLInputElement)
                                    .checked,
                            })
                        "
                    />
                    Hiện {{ legacy_count }} bản ghi cũ
                </label>
            </div>
        </section>

        <!-- Lưới video -->
        <section aria-live="polite">
            <div
                v-if="loading"
                class="grid grid-cols-2 gap-5 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6"
                data-testid="fork-kho-skeleton"
            >
                <div v-for="i in 10" :key="i" class="flex flex-col gap-2">
                    <Skeleton class="aspect-[9/16] w-full rounded-xl" />
                    <Skeleton class="h-4 w-2/3" />
                    <Skeleton class="h-3 w-full" />
                </div>
            </div>

            <div
                v-else-if="videos.data.length"
                class="flex flex-col gap-6"
                data-testid="fork-kho-videos"
            >
                <div
                    v-for="g in groups"
                    :key="g.key"
                    class="flex flex-col gap-3"
                >
                    <h3
                        v-if="grouped"
                        class="flex items-baseline gap-2 text-[15px] font-semibold"
                    >
                        {{ g.label }}
                        <span class="text-xs font-normal text-muted-foreground"
                            >{{ g.items.length }} video</span
                        >
                    </h3>
                    <div
                        class="grid grid-cols-2 gap-5 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6"
                    >
                        <VideoCard
                            v-for="v in g.items"
                            :key="v.id"
                            :video="v"
                            @open="openVideo(v)"
                        />
                    </div>
                </div>
            </div>

            <EmptyState
                v-else
                :icon="IconVideoOff"
                :title="
                    filtered
                        ? 'Không có video nào khớp bộ lọc'
                        : filters.tab === 'cho'
                          ? 'Chưa có video nào đang chờ đăng'
                          : 'Không có video nào trong mục này'
                "
                :description="
                    filtered
                        ? 'Thử bỏ bộ lọc sản phẩm, từ khoá tìm kiếm hoặc bản ghi cũ.'
                        : filters.tab === 'cho'
                          ? 'Hãy sản xuất video trong Xưởng Video rồi quét kho để lấy video mới về.'
                          : 'Chuyển sang mục khác hoặc xem tất cả video.'
                "
                data-testid="fork-kho-empty"
            >
                <Button
                    v-if="filtered"
                    size="sm"
                    variant="outline"
                    @click="clearFilters"
                >
                    <IconX class="size-4" /> Xoá bộ lọc
                </Button>
                <Button
                    v-else-if="filters.tab === 'cho'"
                    size="sm"
                    :disabled="busy === 'scan'"
                    @click="scan"
                >
                    <IconRefresh class="size-4" /> Quét kho ngay
                </Button>
                <Button
                    v-else
                    size="sm"
                    variant="outline"
                    @click="go({ tab: 'all' })"
                >
                    Xem tất cả video
                </Button>
            </EmptyState>

            <div
                v-if="videos.last_page > 1"
                class="mt-6 flex items-center justify-center gap-3 text-sm"
            >
                <Button
                    size="sm"
                    variant="outline"
                    :disabled="videos.current_page <= 1"
                    @click="go({ page: videos.current_page - 1 })"
                >
                    Trước
                </Button>
                <span class="tabular-nums"
                    >Trang {{ videos.current_page }} /
                    {{ videos.last_page }}</span
                >
                <Button
                    size="sm"
                    variant="outline"
                    :disabled="videos.current_page >= videos.last_page"
                    @click="go({ page: videos.current_page + 1 })"
                >
                    Sau
                </Button>
            </div>
        </section>

        <!-- Nâng cao -->
        <Collapsible v-model:open="advancedOpen">
            <CollapsibleTrigger as-child>
                <Button
                    variant="ghost"
                    size="sm"
                    class="gap-1.5"
                    data-testid="fork-kho-advanced-toggle"
                >
                    <IconChevronDown
                        class="size-4 transition"
                        :class="{ 'rotate-180': advancedOpen }"
                    />
                    Nâng cao
                </Button>
            </CollapsibleTrigger>
            <CollapsibleContent class="mt-3 flex flex-col gap-8">
                <!-- Lưu giữ -->
                <section
                    v-if="hub.enabled"
                    :class="cn(cardCls, 'p-5 sm:p-6')"
                    data-testid="fork-kho-hub-cleanup"
                >
                    <SectionHeading
                        :icon="IconArchive"
                        tone="neutral"
                        title="Lưu giữ video đã đăng"
                        description="Hub tự dọn file sau 30 ngày."
                    />
                </section>
                <section v-else :class="cn(cardCls, 'flex flex-col gap-4 p-5 sm:p-6')">
                    <SectionHeading
                        :icon="IconArchive"
                        tone="neutral"
                        title="Lưu giữ video đã đăng"
                    />
                    <div class="flex flex-wrap items-center gap-3">
                        <NativeSelect
                            :model-value="retention.value"
                            class="max-w-sm"
                            data-testid="fork-kho-retention"
                            :disabled="busy === 'retention'"
                            @update:model-value="saveRetention(String($event))"
                        >
                            <option
                                v-for="o in retention.options"
                                :key="o.value"
                                :value="o.value"
                            >
                                {{ o.label }}
                            </option>
                        </NativeSelect>
                        <span class="text-xs text-muted-foreground">
                            File kết quả luôn được giữ. Mỗi ngày app xoá video
                            và json quá hạn.
                        </span>
                    </div>
                </section>

                <!-- Số lượng -->
                <section :class="cn(cardCls, 'flex flex-col gap-4 p-5 sm:p-6')">
                    <SectionHeading
                        :icon="IconTable"
                        tone="info"
                        title="Số lượng theo sản phẩm và quy cách"
                    />
                    <div :class="tableWrapCls">
                        <table
                            class="w-full border-separate border-spacing-0 text-sm"
                            data-testid="fork-kho-matrix"
                        >
                            <thead>
                                <tr>
                                    <th :class="thCls">Sản phẩm</th>
                                    <th :class="thCls">Quy cách</th>
                                    <th :class="cn(thCls, 'text-right')">Mới</th>
                                    <th :class="cn(thCls, 'text-right')">Đã xếp</th>
                                    <th :class="cn(thCls, 'text-right')">Đã đăng</th>
                                    <th :class="cn(thCls, 'text-right')">Lỗi</th>
                                </tr>
                            </thead>
                            <tbody class="tabular-nums [&>tr:hover>td]:bg-accent/60 [&>tr:last-child>td]:border-b-0">
                                <tr
                                    v-for="r in matrix"
                                    :key="`${r.code}|${r.quy_cach}`"
                                >
                                    <td :class="cn(tdCls, 'font-medium')">
                                        <span class="flex items-center gap-2.5">
                                            <ProductThumb :src="r.image" />
                                            {{ r.name }}
                                        </span>
                                    </td>
                                    <td :class="tdCls">
                                        {{ r.quy_cach_name ?? '—' }}
                                    </td>
                                    <td :class="cn(tdCls, 'text-right')">{{ r.new }}</td>
                                    <td :class="cn(tdCls, 'text-right')">{{ r.scheduled }}</td>
                                    <td :class="cn(tdCls, 'text-right')">{{ r.posted }}</td>
                                    <td :class="cn(tdCls, 'text-right')">{{ r.failed }}</td>
                                </tr>
                                <tr v-if="!matrix.length">
                                    <td
                                        colspan="6"
                                        class="p-6 text-center text-muted-foreground"
                                    >
                                        Chưa có video nào trong kho.
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </section>

                <!-- Chuẩn kho (chỉ khi dùng thư mục hub) -->
                <section
                    v-if="!hub.enabled"
                    :class="cn(cardCls, 'flex flex-col gap-4 p-5 sm:p-6')"
                    data-testid="fork-kho-standard"
                >
                    <SectionHeading
                        :icon="IconFolder"
                        tone="neutral"
                        title="Chuẩn kho"
                    />
                    <div
                        class="rounded-xl border bg-muted/50 p-4 text-sm leading-relaxed"
                    >
                        <p>
                            Hub bỏ video sẵn sàng đăng vào
                            <code class="rounded bg-muted px-1">{{
                                kho.path
                            }}</code>
                            (thẳng trong thư mục, hoặc trong thư mục con theo mã
                            sản phẩm). Mỗi
                            <code class="rounded bg-muted px-1">X.mp4</code>
                            phải có
                            <code class="rounded bg-muted px-1">X.json</code>
                            cùng tên ghi <em>ma</em>, <em>quy_cach</em>,
                            <em>goc</em>, <em>giong</em>, <em>loi_thoai</em>,
                            <em>ngay_lam</em>, <em>phien_ban</em>. App chỉ nhặt
                            khi có đủ cả hai file, json đúng và mp4 đã ghi xong
                            (kích thước không đổi).
                        </p>
                        <p class="mt-2">
                            Video lỗi được chuyển vào
                            <code class="rounded bg-muted px-1">{{
                                kho.error_path
                            }}</code>
                            kèm file <em>.loi.txt</em> ghi lý do. Video đã đăng
                            chuyển sang
                            <code class="rounded bg-muted px-1">{{
                                kho.done_path
                            }}</code>
                            cùng file kết quả (<em>.ket-qua.json</em>).
                        </p>
                        <p class="mt-2 text-muted-foreground">
                            Thư mục kho: {{ kho.exists ? 'có' : 'chưa có' }} ·
                            đang chờ nhặt: {{ kho.waiting }} · trong _loi:
                            {{ kho.error }}
                            <template v-if="kho.legacy_ra">
                                · vẫn nhặt kiểu cũ ra/&lt;ngày&gt;</template
                            >
                        </p>
                    </div>
                </section>
            </CollapsibleContent>
        </Collapsible>
    </AutoShell>
</template>

<script setup lang="ts">
// Trang "Số liệu": hiệu quả các video đã đăng — lượt xem, tương tác, so sánh theo sản phẩm / góc / giờ / giọng / nhạc.
// Bố cục: chỉ số chính trong một thẻ → lượt xem theo ngày + người theo dõi → so sánh + top video → bình luận → bảng video.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en).
import { Link, router } from '@inertiajs/vue3';
import {
    IconArrowDownRight,
    IconArrowUpRight,
    IconChartBar,
    IconExternalLink,
    IconFilterOff,
} from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import {
    cardCls,
    fmtCompact,
    fmtNum,
    toneClasses,
} from '@/components/fork/shared/status';
import { useVisitLoading } from '@/components/fork/shared/useVisitLoading';
import BarChart from '@/components/fork/so-lieu/BarChart.vue';
import BreakdownCard from '@/components/fork/so-lieu/BreakdownCard.vue';
import type {
    BarPoint,
    CommentsData,
    DailyPoint,
    ExtensionInfo,
    Filters,
    Followers,
    Group,
    Kpi,
    KpiKey,
    Options,
    StatVideo,
} from '@/components/fork/so-lieu/types';
import VideoStatRow from '@/components/fork/so-lieu/VideoStatRow.vue';
import { openVideo } from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Skeleton } from '@/components/ui/skeleton';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    filters: Filters;
    options: Options;
    kpis: Record<KpiKey, Kpi>;
    daily: DailyPoint[];
    breakdowns: Record<string, Group[]>;
    videos: StatVideo[];
    videos_total: number;
    top: StatVideo[];
    bottom: StatVideo[];
    metrics_count: number;
    updated_at: string;
    collected_at: string | null;
    followers: Followers | null;
    comments: CommentsData;
    extension: ExtensionInfo;
}>();

const { loading, callbacks } = useVisitLoading();

const ranges = [
    { key: 'today', label: 'Hôm nay' },
    { key: '7d', label: '7 ngày' },
    { key: '30d', label: '30 ngày' },
    { key: 'custom', label: 'Tuỳ chọn' },
] as const;

const customOpen = ref(props.filters.range === 'custom');
const customFrom = ref(props.filters.from);
const customTo = ref(props.filters.to);

const apply = (patch: Partial<Filters>) => {
    const next = { ...props.filters, ...patch };
    const query: Record<string, string> = { range: next.range };

    if (next.range === 'custom') {
        query.from = next.from;
        query.to = next.to;
    }

    for (const k of ['channel', 'product', 'goc', 'giong'] as const) {
        if (next[k]) {
            query[k] = next[k];
        }
    }

    if (next.sort !== 'moi') {
        query.sort = next.sort;
    }

    if (next.cm === 'mua') {
        query.cm = 'mua';
    }

    router.get('/auto/so-lieu', query, {
        preserveScroll: true,
        preserveState: true,
        ...callbacks,
    });
};

const pickRange = (key: Filters['range']) => {
    customOpen.value = key === 'custom';

    if (key !== 'custom') {
        apply({ range: key });
    }
};

const applyCustom = () => {
    if (
        customFrom.value &&
        customTo.value &&
        customFrom.value <= customTo.value
    ) {
        apply({ range: 'custom', from: customFrom.value, to: customTo.value });
    }
};

const hasFilter = computed(
    () =>
        !!(
            props.filters.channel ||
            props.filters.product ||
            props.filters.goc ||
            props.filters.giong
        ),
);

const clearFilters = () =>
    apply({ channel: '', product: '', goc: '', giong: '' });

const productName = (code: string | null) =>
    props.options.products.find((p) => p.code === code)?.name ?? code ?? '—';

const rangeText = computed(() => {
    const f = dayjs(props.filters.from).format('DD/MM/YYYY');
    const t = dayjs(props.filters.to).format('DD/MM/YYYY');

    return f === t ? f : `${f} – ${t}`;
});

const pctText = (n: number) => `${n.toLocaleString('vi-VN')}%`;

// 4 chỉ số chính (to) và các chỉ số phụ (nhỏ, một hàng).
const primary: {
    key: KpiKey;
    label: string;
    format: (n: number) => string;
    hint?: string;
}[] = [
    { key: 'views', label: 'Tổng lượt xem', format: fmtNum },
    { key: 'posts', label: 'Bài đã đăng', format: fmtNum },
    {
        key: 'avg_views',
        label: 'View trung bình / bài',
        format: (n) => fmtNum(Math.round(n)),
    },
    {
        key: 'engagement',
        label: 'Tỉ lệ tương tác',
        format: pctText,
        hint: '(tim + bình luận + chia sẻ) / lượt xem',
    },
];

const secondary: {
    key: KpiKey;
    label: string;
    format: (n: number) => string;
}[] = [
    { key: 'likes', label: 'Tim', format: fmtNum },
    { key: 'comments', label: 'Bình luận', format: fmtNum },
    { key: 'shares', label: 'Chia sẻ', format: fmtNum },
    { key: 'saves', label: 'Lưu', format: fmtNum },
    {
        key: 'avg_watch_s',
        label: 'Xem TB · video ≤ 7 ngày',
        format: (n) => (n > 0 ? `${n.toLocaleString('vi-VN')} giây` : '—'),
    },
    {
        key: 'finish_rate',
        label: 'Xem hết · video ≤ 7 ngày',
        format: (n) => (n > 0 ? pctText(n) : '—'),
    },
];

const deltaCls = (k: Kpi) =>
    k.delta_pct === null || k.delta_pct === 0
        ? 'text-muted-foreground'
        : k.delta_pct > 0
          ? toneClasses.success.text
          : toneClasses.danger.text;

const deltaText = (k: Kpi) =>
    k.delta_pct === null
        ? 'chưa có kỳ trước'
        : `${Math.abs(k.delta_pct).toLocaleString('vi-VN')}%`;

// Đường nhỏ dưới "Tổng lượt xem".
const spark = computed(() => {
    const v = props.daily.map((d) => d.views);

    if (v.length < 2) {
        return null;
    }

    const max = Math.max(1, ...v);
    const W = 100;
    const H = 28;
    const pts = v.map(
        (y, i) =>
            `${((i / (v.length - 1)) * W).toFixed(2)},${(H - (y / max) * (H - 2) - 1).toFixed(2)}`,
    );

    return { line: pts.join(' '), area: `0,${H} ${pts.join(' ')} ${W},${H}` };
});

const axisEvery = (n: number) => (n > 60 ? 10 : n > 20 ? 5 : n > 10 ? 2 : 1);

const dailyPoints = computed<BarPoint[]>(() => {
    const every = axisEvery(props.daily.length);

    return props.daily.map((d, i) => ({
        key: d.date,
        axis: i % every === 0 ? dayjs(d.date).format('DD/MM') : '',
        title: dayjs(d.date).format('DD/MM/YYYY'),
        value: d.views,
        sub: `${d.posts} bài đăng`,
    }));
});

const bestDay = computed(() =>
    props.daily.reduce<DailyPoint | null>(
        (b, d) => (d.views > (b?.views ?? 0) ? d : b),
        null,
    ),
);

const followerPoints = computed<BarPoint[]>(() => {
    const series = props.followers?.series ?? [];
    const every = axisEvery(series.length);

    return series.map((d, i) => ({
        key: d.date,
        axis: i % every === 0 ? dayjs(d.date).format('DD/MM') : '',
        title: dayjs(d.date).format('DD/MM/YYYY'),
        value: Math.max(0, d.gain ?? 0),
        sub: `${fmtNum(d.followers)} người theo dõi`,
    }));
});

const collectedText = computed(() =>
    props.collected_at
        ? `Cập nhật ${dayjs(props.collected_at).format('HH:mm DD/MM')}`
        : 'Chưa thu số liệu lần nào',
);

const setComments = (cm: Filters['cm']) => apply({ cm });

const sorts = [
    { key: 'moi', label: 'Mới nhất' },
    { key: 'view', label: 'Nhiều view nhất' },
    { key: 'tuong-tac', label: 'Tương tác nhiều nhất' },
] as const;

// Top video: một thẻ, đổi giữa nhiều view nhất / ít view nhất.
const rankMode = ref<'top' | 'bottom'>('top');
const rankList = computed(() =>
    rankMode.value === 'top' ? props.top : props.bottom,
);
const rankMax = computed(() => Math.max(1, ...props.top.map((v) => v.views)));

const maxViews = computed(() =>
    Math.max(1, ...props.videos.map((v) => v.views)),
);

const seg = (on: boolean) =>
    cn(
        'inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-colors',
        on
            ? 'bg-card text-foreground shadow-xs dark:bg-white/10'
            : 'text-muted-foreground hover:text-foreground',
    );
const h2 = 'font-heading text-[16px] font-semibold tracking-[-0.01em]';
</script>

<template>
    <AutoShell
        title="Số liệu"
        :description="`Hiệu quả các video đã đăng · ${rangeText} · ${collectedText}.`"
        testid="fork-so-lieu-page"
    >
        <template #actions>
            <div
                class="flex gap-0.5 rounded-lg bg-muted p-1"
                role="tablist"
                aria-label="Khoảng thời gian"
            >
                <button
                    v-for="r in ranges"
                    :key="r.key"
                    type="button"
                    role="tab"
                    :aria-selected="filters.range === r.key"
                    :class="seg(filters.range === r.key)"
                    @click="pickRange(r.key)"
                >
                    {{ r.label }}
                </button>
            </div>
        </template>

        <!-- Bộ lọc -->
        <div
            class="flex flex-wrap items-center gap-2"
            data-testid="fork-so-lieu-filters"
        >
            <template v-if="customOpen">
                <Input
                    v-model="customFrom"
                    type="date"
                    class="h-9 w-40"
                    aria-label="Từ ngày"
                />
                <span class="text-sm text-muted-foreground">đến</span>
                <Input
                    v-model="customTo"
                    type="date"
                    class="h-9 w-40"
                    aria-label="Đến ngày"
                />
                <Button size="sm" class="h-9" @click="applyCustom"
                    >Áp dụng</Button
                >
                <span class="mx-1 hidden h-5 w-px bg-border sm:block" />
            </template>
            <NativeSelect
                :model-value="filters.channel"
                class="h-9"
                aria-label="Kênh"
                @update:model-value="apply({ channel: String($event) })"
            >
                <option value="">Mọi kênh</option>
                <option v-for="c in options.channels" :key="c.id" :value="c.id">
                    {{ c.name }}
                </option>
            </NativeSelect>
            <NativeSelect
                :model-value="filters.product"
                class="h-9"
                aria-label="Sản phẩm"
                @update:model-value="apply({ product: String($event) })"
            >
                <option value="">Mọi sản phẩm</option>
                <option
                    v-for="p in options.products"
                    :key="p.code"
                    :value="p.code"
                >
                    {{ p.name }}
                </option>
            </NativeSelect>
            <NativeSelect
                v-if="options.goc.length"
                :model-value="filters.goc"
                class="h-9"
                aria-label="Góc nội dung"
                @update:model-value="apply({ goc: String($event) })"
            >
                <option value="">Mọi góc</option>
                <option v-for="g in options.goc" :key="g" :value="g">
                    {{ g }}
                </option>
            </NativeSelect>
            <NativeSelect
                v-if="options.giong.length"
                :model-value="filters.giong"
                class="h-9"
                aria-label="Giọng"
                @update:model-value="apply({ giong: String($event) })"
            >
                <option value="">Mọi giọng</option>
                <option v-for="g in options.giong" :key="g" :value="g">
                    {{ g }}
                </option>
            </NativeSelect>
            <Button
                v-if="hasFilter"
                variant="ghost"
                size="sm"
                class="h-9"
                @click="clearFilters"
            >
                <IconFilterOff class="size-4" />
                Xoá lọc
            </Button>
        </div>

        <Callout
            v-if="extension.outdated"
            tone="warn"
            data-testid="fork-so-lieu-extension-banner"
        >
            <b>Tải lại tiện ích để thu số liệu.</b>
            Chrome đang chạy tiện ích bản {{ extension.version || 'cũ' }}, chưa
            thu được số liệu và bình luận (cần từ bản {{ extension.min }}). Mở
            chrome://extensions, bấm ⟳ ở tiện ích TikTok Auto Kid (nạp từ thư
            mục <code>extension\autotok</code> của app) rồi mở lại Chrome
            profile đó.
        </Callout>

        <!-- Khi chưa có bài nào -->
        <EmptyState
            v-if="!videos_total && !loading"
            :icon="IconChartBar"
            :title="
                hasFilter
                    ? 'Không có bài đăng nào khớp bộ lọc'
                    : 'Chưa có bài đăng nào trong khoảng này'
            "
            :description="
                hasFilter
                    ? 'Thử bỏ bớt bộ lọc hoặc chọn khoảng ngày rộng hơn.'
                    : 'Khi app đăng video lên TikTok, lượt xem và tương tác sẽ hiện ở đây. Thử chọn 30 ngày hoặc xem lịch đăng sắp tới.'
            "
            data-testid="fork-so-lieu-empty"
        >
            <Button
                v-if="hasFilter"
                size="sm"
                variant="outline"
                @click="clearFilters"
                ><IconFilterOff class="size-4" /> Xoá bộ lọc</Button
            >
            <Button
                v-else-if="filters.range !== '30d'"
                size="sm"
                variant="outline"
                @click="apply({ range: '30d' })"
                >Xem 30 ngày</Button
            >
            <Button as-child size="sm">
                <Link href="/auto">Xem lịch đăng →</Link>
            </Button>
        </EmptyState>

        <template v-else>
            <Callout
                v-if="videos_total > 0 && metrics_count === 0 && !loading"
                tone="info"
            >
                Có {{ videos_total }} bài đã đăng nhưng chưa có số liệu. Tiện
                ích Chrome tự thu mỗi giờ (cần mở Chrome đã đăng nhập TikTok);
                số liệu hiện ra sau lần thu đầu tiên.
            </Callout>

            <!-- Chỉ số -->
            <section
                :class="cn(cardCls, 'overflow-hidden')"
                data-testid="fork-so-lieu-kpis"
            >
                <div
                    class="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-4"
                >
                    <div
                        v-for="t in primary"
                        :key="t.key"
                        class="relative flex flex-col gap-1 bg-card p-5 sm:p-6"
                        :data-testid="`fork-so-lieu-kpi-${t.key}`"
                        :title="t.hint"
                    >
                        <span
                            class="text-[12px] font-medium tracking-[0.02em] text-muted-foreground uppercase"
                            >{{ t.label }}</span
                        >
                        <Skeleton v-if="loading" class="mt-1 h-8 w-28" />
                        <span
                            v-else
                            class="font-heading text-[30px] leading-tight font-[650] tracking-[-0.03em] tabular-nums"
                            >{{ t.format(kpis[t.key].value) }}</span
                        >
                        <span
                            :class="
                                cn(
                                    'flex items-center gap-1 text-[12.5px] tabular-nums',
                                    deltaCls(kpis[t.key]),
                                )
                            "
                        >
                            <template v-if="kpis[t.key].delta_pct !== null">
                                <component
                                    :is="
                                        kpis[t.key].delta_pct! >= 0
                                            ? IconArrowUpRight
                                            : IconArrowDownRight
                                    "
                                    class="size-3.5"
                                />
                                {{ deltaText(kpis[t.key]) }}
                                <span class="text-muted-foreground"
                                    >so với kỳ trước</span
                                >
                            </template>
                            <span v-else class="text-muted-foreground"
                                >Chưa có kỳ trước để so</span
                            >
                        </span>
                        <svg
                            v-if="t.key === 'views' && spark && !loading"
                            viewBox="0 0 100 28"
                            preserveAspectRatio="none"
                            class="pointer-events-none absolute right-5 bottom-5 h-9 w-[38%] text-primary"
                            aria-hidden="true"
                        >
                            <polygon
                                :points="spark.area"
                                class="fill-current opacity-10"
                            />
                            <polyline
                                :points="spark.line"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="1.6"
                                vector-effect="non-scaling-stroke"
                            />
                        </svg>
                    </div>
                </div>
                <div
                    class="grid grid-cols-2 border-t bg-muted/30 sm:grid-cols-3 xl:grid-cols-6"
                >
                    <div
                        v-for="t in secondary"
                        :key="t.key"
                        class="flex flex-col gap-0.5 px-5 py-3.5"
                        :data-testid="`fork-so-lieu-kpi-${t.key}`"
                    >
                        <span
                            class="truncate text-[12px] text-muted-foreground"
                            >{{ t.label }}</span
                        >
                        <span class="flex items-baseline gap-2">
                            <span
                                class="text-[17px] font-semibold tabular-nums"
                                >{{ t.format(kpis[t.key].value) }}</span
                            >
                            <span
                                v-if="kpis[t.key].delta_pct !== null"
                                :class="
                                    cn(
                                        'text-[12px] tabular-nums',
                                        deltaCls(kpis[t.key]),
                                    )
                                "
                                >{{ kpis[t.key].delta_pct! >= 0 ? '+' : '−'
                                }}{{ deltaText(kpis[t.key]) }}</span
                            >
                        </span>
                    </div>
                </div>
            </section>

            <!-- Lượt xem theo ngày + người theo dõi -->
            <div
                class="grid items-stretch gap-6 xl:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_400px]"
            >
                <section :class="cn(cardCls, 'flex flex-col gap-4 p-5')">
                    <header
                        class="flex flex-wrap items-start justify-between gap-2"
                    >
                        <div>
                            <h2 :class="h2">Lượt xem theo ngày</h2>
                            <p class="text-[12.5px] text-muted-foreground">
                                Tổng lượt xem của các bài đăng trong ngày đó (số
                                liệu mới nhất).
                            </p>
                        </div>
                        <div
                            v-if="bestDay"
                            class="text-right text-[12.5px] text-muted-foreground"
                        >
                            Ngày tốt nhất
                            <div
                                class="font-medium text-foreground tabular-nums"
                            >
                                {{ dayjs(bestDay.date).format('DD/MM') }} ·
                                {{ fmtNum(bestDay.views) }} lượt xem
                            </div>
                        </div>
                    </header>
                    <Skeleton v-if="loading" class="h-48 w-full" />
                    <BarChart
                        v-else
                        :points="dailyPoints"
                        unit="lượt xem"
                        height="h-48"
                    />
                </section>

                <section
                    :class="cn(cardCls, 'flex flex-col gap-3 p-5')"
                    data-testid="fork-so-lieu-followers"
                >
                    <h2 :class="h2">Người theo dõi</h2>
                    <template v-if="followers">
                        <div class="flex items-baseline gap-3">
                            <span
                                class="font-heading text-[30px] leading-none font-[650] tracking-[-0.03em] tabular-nums"
                                >{{ fmtNum(followers.current) }}</span
                            >
                            <span
                                v-if="followers.change !== null"
                                :class="
                                    cn(
                                        'text-[13px] font-medium tabular-nums',
                                        followers.change >= 0
                                            ? toneClasses.success.text
                                            : toneClasses.danger.text,
                                    )
                                "
                                >{{ followers.change >= 0 ? '+' : ''
                                }}{{ fmtNum(followers.change) }} trong kỳ</span
                            >
                        </div>
                        <BarChart
                            v-if="followers.series.length > 1"
                            :points="followerPoints"
                            unit="người theo dõi mới"
                            height="h-32"
                            class="mt-auto"
                        />
                        <p
                            v-else
                            class="mt-auto text-[12.5px] text-muted-foreground"
                        >
                            Mới có một ngày số liệu — biểu đồ hiện khi có thêm
                            ngày.
                        </p>
                    </template>
                    <p v-else class="text-[13px] text-muted-foreground">
                        Chưa có số liệu người theo dõi. Tiện ích đọc từ TikTok
                        Studio mỗi giờ.
                    </p>
                </section>
            </div>

            <!-- So sánh + top video -->
            <div
                class="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
            >
                <Skeleton v-if="loading" class="h-72 w-full rounded-[14px]" />
                <BreakdownCard v-else :breakdowns="breakdowns" />

                <section
                    v-if="top.length"
                    :class="cn(cardCls, 'flex flex-col overflow-hidden')"
                    data-testid="fork-so-lieu-ranking"
                >
                    <header
                        class="flex items-center justify-between gap-3 border-b px-5 py-4"
                    >
                        <h2 :class="h2">Video nổi bật</h2>
                        <div
                            class="flex gap-0.5 rounded-lg bg-muted p-0.5 text-[12.5px]"
                        >
                            <button
                                v-for="m in [
                                    { k: 'top', t: 'Nhiều view nhất' },
                                    { k: 'bottom', t: 'Ít view nhất' },
                                ] as const"
                                :key="m.k"
                                type="button"
                                :class="
                                    cn(
                                        'rounded-md px-2.5 py-1 font-medium transition',
                                        rankMode === m.k
                                            ? 'bg-card text-foreground shadow-xs'
                                            : 'text-muted-foreground hover:text-foreground',
                                    )
                                "
                                @click="rankMode = m.k"
                            >
                                {{ m.t }}
                            </button>
                        </div>
                    </header>
                    <ol class="flex flex-col p-2">
                        <li v-for="(v, i) in rankList" :key="v.id">
                            <button
                                type="button"
                                class="grid w-full grid-cols-[20px_32px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-accent/50 focus-visible:outline-2 focus-visible:outline-ring"
                                @click="
                                    openVideo(
                                        rankList.map((x) => x.id),
                                        v.id,
                                    )
                                "
                            >
                                <span
                                    class="text-center text-[13px] font-semibold text-muted-foreground tabular-nums"
                                    >{{ i + 1 }}</span
                                >
                                <CoverThumb
                                    :id="v.id"
                                    :fallback="v.product_image"
                                    class="h-14 w-8 rounded-md"
                                />
                                <span class="min-w-0">
                                    <span
                                        class="block truncate text-[13.5px] font-medium"
                                        >{{ productName(v.product_code) }}</span
                                    >
                                    <span
                                        class="block truncate text-[12px] text-muted-foreground"
                                        >{{
                                            dayjs(v.posted_at).format(
                                                'HH:mm DD/MM',
                                            )
                                        }}<template v-if="v.channel">
                                            · {{ v.channel }}</template
                                        ></span
                                    >
                                    <span
                                        class="mt-1 block h-1 overflow-hidden rounded-full bg-muted"
                                    >
                                        <span
                                            :class="
                                                cn(
                                                    'block h-full rounded-full',
                                                    rankMode === 'top'
                                                        ? 'bg-primary'
                                                        : 'bg-muted-foreground/40',
                                                )
                                            "
                                            :style="{
                                                width: `${Math.max(2, (v.views / rankMax) * 100)}%`,
                                            }"
                                        />
                                    </span>
                                </span>
                                <span class="flex items-center gap-2">
                                    <span
                                        class="text-[14px] font-semibold tabular-nums"
                                        >{{ fmtCompact(v.views) }}</span
                                    >
                                    <a
                                        v-if="v.link"
                                        :href="v.link"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        class="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
                                        title="Mở trên TikTok"
                                        aria-label="Mở trên TikTok"
                                        @click.stop
                                        ><IconExternalLink class="size-4"
                                    /></a>
                                </span>
                            </button>
                        </li>
                    </ol>
                </section>
            </div>

            <!-- Bình luận -->
            <section
                :class="cn(cardCls, 'flex flex-col overflow-hidden')"
                data-testid="fork-so-lieu-comments"
            >
                <header
                    class="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4"
                >
                    <div>
                        <h2 :class="h2">Bình luận</h2>
                        <p class="text-[12.5px] text-muted-foreground">
                            {{ fmtNum(comments.counts.total) }} bình luận đã thu
                            · {{ fmtNum(comments.counts.buy) }} hỏi mua / hỏi
                            giá ({{ comments.counts.buy_24h }}
                            trong 24 giờ qua)
                        </p>
                    </div>
                    <div class="flex gap-0.5 rounded-lg bg-muted p-1">
                        <button
                            v-for="o in [
                                { k: 'all', t: 'Tất cả' },
                                { k: 'mua', t: 'Hỏi mua' },
                            ] as const"
                            :key="o.k"
                            type="button"
                            :class="seg(filters.cm === o.k)"
                            @click="setComments(o.k)"
                        >
                            {{ o.t }}
                            <span
                                v-if="o.k === 'mua' && comments.counts.buy_24h"
                                class="rounded-full bg-amber-500 px-1.5 text-[11.5px] leading-5 font-semibold text-amber-950"
                                >{{ comments.counts.buy_24h }}</span
                            >
                        </button>
                    </div>
                </header>

                <p
                    v-if="!comments.rows.length"
                    class="px-5 py-10 text-center text-[13px] text-muted-foreground"
                >
                    {{
                        filters.cm === 'mua'
                            ? 'Chưa có bình luận hỏi mua nào.'
                            : 'Chưa thu được bình luận nào. Tiện ích thu bình luận mới mỗi giờ.'
                    }}
                </p>
                <ul v-else class="grid divide-y xl:grid-cols-2 xl:divide-y-0">
                    <li
                        v-for="(c, i) in comments.rows"
                        :key="c.id"
                        :class="
                            cn(
                                'flex gap-3 px-5 py-3.5 text-[13.5px]',
                                'xl:border-b',
                                i % 2 === 0 && 'xl:border-r',
                                c.buy && 'bg-amber-50/60 dark:bg-amber-950/15',
                            )
                        "
                        :data-testid="`fork-so-lieu-comment-${c.id}`"
                    >
                        <span
                            class="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-[12.5px] font-semibold text-muted-foreground"
                            aria-hidden="true"
                            >{{
                                [
                                    ...(c.author || c.handle || '?'),
                                ][0]?.toUpperCase()
                            }}</span
                        >
                        <div class="min-w-0 flex-1">
                            <div
                                class="flex flex-wrap items-center gap-x-2 gap-y-0.5"
                            >
                                <span class="font-medium">{{
                                    c.author || c.handle || 'Ẩn danh'
                                }}</span>
                                <span
                                    v-if="c.buy"
                                    :class="
                                        cn(
                                            'rounded-full px-2 text-[11.5px] leading-5 font-medium',
                                            toneClasses.warn.chip,
                                        )
                                    "
                                    :title="c.keywords ?? ''"
                                    >Hỏi mua</span
                                >
                                <span class="text-[12px] text-muted-foreground"
                                    >{{
                                        c.at
                                            ? dayjs(c.at).format('HH:mm DD/MM')
                                            : ''
                                    }}<template v-if="c.channel">
                                        · {{ c.channel }}</template
                                    ></span
                                >
                            </div>
                            <p class="mt-0.5 break-words whitespace-pre-line">
                                {{ c.text }}
                            </p>
                            <div
                                class="mt-1 flex flex-wrap items-center gap-x-3 text-[12px] text-muted-foreground"
                            >
                                <button
                                    v-if="c.video_id"
                                    type="button"
                                    class="truncate hover:text-foreground hover:underline"
                                    @click="openVideo([c.video_id], c.video_id)"
                                >
                                    {{
                                        c.video_label
                                            ? `Video: ${c.video_label}`
                                            : 'Xem video'
                                    }}
                                </button>
                                <span v-else-if="c.video_label" class="truncate"
                                    >Video: {{ c.video_label }}</span
                                >
                                <a
                                    v-if="c.link"
                                    :href="c.link"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="inline-flex items-center gap-1 font-medium text-primary-text hover:underline"
                                    >Trả lời trên TikTok
                                    <IconExternalLink class="size-3.5"
                                /></a>
                                <span class="ml-auto tabular-nums"
                                    >{{ c.likes }} tim · {{ c.replies }} trả
                                    lời</span
                                >
                            </div>
                        </div>
                    </li>
                </ul>
            </section>

            <!-- Video đã đăng -->
            <section
                :class="cn(cardCls, 'flex flex-col overflow-hidden')"
                data-testid="fork-so-lieu-videos"
            >
                <header
                    class="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4"
                >
                    <div>
                        <h2 :class="h2">Video đã đăng</h2>
                        <p class="text-[12.5px] text-muted-foreground">
                            {{
                                videos_total > videos.length
                                    ? `Hiển thị ${videos.length} / ${videos_total} video trong khoảng đã chọn.`
                                    : `${videos_total} video trong khoảng đã chọn.`
                            }}
                        </p>
                    </div>
                    <NativeSelect
                        :model-value="filters.sort"
                        class="h-9"
                        aria-label="Sắp xếp"
                        @update:model-value="
                            apply({ sort: String($event) as Filters['sort'] })
                        "
                    >
                        <option v-for="s in sorts" :key="s.key" :value="s.key">
                            {{ s.label }}
                        </option>
                    </NativeSelect>
                </header>
                <div
                    class="hidden border-b bg-muted/40 px-5 py-2 text-[11.5px] font-medium tracking-[0.04em] text-muted-foreground uppercase lg:grid lg:grid-cols-[36px_minmax(0,1.7fr)_minmax(120px,1fr)_repeat(3,60px)_84px_96px_28px] lg:gap-x-4"
                    aria-hidden="true"
                >
                    <span />
                    <span>Video</span>
                    <span>Lượt xem</span>
                    <span class="text-right">Tim</span>
                    <span class="text-right">B.luận</span>
                    <span class="text-right">Chia sẻ</span>
                    <span class="text-right">Tương tác</span>
                    <span class="text-right">Sau 24h/72h</span>
                    <span />
                </div>
                <div v-if="loading" class="flex flex-col divide-y">
                    <div
                        v-for="i in 5"
                        :key="i"
                        class="flex items-center gap-4 px-5 py-3"
                    >
                        <Skeleton class="h-16 w-9" />
                        <Skeleton class="h-4 flex-1" />
                    </div>
                </div>
                <ul v-else class="flex flex-col divide-y">
                    <VideoStatRow
                        v-for="v in videos"
                        :key="v.id"
                        :video="v"
                        :product-name="productName(v.product_code)"
                        :ids="videos.map((x) => x.id)"
                        :max-views="maxViews"
                    />
                </ul>
            </section>
        </template>
    </AutoShell>
</template>

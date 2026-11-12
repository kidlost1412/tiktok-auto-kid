<script setup lang="ts">
// Trang "Số liệu": hiệu quả các video đã đăng - lượt xem, tương tác, so sánh theo sản phẩm / góc / giờ / giọng / nhạc.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en).
import { Link, router } from '@inertiajs/vue3';
import {
    IconArrowDownRight,
    IconArrowUpRight,
    IconChartBar,
    IconFilterOff,
    IconExternalLink,
    IconMessageCircle,
    IconMinus,
} from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { fmtNum, toneClasses } from '@/components/fork/shared/status';
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
import VideoThumb from '@/components/fork/VideoThumb.vue';
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

const tiles: {
    key: KpiKey;
    label: string;
    format: (n: number) => string;
}[] = [
    { key: 'posts', label: 'Bài đăng', format: fmtNum },
    { key: 'views', label: 'Tổng lượt xem', format: fmtNum },
    {
        key: 'avg_views',
        label: 'View TB / bài',
        format: (n) => fmtNum(Math.round(n)),
    },
    { key: 'likes', label: 'Tim', format: fmtNum },
    { key: 'comments', label: 'Bình luận', format: fmtNum },
    { key: 'shares', label: 'Chia sẻ', format: fmtNum },
    { key: 'saves', label: 'Lưu', format: fmtNum },
    {
        key: 'avg_watch_s',
        label: 'Xem TB (video ≤ 7 ngày)',
        format: (n) => (n > 0 ? `${n.toLocaleString('vi-VN')} giây` : '—'),
    },
    {
        key: 'finish_rate',
        label: 'Xem hết (video ≤ 7 ngày)',
        format: (n) => (n > 0 ? `${n.toLocaleString('vi-VN')}%` : '—'),
    },
    {
        key: 'engagement',
        label: 'Tỉ lệ tương tác',
        format: (n) => `${n.toLocaleString('vi-VN')}%`,
    },
];

const deltaTone = (k: Kpi) =>
    k.delta_pct === null || k.delta_pct === 0
        ? 'text-muted-foreground'
        : k.delta_pct > 0
          ? toneClasses.success.text
          : toneClasses.danger.text;

const dailyPoints = computed<BarPoint[]>(() => {
    const n = props.daily.length;
    const every = n > 60 ? 10 : n > 20 ? 5 : n > 10 ? 2 : 1;

    return props.daily.map((d, i) => ({
        key: d.date,
        axis: i % every === 0 ? dayjs(d.date).format('DD/MM') : '',
        title: dayjs(d.date).format('DD/MM/YYYY'),
        value: d.views,
        sub: `${d.posts} bài đăng`,
    }));
});

const followerPoints = computed<BarPoint[]>(() => {
    const series = props.followers?.series ?? [];
    const n = series.length;
    const every = n > 60 ? 10 : n > 20 ? 5 : n > 10 ? 2 : 1;

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
        ? `Cập nhật lúc ${dayjs(props.collected_at).format('HH:mm DD/MM')}`
        : 'Chưa thu số liệu lần nào',
);

const setComments = (cm: Filters['cm']) => apply({ cm });

const sorts = [
    { key: 'moi', label: 'Mới nhất' },
    { key: 'view', label: 'Nhiều view nhất' },
    { key: 'tuong-tac', label: 'Tương tác nhiều nhất' },
] as const;
</script>

<template>
    <AutoShell
        title="Số liệu"
        :description="`Hiệu quả các video đã đăng, ${rangeText}. Số liệu do tiện ích Chrome đọc từ TikTok Studio. ${collectedText}.`"
        testid="fork-so-lieu-page"
    >
        <Callout
            v-if="extension.outdated"
            tone="warn"
            data-testid="fork-so-lieu-extension-banner"
        >
            <b>Tải lại tiện ích để thu số liệu.</b>
            Chrome đang chạy tiện ích bản
            {{ extension.version || 'cũ' }}, chưa thu được số liệu và bình
            luận (cần từ bản {{ extension.min }}). Mở chrome://extensions, bấm
            ⟳ ở tiện ích TikTok Auto Kid (nạp từ thư mục
            <code>extension\autotok</code> của app) rồi mở lại Chrome profile
            đó.
        </Callout>

        <!-- Thanh lọc -->
        <section
            class="sticky top-0 z-20 -mx-4 flex flex-col gap-3 border-b bg-card/90 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-card/75 sm:-mx-6 sm:px-6"
            data-testid="fork-so-lieu-filters"
        >
            <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
                <div class="flex rounded-lg bg-muted p-0.5" role="tablist">
                    <button
                        v-for="r in ranges"
                        :key="r.key"
                        type="button"
                        role="tab"
                        :aria-selected="filters.range === r.key"
                        :class="
                            cn(
                                'rounded-md px-3 py-1 text-sm font-medium transition',
                                filters.range === r.key
                                    ? 'bg-card text-foreground shadow-xs'
                                    : 'text-muted-foreground hover:text-foreground',
                            )
                        "
                        @click="pickRange(r.key)"
                    >
                        {{ r.label }}
                    </button>
                </div>

                <div
                    v-if="customOpen"
                    class="flex flex-wrap items-center gap-2"
                >
                    <Input
                        v-model="customFrom"
                        type="date"
                        class="h-8 w-36"
                        aria-label="Từ ngày"
                    />
                    <span class="text-sm text-muted-foreground">đến</span>
                    <Input
                        v-model="customTo"
                        type="date"
                        class="h-8 w-36"
                        aria-label="Đến ngày"
                    />
                    <Button size="sm" @click="applyCustom">Áp dụng</Button>
                </div>

                <div class="ml-auto flex flex-wrap items-center gap-2">
                    <NativeSelect
                        :model-value="filters.channel"
                        aria-label="Kênh"
                        @update:model-value="apply({ channel: String($event) })"
                    >
                        <option value="">Mọi kênh</option>
                        <option
                            v-for="c in options.channels"
                            :key="c.id"
                            :value="c.id"
                        >
                            {{ c.name }}
                        </option>
                    </NativeSelect>
                    <NativeSelect
                        :model-value="filters.product"
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
                        size="sm"
                        variant="ghost"
                        @click="clearFilters"
                    >
                        <IconFilterOff class="size-4" />
                        Xoá lọc
                    </Button>
                </div>
            </div>
        </section>

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
            >
                <IconFilterOff class="size-4" /> Xoá bộ lọc
            </Button>
            <Button
                v-else-if="filters.range !== '30d'"
                size="sm"
                variant="outline"
                @click="apply({ range: '30d' })"
            >
                Xem 30 ngày
            </Button>
            <Button as-child size="sm">
                <Link href="/auto">Xem lịch đăng →</Link>
            </Button>
        </EmptyState>

        <template v-else>
            <Callout
                v-if="videos_total > 0 && metrics_count === 0 && !loading"
                tone="info"
            >
                Có {{ videos_total }} bài đã đăng nhưng chưa có số liệu.
                Tiện ích Chrome tự thu mỗi giờ (cần mở Chrome đã đăng nhập
                TikTok); số liệu hiện ra sau lần thu đầu tiên.
            </Callout>

            <!-- KPI -->
            <section
                class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-5"
                data-testid="fork-so-lieu-kpis"
            >
                <template v-if="loading">
                    <Skeleton v-for="i in 10" :key="i" class="h-24 rounded-xl" />
                </template>
                <template v-else>
                    <div
                        v-for="t in tiles"
                        :key="t.key"
                        class="flex flex-col gap-1 rounded-xl border bg-card p-3.5 shadow-xs"
                        :data-testid="`fork-so-lieu-kpi-${t.key}`"
                    >
                        <span class="text-xs text-muted-foreground">{{
                            t.label
                        }}</span>
                        <span
                            class="text-2xl font-semibold tracking-tight tabular-nums"
                            >{{ t.format(kpis[t.key].value) }}</span
                        >
                        <span
                            :class="
                                cn(
                                    'flex items-center gap-1 text-xs tabular-nums',
                                    deltaTone(kpis[t.key]),
                                )
                            "
                        >
                            <template v-if="kpis[t.key].delta_pct === null">
                                <IconMinus class="size-3.5" />
                                <span class="text-muted-foreground"
                                    >Chưa có kỳ trước</span
                                >
                            </template>
                            <template v-else>
                                <component
                                    :is="
                                        kpis[t.key].delta_pct! >= 0
                                            ? IconArrowUpRight
                                            : IconArrowDownRight
                                    "
                                    class="size-3.5"
                                />
                                {{
                                    Math.abs(
                                        kpis[t.key].delta_pct!,
                                    ).toLocaleString('vi-VN')
                                }}%
                                <span class="text-muted-foreground"
                                    >so với kỳ trước</span
                                >
                            </template>
                        </span>
                    </div>
                </template>
            </section>

            <!-- Người theo dõi -->
            <section
                v-if="followers"
                class="flex flex-col gap-3"
                data-testid="fork-so-lieu-followers"
            >
                <SectionHeading
                    title="Người theo dõi"
                    :description="
                        followers.change === null
                            ? 'Mới có một ngày số liệu, biểu đồ sẽ hiện khi có thêm ngày.'
                            : 'Số người theo dõi mới mỗi ngày trong khoảng đã chọn.'
                    "
                />
                <div
                    class="flex flex-col gap-4 rounded-xl border bg-card p-4 shadow-xs"
                >
                    <div class="flex items-baseline gap-3">
                        <span class="text-3xl font-semibold tabular-nums">{{
                            fmtNum(followers.current)
                        }}</span>
                        <span
                            v-if="followers.change !== null"
                            :class="
                                cn(
                                    'text-sm tabular-nums',
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
                    />
                </div>
            </section>

            <!-- Lượt xem theo ngày -->
            <section class="flex flex-col gap-3">
                <SectionHeading
                    title="Lượt xem theo ngày"
                    description="Tổng lượt xem của các bài đăng trong ngày đó (số liệu mới nhất)."
                />
                <div class="rounded-xl border bg-card p-4 shadow-xs">
                    <Skeleton v-if="loading" class="h-44 w-full" />
                    <BarChart v-else :points="dailyPoints" unit="lượt xem" />
                </div>
            </section>

            <!-- So sánh -->
            <section class="flex flex-col gap-3">
                <SectionHeading
                    title="So sánh hiệu quả"
                    description="Chiều nào cho view TB mỗi bài cao hơn thì nên làm nhiều hơn."
                />
                <Skeleton v-if="loading" class="h-72 w-full rounded-xl" />
                <BreakdownCard v-else :breakdowns="breakdowns" />
            </section>

            <!-- Top / bottom -->
            <section
                v-if="top.length"
                class="grid gap-6 md:grid-cols-2"
                data-testid="fork-so-lieu-ranking"
            >
                <div
                    v-for="block in [
                        {
                            title: 'Top 5 video nhiều view nhất',
                            list: top,
                            tone: 'success',
                        },
                        {
                            title: '5 video ít view nhất',
                            list: bottom,
                            tone: 'danger',
                        },
                    ] as const"
                    v-show="block.list.length"
                    :key="block.title"
                    class="flex flex-col gap-3"
                >
                    <SectionHeading :title="block.title" />
                    <ol class="flex flex-col gap-2">
                        <li
                            v-for="(v, i) in block.list"
                            :key="v.id"
                            class="flex cursor-pointer items-center gap-3 rounded-xl border bg-card p-2.5 shadow-xs transition hover:border-foreground/25"
                            tabindex="0"
                            @click="
                                openVideo(
                                    block.list.map((x) => x.id),
                                    v.id,
                                )
                            "
                            @keydown.enter.self.prevent="
                                openVideo(
                                    block.list.map((x) => x.id),
                                    v.id,
                                )
                            "
                        >
                            <span
                                :class="
                                    cn(
                                        'flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
                                        toneClasses[block.tone].chip,
                                    )
                                "
                                >{{ i + 1 }}</span
                            >
                            <VideoThumb
                                :id="v.id"
                                class="h-14 w-8 rounded-md"
                            />
                            <div class="min-w-0 flex-1 text-sm">
                                <div
                                    class="flex items-center gap-1.5 truncate font-medium"
                                >
                                    <ProductThumb
                                        :src="v.product_image"
                                        class="size-5"
                                    />
                                    {{ productName(v.product_code) }}
                                </div>
                                <div
                                    class="truncate text-xs text-muted-foreground"
                                >
                                    {{ v.channel }} ·
                                    {{
                                        dayjs(v.posted_at).format('HH:mm DD/MM')
                                    }}
                                </div>
                            </div>
                            <div class="shrink-0 text-right">
                                <div class="font-semibold tabular-nums">
                                    {{ fmtNum(v.views) }}
                                </div>
                                <a
                                    v-if="v.link"
                                    :href="v.link"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="text-xs text-primary hover:underline"
                                    @click.stop
                                    >TikTok</a
                                >
                            </div>
                        </li>
                    </ol>
                </div>
            </section>

            <!-- Bình luận -->
            <section
                class="flex flex-col gap-3"
                data-testid="fork-so-lieu-comments"
            >
                <SectionHeading
                    title="Bình luận"
                    :description="`${comments.counts.total} bình luận đã thu, ${comments.counts.buy} hỏi mua / hỏi giá (${comments.counts.buy_24h} trong 24 giờ qua).`"
                >
                    <div class="flex rounded-lg bg-muted p-0.5">
                        <button
                            v-for="o in [
                                { k: 'all', t: 'Tất cả' },
                                { k: 'mua', t: 'Hỏi mua' },
                            ] as const"
                            :key="o.k"
                            type="button"
                            :class="
                                cn(
                                    'inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-sm font-medium transition',
                                    filters.cm === o.k
                                        ? 'bg-card text-foreground shadow-xs'
                                        : 'text-muted-foreground hover:text-foreground',
                                )
                            "
                            @click="setComments(o.k)"
                        >
                            {{ o.t }}
                            <span
                                v-if="o.k === 'mua' && comments.counts.buy_24h"
                                class="rounded-full bg-amber-500 px-1.5 text-[0.75rem] leading-5 font-semibold text-white"
                                >{{ comments.counts.buy_24h }}</span
                            >
                        </button>
                    </div>
                </SectionHeading>

                <p
                    v-if="!comments.rows.length"
                    class="rounded-xl border bg-card p-4 text-sm text-muted-foreground"
                >
                    {{
                        filters.cm === 'mua'
                            ? 'Chưa có bình luận hỏi mua nào.'
                            : 'Chưa thu được bình luận nào. Tiện ích thu bình luận mới mỗi giờ.'
                    }}
                </p>
                <ul v-else class="flex flex-col gap-2">
                    <li
                        v-for="c in comments.rows"
                        :key="c.id"
                        :class="
                            cn(
                                'flex flex-col gap-1 rounded-xl border bg-card p-3 text-sm shadow-xs',
                                c.buy && 'border-amber-300 dark:border-amber-800',
                            )
                        "
                        :data-testid="`fork-so-lieu-comment-${c.id}`"
                    >
                        <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                            <IconMessageCircle
                                class="size-4 text-muted-foreground"
                            />
                            <span class="font-medium">{{
                                c.author || c.handle || 'Ẩn danh'
                            }}</span>
                            <span
                                v-if="c.buy"
                                class="rounded-full bg-amber-100 px-2 py-0.5 text-[0.75rem] font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                                :title="c.keywords ?? ''"
                                >Hỏi mua</span
                            >
                            <span class="text-xs text-muted-foreground">{{
                                c.at ? dayjs(c.at).format('HH:mm DD/MM') : ''
                            }}</span>
                            <span
                                v-if="c.channel"
                                class="text-xs text-muted-foreground"
                                >· {{ c.channel }}</span
                            >
                        </div>
                        <p class="whitespace-pre-line break-words">
                            {{ c.text }}
                        </p>
                        <div
                            class="flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground"
                        >
                            <span v-if="c.video_label"
                                >Video: {{ c.video_label }}</span
                            >
                            <button
                                v-if="c.video_id"
                                type="button"
                                class="text-primary hover:underline"
                                @click="openVideo([c.video_id], c.video_id)"
                            >
                                Xem video
                            </button>
                            <a
                                v-if="c.link"
                                :href="c.link"
                                target="_blank"
                                rel="noopener noreferrer"
                                class="inline-flex items-center gap-1 text-primary hover:underline"
                                >Mở trên TikTok
                                <IconExternalLink class="size-3.5"
                            /></a>
                            <span class="ml-auto tabular-nums"
                                >{{ c.likes }} tim · {{ c.replies }} trả lời</span
                            >
                        </div>
                    </li>
                </ul>
            </section>

            <!-- Video vừa đăng -->
            <section
                class="flex flex-col gap-3"
                data-testid="fork-so-lieu-videos"
            >
                <SectionHeading
                    title="Video đã đăng"
                    :description="
                        videos_total > videos.length
                            ? `Hiển thị ${videos.length} / ${videos_total} video trong khoảng đã chọn.`
                            : `${videos_total} video trong khoảng đã chọn.`
                    "
                >
                    <NativeSelect
                        :model-value="filters.sort"
                        aria-label="Sắp xếp"
                        @update:model-value="
                            apply({ sort: String($event) as Filters['sort'] })
                        "
                    >
                        <option v-for="s in sorts" :key="s.key" :value="s.key">
                            {{ s.label }}
                        </option>
                    </NativeSelect>
                </SectionHeading>

                <ul v-if="loading" class="flex flex-col gap-3">
                    <Skeleton v-for="i in 4" :key="i" class="h-28 rounded-xl" />
                </ul>
                <ul v-else class="flex flex-col gap-3">
                    <VideoStatRow
                        v-for="v in videos"
                        :key="v.id"
                        :video="v"
                        :product-name="productName(v.product_code)"
                        :ids="videos.map((x) => x.id)"
                    />
                </ul>
            </section>
        </template>
    </AutoShell>
</template>

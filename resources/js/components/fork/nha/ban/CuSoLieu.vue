<script setup lang="ts">
// Nội dung bàn Cú cho MỘT khoảng ngày: đọc /auto/so-lieu?range=…&cm=mua (chỉ bình luận hỏi mua).
// KPI, biểu đồ lượt xem theo ngày, video nổi bật, bình luận hỏi mua. Đổi khoảng ngày: địa chỉ đổi theo `range`, tự tải lại.
import {
    IconArrowDownRight,
    IconArrowUpRight,
    IconExternalLink,
    IconRefresh,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted } from 'vue';

import { banBao } from '@/components/fork/nha/ban/bus';
import { useInertiaProps } from '@/components/fork/nha/ban/useInertiaProps';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import {
    cardCls,
    fmtCompact,
    fmtNum,
    toneClasses,
} from '@/components/fork/shared/status';
import BarChart from '@/components/fork/so-lieu/BarChart.vue';
import type {
    BarPoint,
    CommentsData,
    DailyPoint,
    Filters,
    Kpi,
    KpiKey,
    Options,
    StatVideo,
} from '@/components/fork/so-lieu/types';
import { openVideo } from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

type Range = 'today' | '7d' | '30d';

const props = defineProps<{ range: Range }>();
const emit = defineEmits<{ range: [r: Range] }>();

type SoLieuProps = {
    filters: Filters;
    options: Options;
    kpis: Record<KpiKey, Kpi>;
    daily: DailyPoint[];
    top: StatVideo[];
    collected_at: string | null;
    comments: CommentsData;
};

const {
    props: p,
    error,
    reload,
} = useInertiaProps<SoLieuProps>(
    () => `/auto/so-lieu?range=${props.range}&cm=mua`,
    'fork/SoLieu',
    ['filters', 'options', 'kpis', 'daily', 'top', 'collected_at', 'comments'],
);

let poll: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
    reload();
    poll = setInterval(() => {
        if (document.visibilityState === 'visible') {
            reload();
        }
    }, 60000);
});
onBeforeUnmount(() => clearInterval(poll));

const ranges: { key: Range; label: string }[] = [
    { key: 'today', label: 'Hôm nay' },
    { key: '7d', label: '7 ngày' },
    { key: '30d', label: '30 ngày' },
];

const pick = (r: Range) => {
    if (r !== props.range) {
        emit('range', r);
        banBao('cu', 'xem');
    }
};

const productName = (code: string | null) =>
    p.value?.options.products.find((x) => x.code === code)?.name ?? code ?? '—';

const tiles = computed(() => {
    const k = p.value?.kpis;

    if (!k) {
        return [];
    }

    return [
        {
            key: 'views' as const,
            label: 'Lượt xem',
            value: fmtNum(k.views.value),
            kpi: k.views,
        },
        {
            key: 'posts' as const,
            label: 'Bài đã đăng',
            value: fmtNum(k.posts.value),
            kpi: k.posts,
        },
        {
            key: 'avg_views' as const,
            label: 'View trung bình',
            value: fmtNum(Math.round(k.avg_views.value)),
            kpi: k.avg_views,
        },
        {
            key: 'engagement' as const,
            label: 'Tương tác',
            value: `${k.engagement.value.toLocaleString('vi-VN')}%`,
            kpi: k.engagement,
        },
    ];
});

const deltaCls = (k: Kpi) =>
    k.delta_pct === null || k.delta_pct === 0
        ? 'text-muted-foreground'
        : k.delta_pct > 0
          ? toneClasses.success.text
          : toneClasses.danger.text;

// Đường nhỏ cạnh ô "Lượt xem".
const spark = computed(() => {
    const v = (p.value?.daily ?? []).map((d) => d.views);

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
    const daily = p.value?.daily ?? [];
    const every = axisEvery(daily.length);

    return daily.map((d, i) => ({
        key: d.date,
        axis: i % every === 0 ? dayjs(d.date).format('DD/MM') : '',
        title: dayjs(d.date).format('DD/MM/YYYY'),
        value: d.views,
        sub: `${d.posts} bài đăng`,
    }));
});

const bestDay = computed(() =>
    (p.value?.daily ?? []).reduce<DailyPoint | null>(
        (b, d) => (d.views > (b?.views ?? 0) ? d : b),
        null,
    ),
);

const top = computed(() => (p.value?.top ?? []).slice(0, 5));
const topMax = computed(() => Math.max(1, ...top.value.map((v) => v.views)));
const comments = computed(() => p.value?.comments.rows.slice(0, 12) ?? []);

const rangeText = computed(() => {
    const f = p.value?.filters;

    if (!f) {
        return '';
    }

    const a = dayjs(f.from).format('DD/MM');
    const b = dayjs(f.to).format('DD/MM');

    return a === b ? a : `${a} – ${b}`;
});

const collectedText = computed(() =>
    p.value?.collected_at
        ? `cập nhật ${dayjs(p.value.collected_at).format('HH:mm DD/MM')}`
        : 'chưa thu số liệu lần nào',
);

const labelCls =
    'text-xs font-medium tracking-[0.02em] text-muted-foreground uppercase';
const h2 = 'font-heading text-base font-semibold tracking-[-0.01em]';
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col gap-4" data-testid="ban-cu">
        <!-- Thanh khoảng ngày -->
        <div class="flex flex-wrap items-center justify-between gap-3">
            <div
                class="flex gap-0.5 rounded-lg bg-muted p-1"
                role="tablist"
                aria-label="Khoảng ngày"
            >
                <button
                    v-for="r in ranges"
                    :key="r.key"
                    type="button"
                    role="tab"
                    :aria-selected="range === r.key"
                    :data-testid="`ban-cu-range-${r.key}`"
                    :class="
                        cn(
                            'rounded-md px-3 py-1 text-sm font-medium transition',
                            range === r.key
                                ? 'bg-card text-foreground shadow-xs'
                                : 'text-muted-foreground hover:text-foreground',
                        )
                    "
                    @click="pick(r.key)"
                >
                    {{ r.label }}
                </button>
            </div>
            <span v-if="p" class="text-xs text-muted-foreground tabular-nums"
                >{{ rangeText }} · {{ collectedText }}</span
            >
        </div>

        <div
            v-if="error && !p"
            class="flex items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 text-sm"
        >
            <span class="text-muted-foreground">{{ error }}</span>
            <Button size="sm" variant="outline" @click="reload()">
                <IconRefresh class="size-4" />
                Thử lại
            </Button>
        </div>

        <template v-else-if="!p">
            <div class="grid grid-cols-4 gap-3">
                <Skeleton v-for="i in 4" :key="i" class="h-24 rounded-[14px]" />
            </div>
            <Skeleton class="h-52 rounded-[14px]" />
            <div class="grid grid-cols-2 gap-4">
                <Skeleton class="h-64 rounded-[14px]" />
                <Skeleton class="h-64 rounded-[14px]" />
            </div>
        </template>

        <template v-else>
            <!-- KPI -->
            <div class="grid grid-cols-4 gap-3" data-testid="ban-cu-kpi">
                <div
                    v-for="t in tiles"
                    :key="t.key"
                    :class="
                        cn(
                            cardCls,
                            'relative flex min-w-0 flex-col gap-1 px-4 py-3.5',
                        )
                    "
                >
                    <span :class="labelCls">{{ t.label }}</span>
                    <span
                        class="font-heading text-2xl font-semibold tabular-nums"
                        >{{ t.value }}</span
                    >
                    <span
                        :class="
                            cn(
                                'flex items-center gap-1 text-xs tabular-nums',
                                deltaCls(t.kpi),
                            )
                        "
                    >
                        <template v-if="t.kpi.delta_pct !== null">
                            <component
                                :is="
                                    t.kpi.delta_pct >= 0
                                        ? IconArrowUpRight
                                        : IconArrowDownRight
                                "
                                class="size-3.5"
                            />
                            {{
                                Math.abs(t.kpi.delta_pct).toLocaleString(
                                    'vi-VN',
                                )
                            }}%
                            <span class="text-muted-foreground"
                                >so với kỳ trước</span
                            >
                        </template>
                        <span v-else class="text-muted-foreground"
                            >Chưa có kỳ trước</span
                        >
                    </span>
                    <svg
                        v-if="t.key === 'views' && spark"
                        viewBox="0 0 100 28"
                        preserveAspectRatio="none"
                        class="pointer-events-none absolute top-3.5 right-4 h-6 w-[34%] text-primary"
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

            <!-- Lượt xem theo ngày -->
            <section :class="cn(cardCls, 'flex flex-col gap-3 p-4')">
                <div class="flex items-baseline justify-between gap-3">
                    <h2 :class="h2">Lượt xem theo ngày</h2>
                    <span
                        v-if="bestDay && bestDay.views > 0"
                        class="text-xs text-muted-foreground tabular-nums"
                        >Cao nhất {{ dayjs(bestDay.date).format('DD/MM') }} ·
                        {{ fmtNum(bestDay.views) }} lượt xem</span
                    >
                </div>
                <BarChart
                    :points="dailyPoints"
                    :highlight="bestDay ? [bestDay.date] : []"
                    height="h-36"
                />
            </section>

            <div class="grid grid-cols-2 items-start gap-4">
                <!-- Video nổi bật -->
                <section
                    :class="cn(cardCls, 'flex flex-col overflow-hidden')"
                    data-testid="ban-cu-top"
                >
                    <header class="border-b px-4 py-3">
                        <h2 :class="h2">Video nổi bật</h2>
                    </header>
                    <p
                        v-if="!top.length"
                        class="px-4 py-8 text-center text-sm text-muted-foreground"
                    >
                        Chưa có số liệu video trong khoảng này.
                    </p>
                    <ol v-else class="flex flex-col p-1.5">
                        <li v-for="(v, i) in top" :key="v.id">
                            <button
                                type="button"
                                class="grid w-full grid-cols-[18px_30px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-accent/50 focus-visible:outline-2 focus-visible:outline-ring"
                                @click="
                                    openVideo(
                                        top.map((x) => x.id),
                                        v.id,
                                    )
                                "
                            >
                                <span
                                    class="text-center text-sm font-semibold text-muted-foreground tabular-nums"
                                    >{{ i + 1 }}</span
                                >
                                <CoverThumb
                                    :id="v.id"
                                    :fallback="v.product_image"
                                    class="h-[53px] w-[30px] rounded-md"
                                />
                                <span class="min-w-0">
                                    <span
                                        class="block truncate text-sm font-medium"
                                        >{{ productName(v.product_code) }}</span
                                    >
                                    <span
                                        class="block truncate text-xs text-muted-foreground"
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
                                            class="block h-full rounded-full bg-primary"
                                            :style="{
                                                width: `${Math.max(3, (v.views / topMax) * 100)}%`,
                                            }"
                                        />
                                    </span>
                                </span>
                                <span class="flex items-center gap-2">
                                    <span
                                        class="text-sm font-semibold tabular-nums"
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

                <!-- Bình luận hỏi mua -->
                <section
                    :class="cn(cardCls, 'flex flex-col overflow-hidden')"
                    data-testid="ban-cu-binhluan"
                >
                    <header class="border-b px-4 py-3">
                        <h2 :class="h2">Bình luận hỏi mua</h2>
                        <p class="text-xs text-muted-foreground tabular-nums">
                            {{ fmtNum(p.comments.counts.buy) }} hỏi mua / hỏi
                            giá · {{ p.comments.counts.buy_24h }} trong 24 giờ
                            qua
                        </p>
                    </header>
                    <p
                        v-if="!comments.length"
                        class="px-4 py-8 text-center text-sm text-muted-foreground"
                    >
                        Chưa có bình luận hỏi mua nào.
                    </p>
                    <ul
                        v-else
                        class="flex max-h-[420px] flex-col divide-y overflow-y-auto overscroll-contain"
                    >
                        <li
                            v-for="c in comments"
                            :key="c.id"
                            class="flex flex-col gap-1 px-4 py-3 text-sm"
                        >
                            <div
                                class="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground"
                            >
                                <span class="font-medium text-foreground">{{
                                    c.author || c.handle || 'Ẩn danh'
                                }}</span>
                                <span class="tabular-nums"
                                    >{{
                                        c.at
                                            ? dayjs(c.at).format('HH:mm DD/MM')
                                            : ''
                                    }}<template v-if="c.channel">
                                        · {{ c.channel }}</template
                                    ></span
                                >
                            </div>
                            <p class="line-clamp-3 break-words">{{ c.text }}</p>
                            <div
                                class="flex flex-wrap items-center gap-x-3 text-xs"
                            >
                                <button
                                    v-if="c.video_id"
                                    type="button"
                                    class="truncate text-muted-foreground hover:text-foreground hover:underline"
                                    @click="openVideo([c.video_id], c.video_id)"
                                >
                                    {{
                                        c.video_label
                                            ? `Video: ${c.video_label}`
                                            : 'Xem video'
                                    }}
                                </button>
                                <a
                                    v-if="c.link"
                                    :href="c.link"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="inline-flex items-center gap-1 font-medium text-primary-text hover:underline"
                                    >Trả lời trên TikTok
                                    <IconExternalLink class="size-3.5"
                                /></a>
                            </div>
                        </li>
                    </ul>
                </section>
            </div>
        </template>
    </div>
</template>

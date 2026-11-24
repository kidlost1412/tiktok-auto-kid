<script setup lang="ts">
// So sánh hiệu quả theo sản phẩm / kênh / góc / giờ đăng / giọng / nhạc: chọn chiều so sánh và chỉ số (view TB hoặc tương tác).
// Bấm một dòng (sản phẩm, kênh, góc, giọng) là lọc cả trang theo nhóm đó; bấm lần nữa để bỏ lọc.
import { IconChartBar, IconStarFilled } from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import EmptyState from '@/components/fork/shared/EmptyState.vue';
import { cardCls, fmtNum } from '@/components/fork/shared/status';
import BarChart from '@/components/fork/so-lieu/BarChart.vue';
import type { BarPoint, Filters, Group } from '@/components/fork/so-lieu/types';
import { cn } from '@/lib/utils';

const props = defineProps<{
    breakdowns: Record<string, Group[]>;
    /** Bộ lọc đang áp dụng, để tô dòng đang lọc. */
    filters?: Pick<Filters, 'product' | 'channel' | 'goc' | 'giong'>;
}>();

const FILTERABLE = ['product', 'channel', 'goc', 'giong'] as const;
type FilterDim = (typeof FILTERABLE)[number];

const emit = defineEmits<{ filter: [dim: FilterDim, key: string] }>();

/** Nhóm có từ chừng này bài mới đủ tin để gọi là "tốt nhất". */
const MIN_POSTS = 3;

const dims = [
    { key: 'product', label: 'Sản phẩm' },
    { key: 'channel', label: 'Kênh' },
    { key: 'goc', label: 'Góc nội dung' },
    { key: 'hour', label: 'Giờ đăng' },
    { key: 'giong', label: 'Giọng' },
    { key: 'nhac', label: 'Nhạc' },
];

const dim = ref('product');
const metric = ref<'avg_views' | 'engagement'>('avg_views');

const canFilter = computed(() =>
    (FILTERABLE as readonly string[]).includes(dim.value),
);
const isActive = (g: Group) =>
    canFilter.value &&
    g.key !== '' &&
    props.filters?.[dim.value as FilterDim] === g.key;
const pick = (g: Group) => {
    if (canFilter.value) {
        emit('filter', dim.value as FilterDim, isActive(g) ? '' : g.key);
    }
};

const rows = computed(() => props.breakdowns[dim.value] ?? []);
const value = (g: Group) =>
    metric.value === 'avg_views' ? g.avg_views : g.engagement;
const fmtValue = (v: number) =>
    metric.value === 'avg_views'
        ? fmtNum(Math.round(v))
        : `${v.toLocaleString('vi-VN')}%`;
const unit = computed(() =>
    metric.value === 'avg_views' ? 'view TB/bài' : 'tương tác',
);

const sorted = computed(() =>
    [...rows.value].sort((a, b) => value(b) - value(a)),
);
const max = computed(() => Math.max(1, ...rows.value.map(value)));
// Chỉ nhóm có từ 3 bài trở lên mới được gắn ★; nhóm ít bài hiện huy hiệu "ít bài" (chưa đủ tin để so).
const bestKey = computed(
    () => sorted.value.find((g) => g.posts >= MIN_POSTS)?.key ?? null,
);

// Biểu đồ 24 giờ: giờ không có bài vẫn hiện cột rỗng để thấy khoảng trống trong ngày.
const hourPoints = computed<BarPoint[]>(() =>
    Array.from({ length: 24 }, (_, h) => {
        const g = rows.value.find((r) => Number(r.key) === h);

        return {
            key: String(h),
            axis: h % 3 === 0 ? `${h}h` : '',
            title: `${h}h – ${h + 1}h`,
            value: g ? value(g) : 0,
            sub: g ? `${g.posts} bài` : 'Chưa có bài',
        };
    }),
);

const bestHours = computed(() =>
    [...hourPoints.value]
        .filter((p) => p.value > 0)
        .sort((a, b) => b.value - a.value)
        .slice(0, 3)
        .map((p) => p.key),
);
</script>

<template>
    <section
        :class="cn(cardCls, 'flex flex-col overflow-hidden')"
        data-testid="fork-so-lieu-breakdown"
    >
        <header
            class="flex flex-wrap items-start justify-between gap-3 px-5 pt-4"
        >
            <div>
                <h2 class="text-base font-semibold">
                    So sánh hiệu quả
                </h2>
                <p class="text-[0.7812rem] text-muted-foreground">
                    Nhóm nào có
                    {{
                        metric === 'avg_views'
                            ? 'view TB mỗi bài'
                            : 'tỉ lệ tương tác'
                    }}
                    cao hơn thì nên làm nhiều hơn.
                </p>
            </div>
            <div
                class="flex gap-0.5 rounded-lg bg-muted p-0.5 text-[0.7812rem]"
                role="group"
                aria-label="Chỉ số so sánh"
            >
                <button
                    v-for="m in [
                        { k: 'avg_views', t: 'View TB / bài' },
                        { k: 'engagement', t: 'Tương tác' },
                    ] as const"
                    :key="m.k"
                    type="button"
                    :aria-pressed="metric === m.k"
                    :class="
                        cn(
                            'rounded-md px-2.5 py-1 font-medium transition',
                            metric === m.k
                                ? 'bg-card text-foreground shadow-xs'
                                : 'text-muted-foreground hover:text-foreground',
                        )
                    "
                    @click="metric = m.k"
                >
                    {{ m.t }}
                </button>
            </div>
        </header>
        <div
            class="mt-3 flex gap-1 overflow-x-auto border-b px-4"
            role="group"
            aria-label="So sánh theo"
        >
            <button
                v-for="d in dims"
                :key="d.key"
                type="button"
                :aria-pressed="dim === d.key"
                :class="
                    cn(
                        'relative shrink-0 px-2.5 pt-1 pb-2.5 text-[0.8125rem] font-medium transition-colors',
                        dim === d.key
                            ? 'text-foreground'
                            : 'text-muted-foreground hover:text-foreground',
                    )
                "
                @click="dim = d.key"
            >
                {{ d.label }}
                <span
                    v-if="dim === d.key"
                    class="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-primary"
                />
            </button>
        </div>
        <div class="flex flex-col gap-4 p-5">
            <EmptyState
                v-if="!rows.length"
                :icon="IconChartBar"
                title="Chưa đủ dữ liệu để so sánh"
                description="Cần các bài đã đăng có số liệu từ TikTok. Thử mở rộng khoảng ngày hoặc bỏ bớt bộ lọc."
            />

            <template v-else-if="dim === 'hour'">
                <BarChart
                    :points="hourPoints"
                    :highlight="bestHours"
                    :unit="unit"
                    :format-value="fmtValue"
                />
                <p class="text-xs text-muted-foreground">
                    Giờ nổi bật nhất:
                    <b class="text-foreground">{{
                        bestHours.length
                            ? bestHours.map((h) => `${h}h`).join(', ')
                            : '—'
                    }}</b>
                    (cột đậm). Giờ chỉ có 1–2 bài thì chưa đủ tin cậy.
                </p>
            </template>

            <template v-else>
                <ul class="flex flex-col gap-1">
                    <li v-for="g in sorted" :key="g.key">
                        <component
                            :is="canFilter ? 'button' : 'div'"
                            :type="canFilter ? 'button' : undefined"
                            :aria-pressed="canFilter ? isActive(g) : undefined"
                            :title="
                                canFilter
                                    ? isActive(g)
                                        ? 'Bấm để bỏ lọc'
                                        : `Chỉ xem: ${g.label}`
                                    : undefined
                            "
                            :class="
                                cn(
                                    'flex w-full flex-col gap-1 rounded-lg px-2 py-1.5 text-left',
                                    canFilter &&
                                        'transition-colors hover:bg-accent/50 focus-visible:outline-2 focus-visible:outline-ring',
                                    isActive(g) && 'bg-accent/60',
                                )
                            "
                            @click="pick(g)"
                        >
                            <span
                                class="flex items-baseline justify-between gap-3 text-sm"
                            >
                                <span class="flex min-w-0 items-center gap-1.5">
                                    <span
                                        v-if="g.key === bestKey"
                                        class="shrink-0"
                                        title="Tốt nhất"
                                        role="img"
                                        aria-label="Tốt nhất"
                                        ><IconStarFilled class="size-3.5"
                                    /></span>
                                    <span class="truncate font-medium">{{
                                        g.label
                                    }}</span>
                                    <span
                                        v-if="g.posts < MIN_POSTS"
                                        class="shrink-0 rounded-md bg-muted px-1.5 text-[0.7rem] leading-5 text-muted-foreground"
                                        title="Dưới 3 bài, chưa đủ tin để so sánh"
                                        >ít bài</span
                                    >
                                </span>
                                <span class="shrink-0 tabular-nums">
                                    <b>{{ fmtValue(value(g)) }}</b>
                                    <span
                                        class="ml-2 text-xs text-muted-foreground"
                                        >{{ g.posts }} bài</span
                                    >
                                </span>
                            </span>
                            <span
                                class="block h-1.5 w-full overflow-hidden rounded-full bg-muted"
                            >
                                <span
                                    :class="
                                        cn(
                                            'block h-full rounded-full transition-[width] duration-200',
                                            g.key === bestKey
                                                ? 'bg-primary'
                                                : g.posts < MIN_POSTS
                                                  ? 'bg-muted-foreground/30'
                                                  : 'bg-primary/45',
                                        )
                                    "
                                    :style="{
                                        width: `${Math.max(2, (value(g) / max) * 100)}%`,
                                    }"
                                />
                            </span>
                        </component>
                    </li>
                </ul>
                <p v-if="canFilter" class="text-xs text-muted-foreground">
                    Bấm một dòng để lọc cả trang theo nhóm đó.
                </p>
            </template>
        </div>
    </section>
</template>

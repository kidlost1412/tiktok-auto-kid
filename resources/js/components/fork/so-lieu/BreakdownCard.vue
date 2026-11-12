<script setup lang="ts">
// So sánh hiệu quả theo sản phẩm / góc / giờ đăng / giọng / nhạc: chọn chiều so sánh và chỉ số (view TB hoặc tương tác).
import { IconChartBar } from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import EmptyState from '@/components/fork/shared/EmptyState.vue';
import { fmtNum } from '@/components/fork/shared/status';
import BarChart from '@/components/fork/so-lieu/BarChart.vue';
import type { BarPoint, Group } from '@/components/fork/so-lieu/types';
import { cn } from '@/lib/utils';

const props = defineProps<{
    breakdowns: Record<string, Group[]>;
}>();

const dims = [
    { key: 'product', label: 'Sản phẩm' },
    { key: 'goc', label: 'Góc nội dung' },
    { key: 'hour', label: 'Giờ đăng' },
    { key: 'giong', label: 'Giọng' },
    { key: 'nhac', label: 'Nhạc' },
];

const dim = ref('product');
const metric = ref<'avg_views' | 'engagement'>('avg_views');

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
    <div
        class="flex flex-col gap-4 rounded-xl border bg-card p-4 shadow-[0_1px_2px_rgba(28,25,23,.04),0_2px_6px_-1px_rgba(28,25,23,.06)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,.03),0_1px_2px_rgba(0,0,0,.35)]"
        data-testid="fork-so-lieu-breakdown"
    >
        <div class="flex flex-wrap items-center justify-between gap-3">
            <div
                class="-mx-1 flex max-w-full gap-1 overflow-x-auto px-1"
                role="tablist"
            >
                <button
                    v-for="d in dims"
                    :key="d.key"
                    type="button"
                    role="tab"
                    :aria-selected="dim === d.key"
                    :class="
                        cn(
                            'shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors',
                            dim === d.key
                                ? 'bg-primary-subtle font-semibold text-primary-text ring-1 ring-inset ring-primary-strong/20'
                                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                        )
                    "
                    @click="dim = d.key"
                >
                    {{ d.label }}
                </button>
            </div>
            <div class="flex gap-0.5 rounded-xl border bg-secondary/50 p-1 text-[13px] dark:bg-muted/60">
                <button
                    v-for="m in [
                        { k: 'avg_views', t: 'View TB / bài' },
                        { k: 'engagement', t: 'Tỉ lệ tương tác' },
                    ] as const"
                    :key="m.k"
                    type="button"
                    :class="
                        cn(
                            'rounded-[9px] px-3 py-1.5 font-medium transition',
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
        </div>

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

        <ul v-else class="flex flex-col gap-2.5">
            <li
                v-for="(g, i) in sorted"
                :key="g.key"
                class="flex flex-col gap-1"
            >
                <div class="flex items-baseline justify-between gap-3 text-sm">
                    <span class="min-w-0 truncate font-medium">
                        <span v-if="i === 0" class="mr-1" title="Tốt nhất"
                            >★</span
                        >{{ g.label }}
                    </span>
                    <span class="shrink-0 tabular-nums">
                        <b>{{ fmtValue(value(g)) }}</b>
                        <span class="ml-2 text-xs text-muted-foreground"
                            >{{ g.posts }} bài</span
                        >
                    </span>
                </div>
                <div class="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                        :class="
                            cn(
                                'h-full rounded-full transition-[width] duration-500',
                                i === 0 ? 'bg-primary-strong' : 'bg-primary-strong/50',
                            )
                        "
                        :style="{
                            width: `${Math.max(2, (value(g) / max) * 100)}%`,
                        }"
                    />
                </div>
            </li>
        </ul>
    </div>
</template>

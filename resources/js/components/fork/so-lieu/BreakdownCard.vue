<script setup lang="ts">
// So sánh hiệu quả theo sản phẩm / góc / giờ đăng / giọng / nhạc: chọn chiều so sánh và chỉ số (view TB hoặc tương tác).
import { IconChartBar } from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import EmptyState from '@/components/fork/shared/EmptyState.vue';
import { cardCls, fmtNum } from '@/components/fork/shared/status';
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
    <section
        :class="cn(cardCls, 'flex flex-col overflow-hidden')"
        data-testid="fork-so-lieu-breakdown"
    >
        <header
            class="flex flex-wrap items-start justify-between gap-3 px-5 pt-4"
        >
            <div>
                <h2
                    class="font-heading text-[1rem] font-semibold tracking-[-0.01em]"
                >
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
            <div class="flex gap-0.5 rounded-lg bg-muted p-0.5 text-[0.7812rem]">
                <button
                    v-for="m in [
                        { k: 'avg_views', t: 'View TB / bài' },
                        { k: 'engagement', t: 'Tương tác' },
                    ] as const"
                    :key="m.k"
                    type="button"
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

            <ul v-else class="flex flex-col gap-3">
                <li
                    v-for="(g, i) in sorted"
                    :key="g.key"
                    class="flex flex-col gap-1"
                >
                    <div
                        class="flex items-baseline justify-between gap-3 text-sm"
                    >
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
                    <div class="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                            :class="
                                cn(
                                    'h-full rounded-full transition-[width] duration-500',
                                    i === 0 ? 'bg-primary' : 'bg-primary/45',
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
    </section>
</template>

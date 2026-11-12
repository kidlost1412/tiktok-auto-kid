<script setup lang="ts">
// Biểu đồ cột thuần CSS (không thêm thư viện): rê chuột / chạm để xem số chính xác.
import { computed, ref } from 'vue';

import { fmtCompact, fmtNum } from '@/components/fork/shared/status';
import type { BarPoint } from '@/components/fork/so-lieu/types';
import { cn } from '@/lib/utils';

const props = withDefaults(
    defineProps<{
        points: BarPoint[];
        /** Các cột được tô nổi bật */
        highlight?: string[];
        unit?: string;
        height?: string;
        formatValue?: (v: number) => string;
    }>(),
    {
        highlight: () => [],
        unit: 'lượt xem',
        height: 'h-44',
        formatValue: undefined,
    },
);

const max = computed(() => Math.max(1, ...props.points.map((p) => p.value)));
const active = ref<string | null>(null);
const fmt = (v: number) => (props.formatValue ?? fmtNum)(v);
const empty = computed(() => props.points.every((p) => p.value === 0));
const hasHighlight = computed(() => props.highlight.length > 0);
</script>

<template>
    <div class="flex flex-col gap-1.5">
        <div :class="cn('relative flex items-stretch gap-1', height)">
            <!-- Vạch ngang -->
            <div
                class="pointer-events-none absolute inset-0 flex flex-col justify-between"
                aria-hidden="true"
            >
                <span
                    v-for="t in [1, 0.5, 0]"
                    :key="t"
                    class="flex items-center gap-2 text-[0.7rem] text-muted-foreground tabular-nums"
                >
                    <span class="w-9 shrink-0 text-right">{{
                        fmtCompact(Math.round(max * t))
                    }}</span>
                    <span class="h-px flex-1 bg-border/70" />
                </span>
            </div>

            <div class="relative ml-11 flex flex-1 items-end gap-px sm:gap-0.5">
                <div
                    v-for="p in points"
                    :key="p.key"
                    class="group relative flex h-full min-w-0 flex-1 items-end"
                    @mouseenter="active = p.key"
                    @mouseleave="active = null"
                    @click="active = active === p.key ? null : p.key"
                >
                    <div
                        :class="
                            cn(
                                'w-full rounded-t-[3px] transition-[height,opacity] duration-500',
                                hasHighlight && !highlight.includes(p.key)
                                    ? 'bg-primary/30 group-hover:bg-primary/60'
                                    : 'bg-primary/80 group-hover:bg-primary',
                            )
                        "
                        :style="{
                            height:
                                p.value > 0
                                    ? `${Math.max(2, (p.value / max) * 100)}%`
                                    : '2px',
                            opacity: p.value > 0 ? 1 : 0.25,
                        }"
                    />
                    <div
                        v-if="active === p.key"
                        class="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 w-max max-w-44 -translate-x-1/2 rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground shadow-md"
                    >
                        <div class="font-medium">{{ p.title }}</div>
                        <div class="tabular-nums">
                            {{ fmt(p.value) }} {{ unit }}
                        </div>
                        <div v-if="p.sub" class="text-muted-foreground">
                            {{ p.sub }}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div
            class="ml-11 flex gap-px text-[0.7rem] text-muted-foreground sm:gap-0.5"
        >
            <span
                v-for="p in points"
                :key="p.key"
                class="min-w-0 flex-1 overflow-visible text-center whitespace-nowrap"
                >{{ p.axis }}</span
            >
        </div>

        <p v-if="empty" class="text-center text-xs text-muted-foreground">
            Chưa có số liệu trong khoảng này.
        </p>
    </div>
</template>

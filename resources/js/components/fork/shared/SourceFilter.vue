<script setup lang="ts">
// Bộ lọc nguồn video (Tất cả / Video AI / Kho riêng) dạng nút chọn nhỏ, dùng chung Tổng quan và Số liệu.
import { SOURCE_FILTERS } from '@/components/fork/shared/source';
import type { SourceFilter } from '@/components/fork/shared/source';
import { cn } from '@/lib/utils';

defineProps<{ class?: string }>();

const model = defineModel<SourceFilter>({ default: 'all' });
</script>

<template>
    <div
        :class="cn('inline-flex gap-0.5 rounded-lg bg-muted p-1', $props.class)"
        role="tablist"
        aria-label="Nguồn video"
        data-testid="fork-source-filter"
    >
        <button
            v-for="f in SOURCE_FILTERS"
            :key="f.value"
            type="button"
            role="tab"
            :aria-selected="model === f.value"
            :data-value="f.value"
            :class="
                cn(
                    'inline-flex h-7 items-center rounded-md px-2.5 text-[0.8125rem] font-medium whitespace-nowrap transition-colors',
                    model === f.value
                        ? 'bg-card text-foreground shadow-xs dark:bg-white/10'
                        : 'text-muted-foreground hover:text-foreground',
                )
            "
            @click="model = f.value"
        >
            {{ f.label }}
        </button>
    </div>
</template>

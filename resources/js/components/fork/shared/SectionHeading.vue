<script setup lang="ts">
// Tiêu đề từng khối trong trang: chip biểu tượng màu + tiêu đề 18px + mô tả nhỏ + nút phụ (cùng kiểu với Xưởng Video).
import type { Component } from 'vue';

import { type Tone, toneClasses } from '@/components/fork/shared/status';
import { cn } from '@/lib/utils';

withDefaults(
    defineProps<{
        title: string;
        description?: string;
        icon?: Component;
        tone?: Tone;
    }>(),
    { tone: 'violet' },
);
</script>

<template>
    <div class="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div class="flex min-w-0 items-start gap-3.5">
            <span
                v-if="icon"
                :class="
                    cn(
                        'flex size-[38px] shrink-0 items-center justify-center rounded-[11px] ring-1 ring-inset ring-black/5 dark:ring-white/10',
                        toneClasses[tone].chip,
                    )
                "
            >
                <component :is="icon" class="size-[18px]" />
            </span>
            <div class="min-w-0">
                <h2
                    class="font-heading text-lg leading-snug font-semibold tracking-[-0.015em]"
                >
                    {{ title }}
                </h2>
                <p
                    v-if="description"
                    class="mt-0.5 text-[0.8125rem] leading-relaxed text-muted-foreground"
                >
                    {{ description }}
                </p>
            </div>
        </div>
        <div v-if="$slots.default" class="flex flex-wrap items-center gap-2">
            <slot />
        </div>
    </div>
</template>

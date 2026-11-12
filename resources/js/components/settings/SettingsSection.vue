<script setup lang="ts">
// Thẻ mục kiểu "Xưởng Video": chip biểu tượng màu + tiêu đề 18px + mô tả mờ, nút hành động bên phải.
import type { Component } from 'vue';

withDefaults(
    defineProps<{
        title: string;
        description?: string;
        icon?: Component;
        tone?: 'primary' | 'green' | 'blue' | 'amber' | 'red' | 'neutral';
    }>(),
    { tone: 'primary' },
);
</script>

<template>
    <section
        class="flex min-w-0 flex-col gap-5 rounded-[14px] border border-border bg-card p-5 shadow-card sm:p-6"
    >
        <div class="flex items-start gap-3.5">
            <span
                v-if="icon"
                class="fk-chip"
                :class="tone !== 'primary' && `is-${tone}`"
                aria-hidden="true"
            >
                <component :is="icon" />
            </span>
            <div class="min-w-0 flex-1">
                <h2
                    class="text-lg leading-snug font-semibold tracking-[-0.015em] text-foreground"
                >
                    {{ title }}
                </h2>
                <p
                    v-if="description"
                    class="mt-1 text-sm leading-normal text-muted-foreground"
                >
                    {{ description }}
                </p>
            </div>
            <div
                v-if="$slots['actions']"
                class="flex shrink-0 flex-wrap items-center justify-end gap-2"
            >
                <slot name="actions" />
            </div>
        </div>
        <slot />
    </section>
</template>

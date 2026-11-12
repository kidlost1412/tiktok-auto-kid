<script setup lang="ts">
// Tiêu đề từng khối trong trang: cùng cỡ chữ, cùng cách đặt mô tả và nút phụ.
import type { Component } from 'vue';

defineProps<{ title: string; description?: string; icon?: Component }>();
</script>

<template>
    <div class="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div class="min-w-0">
            <h2
                class="flex items-center gap-2.5 font-heading text-xl font-semibold tracking-tight"
            >
                <component
                    :is="icon"
                    v-if="icon"
                    class="size-5 text-muted-foreground"
                />
                {{ title }}
            </h2>
            <p v-if="description" class="mt-1 text-sm text-muted-foreground">
                {{ description }}
            </p>
        </div>
        <div v-if="$slots.default" class="flex flex-wrap items-center gap-2">
            <slot />
        </div>
    </div>
</template>

<script setup lang="ts">
// Trạng thái trống: luôn nói rõ vì sao trống và việc nên làm tiếp theo.
import type { Component } from 'vue';

import { cn } from '@/lib/utils';

const props = defineProps<{
    icon?: Component;
    title: string;
    description?: string;
    class?: string;
}>();
</script>

<template>
    <div
        :class="
            cn(
                'flex flex-col items-center gap-3 rounded-xl border border-dashed bg-muted/20 px-6 py-14 text-center',
                props.class,
            )
        "
    >
        <span
            v-if="icon"
            class="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground"
        >
            <component :is="icon" class="size-6" stroke-width="1.5" />
        </span>
        <div class="flex max-w-md flex-col gap-1">
            <p class="text-lg font-medium">{{ title }}</p>
            <p
                v-if="description"
                class="text-sm text-balance text-muted-foreground"
            >
                {{ description }}
            </p>
        </div>
        <div
            v-if="$slots.default"
            class="mt-1 flex flex-wrap justify-center gap-2"
        >
            <slot />
        </div>
    </div>
</template>

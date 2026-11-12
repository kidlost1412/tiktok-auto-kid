<script setup lang="ts">
// Nhãn trạng thái dùng chung: cùng trạng thái thì cùng màu, biểu tượng và chữ ở mọi trang.
import { computed } from 'vue';

import { statusOf, toneClasses } from '@/components/fork/shared/status';
import { cn } from '@/lib/utils';

const props = defineProps<{
    status: string;
    class?: string;
    iconOnly?: boolean;
}>();

const meta = computed(() => statusOf(props.status));
</script>

<template>
    <span
        :class="
            cn(
                'inline-flex h-7 w-fit shrink-0 items-center gap-1.5 rounded-full px-2.5 text-sm font-medium whitespace-nowrap',
                toneClasses[meta.tone].chip,
                meta.dashed &&
                    'border border-dashed border-border bg-transparent',
                props.class,
            )
        "
        :title="meta.label"
    >
        <component
            :is="meta.icon"
            class="size-4"
            :class="{ 'animate-spin': meta.spin }"
        />
        <template v-if="!iconOnly">{{ meta.label }}</template>
    </span>
</template>

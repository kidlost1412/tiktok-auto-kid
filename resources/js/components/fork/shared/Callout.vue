<script setup lang="ts">
// Hộp thông báo dùng chung (cảnh báo, thông tin, thành công, lỗi) với nút hành động tuỳ chọn.
import {
    IconAlertTriangle,
    IconCircleCheck,
    IconInfoCircle,
    IconXboxX,
} from '@tabler/icons-vue';
import { computed } from 'vue';

import { type Tone, toneClasses } from '@/components/fork/shared/status';
import { cn } from '@/lib/utils';

const props = withDefaults(defineProps<{ tone?: Tone; class?: string }>(), {
    tone: 'info',
    class: undefined,
});

const icon = computed(
    () =>
        ({
            warn: IconAlertTriangle,
            danger: IconXboxX,
            success: IconCircleCheck,
            info: IconInfoCircle,
            violet: IconInfoCircle,
            neutral: IconInfoCircle,
        })[props.tone],
);
</script>

<template>
    <div
        :class="
            cn(
                'flex items-start gap-3 rounded-xl border px-4 py-3.5 text-sm font-medium',
                toneClasses[tone].box,
                props.class,
            )
        "
        role="status"
    >
        <component :is="icon" class="mt-0.5 size-5 shrink-0" />
        <div class="min-w-0 flex-1 leading-relaxed"><slot /></div>
        <div v-if="$slots.action" class="shrink-0 self-center">
            <slot name="action" />
        </div>
    </div>
</template>

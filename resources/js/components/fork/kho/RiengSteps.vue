<script setup lang="ts">
// Dải 3 bước (nằm trong thanh lọc): cho chủ app biết đang ở đâu trong quy trình đăng video riêng.
import { IconChevronRight } from '@tabler/icons-vue';

import { cn } from '@/lib/utils';

defineProps<{ current: 1 | 2 | 3 }>();

const steps = [
    'Chọn video',
    'Chọn kênh, sản phẩm, caption',
    'Xem trước lịch rồi hẹn đăng',
];
</script>

<template>
    <ol
        class="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[13px]"
        aria-label="Các bước đăng video riêng"
        data-testid="fork-rieng-steps"
    >
        <template v-for="(label, i) in steps" :key="label">
            <li
                :aria-current="current === i + 1 ? 'step' : undefined"
                :data-active="current === i + 1"
                :class="
                    cn(
                        'flex items-center gap-1.5 rounded-full px-2 py-0.5 transition',
                        current === i + 1
                            ? 'bg-primary/10 font-semibold text-foreground ring-1 ring-primary/40'
                            : current > i + 1
                              ? 'text-muted-foreground'
                              : 'text-muted-foreground/80',
                    )
                "
            >
                <span
                    :class="
                        cn(
                            'flex size-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold tabular-nums',
                            current === i + 1
                                ? 'border-primary bg-primary text-primary-foreground'
                                : 'bg-muted',
                        )
                    "
                    >{{ i + 1 }}</span
                >
                {{ label }}
            </li>
            <IconChevronRight
                v-if="i < steps.length - 1"
                class="size-4 text-muted-foreground/60 max-sm:hidden"
            />
        </template>
    </ol>
</template>

<script setup lang="ts">
// Hướng dẫn gọn: mặc định ẩn, bấm dấu "?" mới mở ra (đỡ rối mắt). Có `title` thì hiện tiêu đề kèm nút.
import { IconHelpCircle } from '@tabler/icons-vue';
import { ref } from 'vue';

import { cn } from '@/lib/utils';

defineProps<{ title?: string; titleClass?: string }>();

const open = ref(false);
</script>

<template>
    <div class="flex min-w-0 flex-col">
        <div class="flex min-w-0 items-center gap-1">
            <span v-if="title" :class="cn('font-medium', titleClass)">{{
                title
            }}</span>
            <slot name="title" />
            <button
                type="button"
                :class="
                    cn(
                        'inline-flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring',
                        open && 'text-primary-text',
                    )
                "
                :aria-expanded="open"
                :title="open ? 'Ẩn hướng dẫn' : 'Xem hướng dẫn'"
                aria-label="Hướng dẫn"
                data-testid="fork-help-toggle"
                @click="open = !open"
            >
                <IconHelpCircle class="size-4" />
            </button>
        </div>
        <div
            v-if="open"
            class="mt-1 text-[0.8125rem] leading-relaxed text-muted-foreground"
        >
            <slot />
        </div>
    </div>
</template>

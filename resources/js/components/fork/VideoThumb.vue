<script setup lang="ts">
// Ảnh bìa video trong kho. Chưa có ảnh (hoặc lỗi tải) thì hiện khung xám có biểu tượng.
import { IconMovie } from '@tabler/icons-vue';
import { ref } from 'vue';

import { cn } from '@/lib/utils';

const props = defineProps<{
    id: number | null | undefined;
    class?: string;
}>();

const failed = ref(false);
</script>

<template>
    <img
        v-if="props.id && !failed"
        :src="`/auto/kho/video/${props.id}/cover`"
        alt=""
        loading="lazy"
        :class="cn('shrink-0 rounded-md bg-muted object-cover', props.class)"
        @error="failed = true"
    />
    <div
        v-else
        :class="
            cn(
                'flex shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground',
                props.class,
            )
        "
    >
        <IconMovie class="size-1/3 min-h-4 min-w-4" />
    </div>
</template>

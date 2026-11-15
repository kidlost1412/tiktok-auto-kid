<script setup lang="ts">
// Ảnh bìa video trong kho. Đang tải thì có khung nhấp nháy; chưa có ảnh (hoặc lỗi tải) thì hiện khung xám có biểu tượng.
import { IconMovie } from '@tabler/icons-vue';
import { ref, watch } from 'vue';

import { cn } from '@/lib/utils';

const props = defineProps<{
    id: number | null | undefined;
    class?: string;
}>();

const failed = ref(false);
const loaded = ref(false);

watch(
    () => props.id,
    () => {
        failed.value = false;
        loaded.value = false;
    },
);
</script>

<template>
    <span
        v-if="props.id && !failed"
        :class="
            cn(
                'relative block shrink-0 overflow-hidden rounded-md bg-muted',
                !loaded && 'animate-pulse',
                props.class,
            )
        "
    >
        <img
            :src="`/auto/kho/video/${props.id}/cover`"
            alt=""
            loading="lazy"
            decoding="async"
            :class="
                cn(
                    'size-full object-cover transition-opacity duration-300',
                    loaded ? 'opacity-100' : 'opacity-0',
                )
            "
            @load="loaded = true"
            @error="failed = true"
        />
    </span>
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

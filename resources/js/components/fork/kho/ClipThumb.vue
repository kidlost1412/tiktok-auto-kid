<script setup lang="ts">
// Hình nhỏ 9:16 của một video trong Kho riêng: ảnh đại diện + thời lượng; rê chuột vào thì phát thử (tắt tiếng),
// bấm để phóng to (cha mở lightbox). Máy cảm ứng không có rê chuột nên chỉ bấm để xem.
import { IconMovie, IconPlayerPlay } from '@tabler/icons-vue';
import { onBeforeUnmount, ref } from 'vue';

import { cn } from '@/lib/utils';

const props = defineProps<{
    id: number;
    duration?: number | null;
    name?: string;
    class?: string;
}>();

const emit = defineEmits<{ zoom: [] }>();

const failed = ref(false);
const playing = ref(false);
let timer: ReturnType<typeof setTimeout> | null = null;

const reduced =
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

// Chờ một chút trước khi tải video để lướt chuột qua danh sách dài không kéo hàng loạt video.
const enter = () => {
    if (reduced || timer) {
        return;
    }

    timer = setTimeout(() => {
        playing.value = true;
    }, 220);
};

const leave = () => {
    if (timer) {
        clearTimeout(timer);
        timer = null;
    }

    playing.value = false;
};

onBeforeUnmount(leave);

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
</script>

<template>
    <button
        type="button"
        :class="
            cn(
                'group relative block aspect-[9/16] w-14 shrink-0 overflow-hidden rounded-lg border bg-muted text-muted-foreground shadow-xs focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring',
                props.class,
            )
        "
        :aria-label="`Xem video${name ? ' ' + name : ''}`"
        :data-testid="`fork-clip-thumb-${id}`"
        @pointerenter="(e: PointerEvent) => e.pointerType === 'mouse' && enter()"
        @pointerleave="leave"
        @click="emit('zoom')"
    >
        <img
            v-if="!failed"
            :src="`/auto/kho/rieng/video/${id}/thumb`"
            alt=""
            loading="lazy"
            class="absolute inset-0 size-full object-cover"
            @error="failed = true"
        />
        <span v-else class="absolute inset-0 flex items-center justify-center"><IconMovie class="size-5" /></span>
        <video
            v-if="playing"
            :src="`/auto/kho/video/${id}`"
            class="absolute inset-0 size-full bg-black object-cover"
            muted
            loop
            autoplay
            playsinline
            preload="metadata"
        />
        <span
            v-if="!playing"
            class="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 text-white opacity-0 transition group-hover:bg-black/25 group-hover:opacity-100"
            ><IconPlayerPlay class="size-5 drop-shadow" /></span
        >
        <span
            v-if="duration"
            class="pointer-events-none absolute right-0.5 bottom-0.5 rounded bg-black/70 px-1 text-[10px] leading-4 font-medium text-white tabular-nums"
            >{{ fmt(duration) }}</span
        >
    </button>
</template>

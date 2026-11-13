<script setup lang="ts">
// Khung 3D nhỏ cho thẻ "Xưởng nhỏ" trong trang Xưởng Video: tải lười (chỉ khi thẻ được mở ra),
// không WebGL/dựng lỗi thì báo lỗi ra ngoài để cha ẩn khung đi (không có bản 2D riêng cho mini này
// — mini chỉ là trang trí, bản 2D của "Xưởng nhỏ" đầy đủ vẫn ở trang chủ /nha).
import { onBeforeUnmount, onMounted, ref } from 'vue';

import type { MiniScene } from './mini';

const emit = defineEmits<{ fail: [] }>();

const host = ref<HTMLDivElement | null>(null);
const ready = ref(false);
let scene: MiniScene | null = null;
let gone = false;

onMounted(async () => {
    try {
        const mod = await import('./index');
        const mini = await import('./mini');
        if (gone || !host.value) {
            return;
        }
        if (!mod.webglOk()) {
            throw new Error('Trình duyệt không hỗ trợ WebGL');
        }
        scene = mini.createMiniXuongScene({
            host: host.value,
            reduced: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
        });
        ready.value = true;
    } catch (err) {
        console.error('[Xưởng Video] không dựng được xưởng nhỏ thu nhỏ:', err);
        emit('fail');
    }
});

onBeforeUnmount(() => {
    gone = true;
    scene?.dispose();
    scene = null;
});
</script>

<template>
    <div
        ref="host"
        class="relative size-full"
        role="img"
        aria-label="Xưởng nhỏ: hai đạo diễn đang ngồi làm việc"
        data-testid="xuong-mini-3d"
    >
        <div v-if="!ready" class="absolute inset-0 grid place-items-center text-xs text-muted-foreground">
            Đang dựng…
        </div>
    </div>
</template>

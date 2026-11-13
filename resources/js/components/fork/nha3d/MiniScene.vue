<script setup lang="ts">
// Khung 3D "Khu Tự Trị" thu nhỏ trong trang Xưởng Video: tải lười three.js khi khung được dựng, nhận dữ liệu thật
// (/nha/trang-thai do trang cha hỏi) để hai Đạo diễn ngồi làm / đứng dậy đi lại / ngủ đúng như ngoài đời.
// Không có WebGL hoặc dựng lỗi thì báo ra ngoài để cha hiện chữ thay thế.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { NhaData } from '../nha/types';

import type { MiniMode, MiniScene } from './mini';

const props = defineProps<{ data: NhaData | null; sep?: string }>();
const emit = defineEmits<{ fail: [] }>();

const host = ref<HTMLDivElement | null>(null);
const ready = ref(false);
let scene: MiniScene | null = null;
let gone = false;

const modeOf = (d: NhaData | null): MiniMode => {
    if (!d) {
        return 'working';
    }

    if (!d.hub.up) {
        return 'down';
    }

    return d.vai.daodien?.state ?? 'idle';
};

const push = () =>
    scene?.setState(
        modeOf(props.data),
        props.data?.vai.daodien?.bubble ?? null,
    );

onMounted(async () => {
    try {
        const [util, mini] = await Promise.all([
            import('./util'),
            import('./mini'),
        ]);
        if (gone || !host.value) {
            return;
        }
        if (!util.webglOk()) {
            throw new Error('Trình duyệt không hỗ trợ WebGL');
        }
        scene = mini.createMiniXuongScene({
            host: host.value,
            reduced:
                window.matchMedia?.('(prefers-reduced-motion: reduce)')
                    .matches ?? false,
            sep: props.sep,
        });
        ready.value = true;
        push();
        if (props.sep) {
            scene.setSep(props.sep);
        }
    } catch (err) {
        console.error('[Xưởng Video] không dựng được Khu Tự Trị thu nhỏ:', err);
        emit('fail');
    }
});

watch(() => props.data, push);
watch(
    () => props.sep,
    (s) => s && scene?.setSep(s),
);

onBeforeUnmount(() => {
    gone = true;
    scene?.dispose();
    scene = null;
});
</script>

<template>
    <div
        ref="host"
        class="relative size-full overflow-hidden"
        role="img"
        aria-label="Khu Tự Trị: hai Đạo diễn — bấm vào một người để trò chuyện"
        data-testid="xuong-mini-3d"
    >
        <div
            v-if="!ready"
            class="absolute inset-0 grid place-items-center text-xs text-muted-foreground"
        >
            Đang dựng…
        </div>
    </div>
</template>

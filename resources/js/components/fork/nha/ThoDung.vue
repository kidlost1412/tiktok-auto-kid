<script setup lang="ts">
// Phòng dựng: Thợ dựng với hai màn hình (timeline + xem trước) và đèn báo đang render.
import Ban from './Ban.vue';
import Chibi from './Chibi.vue';
import Den from './Den.vue';
import Phong from './Phong.vue';
import type { RoomProps } from './types';

defineProps<RoomProps>();
defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';
const clips = [
    [{ x: 4, w: 16, c: '#ff9f5a' }, { x: 22, w: 10, c: '#7fd1c1' }, { x: 34, w: 18, c: '#ff8fa3' }],
    [{ x: 4, w: 9, c: '#a58bea' }, { x: 15, w: 20, c: '#ffd36a' }, { x: 37, w: 12, c: '#6eb5f2' }],
    [{ x: 6, w: 30, c: '#7fd1c1' }, { x: 38, w: 11, c: '#ff9f5a' }],
];
</script>

<template>
    <Phong
        id="thodung" :x="x" :y="y" wall="#e9f0ff" wain="#cbdaf8" floor="#d8c9b8" name="Phòng dựng" emoji="🛠️"
        label="Phòng dựng, Thợ dựng. Bấm để tới Sản xuất" :state="state" :dim="dim"
        @go="$emit('go')" @hover="$emit('hover', $event)" @leave="$emit('leave')"
    >
        <ellipse cx="94" cy="186" rx="76" ry="9" fill="#6e8be0" opacity="0.22" />
        <!-- màn hình trái: timeline -->
        <g transform="translate(6 78)">
            <path d="M24 50 L18 56 H42 L36 50 Z" fill="#5a4f86" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
            <rect width="60" height="48" rx="5" fill="#3f3560" :stroke="OUT" stroke-width="2.2" />
            <rect x="3.5" y="3.5" width="53" height="41" rx="3" :fill="state === 'working' ? '#2a2556' : '#2f2b52'" />
            <g :class="{ 'nha-screen-flicker': state === 'working' }">
                <g v-for="(row, r) in clips" :key="r" :transform="`translate(4 ${7 + r * 10})`">
                    <rect v-for="(c, i) in row" :key="i" :x="c.x" y="0" :width="c.w" height="7" rx="2" :fill="c.c" :opacity="state === 'sleep' ? 0.5 : 1" />
                </g>
                <path d="M30 6 V42" stroke="#fff" stroke-width="1.6" :class="{ playhead: state === 'working' }" />
            </g>
            <path d="M8 8 Q16 5 24 7" stroke="#fff" stroke-width="1.6" stroke-linecap="round" opacity="0.35" fill="none" />
        </g>
        <!-- màn hình phải: xem trước + đèn render -->
        <g transform="translate(123 78)">
            <path d="M24 50 L18 56 H42 L36 50 Z" fill="#5a4f86" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
            <rect width="60" height="48" rx="5" fill="#3f3560" :stroke="OUT" stroke-width="2.2" />
            <rect x="3.5" y="3.5" width="53" height="41" rx="3" fill="#cfe9ff" />
            <path d="M3.5 36 Q16 22 28 32 Q40 24 56.5 34 V44.5 H3.5 Z" fill="#9ad9a0" />
            <circle cx="43" cy="14" r="6" fill="#ffd36a" />
            <path d="M24 17 L38 24 L24 31 Z" fill="#fff" fill-opacity="0.9" :stroke="OUT" stroke-width="1.6" stroke-linejoin="round" />
            <g :class="{ 'nha-screen-flicker': state === 'working' }">
                <rect x="3.5" y="39" width="53" height="5.5" fill="#2a2556" opacity="0.55" />
                <rect x="6" y="40.6" :width="state === 'working' ? 30 : 12" height="2.4" rx="1.2" fill="#ff9f5a" />
            </g>
            <circle cx="54" cy="-5" r="4.6" :fill="state === 'working' ? '#ff4d6a' : '#8a7aa8'" :stroke="OUT" stroke-width="1.8" :class="{ 'nha-led': state === 'working' }" />
            <rect x="40" y="-9" width="9" height="8" rx="2" fill="#fff" :stroke="OUT" stroke-width="1.4" opacity="0" />
        </g>
        <!-- bàn phím -->
        <rect x="68" y="127" width="52" height="8" rx="2.5" fill="#e9e3f7" :stroke="OUT" stroke-width="1.8" />
        <path d="M73 130 h42" stroke="#a58bea" stroke-width="2" stroke-dasharray="3 2.2" stroke-linecap="round" />
        <g transform="translate(94 144) scale(1.15)">
            <Chibi :state="state" outfit="#ff9f5a" :mug="false" :delay="1.7">
                <template #behind>
                    <rect x="-25" y="-46" width="50" height="56" rx="14" fill="#3aa6a0" :stroke="OUT" stroke-width="2.2" />
                </template>
                <template #body>
                    <path d="M-15 -37 Q0 -24 15 -37" fill="#ff8a3a" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <rect x="-10" y="-14" width="20" height="9" rx="3" fill="#ff8a3a" :stroke="OUT" stroke-width="1.6" />
                </template>
                <template #hair-back>
                    <path d="M-29 -62 L-32 -80 L-22 -75 L-17 -94 L-8 -81 L0 -98 L8 -81 L17 -94 L22 -75 L32 -80 L29 -62 Z" fill="#3aa6a0" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hair-front>
                    <path d="M-27 -64 C-27 -78 27 -78 27 -64 C20 -69 10 -71 0 -68 C-10 -71 -20 -69 -27 -64 Z" fill="#46bab3" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hat>
                    <path d="M-28 -70 Q0 -80 28 -70 L28 -64 Q0 -74 -28 -64 Z" fill="#fff" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <path d="M-28 -67 Q0 -77 28 -67" fill="none" stroke="#ff8a3a" stroke-width="2.6" />
                </template>
            </Chibi>
        </g>
        <Ban :cx="94" :w="160" color="#7b8fd6" top-color="#a9b9f0" />
        <Den :x="22" :y="134" :on="state === 'working'" />
    </Phong>
</template>

<style scoped>
.playhead {
    animation: playhead 3.2s linear infinite;
}
@keyframes playhead {
    0% { transform: translateX(-24px); }
    100% { transform: translateX(22px); }
}
</style>

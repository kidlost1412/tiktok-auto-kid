<script setup lang="ts">
// Phòng đạo diễn: hai đạo diễn đội mũ nồi, bảng phân cảnh ghim tường, bảng clap.
import Ban from './Ban.vue';
import Chibi from './Chibi.vue';
import Phong from './Phong.vue';
import type { RoomProps } from './types';

defineProps<RoomProps>();
defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';
const panels = ['#ffd9a8', '#cfe9ff', '#ffd1dc', '#d8f1c9', '#e4d6ff', '#fff0b5'];
</script>

<template>
    <Phong
        id="daodien" :x="x" :y="y" wall="#fff0e6" wain="#f5cfb4" floor="#e3c1a0" name="Phòng đạo diễn" emoji="🎬"
        label="Phòng đạo diễn, hai Đạo diễn. Bấm để tới Gu và bài học" :state="state" :dim="dim"
        @go="$emit('go')" @hover="$emit('hover', $event)" @leave="$emit('leave')"
    >
        <template #wall>
            <!-- bảng phân cảnh -->
            <g transform="translate(18 20)">
                <rect width="153" height="32" rx="4" fill="#d8a878" :stroke="OUT" stroke-width="2" />
                <g v-for="(c, i) in panels" :key="i" :transform="`translate(${5 + i * 24.5} 4)`">
                    <rect width="21" height="24" rx="2" :fill="c" :stroke="OUT" stroke-width="1.5" />
                    <path v-if="i % 3 === 0" d="M3 20 L8 11 L12 17 L15 13 L19 20 Z" fill="#fff" opacity="0.7" :stroke="OUT" stroke-width="1" />
                    <circle v-else-if="i % 3 === 1" cx="10.5" cy="12" r="5" fill="#fff" opacity="0.7" :stroke="OUT" stroke-width="1" />
                    <path v-else d="M4 18 H17 M6 12 H15" stroke="#4a3868" stroke-width="1.6" stroke-linecap="round" />
                </g>
                <circle v-for="i in [3, 77, 150]" :key="i" :cx="i" cy="-1" r="2.6" fill="#ff6f7f" :stroke="OUT" stroke-width="1.2" />
            </g>
        </template>

        <ellipse cx="96" cy="186" rx="78" ry="9" fill="#e85d6f" opacity="0.22" />
        <g transform="translate(52 144) scale(0.97)">
            <Chibi :state="state" outfit="#f2b84b" :mug="false" :delay="0.2" mouth="open" skin="#ffd6bd">
                <template #behind>
                    <rect x="-25" y="-46" width="50" height="56" rx="14" fill="#8a6fd6" :stroke="OUT" stroke-width="2.2" />
                </template>
                <template #body>
                    <path d="M-12 -37 L0 -22 L12 -37" fill="#fff" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <path d="M0 -22 V4" :stroke="OUT" stroke-width="2" />
                </template>
                <template #hair-back>
                    <path d="M-29 -60 C-31 -84 31 -84 29 -60 L29 -50 L-29 -50 Z" fill="#2f2548" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hair-front>
                    <path d="M-27 -62 C-28 -78 28 -78 27 -62 C20 -68 8 -70 0 -66 C-10 -70 -20 -68 -27 -62 Z" fill="#3d3160" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hat>
                    <path d="M-30 -76 C-30 -100 30 -102 32 -80 C34 -72 -30 -68 -30 -76 Z" fill="#b8456b" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-22 -92 C-12 -98 6 -98 16 -94" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity="0.4" />
                    <path d="M-24 -76 Q0 -70 28 -76" fill="none" stroke="#8c2f52" stroke-width="2" stroke-linecap="round" />
                    <circle cx="0" cy="-101" r="3" fill="#8c2f52" :stroke="OUT" stroke-width="1.6" />
                </template>
            </Chibi>
        </g>
        <g transform="translate(140 144) scale(0.97)">
            <Chibi :state="state" outfit="#b79cf0" :mug="false" :delay="2.6" skin="#f9d2b5">
                <template #behind>
                    <rect x="-25" y="-46" width="50" height="56" rx="14" fill="#e85d6f" :stroke="OUT" stroke-width="2.2" />
                </template>
                <template #body>
                    <path d="M-12 -37 L0 -24 L12 -37" fill="#fff" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <rect x="-15" y="-20" width="9" height="8" rx="2" fill="#9a7fdc" :stroke="OUT" stroke-width="1.5" />
                </template>
                <template #hair-back>
                    <path d="M-29 -60 C-31 -84 31 -84 29 -60 C32 -48 30 -42 24 -42 L-24 -42 C-30 -42 -32 -48 -29 -60 Z" fill="#b5603a" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hair-front>
                    <path d="M-27 -62 C-28 -78 28 -78 27 -62 C22 -70 14 -72 6 -69 C-2 -66 -12 -71 -27 -62 Z" fill="#c8714a" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hat>
                    <path d="M-32 -78 C-32 -102 28 -100 30 -76 C30 -70 -32 -70 -32 -78 Z" fill="#3f5bb8" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-24 -94 C-14 -99 4 -98 14 -94" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity="0.4" />
                    <path d="M-26 -77 Q-2 -70 26 -75" fill="none" stroke="#2d4392" stroke-width="2" stroke-linecap="round" />
                    <circle cx="-2" cy="-101" r="3" fill="#2d4392" :stroke="OUT" stroke-width="1.6" />
                </template>
            </Chibi>
        </g>
        <Ban :cx="96" :w="172" color="#c98a5e" top-color="#e5ad82" />
        <!-- bảng clap -->
        <g transform="translate(78 134)">
            <rect x="0" y="-22" width="40" height="22" rx="2.5" fill="#3b3158" :stroke="OUT" stroke-width="2" />
            <path d="M4 -14 H36 M4 -8 H26" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="0.85" />
            <g :class="{ clap: state === 'working' }" style="transform-origin: 0 -22px">
                <rect x="0" y="-31" width="40" height="9" rx="2" fill="#fff" :stroke="OUT" stroke-width="2" />
                <path d="M6 -31 l-5 9 M16 -31 l-5 9 M26 -31 l-5 9 M36 -31 l-5 9" stroke="#3b3158" stroke-width="4" />
            </g>
        </g>
    </Phong>
</template>

<style scoped>
.clap {
    animation: clap 1.5s ease-in-out infinite;
}
@keyframes clap {
    0%, 60%, 100% { transform: rotate(0deg); }
    75% { transform: rotate(-24deg); }
    82% { transform: rotate(0deg); }
}
</style>

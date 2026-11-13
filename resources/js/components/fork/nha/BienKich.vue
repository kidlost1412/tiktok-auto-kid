<script setup lang="ts">
// Phòng viết: Biên kịch (kính tròn, bút lông to) viết lời đọc.
import Ban from './Ban.vue';
import Chibi from './Chibi.vue';
import Den from './Den.vue';
import Phong from './Phong.vue';
import type { RoomProps } from './types';

defineProps<RoomProps>();
defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';
const books = [
    { x: 6, w: 7, h: 22, c: '#ff8fa3' },
    { x: 14, w: 6, h: 18, c: '#7fd1c1' },
    { x: 21, w: 8, h: 24, c: '#ffd36a' },
    { x: 30, w: 6, h: 19, c: '#a58bea' },
    { x: 37, w: 7, h: 22, c: '#6eb5f2' },
];
</script>

<template>
    <Phong
        id="bienkich" :x="x" :y="y" wall="#fff3da" wain="#f6ddb0" floor="#e9c79c" name="Phòng viết" emoji="✍️"
        label="Phòng viết, Biên kịch. Bấm để tới Prompt AI" :state="state" :dim="dim" :win="{ x: 14, y: 36, w: 42, h: 46 }"
        @go="$emit('go')" @hover="$emit('hover', $event)" @leave="$emit('leave')"
    >
        <template #wall>
            <!-- giá sách -->
            <g transform="translate(124 52)">
                <rect x="-3" y="-4" width="58" height="82" rx="5" fill="#c99464" :stroke="OUT" stroke-width="2" />
                <rect x="0" y="0" width="52" height="34" rx="2" fill="#f0cfa5" />
                <rect x="0" y="40" width="52" height="34" rx="2" fill="#f0cfa5" />
                <g transform="translate(0 34)">
                    <rect v-for="b in books" :key="b.x" :x="b.x" :y="-b.h" :width="b.w" :height="b.h" rx="1.5" :fill="b.c" :stroke="OUT" stroke-width="1.5" />
                </g>
                <g transform="translate(0 74)">
                    <rect v-for="(b, i) in books" :key="b.x" :x="b.x + 4" :y="-b.h + 4" :width="b.w" :height="b.h - 4" rx="1.5" :fill="books[(i + 2) % 5].c" :stroke="OUT" stroke-width="1.5" />
                    <circle cx="44" cy="-6" r="5" fill="#fff" :stroke="OUT" stroke-width="1.5" />
                </g>
                <rect x="-3" y="36" width="58" height="5" fill="#c99464" :stroke="OUT" stroke-width="1.6" />
            </g>
            <!-- ghim giấy -->
            <g transform="translate(70 30) rotate(-5)">
                <rect width="30" height="36" rx="2" fill="#fffdf6" :stroke="OUT" stroke-width="1.6" />
                <path d="M5 9h20M5 15h20M5 21h14" stroke="#c9b6ff" stroke-width="2" stroke-linecap="round" />
                <circle cx="15" cy="3" r="2.4" fill="#ff8fa3" :stroke="OUT" stroke-width="1" />
            </g>
        </template>

        <ellipse cx="94" cy="186" rx="62" ry="9" fill="#ff8fa3" opacity="0.3" />
        <g transform="translate(94 144) scale(1.15)">
            <Chibi :state="state" outfit="#6fcfb5" :mug="false" :delay="0.4">
                <template #behind>
                    <rect x="-25" y="-46" width="50" height="56" rx="14" fill="#a58bea" :stroke="OUT" stroke-width="2.2" />
                </template>
                <template #body>
                    <path d="M-10 -37 L0 -27 L10 -37" fill="#fff" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <circle cx="0" cy="-14" r="2" fill="#4a3868" />
                    <circle cx="0" cy="-5" r="2" fill="#4a3868" />
                </template>
                <template #hair-back>
                    <path d="M-32 -60 C-34 -90 -14 -98 0 -98 C14 -98 34 -90 32 -60 C32 -48 33 -40 26 -36 L-26 -36 C-33 -40 -32 -48 -32 -60 Z" fill="#8a5a3c" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hair-front>
                    <path d="M-28 -60 C-30 -90 30 -90 28 -60 C24 -72 16 -78 8 -75 C2 -72 -4 -77 -12 -74 C-20 -72 -25 -67 -28 -60 Z" fill="#9c6a47" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-16 -84 C-8 -88 4 -88 12 -85" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity="0.35" />
                </template>
                <template #face>
                    <g fill="#fff" fill-opacity="0.16" stroke="#8b5fbf" stroke-width="2.2">
                        <circle cx="-10.5" cy="-59" r="9" />
                        <circle cx="10.5" cy="-59" r="9" />
                    </g>
                    <path d="M-1.5 -60 H1.5 M-19.5 -60 L-26 -63 M19.5 -60 L26 -63" stroke="#8b5fbf" stroke-width="2" stroke-linecap="round" fill="none" />
                    <path d="M-15 -64 Q-12 -66 -8 -65" stroke="#fff" stroke-width="1.6" fill="none" stroke-linecap="round" opacity="0.9" />
                </template>
                <template #hand-r>
                    <!-- bút lông to -->
                    <path d="M50 -78 C65 -66 62 -42 40 -33 C30 -29 25 -25 20 -21 C25 -42 34 -62 50 -78 Z" fill="#c9b6ff" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <path d="M20 -21 C30 -40 40 -58 50 -78" fill="none" :stroke="OUT" stroke-width="2" stroke-linecap="round" />
                    <path d="M33 -48 L46 -50 M29 -40 L43 -42 M38 -58 L50 -62 M27 -33 L38 -34" stroke="#8b6fd6" stroke-width="1.6" stroke-linecap="round" />
                    <path d="M20 -21 L14 -11 L18 -13 Z" fill="#4a3868" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                </template>
            </Chibi>
        </g>
        <Ban :cx="94" :w="150" color="#c99464" top-color="#e6b88a" />
        <!-- giấy, lọ mực, đèn -->
        <g>
            <rect x="30" y="127" width="36" height="8" rx="2" fill="#fffdf6" :stroke="OUT" stroke-width="1.8" />
            <rect x="33" y="121" width="36" height="7" rx="2" fill="#fff" :stroke="OUT" stroke-width="1.8" transform="rotate(-4 51 124)" />
            <path d="M38 124h20" stroke="#c9b6ff" stroke-width="2" stroke-linecap="round" transform="rotate(-4 51 124)" />
            <path d="M138 134 v-9 q0 -3 3 -3 h8 q3 0 3 3 v9 Z" fill="#4a5fd6" :stroke="OUT" stroke-width="1.8" stroke-linejoin="round" />
            <rect x="141" y="118" width="8" height="5" rx="1.5" fill="#fff" :stroke="OUT" stroke-width="1.5" />
        </g>
        <Den :x="156" :y="134" :on="state === 'working'" flip />
        <!-- cây cảnh -->
        <g transform="translate(14 180)">
            <path d="M0 0 L-2 -16 H16 L14 0 Z" fill="#ff9f7a" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
            <path d="M7 -16 C-2 -30 -4 -40 4 -46 C6 -34 9 -28 7 -16 M7 -16 C16 -28 22 -34 18 -46 C8 -40 8 -28 7 -16" fill="#7bc67e" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
        </g>
    </Phong>
</template>

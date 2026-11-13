<script setup lang="ts">
// Kho hàng: Thủ kho (mũ lưỡi trai, yếm nâu, ria mép) sau quầy; giá có thùng, chai và cuộn phim.
import Ban from './Ban.vue';
import Chibi from './Chibi.vue';
import Phong from './Phong.vue';
import type { RoomProps } from './types';

defineProps<RoomProps>();
defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';
const bottles = ['#ff8fa3', '#7fd1c1', '#ffd36a', '#a58bea', '#6eb5f2', '#ff9f5a', '#7bc67e'];
</script>

<template>
    <Phong
        id="thukho" :x="x" :y="y" wall="#fff3e2" wain="#ecd0a4" floor="#dfc19a" name="Kho hàng" emoji="📦"
        label="Kho hàng, Thủ kho. Bấm để tới Sản phẩm và quà" :state="state" :dim="dim"
        @go="$emit('go')" @hover="$emit('hover', $event)" @leave="$emit('leave')"
    >
        <template #wall>
            <!-- ba tầng giá -->
            <g v-for="r in [0, 1, 2]" :key="r" :transform="`translate(6 ${44 + r * 36})`">
                <rect x="0" y="0" width="177" height="5" rx="2" fill="#b9824f" :stroke="OUT" stroke-width="1.8" />
            </g>
            <!-- tầng 1: thùng -->
            <g transform="translate(6 44)">
                <g v-for="(b, i) in [{ x: 4, w: 28, h: 24 }, { x: 36, w: 20, h: 17 }, { x: 118, w: 26, h: 22 }, { x: 148, w: 24, h: 26 }]" :key="i">
                    <rect :x="b.x" :y="-b.h" :width="b.w" :height="b.h" rx="2" fill="#e2b078" :stroke="OUT" stroke-width="1.8" />
                    <path :d="`M${b.x} ${-b.h + 6} H${b.x + b.w} M${b.x + b.w / 2 - 4} ${-b.h} v6 h8 v-6`" fill="#fff3c9" stroke="#4a3868" stroke-width="1.3" />
                </g>
            </g>
            <!-- tầng 2: chai lọ -->
            <g transform="translate(6 80)">
                <g v-for="(c, i) in bottles" :key="i">
                    <rect :x="6 + i * 8" y="-16" width="6.4" height="16" rx="2" :fill="c" :stroke="OUT" stroke-width="1.4" />
                    <rect :x="7.5 + i * 8" y="-20" width="3.4" height="5" rx="1" fill="#fffaf0" :stroke="OUT" stroke-width="1.1" />
                </g>
                <g v-for="(c, i) in bottles" :key="'r' + i">
                    <rect :x="126 + i * 8" y="-16" width="6.4" height="16" rx="2" :fill="bottles[(i + 3) % 7]" :stroke="OUT" stroke-width="1.4" />
                    <rect :x="127.5 + i * 8" y="-20" width="3.4" height="5" rx="1" fill="#fffaf0" :stroke="OUT" stroke-width="1.1" />
                </g>
            </g>
            <!-- tầng 3: cuộn phim -->
            <g transform="translate(6 116)">
                <g v-for="(c, i) in [14, 36, 140, 162]" :key="i" :transform="`translate(${c} -11)`">
                    <circle r="11" fill="#5c4a86" :stroke="OUT" stroke-width="1.8" />
                    <circle r="3.4" fill="#fff3c9" :stroke="OUT" stroke-width="1.2" />
                    <circle v-for="k in 5" :key="k" :cx="Math.cos((k * 2 * Math.PI) / 5) * 7" :cy="Math.sin((k * 2 * Math.PI) / 5) * 7" r="1.9" fill="#fff3c9" />
                </g>
            </g>
        </template>

        <ellipse cx="94" cy="186" rx="70" ry="9" fill="#c8955b" opacity="0.28" />
        <g transform="translate(94 144) scale(1.15)">
            <Chibi :state="state" outfit="#ffd66b" :mug="false" :delay="1.4" skin="#f7d1b3">
                <template #behind>
                    <rect x="-25" y="-46" width="50" height="56" rx="14" fill="#c8744a" :stroke="OUT" stroke-width="2.2" />
                </template>
                <template #body>
                    <path d="M-15 -30 H15 L17 4 H-17 Z" fill="#c8955b" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <path d="M-12 -37 L-14 -30 M12 -37 L14 -30" :stroke="OUT" stroke-width="6" stroke-linecap="round" />
                    <path d="M-12 -37 L-14 -30 M12 -37 L14 -30" stroke="#c8955b" stroke-width="3" stroke-linecap="round" />
                    <circle cx="-14" cy="-28" r="2.2" fill="#ffd66b" :stroke="OUT" stroke-width="1.4" />
                    <circle cx="14" cy="-28" r="2.2" fill="#ffd66b" :stroke="OUT" stroke-width="1.4" />
                    <rect x="-8" y="-20" width="16" height="9" rx="2.5" fill="#b3783f" :stroke="OUT" stroke-width="1.5" />
                </template>
                <template #hair-back>
                    <path d="M-29 -58 C-31 -64 -32 -52 -28 -46 L-26 -56 Z M29 -58 C31 -64 32 -52 28 -46 L26 -56 Z" fill="#7a4a2a" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                </template>
                <template #face>
                    <path d="M-9.5 -52.5 Q-4.5 -56.5 0 -52.5 Q4.5 -56.5 9.5 -52.5 Q4.5 -48.5 0 -50.5 Q-4.5 -48.5 -9.5 -52.5 Z" fill="#8a5a36" :stroke="OUT" stroke-width="1.6" stroke-linejoin="round" />
                </template>
                <template #hat>
                    <path d="M-27 -72 C-27 -100 27 -100 27 -72 Z" fill="#e8744f" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-24 -76 Q0 -70 24 -76 Q34 -74 38 -69 Q12 -62 -26 -68 Z" fill="#c95a38" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <circle cx="0" cy="-86" r="6" fill="#fff3c9" :stroke="OUT" stroke-width="1.6" />
                    <path d="M-3 -86 H3 M0 -89 V-83" stroke="#4a3868" stroke-width="1.6" stroke-linecap="round" />
                    <path d="M-18 -94 C-10 -99 6 -99 12 -96" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" opacity="0.45" />
                </template>
            </Chibi>
        </g>
        <Ban :cx="94" :w="164" color="#b9824f" top-color="#dba873" />
        <!-- hàng trên quầy -->
        <g>
            <g transform="translate(138 134)">
                <rect x="0" y="-22" width="26" height="22" rx="2.5" fill="#e2b078" :stroke="OUT" stroke-width="2" />
                <path d="M0 -15 H26 M9 -22 v7 h8 v-7" fill="#fff3c9" stroke="#4a3868" stroke-width="1.5" />
            </g>
            <g transform="translate(26 134)">
                <rect x="0" y="-19" width="22" height="19" rx="2" fill="#fffdf6" :stroke="OUT" stroke-width="2" transform="rotate(-6 11 -9)" />
                <path d="M4 -13 H18 M4 -8 H15" stroke="#a58bea" stroke-width="2" stroke-linecap="round" transform="rotate(-6 11 -9)" />
            </g>
        </g>
    </Phong>
</template>

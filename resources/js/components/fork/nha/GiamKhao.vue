<script setup lang="ts">
// Phòng chấm: Giám khảo (kính lúp, nơ đỏ), bảng điểm và các thẻ điểm trên bàn.
import Ban from './Ban.vue';
import Chibi from './Chibi.vue';
import Den from './Den.vue';
import Phong from './Phong.vue';
import type { RoomProps } from './types';

withDefaults(defineProps<RoomProps & { score?: string }>(), { score: '9' });
defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';
</script>

<template>
    <Phong
        id="giamkhao" :x="x" :y="y" wall="#f1eaff" wain="#d9c9f6" floor="#dcc5b0" name="Phòng chấm" emoji="🧐"
        label="Phòng chấm, Giám khảo. Bấm để tới Kho video" :state="state" :dim="dim"
        @go="$emit('go')" @hover="$emit('hover', $event)" @leave="$emit('leave')"
    >
        <template #wall>
            <!-- bảng điểm -->
            <g transform="translate(12 26)">
                <rect width="60" height="44" rx="5" fill="#3b3158" :stroke="OUT" stroke-width="2.2" />
                <text x="30" y="31" text-anchor="middle" font-size="26" font-weight="900" fill="#ffd36a">{{ score }}</text>
                <path d="M8 38 h44" stroke="#ffd36a" stroke-width="2" stroke-linecap="round" opacity="0.5" />
                <text x="46" y="14" font-size="10" fill="#fff" opacity="0.8">★</text>
                <text x="8" y="14" font-size="10" fill="#fff" opacity="0.8">★</text>
            </g>
            <!-- rèm + khung ảnh -->
            <g transform="translate(138 30)">
                <rect width="38" height="50" rx="4" fill="#fffaf0" :stroke="OUT" stroke-width="2" />
                <rect x="5" y="5" width="28" height="40" rx="2" fill="#cdbcf0" />
                <path d="M5 45 Q14 28 22 36 Q28 30 33 40 V45 Z" fill="#a58bea" />
                <circle cx="25" cy="16" r="5" fill="#fff" opacity="0.85" />
            </g>
        </template>

        <ellipse cx="94" cy="186" rx="62" ry="9" fill="#8b6bd9" opacity="0.22" />
        <g transform="translate(94 144) scale(1.15)">
            <Chibi :state="state" outfit="#8b6bd9" :mug="false" :delay="0.9" skin="#fbd9c0">
                <template #behind>
                    <rect x="-25" y="-46" width="50" height="56" rx="14" fill="#c14f6a" :stroke="OUT" stroke-width="2.2" />
                </template>
                <template #body>
                    <path d="M-9 -37 L0 -20 L9 -37" fill="#fff" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <path d="M-9 -37 L-16 -20 L-5 -12 L0 -20 Z M9 -37 L16 -20 L5 -12 L0 -20 Z" fill="#7a58c8" :stroke="OUT" stroke-width="1.8" stroke-linejoin="round" />
                    <path d="M0 -31 L-9 -35 V-27 Z M0 -31 L9 -35 V-27 Z" fill="#ff5d73" :stroke="OUT" stroke-width="1.6" stroke-linejoin="round" />
                    <circle cx="0" cy="-31" r="2.4" fill="#e0405a" :stroke="OUT" stroke-width="1.4" />
                </template>
                <template #hair-back>
                    <circle cx="0" cy="-94" r="11" fill="#d7d3e8" :stroke="OUT" stroke-width="2.2" />
                    <path d="M-30 -60 C-32 -86 32 -86 30 -60 L30 -48 L-30 -48 Z" fill="#d7d3e8" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hair-front>
                    <path d="M-28 -60 C-30 -88 30 -88 28 -60 C26 -72 14 -78 2 -76 C-10 -78 -24 -72 -28 -60 Z" fill="#e6e2f3" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-12 -82 C-4 -86 6 -85 12 -82" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity="0.7" />
                </template>
                <template #face>
                    <path d="M-17 -69 L-6 -66 M17 -69 L6 -66" stroke="#8a7fa8" stroke-width="3" stroke-linecap="round" />
                </template>
                <template #hand-r>
                    <g>
                        <path d="M17 -16 L34 -36" stroke="#4a3868" stroke-width="6" stroke-linecap="round" />
                        <path d="M17 -16 L34 -36" stroke="#c9966a" stroke-width="3" stroke-linecap="round" />
                        <circle cx="42" cy="-46" r="13" fill="#cfe9ff" fill-opacity="0.55" :stroke="OUT" stroke-width="3.2" />
                        <path d="M35 -50 Q38 -55 44 -55" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round" opacity="0.9" />
                    </g>
                </template>
            </Chibi>
        </g>
        <Ban :cx="94" :w="150" color="#9d86d6" top-color="#bfa9ee" />
        <!-- thẻ điểm -->
        <g>
            <g v-for="(p, i) in [{ n: '7', c: '#ffd36a', x: 30 }, { n: '8', c: '#7fd1c1', x: 52 }]" :key="i" :transform="`translate(${p.x} 134)`">
                <path d="M0 0 V-14" :stroke="OUT" stroke-width="2.4" stroke-linecap="round" />
                <circle cx="0" cy="-22" r="10" :fill="p.c" :stroke="OUT" stroke-width="2.2" />
                <text x="0" y="-17.5" text-anchor="middle" font-size="13" font-weight="900" :fill="OUT">{{ p.n }}</text>
            </g>
        </g>
        <Den :x="162" :y="134" :on="state === 'working'" flip color="#ffe08a" />
    </Phong>
</template>

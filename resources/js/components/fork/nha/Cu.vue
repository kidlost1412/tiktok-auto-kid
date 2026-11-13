<script setup lang="ts">
// Gác mái: Cú thông thái (kính, mũ cử nhân) bên bảng số liệu có cột nhảy.
import Phong from './Phong.vue';
import type { RoomProps } from './types';

defineProps<RoomProps>();
defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';
const bars = [
    { x: 6, h: 12, c: '#ff8fa3', d: 0 },
    { x: 18, h: 20, c: '#ffd36a', d: 0.3 },
    { x: 30, h: 16, c: '#7fd1c1', d: 0.6 },
    { x: 42, h: 26, c: '#a58bea', d: 0.9 },
];
</script>

<template>
    <Phong
        id="cu" :x="x" :y="y" :w="230" :h="100" wall="#efe6ff" wain="#d6c6f4" floor="#d9bf9a" name="Gác mái" emoji="📊"
        label="Gác mái, Cú thông thái. Bấm để tới Số liệu" :state="state" :dim="dim" :win="{ x: 14, y: 14, w: 30, h: 30 }"
        @go="$emit('go')" @hover="$emit('hover', $event)" @leave="$emit('leave')"
    >
        <template #wall>
            <!-- bảng số liệu -->
            <g transform="translate(150 12)">
                <rect width="68" height="50" rx="5" fill="#fffdf6" :stroke="OUT" stroke-width="2.2" />
                <path d="M7 12 H61" stroke="#c9b6ff" stroke-width="2" stroke-linecap="round" />
                <g transform="translate(8 44)">
                    <g v-for="b in bars" :key="b.x" :transform="`translate(${b.x} 0)`">
                        <rect class="bar" :class="{ going: state === 'working' }" :x="0" :y="-b.h" width="8" :height="b.h" rx="2" :fill="b.c" :stroke="OUT" stroke-width="1.5" :style="{ animationDelay: b.d + 's' }" />
                    </g>
                </g>
                <path d="M10 36 L26 26 L40 31 L58 17" fill="none" stroke="#e0405a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.8" />
            </g>
        </template>

        <ellipse cx="112" cy="80" rx="52" ry="6" fill="#4a3868" opacity="0.14" />
        <!-- sách chồng -->
        <g transform="translate(34 74)">
            <rect x="0" y="-8" width="30" height="8" rx="2" fill="#ff8fa3" :stroke="OUT" stroke-width="1.8" />
            <rect x="3" y="-15" width="26" height="7" rx="2" fill="#6eb5f2" :stroke="OUT" stroke-width="1.8" />
            <rect x="-1" y="-22" width="28" height="7" rx="2" fill="#ffd36a" :stroke="OUT" stroke-width="1.8" />
        </g>
        <!-- cành đậu -->
        <rect x="64" y="66" width="96" height="9" rx="4.5" fill="#b9824f" :stroke="OUT" stroke-width="2" />
        <path d="M70 70 h30 M118 70 h20" stroke="#fff" stroke-width="1.8" stroke-linecap="round" opacity="0.4" />
        <g transform="translate(112 68) scale(0.74)">
            <g :class="['nha-chibi', state === 'working' ? 'is-work' : state]" :style="{ '--d': '0.6s' }">
                <g class="nha-bob">
                    <!-- chân -->
                    <path d="M-9 -2 v6 M-12 5 h6 M9 -2 v6 M6 5 h6" stroke="#ff9f5a" stroke-width="3" stroke-linecap="round" fill="none" />
                    <!-- thân -->
                    <ellipse cx="0" cy="-26" rx="25" ry="28" fill="#8e7cc3" :stroke="OUT" stroke-width="2.4" />
                    <ellipse cx="0" cy="-18" rx="16" ry="20" fill="#d9ccf5" :stroke="OUT" stroke-width="1.8" />
                    <path d="M-9 -26 q4 4 8 0 M1 -26 q4 4 8 0 M-5 -17 q4 4 8 0 M-12 -10 q4 4 8 0 M0 -10 q4 4 8 0" fill="none" stroke="#a894dc" stroke-width="1.8" stroke-linecap="round" />
                    <!-- cánh -->
                    <ellipse :class="{ flap: state === 'working' }" cx="-24" cy="-24" rx="8" ry="18" fill="#7566b0" :stroke="OUT" stroke-width="2.2" transform="rotate(10 -24 -24)" style="transform-origin: -22px -38px" />
                    <ellipse :class="{ flap: state === 'working' }" cx="24" cy="-24" rx="8" ry="18" fill="#7566b0" :stroke="OUT" stroke-width="2.2" transform="rotate(-10 24 -24)" style="transform-origin: 22px -38px; animation-delay: 0.2s" />
                    <!-- đầu -->
                    <g class="nha-head" style="transform-origin: 0 -44px">
                        <path d="M-24 -66 L-30 -84 L-14 -74 Z M24 -66 L30 -84 L14 -74 Z" fill="#8e7cc3" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                        <ellipse cx="0" cy="-56" rx="28" ry="23" fill="#8e7cc3" :stroke="OUT" stroke-width="2.4" />
                        <ellipse cx="0" cy="-58" rx="25" ry="19" fill="url(#nha-face)" />
                        <g v-if="state !== 'sleep'" class="nha-eyes">
                            <circle cx="-12.5" cy="-57" r="11" fill="#fff" :stroke="OUT" stroke-width="2" />
                            <circle cx="12.5" cy="-57" r="11" fill="#fff" :stroke="OUT" stroke-width="2" />
                            <circle cx="-12" cy="-56.5" r="7" fill="#ffc83a" />
                            <circle cx="12" cy="-56.5" r="7" fill="#ffc83a" />
                            <circle cx="-12" cy="-56.5" r="3.6" fill="#3a2a57" />
                            <circle cx="12" cy="-56.5" r="3.6" fill="#3a2a57" />
                            <circle cx="-14" cy="-59" r="1.8" fill="#fff" />
                            <circle cx="10" cy="-59" r="1.8" fill="#fff" />
                        </g>
                        <g v-else fill="none" :stroke="OUT" stroke-width="2.4" stroke-linecap="round">
                            <path d="M-21 -57 Q-12.5 -51 -4 -57" />
                            <path d="M4 -57 Q12.5 -51 21 -57" />
                        </g>
                        <!-- kính -->
                        <g fill="none" stroke="#c0457c" stroke-width="2.2">
                            <circle cx="-12.5" cy="-57" r="12.6" />
                            <circle cx="12.5" cy="-57" r="12.6" />
                            <path d="M-0.5 -58 H0.5" />
                        </g>
                        <path d="M-4 -48 L0 -42 L4 -48 Z" fill="#ff9f5a" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                        <ellipse cx="-22" cy="-47" rx="4.4" ry="2.8" fill="#ff9db5" opacity="0.6" />
                        <ellipse cx="22" cy="-47" rx="4.4" ry="2.8" fill="#ff9db5" opacity="0.6" />
                        <!-- mũ cử nhân -->
                        <path d="M-27 -77 L0 -90 L27 -77 L0 -64 Z" fill="#3b3158" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                        <path d="M-14 -73 V-66 Q0 -60 14 -66 V-73" fill="#4d4175" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                        <path d="M22 -79 V-64" :stroke="OUT" stroke-width="2" />
                        <circle cx="22" cy="-62" r="3" fill="#ffd36a" :stroke="OUT" stroke-width="1.6" />
                    </g>
                    <g v-if="state === 'sleep'">
                        <text class="nha-zzz" x="26" y="-90">z</text>
                        <text class="nha-zzz z2" x="34" y="-98">z</text>
                        <text class="nha-zzz z3" x="42" y="-106">Z</text>
                    </g>
                </g>
            </g>
        </g>
    </Phong>
</template>

<style scoped>
.bar.going {
    transform-box: fill-box;
    transform-origin: 50% 100%;
    animation: barUp 1.6s ease-in-out infinite;
}
@keyframes barUp {
    0%, 100% { transform: scaleY(0.55); }
    50% { transform: scaleY(1.15); }
}
.flap {
    animation: flap 0.9s ease-in-out infinite;
}
@keyframes flap {
    0%, 100% { transform: rotate(0deg); }
    50% { transform: rotate(14deg); }
}
</style>

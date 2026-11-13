<script setup lang="ts">
// Nhân vật "chibi" dùng chung: đầu to, thân nhỏ, má hồng. Gốc toạ độ = giữa hông (y âm là hướng lên).
// Mỗi vai (Biên kịch, Thu âm...) bọc component này và thêm tóc/phụ kiện qua slot.
// state: working = gõ phím + đầu gật; idle = nhấp cà phê / vươn vai; sleep = ngủ gật.
import { computed } from 'vue';

const props = withDefaults(
    defineProps<{
        state?: 'working' | 'idle' | 'sleep';
        skin?: string;
        outfit: string;
        outfitDark?: string;
        blush?: string;
        delay?: number;
        stand?: boolean; // đứng (có chân), tay buông thay vì đặt lên bàn
        mug?: boolean; // idle: cầm cốc
        noType?: boolean; // working nhưng không gõ (vd. cầm bút)
        wave?: boolean; // working: giơ tay vẫy (bưu tá)
        mouth?: 'smile' | 'open' | 'flat';
        shoe?: string;
        pants?: string;
    }>(),
    { state: 'idle', skin: '#ffdcc4', outfitDark: '#4a3868', blush: '#ff9db5', delay: 0, stand: false, mug: true, noType: false, wave: false, mouth: 'smile', shoe: '#5a4a7a', pants: '#5b4b8a' },
);
const OUT = '#4a3868';
const cls = computed(() => ({ 'is-work': props.state === 'working', idle: props.state === 'idle', sleep: props.state === 'sleep', 'no-type': props.noType, wave: props.wave }));
const handY = computed(() => (props.stand ? -4 : -14));
const armL = computed(() => (props.stand ? 'M-18 -31 C-29 -20 -27 -10 -22 -4' : 'M-18 -31 C-30 -22 -26 -14 -15 -14'));
const armR = computed(() => (props.stand ? 'M18 -31 C29 -20 27 -10 22 -4' : 'M18 -31 C30 -22 26 -14 15 -14'));
const handLx = computed(() => (props.stand ? -22 : -15));
const handRx = computed(() => (props.stand ? 22 : 15));
</script>

<template>
    <g :class="['nha-chibi', cls]" :style="{ '--d': `${delay}s` }">
        <!-- bóng dưới chân/ghế -->
        <slot name="behind" />
        <g class="nha-bob">
            <!-- chân (đứng) -->
            <g v-if="stand">
                <rect x="-14" y="2" width="11" height="22" rx="5" :fill="pants" :stroke="OUT" stroke-width="2" />
                <rect x="3" y="2" width="11" height="22" rx="5" :fill="pants" :stroke="OUT" stroke-width="2" />
                <ellipse cx="-9.5" cy="26" rx="9" ry="4.6" :fill="shoe" :stroke="OUT" stroke-width="2" />
                <ellipse cx="9.5" cy="26" rx="9" ry="4.6" :fill="shoe" :stroke="OUT" stroke-width="2" />
            </g>
            <!-- thân -->
            <path d="M-21 4 C-24 -18 -19 -34 -9 -37 Q0 -40 9 -37 C19 -34 24 -18 21 4 Z" :fill="outfit" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
            <path d="M-21 4 C-24 -18 -19 -34 -9 -37 Q0 -40 9 -37 C19 -34 24 -18 21 4 Z" fill="url(#nha-shade)" opacity="0.55" />
            <path d="M-17 -26 C-16 -31 -13 -34 -9 -35" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" opacity="0.4" />
            <slot name="body" />
            <!-- cổ -->
            <rect x="-5.5" y="-43" width="11" height="9" rx="4" :fill="skin" :stroke="OUT" stroke-width="2" />
            <g class="nha-head">
                <slot name="hair-back" />
                <circle cx="-26.5" cy="-59" r="4.6" :fill="skin" :stroke="OUT" stroke-width="2" />
                <circle cx="26.5" cy="-59" r="4.6" :fill="skin" :stroke="OUT" stroke-width="2" />
                <ellipse cx="0" cy="-61" rx="27" ry="24.5" :fill="skin" :stroke="OUT" stroke-width="2.2" />
                <ellipse cx="0" cy="-61" rx="27" ry="24.5" fill="url(#nha-face)" />
                <slot name="hair-front" />
                <!-- mắt -->
                <g v-if="state !== 'sleep'" class="nha-eyes">
                    <ellipse cx="-10.5" cy="-59" rx="4.6" ry="6" fill="#3a2a57" />
                    <ellipse cx="10.5" cy="-59" rx="4.6" ry="6" fill="#3a2a57" />
                    <circle cx="-12" cy="-61.5" r="2" fill="#fff" />
                    <circle cx="9" cy="-61.5" r="2" fill="#fff" />
                    <circle cx="-9" cy="-56.5" r="0.9" fill="#fff" opacity="0.85" />
                    <circle cx="12" cy="-56.5" r="0.9" fill="#fff" opacity="0.85" />
                </g>
                <g v-else fill="none" :stroke="OUT" stroke-width="2.2" stroke-linecap="round">
                    <path d="M-15 -59 Q-10.5 -55 -6 -59" />
                    <path d="M6 -59 Q10.5 -55 15 -59" />
                </g>
                <ellipse cx="-17.5" cy="-51" rx="5.2" ry="3.3" :fill="blush" opacity="0.62" />
                <ellipse cx="17.5" cy="-51" rx="5.2" ry="3.3" :fill="blush" opacity="0.62" />
                <path v-if="state === 'sleep'" d="M-2.4 -49.5 a2.4 2.6 0 1 0 4.8 0 a2.4 2.6 0 1 0 -4.8 0" fill="#e8798f" :stroke="OUT" stroke-width="1.4" />
                <path v-else-if="mouth === 'open'" d="M-3.4 -50 Q0 -44.5 3.4 -50 Q0 -48.4 -3.4 -50 Z" fill="#e8798f" :stroke="OUT" stroke-width="1.6" stroke-linejoin="round" />
                <path v-else d="M-3.6 -49.6 Q0 -45.6 3.6 -49.6" fill="none" :stroke="OUT" stroke-width="1.9" stroke-linecap="round" />
                <slot name="face" />
                <slot name="hat" />
            </g>
            <!-- tay -->
            <g class="nha-arm-l">
                <path :d="armL" fill="none" :stroke="OUT" stroke-width="12" stroke-linecap="round" />
                <path :d="armL" fill="none" :stroke="outfit" stroke-width="8.2" stroke-linecap="round" />
                <circle :cx="handLx" :cy="handY" r="5" :fill="skin" :stroke="OUT" stroke-width="1.9" />
                <slot name="hand-l" />
            </g>
            <g class="nha-arm-r">
                <path :d="armR" fill="none" :stroke="OUT" stroke-width="12" stroke-linecap="round" />
                <path :d="armR" fill="none" :stroke="outfit" stroke-width="8.2" stroke-linecap="round" />
                <circle :cx="handRx" :cy="handY" r="5" :fill="skin" :stroke="OUT" stroke-width="1.9" />
                <g v-if="state === 'idle' && mug && !stand" :transform="`translate(${handRx + 6.5} ${handY - 3})`">
                    <path d="M7.5 1.5 q5 0 5 4 q0 4 -5 4" fill="none" stroke="#4a3868" stroke-width="2.2" stroke-linecap="round" />
                    <rect x="-6" y="-2" width="14" height="13" rx="3.4" fill="#fffaf0" :stroke="OUT" stroke-width="2" />
                    <rect x="-4" y="0" width="10" height="3.4" rx="1.6" fill="#9a6a4a" />
                    <path d="M-1 -5 q-2 -3 0 -5 M3 -5 q-2 -3 0 -5" fill="none" stroke="#b9a8da" stroke-width="1.5" stroke-linecap="round" opacity="0.8" />
                </g>
                <slot name="hand-r" />
            </g>
            <g v-if="state === 'sleep'" class="nha-zzzs">
                <text class="nha-zzz" x="14" y="-92">z</text>
                <text class="nha-zzz z2" x="22" y="-100">z</text>
                <text class="nha-zzz z3" x="30" y="-108">Z</text>
            </g>
        </g>
    </g>
</template>

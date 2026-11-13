<script setup lang="ts">
// Phòng thu: Thu âm (tai nghe to, micro có màng lọc, tường tiêu âm, biển ON AIR).
import Ban from './Ban.vue';
import Chibi from './Chibi.vue';
import Phong from './Phong.vue';
import type { RoomProps } from './types';

defineProps<RoomProps>();
defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';
</script>

<template>
    <Phong
        id="thuam" :x="x" :y="y" wall="#ffe9f2" wain="#f9c9da" floor="#e6c6b0" name="Phòng thu" emoji="🎙️"
        label="Phòng thu, Thu âm. Bấm để tới Cài đặt giọng đọc" :state="state" :dim="dim"
        @go="$emit('go')" @hover="$emit('hover', $event)" @leave="$emit('leave')"
    >
        <template #wall>
            <defs>
                <pattern id="nha-foam" width="14" height="14" patternUnits="userSpaceOnUse">
                    <rect width="14" height="14" fill="#8c79bf" />
                    <path d="M0 14 L7 1 L14 14 Z" fill="#a592d6" stroke="#6d5aa3" stroke-width="1" />
                </pattern>
            </defs>
            <rect x="8" y="26" width="70" height="98" rx="5" fill="url(#nha-foam)" :stroke="OUT" stroke-width="2" />
            <rect x="8" y="26" width="70" height="98" rx="5" fill="url(#nha-shade)" opacity="0.25" />
            <!-- ON AIR -->
            <g transform="translate(158 50)">
                <rect width="27" height="34" rx="6" :fill="state === 'working' ? '#ff5d73' : '#9b5a6a'" :stroke="OUT" stroke-width="2" :class="{ 'nha-led': state === 'working' }" />
                <text x="13.5" y="15" text-anchor="middle" font-size="9.5" font-weight="800" fill="#fff">ON</text>
                <text x="13.5" y="27.5" text-anchor="middle" font-size="9.5" font-weight="800" fill="#fff">AIR</text>
            </g>
        </template>

        <ellipse cx="112" cy="186" rx="60" ry="9" fill="#a58bea" opacity="0.28" />
        <g transform="translate(112 144) scale(1.15)">
            <Chibi :state="state" outfit="#ff8fa3" :mug="false" :delay="1.1" mouth="open">
                <template #behind>
                    <rect x="-25" y="-46" width="50" height="56" rx="14" fill="#7e6bb0" :stroke="OUT" stroke-width="2.2" />
                </template>
                <template #body>
                    <path d="M-15 -37 Q0 -24 15 -37" fill="#ff7a96" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <path d="M-5 -28 V-12 M5 -28 V-14" :stroke="OUT" stroke-width="2" stroke-linecap="round" />
                    <circle cx="-5" cy="-10" r="2.2" fill="#fff" :stroke="OUT" stroke-width="1.4" />
                    <circle cx="5" cy="-12" r="2.2" fill="#fff" :stroke="OUT" stroke-width="1.4" />
                </template>
                <template #hair-back>
                    <path d="M-31 -60 C-33 -88 33 -88 31 -60 L31 -48 L24 -54 L-24 -54 L-31 -48 Z" fill="#3b3358" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hair-front>
                    <path d="M-28 -62 C-31 -92 32 -91 28 -62 C26 -74 18 -81 4 -79 C-6 -77 -16 -72 -28 -62 Z" fill="#4b4170" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-14 -85 C-6 -89 6 -89 14 -84" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity="0.3" />
                </template>
                <template #hat>
                    <path d="M-33 -62 C-36 -108 36 -108 33 -62" fill="none" :stroke="OUT" stroke-width="8.5" stroke-linecap="round" />
                    <path d="M-33 -62 C-36 -108 36 -108 33 -62" fill="none" stroke="#b79cf0" stroke-width="4.6" stroke-linecap="round" />
                    <path d="M-24 -90 C-12 -98 10 -98 18 -94" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="0.55" />
                    <g v-for="s in [-1, 1]" :key="s">
                        <ellipse :cx="s * 33" cy="-60" rx="9" ry="12.5" fill="#9b7bea" :stroke="OUT" stroke-width="2.2" />
                        <ellipse :cx="s * 34" cy="-60" rx="5" ry="8.6" fill="#c9b6ff" />
                        <path :d="`M${s * 31} -68 Q${s * 33} -71 ${s * 36} -68`" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="0.7" />
                    </g>
                </template>
            </Chibi>
        </g>
        <!-- micro trên giá -->
        <g>
            <ellipse cx="38" cy="182" rx="17" ry="4.5" fill="#6d5aa3" :stroke="OUT" stroke-width="2" />
            <path d="M38 180 V98 Q38 88 52 86" fill="none" :stroke="OUT" stroke-width="6" stroke-linecap="round" />
            <path d="M38 180 V98 Q38 88 52 86" fill="none" stroke="#b7a5e3" stroke-width="2.6" stroke-linecap="round" />
            <circle cx="64" cy="86" r="12.5" fill="#6d5aa3" fill-opacity="0.45" :stroke="OUT" stroke-width="2.4" />
            <circle cx="64" cy="86" r="8" fill="#463a73" :stroke="OUT" stroke-width="1.6" />
            <path d="M58 82 Q62 79 66 80" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" opacity="0.6" />
            <g v-if="state === 'working'" fill="none" stroke="#a58bea" stroke-width="2.4" stroke-linecap="round" class="nha-led">
                <path d="M81 79 Q85 86 81 93" />
                <path d="M86 74 Q93 86 86 98" />
            </g>
        </g>
        <Ban :cx="118" :w="120" color="#d77c93" top-color="#f4a3b6" />
        <!-- bàn trộn âm -->
        <g>
            <rect x="96" y="122" width="52" height="13" rx="3" fill="#463a73" :stroke="OUT" stroke-width="2" />
            <circle v-for="i in 4" :key="i" :cx="102 + i * 9" cy="127" r="2.4" :fill="['#ff8fa3', '#ffd36a', '#7fd1c1', '#c9b6ff'][i - 1]" />
            <path d="M104 132 h38" stroke="#c9b6ff" stroke-width="1.6" stroke-linecap="round" />
        </g>
    </Phong>
</template>

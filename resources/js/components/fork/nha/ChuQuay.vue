<script setup lang="ts">
// Quầy giỏ hàng: Chủ quầy (tạp dề xanh, đuôi ngựa) sau quầy có máy tính tiền, xe đẩy hàng, mái hiên sọc.
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
        id="chuquay" :x="x" :y="y" wall="#e6f7f1" wain="#bfe8d6" floor="#dfc9a6" name="Quầy giỏ hàng" emoji="🛒"
        label="Quầy giỏ hàng, Chủ quầy. Bấm để tới Giỏ hàng" :state="state" :dim="dim"
        @go="$emit('go')" @hover="$emit('hover', $event)" @leave="$emit('leave')"
    >
        <template #wall>
            <!-- mái hiên sọc -->
            <g transform="translate(0 14)">
                <g v-for="i in 8" :key="i">
                    <path :d="`M${(i - 1) * 23.6} 0 H${i * 23.6} V14 A11.8 11.8 0 0 1 ${(i - 1) * 23.6} 14 Z`" :fill="i % 2 ? '#ff7a8a' : '#fff'" :stroke="OUT" stroke-width="1.8" stroke-linejoin="round" />
                </g>
            </g>
            <!-- kệ nhỏ -->
            <g transform="translate(128 74)">
                <rect x="0" y="22" width="52" height="5" rx="2" fill="#b9824f" :stroke="OUT" stroke-width="1.8" />
                <rect x="4" y="6" width="12" height="16" rx="3" fill="#ffb86b" :stroke="OUT" stroke-width="1.6" />
                <rect x="20" y="2" width="12" height="20" rx="3" fill="#a58bea" :stroke="OUT" stroke-width="1.6" />
                <rect x="36" y="8" width="12" height="14" rx="3" fill="#7fd1c1" :stroke="OUT" stroke-width="1.6" />
                <rect x="0" y="-12" width="52" height="5" rx="2" fill="#b9824f" :stroke="OUT" stroke-width="1.8" />
                <circle cx="12" cy="-18" r="6" fill="#ff8fa3" :stroke="OUT" stroke-width="1.6" />
                <rect x="28" y="-24" width="14" height="12" rx="2" fill="#6eb5f2" :stroke="OUT" stroke-width="1.6" />
            </g>
            <g transform="translate(14 64)">
                <rect width="32" height="26" rx="4" fill="#fff" :stroke="OUT" stroke-width="1.8" />
                <text x="16" y="17" text-anchor="middle" font-size="11" font-weight="900" fill="#ff5d73">SALE</text>
            </g>
        </template>

        <ellipse cx="94" cy="186" rx="76" ry="9" fill="#5fb89a" opacity="0.25" />
        <g transform="translate(96 144) scale(1.15)">
            <Chibi :state="state" outfit="#6eb5f2" :mug="false" :delay="2.1" skin="#fbd8bf">
                <template #behind>
                    <rect x="-25" y="-46" width="50" height="56" rx="14" fill="#f2a36b" :stroke="OUT" stroke-width="2.2" />
                </template>
                <template #body>
                    <path d="M-15 -37 Q0 -27 15 -37 L15 -30 H-15 Z" fill="#fff" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <rect x="-9" y="-14" width="18" height="11" rx="3" fill="#4f9be0" :stroke="OUT" stroke-width="1.6" />
                    <path d="M-14 -30 L-12 -37 M14 -30 L12 -37" :stroke="OUT" stroke-width="2" stroke-linecap="round" />
                </template>
                <template #hair-back>
                    <path d="M26 -72 C50 -74 54 -50 44 -32 C42 -44 36 -52 27 -56 Z" fill="#f2c66d" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-29 -60 C-31 -86 31 -86 29 -60 L29 -50 L-29 -50 Z" fill="#f2c66d" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hair-front>
                    <path d="M-28 -60 C-30 -90 30 -90 28 -60 C26 -72 18 -77 10 -73 C4 -70 -6 -77 -14 -73 C-22 -70 -26 -66 -28 -60 Z" fill="#f7d283" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-14 -84 C-6 -88 6 -88 13 -84" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity="0.45" />
                </template>
                <template #hat>
                    <circle cx="29" cy="-70" r="4.6" fill="#ff7a8a" :stroke="OUT" stroke-width="1.8" />
                </template>
            </Chibi>
        </g>
        <Ban :cx="96" :w="146" color="#ffb86b" top-color="#ffd9a0" />
        <!-- máy tính tiền -->
        <g transform="translate(124 134)">
            <rect x="0" y="-14" width="32" height="14" rx="3" fill="#4f9be0" :stroke="OUT" stroke-width="2" />
            <rect x="3" y="-26" width="22" height="13" rx="2" fill="#2f2b52" :stroke="OUT" stroke-width="1.8" />
            <text x="14" y="-16" text-anchor="middle" font-size="8" font-weight="800" fill="#7fe8b0">12k</text>
            <circle v-for="i in 4" :key="i" :cx="5 + i * 6" cy="-6" r="1.8" fill="#fff" />
        </g>
        <!-- xe đẩy hàng -->
        <g transform="translate(6 180)">
            <path d="M-2 -58 H8 L14 -30" fill="none" :stroke="OUT" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M-2 -58 H8 L14 -30" fill="none" stroke="#c9d2de" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M12 -38 H54 L48 -12 H18 Z" fill="#d8e4f0" fill-opacity="0.75" :stroke="OUT" stroke-width="2.4" stroke-linejoin="round" />
            <path d="M14 -30 H52 M16 -22 H50 M26 -38 L28 -12 M38 -38 L38 -12" stroke="#4a3868" stroke-opacity="0.5" stroke-width="1.4" />
            <rect x="22" y="-52" width="14" height="14" rx="2.5" fill="#ff8fa3" :stroke="OUT" stroke-width="1.8" />
            <path d="M40 -38 C38 -52 52 -52 50 -38 Z" fill="#7bc67e" :stroke="OUT" stroke-width="1.8" stroke-linejoin="round" />
            <circle cx="22" cy="-4" r="5" fill="#5c4a86" :stroke="OUT" stroke-width="1.8" />
            <circle cx="46" cy="-4" r="5" fill="#5c4a86" :stroke="OUT" stroke-width="1.8" />
            <path d="M22 -9 L18 -12 M46 -9 L48 -12" :stroke="OUT" stroke-width="2" />
        </g>
    </Phong>
</template>

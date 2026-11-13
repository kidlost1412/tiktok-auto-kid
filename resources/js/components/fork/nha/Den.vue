<script setup lang="ts">
// Đèn bàn: chân tại (x, y) = mặt bàn. on = bật sáng (toả quầng ấm lên tường).
withDefaults(defineProps<{ x: number; y: number; on?: boolean; color?: string; flip?: boolean }>(), { on: false, color: '#ffd36a', flip: false });
</script>

<template>
    <g :transform="`translate(${x} ${y}) scale(${flip ? -1 : 1} 1)`">
        <g v-if="on" class="nha-glow">
            <ellipse cx="14" cy="-30" rx="40" ry="34" fill="url(#nha-lamp)" />
        </g>
        <ellipse cx="0" cy="-1" rx="10" ry="3.2" fill="#6d5a9a" stroke="#4a3868" stroke-width="1.8" />
        <path d="M0 -2 L0 -22 L12 -38" fill="none" stroke="#4a3868" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />
        <path d="M0 -2 L0 -22 L12 -38" fill="none" stroke="#9a86d4" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
        <path d="M3 -36 L22 -42 L26 -30 L8 -26 Z" :fill="on ? color : '#d9d0ec'" stroke="#4a3868" stroke-width="2" stroke-linejoin="round" />
        <path d="M6 -34 L18 -38" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="0.7" />
    </g>
</template>

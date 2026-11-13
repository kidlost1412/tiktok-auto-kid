<script setup lang="ts">
// Bàn làm việc: mặt bàn + thân bàn có ngăn kéo, đổ bóng xuống sàn. cx = tâm, top = mép trên mặt bàn, floorY = mặt sàn.
withDefaults(defineProps<{ cx: number; w: number; top?: number; floorY?: number; color?: string; topColor?: string }>(), {
    top: 134,
    floorY: 180,
    color: '#c9966a',
    topColor: '#e6b88a',
});
</script>

<template>
    <g>
        <ellipse :cx="cx" :cy="floorY + 3" :rx="w / 2 + 6" ry="5" fill="#4a3868" opacity="0.16" />
        <rect :x="cx - w / 2 + 6" :y="top + 6" :width="w - 12" :height="floorY - top - 6" rx="4" :fill="color" stroke="#4a3868" stroke-width="2" />
        <rect :x="cx - w / 2 + 6" :y="top + 6" :width="w - 12" :height="floorY - top - 6" rx="4" fill="url(#nha-shade)" opacity="0.5" />
        <rect :x="cx - w / 2 + 14" :y="top + 16" :width="w - 28" height="14" rx="3" fill="#fff" opacity="0.18" stroke="#4a3868" stroke-opacity="0.5" stroke-width="1.4" />
        <rect :x="cx - 6" :y="top + 21" width="12" height="4" rx="2" fill="#4a3868" opacity="0.7" />
        <rect :x="cx - w / 2" :y="top" :width="w" height="9" rx="4" :fill="topColor" stroke="#4a3868" stroke-width="2" />
        <path :d="`M${cx - w / 2 + 6} ${top + 3} H${cx + w / 2 - 6}`" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="0.55" />
    </g>
</template>

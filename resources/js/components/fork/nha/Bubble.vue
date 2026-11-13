<script setup lang="ts">
// Bong bóng lời nói trong toạ độ cả ngôi nhà. (x, y) = đầu nhọn của đuôi bong bóng (ngay trên đầu nhân vật).
import { computed } from 'vue';

const props = withDefaults(defineProps<{ x: number; y: number; text: string; max?: number; vw?: number }>(), { max: 21, vw: 1000 });

const lines = computed(() => {
    const out: string[] = [];
    let cur = '';
    for (const w of props.text.split(/\s+/).filter(Boolean)) {
        if ((cur + ' ' + w).trim().length > props.max && cur) {
            out.push(cur);
            cur = w;
        } else {
            cur = (cur + ' ' + w).trim();
        }
    }
    if (cur) {
        out.push(cur);
    }

    return out.slice(0, 3);
});
const W = computed(() => Math.max(46, Math.max(...lines.value.map((l) => l.length)) * 6.5 + 20));
const H = computed(() => lines.value.length * 15 + 11);
const bx = computed(() => Math.min(Math.max(props.x - W.value / 2, 6), props.vw - 6 - W.value));
const by = computed(() => props.y - 9 - H.value);
const tailX = computed(() => Math.min(Math.max(props.x, bx.value + 14), bx.value + W.value - 14));
</script>

<template>
    <g class="nha-bubble" aria-hidden="true">
        <rect :x="bx + 1.5" :y="by + 3" :width="W" :height="H" rx="11" fill="#4a3868" opacity="0.18" />
        <path :d="`M${tailX - 6} ${by + H - 1} L${props.x} ${props.y} L${tailX + 6} ${by + H - 1} Z`" fill="#fff" stroke="#4a3868" stroke-width="2" stroke-linejoin="round" />
        <rect :x="bx" :y="by" :width="W" :height="H" rx="11" fill="#fff" stroke="#4a3868" stroke-width="2" />
        <path :d="`M${tailX - 4.5} ${by + H} H${tailX + 4.5}`" stroke="#fff" stroke-width="3" />
        <text v-for="(l, i) in lines" :key="i" :x="bx + W / 2" :y="by + 17 + i * 15" text-anchor="middle" font-size="12" font-weight="700" fill="#4a3868">{{ l }}</text>
    </g>
</template>

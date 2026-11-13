<script setup lang="ts">
// Một căn phòng trong nhà cắt ngang: tường, sàn, cửa sổ + vùng bấm được (chuột, bàn phím).
// Toạ độ trong phòng: rộng w, cao h; sàn ở y = h - 26. Nội dung (bàn, nhân vật) đưa vào slot mặc định.
import { computed } from 'vue';

const props = withDefaults(
    defineProps<{
        id: string;
        x: number;
        y: number;
        w?: number;
        h?: number;
        wall: string;
        wain: string;
        floor?: string;
        name: string; // "Phòng viết"
        emoji?: string;
        label: string; // aria-label đầy đủ
        state?: 'working' | 'idle' | 'sleep';
        dim?: boolean;
        win?: { x: number; y: number; w: number; h: number } | null;
        link?: boolean; // false: chỉ trang trí, không bấm
    }>(),
    { w: 189, h: 206, floor: '#e7c7a0', state: 'idle', dim: false, win: null, link: true, emoji: '' },
);
defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const floorY = computed(() => props.h - 26);
const plate = computed(() => `${props.emoji} ${props.name}`.trim());
const plateW = computed(() => Math.min(props.w - 14, plate.value.length * 6.4 + 18));
</script>

<template>
    <g
        :class="['nha-phong', { lit: state === 'working', dim }]"
        :transform="`translate(${x} ${y})`"
        :tabindex="link ? 0 : undefined"
        :role="link ? 'link' : undefined"
        :aria-label="link ? label : undefined"
        @click="link && $emit('go')"
        @keydown.enter.prevent="link && $emit('go')"
        @keydown.space.prevent="link && $emit('go')"
        @mouseenter="link && $emit('hover', id)"
        @mouseleave="$emit('leave')"
        @focus="link && $emit('hover', id)"
        @blur="$emit('leave')"
    >
        <defs>
            <clipPath :id="`nha-c-${id}`"><rect :width="w" :height="h" rx="9" /></clipPath>
        </defs>
        <g :clip-path="`url(#nha-c-${id})`">
            <rect :width="w" :height="h" :fill="wall" />
            <rect :width="w" :height="h" fill="url(#nha-dots)" opacity="0.55" />
            <rect :y="floorY - 46" :width="w" :height="46" :fill="wain" />
            <rect :y="floorY - 48" :width="w" height="4" fill="#fff" opacity="0.55" />
            <!-- cửa sổ -->
            <g v-if="win">
                <rect :x="win.x - 4" :y="win.y - 4" :width="win.w + 8" :height="win.h + 8" rx="6" fill="#fffaf3" stroke="#4a3868" stroke-width="2" />
                <rect class="nha-win" :x="win.x" :y="win.y" :width="win.w" :height="win.h" rx="3" />
                <rect :x="win.x" :y="win.y" :width="win.w" :height="win.h * 0.45" rx="3" fill="url(#nha-pane)" opacity="0.7" />
                <path :d="`M${win.x + win.w / 2} ${win.y} V${win.y + win.h} M${win.x} ${win.y + win.h / 2} H${win.x + win.w}`" stroke="#4a3868" stroke-width="2" />
                <path :d="`M${win.x + 3} ${win.y + win.h - 7} l9 -9`" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="0.7" />
                <rect :x="win.x - 7" :y="win.y + win.h + 3" :width="win.w + 14" height="5" rx="2.5" fill="#d9b88c" stroke="#4a3868" stroke-width="1.6" />
            </g>
            <slot name="wall" />
            <!-- sàn -->
            <rect :y="floorY" :width="w" :height="h - floorY" :fill="floor" />
            <path :d="`M0 ${floorY + 9} H${w} M0 ${floorY + 18} H${w}`" stroke="#4a3868" stroke-opacity="0.14" stroke-width="1.4" />
            <rect :y="floorY - 5" :width="w" height="6" fill="#fff" opacity="0.7" />
            <rect :y="floorY - 5" :width="w" height="6" fill="none" />
            <slot />
            <rect :width="w" height="12" fill="url(#nha-ceil)" />
            <rect class="night" :width="w" :height="h" />
            <rect class="warm" :width="w" :height="h" fill="url(#nha-warm)" />
            <rect class="hoverglow" :width="w" :height="h" />
        </g>
        <rect :width="w" :height="h" rx="9" fill="none" stroke="#4a3868" stroke-opacity="0.55" stroke-width="2" />
        <rect class="ring" :x="-2" :y="-2" :width="w + 4" :height="h + 4" rx="11" />
        <!-- biển tên (ở chân phòng để bong bóng lời nói không che) -->
        <g :transform="`translate(8 ${h - 19})`">
            <rect :width="plateW" height="17" rx="8.5" fill="#4a3868" opacity="0.92" />
            <text :x="plateW / 2" y="12.2" text-anchor="middle" font-size="10.5" font-weight="700" fill="#fff" style="letter-spacing: 0.1px">{{ plate }}</text>
        </g>
        <!-- vùng bấm phủ cả phòng -->
        <rect :width="w" :height="h" fill="transparent" />
    </g>
</template>

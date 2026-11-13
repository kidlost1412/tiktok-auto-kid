<script setup lang="ts">
// Sảnh: bảng trắng ghi lô đang làm (sản phẩm, tiến độ, dòng trạng thái) theo dữ liệu thật.
import { computed } from 'vue';

import Phong from './Phong.vue';
import type { NhaData, RoomProps } from './types';

const props = defineProps<RoomProps & { bang?: NhaData['bang'] | null; mode?: NhaData['mode'] }>();
defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';

const cut = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s);
const title = computed(() => cut(props.bang?.san_pham ?? 'Chưa có lô nào', 19));
const pct = computed(() => {
    const t = props.bang?.tien_do;

    return t && t.tong > 0 ? Math.min(1, t.xong / t.tong) : 0;
});
const label = computed(() => {
    const t = props.bang?.tien_do;

    return t && t.tong > 0 ? `${t.xong}/${t.tong} video` : 'Nghỉ ngơi';
});
const lines = computed(() => {
    const words = (props.bang?.dong ?? '').split(/\s+/).filter(Boolean);
    const out: string[] = [];
    let cur = '';
    for (const w of words) {
        if ((cur + ' ' + w).trim().length > 27 && cur) {
            out.push(cur);
            cur = w;
        } else {
            cur = (cur + ' ' + w).trim();
        }
    }
    if (cur) {
        out.push(cur);
    }
    const r = out.slice(0, 2);
    if (out.length > 2) {
        r[1] = cut(r[1] + '…', 27);
    }

    return r;
});
const warn = computed(() => props.mode === 'limit');
</script>

<template>
    <Phong
        id="bang" :x="x" :y="y" wall="#fdf1ff" wain="#e8d3f3" floor="#dcc6b4" name="Sảnh" emoji="📋"
        label="Bảng theo dõi lô đang làm. Bấm để tới Sản xuất" :state="state" :dim="dim"
        @go="$emit('go')" @hover="$emit('hover', $event)" @leave="$emit('leave')"
    >
        <template #wall>
            <g transform="translate(10 22)">
                <rect width="169" height="108" rx="7" fill="#fffefb" :stroke="OUT" stroke-width="2.6" />
                <rect x="4" y="4" width="161" height="100" rx="4" fill="none" stroke="#dcd1f0" stroke-width="1.5" />
                <rect x="0" y="108" width="169" height="7" rx="3" fill="#c9b6ff" :stroke="OUT" stroke-width="2" />
                <rect x="104" y="106" width="22" height="6" rx="3" fill="#ff8fa3" :stroke="OUT" stroke-width="1.4" />
                <rect x="130" y="106" width="22" height="6" rx="3" fill="#6eb5f2" :stroke="OUT" stroke-width="1.4" />
                <text x="12" y="19" font-size="8.5" font-weight="800" fill="#9a86d4" style="letter-spacing: 1px">BẢNG VIỆC</text>
                <text x="12" y="38" font-size="14" font-weight="800" :fill="OUT">{{ title }}</text>
                <rect x="12" y="46" width="145" height="12" rx="6" fill="#efe9fb" :stroke="OUT" stroke-width="1.6" />
                <rect v-if="pct > 0" x="12" y="46" :width="Math.max(12, 145 * pct)" height="12" rx="6" :fill="warn ? '#ff9f5a' : '#7fd1c1'" :stroke="OUT" stroke-width="1.6" />
                <text x="12" y="76" font-size="13" font-weight="800" :fill="warn ? '#d9543a' : '#6b4fc0'">{{ label }}</text>
                <text v-for="(l, i) in lines" :key="i" x="12" :y="90 + i * 12" font-size="9.5" font-weight="600" :fill="warn ? '#c2412d' : '#5a4a7a'">{{ l }}</text>
            </g>
        </template>

        <!-- tủ giày + cây + đồng hồ -->
        <g transform="translate(130 180)">
            <rect x="0" y="-28" width="52" height="28" rx="4" fill="#c99464" :stroke="OUT" stroke-width="2" />
            <path d="M0 -14 H52" :stroke="OUT" stroke-width="1.6" />
            <circle cx="14" cy="-21" r="2" fill="#4a3868" /><circle cx="14" cy="-7" r="2" fill="#4a3868" />
            <g transform="translate(36 -28)">
                <path d="M0 0 L-2 -14 H12 L10 0 Z" fill="#ff9f7a" :stroke="OUT" stroke-width="1.8" stroke-linejoin="round" />
                <path d="M5 -14 C-3 -26 -2 -32 4 -36 C5 -28 8 -24 5 -14 M5 -14 C13 -24 18 -28 15 -36 C7 -32 7 -24 5 -14" fill="#7bc67e" :stroke="OUT" stroke-width="1.8" stroke-linejoin="round" />
            </g>
        </g>
        <g transform="translate(22 168)">
            <ellipse cx="22" cy="12" rx="26" ry="5" fill="#ff8fa3" :stroke="OUT" stroke-width="2" />
            <ellipse cx="22" cy="12" rx="18" ry="2.6" fill="#ffd1dc" />
        </g>
    </Phong>
</template>

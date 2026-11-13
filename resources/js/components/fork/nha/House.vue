<script setup lang="ts">
// Ngôi nhà 2 tầng (cắt ngang) + sân cỏ. Toàn bộ là SVG nội tuyến, co theo bề ngang màn hình (viewBox).
// Nhận trạng thái từng vai từ `data`; bấm nhân vật/phòng thì phát `go(khoá)` để trang chuyển tới nơi làm việc.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import './nha.css';
import BienKich from './BienKich.vue';
import Bubble from './Bubble.vue';
import BuuTa from './BuuTa.vue';
import ChuQuay from './ChuQuay.vue';
import Cu from './Cu.vue';
import DaoDien from './DaoDien.vue';
import GiamKhao from './GiamKhao.vue';
import Meo from './Meo.vue';
import Sanh from './Sanh.vue';
import ThoDung from './ThoDung.vue';
import ThuAm from './ThuAm.vue';
import ThuKho from './ThuKho.vue';
import { DICH, type NhaData, type VaiState } from './types';

const props = defineProps<{ data: NhaData | null }>();
const emit = defineEmits<{ go: [key: string] }>();

const W = 1060;
const H = 700;
const OX = 60; // dịch cả ngôi nhà sang phải để chừa sân trái cho bưu tá + hòm thư

const down = computed(() => !props.data || props.data.mode === 'down');
const dim = computed(() => down.value);
const stateOf = (k: string): VaiState => (down.value ? 'sleep' : (props.data?.vai[k]?.state ?? 'idle'));
const bubbleOf = (k: string) => (down.value ? null : (props.data?.vai[k]?.bubble ?? null));

// Vị trí các phòng (toạ độ trong nhóm nhà) + chỗ gắn đuôi bong bóng (toạ độ tuyệt đối).
const rooms: Record<string, { x: number; y: number; w: number; h: number; tip: [number, number] }> = {
    bienkich: { x: 116, y: 193, w: 189, h: 206, tip: [94, 40] },
    thuam: { x: 309, y: 193, w: 189, h: 206, tip: [112, 40] },
    daodien: { x: 502, y: 193, w: 189, h: 206, tip: [96, 40] },
    thodung: { x: 695, y: 193, w: 189, h: 206, tip: [94, 40] },
    giamkhao: { x: 116, y: 415, w: 189, h: 206, tip: [94, 40] },
    thukho: { x: 309, y: 415, w: 189, h: 206, tip: [94, 40] },
    chuquay: { x: 502, y: 415, w: 189, h: 206, tip: [96, 40] },
    bang: { x: 695, y: 415, w: 189, h: 206, tip: [94, 40] },
    cu: { x: 385, y: 89, w: 230, h: 100, tip: [112, 6] },
};
const bubbles = computed(() => {
    const list: { key: string; x: number; y: number; text: string }[] = [];
    for (const k of ['bienkich', 'thuam', 'daodien', 'thodung', 'giamkhao', 'thukho', 'chuquay', 'cu']) {
        const t = bubbleOf(k);
        if (t) {
            const r = rooms[k];
            list.push({ key: k, x: OX + r.x + r.tip[0], y: r.y + r.tip[1], text: t });
        }
    }
    const b = bubbleOf('buuta');
    if (b) {
        list.push({ key: 'buuta', x: 60 + 14, y: 538, text: b });
    }
    if (meoAwake.value) {
        list.push({ key: 'meo', x: 905, y: 632, text: 'Meo~ meo!' });
    }

    return list;
});

// ---- mèo
const meoAwake = ref(false);
const boing = ref(false);
let meoTimer: number | undefined;
const meo = () => {
    boing.value = false;
    void Promise.resolve().then(() => (boing.value = true));
    meoAwake.value = true;
    window.clearTimeout(meoTimer);
    meoTimer = window.setTimeout(() => {
        meoAwake.value = false;
        boing.value = false;
    }, 1800);
};

// ---- chú thích khi rê chuột / focus
const hovered = ref<string | null>(null);
const tipPos: Record<string, [number, number]> = {
    buuta: [100, 540],
    meo: [905, 630],
};
const tip = computed(() => {
    const k = hovered.value;
    if (!k) {
        return null;
    }
    const d = DICH[k];
    const p = rooms[k] ? ([OX + rooms[k].x + rooms[k].w / 2, rooms[k].y + 2] as [number, number]) : tipPos[k];

    return { left: `${(p[0] / W) * 100}%`, top: `${(p[1] / H) * 100}%`, ten: d.ten, text: d.href ? `Bấm để tới ${d.dich}` : 'Mèo đang ngủ, bấm để nghe meo' };
});

const go = (k: string) => {
    if (DICH[k]?.href) {
        emit('go', k);
    }
};

// ---- dừng hoạt ảnh khi tab ẩn
const paused = ref(typeof document !== 'undefined' && document.hidden);
const onVis = () => (paused.value = document.hidden);
onMounted(() => document.addEventListener('visibilitychange', onVis));
onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', onVis);
    window.clearTimeout(meoTimer);
});

const flowers = [
    [30, 668, '#ff8fa3'], [58, 684, '#ffd36a'], [180, 676, '#fff'], [214, 690, '#ff8fa3'], [262, 672, '#c9b6ff'], [330, 688, '#ffd36a'],
    [686, 676, '#fff'], [738, 690, '#ff8fa3'], [790, 670, '#ffd36a'], [958, 686, '#c9b6ff'], [995, 668, '#ff8fa3'], [1040, 684, '#fff'],
] as const;
</script>

<template>
    <div class="relative w-full" data-testid="nha-house">
        <svg :class="['nha-svg', { 'nha-paused': paused }]" :viewBox="`0 0 ${W} ${H}`" role="group" aria-label="Khu Tự Trị: ngôi nhà của các nhân vật" preserveAspectRatio="xMidYMid meet">
            <defs>
                <linearGradient id="nha-sky" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" style="stop-color: var(--nha-sky-a)" />
                    <stop offset="1" style="stop-color: var(--nha-sky-b)" />
                </linearGradient>
                <linearGradient id="nha-lawn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" style="stop-color: var(--nha-lawn-a)" />
                    <stop offset="1" style="stop-color: var(--nha-lawn-b)" />
                </linearGradient>
                <linearGradient id="nha-roofg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" style="stop-color: var(--nha-roof-a)" />
                    <stop offset="1" style="stop-color: var(--nha-roof-b)" />
                </linearGradient>
                <linearGradient id="nha-shade" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stop-color="#000" stop-opacity="0" />
                    <stop offset="1" stop-color="#2a1b4d" stop-opacity="0.35" />
                </linearGradient>
                <linearGradient id="nha-ceil" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stop-color="#2a1b4d" stop-opacity="0.2" />
                    <stop offset="1" stop-color="#2a1b4d" stop-opacity="0" />
                </linearGradient>
                <linearGradient id="nha-pane" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0" stop-color="#fff" stop-opacity="0.9" />
                    <stop offset="1" stop-color="#fff" stop-opacity="0" />
                </linearGradient>
                <radialGradient id="nha-face" cx="0.35" cy="0.28" r="0.75">
                    <stop offset="0" stop-color="#fff" stop-opacity="0.5" />
                    <stop offset="0.6" stop-color="#fff" stop-opacity="0" />
                    <stop offset="1" stop-color="#d98a6a" stop-opacity="0.18" />
                </radialGradient>
                <radialGradient id="nha-warm" cx="0.5" cy="0.55" r="0.65">
                    <stop offset="0" stop-color="#ffd98a" stop-opacity="0.5" />
                    <stop offset="1" stop-color="#ffd98a" stop-opacity="0" />
                </radialGradient>
                <radialGradient id="nha-lamp" cx="0.5" cy="0.5" r="0.5">
                    <stop offset="0" stop-color="#fff1b8" stop-opacity="0.75" />
                    <stop offset="1" stop-color="#fff1b8" stop-opacity="0" />
                </radialGradient>
                <pattern id="nha-dots" width="16" height="16" patternUnits="userSpaceOnUse">
                    <circle cx="4" cy="4" r="1.3" fill="#fff" opacity="0.7" />
                    <circle cx="12" cy="12" r="1.3" fill="#fff" opacity="0.7" />
                </pattern>
                <pattern id="nha-shingle" width="26" height="18" patternUnits="userSpaceOnUse">
                    <path d="M0 18 Q13 2 26 18 M-13 9 Q0 -7 13 9 M13 9 Q26 -7 39 9" fill="none" stroke="#fff" stroke-opacity="0.22" stroke-width="2" />
                </pattern>
            </defs>

            <!-- trời -->
            <rect :width="W" :height="H" fill="url(#nha-sky)" />
            <g :style="{ opacity: 'var(--nha-star)' }">
                <circle v-for="(s, i) in [[90, 60], [220, 130], [340, 40], [560, 70], [700, 36], [830, 110], [960, 54], [1020, 150], [140, 210], [940, 220]]" :key="i" class="nha-star" :cx="s[0]" :cy="s[1]" :r="i % 3 ? 1.8 : 2.6" fill="#fff" :style="{ animationDelay: i * 0.4 + 's' }" />
            </g>
            <g :style="{ opacity: 'var(--nha-sun)' }">
                <circle cx="930" cy="84" r="52" fill="#ffe9a8" opacity="0.4" />
                <circle cx="930" cy="84" r="34" fill="#ffd36a" stroke="#4a3868" stroke-width="2.4" />
                <path d="M918 78 q4 -6 10 -6" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" opacity="0.7" />
            </g>
            <g :style="{ opacity: 'var(--nha-moon)' }">
                <circle cx="930" cy="84" r="34" fill="#fff6cf" stroke="#4a3868" stroke-width="2.4" />
                <circle cx="940" cy="76" r="6" fill="#efe3a8" /><circle cx="920" cy="96" r="4.5" fill="#efe3a8" /><circle cx="944" cy="98" r="3" fill="#efe3a8" />
            </g>
            <g class="nha-cloud" :style="{ opacity: 'calc(1 - var(--nha-night) * 0.8)' }">
                <path d="M110 120 q-4 -22 22 -22 q8 -20 34 -10 q26 -4 28 18 q22 2 14 18 H108 q-14 -2 2 -4 Z" fill="#fff" opacity="0.95" stroke="#4a3868" stroke-width="2" stroke-linejoin="round" />
                <path d="M720 70 q-4 -18 18 -18 q8 -16 30 -8 q22 -3 24 14 q18 2 12 14 H718 q-12 -2 2 -2 Z" fill="#fff" opacity="0.95" stroke="#4a3868" stroke-width="2" stroke-linejoin="round" />
            </g>
            <!-- đồi xa + cỏ -->
            <ellipse cx="200" cy="640" rx="320" ry="60" fill="url(#nha-lawn)" opacity="0.7" />
            <ellipse cx="880" cy="640" rx="300" ry="64" fill="url(#nha-lawn)" opacity="0.7" />
            <rect y="632" :width="W" :height="H - 632" fill="url(#nha-lawn)" />
            <path d="M0 636 Q60 624 130 636 T270 636 T410 636 T550 636 T690 636 T830 636 T970 636 T1060 636 V644 H0 Z" fill="var(--nha-lawn-a)" opacity="0.9" />
            <!-- đường đi -->
            <path d="M530 640 H590 L640 700 H480 Z" fill="#ecd9bd" stroke="#4a3868" stroke-width="2" stroke-linejoin="round" opacity="0.95" />
            <g fill="#fff" opacity="0.6">
                <ellipse cx="560" cy="656" rx="14" ry="5" /><ellipse cx="552" cy="676" rx="18" ry="6" /><ellipse cx="572" cy="692" rx="22" ry="6" />
            </g>
            <g>
                <g v-for="(f, i) in flowers" :key="i" :transform="`translate(${f[0]} ${f[1]})`">
                    <path d="M0 0 V10" stroke="#4a8a5a" stroke-width="2" stroke-linecap="round" />
                    <circle r="4.4" :fill="f[2]" stroke="#4a3868" stroke-width="1.4" />
                    <circle r="1.6" fill="#ffd36a" />
                </g>
            </g>
            <!-- cây -->
            <g class="nha-tree" transform="translate(1004 690)">
                <path d="M-8 0 L-6 -78 H8 L10 0 Z" fill="#b98557" stroke="#4a3868" stroke-width="2.4" stroke-linejoin="round" />
                <circle cx="-26" cy="-96" r="32" fill="#7bc67e" stroke="#4a3868" stroke-width="2.4" />
                <circle cx="26" cy="-98" r="30" fill="#6fbd78" stroke="#4a3868" stroke-width="2.4" />
                <circle cx="0" cy="-124" r="36" fill="#86d08a" stroke="#4a3868" stroke-width="2.4" />
                <path d="M-18 -138 q8 -8 18 -6" stroke="#fff" stroke-width="3.4" fill="none" stroke-linecap="round" opacity="0.5" />
                <circle cx="-18" cy="-92" r="4.6" fill="#ff6f7f" stroke="#4a3868" stroke-width="1.4" /><circle cx="22" cy="-112" r="4.6" fill="#ff6f7f" stroke="#4a3868" stroke-width="1.4" /><circle cx="6" cy="-80" r="4.6" fill="#ff6f7f" stroke="#4a3868" stroke-width="1.4" />
            </g>

            <!-- ngôi nhà -->
            <g :transform="`translate(${OX} 0)`">
                <!-- ống khói -->
                <g>
                    <rect x="190" y="64" width="38" height="84" rx="3" fill="#e8a98f" stroke="#4a3868" stroke-width="2.6" />
                    <path d="M190 84 H228 M190 104 H228 M190 124 H228 M204 64 V84 M218 84 V104 M204 104 V124" stroke="#4a3868" stroke-opacity="0.35" stroke-width="1.6" />
                    <rect x="184" y="56" width="50" height="12" rx="4" fill="#c98568" stroke="#4a3868" stroke-width="2.4" />
                    <g v-if="!down" fill="#fff" stroke="#4a3868" stroke-width="1.6" opacity="0.9">
                        <circle class="nha-smoke s1" cx="209" cy="44" r="7" /><circle class="nha-smoke s2" cx="209" cy="44" r="6" /><circle class="nha-smoke s3" cx="209" cy="44" r="5" />
                    </g>
                </g>
                <!-- mái -->
                <polygon points="78,192 500,8 922,192" fill="url(#nha-roofg)" stroke="#4a3868" stroke-width="3.2" stroke-linejoin="round" />
                <polygon points="78,192 500,8 922,192" fill="url(#nha-shingle)" />
                <path d="M500 8 L922 192" stroke="#fff" stroke-opacity="0.25" stroke-width="3" />
                <polygon points="132,191 500,40 868,191" fill="#e9d6b8" stroke="#4a3868" stroke-width="2.6" stroke-linejoin="round" />
                <path d="M170 191 L500 56 L830 191 M210 191 L500 72" stroke="#4a3868" stroke-opacity="0.14" stroke-width="2" fill="none" />
                <path d="M160 176 H840 M200 160 H800 M250 140 H750 M300 120 H700" stroke="#4a3868" stroke-opacity="0.1" stroke-width="2" />
                <!-- gác mái -->
                <Cu :x="385" :y="89" :state="stateOf('cu')" :dim="dim" @go="go('cu')" @hover="hovered = $event" @leave="hovered = null" />
                <!-- diềm mái -->
                <rect x="66" y="184" width="868" height="14" rx="7" fill="#7a5fd0" stroke="#4a3868" stroke-width="2.6" />
                <rect x="76" y="186" width="848" height="3" rx="1.5" fill="#fff" opacity="0.3" />
                <!-- khung nhà -->
                <rect x="110" y="190" width="780" height="440" rx="10" style="fill: var(--nha-wall-out)" stroke="#4a3868" stroke-width="3" />
                <rect x="110" y="397" width="780" height="20" fill="#cdbbee" opacity="0.7" />
                <path d="M110 399 H890 M110 415 H890" stroke="#4a3868" stroke-opacity="0.4" stroke-width="2" />

                <BienKich :x="rooms.bienkich.x" :y="rooms.bienkich.y" :state="stateOf('bienkich')" :dim="dim" @go="go('bienkich')" @hover="hovered = $event" @leave="hovered = null" />
                <ThuAm :x="rooms.thuam.x" :y="rooms.thuam.y" :state="stateOf('thuam')" :dim="dim" @go="go('thuam')" @hover="hovered = $event" @leave="hovered = null" />
                <DaoDien :x="rooms.daodien.x" :y="rooms.daodien.y" :state="stateOf('daodien')" :dim="dim" @go="go('daodien')" @hover="hovered = $event" @leave="hovered = null" />
                <ThoDung :x="rooms.thodung.x" :y="rooms.thodung.y" :state="stateOf('thodung')" :dim="dim" @go="go('thodung')" @hover="hovered = $event" @leave="hovered = null" />
                <GiamKhao :x="rooms.giamkhao.x" :y="rooms.giamkhao.y" :state="stateOf('giamkhao')" :dim="dim" @go="go('giamkhao')" @hover="hovered = $event" @leave="hovered = null" />
                <ThuKho :x="rooms.thukho.x" :y="rooms.thukho.y" :state="stateOf('thukho')" :dim="dim" @go="go('thukho')" @hover="hovered = $event" @leave="hovered = null" />
                <ChuQuay :x="rooms.chuquay.x" :y="rooms.chuquay.y" :state="stateOf('chuquay')" :dim="dim" @go="go('chuquay')" @hover="hovered = $event" @leave="hovered = null" />
                <Sanh :x="rooms.bang.x" :y="rooms.bang.y" :bang="data?.bang" :mode="data?.mode" :state="data?.mode === 'working' ? 'working' : 'idle'" :dim="dim" @go="go('bang')" @hover="hovered = $event" @leave="hovered = null" />

                <!-- móng nhà + bậc thềm -->
                <rect x="100" y="626" width="800" height="22" rx="6" fill="#c8b6ea" stroke="#4a3868" stroke-width="3" />
                <rect x="470" y="640" width="120" height="12" rx="4" fill="#e6d7f7" stroke="#4a3868" stroke-width="2.4" />
                <path d="M200 626 H236 M420 626 H456 M650 626 H690 M780 626 H820" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity="0.45" />
            </g>

            <!-- ngoài sân -->
            <BuuTa :x="60" :y="650" :state="stateOf('buuta')" :dim="dim" @go="go('buuta')" @hover="hovered = $event" @leave="hovered = null" />
            <Meo :x="905" :y="692" :boing="boing" :awake="meoAwake" @meo="meo" @hover="hovered = $event" @leave="hovered = null" />

            <!-- bong bóng luôn nằm trên cùng -->
            <Bubble v-for="b in bubbles" :key="b.key" :x="b.x" :y="b.y" :text="b.text" :vw="W" />
        </svg>
        <div
            v-if="tip"
            class="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-xl border border-border bg-popover px-3 py-1.5 text-center text-[13px] leading-tight whitespace-nowrap text-popover-foreground shadow-lg"
            :style="{ left: tip.left, top: tip.top }"
            role="tooltip"
        >
            <b class="block text-sm">{{ tip.ten }}</b>
            <span class="text-muted-foreground">{{ tip.text }}</span>
        </div>
    </div>
</template>

<style scoped>
.nha-smoke {
    transform-box: fill-box;
    transform-origin: center;
    animation: smoke 5s ease-out infinite;
}
.nha-smoke.s2 {
    animation-delay: 1.7s;
}
.nha-smoke.s3 {
    animation-delay: 3.4s;
}
@keyframes smoke {
    0% { transform: translate(0, 0) scale(0.5); opacity: 0.9; }
    100% { transform: translate(24px, -52px) scale(1.7); opacity: 0; }
}
</style>

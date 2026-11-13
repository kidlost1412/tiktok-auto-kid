<script setup lang="ts">
// Mèo ngủ trên đệm. Bấm vào thì nảy lên "meo" (không chuyển trang). Gốc toạ độ = giữa đáy đệm.
defineProps<{ x: number; y: number; boing?: boolean; awake?: boolean }>();
const emit = defineEmits<{ meo: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';
</script>

<template>
    <g
        class="nha-npc" :transform="`translate(${x} ${y})`" tabindex="0" role="button" aria-label="Con mèo đang ngủ. Bấm để nghe meo"
        @click="emit('meo')" @keydown.enter.prevent="emit('meo')" @keydown.space.prevent="emit('meo')"
        @mouseenter="emit('hover', 'meo')" @mouseleave="emit('leave')" @focus="emit('hover', 'meo')" @blur="emit('leave')"
    >
        <rect class="ring" x="-46" y="-52" width="92" height="62" rx="14" />
        <ellipse cx="0" cy="3" rx="42" ry="8" fill="#4a3868" opacity="0.16" />
        <ellipse cx="0" cy="-2" rx="40" ry="11" fill="#ff9bb8" :stroke="OUT" stroke-width="2.2" />
        <path d="M-30 -4 q8 5 16 0 M4 -4 q8 5 16 0" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="0.5" />
        <g :class="['nha-meo', { boing }]">
            <!-- đuôi -->
            <g transform="translate(26 -14)">
                <g class="nha-tail">
                    <path d="M0 0 C16 2 22 -8 16 -18 C14 -22 10 -21 12 -17 C16 -10 10 -6 0 -7 Z" fill="#ffb86b" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M13 -17 C15 -12 14 -9 11 -7" stroke="#e08a3c" stroke-width="3" stroke-linecap="round" fill="none" />
                </g>
            </g>
            <g class="nha-bob" style="--d: 0.5s">
                <!-- thân -->
                <ellipse cx="4" cy="-17" rx="30" ry="16" fill="#ffb86b" :stroke="OUT" stroke-width="2.4" />
                <path d="M-6 -30 q3 6 0 12 M6 -32 q3 7 0 14 M18 -30 q3 6 0 12" fill="none" stroke="#e08a3c" stroke-width="3" stroke-linecap="round" />
                <ellipse cx="0" cy="-14" rx="22" ry="10" fill="url(#nha-shade)" opacity="0.4" />
                <!-- đầu -->
                <g transform="translate(-24 -20)">
                    <path d="M-12 -8 L-14 -22 L-3 -14 Z M12 -8 L14 -22 L3 -14 Z" fill="#ffb86b" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-10 -10 L-11 -18 L-5 -13 Z M10 -10 L11 -18 L5 -13 Z" fill="#ff9bb8" />
                    <ellipse cx="0" cy="0" rx="15" ry="13" fill="#ffb86b" :stroke="OUT" stroke-width="2.4" />
                    <path v-if="!awake" d="M-9 -1 Q-6 3 -3 -1 M3 -1 Q6 3 9 -1" fill="none" :stroke="OUT" stroke-width="2" stroke-linecap="round" />
                    <g v-else>
                        <ellipse cx="-6" cy="-1" rx="2.6" ry="3.4" fill="#3a2a57" /><ellipse cx="6" cy="-1" rx="2.6" ry="3.4" fill="#3a2a57" />
                        <circle cx="-7" cy="-2.4" r="1" fill="#fff" /><circle cx="5" cy="-2.4" r="1" fill="#fff" />
                    </g>
                    <path d="M-1.6 4 H1.6 L0 5.8 Z" fill="#ff7a96" />
                    <path v-if="!awake" d="M-3 7 q3 2 6 0" fill="none" :stroke="OUT" stroke-width="1.4" stroke-linecap="round" />
                    <ellipse v-else cx="0" cy="8" rx="2.4" ry="2.8" fill="#e8798f" :stroke="OUT" stroke-width="1.3" />
                    <ellipse cx="-10" cy="4" rx="3.4" ry="2.2" fill="#ff9db5" opacity="0.65" /><ellipse cx="10" cy="4" rx="3.4" ry="2.2" fill="#ff9db5" opacity="0.65" />
                    <path d="M-12 4 l-9 -2 M-12 7 l-9 3 M12 4 l9 -2 M12 7 l9 3" stroke="#4a3868" stroke-width="1.2" stroke-linecap="round" opacity="0.7" />
                </g>
                <!-- chân trước -->
                <ellipse cx="-12" cy="-4" rx="9" ry="5" fill="#ffc98a" :stroke="OUT" stroke-width="2" />
                <g v-if="!awake">
                    <text class="nha-zzz" x="-34" y="-46">z</text>
                    <text class="nha-zzz z2" x="-28" y="-54">z</text>
                    <text class="nha-zzz z3" x="-20" y="-62">Z</text>
                </g>
            </g>
        </g>
    </g>
</template>

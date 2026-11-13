<script setup lang="ts">
// Bưu tá bên hòm thư ngoài sân. Có bài sắp đến giờ đăng thì giơ thư vẫy và dựng cờ hòm thư.
import Chibi from './Chibi.vue';
import type { RoomProps } from './types';

defineProps<RoomProps>();
const emit = defineEmits<{ go: []; hover: [id: string]; leave: [] }>();
const OUT = '#4a3868';
</script>

<template>
    <g
        class="nha-npc" :transform="`translate(${x} ${y})`" tabindex="0" role="link"
        aria-label="Bưu tá bên hòm thư. Bấm để tới Tự động đăng" :opacity="dim ? 0.75 : 1"
        @click="emit('go')" @keydown.enter.prevent="emit('go')" @keydown.space.prevent="emit('go')"
        @mouseenter="emit('hover', 'buuta')" @mouseleave="emit('leave')" @focus="emit('hover', 'buuta')" @blur="emit('leave')"
    >
        <rect class="ring" x="-22" y="-68" width="150" height="132" rx="16" />
        <!-- hòm thư -->
        <g transform="translate(80 0)">
            <ellipse cx="0" cy="48" rx="20" ry="4.5" fill="#4a3868" opacity="0.18" />
            <rect x="-4" y="-6" width="8" height="54" rx="2" fill="#b9824f" :stroke="OUT" stroke-width="2" />
            <path d="M-24 -4 V-22 Q-24 -40 0 -40 Q24 -40 24 -22 V-4 Z" fill="#ff7a8a" :stroke="OUT" stroke-width="2.4" stroke-linejoin="round" />
            <path d="M-24 -4 V-22 Q-24 -40 0 -40 Q24 -40 24 -22 V-4 Z" fill="url(#nha-shade)" opacity="0.4" />
            <path d="M-17 -30 Q-12 -35 -4 -35" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" opacity="0.6" />
            <rect x="-13" y="-17" width="26" height="5" rx="2.5" fill="#4a3868" opacity="0.8" />
            <g transform="translate(24 -22)">
                <path d="M0 0 V-16" :stroke="OUT" stroke-width="3" stroke-linecap="round" />
                <g :class="{ 'nha-flag': state === 'working' }" :transform="state === 'working' ? '' : 'rotate(70)'">
                    <path d="M0 -16 H14 L10 -11 L14 -6 H0 Z" fill="#ffd36a" :stroke="OUT" stroke-width="1.8" stroke-linejoin="round" />
                </g>
            </g>
        </g>
        <!-- bưu tá -->
        <g transform="translate(14 0) scale(1.1)">
            <Chibi :state="state" outfit="#5c8df0" stand :mug="false" no-type wave :delay="0.8" pants="#44527f" shoe="#3b3158">
                <template #body>
                    <path d="M-20 -30 L20 -2" :stroke="OUT" stroke-width="9" stroke-linecap="round" />
                    <path d="M-20 -30 L20 -2" stroke="#ffd36a" stroke-width="5" stroke-linecap="round" />
                    <path d="M-12 -37 L0 -26 L12 -37" fill="#fff" :stroke="OUT" stroke-width="2" stroke-linejoin="round" />
                    <rect x="8" y="-8" width="18" height="16" rx="3" fill="#ffb86b" :stroke="OUT" stroke-width="2" />
                    <path d="M8 -4 H26" :stroke="OUT" stroke-width="1.6" />
                </template>
                <template #hair-back>
                    <path d="M-29 -60 C-31 -84 31 -84 29 -60 L29 -50 L-29 -50 Z" fill="#5a3e2b" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hair-front>
                    <path d="M-27 -62 C-27 -76 27 -76 27 -62 C20 -68 10 -70 2 -67 C-8 -70 -20 -68 -27 -62 Z" fill="#6e4d36" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                </template>
                <template #hat>
                    <path d="M-27 -74 C-27 -98 27 -98 27 -74 Z" fill="#3f6fe0" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <path d="M-26 -74 Q0 -68 26 -74 Q38 -72 40 -67 Q12 -60 -28 -67 Z" fill="#2f55b8" :stroke="OUT" stroke-width="2.2" stroke-linejoin="round" />
                    <circle cx="0" cy="-86" r="6" fill="#ffd36a" :stroke="OUT" stroke-width="1.6" />
                    <path d="M-4 -86 l4 -4 l4 4 l-4 4 Z" fill="#fff" :stroke="OUT" stroke-width="1.2" stroke-linejoin="round" />
                </template>
                <template #hand-r>
                    <g transform="translate(18 -14)">
                        <rect x="-2" y="-14" width="22" height="15" rx="2" fill="#fff" :stroke="OUT" stroke-width="2" transform="rotate(-12)" />
                        <path d="M-2 -13 L9 -5 L20 -14" fill="none" :stroke="OUT" stroke-width="1.6" stroke-linejoin="round" transform="rotate(-12)" />
                        <path d="M8 -4 q-3 -3 0 -4 q3 -1 0 4 Z" fill="#ff5d73" transform="rotate(-12)" />
                    </g>
                </template>
            </Chibi>
        </g>
    </g>
</template>

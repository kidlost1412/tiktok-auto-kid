<script setup lang="ts">
// Nút nghe thử một bài nhạc (bấm lần nữa để dừng); cả app chỉ phát một bài một lúc.
import { IconPlayerPause, IconPlayerPlay } from '@tabler/icons-vue';
import { computed } from 'vue';

import {
    listenUrl,
    playingUrl,
    toggleTrack,
} from '@/components/fork/kho/music';

const props = defineProps<{ dir: string; rel: string }>();
const url = computed(() => listenUrl(props.dir, props.rel));
const playing = computed(() => playingUrl.value === url.value);
</script>

<template>
    <button
        type="button"
        class="inline-flex size-7 shrink-0 items-center justify-center rounded-full border hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring"
        :aria-label="playing ? 'Dừng nghe thử' : 'Nghe thử bài nhạc'"
        :aria-pressed="playing"
        @click="toggleTrack(url)"
    >
        <IconPlayerPause v-if="playing" class="size-4" />
        <IconPlayerPlay v-else class="size-4" />
    </button>
</template>

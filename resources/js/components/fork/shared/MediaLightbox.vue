<script setup lang="ts">
// Xem phóng to một ảnh hoặc một video ngay trên hộp thoại đang mở (dùng được lồng trong hộp thoại khác).
// Esc hoặc bấm ra ngoài để đóng; video tự phát khi mở.
import { IconX } from '@tabler/icons-vue';
import { computed } from 'vue';

import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from '@/components/ui/dialog';

const props = defineProps<{
    open: boolean;
    kind: 'image' | 'video';
    src: string | null;
    title?: string;
    /** Ảnh hiện trong lúc video đang tải. */
    poster?: string | null;
}>();

const emit = defineEmits<{ 'update:open': [value: boolean] }>();

const heading = computed(() => props.title || 'Xem phóng to');
</script>

<template>
    <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
        <DialogContent
            :fullscreen-on-mobile="false"
            :show-close-button="false"
            class="flex w-auto max-w-[min(94vw,56rem)] items-center justify-center gap-0 border-0 bg-black/90 p-2 sm:max-w-[min(94vw,56rem)]"
            data-testid="fork-lightbox"
        >
            <DialogTitle class="sr-only">{{ heading }}</DialogTitle>
            <DialogDescription class="sr-only"
                >Bấm Esc hoặc bấm ra ngoài để đóng.</DialogDescription
            >
            <img
                v-if="kind === 'image' && src"
                :src="src"
                :alt="heading"
                class="max-h-[82dvh] max-w-full rounded-lg object-contain"
            />
            <video
                v-else-if="kind === 'video' && src"
                :src="src"
                :poster="poster ?? undefined"
                class="max-h-[82dvh] max-w-full rounded-lg bg-black"
                controls
                autoplay
                playsinline
            />
            <DialogClose
                aria-label="Đóng"
                class="absolute top-3 right-3 z-10 flex size-8 items-center justify-center rounded-full bg-black/60 text-white transition-colors hover:bg-black/80 focus-visible:outline-2 focus-visible:outline-white"
            >
                <IconX class="size-4" />
            </DialogClose>
            <p
                v-if="title"
                class="absolute inset-x-0 bottom-0 truncate rounded-b-2xl bg-gradient-to-t from-black/70 to-transparent px-4 pt-8 pb-2.5 text-sm text-white"
            >
                {{ title }}
            </p>
        </DialogContent>
    </Dialog>
</template>

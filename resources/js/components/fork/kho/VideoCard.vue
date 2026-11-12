<script setup lang="ts">
// Thẻ video trong kho: rê chuột để xem trước (tự phát, tắt tiếng), có thao tác nhanh chép caption / mở TikTok.
import {
    IconCopy,
    IconExternalLink,
    IconMovie,
    IconPlayerPlayFilled,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref } from 'vue';

import {
    cardLine,
    copyCaption,
    coverUrl,
    fmtDuration,
    type KhoVideo,
    videoUrl,
} from '@/components/fork/kho/kho';
import { toneClasses } from '@/components/fork/shared/status';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import StatusChip from '@/components/fork/shared/StatusChip.vue';
import { cn } from '@/lib/utils';

const props = defineProps<{ video: KhoVideo }>();
defineEmits<{ open: [] }>();

const coverFailed = ref(false);
const line = computed(() => cardLine(props.video));

// Xem trước khi rê chuột: chỉ trên thiết bị có chuột, chờ một nhịp để lướt qua không tải video.
const previewing = ref(false);
const previewReady = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;

const enter = () => {
    if (
        !props.video.can_preview ||
        !window.matchMedia('(hover: hover)').matches
    ) {
        return;
    }

    timer = setTimeout(() => {
        previewing.value = true;
    }, 320);
};

const leave = () => {
    clearTimeout(timer);
    previewing.value = false;
    previewReady.value = false;
};

onBeforeUnmount(() => clearTimeout(timer));
</script>

<template>
    <div
        role="button"
        tabindex="0"
        class="group flex cursor-pointer flex-col overflow-hidden rounded-xl border bg-card text-left shadow-xs transition duration-200 hover:-translate-y-0.5 hover:border-foreground/20 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        :data-testid="`fork-kho-card-${video.id}`"
        @click="$emit('open')"
        @keydown.enter.self.prevent="$emit('open')"
        @keydown.space.self.prevent="$emit('open')"
        @mouseenter="enter"
        @mouseleave="leave"
    >
        <div class="relative aspect-[9/16] w-full overflow-hidden bg-muted">
            <img
                v-if="video.has_cover && !coverFailed"
                :src="coverUrl(video.id)"
                :alt="video.file_name"
                loading="lazy"
                class="size-full object-cover"
                @error="coverFailed = true"
            />
            <div
                v-else
                class="flex size-full flex-col items-center justify-center gap-2 text-muted-foreground"
            >
                <IconMovie class="size-10 opacity-50" />
                <span class="text-xs">Chưa có ảnh bìa</span>
            </div>

            <video
                v-if="previewing"
                :src="videoUrl(video.id)"
                autoplay
                muted
                loop
                playsinline
                preload="metadata"
                :class="
                    cn(
                        'absolute inset-0 size-full bg-black object-cover transition-opacity duration-300',
                        previewReady ? 'opacity-100' : 'opacity-0',
                    )
                "
                @loadeddata="previewReady = true"
            />

            <StatusChip
                :status="video.status"
                class="absolute top-2 left-2 bg-background/90 shadow-sm backdrop-blur"
            />

            <span
                v-if="video.duration"
                class="absolute right-2 bottom-2 rounded bg-black/65 px-1.5 py-0.5 text-[0.75rem] font-medium text-white tabular-nums"
            >
                {{ fmtDuration(video.duration) }}
            </span>

            <span
                v-if="!previewing"
                class="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition group-hover:bg-black/20 group-hover:opacity-100 max-sm:hidden"
            >
                <IconPlayerPlayFilled class="size-10 text-white drop-shadow" />
            </span>

            <!-- Thao tác nhanh -->
            <div
                class="absolute top-2 right-2 flex flex-col gap-1.5 opacity-0 transition group-focus-within:opacity-100 group-hover:opacity-100 max-sm:opacity-100"
            >
                <button
                    v-if="video.caption"
                    type="button"
                    class="flex size-8 items-center justify-center rounded-full bg-background/90 text-foreground shadow-sm backdrop-blur transition hover:bg-background"
                    title="Chép caption và hashtag"
                    aria-label="Chép caption và hashtag"
                    @click.stop="copyCaption(video)"
                    @keydown.enter.stop
                    @keydown.space.stop
                >
                    <IconCopy class="size-4" />
                </button>
                <a
                    v-if="video.tiktok_link"
                    :href="video.tiktok_link"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="flex size-8 items-center justify-center rounded-full bg-background/90 text-foreground shadow-sm backdrop-blur transition hover:bg-background"
                    title="Mở trên TikTok"
                    aria-label="Mở trên TikTok"
                    @click.stop
                    @keydown.enter.stop
                >
                    <IconExternalLink class="size-4" />
                </a>
            </div>
        </div>

        <div class="flex flex-1 flex-col gap-1 p-3">
            <div class="flex items-center gap-2">
                <ProductThumb :src="video.product_image" class="size-6" />
                <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-semibold">
                        {{ video.product ?? 'Chưa rõ sản phẩm' }}
                    </div>
                </div>
            </div>
            <div
                v-if="video.quy_cach"
                class="truncate text-xs text-muted-foreground"
            >
                {{ video.quy_cach }}
            </div>
            <p
                class="line-clamp-2 text-xs leading-snug"
                :class="toneClasses[line.tone].text"
            >
                {{ line.text }}
            </p>
        </div>
    </div>
</template>

<script setup lang="ts">
// Một dòng trong bảng "Video đã đăng": ảnh bìa · sản phẩm & giờ đăng · lượt xem · tim · bình luận · chia sẻ · tương tác · mốc 24h/72h.
import {
    IconExternalLink,
    IconHeart,
    IconMessageCircle,
    IconShare3,
} from '@tabler/icons-vue';

import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import { fmtCompact, fmtNum } from '@/components/fork/shared/status';
import type { StatVideo } from '@/components/fork/so-lieu/types';
import { openVideo } from '@/components/fork/viewer';
import dayjs from '@/dayjs';

const props = defineProps<{
    video: StatVideo;
    productName: string;
    /** Danh sách id đang hiển thị, để ←/→ trong khung xem. */
    ids?: number[];
    /** Lượt xem lớn nhất trong bảng, để vẽ thanh so sánh. */
    maxViews?: number;
}>();

const open = () => openVideo(props.ids ?? [props.video.id], props.video.id);
const pct = (n: number) =>
    `${Math.max(2, Math.min(100, (n / Math.max(1, props.maxViews ?? n)) * 100))}%`;
</script>

<template>
    <li
        class="grid cursor-pointer grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-5 py-3 transition-colors hover:bg-accent/40 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring lg:grid-cols-[36px_minmax(0,1.7fr)_minmax(120px,1fr)_repeat(3,60px)_84px_96px_28px]"
        tabindex="0"
        role="button"
        :data-testid="`fork-so-lieu-video-${video.id}`"
        @click="open"
        @keydown.enter.self.prevent="open"
    >
        <CoverThumb
            :id="video.id"
            :fallback="video.product_image"
            class="h-16 w-9 rounded-md"
        />

        <div class="min-w-0">
            <div class="flex min-w-0 items-center gap-2">
                <span class="truncate text-[13.5px] font-medium">{{
                    productName
                }}</span>
                <span
                    v-if="video.quy_cach"
                    class="shrink-0 text-[12px] text-muted-foreground"
                    >{{ video.quy_cach }}</span
                >
            </div>
            <div class="truncate text-[12px] text-muted-foreground">
                {{ dayjs(video.posted_at).format('HH:mm DD/MM')
                }}<template v-if="video.channel">
                    · {{ video.channel }}</template
                >
            </div>
            <div
                v-if="video.goc || video.giong"
                class="mt-1 flex min-w-0 gap-1 overflow-hidden"
            >
                <span
                    v-for="t in [video.goc, video.giong].filter(Boolean)"
                    :key="String(t)"
                    class="truncate rounded bg-muted px-1.5 text-[11.5px] leading-5 text-muted-foreground"
                    >{{ t }}</span
                >
            </div>
        </div>

        <!-- Lượt xem -->
        <div v-if="video.has_metrics" class="min-w-0 text-right lg:text-left">
            <div class="text-[14px] font-semibold tabular-nums">
                {{ fmtNum(video.views) }}
            </div>
            <div
                class="mt-1 hidden h-1 overflow-hidden rounded-full bg-muted lg:block"
            >
                <div
                    class="h-full rounded-full bg-primary/70"
                    :style="{ width: pct(video.views) }"
                />
            </div>
        </div>
        <div
            v-else
            class="text-right text-[12px] text-muted-foreground lg:col-span-6 lg:text-left"
        >
            Chưa có số liệu (tiện ích thu mỗi giờ)
        </div>

        <template v-if="video.has_metrics">
            <span
                class="hidden items-center justify-end gap-1 text-[13px] text-muted-foreground tabular-nums lg:flex"
                title="Tim"
                ><IconHeart class="size-3.5" />{{
                    fmtCompact(video.likes)
                }}</span
            >
            <span
                class="hidden items-center justify-end gap-1 text-[13px] text-muted-foreground tabular-nums lg:flex"
                title="Bình luận"
                ><IconMessageCircle class="size-3.5" />{{
                    fmtCompact(video.comments)
                }}</span
            >
            <span
                class="hidden items-center justify-end gap-1 text-[13px] text-muted-foreground tabular-nums lg:flex"
                title="Chia sẻ"
                ><IconShare3 class="size-3.5" />{{
                    fmtCompact(video.shares)
                }}</span
            >
            <span
                class="hidden text-right text-[13px] tabular-nums lg:block"
                title="Tỉ lệ tương tác = (tim + bình luận + chia sẻ) / lượt xem"
                >{{
                    video.engagement > 0
                        ? `${video.engagement.toLocaleString('vi-VN')}%`
                        : '—'
                }}</span
            >
            <span
                class="hidden text-right text-[12px] leading-tight text-muted-foreground tabular-nums lg:block"
            >
                <span class="block"
                    >24h
                    <b class="font-medium text-foreground">{{
                        video.views_24h === null
                            ? '—'
                            : fmtCompact(video.views_24h)
                    }}</b></span
                >
                <span class="block"
                    >72h
                    <b class="font-medium text-foreground">{{
                        video.views_72h === null
                            ? '—'
                            : fmtCompact(video.views_72h)
                    }}</b></span
                >
            </span>
        </template>

        <a
            v-if="video.link"
            :href="video.link"
            target="_blank"
            rel="noopener noreferrer"
            class="hidden size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground lg:flex"
            title="Mở trên TikTok"
            aria-label="Mở trên TikTok"
            @click.stop
        >
            <IconExternalLink class="size-4" />
        </a>
        <span v-else class="hidden lg:block" />
    </li>
</template>

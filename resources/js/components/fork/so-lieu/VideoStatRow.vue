<script setup lang="ts">
// Một video đã đăng kèm số liệu: ảnh bìa, thông tin đăng, lượt xem / tim / bình luận / chia sẻ, mốc 24h và 72h.
import {
    IconBookmark,
    IconExternalLink,
    IconEye,
    IconHeart,
    IconMessageCircle,
    IconShare3,
    IconShoppingCart,
} from '@tabler/icons-vue';

import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { fmtNum } from '@/components/fork/shared/status';
import type { StatVideo } from '@/components/fork/so-lieu/types';
import VideoThumb from '@/components/fork/VideoThumb.vue';
import { openVideo } from '@/components/fork/viewer';
import dayjs from '@/dayjs';

const props = defineProps<{
    video: StatVideo;
    productName: string;
    /** Danh sách id đang hiển thị, để ←/→ trong khung xem. */
    ids?: number[];
}>();

const open = () => openVideo(props.ids ?? [props.video.id], props.video.id);
</script>

<template>
    <li
        class="flex cursor-pointer flex-col gap-3 rounded-xl border bg-card p-3 shadow-xs transition hover:border-foreground/25 hover:shadow-sm sm:flex-row sm:items-center"
        tabindex="0"
        role="button"
        @click="open"
        @keydown.enter.self.prevent="open"
        :data-testid="`fork-so-lieu-video-${video.id}`"
    >
        <div class="flex min-w-0 flex-1 gap-3">
            <VideoThumb :id="video.id" class="h-24 w-[54px] rounded-lg" />
            <div class="flex min-w-0 flex-1 flex-col gap-1 text-sm">
                <div class="flex flex-wrap items-center gap-x-2">
                    <ProductThumb :src="video.product_image" class="size-5" />
                    <span class="truncate font-medium">{{ productName }}</span>
                    <span
                        v-if="video.quy_cach"
                        class="text-xs text-muted-foreground"
                        >{{ video.quy_cach }}</span
                    >
                </div>
                <div class="text-xs text-muted-foreground">
                    {{ dayjs(video.posted_at).format('HH:mm DD/MM/YYYY') }}
                    <template v-if="video.channel">
                        · {{ video.channel }}</template
                    >
                </div>
                <div
                    v-if="video.cart_name"
                    class="flex items-center gap-1 truncate text-xs text-muted-foreground"
                >
                    <IconShoppingCart class="size-3.5 shrink-0" />
                    <span class="truncate">{{ video.cart_name }}</span>
                </div>
                <div class="mt-0.5 flex flex-wrap gap-1">
                    <span
                        v-for="t in [video.goc, video.giong, video.nhac].filter(
                            Boolean,
                        )"
                        :key="String(t)"
                        class="rounded-full bg-muted px-1.5 py-0.5 text-[0.75rem] text-muted-foreground"
                        >{{ t }}</span
                    >
                </div>
            </div>
        </div>

        <div class="flex shrink-0 flex-col gap-1.5 sm:w-64">
            <template v-if="video.has_metrics">
                <div class="flex items-baseline gap-2">
                    <IconEye class="size-4 self-center text-muted-foreground" />
                    <span class="text-lg font-semibold tabular-nums">{{
                        fmtNum(video.views)
                    }}</span>
                    <span class="text-xs text-muted-foreground">lượt xem</span>
                    <span
                        v-if="video.engagement > 0"
                        class="ml-auto text-xs text-muted-foreground tabular-nums"
                        title="Tỉ lệ tương tác = (tim + bình luận + chia sẻ) / lượt xem"
                        >{{ video.engagement.toLocaleString('vi-VN') }}%</span
                    >
                </div>
                <div
                    class="flex items-center gap-3 text-xs text-muted-foreground tabular-nums"
                >
                    <span class="inline-flex items-center gap-1" title="Tim"
                        ><IconHeart class="size-3.5" />{{
                            fmtNum(video.likes)
                        }}</span
                    >
                    <span
                        class="inline-flex items-center gap-1"
                        title="Bình luận"
                        ><IconMessageCircle class="size-3.5" />{{
                            fmtNum(video.comments)
                        }}</span
                    >
                    <span class="inline-flex items-center gap-1" title="Chia sẻ"
                        ><IconShare3 class="size-3.5" />{{
                            fmtNum(video.shares)
                        }}</span
                    >
                    <span
                        v-if="video.saves"
                        class="inline-flex items-center gap-1"
                        title="Lưu"
                        ><IconBookmark class="size-3.5" />{{
                            fmtNum(video.saves)
                        }}</span
                    >
                </div>
                <div
                    v-if="video.avg_watch_s !== null || video.finish_rate !== null"
                    class="text-xs text-muted-foreground tabular-nums"
                >
                    <template v-if="video.avg_watch_s !== null"
                        >Xem TB
                        <b class="text-foreground"
                            >{{ video.avg_watch_s.toLocaleString('vi-VN') }}s</b
                        ></template
                    >
                    <template v-if="video.finish_rate !== null">
                        · Xem hết
                        <b class="text-foreground"
                            >{{ video.finish_rate.toLocaleString('vi-VN') }}%</b
                        ></template
                    >
                </div>
                <div class="text-xs text-muted-foreground tabular-nums">
                    24h:
                    <b class="text-foreground">{{ fmtNum(video.views_24h) }}</b>
                    · 72h:
                    <b class="text-foreground">{{ fmtNum(video.views_72h) }}</b>
                </div>
            </template>
            <p v-else class="text-sm text-muted-foreground">
                Chưa có số liệu
                <span class="text-xs">(tiện ích thu mỗi giờ)</span>
            </p>
            <a
                v-if="video.link"
                :href="video.link"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex w-fit items-center gap-1 text-xs font-medium text-primary hover:underline"
                @click.stop
            >
                Mở trên TikTok
                <IconExternalLink class="size-3.5" />
            </a>
        </div>
    </li>
</template>

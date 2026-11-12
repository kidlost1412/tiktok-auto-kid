<script setup lang="ts">
// Khung xem video dùng chung cho mọi trang: phát video, caption + hashtag, sản phẩm, giỏ hàng, kênh, giờ đăng, số liệu.
// ←/→ chuyển video trong danh sách đang xem, Esc đóng. File đã dọn thì hiện ảnh bìa + "Mở trên TikTok".
import {
    IconChevronLeft,
    IconChevronRight,
    IconCopy,
    IconExternalLink,
    IconEye,
    IconHeart,
    IconMessageCircle,
    IconBookmark,
    IconMovieOff,
    IconShare3,
    IconShoppingCart,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, watch } from 'vue';

import {
    copyCaption,
    coverUrl,
    fmtTime,
    severityTone,
    videoUrl,
} from '@/components/fork/kho/kho';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { fmtNum, toneClasses } from '@/components/fork/shared/status';
import StatusChip from '@/components/fork/shared/StatusChip.vue';
import { stepVideo, viewer } from '@/components/fork/viewer';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

const entry = computed(() => viewer.cache[viewer.ids[viewer.index]]);
const video = computed(() =>
    entry.value && entry.value !== 'error' ? entry.value : null,
);
const total = computed(() => viewer.ids.length);
const hasPrev = computed(() => viewer.index > 0);
const hasNext = computed(() => viewer.index < total.value - 1);

const onKey = (e: KeyboardEvent) => {
    const t = e.target as HTMLElement | null;

    if (
        e.altKey ||
        e.ctrlKey ||
        e.metaKey ||
        (t && ['INPUT', 'TEXTAREA', 'SELECT', 'VIDEO'].includes(t.tagName))
    ) {
        return;
    }

    if (e.key === 'ArrowLeft' && hasPrev.value) {
        e.preventDefault();
        stepVideo(-1);
    } else if (e.key === 'ArrowRight' && hasNext.value) {
        e.preventDefault();
        stepVideo(1);
    }
};

watch(
    () => viewer.open,
    (open) => {
        if (open) {
            window.addEventListener('keydown', onKey);
        } else {
            window.removeEventListener('keydown', onKey);
        }
    },
    { immediate: true },
);

onBeforeUnmount(() => window.removeEventListener('keydown', onKey));

const timeRow = computed<[string, string] | null>(() => {
    const v = video.value;

    if (!v) {
        return null;
    }

    if (v.status === 'posted' && v.posted_at) {
        return ['Đã đăng lúc', fmtTime(v.posted_at)];
    }

    if (v.scheduled_for) {
        return [
            v.on_tiktok_schedule ? 'Hẹn trên TikTok lúc' : 'Giờ đăng dự kiến',
            fmtTime(v.scheduled_for),
        ];
    }

    return null;
});

const statLine = computed(() => {
    const s = video.value?.stats;

    return s
        ? [
              { icon: IconHeart, label: 'Thích', value: s.likes },
              {
                  icon: IconMessageCircle,
                  label: 'Bình luận',
                  value: s.comments,
              },
              { icon: IconShare3, label: 'Chia sẻ', value: s.shares },
              { icon: IconBookmark, label: 'Lưu', value: s.saves ?? null },
              { icon: IconEye, label: '72h', value: s.views_72h ?? null },
          ].filter((x) => x.value !== null)
        : [];
});
</script>

<template>
    <Dialog :open="viewer.open" @update:open="viewer.open = $event">
        <DialogContent
            class="gap-0 overflow-hidden p-0 sm:max-w-4xl"
            data-testid="fork-kho-dialog"
        >
            <DialogHeader class="sr-only">
                <DialogTitle>{{ video?.product ?? 'Video' }}</DialogTitle>
                <DialogDescription>Chi tiết video</DialogDescription>
            </DialogHeader>

            <div
                v-if="!video"
                class="flex h-72 items-center justify-center p-8 text-sm text-muted-foreground"
            >
                {{
                    entry === 'error'
                        ? 'Không tải được thông tin video này.'
                        : 'Đang tải…'
                }}
            </div>

            <div
                v-else
                class="grid max-h-[88vh] overflow-y-auto sm:grid-cols-[minmax(0,320px)_1fr] sm:overflow-hidden"
            >
                <!-- Trình phát -->
                <div
                    class="relative flex items-center justify-center bg-black p-3 sm:max-h-[88vh]"
                >
                    <video
                        v-if="viewer.open && video.can_preview"
                        :key="video.id"
                        :src="videoUrl(video.id)"
                        :poster="
                            video.has_cover ? coverUrl(video.id) : undefined
                        "
                        controls
                        autoplay
                        playsinline
                        preload="metadata"
                        class="aspect-[9/16] max-h-[80vh] w-full rounded-lg bg-black object-contain"
                    />
                    <div
                        v-else
                        class="relative aspect-[9/16] w-full max-w-[280px] overflow-hidden rounded-lg bg-zinc-900"
                    >
                        <img
                            v-if="video.has_cover"
                            :src="coverUrl(video.id)"
                            alt=""
                            class="size-full object-cover opacity-60"
                        />
                        <div
                            class="absolute inset-0 flex flex-col items-center justify-center gap-3 p-5 text-center text-sm text-white"
                        >
                            <IconMovieOff class="size-9 opacity-80" />
                            <span class="opacity-90"
                                >File video đã được dọn khỏi máy.</span
                            >
                            <Button
                                v-if="video.tiktok_link"
                                as-child
                                size="sm"
                                variant="secondary"
                            >
                                <a
                                    :href="video.tiktok_link"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    ><IconExternalLink class="size-4" /> Mở trên
                                    TikTok</a
                                >
                            </Button>
                        </div>
                    </div>
                </div>

                <!-- Thông tin -->
                <div
                    class="flex min-w-0 flex-col gap-4 p-5 sm:max-h-[88vh] sm:overflow-y-auto"
                >
                    <div class="flex items-start gap-3 pr-8">
                        <ProductThumb
                            :src="video.product_image"
                            class="size-12 rounded-lg"
                        />
                        <div class="min-w-0 flex-1">
                            <h2 class="truncate text-lg font-semibold">
                                {{ video.product ?? 'Video' }}
                            </h2>
                            <p
                                v-if="video.quy_cach"
                                class="truncate text-sm text-muted-foreground"
                            >
                                {{ video.quy_cach }}
                            </p>
                        </div>
                        <StatusChip :status="video.status" class="mt-0.5" />
                    </div>

                    <div
                        v-if="total > 1"
                        class="flex items-center gap-1 text-sm text-muted-foreground"
                    >
                        <Button
                            size="icon"
                            variant="outline"
                            class="size-8"
                            :disabled="!hasPrev"
                            aria-label="Video trước (phím ←)"
                            title="Video trước (←)"
                            @click="stepVideo(-1)"
                        >
                            <IconChevronLeft class="size-4" />
                        </Button>
                        <span class="min-w-14 text-center tabular-nums"
                            >{{ viewer.index + 1 }} / {{ total }}</span
                        >
                        <Button
                            size="icon"
                            variant="outline"
                            class="size-8"
                            :disabled="!hasNext"
                            aria-label="Video sau (phím →)"
                            title="Video sau (→)"
                            @click="stepVideo(1)"
                        >
                            <IconChevronRight class="size-4" />
                        </Button>
                        <span class="ml-2 hidden text-xs sm:inline"
                            >Phím ← → chuyển video · Esc đóng</span
                        >
                    </div>

                    <div
                        v-if="video.readiness"
                        :class="
                            cn(
                                'rounded-lg border p-3 text-sm',
                                toneClasses[
                                    severityTone[video.readiness.severity] ??
                                        'neutral'
                                ].box,
                            )
                        "
                        data-testid="fork-kho-dialog-readiness"
                    >
                        {{ video.readiness.reason }}
                    </div>
                    <div
                        v-else-if="video.reason"
                        :class="
                            cn(
                                'rounded-lg border p-3 text-sm',
                                toneClasses[
                                    video.status === 'failed'
                                        ? 'danger'
                                        : 'warn'
                                ].box,
                            )
                        "
                    >
                        {{ video.reason }}
                    </div>

                    <dl
                        class="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 text-sm"
                    >
                        <dt class="text-muted-foreground">Giỏ hàng</dt>
                        <dd
                            class="flex min-w-0 items-center gap-1.5 font-medium"
                        >
                            <IconShoppingCart
                                class="size-4 shrink-0 text-muted-foreground"
                            />
                            <span class="truncate">{{
                                video.cart_name ?? '—'
                            }}</span>
                        </dd>
                        <dt class="text-muted-foreground">Kênh</dt>
                        <dd
                            class="flex min-w-0 items-center gap-1.5 font-medium"
                        >
                            <Avatar
                                :src="video.channel_avatar ?? null"
                                :name="video.channel?.replace(/^@+/, '') || '?'"
                                class="size-5 rounded-full"
                                fallback-class="bg-secondary text-[0.65rem] font-bold"
                            />
                            <span class="truncate">{{
                                video.channel ?? '—'
                            }}</span>
                        </dd>
                        <template v-if="timeRow">
                            <dt class="text-muted-foreground">
                                {{ timeRow[0] }}
                            </dt>
                            <dd class="font-medium tabular-nums">
                                {{ timeRow[1] }}
                            </dd>
                        </template>
                        <dt class="text-muted-foreground">Góc / ngày làm</dt>
                        <dd class="font-medium">
                            {{ video.goc ?? '—' }} · {{ video.ngay_lam ?? '—' }}
                        </dd>
                    </dl>

                    <!-- Số liệu -->
                    <div
                        v-if="video.status === 'posted'"
                        class="grid grid-cols-2 gap-2 rounded-xl border bg-muted/30 p-3 sm:grid-cols-4"
                    >
                        <template v-if="video.stats">
                            <div class="flex flex-col">
                                <span class="text-xs text-muted-foreground"
                                    >Lượt xem</span
                                >
                                <span
                                    class="text-base font-semibold tabular-nums"
                                    >{{ fmtNum(video.stats.views) }}</span
                                >
                            </div>
                            <div
                                v-for="s in statLine"
                                :key="s.label"
                                class="flex flex-col"
                            >
                                <span class="text-xs text-muted-foreground">{{
                                    s.label
                                }}</span>
                                <span
                                    class="text-base font-semibold tabular-nums"
                                    >{{ fmtNum(s.value) }}</span
                                >
                            </div>
                        </template>
                        <span
                            v-else
                            class="col-span-full text-xs text-muted-foreground"
                            >Chưa có số liệu (tiện ích sẽ cập nhật sau).</span
                        >
                    </div>

                    <div
                        v-if="
                            video.stats &&
                            (video.stats.avg_watch_s != null ||
                                video.stats.finish_rate != null ||
                                video.stats.traffic?.length)
                        "
                        class="flex flex-col gap-1 rounded-xl border p-3 text-xs text-muted-foreground"
                        data-testid="fork-viewer-insight"
                    >
                        <div class="flex flex-wrap gap-x-4 gap-y-1">
                            <span v-if="video.stats.avg_watch_s != null"
                                >Xem TB:
                                <b class="text-foreground"
                                    >{{ video.stats.avg_watch_s }} giây</b
                                ></span
                            >
                            <span v-if="video.stats.finish_rate != null"
                                >Xem hết:
                                <b class="text-foreground"
                                    >{{ video.stats.finish_rate }}%</b
                                ></span
                            >
                            <span v-if="video.stats.new_followers != null"
                                >Người theo dõi mới:
                                <b class="text-foreground">{{
                                    video.stats.new_followers
                                }}</b></span
                            >
                        </div>
                        <div
                            v-if="video.stats.traffic?.length"
                            class="flex flex-wrap gap-x-4 gap-y-1"
                        >
                            <span v-for="t in video.stats.traffic" :key="t.key"
                                >{{ t.key }}:
                                <b class="text-foreground"
                                    >{{ Math.round(t.value * 100) }}%</b
                                ></span
                            >
                        </div>
                        <span v-if="video.stats.collected_at"
                            >Cập nhật lúc
                            {{ fmtTime(video.stats.collected_at) }}</span
                        >
                    </div>

                    <div
                        v-if="video.comments && video.comments.total > 0"
                        class="flex flex-col gap-2"
                        data-testid="fork-viewer-comments"
                    >
                        <span class="text-sm font-semibold"
                            >Bình luận ({{ video.comments.total
                            }}<template v-if="video.comments.buy"
                                >, {{ video.comments.buy }} hỏi mua</template
                            >)</span
                        >
                        <ul
                            class="flex max-h-48 flex-col gap-1.5 overflow-y-auto"
                        >
                            <li
                                v-for="c in video.comments.rows"
                                :key="c.id"
                                class="rounded-lg bg-muted p-2 text-sm"
                            >
                                <span class="font-medium">{{
                                    c.author || 'Ẩn danh'
                                }}</span>
                                <Badge
                                    v-if="c.buy"
                                    variant="outline"
                                    class="ml-1.5"
                                    >Hỏi mua</Badge
                                >
                                <span
                                    class="ml-1.5 text-xs text-muted-foreground"
                                    >{{ fmtTime(c.at) }}</span
                                >
                                <p class="break-words whitespace-pre-line">
                                    {{ c.text }}
                                </p>
                            </li>
                        </ul>
                    </div>

                    <a
                        v-if="video.tiktok_link"
                        :href="video.tiktok_link"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-primary-text underline-offset-4 hover:underline"
                    >
                        <IconExternalLink class="size-4" /> Mở trên TikTok
                    </a>

                    <div class="flex flex-col gap-2">
                        <div class="flex items-center justify-between">
                            <span class="text-sm font-semibold"
                                >Caption và hashtag</span
                            >
                            <Button
                                v-if="video.caption || video.hashtags.length"
                                size="sm"
                                variant="outline"
                                @click="copyCaption(video)"
                            >
                                <IconCopy class="size-4" />
                                Chép
                            </Button>
                        </div>
                        <p
                            v-if="video.caption"
                            class="max-h-40 overflow-y-auto rounded-lg bg-muted p-3 text-sm leading-relaxed whitespace-pre-wrap"
                        >
                            {{ video.caption }}
                        </p>
                        <p
                            v-else
                            class="rounded-lg bg-muted p-3 text-sm text-muted-foreground"
                        >
                            Chưa có caption.
                        </p>
                        <div
                            v-if="video.hashtags.length"
                            class="flex flex-wrap gap-1.5"
                        >
                            <Badge
                                v-for="t in video.hashtags"
                                :key="t"
                                variant="outline"
                                >{{ t }}</Badge
                            >
                        </div>
                    </div>

                    <p class="truncate text-xs text-muted-foreground">
                        {{ video.file_name }}
                    </p>
                </div>
            </div>
        </DialogContent>
    </Dialog>
</template>

<script setup lang="ts">
// Các bài đã thật sự lên TikTok (giờ đăng đã qua), dạng thẻ gọn có ảnh bìa, sản phẩm và lượt xem. Bấm thẻ để xem video.
// Phía trên là các bài lỗi gần đây, có nút "Thử lại" khi chắc chắn bài chưa lên TikTok.
import { Link, router } from '@inertiajs/vue3';
import {
    IconAlertCircle,
    IconChartBar,
    IconExternalLink,
    IconEye,
    IconPlayerPlayFilled,
    IconRefresh,
    IconSend,
} from '@tabler/icons-vue';
import { ref } from 'vue';

import type { FailedRow, RecentRow } from '@/components/fork/auto/types';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import { fmtNum } from '@/components/fork/shared/status';
import StatusChip from '@/components/fork/shared/StatusChip.vue';
import VideoThumb from '@/components/fork/VideoThumb.vue';
import { openVideo } from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';

const props = withDefaults(
    defineProps<{
        recent: RecentRow[];
        failed?: FailedRow[];
        productName: (code: string | null) => string;
    }>(),
    { failed: () => [] },
);

const retrying = ref<number | null>(null);

// Máy chủ kiểm lại lần nữa (chưa có gì lên TikTok) rồi mới đưa video về kho; kết quả hiện bằng thông báo.
const retry = (id: number) => {
    retrying.value = id;
    router.post(
        `/auto/videos/${id}/thu-lai`,
        {},
        {
            preserveScroll: true,
            onFinish: () => {
                retrying.value = null;
            },
        },
    );
};

const open = (id: number) =>
    openVideo(
        props.recent.map((r) => r.id),
        id,
    );
</script>

<template>
    <section class="flex flex-col gap-3" data-testid="fork-auto-recent">
        <SectionHeading
            title="Vừa đăng gần đây"
            description="Những bài đã lên TikTok, mới nhất trước. Bài hẹn giờ chưa tới nằm trong lịch phía trên."
        >
            <Link
                href="/auto/so-lieu"
                class="inline-flex items-center gap-1.5 text-base font-medium text-primary hover:underline"
            >
                <IconChartBar class="size-5" />
                Xem số liệu chi tiết
            </Link>
        </SectionHeading>

        <div
            v-if="failed.length"
            class="overflow-hidden rounded-2xl border border-red-200 bg-card shadow-xs dark:border-red-900"
            data-testid="fork-auto-failed"
        >
            <div
                class="flex items-center gap-2 border-b border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
            >
                <IconAlertCircle class="size-4" />
                {{ failed.length }} bài đăng lỗi gần đây
            </div>
            <ul class="divide-y">
                <li
                    v-for="f in failed"
                    :key="f.id"
                    class="flex items-center gap-3 px-4 py-3"
                    :data-testid="`fork-auto-failed-${f.id}`"
                >
                    <ProductThumb :src="f.product_image" class="size-9" />
                    <div class="min-w-0 flex-1">
                        <div class="truncate text-sm font-medium">
                            {{ productName(f.product_code) }}
                            <span class="font-normal text-muted-foreground">
                                · @{{ f.username }} ·
                                {{
                                    f.at
                                        ? dayjs(f.at).format('HH:mm DD/MM')
                                        : '—'
                                }}
                            </span>
                        </div>
                        <p
                            v-if="f.error"
                            class="line-clamp-2 text-sm text-red-700 dark:text-red-300"
                        >
                            {{ f.error }}
                        </p>
                        <p
                            v-if="!f.can_retry && f.retry_note"
                            class="mt-0.5 line-clamp-2 text-xs text-muted-foreground"
                        >
                            {{ f.retry_note }}
                        </p>
                    </div>
                    <Button
                        v-if="f.can_retry"
                        size="sm"
                        variant="outline"
                        class="shrink-0"
                        :disabled="retrying !== null"
                        :data-testid="`fork-auto-retry-${f.id}`"
                        @click="retry(f.id)"
                    >
                        <Spinner v-if="retrying === f.id" class="size-4" />
                        <IconRefresh v-else class="size-4" />
                        Thử lại
                    </Button>
                </li>
            </ul>
        </div>

        <EmptyState
            v-if="!recent.length"
            :icon="IconSend"
            title="Chưa có bài nào được đăng"
            description="Khi kênh bật tự động đăng và có video đủ điều kiện, bài đăng sẽ hiện ở đây cùng lượt xem."
        >
            <Link
                href="/auto/kho"
                class="text-sm font-medium text-primary hover:underline"
                >Xem video đang chờ trong kho →</Link
            >
        </EmptyState>

        <ul v-else class="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
            <li
                v-for="r in recent"
                :key="r.id"
                role="button"
                tabindex="0"
                class="flex cursor-pointer items-center gap-4 rounded-2xl border bg-card p-3.5 shadow-xs transition hover:-translate-y-px hover:border-foreground/25 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                :data-testid="`fork-auto-recent-${r.id}`"
                @click="open(r.id)"
                @keydown.enter.self.prevent="open(r.id)"
            >
                <VideoThumb :id="r.id" class="h-[136px] w-[77px] rounded-xl" />
                <div class="min-w-0 flex-1 text-base">
                    <div class="flex items-center gap-2">
                        <ProductThumb :src="r.product_image" class="size-9" />
                        <span class="truncate font-medium">{{
                            productName(r.product_code)
                        }}</span>
                    </div>
                    <div class="mt-1 truncate text-sm text-muted-foreground">
                        @{{ r.username }} ·
                        {{
                            r.posted_at
                                ? dayjs(r.posted_at).format('HH:mm DD/MM')
                                : '—'
                        }}
                    </div>
                    <p
                        v-if="r.caption"
                        class="mt-1.5 line-clamp-2 text-sm text-muted-foreground"
                    >
                        {{ r.caption }}
                    </p>
                    <div
                        class="mt-2 flex items-center gap-1.5 text-sm tabular-nums"
                        :class="
                            r.views === null
                                ? 'text-muted-foreground/70'
                                : 'text-muted-foreground'
                        "
                    >
                        <IconEye class="size-4" />
                        <template v-if="r.views !== null">
                            {{ fmtNum(r.views) }} lượt xem
                            <template v-if="r.views_24h !== null">
                                · 24h: {{ fmtNum(r.views_24h) }}
                            </template>
                        </template>
                        <template v-else>Chưa có số liệu</template>
                    </div>
                    <div
                        class="mt-2 inline-flex items-center gap-1.5 text-sm font-medium text-primary"
                    >
                        <IconPlayerPlayFilled class="size-4" />
                        Bấm để xem video
                    </div>
                </div>
                <div class="flex shrink-0 flex-col items-end gap-2">
                    <StatusChip status="posted" icon-only />
                    <a
                        v-if="r.link"
                        :href="r.link"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                        @click.stop
                    >
                        TikTok
                        <IconExternalLink class="size-4" />
                    </a>
                </div>
            </li>
        </ul>
    </section>
</template>

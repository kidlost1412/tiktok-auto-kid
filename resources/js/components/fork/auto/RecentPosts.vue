<script setup lang="ts">
// Các bài đã thật sự lên TikTok (giờ đăng đã qua), dạng thẻ gọn có ảnh bìa, sản phẩm và lượt xem. Bấm thẻ để xem video.
import { Link } from '@inertiajs/vue3';
import {
    IconChartBar,
    IconExternalLink,
    IconEye,
    IconPlayerPlayFilled,
    IconSend,
} from '@tabler/icons-vue';

import type { RecentRow } from '@/components/fork/auto/types';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import { fmtNum } from '@/components/fork/shared/status';
import StatusChip from '@/components/fork/shared/StatusChip.vue';
import { openVideo } from '@/components/fork/viewer';
import VideoThumb from '@/components/fork/VideoThumb.vue';
import dayjs from '@/dayjs';

const props = defineProps<{
    recent: RecentRow[];
    productName: (code: string | null) => string;
}>();

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
                    <div class="mt-2 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
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

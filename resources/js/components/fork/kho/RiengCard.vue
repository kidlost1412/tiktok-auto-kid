<script setup lang="ts">
// Thẻ một video trong Kho riêng: ảnh xem trước, ô chọn to, cờ trùng video, sản phẩm đã gắn, nút "+ giỏ chờ".
import {
    IconAlertTriangle,
    IconCheck,
    IconCircleCheck,
    IconFolder,
    IconMovie,
    IconMusic,
    IconPlaylistAdd,
    IconTrash,
} from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import { fmtDuration, whereLabel } from '@/components/fork/kho/kho';
import type { RiengVideo } from '@/components/fork/kho/rieng';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import {
    fmtNum,
    toneClasses,
    type Tone,
} from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    video: RiengVideo;
    selected: boolean;
    selectMode: boolean;
    queued: boolean;
    /** Đang nhấn giữ (cảm ứng) chờ vào chế độ kéo chọn: thẻ thu nhẹ + viền nháy. */
    holding?: boolean;
}>();

// Thư mục con trong thư mục đã thêm (vd "test" của MIG 38/test/a.mp4); rỗng = nằm ngay thư mục gốc.
const subFolder = computed(() => {
    const rel = props.video.rel_path ?? '';
    const i = rel.lastIndexOf('/');

    return i > 0 ? rel.slice(0, i).replaceAll('/', ' › ') : '';
});

const emit = defineEmits<{
    open: [];
    toggle: [shift: boolean];
    queue: [];
    retry: [];
    auto: [];
    forget: [];
}>();

// Phần "tự đăng theo khung" chỉ hiện cho video còn chờ đăng.
const auto = () =>
    props.video.status === 'new' && !props.video.gone ? props.video.auto : null;

const thumbFailed = ref(false);
const thumbLoaded = ref(false);
const fmt = (iso: string | null) =>
    iso ? dayjs(iso).format('HH:mm DD/MM') : '—';

const status = (): { label: string; tone: Tone } => {
    const v = props.video;

    if (v.gone && v.status === 'new') {
        return { label: 'Mất file', tone: 'warn' };
    }

    // Đã xếp: nói rõ đã lên TikTok chưa (chưa lên thì sửa / xoá thoải mái).
    if (
        (v.status === 'scheduled' || v.status === 'reserved') &&
        v.schedule_state
    ) {
        return {
            label: whereLabel[v.schedule_state],
            tone: (
                {
                    tiktok: 'info',
                    uploading: 'info',
                    direct: 'violet',
                    in_app: 'neutral',
                } as Record<string, Tone>
            )[v.schedule_state],
        };
    }

    return (
        {
            new: { label: 'Chưa đăng', tone: 'neutral' as Tone },
            reserved: { label: 'Đã hẹn giờ', tone: 'info' as Tone },
            scheduled: { label: 'Đã hẹn giờ', tone: 'info' as Tone },
            posted: { label: 'Đã đăng', tone: 'success' as Tone },
            failed: { label: 'Lỗi', tone: 'danger' as Tone },
            skipped: { label: 'Bỏ qua', tone: 'warn' as Tone },
        }[v.status] ?? { label: v.status, tone: 'neutral' as Tone }
    );
};

const detail = (): string => {
    const v = props.video;

    if (v.status === 'scheduled' || v.status === 'reserved') {
        return `${v.channel ? `Kênh ${v.channel} · ` : ''}hẹn ${fmt(v.scheduled_for)}`;
    }

    if (v.status === 'posted') {
        return `${v.channel ? `Kênh ${v.channel} · ` : ''}đăng ${fmt(v.posted_at)}`;
    }

    return v.reason ?? '';
};

// Bấm vào thẻ: bình thường mở chi tiết; đang ở chế độ "Chọn" (hoặc giữ Shift/Ctrl) thì chọn/bỏ chọn.
const onClick = (e: MouseEvent) => {
    if (props.selectMode || e.shiftKey || e.ctrlKey || e.metaKey) {
        emit('toggle', e.shiftKey);

        return;
    }

    emit('open');
};
</script>

<template>
    <div
        :data-card-id="video.id"
        :data-testid="`fork-rieng-card-${video.id}`"
        :class="
            cn(
                'flex flex-col overflow-hidden rounded-xl border bg-card shadow-sm transition',
                selected && 'ring-2 ring-primary',
                holding && 'scale-[0.97] ring-2 ring-primary/60',
                selectMode && 'cursor-pointer',
            )
        "
    >
        <div
            :class="
                cn(
                    'relative aspect-[9/16] w-full cursor-pointer overflow-hidden bg-muted',
                    !thumbFailed &&
                        !video.gone &&
                        !thumbLoaded &&
                        'animate-pulse',
                )
            "
            @click="onClick"
        >
            <img
                v-if="!thumbFailed && !video.gone"
                :src="`/auto/kho/rieng/video/${video.id}/thumb`"
                :alt="video.file_name"
                loading="lazy"
                decoding="async"
                draggable="false"
                :class="
                    cn(
                        'size-full object-cover transition-opacity duration-300',
                        thumbLoaded ? 'opacity-100' : 'opacity-0',
                    )
                "
                @load="thumbLoaded = true"
                @error="thumbFailed = true"
            />
            <div
                v-else
                class="flex size-full flex-col items-center justify-center gap-2 text-muted-foreground"
            >
                <IconMovie class="size-10 opacity-50" />
                <span class="text-xs">{{
                    video.gone ? 'Không còn file' : 'Chưa có ảnh xem trước'
                }}</span>
            </div>
            <span
                v-if="video.duration"
                class="absolute right-2 bottom-2 rounded bg-black/65 px-1.5 py-0.5 text-xs font-medium text-white tabular-nums"
                >{{ fmtDuration(video.duration) }}</span
            >
            <span
                :class="
                    cn(
                        'absolute top-2 left-2 rounded-md px-2 py-0.5 text-xs font-medium',
                        toneClasses[status().tone].chip,
                    )
                "
                :title="`Trạng thái: ${status().label}`"
                :aria-label="`Trạng thái: ${status().label}`"
                >{{ status().label }}</span
            >

            <!-- Ô chọn to, luôn thấy -->
            <button
                v-if="video.selectable"
                type="button"
                role="checkbox"
                :aria-checked="selected"
                :aria-label="`Chọn video ${video.file_name}`"
                :data-testid="`fork-rieng-check-${video.id}`"
                :class="
                    cn(
                        'absolute top-2 right-2 flex size-8 items-center justify-center rounded-full border shadow-sm transition',
                        selected
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-white/90 bg-black/35 text-transparent hover:bg-black/55',
                    )
                "
                @click.stop="emit('toggle', $event.shiftKey)"
            >
                <IconCheck class="size-5" stroke-width="3" />
            </button>
        </div>

        <div class="flex flex-1 flex-col gap-1 p-3 text-sm">
            <div class="truncate font-medium" :title="video.file_name">
                {{ video.file_name }}
            </div>
            <div
                class="flex min-w-0 items-center gap-1 text-xs text-muted-foreground"
                :title="video.rel_path ?? ''"
            >
                <span class="truncate">{{ video.folder }}</span>
                <span
                    v-if="subFolder"
                    class="inline-flex min-w-0 shrink items-center gap-0.5 rounded-md bg-secondary px-1.5 py-0.5 font-medium text-foreground"
                    :data-testid="`fork-rieng-subfolder-${video.id}`"
                >
                    <IconFolder class="size-3 shrink-0" />
                    <span class="truncate">{{ subFolder }}</span>
                </span>
            </div>
            <div
                v-if="video.moved_from"
                class="truncate text-xs text-muted-foreground"
                :title="`Anh vừa dời video từ ${video.moved_from}`"
            >
                Đã dời từ {{ video.moved_from }}
            </div>
            <div class="text-xs text-muted-foreground">
                Làm lúc
                {{
                    video.file_time
                        ? dayjs(video.file_time).format('HH:mm DD/MM/YYYY')
                        : (video.file_date ?? '—')
                }}
            </div>
            <div
                v-if="detail()"
                :class="cn('mt-1 text-xs', toneClasses[status().tone].text)"
            >
                {{ detail() }}
            </div>
            <div
                v-if="video.stats"
                class="mt-1 flex flex-wrap gap-x-3 text-xs text-muted-foreground"
                :data-testid="`fork-rieng-stats-${video.id}`"
                :title="
                    video.stats.collected_at
                        ? `Đọc lúc ${dayjs(video.stats.collected_at).format('HH:mm DD/MM')}`
                        : undefined
                "
            >
                <span
                    ><b class="text-foreground">{{
                        fmtNum(video.stats.views)
                    }}</b>
                    view</span
                >
                <span>{{ fmtNum(video.stats.likes) }} thích</span>
                <span>{{ fmtNum(video.stats.comments) }} bình luận</span>
                <span>{{ fmtNum(video.stats.shares) }} chia sẻ</span>
                <span v-if="video.stats.saves != null"
                    >{{ fmtNum(video.stats.saves) }} lưu</span
                >
            </div>
            <div
                v-if="video.music"
                class="mt-1 truncate text-xs font-medium"
                :title="video.music"
                :data-testid="`fork-rieng-music-${video.id}`"
            >
                <IconMusic class="mr-1 inline size-3.5" />{{ video.music }}
            </div>

            <!-- Sản phẩm đã gắn (có sau khi hẹn giờ) -->
            <div
                v-if="video.product"
                class="mt-1 flex items-center gap-1.5 text-xs font-medium"
                :data-testid="`fork-rieng-product-${video.id}`"
            >
                <ProductThumb :src="video.product.image" class="size-6" />
                <span class="truncate">{{ video.product.name }}</span>
            </div>

            <!-- Tự đăng theo khung: sẵn sàng / đang chờ gì, caption sẽ đăng -->
            <button
                v-if="auto()"
                type="button"
                :class="
                    cn(
                        'mt-1 flex flex-col gap-0.5 rounded-md border px-2 py-1.5 text-left text-xs leading-snug transition hover:bg-muted/60',
                        auto()!.ready
                            ? 'border-border bg-secondary/50'
                            : 'border-border bg-secondary/50',
                    )
                "
                :title="'Bấm để xem AI thấy gì, chọn sản phẩm, sửa caption, chọn kênh'"
                :data-testid="`fork-rieng-auto-${video.id}`"
                @click.stop="emit('auto')"
            >
                <span class="flex items-start gap-1 font-medium">
                    <IconCircleCheck
                        v-if="auto()!.ready"
                        class="mt-px size-3.5 shrink-0 text-success-text"
                    />
                    <IconAlertTriangle
                        v-else
                        class="mt-px size-3.5 shrink-0 text-warning"
                    />
                    <span class="min-w-0 flex-1">{{
                        auto()!.ready ? 'Sẵn sàng tự đăng' : auto()!.blocker
                    }}</span>
                    <span
                        v-if="auto()!.product_by"
                        class="shrink-0 self-start font-normal whitespace-nowrap text-muted-foreground"
                        >{{
                            auto()!.product_by === 'kid'
                                ? 'anh chọn'
                                : 'AI chọn'
                        }}</span
                    >
                </span>
                <span
                    v-if="
                        auto()!.final_caption ??
                        auto()!.kid_caption ??
                        auto()!.ai_caption
                    "
                    class="line-clamp-2 text-foreground/80"
                    >“{{
                        auto()!.final_caption ??
                        auto()!.kid_caption ??
                        auto()!.ai_caption
                    }}”</span
                >
                <span
                    v-else-if="auto()!.final_caption === ''"
                    class="text-muted-foreground"
                    >Đăng không caption</span
                >
                <span
                    v-if="
                        (auto()!.kid_hashtags ?? auto()!.ai_hashtags)?.length &&
                        auto()!.final_caption !== ''
                    "
                    class="truncate text-muted-foreground"
                    >{{
                        (auto()!.kid_hashtags ?? auto()!.ai_hashtags).join(' ')
                    }}</span
                >
            </button>

            <!-- Cờ trùng video -->
            <div
                v-if="video.duplicate"
                class="mt-1 flex items-start gap-1.5 rounded-md border border-l-2 border-l-warning bg-secondary px-2 py-1.5 text-xs leading-snug text-foreground"
                :data-testid="`fork-rieng-dup-${video.id}`"
            >
                <IconAlertTriangle class="mt-px size-3.5 shrink-0" />
                <span>
                    {{ video.duplicate.text }}
                    <a
                        v-if="video.duplicate.link"
                        :href="video.duplicate.link"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="underline"
                        >(mở link)</a
                    >
                </span>
            </div>

            <a
                v-if="video.tiktok_link"
                :href="video.tiktok_link"
                target="_blank"
                rel="noopener"
                class="text-xs text-primary underline"
                >Mở trên TikTok</a
            >

            <div class="mt-1.5 flex flex-wrap gap-1.5">
                <Button
                    v-if="video.selectable"
                    size="sm"
                    :variant="queued ? 'secondary' : 'outline'"
                    class="h-8"
                    :title="
                        queued
                            ? 'Bấm để bỏ khỏi giỏ chờ đăng'
                            : 'Cất vào giỏ chờ đăng để đăng sau'
                    "
                    :data-testid="`fork-rieng-queue-${video.id}`"
                    @click.stop="emit('queue')"
                >
                    <IconCheck v-if="queued" class="size-4" />
                    <IconPlaylistAdd v-else class="size-4" />
                    {{ queued ? 'Trong giỏ chờ' : '+ Giỏ chờ' }}
                </Button>
                <Button
                    v-if="video.gone && video.status === 'new'"
                    size="sm"
                    variant="outline"
                    class="h-8"
                    title="Bỏ video này khỏi danh sách (không xoá file nào)"
                    :data-testid="`fork-rieng-forget-${video.id}`"
                    @click.stop="emit('forget')"
                >
                    <IconTrash class="size-4" /> Bỏ khỏi danh sách
                </Button>
                <Button
                    v-if="video.can_retry"
                    size="sm"
                    variant="outline"
                    class="h-8"
                    @click.stop="emit('retry')"
                    >Thử lại</Button
                >
            </div>
        </div>
    </div>
</template>

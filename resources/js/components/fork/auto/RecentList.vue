<script setup lang="ts">
// "Vừa đăng" cho cột phải: danh sách gọn (ảnh bìa nhỏ, sản phẩm, giờ, lượt xem). Bài lỗi nằm trên cùng, có "Thử lại"
// khi máy chủ chắc chắn bài chưa lên TikTok.
import { Link, router } from '@inertiajs/vue3';
import { IconAlertCircle, IconEye, IconRefresh } from '@tabler/icons-vue';
import { ref } from 'vue';

import type { FailedRow, RecentRow } from '@/components/fork/auto/types';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import {
    cardCls,
    fmtCompact,
    toneClasses,
} from '@/components/fork/shared/status';
import { openVideo } from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = withDefaults(
    defineProps<{
        recent: RecentRow[];
        failed?: FailedRow[];
        productName: (code: string | null) => string;
        limit?: number;
    }>(),
    { failed: () => [], limit: 6 },
);

const retrying = ref<number | null>(null);
// Bài "chưa rõ đã lên chưa": chủ app phải tự kiểm tra TikTok Studio rồi xác nhận, app mới đăng lại.
const confirming = ref<FailedRow | null>(null);

const retry = (id: number, checked = false) => {
    retrying.value = id;
    router.post(
        `/auto/videos/${id}/thu-lai`,
        checked ? { da_kiem_tra: true } : {},
        {
            preserveScroll: true,
            onFinish: () => {
                retrying.value = null;
                confirming.value = null;
            },
        },
    );
};

const open = (id: number) =>
    openVideo(
        props.recent.map((r) => r.id),
        id,
    );

const when = (iso: string | null) => {
    if (!iso) {
        return '—';
    }

    const d = dayjs(iso);

    return d.isSame(dayjs(), 'day')
        ? d.format('HH:mm')
        : d.format('HH:mm DD/MM');
};
</script>

<template>
    <section
        id="vua-dang"
        :class="
            cn(cardCls, 'flex min-h-0 scroll-mt-24 flex-col overflow-hidden')
        "
        data-testid="fork-auto-recent"
    >
        <header
            class="flex shrink-0 items-center justify-between gap-2 border-b px-4 py-3"
        >
            <h2
                class="font-heading text-[15px] font-semibold tracking-[-0.01em]"
            >
                Vừa đăng
            </h2>
            <Link
                href="/auto/so-lieu"
                class="text-[12.5px] font-medium text-primary-text hover:underline"
                >Số liệu →</Link
            >
        </header>

        <ul
            v-if="failed.length"
            class="max-h-[232px] shrink-0 divide-y overflow-y-auto overscroll-contain border-b"
            data-testid="fork-auto-failed"
        >
            <li
                v-for="f in failed"
                :key="f.id"
                class="flex items-start gap-3 bg-red-50/50 px-4 py-3 dark:bg-red-950/20"
                :data-testid="`fork-auto-failed-${f.id}`"
            >
                <IconAlertCircle
                    :class="
                        cn('mt-0.5 size-4 shrink-0', toneClasses.danger.text)
                    "
                />
                <div class="min-w-0 flex-1">
                    <div class="truncate text-[13px] font-medium">
                        {{ productName(f.product_code) }}
                        <span class="font-normal text-muted-foreground"
                            >· {{ when(f.at) }}</span
                        >
                    </div>
                    <p
                        v-if="f.error"
                        class="line-clamp-2 text-[12.5px] text-red-700 dark:text-red-300"
                    >
                        {{ f.error }}
                    </p>
                    <p
                        v-if="!f.can_retry && f.retry_note"
                        class="mt-0.5 line-clamp-2 text-[12px] text-muted-foreground"
                    >
                        {{ f.retry_note }}
                    </p>
                </div>
                <Button
                    v-if="f.can_retry"
                    size="sm"
                    variant="outline"
                    class="h-7 shrink-0 px-2 text-[12.5px]"
                    :disabled="retrying !== null"
                    :data-testid="`fork-auto-retry-${f.id}`"
                    @click="retry(f.id)"
                >
                    <Spinner v-if="retrying === f.id" class="size-3.5" />
                    <IconRefresh v-else class="size-3.5" />
                    Thử lại
                </Button>
                <Button
                    v-else-if="f.can_confirm_retry"
                    size="sm"
                    variant="outline"
                    class="h-7 shrink-0 px-2 text-[12.5px]"
                    :disabled="retrying !== null"
                    :data-testid="`fork-auto-confirm-retry-${f.id}`"
                    @click="confirming = f"
                >
                    <IconRefresh class="size-3.5" />
                    Đã kiểm tra
                </Button>
            </li>
        </ul>

        <Dialog
            :open="confirming !== null"
            @update:open="
                (o) => {
                    if (!o && retrying === null) confirming = null;
                }
            "
        >
            <DialogContent class="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Bài này thật sự chưa lên TikTok?</DialogTitle>
                    <DialogDescription>
                        Chrome không báo được kết quả nên app không biết bài
                        <b>{{
                            confirming
                                ? productName(confirming.product_code)
                                : ''
                        }}</b>
                        <template v-if="confirming?.username">
                            của @{{ confirming.username }}</template
                        >
                        đã lên hay chưa. Hãy mở TikTok Studio, xem cả mục bài đã
                        hẹn giờ. Chỉ bấm đăng lại khi chắc chắn không thấy bài,
                        nếu không sẽ bị đăng trùng.
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter class="gap-2">
                    <Button
                        variant="outline"
                        :disabled="retrying !== null"
                        @click="confirming = null"
                        >Để sau</Button
                    >
                    <Button
                        :disabled="retrying !== null"
                        data-testid="fork-auto-confirm-retry-ok"
                        @click="confirming && retry(confirming.id, true)"
                    >
                        <Spinner v-if="retrying !== null" class="size-4" />
                        Chưa lên, đăng lại
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>

        <p
            v-if="!recent.length"
            class="px-4 py-8 text-center text-[13px] text-muted-foreground"
        >
            Chưa có bài nào lên TikTok.
        </p>

        <ul
            v-else
            class="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain p-1.5"
        >
            <li v-for="r in recent.slice(0, limit)" :key="r.id">
                <button
                    type="button"
                    class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-accent/50 focus-visible:outline-2 focus-visible:outline-ring"
                    :data-testid="`fork-auto-recent-${r.id}`"
                    @click="open(r.id)"
                >
                    <CoverThumb
                        :id="r.id"
                        :fallback="r.product_image"
                        class="h-[50px] w-[28px] rounded"
                    />
                    <div class="min-w-0 flex-1">
                        <div class="truncate text-[13px] font-medium">
                            {{ productName(r.product_code) }}
                        </div>
                        <div class="truncate text-[12px] text-muted-foreground">
                            {{ when(r.posted_at) }} · @{{ r.username }}
                        </div>
                    </div>
                    <span
                        class="flex shrink-0 items-center gap-1 text-[12.5px] tabular-nums"
                        :class="
                            r.views === null
                                ? 'text-muted-foreground/60'
                                : 'text-muted-foreground'
                        "
                        :title="
                            r.views === null
                                ? 'Chưa có số liệu'
                                : `${r.views} lượt xem`
                        "
                    >
                        <IconEye class="size-3.5" />
                        {{ r.views === null ? '—' : fmtCompact(r.views) }}
                    </span>
                </button>
            </li>
        </ul>
    </section>
</template>

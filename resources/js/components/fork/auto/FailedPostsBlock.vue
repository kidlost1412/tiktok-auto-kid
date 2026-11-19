<script setup lang="ts">
// "Bài không đăng được": khối đỏ ở Tổng quan, hiện ngay khi Chrome báo lỗi một bài (hết hàng, sai tài khoản...), không đợi tới
// giờ đăng. Mỗi dòng: ảnh bìa, giờ hẹn, kênh, lý do bằng tiếng Việt và việc nên làm. Bấm dòng để mở khung xem bài.
import { router } from '@inertiajs/vue3';
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-vue';
import { computed, ref } from 'vue';
import { toast } from 'vue-sonner';

import ConfirmRetryDialog from '@/components/fork/auto/ConfirmRetryDialog.vue';
import type { FailedPostRow } from '@/components/fork/auto/types';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import { toneClasses } from '@/components/fork/shared/status';
import { openVideo } from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{ rows: FailedPostRow[] }>();

const FOLD = 5;
const showAll = ref(false);
const shown = computed(() =>
    showAll.value ? props.rows : props.rows.slice(0, FOLD),
);

const busy = ref<number | null>(null);
// "Thử lại tất cả": đang gửi bài thứ mấy trên tổng số.
const all = ref<{ done: number; total: number } | null>(null);
const retryable = computed(() => props.rows.filter((r) => r.can_retry));
// Bài "chưa rõ đã lên chưa": chủ app phải tự kiểm tra TikTok Studio rồi xác nhận, app mới đăng lại.
const confirming = ref<FailedPostRow | null>(null);

const open = (id: number) =>
    openVideo(
        props.rows.map((r) => r.id),
        id,
    );

// Bài hẹn giờ (job): giao lại cho Chrome. Bài đã chốt lỗi (video): về kho để app xếp lại.
const retryUrl = (r: FailedPostRow) =>
    r.kind === 'job'
        ? `/auto/videos/${r.id}/dang-lai`
        : `/auto/videos/${r.id}/thu-lai`;

// Gửi một bài; trả về true nếu server nhận (không có lỗi).
const post = (r: FailedPostRow, checked = false) =>
    new Promise<boolean>((resolve) => {
        let ok = true;
        router.post(retryUrl(r), checked ? { da_kiem_tra: true } : {}, {
            preserveScroll: true,
            onError: () => {
                ok = false;
            },
            onFinish: () => resolve(ok),
        });
    });

const retry = async (r: FailedPostRow, checked = false) => {
    busy.value = r.id;
    await post(r, checked);
    busy.value = null;
    confirming.value = null;
};

// Lần lượt từng bài (không gửi dồn một lúc để khỏi nghẽn).
const retryAll = async () => {
    const list = [...retryable.value];

    if (!list.length || all.value) {
        return;
    }

    all.value = { done: 0, total: list.length };
    let sent = 0;
    let n = 0;

    for (const r of list) {
        busy.value = r.id;

        if (await post(r)) {
            sent++;
        }

        all.value = { done: ++n, total: list.length };
    }

    busy.value = null;
    all.value = null;
    toast.success(`Đã gửi lại ${sent} bài`);
};

const when = (iso: string | null) => {
    if (!iso) {
        return '—';
    }

    const d = dayjs(iso);

    return d.isSame(dayjs(), 'day')
        ? `hôm nay ${d.format('HH:mm')}`
        : d.format('HH:mm DD/MM');
};
</script>

<template>
    <section
        :class="cn('overflow-hidden rounded-xl border', toneClasses.danger.box)"
        data-testid="fork-auto-failed-posts"
        aria-label="Bài không đăng được"
    >
        <header class="flex items-center gap-2.5 px-4 py-3">
            <IconAlertTriangle class="size-5 shrink-0" />
            <h2 class="font-heading text-[0.9375rem] font-semibold">
                Bài không đăng được ({{ rows.length }})
            </h2>
            <span
                class="hidden text-[0.8125rem] font-normal opacity-80 sm:inline"
                >Bấm vào bài để xem lý do và xử lý.</span
            >
            <Button
                v-if="retryable.length > 1"
                size="sm"
                variant="outline"
                class="ml-auto h-8 shrink-0 bg-background px-2.5 text-[0.8125rem]"
                :disabled="busy !== null"
                data-testid="fork-auto-failed-retry-all"
                @click="retryAll"
            >
                <Spinner v-if="all" class="size-3.5" />
                <IconRefresh v-else class="size-3.5" />
                {{
                    all
                        ? `Đang gửi ${all.done}/${all.total}…`
                        : `Thử lại tất cả (${retryable.length})`
                }}
            </Button>
        </header>

        <ul
            class="divide-y divide-red-200/70 border-t border-red-200/70 dark:divide-red-900/50 dark:border-red-900/50"
        >
            <li
                v-for="r in shown"
                :key="r.id"
                class="flex items-start gap-3 bg-background/60 px-4 py-3"
                :data-testid="`fork-auto-failed-post-${r.id}`"
            >
                <button
                    type="button"
                    class="flex min-w-0 flex-1 items-start gap-3 rounded-lg text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                    @click="open(r.id)"
                >
                    <CoverThumb
                        :id="r.id"
                        :fallback="r.product_image"
                        class="h-[56px] w-[32px] rounded"
                    />
                    <div class="min-w-0 flex-1 text-foreground">
                        <div
                            class="flex min-w-0 flex-wrap items-baseline gap-x-2 text-[0.8125rem]"
                        >
                            <span class="font-semibold tabular-nums">{{
                                when(r.at)
                            }}</span>
                            <span
                                v-if="r.username"
                                class="text-muted-foreground"
                                >@{{ r.username }}</span
                            >
                            <span class="truncate text-muted-foreground">{{
                                r.product_label
                            }}</span>
                        </div>
                        <p
                            v-if="r.caption"
                            class="truncate text-[0.75rem] text-muted-foreground"
                            :title="r.caption"
                        >
                            {{ r.caption }}
                        </p>
                        <p
                            :class="
                                cn(
                                    'mt-0.5 text-[0.8125rem] font-medium',
                                    toneClasses.danger.text,
                                )
                            "
                        >
                            {{ r.title }}
                        </p>
                        <p class="text-[0.75rem] text-muted-foreground">
                            {{ r.fix }}
                        </p>
                        <p
                            v-if="!r.can_retry && r.retry_note"
                            class="mt-0.5 text-[0.75rem] text-muted-foreground"
                        >
                            {{ r.retry_note }}
                        </p>
                    </div>
                </button>
                <Button
                    v-if="r.can_retry"
                    size="sm"
                    variant="outline"
                    class="h-8 shrink-0 bg-background px-2.5 text-[0.8125rem]"
                    :disabled="busy !== null"
                    :data-testid="`fork-auto-failed-post-retry-${r.id}`"
                    @click="retry(r)"
                >
                    <Spinner v-if="busy === r.id" class="size-3.5" />
                    <IconRefresh v-else class="size-3.5" />
                    {{ r.kind === 'job' ? 'Đăng lại' : 'Thử lại' }}
                </Button>
                <Button
                    v-else-if="r.can_confirm_retry"
                    size="sm"
                    variant="outline"
                    class="h-8 shrink-0 bg-background px-2.5 text-[0.8125rem]"
                    :disabled="busy !== null"
                    :data-testid="`fork-auto-failed-post-confirm-${r.id}`"
                    @click="confirming = r"
                >
                    <IconRefresh class="size-3.5" />
                    Đã kiểm tra
                </Button>
            </li>
        </ul>

        <div
            v-if="rows.length > FOLD"
            class="border-t border-red-200/70 bg-background/60 px-4 py-2 text-center dark:border-red-900/50"
        >
            <button
                type="button"
                class="text-[0.7812rem] font-medium text-primary-text hover:underline"
                @click="showAll = !showAll"
            >
                {{ showAll ? 'Thu gọn' : `Xem tất cả ${rows.length} bài` }}
            </button>
        </div>

        <ConfirmRetryDialog
            :target="
                confirming
                    ? {
                          label: confirming.product_label ?? 'này',
                          username: confirming.username,
                      }
                    : null
            "
            :busy="busy !== null"
            ok-testid="fork-auto-failed-post-confirm-ok"
            @cancel="confirming = null"
            @confirm="confirming && retry(confirming, true)"
        />
    </section>
</template>

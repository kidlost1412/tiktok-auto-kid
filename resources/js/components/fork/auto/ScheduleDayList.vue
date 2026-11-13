<script setup lang="ts">
// Danh sách bài của MỘT ngày trong Lịch đăng. Dùng cho cả kiểu tab (màn hẹp) và kiểu 3 cột (màn rộng, `compact`).
// Hôm nay: các bài đã đăng gấp lại thành một dòng để mắt đi thẳng tới bài sắp tới; có vạch "Bây giờ".
import {
    IconCalendarOff,
    IconChevronDown,
    IconExternalLink,
    IconShoppingCart,
} from '@tabler/icons-vue';
import { computed, ref, watch } from 'vue';

import type { ScheduleEntry } from '@/components/fork/auto/types';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import { statusOf, toneClasses } from '@/components/fork/shared/status';
import StatusChip from '@/components/fork/shared/StatusChip.vue';
import { openVideo } from '@/components/fork/viewer';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    dayKey: string;
    list: ScheduleEntry[];
    isToday: boolean;
    multi: boolean;
    /** Kiểu gọn cho cột hẹp (3 ngày cạnh nhau). */
    compact?: boolean;
}>();

const showDone = ref(false);

watch(
    () => props.dayKey,
    () => {
        showDone.value = false;
    },
);

const isEmptySlot = (e: ScheduleEntry) =>
    e.state === 'projected' && !e.video_id;

// Hôm nay: bài đã đăng xong gấp lại.
const done = computed(() =>
    props.isToday ? props.list.filter((e) => e.state === 'posted') : [],
);
const rest = computed(() => props.list.filter((e) => !done.value.includes(e)));
const shown = computed(() => [
    ...(showDone.value ? done.value : []),
    ...rest.value,
]);

const nowIndex = computed(() => {
    if (!props.isToday) {
        return -1;
    }

    const now = dayjs();
    const i = rest.value.findIndex((e) => dayjs(e.at).isAfter(now));

    return i === -1 ? rest.value.length : i;
});

const videoId = (e: ScheduleEntry) => e.id ?? e.video_id ?? null;
const isLate = (e: ScheduleEntry) =>
    !['projected', 'posted', 'failed', 'tiktok_scheduled'].includes(e.state) &&
    dayjs(e.at).isBefore(dayjs().subtract(2, 'minute'));

const dayIds = computed(() =>
    props.list
        .map((e) => videoId(e))
        .filter((x): x is number => x !== null && x !== undefined),
);

const open = (e: ScheduleEntry) => {
    const id = videoId(e);

    if (id !== null && id !== undefined) {
        openVideo(dayIds.value, id);
    }
};

// Kiểu gọn: trạng thái thường gặp chỉ là một chấm màu (có chú thích ở đầu bảng); trạng thái cần chú ý mới thành nhãn.
const QUIET = ['scheduled', 'posted', 'projected'];

const timeW = computed(() => (props.compact ? 'w-[40px]' : 'w-[52px]'));
</script>

<template>
    <div
        :data-testid="`fork-auto-day-${dayKey}`"
        :class="cn('flex flex-col', compact ? 'py-1.5' : 'py-2')"
    >
        <div
            v-if="!list.length"
            :class="
                cn(
                    'flex flex-col items-center gap-2 text-center',
                    compact ? 'px-4 py-10' : 'px-6 py-14',
                )
            "
        >
            <IconCalendarOff class="size-7 text-muted-foreground/60" />
            <div class="text-[0.8438rem] font-medium">Chưa có giờ đăng nào</div>
            <p class="max-w-xs text-[0.7812rem] text-muted-foreground">
                Kênh đang tắt, đã đủ hạn mức hoặc ngoài khung giờ. Nới khung giờ
                bằng nút “Chỉnh” ở thẻ kênh.
            </p>
        </div>

        <!-- Đã đăng hôm nay (gấp lại) -->
        <button
            v-if="done.length"
            type="button"
            :class="
                cn(
                    'flex items-center gap-3 rounded-lg text-left text-[0.8125rem] transition-colors hover:bg-accent/50',
                    compact ? 'mx-2 px-2 py-1.5' : 'mx-3 px-2 py-2',
                )
            "
            :aria-expanded="showDone"
            data-testid="fork-auto-done-toggle"
            @click="showDone = !showDone"
        >
            <span :class="cn('flex justify-end', timeW)">
                <span
                    :class="
                        cn(
                            'flex size-6 items-center justify-center rounded-full',
                            toneClasses.success.chip,
                        )
                    "
                >
                    <IconChevronDown
                        :class="
                            cn(
                                'size-4 transition-transform',
                                showDone && 'rotate-180',
                            )
                        "
                    />
                </span>
            </span>
            <span class="min-w-0 truncate">
                <b class="font-semibold">{{ done.length }} bài đã đăng</b>
                <span class="text-muted-foreground tabular-nums">
                    · {{ dayjs(done[0].at).format('HH:mm') }}–{{
                        dayjs(done[done.length - 1].at).format('HH:mm')
                    }}</span
                >
            </span>
            <span class="ml-auto shrink-0 text-[0.7812rem] text-primary-text">{{
                showDone ? 'Ẩn' : 'Xem'
            }}</span>
        </button>

        <ol class="flex flex-col">
            <template
                v-for="(e, i) in shown"
                :key="`${e.channelId}-${e.state}-${e.id ?? e.video_id ?? e.at}`"
            >
                <li
                    v-if="
                        isToday && i === nowIndex + (showDone ? done.length : 0)
                    "
                    :class="
                        cn(
                            'flex items-center gap-3 py-1.5',
                            compact ? 'mx-4' : 'mx-5',
                        )
                    "
                    aria-label="Bây giờ"
                >
                    <span
                        :class="
                            cn(
                                'text-right text-[0.75rem] font-semibold text-primary-text tabular-nums',
                                timeW,
                            )
                        "
                        >{{ dayjs().format('HH:mm') }}</span
                    >
                    <span class="size-2 rounded-full bg-primary" />
                    <span class="h-px flex-1 bg-primary/40" />
                    <span class="text-[0.75rem] font-medium text-primary-text"
                        >Bây giờ</span
                    >
                </li>
                <li>
                    <div
                        v-if="isEmptySlot(e)"
                        :class="
                            cn(
                                'grid items-center gap-3 rounded-lg px-2 text-muted-foreground',
                                compact
                                    ? 'mx-2 grid-cols-[40px_minmax(0,1fr)] py-1 text-[0.7812rem]'
                                    : 'mx-3 grid-cols-[52px_minmax(0,1fr)] py-2 text-[0.8125rem]',
                            )
                        "
                    >
                        <span class="text-right tabular-nums">{{
                            dayjs(e.at).format('HH:mm')
                        }}</span>
                        <span
                            :class="
                                cn(
                                    'truncate rounded-md border border-dashed',
                                    compact ? 'px-2.5 py-1' : 'px-3 py-1.5',
                                )
                            "
                        >
                            Giờ trống —
                            {{
                                e.empty_reason === 'chưa chọn giỏ hàng'
                                    ? 'chưa chọn giỏ hàng'
                                    : 'hết video đã có giỏ'
                            }}
                        </span>
                    </div>
                    <div
                        v-else
                        role="button"
                        tabindex="0"
                        :title="
                            compact && e.cart_name
                                ? `Giỏ: ${e.cart_name}`
                                : undefined
                        "
                        :class="
                            cn(
                                'group grid cursor-pointer items-center rounded-lg px-2 transition-colors hover:bg-accent/50 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring',
                                compact
                                    ? 'mx-2 grid-cols-[40px_28px_minmax(0,1fr)_auto] gap-2.5 py-1.5'
                                    : 'mx-3 grid-cols-[52px_36px_minmax(0,1fr)_auto] gap-3 py-2',
                                e.state === 'failed' &&
                                    'bg-red-50/60 dark:bg-red-950/20',
                                compact &&
                                    e.state === 'posted' &&
                                    'opacity-70 hover:opacity-100',
                            )
                        "
                        @click="open(e)"
                        @keydown.enter.self.prevent="open(e)"
                        @keydown.space.self.prevent="open(e)"
                    >
                        <span
                            :class="
                                cn(
                                    'text-right font-semibold tabular-nums',
                                    compact ? 'text-[0.8438rem]' : 'text-[0.9375rem]',
                                    e.state === 'projected' &&
                                        'font-medium text-muted-foreground',
                                    e.state === 'posted' &&
                                        'text-muted-foreground',
                                )
                            "
                            >{{ dayjs(e.at).format('HH:mm') }}</span
                        >
                        <CoverThumb
                            :id="videoId(e)"
                            :fallback="e.product_image"
                            :class="
                                cn(
                                    compact
                                        ? 'h-[48px] w-[28px] rounded'
                                        : 'h-[64px] w-[36px] rounded-md',
                                    e.state === 'projected' && 'opacity-70',
                                )
                            "
                        />
                        <div class="min-w-0">
                            <div class="flex min-w-0 items-center gap-2">
                                <span
                                    :class="
                                        cn(
                                            'truncate font-medium',
                                            compact
                                                ? 'text-[0.8125rem]'
                                                : 'text-[0.875rem]',
                                        )
                                    "
                                    >{{
                                        e.product_label ?? e.product_code ?? '—'
                                    }}</span
                                >
                                <span
                                    v-if="multi"
                                    class="shrink-0 text-[0.75rem] text-muted-foreground"
                                    >@{{ e.username }}</span
                                >
                            </div>
                            <p
                                v-if="e.error"
                                :class="
                                    cn(
                                        'truncate text-[0.75rem]',
                                        toneClasses.danger.text,
                                    )
                                "
                                :title="e.error"
                            >
                                {{ e.error }}
                            </p>
                            <p
                                v-else-if="e.caption"
                                class="truncate text-[0.75rem] text-muted-foreground"
                                :title="e.caption"
                            >
                                {{ e.caption }}
                            </p>
                            <div
                                v-if="!compact && e.cart_name"
                                class="mt-0.5 flex min-w-0 items-center gap-1 text-[0.75rem] text-muted-foreground/90"
                            >
                                <IconShoppingCart class="size-3.5 shrink-0" />
                                <span class="truncate">{{ e.cart_name }}</span>
                            </div>
                        </div>
                        <div
                            :class="
                                cn(
                                    'flex items-center',
                                    compact ? 'gap-1.5' : 'gap-2',
                                )
                            "
                        >
                            <span
                                v-if="isLate(e)"
                                :class="
                                    cn(
                                        'rounded-full px-2 py-0.5 text-[0.7188rem] font-medium',
                                        toneClasses.warn.chip,
                                    )
                                "
                                title="Đã quá giờ hẹn mà chưa đăng xong"
                                >Trễ</span
                            >
                            <template v-if="compact">
                                <a
                                    v-if="e.link"
                                    :href="e.link"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="flex size-6 items-center justify-center rounded-md text-muted-foreground opacity-0 group-hover:opacity-100 hover:bg-accent hover:text-foreground focus-visible:opacity-100"
                                    title="Mở trên TikTok"
                                    aria-label="Mở trên TikTok"
                                    @click.stop
                                >
                                    <IconExternalLink class="size-3.5" />
                                </a>
                                <span
                                    v-if="QUIET.includes(e.state)"
                                    :class="
                                        cn(
                                            'size-2 rounded-full',
                                            e.state === 'scheduled'
                                                ? toneClasses.info.dot
                                                : toneClasses[
                                                      statusOf(e.state).tone
                                                  ].dot,
                                            e.state === 'projected' &&
                                                'border border-dashed border-muted-foreground bg-transparent',
                                        )
                                    "
                                    :title="statusOf(e.state).label"
                                    :aria-label="statusOf(e.state).label"
                                />
                                <StatusChip
                                    v-else
                                    :status="e.state"
                                    class="h-5 gap-1 px-1.5 text-[0.7188rem] [&_svg]:size-3"
                                />
                            </template>
                            <template v-else>
                                <StatusChip
                                    :status="e.state"
                                    class="h-6 px-2 text-[0.75rem] max-sm:hidden"
                                />
                                <span
                                    :class="
                                        cn(
                                            'size-2 rounded-full sm:hidden',
                                            toneClasses[statusOf(e.state).tone]
                                                .dot,
                                        )
                                    "
                                />
                                <a
                                    v-if="e.link"
                                    :href="e.link"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
                                    title="Mở trên TikTok"
                                    aria-label="Mở trên TikTok"
                                    @click.stop
                                >
                                    <IconExternalLink class="size-4" />
                                </a>
                            </template>
                        </div>
                    </div>
                </li>
            </template>
            <li
                v-if="isToday && rest.length && nowIndex === rest.length"
                :class="
                    cn(
                        'flex items-center gap-3 py-1.5',
                        compact ? 'mx-4' : 'mx-5',
                    )
                "
            >
                <span
                    :class="
                        cn(
                            'text-right text-[0.75rem] font-semibold text-primary-text tabular-nums',
                            timeW,
                        )
                    "
                    >{{ dayjs().format('HH:mm') }}</span
                >
                <span class="size-2 rounded-full bg-primary" />
                <span class="h-px flex-1 bg-primary/40" />
                <span class="text-[0.75rem] font-medium text-primary-text"
                    >Bây giờ · hết bài trong ngày</span
                >
            </li>
        </ol>
    </div>
</template>

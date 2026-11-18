<script setup lang="ts">
// Danh sách bài của MỘT ngày trong Lịch đăng. Dùng cho cả kiểu tab (màn hẹp) và kiểu 3 cột (màn rộng, `compact`).
// Hôm nay: các bài đã đăng gấp lại thành một dòng để mắt đi thẳng tới bài sắp tới; có vạch "Bây giờ".
import { router } from '@inertiajs/vue3';
import {
    IconBolt,
    IconCalendarOff,
    IconChevronDown,
    IconClockEdit,
    IconExternalLink,
    IconLoader2,
    IconShoppingCart,
    IconShoppingCartOff,
    IconTrash,
} from '@tabler/icons-vue';
import { computed, ref, watch } from 'vue';

import { channelColor } from '@/components/fork/auto/channelColors';
import type { DropPoint } from '@/components/fork/auto/dragMove';
import { dragging, pointAt } from '@/components/fork/auto/dragMove';
import RemoveDialog from '@/components/fork/auto/RemoveDialog.vue';
import RescheduleDialog from '@/components/fork/auto/RescheduleDialog.vue';
import type { ScheduleEntry } from '@/components/fork/auto/types';
import { moveWithUndo } from '@/components/fork/auto/undo';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import SourceBadge from '@/components/fork/shared/SourceBadge.vue';
import {
    lichStatus,
    statusOf,
    toneClasses,
} from '@/components/fork/shared/status';
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

// "Đổi giờ": bài đã xếp mà chưa đăng (kể cả đã hẹn sẵn trên TikTok), giờ còn ở tương lai.
const canMove = (e: ScheduleEntry) =>
    !!e.id && !!e.can_reschedule && dayjs(e.at).isAfter(dayjs());
const moving = (e: ScheduleEntry) => !!e.reschedule?.open;
const moveOpen = ref(false);
const moveEntry = ref<ScheduleEntry | null>(null);
const startMove = (e: ScheduleEntry) => {
    moveEntry.value = e;
    moveOpen.value = true;
};

// Kéo thả: kéo một bài (đổi giờ được) thả vào bất kỳ chỗ nào trong danh sách ngày (cả ngày khác). Kéo tới đâu hiện giờ
// tới đó; thả ra là đổi giờ luôn, có "Hoàn tác" vài giây.
const rootEl = ref<HTMLElement | null>(null);
const drop = ref<DropPoint | null>(null);
const keyOf = (e: ScheduleEntry | null) =>
    e ? `${e.channelId}-${e.id ?? e.video_id ?? e.at}` : 'end';
const onDragStart = (ev: DragEvent, e: ScheduleEntry) => {
    dragging.value = e;

    if (ev.dataTransfer) {
        ev.dataTransfer.effectAllowed = 'move';
        ev.dataTransfer.setData('text/plain', String(e.id));
    }
};
const onDragEnd = () => {
    dragging.value = null;
    drop.value = null;
};
const onListOver = (ev: DragEvent) => {
    const d = dragging.value;

    if (!d || !rootEl.value) {
        return;
    }

    ev.preventDefault();

    if (ev.dataTransfer) {
        ev.dataTransfer.dropEffect = 'move';
    }

    drop.value = pointAt(rootEl.value, ev.clientY, props.dayKey, keyOf(d));
};
const onListLeave = (ev: DragEvent) => {
    const to = ev.relatedTarget as Node | null;

    if (!to || !rootEl.value?.contains(to)) {
        drop.value = null;
    }
};
const onListDrop = (ev: DragEvent) => {
    const d = dragging.value;
    const p = drop.value;
    drop.value = null;
    dragging.value = null;

    if (!d || !p) {
        return;
    }

    ev.preventDefault();

    if (dayjs(p.at).isSame(dayjs(d.at), 'minute')) {
        return;
    }

    void moveWithUndo(d, p.at, () => router.reload({ only: ['lich'] }));
};
const dropLabel = computed(() => {
    const p = drop.value;

    if (!p) {
        return '';
    }

    const at = dayjs(p.at);

    return at.isSame(dayjs(), 'day')
        ? at.format('HH:mm')
        : `${at.format('HH:mm')} · ${at.format('DD/MM')}`;
});

// Xoá / bỏ xếp lịch ngay trên dòng lịch.
const removeOpen = ref(false);
const removeEntry = ref<ScheduleEntry | null>(null);
const canRemove = (e: ScheduleEntry) =>
    !!e.id &&
    ['scheduled', 'direct', 'reserved', 'tiktok_scheduled', 'failed'].includes(
        e.state,
    );
const startRemove = (e: ScheduleEntry) => {
    removeEntry.value = e;
    removeOpen.value = true;
};

// Kiểu gọn: trạng thái thường gặp chỉ là một chấm màu (có chú thích ở đầu bảng); trạng thái cần chú ý mới thành nhãn.
// "Chưa lên TikTok" / "Đăng thẳng" luôn là nhãn chữ để phân biệt rõ với bài đã hẹn trên TikTok.
const QUIET = ['tiktok_scheduled', 'posted', 'projected'];
// Cột hẹp: video chưa lên TikTok / đăng thẳng / đang gửi chỉ hiện biểu tượng màu riêng (chú thích ở đầu bảng, rê chuột xem chữ).
const ICON_ONLY = ['scheduled', 'direct', 'uploading'];

const timeW = computed(() => (props.compact ? 'w-[46px]' : 'w-[58px]'));
</script>

<template>
    <div
        ref="rootEl"
        :data-testid="`fork-auto-day-${dayKey}`"
        :class="cn('relative flex flex-col', compact ? 'py-1.5' : 'py-2')"
        @dragover="onListOver"
        @dragleave="onListLeave"
        @drop="onListDrop"
    >
        <!-- Vạch thả + giờ ở chỗ đang kéo tới -->
        <div
            v-if="drop && dragging"
            class="pointer-events-none absolute inset-x-1 z-30 flex -translate-y-1/2 items-center gap-1.5"
            :style="{ top: `${drop.y}px` }"
            data-testid="fork-auto-drop-marker"
        >
            <span
                :class="
                    cn(
                        'rounded-full px-2.5 py-1 text-[1rem] leading-none font-bold text-white tabular-nums shadow-lg',
                        drop.tooSoon ? 'bg-red-600' : 'bg-primary',
                    )
                "
                >{{ dropLabel
                }}<template v-if="drop.tooSoon"> · quá sát giờ</template></span
            >
            <span
                :class="
                    cn(
                        'h-0.5 flex-1 rounded-full',
                        drop.tooSoon ? 'bg-red-600' : 'bg-primary',
                    )
                "
            />
        </div>
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
            <div class="text-[0.9375rem] font-medium">Chưa có giờ đăng nào</div>
            <p class="max-w-xs text-[0.8438rem] text-muted-foreground">
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
                    'flex items-center gap-3 rounded-lg text-left text-[0.875rem] transition-colors hover:bg-accent/50',
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
            <span class="ml-auto shrink-0 text-[0.8438rem] text-primary-text">{{
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
                                'text-right text-[0.8125rem] font-semibold text-primary-text tabular-nums',
                                timeW,
                            )
                        "
                        >{{ dayjs().format('HH:mm') }}</span
                    >
                    <span class="size-2 rounded-full bg-primary" />
                    <span class="h-px flex-1 bg-primary/40" />
                    <span class="text-[0.8125rem] font-medium text-primary-text"
                        >Bây giờ</span
                    >
                </li>
                <li
                    class="relative"
                    :data-row-at="e.at"
                    :data-row-key="keyOf(e)"
                    :data-slot="isEmptySlot(e) ? '1' : undefined"
                >
                    <div
                        v-if="isEmptySlot(e)"
                        :class="
                            cn(
                                'grid items-center gap-3 rounded-lg px-2 text-muted-foreground',
                                compact
                                    ? 'mx-2 grid-cols-[46px_minmax(0,1fr)] py-1 text-[0.8438rem]'
                                    : 'mx-3 grid-cols-[58px_minmax(0,1fr)] py-2 text-[0.875rem]',
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
                                'group relative grid cursor-pointer items-center rounded-lg px-2 transition-colors hover:bg-accent/50 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring data-[dragging=true]:opacity-40',
                                compact
                                    ? 'mx-2 grid-cols-[46px_30px_minmax(0,1fr)_auto] gap-2.5 py-1.5'
                                    : 'mx-3 grid-cols-[58px_38px_minmax(0,1fr)_auto] gap-3 py-2',
                                e.state === 'failed' &&
                                    'bg-red-50/60 dark:bg-red-950/20',
                                compact &&
                                    e.state === 'posted' &&
                                    'opacity-70 hover:opacity-100',
                            )
                        "
                        :draggable="canMove(e) && !moving(e)"
                        :data-dragging="
                            dragging && keyOf(dragging) === keyOf(e)
                                ? 'true'
                                : undefined
                        "
                        @dragstart="onDragStart($event, e)"
                        @dragend="onDragEnd"
                        @click="open(e)"
                        @keydown.enter.self.prevent="open(e)"
                        @keydown.space.self.prevent="open(e)"
                    >
                        <!-- Màu của kênh -->
                        <span
                            v-if="multi"
                            aria-hidden="true"
                            :class="
                                cn(
                                    'absolute inset-y-2 left-0 w-[3px] rounded-full',
                                    channelColor(e.color).dot,
                                )
                            "
                        />
                        <!-- Bấm giờ để đổi giờ ngay (bài đã xếp mà chưa đăng) -->
                        <button
                            v-if="canMove(e)"
                            type="button"
                            :class="
                                cn(
                                    'justify-self-end rounded-md px-1 text-right font-semibold tabular-nums underline decoration-muted-foreground/50 decoration-dotted underline-offset-4 hover:bg-accent hover:decoration-foreground focus-visible:outline-2 focus-visible:outline-ring',
                                    compact
                                        ? '-mr-1 text-[0.9375rem]'
                                        : '-mr-1 text-[1rem]',
                                    moving(e) && 'text-primary-text',
                                )
                            "
                            :title="
                                moving(e)
                                    ? 'Đang xoá bài hẹn cũ trên TikTok để đổi giờ…'
                                    : 'Bấm để đổi giờ'
                            "
                            :data-testid="`fork-auto-time-${e.id}`"
                            @click.stop="startMove(e)"
                            @keydown.enter.stop
                            @keydown.space.stop
                        >
                            {{ dayjs(e.at).format('HH:mm') }}
                        </button>
                        <span
                            v-else
                            :class="
                                cn(
                                    'text-right font-semibold tabular-nums',
                                    compact
                                        ? 'text-[0.9375rem]'
                                        : 'text-[1rem]',
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
                                        ? 'h-[52px] w-[30px] rounded'
                                        : 'h-[68px] w-[38px] rounded-md',
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
                                                ? 'text-[0.875rem]'
                                                : 'text-[0.9375rem]',
                                        )
                                    "
                                    >{{
                                        e.product_label ?? e.product_code ?? '—'
                                    }}</span
                                >
                                <SourceBadge
                                    :source="e.source"
                                    :class="
                                        compact
                                            ? 'h-4 px-1 text-[0.625rem] [&_svg]:size-2.5'
                                            : ''
                                    "
                                />
                                <span
                                    v-if="multi"
                                    :class="
                                        cn(
                                            'max-w-[9rem] shrink-0 truncate rounded px-1.5 text-[0.75rem] leading-[1.125rem] font-medium',
                                            channelColor(e.color).chip,
                                        )
                                    "
                                    >@{{ e.username }}</span
                                >
                            </div>
                            <p
                                v-if="e.error"
                                :class="
                                    cn(
                                        'truncate text-[0.8125rem]',
                                        toneClasses.danger.text,
                                    )
                                "
                                :title="e.error_full ?? e.error"
                            >
                                {{ e.error }}
                            </p>
                            <p
                                v-else-if="e.cart_warn"
                                :class="
                                    cn(
                                        'flex min-w-0 items-start gap-1 text-[0.8125rem] font-medium',
                                        toneClasses.danger.text,
                                    )
                                "
                                :title="e.cart_warn"
                                :data-testid="`fork-auto-cart-warn-${e.id}`"
                            >
                                <IconShoppingCartOff
                                    class="mt-px size-3.5 shrink-0"
                                />
                                <span class="line-clamp-2">{{
                                    e.cart_warn
                                }}</span>
                            </p>
                            <p
                                v-else-if="e.note"
                                :class="
                                    cn(
                                        'line-clamp-2 text-[0.8125rem]',
                                        toneClasses.warn.text,
                                    )
                                "
                                :title="e.note"
                            >
                                {{ e.note }}
                            </p>
                            <p
                                v-else-if="e.caption"
                                class="truncate text-[0.8125rem] text-muted-foreground"
                                :title="e.caption"
                            >
                                {{ e.caption }}
                            </p>
                            <div
                                v-if="!compact && e.cart_name"
                                class="mt-0.5 flex min-w-0 items-center gap-1 text-[0.8125rem] text-muted-foreground/90"
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
                                        'rounded-full px-2 py-0.5 text-[0.75rem] font-medium',
                                        toneClasses.warn.chip,
                                    )
                                "
                                title="Đã quá giờ hẹn mà chưa đăng xong"
                                >Trễ</span
                            >
                            <button
                                v-if="canMove(e)"
                                type="button"
                                :class="
                                    cn(
                                        'flex items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-ring',
                                        compact ? 'size-6' : 'size-7',
                                        compact &&
                                            !moving(e) &&
                                            'opacity-0 group-hover:opacity-100',
                                        moving(e) && 'text-primary-text',
                                    )
                                "
                                :title="
                                    moving(e)
                                        ? 'Đang xoá bài hẹn cũ trên TikTok để đổi giờ…'
                                        : 'Đổi giờ'
                                "
                                :aria-label="
                                    moving(e) ? 'Đang đổi giờ' : 'Đổi giờ'
                                "
                                :data-testid="`fork-auto-move-${e.id}`"
                                @click.stop="startMove(e)"
                                @keydown.enter.stop
                                @keydown.space.stop
                            >
                                <IconLoader2
                                    v-if="moving(e)"
                                    :class="
                                        cn(
                                            'animate-spin',
                                            compact ? 'size-3.5' : 'size-4',
                                        )
                                    "
                                />
                                <IconClockEdit
                                    v-else
                                    :class="compact ? 'size-3.5' : 'size-4'"
                                />
                            </button>
                            <button
                                v-if="canRemove(e) && !moving(e)"
                                type="button"
                                :class="
                                    cn(
                                        'flex items-center justify-center rounded-md text-muted-foreground opacity-0 group-hover:opacity-100 hover:bg-accent hover:text-red-600 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-ring',
                                        compact ? 'size-6' : 'size-7',
                                    )
                                "
                                title="Xoá hoặc bỏ xếp lịch"
                                aria-label="Xoá hoặc bỏ xếp lịch"
                                :data-testid="`fork-auto-remove-${e.id}`"
                                @click.stop="startRemove(e)"
                                @keydown.enter.stop
                                @keydown.space.stop
                            >
                                <IconTrash
                                    :class="compact ? 'size-3.5' : 'size-4'"
                                />
                            </button>
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
                                <IconBolt
                                    v-if="e.state === 'projected' && e.direct"
                                    :class="
                                        cn('size-3.5', toneClasses.violet.text)
                                    "
                                    title="Dự kiến · trong khung đăng thẳng"
                                    aria-label="Dự kiến, đăng thẳng"
                                />
                                <span
                                    v-else-if="QUIET.includes(e.state)"
                                    :class="
                                        cn(
                                            'size-2 rounded-full',
                                            toneClasses[statusOf(e.state).tone]
                                                .dot,
                                            e.state === 'projected' &&
                                                'border border-dashed border-muted-foreground bg-transparent',
                                        )
                                    "
                                    :title="statusOf(e.state).label"
                                    :aria-label="statusOf(e.state).label"
                                />
                                <StatusChip
                                    v-else
                                    :status="lichStatus(e.state)"
                                    :icon-only="ICON_ONLY.includes(e.state)"
                                    class="h-5 gap-1 px-1.5 text-[0.75rem] [&_svg]:size-3"
                                />
                            </template>
                            <template v-else>
                                <StatusChip
                                    :status="lichStatus(e.state)"
                                    class="h-6 px-2 text-[0.8125rem] max-sm:hidden"
                                />
                                <span
                                    v-if="e.state === 'projected' && e.direct"
                                    :class="
                                        cn(
                                            'inline-flex items-center gap-1 text-[0.8125rem] max-sm:hidden',
                                            toneClasses.violet.text,
                                        )
                                    "
                                    title="Giờ dự kiến trong khung đăng thẳng: tới giờ Chrome đăng luôn"
                                    ><IconBolt class="size-3.5" />Đăng
                                    thẳng</span
                                >
                                <span
                                    :class="
                                        cn(
                                            'size-2 rounded-full sm:hidden',
                                            toneClasses[
                                                statusOf(lichStatus(e.state))
                                                    .tone
                                            ].dot,
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
                            'text-right text-[0.8125rem] font-semibold text-primary-text tabular-nums',
                            timeW,
                        )
                    "
                    >{{ dayjs().format('HH:mm') }}</span
                >
                <span class="size-2 rounded-full bg-primary" />
                <span class="h-px flex-1 bg-primary/40" />
                <span class="text-[0.8125rem] font-medium text-primary-text"
                    >Bây giờ · hết bài trong ngày</span
                >
            </li>
        </ol>
        <!-- Chỗ trống dưới bài cuối: vẫn thả được (giờ tăng dần theo khoảng kéo xuống) -->
        <div v-if="dragging" class="min-h-24 flex-1" aria-hidden="true" />
        <RescheduleDialog v-model:open="moveOpen" :entry="moveEntry" />
        <RemoveDialog v-model:open="removeOpen" :entry="removeEntry" />
    </div>
</template>

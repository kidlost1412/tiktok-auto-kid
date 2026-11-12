<script setup lang="ts">
// Dải số lớn đầu trang: việc quan trọng nhất cần thấy ngay (hôm nay đã xếp bao nhiêu, bài kế tiếp lúc nào, kênh có chạy không, kho còn bao lâu).
import { IconCalendarEvent, IconClockPlay, IconMovie, IconRobot } from '@tabler/icons-vue';
import { computed } from 'vue';

import type { AccountRow, Lich } from '@/components/fork/auto/types';
import { cardCls, toneClasses, type Tone } from '@/components/fork/shared/status';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    accounts: AccountRow[];
    lich: Lich;
    stock: { new_total: number; days_left: number | null; low: boolean };
}>();

const today = computed(() => {
    let planned = 0;
    let posted = 0;
    let cap = 0;

    for (const a of props.accounts) {
        const t = props.lich.channels[a.id]?.today;
        planned += t?.planned ?? 0;
        posted += t?.posted ?? 0;
        cap += t?.cap ?? (a.enabled ? a.daily_cap : 0);
    }

    return { planned, posted, cap };
});

const next = computed(() => {
    const now = dayjs();
    let best: { at: string; username: string | null; state: string } | null = null;

    for (const a of props.accounts) {
        for (const e of props.lich.channels[a.id]?.items ?? []) {
            if (!['scheduled', 'tiktok_scheduled', 'reserved', 'publishing'].includes(e.state) || !dayjs(e.at).isAfter(now.subtract(5, 'minute'))) {
                continue;
            }

            if (best === null || dayjs(e.at).isBefore(best.at)) {
                best = { at: e.at, username: a.username, state: e.state };
            }
        }
    }

    return best;
});

const nextLeft = computed(() => {
    if (!next.value) {
        return '';
    }

    const m = Math.round(dayjs(next.value.at).diff(dayjs(), 'minute', true));

    if (m <= 0) {
        return 'đang tới giờ';
    }

    return m < 60 ? `còn ${m} phút` : `còn ${Math.floor(m / 60)} giờ ${m % 60} phút`;
});

const on = computed(() => props.accounts.filter((a) => a.enabled).length);

const cards = computed<{ key: string; label: string; value: string; unit?: string; hint: string; tone: Tone; icon: typeof IconRobot }[]>(() => [
    {
        key: 'today',
        label: 'Hôm nay',
        value: `${today.value.planned}/${today.value.cap}`,
        unit: 'bài',
        hint: `Đã đăng ${today.value.posted}, còn ${Math.max(0, today.value.cap - today.value.planned)} chỗ trong ngày`,
        tone: today.value.cap > 0 && today.value.planned >= today.value.cap ? 'success' : 'info',
        icon: IconCalendarEvent,
    },
    {
        key: 'next',
        label: 'Bài kế tiếp',
        value: next.value ? dayjs(next.value.at).format('HH:mm') : '—',
        unit: next.value && !dayjs(next.value.at).isSame(dayjs(), 'day') ? dayjs(next.value.at).format('DD/MM') : undefined,
        hint: next.value ? `${nextLeft.value}${next.value.username ? ` · @${next.value.username}` : ''}` : 'Chưa có bài nào được hẹn',
        tone: next.value ? 'info' : 'neutral',
        icon: IconClockPlay,
    },
    {
        key: 'auto',
        label: 'Tự động đăng',
        value: props.accounts.length ? `${on.value}/${props.accounts.length}` : '0',
        unit: 'kênh đang bật',
        hint: on.value ? 'Kênh bật sẽ tự xếp và hẹn lịch' : 'Bật công tắc ở thẻ kênh để bắt đầu',
        tone: on.value ? 'success' : 'danger',
        icon: IconRobot,
    },
    {
        key: 'stock',
        label: 'Video trong kho',
        value: String(props.stock.new_total),
        unit: 'video',
        hint: props.stock.days_left !== null ? `Đủ khoảng ${props.stock.days_left} ngày đăng` : 'Video đã duyệt, chưa đăng',
        tone: props.stock.low ? 'warn' : 'neutral',
        icon: IconMovie,
    },
]);
</script>

<template>
    <div class="grid gap-5 sm:grid-cols-2 xl:grid-cols-4" data-testid="fork-auto-kpi">
        <div
            v-for="c in cards"
            :key="c.key"
            :class="cn(cardCls, 'relative flex flex-col gap-3 overflow-hidden p-5')"
            :data-testid="`fork-auto-kpi-${c.key}`"
        >
            <div class="flex items-center gap-3">
                <span :class="cn('flex size-[34px] shrink-0 items-center justify-center rounded-[10px]', toneClasses[c.tone].chip)">
                    <component :is="c.icon" class="size-[18px]" />
                </span>
                <div class="text-sm font-medium text-muted-foreground">{{ c.label }}</div>
            </div>
            <div class="flex items-baseline gap-2">
                <span class="font-heading text-[32px] leading-none font-[650] tracking-[-0.025em] tabular-nums">{{ c.value }}</span>
                <span v-if="c.unit" class="text-sm text-muted-foreground">{{ c.unit }}</span>
            </div>
            <div class="text-[13px] leading-snug text-muted-foreground">{{ c.hint }}</div>
        </div>
    </div>
</template>

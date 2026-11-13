<script setup lang="ts">
// Lịch đăng. Màn rộng (≥1536px): 3 ngày cạnh nhau, mỗi cột có đầu cột (ngày, số bài, thanh tiến độ) và cuộn riêng.
// Màn hẹp hơn: chọn ngày bằng tab ở đầu thẻ, hiện một ngày. Nét đứt là giờ dự kiến, chưa hẹn lên TikTok.
import { useMediaQuery } from '@vueuse/core';
import { computed, ref } from 'vue';

import ScheduleDayList from '@/components/fork/auto/ScheduleDayList.vue';
import type {
    AccountRow,
    Lich,
    ScheduleEntry,
} from '@/components/fork/auto/types';
import { cardCls, toneClasses } from '@/components/fork/shared/status';
import { NativeSelect } from '@/components/ui/native-select';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    lich: Lich;
    accounts: AccountRow[];
}>();

const wide = useMediaQuery('(min-width: 1536px)');

const channel = ref<string>('all');
const picked = ref<string | null>(null);

const entries = computed<ScheduleEntry[]>(() => {
    const out: ScheduleEntry[] = [];

    for (const a of props.accounts) {
        if (channel.value !== 'all' && channel.value !== a.id) {
            continue;
        }

        for (const item of props.lich.channels[a.id]?.items ?? []) {
            out.push({
                ...item,
                channelId: a.id,
                username: a.username ?? a.display_name ?? '—',
            });
        }
    }

    return out.sort((x, y) => dayjs(x.at).valueOf() - dayjs(y.at).valueOf());
});

const notes = computed(() =>
    props.accounts
        .filter((a) => channel.value === 'all' || channel.value === a.id)
        .map((a) => ({
            id: a.id,
            username: a.username ?? '—',
            note: props.lich.channels[a.id]?.note ?? null,
        }))
        .filter((n) => n.note),
);

const todayKey = computed(() => dayjs().format('YYYY-MM-DD'));

const days = computed(() =>
    props.lich.days.map((d, i) => {
        const list = entries.value.filter((e) => e.day === d.key);
        const real = list.filter((e) => e.state !== 'projected').length;
        const posted = list.filter((e) => e.state === 'posted').length;
        const failed = list.filter((e) => e.state === 'failed').length;
        const planned = list.filter(
            (e) => e.state === 'projected' && e.video_id,
        ).length;

        return {
            ...d,
            label: d.label || (i === 0 ? 'Hôm nay' : d.date),
            list,
            real,
            posted,
            failed,
            planned,
            empty: list.length - real - planned,
            isToday: d.key === todayKey.value,
        };
    }),
);

type Day = (typeof days.value)[number];

const current = computed(
    () => days.value.find((d) => d.key === picked.value) ?? days.value[0],
);

const multi = computed(() => props.accounts.length > 1);
const pct = (n: number, d: Day) =>
    `${(n / (d.real + d.planned + d.empty || 1)) * 100}%`;
</script>

<template>
    <section
        :class="cn(cardCls, 'flex min-h-0 min-w-0 flex-col overflow-hidden')"
        data-testid="fork-auto-lich"
    >
        <header
            class="flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b px-5 py-3"
        >
            <div class="min-w-0">
                <h2
                    class="font-heading text-[0.9375rem] font-semibold tracking-[-0.01em]"
                >
                    Lịch đăng
                </h2>
                <p class="text-[0.7812rem] text-muted-foreground">
                    Bấm một dòng để xem video. Nét đứt là giờ dự kiến, chưa hẹn
                    lên TikTok.
                </p>
            </div>
            <div class="flex items-center gap-4">
                <!-- Chú thích chấm trạng thái (kiểu 3 cột) -->
                <div
                    v-if="wide"
                    class="flex items-center gap-3 text-[0.75rem] text-muted-foreground"
                    aria-hidden="true"
                >
                    <span class="inline-flex items-center gap-1.5"
                        ><i
                            :class="
                                cn(
                                    'size-2 rounded-full',
                                    toneClasses.success.dot,
                                )
                            "
                        />Đã đăng</span
                    >
                    <span class="inline-flex items-center gap-1.5"
                        ><i
                            :class="
                                cn('size-2 rounded-full', toneClasses.info.dot)
                            "
                        />Đã xếp lịch</span
                    >
                    <span class="inline-flex items-center gap-1.5"
                        ><i
                            class="size-2 rounded-full border border-dashed border-muted-foreground"
                        />Dự kiến</span
                    >
                </div>
                <NativeSelect
                    v-if="multi"
                    v-model="channel"
                    class="h-8 w-44"
                    aria-label="Lọc theo kênh"
                >
                    <option value="all">Tất cả kênh</option>
                    <option v-for="a in accounts" :key="a.id" :value="a.id">
                        @{{ a.username ?? a.display_name }}
                    </option>
                </NativeSelect>
            </div>
        </header>

        <div v-if="notes.length" class="flex shrink-0 flex-col gap-2 px-5 pt-3">
            <div
                v-for="n in notes"
                :key="n.id"
                :class="
                    cn(
                        'rounded-lg border px-3.5 py-2 text-[0.8125rem]',
                        toneClasses.warn.box,
                    )
                "
            >
                <b v-if="multi">@{{ n.username }}: </b>{{ n.note }}
            </div>
        </div>

        <!-- Màn rộng: 3 ngày cạnh nhau -->
        <div
            v-if="wide"
            class="grid min-h-0 flex-1 grid-cols-3 divide-x"
            data-testid="fork-auto-lich-columns"
        >
            <div
                v-for="d in days"
                :key="d.key"
                class="flex min-h-0 min-w-0 flex-col"
            >
                <div
                    :class="
                        cn(
                            'shrink-0 border-b px-4 pt-3 pb-2.5',
                            d.isToday &&
                                'bg-primary/[0.04] dark:bg-primary/[0.07]',
                        )
                    "
                    :data-testid="`fork-auto-day-tab-${d.key}`"
                >
                    <div class="flex items-baseline justify-between gap-2">
                        <span class="flex items-baseline gap-2">
                            <span
                                :class="
                                    cn(
                                        'text-[0.8438rem] font-semibold',
                                        d.isToday
                                            ? 'text-primary-text'
                                            : 'text-foreground',
                                    )
                                "
                                >{{ d.label }}</span
                            >
                            <span
                                class="text-[0.7812rem] text-muted-foreground tabular-nums"
                                >{{ d.date }}</span
                            >
                        </span>
                        <span class="flex items-baseline gap-1">
                            <span
                                class="font-heading text-[1.25rem] leading-none font-[650] tracking-tight tabular-nums"
                                >{{ d.real + d.planned }}</span
                            >
                            <span class="text-[0.75rem] text-muted-foreground"
                                >bài</span
                            >
                        </span>
                    </div>
                    <div
                        class="mt-2 flex h-1.5 overflow-hidden rounded-full bg-muted"
                    >
                        <span
                            class="bg-primary"
                            :style="{ width: pct(d.posted, d) }"
                        />
                        <span
                            class="bg-primary/40"
                            :style="{ width: pct(d.real - d.posted, d) }"
                        />
                        <span
                            class="bg-muted-foreground/30"
                            :style="{ width: pct(d.planned, d) }"
                        />
                    </div>
                    <div
                        class="mt-1.5 flex flex-wrap gap-x-2.5 text-[0.75rem] text-muted-foreground tabular-nums"
                    >
                        <span v-if="d.posted">{{ d.posted }} đã đăng</span>
                        <span v-if="d.real - d.posted - d.failed"
                            >{{ d.real - d.posted - d.failed }} đã xếp</span
                        >
                        <span v-if="d.planned">{{ d.planned }} dự kiến</span>
                        <span v-if="d.failed" :class="toneClasses.danger.text"
                            >{{ d.failed }} lỗi</span
                        >
                        <span v-if="d.empty" :class="toneClasses.warn.text"
                            >{{ d.empty }} giờ trống</span
                        >
                        <span v-if="!d.list.length">Chưa có giờ đăng</span>
                    </div>
                </div>
                <ScheduleDayList
                    :day-key="d.key"
                    :list="d.list"
                    :is-today="d.isToday"
                    :multi="multi"
                    compact
                    class="min-h-0 flex-1 overflow-y-auto overscroll-contain"
                />
            </div>
        </div>

        <!-- Màn hẹp: chọn ngày bằng tab -->
        <template v-else>
            <div
                class="grid shrink-0 grid-cols-3 gap-px border-b bg-border"
                :class="notes.length && 'mt-3 border-t'"
                role="tablist"
                aria-label="Chọn ngày"
            >
                <button
                    v-for="d in days"
                    :key="d.key"
                    type="button"
                    role="tab"
                    :aria-selected="current?.key === d.key"
                    :data-testid="`fork-auto-day-tab-${d.key}`"
                    :class="
                        cn(
                            'relative flex flex-col gap-1.5 bg-card px-5 py-3 text-left transition-colors hover:bg-accent/40 focus-visible:z-10 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring',
                            current?.key === d.key &&
                                'bg-primary/[0.04] dark:bg-primary/[0.08]',
                        )
                    "
                    @click="picked = d.key"
                >
                    <span
                        v-if="current?.key === d.key"
                        class="absolute inset-x-0 bottom-0 h-0.5 bg-primary"
                        aria-hidden="true"
                    />
                    <span
                        class="flex items-baseline justify-between gap-2 text-[0.8125rem]"
                    >
                        <span
                            :class="
                                cn(
                                    'font-semibold',
                                    current?.key === d.key
                                        ? 'text-foreground'
                                        : 'text-muted-foreground',
                                )
                            "
                            >{{ d.label }}</span
                        >
                        <span class="text-muted-foreground tabular-nums">{{
                            d.date
                        }}</span>
                    </span>
                    <span class="flex items-baseline gap-1">
                        <span
                            class="font-heading text-[1.375rem] leading-none font-[650] tracking-tight tabular-nums"
                            >{{ d.real + d.planned }}</span
                        >
                        <span class="text-[0.7812rem] text-muted-foreground"
                            >bài<template v-if="d.planned">
                                · {{ d.planned }} dự kiến</template
                            ></span
                        >
                    </span>
                    <span
                        class="flex h-1 overflow-hidden rounded-full bg-muted"
                    >
                        <span
                            class="bg-primary"
                            :style="{ width: pct(d.real, d) }"
                        />
                        <span
                            class="bg-muted-foreground/30"
                            :style="{ width: pct(d.planned, d) }"
                        />
                    </span>
                </button>
            </div>

            <ScheduleDayList
                v-if="current"
                :day-key="current.key"
                :list="current.list"
                :is-today="current.isToday"
                :multi="multi"
                class="min-h-0 flex-1 overflow-y-auto overscroll-contain"
            />
        </template>
    </section>
</template>

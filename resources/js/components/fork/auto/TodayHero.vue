<script setup lang="ts">
// Dải "Hôm nay" đầu trang: 4 câu hỏi chủ shop hay hỏi nhất, trả lời trong một cái liếc —
// hôm nay đăng tới đâu, bài kế tiếp là bài nào, kho còn bao lâu, hệ thống có chạy không.
import { Link } from '@inertiajs/vue3';
import { IconArrowUpRight } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import type {
    AccountRow,
    Health,
    HubStatus,
    Lich,
    LichItem,
    TrendDay,
} from '@/components/fork/auto/types';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import {
    cardCls,
    fmtCompact,
    fmtNum,
    toneClasses,
    type Tone,
} from '@/components/fork/shared/status';
import { openVideo } from '@/components/fork/viewer';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    accounts: AccountRow[];
    lich: Lich;
    health: Health;
    hub?: HubStatus;
    stock: {
        new_total: number;
        scheduled_total?: number;
        days_left: number | null;
        low: boolean;
        daily_cap: number;
    };
    /** 7 ngày gần nhất (bản server cũ chưa gửi thì ẩn biểu đồ). */
    trend?: TrendDay[];
    /** Số bài lỗi gần đây (14 ngày). */
    failedCount?: number;
}>();

// Đồng hồ nội bộ để "còn x phút" tự chạy giữa hai lần làm mới trang.
const now = ref(dayjs());
let tick: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
    tick = setInterval(() => {
        now.value = dayjs();
    }, 20000);
});
onBeforeUnmount(() => clearInterval(tick));

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

    return {
        planned,
        posted,
        waiting: Math.max(0, planned - posted),
        free: Math.max(0, cap - planned),
        cap,
    };
});

// Vòng tiến độ: phần đậm = đã đăng, phần nhạt = đã hẹn chờ giờ.
const R = 30;
const C = 2 * Math.PI * R;
const arc = (n: number) =>
    today.value.cap > 0 ? Math.min(1, n / today.value.cap) * C : 0;

const NEXT_STATES = ['scheduled', 'tiktok_scheduled', 'reserved', 'publishing'];

const next = computed<(LichItem & { username: string | null }) | null>(() => {
    let best: (LichItem & { username: string | null }) | null = null;
    const from = now.value.subtract(5, 'minute');

    for (const a of props.accounts) {
        for (const e of props.lich.channels[a.id]?.items ?? []) {
            if (!NEXT_STATES.includes(e.state) || !dayjs(e.at).isAfter(from)) {
                continue;
            }

            if (best === null || dayjs(e.at).isBefore(best.at)) {
                best = { ...e, username: a.username };
            }
        }
    }

    return best;
});

const nextLeft = computed(() => {
    if (!next.value) {
        return '';
    }

    const m = Math.round(dayjs(next.value.at).diff(now.value, 'minute', true));

    if (m <= 0) {
        return 'đang tới giờ';
    }

    if (m < 60) {
        return `còn ${m} phút`;
    }

    const h = Math.floor(m / 60);

    return h < 24
        ? `còn ${h} giờ ${m % 60} phút`
        : `còn ${Math.round(h / 24)} ngày`;
});

const nextDay = computed(() => {
    if (!next.value) {
        return '';
    }

    const d = dayjs(next.value.at);

    if (d.isSame(now.value, 'day')) {
        return 'hôm nay';
    }

    return d.isSame(now.value.add(1, 'day'), 'day')
        ? 'ngày mai'
        : d.format('DD/MM');
});

const openNext = () => {
    const id = next.value?.id ?? next.value?.video_id ?? null;

    if (id !== null && id !== undefined) {
        openVideo([id], id);
    }
};

const daysLeft = computed(() =>
    props.stock.days_left === null
        ? null
        : props.stock.days_left.toLocaleString('vi-VN', {
              maximumFractionDigits: 1,
          }),
);

// Ngày kho dự kiến cạn (nếu không làm thêm video).
const runOut = computed(() => {
    const d = props.stock.days_left;

    if (d === null) {
        return null;
    }

    const at = now.value.add(Math.max(0, Math.floor(d)), 'day');

    return at.isSame(now.value, 'day')
        ? 'hôm nay'
        : at.isSame(now.value.add(1, 'day'), 'day')
          ? 'ngày mai'
          : at.format('DD/MM');
});

// 7 ngày qua: cột theo lượt xem; chưa có số liệu lượt xem thì theo số bài.
const trend = computed(() => {
    const days = props.trend ?? [];
    const views = days.reduce((s, d) => s + d.views, 0);
    const posts = days.reduce((s, d) => s + d.posts, 0);
    const byViews = views > 0;
    const max = Math.max(1, ...days.map((d) => (byViews ? d.views : d.posts)));

    return {
        views,
        posts,
        byViews,
        bars: days.map((d, i) => ({
            ...d,
            h: Math.max(6, ((byViews ? d.views : d.posts) / max) * 100),
            last: i === days.length - 1,
        })),
    };
});

interface Sys {
    key: string;
    label: string;
    value: string;
    tone: Tone;
    href: string;
}

const system = computed<Sys[]>(() => {
    const hub = props.hub;
    const on = props.health.channels.filter((c) => c.chrome_enabled);
    const online = on.filter((c) => c.chrome_online).length;

    return [
        {
            key: 'hub',
            label: 'Xưởng Video',
            value: hub ? hub.label : 'đang kiểm tra…',
            tone: !hub
                ? 'neutral'
                : hub.state === 'ok'
                  ? 'success'
                  : hub.state === 'off'
                    ? 'neutral'
                    : hub.state === 'offline'
                      ? 'warn'
                      : 'danger',
            href: '/xuong',
        },
        {
            key: 'chrome',
            label: 'Chrome đăng bài',
            value: !on.length
                ? 'chưa ghép'
                : online === on.length
                  ? 'đang kết nối'
                  : online === 0
                    ? 'mất kết nối'
                    : `${online}/${on.length} kênh kết nối`,
            tone: !on.length
                ? 'danger'
                : online === on.length
                  ? 'success'
                  : 'warn',
            href: '/settings#chrome',
        },
        {
            key: 'telegram',
            label: 'Báo Telegram',
            value: props.health.telegram ? 'đang bật' : 'chưa cài',
            tone: props.health.telegram ? 'success' : 'neutral',
            href: '/settings#telegram',
        },
        {
            key: 'failed',
            label: 'Bài lỗi gần đây',
            value: props.failedCount ? `${props.failedCount} bài` : 'không có',
            tone: props.failedCount ? 'danger' : 'success',
            href: '#vua-dang',
        },
    ];
});

const label =
    'text-[12px] font-medium tracking-[0.02em] text-muted-foreground uppercase';
</script>

<template>
    <section
        :class="
            cn(
                cardCls,
                'grid overflow-hidden sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-[1.05fr_1.3fr_0.95fr_1.25fr_1fr]',
            )
        "
        data-testid="fork-auto-kpi"
    >
        <!-- Hôm nay -->
        <div
            class="flex items-center gap-5 p-5"
            data-testid="fork-auto-kpi-today"
        >
            <div class="relative size-[76px] shrink-0">
                <svg viewBox="0 0 76 76" class="size-full -rotate-90">
                    <circle
                        cx="38"
                        cy="38"
                        :r="R"
                        fill="none"
                        stroke-width="7"
                        class="stroke-muted"
                    />
                    <circle
                        cx="38"
                        cy="38"
                        :r="R"
                        fill="none"
                        stroke-width="7"
                        stroke-linecap="round"
                        class="stroke-primary/30 transition-[stroke-dasharray] duration-700"
                        :stroke-dasharray="`${arc(today.planned)} ${C}`"
                    />
                    <circle
                        cx="38"
                        cy="38"
                        :r="R"
                        fill="none"
                        stroke-width="7"
                        stroke-linecap="round"
                        class="stroke-primary transition-[stroke-dasharray] duration-700"
                        :stroke-dasharray="`${arc(today.posted)} ${C}`"
                    />
                </svg>
                <span
                    class="absolute inset-0 flex items-center justify-center text-[13px] font-semibold tabular-nums"
                >
                    {{
                        today.cap
                            ? Math.round((today.posted / today.cap) * 100)
                            : 0
                    }}%
                </span>
            </div>
            <div class="min-w-0">
                <div :class="label">Hôm nay đã đăng</div>
                <div class="mt-1 flex items-baseline gap-1 whitespace-nowrap">
                    <span
                        class="font-heading text-[30px] leading-none font-[650] tracking-[-0.03em] tabular-nums"
                        >{{ today.posted }}</span
                    >
                    <span class="text-[15px] text-muted-foreground tabular-nums"
                        >/ {{ today.cap }} bài</span
                    >
                </div>
                <div
                    class="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-[12.5px] text-muted-foreground tabular-nums"
                >
                    <span class="inline-flex items-center gap-1.5"
                        ><i class="size-2 rounded-full bg-primary/35" />{{
                            today.waiting
                        }}
                        chờ giờ</span
                    >
                    <span class="inline-flex items-center gap-1.5"
                        ><i
                            class="size-2 rounded-full bg-muted-foreground/25"
                        />{{ today.free }} chỗ trống</span
                    >
                </div>
            </div>
        </div>

        <!-- Bài kế tiếp -->
        <div
            class="flex items-center gap-4 border-t p-5 sm:border-t-0 sm:border-l"
            data-testid="fork-auto-kpi-next"
        >
            <template v-if="next">
                <button
                    type="button"
                    class="group relative shrink-0 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                    aria-label="Xem video bài kế tiếp"
                    @click="openNext"
                >
                    <CoverThumb
                        :id="next.id ?? next.video_id"
                        :fallback="next.product_image"
                        class="h-[78px] w-[44px] transition group-hover:brightness-90"
                    />
                </button>
                <div class="min-w-0 flex-1">
                    <div :class="label">Bài kế tiếp · {{ nextDay }}</div>
                    <div class="mt-1 flex items-baseline gap-2">
                        <span
                            class="font-heading text-[30px] leading-none font-[650] tracking-[-0.03em] tabular-nums"
                            >{{ dayjs(next.at).format('HH:mm') }}</span
                        >
                        <span
                            :class="
                                cn(
                                    'truncate text-[13px] font-medium',
                                    toneClasses.info.text,
                                )
                            "
                            >{{ nextLeft }}</span
                        >
                    </div>
                    <div
                        class="mt-2 truncate text-[13px] text-muted-foreground"
                    >
                        <span class="font-medium text-foreground">{{
                            next.product_label ?? next.product_code ?? '—'
                        }}</span>
                        <template v-if="next.username">
                            · @{{ next.username }}</template
                        >
                    </div>
                    <div
                        v-if="next.caption"
                        class="mt-0.5 truncate text-[12px] text-muted-foreground/90"
                        :title="next.caption"
                    >
                        {{ next.caption }}
                    </div>
                </div>
            </template>
            <div v-else class="min-w-0">
                <div :class="label">Bài kế tiếp</div>
                <div
                    class="mt-1.5 font-heading text-[20px] font-semibold tracking-tight text-muted-foreground"
                >
                    Chưa có bài hẹn
                </div>
                <div class="mt-1 text-[13px] text-muted-foreground">
                    Bấm “Xếp lịch ngay” khi kho có video.
                </div>
            </div>
        </div>

        <!-- Kho -->
        <Link
            href="/auto/kho"
            :class="
                cn(
                    'group flex flex-col justify-center border-t p-5 transition-colors hover:bg-accent/40 xl:border-t-0 xl:border-l',
                    stock.low && 'bg-amber-50/60 dark:bg-amber-950/20',
                )
            "
            data-testid="fork-auto-kpi-stock"
        >
            <div :class="cn(label, 'flex items-center justify-between')">
                Kho video
                <IconArrowUpRight
                    class="size-4 opacity-0 transition group-hover:opacity-100"
                />
            </div>
            <div class="mt-1 flex items-baseline gap-1.5">
                <span
                    class="font-heading text-[30px] leading-none font-[650] tracking-[-0.03em] tabular-nums"
                    >{{
                        fmtNum(stock.new_total + (stock.scheduled_total ?? 0))
                    }}</span
                >
                <span class="text-[15px] text-muted-foreground">video</span>
            </div>
            <div
                :class="
                    cn(
                        'mt-2 text-[12.5px] tabular-nums',
                        stock.low
                            ? toneClasses.warn.text
                            : 'text-muted-foreground',
                    )
                "
            >
                <template v-if="daysLeft !== null"
                    >Đủ đăng ~{{ daysLeft }} ngày · hết khoảng
                    {{ runOut }}</template
                >
                <template v-else>Chưa kênh nào bật đăng</template>
            </div>
            <div class="text-[12.5px] text-muted-foreground tabular-nums">
                {{ fmtNum(stock.new_total) }} chờ xếp ·
                {{ fmtNum(stock.scheduled_total ?? 0) }} đã hẹn
            </div>
        </Link>

        <!-- 7 ngày qua -->
        <Link
            v-if="trend.bars.length"
            href="/auto/so-lieu"
            class="group flex items-center gap-4 border-t p-5 transition-colors hover:bg-accent/40 sm:border-l xl:border-l-0 2xl:border-t-0 2xl:border-l"
            data-testid="fork-auto-kpi-trend"
        >
            <div class="min-w-0 shrink-0">
                <div :class="cn(label, 'flex items-center gap-1.5')">
                    7 ngày qua
                    <IconArrowUpRight
                        class="size-4 opacity-0 transition group-hover:opacity-100"
                    />
                </div>
                <div class="mt-1 flex items-baseline gap-1.5 whitespace-nowrap">
                    <span
                        class="font-heading text-[30px] leading-none font-[650] tracking-[-0.03em] tabular-nums"
                        >{{
                            trend.byViews
                                ? fmtCompact(trend.views)
                                : fmtNum(trend.posts)
                        }}</span
                    >
                    <span class="text-[15px] text-muted-foreground">{{
                        trend.byViews ? 'lượt xem' : 'bài'
                    }}</span>
                </div>
                <div
                    class="mt-2 text-[12.5px] text-muted-foreground tabular-nums"
                >
                    <template v-if="trend.byViews"
                        >{{ fmtNum(trend.posts) }} bài đã đăng</template
                    >
                    <template v-else>Chưa có số liệu lượt xem</template>
                </div>
            </div>
            <div
                class="flex h-[60px] min-w-[84px] flex-1 items-end gap-1"
                role="img"
                :aria-label="`Biểu đồ 7 ngày: ${trend.byViews ? 'lượt xem' : 'số bài'} theo ngày`"
            >
                <span
                    v-for="b in trend.bars"
                    :key="b.date"
                    :class="
                        cn(
                            'flex-1 rounded-[3px] transition-colors',
                            b.last
                                ? 'bg-primary'
                                : 'bg-primary/30 group-hover:bg-primary/45',
                        )
                    "
                    :style="{ height: `${b.h}%` }"
                    :title="`${b.label}: ${fmtNum(b.views)} lượt xem · ${b.posts} bài`"
                />
            </div>
        </Link>

        <!-- Hệ thống -->
        <div
            class="flex flex-col justify-center gap-0.5 border-t px-5 py-3 sm:col-span-2 xl:border-l 2xl:col-span-1 2xl:border-t-0"
            data-testid="fork-auto-health"
        >
            <component
                :is="s.href.startsWith('#') ? 'a' : Link"
                v-for="s in system"
                :key="s.key"
                :href="s.href"
                :data-testid="`fork-health-chip-${s.key}`"
                class="-mx-2 flex items-center gap-2.5 rounded-lg px-2 py-1 text-[13px] transition-colors hover:bg-accent/50"
            >
                <span
                    :class="
                        cn(
                            'size-2 shrink-0 rounded-full',
                            toneClasses[s.tone].dot,
                            !hub && s.key === 'hub' && 'animate-pulse',
                        )
                    "
                />
                <span class="text-muted-foreground">{{ s.label }}</span>
                <span
                    :class="
                        cn(
                            'ml-auto truncate font-medium',
                            s.tone === 'neutral'
                                ? 'text-muted-foreground'
                                : toneClasses[s.tone].text,
                        )
                    "
                    >{{ s.value }}</span
                >
            </component>
        </div>
    </section>
</template>

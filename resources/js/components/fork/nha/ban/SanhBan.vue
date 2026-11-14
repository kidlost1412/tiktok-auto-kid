<script setup lang="ts">
// Bàn Sảnh: bảng tin của cả nhà — lời chào, các ô tình hình, việc cần anh xử lý (bấm là mở đúng bàn), hoạt động gần đây.
// Số tổng quan lấy từ `data` (poll 3–10 giây của /nha); phần kênh/kho/giỏ/bài lỗi đọc thêm từ trang /auto.
import { Link } from '@inertiajs/vue3';
import {
    IconAlertTriangle,
    IconChevronRight,
    IconCircleCheck,
    IconRefresh,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted } from 'vue';

import type {
    AccountRow,
    FailedRow,
    Health,
    Lich,
} from '@/components/fork/auto/types';
import { moBan } from '@/components/fork/nha/ban/bus';
import { useInertiaProps } from '@/components/fork/nha/ban/useInertiaProps';
import { recentEvents } from '@/components/fork/nha/su-kien';
import type { NhaData } from '@/components/fork/nha/types';
import { cardCls, fmtNum, toneClasses } from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{ data: NhaData | null }>();

type AutoProps = {
    stock: {
        new_total: number;
        scheduled_total?: number;
        daily_cap: number;
        days_left: number | null;
        low: boolean;
    };
    accounts: AccountRow[];
    health: Health;
    lich: Lich;
    failed_recent?: FailedRow[];
};

const {
    props: p,
    loading,
    error,
    reload,
} = useInertiaProps<AutoProps>('/auto', 'fork/Auto', [
    'stock',
    'accounts',
    'health',
    'lich',
    'failed_recent',
]);

let poll: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
    reload();
    poll = setInterval(() => {
        if (document.visibilityState === 'visible') {
            reload();
        }
    }, 30000);
});
onBeforeUnmount(() => clearInterval(poll));

// ---- Lời chào
const greeting = computed(() => {
    const h = dayjs().hour();

    return h < 11
        ? 'Chào buổi sáng, anh.'
        : h < 14
          ? 'Chào buổi trưa, anh.'
          : h < 18
            ? 'Chào buổi chiều, anh.'
            : 'Chào buổi tối, anh.';
});

// ---- Số liệu
const accounts = computed(() => p.value?.accounts ?? []);
const channelsOn = computed(() => accounts.value.filter((a) => a.enabled));

const today = computed(() => {
    let planned = 0;
    let posted = 0;

    for (const a of accounts.value) {
        const t = p.value?.lich.channels[a.id]?.today;
        planned += t?.planned ?? 0;
        posted += t?.posted ?? 0;
    }

    return {
        planned: p.value ? planned : (props.data?.app?.posts_today ?? 0),
        posted,
    };
});

const next = computed(() => props.data?.app?.next ?? null);
const nextLeft = computed(() => {
    const m = next.value?.minutes;

    if (m === undefined || m === null) {
        return '';
    }

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

const failed = computed(() => p.value?.failed_recent ?? []);

const blockedTotal = computed(() => {
    let best = 0;

    for (const a of accounts.value) {
        const total = (p.value?.lich.channels[a.id]?.blocked ?? []).reduce(
            (s, g) => s + g.count,
            0,
        );
        best = Math.max(best, total);
    }

    return best;
});

// Chrome: ưu tiên số kênh nối được (health); chưa có thì dùng cờ chung của /nha.
const chrome = computed(() => {
    const ch = (p.value?.health.channels ?? []).filter((c) => c.chrome_enabled);

    if (ch.length) {
        const on = ch.filter((c) => c.chrome_online).length;

        return {
            ok: on === ch.length,
            value: `${on}/${ch.length}`,
            sub: 'kênh đang nối',
        };
    }

    const v = props.data?.app?.chrome_online;

    if (v === null || v === undefined) {
        return { ok: null as boolean | null, value: '—', sub: 'Chưa rõ' };
    }

    return {
        ok: v,
        value: v ? 'Nối' : 'Mất',
        sub: v ? 'Chrome đang kết nối' : 'Chrome mất kết nối',
    };
});

const stockTotal = computed(
    () =>
        (p.value?.stock.new_total ?? 0) + (p.value?.stock.scheduled_total ?? 0),
);

const down = computed(() => !props.data || props.data.mode === 'down');

// ---- Câu tình hình (một câu)
const tinhHinh = computed(() => {
    if (!props.data) {
        return 'Đang xem tình hình trong nhà…';
    }

    return (
        props.data.line ||
        (down.value ? 'Xưởng đang tắt.' : 'Mọi thứ đang chạy.')
    );
});

// ---- Việc cần anh xử lý
interface Viec {
    key: string;
    text: string;
    hint?: string;
    ban?: string;
    href?: string;
    nut: string;
    tone: 'danger' | 'warn';
}

const viec = computed<Viec[]>(() => {
    const out: Viec[] = [];

    if (failed.value.length) {
        out.push({
            key: 'loi',
            text: `${failed.value.length} bài đăng bị lỗi`,
            hint: 'Xem lý do và bấm Thử lại ở bàn Bưu tá.',
            ban: 'buuta',
            nut: 'Mở bàn Bưu tá',
            tone: 'danger',
        });
    }

    if (blockedTotal.value) {
        out.push({
            key: 'gio',
            text: `${blockedTotal.value} video đã duyệt chưa đăng được vì chưa chọn giỏ hàng`,
            hint: 'Chọn giỏ ở bàn Chủ quầy để app bắt đầu đăng.',
            ban: 'chuquay',
            nut: 'Chọn giỏ',
            tone: 'warn',
        });
    }

    if (chrome.value.ok === false) {
        out.push({
            key: 'chrome',
            text: 'Chrome đang mất kết nối',
            hint: 'Mở Chrome đã cài tiện ích và đăng nhập TikTok.',
            href: '/settings#chrome',
            nut: 'Kết nối Chrome',
            tone: 'danger',
        });
    }

    if (p.value?.stock.low) {
        out.push({
            key: 'kho',
            text: `Kho video sắp hết: còn ${fmtNum(stockTotal.value)} video, chưa đủ một ngày đăng`,
            hint: 'Làm thêm video ở Xưởng Video.',
            ban: 'thukho',
            nut: 'Mở bàn Thủ kho',
            tone: 'warn',
        });
    }

    if (accounts.value.length && !channelsOn.value.length) {
        out.push({
            key: 'kenh',
            text: 'Chưa kênh nào bật tự động đăng',
            hint: 'Bật công tắc ở thẻ kênh để app bắt đầu xếp lịch.',
            ban: 'buuta',
            nut: 'Mở bàn Bưu tá',
            tone: 'warn',
        });
    }

    if (props.data?.mode === 'limit') {
        out.push({
            key: 'han-muc',
            text: 'Hết hạn mức Claude, xưởng đang nghỉ',
            ban: 'thodung',
            nut: 'Mở bàn Thợ dựng',
            tone: 'warn',
        });
    } else if (props.data && props.data.mode === 'down') {
        out.push({
            key: 'xuong',
            text: 'Xưởng Video đang tắt',
            hint: 'Mở lại Xưởng Video để làm video mới.',
            ban: 'thodung',
            nut: 'Mở bàn Thợ dựng',
            tone: 'warn',
        });
    }

    return out;
});

const events = computed(() => recentEvents(props.data?.events, 8));

const labelCls =
    'text-xs font-medium tracking-[0.02em] text-muted-foreground uppercase';
const tileCls = cn(
    cardCls,
    'flex min-w-0 flex-col gap-1 px-4 py-3.5 text-left transition-colors',
);
const h2 = 'font-heading text-base font-semibold tracking-[-0.01em]';
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col gap-4" data-testid="ban-sanh">
        <!-- Lời chào + một câu tình hình -->
        <div>
            <h2
                class="font-heading text-xl font-semibold tracking-[-0.015em]"
                data-testid="ban-sanh-loichao"
            >
                {{ greeting }}
            </h2>
            <p class="mt-0.5 text-sm text-muted-foreground">{{ tinhHinh }}</p>
        </div>

        <div
            v-if="error && !p"
            class="flex items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 text-sm"
        >
            <span class="text-muted-foreground">{{ error }}</span>
            <Button size="sm" variant="outline" @click="reload()">
                <IconRefresh class="size-4" />
                Thử lại
            </Button>
        </div>

        <!-- Lưới tình hình -->
        <div class="grid grid-cols-3 gap-3" data-testid="ban-sanh-luoi">
            <button
                type="button"
                :class="[tileCls, 'hover:bg-accent/40']"
                @click="moBan('buuta')"
            >
                <span :class="labelCls">Hôm nay đăng</span>
                <Skeleton v-if="!p && loading" class="h-8 w-20" />
                <span v-else class="flex items-baseline gap-1">
                    <span
                        class="font-heading text-2xl font-semibold tabular-nums"
                        >{{ today.posted }}</span
                    >
                    <span class="text-sm text-muted-foreground tabular-nums"
                        >/ {{ today.planned }} bài</span
                    >
                </span>
                <span class="text-xs text-muted-foreground"
                    >Đã đăng / đã hẹn</span
                >
            </button>

            <button
                type="button"
                :class="[tileCls, 'hover:bg-accent/40']"
                @click="moBan('buuta')"
            >
                <span :class="labelCls">Bài kế tiếp</span>
                <template v-if="next">
                    <span
                        class="font-heading text-2xl font-semibold tabular-nums"
                        >{{ dayjs(next.at).format('HH:mm') }}</span
                    >
                    <span class="truncate text-xs text-muted-foreground"
                        >{{ nextLeft
                        }}<template v-if="next.channel">
                            · @{{ next.channel }}</template
                        ></span
                    >
                </template>
                <template v-else>
                    <span
                        class="font-heading text-2xl font-semibold text-muted-foreground"
                        >—</span
                    >
                    <span class="text-xs text-muted-foreground"
                        >Chưa có bài nào được xếp</span
                    >
                </template>
            </button>

            <button
                type="button"
                :class="[tileCls, 'hover:bg-accent/40']"
                @click="moBan('thodung')"
            >
                <span :class="labelCls">Xưởng đang làm gì</span>
                <span
                    class="flex items-center gap-2 font-heading text-lg leading-tight font-semibold"
                >
                    <i
                        :class="
                            cn(
                                'size-2 shrink-0 rounded-full',
                                down
                                    ? 'bg-muted-foreground/40'
                                    : data?.mode === 'working'
                                      ? 'bg-emerald-500'
                                      : 'bg-amber-400',
                            )
                        "
                    />
                    {{
                        down
                            ? 'Đang nghỉ'
                            : data?.mode === 'working'
                              ? 'Đang làm việc'
                              : data?.mode === 'limit'
                                ? 'Hết hạn mức'
                                : 'Đang rảnh'
                    }}
                </span>
                <span class="line-clamp-2 text-xs text-muted-foreground">{{
                    data?.bang?.dong || 'Chưa có thông tin'
                }}</span>
            </button>

            <Link
                href="/settings#chrome"
                :class="[tileCls, 'hover:bg-accent/40']"
            >
                <span :class="labelCls">Chrome</span>
                <Skeleton v-if="!p && loading" class="h-8 w-20" />
                <span
                    v-else
                    :class="
                        cn(
                            'font-heading text-2xl font-semibold tabular-nums',
                            chrome.ok === false && toneClasses.danger.text,
                        )
                    "
                    >{{ chrome.value }}</span
                >
                <span class="text-xs text-muted-foreground">{{
                    chrome.sub
                }}</span>
            </Link>

            <button
                type="button"
                :class="[tileCls, 'hover:bg-accent/40']"
                @click="moBan('thukho')"
            >
                <span :class="labelCls">Kho video</span>
                <Skeleton v-if="!p && loading" class="h-8 w-20" />
                <span v-else class="flex items-baseline gap-1">
                    <span
                        :class="
                            cn(
                                'font-heading text-2xl font-semibold tabular-nums',
                                p?.stock.low && toneClasses.warn.text,
                            )
                        "
                        >{{ fmtNum(stockTotal) }}</span
                    >
                    <span class="text-sm text-muted-foreground">video</span>
                </span>
                <span class="text-xs text-muted-foreground tabular-nums">{{
                    p?.stock.days_left == null
                        ? 'Chờ đăng và đã hẹn'
                        : `Đủ đăng ${p.stock.days_left.toLocaleString('vi-VN', { maximumFractionDigits: 1 })} ngày`
                }}</span>
            </button>

            <button
                type="button"
                :class="[tileCls, 'hover:bg-accent/40']"
                @click="moBan('buuta')"
            >
                <span :class="labelCls">Bài lỗi</span>
                <Skeleton v-if="!p && loading" class="h-8 w-20" />
                <span
                    v-else
                    :class="
                        cn(
                            'font-heading text-2xl font-semibold tabular-nums',
                            failed.length && toneClasses.danger.text,
                        )
                    "
                    >{{ failed.length }}</span
                >
                <span class="text-xs text-muted-foreground">{{
                    failed.length ? 'Cần xem lại' : 'Không có'
                }}</span>
            </button>
        </div>

        <div
            class="grid grid-cols-[minmax(0,3fr)_minmax(0,2fr)] items-start gap-4"
        >
            <!-- Việc cần anh xử lý -->
            <section
                :class="cn(cardCls, 'flex flex-col overflow-hidden')"
                data-testid="ban-sanh-viec"
            >
                <header
                    class="flex items-baseline justify-between border-b px-4 py-3"
                >
                    <h2 :class="h2">Việc cần anh xử lý</h2>
                    <span
                        v-if="viec.length"
                        class="text-xs text-muted-foreground tabular-nums"
                        >{{ viec.length }} việc</span
                    >
                </header>
                <div v-if="!p && loading" class="flex flex-col gap-2 p-4">
                    <Skeleton class="h-10 w-full" />
                    <Skeleton class="h-10 w-full" />
                </div>
                <p
                    v-else-if="!viec.length"
                    class="flex items-center justify-center gap-2 px-4 py-8 text-sm text-muted-foreground"
                >
                    <IconCircleCheck
                        :class="cn('size-5', toneClasses.success.text)"
                    />
                    Không có việc nào cần xử lý. Mọi thứ đang chạy ổn.
                </p>
                <ul v-else class="flex flex-col divide-y">
                    <li
                        v-for="v in viec"
                        :key="v.key"
                        class="flex items-center gap-3 px-4 py-3"
                    >
                        <IconAlertTriangle
                            :class="
                                cn(
                                    'size-4.5 shrink-0',
                                    toneClasses[v.tone].text,
                                )
                            "
                        />
                        <div class="min-w-0 flex-1">
                            <div class="text-sm font-medium">{{ v.text }}</div>
                            <div
                                v-if="v.hint"
                                class="text-xs text-muted-foreground"
                            >
                                {{ v.hint }}
                            </div>
                        </div>
                        <Button
                            v-if="v.href"
                            as-child
                            size="sm"
                            variant="outline"
                            class="shrink-0"
                        >
                            <Link :href="v.href"
                                >{{ v.nut }} <IconChevronRight class="size-4"
                            /></Link>
                        </Button>
                        <Button
                            v-else
                            size="sm"
                            variant="outline"
                            class="shrink-0"
                            :data-testid="`ban-sanh-mo-${v.key}`"
                            @click="v.ban && moBan(v.ban)"
                        >
                            {{ v.nut }}
                            <IconChevronRight class="size-4" />
                        </Button>
                    </li>
                </ul>
            </section>

            <!-- Hoạt động gần đây -->
            <section
                :class="cn(cardCls, 'flex flex-col overflow-hidden')"
                data-testid="ban-sanh-hoatdong"
            >
                <header class="border-b px-4 py-3">
                    <h2 :class="h2">Hoạt động gần đây</h2>
                </header>
                <p
                    v-if="!events.length"
                    class="px-4 py-8 text-center text-sm text-muted-foreground"
                >
                    Chưa có hoạt động nào của xưởng.
                </p>
                <ul
                    v-else
                    class="flex max-h-[360px] flex-col overflow-y-auto p-1.5"
                >
                    <li
                        v-for="e in events"
                        :key="e.n"
                        class="flex items-baseline gap-3 rounded-lg px-2.5 py-1.5 text-sm"
                    >
                        <span
                            class="w-11 shrink-0 text-xs text-muted-foreground tabular-nums"
                            >{{ e.time }}</span
                        >
                        <span
                            :class="e.bad ? toneClasses.danger.text : undefined"
                            >{{ e.text }}</span
                        >
                    </li>
                </ul>
            </section>
        </div>
    </div>
</template>

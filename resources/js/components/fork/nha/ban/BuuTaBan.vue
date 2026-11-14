<script setup lang="ts">
// Bàn của Bưu tá: dải tóm tắt hôm nay, lịch đăng 3 ngày, bài lỗi + thử lại. Dữ liệu = trang /auto (Tổng quan & Lịch).
import { router } from '@inertiajs/vue3';
import { IconBolt, IconRefresh } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import RecentList from '@/components/fork/auto/RecentList.vue';
import ScheduleBoard from '@/components/fork/auto/ScheduleBoard.vue';
import type {
    AccountRow,
    FailedRow,
    Health,
    Lich,
    LichItem,
    ProductRow,
    RecentRow,
} from '@/components/fork/auto/types';
import { banBao, moBan } from '@/components/fork/nha/ban/bus';
import { useInertiaProps } from '@/components/fork/nha/ban/useInertiaProps';
import type { NhaData } from '@/components/fork/nha/types';
import Callout from '@/components/fork/shared/Callout.vue';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import { cardCls, fmtNum, toneClasses } from '@/components/fork/shared/status';
import { openVideo } from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

defineProps<{ data: NhaData | null }>();

type AutoProps = {
    products: ProductRow[];
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
    recent: RecentRow[];
    failed_recent?: FailedRow[];
};

const {
    props: p,
    loading,
    error,
    reload,
} = useInertiaProps<AutoProps>('/auto', 'fork/Auto', [
    'products',
    'stock',
    'accounts',
    'health',
    'lich',
    'recent',
    'failed_recent',
]);

// Đồng hồ nội bộ để "còn x phút" tự chạy; làm mới số liệu mỗi 30 giây khi popup đang mở.
const now = ref(dayjs());
let tick: ReturnType<typeof setInterval> | undefined;
let poll: ReturnType<typeof setInterval> | undefined;

onMounted(() => {
    reload();
    tick = setInterval(() => {
        now.value = dayjs();
    }, 20000);
    poll = setInterval(() => {
        if (document.visibilityState === 'visible') {
            reload();
        }
    }, 30000);
});
onBeforeUnmount(() => {
    clearInterval(tick);
    clearInterval(poll);
});

const accounts = computed(() => p.value?.accounts ?? []);
const channelsOn = computed(() => accounts.value.filter((a) => a.enabled));

const today = computed(() => {
    let planned = 0;
    let posted = 0;
    let cap = 0;

    for (const a of accounts.value) {
        const t = p.value?.lich.channels[a.id]?.today;
        planned += t?.planned ?? 0;
        posted += t?.posted ?? 0;
        cap += t?.cap ?? (a.enabled ? a.daily_cap : 0);
    }

    return { planned, posted, cap };
});

const NEXT_STATES = ['scheduled', 'tiktok_scheduled', 'reserved', 'publishing'];

const next = computed<(LichItem & { username: string | null }) | null>(() => {
    let best: (LichItem & { username: string | null }) | null = null;
    const from = now.value.subtract(5, 'minute');

    for (const a of accounts.value) {
        for (const e of p.value?.lich.channels[a.id]?.items ?? []) {
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
        banBao('buuta', 'xem');
    }
};

const failed = computed(() => p.value?.failed_recent ?? []);
const stock = computed(() => p.value?.stock ?? null);
const daysLeft = computed(() =>
    stock.value?.days_left == null
        ? '—'
        : stock.value.days_left.toLocaleString('vi-VN', {
              maximumFractionDigits: 1,
          }),
);

// Video đã duyệt nhưng bị giữ vì chưa chọn giỏ (kênh bị chặn nhiều nhất; cùng một kho nên không cộng dồn).
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

const productName = (code: string | null) =>
    p.value?.products.find((x) => x.code === code)?.short_name ?? code ?? '—';

// "Xếp lịch ngay": cùng bộ xếp lịch của cron, như nút ở trang Tổng quan & Lịch.
const planning = ref(false);
const planNow = () => {
    planning.value = true;
    router.post(
        '/auto/plan-now',
        {},
        {
            preserveScroll: true,
            preserveState: true,
            onSuccess: () => {
                reload();
                banBao('buuta', 'xep-lich');
            },
            onFinish: () => {
                planning.value = false;
            },
        },
    );
};

const onRetried = () => {
    reload();
    banBao('buuta', 'thu-lai');
};

const tileCls = cn(cardCls, 'flex min-w-0 flex-col gap-1 px-4 py-3.5');
const labelCls =
    'text-xs font-medium tracking-[0.02em] text-muted-foreground uppercase';
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col gap-4" data-testid="ban-buuta">
        <!-- Lỗi tải -->
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

        <!-- Đang tải lần đầu -->
        <template v-else-if="!p && loading">
            <div class="grid grid-cols-4 gap-3">
                <Skeleton v-for="i in 4" :key="i" class="h-24 rounded-[14px]" />
            </div>
            <Skeleton class="h-[420px] rounded-[14px]" />
        </template>

        <template v-else-if="p">
            <div class="flex items-center justify-between gap-3">
                <p class="min-w-0 truncate text-sm text-muted-foreground">
                    <template v-if="!accounts.length"
                        >Chưa có kênh TikTok nào để đăng.</template
                    >
                    <template v-else-if="channelsOn.length"
                        >{{ channelsOn.length }}/{{ accounts.length }} kênh đang
                        tự động đăng.</template
                    >
                    <template v-else>Chưa kênh nào bật tự động đăng.</template>
                </p>
                <Button
                    :disabled="planning || !channelsOn.length"
                    data-testid="ban-buuta-xep-lich"
                    @click="planNow"
                >
                    <Spinner v-if="planning" class="size-4" />
                    <IconBolt v-else class="size-4" />
                    {{ planning ? 'Đang xếp lịch…' : 'Xếp lịch ngay' }}
                </Button>
            </div>

            <!-- Dải tóm tắt -->
            <div class="grid grid-cols-4 gap-3" data-testid="ban-buuta-tomtat">
                <div :class="tileCls">
                    <span :class="labelCls">Hôm nay đã đăng</span>
                    <span class="flex items-baseline gap-1">
                        <span
                            class="font-heading text-2xl font-semibold tabular-nums"
                            >{{ today.posted }}</span
                        >
                        <span class="text-sm text-muted-foreground tabular-nums"
                            >/ {{ today.planned }} bài</span
                        >
                    </span>
                    <span class="text-xs text-muted-foreground tabular-nums"
                        >Tối đa {{ today.cap }} bài mỗi ngày</span
                    >
                </div>

                <button
                    type="button"
                    :class="
                        cn(
                            tileCls,
                            'text-left transition-colors',
                            next && 'hover:bg-accent/40',
                        )
                    "
                    :disabled="!next"
                    @click="openNext"
                >
                    <span :class="labelCls">Bài kế tiếp</span>
                    <span v-if="next" class="flex items-center gap-3">
                        <CoverThumb
                            :id="next.id ?? next.video_id"
                            :fallback="next.product_image"
                            class="h-12 w-[27px] rounded"
                        />
                        <span class="min-w-0">
                            <span
                                class="block font-heading text-2xl leading-tight font-semibold tabular-nums"
                                >{{ dayjs(next.at).format('HH:mm') }}</span
                            >
                            <span
                                class="block truncate text-xs text-muted-foreground"
                                >{{ nextDay }} · {{ nextLeft }}</span
                            >
                        </span>
                    </span>
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

                <div :class="tileCls">
                    <span :class="labelCls">Kho đủ đăng</span>
                    <span class="flex items-baseline gap-1">
                        <span
                            :class="
                                cn(
                                    'font-heading text-2xl font-semibold tabular-nums',
                                    stock?.low && toneClasses.warn.text,
                                )
                            "
                            >{{ daysLeft }}</span
                        >
                        <span class="text-sm text-muted-foreground">ngày</span>
                    </span>
                    <span class="text-xs text-muted-foreground tabular-nums"
                        >{{
                            fmtNum(
                                (stock?.new_total ?? 0) +
                                    (stock?.scheduled_total ?? 0),
                            )
                        }}
                        video chờ và đã hẹn</span
                    >
                </div>

                <div :class="tileCls">
                    <span :class="labelCls">Bài lỗi gần đây</span>
                    <span
                        :class="
                            cn(
                                'font-heading text-2xl font-semibold tabular-nums',
                                failed.length && toneClasses.danger.text,
                            )
                        "
                        >{{ failed.length }}</span
                    >
                    <span class="text-xs text-muted-foreground">{{
                        failed.length ? 'Cần xem ở danh sách dưới' : 'Không có'
                    }}</span>
                </div>
            </div>

            <Callout v-if="blockedTotal" tone="warn">
                <b>{{ blockedTotal }} video đã duyệt chưa được đăng</b> vì chưa
                chọn giỏ hàng.
                <template #action>
                    <Button
                        size="sm"
                        variant="outline"
                        class="bg-background"
                        @click="moBan('chuquay')"
                        >Chọn giỏ ngay →</Button
                    >
                </template>
            </Callout>

            <!-- Lịch đăng 3 ngày -->
            <div class="h-[440px] shrink-0">
                <ScheduleBoard
                    :lich="p.lich"
                    :accounts="p.accounts"
                    class="h-full"
                />
            </div>

            <!-- Bài lỗi + vừa đăng -->
            <RecentList
                :recent="p.recent"
                :failed="failed"
                :product-name="productName"
                :limit="6"
                in-place
                class="max-h-[460px] shrink-0"
                @retried="onRetried"
            />
        </template>
    </div>
</template>

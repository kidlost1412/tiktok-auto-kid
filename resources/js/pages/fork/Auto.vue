<script setup lang="ts">
// "Tổng quan & Lịch": dải Hôm nay ở trên; giữa là Lịch đăng (màn rộng: 3 ngày cạnh nhau) + cột phải Kênh · Vừa đăng,
// hai bên cao bằng nhau và cuộn bên trong; dưới cùng là Kho theo sản phẩm trải ngang.
// Chữ trên trang viết thẳng bằng tiếng Việt.
import { Link, router } from '@inertiajs/vue3';
import { IconBolt, IconBrandTiktok } from '@tabler/icons-vue';
import { useMediaQuery } from '@vueuse/core';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import ChannelPanel from '@/components/fork/auto/ChannelPanel.vue';
import OnboardingCard from '@/components/fork/auto/OnboardingCard.vue';
import RecentList from '@/components/fork/auto/RecentList.vue';
import ScheduleBoard from '@/components/fork/auto/ScheduleBoard.vue';
import TodayHero from '@/components/fork/auto/TodayHero.vue';
import type {
    AccountRow,
    FailedRow,
    Health,
    HubStatus,
    Lich,
    Onboarding,
    ProductRow,
    RecentRow,
    TrendDay,
} from '@/components/fork/auto/types';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { cardCls, fmtNum } from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils';

const props = defineProps<{
    products: ProductRow[];
    stock: {
        new_total: number;
        scheduled_total?: number;
        daily_cap: number;
        days_left: number | null;
        low: boolean;
        updated_at: string;
        last_ingest_at: string | null;
    };
    accounts: AccountRow[];
    health: Health;
    hub?: HubStatus;
    lich: Lich;
    recent: RecentRow[];
    failed_recent?: FailedRow[];
    /** 7 ngày gần nhất: số bài + lượt xem (biểu đồ nhỏ ở dải Hôm nay). */
    trend?: TrendDay[];
    /** Tải sau (hỏi hub); null = đã xong hoặc đã ẩn. */
    onboarding?: Onboarding | null;
}>();

const planning = ref(false);

// "Xếp lịch ngay": chạy cùng bộ xếp lịch của cron, chỉ cho các kênh của chủ tài khoản.
const planNow = () => {
    planning.value = true;
    router.post(
        '/auto/plan-now',
        {},
        {
            preserveScroll: true,
            onFinish: () => {
                planning.value = false;
            },
        },
    );
};

const productName = (code: string | null) =>
    props.products.find((p) => p.code === code)?.short_name ?? code ?? '—';

// Video đã duyệt nhưng bị giữ vì chưa chọn giỏ: lấy kênh bị chặn nhiều nhất (cùng một kho nên không cộng dồn các kênh).
const blocked = computed(() => {
    let best: {
        id: string;
        total: number;
        groups: {
            code: string;
            quy_cach: string | null;
            label: string;
            count: number;
            image?: string | null;
        }[];
    } | null = null;

    for (const a of props.accounts) {
        const groups = props.lich.channels[a.id]?.blocked ?? [];
        const total = groups.reduce((s, g) => s + g.count, 0);

        if (total > 0 && (best === null || total > best.total)) {
            best = { id: a.id, total, groups };
        }
    }

    return best;
});

const blockedOf = (id: string) =>
    (props.lich.channels[id]?.blocked ?? []).reduce((s, g) => s + g.count, 0);
const channelsOn = computed(() => props.accounts.filter((a) => a.enabled));

const description = computed(() => {
    const on = channelsOn.value.length;

    if (!props.accounts.length) {
        return 'Kết nối kênh TikTok để bắt đầu tự động đăng.';
    }

    return on
        ? `${on}/${props.accounts.length} kênh đang tự động đăng.`
        : 'Chưa kênh nào bật tự động đăng.';
});

// Kho theo sản phẩm: sản phẩm còn nhiều video chờ lên trước; sản phẩm đã hết hẳn video thì xuống cuối.
const stockRows = computed(() =>
    [...props.products]
        .filter((p) => p.counts.new + p.counts.scheduled + p.counts.posted > 0)
        .sort(
            (a, b) =>
                b.counts.new +
                b.counts.scheduled -
                (a.counts.new + a.counts.scheduled),
        ),
);
const stockMax = computed(() =>
    Math.max(
        1,
        ...stockRows.value.map((p) => p.counts.new + p.counts.scheduled),
    ),
);
const stockSum = computed(() =>
    stockRows.value.reduce(
        (s, p) => ({
            new: s.new + p.counts.new,
            scheduled: s.scheduled + p.counts.scheduled,
        }),
        { new: 0, scheduled: 0 },
    ),
);
const STOCK_FOLD = 15;
const showAllStock = ref(false);
const stockShown = computed(() =>
    showAllStock.value ? stockRows.value : stockRows.value.slice(0, STOCK_FOLD),
);

// Từ 1280px: Lịch và cột phải đặt cạnh nhau, cao bằng nhau, "Vừa đăng" cuộn bên trong nên hiện được nhiều bài hơn.
const sideBySide = useMediaQuery('(min-width: 1280px)');

// Số liệu đọc từ DB lúc tải trang; tự làm mới (chỉ khi đang xem trang) để không hiện số cũ.
let refreshTimer: ReturnType<typeof setInterval> | undefined;

onMounted(() => {
    refreshTimer = setInterval(() => {
        if (document.visibilityState === 'visible') {
            router.reload({
                only: [
                    'products',
                    'stock',
                    'recent',
                    'failed_recent',
                    'trend',
                    'onboarding',
                    'lich',
                    'health',
                    'accounts',
                ],
            });
        }
    }, 30000);
});

onBeforeUnmount(() => clearInterval(refreshTimer));
</script>

<template>
    <AutoShell
        title="Tổng quan & Lịch"
        :description="description"
        testid="fork-auto-page"
    >
        <template #actions>
            <Button
                :disabled="planning || !channelsOn.length"
                data-testid="fork-auto-plan-now"
                @click="planNow"
            >
                <Spinner v-if="planning" class="size-4" />
                <IconBolt v-else class="size-4" />
                {{ planning ? 'Đang xếp lịch…' : 'Xếp lịch ngay' }}
            </Button>
        </template>

        <OnboardingCard v-if="onboarding" :onboarding="onboarding" />

        <TodayHero
            :accounts="accounts"
            :lich="lich"
            :health="health"
            :hub="hub"
            :stock="stock"
            :trend="trend"
            :failed-count="failed_recent?.length ?? 0"
        />

        <div class="flex flex-col gap-3 empty:hidden">
            <Callout v-if="blocked" tone="warn" data-testid="fork-auto-blocked">
                <b>{{ blocked.total }} video đã duyệt chưa được đăng</b> vì chưa
                chọn giỏ hàng:
                <span
                    v-for="g in blocked.groups"
                    :key="`${g.code}|${g.quy_cach}`"
                    class="mx-0.5 inline-flex items-center gap-1 rounded-full bg-background/70 py-0.5 pr-2 pl-0.5 align-middle text-xs font-medium"
                >
                    <ProductThumb :src="g.image" class="size-5 rounded-full" />
                    {{ g.label }} ({{ g.count }})
                </span>
                <template #action>
                    <Button
                        as-child
                        size="sm"
                        variant="outline"
                        class="bg-background"
                    >
                        <Link :href="`/auto/gio-hang?kenh=${blocked.id}`"
                            >Chọn giỏ ngay →</Link
                        >
                    </Button>
                </template>
            </Callout>
            <Callout
                v-if="stock.low"
                tone="warn"
                data-testid="fork-auto-low-stock"
            >
                Kho còn
                {{ stock.new_total + (stock.scheduled_total ?? 0) }} video (gồm
                cả bài đã hẹn) — chưa đủ một ngày đăng ({{
                    stock.daily_cap
                }}
                bài). Hãy làm thêm video ở Xưởng Video.
            </Callout>
            <Callout v-if="accounts.length && !channelsOn.length" tone="danger">
                Chưa kênh nào bật tự động đăng. Bật công tắc ở thẻ kênh bên phải
                để app bắt đầu xếp lịch.
            </Callout>
        </div>

        <EmptyState
            v-if="!accounts.length"
            :icon="IconBrandTiktok"
            title="Chưa có tài khoản TikTok nào"
            description="Kết nối tài khoản TikTok và bật đăng qua Chrome để app bắt đầu tự động đăng."
        >
            <Button as-child size="sm">
                <Link href="/settings#chrome">Kết nối Chrome →</Link>
            </Button>
        </EmptyState>

        <template v-else>
            <div
                class="grid gap-6 xl:h-[max(560px,calc(100dvh-320px))] xl:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_400px]"
                data-testid="fork-auto-main"
            >
                <ScheduleBoard
                    :lich="lich"
                    :accounts="accounts"
                    class="max-xl:max-h-[760px]"
                />

                <aside class="flex min-h-0 flex-col gap-4">
                    <section
                        id="kenh"
                        class="flex shrink-0 scroll-mt-24 flex-col gap-3 xl:max-h-[62%] xl:overflow-y-auto"
                        aria-label="Kênh TikTok"
                    >
                        <div class="flex items-baseline justify-between px-1">
                            <h2
                                class="font-heading text-[0.9375rem] font-semibold tracking-[-0.01em]"
                            >
                                Kênh TikTok
                            </h2>
                            <span class="text-[0.7812rem] text-muted-foreground"
                                >{{ channelsOn.length }}/{{
                                    accounts.length
                                }}
                                đang bật</span
                            >
                        </div>
                        <ChannelPanel
                            v-for="a in accounts"
                            :key="a.id"
                            :account="a"
                            :today="lich.channels[a.id]?.today"
                            :chrome="health.channels.find((c) => c.id === a.id)"
                            :blocked-count="blockedOf(a.id)"
                        />
                    </section>

                    <RecentList
                        :recent="recent"
                        :failed="failed_recent ?? []"
                        :product-name="productName"
                        :limit="sideBySide ? 20 : 6"
                        class="xl:flex-1"
                    />
                </aside>
            </div>

            <section
                :class="cn(cardCls, 'overflow-hidden')"
                data-testid="fork-auto-stock"
            >
                <header
                    class="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b px-5 py-3"
                >
                    <div class="flex flex-wrap items-baseline gap-x-3">
                        <h2
                            class="font-heading text-[0.9375rem] font-semibold tracking-[-0.01em]"
                        >
                            Kho theo sản phẩm
                        </h2>
                        <span
                            v-if="stockRows.length"
                            class="text-[0.7812rem] text-muted-foreground tabular-nums"
                        >
                            {{ stockRows.length }} sản phẩm ·
                            {{ fmtNum(stockSum.new) }} chờ xếp ·
                            {{ fmtNum(stockSum.scheduled) }} đã hẹn
                        </span>
                    </div>
                    <div
                        class="flex items-center gap-4 text-[0.75rem] text-muted-foreground"
                    >
                        <span class="hidden items-center gap-1.5 sm:inline-flex"
                            ><i class="h-1.5 w-3 rounded-full bg-primary" />Chờ
                            xếp</span
                        >
                        <span class="hidden items-center gap-1.5 sm:inline-flex"
                            ><i
                                class="h-1.5 w-3 rounded-full bg-primary/35"
                            />Đã hẹn</span
                        >
                        <Link
                            href="/auto/kho"
                            class="text-[0.7812rem] font-medium text-primary-text hover:underline"
                            >Kho video →</Link
                        >
                    </div>
                </header>
                <ul
                    v-if="stockRows.length"
                    class="grid gap-x-2 gap-y-0.5 p-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5"
                >
                    <li
                        v-for="p in stockShown"
                        :key="p.code"
                        class="flex items-center gap-3 rounded-lg px-2.5 py-2 transition-colors hover:bg-accent/40"
                        :class="!p.enabled && 'opacity-60'"
                        :title="p.enabled ? p.name : `${p.name} (đang tắt)`"
                        :data-testid="`fork-auto-product-${p.code}`"
                    >
                        <ProductThumb :src="p.image" class="size-9" />
                        <div class="min-w-0 flex-1">
                            <div
                                class="flex items-baseline justify-between gap-2 text-[0.8125rem]"
                            >
                                <span class="truncate font-medium">{{
                                    p.short_name
                                }}</span>
                                <span
                                    class="shrink-0 text-muted-foreground tabular-nums"
                                    ><b class="font-semibold text-foreground">{{
                                        fmtNum(p.counts.new)
                                    }}</b>
                                    · {{ fmtNum(p.counts.scheduled) }}</span
                                >
                            </div>
                            <div
                                class="mt-1 flex h-1 overflow-hidden rounded-full bg-muted"
                            >
                                <span
                                    class="bg-primary"
                                    :style="{
                                        width: `${(p.counts.new / stockMax) * 100}%`,
                                    }"
                                />
                                <span
                                    class="bg-primary/35"
                                    :style="{
                                        width: `${(p.counts.scheduled / stockMax) * 100}%`,
                                    }"
                                />
                            </div>
                            <div
                                class="mt-0.5 truncate text-[0.7188rem] text-muted-foreground/90 tabular-nums"
                            >
                                {{ fmtNum(p.counts.posted) }} đã đăng<template
                                    v-if="p.counts.failed"
                                >
                                    ·
                                    {{ fmtNum(p.counts.failed) }} lỗi</template
                                ><template v-if="!p.enabled">
                                    · đang tắt</template
                                >
                            </div>
                        </div>
                    </li>
                </ul>
                <p
                    v-else
                    class="px-4 py-5 text-center text-[0.8125rem] text-muted-foreground"
                >
                    Chưa có sản phẩm nào. App sẽ đọc từ Xưởng Video ở lần quét
                    tới.
                </p>
                <div
                    v-if="stockRows.length > STOCK_FOLD"
                    class="border-t px-5 py-2 text-center"
                >
                    <button
                        type="button"
                        class="text-[0.7812rem] font-medium text-primary-text hover:underline"
                        @click="showAllStock = !showAllStock"
                    >
                        {{
                            showAllStock
                                ? 'Thu gọn'
                                : `Xem tất cả ${stockRows.length} sản phẩm`
                        }}
                    </button>
                </div>
            </section>
        </template>
    </AutoShell>
</template>

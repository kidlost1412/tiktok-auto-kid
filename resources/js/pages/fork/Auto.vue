<script setup lang="ts">
// Trang riêng của bản Việt hoá: "Tổng quan & Lịch" - theo dõi và điều khiển việc tự động đăng video từ hub sản xuất.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en).
import { Link, router } from '@inertiajs/vue3';
import {
    IconBolt,
    IconBrandTiktok,
    IconBuildingWarehouse,
    IconChartBar,
    IconChevronDown,
    IconDeviceTv,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import ChannelCard from '@/components/fork/auto/ChannelCard.vue';
import HealthStrip from '@/components/fork/auto/HealthStrip.vue';
import KpiStrip from '@/components/fork/auto/KpiStrip.vue';
import OnboardingCard from '@/components/fork/auto/OnboardingCard.vue';
import RecentPosts from '@/components/fork/auto/RecentPosts.vue';
import ScheduleTimeline from '@/components/fork/auto/ScheduleTimeline.vue';
import type {
    AccountRow,
    FailedRow,
    Health,
    HubStatus,
    Lich,
    Onboarding,
    ProductRow,
    RecentRow,
} from '@/components/fork/auto/types';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import {
    cardCls,
    fmtNum,
    tableWrapCls,
    tdCls,
    thCls,
    toneClasses,
} from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

interface UpcomingRow {
    id: number;
    file_name: string;
    product_code: string | null;
    username: string | null;
    scheduled_for: string | null;
    caption: string | null;
}

interface Group {
    key: string;
    avg_views: number;
    samples: number;
}

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
    plan_ahead_hours: number;
    upcoming: UpcomingRow[];
    recent: RecentRow[];
    failed_recent?: FailedRow[];
    /** Tải sau (hỏi hub); null = đã xong hoặc đã ẩn. */
    onboarding?: Onboarding | null;
    insights: Record<string, Group[]>;
    hasWorkspace: boolean;
}>();

const planning = ref(false);

// "Xếp lịch ngay": chạy cùng bộ xếp lịch của cron, chỉ cho các kênh của chủ tài khoản.
// Kết quả hiện bằng thông báo (toast) từ phản hồi của máy chủ.
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

const fmtClock = (iso: string | null) =>
    iso ? dayjs(iso).format('HH:mm:ss DD/MM') : '—';

// Video đã duyệt nhưng bị giữ vì chưa chọn giỏ: lấy kênh bị chặn nhiều nhất (cùng một kho nên không cộng dồn các kênh).
const blocked = computed(() => {
    let best: {
        id: string;
        total: number;
        groups: { code: string; quy_cach: string | null; label: string; count: number; image?: string | null }[];
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

const channelsOn = computed(() => props.accounts.filter((a) => a.enabled));

const description = computed(() => {
    const sched = props.stock.scheduled_total ?? 0;
    const base = `Còn ${fmtNum(props.stock.new_total)} video chưa xếp lịch`;
    const withSched = sched > 0 ? `${base} · ${fmtNum(sched)} bài đã xếp lịch chờ đăng` : base;

    return props.stock.days_left !== null
        ? `${withSched} (đủ khoảng ${props.stock.days_left} ngày đăng).`
        : `${withSched}.`;
});

// Số liệu đọc từ DB lúc tải trang; tự làm mới để không hiện số cũ.
let refreshTimer: ReturnType<typeof setInterval> | undefined;

onMounted(() => {
    refreshTimer = setInterval(() => {
        if (document.visibilityState === 'visible') {
            router.reload({
                only: [
                    'products',
                    'stock',
                    'upcoming',
                    'recent',
                    'failed_recent',
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

const analyses = computed(() => [
    {
        key: 'hour',
        title: 'Theo giờ đăng',
        fmt: (k: string) => `${Number(k)}h`,
    },
    {
        key: 'product_code',
        title: 'Theo sản phẩm',
        fmt: (k: string) => productName(k),
    },
    { key: 'goc', title: 'Theo góc', fmt: (k: string) => k },
    { key: 'giong', title: 'Theo giọng', fmt: (k: string) => k },
    { key: 'nhac', title: 'Theo nhạc', fmt: (k: string) => k },
    { key: 'font', title: 'Theo font', fmt: (k: string) => k },
    { key: 'chuyen_canh', title: 'Theo chuyển cảnh', fmt: (k: string) => k },
    { key: 'mau', title: 'Theo màu', fmt: (k: string) => k },
]);
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

        <KpiStrip :accounts="accounts" :lich="lich" :stock="stock" />

        <HealthStrip :hub="hub" :health="health" :accounts="accounts" />

        <!-- Cảnh báo cần xử lý -->
        <div class="flex flex-col gap-3 empty:hidden">
            <Callout v-if="blocked" tone="warn" data-testid="fork-auto-blocked">
                <b>{{ blocked.total }} video đã duyệt chưa được đăng</b>
                vì chưa chọn giỏ hàng:
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
                Video còn lại ({{ stock.new_total + (stock.scheduled_total ?? 0) }},
                gồm cả bài đã xếp lịch) không đủ cho một ngày đăng ({{ stock.daily_cap }} bài). Hãy sản xuất thêm video trong
                hub.
            </Callout>
            <Callout v-if="accounts.length && !channelsOn.length" tone="danger">
                Chưa kênh nào bật tự động đăng. Bật công tắc ở thẻ kênh bên dưới
                để app bắt đầu xếp lịch.
            </Callout>
        </div>

        <!-- Các kênh -->
        <section id="kenh" class="flex scroll-mt-24 flex-col gap-5">
            <SectionHeading
                :icon="IconDeviceTv"
                title="Kênh TikTok"
                description="Bật kênh, chỉnh hạn mức, khung giờ và số ngày hẹn trước ngay trên thẻ."
            />
            <div class="grid gap-5 lg:grid-cols-[repeat(auto-fit,minmax(34rem,1fr))]">
                <ChannelCard
                    v-for="a in accounts"
                    :key="a.id"
                    :account="a"
                    :avatar-url="a.avatar_url"
                    :today="lich.channels[a.id]?.today"
                    :blocked-count="
                        (lich.channels[a.id]?.blocked ?? []).reduce(
                            (s, g) => s + g.count,
                            0,
                        )
                    "
                />
            </div>
            <EmptyState
                v-if="!accounts.length"
                :icon="IconBrandTiktok"
                title="Chưa có tài khoản TikTok nào"
                description="Kết nối tài khoản TikTok và bật đăng qua Chrome để app bắt đầu tự động đăng."
            >
                <Button as-child size="sm">
                    <Link href="/settings/chrome">Kết nối Chrome →</Link>
                </Button>
            </EmptyState>
        </section>

        <ScheduleTimeline
            v-if="accounts.length"
            :lich="lich"
            :accounts="accounts"
        />

        <RecentPosts
            :recent="recent"
            :failed="failed_recent ?? []"
            :product-name="productName"
        />

        <!-- Kho video theo sản phẩm -->
        <details
            :class="cn(cardCls, 'group p-5 sm:p-6')"
            data-testid="fork-auto-stock"
        >
            <summary
                class="flex cursor-pointer list-none flex-wrap items-center gap-3.5 select-none [&::-webkit-details-marker]:hidden"
            >
                <span
                    :class="cn('flex size-[38px] shrink-0 items-center justify-center rounded-[11px]', toneClasses.info.chip)"
                >
                    <IconBuildingWarehouse class="size-[18px]" />
                </span>
                <span class="min-w-0 flex-1">
                    <span
                        class="block font-heading text-lg leading-snug font-semibold tracking-[-0.015em]"
                        >Kho video theo sản phẩm</span
                    >
                    <span class="block text-[13px] text-muted-foreground"
                        >cập nhật {{ fmtClock(stock.updated_at)
                        }}<template v-if="stock.last_ingest_at"
                            >, quét kho lần cuối
                            {{ fmtClock(stock.last_ingest_at) }}</template
                        ></span
                    >
                </span>
                <IconChevronDown
                    class="size-5 text-muted-foreground transition-transform group-open:rotate-180"
                />
            </summary>
            <div :class="cn(tableWrapCls, 'mt-4')">
                <table class="w-full border-separate border-spacing-0 text-sm">
                    <thead>
                        <tr>
                            <th :class="thCls">Sản phẩm</th>
                            <th :class="cn(thCls, 'text-right')">Mới</th>
                            <th :class="cn(thCls, 'text-right')">Đã xếp</th>
                            <th :class="cn(thCls, 'text-right')">Đã đăng</th>
                            <th :class="cn(thCls, 'text-right')">Bỏ qua</th>
                            <th :class="cn(thCls, 'text-right')">Lỗi</th>
                        </tr>
                    </thead>
                    <tbody class="tabular-nums [&>tr:hover>td]:bg-accent/60 [&>tr:last-child>td]:border-b-0">
                        <tr
                            v-for="p in products"
                            :key="p.code"
                            :data-testid="`fork-auto-product-${p.code}`"
                        >
                            <td :class="cn(tdCls, 'font-medium')">
                                <span class="flex items-center gap-2.5">
                                    <ProductThumb :src="p.image" />
                                    {{ p.short_name }}
                                    <span
                                        v-if="!p.enabled"
                                        class="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground"
                                        >tắt</span
                                    >
                                </span>
                            </td>
                            <td :class="cn(tdCls, 'text-right')">{{ p.counts.new }}</td>
                            <td :class="cn(tdCls, 'text-right')">{{ p.counts.scheduled }}</td>
                            <td :class="cn(tdCls, 'text-right')">{{ p.counts.posted }}</td>
                            <td :class="cn(tdCls, 'text-right')">{{ p.counts.skipped }}</td>
                            <td :class="cn(tdCls, 'text-right')">{{ p.counts.failed }}</td>
                        </tr>
                        <tr v-if="!products.length">
                            <td colspan="6" class="p-6 text-center text-muted-foreground">
                                Chưa có sản phẩm nào. Hệ thống sẽ đọc từ hub sau
                                lần quét kế tiếp.
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </details>

        <!-- Phân tích -->
        <details :class="cn(cardCls, 'group p-5 sm:p-6')">
            <summary
                class="flex cursor-pointer list-none flex-wrap items-center gap-3.5 select-none [&::-webkit-details-marker]:hidden"
            >
                <span
                    :class="cn('flex size-[38px] shrink-0 items-center justify-center rounded-[11px]', toneClasses.violet.chip)"
                >
                    <IconChartBar class="size-[18px]" />
                </span>
                <span class="min-w-0 flex-1">
                    <span
                        class="block font-heading text-lg leading-snug font-semibold tracking-[-0.015em]"
                        >Phân tích nhanh (lượt xem trung bình sau 24 giờ)</span
                    >
                    <Link
                        href="/auto/so-lieu"
                        class="text-[13px] font-medium text-primary-text hover:underline"
                        @click.stop
                        >Mở trang Số liệu để xem đầy đủ →</Link
                    >
                </span>
                <IconChevronDown
                    class="size-5 text-muted-foreground transition-transform group-open:rotate-180"
                />
            </summary>
            <div class="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                <div
                    v-for="g in analyses"
                    :key="g.key"
                    :class="cn(tableWrapCls, 'overflow-hidden')"
                    :data-testid="`fork-auto-insight-${g.key}`"
                >
                    <div class="border-b bg-muted px-3.5 py-2.5 text-sm font-semibold">
                        {{ g.title }}
                    </div>
                    <table class="w-full border-separate border-spacing-0 text-sm">
                        <tbody class="tabular-nums [&>tr:hover>td]:bg-accent/60 [&>tr:last-child>td]:border-b-0">
                            <tr
                                v-for="row in insights[g.key] ?? []"
                                :key="row.key"
                            >
                                <td :class="tdCls">{{ g.fmt(row.key) }}</td>
                                <td :class="cn(tdCls, 'text-right font-medium')">
                                    {{ fmtNum(row.avg_views) }}
                                </td>
                                <td
                                    :class="cn(tdCls, 'text-right text-muted-foreground')"
                                >
                                    {{ row.samples }} bài
                                </td>
                            </tr>
                            <tr v-if="!(insights[g.key] ?? []).length">
                                <td :class="cn(tdCls, 'text-muted-foreground')">
                                    Chưa có số liệu.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </details>
    </AutoShell>
</template>

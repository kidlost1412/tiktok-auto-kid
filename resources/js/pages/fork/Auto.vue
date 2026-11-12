<script setup lang="ts">
// Trang riêng của bản Việt hoá: "Tổng quan & Lịch" - theo dõi và điều khiển việc tự động đăng video từ hub sản xuất.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en).
import { Link, router } from '@inertiajs/vue3';
import { IconBolt, IconBrandTiktok } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import ChannelCard from '@/components/fork/auto/ChannelCard.vue';
import KpiStrip from '@/components/fork/auto/KpiStrip.vue';
import HealthStrip from '@/components/fork/auto/HealthStrip.vue';
import RecentPosts from '@/components/fork/auto/RecentPosts.vue';
import ScheduleTimeline from '@/components/fork/auto/ScheduleTimeline.vue';
import type {
    AccountRow,
    Health,
    HubStatus,
    Lich,
    ProductRow,
    RecentRow,
} from '@/components/fork/auto/types';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { fmtNum } from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';

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
    const base = `Còn ${fmtNum(props.stock.new_total)} video đã duyệt trong kho`;

    return props.stock.days_left !== null
        ? `${base} (đủ khoảng ${props.stock.days_left} ngày đăng).`
        : `${base}.`;
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
                Video mới còn lại ({{ stock.new_total }}) không đủ cho một ngày
                đăng ({{ stock.daily_cap }} bài). Hãy sản xuất thêm video trong
                hub.
            </Callout>
            <Callout v-if="accounts.length && !channelsOn.length" tone="danger">
                Chưa kênh nào bật tự động đăng. Bật công tắc ở thẻ kênh bên dưới
                để app bắt đầu xếp lịch.
            </Callout>
        </div>

        <!-- Các kênh -->
        <section id="kenh" class="flex scroll-mt-24 flex-col gap-4">
            <SectionHeading
                title="Kênh TikTok"
                description="Bật kênh, chỉnh hạn mức, khung giờ và số ngày hẹn trước ngay trên thẻ."
            />
            <div class="grid gap-6 lg:grid-cols-[repeat(auto-fit,minmax(34rem,1fr))] 2xl:grid-cols-[repeat(auto-fit,minmax(38rem,1fr))]">
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

        <RecentPosts :recent="recent" :product-name="productName" />

        <!-- Kho video theo sản phẩm -->
        <details
            class="group rounded-2xl border bg-card p-5 shadow-xs"
            data-testid="fork-auto-stock"
        >
            <summary
                class="flex cursor-pointer flex-wrap items-baseline gap-x-3 text-lg font-semibold select-none"
            >
                Kho video theo sản phẩm
                <span class="text-sm font-normal text-muted-foreground"
                    >cập nhật {{ fmtClock(stock.updated_at)
                    }}<template v-if="stock.last_ingest_at"
                        >, quét kho lần cuối
                        {{ fmtClock(stock.last_ingest_at) }}</template
                    ></span
                >
            </summary>
            <div class="mt-3 overflow-x-auto">
                <table class="w-full text-sm">
                    <thead class="text-left text-muted-foreground">
                        <tr>
                            <th class="p-3 font-medium">Sản phẩm</th>
                            <th class="p-3 font-medium">Mới</th>
                            <th class="p-3 font-medium">Đã xếp</th>
                            <th class="p-3 font-medium">Đã đăng</th>
                            <th class="p-3 font-medium">Bỏ qua</th>
                            <th class="p-3 font-medium">Lỗi</th>
                        </tr>
                    </thead>
                    <tbody class="tabular-nums">
                        <tr
                            v-for="p in products"
                            :key="p.code"
                            class="border-t"
                            :data-testid="`fork-auto-product-${p.code}`"
                        >
                            <td class="flex items-center gap-2 p-2 font-medium">
                                <ProductThumb :src="p.image" />
                                {{ p.short_name }}
                                <span
                                    v-if="!p.enabled"
                                    class="ml-1 rounded-full bg-muted px-1.5 py-0.5 text-xs font-normal text-muted-foreground"
                                    >tắt</span
                                >
                            </td>
                            <td class="p-3">{{ p.counts.new }}</td>
                            <td class="p-3">{{ p.counts.scheduled }}</td>
                            <td class="p-3">{{ p.counts.posted }}</td>
                            <td class="p-3">{{ p.counts.skipped }}</td>
                            <td class="p-3">{{ p.counts.failed }}</td>
                        </tr>
                        <tr v-if="!products.length">
                            <td colspan="6" class="p-3 text-muted-foreground">
                                Chưa có sản phẩm nào. Hệ thống sẽ đọc từ hub sau
                                lần quét kế tiếp.
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </details>

        <!-- Phân tích -->
        <details class="group rounded-2xl border bg-card p-5 shadow-xs">
            <summary
                class="flex cursor-pointer flex-wrap items-baseline gap-x-3 text-lg font-semibold select-none"
            >
                Phân tích nhanh (lượt xem trung bình sau 24 giờ)
                <Link
                    href="/auto/so-lieu"
                    class="text-sm font-normal text-primary hover:underline"
                    @click.stop
                    >Mở trang Số liệu để xem đầy đủ →</Link
                >
            </summary>
            <div class="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <div
                    v-for="g in analyses"
                    :key="g.key"
                    class="overflow-hidden rounded-lg border"
                    :data-testid="`fork-auto-insight-${g.key}`"
                >
                    <div class="border-b bg-muted/50 p-3 text-base font-medium">
                        {{ g.title }}
                    </div>
                    <table class="w-full text-sm">
                        <tbody>
                            <tr
                                v-for="row in insights[g.key] ?? []"
                                :key="row.key"
                                class="border-t first:border-t-0"
                            >
                                <td class="p-3">{{ g.fmt(row.key) }}</td>
                                <td class="p-3 text-right tabular-nums">
                                    {{ fmtNum(row.avg_views) }}
                                </td>
                                <td
                                    class="p-3 text-right text-muted-foreground"
                                >
                                    {{ row.samples }} bài
                                </td>
                            </tr>
                            <tr v-if="!(insights[g.key] ?? []).length">
                                <td class="p-3 text-muted-foreground">
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

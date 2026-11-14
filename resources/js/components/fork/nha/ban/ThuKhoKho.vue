<script setup lang="ts">
// Nội dung tab "Kho video" của bàn Thủ kho cho MỘT bộ lọc (tab trạng thái + sản phẩm): đọc /auto/kho?tab=…&product=…
// Tóm tắt số video theo trạng thái (bấm để chuyển tab), chip sản phẩm, lưới video (VideoCard), nút "Quét kho ngay".
import { router } from '@inertiajs/vue3';
import { IconRefresh, IconVideoOff } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import type { KhoVideo } from '@/components/fork/kho/kho';
import VideoCard from '@/components/fork/kho/VideoCard.vue';
import { banBao } from '@/components/fork/nha/ban/bus';
import { useInertiaProps } from '@/components/fork/nha/ban/useInertiaProps';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { cardCls, fmtNum, toneClasses } from '@/components/fork/shared/status';
import { openVideo } from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    /** null = chưa chọn: tự lấy tab đầu tiên có video. */
    tab: string | null;
    product: string;
}>();
const emit = defineEmits<{ tab: [key: string]; product: [code: string] }>();

type KhoProps = {
    filters: { tab: string; product: string };
    counts: Record<string, number>;
    products: {
        code: string;
        name: string;
        image?: string | null;
        count: number;
    }[];
    videos: { data: KhoVideo[]; total: number; last_page: number };
    kho: { waiting: number; error: number };
    last_ingest_at: string | null;
};

const q = new URLSearchParams();
q.set('tab', props.tab ?? 'cho');

if (props.product) {
    q.set('product', props.product);
}

const {
    props: p,
    error,
    reload,
} = useInertiaProps<KhoProps>(`/auto/kho?${q.toString()}`, 'fork/Kho', [
    'filters',
    'counts',
    'products',
    'videos',
    'kho',
    'last_ingest_at',
]);

// Giống trang Kho: chưa chọn tab mà tab "Chờ đăng" trống thì tự nhảy sang tab đầu tiên có video.
const AUTO_ORDER = ['xep', 'loi', 'dang'];
const autoJump = ref(props.tab === null);

let poll: ReturnType<typeof setInterval> | undefined;
onMounted(async () => {
    await reload();

    if (autoJump.value && p.value) {
        autoJump.value = false;

        if ((p.value.counts.cho ?? 0) === 0) {
            const k = AUTO_ORDER.find((x) => (p.value?.counts[x] ?? 0) > 0);

            if (k) {
                emit('tab', k);
            }
        }
    }

    poll = setInterval(() => {
        if (document.visibilityState === 'visible') {
            reload();
        }
    }, 30000);
});
onBeforeUnmount(() => clearInterval(poll));

const current = computed(() => props.tab ?? 'cho');

const tiles = computed(() => {
    const c = p.value?.counts ?? {};

    return [
        { key: 'cho', label: 'Chờ đăng', dot: 'bg-primary', n: c.cho ?? 0 },
        {
            key: 'xep',
            label: 'Đã xếp lịch',
            dot: toneClasses.info.dot,
            n: c.xep ?? 0,
        },
        {
            key: 'dang',
            label: 'Đã đăng',
            dot: toneClasses.success.dot,
            n: c.dang ?? 0,
        },
        {
            key: 'loi',
            label: 'Lỗi và bỏ qua',
            dot: toneClasses.danger.dot,
            n: c.loi ?? 0,
        },
    ];
});

const videos = computed(() => p.value?.videos.data ?? []);
const products = computed(() =>
    (p.value?.products ?? []).filter(
        (x) => x.count > 0 || x.code === props.product,
    ),
);

const open = (v: KhoVideo) =>
    openVideo(
        videos.value.map((x) => x.id),
        v.id,
        videos.value,
    );

// "Quét kho ngay": đưa video mới của Xưởng Video vào kho của app (cùng nút ở trang Kho).
const scanning = ref(false);
const scan = () => {
    scanning.value = true;
    router.post(
        '/auto/kho/scan',
        {},
        {
            preserveScroll: true,
            preserveState: true,
            onSuccess: () => {
                reload();
                banBao('thukho', 'quet');
            },
            onFinish: () => {
                scanning.value = false;
            },
        },
    );
};

const onRetried = () => {
    reload();
    banBao('thukho', 'xem');
};

const tileLabel =
    'text-xs font-medium tracking-[0.02em] text-muted-foreground uppercase';
</script>

<template>
    <div
        class="flex min-h-0 flex-1 flex-col gap-4"
        data-testid="ban-thukho-kho"
    >
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

        <template v-else-if="!p">
            <div class="grid grid-cols-4 gap-3">
                <Skeleton v-for="i in 4" :key="i" class="h-20 rounded-[14px]" />
            </div>
            <div class="grid grid-cols-5 gap-3">
                <Skeleton
                    v-for="i in 5"
                    :key="i"
                    class="aspect-[9/16] rounded-[14px]"
                />
            </div>
        </template>

        <template v-else>
            <div class="flex items-center justify-between gap-3">
                <p class="min-w-0 truncate text-sm text-muted-foreground">
                    Lần quét kho gần nhất:
                    {{
                        p.last_ingest_at
                            ? dayjs(p.last_ingest_at).format('HH:mm DD/MM')
                            : 'chưa quét lần nào'
                    }}
                </p>
                <Button
                    variant="outline"
                    :disabled="scanning"
                    data-testid="ban-thukho-quet"
                    @click="scan"
                >
                    <Spinner v-if="scanning" class="size-4" />
                    <IconRefresh v-else class="size-4" />
                    {{ scanning ? 'Đang quét…' : 'Quét kho ngay' }}
                </Button>
            </div>

            <!-- Tóm tắt theo trạng thái (bấm để lọc) -->
            <div class="grid grid-cols-4 gap-3" data-testid="ban-thukho-tomtat">
                <button
                    v-for="t in tiles"
                    :key="t.key"
                    type="button"
                    :aria-pressed="current === t.key"
                    :class="
                        cn(
                            cardCls,
                            'flex min-w-0 flex-col gap-1 px-4 py-3.5 text-left transition-colors hover:bg-accent/40',
                            current === t.key &&
                                'border-primary bg-primary/[0.05] dark:bg-primary/10',
                        )
                    "
                    @click="emit('tab', t.key)"
                >
                    <span :class="cn(tileLabel, 'flex items-center gap-2')">
                        <i :class="cn('size-2 rounded-full', t.dot)" />
                        {{ t.label }}
                    </span>
                    <span
                        class="font-heading text-2xl font-semibold tabular-nums"
                        >{{ fmtNum(t.n) }}</span
                    >
                </button>
            </div>

            <!-- Chip sản phẩm -->
            <div
                v-if="products.length"
                class="flex flex-wrap items-center gap-1.5"
                data-testid="ban-thukho-sanpham"
            >
                <button
                    type="button"
                    :class="
                        cn(
                            'h-8 rounded-full border px-3 text-sm font-medium transition-colors',
                            product === ''
                                ? 'border-primary bg-primary/[0.07] text-foreground dark:bg-primary/15'
                                : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                        )
                    "
                    @click="emit('product', '')"
                >
                    Tất cả sản phẩm
                </button>
                <button
                    v-for="x in products"
                    :key="x.code"
                    type="button"
                    :class="
                        cn(
                            'flex h-8 items-center gap-2 rounded-full border py-1 pr-3 pl-1 text-sm font-medium transition-colors',
                            product === x.code
                                ? 'border-primary bg-primary/[0.07] text-foreground dark:bg-primary/15'
                                : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                        )
                    "
                    @click="emit('product', product === x.code ? '' : x.code)"
                >
                    <ProductThumb :src="x.image" class="size-6 rounded-full" />
                    {{ x.name }}
                    <span class="text-xs tabular-nums opacity-70">{{
                        x.count
                    }}</span>
                </button>
            </div>

            <!-- Lưới video -->
            <div
                v-if="videos.length"
                class="grid grid-cols-5 gap-3"
                data-testid="ban-thukho-luoi"
            >
                <VideoCard
                    v-for="v in videos"
                    :key="v.id"
                    :video="v"
                    in-place
                    @open="open(v)"
                    @retried="onRetried"
                />
            </div>
            <EmptyState
                v-else
                class="gap-2 py-8"
                :icon="IconVideoOff"
                :title="
                    current === 'cho'
                        ? 'Chưa có video nào đang chờ đăng'
                        : 'Không có video nào trong mục này'
                "
                description="Hãy làm video ở Xưởng Video rồi bấm Quét kho ngay để lấy video mới về."
            />
            <p
                v-if="p.videos.total > videos.length"
                class="text-center text-xs text-muted-foreground tabular-nums"
            >
                Đang hiện {{ videos.length }}/{{ fmtNum(p.videos.total) }} video
                — mở trang đầy đủ để xem hết.
            </p>
        </template>
    </div>
</template>

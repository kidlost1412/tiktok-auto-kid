<script setup lang="ts">
// Lịch đăng. Màn rộng (≥1536px): 3 ngày cạnh nhau, mỗi cột có đầu cột (ngày, số bài, thanh tiến độ) và cuộn riêng.
// Màn hẹp hơn: chọn ngày bằng tab ở đầu thẻ, hiện một ngày. Nét đứt là giờ dự kiến, chưa hẹn lên TikTok.
import { Link } from '@inertiajs/vue3';
import {
    IconArrowsShuffle,
    IconBolt,
    IconClock,
    IconShoppingCartOff,
    IconTrash,
} from '@tabler/icons-vue';
import { useMediaQuery } from '@vueuse/core';
import { computed, ref } from 'vue';

import { channelColor } from '@/components/fork/auto/channelColors';
import DirectWindowDialog from '@/components/fork/auto/DirectWindowDialog.vue';
import { dragging } from '@/components/fork/auto/dragMove';
import MixDialog from '@/components/fork/auto/MixDialog.vue';
import ScheduleDayList from '@/components/fork/auto/ScheduleDayList.vue';
import TrashDialog from '@/components/fork/auto/TrashDialog.vue';
import type {
    AccountRow,
    DirectWindow,
    Lich,
    ScheduleEntry,
} from '@/components/fork/auto/types';
import HelpToggle from '@/components/fork/shared/HelpToggle.vue';
import { matchesSource } from '@/components/fork/shared/source';
import type { SourceFilter as SourceFilterValue } from '@/components/fork/shared/source';
import SourceFilter from '@/components/fork/shared/SourceFilter.vue';
import {
    cardCls,
    EDITABLE_STATES,
    toneClasses,
} from '@/components/fork/shared/status';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    lich: Lich;
    accounts: AccountRow[];
    directWindow?: DirectWindow | null;
}>();

const directOpen = ref(false);
// Chỉ hiện video còn nằm trong app (chưa lên TikTok): sửa / xoá thoải mái.
const onlyEditable = ref(false);
// Chỉ hiện bài sắp đăng mà giỏ có vấn đề (hết hàng / không còn trong shop).
const onlyCart = ref(false);
const trashOpen = ref(false);
const mixOpen = ref(false);

const wide = useMediaQuery('(min-width: 1536px)');

const channel = ref<string>('all');
// Lọc nguồn: video AI (Xưởng Video) / Kho riêng.
const source = ref<SourceFilterValue>('all');
const picked = ref<string | null>(null);
// Có bộ lọc nào đang bật: ngày trống thì nói "không có bài khớp bộ lọc" thay vì lý do khác.
const filtered = computed(
    () =>
        channel.value !== 'all' ||
        source.value !== 'all' ||
        onlyEditable.value ||
        onlyCart.value,
);

const entries = computed<ScheduleEntry[]>(() => {
    const out: ScheduleEntry[] = [];

    props.accounts.forEach((a, color) => {
        if (channel.value !== 'all' && channel.value !== a.id) {
            return;
        }

        for (const item of props.lich.channels[a.id]?.items ?? []) {
            if (onlyCart.value && !item.cart_warn) {
                continue;
            }

            // Giờ trống (không có video) chỉ hiện khi không lọc nguồn.
            if (
                source.value !== 'all' &&
                !(item.source && matchesSource(item.source, source.value))
            ) {
                continue;
            }

            if (onlyEditable.value && !EDITABLE_STATES.includes(item.state)) {
                continue;
            }

            out.push({
                ...item,
                channelId: a.id,
                username: a.username ?? a.display_name ?? '—',
                color,
            });
        }
    });

    return out.sort((x, y) => dayjs(x.at).valueOf() - dayjs(y.at).valueOf());
});

const notes = computed(() =>
    props.accounts
        .filter((a) => channel.value === 'all' || channel.value === a.id)
        .flatMap((a) => [
            {
                id: a.id,
                username: a.username ?? '—',
                note: props.lich.channels[a.id]?.note ?? null,
                cart: false,
            },
            {
                id: `${a.id}-cart`,
                username: a.username ?? '—',
                note: props.lich.channels[a.id]?.cart_stale ?? null,
                cart: true,
            },
        ])
        .filter((n) => n.note),
);

// Số bài sắp đăng có giỏ lỗi (mọi kênh, mọi ngày đang xem).
const cartCount = computed(() =>
    props.accounts.reduce(
        (n, a) =>
            n +
            (props.lich.channels[a.id]?.items ?? []).filter((i) => i.cart_warn)
                .length,
        0,
    ),
);

const todayKey = computed(() => dayjs().format('YYYY-MM-DD'));

const days = computed(() =>
    props.lich.days.map((d, i) => {
        const list = entries.value.filter((e) => e.day === d.key);
        const real = list.filter((e) => e.state !== 'projected').length;
        const posted = list.filter((e) => e.state === 'posted').length;
        const failed = list.filter((e) => e.state === 'failed').length;
        const onTikTok = list.filter(
            (e) => e.state === 'tiktok_scheduled' || e.state === 'uploading',
        ).length;
        const inApp = list.filter((e) =>
            EDITABLE_STATES.includes(e.state),
        ).length;
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
            onTikTok,
            inApp,
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

// Số video đã xếp mà còn nằm trong app (mọi ngày đang xem, đúng bộ lọc kênh / nguồn).
const editableCount = computed(() => {
    let n = 0;

    for (const a of props.accounts) {
        if (channel.value !== 'all' && channel.value !== a.id) {
            continue;
        }

        for (const item of props.lich.channels[a.id]?.items ?? []) {
            if (
                EDITABLE_STATES.includes(item.state) &&
                (source.value === 'all' ||
                    (item.source && matchesSource(item.source, source.value)))
            ) {
                n++;
            }
        }
    }

    return n;
});
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
                <HelpToggle>
                    <template #title>
                        <h2 class="font-heading text-[1.0625rem] font-semibold">
                            Lịch đăng
                        </h2>
                    </template>
                    Bấm dòng để xem / sửa video. Bấm giờ hoặc kéo thả để đổi
                    giờ. Bài đã hẹn trên TikTok thì app xoá bài hẹn cũ rồi hẹn
                    lại.
                </HelpToggle>
            </div>
            <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
                <!-- Chú thích chấm trạng thái (kiểu 3 cột) -->
                <div
                    v-if="wide"
                    class="flex items-center gap-3 text-[0.8125rem] text-muted-foreground"
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
                        />Đã hẹn trên TikTok</span
                    >
                    <span class="inline-flex items-center gap-1"
                        ><IconClock class="size-3.5" />Chưa lên TikTok</span
                    >
                    <span
                        v-if="directWindow?.enabled"
                        class="inline-flex items-center gap-1"
                        ><IconBolt class="size-3.5" />Đăng thẳng</span
                    >
                    <span class="inline-flex items-center gap-1.5"
                        ><i
                            class="size-2 rounded-full border border-dashed border-muted-foreground"
                        />Dự kiến</span
                    >
                </div>
                <button
                    type="button"
                    :aria-pressed="onlyEditable"
                    :class="
                        cn(
                            'inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-[0.875rem] font-medium transition-colors',
                            onlyEditable
                                ? 'border-primary bg-primary/10 text-primary-text'
                                : 'bg-card text-foreground hover:bg-accent',
                        )
                    "
                    title="Video đã xếp mà chưa gửi lên TikTok: sửa, xoá thoải mái. Bấm để chỉ xem các video này."
                    data-testid="fork-auto-only-editable"
                    @click="onlyEditable = !onlyEditable"
                >
                    <b class="tabular-nums">{{ editableCount }}</b>
                    chưa lên TikTok
                </button>
                <button
                    v-if="directWindow"
                    type="button"
                    :class="
                        cn(
                            'inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-[0.875rem] font-medium transition-colors hover:bg-accent',
                            directWindow.enabled
                                ? 'bg-secondary text-foreground'
                                : 'bg-card text-muted-foreground',
                        )
                    "
                    title="Khung giờ đăng thẳng: trong khung tới giờ Chrome đăng luôn, không hẹn trước lên TikTok"
                    data-testid="fork-auto-direct-open"
                    @click="directOpen = true"
                >
                    <IconBolt class="size-4" />
                    <template v-if="directWindow.enabled"
                        >Đăng thẳng {{ directWindow.start }}–{{
                            directWindow.end
                        }}</template
                    >
                    <template v-else>Đăng thẳng: tắt</template>
                </button>
                <button
                    v-if="cartCount || onlyCart"
                    type="button"
                    :aria-pressed="onlyCart"
                    :class="
                        cn(
                            'inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-[0.875rem] font-medium transition-colors',
                            onlyCart
                                ? 'border-destructive bg-critical-subtle text-destructive-text'
                                : 'border-transparent bg-critical-subtle text-destructive-text hover:opacity-90',
                        )
                    "
                    title="Bài sắp đăng mà giỏ đã hết hàng hoặc không còn trong shop. Bấm để chỉ xem các bài này."
                    data-testid="fork-auto-only-cart"
                    @click="onlyCart = !onlyCart"
                >
                    <IconShoppingCartOff class="size-4" />
                    <b class="tabular-nums">{{ cartCount }}</b> lỗi giỏ
                </button>
                <SourceFilter v-model="source" />
                <button
                    type="button"
                    class="inline-flex h-8 items-center gap-1.5 rounded-md border bg-card px-3 text-[0.875rem] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                    title="Đổi chỗ giờ các bài chưa gửi lên TikTok để hai bài liền nhau khác sản phẩm (có xem trước và hoàn tác)"
                    data-testid="fork-auto-mix-open"
                    @click="mixOpen = true"
                >
                    <IconArrowsShuffle class="size-4" /> Trộn sản phẩm
                </button>
                <button
                    type="button"
                    class="inline-flex h-8 items-center gap-1.5 rounded-md border bg-card px-3 text-[0.875rem] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                    title="Video anh đã xoá: khôi phục được trong 30 ngày"
                    data-testid="fork-auto-trash-open"
                    @click="trashOpen = true"
                >
                    <IconTrash class="size-4" /> Thùng rác
                </button>
            </div>
        </header>

        <!-- Lọc theo kênh -->
        <div
            v-if="multi"
            class="flex shrink-0 flex-wrap items-center gap-1.5 border-b px-5 py-2"
            role="group"
            aria-label="Lọc theo kênh"
            data-testid="fork-auto-channel-filter"
        >
            <button
                type="button"
                :aria-pressed="channel === 'all'"
                :class="
                    cn(
                        'inline-flex h-7 items-center rounded-md border px-3 text-[0.875rem] font-medium transition-colors',
                        channel === 'all'
                            ? 'border-foreground/30 bg-foreground/5 text-foreground'
                            : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                    )
                "
                @click="channel = 'all'"
            >
                Tất cả kênh
            </button>
            <button
                v-for="(a, i) in accounts"
                :key="a.id"
                type="button"
                :aria-pressed="channel === a.id"
                :class="
                    cn(
                        'inline-flex h-7 max-w-56 items-center gap-1.5 rounded-md border px-3 text-[0.875rem] font-medium transition-colors',
                        channel === a.id
                            ? 'border-foreground/30 bg-foreground/5 text-foreground'
                            : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                    )
                "
                :data-testid="`fork-auto-channel-${a.id}`"
                @click="channel = channel === a.id ? 'all' : a.id"
            >
                <i
                    :class="
                        cn('size-2 shrink-0 rounded-full', channelColor(i).dot)
                    "
                    aria-hidden="true"
                />
                <span class="truncate"
                    >@{{ a.username ?? a.display_name }}</span
                >
            </button>
        </div>

        <div v-if="notes.length" class="flex shrink-0 flex-col gap-2 px-5 pt-3">
            <div
                v-for="n in notes"
                :key="n.id"
                :class="
                    cn(
                        'rounded-lg border border-l-2 border-l-warning bg-muted/50 px-4 py-2 text-[0.875rem] text-foreground',
                    )
                "
            >
                <IconShoppingCartOff
                    v-if="n.cart"
                    class="mr-1 inline size-4 align-[-3px] text-warning"
                />
                <b v-if="multi">@{{ n.username }}: </b>{{ n.note }}
                <Link
                    v-if="n.cart"
                    href="/auto/gio-hang"
                    class="ml-1 font-medium underline underline-offset-2"
                    >Mở Giỏ hàng</Link
                >
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
                                        'text-[0.9375rem] font-semibold',
                                        d.isToday
                                            ? 'text-primary-text'
                                            : 'text-foreground',
                                    )
                                "
                                >{{ d.label }}</span
                            >
                            <span
                                class="text-[0.8438rem] text-muted-foreground tabular-nums"
                                >{{ d.date }}</span
                            >
                        </span>
                        <span class="flex items-baseline gap-1">
                            <span
                                class="font-heading text-[1.5rem] leading-none font-medium tabular-nums"
                                >{{ d.real + d.planned }}</span
                            >
                            <span class="text-[0.8125rem] text-muted-foreground"
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
                        class="mt-1.5 flex flex-wrap gap-x-2.5 text-[0.8125rem] text-muted-foreground tabular-nums"
                    >
                        <span v-if="d.posted">{{ d.posted }} đã đăng</span>
                        <span v-if="d.onTikTok"
                            >{{ d.onTikTok }} đã hẹn TikTok</span
                        >
                        <span v-if="d.inApp"
                            >{{ d.inApp }} chưa lên TikTok</span
                        >
                        <span v-if="d.planned">{{ d.planned }} dự kiến</span>
                        <span v-if="d.failed" class="text-destructive-text"
                            >{{ d.failed }} lỗi</span
                        >
                        <span v-if="d.empty" class="text-warning"
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
                    :filtered="filtered"
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
                    @dragover="
                        dragging && ($event.preventDefault(), (picked = d.key))
                    "
                >
                    <span
                        v-if="current?.key === d.key"
                        class="absolute inset-x-0 bottom-0 h-0.5 bg-primary"
                        aria-hidden="true"
                    />
                    <span
                        class="flex items-baseline justify-between gap-2 text-[0.875rem]"
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
                            class="font-heading text-[1.625rem] leading-none font-medium tabular-nums"
                            >{{ d.real + d.planned }}</span
                        >
                        <span class="text-[0.8438rem] text-muted-foreground"
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
                :filtered="filtered"
                class="min-h-0 flex-1 overflow-y-auto overscroll-contain"
            />
        </template>

        <TrashDialog v-model:open="trashOpen" />
        <MixDialog
            v-model:open="mixOpen"
            :accounts="accounts.filter((a) => a.enabled)"
            :account-id="channel !== 'all' ? channel : null"
            :reload-only="['lich']"
        />
        <DirectWindowDialog
            v-if="directWindow"
            v-model:open="directOpen"
            :value="directWindow"
            :accounts="accounts"
        />
    </section>
</template>

<script setup lang="ts">
// Lịch hẹn các ngày tới dạng "nhật ký ngày": chọn ngày, xem từng giờ với ảnh bìa video, sản phẩm, caption và trạng thái.
// Màn rộng chia 2 cột để không bị trống bên phải. Bài thật nét liền; giờ dự kiến (chạy thử bộ xếp lịch) nét đứt.
import {
    IconCalendarOff,
    IconExternalLink,
    IconPlayerPlayFilled,
    IconShoppingCart,
} from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import type { AccountRow, Lich, LichItem } from '@/components/fork/auto/types';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import { statusOf, toneClasses } from '@/components/fork/shared/status';
import StatusChip from '@/components/fork/shared/StatusChip.vue';
import { openVideo } from '@/components/fork/viewer';
import VideoThumb from '@/components/fork/VideoThumb.vue';
import { Avatar } from '@/components/ui/avatar';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    lich: Lich;
    accounts: AccountRow[];
}>();

const channel = ref<string | null>(null);
const picked = ref<string | null>(null);

interface Entry extends LichItem {
    channelId: string;
    username: string;
}

const entries = computed<Entry[]>(() => {
    const out: Entry[] = [];

    for (const a of props.accounts) {
        if (channel.value && channel.value !== a.id) {
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

    return out.sort((x, y) => x.at.localeCompare(y.at));
});

const notes = computed(() =>
    props.accounts
        .filter((a) => !channel.value || channel.value === a.id)
        .map((a) => ({
            id: a.id,
            username: a.username ?? '—',
            note: props.lich.channels[a.id]?.note ?? null,
        }))
        .filter((n) => n.note),
);

const todayKey = dayjs().format('YYYY-MM-DD');

const days = computed(() =>
    props.lich.days.map((d, i) => {
        const list = entries.value.filter((e) => e.day === d.key);
        const real = list.filter((e) => e.state !== 'projected').length;
        const planned = list.filter(
            (e) => e.state === 'projected' && e.video_id,
        ).length;
        const empty = list.length - real - planned;

        return {
            ...d,
            label: d.label || (i === 0 ? 'Hôm nay' : d.date),
            list,
            real,
            planned,
            empty,
        };
    }),
);

const current = computed(
    () => days.value.find((d) => d.key === picked.value) ?? days.value[0],
);

type Row =
    | { kind: 'now'; key: string; at: string }
    | { kind: 'item'; key: string; e: Entry };

const rows = computed<Row[]>(() => {
    const d = current.value;

    if (!d) {
        return [];
    }

    const out: Row[] = [];
    const now = dayjs();
    let placed = d.key !== todayKey;

    for (const e of d.list) {
        if (!placed && dayjs(e.at).isAfter(now)) {
            out.push({ kind: 'now', key: 'now', at: now.format('HH:mm') });
            placed = true;
        }

        out.push({
            kind: 'item',
            key: `${e.channelId}-${e.state}-${e.id ?? e.at}`,
            e,
        });
    }

    if (!placed && d.list.length) {
        out.push({ kind: 'now', key: 'now', at: now.format('HH:mm') });
    }

    return out;
});

const fmtHour = (iso: string) => dayjs(iso).format('HH:mm');
const videoId = (e: Entry) => e.id ?? e.video_id ?? null;
const isLate = (e: Entry) =>
    !['projected', 'posted', 'failed', 'tiktok_scheduled'].includes(e.state) &&
    dayjs(e.at).isBefore(dayjs());
const isEmptySlot = (e: Entry) => e.state === 'projected' && !e.video_id;

// ←/→ trong khung xem chạy theo đúng thứ tự các video của ngày đang xem.
const dayIds = computed(() =>
    (current.value?.list ?? [])
        .map((e) => videoId(e as Entry))
        .filter((x): x is number => x !== null),
);

const open = (e: Entry) => {
    const id = videoId(e);

    if (id !== null) {
        openVideo(dayIds.value, id);
    }
};

const dayTotal = (d: { real: number; planned: number; empty: number }) =>
    d.real + d.planned + d.empty;
const dayCount = (d: { real: number; planned: number }) => d.real + d.planned;
</script>

<template>
    <section class="flex flex-col gap-4" data-testid="fork-auto-lich">
        <SectionHeading
            :title="`Lịch ${lich.days.length} ngày tới`"
            description="Mỗi thẻ là một giờ đăng: bài đã hẹn thật nét liền, giờ dự kiến nét đứt. Bấm vào thẻ để xem video."
        >
            <div v-if="accounts.length > 1" class="flex flex-wrap gap-1.5">
                <button
                    type="button"
                    :class="
                        cn(
                            'inline-flex h-10 items-center rounded-full border px-4 text-base transition',
                            channel === null
                                ? 'border-primary bg-primary text-primary-foreground'
                                : 'bg-card hover:border-foreground/30',
                        )
                    "
                    @click="channel = null"
                >
                    Tất cả kênh
                </button>
                <button
                    v-for="a in accounts"
                    :key="a.id"
                    type="button"
                    :class="
                        cn(
                            'inline-flex h-10 items-center gap-2 rounded-full border pr-4 pl-1 text-base transition',
                            channel === a.id
                                ? 'border-primary bg-primary text-primary-foreground'
                                : 'bg-card hover:border-foreground/30',
                        )
                    "
                    @click="channel = a.id"
                >
                    <Avatar
                        :src="a.avatar_url"
                        :name="a.username ?? '?'"
                        class="size-8"
                        fallback-class="bg-secondary text-[0.7rem] font-bold text-foreground"
                    />
                    @{{ a.username }}
                </button>
            </div>
        </SectionHeading>

        <div
            v-for="n in notes"
            :key="n.id"
            :class="
                cn(
                    'flex items-start gap-2 rounded-xl border p-4 text-base',
                    toneClasses.warn.box,
                )
            "
        >
            <span
                ><b>@{{ n.username }}</b
                >: {{ n.note }}</span
            >
        </div>

        <!-- Chọn ngày: dính đầu khi cuộn -->
        <div
            class="sticky top-0 z-10 -mx-4 bg-background/85 px-4 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/70 sm:mx-0 sm:px-0"
        >
            <div class="flex gap-2 overflow-x-auto pb-0.5" role="tablist">
                <button
                    v-for="d in days"
                    :key="d.key"
                    type="button"
                    role="tab"
                    :aria-selected="current?.key === d.key"
                    :class="
                        cn(
                            'flex min-w-[12rem] shrink-0 flex-col gap-2.5 rounded-2xl border bg-card p-4 text-left transition',
                            'hover:border-foreground/30 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                            current?.key === d.key &&
                                'border-primary ring-1 ring-primary',
                        )
                    "
                    :data-testid="`fork-auto-day-tab-${d.key}`"
                    @click="picked = d.key"
                >
                    <span class="flex items-baseline justify-between gap-2">
                        <span class="text-base font-semibold">{{ d.label }}</span>
                        <span class="text-sm text-muted-foreground">{{
                            d.date
                        }}</span>
                    </span>
                    <span class="flex items-baseline gap-1.5">
                        <span class="font-heading text-4xl leading-none font-semibold tabular-nums">{{
                            dayCount(d)
                        }}</span>
                        <span class="text-sm text-muted-foreground">bài</span>
                    </span>
                    <span
                        class="flex h-2 overflow-hidden rounded-full bg-muted"
                    >
                        <span
                            :class="toneClasses.info.bar"
                            :style="{
                                width: `${(d.real / (dayTotal(d) || 1)) * 100}%`,
                            }"
                        />
                        <span
                            class="bg-muted-foreground/30"
                            :style="{
                                width: `${(d.planned / (dayTotal(d) || 1)) * 100}%`,
                            }"
                        />
                    </span>
                    <span class="text-sm text-muted-foreground tabular-nums">
                        {{ d.real }} đã hẹn · {{ d.planned }} dự kiến
                    </span>
                </button>
            </div>
        </div>

        <div
            v-if="current"
            :data-testid="`fork-auto-day-${current.key}`"
            class="flex flex-col"
        >
            <EmptyState
                v-if="!current.list.length"
                :icon="IconCalendarOff"
                title="Chưa có giờ nào trong ngày này"
                description="Kênh đang tắt, đã hết hạn mức hoặc ngoài khung giờ đăng. Bật kênh hoặc nới khung giờ ở thẻ kênh phía trên."
            />

            <ol v-else class="grid gap-x-10 2xl:grid-cols-2">
                <li
                    v-for="r in rows"
                    :key="r.key"
                    :class="
                        cn(
                            'flex gap-3',
                            r.kind === 'now' && '2xl:col-span-2',
                        )
                    "
                >
                    <!-- Mốc "bây giờ" -->
                    <template v-if="r.kind === 'now'">
                        <div
                            class="flex w-16 shrink-0 items-center justify-end text-sm font-semibold text-primary tabular-nums"
                        >
                            {{ r.at }}
                        </div>
                        <div class="flex flex-1 items-center gap-2 pb-3">
                            <span class="size-2.5 rounded-full bg-primary" />
                            <span class="h-px flex-1 bg-primary/40" />
                            <span class="text-sm font-medium text-primary"
                                >Bây giờ</span
                            >
                        </div>
                    </template>

                    <template v-else>
                        <div
                            class="w-16 shrink-0 pt-4 text-right text-lg font-semibold tabular-nums"
                            :class="
                                r.e.state === 'projected'
                                    ? 'text-muted-foreground'
                                    : ''
                            "
                        >
                            {{ fmtHour(r.e.at) }}
                        </div>

                        <div
                            class="relative flex w-4 shrink-0 flex-col items-center"
                        >
                            <span
                                :class="
                                    cn(
                                        'mt-6 size-3 shrink-0 rounded-full ring-4 ring-background',
                                        toneClasses[statusOf(r.e.state).tone]
                                            .dot,
                                    )
                                "
                            />
                            <span class="w-px flex-1 bg-border" />
                        </div>

                        <div
                            :role="isEmptySlot(r.e) ? undefined : 'button'"
                            :tabindex="isEmptySlot(r.e) ? undefined : 0"
                            :class="
                                cn(
                                    'group mb-4 flex min-w-0 flex-1 gap-4 rounded-2xl border bg-card p-3.5 text-left shadow-xs transition',
                                    !isEmptySlot(r.e) &&
                                        'cursor-pointer hover:-translate-y-px hover:border-foreground/25 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                                    r.e.state === 'projected' &&
                                        'border-dashed bg-muted/20 shadow-none',
                                    isEmptySlot(r.e) && 'opacity-60',
                                    r.e.state === 'failed' &&
                                        toneClasses.danger.box,
                                    isLate(r.e) && 'border-amber-300',
                                )
                            "
                            @click="!isEmptySlot(r.e) && open(r.e)"
                            @keydown.enter.self.prevent="
                                !isEmptySlot(r.e) && open(r.e)
                            "
                        >
                            <VideoThumb
                                :id="videoId(r.e)"
                                class="h-[144px] w-[81px] rounded-xl"
                            />

                            <div
                                class="flex min-w-0 flex-1 flex-col gap-1.5 text-base"
                            >
                                <template v-if="isEmptySlot(r.e)">
                                    <div class="font-medium">
                                        Chưa có video cho giờ này
                                    </div>
                                    <div class="text-sm text-muted-foreground">
                                        {{
                                            r.e.empty_reason ===
                                            'chưa chọn giỏ hàng'
                                                ? 'Chưa chọn giỏ hàng cho sản phẩm nào, nên chưa xếp được video.'
                                                : 'Hết video có giỏ: video còn lại đang chờ chọn giỏ hoặc kho đã hết.'
                                        }}
                                    </div>
                                </template>
                                <template v-else>
                                    <div
                                        class="flex min-w-0 items-center gap-2"
                                    >
                                        <ProductThumb
                                            :src="r.e.product_image"
                                            class="size-9"
                                        />
                                        <span class="truncate font-medium">{{
                                            r.e.product_label ??
                                            r.e.product_code ??
                                            '—'
                                        }}</span>
                                    </div>
                                    <div
                                        v-if="r.e.cart_name"
                                        class="flex items-center gap-1.5 truncate text-sm text-muted-foreground"
                                    >
                                        <IconShoppingCart
                                            class="size-4 shrink-0"
                                        />
                                        <span class="truncate">{{
                                            r.e.cart_name
                                        }}</span>
                                    </div>
                                    <p
                                        v-if="r.e.caption"
                                        class="line-clamp-2 text-sm leading-snug text-muted-foreground"
                                    >
                                        {{ r.e.caption }}
                                    </p>
                                    <div
                                        v-if="r.e.error"
                                        class="line-clamp-2 text-sm"
                                        :class="toneClasses.danger.text"
                                        :title="r.e.error"
                                    >
                                        {{ r.e.error }}
                                    </div>
                                </template>
                                <div
                                    v-if="accounts.length > 1"
                                    class="text-sm text-muted-foreground"
                                >
                                    @{{ r.e.username }}
                                </div>
                                <div
                                    v-if="!isEmptySlot(r.e)"
                                    class="mt-auto inline-flex items-center gap-1.5 pt-1 text-sm font-medium text-primary"
                                >
                                    <IconPlayerPlayFilled class="size-4" />
                                    Bấm để xem video
                                </div>
                            </div>

                            <div
                                class="flex shrink-0 flex-col items-end justify-between gap-1.5"
                            >
                                <StatusChip :status="r.e.state" />
                                <a
                                    v-if="r.e.link"
                                    :href="r.e.link"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                                    @click.stop
                                >
                                    TikTok
                                    <IconExternalLink class="size-4" />
                                </a>
                            </div>
                        </div>
                    </template>
                </li>
            </ol>
        </div>
    </section>
</template>

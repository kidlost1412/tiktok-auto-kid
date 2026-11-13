<script setup lang="ts">
// Lịch đăng dạng bảng gọn: chọn ngày ở đầu thẻ, mỗi bài là một dòng (giờ · ảnh bìa · sản phẩm + caption · trạng thái).
// Hôm nay: các bài đã đăng gấp lại thành một dòng để mắt đi thẳng tới bài sắp tới. Giờ dự kiến nét đứt.
import {
    IconCalendarOff,
    IconChevronDown,
    IconExternalLink,
    IconShoppingCart,
} from '@tabler/icons-vue';
import { computed, ref, watch } from 'vue';

import type { AccountRow, Lich, LichItem } from '@/components/fork/auto/types';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import { cardCls, statusOf, toneClasses } from '@/components/fork/shared/status';
import StatusChip from '@/components/fork/shared/StatusChip.vue';
import { openVideo } from '@/components/fork/viewer';
import { NativeSelect } from '@/components/ui/native-select';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    lich: Lich;
    accounts: AccountRow[];
}>();

interface Entry extends LichItem {
    channelId: string;
    username: string;
}

const channel = ref<string>('all');
const picked = ref<string | null>(null);
const showDone = ref(false);

const entries = computed<Entry[]>(() => {
    const out: Entry[] = [];

    for (const a of props.accounts) {
        if (channel.value !== 'all' && channel.value !== a.id) {
            continue;
        }

        for (const item of props.lich.channels[a.id]?.items ?? []) {
            out.push({ ...item, channelId: a.id, username: a.username ?? a.display_name ?? '—' });
        }
    }

    return out.sort((x, y) => dayjs(x.at).valueOf() - dayjs(y.at).valueOf());
});

const notes = computed(() =>
    props.accounts
        .filter((a) => channel.value === 'all' || channel.value === a.id)
        .map((a) => ({ id: a.id, username: a.username ?? '—', note: props.lich.channels[a.id]?.note ?? null }))
        .filter((n) => n.note),
);

const isEmptySlot = (e: Entry) => e.state === 'projected' && !e.video_id;

const days = computed(() =>
    props.lich.days.map((d, i) => {
        const list = entries.value.filter((e) => e.day === d.key);
        const real = list.filter((e) => e.state !== 'projected').length;
        const planned = list.filter((e) => e.state === 'projected' && e.video_id).length;

        return { ...d, label: d.label || (i === 0 ? 'Hôm nay' : d.date), list, real, planned, empty: list.length - real - planned };
    }),
);

const current = computed(() => days.value.find((d) => d.key === picked.value) ?? days.value[0]);

watch(picked, () => {
    showDone.value = false;
});

const isToday = computed(() => current.value?.key === dayjs().format('YYYY-MM-DD'));

// Hôm nay: bài đã qua giờ & đã xong (đăng / hẹn trên TikTok đã tới giờ) gấp lại.
const DONE = ['posted'];
const done = computed(() => (isToday.value ? (current.value?.list ?? []).filter((e) => DONE.includes(e.state)) : []));
const rest = computed(() => (current.value?.list ?? []).filter((e) => !done.value.includes(e)));

const nowIndex = computed(() => {
    if (!isToday.value) {
        return -1;
    }

    const now = dayjs();
    const i = rest.value.findIndex((e) => dayjs(e.at).isAfter(now));

    return i === -1 ? rest.value.length : i;
});

const videoId = (e: Entry) => e.id ?? e.video_id ?? null;
const isLate = (e: Entry) =>
    !['projected', 'posted', 'failed', 'tiktok_scheduled'].includes(e.state) && dayjs(e.at).isBefore(dayjs().subtract(2, 'minute'));

const dayIds = computed(() =>
    (current.value?.list ?? []).map((e) => videoId(e as Entry)).filter((x): x is number => x !== null && x !== undefined),
);

const open = (e: Entry) => {
    const id = videoId(e);

    if (id !== null && id !== undefined) {
        openVideo(dayIds.value, id);
    }
};

const multi = computed(() => props.accounts.length > 1);
const pct = (n: number, d: { real: number; planned: number; empty: number }) => `${(n / (d.real + d.planned + d.empty || 1)) * 100}%`;
</script>

<template>
    <section :class="cn(cardCls, 'flex min-w-0 flex-col overflow-hidden')" data-testid="fork-auto-lich">
        <header class="flex flex-wrap items-center justify-between gap-3 border-b px-5 pt-4 pb-3">
            <div>
                <h2 class="font-heading text-[17px] font-semibold tracking-[-0.015em]">Lịch đăng</h2>
                <p class="text-[12.5px] text-muted-foreground">Bấm một dòng để xem video. Nét đứt là giờ dự kiến, chưa hẹn lên TikTok.</p>
            </div>
            <NativeSelect v-if="multi" v-model="channel" class="h-9 w-48" aria-label="Lọc theo kênh">
                <option value="all">Tất cả kênh</option>
                <option v-for="a in accounts" :key="a.id" :value="a.id">@{{ a.username ?? a.display_name }}</option>
            </NativeSelect>
        </header>

        <!-- Chọn ngày -->
        <div class="grid grid-cols-3 gap-px border-b bg-border" role="tablist" aria-label="Chọn ngày">
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
                        current?.key === d.key && 'bg-primary/[0.04] dark:bg-primary/[0.08]',
                    )
                "
                @click="picked = d.key"
            >
                <span
                    v-if="current?.key === d.key"
                    class="absolute inset-x-0 bottom-0 h-0.5 bg-primary"
                    aria-hidden="true"
                />
                <span class="flex items-baseline justify-between gap-2 text-[13px]">
                    <span :class="cn('font-semibold', current?.key === d.key ? 'text-foreground' : 'text-muted-foreground')">{{ d.label }}</span>
                    <span class="text-muted-foreground tabular-nums">{{ d.date }}</span>
                </span>
                <span class="flex items-baseline gap-1">
                    <span class="font-heading text-[22px] leading-none font-[650] tracking-tight tabular-nums">{{ d.real + d.planned }}</span>
                    <span class="text-[12.5px] text-muted-foreground">bài<template v-if="d.planned"> · {{ d.planned }} dự kiến</template></span>
                </span>
                <span class="flex h-1 overflow-hidden rounded-full bg-muted">
                    <span class="bg-primary" :style="{ width: pct(d.real, d) }" />
                    <span class="bg-muted-foreground/30" :style="{ width: pct(d.planned, d) }" />
                </span>
            </button>
        </div>

        <div
            v-for="n in notes"
            :key="n.id"
            :class="cn('mx-5 mt-4 rounded-lg border px-3.5 py-2.5 text-[13px]', toneClasses.warn.box)"
        >
            <b v-if="multi">@{{ n.username }}: </b>{{ n.note }}
        </div>

        <div v-if="current" :data-testid="`fork-auto-day-${current.key}`" class="flex flex-col py-2">
            <div v-if="!current.list.length" class="flex flex-col items-center gap-2 px-6 py-14 text-center">
                <IconCalendarOff class="size-8 text-muted-foreground/60" />
                <div class="font-medium">Chưa có giờ đăng nào trong ngày này</div>
                <p class="max-w-sm text-[13px] text-muted-foreground">Kênh đang tắt, đã đủ hạn mức hoặc ngoài khung giờ. Bật kênh hoặc nới khung giờ bằng nút “Chỉnh” ở thẻ kênh.</p>
            </div>

            <!-- Đã đăng hôm nay (gấp lại) -->
            <template v-if="done.length">
                <button
                    type="button"
                    class="mx-3 flex items-center gap-3 rounded-lg px-2 py-2 text-left text-[13px] transition-colors hover:bg-accent/50"
                    :aria-expanded="showDone"
                    @click="showDone = !showDone"
                >
                    <span class="flex w-[52px] justify-end">
                        <span :class="cn('flex size-6 items-center justify-center rounded-full', toneClasses.success.chip)">
                            <IconChevronDown :class="cn('size-4 transition-transform', showDone && 'rotate-180')" />
                        </span>
                    </span>
                    <span>
                        <b class="font-semibold">{{ done.length }} bài đã đăng</b>
                        <span class="text-muted-foreground"> từ {{ dayjs(done[0].at).format('HH:mm') }} đến {{ dayjs(done[done.length - 1].at).format('HH:mm') }}</span>
                    </span>
                    <span class="ml-auto text-primary-text">{{ showDone ? 'Ẩn' : 'Xem' }}</span>
                </button>
            </template>

            <ol class="flex flex-col">
                <template v-for="(e, i) in [...(showDone ? done : []), ...rest]" :key="`${e.channelId}-${e.state}-${e.id ?? e.video_id ?? e.at}`">
                    <li
                        v-if="isToday && i === nowIndex + (showDone ? done.length : 0)"
                        class="mx-5 flex items-center gap-3 py-1.5"
                        aria-label="Bây giờ"
                    >
                        <span class="w-[52px] text-right text-[12px] font-semibold text-primary-text tabular-nums">{{ dayjs().format('HH:mm') }}</span>
                        <span class="size-2 rounded-full bg-primary" />
                        <span class="h-px flex-1 bg-primary/40" />
                        <span class="text-[12px] font-medium text-primary-text">Bây giờ</span>
                    </li>
                    <li>
                        <div
                            v-if="isEmptySlot(e)"
                            class="mx-3 grid grid-cols-[52px_minmax(0,1fr)] items-center gap-3 rounded-lg px-2 py-2 text-[13px] text-muted-foreground"
                        >
                            <span class="text-right tabular-nums">{{ dayjs(e.at).format('HH:mm') }}</span>
                            <span class="truncate rounded-md border border-dashed px-3 py-1.5">
                                Giờ trống —
                                {{ e.empty_reason === 'chưa chọn giỏ hàng' ? 'chưa chọn giỏ hàng cho sản phẩm nào' : 'hết video đã có giỏ' }}
                            </span>
                        </div>
                        <div
                            v-else
                            role="button"
                            tabindex="0"
                            :class="
                                cn(
                                    'group mx-3 grid cursor-pointer grid-cols-[52px_36px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-accent/50 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring',
                                    e.state === 'failed' && 'bg-red-50/60 dark:bg-red-950/20',
                                )
                            "
                            @click="open(e)"
                            @keydown.enter.self.prevent="open(e)"
                            @keydown.space.self.prevent="open(e)"
                        >
                            <span
                                :class="
                                    cn(
                                        'text-right text-[15px] font-semibold tabular-nums',
                                        e.state === 'projected' && 'font-medium text-muted-foreground',
                                        e.state === 'posted' && 'text-muted-foreground',
                                    )
                                "
                                >{{ dayjs(e.at).format('HH:mm') }}</span
                            >
                            <CoverThumb
                                :id="videoId(e)"
                                :fallback="e.product_image"
                                :class="cn('h-[64px] w-[36px] rounded-md', e.state === 'projected' && 'opacity-70')"
                            />
                            <div class="min-w-0">
                                <div class="flex min-w-0 items-center gap-2">
                                    <span class="truncate text-[14px] font-medium">{{ e.product_label ?? e.product_code ?? '—' }}</span>
                                    <span v-if="multi" class="shrink-0 text-[12px] text-muted-foreground">@{{ e.username }}</span>
                                </div>
                                <p v-if="e.error" :class="cn('truncate text-[12.5px]', toneClasses.danger.text)" :title="e.error">{{ e.error }}</p>
                                <p v-else-if="e.caption" class="truncate text-[12.5px] text-muted-foreground" :title="e.caption">{{ e.caption }}</p>
                                <div v-if="e.cart_name" class="mt-0.5 flex min-w-0 items-center gap-1 text-[12px] text-muted-foreground/90">
                                    <IconShoppingCart class="size-3.5 shrink-0" />
                                    <span class="truncate">{{ e.cart_name }}</span>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <span
                                    v-if="isLate(e)"
                                    :class="cn('hidden rounded-full px-2 py-0.5 text-[12px] font-medium sm:inline', toneClasses.warn.chip)"
                                    title="Đã quá giờ hẹn mà chưa đăng xong"
                                    >Trễ</span
                                >
                                <StatusChip :status="e.state" class="h-6 px-2 text-[12px] max-sm:hidden" />
                                <span :class="cn('size-2 rounded-full sm:hidden', toneClasses[statusOf(e.state).tone].dot)" />
                                <a
                                    v-if="e.link"
                                    :href="e.link"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
                                    title="Mở trên TikTok"
                                    aria-label="Mở trên TikTok"
                                    @click.stop
                                >
                                    <IconExternalLink class="size-4" />
                                </a>
                            </div>
                        </div>
                    </li>
                </template>
                <li v-if="isToday && rest.length && nowIndex === rest.length" class="mx-5 flex items-center gap-3 py-1.5">
                    <span class="w-[52px] text-right text-[12px] font-semibold text-primary-text tabular-nums">{{ dayjs().format('HH:mm') }}</span>
                    <span class="size-2 rounded-full bg-primary" />
                    <span class="h-px flex-1 bg-primary/40" />
                    <span class="text-[12px] font-medium text-primary-text">Bây giờ · hết bài trong ngày</span>
                </li>
            </ol>
        </div>
    </section>
</template>

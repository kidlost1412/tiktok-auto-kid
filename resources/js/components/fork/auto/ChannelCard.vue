<script setup lang="ts">
// Thẻ một kênh: bật/tắt, tiến độ hôm nay, khung giờ, hạn mức và "Hẹn trước" sửa ngay tại chỗ.
import { Link, router } from '@inertiajs/vue3';
import {
    IconCalendarClock,
    IconChevronDown,
    IconPlayerPause,
    IconShoppingCart,
    IconSparkles,
} from '@tabler/icons-vue';
import { computed, reactive, ref } from 'vue';

import type { AccountRow, HealthChannel, LichChannel } from '@/components/fork/auto/types';
import { cardCls, fmtNum, toneClasses } from '@/components/fork/shared/status';
import dayjs from '@/dayjs';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Progress } from '@/components/ui/progress';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

const props = defineProps<{
    account: AccountRow;
    avatarUrl: string | null;
    today: LichChannel['today'] | undefined;
    chrome?: HealthChannel;
    blockedCount: number;
}>();

const chromeStatus = computed(() => {
    const c = props.chrome;

    if (!c || !c.chrome_enabled) {
        return { text: 'Chrome: chưa bật', tone: 'danger' as const };
    }

    if (c.chrome_online) {
        return { text: 'Chrome: đang kết nối', tone: 'success' as const };
    }

    return {
        text: c.chrome_last_seen
            ? `Chrome: mất kết nối từ ${dayjs(c.chrome_last_seen).format('HH:mm DD/MM')}`
            : 'Chrome: chưa thấy tiện ích',
        tone: 'warn' as const,
    };
});

const busy = ref(false);
const opts = {
    preserveScroll: true,
    onFinish: () => {
        busy.value = false;
    },
};

type Draft = Partial<
    Pick<
        AccountRow,
        | 'daily_cap'
        | 'window_start'
        | 'window_end'
        | 'mode'
        | 'schedule_ahead_days'
    >
>;
const draft = reactive<Draft>({});

const field = <K extends keyof Draft>(key: K) =>
    (draft[key] ??
        props.account[key] ??
        (key === 'schedule_ahead_days' ? 3 : undefined)) as AccountRow[K];
const dirty = computed(() => Object.keys(draft).length > 0);
const aheadDays = computed(() => Number(field('schedule_ahead_days') ?? 3));

const hourOptions = Array.from({ length: 24 }, (_, i) => i);
const endOptions = hourOptions.slice(1).concat(24);
const aheadOptions = Array.from({ length: 9 }, (_, i) => i + 1);

const save = () => {
    busy.value = true;
    router.patch(
        `/auto/accounts/${props.account.id}`,
        { ...draft },
        {
            ...opts,
            onSuccess: () => {
                Object.keys(draft).forEach(
                    (k) => delete draft[k as keyof Draft],
                );
            },
        },
    );
};

const reset = () => {
    Object.keys(draft).forEach((k) => delete draft[k as keyof Draft]);
};

const toggle = (enabled: boolean) => {
    busy.value = true;
    router.patch(`/auto/accounts/${props.account.id}`, { enabled }, opts);
};

const pause = () => {
    busy.value = true;
    router.post(`/auto/accounts/${props.account.id}/pause`, {}, opts);
};

const applyHours = () => {
    busy.value = true;
    router.post(`/auto/accounts/${props.account.id}/apply-hours`, {}, opts);
};

const cap = computed(() => props.today?.cap ?? props.account.daily_cap);
const planned = computed(() => props.today?.planned ?? 0);
const percent = computed(() =>
    Math.min(100, Math.round((planned.value / (cap.value || 1)) * 100)),
);

const name = computed(
    () => `@${props.account.username ?? props.account.display_name ?? '—'}`,
);

const recOpen = ref(false);
</script>

<template>
    <div
        :class="
            cn(
                cardCls,
                'flex flex-col gap-5 p-6 transition-colors',
                !account.enabled && 'bg-muted/30',
            )
        "
        :data-testid="`fork-auto-account-${account.id}`"
    >
        <div class="flex items-center gap-4">
            <div class="relative">
                <Avatar class="size-16">
                    <AvatarImage v-if="avatarUrl" :src="avatarUrl" alt="" />
                    <AvatarFallback>{{
                        (account.username ?? '?').slice(0, 1).toUpperCase()
                    }}</AvatarFallback>
                </Avatar>
                <span
                    :class="
                        cn(
                            'absolute -right-0.5 -bottom-0.5 size-4.5 rounded-full border-2 border-card',
                            toneClasses[account.enabled ? 'success' : 'neutral']
                                .dot,
                        )
                    "
                />
            </div>
            <div class="min-w-0 flex-1">
                <div class="truncate text-lg font-semibold tracking-tight">{{ name }}</div>
                <div
                    v-if="account.display_name"
                    class="truncate text-sm text-muted-foreground"
                >
                    {{ account.display_name }}
                </div>
                <div
                    v-if="!avatarUrl"
                    class="truncate text-xs text-muted-foreground"
                    title="Tiện ích Chrome tự lấy ảnh đại diện khi bạn mở TikTok Studio hoặc tiktok.com trong Chrome đã ghép (cần tiện ích bản 1.4.5 trở lên)"
                >
                    Chưa có ảnh đại diện — mở TikTok Studio trong Chrome đã ghép, ảnh sẽ tự hiện (nhớ tải lại tiện ích)
                </div>
            </div>
            <div class="flex flex-col items-end gap-1">
                <Switch
                    :model-value="account.enabled"
                    :disabled="busy"
                    :aria-label="`Bật tự động đăng cho ${name}`"
                    @update:model-value="(v: boolean) => toggle(v)"
                />
                <span
                    :class="
                        cn(
                            'text-sm font-medium',
                            account.enabled
                                ? toneClasses.success.text
                                : 'text-muted-foreground',
                        )
                    "
                    >{{ account.enabled ? 'Đang bật' : 'Đang tắt' }}</span
                >
            </div>
        </div>

        <div class="flex flex-wrap gap-1.5">
            <Link
                :href="'/settings#chrome'"
                :class="
                    cn(
                        'rounded-full px-3 py-1 text-sm font-medium hover:underline',
                        toneClasses[chromeStatus.tone].chip,
                    )
                "
                >{{ chromeStatus.text }}</Link
            >
            <span
                v-if="account.paused_reason"
                :class="
                    cn(
                        'rounded-full px-3 py-1 text-sm font-medium',
                        toneClasses.warn.chip,
                    )
                "
                >Tạm dừng: {{ account.paused_reason }}</span
            >
            <Link
                v-if="blockedCount > 0"
                :href="`/auto/gio-hang?kenh=${account.id}`"
                :class="
                    cn(
                        'rounded-full px-3 py-1 text-sm font-medium hover:underline',
                        toneClasses.warn.chip,
                    )
                "
                >{{ blockedCount }} video đang chờ giỏ</Link
            >
        </div>

        <div class="flex flex-col gap-2">
            <div class="flex items-baseline justify-between">
                <span class="text-sm font-medium text-muted-foreground">Hôm nay</span>
                <span class="font-heading text-2xl font-[650] tracking-tight tabular-nums">
                    {{ planned }}/{{ cap }} bài
                </span>
            </div>
            <Progress :model-value="percent" class="h-2" />
            <div class="text-sm text-muted-foreground">
                Đã đăng {{ today?.posted ?? 0 }}, còn
                {{ Math.max(0, cap - planned) }} chỗ trong ngày.
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <label class="flex flex-col gap-1">
                <span class="text-muted-foreground">Bài / ngày</span>
                <Input
                    type="number"
                    min="1"
                    max="100"
                    class="h-10"
                    :model-value="field('daily_cap')"
                    @update:model-value="draft.daily_cap = Number($event)"
                />
            </label>
            <label class="flex flex-col gap-1">
                <span class="text-muted-foreground">Từ giờ</span>
                <NativeSelect
                    class="w-full"
                    :model-value="field('window_start')"
                    @update:model-value="draft.window_start = Number($event)"
                >
                    <option v-for="h in hourOptions" :key="h" :value="h">
                        {{ h }}h
                    </option>
                </NativeSelect>
            </label>
            <label class="flex flex-col gap-1">
                <span class="text-muted-foreground">Đến giờ</span>
                <NativeSelect
                    class="w-full"
                    :model-value="field('window_end')"
                    @update:model-value="draft.window_end = Number($event)"
                >
                    <option v-for="h in endOptions" :key="h" :value="h">
                        {{ h }}h
                    </option>
                </NativeSelect>
            </label>
            <label class="flex flex-col gap-1">
                <span
                    class="flex items-center gap-1 text-muted-foreground"
                    title="Hẹn lịch trước bao nhiêu ngày"
                >
                    <IconCalendarClock class="size-3.5" />
                    Hẹn trước
                </span>
                <NativeSelect
                    class="w-full"
                    :model-value="aheadDays"
                    :data-testid="`fork-auto-ahead-${account.id}`"
                    @update:model-value="
                        draft.schedule_ahead_days = Number($event)
                    "
                >
                    <option v-for="d in aheadOptions" :key="d" :value="d">
                        {{ d }} ngày
                    </option>
                </NativeSelect>
            </label>
        </div>
        <p
            :class="
                cn(
                    'flex items-start gap-3 rounded-xl border px-4 py-3 text-sm leading-relaxed',
                    toneClasses.info.box,
                )
            "
            data-testid="fork-auto-ahead-hint"
        >
            <IconCalendarClock class="mt-0.5 size-5 shrink-0" />
            <span
                >Có video là app hẹn lịch luôn lên TikTok cho
                <b>{{ aheadDays }} ngày tới</b> — tắt máy vẫn đăng đúng
                giờ.</span
            >
        </p>

        <div class="flex flex-wrap items-center gap-2">
            <Transition
                enter-active-class="transition duration-200"
                enter-from-class="opacity-0 translate-y-1"
                leave-active-class="transition duration-150"
                leave-to-class="opacity-0"
                mode="out-in"
            >
                <div v-if="dirty" key="dirty" class="flex items-center gap-2">
                    <Button size="sm" :disabled="busy" @click="save"
                        >Lưu cài đặt</Button
                    >
                    <Button
                        size="sm"
                        variant="ghost"
                        :disabled="busy"
                        @click="reset"
                        >Bỏ thay đổi</Button
                    >
                </div>
                <Button
                    v-else-if="account.enabled"
                    key="pause"
                    size="sm"
                    variant="outline"
                    :disabled="busy"
                    @click="pause"
                >
                    <IconPlayerPause class="size-4" />
                    Tạm dừng
                </Button>
            </Transition>
            <Link
                :href="`/auto/gio-hang?kenh=${account.id}`"
                class="ml-auto inline-flex items-center gap-1.5 text-sm text-primary-text hover:underline"
                :data-testid="`fork-auto-cart-${account.id}`"
            >
                <IconShoppingCart class="size-4" />
                {{ account.cart.linked_count }} giỏ đã chọn
            </Link>
        </div>

        <div
            class="rounded-xl border bg-muted/50 text-sm"
            data-testid="fork-auto-recommend"
        >
            <button
                type="button"
                class="flex w-full cursor-pointer items-center gap-2 p-4 font-medium select-none"
                :aria-expanded="recOpen"
                @click="recOpen = !recOpen"
            >
                <IconSparkles class="size-4" />
                Chế độ giờ đăng và đề xuất
                <IconChevronDown
                    class="ml-auto size-4 text-muted-foreground transition-transform"
                    :class="{ 'rotate-180': recOpen }"
                />
            </button>
            <div v-show="recOpen" class="flex flex-col gap-4 px-4 pb-4">
                <label class="flex flex-col gap-1 text-sm">
                    <span class="text-muted-foreground">Chế độ</span>
                    <NativeSelect
                        class="w-full"
                        :model-value="field('mode')"
                        @update:model-value="
                            draft.mode =
                                $event === 'optimized' ? 'optimized' : 'explore'
                        "
                    >
                        <option value="explore">
                            Thăm dò (giờ rải đều, ngẫu nhiên)
                        </option>
                        <option value="optimized">
                            Tối ưu (ưu tiên giờ đề xuất)
                        </option>
                    </NativeSelect>
                </label>
                <p
                    v-if="
                        account.mode === 'optimized' &&
                        account.preferred_hours.length
                    "
                    class="text-sm text-muted-foreground"
                >
                    Giờ ưu tiên:
                    {{ account.preferred_hours.map((h) => `${h}h`).join(', ') }}
                </p>
                <template v-if="account.recommendation?.hours">
                    <ul class="flex flex-wrap gap-2">
                        <li
                            v-for="h in account.recommendation.hours"
                            :key="h.hour"
                            class="rounded-md border bg-background px-3 py-1.5 text-sm"
                        >
                            <b>{{ h.hour }}h</b> ·
                            {{ fmtNum(h.avg_views) }} lượt xem ({{
                                h.delta_pct > 0 ? '+' : ''
                            }}{{ h.delta_pct }}%, {{ h.samples }} bài)
                        </li>
                    </ul>
                    <div>
                        <Button size="sm" :disabled="busy" @click="applyHours"
                            >Áp dụng khung giờ đề xuất</Button
                        >
                    </div>
                </template>
                <p v-else class="text-sm text-muted-foreground">
                    {{
                        account.recommendation?.reason ??
                        'Bật tự động đăng để bắt đầu thu số liệu.'
                    }}
                </p>
            </div>
        </div>
    </div>
</template>

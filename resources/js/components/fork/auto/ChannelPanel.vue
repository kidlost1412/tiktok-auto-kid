<script setup lang="ts">
// Thẻ kênh gọn cho cột phải: ai, có bật không, hôm nay tới đâu, Chrome có nối không.
// Mọi chỉnh sửa (hạn mức, khung giờ, hẹn trước, chế độ) nằm trong hộp "Chỉnh".
import { Link, router } from '@inertiajs/vue3';
import { IconAdjustmentsHorizontal, IconPlayerPause, IconShoppingCart } from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import ChannelSettingsDialog from '@/components/fork/auto/ChannelSettingsDialog.vue';
import type { AccountRow, HealthChannel, LichChannel } from '@/components/fork/auto/types';
import { cardCls, toneClasses, type Tone } from '@/components/fork/shared/status';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    account: AccountRow;
    today: LichChannel['today'] | undefined;
    chrome?: HealthChannel;
    blockedCount: number;
}>();

const busy = ref(false);
const editing = ref(false);
const opts = {
    preserveScroll: true,
    onFinish: () => {
        busy.value = false;
    },
};

const toggle = (enabled: boolean) => {
    busy.value = true;
    router.patch(`/auto/accounts/${props.account.id}`, { enabled }, opts);
};

const pause = () => {
    busy.value = true;
    router.post(`/auto/accounts/${props.account.id}/pause`, {}, opts);
};

const name = computed(() => `@${props.account.username ?? props.account.display_name ?? '—'}`);
const cap = computed(() => props.today?.cap ?? props.account.daily_cap);
const planned = computed(() => props.today?.planned ?? 0);
const posted = computed(() => props.today?.posted ?? 0);
const pct = (n: number) => `${Math.min(100, (n / (cap.value || 1)) * 100)}%`;

const chrome = computed<{ text: string; tone: Tone }>(() => {
    const c = props.chrome;

    if (!c || !c.chrome_enabled) {
        return { text: 'Chrome chưa bật', tone: 'danger' };
    }

    if (c.chrome_online) {
        return { text: 'Chrome đang kết nối', tone: 'success' };
    }

    return {
        text: c.chrome_last_seen ? `Chrome mất kết nối từ ${dayjs(c.chrome_last_seen).format('HH:mm DD/MM')}` : 'Chưa thấy tiện ích Chrome',
        tone: 'warn',
    };
});

const hh = (h: number) => `${String(h).padStart(2, '0')}h`;
const summary = computed(() => {
    const a = props.account;

    return `${a.daily_cap} bài/ngày · ${hh(a.window_start)}–${hh(a.window_end)} · hẹn trước ${a.schedule_ahead_days ?? 3} ngày`;
});
</script>

<template>
    <div
        :class="cn(cardCls, 'flex flex-col gap-4 p-4', !account.enabled && 'bg-muted/30')"
        :data-testid="`fork-auto-account-${account.id}`"
    >
        <div class="flex items-center gap-3">
            <div class="relative shrink-0">
                <Avatar class="size-11">
                    <AvatarImage v-if="account.avatar_url" :src="account.avatar_url" alt="" />
                    <AvatarFallback class="font-semibold">{{ (account.username ?? '?').slice(0, 1).toUpperCase() }}</AvatarFallback>
                </Avatar>
                <span
                    :class="cn('absolute -right-0.5 -bottom-0.5 size-3.5 rounded-full border-2 border-card', toneClasses[chrome.tone].dot)"
                    :title="chrome.text"
                />
            </div>
            <div class="min-w-0 flex-1">
                <div class="truncate text-[15px] font-semibold tracking-tight">{{ name }}</div>
                <div class="truncate text-[12.5px] text-muted-foreground">{{ account.display_name ?? summary }}</div>
            </div>
            <Switch
                :model-value="account.enabled"
                :disabled="busy"
                :aria-label="`${account.enabled ? 'Tắt' : 'Bật'} tự động đăng cho ${name}`"
                @update:model-value="(v: boolean) => toggle(v)"
            />
        </div>

        <div>
            <div class="mb-1.5 flex items-baseline justify-between text-[13px]">
                <span class="text-muted-foreground">Hôm nay</span>
                <span class="tabular-nums"
                    ><b class="font-semibold">{{ posted }}</b><span class="text-muted-foreground"> đã đăng · {{ planned }}/{{ cap }} đã hẹn</span></span
                >
            </div>
            <div class="relative h-1.5 overflow-hidden rounded-full bg-muted">
                <span class="absolute inset-y-0 left-0 rounded-full bg-primary/30 transition-[width] duration-500" :style="{ width: pct(planned) }" />
                <span class="absolute inset-y-0 left-0 rounded-full bg-primary transition-[width] duration-500" :style="{ width: pct(posted) }" />
            </div>
        </div>

        <div class="flex flex-wrap gap-1.5 text-[12.5px] empty:hidden">
            <Link
                v-if="chrome.tone !== 'success'"
                href="/settings#chrome"
                :class="cn('rounded-full px-2.5 py-1 font-medium hover:underline', toneClasses[chrome.tone].chip)"
                >{{ chrome.text }}</Link
            >
            <span v-if="account.paused_reason" :class="cn('rounded-full px-2.5 py-1 font-medium', toneClasses.warn.chip)"
                >Tạm dừng: {{ account.paused_reason }}</span
            >
            <Link
                v-if="blockedCount > 0"
                :href="`/auto/gio-hang?kenh=${account.id}`"
                :class="cn('rounded-full px-2.5 py-1 font-medium hover:underline', toneClasses.warn.chip)"
                >{{ blockedCount }} video chờ chọn giỏ</Link
            >
        </div>

        <div class="flex items-center gap-1.5 border-t pt-3">
            <Button size="sm" variant="outline" class="h-8" :data-testid="`fork-auto-edit-${account.id}`" @click="editing = true">
                <IconAdjustmentsHorizontal class="size-4" />
                Chỉnh
            </Button>
            <Button v-if="account.enabled" size="sm" variant="ghost" class="h-8" :disabled="busy" @click="pause">
                <IconPlayerPause class="size-4" />
                Tạm dừng
            </Button>
            <Link
                :href="`/auto/gio-hang?kenh=${account.id}`"
                class="ml-auto inline-flex items-center gap-1 text-[13px] font-medium text-primary-text hover:underline"
                :data-testid="`fork-auto-cart-${account.id}`"
            >
                <IconShoppingCart class="size-4" />
                {{ account.cart.linked_count }} giỏ
            </Link>
        </div>

        <ChannelSettingsDialog v-model:open="editing" :account="account" />
    </div>
</template>

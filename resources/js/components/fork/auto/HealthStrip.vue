<script setup lang="ts">
// Dải sức khoẻ hệ thống ở đầu trang: hub, Chrome từng kênh, tự động đăng, Telegram.
import { Link } from '@inertiajs/vue3';
import {
    IconBellRinging,
    IconBrandChrome,
    IconPlugConnected,
    IconRobot,
} from '@tabler/icons-vue';
import { computed } from 'vue';

import type {
    AccountRow,
    Health,
    HubStatus,
} from '@/components/fork/auto/types';
import type { Tone } from '@/components/fork/shared/status';
import { cardCls, healthTone, toneClasses } from '@/components/fork/shared/status';
import { Skeleton } from '@/components/ui/skeleton';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    hub?: HubStatus;
    health: Health;
    accounts: AccountRow[];
}>();

type Level = keyof typeof healthTone;

interface Chip {
    key: string;
    title: string;
    text: string;
    level: Level;
    icon: typeof IconRobot;
    href: string;
    hint: string;
    loading?: boolean;
}

const chips = computed<Chip[]>(() => {
    const out: Chip[] = [];

    const hub = props.hub;
    out.push({
        key: 'hub',
        href: '/xuong',
        hint: 'Mở Xưởng Video',
        title: 'Xưởng Video',
        text: hub ? hub.label : '',
        loading: !hub,
        icon: IconPlugConnected,
        level: !hub
            ? 'idle'
            : hub.state === 'ok'
              ? 'ok'
              : hub.state === 'off'
                ? 'idle'
                : hub.state === 'offline'
                  ? 'warn'
                  : 'bad',
    });

    const on = props.accounts.filter((a) => a.enabled).length;
    out.push({
        key: 'auto',
        href: '/auto#kenh',
        hint: 'Xem và bật/tắt từng kênh',
        title: 'Tự động đăng',
        icon: IconRobot,
        text: props.accounts.length
            ? `Bật ${on}/${props.accounts.length} kênh`
            : 'Chưa có kênh',
        level: on === 0 ? 'bad' : on < props.accounts.length ? 'warn' : 'ok',
    });

    for (const a of props.accounts) {
        const h = props.health.channels.find((c) => c.id === a.id);
        const name = `@${a.username ?? a.display_name ?? '—'}`;
        const base = {
            key: `chrome-${a.id}`,
            href: '/settings/chrome',
            hint: 'Mở trang Kết nối Chrome',
            title: `Chrome ${name}`,
            icon: IconBrandChrome,
        };

        if (!h?.chrome_enabled) {
            out.push({
                ...base,
                text: 'Chưa bật đăng qua Chrome',
                level: 'bad',
            });
        } else if (h.chrome_online) {
            out.push({ ...base, text: 'Đang kết nối', level: 'ok' });
        } else {
            out.push({
                ...base,
                text: h.chrome_last_seen
                    ? `Mất kết nối từ ${dayjs(h.chrome_last_seen).format('HH:mm DD/MM')}`
                    : 'Chưa thấy tiện ích',
                level: 'warn',
            });
        }
    }

    out.push({
        key: 'telegram',
        href: '/settings/telegram',
        hint: props.health.telegram ? 'Mở cài đặt Telegram' : 'Cài đặt Telegram (3 bước, không cần sửa file)',
        title: 'Cảnh báo Telegram',
        icon: IconBellRinging,
        text: props.health.telegram ? 'Đã cấu hình' : 'Chưa cấu hình',
        level: props.health.telegram ? 'ok' : 'idle',
    });

    return out;
});

const tone = (l: Level): Tone => healthTone[l];
</script>

<template>
    <div
        class="grid gap-5 sm:grid-cols-2 xl:grid-cols-4"
        data-testid="fork-auto-health"
    >
        <Link
            v-for="c in chips"
            :key="c.key"
            :href="c.href"
            :title="c.hint"
            :data-testid="`fork-health-chip-${c.key}`"
            :class="cn(cardCls, 'flex items-center gap-3.5 px-5 py-4 transition hover:border-border-strong hover:bg-accent/40 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none')"
        >
            <span
                :class="
                    cn(
                        'flex size-[38px] shrink-0 items-center justify-center rounded-[11px]',
                        toneClasses[tone(c.level)].chip,
                    )
                "
            >
                <component :is="c.icon" class="size-[18px]" />
            </span>
            <div class="min-w-0 flex-1 leading-snug">
                <div class="truncate text-sm font-semibold">{{ c.title }}</div>
                <Skeleton v-if="c.loading" class="mt-2 h-4 w-28" />
                <div v-else class="truncate text-sm text-muted-foreground">
                    {{ c.text }}
                </div>
            </div>
            <span
                :class="
                    cn(
                        'size-2.5 shrink-0 rounded-full',
                        toneClasses[tone(c.level)].dot,
                        c.level === 'ok' && 'ring-[3px] ring-emerald-500/20',
                        c.loading && 'animate-pulse',
                    )
                "
            />
        </Link>
    </div>
</template>

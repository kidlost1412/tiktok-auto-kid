<script setup lang="ts">
// Dải sức khoẻ hệ thống, gọn thành một thanh ngang: hub sản xuất và Telegram.
// Trạng thái Chrome của từng kênh hiện ngay trên thẻ kênh tương ứng (đỡ lặp lại ở đây).
import { Link } from '@inertiajs/vue3';
import { IconBellRinging, IconPlugConnected } from '@tabler/icons-vue';
import { computed } from 'vue';

import type { Health, HubStatus } from '@/components/fork/auto/types';
import type { Tone } from '@/components/fork/shared/status';
import { healthTone, toneClasses } from '@/components/fork/shared/status';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const props = defineProps<{
    hub?: HubStatus;
    health: Health;
}>();

type Level = keyof typeof healthTone;

interface Chip {
    key: string;
    text: string;
    level: Level;
    icon: typeof IconPlugConnected;
    href: string;
    hint: string;
    loading?: boolean;
}

const chips = computed<Chip[]>(() => {
    const hub = props.hub;

    return [
        {
            key: 'hub',
            href: '/xuong',
            hint: 'Mở Xưởng Video',
            text: hub ? `Xưởng Video: ${hub.label}` : 'Xưởng Video',
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
        },
        {
            key: 'telegram',
            href: '/settings#telegram',
            hint: props.health.telegram ? 'Mở cài đặt Telegram' : 'Cài đặt Telegram (3 bước, không cần sửa file)',
            text: `Telegram: ${props.health.telegram ? 'Đã cấu hình' : 'Chưa cấu hình'}`,
            icon: IconBellRinging,
            level: props.health.telegram ? 'ok' : 'idle',
        },
    ];
});

const tone = (l: Level): Tone => healthTone[l];
</script>

<template>
    <div
        class="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card/60 px-3 py-2"
        data-testid="fork-auto-health"
    >
        <Link
            v-for="c in chips"
            :key="c.key"
            :href="c.href"
            :title="c.hint"
            :data-testid="`fork-health-chip-${c.key}`"
            :class="
                cn(
                    'inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[0.8125rem] font-medium transition hover:bg-accent/50',
                )
            "
        >
            <span
                :class="cn('flex size-2.5 shrink-0 rounded-full', toneClasses[tone(c.level)].dot, c.loading && 'animate-pulse')"
            />
            <component :is="c.icon" class="size-4 text-muted-foreground" />
            <Skeleton v-if="c.loading" class="h-4 w-24" />
            <span v-else class="text-foreground">{{ c.text }}</span>
        </Link>
    </div>
</template>

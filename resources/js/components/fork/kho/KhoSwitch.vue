<script setup lang="ts">
// Chuyển giữa "Kho Xưởng Video" (video từ hub) và "Kho riêng" (video bạn tự làm).
import { Link } from '@inertiajs/vue3';

import { cn } from '@/lib/utils';

defineProps<{ active: 'hub' | 'rieng' }>();

const items = [
    { key: 'hub', href: '/auto/kho', label: 'Kho Xưởng Video' },
    { key: 'rieng', href: '/auto/kho/rieng', label: 'Kho riêng' },
] as const;
</script>

<template>
    <nav
        class="inline-flex w-fit gap-1 rounded-xl bg-muted p-1"
        aria-label="Chọn kho"
        data-testid="fork-kho-switch"
    >
        <Link
            v-for="i in items"
            :key="i.key"
            :href="i.href"
            :class="
                cn(
                    'rounded-lg px-4 py-1.5 text-sm font-medium transition',
                    active === i.key
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground',
                )
            "
        >
            {{ i.label }}
        </Link>
    </nav>
</template>

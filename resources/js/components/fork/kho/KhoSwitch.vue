<script setup lang="ts">
// Chuyển giữa "Kho Xưởng Video" (video từ hub) và "Kho riêng" (video anh tự làm).
import { Link } from '@inertiajs/vue3';
import { IconTrash } from '@tabler/icons-vue';
import { ref } from 'vue';

import TrashDialog from '@/components/fork/auto/TrashDialog.vue';
import { cn } from '@/lib/utils';

defineProps<{ active: 'hub' | 'rieng' }>();

const items = [
    { key: 'hub', href: '/auto/kho', label: 'Kho Xưởng Video' },
    { key: 'rieng', href: '/auto/kho/rieng', label: 'Kho riêng' },
] as const;

const trashOpen = ref(false);
</script>

<template>
    <div class="flex flex-wrap items-center gap-2">
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
        <button
            type="button"
            class="inline-flex h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            title="Video anh đã xoá: khôi phục được trong 30 ngày"
            data-testid="fork-kho-trash-open"
            @click="trashOpen = true"
        >
            <IconTrash class="size-4" /> Thùng rác
        </button>
        <TrashDialog v-model:open="trashOpen" />
    </div>
</template>

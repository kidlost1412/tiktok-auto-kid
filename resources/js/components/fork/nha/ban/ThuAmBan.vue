<script setup lang="ts">
// Bàn Thu âm: dải trạng thái + khối Giọng đọc của hub nhúng bên dưới.
import { computed } from 'vue';

import HubEmbed from '@/components/fork/nha/ban/HubEmbed.vue';
import type { NhaData } from '@/components/fork/nha/types';

const props = defineProps<{ data: NhaData | null }>();

const vai = computed(() => props.data?.vai?.thuam ?? null);
const dot = computed(() =>
    vai.value?.state === 'working'
        ? 'bg-emerald-500'
        : vai.value?.state === 'idle'
          ? 'bg-amber-400'
          : 'bg-muted-foreground/40',
);
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col gap-4" data-testid="nha-ban-thuam">
        <section
            class="flex shrink-0 items-center gap-2 rounded-xl border bg-card px-4 py-3"
        >
            <span class="size-2 rounded-full" :class="dot" />
            <p class="truncate text-sm font-medium">
                <template v-if="!data">Đang tải…</template>
                <template v-else-if="!data.hub.up"
                    >Xưởng Video đang tắt.</template
                >
                <template v-else>{{
                    vai?.bubble ||
                    (vai?.state === 'working'
                        ? 'Đang thu giọng'
                        : 'Đang chờ thu giọng')
                }}</template>
            </p>
        </section>
        <HubEmbed :hub-url="data?.hub.url" tab="cai-dat" muc="giong" />
    </div>
</template>

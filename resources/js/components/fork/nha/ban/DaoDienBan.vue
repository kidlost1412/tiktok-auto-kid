<script setup lang="ts">
// Bàn Đạo diễn: dải trạng thái + nhật ký gần nhất, bên dưới là tab Gu & bài học của hub.
import { computed } from 'vue';

import HubEmbed from '@/components/fork/nha/ban/HubEmbed.vue';
import type { NhaData } from '@/components/fork/nha/types';
import NhatKyDaoDien from '@/components/fork/nha3d/NhatKyDaoDien.vue';

const props = defineProps<{ data: NhaData | null }>();

const vai = computed(() => props.data?.vai?.daodien ?? null);
const dot = computed(() =>
    vai.value?.state === 'working'
        ? 'bg-emerald-500'
        : vai.value?.state === 'idle'
          ? 'bg-amber-400'
          : 'bg-muted-foreground/40',
);
</script>

<template>
    <div
        class="flex min-h-0 flex-1 flex-col gap-4"
        data-testid="nha-ban-daodien"
    >
        <section class="shrink-0 rounded-xl border bg-card p-4">
            <div class="flex items-center gap-2">
                <span class="size-2 rounded-full" :class="dot" />
                <p class="truncate text-sm font-medium">
                    {{
                        vai?.bubble ||
                        (vai?.state === 'working'
                            ? 'Đang dựng video'
                            : 'Đang chờ việc')
                    }}
                </p>
            </div>
            <div class="mt-3 flex max-h-24 flex-col overflow-y-auto">
                <NhatKyDaoDien :data="data" />
            </div>
        </section>
        <HubEmbed :hub-url="data?.hub.url" tab="gu" />
    </div>
</template>

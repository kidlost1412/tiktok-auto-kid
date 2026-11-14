<script setup lang="ts">
// Bàn Giám khảo: dải "Video mới chấm" (bấm để mở file) + tab Kho video của hub nhúng bên dưới.
import { computed } from 'vue';

import HubEmbed from '@/components/fork/nha/ban/HubEmbed.vue';
import type { NhaData } from '@/components/fork/nha/types';

const props = defineProps<{ data: NhaData | null }>();

// Đạt/không đạt lấy từ sổ sự kiện (cùng nguồn với cảnh 3D); thiếu thì suy từ điểm.
const datMap = computed(() => {
    const m = new Map<string, boolean>();

    for (const e of props.data?.events ?? []) {
        if (e.file && typeof e.dat === 'boolean') {
            m.set(e.file, e.dat);
        }
    }

    return m;
});

const reels = computed(() =>
    (props.data?.reels ?? [])
        .slice(-8)
        .reverse()
        .map((r) => ({
            ...r,
            dat:
                datMap.value.get(r.file) ??
                (r.diem === null ? null : r.diem >= 7),
        })),
);

const tong = computed(() => ({
    dat: reels.value.filter((r) => r.dat === true).length,
    khong: reels.value.filter((r) => r.dat === false).length,
}));

const mo = (r: { file: string; ngay: string }) => {
    const hub = props.data?.hub.url?.replace(/\/+$/, '');

    if (hub && r.file && r.ngay) {
        window.open(
            `${hub}/file?p=${encodeURIComponent(`${r.ngay}/${r.file}`)}`,
            '_blank',
            'noopener',
        );
    }
};

const mauDiem = (dat: boolean | null) =>
    dat === null
        ? 'text-muted-foreground'
        : dat
          ? 'text-emerald-600 dark:text-emerald-400'
          : 'text-rose-600 dark:text-rose-400';
</script>

<template>
    <div
        class="flex min-h-0 flex-1 flex-col gap-4"
        data-testid="nha-ban-giamkhao"
    >
        <section class="shrink-0 rounded-xl border bg-card p-4">
            <div class="flex items-center justify-between gap-4">
                <p
                    class="text-xs font-medium tracking-wide text-muted-foreground uppercase"
                >
                    Video mới chấm
                </p>
                <p
                    v-if="reels.length"
                    class="text-xs text-muted-foreground tabular-nums"
                >
                    <span
                        class="font-semibold text-emerald-600 dark:text-emerald-400"
                        >{{ tong.dat }}</span
                    >
                    đạt ·
                    <span
                        class="font-semibold text-rose-600 dark:text-rose-400"
                        >{{ tong.khong }}</span
                    >
                    không đạt
                </p>
            </div>
            <p v-if="!data" class="mt-2 text-sm text-muted-foreground">
                Đang tải…
            </p>
            <p
                v-else-if="!data.hub.up"
                class="mt-2 text-sm text-muted-foreground"
            >
                Xưởng Video đang tắt.
            </p>
            <p
                v-else-if="!reels.length"
                class="mt-2 text-sm text-muted-foreground"
            >
                Chưa có video nào được chấm gần đây.
            </p>
            <ul v-else class="mt-3 flex gap-2 overflow-x-auto pb-1">
                <li v-for="r in reels" :key="r.n" class="shrink-0">
                    <button
                        type="button"
                        class="flex w-36 flex-col gap-1 rounded-lg border bg-background px-3 py-2 text-left transition hover:bg-accent"
                        :title="r.file"
                        @click="mo(r)"
                    >
                        <span class="truncate text-xs text-muted-foreground">{{
                            r.file
                        }}</span>
                        <span
                            class="text-lg leading-none font-semibold tabular-nums"
                            :class="mauDiem(r.dat)"
                        >
                            {{ r.diem === null ? '—' : r.diem
                            }}<span
                                class="text-xs font-normal text-muted-foreground"
                            >
                                /10</span
                            >
                        </span>
                    </button>
                </li>
            </ul>
        </section>
        <HubEmbed :hub-url="data?.hub.url" tab="kho" />
    </div>
</template>

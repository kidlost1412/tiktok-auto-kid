<script setup lang="ts">
// Bàn Thợ dựng / Bảng việc: dải "Lô đang làm" (dữ liệu sống) + giao diện Sản xuất của hub nhúng bên dưới.
import { computed } from 'vue';

import HubEmbed from '@/components/fork/nha/ban/HubEmbed.vue';
import type { NhaData, VaiState } from '@/components/fork/nha/types';

const props = defineProps<{ data: NhaData | null }>();

const VAI: [string, string][] = [
    ['thodung', 'Thợ dựng'],
    ['giamkhao', 'Giám khảo'],
    ['daodien', 'Đạo diễn'],
    ['bienkich', 'Biên kịch'],
    ['thuam', 'Thu âm'],
    ['thukho', 'Thủ kho'],
    ['buuta', 'Bưu tá'],
    ['chuquay', 'Chủ quầy'],
    ['cu', 'Cú'],
];

const DOT: Record<VaiState, string> = {
    working: 'bg-emerald-500',
    idle: 'bg-amber-400',
    sleep: 'bg-muted-foreground/40',
};

const chips = computed(() => {
    const vai = props.data?.vai ?? {};

    return VAI.filter(([k]) => vai[k]).map(([k, ten]) => ({
        k,
        ten,
        state: vai[k].state,
    }));
});

const td = computed(() => props.data?.bang?.tien_do ?? null);
const pct = computed(() =>
    td.value && td.value.tong > 0
        ? Math.min(100, Math.round((td.value.xong / td.value.tong) * 100))
        : 0,
);
</script>

<template>
    <div
        class="flex min-h-0 flex-1 flex-col gap-4"
        data-testid="nha-ban-thodung"
    >
        <section class="shrink-0 rounded-xl border bg-card p-4">
            <div class="flex items-center justify-between gap-4">
                <div class="min-w-0">
                    <p
                        class="text-xs font-medium tracking-wide text-muted-foreground uppercase"
                    >
                        Lô đang làm
                    </p>
                    <p v-if="!data" class="mt-1 text-sm text-muted-foreground">
                        Đang tải…
                    </p>
                    <p
                        v-else-if="!data.hub.up"
                        class="mt-1 text-sm text-muted-foreground"
                    >
                        Xưởng Video đang tắt.
                    </p>
                    <p
                        v-else-if="!data.bang.san_pham"
                        class="mt-1 truncate text-base font-semibold"
                    >
                        Chưa có lô nào đang làm
                    </p>
                    <p v-else class="mt-1 truncate text-base font-semibold">
                        {{ data.bang.san_pham }}
                    </p>
                </div>
                <div v-if="td" class="shrink-0 text-right">
                    <p class="text-2xl leading-none font-semibold tabular-nums">
                        {{ td.xong
                        }}<span
                            class="text-base font-normal text-muted-foreground"
                        >
                            / {{ td.tong }}</span
                        >
                    </p>
                    <p class="mt-1 text-xs text-muted-foreground">video xong</p>
                </div>
            </div>
            <div
                v-if="td"
                class="mt-3 h-1.5 overflow-hidden rounded-full bg-secondary"
            >
                <div
                    class="h-full rounded-full bg-primary transition-all duration-500"
                    :style="{ width: pct + '%' }"
                />
            </div>
            <p
                v-if="data?.bang.dong"
                class="mt-2 truncate text-sm text-muted-foreground"
            >
                {{ data.bang.dong }}
            </p>
            <p
                v-if="data?.mode === 'limit'"
                class="mt-2 rounded-lg bg-amber-500/10 px-3 py-1.5 text-xs text-amber-600 dark:text-amber-400"
            >
                Hết hạn mức Claude — vào Cài đặt, đổi tài khoản rồi bấm Bắt đầu
                làm để làm tiếp.
            </p>
            <ul v-if="chips.length" class="mt-3 flex flex-wrap gap-1.5">
                <li
                    v-for="c in chips"
                    :key="c.k"
                    class="inline-flex items-center gap-1.5 rounded-full border bg-background px-2 py-0.5 text-xs text-muted-foreground"
                >
                    <span class="size-1.5 rounded-full" :class="DOT[c.state]" />
                    {{ c.ten }}
                </li>
            </ul>
        </section>
        <HubEmbed :hub-url="data?.hub.url" tab="san-xuat" />
    </div>
</template>

<script setup lang="ts">
// Sổ tự thoại của một nhân vật: những câu nó vừa lẩm bẩm khi làm việc thật (cùng câu với bong bóng trên đầu).
// Chỉ đọc dữ liệu trang cha đã có (/nha/trang-thai), không gọi API, không gọi AI.
import { computed } from 'vue';

import { tatCaTuThoai } from '@/components/fork/nha/tu-thoai';
import type { NhaData } from '@/components/fork/nha/types';

// dangLam: màn hình trực tiếp ngay phía trên đang chạy → sổ trống thì ẩn hẳn, đừng nói "chưa có việc" khi đang làm.
const props = defineProps<{
    data: NhaData | null;
    who: string;
    dangLam?: boolean;
}>();

const now = computed(
    () => props.data?.bay_gio_app ?? props.data?.bay_gio ?? Date.now() / 1000,
);

const truoc = (n: number) => {
    const s = now.value - n / 1_000_000;
    if (s < 45) {
        return 'vừa xong';
    }
    if (s < 3600) {
        return `${Math.max(1, Math.round(s / 60))} phút trước`;
    }

    return `${Math.round(s / 3600)} giờ trước`;
};

const dong = computed(() =>
    tatCaTuThoai(props.data)
        .filter((t) => t.who === props.who)
        .slice(-8)
        .reverse()
        .map((t) => ({ ...t, luc: truoc(t.n) })),
);
</script>

<template>
    <section
        v-if="dong.length || !dangLam"
        class="mb-4 shrink-0 rounded-xl border bg-card px-4 py-3"
        data-testid="nha-tu-thoai"
    >
        <p
            class="text-xs font-medium text-muted-foreground"
        >
            Đang nghĩ gì
        </p>
        <p v-if="!dong.length" class="mt-1.5 text-sm text-muted-foreground">
            Chưa có việc gì để lẩm bẩm
        </p>
        <ul v-else class="mt-1.5 flex max-h-44 flex-col gap-1 overflow-y-auto">
            <li
                v-for="(l, i) in dong"
                :key="l.id"
                class="flex items-baseline justify-between gap-3 rounded-md px-2 py-1 text-sm"
                :class="
                    i === 0
                        ? 'bg-secondary font-medium'
                        : 'text-muted-foreground'
                "
            >
                <span class="min-w-0 break-words">{{ l.text }}</span>
                <span class="shrink-0 text-xs text-muted-foreground tabular-nums">{{
                    l.luc
                }}</span>
            </li>
        </ul>
    </section>
</template>

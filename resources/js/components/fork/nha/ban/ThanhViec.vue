<script setup lang="ts">
// Thanh avatar nổi ở giữa cạnh dưới cảnh 3D: mỗi vai một avatar, chấm trạng thái, huy hiệu số việc chờ.
// Rê chuột hiện tên + việc đang chờ / lời nhân vật; bấm mở "Bàn làm việc" của vai đó.
import { computed } from 'vue';

import { BAN, BAN_THU_TU } from '@/components/fork/nha/ban/registry';
import type { NhaData } from '@/components/fork/nha/types';

const props = defineProps<{ data: NhaData | null }>();
defineEmits<{ open: [vai: string] }>();

const DOT: Record<string, string> = {
    working: 'bg-emerald-500',
    idle: 'bg-amber-400',
    sleep: 'bg-slate-400',
};

const STATE_TEXT: Record<string, string> = {
    working: 'Đang làm việc',
    idle: 'Đang rảnh',
    sleep: 'Đang nghỉ',
};

const items = computed(() =>
    BAN_THU_TU.filter((v) => BAN[v]).map((v) => {
        const def = BAN[v];
        const info = props.data?.vai?.[def.vai ?? v];
        const viec = props.data?.viec?.[v];
        const state = info?.state ?? 'idle';

        return {
            vai: v,
            ten: def.ten,
            emoji: def.emoji,
            mau: def.mau,
            so: viec?.so ?? 0,
            dot: DOT[state] ?? DOT.idle,
            tip: viec?.tom_tat || info?.bubble || STATE_TEXT[state],
        };
    }),
);
</script>

<template>
    <nav
        class="pointer-events-none absolute bottom-4 left-1/2 z-[4] hidden -translate-x-1/2 md:block"
        aria-label="Các bàn làm việc"
        data-testid="nha-thanh-viec"
    >
        <ul
            class="pointer-events-auto flex items-end gap-1.5 rounded-2xl border border-border/70 bg-background/70 p-1.5 shadow-lg ring-1 ring-black/5 backdrop-blur-md dark:ring-white/5"
        >
            <li v-for="it in items" :key="it.vai" class="group relative">
                <button
                    type="button"
                    class="relative grid size-11 place-items-center rounded-full bg-gradient-to-br text-xl shadow-sm ring-1 ring-black/10 transition duration-150 hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none active:scale-95"
                    :class="it.mau"
                    :aria-label="`Mở bàn làm việc: ${it.ten}${it.so > 0 ? `, ${it.so} việc chờ` : ''}`"
                    :data-testid="`nha-thanh-viec-${it.vai}`"
                    @click="$emit('open', it.vai)"
                >
                    <span aria-hidden="true">{{ it.emoji }}</span>
                    <span
                        class="absolute right-0 bottom-0 size-3 rounded-full border-2 border-background"
                        :class="it.dot"
                        aria-hidden="true"
                    />
                    <span
                        v-if="it.so > 0"
                        class="absolute -top-1 -right-1 grid h-5 min-w-5 place-items-center rounded-full border-2 border-background bg-red-500 px-1 text-xs leading-none font-semibold text-white tabular-nums"
                        :data-testid="`nha-thanh-viec-${it.vai}-so`"
                    >
                        {{ it.so > 99 ? '99+' : it.so }}
                    </span>
                </button>
                <div
                    class="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 w-max max-w-56 -translate-x-1/2 translate-y-1 rounded-xl border border-border bg-popover px-3 py-1.5 text-center text-popover-foreground opacity-0 shadow-lg transition duration-150 group-focus-within:translate-y-0 group-focus-within:opacity-100 group-hover:translate-y-0 group-hover:opacity-100"
                    role="tooltip"
                >
                    <div class="text-sm font-semibold">{{ it.ten }}</div>
                    <div class="text-xs text-muted-foreground">
                        {{ it.tip }}
                    </div>
                </div>
            </li>
        </ul>
    </nav>
</template>

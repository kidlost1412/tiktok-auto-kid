<script setup lang="ts">
// "Màn hình trực tiếp" của một việc đang chạy: tiêu đề (việc · sản phẩm · đã làm bao lâu · bước/tiến độ) và phần chữ thật đang
// chảy về như một màn hình theo dõi: các dòng đã xong + dòng đang gõ dở có con trỏ nhấp nháy, tự cuộn xuống dưới, chữ mới hiện dần.
// Chỉ đọc LiveItem do trang cha cấp (hub/app), không gọi API, không gọi AI, không bịa chữ.
import { IconAlertTriangle, IconCircleCheck } from '@tabler/icons-vue';
import { computed, nextTick, ref, watch } from 'vue';

import { daLam, dongHo, soVi, tenVai } from '@/components/fork/nha/truc-tiep';
import type { LiveItem } from '@/components/fork/nha/types';
import { useGoChu } from '@/components/fork/nha/useGoChu';
import { useTrucTiepKho } from '@/components/fork/nha/useTrucTiep';
import { cn } from '@/lib/utils';

const props = defineProps<{ item: LiveItem }>();

const kho = useTrucTiepKho();
const now = computed(() => kho?.nowSec.value ?? Date.now() / 1000);

const dang = computed(() => !props.item.xong);
const loi = computed(() => props.item.xong && props.item.ket_qua === 'loi');
const mat = computed(() => {
    const d = daLam(props.item, now.value);

    return d === null ? null : dongHo(d);
});

const tieuDe = computed(
    () => props.item.viec || `${tenVai(props.item)} đang làm việc`,
);
// Dòng phụ: ai · cho cái gì · bước nào
const phu = computed(() =>
    [
        tenVai(props.item),
        props.item.sp || props.item.video || props.item.kenh,
        props.item.buoc,
    ].filter((x): x is string => !!x),
);
const phanTram = computed(() =>
    props.item.tien_do != null && props.item.tien_do > 0
        ? Math.round(props.item.tien_do * 100)
        : null,
);

// Các số thật hay gặp trong chi_tiet (khoá lạ thì bỏ qua, không in tên khoá thô ra màn hình)
const NHAN: Record<string, string> = {
    diem: 'điểm',
    giay: 'giây',
    dur: 'giây',
    so_canh: 'cảnh',
    so_loi: 'lỗi',
    so: 'mục',
};
const chip = computed(() => {
    const out: string[] = [];

    if (props.item.ky_tu && props.item.ky_tu > 0) {
        out.push(`${soVi(props.item.ky_tu)} chữ`);
    }

    for (const [k, v] of Object.entries(props.item.chi_tiet ?? {})) {
        if (NHAN[k] && typeof v === 'number' && Number.isFinite(v)) {
            out.push(
                `${String(Math.round(v * 10) / 10).replace('.', ',')} ${NHAN[k]}`,
            );
        }
    }

    return out;
});

const { hang } = useGoChu(() => ({
    dong: props.item.dong ?? [],
    dang: props.item.dang_go ?? null,
}));
// Chữ hiện lần lượt từ trên xuống: dòng nào chưa tới lượt gõ thì chưa hiện (không có dòng trống nhảy ra).
const hetChu = computed(() => hang.value.every((h) => h.hien >= h.text.length));
const hien = computed(() => {
    const i = hang.value.findIndex((h) => h.hien < h.text.length);

    return i < 0 ? hang.value : hang.value.slice(0, i + 1);
});
const coChu = computed(() => hang.value.length > 0 || !!props.item.suy_nghi);

// Tự cuộn xuống dòng mới nhất, trừ khi anh đang kéo lên đọc lại.
const man = ref<HTMLElement | null>(null);
let dinh = true;
const onScroll = () => {
    const el = man.value;

    if (el) {
        dinh = el.scrollHeight - el.scrollTop - el.clientHeight < 28;
    }
};
watch(
    [hang, () => props.item.suy_nghi],
    async () => {
        if (!dinh) {
            return;
        }
        await nextTick();

        if (man.value) {
            man.value.scrollTop = man.value.scrollHeight;
        }
    },
    { flush: 'post' },
);
</script>

<template>
    <section
        class="overflow-hidden rounded-xl border bg-card"
        data-testid="nha-truc-tiep"
        :aria-label="`Đang làm: ${tieuDe}`"
    >
        <header class="flex flex-col gap-1.5 px-4 py-3">
            <div class="flex items-center gap-2">
                <IconCircleCheck
                    v-if="item.xong && !loi"
                    class="size-4 shrink-0 text-emerald-500"
                    aria-hidden="true"
                />
                <IconAlertTriangle
                    v-else-if="loi"
                    class="size-4 shrink-0 text-red-600 dark:text-red-400"
                    aria-hidden="true"
                />
                <span
                    v-else
                    class="relative flex size-2.5 shrink-0"
                    aria-hidden="true"
                >
                    <span
                        class="ls-ping absolute inline-flex size-full rounded-full bg-emerald-400/70"
                    />
                    <span
                        class="relative inline-flex size-2.5 rounded-full bg-emerald-500"
                    />
                </span>
                <p class="min-w-0 flex-1 truncate text-sm font-medium">
                    {{ tieuDe }}
                </p>
                <span
                    v-if="item.xong"
                    :class="
                        cn(
                            'shrink-0 rounded-md px-2 py-0.5 text-xs font-medium',
                            loi
                                ? 'bg-red-500/15 text-red-600 dark:text-red-400'
                                : 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
                        )
                    "
                    >{{ loi ? 'Lỗi' : 'Xong' }}</span
                >
                <span
                    v-if="mat"
                    class="shrink-0 text-xs text-muted-foreground tabular-nums"
                    title="Đã làm được"
                    >{{ mat }}</span
                >
            </div>
            <p class="truncate text-xs text-muted-foreground">
                <template v-for="(p, i) in phu" :key="i"
                    ><span v-if="i" class="mx-1.5 opacity-50">·</span
                    >{{ p }}</template
                >
                <template v-if="phanTram !== null">
                    <span class="mx-1.5 opacity-50">·</span>{{ phanTram }}%
                </template>
            </p>
            <div
                v-if="phanTram !== null"
                class="h-1 overflow-hidden rounded-full bg-secondary"
                role="progressbar"
                :aria-valuenow="phanTram"
                aria-valuemin="0"
                aria-valuemax="100"
            >
                <div
                    class="h-full rounded-full bg-emerald-500 transition-[width] duration-700"
                    :style="{ width: `${phanTram}%` }"
                />
            </div>
        </header>

        <div
            v-if="coChu"
            ref="man"
            class="ls-man max-h-52 min-h-16 overflow-y-auto border-t border-zinc-800 bg-zinc-950 px-4 py-3 text-sm leading-relaxed text-zinc-300"
            role="log"
            aria-live="off"
            data-testid="nha-truc-tiep-man"
            @scroll.passive="onScroll"
        >
            <p
                v-for="(h, i) in hien"
                :key="i"
                :class="
                    cn('break-words', h.dang ? 'text-zinc-50' : 'text-zinc-300')
                "
            >
                <span class="mr-1.5 text-emerald-400/80 select-none">{{
                    h.dang ? '▸' : '›'
                }}</span
                >{{ h.text.slice(0, h.hien)
                }}<span
                    v-if="dang && i === hien.length - 1 && (h.dang || !hetChu)"
                    class="ls-caret ml-px inline-block h-[1.05em] w-[0.5ch] translate-y-[0.18em] bg-emerald-400"
                    aria-hidden="true"
                />
            </p>
            <p
                v-if="dang && hetChu && !hang.some((h) => h.dang)"
                class="text-zinc-500"
            >
                <span class="mr-1.5 text-emerald-400/80 select-none">▸</span
                ><span
                    class="ls-caret inline-block h-[1.05em] w-[0.5ch] translate-y-[0.18em] bg-emerald-400"
                    aria-hidden="true"
                />
            </p>
            <p
                v-if="item.suy_nghi && dang"
                class="mt-1.5 text-xs break-words text-zinc-500"
            >
                Đang nghĩ: …{{ item.suy_nghi }}
            </p>
        </div>

        <footer
            v-if="chip.length"
            class="flex flex-wrap gap-1.5 border-t px-4 py-2"
        >
            <span
                v-for="c in chip"
                :key="c"
                class="rounded-md bg-secondary px-2 py-0.5 text-xs text-muted-foreground tabular-nums"
                >{{ c }}</span
            >
        </footer>
    </section>
</template>

<style scoped>
.ls-caret {
    animation: ls-blink 1s steps(1, end) infinite;
}
.ls-ping {
    animation: ls-ping 1.6s cubic-bezier(0, 0, 0.2, 1) infinite;
}
@keyframes ls-blink {
    0%,
    50% {
        opacity: 1;
    }
    50.01%,
    100% {
        opacity: 0;
    }
}
@keyframes ls-ping {
    0% {
        transform: scale(1);
        opacity: 0.8;
    }
    75%,
    100% {
        transform: scale(2.2);
        opacity: 0;
    }
}
@media (prefers-reduced-motion: reduce) {
    .ls-caret,
    .ls-ping {
        animation: none;
    }
}
</style>

<script setup lang="ts">
// Popup "Bàn làm việc" trượt từ phải: cảnh Khu Tự Trị vẫn thấy bên trái, bên phải là phần làm việc thật của vai.
// Nội dung từng vai nằm ở BAN[vai].component (xem registry.ts); khung này chỉ lo đầu popup, đóng/mở, chuyển vai.
import { Link } from '@inertiajs/vue3';
import {
    IconArrowUpRight,
    IconChevronLeft,
    IconChevronRight,
    IconX,
} from '@tabler/icons-vue';
import {
    DialogContent,
    DialogDescription,
    DialogOverlay,
    DialogPortal,
    DialogRoot,
    DialogTitle,
} from 'reka-ui';
import { computed, watch } from 'vue';

import { banBao } from '@/components/fork/nha/ban/bus';
import { BAN, BAN_THU_TU } from '@/components/fork/nha/ban/registry';
import type { NhaData } from '@/components/fork/nha/types';
import { cn } from '@/lib/utils';

const vai = defineModel<string | null>('vai', { required: true });
const props = defineProps<{ data: NhaData | null }>();

const def = computed(() => (vai.value ? (BAN[vai.value] ?? null) : null));
const open = computed({
    get: () => def.value !== null,
    set: (v: boolean) => {
        if (!v) {
            vai.value = null;
        }
    },
});

const trangThai = computed(() => {
    const k = def.value?.vai ?? vai.value ?? '';
    const v = props.data?.vai?.[k];
    const down = !props.data || props.data.mode === 'down';
    const st = down ? 'sleep' : (v?.state ?? 'idle');

    return {
        st,
        text:
            st === 'sleep'
                ? 'Đang nghỉ'
                : (v?.bubble ??
                  (st === 'working' ? 'Đang làm việc' : 'Đang rảnh')),
    };
});

const step = (d: number) => {
    const i = BAN_THU_TU.indexOf(vai.value ?? '');
    const n = BAN_THU_TU.length;
    vai.value = BAN_THU_TU[(Math.max(i, 0) + d + n) % n];
};

watch(vai, (now, before) => {
    if (before) {
        banBao(before, 'dong');
    }
    if (now) {
        banBao(now, 'mo');
    }
});
</script>

<template>
    <DialogRoot v-model:open="open">
        <DialogPortal>
            <DialogOverlay
                class="fixed inset-0 z-50 bg-black/25 backdrop-blur-[1px] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0"
            />
            <DialogContent
                v-if="def"
                class="fixed top-3 right-3 bottom-3 z-50 flex w-[min(1080px,calc(100vw-24px))] flex-col overflow-hidden rounded-2xl border bg-background shadow-[0_24px_80px_-12px_rgba(0,0,0,.45)] duration-300 outline-none data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-right-8 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-right-8 max-sm:inset-0 max-sm:w-full max-sm:rounded-none"
                :data-testid="`nha-ban-${vai}`"
                @open-auto-focus.prevent
            >
                <header
                    class="flex shrink-0 items-center gap-4 border-b bg-card/60 px-6 py-4"
                >
                    <span
                        :class="
                            cn(
                                'grid size-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br text-2xl shadow-sm ring-1 ring-white/20',
                                def.mau,
                            )
                        "
                        aria-hidden="true"
                        >{{ def.emoji }}</span
                    >
                    <div class="min-w-0 flex-1">
                        <DialogTitle
                            class="font-heading text-xl leading-tight font-semibold tracking-[-0.015em]"
                        >
                            {{ def.ten }}
                        </DialogTitle>
                        <DialogDescription
                            class="mt-0.5 flex min-w-0 items-center gap-2 text-sm text-muted-foreground"
                        >
                            <span
                                :class="
                                    cn(
                                        'size-2 shrink-0 rounded-full',
                                        trangThai.st === 'working'
                                            ? 'bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,.18)]'
                                            : trangThai.st === 'sleep'
                                              ? 'bg-muted-foreground/40'
                                              : 'bg-amber-400',
                                    )
                                "
                            />
                            <span
                                class="truncate"
                                data-testid="nha-ban-status"
                                >{{ trangThai.text }}</span
                            >
                            <span
                                class="hidden text-muted-foreground/60 md:inline"
                                >·</span
                            >
                            <span class="hidden truncate md:inline">{{
                                def.mo_ta
                            }}</span>
                        </DialogDescription>
                    </div>
                    <div class="flex shrink-0 items-center gap-1.5">
                        <button
                            type="button"
                            class="grid size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                            title="Bàn trước"
                            aria-label="Bàn trước"
                            data-testid="nha-ban-truoc"
                            @click="step(-1)"
                        >
                            <IconChevronLeft class="size-5" />
                        </button>
                        <button
                            type="button"
                            class="grid size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                            title="Bàn sau"
                            aria-label="Bàn sau"
                            data-testid="nha-ban-sau"
                            @click="step(1)"
                        >
                            <IconChevronRight class="size-5" />
                        </button>
                        <Link
                            v-if="def.full"
                            :href="def.full"
                            class="ml-1 inline-flex h-9 items-center gap-1.5 rounded-lg border bg-card px-3 text-sm font-medium transition-colors hover:bg-secondary"
                            data-testid="nha-ban-full"
                        >
                            Trang đầy đủ
                            <IconArrowUpRight class="size-4" />
                        </Link>
                        <button
                            type="button"
                            class="ml-1 grid size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                            aria-label="Đóng"
                            data-testid="nha-ban-dong"
                            @click="vai = null"
                        >
                            <IconX class="size-5" />
                        </button>
                    </div>
                </header>

                <div
                    class="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-5"
                >
                    <component :is="def.component" :key="vai" :data="data" />
                </div>
            </DialogContent>
        </DialogPortal>
    </DialogRoot>
</template>

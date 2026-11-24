<script setup lang="ts">
// Dải "Cần xử lý hôm nay" dưới lời chào ở trang Khu Tự Trị (cả bản 3D lẫn 2D): mỗi việc đang chờ anh là một chip (bấm là mở
// đúng bàn), hết việc thì hiện chip xanh "Hôm nay ổn" + bài kế tiếp. Kèm pill vàng khi hỏi trạng thái lỗi mà vẫn đang hiện số cũ.
// Khung ngoài của bản 3D là pointer-events-none (để chuột xuyên xuống cảnh 3D), nên mọi thứ bấm được ở đây phải có pointer-events-auto.
import {
    IconAlertTriangle,
    IconCircleCheck,
    IconLayoutDashboard,
    IconRefresh,
} from '@tabler/icons-vue';
import { computed } from 'vue';

import { DICH, type NhaData } from '@/components/fork/nha/types';
import { toneClasses } from '@/components/fork/shared/status';
import dayjs from '@/dayjs';
import { atHandle } from '@/lib/handle';
import { cn } from '@/lib/utils';

const props = defineProps<{
    data: NhaData | null;
    /** Lần hỏi gần nhất lỗi (mạng/máy chủ) nhưng vẫn còn số liệu cũ trên màn hình. */
    stale?: boolean;
    /** Đang hỏi lại (khoá nút "Thử lại"). */
    refreshing?: boolean;
    /** Nền trắng đặc cho bản 3D (đặt trên cảnh), bản 2D dùng nền thẻ. */
    glass?: boolean;
}>();
const emit = defineEmits<{ go: [key: string]; retry: [] }>();

// Việc về bài lỗi là đỏ (đang mất bài), còn lại là vàng (cần anh quyết nhưng chưa mất gì).
const DANGER = new Set(['buuta']);

const viec = computed(() =>
    Object.entries(props.data?.viec ?? {}).map(([key, v]) => ({
        key,
        text: v.tom_tat,
        ten: DICH[key]?.ten ?? key,
        tone: DANGER.has(key) ? ('danger' as const) : ('warn' as const),
    })),
);

const next = computed(() => props.data?.app?.next ?? null);

const frame = computed(() =>
    cn(
        'pointer-events-auto flex w-full flex-wrap items-center gap-1.5 rounded-xl border px-2 py-1.5',
        props.glass
            ? 'border-black/10 bg-white/95 text-neutral-800 shadow-md'
            : 'border-border bg-card shadow-sm',
    ),
);
// Khung kính luôn nền trắng (cả khi app ở giao diện tối) nên chip trên đó dùng bảng màu sáng.
const GLASS_CHIP = {
    danger: 'bg-red-50 text-red-700',
    warn: 'bg-amber-50 text-amber-800',
    success: 'bg-emerald-50 text-emerald-700',
    neutral: 'bg-neutral-100 text-neutral-600',
} as const;
const chipTone = (tone: keyof typeof GLASS_CHIP) =>
    props.glass ? GLASS_CHIP[tone] : toneClasses[tone].chip;
const chipBase =
    'inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-xs leading-tight font-medium whitespace-nowrap';
</script>

<template>
    <div class="flex w-full flex-col gap-1.5" data-testid="nha-viec-homnay">
        <div
            v-if="stale"
            :class="
                cn(
                    'pointer-events-auto flex w-fit max-w-full items-center gap-2 rounded-lg border px-3 py-1 text-xs font-medium',
                    toneClasses.warn.box,
                )
            "
            role="status"
            data-testid="nha-mat-ket-noi"
        >
            <IconAlertTriangle class="size-3.5 shrink-0" aria-hidden="true" />
            <span class="min-w-0">Mất kết nối, đang hiện số liệu cũ</span>
            <button
                type="button"
                class="inline-flex shrink-0 items-center gap-1 rounded-md bg-amber-500/20 px-2 py-0.5 font-medium hover:bg-amber-500/30 focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-60"
                :disabled="refreshing"
                @click="emit('retry')"
            >
                <IconRefresh
                    :class="cn('size-3', refreshing && 'animate-spin')"
                    aria-hidden="true"
                />
                Thử lại
            </button>
        </div>

        <div
            v-if="data"
            :class="frame"
            role="group"
            aria-label="Việc cần xử lý hôm nay"
        >
            <template v-if="viec.length">
                <span
                    class="shrink-0 px-1.5 text-xs font-medium whitespace-nowrap"
                    >Cần xử lý hôm nay ({{ viec.length }})</span
                >
                <button
                    v-for="v in viec"
                    :key="v.key"
                    type="button"
                    :title="`Mở bàn ${v.ten}`"
                    :class="
                        cn(
                            chipBase,
                            chipTone(v.tone),
                            'hover:brightness-95 focus-visible:outline-2 focus-visible:outline-ring',
                        )
                    "
                    :data-testid="`nha-viec-${v.key}`"
                    @click="emit('go', v.key)"
                >
                    <i
                        :class="
                            cn('size-1.5 rounded-full', toneClasses[v.tone].dot)
                        "
                        aria-hidden="true"
                    />
                    {{ v.text }}
                </button>
            </template>
            <template v-else>
                <span
                    :class="cn(chipBase, chipTone('success'))"
                    data-testid="nha-viec-on"
                >
                    <IconCircleCheck class="size-3.5" aria-hidden="true" />
                    Hôm nay ổn, không có việc cần xử lý
                </span>
                <span
                    v-if="next"
                    :class="cn(chipBase, chipTone('neutral'))"
                    data-testid="nha-viec-ke-tiep"
                >
                    Bài kế tiếp {{ dayjs(next.at).format('HH:mm')
                    }}<template v-if="next.channel">
                        · {{ atHandle(next.channel) }}</template
                    >
                </span>
            </template>
            <button
                type="button"
                :class="
                    cn(
                        chipBase,
                        'ml-auto border focus-visible:outline-2 focus-visible:outline-ring',
                        glass
                            ? 'border-black/10 bg-white hover:bg-neutral-100'
                            : 'border-border/70 bg-background/70 hover:bg-accent',
                    )
                "
                data-testid="nha-mo-bang-tin"
                @click="emit('go', 'sanh')"
            >
                <IconLayoutDashboard class="size-3.5" aria-hidden="true" />
                Mở bảng tin
            </button>
        </div>
    </div>
</template>

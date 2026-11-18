<script setup lang="ts">
// Hộp "Đổi giờ" cho một bài đã xếp lịch mà chưa đăng (Lịch đăng). Bài chưa lên TikTok: đổi ngay. Bài đã hẹn trên TikTok:
// TikTok không cho sửa giờ hẹn, nên app nhờ Chrome xoá hẳn bài hẹn cũ, kiểm lại rồi mới tải lên lại với giờ mới.
import { router } from '@inertiajs/vue3';
import {
    IconBrandTiktok,
    IconCircleCheck,
    IconClockEdit,
    IconInfoCircle,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';

import type {
    RescheduleInfo,
    ScheduleEntry,
} from '@/components/fork/auto/types';
import { moveWithUndo } from '@/components/fork/auto/undo';
import DateTimePicker from '@/components/fork/shared/DateTimePicker.vue';
import { toneClasses } from '@/components/fork/shared/status';
import { timeNotice } from '@/components/fork/shared/timeNotice';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    entry: ScheduleEntry | null;
    /** Giờ gợi ý khi kéo thả bài sang chỗ mới (ISO); không có thì lấy giờ hiện tại của bài. */
    proposed?: string | null;
}>();
const open = defineModel<boolean>('open', { default: false });

const FORMAT = 'YYYY-MM-DDTHH:mm';
const info = ref<RescheduleInfo | null>(null);
const loading = ref(false);
const busy = ref(false);
const value = ref('');
const problem = ref('');
const success = ref('');
const changed = ref(false);
const nowTick = ref(Date.now());
const clock = setInterval(() => (nowTick.value = Date.now()), 30000);
let timer: ReturnType<typeof setTimeout> | null = null;
let pollUntil = 0;

const url = computed(() =>
    props.entry?.id ? `/auto/videos/${props.entry.id}/doi-gio` : '',
);

const req = computed(() => info.value?.request ?? null);
const waiting = computed(() => !!req.value?.open);
const isTikTok = computed(
    () =>
        info.value?.kind === 'tiktok' ||
        props.entry?.state === 'tiktok_scheduled',
);
const minValue = computed(() => {
    const lead = info.value?.rules.min_lead_minutes ?? 20;
    const m = dayjs().add(lead + 1, 'minute');

    return m
        .minute(Math.ceil(m.minute() / 5) * 5)
        .second(0)
        .format(FORMAT);
});
const rulesText = computed(() => {
    const r = info.value?.rules;

    return r
        ? `Sớm nhất sau ${r.min_lead_minutes} phút, xa nhất ${Math.floor(r.max_ahead_hours / 24)} ngày.`
        : '';
});
const notice = computed(() =>
    unchanged.value
        ? null
        : timeNotice(
              value.value,
              info.value?.channel_times ?? [],
              nowTick.value,
          ),
);

const stop = () => {
    if (timer) {
        clearTimeout(timer);
        timer = null;
    }
};

async function load(): Promise<RescheduleInfo | null> {
    if (!url.value) {
        return null;
    }

    try {
        const r = await fetch(url.value, {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });

        if (!r.ok) {
            problem.value = 'Không tải được thông tin bài, hãy thử lại.';

            return null;
        }

        return (await r.json()) as RescheduleInfo;
    } catch {
        problem.value = 'Mất kết nối với app, hãy thử lại.';

        return null;
    }
}

const settle = () => {
    const r = req.value;

    if (!r || r.open) {
        return;
    }

    changed.value = true;

    if (r.state === 'done') {
        success.value = r.message;
        problem.value = '';
    } else {
        problem.value = r.message;
    }
};

const poll = () => {
    stop();
    timer = setTimeout(async () => {
        const next = await load();

        if (next) {
            info.value = next;
        }

        if (waiting.value && Date.now() < pollUntil && open.value) {
            poll();
        } else {
            settle();
        }
    }, 3000);
};

watch(open, async (v) => {
    stop();

    if (!v) {
        if (changed.value) {
            router.reload({ only: ['lich'] });
        }

        return;
    }

    info.value = null;
    problem.value = '';
    success.value = '';
    changed.value = false;
    loading.value = true;
    info.value = await load();
    loading.value = false;
    const cur = props.proposed ?? info.value?.current_at ?? props.entry?.at;
    value.value = cur ? dayjs(cur).format(FORMAT) : '';

    if (waiting.value) {
        pollUntil = Date.now() + 17 * 60 * 1000;
        poll();
    }
});

onBeforeUnmount(() => {
    stop();
    clearInterval(clock);
});

const unchanged = computed(() => {
    const cur = info.value?.current_at;

    return !value.value || (!!cur && dayjs(cur).format(FORMAT) === value.value);
});

// Đổi giờ có "Hoàn tác": hộp đóng ngay, vài giây sau mới gửi đi (bấm "Hoàn tác" là không đổi gì).
function save() {
    if (!url.value || unchanged.value) {
        return;
    }

    const at = dayjs(value.value).toISOString();
    open.value = false;
    void moveWithUndo(props.entry ?? {}, at, () =>
        router.reload({ only: ['lich'] }),
    );
}
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent
            class="sm:max-w-[520px]"
            data-testid="fork-auto-reschedule"
        >
            <DialogHeader>
                <DialogTitle class="flex items-center gap-2"
                    ><IconClockEdit class="size-5 text-muted-foreground" />Đổi
                    giờ đăng</DialogTitle
                >
                <DialogDescription>
                    {{ entry?.product_label ?? entry?.product_code ?? 'Bài'
                    }}<template v-if="entry?.username">
                        · @{{ entry.username }}</template
                    >
                    <template v-if="info?.current_at">
                        · đang hẹn
                        {{
                            dayjs(info.current_at).format('HH:mm DD/MM')
                        }}</template
                    >
                </DialogDescription>
            </DialogHeader>

            <div
                v-if="loading"
                class="flex items-center gap-2 py-6 text-sm text-muted-foreground"
            >
                <Spinner class="size-4" />Đang tải…
            </div>

            <div v-else class="grid gap-4">
                <p
                    v-if="isTikTok"
                    :class="
                        cn(
                            'flex gap-2 rounded-xl border px-3.5 py-3 text-[0.8125rem] leading-relaxed',
                            toneClasses.info.box,
                        )
                    "
                    data-testid="fork-auto-reschedule-tiktok"
                >
                    <IconBrandTiktok class="mt-0.5 size-4 shrink-0" />
                    <span>
                        <b>Đã hẹn trên TikTok:</b> app xoá bài hẹn cũ, kiểm lại
                        rồi hẹn giờ mới (cần Chrome đang mở). Không xoá được thì
                        giữ nguyên.
                    </span>
                </p>

                <p
                    v-if="info && !info.kind && !waiting && !success"
                    :class="
                        cn(
                            'rounded-xl border px-3.5 py-3 text-[0.8125rem]',
                            toneClasses.warn.box,
                        )
                    "
                >
                    {{ info.reason }}
                </p>

                <label
                    v-if="info?.kind && !waiting && !success"
                    class="flex flex-col gap-1.5 text-sm"
                >
                    <span class="font-medium">Giờ mới</span>
                    <DateTimePicker
                        v-model="value"
                        :min="minValue"
                        testid="fork-auto-reschedule-at"
                        aria-label="Giờ đăng mới"
                    />
                    <span class="flex gap-1.5 text-xs text-muted-foreground"
                        ><IconInfoCircle class="mt-px size-3.5 shrink-0" />{{
                            rulesText
                        }}</span
                    >
                    <span
                        v-if="notice"
                        :class="
                            cn(
                                'rounded-lg border px-2.5 py-2 text-xs leading-relaxed',
                                notice.tight
                                    ? toneClasses.warn.box
                                    : 'border-border bg-muted/40 text-muted-foreground',
                            )
                        "
                        data-testid="fork-auto-reschedule-notice"
                        aria-live="polite"
                    >
                        <span class="block">{{ notice.fromNow }}</span>
                        <span
                            v-if="notice.before || notice.after"
                            class="block"
                            >{{
                                [notice.before, notice.after]
                                    .filter(Boolean)
                                    .join(' · ')
                            }}</span
                        >
                    </span>
                </label>

                <div
                    v-if="waiting"
                    :class="
                        cn(
                            'flex items-center gap-2.5 rounded-xl border px-3.5 py-3 text-[0.8125rem]',
                            toneClasses.info.box,
                        )
                    "
                    data-testid="fork-auto-reschedule-waiting"
                    aria-live="polite"
                >
                    <Spinner class="size-4 shrink-0" />
                    <span>
                        <b>Đang xoá bài hẹn cũ trên TikTok…</b>
                        <span class="block text-muted-foreground"
                            >{{ req?.message
                            }}<template v-if="req?.new_at">
                                Giờ mới:
                                {{
                                    dayjs(req.new_at).format('HH:mm DD/MM')
                                }}.</template
                            ></span
                        >
                    </span>
                </div>

                <p
                    v-if="success"
                    :class="
                        cn(
                            'flex gap-2 rounded-xl border px-3.5 py-3 text-[0.8125rem]',
                            toneClasses.success.box,
                        )
                    "
                    data-testid="fork-auto-reschedule-ok"
                    aria-live="polite"
                >
                    <IconCircleCheck class="mt-0.5 size-4 shrink-0" />{{
                        success
                    }}
                </p>
                <p
                    v-if="problem"
                    :class="
                        cn(
                            'rounded-xl border px-3.5 py-3 text-[0.8125rem]',
                            toneClasses.danger.box,
                        )
                    "
                    data-testid="fork-auto-reschedule-error"
                    aria-live="polite"
                >
                    {{ problem }}
                </p>
            </div>

            <DialogFooter class="gap-2">
                <Button variant="ghost" @click="open = false">{{
                    success || waiting ? 'Đóng' : 'Huỷ'
                }}</Button>
                <Button
                    v-if="info?.kind && !waiting && !success"
                    :disabled="busy || unchanged"
                    data-testid="fork-auto-reschedule-save"
                    @click="save"
                >
                    <Spinner v-if="busy" class="size-4" />
                    {{ isTikTok ? 'Xoá bài hẹn cũ và đổi giờ' : 'Đổi giờ' }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

<script setup lang="ts">
// Chọn ngày giờ: lịch (tuần bắt đầu từ Thứ Hai) + cột giờ/phút 24h, thay cho ô datetime-local của trình duyệt.
// Giá trị là chuỗi "YYYY-MM-DDTHH:mm" theo giờ máy (giống datetime-local nên chỗ dùng cũ không phải đổi).
// Không cho chọn quá khứ (mặc định "min" là giờ hiện tại). Bàn phím: mũi tên di chuyển ngày, Home/End đầu/cuối tuần,
// PageUp/PageDown đổi tháng, Enter chọn; cột giờ/phút dùng ↑/↓; ô "Giờ" gõ tay được (ví dụ 20:30).
import {
    IconCalendarEvent,
    IconChevronDown,
    IconChevronLeft,
    IconChevronRight,
} from '@tabler/icons-vue';
import { computed, nextTick, ref, watch } from 'vue';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

type D = ReturnType<typeof dayjs>;

const FORMAT = 'YYYY-MM-DDTHH:mm';

const props = withDefaults(
    defineProps<{
        modelValue: string;
        /** Giá trị nhỏ nhất (cùng định dạng). Bỏ trống = không chọn quá khứ (tính từ lúc mở). */
        min?: string;
        placeholder?: string;
        disabled?: boolean;
        class?: string;
        testid?: string;
        id?: string;
        ariaLabel?: string;
    }>(),
    {
        min: undefined,
        placeholder: 'Chọn ngày và giờ',
        disabled: false,
        class: undefined,
        testid: undefined,
        id: undefined,
        ariaLabel: undefined,
    },
);

const emit = defineEmits<{ 'update:modelValue': [value: string] }>();

const open = ref(false);
/** "Bây giờ" được chốt lúc mở hộp để lịch không nhảy khi đang chọn. */
const now = ref(dayjs());
const minDt = computed<D>(() => {
    if (props.min) {
        const m = dayjs(props.min);

        if (m.isValid()) {
            return m;
        }
    }

    // Mặc định: giờ hiện tại làm tròn lên bội số 5 phút (ví dụ 15:28 thì sớm nhất 15:30).
    const n = now.value.second(0).millisecond(0);
    const rest = n.minute() % 5;

    return rest === 0 && now.value.second() === 0 ? n : n.add(5 - rest, 'minute');
});

const value = computed<D | null>(() => {
    const d = props.modelValue ? dayjs(props.modelValue) : null;

    return d && d.isValid() ? d : null;
});

const label = computed(() =>
    value.value ? value.value.format('HH:mm · DD/MM/YYYY') : '',
);
const past = computed(
    () => !!value.value && value.value.isBefore(dayjs().startOf('minute')),
);

const view = ref<D>(dayjs().startOf('month'));
const focusDay = ref<D>(dayjs().startOf('day'));
const timeText = ref('');
const calEl = ref<HTMLElement | null>(null);
const hourEl = ref<HTMLElement | null>(null);
const minuteEl = ref<HTMLElement | null>(null);

const weekdays = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
const monthTitle = computed(() => {
    const t = view.value.format('MMMM YYYY');

    return t.charAt(0).toUpperCase() + t.slice(1);
});

/** 6 tuần x 7 ngày, bắt đầu từ Thứ Hai. */
const cells = computed<D[]>(() => {
    const first = view.value.startOf('month');
    const start = first.subtract((first.day() + 6) % 7, 'day');

    return Array.from({ length: 42 }, (_, i) => start.add(i, 'day'));
});

const dayDisabled = (d: D) => d.endOf('day').isBefore(minDt.value);
const sameDay = (a: D | null, b: D) => !!a && a.isSame(b, 'day');
const isToday = (d: D) => d.isSame(dayjs(), 'day');

/** Giờ mặc định khi chọn một ngày mà chưa có giờ: 08:00, hoặc phút làm tròn lên 5 phút nếu là hôm nay/ngày tối thiểu. */
const defaultTime = (day: D): D => {
    const base = day.hour(8).minute(0).second(0).millisecond(0);

    if (!base.isBefore(minDt.value)) {
        return base;
    }

    const m = minDt.value;
    const up = Math.ceil(m.minute() / 5) * 5;

    return m.minute(0).add(up, 'minute').second(0).millisecond(0);
};

const clampMin = (d: D): D => (d.isBefore(minDt.value) ? minDt.value : d);

const commit = (d: D) => {
    const next = clampMin(d).second(0).millisecond(0).format(FORMAT);

    if (next !== props.modelValue) {
        emit('update:modelValue', next);
    }
};

const pickDay = (d: D) => {
    if (dayDisabled(d)) {
        return;
    }

    const cur = value.value;
    commit(
        cur
            ? d.hour(cur.hour()).minute(cur.minute())
            : defaultTime(d),
    );
    focusDay.value = d;

    if (d.month() !== view.value.month() || d.year() !== view.value.year()) {
        view.value = d.startOf('month');
    }
};

const goMonth = (n: number) => {
    view.value = view.value.add(n, 'month').startOf('month');
};
const prevDisabled = computed(() =>
    view.value.startOf('month').isBefore(minDt.value.startOf('month')) ||
    view.value.startOf('month').isSame(minDt.value.startOf('month')),
);

// ---- Giờ / phút ----
const hours = Array.from({ length: 24 }, (_, i) => i);
const minutes = Array.from({ length: 12 }, (_, i) => i * 5);
const hh = (n: number) => String(n).padStart(2, '0');

const hourDisabled = (h: number) => {
    const v = value.value;

    return !!v && v.hour(h).minute(59).isBefore(minDt.value);
};
const minuteDisabled = (m: number) => {
    const v = value.value;

    return !!v && v.minute(m).isBefore(minDt.value);
};

const pickHour = (h: number) => {
    const v = value.value ?? defaultTime(focusDay.value);

    commit(v.hour(h));
};
const pickMinute = (m: number) => {
    const v = value.value ?? defaultTime(focusDay.value);

    commit(v.minute(m));
};

/** ↑/↓ trong cột giờ hoặc phút: chọn mục liền kề (bỏ qua mục bị khoá). */
const onListKey = (e: KeyboardEvent, kind: 'h' | 'm') => {
    const list = kind === 'h' ? hours : minutes;
    const dis = kind === 'h' ? hourDisabled : minuteDisabled;
    const cur = value.value ? (kind === 'h' ? value.value.hour() : value.value.minute()) : -1;
    const dir = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0;

    if (!dir) {
        return;
    }

    e.preventDefault();
    let i = list.findIndex((x) => x === cur);

    if (i < 0) {
        i = dir > 0 ? -1 : list.length;
    }

    for (i += dir; i >= 0 && i < list.length; i += dir) {
        if (!dis(list[i])) {
            (kind === 'h' ? pickHour : pickMinute)(list[i]);
            void nextTick(() => {
                const root = kind === 'h' ? hourEl.value : minuteEl.value;
                const el = root?.querySelector<HTMLElement>(`[data-v="${list[i]}"]`);
                el?.focus();
                el?.scrollIntoView({ block: 'nearest' });
            });

            return;
        }
    }
};

const commitTimeText = () => {
    const m = /^\s*(\d{1,2})\s*(?:[:h.]\s*(\d{1,2})?)?\s*$/i.exec(timeText.value);

    if (!m) {
        timeText.value = value.value?.format('HH:mm') ?? '';

        return;
    }

    const h = Math.min(23, Number(m[1]));
    const mi = Math.min(59, Number(m[2] ?? 0));
    const base = value.value ?? defaultTime(focusDay.value);
    commit(base.hour(h).minute(mi));
    timeText.value = (value.value?.format('HH:mm')) ?? '';
};

watch(
    () => props.modelValue,
    () => {
        timeText.value = value.value?.format('HH:mm') ?? '';
    },
    { immediate: true },
);

// ---- Gợi ý nhanh ----
const presets = computed(() => {
    const n = dayjs();
    const list: { t: string; d: D }[] = [
        { t: 'Sau 1 giờ', d: n.add(1, 'hour').minute(0).second(0).millisecond(0) },
        { t: 'Tối nay 20:00', d: n.hour(20).minute(0).second(0).millisecond(0) },
        { t: 'Sáng mai 08:00', d: n.add(1, 'day').hour(8).minute(0).second(0).millisecond(0) },
    ];

    return list.filter((p) => !p.d.isBefore(minDt.value));
});

const usePreset = (d: D) => {
    commit(d);
    view.value = d.startOf('month');
    focusDay.value = d.startOf('day');
};

// ---- Mở / bàn phím lịch ----
watch(open, (isOpen) => {
    if (!isOpen) {
        return;
    }

    now.value = dayjs();
    const base = value.value ?? clampMin(dayjs());
    view.value = base.startOf('month');
    focusDay.value = base.startOf('day');
    void nextTick(() => {
        for (const root of [hourEl.value, minuteEl.value]) {
            root?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'center' });
        }
    });
});

const focusCell = async () => {
    await nextTick();
    calEl.value
        ?.querySelector<HTMLElement>(`[data-date="${focusDay.value.format('YYYY-MM-DD')}"]`)
        ?.focus();
};

const onOpenFocus = (e: Event) => {
    e.preventDefault();
    void focusCell();
};

const onCalKey = (e: KeyboardEvent) => {
    const step: Record<string, [number, 'day' | 'month' | 'year']> = {
        ArrowLeft: [-1, 'day'],
        ArrowRight: [1, 'day'],
        ArrowUp: [-7, 'day'],
        ArrowDown: [7, 'day'],
        PageUp: [-1, e.shiftKey ? 'year' : 'month'],
        PageDown: [1, e.shiftKey ? 'year' : 'month'],
    };
    let next: D | null = null;

    if (step[e.key]) {
        next = focusDay.value.add(step[e.key][0], step[e.key][1]);
    } else if (e.key === 'Home') {
        next = focusDay.value.subtract((focusDay.value.day() + 6) % 7, 'day');
    } else if (e.key === 'End') {
        next = focusDay.value.add(6 - ((focusDay.value.day() + 6) % 7), 'day');
    }

    if (!next) {
        return;
    }

    e.preventDefault();

    // Không đi lùi quá ngày tối thiểu.
    if (next.endOf('day').isBefore(minDt.value)) {
        next = minDt.value.startOf('day');
    }

    focusDay.value = next.startOf('day');

    if (next.month() !== view.value.month() || next.year() !== view.value.year()) {
        view.value = next.startOf('month');
    }

    void focusCell();
};
</script>

<template>
    <Popover v-model:open="open">
        <PopoverTrigger as-child>
            <button
                :id="id"
                type="button"
                :disabled="disabled"
                :aria-label="ariaLabel"
                :aria-invalid="past || undefined"
                :data-testid="testid"
                :class="
                    cn(
                        'dark:bg-input/30 flex h-10 w-full min-w-0 cursor-pointer items-center gap-2 rounded-md border border-input bg-card px-3 text-left text-sm transition-[color,box-shadow] outline-none',
                        'hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring',
                        'disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive',
                        'data-[state=open]:border-ring data-[state=open]:outline-2 data-[state=open]:outline-offset-1 data-[state=open]:outline-ring',
                        props.class,
                    )
                "
            >
                <IconCalendarEvent class="size-4 shrink-0 text-muted-foreground" />
                <span
                    :class="
                        cn(
                            'min-w-0 flex-1 truncate tabular-nums',
                            !label && 'text-subtle-foreground',
                        )
                    "
                >
                    {{ label || placeholder }}
                </span>
                <IconChevronDown class="size-4 shrink-0 text-muted-foreground" />
            </button>
        </PopoverTrigger>

        <PopoverContent
            class="w-[19.5rem] sm:w-[27rem]"
            data-testid="fork-datetime-popover"
            @open-auto-focus="onOpenFocus"
        >
            <div class="flex flex-col sm:flex-row">
                <!-- Lịch -->
                <div class="flex flex-col gap-2 p-3 sm:w-[16.5rem]">
                    <div class="flex items-center justify-between gap-1">
                        <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            aria-label="Tháng trước"
                            :disabled="prevDisabled"
                            @click="goMonth(-1)"
                        >
                            <IconChevronLeft class="size-4" />
                        </Button>
                        <span
                            class="text-sm font-semibold"
                            aria-live="polite"
                            >{{ monthTitle }}</span
                        >
                        <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            aria-label="Tháng sau"
                            @click="goMonth(1)"
                        >
                            <IconChevronRight class="size-4" />
                        </Button>
                    </div>

                    <div
                        ref="calEl"
                        role="grid"
                        :aria-label="monthTitle"
                        class="grid grid-cols-7 gap-y-0.5"
                        @keydown="onCalKey"
                    >
                        <span
                            v-for="w in weekdays"
                            :key="w"
                            role="columnheader"
                            class="pb-1 text-center text-[11px] font-medium text-muted-foreground"
                            >{{ w }}</span
                        >
                        <button
                            v-for="d in cells"
                            :key="d.format('YYYY-MM-DD')"
                            type="button"
                            role="gridcell"
                            :data-date="d.format('YYYY-MM-DD')"
                            :tabindex="sameDay(focusDay, d) ? 0 : -1"
                            :aria-selected="sameDay(value, d)"
                            :aria-disabled="dayDisabled(d) || undefined"
                            :aria-label="d.format('dddd, D [tháng] M [năm] YYYY')"
                            :aria-current="isToday(d) ? 'date' : undefined"
                            :class="
                                cn(
                                    'mx-auto flex size-8 items-center justify-center rounded-lg text-sm tabular-nums transition-colors outline-none',
                                    'focus-visible:ring-2 focus-visible:ring-ring',
                                    d.month() !== view.month() && 'text-subtle-foreground',
                                    !dayDisabled(d) && !sameDay(value, d) && 'hover:bg-accent',
                                    isToday(d) && !sameDay(value, d) && 'font-semibold text-primary-text ring-1 ring-primary/50',
                                    sameDay(value, d) && 'bg-primary-strong font-semibold text-primary-strong-foreground dark:bg-primary dark:text-primary-foreground',
                                    dayDisabled(d) && 'cursor-not-allowed text-subtle-foreground/50 line-through decoration-transparent',
                                )
                            "
                            @click="pickDay(d)"
                        >
                            {{ d.date() }}
                        </button>
                    </div>
                </div>

                <!-- Giờ -->
                <div
                    class="flex flex-col gap-2 border-t p-3 sm:w-[10.5rem] sm:border-t-0 sm:border-l"
                >
                    <label class="flex items-center justify-between gap-2 text-sm font-medium">
                        Giờ
                        <input
                            v-model="timeText"
                            type="text"
                            inputmode="numeric"
                            maxlength="5"
                            placeholder="HH:mm"
                            aria-label="Giờ và phút, ví dụ 20:30"
                            class="h-8 w-[4.5rem] rounded-md border border-input bg-card px-2 text-center text-sm tabular-nums outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            data-testid="fork-datetime-time"
                            @keydown.enter.prevent="commitTimeText"
                            @blur="commitTimeText"
                        />
                    </label>
                    <div class="grid grid-cols-2 gap-1.5">
                        <div
                            ref="hourEl"
                            role="listbox"
                            aria-label="Giờ"
                            class="flex max-h-44 flex-col gap-0.5 overflow-y-auto rounded-lg bg-muted/40 p-1 sm:max-h-52"
                            @keydown="onListKey($event, 'h')"
                        >
                            <button
                                v-for="h in hours"
                                :key="h"
                                type="button"
                                role="option"
                                :data-v="h"
                                :aria-selected="value?.hour() === h"
                                :aria-disabled="hourDisabled(h) || undefined"
                                :tabindex="value?.hour() === h || (!value && h === 8) ? 0 : -1"
                                :class="
                                    cn(
                                        'rounded-md py-1 text-center text-sm tabular-nums transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring',
                                        value?.hour() === h
                                            ? 'bg-primary-strong font-semibold text-primary-strong-foreground dark:bg-primary dark:text-primary-foreground'
                                            : 'hover:bg-accent',
                                        hourDisabled(h) && 'pointer-events-none text-subtle-foreground/50',
                                    )
                                "
                                @click="pickHour(h)"
                            >
                                {{ hh(h) }}
                            </button>
                        </div>
                        <div
                            ref="minuteEl"
                            role="listbox"
                            aria-label="Phút"
                            class="flex max-h-44 flex-col gap-0.5 overflow-y-auto rounded-lg bg-muted/40 p-1 sm:max-h-52"
                            @keydown="onListKey($event, 'm')"
                        >
                            <button
                                v-for="m in minutes"
                                :key="m"
                                type="button"
                                role="option"
                                :data-v="m"
                                :aria-selected="value?.minute() === m"
                                :aria-disabled="minuteDisabled(m) || undefined"
                                :tabindex="value?.minute() === m || (!value && m === 0) ? 0 : -1"
                                :class="
                                    cn(
                                        'rounded-md py-1 text-center text-sm tabular-nums transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring',
                                        value?.minute() === m
                                            ? 'bg-primary-strong font-semibold text-primary-strong-foreground dark:bg-primary dark:text-primary-foreground'
                                            : 'hover:bg-accent',
                                        minuteDisabled(m) && 'pointer-events-none text-subtle-foreground/50',
                                    )
                                "
                                @click="pickMinute(m)"
                            >
                                {{ hh(m) }}
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div
                class="flex flex-wrap items-center justify-between gap-2 border-t bg-muted/30 px-3 py-2.5"
            >
                <div class="flex flex-wrap gap-1.5">
                    <button
                        v-for="p in presets"
                        :key="p.t"
                        type="button"
                        class="rounded-full border bg-background px-2.5 py-1 text-xs transition-colors hover:border-primary hover:bg-primary-subtle hover:text-primary-text focus-visible:outline-2 focus-visible:outline-ring"
                        @click="usePreset(p.d)"
                    >
                        {{ p.t }}
                    </button>
                </div>
                <Button
                    type="button"
                    size="sm"
                    data-testid="fork-datetime-done"
                    :disabled="!value"
                    @click="open = false"
                >
                    Xong
                </Button>
            </div>
        </PopoverContent>
    </Popover>
</template>

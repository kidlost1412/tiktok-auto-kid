<script setup lang="ts">
// Hộp "Chỉnh kênh": hạn mức, khung giờ, hẹn trước, chế độ giờ đăng và giờ đề xuất — gom vào một chỗ
// để thẻ kênh ngoài trang chỉ còn những gì cần nhìn hằng ngày.
import { router } from '@inertiajs/vue3';
import {
    IconArrowsShuffle,
    IconCalendarClock,
    IconClock,
} from '@tabler/icons-vue';
import { computed, reactive, ref, watch } from 'vue';

import MixDialog from '@/components/fork/auto/MixDialog.vue';
import type { AccountRow } from '@/components/fork/auto/types';
import { fmtNum } from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

const props = defineProps<{ account: AccountRow; inPlace?: boolean }>();
const emit = defineEmits<{ changed: [] }>();
const open = defineModel<boolean>('open', { default: false });

interface Draft {
    daily_cap: number;
    window_start: number;
    window_end: number;
    schedule_ahead_days: number;
    mode: 'explore' | 'optimized';
    video_source: 'both' | 'rieng' | 'hub';
    mix_products: boolean;
}

const fromAccount = (): Draft => ({
    daily_cap: props.account.daily_cap,
    window_start: props.account.window_start,
    window_end: props.account.window_end,
    schedule_ahead_days: props.account.schedule_ahead_days ?? 3,
    mode: props.account.mode,
    video_source: props.account.video_source ?? 'both',
    mix_products: props.account.mix_products ?? false,
});

const draft = reactive<Draft>(fromAccount());

// Mỗi lần mở lại hộp thì lấy số mới nhất từ máy chủ (bỏ phần sửa dở lần trước).
watch(open, (v) => {
    if (v) {
        Object.assign(draft, fromAccount());
    }
});

const dirty = computed(() => {
    const a = fromAccount();

    return (Object.keys(a) as (keyof Draft)[]).some((k) => a[k] !== draft[k]);
});

const windowBad = computed(() => draft.window_end <= draft.window_start);
const capBad = computed(
    () =>
        !Number.isFinite(draft.daily_cap) ||
        draft.daily_cap < 1 ||
        draft.daily_cap > 100,
);

const hours = Array.from({ length: 24 }, (_, i) => i);
const ends = hours.slice(1).concat(24);
const aheads = Array.from({ length: 9 }, (_, i) => i + 1);

const busy = ref(false);
const mixOpen = ref(false);

const save = () => {
    if (windowBad.value || capBad.value) {
        return;
    }

    const a = fromAccount();
    const changed = Object.fromEntries(
        (Object.keys(a) as (keyof Draft)[])
            .filter((k) => a[k] !== draft[k])
            .map((k) => [k, draft[k]]),
    );
    busy.value = true;
    router.patch(`/auto/accounts/${props.account.id}`, changed, {
        preserveScroll: true,
        ...(props.inPlace ? { preserveState: true } : {}),
        onSuccess: () => {
            open.value = false;

            if (props.inPlace) {
                emit('changed');
            }
        },
        onFinish: () => {
            busy.value = false;
        },
    });
};

const applyHours = () => {
    busy.value = true;
    router.post(
        `/auto/accounts/${props.account.id}/apply-hours`,
        {},
        {
            preserveScroll: true,
            ...(props.inPlace ? { preserveState: true } : {}),
            onSuccess: () => {
                if (props.inPlace) {
                    emit('changed');
                }
            },
            onFinish: () => {
                busy.value = false;
            },
        },
    );
};

const sourceHint = computed(() =>
    draft.video_source === 'rieng'
        ? `Cả ${draft.daily_cap || 0} bài/ngày dành cho video Kho riêng; app không lấy video Xưởng cho kênh này. Bài Xưởng đã hẹn trước đó vẫn giữ.`
        : draft.video_source === 'hub'
          ? 'Chỉ đăng video Xưởng tự tạo; Kho riêng tự đăng bỏ qua kênh này (vẫn tự rải lịch Kho riêng bằng tay được).'
          : 'Video Kho riêng sẵn sàng được đăng trước, chỗ còn lại lấy video Xưởng.',
);

const rec = computed(() => props.account.recommendation);
const fieldCls = 'flex flex-col gap-1.5 text-sm';
const labelCls = 'font-medium text-foreground';
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent
            class="sm:max-w-[560px]"
            :data-testid="`fork-auto-settings-${account.id}`"
        >
            <DialogHeader>
                <DialogTitle
                    >Chỉnh kênh @{{
                        account.username ?? account.display_name ?? '—'
                    }}</DialogTitle
                >
                <DialogDescription
                    >Thay đổi áp dụng cho các lần xếp lịch tiếp theo; bài đã hẹn
                    giữ nguyên giờ.</DialogDescription
                >
            </DialogHeader>

            <div class="grid gap-5">
                <div class="grid grid-cols-2 gap-4">
                    <label :class="fieldCls">
                        <span :class="labelCls">Số bài mỗi ngày</span>
                        <Input
                            v-model.number="draft.daily_cap"
                            type="number"
                            min="1"
                            max="100"
                            inputmode="numeric"
                            :aria-invalid="capBad || undefined"
                        />
                        <span
                            v-if="capBad"
                            class="text-xs text-destructive-text"
                            >Từ 1 đến 100 bài</span
                        >
                    </label>
                    <label :class="fieldCls">
                        <span :class="cn(labelCls, 'flex items-center gap-1.5')"
                            ><IconCalendarClock
                                class="size-4 text-muted-foreground"
                            />Hẹn trước</span
                        >
                        <NativeSelect
                            v-model.number="draft.schedule_ahead_days"
                            class="w-full"
                            :data-testid="`fork-auto-ahead-${account.id}`"
                        >
                            <option v-for="d in aheads" :key="d" :value="d">
                                {{ d }} ngày
                            </option>
                        </NativeSelect>
                    </label>
                    <label :class="fieldCls">
                        <span :class="labelCls">Đăng từ</span>
                        <NativeSelect
                            v-model.number="draft.window_start"
                            class="w-full"
                        >
                            <option v-for="h in hours" :key="h" :value="h">
                                {{ String(h).padStart(2, '0') }}:00
                            </option>
                        </NativeSelect>
                    </label>
                    <label :class="fieldCls">
                        <span :class="labelCls">Đến</span>
                        <NativeSelect
                            v-model.number="draft.window_end"
                            class="w-full"
                            :aria-invalid="windowBad || undefined"
                        >
                            <option v-for="h in ends" :key="h" :value="h">
                                {{
                                    h === 24
                                        ? '24:00'
                                        : `${String(h).padStart(2, '0')}:00`
                                }}
                            </option>
                        </NativeSelect>
                    </label>
                    <p
                        v-if="windowBad"
                        class="col-span-2 -mt-2 text-xs text-destructive-text"
                    >
                        Giờ kết thúc phải sau giờ bắt đầu
                    </p>
                </div>

                <label :class="fieldCls">
                    <span :class="labelCls">Nguồn video</span>
                    <NativeSelect
                        v-model="draft.video_source"
                        class="w-full"
                        :data-testid="`fork-auto-source-${account.id}`"
                    >
                        <option value="both">
                            Xưởng + Kho riêng (Kho riêng ưu tiên trước)
                        </option>
                        <option value="rieng">Chỉ Kho riêng</option>
                        <option value="hub">Chỉ Xưởng (video tự tạo)</option>
                    </NativeSelect>
                    <span class="text-xs text-muted-foreground">{{
                        sourceHint
                    }}</span>
                </label>

                <div
                    class="grid gap-2 rounded-xl border p-4"
                    data-testid="fork-auto-mix-setting"
                >
                    <label class="flex items-start justify-between gap-3">
                        <span class="grid gap-0.5">
                            <span
                                :class="
                                    cn(labelCls, 'flex items-center gap-1.5')
                                "
                                ><IconArrowsShuffle
                                    class="size-4 text-muted-foreground"
                                />Tự trộn xen kẽ sản phẩm</span
                            >
                            <span class="text-xs text-muted-foreground">
                                Bài đã xếp lịch mà chưa gửi lên TikTok được đổi
                                chỗ giờ cho nhau để hai bài liền nhau khác sản
                                phẩm (vd. A, B, C, A, B…). Bài anh tự chỉnh giờ
                                và bài đã lên TikTok giữ nguyên.
                            </span>
                        </span>
                        <Switch
                            v-model="draft.mix_products"
                            :data-testid="`fork-auto-mix-${account.id}`"
                        />
                    </label>
                    <button
                        type="button"
                        class="justify-self-start text-xs font-medium text-primary-text underline-offset-4 hover:underline"
                        @click="mixOpen = true"
                    >
                        Xem trước và trộn ngay một lần…
                    </button>
                </div>

                <p
                    class="rounded-xl border bg-muted/50 px-4 py-3 text-[0.8125rem] leading-relaxed text-foreground"
                    data-testid="fork-auto-ahead-hint"
                >
                    Có video là app hẹn sẵn lên TikTok cho
                    <b>{{ draft.schedule_ahead_days }} ngày tới</b> — tắt máy
                    vẫn đăng đúng giờ.
                </p>

                <div
                    class="grid gap-3 rounded-xl border bg-muted/40 p-4"
                    data-testid="fork-auto-recommend"
                >
                    <label :class="fieldCls">
                        <span :class="cn(labelCls, 'flex items-center gap-1.5')"
                            ><IconClock
                                class="size-4 text-muted-foreground"
                            />Chọn giờ đăng</span
                        >
                        <NativeSelect v-model="draft.mode" class="w-full">
                            <option value="explore">
                                Thăm dò — rải đều, thử nhiều giờ khác nhau
                            </option>
                            <option value="optimized">
                                Tối ưu — ưu tiên giờ có nhiều lượt xem
                            </option>
                        </NativeSelect>
                    </label>
                    <template v-if="rec?.hours?.length">
                        <div class="text-[0.8125rem] text-muted-foreground">
                            Giờ có lượt xem cao ({{ rec.videos }} bài,
                            {{ rec.days }} ngày):
                        </div>
                        <ul class="flex flex-wrap gap-2">
                            <li
                                v-for="h in rec.hours"
                                :key="h.hour"
                                class="inline-flex items-baseline gap-1.5 rounded-lg border bg-background px-3 py-1 text-[0.8125rem] tabular-nums"
                                :title="`${fmtNum(h.avg_views)} lượt xem trung bình, ${h.samples} bài`"
                            >
                                <b class="font-medium">{{ h.hour }}h</b>
                                <span
                                    :class="
                                        h.delta_pct >= 0
                                            ? 'text-success-text'
                                            : 'text-destructive-text'
                                    "
                                >
                                    {{ h.delta_pct > 0 ? '+' : ''
                                    }}{{
                                        Number(h.delta_pct).toLocaleString(
                                            'vi-VN',
                                        )
                                    }}%</span
                                >
                            </li>
                        </ul>
                        <div>
                            <Button
                                size="sm"
                                variant="outline"
                                :disabled="busy"
                                @click="applyHours"
                                >Dùng các giờ này</Button
                            >
                        </div>
                    </template>
                    <p v-else class="text-[0.8125rem] text-muted-foreground">
                        {{
                            rec?.reason ??
                            'Chưa đủ số liệu — app sẽ đề xuất giờ sau vài ngày đăng.'
                        }}
                    </p>
                    <p
                        v-if="
                            account.mode === 'optimized' &&
                            account.preferred_hours.length
                        "
                        class="text-[0.8125rem] text-muted-foreground"
                    >
                        Đang ưu tiên:
                        {{
                            account.preferred_hours
                                .map((h) => `${h}h`)
                                .join(', ')
                        }}
                    </p>
                </div>
            </div>

            <DialogFooter class="gap-2">
                <Button variant="ghost" :disabled="busy" @click="open = false"
                    >Huỷ</Button
                >
                <Button
                    :disabled="busy || !dirty || windowBad || capBad"
                    @click="save"
                >
                    <Spinner v-if="busy" class="size-4" />
                    Lưu
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
    <MixDialog
        v-model:open="mixOpen"
        :accounts="[account]"
        :account-id="account.id"
    />
</template>

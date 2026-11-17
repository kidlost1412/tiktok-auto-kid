<script setup lang="ts">
// Hộp "Khung giờ đăng thẳng": trong khung (lúc máy bật) tới giờ Chrome đăng ngay, không hẹn trước lên TikTok;
// ngoài khung vẫn hẹn trước như cũ. Tuỳ chọn, mặc định tắt.
import { router } from '@inertiajs/vue3';
import { IconBolt } from '@tabler/icons-vue';
import { computed, reactive, ref, watch } from 'vue';

import type { AccountRow, DirectWindow } from '@/components/fork/auto/types';
import { toneClasses } from '@/components/fork/shared/status';
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
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

const props = defineProps<{ value: DirectWindow; accounts: AccountRow[] }>();
const open = defineModel<boolean>('open', { default: false });

const DAYS: { n: number; label: string }[] = [
    { n: 1, label: 'T2' },
    { n: 2, label: 'T3' },
    { n: 3, label: 'T4' },
    { n: 4, label: 'T5' },
    { n: 5, label: 'T6' },
    { n: 6, label: 'T7' },
    { n: 7, label: 'CN' },
];

const fromProps = () => ({
    enabled: props.value.enabled,
    start: props.value.start,
    end: props.value.end,
    days: [...props.value.days],
    off_channels: [...props.value.off_channels],
});

const form = reactive(fromProps());

watch(open, (v) => {
    if (v) {
        Object.assign(form, fromProps());
    }
});

const toggleDay = (n: number) => {
    form.days = form.days.includes(n)
        ? form.days.filter((d) => d !== n)
        : [...form.days, n].sort();
};

const channelOn = (id: string) => !form.off_channels.includes(id);
const toggleChannel = (id: string) => {
    form.off_channels = channelOn(id)
        ? [...form.off_channels, id]
        : form.off_channels.filter((c) => c !== id);
};

const timeBad = computed(
    () => !form.start || !form.end || form.end <= form.start,
);
const daysBad = computed(() => form.enabled && form.days.length === 0);

// Giờ cuối cùng còn đăng thẳng (bài sát giờ tắt máy được hẹn trước).
const lastDirect = computed(() => {
    const [h, m] = form.end.split(':').map(Number);
    const t = h * 60 + m - props.value.margin_minutes;

    if (Number.isNaN(t) || t <= 0) {
        return null;
    }

    return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`;
});

const busy = ref(false);

const save = () => {
    busy.value = true;
    router.put(
        '/auto/dang-thang',
        { ...form },
        {
            preserveScroll: true,
            onSuccess: () => {
                open.value = false;
            },
            onFinish: () => {
                busy.value = false;
            },
        },
    );
};

const labelCls = 'text-sm font-medium text-foreground';
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent
            class="sm:max-w-[520px]"
            data-testid="fork-auto-direct-window"
        >
            <DialogHeader>
                <DialogTitle class="flex items-center gap-2"
                    ><IconBolt class="size-5 text-primary-text" />Khung giờ đăng
                    thẳng</DialogTitle
                >
                <DialogDescription>
                    Trong khung này (lúc máy tính bật), video không được hẹn
                    trước lên TikTok: tới giờ Chrome đăng luôn, nên trước đó sửa
                    hay xoá thoải mái. Ngoài khung vẫn hẹn trước như cũ.
                </DialogDescription>
            </DialogHeader>

            <div class="grid gap-5">
                <label class="flex items-center justify-between gap-4">
                    <span :class="labelCls">Bật đăng thẳng</span>
                    <Switch
                        v-model="form.enabled"
                        aria-label="Bật đăng thẳng"
                        data-testid="fork-direct-enabled"
                    />
                </label>

                <div
                    :class="
                        cn(
                            'grid gap-5',
                            !form.enabled && 'pointer-events-none opacity-50',
                        )
                    "
                    :aria-disabled="!form.enabled"
                >
                    <div class="grid grid-cols-2 gap-4">
                        <label class="flex flex-col gap-1.5">
                            <span :class="labelCls">Máy bật lúc</span>
                            <Input
                                v-model="form.start"
                                type="time"
                                data-testid="fork-direct-start"
                            />
                        </label>
                        <label class="flex flex-col gap-1.5">
                            <span :class="labelCls">Máy tắt lúc</span>
                            <Input
                                v-model="form.end"
                                type="time"
                                data-testid="fork-direct-end"
                            />
                        </label>
                    </div>
                    <p
                        v-if="timeBad"
                        :class="
                            cn(
                                '-mt-3 text-[0.8125rem]',
                                toneClasses.danger.text,
                            )
                        "
                    >
                        Giờ tắt phải sau giờ bật.
                    </p>

                    <div class="flex flex-col gap-2">
                        <span :class="labelCls">Những ngày máy bật</span>
                        <div class="flex flex-wrap gap-1.5">
                            <button
                                v-for="d in DAYS"
                                :key="d.n"
                                type="button"
                                :aria-pressed="form.days.includes(d.n)"
                                :class="
                                    cn(
                                        'h-8 min-w-10 rounded-md border px-2.5 text-sm font-medium transition-colors',
                                        form.days.includes(d.n)
                                            ? 'border-primary bg-primary text-primary-foreground'
                                            : 'bg-card text-muted-foreground hover:bg-accent',
                                    )
                                "
                                :data-testid="`fork-direct-day-${d.n}`"
                                @click="toggleDay(d.n)"
                            >
                                {{ d.label }}
                            </button>
                        </div>
                        <p
                            v-if="daysBad"
                            :class="
                                cn('text-[0.8125rem]', toneClasses.danger.text)
                            "
                        >
                            Chọn ít nhất một ngày.
                        </p>
                    </div>

                    <div v-if="accounts.length > 1" class="flex flex-col gap-2">
                        <span :class="labelCls">Áp dụng cho kênh</span>
                        <label
                            v-for="a in accounts"
                            :key="a.id"
                            class="flex items-center justify-between gap-4 text-sm"
                        >
                            <span class="truncate"
                                >@{{ a.username ?? a.display_name }}</span
                            >
                            <Switch
                                :model-value="channelOn(a.id)"
                                :aria-label="`Đăng thẳng cho @${a.username ?? a.display_name}`"
                                @update:model-value="toggleChannel(a.id)"
                            />
                        </label>
                    </div>

                    <ul
                        class="flex list-disc flex-col gap-1 rounded-lg border bg-muted/40 py-2.5 pr-3 pl-7 text-[0.8125rem] text-muted-foreground"
                    >
                        <li v-if="lastDirect">
                            Bài từ {{ lastDirect }} tới {{ form.end }} vẫn hẹn
                            trước ({{ value.margin_minutes }} phút cuối), để
                            không kẹt lúc tắt máy.
                        </li>
                        <li>
                            Máy tắt hoặc Chrome đóng lúc tới giờ: bật lại trong
                            {{ value.catch_up_minutes / 60 }} tiếng thì app đăng
                            bù từng bài; trễ hơn thì dời sang giờ trống kế tiếp.
                        </li>
                        <li>
                            Tới giờ đăng thẳng, kênh ưu tiên bài đó trước việc
                            gửi các bài hẹn tối lên TikTok. Giờ đăng vẫn lệch
                            ngẫu nhiên vài phút như hiện nay.
                        </li>
                    </ul>
                </div>
            </div>

            <DialogFooter class="gap-2">
                <Button variant="ghost" :disabled="busy" @click="open = false"
                    >Huỷ</Button
                >
                <Button
                    :disabled="busy || timeBad || daysBad"
                    data-testid="fork-direct-save"
                    @click="save"
                >
                    <Spinner v-if="busy" class="size-4" />
                    Lưu
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

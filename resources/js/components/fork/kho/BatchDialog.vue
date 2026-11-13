<script setup lang="ts">
// Đăng hàng loạt video riêng: chọn kênh + sản phẩm giỏ hàng + caption, rồi hẹn giờ tự động hoặc thủ công, xem trước lịch và xác nhận.
import { router } from '@inertiajs/vue3';
import { computed, ref, watch } from 'vue';

import Callout from '@/components/fork/shared/Callout.vue';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

interface ProductOption {
    code: string;
    quy_cach: string | null;
    label: string;
    name: string;
    tags: string[];
}

export interface BatchAccount {
    id: string;
    name: string;
    auto_enabled: boolean;
    usable: boolean;
    unusable_reason: string | null;
    ahead_days: number;
    products: ProductOption[];
}

interface PlanRow {
    id: number;
    file_name: string | null;
    status: 'ok' | 'warn' | 'error' | 'skip';
    messages: string[];
    at: string | null;
    result?: 'done' | 'error' | 'skip';
    error?: string;
}

interface Plan {
    ok: boolean;
    error: string | null;
    rows: PlanRow[];
    left: number;
    needs_confirm: boolean;
    committed?: boolean;
    done?: number;
    failed?: number;
    channel?: string;
}

const props = defineProps<{
    open: boolean;
    items: { id: number; file_name: string }[];
    accounts: BatchAccount[];
    limits: { min_lead_minutes: number; gap_minutes: number; caption_max: number };
}>();

const emit = defineEmits<{ 'update:open': [value: boolean]; done: [] }>();

const usable = computed(() => props.accounts.filter((a) => a.usable));
const accountId = ref('');
const productKey = ref('');
const caption = ref('');
const tags = ref('');
const mode = ref<'auto' | 'manual'>('auto');
const times = ref<Record<number, string>>({});
const overrides = ref<Record<number, { caption: string; tags: string; open: boolean }>>({});
const startAt = ref('');
const stepMin = ref(30);
const step = ref<'form' | 'preview' | 'result'>('form');
const plan = ref<Plan | null>(null);
const busy = ref(false);
const problem = ref('');
let lastTags = '';

const account = computed(() => usable.value.find((a) => a.id === accountId.value) ?? null);
const optionKey = (o: ProductOption) => `${o.code}|${o.quy_cach ?? ''}`;
const product = computed(() => account.value?.products.find((o) => optionKey(o) === productKey.value) ?? null);
const captionLen = computed(() => caption.value.length + (tags.value ? tags.value.length + 2 : 0));

watch(
    () => props.open,
    (open) => {
        if (!open) {
            return;
        }

        step.value = 'form';
        plan.value = null;
        problem.value = '';
        mode.value = 'auto';
        times.value = {};
        overrides.value = {};
        startAt.value = dayjs().add(1, 'hour').minute(0).format('YYYY-MM-DDTHH:mm');
        accountId.value = usable.value[0]?.id ?? '';
    },
    { immediate: true },
);

watch(accountId, () => {
    productKey.value = account.value?.products[0] ? optionKey(account.value.products[0]) : '';
});

// Gợi ý hashtag mặc định của sản phẩm (chỉ ghi đè khi ô hashtag còn trống hoặc chưa bị sửa tay).
watch(product, (p) => {
    const next = (p?.tags ?? []).join(' ');

    if (tags.value.trim() === '' || tags.value === lastTags) {
        tags.value = next;
    }

    lastTags = next;
});

const fillTimes = () => {
    let t = dayjs(startAt.value);

    if (!t.isValid()) {
        return;
    }

    for (const it of props.items) {
        times.value[it.id] = t.format('YYYY-MM-DDTHH:mm');
        t = t.add(Math.max(1, Number(stepMin.value) || 30), 'minute');
    }
};

const payload = (acceptWarnings: boolean) => ({
    social_account_id: accountId.value,
    product_code: product.value?.code ?? '',
    quy_cach: product.value?.quy_cach ?? null,
    caption: caption.value,
    hashtags: tags.value,
    mode: mode.value,
    accept_warnings: acceptWarnings,
    items: props.items.map((it) => {
        const o = overrides.value[it.id];
        const at = times.value[it.id];

        return {
            id: it.id,
            ...(mode.value === 'manual' && at ? { at: dayjs(at).toISOString() } : {}),
            ...(o?.caption?.trim() ? { caption: o.caption } : {}),
            ...(o?.tags?.trim() ? { hashtags: o.tags } : {}),
        };
    }),
});

const xsrf = () =>
    decodeURIComponent(document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '');

async function send(url: string, acceptWarnings: boolean): Promise<Plan | null> {
    busy.value = true;
    problem.value = '';

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-XSRF-TOKEN': xsrf(),
            },
            credentials: 'same-origin',
            body: JSON.stringify(payload(acceptWarnings)),
        });

        if (!r.ok) {
            problem.value =
                r.status === 422
                    ? 'Thông tin chưa đủ hoặc chưa đúng, hãy kiểm tra lại các ô.'
                    : 'Không làm được, hãy thử lại.';

            return null;
        }

        return (await r.json()) as Plan;
    } catch {
        problem.value = 'Mất kết nối với app, hãy thử lại.';

        return null;
    } finally {
        busy.value = false;
    }
}

const checkForm = (): string => {
    if (!account.value) {
        return 'Hãy chọn kênh.';
    }

    if (!product.value) {
        return 'Hãy chọn sản phẩm gắn giỏ hàng.';
    }

    if (mode.value === 'manual' && props.items.some((it) => !times.value[it.id])) {
        return 'Hãy nhập giờ đăng cho từng video (hoặc bấm "Điền giờ").';
    }

    return '';
};

async function preview() {
    const err = checkForm();

    if (err) {
        problem.value = err;

        return;
    }

    const res = await send('/auto/kho/rieng/dat-lich/xem', false);

    if (res) {
        plan.value = res;
        problem.value = res.ok ? '' : (res.error ?? '');
        step.value = res.ok ? 'preview' : 'form';
    }
}

async function confirm() {
    const res = await send('/auto/kho/rieng/dat-lich', true);

    if (res) {
        plan.value = res;
        problem.value = res.ok ? '' : (res.error ?? '');
        step.value = res.ok ? 'result' : 'form';
    }
}

const close = () => {
    const finished = step.value === 'result';
    emit('update:open', false);

    if (finished) {
        emit('done');
        router.reload({ only: ['videos', 'counts', 'selectable', 'days', 'folders'] });
    }
};

const fmt = (iso: string | null) => (iso ? dayjs(iso).format('HH:mm DD/MM/YYYY') : '—');
const hasWarn = computed(() => plan.value?.rows.some((r) => r.status === 'warn') ?? false);
const okCount = computed(() => plan.value?.rows.filter((r) => r.status === 'ok' || r.status === 'warn').length ?? 0);
const nameOf = (r: PlanRow) => r.file_name ?? props.items.find((i) => i.id === r.id)?.file_name ?? `#${r.id}`;

const chip = (s: string) =>
    ({
        ok: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300',
        warn: 'bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300',
        error: 'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300',
        skip: 'bg-muted text-muted-foreground',
    })[s] ?? 'bg-muted';

const selectCls =
    'w-full';
const areaCls =
    'min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring';
</script>

<template>
    <Dialog :open="open" @update:open="(v: boolean) => (v ? emit('update:open', true) : close())">
        <DialogContent
            class="flex max-h-[90dvh] max-w-3xl flex-col overflow-hidden"
            data-testid="fork-rieng-batch"
        >
            <DialogHeader>
                <DialogTitle>Đăng hàng loạt · {{ items.length }} video</DialogTitle>
                <DialogDescription>
                    Chọn kênh và sản phẩm giỏ hàng, viết caption, rồi hẹn giờ đăng.
                </DialogDescription>
            </DialogHeader>

            <div class="-mx-6 flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-6">
                <Callout v-if="problem" tone="danger">{{ problem }}</Callout>

                <!-- BƯỚC 1: nhập thông tin -->
                <template v-if="step === 'form'">
                    <Callout v-if="!usable.length" tone="warn">
                        Chưa có kênh nào dùng được để đăng. Cần một kênh đã kết nối, đã bật đăng qua Chrome và có sản phẩm gắn giỏ hàng.
                        <ul class="mt-1.5 list-disc pl-5 text-sm">
                            <li v-for="a in accounts" :key="a.id">
                                {{ a.name }}: {{ a.unusable_reason }}
                            </li>
                        </ul>
                    </Callout>

                    <template v-else>
                        <div class="grid gap-3 sm:grid-cols-2">
                            <label class="flex flex-col gap-1.5 text-sm font-medium">
                                Kênh đăng
                                <NativeSelect v-model="accountId" :class="selectCls" data-testid="fork-rieng-account">
                                    <option v-for="a in usable" :key="a.id" :value="a.id">
                                        {{ a.name }}{{ a.auto_enabled ? '' : ' (tự động đang tắt)' }}
                                    </option>
                                </NativeSelect>
                            </label>
                            <label class="flex flex-col gap-1.5 text-sm font-medium">
                                Sản phẩm gắn giỏ hàng
                                <NativeSelect v-model="productKey" :class="selectCls" data-testid="fork-rieng-product">
                                    <option v-for="o in account?.products ?? []" :key="optionKey(o)" :value="optionKey(o)">
                                        {{ o.label }}
                                    </option>
                                </NativeSelect>
                            </label>
                        </div>

                        <div class="flex flex-col gap-1.5">
                            <label class="text-sm font-medium" for="rieng-caption">Caption chung cho cả lượt</label>
                            <textarea id="rieng-caption" v-model="caption" :class="areaCls" placeholder="Viết nội dung bài đăng…" data-testid="fork-rieng-caption" />
                            <label class="text-sm font-medium" for="rieng-tags">Hashtag chung</label>
                            <Input id="rieng-tags" v-model="tags" placeholder="#nongnghiep #nanodong" />
                            <span :class="cn('text-xs', captionLen > limits.caption_max ? 'text-red-600' : 'text-muted-foreground')">
                                {{ captionLen }} / {{ limits.caption_max }} ký tự
                            </span>
                        </div>

                        <div class="flex flex-col gap-2">
                            <span class="text-sm font-medium">Cách hẹn giờ</span>
                            <div class="grid gap-2 sm:grid-cols-2">
                                <label :class="cn('flex cursor-pointer flex-col gap-0.5 rounded-lg border p-3 text-sm', mode === 'auto' ? 'border-primary bg-primary/5 ring-1 ring-primary/40' : 'hover:bg-muted/50')">
                                    <span class="flex items-center gap-2 font-medium"><input v-model="mode" type="radio" value="auto" /> Tự động</span>
                                    <span class="text-xs text-muted-foreground">Xếp vào các giờ trống gần nhất của kênh (đúng khung giờ, giãn cách và tránh kênh khác).</span>
                                </label>
                                <label :class="cn('flex cursor-pointer flex-col gap-0.5 rounded-lg border p-3 text-sm', mode === 'manual' ? 'border-primary bg-primary/5 ring-1 ring-primary/40' : 'hover:bg-muted/50')">
                                    <span class="flex items-center gap-2 font-medium"><input v-model="mode" type="radio" value="manual" data-testid="fork-rieng-mode-manual" /> Thủ công</span>
                                    <span class="text-xs text-muted-foreground">Tự chọn giờ cho từng video. App báo nếu trùng giờ bài khác.</span>
                                </label>
                            </div>
                        </div>

                        <div v-if="mode === 'manual'" class="flex flex-wrap items-end gap-3 rounded-lg border bg-muted/40 p-3">
                            <label class="flex flex-col gap-1 text-sm">
                                Giờ bắt đầu
                                <Input v-model="startAt" type="datetime-local" class="w-56" />
                            </label>
                            <label class="flex flex-col gap-1 text-sm">
                                Cách nhau (phút)
                                <Input v-model.number="stepMin" type="number" min="1" class="w-28" />
                            </label>
                            <Button type="button" variant="outline" @click="fillTimes">Điền giờ</Button>
                            <span class="text-xs text-muted-foreground">Cách hiện tại ít nhất {{ limits.min_lead_minutes }} phút; các bài cùng kênh nên cách nhau từ {{ limits.gap_minutes }} phút.</span>
                        </div>

                        <ul class="flex flex-col divide-y rounded-lg border text-sm">
                            <li v-for="it in items" :key="it.id" class="flex flex-col gap-2 p-2.5">
                                <div class="flex flex-wrap items-center gap-2">
                                    <span class="min-w-0 flex-1 truncate font-medium">{{ it.file_name }}</span>
                                    <Input v-if="mode === 'manual'" v-model="times[it.id]" type="datetime-local" class="w-52" :data-testid="`fork-rieng-time-${it.id}`" />
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant="ghost"
                                        @click="overrides[it.id] = { caption: overrides[it.id]?.caption ?? '', tags: overrides[it.id]?.tags ?? '', open: !overrides[it.id]?.open }"
                                    >
                                        {{ overrides[it.id]?.open ? 'Ẩn' : 'Sửa caption riêng' }}
                                    </Button>
                                </div>
                                <div v-if="overrides[it.id]?.open" class="flex flex-col gap-1.5">
                                    <textarea v-model="overrides[it.id].caption" :class="areaCls" placeholder="Caption riêng (để trống = dùng caption chung)" />
                                    <Input v-model="overrides[it.id].tags" placeholder="Hashtag riêng (để trống = dùng hashtag chung)" />
                                </div>
                            </li>
                        </ul>
                    </template>
                </template>

                <!-- BƯỚC 2: xem trước -->
                <template v-else-if="step === 'preview' && plan">
                    <Callout v-if="plan.left > 0" tone="warn">
                        Chỉ xếp được {{ okCount }} video. Còn {{ plan.left }} video chưa có giờ trống, sẽ để lại để bạn đăng sau.
                    </Callout>
                    <Callout v-if="hasWarn" tone="warn">
                        Có giờ bị trùng với bài khác. Bạn có thể quay lại sửa giờ, hoặc bấm "Vẫn hẹn".
                    </Callout>
                    <ul class="flex flex-col divide-y rounded-lg border text-sm" data-testid="fork-rieng-preview">
                        <li v-for="r in plan.rows" :key="r.id" class="flex flex-col gap-1 p-2.5">
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="min-w-0 flex-1 truncate font-medium">{{ nameOf(r) }}</span>
                                <span class="tabular-nums">{{ fmt(r.at) }}</span>
                                <span :class="cn('rounded-full px-2 py-0.5 text-xs font-medium', chip(r.status))">
                                    {{ { ok: 'Ổn', warn: 'Trùng giờ', error: 'Không hẹn được', skip: 'Để lại' }[r.status] }}
                                </span>
                            </div>
                            <p v-for="m in r.messages" :key="m" class="text-xs text-muted-foreground">{{ m }}</p>
                        </li>
                    </ul>
                </template>

                <!-- BƯỚC 3: kết quả -->
                <template v-else-if="step === 'result' && plan">
                    <Callout :tone="(plan.failed ?? 0) > 0 || (plan.done ?? 0) === 0 ? 'warn' : 'success'" data-testid="fork-rieng-result">
                        Đã hẹn giờ {{ plan.done ?? 0 }} video{{ plan.channel ? ` cho ${plan.channel}` : '' }}.
                        <template v-if="(plan.failed ?? 0) > 0"> Lỗi {{ plan.failed }} video (đã trả về kho).</template>
                        <template v-if="plan.left > 0"> Còn {{ plan.left }} video chưa có giờ trống.</template>
                    </Callout>
                    <ul class="flex flex-col divide-y rounded-lg border text-sm">
                        <li v-for="r in plan.rows" :key="r.id" class="flex flex-col gap-1 p-2.5">
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="min-w-0 flex-1 truncate font-medium">{{ nameOf(r) }}</span>
                                <span class="tabular-nums">{{ r.result === 'done' ? fmt(r.at) : '' }}</span>
                                <span :class="cn('rounded-full px-2 py-0.5 text-xs font-medium', chip(r.result === 'done' ? 'ok' : r.result === 'skip' ? 'skip' : 'error'))">
                                    {{ r.result === 'done' ? 'Đã hẹn giờ' : r.result === 'skip' ? 'Để lại' : 'Lỗi' }}
                                </span>
                            </div>
                            <p v-if="r.error" class="text-xs text-red-600">{{ r.error }}</p>
                            <p v-for="m in r.result === 'error' && !r.error ? r.messages : []" :key="m" class="text-xs text-muted-foreground">{{ m }}</p>
                        </li>
                    </ul>
                </template>
            </div>

            <div class="flex flex-wrap items-center justify-end gap-2 pt-2">
                <template v-if="step === 'form'">
                    <Button variant="outline" @click="close">Đóng</Button>
                    <Button :disabled="busy || !usable.length" data-testid="fork-rieng-preview-btn" @click="preview">
                        {{ busy ? 'Đang kiểm tra…' : 'Xem trước lịch' }}
                    </Button>
                </template>
                <template v-else-if="step === 'preview'">
                    <Button variant="outline" :disabled="busy" @click="step = 'form'">Quay lại sửa</Button>
                    <Button :disabled="busy || okCount === 0" data-testid="fork-rieng-confirm" @click="confirm">
                        {{ busy ? 'Đang hẹn giờ…' : hasWarn ? 'Vẫn hẹn' : `Hẹn giờ ${okCount} video` }}
                    </Button>
                </template>
                <Button v-else @click="close">Xong</Button>
            </div>
        </DialogContent>
    </Dialog>
</template>

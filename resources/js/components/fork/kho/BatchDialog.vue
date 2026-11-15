<script setup lang="ts">
// Đăng hàng loạt video riêng: chọn kênh + sản phẩm giỏ hàng + caption; giờ đăng luôn được tự đề xuất (sửa thẳng từng giờ được), xem trước lịch và xác nhận.
// Ảnh bìa đã chọn được nhớ (theo video, theo kênh + sản phẩm, theo kênh) để lần sau tự dùng lại.
import { router } from '@inertiajs/vue3';
import { computed, ref, watch } from 'vue';

import ChannelPicker from '@/components/fork/kho/ChannelPicker.vue';
import ClipThumb from '@/components/fork/kho/ClipThumb.vue';
import ProductPicker from '@/components/fork/kho/ProductPicker.vue';
import { postJson, type BatchItem } from '@/components/fork/kho/rieng';
import Callout from '@/components/fork/shared/Callout.vue';
import DateTimePicker from '@/components/fork/shared/DateTimePicker.vue';
import HashtagChips from '@/components/fork/shared/HashtagChips.vue';
import type { TagSuggestion } from '@/components/fork/shared/hashtags';
import MediaLightbox from '@/components/fork/shared/MediaLightbox.vue';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

interface ProductOption {
    code: string;
    quy_cach: string | null;
    label: string;
    name: string;
    tags: string[];
    cover_count: number;
    /** Ảnh sản phẩm TikTok Shop đã gắn giỏ (nếu có). */
    image?: string | null;
}

type CoverMode = 'product' | 'upload' | 'frame';

interface PickedCover {
    token: string;
    url: string;
    /** Ảnh nhớ từ lần trước (không phải vừa chọn). */
    remembered?: boolean;
}

interface ProposeRow {
    id: number;
    at: string | null;
    status: 'ok' | 'warn' | 'error' | 'skip';
    messages: string[];
    edited: boolean;
}

interface CoverRecall {
    mode: CoverMode | null;
    from: 'pair' | 'account' | null;
    batch: PickedCover | null;
    rows: Record<string, PickedCover>;
}

const FORMAT = 'YYYY-MM-DDTHH:mm';

export interface BatchAccount {
    id: string;
    name: string;
    avatar_url?: string | null;
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
    duplicate?: string | null;
    at: string | null;
    cover?: { kind: string; url: string | null; note: string };
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
    items: BatchItem[];
    accounts: BatchAccount[];
    limits: { min_lead_minutes: number; gap_minutes: number; caption_max: number };
    /** Hashtag đã dùng trước đây (nhiều nhất trước) để gợi ý dưới ô "Hashtag chung". */
    hashtagSuggestions?: TagSuggestion[];
    /** Dùng trong popup "Bàn làm việc": không tự tải lại trang, nơi gọi lo qua sự kiện `done`. */
    inPlace?: boolean;
}>();

const emit = defineEmits<{
    'update:open': [value: boolean];
    done: [];
    step: [value: 'form' | 'preview' | 'result'];
}>();

const usable = computed(() => props.accounts.filter((a) => a.usable));
const accountId = ref('');
const productKey = ref('');
const caption = ref('');
const tags = ref('');
const times = ref<Record<number, string>>({});
// Giờ chủ app đã tự sửa: giữ nguyên; các giờ khác do app đề xuất (tính lại khi đổi kênh / sửa giờ khác).
const edited = ref<Record<number, boolean>>({});
const slotInfo = ref<Record<number, { status: ProposeRow['status']; messages: string[] }>>({});
const slotsBusy = ref(false);
const slotProblem = ref('');
const rules = ref<{ window: string | null; gap: number }>({ window: null, gap: 20 });
const overrides = ref<Record<number, { caption: string; tags: string; open: boolean }>>({});
const step = ref<'form' | 'preview' | 'result'>('form');
const plan = ref<Plan | null>(null);
const busy = ref(false);
const problem = ref('');
let lastTags = '';

// Ảnh bìa: theo sản phẩm (mặc định), tải ảnh lên, hoặc chọn một khung trong video.
const coverMode = ref<CoverMode>('product');
// Chủ app đã tự đổi cách chọn bìa trong lượt này: không để "ảnh đã nhớ" ghi đè nữa.
const coverTouched = ref(false);
const coverFrom = ref<'pair' | 'account' | null>(null);
const batchCover = ref<PickedCover | null>(null);
const rowCover = ref<Record<number, PickedCover>>({});
const coverBusy = ref<Record<string, boolean>>({});
const coverError = ref('');
const frameOpen = ref<Record<number, boolean>>({});
const frameT = ref<Record<number, number>>({});
const frameDur = ref<Record<number, number>>({});

// Xem phóng to video / ảnh bìa (lightbox).
const lightbox = ref<{ kind: 'image' | 'video'; src: string; title: string; poster?: string } | null>(null);
const zoomVideo = (it: { id: number; file_name: string }) => {
    lightbox.value = { kind: 'video', src: `/auto/kho/video/${it.id}`, title: it.file_name, poster: `/auto/kho/rieng/video/${it.id}/thumb` };
};
const zoomCover = (url: string, title: string) => {
    lightbox.value = { kind: 'image', src: url, title };
};
const durationOf = (id: number) => props.items.find((i) => i.id === id)?.duration ?? null;

const pickerOptions = computed(() =>
    (account.value?.products ?? []).map((o) => ({ key: optionKey(o), name: o.name, label: o.label, image: o.image })),
);

const account = computed(() => usable.value.find((a) => a.id === accountId.value) ?? null);
const optionKey = (o: ProductOption) => `${o.code}|${o.quy_cach ?? ''}`;
const product = computed(() => account.value?.products.find((o) => optionKey(o) === productKey.value) ?? null);
// Video trùng nội dung với video đã có: vẫn đăng được, nhưng phải cảnh báo rõ để chủ app không đăng trùng nhầm.
const dupItems = computed(() => props.items.filter((i) => i.duplicate));

watch(step, (s) => emit('step', s));

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
        times.value = {};
        edited.value = {};
        slotInfo.value = {};
        slotProblem.value = '';
        overrides.value = {};
        coverMode.value = 'product';
        coverTouched.value = false;
        coverFrom.value = null;
        batchCover.value = null;
        rowCover.value = {};
        coverBusy.value = {};
        coverError.value = '';
        frameOpen.value = {};
        frameT.value = {};
        frameDur.value = {};
        const keep = accountId.value !== '' && usable.value.some((a) => a.id === accountId.value);
        accountId.value = keep ? accountId.value : (usable.value[0]?.id ?? '');

        // Tự đề xuất giờ + gọi lại ảnh nhớ (để sau một nhịp: các hàm/biến bên dưới đã sẵn sàng). Gọi trùng với watch(accountId) cũng không sao.
        void Promise.resolve().then(() => {
            void propose();
            void recallCovers(true);
        });
    },
    { immediate: true },
);

watch(accountId, () => {
    productKey.value = account.value?.products[0] ? optionKey(account.value.products[0]) : '';
    void propose();
    void recallCovers(true);
});

watch(productKey, (k, old) => {
    if (old !== undefined && old !== '' && k !== old) {
        void recallCovers(false);
    }
});

// ---------------------------------------------------------------- Giờ đăng (luôn tự đề xuất, sửa tay được)
let proposeSeq = 0;
let proposeTimer: ReturnType<typeof setTimeout> | null = null;

async function propose() {
    if (!props.open || !accountId.value || !props.items.length) {
        return;
    }

    const seq = ++proposeSeq;
    slotsBusy.value = true;
    const res = await postJson<{ ok: boolean; error: string | null; rows: ProposeRow[]; window: string | null; gap_minutes: number }>(
        '/auto/kho/rieng/dat-lich/goi-y',
        {
            social_account_id: accountId.value,
            items: props.items.map((it) => ({
                id: it.id,
                ...(edited.value[it.id] && times.value[it.id] ? { at: dayjs(times.value[it.id]).toISOString() } : {}),
            })),
        },
    );

    if (seq !== proposeSeq) {
        return;
    }

    slotsBusy.value = false;

    if (!res?.ok) {
        slotProblem.value = res?.error ?? 'Không tính được giờ đăng, hãy thử lại.';

        return;
    }

    slotProblem.value = '';
    rules.value = { window: res.window, gap: res.gap_minutes };
    const nextTimes = { ...times.value };
    const info: typeof slotInfo.value = {};

    for (const r of res.rows) {
        if (!edited.value[r.id]) {
            nextTimes[r.id] = r.at ? dayjs(r.at).format(FORMAT) : '';
        }

        info[r.id] = { status: r.status, messages: r.messages };
    }

    times.value = nextTimes;
    slotInfo.value = info;
}

const proposeSoon = () => {
    if (proposeTimer) {
        clearTimeout(proposeTimer);
    }

    proposeTimer = setTimeout(() => void propose(), 250);
};

const setTime = (id: number, v: string) => {
    if (v === times.value[id]) {
        return;
    }

    times.value = { ...times.value, [id]: v };
    edited.value = { ...edited.value, [id]: v !== '' };
    proposeSoon();
};

const autoTime = (id: number) => {
    const next = { ...edited.value };
    delete next[id];
    edited.value = next;
    void propose();
};

// ---------------------------------------------------------------- Ảnh bìa đã nhớ
async function recallCovers(withRows: boolean) {
    if (!props.open || !accountId.value) {
        return;
    }

    const acc = accountId.value;
    const res = await postJson<CoverRecall>('/auto/kho/rieng/anh-bia/nho', {
        social_account_id: acc,
        product_code: product.value?.code ?? '',
        quy_cach: product.value?.quy_cach ?? null,
        ids: props.items.map((i) => i.id),
    });

    if (!res || acc !== accountId.value) {
        return;
    }

    if (!coverTouched.value) {
        coverMode.value = res.mode ?? 'product';
        batchCover.value = res.batch ? { ...res.batch, remembered: true } : null;
        coverFrom.value = res.mode ? res.from : null;
    }

    if (withRows) {
        const rows: Record<number, PickedCover> = {};

        for (const [id, c] of Object.entries(res.rows ?? {})) {
            rows[Number(id)] = { ...c, remembered: true };
        }

        // Ảnh vừa chọn trong lượt này luôn thắng ảnh nhớ.
        rowCover.value = { ...rows, ...rowCover.value };
    }
}

const pickMode = (m: CoverMode) => {
    coverMode.value = m;
    coverTouched.value = true;
    coverFrom.value = null;
};

async function clearRowCover(id: number) {
    const next = { ...rowCover.value };
    delete next[id];
    rowCover.value = next;
    await postJson(`/auto/kho/rieng/video/${id}/quen-bia`);
}

// Gợi ý hashtag mặc định của sản phẩm (chỉ ghi đè khi ô hashtag còn trống hoặc chưa bị sửa tay).
watch(product, (p) => {
    const next = (p?.tags ?? []).join(' ');

    if (tags.value.trim() === '' || tags.value === lastTags) {
        tags.value = next;
    }

    lastTags = next;
});

const payload = (acceptWarnings: boolean) => ({
    social_account_id: accountId.value,
    product_code: product.value?.code ?? '',
    quy_cach: product.value?.quy_cach ?? null,
    caption: caption.value,
    hashtags: tags.value,
    accept_warnings: acceptWarnings,
    cover_mode: coverMode.value,
    cover_token: coverMode.value === 'upload' ? (batchCover.value?.token ?? null) : null,
    items: props.items.map((it) => {
        const o = overrides.value[it.id];
        const at = times.value[it.id];
        const c = rowCover.value[it.id];

        return {
            id: it.id,
            ...(c ? { cover_token: c.token } : {}),
            ...(edited.value[it.id] && at ? { at: dayjs(at).toISOString() } : {}),
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

    if (coverMode.value === 'upload' && !batchCover.value && props.items.some((it) => !rowCover.value[it.id])) {
        return 'Hãy tải một ảnh bìa lên (hoặc chọn ảnh cho từng video).';
    }

    return '';
};

// Ảnh bìa hiện tại của một video trong danh sách (để hiện hình nhỏ).
const coverUrlOf = (id: number): string | null => {
    if (rowCover.value[id]) {
        return rowCover.value[id].url;
    }

    if (coverMode.value === 'product') {
        return null;
    }

    return coverMode.value === 'upload' ? (batchCover.value?.url ?? null) : `/auto/kho/rieng/video/${id}/thumb`;
};

async function postCover(url: string, body: FormData | string, key: string): Promise<PickedCover | null> {
    coverBusy.value[key] = true;
    coverError.value = '';

    try {
        const isForm = body instanceof FormData;
        const r = await fetch(url, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                ...(isForm ? {} : { 'Content-Type': 'application/json' }),
                'X-XSRF-TOKEN': xsrf(),
            },
            credentials: 'same-origin',
            body,
        });
        const j = await r.json().catch(() => ({}));

        if (!r.ok || !j.token) {
            coverError.value = j?.errors?.image?.[0] ?? j?.error ?? 'Không lấy được ảnh bìa, hãy thử lại.';

            return null;
        }

        return { token: j.token as string, url: j.url as string };
    } catch {
        coverError.value = 'Mất kết nối với app, hãy thử lại.';

        return null;
    } finally {
        coverBusy.value[key] = false;
    }
}

// Tải ảnh lên: cho cả lượt (id = null) hoặc riêng một video.
async function uploadCover(e: Event, id: number | null) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';

    if (!file) {
        return;
    }

    const fd = new FormData();
    fd.append('image', file);

    if (id !== null) {
        fd.append('video_id', String(id));
    }

    const c = await postCover('/auto/kho/rieng/anh-bia/tai-len', fd, id === null ? 'batch' : `up-${id}`);

    if (c) {
        if (id === null) {
            batchCover.value = c;
            coverTouched.value = true;
        } else {
            rowCover.value = { ...rowCover.value, [id]: c };
        }
    }
}

const onMeta = (id: number, e: Event) => {
    const d = (e.target as HTMLVideoElement).duration;

    if (Number.isFinite(d) && d > 0) {
        frameDur.value[id] = d;
        frameT.value[id] ??= d > 2 ? 1 : 0;
        seek(id, frameT.value[id]);
    }
};

const seek = (id: number, t: number) => {
    frameT.value[id] = t;
    const v = document.getElementById(`rieng-frame-${id}`) as HTMLVideoElement | null;

    if (v) {
        v.currentTime = t;
    }
};

async function takeFrame(id: number) {
    const c = await postCover(`/auto/kho/rieng/video/${id}/khung`, JSON.stringify({ t: frameT.value[id] ?? 0 }), `fr-${id}`);

    if (c) {
        rowCover.value = { ...rowCover.value, [id]: c };
        frameOpen.value[id] = false;
    }
}

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
        if (!props.inPlace) router.reload({ only: ['videos', 'counts', 'selectable', 'days', 'folders', 'queue', 'scan_sig'] });
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

const areaCls =
    'min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring';
</script>

<template>
    <Dialog :open="open" @update:open="(v: boolean) => (v ? emit('update:open', true) : close())">
        <!-- Khung cố định: tiêu đề trên, thân cuộn ở giữa, nút dưới cùng. Không đặt chiều cao cứng nên không thừa khoảng trắng.
             overflow-clip (không phải overflow-hidden): khung không bao giờ bị trình duyệt tự cuộn khi ô chọn ảnh ẩn nhận focus
             (lỗi cũ: bấm "Đổi ảnh" làm hộp co lại, trắng một mảng phía dưới). -->
        <DialogContent
            class="flex max-h-[90dvh] flex-col gap-0 overflow-clip p-0 sm:max-w-[min(56rem,calc(100%-2rem))]"
            data-testid="fork-rieng-batch"
        >
            <DialogHeader class="shrink-0 border-b px-5 pt-5 pr-14 pb-4 sm:px-6">
                <DialogTitle class="text-lg">Đăng hàng loạt · {{ items.length }} video</DialogTitle>
                <DialogDescription>
                    Chọn kênh và sản phẩm giỏ hàng, viết caption, rồi hẹn giờ đăng.
                </DialogDescription>
            </DialogHeader>

            <div class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-5 sm:px-6">
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
                            <div class="flex min-w-0 flex-col gap-1.5 text-sm font-medium">
                                Kênh đăng
                                <ChannelPicker
                                    v-model="accountId"
                                    :options="usable.map((a) => ({ id: a.id, name: a.name, avatar_url: a.avatar_url, note: a.auto_enabled ? null : 'tự động đang tắt' }))"
                                    testid="fork-rieng-account"
                                />
                            </div>
                            <div class="flex min-w-0 flex-col gap-1.5 text-sm font-medium">
                                Sản phẩm gắn giỏ hàng
                                <ProductPicker v-model="productKey" :options="pickerOptions" testid="fork-rieng-product-trigger" />
                            </div>
                        </div>

                        <Callout v-if="dupItems.length" tone="warn" data-testid="fork-rieng-dup-warning">
                            <div>
                                Có {{ dupItems.length }} video trùng với video đã có. Bạn vẫn đăng được, nhưng hãy kiểm tra để khỏi đăng trùng:
                                <ul class="mt-1.5 list-disc pl-5 text-sm font-normal">
                                    <li v-for="d in dupItems" :key="d.id"><b class="break-all">{{ d.file_name }}</b>: {{ d.duplicate }}</li>
                                </ul>
                            </div>
                        </Callout>

                        <div class="flex flex-col gap-1.5">
                            <label class="text-sm font-medium" for="rieng-caption">Caption chung cho cả lượt</label>
                            <textarea id="rieng-caption" v-model="caption" :class="areaCls" placeholder="Viết nội dung bài đăng…" data-testid="fork-rieng-caption" />
                            <label class="mt-1 text-sm font-medium" for="rieng-tags">Hashtag chung</label>
                            <HashtagChips v-model="tags" input-id="rieng-tags" :suggestions="hashtagSuggestions ?? []" placeholder="Ví dụ: #nongnghiep #nanodong" testid="fork-rieng-tags" />
                            <span :class="cn('text-xs', captionLen > limits.caption_max ? 'text-red-600 dark:text-red-400' : 'text-muted-foreground')">
                                {{ captionLen }} / {{ limits.caption_max }} ký tự
                            </span>
                        </div>

                        <div class="flex flex-col gap-2" data-testid="fork-rieng-cover">
                            <span class="text-sm font-medium">Ảnh bìa chung</span>
                            <div class="grid gap-2 sm:grid-cols-3">
                                <label :class="cn('relative flex cursor-pointer flex-col gap-0.5 rounded-lg border p-3 text-sm', coverMode === 'product' ? 'border-primary bg-primary/5 ring-1 ring-primary/40' : 'hover:bg-muted/50')">
                                    <span class="flex items-center gap-2 font-medium"><input :checked="coverMode === 'product'" type="radio" name="rieng-cover-mode" value="product" data-testid="fork-rieng-cover-product" @change="pickMode('product')" /> Ảnh bìa của sản phẩm</span>
                                    <span class="text-xs text-muted-foreground">Xoay vòng các ảnh bìa đã cài cho sản phẩm.</span>
                                </label>
                                <label :class="cn('relative flex cursor-pointer flex-col gap-0.5 rounded-lg border p-3 text-sm', coverMode === 'upload' ? 'border-primary bg-primary/5 ring-1 ring-primary/40' : 'hover:bg-muted/50')">
                                    <span class="flex items-center gap-2 font-medium"><input :checked="coverMode === 'upload'" type="radio" name="rieng-cover-mode" value="upload" data-testid="fork-rieng-cover-upload" @change="pickMode('upload')" /> Tải ảnh lên</span>
                                    <span class="text-xs text-muted-foreground">Một ảnh dùng chung cho cả lượt.</span>
                                </label>
                                <label :class="cn('relative flex cursor-pointer flex-col gap-0.5 rounded-lg border p-3 text-sm', coverMode === 'frame' ? 'border-primary bg-primary/5 ring-1 ring-primary/40' : 'hover:bg-muted/50')">
                                    <span class="flex items-center gap-2 font-medium"><input :checked="coverMode === 'frame'" type="radio" name="rieng-cover-mode" value="frame" data-testid="fork-rieng-cover-frame" @change="pickMode('frame')" /> Khung trong video</span>
                                    <span class="text-xs text-muted-foreground">Mỗi video lấy một khung của chính nó làm bìa.</span>
                                </label>
                            </div>

                            <p v-if="coverFrom" class="text-xs text-primary" data-testid="fork-rieng-cover-remembered">
                                Đã tự chọn lại như lần đăng trước {{ coverFrom === 'pair' ? 'của kênh + sản phẩm này' : 'của kênh này' }}.
                            </p>
                            <p v-if="coverMode === 'product' && product && product.cover_count === 0" class="text-xs text-amber-700 dark:text-amber-300" data-testid="fork-rieng-cover-empty">
                                Sản phẩm này chưa có ảnh bìa nên TikTok sẽ dùng bìa mặc định. Muốn tự chọn thì tải ảnh lên hoặc chọn khung.
                            </p>
                            <p v-else-if="coverMode === 'product'" class="text-xs text-muted-foreground">
                                Dùng {{ product?.cover_count ?? 0 }} ảnh bìa của sản phẩm, xoay vòng đều giữa các bài.
                            </p>

                            <div v-if="coverMode === 'upload'" class="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/40 p-3">
                                <img v-if="batchCover" :src="batchCover.url" alt="Ảnh bìa chung" class="h-20 w-[60px] rounded border object-cover" />
                                <label class="relative inline-flex">
                                    <input type="file" accept="image/jpeg,image/png,image/webp" class="peer sr-only" data-testid="fork-rieng-cover-file" @change="uploadCover($event, null)" />
                                    <span class="inline-flex h-9 cursor-pointer items-center rounded-md border bg-background px-3 text-sm font-medium hover:bg-muted peer-focus-visible:outline-2 peer-focus-visible:outline-ring">
                                        {{ coverBusy.batch ? 'Đang tải…' : batchCover ? 'Đổi ảnh chung' : 'Chọn ảnh' }}
                                    </span>
                                </label>
                                <span class="text-xs text-muted-foreground">jpg, png hoặc webp, tối đa 5 MB. Ảnh được cắt giữa theo tỉ lệ 3:4.</span>
                            </div>
                            <p class="text-xs text-muted-foreground">
                                Muốn video nào có bìa riêng thì bấm "Tải ảnh" hoặc "Chọn khung" ở video đó bên dưới. Ảnh bạn chọn được nhớ cho lần sau.
                            </p>
                            <p v-if="coverError" class="text-xs text-red-600 dark:text-red-400" data-testid="fork-rieng-cover-error">{{ coverError }}</p>
                        </div>

                        <div class="flex flex-col gap-1 rounded-lg border bg-muted/40 p-3 text-sm" data-testid="fork-rieng-time-rules">
                            <span class="font-medium">Giờ đăng: app tự xếp, bạn bấm vào giờ để sửa</span>
                            <span class="text-xs text-muted-foreground">
                                Luôn trong khung giờ đăng của kênh{{ rules.window ? ` (${rules.window})` : '' }}, hết khung thì sang ngày hôm sau;
                                cách bài khác của cùng kênh ít nhất {{ rules.gap }} phút (kênh khác không tính); sớm nhất sau {{ limits.min_lead_minutes }} phút nữa.
                            </span>
                            <span v-if="slotProblem" class="text-xs text-red-600 dark:text-red-400">{{ slotProblem }}</span>
                        </div>

                        <!-- Danh sách video: mỗi video một thẻ, hình nhỏ bên trái, thông tin + giờ + nút bên phải. -->
                        <div class="flex flex-col gap-2">
                            <span class="text-sm font-medium">Các video ({{ items.length }})</span>
                            <ul class="flex flex-col gap-2.5" data-testid="fork-rieng-rows">
                                <li v-for="(it, n) in items" :key="it.id" class="flex flex-col gap-2.5 rounded-xl border bg-card p-3 text-sm" :data-testid="`fork-rieng-row-${it.id}`">
                                    <div class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2.5">
                                        <!-- Hình: video 9:16 (rê chuột để xem thử) và ảnh bìa 3:4 -->
                                        <div class="flex items-end gap-2 sm:row-span-2">
                                            <ClipThumb :id="it.id" :duration="it.duration ?? durationOf(it.id)" :name="it.file_name" class="w-14 sm:w-16" @zoom="zoomVideo(it)" />
                                            <div class="flex flex-col items-center gap-1">
                                                <button
                                                    v-if="coverUrlOf(it.id)"
                                                    type="button"
                                                    class="block aspect-[3/4] w-12 overflow-hidden rounded-md border bg-muted focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring"
                                                    :aria-label="`Phóng to ảnh bìa video ${n + 1}`"
                                                    :data-testid="`fork-rieng-cover-thumb-${it.id}`"
                                                    @click="zoomCover(coverUrlOf(it.id)!, `Bìa · ${it.file_name}`)"
                                                >
                                                    <img :src="coverUrlOf(it.id)!" alt="Ảnh bìa" class="size-full object-cover" />
                                                </button>
                                                <span v-else class="flex aspect-[3/4] w-12 items-center justify-center rounded-md border border-dashed px-0.5 text-center text-[0.625rem] leading-tight text-muted-foreground">
                                                    {{ coverMode === 'product' ? 'Bìa sản phẩm' : 'Chưa có bìa' }}
                                                </span>
                                                <span class="text-[0.625rem] text-muted-foreground">{{ rowCover[it.id] ? (rowCover[it.id].remembered ? 'Bìa đã nhớ' : 'Bìa riêng') : 'Bìa' }}</span>
                                            </div>
                                        </div>

                                        <div class="min-w-0 self-center">
                                            <span class="block truncate font-medium" :title="it.file_name">{{ n + 1 }}. {{ it.file_name }}</span>
                                            <span v-if="it.duplicate" class="mt-0.5 inline-block rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">Trùng video đã có</span>
                                        </div>

                                        <div class="col-span-2 flex min-w-0 flex-col gap-2 sm:col-span-1">
                                            <div class="flex flex-wrap items-center gap-2">
                                                <DateTimePicker
                                                    :model-value="times[it.id] ?? ''"
                                                    class="w-full sm:w-60"
                                                    :placeholder="slotsBusy ? 'Đang tìm giờ trống…' : 'Chưa có giờ trống'"
                                                    :aria-label="`Giờ đăng video ${n + 1}`"
                                                    :testid="`fork-rieng-time-${it.id}`"
                                                    @update:model-value="(v: string) => setTime(it.id, v)"
                                                />
                                                <span v-if="edited[it.id]" class="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">Giờ bạn chọn</span>
                                                <span v-else-if="times[it.id]" class="text-xs text-muted-foreground">App đề xuất</span>
                                                <Button v-if="edited[it.id]" type="button" size="sm" variant="ghost" class="h-7 px-2 text-xs" :data-testid="`fork-rieng-time-auto-${it.id}`" @click="autoTime(it.id)">Để app tự xếp</Button>
                                            </div>
                                            <p
                                                v-for="m in slotInfo[it.id]?.messages ?? []"
                                                :key="m"
                                                :class="cn('text-xs', slotInfo[it.id]?.status === 'error' ? 'text-red-600 dark:text-red-400' : slotInfo[it.id]?.status === 'warn' ? 'text-amber-700 dark:text-amber-300' : 'text-muted-foreground')"
                                                :data-testid="`fork-rieng-time-msg-${it.id}`"
                                            >
                                                {{ m }}
                                            </p>
                                            <div class="flex flex-wrap items-center gap-1.5">
                                                <label class="relative inline-flex">
                                                    <input type="file" accept="image/jpeg,image/png,image/webp" class="peer sr-only" :data-testid="`fork-rieng-row-file-${it.id}`" @change="uploadCover($event, it.id)" />
                                                    <span class="inline-flex h-8 cursor-pointer items-center rounded-md border px-3 text-sm font-medium whitespace-nowrap hover:bg-muted peer-focus-visible:outline-2 peer-focus-visible:outline-ring">
                                                        {{ coverBusy[`up-${it.id}`] ? 'Đang tải…' : 'Tải ảnh bìa' }}
                                                    </span>
                                                </label>
                                                <Button type="button" size="sm" variant="outline" class="h-8" :data-testid="`fork-rieng-frame-btn-${it.id}`" @click="frameOpen[it.id] = !frameOpen[it.id]">
                                                    {{ frameOpen[it.id] ? 'Ẩn khung' : 'Chọn khung' }}
                                                </Button>
                                                <Button v-if="rowCover[it.id]" type="button" size="sm" variant="ghost" class="h-8" :data-testid="`fork-rieng-cover-clear-${it.id}`" @click="clearRowCover(it.id)">
                                                    Bỏ bìa riêng
                                                </Button>
                                                <Button
                                                    type="button"
                                                    size="sm"
                                                    variant="ghost"
                                                    class="h-8"
                                                    @click="overrides[it.id] = { caption: overrides[it.id]?.caption ?? '', tags: overrides[it.id]?.tags ?? '', open: !overrides[it.id]?.open }"
                                                >
                                                    {{ overrides[it.id]?.open ? 'Ẩn caption riêng' : 'Sửa caption riêng' }}
                                                </Button>
                                            </div>
                                        </div>
                                    </div>

                                    <div v-if="frameOpen[it.id]" class="flex flex-wrap items-start gap-3 rounded-lg border bg-muted/40 p-2.5">
                                        <video
                                            :id="`rieng-frame-${it.id}`"
                                            :src="`/auto/kho/video/${it.id}`"
                                            class="h-44 rounded bg-black"
                                            preload="metadata"
                                            muted
                                            playsinline
                                            @loadedmetadata="onMeta(it.id, $event)"
                                        />
                                        <div class="flex min-w-48 flex-1 flex-col gap-2">
                                            <input
                                                type="range"
                                                min="0"
                                                :max="frameDur[it.id] ?? 0"
                                                step="0.1"
                                                :value="frameT[it.id] ?? 0"
                                                :disabled="!frameDur[it.id]"
                                                class="w-full"
                                                @input="seek(it.id, Number(($event.target as HTMLInputElement).value))"
                                            />
                                            <span class="text-xs tabular-nums text-muted-foreground">Giây {{ (frameT[it.id] ?? 0).toFixed(1) }} / {{ (frameDur[it.id] ?? 0).toFixed(1) }}</span>
                                            <Button type="button" size="sm" :disabled="coverBusy[`fr-${it.id}`]" class="self-start" :data-testid="`fork-rieng-frame-take-${it.id}`" @click="takeFrame(it.id)">
                                                {{ coverBusy[`fr-${it.id}`] ? 'Đang lấy…' : 'Lấy khung này' }}
                                            </Button>
                                        </div>
                                    </div>
                                    <div v-if="overrides[it.id]?.open" class="flex flex-col gap-1.5">
                                        <textarea v-model="overrides[it.id].caption" :class="areaCls" placeholder="Caption riêng (để trống = dùng caption chung)" />
                                        <Input v-model="overrides[it.id].tags" placeholder="Hashtag riêng (để trống = dùng hashtag chung)" />
                                    </div>
                                </li>
                            </ul>
                        </div>
                    </template>
                </template>
                <!-- BƯỚC 2: xem trước -->
                <template v-else-if="step === 'preview' && plan">
                    <Callout v-if="plan.left > 0" tone="warn">
                        Chỉ xếp được {{ okCount }} video. Còn {{ plan.left }} video chưa có giờ trống, sẽ để lại để bạn đăng sau.
                    </Callout>
                    <Callout v-if="hasWarn" tone="warn">
                        Có giờ gần bài khác của cùng kênh (dưới {{ rules.gap }} phút). Bạn có thể quay lại sửa giờ, hoặc bấm "Vẫn hẹn".
                    </Callout>
                    <ul class="flex flex-col divide-y rounded-lg border text-sm" data-testid="fork-rieng-preview">
                        <li v-for="r in plan.rows" :key="r.id" class="flex flex-col gap-1 p-2.5">
                            <div class="flex flex-wrap items-center gap-2">
                                <ClipThumb :id="r.id" :duration="durationOf(r.id)" :name="nameOf(r)" class="w-9" @zoom="zoomVideo({ id: r.id, file_name: nameOf(r) })" />
                                <button v-if="r.cover?.url" type="button" class="block h-12 w-9 shrink-0 overflow-hidden rounded border bg-muted" :aria-label="`Phóng to ảnh bìa ${nameOf(r)}`" :data-testid="`fork-rieng-preview-cover-${r.id}`" @click="zoomCover(r.cover.url!, `Bìa · ${nameOf(r)}`)">
                                    <img :src="r.cover.url" alt="Ảnh bìa" class="size-full object-cover" />
                                </button>
                                <span class="min-w-0 flex-1 truncate font-medium">
                                    {{ nameOf(r) }}
                                    <span v-if="r.cover" class="block text-xs font-normal text-muted-foreground">Bìa: {{ r.cover.note }}</span>
                                </span>
                                <span class="tabular-nums">{{ fmt(r.at) }}</span>
                                <span :class="cn('rounded-full px-2 py-0.5 text-xs font-medium', chip(r.status))">
                                    {{ { ok: 'Ổn', warn: 'Gần giờ bài khác', error: 'Không hẹn được', skip: 'Để lại' }[r.status] }}
                                </span>
                            </div>
                            <p v-if="r.duplicate" class="text-xs text-amber-800 dark:text-amber-300">{{ r.duplicate }}</p>
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
                                <ClipThumb :id="r.id" :duration="durationOf(r.id)" :name="nameOf(r)" class="w-9" @zoom="zoomVideo({ id: r.id, file_name: nameOf(r) })" />
                                <span class="min-w-0 flex-1 truncate font-medium">{{ nameOf(r) }}</span>
                                <span class="tabular-nums">{{ r.result === 'done' ? fmt(r.at) : '' }}</span>
                                <span :class="cn('rounded-full px-2 py-0.5 text-xs font-medium', chip(r.result === 'done' ? 'ok' : r.result === 'skip' ? 'skip' : 'error'))">
                                    {{ r.result === 'done' ? 'Đã hẹn giờ' : r.result === 'skip' ? 'Để lại' : 'Lỗi' }}
                                </span>
                            </div>
                            <p v-if="r.error" class="text-xs text-red-600 dark:text-red-400">{{ r.error }}</p>
                            <p v-for="m in r.result === 'error' && !r.error ? r.messages : []" :key="m" class="text-xs text-muted-foreground">{{ m }}</p>
                        </li>
                    </ul>
                </template>
            </div>

            <div class="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t bg-background px-5 py-3.5 sm:px-6">
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

        <MediaLightbox
            :open="lightbox !== null"
            :kind="lightbox?.kind ?? 'image'"
            :src="lightbox?.src ?? null"
            :title="lightbox?.title"
            :poster="lightbox?.poster"
            @update:open="(v: boolean) => !v && (lightbox = null)"
        />
    </Dialog>
</template>

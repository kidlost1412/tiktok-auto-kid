<script setup lang="ts">
// Chỉnh "tự đăng" của một video riêng: xem AI thấy gì, chọn sản phẩm, sửa caption, duyệt, chọn kênh, cho đăng video trùng.
import {
    IconCheck,
    IconLoader2,
    IconRefresh,
    IconEye,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import {
    callJson,
    type AutoPayload,
    type RiengAuto,
    type RiengVideo,
} from '@/components/fork/kho/rieng';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { NativeSelect } from '@/components/ui/native-select';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

const open = defineModel<boolean>('open', { default: false });
const props = defineProps<{
    video: RiengVideo | null;
    payload: AutoPayload | null;
}>();
const emit = defineEmits<{ saved: [id: number, auto: RiengAuto] }>();

const auto = ref<RiengAuto | null>(null);
const product = ref('');
const quyCach = ref('');
const caption = ref('');
const tags = ref('');
const channels = ref<string[]>([]);
let poll: ReturnType<typeof setInterval> | null = null;
const busy = ref<'save' | 'ai' | null>(null);

watch(
    () => [open.value, props.video?.id],
    () => {
        if (!open.value || !props.video) {
            return;
        }

        auto.value = props.video.auto ?? null;
        reset();

        if (auto.value?.ai_progress) {
            watchAi();
        }
    },
    { immediate: true },
);

watch(open, (o) => {
    if (!o) {
        stopPoll();
    }
});

onBeforeUnmount(() => stopPoll());

const tagsOf = (a: RiengAuto | null) =>
    (a?.kid_hashtags ?? a?.ai_hashtags ?? []).join(' ');

function reset() {
    const a = auto.value;
    product.value = a?.product_by === 'kid' ? (a.product_code ?? '') : '';
    quyCach.value = a?.quy_cach ?? '';
    caption.value = a?.kid_caption ?? a?.ai_caption ?? '';
    tags.value = tagsOf(a);
    channels.value = [...(a?.channels ?? [])];
}

const settings = computed(() => props.payload?.settings);
const productName = (code: string | null) =>
    props.payload?.products.find((p) => p.code === code)?.name ?? code ?? '';
const quyOptions = computed(
    () =>
        props.payload?.products.find(
            (p) => p.code === (product.value || auto.value?.product_code),
        )?.quy_cach ?? [],
);

const sureText = computed(() => {
    const a = auto.value;

    if (a?.ai_progress) {
        const p = a.ai_progress;

        return p.tong
            ? `AI đang xem (bước ${p.buoc}/${p.tong}): ${p.viec}…`
            : 'AI sắp xem video này…';
    }

    if (!a?.ai_state) {
        return 'AI chưa xem video này.';
    }

    if (a.ai_state === 'error' && !a.ai_tries) {
        return 'AI sẽ xem video này trong vòng 2 phút.';
    }

    if (a.ai_state === 'error' || a.ai_state === 'gave_up') {
        const due = a.ai_next_try_at ? new Date(a.ai_next_try_at) : null;
        const when =
            a.ai_state === 'gave_up' || !due
                ? 'Đã thử nhiều lần chưa được, anh bấm "AI xem lại".'
                : due.getTime() <= Date.now() + 60_000
                  ? 'App sẽ thử lại trong vòng 2 phút.'
                  : `App tự thử lại lúc ${due.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}.`;

        return `AI chưa xem được (${a.ai_error ?? 'lỗi'}). ${when}`;
    }

    if (!a.ai_product) {
        return 'AI không nhận ra sản phẩm nào trong danh sách.';
    }

    const lvl = { cao: 'chắc chắn', vua: 'khá chắc', thap: 'không chắc' }[
        a.ai_sure ?? 'thap'
    ];

    return `AI đoán: ${productName(a.ai_product)} (${lvl})`;
});

const toggleChannel = (id: string) => {
    channels.value = channels.value.includes(id)
        ? channels.value.filter((c) => c !== id)
        : [...channels.value, id];
};

const send = async (body: Record<string, unknown>, quiet = false) => {
    if (!props.video) {
        return false;
    }

    busy.value = 'save';
    const r = await callJson<{ ok: boolean; error?: string; auto: RiengAuto }>(
        'POST',
        `/auto/kho/rieng/video/${props.video.id}/tu-dong`,
        body,
    );
    busy.value = null;

    if (!r.ok || !r.data?.auto) {
        toast.error(r.data?.error ?? 'Chưa lưu được, anh thử lại');

        return false;
    }

    auto.value = r.data.auto;
    emit('saved', props.video.id, r.data.auto);

    if (!quiet) {
        toast.success('Đã lưu');
    }

    return true;
};

const save = async () => {
    const a = auto.value;
    // Caption: giống hệt caption AI thì coi như chưa tự viết (để AI viết lại còn được dùng).
    const cap = caption.value.trim();
    const own = cap !== '' && cap !== (a?.ai_caption ?? '').trim() ? cap : '';
    // Hashtag: giống hệt hashtag AI thì giữ "theo AI" (AI xem lại còn cập nhật được).
    const list = tags.value
        .split(/[\s,]+/)
        .map((t) => t.trim())
        .filter((t) => t.replace(/^#+/, '') !== '');
    const sameAsAi = list.join(' ') === (a?.ai_hashtags ?? []).join(' ');
    const ok = await send({
        product_code: product.value || null,
        quy_cach: quyCach.value || null,
        caption: own,
        hashtags: sameAsAi ? null : list,
        channels: channels.value,
        ...(settings.value?.approve_first && cap !== ''
            ? { approved: true }
            : {}),
    });

    if (ok) {
        open.value = false;
    }
};

// ---- AI xem lại: chạy ngay ở nền, trang hỏi tiến độ mỗi 3 giây tới khi xong.
const stopPoll = () => {
    if (poll) {
        clearInterval(poll);
        poll = null;
    }
};

const watchAi = () => {
    stopPoll();
    const id = props.video?.id;

    if (!id) {
        return;
    }

    poll = setInterval(async () => {
        if (document.visibilityState !== 'visible') {
            return;
        }

        const r = await callJson<{ auto: RiengAuto }>(
            'GET',
            `/auto/kho/rieng/video/${id}/trang-thai`,
        );

        if (!r.data?.auto || props.video?.id !== id) {
            return;
        }

        const was = auto.value;
        auto.value = r.data.auto;

        if (!r.data.auto.ai_progress) {
            stopPoll();
            emit('saved', id, r.data.auto);

            // Anh chưa sửa gì thì cập nhật caption / hashtag theo kết quả mới.
            if (caption.value === (was?.kid_caption ?? was?.ai_caption ?? '')) {
                caption.value =
                    r.data.auto.kid_caption ?? r.data.auto.ai_caption ?? '';
            }

            if (tags.value === tagsOf(was)) {
                tags.value = tagsOf(r.data.auto);
            }

            if (r.data.auto.ai_state === 'ok') {
                toast.success('AI đã nhận ra sản phẩm');
            } else if (r.data.auto.ai_state === 'unsure') {
                toast('AI xem xong nhưng chưa chắc sản phẩm, anh chọn giúp');
            } else {
                toast.error('AI chưa xem được video này');
            }
        }
    }, 3000);
};

const reanalyze = async () => {
    if (!props.video) {
        return;
    }

    busy.value = 'ai';
    const r = await callJson<{
        ok: boolean;
        error?: string | null;
        auto: RiengAuto;
    }>('POST', `/auto/kho/rieng/video/${props.video.id}/ai-xem-lai`);
    busy.value = null;

    if (r.ok && r.data?.auto) {
        auto.value = r.data.auto;
        emit('saved', props.video.id, r.data.auto);
        watchAi();
    } else {
        toast.error(r.data?.error ?? 'Chưa cho AI xem lại được, anh thử lại');
    }
};

const aiBusy = computed(() => busy.value === 'ai' || !!auto.value?.ai_progress);
const showSteps = ref(false);

const chipCls = (on: boolean) =>
    cn(
        'inline-flex items-center gap-1.5 rounded-lg border py-0.5 pr-3 pl-0.5 text-sm font-medium transition',
        on
            ? 'border-primary bg-primary-subtle text-foreground'
            : 'border-border bg-background text-foreground/80 hover:border-foreground/40',
    );

const initial = (name: string) =>
    name.replace(/^@/, '').charAt(0).toUpperCase() || '?';
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent
            class="max-h-[90dvh] overflow-x-hidden overflow-y-auto sm:max-w-xl"
            data-testid="fork-rieng-auto-edit"
        >
            <DialogHeader>
                <DialogTitle class="pr-6 text-base break-all">{{
                    video?.file_name
                }}</DialogTitle>
                <DialogDescription>
                    Tự đăng theo khung: sản phẩm, caption và kênh của video này.
                </DialogDescription>
            </DialogHeader>

            <div v-if="video" class="flex min-w-0 flex-col gap-4 text-sm">
                <!-- AI thấy gì -->
                <section class="rounded-xl border bg-muted/30 p-3">
                    <div class="flex items-start justify-between gap-2">
                        <div class="flex items-center gap-1.5 font-semibold">
                            <IconEye class="size-4 shrink-0 text-muted-foreground" />
                            {{ sureText }}
                        </div>
                        <Button
                            size="sm"
                            variant="outline"
                            class="h-7 shrink-0"
                            :disabled="busy !== null || aiBusy"
                            data-testid="fork-rieng-ai-again"
                            @click="reanalyze"
                        >
                            <IconLoader2
                                v-if="aiBusy"
                                class="size-3.5 animate-spin"
                            />
                            <IconRefresh v-else class="size-3.5" />
                            {{ aiBusy ? 'AI đang xem…' : 'AI xem lại' }}
                        </Button>
                    </div>
                    <div
                        v-if="auto?.ai_progress?.tong"
                        class="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"
                    >
                        <div
                            class="h-full rounded-full bg-primary transition-all"
                            :style="{
                                width:
                                    Math.round(
                                        (auto.ai_progress.buoc /
                                            auto.ai_progress.tong) *
                                            100,
                                    ) + '%',
                            }"
                        />
                    </div>
                    <p
                        v-if="auto?.ai_reason"
                        class="mt-1 text-sm text-foreground/70"
                    >
                        Vì: {{ auto.ai_reason }}
                    </p>
                    <p v-if="auto?.ai_summary" class="mt-1 text-sm">
                        Video: {{ auto.ai_summary }}
                    </p>
                    <details
                        v-if="auto?.ai_heard"
                        class="mt-1 text-sm"
                        data-testid="fork-rieng-ai-heard"
                    >
                        <summary class="cursor-pointer font-medium">
                            Lời nói app nghe được
                        </summary>
                        <p class="mt-1 whitespace-pre-line text-foreground/80">
                            {{ auto.ai_heard }}
                        </p>
                    </details>
                    <div
                        v-if="auto?.ai_steps?.length && !auto.ai_progress"
                        class="mt-1 text-sm"
                    >
                        <button
                            type="button"
                            class="font-medium underline"
                            @click="showSteps = !showSteps"
                        >
                            AI đã thử {{ auto.ai_steps.length }} cách
                        </button>
                        <ol
                            v-if="showSteps"
                            class="mt-1 list-decimal pl-5 text-foreground/80"
                        >
                            <li v-for="(st, i) in auto.ai_steps" :key="i">
                                {{ st.buoc }} → {{ st.ket_qua }}
                            </li>
                        </ol>
                    </div>
                </section>

                <!-- Sản phẩm -->
                <section class="flex flex-col gap-1.5">
                    <h3 class="text-base font-semibold">Sản phẩm gắn giỏ</h3>
                    <NativeSelect
                        v-model="product"
                        aria-label="Sản phẩm"
                        class="w-full"
                    >
                        <option value="">
                            Theo AI{{
                                auto?.ai_state === 'ok' && auto.ai_product
                                    ? ` (${productName(auto.ai_product)})`
                                    : ' (chưa chắc, chưa gắn)'
                            }}
                        </option>
                        <option
                            v-for="p in payload?.products ?? []"
                            :key="p.code"
                            :value="p.code"
                        >
                            {{ p.name }}
                        </option>
                    </NativeSelect>
                    <NativeSelect
                        v-if="quyOptions.length"
                        v-model="quyCach"
                        aria-label="Quy cách"
                        class="w-full"
                    >
                        <option value="">
                            Quy cách: tự chọn theo giỏ của kênh
                        </option>
                        <option
                            v-for="q in quyOptions"
                            :key="q.ma"
                            :value="q.ma"
                        >
                            {{ q.ten }}
                        </option>
                    </NativeSelect>
                </section>

                <!-- Caption -->
                <section class="flex flex-col gap-1.5">
                    <h3 class="text-base font-semibold">Caption</h3>
                    <textarea
                        v-model="caption"
                        rows="3"
                        maxlength="2200"
                        class="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                        :placeholder="
                            settings?.empty_caption_ok
                                ? 'Để trống thì đăng không chữ'
                                : 'Viết caption cho video này'
                        "
                    />
                    <div
                        class="flex flex-wrap items-center justify-between gap-2 text-sm text-foreground/70"
                    >
                        <span
                            >{{ caption.length }} ký tự · hashtag sản phẩm app
                            tự thêm</span
                        >
                        <button
                            v-if="
                                auto?.ai_caption && caption !== auto.ai_caption
                            "
                            type="button"
                            class="underline"
                            @click="caption = auto?.ai_caption ?? ''"
                        >
                            Dùng lại caption AI
                        </button>
                    </div>
                    <div class="flex flex-col gap-1">
                        <span class="font-medium">Hashtag</span>
                        <input
                            v-model="tags"
                            type="text"
                            class="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                            placeholder="#vuoncaphe #ruavuon"
                            aria-label="Hashtag của video"
                            data-testid="fork-rieng-hashtags"
                        />
                        <div
                            class="flex flex-wrap items-center justify-between gap-2 text-sm text-foreground/70"
                        >
                            <span
                                >Cách nhau bằng dấu cách. Để trống = không
                                hashtag.</span
                            >
                            <button
                                v-if="
                                    auto?.ai_hashtags?.length &&
                                    tags !== (auto.ai_hashtags ?? []).join(' ')
                                "
                                type="button"
                                class="underline"
                                @click="
                                    tags = (auto?.ai_hashtags ?? []).join(' ')
                                "
                            >
                                Dùng lại hashtag AI
                            </button>
                        </div>
                    </div>
                    <label
                        v-if="settings?.approve_first && auto?.ai_caption"
                        class="flex items-center justify-between gap-3"
                    >
                        <span class="font-medium">Đã duyệt caption AI</span>
                        <Switch
                            :model-value="auto?.approved ?? false"
                            @update:model-value="
                                (v: boolean) => send({ approved: v }, true)
                            "
                        />
                    </label>
                </section>

                <!-- Kênh -->
                <section class="flex flex-col gap-1.5">
                    <h3 class="text-base font-semibold">Kênh đăng video này</h3>
                    <div class="flex flex-wrap items-center gap-1.5">
                        <button
                            type="button"
                            :class="
                                cn(chipCls(channels.length === 0), 'pl-2.5')
                            "
                            :aria-pressed="channels.length === 0"
                            @click="channels = []"
                        >
                            <IconCheck
                                v-if="channels.length === 0"
                                class="size-3.5 text-muted-foreground"
                                stroke-width="3"
                            />
                            Theo thư mục / mọi kênh
                        </button>
                        <button
                            v-for="c in payload?.channels ?? []"
                            :key="c.id"
                            type="button"
                            :class="chipCls(channels.includes(c.id))"
                            :aria-pressed="channels.includes(c.id)"
                            @click="toggleChannel(c.id)"
                        >
                            <Avatar class="size-6 shrink-0">
                                <AvatarImage
                                    v-if="c.avatar_url"
                                    :src="c.avatar_url"
                                    alt=""
                                />
                                <AvatarFallback
                                    class="text-xs font-semibold"
                                    >{{ initial(c.name) }}</AvatarFallback
                                >
                            </Avatar>
                            {{ c.name }}
                            <IconCheck
                                v-if="channels.includes(c.id)"
                                class="size-3.5 text-muted-foreground"
                                stroke-width="3"
                            />
                        </button>
                    </div>
                </section>

                <!-- Video trùng -->
                <section
                    v-if="video.duplicate && settings?.duplicates === 'ask'"
                    class="flex items-center justify-between gap-3 rounded-lg border border-l-4 border-l-warning bg-card p-3 text-foreground"
                >
                    <span class="text-sm font-medium"
                        >{{ video.duplicate.text }}. Vẫn đăng?</span
                    >
                    <Switch
                        :model-value="auto?.dup_ok ?? false"
                        aria-label="Vẫn đăng video trùng"
                        @update:model-value="
                            (v: boolean) => send({ dup_ok: v }, true)
                        "
                    />
                </section>

                <div class="flex justify-end gap-2">
                    <Button variant="ghost" @click="open = false">Đóng</Button>
                    <Button
                        :disabled="busy !== null"
                        data-testid="fork-rieng-auto-save"
                        @click="save"
                    >
                        <IconLoader2
                            v-if="busy === 'save'"
                            class="size-4 animate-spin"
                        />
                        {{
                            settings?.approve_first && caption.trim()
                                ? 'Lưu & duyệt'
                                : 'Lưu'
                        }}
                    </Button>
                </div>
            </div>
        </DialogContent>
    </Dialog>
</template>

<script setup lang="ts">
// Chỉnh "tự đăng" của một video riêng: xem AI thấy gì, chọn sản phẩm, sửa caption, duyệt, chọn kênh, cho đăng video trùng.
import { IconLoader2, IconRefresh, IconSparkles } from '@tabler/icons-vue';
import { computed, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import {
    callJson,
    type AutoPayload,
    type RiengAuto,
    type RiengVideo,
} from '@/components/fork/kho/rieng';
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
const channels = ref<string[]>([]);
const busy = ref<'save' | 'ai' | null>(null);

watch(
    () => [open.value, props.video?.id],
    () => {
        if (!open.value || !props.video) {
            return;
        }

        auto.value = props.video.auto ?? null;
        reset();
    },
    { immediate: true },
);

function reset() {
    const a = auto.value;
    product.value = a?.product_by === 'kid' ? (a.product_code ?? '') : '';
    quyCach.value = a?.quy_cach ?? '';
    caption.value = a?.kid_caption ?? a?.ai_caption ?? '';
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

    if (!a?.ai_state) {
        return 'AI chưa xem video này.';
    }

    if (a.ai_state === 'error' || a.ai_state === 'gave_up') {
        return `AI chưa xem được: ${a.ai_error ?? 'lỗi'}`;
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
        toast.error(r.data?.error ?? 'Chưa lưu được, anh thử lại.');

        return false;
    }

    auto.value = r.data.auto;
    emit('saved', props.video.id, r.data.auto);

    if (!quiet) {
        toast.success('Đã lưu.');
    }

    return true;
};

const save = async () => {
    const a = auto.value;
    // Caption: giống hệt caption AI thì coi như chưa tự viết (để AI viết lại còn được dùng).
    const cap = caption.value.trim();
    const own = cap !== '' && cap !== (a?.ai_caption ?? '').trim() ? cap : '';
    const ok = await send({
        product_code: product.value || null,
        quy_cach: quyCach.value || null,
        caption: own,
        channels: channels.value,
        ...(settings.value?.approve_first && cap !== ''
            ? { approved: true }
            : {}),
    });

    if (ok) {
        open.value = false;
    }
};

const reanalyze = async () => {
    if (!props.video) {
        return;
    }

    busy.value = 'ai';
    const r = await callJson<{
        ok: boolean;
        error: string | null;
        auto: RiengAuto;
    }>('POST', `/auto/kho/rieng/video/${props.video.id}/ai-xem-lai`);
    busy.value = null;

    if (r.data?.auto) {
        auto.value = r.data.auto;
        emit('saved', props.video.id, r.data.auto);
        reset();
    }

    if (r.ok && r.data?.ok) {
        toast.success('AI đã xem lại video.');
    } else {
        toast.error(r.data?.error ?? 'AI chưa xem được, anh thử lại sau.');
    }
};

const chipCls = (on: boolean) =>
    cn(
        'rounded-full border px-2.5 py-0.5 text-xs transition',
        on
            ? 'border-primary bg-primary text-primary-foreground'
            : 'hover:bg-muted',
    );
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
                        <div class="flex items-center gap-1.5 font-medium">
                            <IconSparkles class="size-4 shrink-0" />
                            {{ sureText }}
                        </div>
                        <Button
                            size="sm"
                            variant="outline"
                            class="h-7 shrink-0"
                            :disabled="busy !== null"
                            @click="reanalyze"
                        >
                            <IconLoader2
                                v-if="busy === 'ai'"
                                class="size-3.5 animate-spin"
                            />
                            <IconRefresh v-else class="size-3.5" />
                            {{ busy === 'ai' ? 'AI đang xem…' : 'AI xem lại' }}
                        </Button>
                    </div>
                    <p
                        v-if="auto?.ai_reason"
                        class="mt-1 text-xs text-muted-foreground"
                    >
                        Vì: {{ auto.ai_reason }}
                    </p>
                    <p v-if="auto?.ai_summary" class="mt-1 text-xs">
                        Video: {{ auto.ai_summary }}
                    </p>
                    <details v-if="auto?.ai_speech" class="mt-1 text-xs">
                        <summary class="cursor-pointer text-muted-foreground">
                            Lời nói trong video
                        </summary>
                        <p class="mt-1 whitespace-pre-line">
                            {{ auto.ai_speech }}
                        </p>
                    </details>
                </section>

                <!-- Sản phẩm -->
                <section class="flex flex-col gap-1.5">
                    <h3 class="font-semibold">Sản phẩm gắn giỏ</h3>
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
                    <h3 class="font-semibold">Caption</h3>
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
                        class="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground"
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
                    <label
                        v-if="settings?.approve_first && auto?.ai_caption"
                        class="flex items-center justify-between gap-3"
                    >
                        <span>Đã duyệt caption AI</span>
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
                    <h3 class="font-semibold">Kênh đăng video này</h3>
                    <div class="flex flex-wrap items-center gap-1.5">
                        <button
                            type="button"
                            :class="chipCls(channels.length === 0)"
                            @click="channels = []"
                        >
                            Theo thư mục / mọi kênh
                        </button>
                        <button
                            v-for="c in payload?.channels ?? []"
                            :key="c.id"
                            type="button"
                            :class="chipCls(channels.includes(c.id))"
                            @click="toggleChannel(c.id)"
                        >
                            {{ c.name }}
                        </button>
                    </div>
                </section>

                <!-- Video trùng -->
                <section
                    v-if="video.duplicate && settings?.duplicates === 'ask'"
                    class="flex items-center justify-between gap-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
                >
                    <span class="text-xs"
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

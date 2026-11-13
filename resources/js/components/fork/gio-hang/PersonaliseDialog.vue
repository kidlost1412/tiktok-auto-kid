<script setup lang="ts">
// "Cá nhân hoá" một sản phẩm hub: ảnh bìa riêng (cố định / ngẫu nhiên trong bộ ảnh) và hashtag riêng.
// scope = 'default' thì chỉ có phần hashtag mặc định chung (áp cho sản phẩm không có hashtag riêng).
// Bố cục: tiêu đề cố định, thân cuộn được gồm các khối (Ảnh bìa, Hashtag, Caption cuối cùng), chân có nút Lưu luôn nằm dưới cùng.
import { router } from '@inertiajs/vue3';
import {
    IconArrowsShuffle,
    IconCheck,
    IconHash,
    IconMovie,
    IconPhoto,
    IconPhotoCheck,
    IconPhotoPlus,
    IconTrash,
    IconZoomIn,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';

import CoverPreview from '@/components/fork/gio-hang/CoverPreview.vue';
import type { Persona } from '@/components/fork/gio-hang/types';
import HashtagChips from '@/components/fork/shared/HashtagChips.vue';
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
import { cn } from '@/lib/utils';

const props = defineProps<{
    open: boolean;
    scope: 'product' | 'default';
    code: string;
    label: string;
    state: Persona;
}>();

const emit = defineEmits<{ 'update:open': [value: boolean] }>();

const isProduct = computed(() => props.scope === 'product');

const coverMode = ref<'default' | 'fixed' | 'random'>('default');
const coverFixed = ref<string | null>(null);
/** Hashtag dạng chuỗi cách nhau bằng dấu cách (đúng định dạng máy chủ nhận). */
const tags = ref('');
const tagMode = ref<'append' | 'replace'>('append');
const pick = ref(0);
const sample = ref('');
const busy = ref(false);
const dragging = ref(false);
const preview = ref<{ text: string; length: number; max: number } | null>(
    null,
);
const fileInput = ref<HTMLInputElement | null>(null);
/** Ảnh đang xem trước ở chế độ ngẫu nhiên (bấm ảnh để đổi). */
const previewFile = ref<string | null>(null);
/** Ảnh đang phóng to (lightbox). */
const zoom = ref<{ url: string; name: string } | null>(null);

watch(
    () => props.open,
    (open) => {
        if (!open) {
            zoom.value = null;

            return;
        }

        coverMode.value = props.state.cover_mode ?? 'default';
        coverFixed.value = props.state.cover_fixed ?? null;
        tags.value = (props.state.hashtags ?? []).join(' ');
        tagMode.value = props.state.hashtag_mode ?? 'append';
        pick.value = props.state.hashtag_pick ?? 0;
        sample.value = '';
        previewFile.value = null;
        void loadPreview();
    },
);

const covers = computed(() => props.state.covers ?? []);

const effectiveFixed = computed(
    () =>
        covers.value.find((c) => c.file === coverFixed.value)?.file ??
        covers.value[0]?.file ??
        null,
);

// Cố định: xem đúng ảnh đã chọn. Ngẫu nhiên: ảnh vừa bấm, mặc định ảnh đầu tiên.
const previewCover = computed(() => {
    const file =
        coverMode.value === 'fixed' ? effectiveFixed.value : previewFile.value;

    return covers.value.find((c) => c.file === file) ?? covers.value[0] ?? null;
});

function selectCover(file: string) {
    if (coverMode.value === 'fixed') {
        coverFixed.value = file;
    } else {
        previewFile.value = file;
    }
}

const tagCount = computed(
    () => tags.value.split(/[\s,;]+/).filter((t) => t.replace(/#/g, '')).length,
);

watch(tagCount, (n) => {
    // Số hashtag giảm xuống dưới số "chọn ngẫu nhiên" thì kéo số đó xuống theo để khỏi vô nghĩa.
    if (pick.value > n) {
        pick.value = n;
    }
});

// ---- Xem trước caption (gọi server để đúng y như lúc đăng) ----
let timer: ReturnType<typeof setTimeout> | null = null;

const xsrf = () =>
    decodeURIComponent(document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '');

const previewUrl = computed(() =>
    isProduct.value
        ? `/auto/products/${encodeURIComponent(props.code)}/personalise/preview`
        : '/auto/hashtag-mac-dinh/preview',
);

async function loadPreview() {
    try {
        const r = await fetch(previewUrl.value, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-XSRF-TOKEN': xsrf(),
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                sample: sample.value,
                hashtags: tags.value,
                hashtag_mode: tagMode.value,
                hashtag_pick: Number(pick.value) || 0,
            }),
        });

        if (r.ok) {
            preview.value = await r.json();
        }
    } catch {
        preview.value = null;
    }
}

watch([tags, tagMode, pick, sample], () => {
    if (timer) {
        clearTimeout(timer);
    }

    timer = setTimeout(loadPreview, 350);
});
onBeforeUnmount(() => {
    if (timer) {
        clearTimeout(timer);
    }
});

// ---- Ảnh bìa ----
const base = computed(() => `/auto/products/${encodeURIComponent(props.code)}`);

function uploadFiles(files: File[]) {
    const images = files.filter((f) => /^image\/(jpeg|png|webp)$/.test(f.type));

    if (!images.length) {
        return;
    }

    busy.value = true;
    router.post(
        `${base.value}/covers`,
        { images },
        {
            forceFormData: true,
            preserveScroll: true,
            only: ['personalise', 'flash', 'errors'],
            onFinish: () => {
                busy.value = false;

                if (fileInput.value) {
                    fileInput.value.value = '';
                }
            },
        },
    );
}

function upload(ev: Event) {
    uploadFiles(Array.from((ev.target as HTMLInputElement).files ?? []));
}

function onDrop(ev: DragEvent) {
    dragging.value = false;
    uploadFiles(Array.from(ev.dataTransfer?.files ?? []));
}

function removeCover(file: string) {
    if (!window.confirm('Xoá ảnh bìa này?')) {
        return;
    }

    busy.value = true;
    router.delete(`${base.value}/covers/${file}`, {
        preserveScroll: true,
        only: ['personalise', 'flash'],
        onFinish: () => {
            busy.value = false;
        },
    });
}

// ---- Lưu ----
function save() {
    busy.value = true;
    const done = {
        preserveScroll: true,
        onSuccess: () => emit('update:open', false),
        onFinish: () => {
            busy.value = false;
        },
    };

    if (isProduct.value) {
        router.put(
            `${base.value}/personalise`,
            {
                cover_mode: coverMode.value,
                cover_fixed: effectiveFixed.value,
                hashtags: tags.value,
                hashtag_mode: tagMode.value,
                hashtag_pick: Number(pick.value) || 0,
            },
            done,
        );
    } else {
        router.put(
            '/auto/hashtag-mac-dinh',
            {
                hashtags: tags.value,
                hashtag_mode: tagMode.value,
                hashtag_pick: Number(pick.value) || 0,
            },
            done,
        );
    }
}

const modes = [
    {
        v: 'default',
        t: 'Mặc định',
        d: 'TikTok tự lấy khung hình trong video',
        icon: IconMovie,
    },
    {
        v: 'fixed',
        t: 'Một ảnh cố định',
        d: 'Mọi bài của sản phẩm dùng cùng một ảnh',
        icon: IconPhotoCheck,
    },
    {
        v: 'random',
        t: 'Ngẫu nhiên',
        d: 'Xoay vòng đều các ảnh trong bộ',
        icon: IconArrowsShuffle,
    },
] as const;

const tagModes = [
    {
        v: 'append',
        t: 'Thêm vào cuối caption',
        d: 'Giữ hashtag hub đã viết, thêm hashtag của bạn phía sau.',
    },
    {
        v: 'replace',
        t: 'Thay toàn bộ hashtag',
        d: 'Bỏ hashtag cũ trong caption, chỉ dùng hashtag của bạn.',
    },
] as const;

const card = 'rounded-xl border bg-card p-4 sm:p-5';
</script>

<template>
    <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
        <DialogContent
            class="flex max-h-[90dvh] flex-col gap-0 overflow-hidden p-0 sm:max-w-[min(48rem,calc(100%-2rem))]"
            data-testid="fork-personalise-dialog"
        >
            <DialogHeader class="shrink-0 border-b px-5 pt-5 pr-14 pb-4 sm:px-6">
                <DialogTitle class="text-lg">
                    {{
                        isProduct
                            ? 'Ảnh bìa & hashtag'
                            : 'Hashtag mặc định chung'
                    }}
                </DialogTitle>
                <DialogDescription>
                    <template v-if="isProduct">
                        <b class="font-medium text-foreground">{{ label }}</b>
                        · áp cho mọi bài của sản phẩm này (mọi quy cách, mọi
                        kênh).
                    </template>
                    <template v-else>
                        Dùng cho sản phẩm không có hashtag riêng.
                    </template>
                </DialogDescription>
            </DialogHeader>

            <!-- Chỉ phần giữa cuộn: nút Đóng/Lưu luôn thấy trên màn hình thấp. -->
            <div
                class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto bg-muted/30 px-5 py-5 sm:px-6"
            >
                <!-- 1. Ảnh bìa -->
                <section v-if="isProduct" :class="card" class="flex flex-col gap-4">
                    <div class="flex items-start gap-3">
                        <span
                            class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary-subtle text-primary-text"
                            ><IconPhoto class="size-4"
                        /></span>
                        <div class="min-w-0">
                            <h3 class="text-base leading-tight font-semibold">
                                Ảnh bìa
                            </h3>
                            <p class="text-sm text-muted-foreground">
                                Ảnh hiện ở ô bài đăng trên trang cá nhân TikTok.
                            </p>
                        </div>
                    </div>

                    <div
                        class="grid gap-2 sm:grid-cols-3"
                        role="radiogroup"
                        aria-label="Kiểu ảnh bìa"
                    >
                        <label
                            v-for="m in modes"
                            :key="m.v"
                            :class="
                                cn(
                                    'relative flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring/50',
                                    coverMode === m.v
                                        ? 'border-primary bg-primary/5 ring-1 ring-primary/40'
                                        : 'hover:bg-muted/50',
                                )
                            "
                        >
                            <input
                                v-model="coverMode"
                                type="radio"
                                name="cover-mode"
                                :value="m.v"
                                class="sr-only"
                            />
                            <component
                                :is="m.icon"
                                :class="
                                    cn(
                                        'mt-0.5 size-4 shrink-0',
                                        coverMode === m.v
                                            ? 'text-primary-text'
                                            : 'text-muted-foreground',
                                    )
                                "
                            />
                            <span class="flex min-w-0 flex-col gap-0.5">
                                <span class="font-medium">{{ m.t }}</span>
                                <span class="text-xs text-muted-foreground">{{
                                    m.d
                                }}</span>
                            </span>
                            <IconCheck
                                v-if="coverMode === m.v"
                                class="absolute top-2 right-2 size-3.5 text-primary-text"
                            />
                        </label>
                    </div>

                    <template v-if="coverMode !== 'default'">
                        <div
                            :class="
                                cn(
                                    'flex flex-col gap-4 rounded-lg border border-dashed p-3 transition-colors sm:flex-row sm:p-4',
                                    dragging
                                        ? 'border-primary bg-primary/5'
                                        : 'bg-muted/20',
                                )
                            "
                            @dragover.prevent="dragging = true"
                            @dragleave.prevent="dragging = false"
                            @drop.prevent="onDrop"
                        >
                            <!-- Ảnh đang chọn / đang xem: bấm để phóng to -->
                            <div
                                v-if="previewCover"
                                class="flex shrink-0 flex-col items-center gap-1.5 sm:w-48"
                            >
                                <button
                                    type="button"
                                    class="group relative aspect-[3/4] w-36 overflow-hidden rounded-lg border bg-muted shadow-sm focus-visible:outline-2 focus-visible:outline-ring sm:w-full"
                                    :aria-label="`Phóng to ảnh ${previewCover.name}`"
                                    data-testid="fork-personalise-cover-main"
                                    @click="
                                        zoom = {
                                            url: previewCover.url,
                                            name: previewCover.name,
                                        }
                                    "
                                >
                                    <img
                                        :src="previewCover.url"
                                        :alt="previewCover.name"
                                        class="size-full object-cover"
                                    />
                                    <span
                                        class="absolute top-2 left-2 rounded-full bg-black/60 px-2 py-0.5 text-[0.6875rem] font-medium text-white"
                                    >
                                        {{
                                            coverMode === 'fixed'
                                                ? 'Ảnh sẽ dùng'
                                                : 'Ví dụ 1 ảnh'
                                        }}
                                    </span>
                                    <span
                                        class="absolute inset-0 flex items-center justify-center bg-black/0 text-white opacity-0 transition group-hover:bg-black/30 group-hover:opacity-100 group-focus-visible:opacity-100"
                                    >
                                        <IconZoomIn class="size-7" />
                                    </span>
                                </button>
                                <span class="text-xs text-muted-foreground"
                                    >{{ previewCover.w }}×{{
                                        previewCover.h
                                    }}
                                    · bấm để phóng to</span
                                >
                            </div>

                            <!-- Bộ ảnh -->
                            <div class="flex min-w-0 flex-1 flex-col gap-2.5">
                                <div
                                    class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5"
                                >
                                    <span class="text-sm font-medium"
                                        >Bộ ảnh
                                        <span
                                            class="font-normal text-muted-foreground"
                                            >({{ covers.length }})</span
                                        ></span
                                    >
                                    <span class="text-xs text-muted-foreground">
                                        {{
                                            coverMode === 'fixed'
                                                ? 'Bấm một ảnh để chọn làm ảnh cố định'
                                                : 'Bấm một ảnh để xem thử; mỗi bài sẽ lấy một ảnh trong bộ'
                                        }}
                                    </span>
                                </div>

                                <div
                                    class="grid grid-cols-3 gap-2 sm:grid-cols-4"
                                    data-testid="fork-personalise-covers"
                                >
                                    <div
                                        v-for="c in covers"
                                        :key="c.file"
                                        :class="
                                            cn(
                                                'group relative overflow-hidden rounded-lg border bg-muted',
                                                coverMode === 'fixed' &&
                                                    effectiveFixed === c.file &&
                                                    'ring-2 ring-primary',
                                                coverMode === 'random' &&
                                                    covers.length > 1 &&
                                                    previewCover?.file ===
                                                        c.file &&
                                                    'ring-2 ring-muted-foreground/50',
                                            )
                                        "
                                    >
                                        <button
                                            type="button"
                                            class="block aspect-[3/4] w-full focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
                                            :title="`${c.name} · ${c.w}×${c.h}`"
                                            @click="selectCover(c.file)"
                                        >
                                            <img
                                                :src="c.url"
                                                :alt="c.name"
                                                class="size-full object-cover"
                                                loading="lazy"
                                            />
                                        </button>
                                        <span
                                            v-if="
                                                coverMode === 'fixed' &&
                                                effectiveFixed === c.file
                                            "
                                            class="pointer-events-none absolute top-1 left-1 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground"
                                            ><IconCheck class="size-3.5"
                                        /></span>
                                        <div
                                            class="absolute top-1 right-1 flex gap-1 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100"
                                        >
                                            <button
                                                type="button"
                                                class="rounded-md bg-black/60 p-1 text-white hover:bg-black/80 focus-visible:outline-2 focus-visible:outline-white"
                                                aria-label="Phóng to ảnh"
                                                @click="
                                                    zoom = {
                                                        url: c.url,
                                                        name: c.name,
                                                    }
                                                "
                                            >
                                                <IconZoomIn class="size-3.5" />
                                            </button>
                                            <button
                                                type="button"
                                                class="rounded-md bg-black/60 p-1 text-white hover:bg-red-600 focus-visible:outline-2 focus-visible:outline-white"
                                                aria-label="Xoá ảnh"
                                                :disabled="busy"
                                                @click="removeCover(c.file)"
                                            >
                                                <IconTrash class="size-3.5" />
                                            </button>
                                        </div>
                                    </div>

                                    <!-- Ô thêm ảnh -->
                                    <button
                                        type="button"
                                        class="flex aspect-[3/4] flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-xs text-muted-foreground transition-colors hover:border-primary hover:bg-primary/5 hover:text-primary-text focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50"
                                        :disabled="busy"
                                        data-testid="fork-personalise-upload"
                                        @click="fileInput?.click()"
                                    >
                                        <IconPhotoPlus class="size-5" />
                                        {{ covers.length ? 'Thêm ảnh' : 'Tải ảnh lên' }}
                                    </button>
                                    <input
                                        ref="fileInput"
                                        type="file"
                                        class="hidden"
                                        multiple
                                        accept="image/jpeg,image/png,image/webp"
                                        @change="upload"
                                    />
                                </div>

                                <p
                                    v-if="!covers.length"
                                    class="text-sm text-muted-foreground"
                                >
                                    Chưa có ảnh nào: bấm ô bên trên hoặc kéo ảnh
                                    thả vào đây. Khi chưa có ảnh, bài sẽ dùng bìa
                                    mặc định.
                                </p>
                                <p class="text-xs text-muted-foreground">
                                    jpg, png, webp · tối đa 5 MB/ảnh · nên dùng
                                    1080×1440 (3:4), tối thiểu 324×432. Ảnh được
                                    cắt giữa theo 3:4; png/webp được đổi sang
                                    jpg.
                                </p>
                            </div>
                        </div>

                        <details
                            v-if="previewCover"
                            class="group rounded-lg border bg-background"
                        >
                            <summary
                                class="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2.5 text-sm font-medium select-none [&::-webkit-details-marker]:hidden"
                            >
                                Xem trước ảnh trên TikTok
                                <span
                                    class="text-xs font-normal text-muted-foreground group-open:hidden"
                                    >Bấm để mở</span
                                >
                            </summary>
                            <div class="border-t p-3">
                                <CoverPreview
                                    :cover="previewCover"
                                    :random="
                                        coverMode === 'random' &&
                                        covers.length > 1
                                    "
                                />
                            </div>
                        </details>
                    </template>
                </section>

                <!-- 2. Hashtag -->
                <section :class="card" class="flex flex-col gap-4">
                    <div class="flex items-start gap-3">
                        <span
                            class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary-subtle text-primary-text"
                            ><IconHash class="size-4"
                        /></span>
                        <div class="min-w-0">
                            <h3 class="text-base leading-tight font-semibold">
                                Hashtag
                            </h3>
                            <p class="text-sm text-muted-foreground">
                                Hashtag app tự gắn vào caption mỗi bài đăng.
                            </p>
                        </div>
                    </div>

                    <HashtagChips
                        v-model="tags"
                        placeholder="Ví dụ: #damca #phanbon #nongnghiep"
                        testid="fork-personalise-tags"
                    />

                    <div
                        class="grid gap-2 sm:grid-cols-2"
                        role="radiogroup"
                        aria-label="Cách gắn hashtag"
                    >
                        <label
                            v-for="m in tagModes"
                            :key="m.v"
                            :class="
                                cn(
                                    'flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring/50',
                                    tagMode === m.v
                                        ? 'border-primary bg-primary/5 ring-1 ring-primary/40'
                                        : 'hover:bg-muted/50',
                                )
                            "
                        >
                            <input
                                v-model="tagMode"
                                type="radio"
                                name="tag-mode"
                                :value="m.v"
                                class="mt-0.5 accent-primary"
                            />
                            <span class="flex flex-col gap-0.5">
                                <span class="font-medium">{{ m.t }}</span>
                                <span class="text-xs text-muted-foreground">{{
                                    m.d
                                }}</span>
                            </span>
                        </label>
                    </div>

                    <label
                        class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm"
                    >
                        <span>Mỗi bài chọn ngẫu nhiên</span>
                        <Input
                            v-model.number="pick"
                            type="number"
                            min="0"
                            :max="Math.max(tagCount, 0)"
                            class="h-9 w-20 text-center"
                            :disabled="tagCount === 0"
                        />
                        <span>hashtag</span>
                        <span class="text-xs text-muted-foreground"
                            >(0 = dùng tất cả {{ tagCount }} hashtag)</span
                        >
                    </label>
                </section>

                <!-- 3. Caption cuối cùng -->
                <section :class="card" class="flex flex-col gap-3">
                    <div class="flex items-baseline justify-between gap-2">
                        <h3 class="text-base leading-tight font-semibold">
                            Caption cuối cùng
                        </h3>
                        <span class="text-xs text-muted-foreground"
                            >Hashtag chọn ngẫu nhiên có thể khác mỗi bài</span
                        >
                    </div>
                    <label
                        class="flex flex-col gap-1 text-xs text-muted-foreground"
                    >
                        Caption mẫu của video (gõ thử)
                        <Input
                            v-model="sample"
                            class="h-9 text-sm text-foreground"
                            placeholder="Đạm cá nguyên chất cho cây khoẻ #damca #phanbon"
                        />
                    </label>
                    <div
                        class="flex flex-col gap-2 rounded-lg bg-muted/60 p-3 dark:bg-muted/40"
                    >
                        <pre
                            class="font-sans text-sm leading-relaxed break-words whitespace-pre-wrap"
                            data-testid="fork-personalise-preview"
                            >{{ preview?.text ?? '…' }}</pre
                        >
                        <div
                            v-if="preview"
                            class="flex items-center gap-2 text-xs text-muted-foreground"
                        >
                            <span
                                class="h-1 flex-1 overflow-hidden rounded-full bg-border"
                            >
                                <span
                                    :class="
                                        cn(
                                            'block h-full rounded-full bg-primary-strong transition-all',
                                            preview.length > preview.max &&
                                                'bg-red-600',
                                        )
                                    "
                                    :style="{
                                        width: `${Math.min(100, (preview.length / preview.max) * 100)}%`,
                                    }"
                                />
                            </span>
                            <span
                                :class="
                                    cn(
                                        'tabular-nums',
                                        preview.length > preview.max &&
                                            'font-semibold text-red-600 dark:text-red-400',
                                    )
                                "
                                >{{ preview.length }}/{{ preview.max }} ký
                                tự</span
                            >
                        </div>
                    </div>
                </section>
            </div>

            <div
                class="flex shrink-0 items-center justify-end gap-2 border-t bg-background px-5 py-3.5 sm:px-6"
            >
                <Button variant="ghost" @click="emit('update:open', false)"
                    >Đóng</Button
                >
                <Button
                    :disabled="busy"
                    data-testid="fork-personalise-save"
                    @click="save"
                    >Lưu</Button
                >
            </div>
        </DialogContent>

        <MediaLightbox
            :open="zoom !== null"
            kind="image"
            :src="zoom?.url ?? null"
            :title="zoom?.name"
            @update:open="(v: boolean) => !v && (zoom = null)"
        />
    </Dialog>
</template>

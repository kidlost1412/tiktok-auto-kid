<script setup lang="ts">
// "Cá nhân hoá" một sản phẩm hub: ảnh bìa riêng (cố định / ngẫu nhiên trong bộ ảnh) và hashtag riêng.
// scope = 'default' thì chỉ có phần hashtag mặc định chung (áp cho sản phẩm không có hashtag riêng).
import { router } from '@inertiajs/vue3';
import { IconPhotoPlus, IconTrash } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';

import CoverPreview from '@/components/fork/gio-hang/CoverPreview.vue';
import type { Persona } from '@/components/fork/gio-hang/types';
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
const tags = ref('');
const tagMode = ref<'append' | 'replace'>('append');
const pick = ref(0);
const sample = ref('');
const busy = ref(false);
const preview = ref<{ text: string; length: number; max: number } | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
/** Ảnh đang xem trước ở chế độ ngẫu nhiên (bấm ảnh để đổi). */
const previewFile = ref<string | null>(null);

watch(
    () => props.open,
    (open) => {
        if (!open) {
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

function upload(ev: Event) {
    const files = Array.from((ev.target as HTMLInputElement).files ?? []);

    if (!files.length) {
        return;
    }

    busy.value = true;
    router.post(
        `${base.value}/covers`,
        { images: files },
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
        d: 'Bìa trong video (TikTok tự lấy khung đầu)',
    },
    {
        v: 'fixed',
        t: 'Một ảnh cố định',
        d: 'Mọi bài của sản phẩm dùng cùng một ảnh',
    },
    {
        v: 'random',
        t: 'Ngẫu nhiên trong bộ ảnh',
        d: 'Mỗi bài một ảnh, không lặp ảnh bài trước',
    },
] as const;
</script>

<template>
    <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
        <DialogContent
            class="flex max-h-[88dvh] max-w-2xl flex-col overflow-hidden"
            data-testid="fork-personalise-dialog"
        >
            <DialogHeader>
                <DialogTitle>
                    {{
                        isProduct
                            ? `Cá nhân hoá — ${label}`
                            : 'Hashtag mặc định chung'
                    }}
                </DialogTitle>
                <DialogDescription>
                    {{
                        isProduct
                            ? 'Áp cho mọi bài của sản phẩm này (mọi quy cách, mọi kênh).'
                            : 'Dùng cho sản phẩm không có hashtag riêng.'
                    }}
                </DialogDescription>
            </DialogHeader>

            <!-- Chỉ phần giữa cuộn: nút Đóng/Lưu luôn thấy trên màn hình thấp. -->
            <div
                class="-mx-6 flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-6"
            >
                <!-- Ảnh bìa -->
                <section v-if="isProduct" class="flex flex-col gap-3">
                    <h3 class="text-base font-semibold">Ảnh bìa</h3>
                    <div class="grid gap-2 sm:grid-cols-3">
                        <label
                            v-for="m in modes"
                            :key="m.v"
                            :class="
                                cn(
                                    'flex cursor-pointer flex-col gap-1 rounded-lg border p-3 text-sm transition-colors',
                                    coverMode === m.v
                                        ? 'border-primary bg-primary/5 ring-1 ring-primary/40'
                                        : 'hover:bg-muted/50',
                                )
                            "
                        >
                            <span class="flex items-center gap-2 font-medium">
                                <input
                                    v-model="coverMode"
                                    type="radio"
                                    name="cover-mode"
                                    :value="m.v"
                                    class="accent-primary"
                                />
                                {{ m.t }}
                            </span>
                            <span class="text-xs text-muted-foreground">{{
                                m.d
                            }}</span>
                        </label>
                    </div>

                    <template v-if="coverMode !== 'default'">
                        <div
                            class="flex flex-wrap items-center justify-between gap-2"
                        >
                            <span class="text-xs text-muted-foreground">
                                jpg, png, webp · tối đa 5 MB/ảnh · khuyên dùng
                                1080×1440 (3:4), tối thiểu 324×432. Ảnh được cắt
                                giữa theo 3:4 (TikTok dùng bìa 3:4); png/webp
                                được đổi sang jpg.
                            </span>
                            <Button
                                size="sm"
                                variant="outline"
                                :disabled="busy"
                                data-testid="fork-personalise-upload"
                                @click="fileInput?.click()"
                            >
                                <IconPhotoPlus class="size-4" />
                                Thêm ảnh
                            </Button>
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
                            class="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground"
                        >
                            Chưa có ảnh nào — khi đăng sẽ dùng bìa mặc định.
                        </p>
                        <div
                            v-else
                            class="grid grid-cols-3 gap-2 sm:grid-cols-5"
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
                                            previewCover?.file === c.file &&
                                            'ring-2 ring-muted-foreground/50',
                                    )
                                "
                            >
                                <button
                                    type="button"
                                    class="block aspect-[3/4] w-full"
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
                                    class="absolute inset-x-0 bottom-0 bg-black/55 px-1 py-0.5 text-center text-[10px] text-white"
                                    >{{ c.w }}×{{ c.h }}</span
                                >
                                <button
                                    type="button"
                                    class="absolute top-1 right-1 rounded-md bg-black/60 p-1 text-white opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
                                    aria-label="Xoá ảnh"
                                    :disabled="busy"
                                    @click="removeCover(c.file)"
                                >
                                    <IconTrash class="size-3.5" />
                                </button>
                            </div>
                        </div>
                        <p
                            v-if="coverMode === 'fixed' && covers.length > 1"
                            class="text-xs text-muted-foreground"
                        >
                            Bấm vào ảnh để chọn ảnh cố định (viền xanh).
                        </p>

                        <CoverPreview
                            v-if="previewCover"
                            :cover="previewCover"
                            :random="
                                coverMode === 'random' && covers.length > 1
                            "
                        />
                    </template>
                </section>

                <!-- Hashtag -->
                <section class="flex flex-col gap-3">
                    <h3 class="text-base font-semibold">Hashtag</h3>
                    <label class="flex flex-col gap-1.5 text-sm">
                        <span
                            class="flex items-center justify-between text-muted-foreground"
                        >
                            <span
                                >Danh sách (cách nhau bằng dấu cách hoặc xuống
                                dòng)</span
                            >
                            <span>{{ tagCount }} hashtag</span>
                        </span>
                        <textarea
                            v-model="tags"
                            rows="3"
                            placeholder="#damca #phanbon #nongnghiep"
                            class="rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                            data-testid="fork-personalise-tags"
                        />
                    </label>

                    <div class="grid gap-2 sm:grid-cols-2">
                        <label
                            :class="
                                cn(
                                    'flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-sm',
                                    tagMode === 'append' &&
                                        'border-primary bg-primary/5',
                                )
                            "
                        >
                            <input
                                v-model="tagMode"
                                type="radio"
                                name="tag-mode"
                                value="append"
                                class="accent-primary"
                            />
                            Thêm vào cuối caption
                        </label>
                        <label
                            :class="
                                cn(
                                    'flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-sm',
                                    tagMode === 'replace' &&
                                        'border-primary bg-primary/5',
                                )
                            "
                        >
                            <input
                                v-model="tagMode"
                                type="radio"
                                name="tag-mode"
                                value="replace"
                                class="accent-primary"
                            />
                            Thay toàn bộ hashtag
                        </label>
                    </div>

                    <label class="flex items-center gap-2 text-sm">
                        Chọn ngẫu nhiên
                        <Input
                            v-model.number="pick"
                            type="number"
                            min="0"
                            max="50"
                            class="h-9 w-20"
                        />
                        cái mỗi bài
                        <span class="text-xs text-muted-foreground"
                            >(0 = dùng tất cả)</span
                        >
                    </label>

                    <!-- Xem trước -->
                    <div
                        class="flex flex-col gap-1.5 rounded-lg bg-muted/50 p-3"
                    >
                        <label
                            class="flex flex-col gap-1 text-xs text-muted-foreground"
                        >
                            Caption mẫu của video (sửa thử)
                            <Input
                                v-model="sample"
                                class="h-9 text-sm text-foreground"
                                placeholder="Đạm cá nguyên chất cho cây khoẻ #damca #phanbon"
                            />
                        </label>
                        <div class="text-xs text-muted-foreground">
                            Caption cuối cùng (hashtag chọn ngẫu nhiên có thể
                            khác mỗi bài)
                        </div>
                        <pre
                            class="font-sans text-sm break-words whitespace-pre-wrap"
                            data-testid="fork-personalise-preview"
                            >{{ preview?.text ?? '…' }}</pre
                        >
                        <div
                            v-if="preview"
                            :class="
                                cn(
                                    'text-right text-xs text-muted-foreground',
                                    preview.length > preview.max &&
                                        'font-semibold text-red-600',
                                )
                            "
                        >
                            {{ preview.length }}/{{ preview.max }} ký tự
                        </div>
                    </div>
                </section>
            </div>

            <div class="flex shrink-0 justify-end gap-2 border-t pt-3">
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
    </Dialog>
</template>

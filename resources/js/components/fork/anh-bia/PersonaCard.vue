<script setup lang="ts">
// Thẻ tóm tắt cá nhân hoá của một sản phẩm hub: ảnh bìa, hashtag và một dòng caption mẫu.
// Chỉ để xem nhanh; sửa trong hộp thoại PersonaliseDialog (nút "Chỉnh").
import {
    IconAdjustments,
    IconHash,
    IconMovie,
    IconPhoto,
    IconTextCaption,
} from '@tabler/icons-vue';
import { computed } from 'vue';

import type { PersonaProduct } from '@/components/fork/anh-bia/types';
import type { Persona, PersonaDefault } from '@/components/fork/gio-hang/types';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const props = defineProps<{
    product: PersonaProduct;
    persona: Persona;
    defaults?: PersonaDefault;
}>();

const emit = defineEmits<{ edit: [] }>();

const MAX_THUMBS = 5;
const MAX_TAGS = 8;

const covers = computed(() => props.persona.covers ?? []);

/** Chế độ thật sự khi đăng: chọn cố định/ngẫu nhiên mà chưa có ảnh thì vẫn là bìa mặc định. */
const coverMode = computed(() =>
    props.persona.cover_mode !== 'default' && covers.value.length
        ? props.persona.cover_mode
        : 'default',
);
const coverMissing = computed(
    () => props.persona.cover_mode !== 'default' && !covers.value.length,
);

const fixedFile = computed(
    () =>
        covers.value.find((c) => c.file === props.persona.cover_fixed)?.file ??
        covers.value[0]?.file ??
        null,
);

const coverLabel = computed(() => {
    if (coverMode.value === 'fixed') {
        return '1 ảnh cố định';
    }

    if (coverMode.value === 'random') {
        return `Ngẫu nhiên ${covers.value.length} ảnh`;
    }

    return 'Mặc định từ video';
});

// Cố định: ảnh được chọn lên đầu. Ngẫu nhiên: cả bộ.
const thumbs = computed(() => {
    const list =
        coverMode.value === 'fixed'
            ? [
                  ...covers.value.filter((c) => c.file === fixedFile.value),
                  ...covers.value.filter((c) => c.file !== fixedFile.value),
              ]
            : covers.value;

    return list.slice(0, MAX_THUMBS);
});
const moreThumbs = computed(() =>
    Math.max(0, covers.value.length - MAX_THUMBS),
);

// ---- Hashtag: riêng của sản phẩm, nếu không có thì mặc định chung ----
const ownTags = computed(() => props.persona.hashtags ?? []);
const usesDefault = computed(
    () => !ownTags.value.length && !!props.defaults?.tags.length,
);
const shownTags = computed(() =>
    ownTags.value.length ? ownTags.value : (props.defaults?.tags ?? []),
);
const tagMode = computed(() =>
    ownTags.value.length
        ? props.persona.hashtag_mode
        : (props.defaults?.mode ?? 'append'),
);
const tagPick = computed(() =>
    ownTags.value.length
        ? props.persona.hashtag_pick
        : (props.defaults?.pick ?? 0),
);

const tagLabel = computed(() => {
    if (!shownTags.value.length) {
        return 'Không thêm hashtag';
    }

    return usesDefault.value ? 'Dùng hashtag chung' : 'Hashtag riêng';
});

const tagDetail = computed(() => {
    if (!shownTags.value.length) {
        return 'Giữ nguyên hashtag hub viết trong caption.';
    }

    const how =
        tagMode.value === 'replace'
            ? 'thay toàn bộ hashtag cũ'
            : 'thêm vào cuối caption';
    const pick =
        tagPick.value > 0 && tagPick.value < shownTags.value.length
            ? ` · mỗi bài chọn ngẫu nhiên ${tagPick.value}/${shownTags.value.length}`
            : '';

    return `${how}${pick}`;
});
</script>

<template>
    <article
        class="group flex flex-col overflow-hidden rounded-2xl border bg-card shadow-xs transition-shadow hover:shadow-md"
        :data-testid="`fork-anh-bia-card-${product.code}`"
    >
        <!-- Đầu thẻ: sản phẩm -->
        <header class="flex items-center gap-3 border-b p-4">
            <ProductThumb :src="product.image" class="size-14 rounded-xl" />
            <div class="min-w-0 flex-1">
                <h3
                    class="truncate text-lg leading-tight font-semibold"
                    :title="product.full_name"
                >
                    {{ product.name }}
                </h3>
                <p
                    class="mt-0.5 truncate text-sm text-muted-foreground"
                    :title="product.quy_cach.join(', ')"
                >
                    <template v-if="product.quy_cach.length">
                        {{ product.quy_cach.join(' · ') }}
                    </template>
                    <template v-else>Một quy cách</template>
                    <template v-if="product.videos_waiting">
                        · {{ product.videos_waiting }} video chờ đăng
                    </template>
                </p>
            </div>
        </header>

        <div class="flex flex-1 flex-col gap-4 p-4">
            <!-- Ảnh bìa -->
            <section class="flex flex-col gap-2">
                <div class="flex items-center justify-between gap-2">
                    <span
                        class="flex items-center gap-1.5 text-sm font-medium text-muted-foreground"
                    >
                        <IconPhoto class="size-4" />
                        Ảnh bìa
                    </span>
                    <Badge
                        :variant="coverMode === 'default' ? 'outline' : 'info'"
                        data-testid="fork-anh-bia-cover-mode"
                        >{{ coverLabel }}</Badge
                    >
                </div>

                <div
                    v-if="coverMode !== 'default'"
                    class="flex items-end gap-1.5"
                >
                    <div
                        v-for="c in thumbs"
                        :key="c.file"
                        :class="
                            cn(
                                'relative aspect-[3/4] w-14 shrink-0 overflow-hidden rounded-md border bg-muted',
                                coverMode === 'fixed' &&
                                    c.file === fixedFile &&
                                    'w-16 ring-2 ring-primary ring-offset-1 ring-offset-card',
                                coverMode === 'fixed' &&
                                    c.file !== fixedFile &&
                                    'opacity-45',
                            )
                        "
                    >
                        <img
                            :src="c.url"
                            :alt="c.name"
                            class="size-full object-cover"
                            loading="lazy"
                        />
                    </div>
                    <span
                        v-if="moreThumbs"
                        class="flex aspect-[3/4] w-14 shrink-0 items-center justify-center rounded-md border border-dashed text-sm font-medium text-muted-foreground"
                        >+{{ moreThumbs }}</span
                    >
                </div>
                <div
                    v-else
                    class="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-2.5 text-sm text-muted-foreground"
                >
                    <span
                        class="flex aspect-[3/4] w-9 shrink-0 items-center justify-center rounded border border-dashed bg-background"
                    >
                        <IconMovie class="size-4" />
                    </span>
                    <span>
                        <template v-if="coverMissing"
                            >Đã chọn ảnh riêng nhưng chưa tải ảnh nào — đang
                            dùng bìa trong video.</template
                        >
                        <template v-else
                            >TikTok lấy khung hình trong video làm
                            bìa.</template
                        >
                    </span>
                </div>
            </section>

            <!-- Hashtag -->
            <section class="flex flex-col gap-2">
                <div class="flex items-center justify-between gap-2">
                    <span
                        class="flex items-center gap-1.5 text-sm font-medium text-muted-foreground"
                    >
                        <IconHash class="size-4" />
                        Hashtag
                    </span>
                    <Badge
                        :variant="
                            !shownTags.length || usesDefault
                                ? 'outline'
                                : 'info'
                        "
                        data-testid="fork-anh-bia-tag-mode"
                        >{{ tagLabel }}</Badge
                    >
                </div>
                <div v-if="shownTags.length" class="flex flex-wrap gap-1.5">
                    <span
                        v-for="t in shownTags.slice(0, MAX_TAGS)"
                        :key="t"
                        :class="
                            cn(
                                'rounded-full px-2 py-0.5 text-xs font-medium',
                                usesDefault
                                    ? 'bg-muted text-muted-foreground'
                                    : 'bg-primary/10 text-primary-text dark:bg-primary/20',
                            )
                        "
                        >{{ t }}</span
                    >
                    <span
                        v-if="shownTags.length > MAX_TAGS"
                        class="rounded-full border border-dashed px-2 py-0.5 text-xs text-muted-foreground"
                        >+{{ shownTags.length - MAX_TAGS }}</span
                    >
                </div>
                <p class="text-xs text-muted-foreground">{{ tagDetail }}</p>
            </section>

            <!-- Caption mẫu -->
            <section
                class="mt-auto flex flex-col gap-1 rounded-lg border border-dashed bg-muted/30 p-3"
            >
                <span
                    class="flex items-center gap-1.5 text-xs text-muted-foreground"
                >
                    <IconTextCaption class="size-3.5" />
                    {{
                        product.caption.source === 'video'
                            ? 'Caption bài gần nhất sẽ thành'
                            : 'Ví dụ caption khi đăng'
                    }}
                </span>
                <p
                    class="line-clamp-2 text-sm break-words"
                    :title="product.caption.text"
                    data-testid="fork-anh-bia-caption"
                >
                    {{ product.caption.text }}
                </p>
            </section>
        </div>

        <footer class="border-t bg-muted/20 p-3">
            <Button
                class="w-full"
                :data-testid="`fork-anh-bia-edit-${product.code}`"
                @click="emit('edit')"
            >
                <IconAdjustments class="size-4" />
                Chỉnh ảnh bìa &amp; hashtag
            </Button>
        </footer>
    </article>
</template>

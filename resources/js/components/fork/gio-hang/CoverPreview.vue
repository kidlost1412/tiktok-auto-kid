<script setup lang="ts">
// Xem trước ảnh bìa như trên TikTok: ô 3:4 trong lưới trang cá nhân (kèm số lượt xem như TikTok)
// và khung video 9:16 với vùng 3:4 được tô sáng, để thấy phần nào bị cắt. Chỉ vẽ ở trình duyệt.
import { IconPhoto, IconPlayerPlay } from '@tabler/icons-vue';
import { computed } from 'vue';

import type { Persona } from '@/components/fork/gio-hang/types';

type Cover = Persona['covers'][number];

const props = defineProps<{
    cover: Cover;
    /** random = mỗi bài một ảnh: ảnh đang xem chỉ là ví dụ. */
    random?: boolean;
}>();

// Bài mới nhất nằm ô đầu tiên (trên cùng bên trái) của lưới TikTok; hai ô sau là bài cũ (giả).
const tiles = [
    { mine: true, views: '1,2K' },
    { mine: false, views: '8.534' },
    { mine: false, views: '24,6K' },
];

/** Phần đã cắt khỏi ảnh gốc (px mỗi phía), null khi không biết ảnh gốc hoặc ảnh gốc đã đúng 3:4. */
const cropNote = computed<string | null>(() => {
    const ow = props.cover.orig_w ?? 0;
    const oh = props.cover.orig_h ?? 0;

    if (ow <= 0 || oh <= 0 || Math.abs(ow / oh - 3 / 4) <= 0.01) {
        return null;
    }

    if (ow * 4 > oh * 3) {
        const cut = Math.round((ow - (oh * 3) / 4) / 2);

        return `Ảnh gốc ${ow}×${oh} rộng hơn 3:4 nên đã bị cắt bỏ ${cut} px ở mỗi bên trái và phải.`;
    }

    const cut = Math.round((oh - (ow * 4) / 3) / 2);

    return `Ảnh gốc ${ow}×${oh} cao hơn 3:4 nên đã bị cắt bỏ ${cut} px ở trên và ${cut} px ở dưới.`;
});

const hatch =
    'bg-[repeating-linear-gradient(135deg,transparent_0_6px,rgb(0_0_0/0.09)_6px_12px)] dark:bg-[repeating-linear-gradient(135deg,transparent_0_6px,rgb(255_255_255/0.09)_6px_12px)]';
</script>

<template>
    <div
        class="flex flex-col gap-3 rounded-lg bg-muted/50 p-3"
        data-testid="fork-personalise-cover-preview"
    >
        <div class="flex items-baseline justify-between gap-2">
            <h4 class="text-sm font-semibold">Xem trước trên TikTok</h4>
            <span
                v-if="random"
                class="text-right text-xs text-muted-foreground"
            >
                Ví dụ một ảnh trong bộ · bấm ảnh khác để xem
            </span>
        </div>

        <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
            <!-- Lưới trang cá nhân -->
            <figure class="flex min-w-0 flex-col gap-1.5">
                <div
                    class="grid grid-cols-3 gap-0.5 overflow-hidden rounded-md bg-background"
                >
                    <div
                        v-for="(t, i) in tiles"
                        :key="i"
                        class="relative aspect-[3/4] overflow-hidden bg-muted"
                    >
                        <img
                            v-if="t.mine"
                            :src="cover.url"
                            :alt="cover.name"
                            class="size-full object-cover"
                        />
                        <div
                            v-else
                            class="flex size-full items-center justify-center bg-gradient-to-b from-muted to-muted-foreground/20"
                            aria-hidden="true"
                        >
                            <IconPhoto
                                class="size-6 text-muted-foreground/40"
                            />
                        </div>
                        <span
                            class="pointer-events-none absolute inset-x-0 bottom-0 flex items-center gap-0.5 bg-gradient-to-t from-black/60 to-transparent px-1.5 pt-4 pb-1 text-[0.6875rem] font-semibold text-white"
                        >
                            <IconPlayerPlay class="size-3" />
                            {{ t.views }}
                        </span>
                    </div>
                </div>
                <figcaption class="text-xs text-muted-foreground">
                    Trên trang cá nhân TikTok, mỗi bài là một ô 3:4. Bài mới
                    đăng nằm ô đầu tiên; hai ô bên cạnh chỉ để minh hoạ.
                </figcaption>
            </figure>

            <!-- Khung video 9:16 và vùng bìa 3:4 -->
            <figure class="flex flex-col items-center gap-1.5">
                <div
                    class="relative aspect-[9/16] w-28 overflow-hidden rounded-md border bg-background"
                    aria-label="Khung video 9:16, vùng giữa là bìa 3:4"
                >
                    <div
                        :class="[
                            'absolute inset-x-0 top-0 flex h-[12.5%] items-center justify-center',
                            hatch,
                        ]"
                    >
                        <span class="text-[0.5625rem] text-muted-foreground"
                            >bị cắt</span
                        >
                    </div>
                    <img
                        :src="cover.url"
                        alt=""
                        class="absolute inset-x-0 top-[12.5%] h-3/4 w-full object-cover"
                    />
                    <div
                        class="pointer-events-none absolute inset-x-0 top-[12.5%] h-3/4 border-2 border-dashed border-primary"
                    />
                    <span
                        class="absolute top-[12.5%] left-0 m-1 rounded bg-primary px-1 text-[0.5625rem] font-semibold text-primary-foreground"
                        >3:4</span
                    >
                    <div
                        :class="[
                            'absolute inset-x-0 bottom-0 flex h-[12.5%] items-center justify-center',
                            hatch,
                        ]"
                    >
                        <span class="text-[0.5625rem] text-muted-foreground"
                            >bị cắt</span
                        >
                    </div>
                </div>
                <figcaption
                    class="w-36 text-center text-xs text-muted-foreground"
                >
                    Khung dọc 9:16: chỉ phần giữa (khung nét đứt) thành bìa.
                </figcaption>
            </figure>
        </div>

        <p class="text-xs text-muted-foreground">
            <template v-if="cropNote">{{ cropNote }} </template>
            Ảnh làm từ khung dọc 9:16 sẽ mất khoảng 1/8 ở trên và 1/8 ở dưới:
            hãy đặt chữ và sản phẩm ở giữa ảnh.
        </p>
    </div>
</template>

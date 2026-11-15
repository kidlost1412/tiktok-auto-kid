<script setup lang="ts">
// Ảnh bìa dọc 9:16 của một bài. Không có ảnh bìa (video đã dọn khỏi hub, chưa có bìa...) thì lùi về ảnh sản phẩm,
// rồi mới tới khung xám — để danh sách không thành một dãy ô trống.
import { IconMovie } from '@tabler/icons-vue';
import { ref, watch } from 'vue';

import { cn } from '@/lib/utils';

const props = defineProps<{
    id: number | null | undefined;
    fallback?: string | null;
    class?: string;
}>();

const coverFailed = ref(false);
const fallbackFailed = ref(false);
const loaded = ref(false);

watch(
    () => [props.id, props.fallback],
    () => {
        coverFailed.value = false;
        fallbackFailed.value = false;
        loaded.value = false;
    },
);
</script>

<template>
    <div
        :class="
            cn(
                'relative isolate shrink-0 overflow-hidden rounded-lg bg-muted ring-1 ring-black/5 ring-inset dark:ring-white/10',
                props.class,
            )
        "
    >
        <div
            v-if="
                !loaded &&
                ((props.id && !coverFailed) ||
                    (props.fallback && !fallbackFailed))
            "
            class="absolute inset-0 animate-pulse bg-muted-foreground/10"
            aria-hidden="true"
        />
        <img
            v-if="props.id && !coverFailed"
            :src="`/auto/kho/video/${props.id}/cover`"
            alt=""
            loading="lazy"
            decoding="async"
            :class="
                cn(
                    'size-full object-cover transition-opacity duration-300',
                    loaded ? 'opacity-100' : 'opacity-0',
                )
            "
            @load="loaded = true"
            @error="coverFailed = true"
        />
        <template v-else-if="props.fallback && !fallbackFailed">
            <img
                :src="props.fallback"
                alt=""
                aria-hidden="true"
                loading="lazy"
                class="absolute inset-0 -z-10 size-full scale-125 object-cover opacity-50 blur-md"
            />
            <img
                :src="props.fallback"
                alt=""
                loading="lazy"
                decoding="async"
                class="size-full object-contain p-1"
                @load="loaded = true"
                @error="fallbackFailed = true"
            />
        </template>
        <div
            v-else
            class="flex size-full items-center justify-center text-muted-foreground"
        >
            <IconMovie class="size-1/3 min-h-4 min-w-4" />
        </div>
    </div>
</template>

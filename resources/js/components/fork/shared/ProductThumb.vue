<script setup lang="ts">
// Ảnh nhỏ sản phẩm TikTok Shop cạnh tên sản phẩm. Luôn có biểu tượng túi hàng làm nền: ảnh chưa tải xong (hoặc không có,
// hoặc lỗi tải) thì người dùng thấy biểu tượng thay vì ô xám trống; ảnh tải xong sẽ phủ lên.
import { IconShoppingBag } from '@tabler/icons-vue';
import { nextTick, onMounted, ref, watch } from 'vue';

import { cn } from '@/lib/utils';

const props = defineProps<{
    src?: string | null;
    class?: string;
}>();

const failed = ref(false);
const loaded = ref(false);
const img = ref<HTMLImageElement | null>(null);

// Ảnh đã có trong bộ nhớ đệm có thể tải xong trước khi gắn sự kiện load.
const syncLoaded = () => {
    loaded.value = !!img.value?.complete && img.value.naturalWidth > 0;
};

onMounted(syncLoaded);
watch(
    () => props.src,
    async () => {
        failed.value = false;
        loaded.value = false;
        await nextTick();
        syncLoaded();
    },
);
</script>

<template>
    <span
        :class="
            cn(
                'relative flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted text-muted-foreground ring-1 ring-border',
                props.class,
            )
        "
    >
        <IconShoppingBag class="size-3/5" />
        <img
            v-if="src && !failed"
            ref="img"
            :src="src"
            alt=""
            loading="lazy"
            decoding="async"
            :class="
                cn(
                    'absolute inset-0 size-full bg-muted object-cover transition-opacity duration-200',
                    loaded ? 'opacity-100' : 'opacity-0',
                )
            "
            @load="loaded = true"
            @error="failed = true"
        />
    </span>
</template>

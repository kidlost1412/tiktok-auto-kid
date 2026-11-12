<script setup lang="ts">
// Ảnh nhỏ sản phẩm TikTok Shop cạnh tên sản phẩm. Chưa có ảnh (hoặc lỗi tải) thì hiện biểu tượng túi hàng trung tính.
import { IconShoppingBag } from '@tabler/icons-vue';
import { ref, watch } from 'vue';

import { cn } from '@/lib/utils';

const props = defineProps<{
    src?: string | null;
    class?: string;
}>();

const failed = ref(false);

watch(
    () => props.src,
    () => {
        failed.value = false;
    },
);
</script>

<template>
    <img
        v-if="src && !failed"
        :src="src"
        alt=""
        loading="lazy"
        :class="
            cn(
                'size-6 shrink-0 rounded-md bg-muted object-cover ring-1 ring-border',
                props.class,
            )
        "
        @error="failed = true"
    />
    <span
        v-else
        :class="
            cn(
                'flex size-6 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground ring-1 ring-border',
                props.class,
            )
        "
    >
        <IconShoppingBag class="size-3/5" />
    </span>
</template>

<script setup lang="ts">
// Bàn của Chủ quầy: giỏ hàng TikTok Shop cho từng sản phẩm (dùng lại phần thân của trang Giỏ hàng).
// Giữ kênh đang xem; nội dung ở ChuQuayGio (đổi kênh thì tự tải lại, không dựng lại).
import { ref } from 'vue';

import ChuQuayGio from '@/components/fork/nha/ban/ChuQuayGio.vue';
import type { NhaData } from '@/components/fork/nha/types';

defineProps<{ data: NhaData | null }>();

const kenh = ref<string | null>(null);
</script>

<template>
    <ChuQuayGio :kenh="kenh" @kenh="(id) => (kenh = id)" />
</template>

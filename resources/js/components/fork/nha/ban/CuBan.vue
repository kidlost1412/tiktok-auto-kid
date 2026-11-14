<script setup lang="ts">
// Bàn của Cú thông thái: số liệu theo khoảng ngày. Giữ khoảng ngày đang chọn; nội dung ở CuSoLieu (dựng lại khi đổi khoảng).
import { ref } from 'vue';

import CuSoLieu from '@/components/fork/nha/ban/CuSoLieu.vue';
import type { NhaData } from '@/components/fork/nha/types';

defineProps<{ data: NhaData | null }>();

const range = ref<'today' | '7d' | '30d'>('7d');
</script>

<template>
    <CuSoLieu :key="range" :range="range" @range="(r) => (range = r)" />
</template>

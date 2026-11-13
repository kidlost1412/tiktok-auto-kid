<script setup lang="ts">
// "Nhật ký đang làm gì" của hai Đạo diễn: chỉ định dạng lại sự kiện thật mà trang cha đã hỏi từ /nha/trang-thai
// (cùng nguồn với Khu Tự Trị) — không tự gọi API, không gọi AI.
import { computed } from 'vue';

import type { NhaData } from '../nha/types';

import { daoDienLog } from './nhat-ky';

const props = defineProps<{ data: NhaData | null }>();

const lines = computed(() => (props.data ? daoDienLog(props.data.events ?? [], props.data.bay_gio ?? Date.now() / 1000) : []));
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto text-[12.5px]" data-testid="xuong-nhat-ky">
        <p v-if="!data" class="text-muted-foreground">Đang tải nhật ký…</p>
        <p v-else-if="!data.hub.up" class="text-muted-foreground">Xưởng Video đang tắt, chưa có gì để ghi.</p>
        <p v-else-if="!lines.length" class="text-muted-foreground">Chưa có hoạt động nào của Đạo diễn gần đây.</p>
        <ul v-else class="flex flex-col gap-1">
            <li v-for="l in lines" :key="l.key" class="flex items-baseline justify-between gap-2 rounded-md bg-secondary/50 px-2 py-1">
                <span class="truncate">{{ l.text }}</span>
                <span class="shrink-0 text-[11px] text-muted-foreground">{{ l.agoLabel }}</span>
            </li>
        </ul>
    </div>
</template>

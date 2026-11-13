<script setup lang="ts">
// "Nhật ký đang làm gì" của hai Đạo diễn: tự hỏi /nha/trang-thai khi đang mở (prop `active`),
// dừng hẳn khi đóng thẻ hoặc tab ẩn — cùng nguồn dữ liệu thật mà trang chủ "Xưởng nhỏ" dùng,
// không gọi thêm API nào khác, không gọi AI.
import { onBeforeUnmount, ref, watch } from 'vue';

import type { NhaData } from '../nha/types';

import { daoDienLog, type DongNhatKy } from './nhat-ky';

const props = defineProps<{ active: boolean }>();

const lines = ref<DongNhatKy[]>([]);
const loaded = ref(false);
const upNow = ref(true);

let timer: number | undefined;
let inflight = false;

const load = async () => {
    if (inflight || document.hidden) {
        return;
    }
    inflight = true;
    try {
        const r = await fetch('/nha/trang-thai', {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });
        const d = (await r.json()) as NhaData;
        upNow.value = d.hub.up;
        lines.value = daoDienLog(d.events ?? [], d.bay_gio ?? Date.now() / 1000);
        loaded.value = true;
    } catch {
        // im lặng: chỉ là nhật ký trang trí, không ảnh hưởng phần còn lại của trang
    } finally {
        inflight = false;
    }
};

const schedule = () => {
    window.clearTimeout(timer);
    if (!props.active || document.hidden) {
        return;
    }
    timer = window.setTimeout(async () => {
        await load();
        schedule();
    }, 6000);
};

watch(
    () => props.active,
    (on) => {
        if (on) {
            void load();
            schedule();
        } else {
            window.clearTimeout(timer);
        }
    },
    { immediate: true },
);

const onVis = () => {
    if (document.hidden) {
        window.clearTimeout(timer);
    } else {
        schedule();
    }
};
document.addEventListener('visibilitychange', onVis);

onBeforeUnmount(() => {
    window.clearTimeout(timer);
    document.removeEventListener('visibilitychange', onVis);
});
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto text-[13px]" data-testid="xuong-nhat-ky">
        <p v-if="!loaded" class="text-muted-foreground">Đang tải nhật ký…</p>
        <p v-else-if="!upNow" class="text-muted-foreground">Xưởng Video đang tắt, chưa có gì để ghi.</p>
        <p v-else-if="!lines.length" class="text-muted-foreground">Chưa có hoạt động nào của Đạo diễn gần đây.</p>
        <ul v-else class="flex flex-col gap-1.5">
            <li
                v-for="l in lines"
                :key="l.key"
                class="flex items-baseline justify-between gap-2 rounded-md bg-secondary/50 px-2 py-1"
            >
                <span class="truncate">{{ l.text }}</span>
                <span class="shrink-0 text-[11px] text-muted-foreground">{{ l.agoLabel }}</span>
            </li>
        </ul>
    </div>
</template>

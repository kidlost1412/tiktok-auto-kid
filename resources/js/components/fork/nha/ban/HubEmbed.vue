<script setup lang="ts">
// Nhúng MỘT tab của giao diện hub Xưởng Video vào popup ("gon=1": ẩn thanh đầu/tab của hub, chỉ còn nội dung).
// Dùng lại nguyên giao diện hub — không viết lại form/bảng của hub.
import { IconAlertTriangle, IconLoader2 } from '@tabler/icons-vue';
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { banBao } from '@/components/fork/nha/ban/bus';

const props = defineProps<{
    /** Địa chỉ hub (data.hub.url của /nha/trang-thai), vd http://127.0.0.1:8765 */
    hubUrl: string | null | undefined;
    tab: 'san-xuat' | 'kho' | 'san-pham' | 'gu' | 'prompt-ai' | 'cai-dat';
    muc?: string | null;
}>();

const box = ref<HTMLElement | null>(null);
const src = ref('');
const loaded = ref(false);

const bgHex = (el: HTMLElement | null) => {
    const m = getComputedStyle(el ?? document.body).backgroundColor.match(
        /\d+/g,
    );

    return m && m.length >= 3
        ? '#' +
              m
                  .slice(0, 3)
                  .map((n) => Number(n).toString(16).padStart(2, '0'))
                  .join('')
        : '';
};

let hubOrigin = '';

// Hub báo việc chính người dùng vừa làm trong iframe → nhân vật 3D phản ứng.
const onMessage = (e: MessageEvent) => {
    const d = e.data as { type?: string; vai?: unknown; viec?: unknown } | null;

    if (
        !hubOrigin ||
        e.origin !== hubOrigin ||
        !d ||
        d.type !== 'xuong-video:viec'
    ) {
        return;
    }

    if (typeof d.vai === 'string' && typeof d.viec === 'string') {
        banBao(d.vai, d.viec);
    }
};

onBeforeUnmount(() => window.removeEventListener('message', onMessage));

// Mở thẳng /nha?ban=... thì lúc gắn dữ liệu chưa về (hubUrl rỗng): nạp khi có địa chỉ hub.
const nap = () => {
    if (!props.hubUrl || src.value) {
        return;
    }

    try {
        hubOrigin = new URL(props.hubUrl).origin;
        window.addEventListener('message', onMessage);
    } catch {
        hubOrigin = '';
    }
    const q = new URLSearchParams({
        nhung: '1',
        gon: '1',
        tab: props.tab,
        theme: document.documentElement.classList.contains('dark')
            ? 'dark'
            : 'light',
    });
    if (props.muc) {
        q.set('muc', props.muc);
    }
    const bg = bgHex(box.value);
    if (bg) {
        q.set('bg', bg);
    }
    src.value = `${props.hubUrl.replace(/\/+$/, '')}/?${q.toString()}`;
};

onMounted(nap);
watch(() => props.hubUrl, nap);
</script>

<template>
    <div
        ref="box"
        class="relative min-h-[70vh] flex-1 overflow-hidden rounded-xl bg-card"
        data-testid="nha-ban-hub"
    >
        <div
            v-if="!hubUrl"
            class="grid h-full min-h-60 place-items-center p-6 text-center text-sm text-muted-foreground"
        >
            <span class="flex flex-col items-center gap-2">
                <IconAlertTriangle class="size-6 text-amber-500" />
                Xưởng Video chưa chạy nên chưa mở được phần này.
            </span>
        </div>
        <template v-else>
            <div
                v-if="!loaded"
                class="absolute inset-0 grid place-items-center text-muted-foreground"
            >
                <IconLoader2 class="size-6 animate-spin" />
            </div>
            <iframe
                v-if="src"
                :src="src"
                class="size-full border-0"
                :class="loaded ? 'opacity-100' : 'opacity-0'"
                title="Xưởng Video"
                @load="loaded = true"
            />
        </template>
    </div>
</template>

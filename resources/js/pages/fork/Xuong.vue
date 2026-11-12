<script setup lang="ts">
// Trang "Xưởng Video": nhúng giao diện hub sản xuất (iframe trỏ thẳng cổng hub).
// Hub báo đổi tab qua postMessage; app báo đổi giao diện sáng/tối cho hub. Hub tắt thì hiện thẻ "Bật lại".
import { Head } from '@inertiajs/vue3';
import { IconMovie, IconPower } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/AppLayout.vue';

const props = defineProps<{ url: string; tab: string | null }>();

const TABS = ['san-xuat', 'kho', 'san-pham', 'gu', 'cai-dat'];
const initialTab = ref(props.tab ?? '');
const up = ref<boolean | null>(null); // null = chưa kiểm tra
const restarting = ref(false);
const message = ref('');
const frame = ref<HTMLIFrameElement | null>(null);
const dark = ref(document.documentElement.classList.contains('dark'));

const hubOrigin = computed(() => {
    try {
        return new URL(props.url).origin;
    } catch {
        return '';
    }
});

const bgHex = () => {
    const m = getComputedStyle(document.body).backgroundColor.match(/\d+/g);

    return m ? '#' + m.slice(0, 3).map((n) => Number(n).toString(16).padStart(2, '0')).join('') : '';
};

// Địa chỉ iframe chỉ tính một lần lúc mở (đổi tab/giao diện sau đó dùng postMessage, không tải lại hub).
const src = ref('');
const buildSrc = () => {
    const q = new URLSearchParams({ nhung: '1', theme: dark.value ? 'dark' : 'light' });
    if (initialTab.value) {
        q.set('tab', initialTab.value);
    }
    const bg = bgHex();
    if (bg) {
        q.set('bg', bg);
    }

    return `${props.url}/?${q.toString()}`;
};

const post = (data: Record<string, string>) => frame.value?.contentWindow?.postMessage(data, hubOrigin.value);

const onMessage = (e: MessageEvent) => {
    if (e.origin !== hubOrigin.value || typeof e.data !== 'object' || e.data === null) {
        return;
    }
    const d = e.data as { type?: string; tab?: string };
    if ((d.type === 'xuong-video:tab' || d.type === 'xuong-video:san-sang') && typeof d.tab === 'string' && TABS.includes(d.tab)) {
        const u = new URL(window.location.href);
        u.searchParams.set('tab', d.tab);
        window.history.replaceState(window.history.state, '', u.toString());
    }
};

let observer: MutationObserver | null = null;
let timer: number | undefined;

const check = async () => {
    try {
        const r = await fetch('/xuong/health', { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
        const j = (await r.json()) as { up: boolean };
        const was = up.value;
        up.value = j.up;
        if (j.up && !src.value) {
            src.value = buildSrc();
        }
        if (j.up && was === false) {
            src.value = buildSrc(); // hub vừa bật lại: nạp lại khung
        }
    } catch {
        up.value = false;
    }
};

const restart = async () => {
    restarting.value = true;
    message.value = '';
    try {
        const xsrf = decodeURIComponent(document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '');
        const r = await fetch('/xuong/restart', {
            method: 'POST',
            headers: { Accept: 'application/json', 'X-XSRF-TOKEN': xsrf },
            credentials: 'same-origin',
        });
        const j = (await r.json()) as { ok: boolean; message?: string };
        message.value = j.ok ? 'Đang bật Xưởng Video, chờ vài giây…' : (j.message ?? 'Không bật lại được.');
    } catch {
        message.value = 'Không gọi được app. Dùng khay hệ thống: TikTok Auto Kid > Khởi động lại.';
    }
    window.setTimeout(() => {
        restarting.value = false;
        void check();
    }, 6000);
};

onMounted(() => {
    window.addEventListener('message', onMessage);
    observer = new MutationObserver(() => {
        const d = document.documentElement.classList.contains('dark');
        if (d !== dark.value) {
            dark.value = d;
            post({ type: 'xuong-video:theme', theme: d ? 'dark' : 'light' });
        }
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    void check();
    timer = window.setInterval(check, 5000);
});

onBeforeUnmount(() => {
    window.removeEventListener('message', onMessage);
    observer?.disconnect();
    window.clearInterval(timer);
});
</script>

<template>
    <Head title="Xưởng Video" />

    <AppLayout title="Xưởng Video" :icon="IconMovie" full-width>
        <div class="relative flex min-h-0 flex-1 flex-col" style="height: calc(100vh - 4rem)" data-testid="fork-xuong">
            <iframe
                v-if="up && src"
                ref="frame"
                :src="src"
                title="Xưởng Video"
                class="size-full flex-1 border-0"
                allow="clipboard-write; fullscreen"
                data-testid="fork-xuong-frame"
            />
            <div v-else-if="up === false" class="m-auto flex max-w-md flex-col items-center gap-4 p-8 text-center" data-testid="fork-xuong-offline">
                <IconPower class="size-12 text-muted-foreground" />
                <h1 class="font-heading text-2xl font-semibold">Xưởng Video đang tắt</h1>
                <p class="text-muted-foreground">Chưa kết nối được tới Xưởng Video. Bấm nút dưới để bật lại; lần đầu có thể mất vài giây.</p>
                <Button :disabled="restarting" data-testid="fork-xuong-restart" @click="restart">
                    {{ restarting ? 'Đang bật…' : 'Bật lại' }}
                </Button>
                <p v-if="message" class="text-sm text-muted-foreground" role="status">{{ message }}</p>
            </div>
            <div v-else class="m-auto text-muted-foreground">Đang kiểm tra Xưởng Video…</div>
        </div>
    </AppLayout>
</template>

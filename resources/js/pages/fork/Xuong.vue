<script setup lang="ts">
// Trang "Xưởng Video": nhúng giao diện hub sản xuất (iframe trỏ thẳng cổng hub).
// Hub báo đổi tab qua postMessage; app báo đổi giao diện sáng/tối cho hub. Hub tắt thì hiện thẻ "Bật lại".
import { Head } from '@inertiajs/vue3';
import { IconExternalLink, IconMovie, IconPower } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import AppLayout from '@/layouts/AppLayout.vue';

const props = defineProps<{
    url: string;
    tab: string | null;
    muc?: string | null;
}>();

const TABS = ['san-xuat', 'kho', 'san-pham', 'gu', 'prompt-ai', 'cai-dat'];
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

    return m
        ? '#' +
              m
                  .slice(0, 3)
                  .map((n) => Number(n).toString(16).padStart(2, '0'))
                  .join('')
        : '';
};

// Địa chỉ iframe chỉ tính một lần lúc mở (đổi tab/giao diện sau đó dùng postMessage, không tải lại hub).
const src = ref('');
// Khung hub nạp xong chưa (hub dựng giao diện mất vài giây): chưa xong thì phủ lớp "Đang mở…" lên trên.
const frameLoaded = ref(false);
watch(src, () => {
    frameLoaded.value = false;
});
// Mở hub ở cửa sổ riêng (khi khung nhúng chậm hoặc anh muốn xem rộng hơn).
const openUrl = computed(() => `${props.url}/`);
const buildSrc = () => {
    const q = new URLSearchParams({
        nhung: '1',
        theme: dark.value ? 'dark' : 'light',
    });
    if (initialTab.value) {
        q.set('tab', initialTab.value);
        if (props.muc) {
            q.set('muc', props.muc);
        }
    }
    const bg = bgHex();
    if (bg) {
        q.set('bg', bg);
    }

    return `${props.url}/?${q.toString()}`;
};

const post = (data: Record<string, string>) =>
    frame.value?.contentWindow?.postMessage(data, hubOrigin.value);

// Đang ở sẵn trang Xưởng mà bấm một nơi khác (vd. từ Khu Tự Trị): bảo hub đổi tab/mục, không nạp lại khung.
watch(
    () => [props.tab, props.muc],
    ([tab, muc]) => {
        if (tab && TABS.includes(tab)) {
            post({ type: 'xuong-video:set-tab', tab, muc: muc ?? '' });
        }
    },
);

const onMessage = (e: MessageEvent) => {
    if (
        e.origin !== hubOrigin.value ||
        typeof e.data !== 'object' ||
        e.data === null
    ) {
        return;
    }
    const d = e.data as { type?: string; tab?: string };
    if (
        (d.type === 'xuong-video:tab' || d.type === 'xuong-video:san-sang') &&
        typeof d.tab === 'string' &&
        TABS.includes(d.tab)
    ) {
        const u = new URL(window.location.href);
        u.searchParams.set('tab', d.tab);
        window.history.replaceState(window.history.state, '', u.toString());
    }
};

let observer: MutationObserver | null = null;
let timer: number | undefined;

// Một lần hỏi hụt (máy bận, hub đang ghi file) không gỡ khung hub ra: phải hụt 2 lần liền mới coi là tắt.
let misses = 0;
let lastCheck = 0;

// Hỏi xưởng còn chạy không: tab ẩn thì thôi (hiện lại sẽ hỏi ngay); xưởng đang chạy ổn thì 15 giây một lần,
// đang tắt / vừa lỗi thì 5 giây một lần để bật lên là thấy liền.
const check = async (force = false) => {
    if (
        document.hidden ||
        (!force && up.value && Date.now() - lastCheck < 15000)
    ) {
        return;
    }
    lastCheck = Date.now();
    let ok = false;
    try {
        const r = await fetch('/xuong/health', {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });
        ok = ((await r.json()) as { up: boolean }).up;
    } catch {
        ok = false;
    }
    misses = ok ? 0 : misses + 1;
    if (!ok && up.value && misses < 2) {
        return;
    }
    const was = up.value;
    up.value = ok;
    if (ok && (!src.value || was === false)) {
        src.value = buildSrc(); // lần đầu, hoặc hub vừa bật lại: nạp lại khung
    }
};

const restart = async () => {
    restarting.value = true;
    message.value = '';
    try {
        const xsrf = decodeURIComponent(
            document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '',
        );
        const r = await fetch('/xuong/restart', {
            method: 'POST',
            headers: { Accept: 'application/json', 'X-XSRF-TOKEN': xsrf },
            credentials: 'same-origin',
        });
        const j = (await r.json()) as { ok: boolean; message?: string };
        message.value = j.ok
            ? 'Đang bật Xưởng Video, chờ vài giây…'
            : (j.message ?? 'Không bật lại được.');
    } catch {
        message.value =
            'Không gọi được app. Dùng khay hệ thống: TikTok Auto Kid > Khởi động lại.';
    }
    window.setTimeout(() => {
        restarting.value = false;
        void check(true);
    }, 6000);
};

// Quay lại tab: hỏi xưởng còn chạy không ngay (không đợi nhịp 5 giây).
const onVis = () => {
    if (!document.hidden) {
        void check(true);
    }
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
    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class'],
    });
    void check(true);
    timer = window.setInterval(() => void check(), 5000);
    document.addEventListener('visibilitychange', onVis);
});

onBeforeUnmount(() => {
    window.removeEventListener('message', onMessage);
    observer?.disconnect();
    window.clearInterval(timer);
    document.removeEventListener('visibilitychange', onVis);
});
</script>

<template>
    <Head title="Xưởng Video" />

    <AppLayout title="Xưởng Video" :icon="IconMovie" full-width>
        <div
            class="relative flex min-h-0 flex-1 flex-col"
            style="height: calc(100vh - 4rem)"
            data-testid="fork-xuong"
        >
            <div class="relative flex min-h-0 min-w-0 flex-1 flex-col">
                <iframe
                    v-if="up && src"
                    ref="frame"
                    :src="src"
                    title="Xưởng Video"
                    class="size-full flex-1 border-0"
                    allow="clipboard-write; fullscreen"
                    data-testid="fork-xuong-frame"
                    @load="frameLoaded = true"
                />
                <div
                    v-if="up && src && !frameLoaded"
                    class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-background text-muted-foreground"
                    role="status"
                    data-testid="fork-xuong-loading"
                >
                    <Spinner class="size-6" />
                    <p class="text-sm">Đang mở Xưởng Video…</p>
                </div>
                <a
                    v-if="up && src"
                    :href="openUrl"
                    target="_blank"
                    rel="noopener"
                    class="absolute bottom-3 left-3 z-10 inline-flex items-center gap-1.5 rounded-full border bg-background/90 px-2.5 py-1 text-[0.75rem] font-medium text-muted-foreground shadow-sm backdrop-blur hover:text-foreground"
                    title="Mở Xưởng Video trong một cửa sổ mới"
                    data-testid="fork-xuong-open-new"
                >
                    <IconExternalLink class="size-3.5" />
                    Mở trong cửa sổ mới
                </a>
                <div
                    v-else-if="up === false"
                    class="m-auto flex max-w-md flex-col items-center gap-4 p-8 text-center"
                    data-testid="fork-xuong-offline"
                >
                    <IconPower class="size-12 text-muted-foreground" />
                    <h1 class="font-heading text-2xl font-semibold">
                        Xưởng Video đang tắt
                    </h1>
                    <p class="text-muted-foreground">
                        Chưa kết nối được tới Xưởng Video. Bấm nút dưới để bật
                        lại; lần đầu có thể mất vài giây.
                    </p>
                    <Button
                        :disabled="restarting"
                        data-testid="fork-xuong-restart"
                        @click="restart"
                    >
                        {{ restarting ? 'Đang bật…' : 'Bật lại' }}
                    </Button>
                    <p
                        v-if="message"
                        class="text-sm text-muted-foreground"
                        role="status"
                    >
                        {{ message }}
                    </p>
                </div>
                <div v-else class="m-auto text-muted-foreground">
                    Đang kiểm tra Xưởng Video…
                </div>
            </div>
        </div>
    </AppLayout>
</template>

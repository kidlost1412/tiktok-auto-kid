<script setup lang="ts">
// Trang "Xưởng Video": nhúng giao diện hub sản xuất (iframe trỏ thẳng cổng hub).
// Hub báo đổi tab qua postMessage; app báo đổi giao diện sáng/tối cho hub. Hub tắt thì hiện thẻ "Bật lại".
import { Head, Link } from '@inertiajs/vue3';
import { IconChevronDown, IconHome2, IconMovie, IconPower } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import MiniScene from '@/components/fork/nha3d/MiniScene.vue';
import NhatKyDaoDien from '@/components/fork/nha3d/NhatKyDaoDien.vue';
import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/AppLayout.vue';

const props = defineProps<{ url: string; tab: string | null; muc?: string | null }>();

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

    return m ? '#' + m.slice(0, 3).map((n) => Number(n).toString(16).padStart(2, '0')).join('') : '';
};

// Địa chỉ iframe chỉ tính một lần lúc mở (đổi tab/giao diện sau đó dùng postMessage, không tải lại hub).
const src = ref('');
const buildSrc = () => {
    const q = new URLSearchParams({ nhung: '1', theme: dark.value ? 'dark' : 'light' });
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

const post = (data: Record<string, string>) => frame.value?.contentWindow?.postMessage(data, hubOrigin.value);

// Đang ở sẵn trang Xưởng mà bấm một nơi khác (vd. từ Xưởng nhỏ): bảo hub đổi tab/mục, không nạp lại khung.
watch(
    () => [props.tab, props.muc],
    ([tab, muc]) => {
        if (tab && TABS.includes(tab)) {
            post({ type: 'xuong-video:set-tab', tab, muc: muc ?? '' });
        }
    },
);

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

// ---------------------------------------------------------------- thẻ "Xưởng nhỏ" thu nhỏ
// Mặc định ĐÓNG (theo yêu cầu của chủ app). Cảnh 3D chỉ được dựng (tốn three.js) khi thẻ MỞ,
// và bị dọn sạch (dispose) ngay khi đóng lại hoặc rời trang — không giữ một bản sống liên tục
// qua các lần điều hướng vì AppLayout hiện không có vùng bọc riêng nào để gửi một thực thể
// <KeepAlive> qua lại giữa Xưởng Video và Xưởng nhỏ mà không phải sửa khung dùng chung (đang có
// agent khác chỉnh ở phần khác của khung) — lazy-mount-khi-mở là phương án đánh đổi chấp nhận
// được cho lượt này: mở lại tốn khoảng 1 lần dựng three.js (dưới 1 giây), đổi lại không cõng
// chi phí 3D khi chủ app chỉ ghé qua Xưởng Video mà không cần xem.
const miniOpen = ref(false);
const miniFailed = ref(false);
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

            <!-- Thẻ "Xưởng nhỏ" thu nhỏ: nổi ở góc, không che hết khung hub, mặc định đóng. -->
            <div class="pointer-events-none absolute top-3 right-3 z-20 flex w-[min(19rem,calc(100vw-1.5rem))] flex-col items-end gap-2">
                <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    class="pointer-events-auto gap-1.5 shadow-md"
                    data-testid="xuong-mini-toggle"
                    @click="miniOpen = !miniOpen"
                >
                    <IconHome2 class="size-4" />
                    Xưởng nhỏ
                    <IconChevronDown :class="['size-3.5 transition-transform motion-reduce:transition-none', miniOpen && 'rotate-180']" />
                </Button>

                <div
                    :class="['xuong-mini-panel pointer-events-auto w-full', miniOpen && 'is-open']"
                    data-testid="xuong-mini-panel"
                >
                    <div class="xuong-mini-panel-inner">
                        <div class="flex flex-col gap-2 rounded-xl border border-border bg-card/95 p-2.5 shadow-lg backdrop-blur-sm">
                            <div class="h-36 overflow-hidden rounded-lg bg-secondary/40">
                                <MiniScene v-if="miniOpen && !miniFailed" @fail="miniFailed = true" />
                                <div v-else class="grid h-full place-items-center text-xs text-muted-foreground">
                                    {{ miniFailed ? 'Không dựng được cảnh 3D nhỏ này.' : '' }}
                                </div>
                            </div>
                            <div>
                                <p class="mb-1 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                                    Nhật ký đang làm gì
                                </p>
                                <NhatKyDaoDien :active="miniOpen" class="max-h-28" />
                            </div>
                            <Link
                                href="/nha"
                                class="inline-flex items-center justify-center gap-1.5 rounded-md border border-border py-1.5 text-[13px] font-medium hover:bg-secondary"
                                data-testid="xuong-mini-ve-xuong"
                            >
                                <IconHome2 class="size-3.5" />
                                Về xưởng nhỏ
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

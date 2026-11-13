<script setup lang="ts">
// Trang "Xưởng Video": nhúng giao diện hub sản xuất (iframe trỏ thẳng cổng hub).
// Hub báo đổi tab qua postMessage; app báo đổi giao diện sáng/tối cho hub. Hub tắt thì hiện thẻ "Bật lại".
import { Head, Link } from '@inertiajs/vue3';
import {
    IconArrowUpRight,
    IconMovie,
    IconNotes,
    IconPower,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { NhaData } from '@/components/fork/nha/types';
import MiniScene from '@/components/fork/nha3d/MiniScene.vue';
import NhatKyDaoDien from '@/components/fork/nha3d/NhatKyDaoDien.vue';
import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/AppLayout.vue';
import { cn } from '@/lib/utils';

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
const check = async () => {
    if (document.hidden && up.value) {
        return;
    }
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
    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class'],
    });
    void check();
    timer = window.setInterval(check, 5000);
});

onBeforeUnmount(() => {
    window.removeEventListener('message', onMessage);
    observer?.disconnect();
    window.clearInterval(timer);
});

// ---------------------------------------------------------------- "Khu Tự Trị" thu nhỏ
// Luôn hiện ở góc dưới bên phải (không ẩn): hai Đạo diễn ngồi làm khi xưởng có việc, đứng dậy đi lại khi rảnh,
// bấm vào để trò chuyện. Nhật ký "đang làm gì" thì gấp lại mặc định, bấm "Nhật ký" mới mở.
// Một nguồn dữ liệu chung (/nha/trang-thai) cho cả cảnh 3D lẫn nhật ký; chỉ hỏi khi tab đang hiện.
const nha = ref<NhaData | null>(null);
const sep = ref<string | undefined>(undefined);
const miniFailed = ref(false);
const diaryOpen = ref(false);
let alive = true;
let nhaTimer: number | undefined;
let nhaBusy = false;

const loadNha = async () => {
    if (nhaBusy || document.hidden) {
        return;
    }
    nhaBusy = true;
    try {
        const r = await fetch('/nha/trang-thai', {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });
        if (r.ok && alive) {
            nha.value = (await r.json()) as NhaData;
        }
    } catch {
        // im lặng: chỉ là khung trang trí, không ảnh hưởng xưởng
    } finally {
        nhaBusy = false;
    }
};

const pollNha = () => {
    window.clearTimeout(nhaTimer);
    if (!alive) {
        return;
    }
    nhaTimer = window.setTimeout(async () => {
        await loadNha();
        pollNha();
    }, 6000);
};

const onVis = () => {
    if (!document.hidden) {
        void loadNha();
        void check();
    }
};

onMounted(() => {
    void loadNha();
    pollNha();
    document.addEventListener('visibilitychange', onVis);
    fetch('/nha/nhan-vat/chinh', {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
    })
        .then((r) => (r.ok ? r.json() : null))
        .then((j: { avatar?: { ten?: string } } | null) => {
            if (alive && j?.avatar?.ten) {
                sep.value = j.avatar.ten;
            }
        })
        .catch(() => {});
});

onBeforeUnmount(() => {
    alive = false;
    window.clearTimeout(nhaTimer);
    document.removeEventListener('visibilitychange', onVis);
});

const status = computed(() => {
    const d = nha.value;
    if (!d) {
        return { text: 'đang xem…', dot: 'bg-muted-foreground/40' };
    }
    if (!d.hub.up) {
        return { text: 'xưởng tắt, đang ngủ', dot: 'bg-muted-foreground/40' };
    }
    const st = d.vai.daodien?.state ?? 'idle';
    if (st === 'working') {
        return { text: 'đang làm việc', dot: 'bg-emerald-500 animate-pulse' };
    }
    if (st === 'sleep') {
        return { text: 'đang ngủ', dot: 'bg-sky-400' };
    }

    return { text: 'đang rảnh, đi dạo', dot: 'bg-amber-400' };
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
            <iframe
                v-if="up && src"
                ref="frame"
                :src="src"
                title="Xưởng Video"
                class="size-full flex-1 border-0"
                allow="clipboard-write; fullscreen"
                data-testid="fork-xuong-frame"
            />
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
                    Chưa kết nối được tới Xưởng Video. Bấm nút dưới để bật lại;
                    lần đầu có thể mất vài giây.
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

            <!-- "Khu Tự Trị" thu nhỏ: luôn hiện ở góc dưới phải; nhật ký gấp lại mặc định. -->
            <section
                class="absolute right-4 bottom-4 z-20 flex w-[min(20rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border bg-card shadow-[0_12px_32px_-8px_rgba(0,0,0,.28)]"
                aria-label="Khu Tự Trị"
                data-testid="xuong-mini-panel"
            >
                <header class="flex items-center gap-2 px-3 pt-2.5 pb-1.5">
                    <span
                        :class="cn('size-2 shrink-0 rounded-full', status.dot)"
                    />
                    <div class="min-w-0 flex-1 leading-tight">
                        <div class="text-[13px] font-semibold">Khu Tự Trị</div>
                        <div
                            class="truncate text-[11.5px] text-muted-foreground"
                            data-testid="xuong-mini-status"
                        >
                            Đạo diễn {{ status.text }}
                        </div>
                    </div>
                    <button
                        type="button"
                        :class="
                            cn(
                                'flex h-7 items-center gap-1 rounded-md px-2 text-[12px] font-medium transition-colors',
                                diaryOpen
                                    ? 'bg-secondary text-foreground'
                                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
                            )
                        "
                        :aria-expanded="diaryOpen"
                        data-testid="xuong-mini-toggle"
                        @click="diaryOpen = !diaryOpen"
                    >
                        <IconNotes class="size-3.5" />
                        Nhật ký
                    </button>
                    <Link
                        href="/nha"
                        class="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground"
                        title="Mở Khu Tự Trị đầy đủ"
                        aria-label="Mở Khu Tự Trị đầy đủ"
                        data-testid="xuong-mini-ve-xuong"
                    >
                        <IconArrowUpRight class="size-4" />
                    </Link>
                </header>
                <div
                    class="relative mx-2 h-44 overflow-hidden rounded-xl bg-gradient-to-b from-violet-100/70 to-secondary/40 dark:from-violet-950/40 dark:to-secondary/30"
                >
                    <MiniScene
                        v-if="!miniFailed"
                        :data="nha"
                        :sep="sep"
                        @fail="miniFailed = true"
                    />
                    <div
                        v-else
                        class="grid h-full place-items-center px-4 text-center text-xs text-muted-foreground"
                    >
                        Máy này không dựng được cảnh 3D — mở Khu Tự Trị đầy đủ
                        để xem bản 2D.
                    </div>
                </div>
                <p class="px-3 pt-1.5 pb-2 text-[11px] text-muted-foreground">
                    Bấm vào một Đạo diễn để trò chuyện.
                </p>
                <div v-if="diaryOpen" class="border-t px-2.5 py-2">
                    <NhatKyDaoDien :data="nha" class="max-h-32" />
                </div>
            </section>
        </div>
    </AppLayout>
</template>

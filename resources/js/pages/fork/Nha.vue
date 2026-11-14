<script setup lang="ts">
// Trang chủ "Khu Tự Trị": ngôi nhà hoạt hình hiện ê-kíp đang làm gì (dữ liệu thật, hỏi lại mỗi ~3 giây khi đang xem).
// Bấm nhân vật/phòng để tới đúng nơi làm việc của vai đó. Mặc định là ngôi nhà 3D (three.js tải lười);
// máy không có WebGL hoặc dựng lỗi thì tự quay về ngôi nhà 2D. `?demo=1` phát lại một lô giả (không gọi máy chủ).
import { Head, router } from '@inertiajs/vue3';
import { IconHome } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import BanLamViec from '@/components/fork/nha/ban/BanLamViec.vue';
import { onMoBan } from '@/components/fork/nha/ban/bus';
import { BAN } from '@/components/fork/nha/ban/registry';
import ThanhViec from '@/components/fork/nha/ban/ThanhViec.vue';
import House from '@/components/fork/nha/House.vue';
import { recentEvents } from '@/components/fork/nha/su-kien';
import { DICH, type NhaData } from '@/components/fork/nha/types';
import Nha3D from '@/components/fork/nha3d/Nha3D.vue';
import VideoViewer from '@/components/fork/shared/VideoViewer.vue';
import AppLayout from '@/layouts/AppLayout.vue';

const props = defineProps<{ avatar?: Record<string, unknown> | null }>();
const data = ref<NhaData | null>(null);
const failed = ref(false);
const use2d = ref(false);
const params =
    typeof window === 'undefined'
        ? new URLSearchParams()
        : new URLSearchParams(window.location.search);
const demo = params.has('demo');
const debug = demo || params.has('debug');
const hourParam = params.get('gio');
const hour =
    hourParam !== null && hourParam !== '' && !Number.isNaN(Number(hourParam))
        ? Number(hourParam)
        : null;
let demoSrc: { snapshot: () => NhaData } | null = null;
const now = ref(new Date());

const greeting = computed(() => {
    const h = now.value.getHours();

    return h < 11
        ? 'Chào buổi sáng'
        : h < 14
          ? 'Chào buổi trưa'
          : h < 18
            ? 'Chào buổi chiều'
            : 'Chào buổi tối';
});
const line = computed(() =>
    failed.value && !data.value
        ? 'Chưa hỏi được trạng thái xưởng, đang thử lại…'
        : (data.value?.line ?? 'Đang mở cửa xưởng…'),
);

const roles: { key: string; emoji: string }[] = [
    { key: 'bienkich', emoji: '✍️' },
    { key: 'thuam', emoji: '🎙️' },
    { key: 'daodien', emoji: '🎬' },
    { key: 'thodung', emoji: '🛠️' },
    { key: 'giamkhao', emoji: '🧐' },
    { key: 'thukho', emoji: '📦' },
    { key: 'chuquay', emoji: '🛒' },
    { key: 'cu', emoji: '📊' },
    { key: 'buuta', emoji: '📮' },
];
const chips = computed(() =>
    roles.map((r) => {
        const v = data.value?.vai[r.key];
        const down = !data.value || data.value.mode === 'down';
        const st = down ? 'sleep' : (v?.state ?? 'idle');

        return {
            ...r,
            ten: DICH[r.key].ten,
            st,
            text:
                st === 'sleep'
                    ? 'Đang ngủ'
                    : (v?.bubble ??
                      (st === 'working' ? 'Đang làm việc' : 'Đang rảnh')),
        };
    }),
);

// ---- hoạt động gần đây: 8 sự kiện mới nhất của sổ sự kiện hub, mới nhất lên đầu
const recent = computed(() => recentEvents(data.value?.events));

// Bấm nhân vật / phòng: mở "Bàn làm việc" (popup) ngay tại chỗ; vai chưa có bàn thì đi tới trang như cũ.
// ?ban=<vai> trên địa chỉ để tải lại / quay lại vẫn mở đúng bàn.
const banParam = params.get('ban');
const ban = ref<string | null>(banParam && BAN[banParam] ? banParam : null);
watch(ban, (v) => {
    const q = new URLSearchParams(window.location.search);
    if (v) {
        q.set('ban', v);
    } else {
        q.delete('ban');
    }
    const qs = q.toString();
    window.history.replaceState(
        window.history.state,
        '',
        `${window.location.pathname}${qs ? `?${qs}` : ''}`,
    );
});
const go = (key: string) => {
    if (BAN[key]) {
        ban.value = key;

        return;
    }
    const href = DICH[key]?.href;
    if (href) {
        router.visit(href);
    }
};

let timer: number | undefined;
let inflight = false;
// Rời trang khi một lượt hỏi đang dở: lượt đó xong thì KHÔNG hẹn lượt mới (tránh vòng hỏi chạy ngầm mãi).
let alive = true;
const load = async () => {
    if (inflight || document.hidden) {
        return;
    }
    inflight = true;
    try {
        if (demo) {
            if (!demoSrc) {
                const { createDemo } =
                    await import('@/components/fork/nha3d/demo');
                demoSrc = createDemo(Number(params.get('t') ?? 0) || 0);
            }
            data.value = demoSrc.snapshot();
            failed.value = false;

            return;
        }
        const r = await fetch('/nha/trang-thai', {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });
        const d = (await r.json()) as NhaData;
        if (alive) {
            data.value = d;
            failed.value = false;
        }
    } catch {
        failed.value = true;
    } finally {
        inflight = false;
    }
};
// Đang làm việc thì hỏi dày (3 giây), rảnh/tắt thì thưa (10 giây); tab ẩn thì dừng hẳn.
const schedule = () => {
    window.clearTimeout(timer);
    if (!alive || document.hidden) {
        return;
    }
    const busy =
        data.value?.mode === 'working' ||
        data.value?.vai.buuta?.state === 'working';
    timer = window.setTimeout(
        async () => {
            await load();
            now.value = new Date();
            schedule();
        },
        demo ? 1000 : busy ? 3000 : 10000,
    );
};
const onVis = () => {
    if (!document.hidden) {
        void load().then(schedule);
    } else {
        window.clearTimeout(timer);
    }
};

const offMoBan = onMoBan((v) => go(v));
onMounted(() => {
    document.addEventListener('visibilitychange', onVis);
    void load().then(schedule);
});
onBeforeUnmount(() => {
    offMoBan();
    alive = false;
    document.removeEventListener('visibilitychange', onVis);
    window.clearTimeout(timer);
});
</script>

<template>
    <Head title="Khu Tự Trị" />

    <AppLayout title="Khu Tự Trị" :icon="IconHome" full-width>
        <div class="flex w-full flex-col" data-testid="fork-nha">
            <!-- Ngôi nhà phủ kín màn hình dưới thanh tiêu đề; lời chào là một khung kính nhỏ góc trên trái -->
            <div
                v-if="!use2d"
                class="relative h-[max(400px,min(calc(100svh-63px),115vw))] w-full overflow-hidden"
            >
                <Nha3D
                    class="absolute inset-0"
                    :data="data"
                    :hour="hour"
                    :debug="debug"
                    :avatar="props.avatar ?? null"
                    @go="go"
                    @fallback="use2d = true"
                />
                <ThanhViec :data="data" @open="go" />
                <div
                    class="pointer-events-none absolute top-3 left-3 flex max-w-[min(440px,calc(100%-24px))] flex-col gap-1.5 md:top-4 md:left-5"
                >
                    <div
                        class="rounded-2xl border border-white/60 bg-white/75 px-3 py-1.5 text-[#3d2f5c] shadow-[0_4px_18px_rgba(74,56,104,.16)] backdrop-blur-md sm:px-3.5 sm:py-2 md:px-4 md:py-2.5"
                    >
                        <h1
                            class="font-heading text-base leading-tight font-bold tracking-tight sm:text-lg md:text-2xl"
                        >
                            {{ greeting }}!
                        </h1>
                        <p
                            class="line-clamp-2 text-xs leading-snug font-medium text-[#5a4a78] sm:text-[0.8125rem] md:text-[0.9375rem]"
                            role="status"
                            data-testid="nha-line"
                        >
                            {{ line }}
                        </p>
                    </div>
                    <span
                        v-if="demo"
                        class="self-start rounded-full bg-amber-300/90 px-2.5 py-0.5 text-[0.6875rem] font-bold text-amber-950 shadow sm:px-3 sm:py-1 sm:text-xs"
                        >Xem thử · dữ liệu giả</span
                    >
                </div>
            </div>
            <div
                v-else
                class="mx-auto flex w-full max-w-[1240px] flex-col gap-3 px-4 pt-5 md:px-8"
            >
                <div class="flex flex-col gap-1">
                    <h1
                        class="font-heading text-2xl font-semibold tracking-tight md:text-3xl"
                    >
                        {{ greeting }}!
                    </h1>
                    <p
                        class="text-base text-muted-foreground md:text-lg"
                        role="status"
                        data-testid="nha-line"
                    >
                        {{ line }}
                    </p>
                </div>
                <div
                    class="relative overflow-hidden rounded-3xl border border-border bg-card shadow-sm"
                >
                    <House :data="data" @go="go" />
                </div>
            </div>

            <div
                class="mx-auto flex w-full max-w-[1240px] flex-col gap-4 px-4 py-5 md:px-8"
            >
                <section
                    class="rounded-2xl border border-border bg-card px-4 py-3"
                    aria-label="Hoạt động gần đây"
                    data-testid="nha-recent"
                >
                    <h2
                        class="mb-1.5 text-sm font-semibold text-muted-foreground"
                    >
                        Hoạt động gần đây
                    </h2>
                    <ol v-if="recent.length" class="flex flex-col gap-1">
                        <li
                            v-for="r in recent"
                            :key="r.n"
                            class="flex gap-2 text-[0.9375rem]"
                            :class="r.bad ? 'text-destructive' : ''"
                        >
                            <span
                                class="w-11 shrink-0 text-muted-foreground tabular-nums"
                                >{{ r.time }}</span
                            >
                            <span class="min-w-0">{{ r.text }}</span>
                        </li>
                    </ol>
                    <p v-else class="text-[0.9375rem] text-muted-foreground">
                        Chưa có hoạt động nào gần đây.
                    </p>
                </section>

                <ul
                    class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3"
                    aria-label="Các nhân vật trong xưởng"
                >
                    <li v-for="c in chips" :key="c.key">
                        <button
                            type="button"
                            class="flex w-full items-center gap-3 rounded-2xl border border-border bg-card px-3.5 py-2.5 text-left transition-colors hover:border-primary/50 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                            :data-testid="`nha-chip-${c.key}`"
                            @click="go(c.key)"
                        >
                            <span
                                class="grid size-10 shrink-0 place-items-center rounded-xl bg-secondary text-xl"
                                >{{ c.emoji }}</span
                            >
                            <span class="min-w-0 flex-1">
                                <span
                                    class="flex items-center gap-2 text-[0.9375rem] font-semibold"
                                >
                                    {{ c.ten }}
                                    <span
                                        class="inline-block size-2 rounded-full"
                                        :class="
                                            c.st === 'working'
                                                ? 'bg-emerald-500'
                                                : c.st === 'sleep'
                                                  ? 'bg-muted-foreground/40'
                                                  : 'bg-amber-400'
                                        "
                                    />
                                </span>
                                <span
                                    class="block truncate text-sm text-muted-foreground"
                                    >{{ c.text }}</span
                                >
                            </span>
                        </button>
                    </li>
                </ul>
            </div>
        </div>
        <BanLamViec v-model:vai="ban" :data="data" />
        <VideoViewer />
    </AppLayout>
</template>

<script setup lang="ts">
// Trang chủ "Xưởng nhỏ": ngôi nhà hoạt hình hiện ê-kíp đang làm gì (dữ liệu thật, hỏi lại mỗi ~3 giây khi đang xem).
// Bấm nhân vật/phòng để tới đúng nơi làm việc của vai đó.
import { Head, router } from '@inertiajs/vue3';
import { IconHome } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import House from '@/components/fork/nha/House.vue';
import { DICH, type NhaData, type NhaEvent } from '@/components/fork/nha/types';
import AppLayout from '@/layouts/AppLayout.vue';

const data = ref<NhaData | null>(null);
const failed = ref(false);
const now = ref(new Date());

const greeting = computed(() => {
    const h = now.value.getHours();

    return h < 11 ? 'Chào buổi sáng' : h < 14 ? 'Chào buổi trưa' : h < 18 ? 'Chào buổi chiều' : 'Chào buổi tối';
});
const line = computed(() => (failed.value && !data.value ? 'Chưa hỏi được trạng thái xưởng, đang thử lại…' : (data.value?.line ?? 'Đang mở cửa xưởng…')));

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
            text: st === 'sleep' ? 'Đang ngủ' : (v?.bubble ?? (st === 'working' ? 'Đang làm việc' : 'Đang rảnh')),
        };
    }),
);

// ---- hoạt động gần đây: 8 sự kiện mới nhất của sổ sự kiện hub, mới nhất lên đầu
const VAI_TEN: Record<string, string> = { 'bien-kich': 'Biên kịch', giong: 'Thu âm', 'dao-dien': 'Đạo diễn', dung: 'Thợ dựng', 'giam-khao': 'Giám khảo', kho: 'Thủ kho', 'he-thong': 'Xưởng' };
const videoNo = (e: NhaEvent) => {
    const m = /-(\d+)$/.exec(e.video ?? '');

    return m ? Number(m[1]) + 1 : null;
};
const describe = (e: NhaEvent): string | null => {
    const v = videoNo(e);
    const vid = v ? ` video ${v}` : '';
    switch (`${e.vai}|${e.loai}`) {
        case 'he-thong|bat-dau-lo':
            return `Bắt đầu lô ${e.ten ?? ''}${e.so_video ? ` · ${e.so_video} video` : ''}`.trim();
        case 'bien-kich|xong':
            return `Biên kịch viết xong ${e.so ?? ''} lời`;
        case 'giong|xong':
            return `Thu âm xong ${e.so ?? ''} giọng`;
        case 'dao-dien|xong':
            return `Đạo diễn xong bảng dựng${vid}`;
        case 'dung|xong':
            return e.buoc === 'chu' ? 'Thợ dựng xong lớp chữ' : `Thợ dựng dựng xong${vid}`;
        case 'giam-khao|diem':
            return e.diem == null ? `Giám khảo chưa chấm được${vid}` : `Giám khảo chấm${vid}: ${e.diem}/10 ${e.dat ? '✓' : '✗'}${!e.dat && e.loi ? ` · ${e.loi}` : ''}`;
        case 'kho|luu':
            return `Nhập kho video ${e.so ?? ''}/${e.tong ?? ''}`;
        case 'he-thong|het-han-muc':
            return 'Hết hạn mức Claude, xưởng nghỉ';
        case 'he-thong|ket-thuc-lo':
            return `Xong lô ${e.so ?? ''}/${e.tong ?? ''}${e.phut ? ` · ${String(e.phut).replace('.', ',')} phút` : ''}`;
        default:
            return e.loai === 'loi' ? `${VAI_TEN[e.vai] ?? 'Xưởng'} gặp lỗi${e.msg ? `: ${e.msg}` : ''}` : null;
    }
};
const recent = computed(() => {
    const out: { n: number; time: string; text: string; bad: boolean }[] = [];
    for (const e of [...(data.value?.events ?? [])].reverse()) {
        const text = describe(e);
        if (text && out.length < 8) {
            out.push({ n: e.n, time: (e.t ?? '').slice(11, 16), text, bad: e.loai === 'loi' || e.loai === 'het-han-muc' || (e.loai === 'diem' && e.dat === false) });
        }
    }

    return out;
});

const go = (key: string) => {
    const href = DICH[key]?.href;
    if (href) {
        router.visit(href);
    }
};

let timer: number | undefined;
let inflight = false;
const load = async () => {
    if (inflight || document.hidden) {
        return;
    }
    inflight = true;
    try {
        const r = await fetch('/nha/trang-thai', { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
        data.value = (await r.json()) as NhaData;
        failed.value = false;
    } catch {
        failed.value = true;
    } finally {
        inflight = false;
    }
};
// Đang làm việc thì hỏi dày (3 giây), rảnh/tắt thì thưa (10 giây); tab ẩn thì dừng hẳn.
const schedule = () => {
    window.clearTimeout(timer);
    if (document.hidden) {
        return;
    }
    const busy = data.value?.mode === 'working' || data.value?.vai.buuta?.state === 'working';
    timer = window.setTimeout(async () => {
        await load();
        now.value = new Date();
        schedule();
    }, busy ? 3000 : 10000);
};
const onVis = () => {
    if (!document.hidden) {
        void load().then(schedule);
    } else {
        window.clearTimeout(timer);
    }
};

onMounted(() => {
    document.addEventListener('visibilitychange', onVis);
    void load().then(schedule);
});
onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', onVis);
    window.clearTimeout(timer);
});
</script>

<template>
    <Head title="Xưởng nhỏ" />

    <AppLayout title="Xưởng nhỏ" :icon="IconHome">
        <div class="mx-auto flex w-full max-w-[1240px] flex-col gap-4 px-4 py-5 md:px-8" data-testid="fork-nha">
            <div class="flex flex-col gap-1">
                <h1 class="font-heading text-2xl font-semibold tracking-tight md:text-3xl">{{ greeting }}!</h1>
                <p class="text-base text-muted-foreground md:text-lg" role="status" data-testid="nha-line">{{ line }}</p>
            </div>

            <div class="overflow-hidden rounded-3xl border border-border bg-card shadow-sm">
                <House :data="data" @go="go" />
            </div>

            <section class="rounded-2xl border border-border bg-card px-4 py-3" aria-label="Hoạt động gần đây" data-testid="nha-recent">
                <h2 class="mb-1.5 text-sm font-semibold text-muted-foreground">Hoạt động gần đây</h2>
                <ol v-if="recent.length" class="flex flex-col gap-1">
                    <li v-for="r in recent" :key="r.n" class="flex gap-2 text-[15px]" :class="r.bad ? 'text-destructive' : ''">
                        <span class="w-11 shrink-0 text-muted-foreground tabular-nums">{{ r.time }}</span>
                        <span class="min-w-0">{{ r.text }}</span>
                    </li>
                </ol>
                <p v-else class="text-[15px] text-muted-foreground">Chưa có hoạt động nào gần đây.</p>
            </section>

            <ul class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3" aria-label="Các nhân vật trong xưởng">
                <li v-for="c in chips" :key="c.key">
                    <button
                        type="button"
                        class="flex w-full items-center gap-3 rounded-2xl border border-border bg-card px-3.5 py-2.5 text-left transition-colors hover:border-primary/50 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                        :data-testid="`nha-chip-${c.key}`"
                        @click="go(c.key)"
                    >
                        <span class="grid size-10 shrink-0 place-items-center rounded-xl bg-secondary text-xl">{{ c.emoji }}</span>
                        <span class="min-w-0 flex-1">
                            <span class="flex items-center gap-2 text-[15px] font-semibold">
                                {{ c.ten }}
                                <span
                                    class="inline-block size-2 rounded-full"
                                    :class="c.st === 'working' ? 'bg-emerald-500' : c.st === 'sleep' ? 'bg-muted-foreground/40' : 'bg-amber-400'"
                                />
                            </span>
                            <span class="block truncate text-sm text-muted-foreground">{{ c.text }}</span>
                        </span>
                    </button>
                </li>
            </ul>
        </div>
    </AppLayout>
</template>

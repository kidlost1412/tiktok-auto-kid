<script setup lang="ts">
// Kho riêng: video bạn tự làm. Thêm thư mục, chọn video (bấm, kéo, Shift) rồi đăng / hẹn giờ, hoặc cất vào "Giỏ chờ đăng".
// Trang tự cập nhật: video mới bỏ vào thư mục xuất hiện trong ~10 giây, không cần bấm gì.
import { router } from '@inertiajs/vue3';
import {
    IconChecks,
    IconClipboardList,
    IconFolder,
    IconFolderPlus,
    IconPlaylistAdd,
    IconRefresh,
    IconSend,
    IconTrash,
    IconVideoOff,
    IconX,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import BatchDialog, { type BatchAccount } from '@/components/fork/kho/BatchDialog.vue';
import KhoSwitch from '@/components/fork/kho/KhoSwitch.vue';
import RiengCard from '@/components/fork/kho/RiengCard.vue';
import RiengQueueDialog from '@/components/fork/kho/RiengQueueDialog.vue';
import {
    type BatchItem,
    postJson,
    type QueueItem,
    type RiengVideo,
    xsrf,
} from '@/components/fork/kho/rieng';
import RiengSteps from '@/components/fork/kho/RiengSteps.vue';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import { cardCls } from '@/components/fork/shared/status';
import { openVideo as openViewer, viewerActions } from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

interface Folder {
    id: number;
    name: string;
    path: string;
    exists: boolean;
    count: number;
}

interface Selectable {
    id: number;
    file_name: string;
    duration?: number | null;
    duplicate: string | null;
}

const props = defineProps<{
    folders: Folder[];
    filters: { folder: number; status: string; day: string };
    counts: Record<string, number>;
    days: string[];
    videos: {
        data: RiengVideo[];
        current_page: number;
        last_page: number;
        total: number;
    };
    selectable: Selectable[];
    queue: QueueItem[];
    scan_sig: string;
    accounts: BatchAccount[];
    hashtag_suggestions?: { tag: string; uses: number }[];
    limits: { min_lead_minutes: number; gap_minutes: number; caption_max: number };
    last_scan_at: string | null;
}>();

const RELOAD_ONLY = ['videos', 'counts', 'selectable', 'days', 'folders', 'queue', 'scan_sig', 'last_scan_at'];
const FORMATS = '.mp4, .mov, .m4v, .webm';

const busy = ref('');
const folderPath = ref('');
const folderName = ref('');
const dialogOpen = ref(false);
const batchStep = ref<'form' | 'preview' | 'result'>('form');
const batchItems = ref<BatchItem[]>([]);
const queueOpen = ref(false);

// ---------------------------------------------------------------- Chọn video
// Các video đã chọn (nhớ cả khi sang trang khác): id -> tên file + cờ trùng.
const picked = ref<Record<number, { file_name: string; duplicate: string | null }>>({});
const selectMode = ref(false);

// Thời lượng (giây) của video đã chọn, để hộp thoại đăng hiện trên hình nhỏ.
const durationOf = (id: number): number | null =>
    props.selectable.find((x) => x.id === id)?.duration ?? props.videos.data.find((x) => x.id === id)?.duration ?? null;

const pickedItems = computed<BatchItem[]>(() =>
    Object.entries(picked.value).map(([id, p]) => ({ id: Number(id), file_name: p.file_name, duration: durationOf(Number(id)), duplicate: p.duplicate })),
);
const pickedDupCount = computed(() => pickedItems.value.filter((i) => i.duplicate).length);

// "Chọn tất cả" chỉ chọn video không trùng; video trùng phải tự chọn.
const plain = computed(() => props.selectable.filter((s) => !s.duplicate));
const dupCount = computed(() => props.selectable.length - plain.value.length);
const allSelected = computed(() => plain.value.length > 0 && plain.value.every((s) => s.id in picked.value));

const dupOf = (v: RiengVideo): string | null => v.duplicate?.text ?? null;
const pickOne = (v: RiengVideo) => {
    picked.value[v.id] = { file_name: v.file_name, duplicate: dupOf(v) };
};

let lastIdx = -1;
const idxOf = (id: number) => props.videos.data.findIndex((x) => x.id === id);

// Bấm chọn / bỏ chọn; giữ Shift thì chọn cả đoạn từ video bấm trước đó.
const toggle = (v: RiengVideo, shift = false) => {
    if (!v.selectable) {
        return;
    }

    const i = idxOf(v.id);
    const on = !(v.id in picked.value);

    if (shift && lastIdx >= 0 && lastIdx !== i) {
        const [lo, hi] = [Math.min(lastIdx, i), Math.max(lastIdx, i)];

        for (const x of props.videos.data.slice(lo, hi + 1)) {
            if (!x.selectable) {
                continue;
            }

            if (on) {
                pickOne(x);
            } else {
                delete picked.value[x.id];
            }
        }
    } else if (on) {
        pickOne(v);
    } else {
        delete picked.value[v.id];
    }

    lastIdx = i;
};

const toggleAll = () => {
    if (allSelected.value) {
        for (const s of plain.value) {
            delete picked.value[s.id];
        }
    } else {
        for (const s of plain.value) {
            picked.value[s.id] = { file_name: s.file_name, duplicate: null };
        }
    }
};

const clearPicked = () => {
    picked.value = {};
    lastIdx = -1;
};

const toggleSelectMode = () => {
    selectMode.value = !selectMode.value;
};

// ---- Kéo để chọn (khung chọn): nhấn chuột rồi kéo quét qua các thẻ, không cần Shift hay chế độ "Chọn".
// Chuột: kéo quá ~6px mới tính là kéo (bấm thường vẫn mở/chọn như cũ). Cảm ứng: nhấn giữ ~0,35 giây rồi kéo.
// Bắt đầu từ thẻ chưa chọn = thêm vào; bắt đầu từ thẻ đã chọn = quét bỏ chọn. Esc huỷ, về như trước khi kéo.
const grid = ref<HTMLElement | null>(null);
const DRAG_THRESHOLD = 6;
const HOLD_MS = 350;
const EDGE = 90;

interface Drag {
    ax: number; // điểm bắt đầu theo toạ độ trang (đã cộng cuộn)
    ay: number;
    cx: number; // con trỏ hiện tại theo màn hình
    cy: number;
    on: boolean;
    base: typeof picked.value;
    active: boolean; // false = mới nhấn, chưa vượt ngưỡng
    touch: boolean;
}

let drag: Drag | null = null;
let hold: { x: number; y: number; id: number; timer: ReturnType<typeof setTimeout> } | null = null;
let raf = 0;
let suppressClick = false;

/** Khung chọn đang vẽ (toạ độ màn hình, position: fixed). */
const band = ref<{ left: number; top: number; width: number; height: number } | null>(null);
/** Thẻ đang được nhấn giữ (cảm ứng) để nháy báo hiệu sắp vào chế độ kéo. */
const holdingId = ref<number | null>(null);

const cardIdAt = (el: Element | null): number | null => {
    const c = el?.closest?.('[data-card-id]') as HTMLElement | null;

    return c ? Number(c.dataset.cardId) : null;
};

const updateBand = () => {
    if (!drag?.active) {
        band.value = null;

        return;
    }

    const x1 = drag.ax - window.scrollX;
    const y1 = drag.ay - window.scrollY;

    band.value = {
        left: Math.min(x1, drag.cx),
        top: Math.min(y1, drag.cy),
        width: Math.abs(drag.cx - x1),
        height: Math.abs(drag.cy - y1),
    };
};

// Chọn mọi thẻ chạm khung (cộng/trừ vào tập chọn ban đầu).
const applyBand = () => {
    if (!drag?.active || !grid.value || !band.value) {
        return;
    }

    const b = band.value;
    const next = { ...drag.base };

    for (const el of grid.value.querySelectorAll<HTMLElement>('[data-card-id]')) {
        const r = el.getBoundingClientRect();

        if (r.right < b.left || r.left > b.left + b.width || r.bottom < b.top || r.top > b.top + b.height) {
            continue;
        }

        const x = props.videos.data.find((v) => v.id === Number(el.dataset.cardId));

        if (!x?.selectable) {
            continue;
        }

        if (drag.on) {
            next[x.id] = { file_name: x.file_name, duplicate: dupOf(x) };
        } else {
            delete next[x.id];
        }
    }

    picked.value = next;
};

const refresh = () => {
    updateBand();
    applyBand();
};

// Tự cuộn khi con trỏ gần mép trên/dưới; càng sát mép càng nhanh.
const tick = () => {
    raf = 0;

    if (!drag?.active) {
        return;
    }

    const top = EDGE - drag.cy;
    const bottom = drag.cy - (window.innerHeight - EDGE);
    const speed = top > 0 ? -Math.min(28, 4 + top * 0.25) : bottom > 0 ? Math.min(28, 4 + bottom * 0.25) : 0;

    if (speed) {
        window.scrollBy(0, speed);
        refresh();
    }

    raf = requestAnimationFrame(tick);
};

const removeListeners = () => {
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', endDrag);
    window.removeEventListener('pointercancel', endDrag);
    window.removeEventListener('keydown', onKey);
    document.documentElement.classList.remove('rieng-dragging');
};

const endDrag = () => {
    removeListeners();

    if (hold) {
        clearTimeout(hold.timer);
        hold = null;
    }

    holdingId.value = null;

    if (raf) {
        cancelAnimationFrame(raf);
        raf = 0;
    }

    const wasActive = drag?.active ?? false;

    drag = null;
    band.value = null;

    // Vừa kéo xong: nuốt cú click đi kèm để không mở video ngoài ý muốn.
    if (wasActive) {
        suppressClick = true;
        setTimeout(() => {
            suppressClick = false;
        }, 0);
    }
};

const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && drag) {
        if (drag.active) {
            picked.value = drag.base;
        }

        endDrag();
    }
};

const activate = () => {
    if (!drag || drag.active) {
        return;
    }

    drag.active = true;
    document.documentElement.classList.add('rieng-dragging');
    window.getSelection()?.removeAllRanges();
    holdingId.value = null;
    raf = requestAnimationFrame(tick);
};

const onMove = (e: PointerEvent) => {
    if (!drag) {
        return;
    }

    drag.cx = e.clientX;
    drag.cy = e.clientY;

    if (!drag.active) {
        const moved = Math.hypot(e.clientX - (drag.ax - window.scrollX), e.clientY - (drag.ay - window.scrollY));

        if (drag.touch) {
            // Vuốt trước khi nhấn giữ đủ lâu = đang cuộn trang, bỏ.
            if (moved > 10) {
                endDrag();
            }

            return;
        }

        if (moved < DRAG_THRESHOLD) {
            return;
        }

        activate();
    }

    refresh();
};

const onPointerDown = (e: PointerEvent) => {
    const t = e.target as HTMLElement;
    const id = cardIdAt(t);

    if (t.closest('button, a, input, select, textarea, [role="checkbox"]')) {
        return;
    }

    if (e.pointerType === 'mouse' && (e.button !== 0 || e.shiftKey || e.ctrlKey || e.metaKey || e.altKey)) {
        return;
    }

    // Điểm bắt đầu: trên thẻ chưa chọn = thêm; trên thẻ đã chọn = quét bỏ; ở khe giữa các thẻ = thêm.
    const startsOnPicked = id !== null && id in picked.value;
    const touch = e.pointerType !== 'mouse';

    drag = {
        ax: e.clientX + window.scrollX,
        ay: e.clientY + window.scrollY,
        cx: e.clientX,
        cy: e.clientY,
        on: !startsOnPicked,
        base: { ...picked.value },
        active: false,
        touch,
    };

    if (touch) {
        if (id === null) {
            drag = null;

            return;
        }

        holdingId.value = id;
        hold = {
            x: e.clientX,
            y: e.clientY,
            id,
            timer: setTimeout(() => {
                hold = null;
                activate();
                refresh();
            }, HOLD_MS),
        };
    }

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', endDrag);
    window.addEventListener('pointercancel', endDrag);
    window.addEventListener('keydown', onKey);
};

// Đang kéo bằng ngón tay thì chặn trang cuộn theo.
const onTouchMove = (e: TouchEvent) => {
    if (drag?.active && e.cancelable) {
        e.preventDefault();
    }
};

// Chặn kéo ảnh gốc của trình duyệt và menu chuột phải/nhấn giữ khi đang kéo chọn.
const onDragStart = (e: Event) => e.preventDefault();
const onContextMenu = (e: Event) => {
    if (drag || hold) {
        e.preventDefault();
    }
};

const onCardClick =(v: RiengVideo, shift: boolean) => {
    if (suppressClick) {
        return;
    }

    toggle(v, shift);
};

const onCardOpen = (v: RiengVideo) => {
    if (suppressClick) {
        return;
    }

    openViewer(
        props.videos.data.map((x) => x.id),
        v.id,
    );
};

// ---------------------------------------------------------------- Giỏ chờ đăng
const queue = ref<QueueItem[]>(props.queue);
watch(
    () => props.queue,
    (q) => {
        queue.value = q;
    },
);
const queuedIds = computed(() => new Set(queue.value.map((q) => q.id)));

const queueCall = async (url: string, body: unknown): Promise<boolean> => {
    const r = await postJson<{ queue: QueueItem[]; added?: number }>(url, body);

    if (!r) {
        toast.error('Không cập nhật được giỏ chờ đăng, hãy thử lại.');

        return false;
    }

    queue.value = r.queue;

    return true;
};

const addToQueue = async (ids: number[]) => {
    const before = queue.value.length;

    if (await queueCall('/auto/kho/rieng/gio-cho/them', { ids })) {
        const n = queue.value.length - before;
        toast.success(n > 0 ? `Đã cất ${n} video vào giỏ chờ đăng.` : 'Các video này đã có trong giỏ chờ đăng.');
    }
};

const removeFromQueue = (ids: number[]) => queueCall('/auto/kho/rieng/gio-cho/bo', { ids });

const toggleQueue = async (id: number) => {
    if (queuedIds.value.has(id)) {
        await removeFromQueue([id]);
    } else {
        await addToQueue([id]);
    }
};

const clearQueue = async () => {
    if (!window.confirm('Xoá hết video khỏi giỏ chờ đăng? Video vẫn còn nguyên trong kho, chỉ bỏ khỏi giỏ.')) {
        return;
    }

    await queueCall('/auto/kho/rieng/gio-cho/bo', { all: true });
};

const pickedToQueue = async () => {
    await addToQueue(pickedItems.value.map((i) => i.id));
    clearPicked();
    selectMode.value = false;
};

// ---------------------------------------------------------------- Đăng / hẹn giờ
const openBatch = (items: BatchItem[]) => {
    if (!items.length) {
        return;
    }

    batchItems.value = items;
    dialogOpen.value = true;
};

const postPicked = () => openBatch(pickedItems.value);
const postQueue = () => {
    queueOpen.value = false;
    openBatch(queue.value.map((q) => ({ id: q.id, file_name: q.file_name, duration: q.duration, duplicate: q.duplicate })));
};

const postOne = (id: number) => {
    const v = props.videos.data.find((x) => x.id === id);
    const s = props.selectable.find((x) => x.id === id);

    openBatch([{ id, file_name: v?.file_name ?? s?.file_name ?? `#${id}`, duration: v?.duration ?? s?.duration ?? null, duplicate: v?.duplicate?.text ?? s?.duplicate ?? null }]);
};

const onBatchDone = () => {
    // Video đã hẹn giờ thì bỏ chọn.
    for (const it of batchItems.value) {
        delete picked.value[it.id];
    }
};

const viewFromQueue = (id: number) => {
    queueOpen.value = false;
    openViewer([id], id);
};

// Các bước: 1 chọn video, 2 chọn kênh / sản phẩm / caption, 3 xem trước lịch rồi hẹn.
const currentStep = computed<1 | 2 | 3>(() => {
    if (dialogOpen.value) {
        return batchStep.value === 'form' ? 2 : 3;
    }

    return pickedItems.value.length ? 2 : 1;
});

// ---------------------------------------------------------------- Lọc, thư mục, quét
const go = (patch: Partial<{ folder: number; status: string; day: string; page: number }>) => {
    const next = { ...props.filters, ...patch };
    const query: Record<string, string | number> = {};

    if (next.folder) {
        query.folder = next.folder;
    }

    if (next.status) {
        query.status = next.status;
    }

    if (next.day) {
        query.day = next.day;
    }

    if (patch.page) {
        query.page = patch.page;
    }

    lastIdx = -1;
    router.get('/auto/kho/rieng', query, {
        preserveScroll: true,
        preserveState: true,
    });
};

const opts = { preserveScroll: true, onFinish: () => (busy.value = '') };

const scan = () => {
    busy.value = 'scan';
    router.post('/auto/kho/rieng/quet', {}, opts);
};

const addFolder = () => {
    if (!folderPath.value.trim()) {
        return;
    }

    busy.value = 'add';
    router.post(
        '/auto/kho/rieng/thu-muc',
        { path: folderPath.value, name: folderName.value },
        {
            ...opts,
            onSuccess: () => {
                folderPath.value = '';
                folderName.value = '';
            },
        },
    );
};

const picking = ref(false);
const pickError = ref('');
const PICK_FAIL = 'Không mở được hộp chọn thư mục, hãy dán đường dẫn.';

// Mở hộp chọn thư mục gốc của Windows (qua launcher), điền đường dẫn vào ô.
const pickFolder = async () => {
    if (picking.value) {
        return;
    }

    picking.value = true;
    pickError.value = '';

    try {
        const r = await fetch('/auto/kho/rieng/chon-thu-muc', {
            method: 'POST',
            headers: { Accept: 'application/json', 'X-XSRF-TOKEN': xsrf() },
            credentials: 'same-origin',
        });
        const j = await r.json().catch(() => null);

        if (j?.ok && typeof j.path === 'string') {
            folderPath.value = j.path;

            if (!folderName.value.trim() && j.name) {
                folderName.value = j.name;
            }
        } else if (!j?.cancelled) {
            pickError.value = typeof j?.error === 'string' ? j.error : PICK_FAIL;
        }
    } catch {
        pickError.value = PICK_FAIL;
    } finally {
        picking.value = false;
    }
};

const removeFolder = (f: Folder) => {
    if (
        !window.confirm(
            `Bỏ thư mục "${f.name}" khỏi Kho riêng?\nFile video trong thư mục vẫn còn nguyên, app chỉ quên chúng.`,
        )
    ) {
        return;
    }

    router.delete(`/auto/kho/rieng/thu-muc/${f.id}`, { preserveScroll: true });
};

const retry = (v: RiengVideo) =>
    router.post(`/auto/videos/${v.id}/thu-lai`, {}, { preserveScroll: true });

const fmt = (iso: string | null) => (iso ? dayjs(iso).format('HH:mm DD/MM') : '—');

const statuses = [
    { key: '', label: 'Mọi trạng thái' },
    { key: 'chua', label: 'Chưa đăng' },
    { key: 'hen', label: 'Đã hẹn giờ' },
    { key: 'dang', label: 'Đã đăng' },
    { key: 'loi', label: 'Lỗi' },
];

// Thư mục đang xem (hoặc cả kho) chưa có video nào: giải thích định dạng nhận và việc tự cập nhật.
const nothingYet = computed(() => {
    if (!props.folders.length) {
        return false;
    }

    const f = props.filters.folder ? props.folders.find((x) => x.id === props.filters.folder) : null;

    return f ? f.count === 0 : (props.counts.all ?? 0) === 0;
});

// ---------------------------------------------------------------- Tự cập nhật (video mới hiện sau ~10 giây)
let pollTimer: ReturnType<typeof setInterval> | undefined;
let polling = false;
let lastSig = props.scan_sig;
let lastTotal = props.counts.all ?? 0;

watch(
    () => props.scan_sig,
    (s) => {
        lastSig = s;
    },
);
watch(
    () => props.counts.all,
    (n) => {
        lastTotal = n ?? 0;
    },
);

const poll = async () => {
    if (polling || drag || busy.value !== '' || document.visibilityState !== 'visible') {
        return;
    }

    polling = true;

    try {
        const j = await postJson<{ sig: string; total: number; new: number }>('/auto/kho/rieng/quet-nhanh');

        if (j && j.sig !== lastSig) {
            const added = Math.max(j.new ?? 0, (j.total ?? 0) - lastTotal);
            lastSig = j.sig;
            lastTotal = j.total ?? lastTotal;
            router.reload({ only: RELOAD_ONLY, preserveScroll: true, preserveState: true });

            if (added > 0) {
                toast.success(added === 1 ? 'Có 1 video mới' : `Có ${added} video mới`);
            }
        }
    } finally {
        polling = false;
    }
};

const onVisible = () => {
    if (document.visibilityState === 'visible') {
        void poll();
    }
};

onMounted(() => {
    pollTimer = setInterval(() => void poll(), 10000);
    document.addEventListener('visibilitychange', onVisible);
    grid.value?.addEventListener('touchmove', onTouchMove, { passive: false });

    // Khung xem video: nút "Đăng / hẹn giờ" và "Thêm vào giỏ chờ" của trang này.
    viewerActions.post = postOne;
    viewerActions.toggleQueue = (id) => void toggleQueue(id);
    viewerActions.isQueued = (id) => queuedIds.value.has(id);
});

onBeforeUnmount(() => {
    clearInterval(pollTimer);
    document.removeEventListener('visibilitychange', onVisible);
    grid.value?.removeEventListener('touchmove', onTouchMove);
    endDrag();
    viewerActions.post = null;
    viewerActions.toggleQueue = null;
    viewerActions.isQueued = null;
});

const barVisible = computed(() => pickedItems.value.length > 0 || selectMode.value);
</script>

<template>
    <AutoShell
        title="Kho riêng"
        :description="`Video bạn tự làm. Quét lần cuối ${fmt(last_scan_at)}. Video mới bỏ vào thư mục sẽ tự hiện sau khoảng 10 giây.`"
        testid="fork-rieng-page"
    >
        <template #actions>
            <Button size="sm" :disabled="busy === 'scan'" data-testid="fork-rieng-scan" @click="scan">
                <IconRefresh class="size-4" :class="{ 'animate-spin': busy === 'scan' }" />
                {{ busy === 'scan' ? 'Đang quét…' : 'Quét lại' }}
            </Button>
        </template>

        <KhoSwitch active="rieng" />

        <!-- Thư mục -->
        <section :class="cn(cardCls, 'flex flex-col gap-4 p-5')" data-testid="fork-rieng-folders">
            <SectionHeading
                :icon="IconFolder"
                tone="info"
                title="Thư mục video của bạn"
                :description="`App chỉ đọc video trong các thư mục này (${FORMATS}; kể cả thư mục con, trừ thư mục bắt đầu bằng _). App không bao giờ dời hay xoá file của bạn.`"
            />
            <ul v-if="folders.length" class="flex flex-col divide-y rounded-lg border">
                <li v-for="f in folders" :key="f.id" class="flex flex-wrap items-center gap-3 p-3 text-sm">
                    <IconFolder class="size-5 shrink-0 text-muted-foreground" />
                    <div class="min-w-0 flex-1">
                        <div class="font-medium">
                            {{ f.name }}
                            <span class="font-normal text-muted-foreground">· {{ f.count }} video</span>
                        </div>
                        <div class="truncate text-xs text-muted-foreground" :title="f.path">{{ f.path }}</div>
                        <div v-if="!f.exists" class="text-xs text-red-600 dark:text-red-400">Không mở được thư mục này (ổ đĩa đang tắt hoặc đã đổi tên?).</div>
                    </div>
                    <Button size="sm" variant="ghost" @click="removeFolder(f)">
                        <IconTrash class="size-4" /> Bỏ khỏi danh sách
                    </Button>
                </li>
            </ul>
            <div class="flex flex-wrap items-end gap-3">
                <label class="flex min-w-72 flex-1 flex-col gap-1 text-sm font-medium">
                    Chọn hoặc dán đường dẫn thư mục
                    <Input v-model="folderPath" placeholder="Ví dụ: D:\Video\Video-cua-toi" data-testid="fork-rieng-path" @keydown.enter="addFolder" />
                </label>
                <Button variant="outline" :disabled="picking" data-testid="fork-rieng-pick" @click="pickFolder">
                    <IconFolder class="size-4" :class="{ 'animate-pulse': picking }" />
                    {{ picking ? 'Đang chờ bạn chọn…' : 'Chọn thư mục…' }}
                </Button>
                <label class="flex w-56 flex-col gap-1 text-sm font-medium">
                    Tên gọi (tuỳ chọn)
                    <Input v-model="folderName" placeholder="Ví dụ: Video quay tay" />
                </label>
                <Button :disabled="busy === 'add' || !folderPath.trim()" data-testid="fork-rieng-add" @click="addFolder">
                    <IconFolderPlus class="size-4" /> Thêm thư mục
                </Button>
            </div>
            <p v-if="pickError" class="text-sm text-red-600 dark:text-red-400" data-testid="fork-rieng-pick-error">{{ pickError }}</p>
        </section>

        <RiengSteps v-if="folders.length" :current="currentStep" />

        <!-- Bộ lọc + chọn -->
        <section :class="cn(cardCls, 'sticky top-2 z-20 flex flex-wrap items-center gap-3 bg-card/95 p-4 backdrop-blur')" data-testid="fork-rieng-filters">
            <NativeSelect :model-value="filters.folder || ''" aria-label="Lọc theo thư mục" @update:model-value="go({ folder: Number($event) || 0 })">
                <option value="">Tất cả thư mục</option>
                <option v-for="f in folders" :key="f.id" :value="f.id">{{ f.name }}</option>
            </NativeSelect>
            <NativeSelect :model-value="filters.status" aria-label="Lọc theo trạng thái" data-testid="fork-rieng-status" @update:model-value="go({ status: String($event) })">
                <option v-for="s in statuses" :key="s.key" :value="s.key">
                    {{ s.label }}{{ s.key ? ` (${counts[s.key] ?? 0})` : ` (${counts.all ?? 0})` }}
                </option>
            </NativeSelect>
            <NativeSelect :model-value="filters.day" aria-label="Lọc theo ngày" data-testid="fork-rieng-day" @update:model-value="go({ day: String($event) })">
                <option value="">Tất cả ngày</option>
                <option v-for="d in days" :key="d" :value="d">{{ dayjs(d).format('DD/MM/YYYY') }}</option>
            </NativeSelect>

            <div class="ml-auto flex flex-wrap items-center gap-2">
                <Button
                    size="sm"
                    :variant="selectMode ? 'default' : 'outline'"
                    :aria-pressed="selectMode"
                    title="Bật để bấm vào video là chọn, hoặc kéo ngón tay / chuột qua nhiều video để chọn cả loạt"
                    data-testid="fork-rieng-select-mode"
                    @click="toggleSelectMode"
                >
                    <IconChecks class="size-4" /> {{ selectMode ? 'Đang chọn…' : 'Chọn' }}
                </Button>
                <label class="flex cursor-pointer items-center gap-2 text-sm">
                    <input
                        type="checkbox"
                        class="size-5 cursor-pointer accent-[var(--primary)]"
                        :checked="allSelected"
                        :disabled="!plain.length"
                        data-testid="fork-rieng-select-all"
                        @change="toggleAll"
                    />
                    Chọn tất cả ({{ plain.length }})
                    <span v-if="dupCount" class="text-xs text-muted-foreground" data-testid="fork-rieng-select-all-note">· bỏ qua {{ dupCount }} video trùng</span>
                </label>
            </div>
        </section>

        <!-- Khung chọn khi kéo -->
        <div
            v-if="band"
            class="pointer-events-none fixed z-50 rounded-sm border-2 border-primary bg-primary/15"
            :style="{ left: band.left + 'px', top: band.top + 'px', width: band.width + 'px', height: band.height + 'px' }"
            data-testid="fork-rieng-band"
        />

        <!-- Lưới video: bấm để mở, nhấn giữ chuột và kéo (hoặc nhấn giữ trên điện thoại) để quét chọn -->
        <section
            v-if="videos.data.length"
            ref="grid"
            class="grid grid-cols-2 gap-5 select-none md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 [-webkit-touch-callout:none]"
            :class="barVisible ? 'pb-28' : ''"
            data-testid="fork-rieng-grid"
            @pointerdown="onPointerDown"
            @dragstart="onDragStart"
            @contextmenu="onContextMenu"
        >
            <RiengCard
                v-for="v in videos.data"
                :key="v.id"
                :video="v"
                :selected="v.id in picked"
                :select-mode="selectMode"
                :holding="holdingId === v.id"
                :queued="queuedIds.has(v.id)"
                @open="onCardOpen(v)"
                @toggle="(shift: boolean) => onCardClick(v, shift)"
                @queue="toggleQueue(v.id)"
                @retry="retry(v)"
            />
        </section>

        <EmptyState
            v-else-if="nothingYet"
            :icon="IconVideoOff"
            title="Chưa có video nào trong thư mục này"
            :description="`App nhận video ${FORMATS} (kể cả thư mục con, trừ thư mục bắt đầu bằng _). Bỏ video vào thư mục, nó sẽ tự hiện ở đây trong khoảng 10 giây khi ghi xong, bạn không cần bấm gì.`"
            data-testid="fork-rieng-empty"
        />
        <EmptyState
            v-else
            :icon="IconVideoOff"
            :title="folders.length ? 'Không có video nào khớp bộ lọc' : 'Chưa có thư mục nào'"
            :description="folders.length ? 'Thử đổi bộ lọc, hoặc bấm Quét lại nếu vừa bỏ video mới vào thư mục.' : `Dán đường dẫn thư mục chứa video của bạn ở trên, app sẽ tự tìm các file ${FORMATS}.`"
        />

        <Callout v-if="accounts.length && !accounts.some((a) => a.usable)" tone="warn">
            Chưa có kênh nào sẵn sàng đăng hàng loạt: {{ accounts.map((a) => `${a.name} (${a.unusable_reason})`).join('; ') }}.
        </Callout>

        <div v-if="videos.last_page > 1" class="flex items-center justify-center gap-3 text-sm">
            <Button size="sm" variant="outline" :disabled="videos.current_page <= 1" @click="go({ page: videos.current_page - 1 })">Trước</Button>
            <span class="tabular-nums">Trang {{ videos.current_page }} / {{ videos.last_page }}</span>
            <Button size="sm" variant="outline" :disabled="videos.current_page >= videos.last_page" @click="go({ page: videos.current_page + 1 })">Sau</Button>
        </div>

        <!-- Nút nổi: Giỏ chờ đăng (không phải giỏ hàng TikTok Shop) -->
        <button
            type="button"
            :class="cn('fixed right-4 z-40 flex items-center gap-2 rounded-full border bg-card px-4 py-3 text-sm font-semibold shadow-lg transition hover:bg-muted', barVisible ? 'bottom-24' : 'bottom-5')"
            data-testid="fork-rieng-queue-btn"
            title="Giỏ chờ đăng: các video bạn để dành đăng sau"
            @click="queueOpen = true"
        >
            <IconClipboardList class="size-5" />
            Giỏ chờ đăng
            <span class="flex min-w-6 items-center justify-center rounded-full bg-primary px-1.5 py-0.5 text-xs text-primary-foreground tabular-nums" data-testid="fork-rieng-queue-count">{{ queue.length }}</span>
        </button>

        <!-- Thanh thao tác dính ở đáy: số video đã chọn + việc làm tiếp -->
        <div
            v-if="barVisible"
            class="fixed inset-x-3 bottom-3 z-40 mx-auto flex max-w-3xl flex-wrap items-center gap-2 rounded-2xl border bg-card/95 p-3 shadow-xl backdrop-blur"
            data-testid="fork-rieng-bar"
        >
            <div class="min-w-0 flex-1 text-sm">
                <template v-if="pickedItems.length">
                    <b class="tabular-nums" data-testid="fork-rieng-picked-count">Đã chọn {{ pickedItems.length }} video</b>
                    <span v-if="pickedDupCount" class="ml-1 text-amber-700 dark:text-amber-300">· {{ pickedDupCount }} video trùng</span>
                </template>
                <span v-else class="text-muted-foreground">Chạm hoặc kéo qua các video để chọn.</span>
            </div>
            <Button v-if="pickedItems.length" variant="ghost" size="sm" @click="clearPicked">
                <IconX class="size-4" /> Bỏ chọn
            </Button>
            <Button v-if="selectMode && !pickedItems.length" variant="outline" size="sm" @click="selectMode = false">Xong</Button>
            <Button v-if="pickedItems.length" variant="outline" data-testid="fork-rieng-to-queue" @click="pickedToQueue">
                <IconPlaylistAdd class="size-4" /> Thêm vào giỏ chờ
            </Button>
            <Button v-if="pickedItems.length" data-testid="fork-rieng-batch-btn" @click="postPicked">
                <IconSend class="size-4" /> Đăng / hẹn giờ ({{ pickedItems.length }})
            </Button>
        </div>

        <RiengQueueDialog
            v-model:open="queueOpen"
            :queue="queue"
            @remove="(id: number) => removeFromQueue([id])"
            @clear="clearQueue"
            @post="postQueue"
            @view="viewFromQueue"
        />

        <BatchDialog
            v-model:open="dialogOpen"
            :items="batchItems"
            :accounts="accounts"
            :limits="limits"
            :hashtag-suggestions="hashtag_suggestions ?? []"
            @step="batchStep = $event"
            @done="onBatchDone"
        />
    </AutoShell>
</template>

<style>
/* Đang kéo chọn: không bôi đen chữ, con trỏ hình chữ thập. */
html.rieng-dragging,
html.rieng-dragging * {
    cursor: crosshair !important;
    user-select: none !important;
}
</style>

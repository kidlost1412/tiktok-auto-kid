<script setup lang="ts">
// Kho riêng: video bạn tự làm. Thêm thư mục, chọn video (bấm, kéo, Shift) rồi đăng / hẹn giờ, hoặc cất vào "Giỏ chờ đăng".
// Trang tự cập nhật: video mới bỏ vào thư mục xuất hiện trong ~10 giây, không cần bấm gì.
import { router } from '@inertiajs/vue3';
import {
    IconChecks,
    IconClipboardList,
    IconDots,
    IconFolder,
    IconFolderPlus,
    IconPlus,
    IconPlaylistAdd,
    IconRefresh,
    IconSend,
    IconTrash,
    IconVideoOff,
    IconX,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import BatchDialog from '@/components/fork/kho/BatchDialog.vue';
import KhoSwitch from '@/components/fork/kho/KhoSwitch.vue';
import {
    type BatchItem,
    type Folder,
    postJson,
    type QueueItem,
    type RiengPageProps,
    type RiengVideo,
    xsrf,
} from '@/components/fork/kho/rieng';
import RiengCard from '@/components/fork/kho/RiengCard.vue';
import RiengQueueDialog from '@/components/fork/kho/RiengQueueDialog.vue';
import RiengSteps from '@/components/fork/kho/RiengSteps.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import { cardCls } from '@/components/fork/shared/status';
import {
    openVideo as openViewer,
    viewerActions,
} from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<RiengPageProps & { embedded?: boolean }>();

const emit = defineEmits<{
    filter: [q: { folder: number; status: string; day: string; page?: number }];
    refresh: [only: string[]];
    changed: [viec: 'quet' | 'xem'];
}>();

const RELOAD_ONLY = [
    'videos',
    'counts',
    'selectable',
    'days',
    'folders',
    'queue',
    'scan_sig',
    'last_scan_at',
];
const FORMATS = '.mp4, .mov, .m4v, .webm';

const busy = ref('');
const folderPath = ref('');
const folderName = ref('');
const dialogOpen = ref(false);
const batchStep = ref<'form' | 'preview' | 'result'>('form');
const batchItems = ref<BatchItem[]>([]);
const queueOpen = ref(false);
const folderDialog = ref(false);
const openMenu = ref<number | null>(null);

// ---------------------------------------------------------------- Chọn video
// Các video đã chọn (nhớ cả khi sang trang khác): id -> tên file + cờ trùng.
const picked = defineModel<
    Record<number, { file_name: string; duplicate: string | null }>
>('picked', { default: () => ({}) });
const selectMode = ref(false);

// Thời lượng (giây) của video đã chọn, để hộp thoại đăng hiện trên hình nhỏ.
const durationOf = (id: number): number | null =>
    props.selectable.find((x) => x.id === id)?.duration ??
    props.videos.data.find((x) => x.id === id)?.duration ??
    null;

const pickedItems = computed<BatchItem[]>(() =>
    Object.entries(picked.value).map(([id, p]) => ({
        id: Number(id),
        file_name: p.file_name,
        duration: durationOf(Number(id)),
        duplicate: p.duplicate,
    })),
);
const pickedDupCount = computed(
    () => pickedItems.value.filter((i) => i.duplicate).length,
);

// "Chọn tất cả" chỉ chọn video không trùng; video trùng phải tự chọn.
const plain = computed(() => props.selectable.filter((s) => !s.duplicate));
const dupCount = computed(() => props.selectable.length - plain.value.length);
const allSelected = computed(
    () =>
        plain.value.length > 0 &&
        plain.value.every((s) => s.id in picked.value),
);

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
let hold: {
    x: number;
    y: number;
    id: number;
    timer: ReturnType<typeof setTimeout>;
} | null = null;
let raf = 0;
let suppressClick = false;

/** Khung chọn đang vẽ (toạ độ màn hình, position: fixed). */
const band = ref<{
    left: number;
    top: number;
    width: number;
    height: number;
} | null>(null);
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

    for (const el of grid.value.querySelectorAll<HTMLElement>(
        '[data-card-id]',
    )) {
        const r = el.getBoundingClientRect();

        if (
            r.right < b.left ||
            r.left > b.left + b.width ||
            r.bottom < b.top ||
            r.top > b.top + b.height
        ) {
            continue;
        }

        const x = props.videos.data.find(
            (v) => v.id === Number(el.dataset.cardId),
        );

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
    const speed =
        top > 0
            ? -Math.min(28, 4 + top * 0.25)
            : bottom > 0
              ? Math.min(28, 4 + bottom * 0.25)
              : 0;

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
        const moved = Math.hypot(
            e.clientX - (drag.ax - window.scrollX),
            e.clientY - (drag.ay - window.scrollY),
        );

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

    if (
        e.pointerType === 'mouse' &&
        (e.button !== 0 || e.shiftKey || e.ctrlKey || e.metaKey || e.altKey)
    ) {
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

const onCardClick = (v: RiengVideo, shift: boolean) => {
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
        toast.success(
            n > 0
                ? `Đã cất ${n} video vào giỏ chờ đăng.`
                : 'Các video này đã có trong giỏ chờ đăng.',
        );
    }
};

const removeFromQueue = (ids: number[]) =>
    queueCall('/auto/kho/rieng/gio-cho/bo', { ids });

const toggleQueue = async (id: number) => {
    if (queuedIds.value.has(id)) {
        await removeFromQueue([id]);
    } else {
        await addToQueue([id]);
    }
};

const clearQueue = async () => {
    if (
        !window.confirm(
            'Xoá hết video khỏi giỏ chờ đăng? Video vẫn còn nguyên trong kho, chỉ bỏ khỏi giỏ.',
        )
    ) {
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
    openBatch(
        queue.value.map((q) => ({
            id: q.id,
            file_name: q.file_name,
            duration: q.duration,
            duplicate: q.duplicate,
        })),
    );
};

const postOne = (id: number) => {
    const v = props.videos.data.find((x) => x.id === id);
    const s = props.selectable.find((x) => x.id === id);

    openBatch([
        {
            id,
            file_name: v?.file_name ?? s?.file_name ?? `#${id}`,
            duration: v?.duration ?? s?.duration ?? null,
            duplicate: v?.duplicate?.text ?? s?.duplicate ?? null,
        },
    ]);
};

const onBatchDone = () => {
    // Video đã hẹn giờ thì bỏ chọn.
    for (const it of batchItems.value) {
        delete picked.value[it.id];
    }

    if (props.embedded) {
        emit('changed', 'xem');
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
const go = (
    patch: Partial<{
        folder: number;
        status: string;
        day: string;
        page: number;
    }>,
) => {
    const next = { ...props.filters, ...patch };

    if (props.embedded) {
        lastIdx = -1;
        emit('filter', {
            folder: next.folder,
            status: next.status,
            day: next.day,
            page: patch.page,
        });

        return;
    }

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

// Tuỳ chọn chung của mọi thao tác ghi. Embedded (bàn Thủ kho): ở yên trang đang mở và báo cho bàn sau khi xong.
const mk = (viec: 'quet' | 'xem', onSuccess?: () => void) => ({
    preserveScroll: true,
    ...(props.embedded ? { preserveState: true } : {}),
    onSuccess: () => {
        onSuccess?.();

        if (props.embedded) {
            emit('changed', viec);
        }
    },
    onFinish: () => (busy.value = ''),
});

const scan = () => {
    busy.value = 'scan';
    router.post('/auto/kho/rieng/quet', {}, mk('quet'));
};

const addFolder = () => {
    if (!folderPath.value.trim()) {
        return;
    }

    busy.value = 'add';
    router.post(
        '/auto/kho/rieng/thu-muc',
        { path: folderPath.value, name: folderName.value },
        mk('quet', () => {
            folderPath.value = '';
            folderName.value = '';
            folderDialog.value = false;
        }),
    );
};

const picking = ref(false);
const pickError = ref('');
const PICK_FAIL = 'Không mở được hộp chọn thư mục, hãy dán đường dẫn.';
const PICK_POLL_MS = 1000;
const PICK_MAX_MS = 11 * 60 * 1000;
let alive = true;

const sleep = (ms: number) =>
    new Promise<void>((resolve) => setTimeout(resolve, ms));

// Kết quả cuối của hộp chọn: điền ô đường dẫn / tên, hoặc báo lỗi (huỷ thì im lặng).
const applyPick = (
    j: {
        ok?: boolean;
        path?: unknown;
        name?: unknown;
        cancelled?: boolean;
        error?: unknown;
    } | null,
) => {
    if (j?.ok && typeof j.path === 'string') {
        folderPath.value = j.path;

        if (!folderName.value.trim() && typeof j.name === 'string' && j.name) {
            folderName.value = j.name;
        }
    } else if (!j?.cancelled) {
        pickError.value = typeof j?.error === 'string' ? j.error : PICK_FAIL;
    }
};

// Hộp chọn thư mục của Windows mở ở máy chủ và không chặn app: hỏi kết quả mỗi giây cho tới khi xong.
const waitPick = async (id: string) => {
    const started = Date.now();
    let fails = 0;

    while (alive && Date.now() - started < PICK_MAX_MS) {
        await sleep(PICK_POLL_MS);

        if (!alive) {
            return;
        }

        try {
            const r = await fetch('/auto/kho/rieng/chon-thu-muc/ket-qua', {
                method: 'POST',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-XSRF-TOKEN': xsrf(),
                },
                credentials: 'same-origin',
                body: JSON.stringify({ id }),
            });
            const j = await r.json().catch(() => null);

            if (j === null) {
                throw new Error('bad response');
            }

            fails = 0;

            if (j.pending) {
                continue;
            }

            applyPick(j);

            return;
        } catch {
            fails++;

            if (fails >= 3) {
                pickError.value = PICK_FAIL;

                return;
            }
        }
    }

    if (alive) {
        pickError.value = PICK_FAIL;
    }
};

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

        if (j?.ok && j.pending && typeof j.id === 'string') {
            await waitPick(j.id);
        } else {
            applyPick(j);
        }
    } catch {
        pickError.value = PICK_FAIL;
    } finally {
        picking.value = false;
    }
};

const removeFolder = (f: Folder) => {
    openMenu.value = null;

    if (
        !window.confirm(
            `Bỏ thư mục "${f.name}" khỏi Kho riêng?\nFile video trong thư mục vẫn còn nguyên, app chỉ quên chúng.`,
        )
    ) {
        return;
    }

    router.delete(`/auto/kho/rieng/thu-muc/${f.id}`, mk('quet'));
};

const retry = (v: RiengVideo) =>
    router.post(`/auto/videos/${v.id}/thu-lai`, {}, mk('xem'));

const fmt = (iso: string | null) =>
    iso ? dayjs(iso).format('HH:mm DD/MM') : '—';

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

    const f = props.filters.folder
        ? props.folders.find((x) => x.id === props.filters.folder)
        : null;

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
    if (
        polling ||
        drag ||
        busy.value !== '' ||
        document.visibilityState !== 'visible'
    ) {
        return;
    }

    polling = true;

    try {
        const j = await postJson<{ sig: string; total: number; new: number }>(
            '/auto/kho/rieng/quet-nhanh',
        );

        if (j && j.sig !== lastSig) {
            const added = Math.max(j.new ?? 0, (j.total ?? 0) - lastTotal);
            lastSig = j.sig;
            lastTotal = j.total ?? lastTotal;
            if (props.embedded) {
                emit('refresh', RELOAD_ONLY);
            } else {
                router.reload({
                    only: RELOAD_ONLY,
                    preserveScroll: true,
                    preserveState: true,
                });
            }

            if (added > 0) {
                toast.success(
                    added === 1 ? 'Có 1 video mới' : `Có ${added} video mới`,
                );
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
    alive = false;
    clearInterval(pollTimer);
    document.removeEventListener('visibilitychange', onVisible);
    grid.value?.removeEventListener('touchmove', onTouchMove);
    endDrag();
    viewerActions.post = null;
    viewerActions.toggleQueue = null;
    viewerActions.isQueued = null;
});

const barVisible = computed(
    () => pickedItems.value.length > 0 || selectMode.value,
);

// Trang thật đặt nút "Quét lại" ở đầu trang (qua ref); bàn Thủ kho có nút riêng ở đầu thân.
defineExpose({ scan, busy });
</script>

<template>
    <!-- Trang thật: "contents" để các khối nằm thẳng trong khung của trang; popup: cột dọc. -->
    <div :class="embedded ? 'flex flex-col gap-4' : 'contents'">
        <div v-if="embedded" class="flex items-center justify-between gap-3">
            <p class="min-w-0 truncate text-sm text-muted-foreground">
                Video bạn tự làm. Quét lần cuối {{ fmt(last_scan_at) }}. Video
                mới bỏ vào thư mục tự hiện sau khoảng 10 giây.
            </p>
            <Button
                size="sm"
                variant="outline"
                :disabled="busy === 'scan'"
                data-testid="fork-rieng-scan"
                @click="scan"
            >
                <IconRefresh
                    class="size-4"
                    :class="{ 'animate-spin': busy === 'scan' }"
                />
                {{ busy === 'scan' ? 'Đang quét…' : 'Quét lại' }}
            </Button>
        </div>

        <KhoSwitch v-if="!embedded" active="rieng" />

        <!-- Thư mục: một dải gọn, thêm thư mục trong hộp thoại -->
        <section
            :class="cn(cardCls, 'flex flex-wrap items-center gap-2 p-3')"
            data-testid="fork-rieng-folders"
        >
            <span
                class="flex items-center gap-1.5 pr-1 text-[0.8125rem] font-semibold text-muted-foreground"
                :title="`App chỉ đọc video trong các thư mục này (${FORMATS}; kể cả thư mục con, trừ thư mục bắt đầu bằng _). App không bao giờ dời hay xoá file của bạn.`"
            >
                <IconFolder class="size-4" /> Thư mục
            </span>
            <div
                v-for="f in folders"
                :key="f.id"
                class="flex max-w-72 items-center gap-1.5 rounded-lg border bg-background/60 py-1 pr-1 pl-2.5 text-sm"
                :title="f.path"
                :data-testid="`fork-rieng-folder-${f.id}`"
            >
                <span
                    v-if="!f.exists"
                    class="size-2 shrink-0 rounded-full bg-red-500"
                    title="Không mở được thư mục này (ổ đĩa đang tắt hoặc đã đổi tên?)"
                />
                <span class="truncate font-medium">{{ f.name }}</span>
                <span
                    class="shrink-0 text-xs text-muted-foreground tabular-nums"
                    >{{ f.count }} video</span
                >
                <Popover
                    :open="openMenu === f.id"
                    @update:open="(o: boolean) => (openMenu = o ? f.id : null)"
                >
                    <PopoverTrigger as-child>
                        <Button
                            size="icon"
                            variant="ghost"
                            class="size-7"
                            :aria-label="`Tuỳ chọn thư mục ${f.name}`"
                        >
                            <IconDots class="size-4" />
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent class="w-72 p-3" align="end">
                        <div
                            class="mb-2 text-xs break-all text-muted-foreground"
                        >
                            {{ f.path }}
                        </div>
                        <div
                            v-if="!f.exists"
                            class="mb-2 text-xs text-red-600 dark:text-red-400"
                        >
                            Không mở được thư mục này (ổ đĩa đang tắt hoặc đã
                            đổi tên?).
                        </div>
                        <Button
                            size="sm"
                            variant="ghost"
                            class="w-full justify-start"
                            @click="removeFolder(f)"
                        >
                            <IconTrash class="size-4" /> Bỏ khỏi danh sách
                        </Button>
                    </PopoverContent>
                </Popover>
            </div>
            <Button
                size="sm"
                variant="outline"
                data-testid="fork-rieng-add-open"
                @click="folderDialog = true"
            >
                <IconPlus class="size-4" /> Thêm thư mục
            </Button>
            <span v-if="!folders.length" class="text-sm text-muted-foreground"
                >Chưa có thư mục nào: thêm thư mục chứa video của bạn.</span
            >
        </section>

        <Dialog v-model:open="folderDialog">
            <DialogContent class="sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle>Thêm thư mục video</DialogTitle>
                    <DialogDescription>
                        App chỉ đọc video trong thư mục ({{ FORMATS }}; kể cả
                        thư mục con, trừ thư mục bắt đầu bằng _). App không bao
                        giờ dời hay xoá file của bạn.
                    </DialogDescription>
                </DialogHeader>
                <div class="flex flex-col gap-3">
                    <div class="flex items-end gap-2">
                        <label
                            class="flex min-w-0 flex-1 flex-col gap-1 text-sm font-medium"
                        >
                            Chọn hoặc dán đường dẫn thư mục
                            <Input
                                v-model="folderPath"
                                placeholder="Ví dụ: D:\Video\Video-cua-toi"
                                data-testid="fork-rieng-path"
                                @keydown.enter="addFolder"
                            />
                        </label>
                        <Button
                            variant="outline"
                            :disabled="picking"
                            data-testid="fork-rieng-pick"
                            @click="pickFolder"
                        >
                            <IconFolder
                                class="size-4"
                                :class="{ 'animate-pulse': picking }"
                            />
                            {{
                                picking
                                    ? 'Đang mở hộp chọn… (xem cửa sổ Windows)'
                                    : 'Chọn thư mục…'
                            }}
                        </Button>
                    </div>
                    <label class="flex flex-col gap-1 text-sm font-medium">
                        Tên gọi (tuỳ chọn)
                        <Input
                            v-model="folderName"
                            placeholder="Ví dụ: Video quay tay"
                        />
                    </label>
                    <p
                        v-if="pickError"
                        class="text-sm text-red-600 dark:text-red-400"
                        data-testid="fork-rieng-pick-error"
                    >
                        {{ pickError }}
                    </p>
                </div>
                <DialogFooter>
                    <Button variant="ghost" @click="folderDialog = false"
                        >Đóng</Button
                    >
                    <Button
                        :disabled="busy === 'add' || !folderPath.trim()"
                        data-testid="fork-rieng-add"
                        @click="addFolder"
                    >
                        <IconFolderPlus class="size-4" /> Thêm thư mục
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>

        <!-- Các bước + bộ lọc + chọn: gộp một thanh -->
        <section
            :class="
                cn(
                    cardCls,
                    'sticky top-2 z-20 flex flex-wrap items-center gap-x-4 gap-y-2 bg-card/95 p-3 backdrop-blur',
                )
            "
            data-testid="fork-rieng-filters"
        >
            <RiengSteps v-if="folders.length" :current="currentStep" />
            <div class="ml-auto flex flex-wrap items-center gap-2">
                <NativeSelect
                    :model-value="filters.folder || ''"
                    aria-label="Lọc theo thư mục"
                    @update:model-value="go({ folder: Number($event) || 0 })"
                >
                    <option value="">Tất cả thư mục</option>
                    <option v-for="f in folders" :key="f.id" :value="f.id">
                        {{ f.name }}
                    </option>
                </NativeSelect>
                <NativeSelect
                    :model-value="filters.status"
                    aria-label="Lọc theo trạng thái"
                    data-testid="fork-rieng-status"
                    @update:model-value="go({ status: String($event) })"
                >
                    <option v-for="s in statuses" :key="s.key" :value="s.key">
                        {{ s.label
                        }}{{
                            s.key
                                ? ` (${counts[s.key] ?? 0})`
                                : ` (${counts.all ?? 0})`
                        }}
                    </option>
                </NativeSelect>
                <NativeSelect
                    :model-value="filters.day"
                    aria-label="Lọc theo ngày"
                    data-testid="fork-rieng-day"
                    @update:model-value="go({ day: String($event) })"
                >
                    <option value="">Tất cả ngày</option>
                    <option v-for="d in days" :key="d" :value="d">
                        {{ dayjs(d).format('DD/MM/YYYY') }}
                    </option>
                </NativeSelect>
                <Button
                    size="sm"
                    :variant="selectMode ? 'default' : 'outline'"
                    :aria-pressed="selectMode"
                    title="Bật để bấm vào video là chọn, hoặc kéo ngón tay / chuột qua nhiều video để chọn cả loạt"
                    data-testid="fork-rieng-select-mode"
                    @click="toggleSelectMode"
                >
                    <IconChecks class="size-4" />
                    {{ selectMode ? 'Đang chọn…' : 'Chọn' }}
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
                    <span
                        v-if="dupCount"
                        class="text-xs text-muted-foreground"
                        data-testid="fork-rieng-select-all-note"
                        >· bỏ qua {{ dupCount }} video trùng</span
                    >
                </label>
            </div>
        </section>

        <!-- Khung chọn khi kéo -->
        <div
            v-if="band"
            class="pointer-events-none fixed z-50 rounded-sm border-2 border-primary bg-primary/15"
            :style="{
                left: band.left + 'px',
                top: band.top + 'px',
                width: band.width + 'px',
                height: band.height + 'px',
            }"
            data-testid="fork-rieng-band"
        />

        <!-- Lưới video: bấm để mở, nhấn giữ chuột và kéo (hoặc nhấn giữ trên điện thoại) để quét chọn -->
        <section
            v-if="videos.data.length"
            ref="grid"
            class="grid grid-cols-2 gap-4 select-none [-webkit-touch-callout:none] sm:grid-cols-[repeat(auto-fill,minmax(232px,1fr))]"
            :class="[
                barVisible && !embedded ? 'pb-28' : '',
                embedded ? 'gap-3! sm:grid-cols-5!' : '',
            ]"
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
            class="gap-2 py-6"
            :icon="IconVideoOff"
            title="Chưa có video nào trong thư mục này"
            :description="`App nhận video ${FORMATS} (kể cả thư mục con, trừ thư mục bắt đầu bằng _). Bỏ video vào thư mục, nó sẽ tự hiện ở đây trong khoảng 10 giây khi ghi xong, bạn không cần bấm gì.`"
            data-testid="fork-rieng-empty"
        />
        <EmptyState
            v-else
            class="gap-2 py-6"
            :icon="IconVideoOff"
            :title="
                folders.length
                    ? 'Không có video nào khớp bộ lọc'
                    : 'Chưa có thư mục nào'
            "
            :description="
                folders.length
                    ? 'Thử đổi bộ lọc, hoặc bấm Quét lại nếu vừa bỏ video mới vào thư mục.'
                    : `Bấm Thêm thư mục ở trên rồi dán đường dẫn thư mục chứa video của bạn, app sẽ tự tìm các file ${FORMATS}.`
            "
        />

        <Callout
            v-if="accounts.length && !accounts.some((a) => a.usable)"
            tone="warn"
        >
            Chưa có kênh nào sẵn sàng đăng hàng loạt:
            {{
                accounts
                    .map((a) => `${a.name} (${a.unusable_reason})`)
                    .join('; ')
            }}.
        </Callout>

        <div
            v-if="videos.last_page > 1"
            class="flex items-center justify-center gap-3 text-sm"
        >
            <Button
                size="sm"
                variant="outline"
                :disabled="videos.current_page <= 1"
                @click="go({ page: videos.current_page - 1 })"
                >Trước</Button
            >
            <span class="tabular-nums"
                >Trang {{ videos.current_page }} / {{ videos.last_page }}</span
            >
            <Button
                size="sm"
                variant="outline"
                :disabled="videos.current_page >= videos.last_page"
                @click="go({ page: videos.current_page + 1 })"
                >Sau</Button
            >
        </div>

        <!-- Nút nổi: Giỏ chờ đăng (không phải giỏ hàng TikTok Shop) -->
        <button
            type="button"
            :class="
                cn(
                    'flex items-center gap-2 rounded-full border bg-card px-4 py-3 text-sm font-semibold shadow-lg transition hover:bg-muted',
                    embedded
                        ? cn(
                              'sticky z-20 self-end',
                              barVisible ? 'bottom-20' : 'bottom-3',
                          )
                        : cn(
                              'fixed right-4 z-40',
                              barVisible ? 'bottom-24' : 'bottom-5',
                          ),
                )
            "
            data-testid="fork-rieng-queue-btn"
            title="Giỏ chờ đăng: các video bạn để dành đăng sau"
            @click="queueOpen = true"
        >
            <IconClipboardList class="size-5" />
            Giỏ chờ đăng
            <span
                class="flex min-w-6 items-center justify-center rounded-full bg-primary px-1.5 py-0.5 text-xs text-primary-foreground tabular-nums"
                data-testid="fork-rieng-queue-count"
                >{{ queue.length }}</span
            >
        </button>

        <!-- Thanh thao tác dính ở đáy: số video đã chọn + việc làm tiếp -->
        <div
            v-if="barVisible"
            :class="
                cn(
                    'flex flex-wrap items-center gap-2 rounded-2xl border bg-card/95 p-3 shadow-xl backdrop-blur',
                    embedded
                        ? 'sticky bottom-3 z-30 w-full'
                        : 'fixed inset-x-3 bottom-3 z-40 mx-auto max-w-3xl',
                )
            "
            data-testid="fork-rieng-bar"
        >
            <div class="min-w-0 flex-1 text-sm">
                <template v-if="pickedItems.length">
                    <b
                        class="tabular-nums"
                        data-testid="fork-rieng-picked-count"
                        >Đã chọn {{ pickedItems.length }} video</b
                    >
                    <span
                        v-if="pickedDupCount"
                        class="ml-1 text-amber-700 dark:text-amber-300"
                        >· {{ pickedDupCount }} video trùng</span
                    >
                </template>
                <span v-else class="text-muted-foreground"
                    >Chạm hoặc kéo qua các video để chọn.</span
                >
            </div>
            <Button
                v-if="pickedItems.length"
                variant="ghost"
                size="sm"
                @click="clearPicked"
            >
                <IconX class="size-4" /> Bỏ chọn
            </Button>
            <Button
                v-if="selectMode && !pickedItems.length"
                variant="outline"
                size="sm"
                @click="selectMode = false"
                >Xong</Button
            >
            <Button
                v-if="pickedItems.length"
                variant="outline"
                data-testid="fork-rieng-to-queue"
                @click="pickedToQueue"
            >
                <IconPlaylistAdd class="size-4" /> Thêm vào giỏ chờ
            </Button>
            <Button
                v-if="pickedItems.length"
                data-testid="fork-rieng-batch-btn"
                @click="postPicked"
            >
                <IconSend class="size-4" /> Đăng / hẹn giờ ({{
                    pickedItems.length
                }})
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
            :in-place="embedded"
            @step="batchStep = $event"
            @done="onBatchDone"
        />
    </div>
</template>

<style>
/* Đang kéo chọn: không bôi đen chữ, con trỏ hình chữ thập. */
html.rieng-dragging,
html.rieng-dragging * {
    cursor: crosshair !important;
    user-select: none !important;
}
</style>

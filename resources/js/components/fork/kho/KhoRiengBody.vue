<script setup lang="ts">
// Kho riêng: video anh tự làm. Thêm thư mục, chọn video (bấm, kéo, Shift) rồi đăng / hẹn giờ, hoặc cất vào "Giỏ chờ đăng".
// Trang tự cập nhật: video mới bỏ vào thư mục xuất hiện trong ~10 giây, không cần bấm gì.
import { router } from '@inertiajs/vue3';
import {
    IconChecks,
    IconClipboardList,
    IconDots,
    IconFolder,
    IconFolderOpen,
    IconFolderPlus,
    IconMusic,
    IconPencil,
    IconPlus,
    IconPlaylistAdd,
    IconRefresh,
    IconSearch,
    IconSend,
    IconArrowsShuffle,
    IconTrash,
    IconUpload,
    IconVideoOff,
    IconX,
} from '@tabler/icons-vue';
import { useDebounceFn } from '@vueuse/core';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import MixDialog from '@/components/fork/auto/MixDialog.vue';
import BatchDialog from '@/components/fork/kho/BatchDialog.vue';
import KhoPager from '@/components/fork/kho/KhoPager.vue';
import KhoSwitch from '@/components/fork/kho/KhoSwitch.vue';
import {
    type AutoPayload,
    type BatchItem,
    callJson,
    type Folder,
    postJson,
    type QueueItem,
    type RiengAuto,
    type RiengPageProps,
    type RiengVideo,
    type SelectAllResult,
    xsrf,
} from '@/components/fork/kho/rieng';
import RiengAiStatus from '@/components/fork/kho/RiengAiStatus.vue';
import RiengAutoDialog from '@/components/fork/kho/RiengAutoDialog.vue';
import RiengAutoEdit from '@/components/fork/kho/RiengAutoEdit.vue';
import RiengCard from '@/components/fork/kho/RiengCard.vue';
import RiengMusicDialog from '@/components/fork/kho/RiengMusicDialog.vue';
import RiengQueueDialog from '@/components/fork/kho/RiengQueueDialog.vue';
import RiengSteps from '@/components/fork/kho/RiengSteps.vue';
import RiengUploadDialog from '@/components/fork/kho/RiengUploadDialog.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import { cardCls } from '@/components/fork/shared/status';
import { useVisitLoading } from '@/components/fork/shared/useVisitLoading';
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
import { Skeleton } from '@/components/ui/skeleton';
import { confirm as confirmDialog } from '@/composables/useConfirm';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<RiengPageProps & { embedded?: boolean }>();

const emit = defineEmits<{
    filter: [
        q: {
            folder: number;
            status: string;
            day: string;
            page?: number;
            q?: string;
            sort?: string;
        },
    ];
    refresh: [only: string[]];
    changed: [viec: 'quet' | 'xem'];
}>();

const RELOAD_ONLY = [
    'videos',
    'counts',
    'selectable_count',
    'days',
    'folders',
    'subfolders',
    'queue',
    'scan_sig',
    'last_scan_at',
];
const FORMATS = '.mp4, .mov, .m4v, .webm';
const SELECT_MAX = 1000;
const { loading, callbacks } = useVisitLoading();
// Điểm neo đầu lưới: đổi trang / bộ lọc thì kéo về đây (mượt).
const gridTop = ref<HTMLElement | null>(null);
const rootEl = ref<HTMLElement | null>(null);

const busy = ref('');
const folderPath = ref('');
const folderName = ref('');
const dialogOpen = ref(false);
const batchStep = ref<'form' | 'preview' | 'result'>('form');
const batchItems = ref<BatchItem[]>([]);
const queueOpen = ref(false);
const folderDialog = ref(false);
const openMenu = ref<number | null>(null);
const renameVal = ref('');
const uploadOpen = ref(false);
const uploadFolder = ref<number | null>(null);
const musicOpen = ref(false);
const musicFolder = ref<Folder | null>(null);

const openMusic = (f: Folder) => {
    openMenu.value = null;
    musicFolder.value = f;
    musicOpen.value = true;
};

watch(openMenu, (id) => {
    const f = props.folders.find((x) => x.id === id);
    renameVal.value = f?.name ?? '';
});

// ---------------------------------------------------------------- Chọn video
// Các video đã chọn (nhớ cả khi sang trang khác): id -> tên file + cờ trùng.
const picked = defineModel<
    Record<number, { file_name: string; duplicate: string | null }>
>('picked', { default: () => ({}) });
const selectMode = ref(false);

// Thời lượng (giây) của video đã chọn, để hộp thoại đăng hiện trên hình nhỏ: lấy từ trang đang xem,
// từ danh sách "Chọn tất cả" đã tải, hoặc từ giỏ chờ đăng.
const knownDurations = new Map<number, number | null>();
const durationOf = (id: number): number | null =>
    props.videos.data.find((x) => x.id === id)?.duration ??
    knownDurations.get(id) ??
    queue.value.find((q) => q.id === id)?.duration ??
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

// "Chọn tất cả" chọn mọi video chưa đăng theo bộ lọc hiện tại (mọi trang, tối đa 1000); video trùng phải tự chọn.
// Danh sách chi tiết chỉ tải khi anh bấm (máy chủ tính cờ "trùng" cho từng video, khá nặng nên không tính mỗi lần tự cập nhật).
const selectableCount = computed(() => props.selectable_count ?? 0);
const capped = computed(() => selectableCount.value > SELECT_MAX);
const selectAllIds = ref<number[]>([]);
const selectAllSkipped = ref(0);
const selectingAll = ref(false);
const allSelected = computed(
    () =>
        selectAllIds.value.length > 0 &&
        selectAllIds.value.every((id) => id in picked.value),
);

// Video chọn được và không trùng ngay trên trang đang xem.
const pagePlain = computed(() =>
    props.videos.data.filter((v) => v.selectable && !v.duplicate),
);

// Đổi bộ lọc hoặc số lượng thì danh sách "Chọn tất cả" đã tải không còn đúng nữa.
watch(
    () => JSON.stringify([props.filters, props.selectable_count]),
    () => {
        selectAllIds.value = [];
        selectAllSkipped.value = 0;
    },
);

const dupOf = (v: RiengVideo): string | null => v.duplicate?.text ?? null;

// Luôn gán một object MỚI cho `picked`: khi trang không truyền v-model, defineModel giữ object thường (không reactive),
// sửa tại chỗ (picked.value[id] = …) thì giao diện không cập nhật — lỗi "bấm không tick được".
const setPicked = (fn: (next: typeof picked.value) => void) => {
    const next = { ...picked.value };
    fn(next);
    picked.value = next;
};

let lastIdx = -1;
const idxOf = (id: number) => props.videos.data.findIndex((x) => x.id === id);

// Bấm chọn / bỏ chọn; giữ Shift thì chọn cả đoạn từ video bấm trước đó. Video trùng vẫn chọn được (hộp đăng sẽ cảnh báo).
const toggle = (v: RiengVideo, shift = false) => {
    if (!v.selectable) {
        return;
    }

    const i = idxOf(v.id);
    const on = !(v.id in picked.value);
    const range =
        shift && lastIdx >= 0 && lastIdx !== i
            ? props.videos.data.slice(
                  Math.min(lastIdx, i),
                  Math.max(lastIdx, i) + 1,
              )
            : [v];

    setPicked((next) => {
        for (const x of range) {
            if (!x.selectable) {
                continue;
            }

            if (on) {
                next[x.id] = { file_name: x.file_name, duplicate: dupOf(x) };
            } else {
                delete next[x.id];
            }
        }
    });

    lastIdx = i;
};

const selectAllQuery = (): string => {
    const f = props.filters;
    const q = new URLSearchParams();

    if (f.folder) {
        q.set('folder', String(f.folder));
    }

    if (f.folder && f.sub) {
        q.set('sub', f.sub);
    }

    if (f.status) {
        q.set('status', f.status);
    }

    if (f.day) {
        q.set('day', f.day);
    }

    if (f.q) {
        q.set('q', f.q);
    }

    return q.toString();
};

// Ô "Chọn tất cả": để trình duyệt tự đổi dấu tick rồi đặt lại theo trạng thái thật sau khi chọn/bỏ chọn xong.
// (Dùng click.prevent thì trình duyệt trả dấu tick về như cũ SAU khi Vue đã cập nhật → bỏ chọn rồi mà ô vẫn tick.)
const onSelectAllChange = (e: Event) => {
    const el = e.target as HTMLInputElement;
    void toggleAll().finally(() => {
        el.checked = allSelected.value;
    });
};

const toggleAll = async () => {
    if (selectingAll.value) {
        return;
    }

    if (allSelected.value) {
        const ids = selectAllIds.value;

        setPicked((next) => {
            for (const id of ids) {
                delete next[id];
            }
        });

        return;
    }

    selectingAll.value = true;

    try {
        const r = await callJson<SelectAllResult>(
            'GET',
            `/auto/kho/rieng/chon-tat-ca?${selectAllQuery()}`,
        );

        if (!r.ok || !r.data) {
            toast.error('Chưa chọn được, anh thử lại');

            return;
        }

        const plain = r.data.items.filter((s) => !s.duplicate);
        selectAllIds.value = plain.map((s) => s.id);
        selectAllSkipped.value = r.data.items.length - plain.length;

        for (const s of r.data.items) {
            knownDurations.set(s.id, s.duration ?? null);
        }

        setPicked((next) => {
            for (const s of plain) {
                next[s.id] = { file_name: s.file_name, duplicate: null };
            }
        });

        if (!plain.length) {
            toast.info('Không có video nào để chọn');
        } else if (r.data.capped) {
            toast.info(
                `Chỉ chọn tối đa ${r.data.max} video một lần (còn ${r.data.total - r.data.items.length} video nữa, đăng xong anh chọn tiếp)`,
            );
        }
    } finally {
        selectingAll.value = false;
    }
};

// Chỉ chọn các video chưa đăng (không trùng) ngay trên trang đang xem.
const selectPage = () => {
    setPicked((next) => {
        for (const v of pagePlain.value) {
            next[v.id] = { file_name: v.file_name, duplicate: null };
        }
    });
};

const clearPicked = () => {
    picked.value = {};
    lastIdx = -1;
};
const hasPicked = () => Object.keys(picked.value).length > 0;

const toggleSelectMode = () => {
    selectMode.value = !selectMode.value;
};

// Phím tắt khi đang chọn: Ctrl/Cmd+A chọn tất cả, Esc bỏ chọn. Không chạy khi đang gõ chữ hoặc có hộp thoại mở.
const otherDialogOpen = () =>
    [
        ...document.querySelectorAll('[role="dialog"], [role="alertdialog"]'),
    ].some((d) => !rootEl.value || !d.contains(rootEl.value));

const onShortcut = (e: KeyboardEvent) => {
    if (drag || e.defaultPrevented || (!selectMode.value && !hasPicked())) {
        return;
    }

    const t = e.target as HTMLElement | null;

    if (
        t?.closest?.(
            'input, textarea, select, [contenteditable="true"], [contenteditable=""]',
        ) ||
        otherDialogOpen()
    ) {
        return;
    }

    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
        e.preventDefault();
        void toggleAll();
    } else if (e.key === 'Escape') {
        if (hasPicked()) {
            clearPicked();
        } else {
            selectMode.value = false;
        }
    }
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

const swallowClick = (e: MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
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

    // Vừa kéo xong: nuốt cú click đi kèm (mở video, bấm nút trên thẻ) để không làm gì ngoài ý muốn.
    if (wasActive) {
        suppressClick = true;
        window.addEventListener('click', swallowClick, true);
        setTimeout(() => {
            suppressClick = false;
            window.removeEventListener('click', swallowClick, true);
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

/**
 * Nơi được bắt đầu quét chọn: trên thẻ video (kể cả nút trên thẻ: kéo đi thì không bấm nút) hoặc khoảng trống
 * ngang hàng lưới (lề hai bên, khe giữa thẻ). Không bắt đầu trong ô nhập, link, hộp thoại hay thanh lọc.
 */
const canStartBand = (t: HTMLElement, e: PointerEvent): boolean => {
    const g = grid.value;

    if (
        !g ||
        t.closest(
            'input, select, textarea, a, [contenteditable], [role="dialog"], [data-no-band], header, nav',
        )
    ) {
        return false;
    }

    if (g.contains(t)) {
        return true;
    }

    if (t.closest('button, [role="button"], [role="menu"], [role="listbox"]')) {
        return false;
    }

    // Lề ngoài lưới: chỉ khi ngang hàng lưới (để không nhầm với phần trên/dưới trang).
    const r = g.getBoundingClientRect();

    return e.clientY >= r.top && e.clientY <= r.bottom;
};

const onPointerDown = (e: PointerEvent) => {
    const t = e.target as HTMLElement;
    const id = cardIdAt(t);

    if (!canStartBand(t, e)) {
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
        toast.error('Không cập nhật được giỏ chờ đăng, hãy thử lại');

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
                ? `Đã cất ${n} video vào giỏ chờ đăng`
                : 'Các video này đã có trong giỏ chờ đăng',
        );
    }
};

// Bỏ khỏi giỏ có "Hoàn tác" (đưa lại vào giỏ, nằm cuối giỏ).
const removeFromQueue = async (ids: number[]) => {
    const ok = await queueCall('/auto/kho/rieng/gio-cho/bo', { ids });

    if (ok) {
        toast('Đã bỏ khỏi giỏ chờ đăng', {
            action: {
                label: 'Hoàn tác',
                onClick: () =>
                    void queueCall('/auto/kho/rieng/gio-cho/them', { ids }),
            },
        });
    }

    return ok;
};

const toggleQueue = async (id: number) => {
    if (queuedIds.value.has(id)) {
        await removeFromQueue([id]);
    } else {
        await addToQueue([id]);
    }
};

const clearQueue = async () => {
    if (
        !(await confirmDialog({
            title: 'Xoá hết video khỏi giỏ chờ đăng?',
            description: 'Video vẫn còn nguyên trong kho, chỉ bỏ khỏi giỏ.',
            confirmText: 'Xoá khỏi giỏ',
            destructive: true,
        }))
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
    // Video mở từ khung xem nhưng không nằm trên trang này: lấy tên / cờ trùng từ giỏ chờ đăng hoặc danh sách đã chọn.
    const q = queue.value.find((x) => x.id === id);
    const chosen = picked.value[id];

    openBatch([
        {
            id,
            file_name:
                v?.file_name ?? q?.file_name ?? chosen?.file_name ?? `#${id}`,
            duration: v?.duration ?? durationOf(id),
            duplicate:
                v?.duplicate?.text ?? q?.duplicate ?? chosen?.duplicate ?? null,
        },
    ]);
};

const onBatchDone = () => {
    // Video đã hẹn giờ thì bỏ chọn.
    setPicked((next) => {
        for (const it of batchItems.value) {
            delete next[it.id];
        }
    });

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
type Patch = Partial<{
    folder: number;
    sub: string;
    status: string;
    day: string;
    page: number;
    q: string;
    sort: string;
}>;

// Đổi trang / bộ lọc: kéo về đầu lưới (mượt) để không bị kẹt ở cuối trang cũ.
const scrollToGrid = () => {
    const el = gridTop.value;

    if (el && el.getBoundingClientRect().top < 0) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
};

const go = (patch: Patch) => {
    const next = { ...props.filters, ...patch };

    // Đổi thư mục thì bỏ lọc thư mục con cũ.
    if (patch.folder !== undefined && patch.sub === undefined) {
        next.sub = '';
    }

    scrollToGrid();

    if (props.embedded) {
        lastIdx = -1;
        emit('filter', {
            folder: next.folder,
            status: next.status,
            day: next.day,
            page: patch.page,
            q: next.q,
            sort: next.sort,
        });

        return;
    }

    const query: Record<string, string | number> = {};

    if (next.folder) {
        query.folder = next.folder;
    }

    if (next.folder && next.sub) {
        query.sub = next.sub;
    }

    if (next.status) {
        query.status = next.status;
    }

    if (next.day) {
        query.day = next.day;
    }

    if (next.q) {
        query.q = next.q;
    }

    if (next.sort && next.sort !== 'moi') {
        query.sort = next.sort;
    }

    if (patch.page) {
        query.page = patch.page;
    }

    lastIdx = -1;
    router.get('/auto/kho/rieng', query, {
        preserveScroll: true,
        preserveState: true,
        onStart: callbacks.onStart,
        onFinish: callbacks.onFinish,
    });
};

// ----- Tìm theo tên file (chờ anh gõ xong mới tải) và sắp xếp. Bàn Thủ kho (embedded) chưa mang được hai bộ lọc này nên ẩn.
const search = ref(props.filters.q ?? '');
const runSearch = useDebounceFn((v: string) => go({ q: v.trim() }), 350);

watch(search, (v) => {
    if (v.trim() !== (props.filters.q ?? '')) {
        runSearch(v);
    }
});

const sort = computed(() => props.filters.sort ?? 'moi');
const sorts = [
    { key: 'moi', label: 'Mới nhất' },
    { key: 'cu', label: 'Cũ nhất' },
    { key: 'ten', label: 'Tên A→Z' },
    { key: 'sap-dang', label: 'Sắp đăng' },
];

const hasFilter = computed(
    () =>
        !!props.filters.folder ||
        !!props.filters.sub ||
        !!props.filters.status ||
        !!props.filters.day ||
        !!(props.filters.q ?? ''),
);

const clearFilters = () => {
    search.value = '';
    go({ folder: 0, sub: '', status: '', day: '', q: '' });
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

const renameFolder = async (f: Folder) => {
    const r = await callJson<{ ok: boolean; name: string }>(
        'PATCH',
        `/auto/kho/rieng/thu-muc/${f.id}`,
        { name: renameVal.value },
    );

    if (r.ok) {
        openMenu.value = null;
        toast.success(`Đã đổi tên thành "${r.data?.name ?? renameVal.value}"`);
        reloadVideos();
    } else {
        toast.error('Chưa đổi được tên, anh thử lại');
    }
};

const openFolderOnDisk = async (f: Folder) => {
    const r = await callJson<{ ok: boolean; error?: string }>(
        'POST',
        `/auto/kho/rieng/thu-muc/${f.id}/mo`,
    );

    if (r.ok) {
        openMenu.value = null;
    } else {
        toast.error(r.data?.error ?? 'Không mở được thư mục');
    }
};

const openUpload = (folderId: number | null) => {
    openMenu.value = null;
    uploadFolder.value = folderId;
    uploadOpen.value = true;
};

const removeFolder = async (f: Folder) => {
    openMenu.value = null;

    if (
        !(await confirmDialog({
            title: `Bỏ thư mục "${f.name}" khỏi Kho riêng?`,
            description:
                'File video trong thư mục vẫn còn nguyên, app chỉ quên chúng.',
            confirmText: 'Bỏ thư mục',
            destructive: true,
        }))
    ) {
        return;
    }

    router.delete(`/auto/kho/rieng/thu-muc/${f.id}`, mk('quet'));
};

// ---- Tự đăng theo khung (Kho riêng): hộp cài đặt + hộp chỉnh từng video.
const autoOpen = ref(false);
const mixOpen = ref(false);
const autoEditOpen = ref(false);
const autoVideo = ref<RiengVideo | null>(null);
const autoPayload = ref<AutoPayload | null>(null);
const autoEnabled = computed(
    () => autoPayload.value?.settings.enabled ?? false,
);

const loadAuto = async () => {
    const r = await callJson<AutoPayload>('GET', '/auto/kho/rieng/tu-dong');

    if (r.ok && r.data) {
        autoPayload.value = r.data;
    }
};

onMounted(loadAuto);

const reloadVideos = () => {
    if (props.embedded) {
        emit('refresh', RELOAD_ONLY);
    } else {
        router.reload({ only: RELOAD_ONLY });
    }
};

const onAutoChanged = (p: AutoPayload) => {
    autoPayload.value = p;
    reloadVideos();
};

const openAutoEdit = async (v: RiengVideo) => {
    autoVideo.value = v;

    if (!autoPayload.value) {
        await loadAuto();
    }

    autoEditOpen.value = true;
};

const onAutoSaved = (id: number, a: RiengAuto) => {
    const v = props.videos.data.find((x) => x.id === id);

    if (v) {
        v.auto = a;
    }

    reloadVideos();
};

// Thẻ "Mất file" (ổ rời chưa cắm...): anh bỏ hẳn video khỏi danh sách (sau khi xác nhận). File không bị đụng tới.
const forgetVideo = async (v: RiengVideo) => {
    if (
        !(await confirmDialog({
            title: 'Bỏ video này khỏi danh sách?',
            description:
                'Chỉ bỏ khỏi app, file trên ổ đĩa không bị xoá. Nếu file xuất hiện lại trong thư mục, app sẽ nhận lại như một video mới.',
            confirmText: 'Bỏ khỏi danh sách',
            destructive: true,
        }))
    ) {
        return;
    }

    busy.value = 'quet';
    router.delete(`/auto/kho/rieng/video/${v.id}`, mk('quet'));
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
// Chuyển tab qua lại liên tục (mỗi lần hiện lại đều quét): giữ cách nhau ít nhất 5 giây.
let lastPollAt = 0;
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
        document.visibilityState !== 'visible' ||
        Date.now() - lastPollAt < 5000
    ) {
        return;
    }

    polling = true;
    lastPollAt = Date.now();

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
                router.reload({ only: RELOAD_ONLY });
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
    // 20 giây: mỗi lượt có thể quét cả thư mục (nặng); tab ẩn thì bỏ qua, hiện lại thì quét ngay.
    pollTimer = setInterval(() => void poll(), 20000);
    document.addEventListener('visibilitychange', onVisible);
    document.addEventListener('keydown', onShortcut);
    // Quét chọn bắt đầu được cả ở lề ngoài lưới (khi thẻ phủ kín màn hình vẫn kéo được).
    document.addEventListener('pointerdown', onPointerDown);

    // Khung xem video: nút "Đăng / hẹn giờ" và "Thêm vào giỏ chờ" của trang này.
    viewerActions.post = postOne;
    viewerActions.toggleQueue = (id) => void toggleQueue(id);
    viewerActions.isQueued = (id) => queuedIds.value.has(id);
});

// Lưới được dựng lại khi chuyển giữa khung xương / video / trang trống: gắn lại bộ bắt cảm ứng mỗi lần.
watch(
    grid,
    (el, old) => {
        old?.removeEventListener('touchmove', onTouchMove);
        el?.addEventListener('touchmove', onTouchMove, { passive: false });
    },
    { flush: 'post' },
);

onBeforeUnmount(() => {
    alive = false;
    document.removeEventListener('keydown', onShortcut);
    clearInterval(pollTimer);
    document.removeEventListener('visibilitychange', onVisible);
    grid.value?.removeEventListener('touchmove', onTouchMove);
    document.removeEventListener('pointerdown', onPointerDown);
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
    <div ref="rootEl" :class="embedded ? 'flex flex-col gap-4' : 'contents'">
        <div v-if="embedded" class="flex items-center justify-between gap-3">
            <p class="min-w-0 truncate text-sm text-muted-foreground">
                Video anh tự làm. Quét lần cuối {{ fmt(last_scan_at) }}. Video
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
                class="flex items-center gap-1.5 pr-1 text-sm font-semibold text-muted-foreground"
                :title="`App chỉ đọc video trong các thư mục này (${FORMATS}; kể cả thư mục con, trừ thư mục bắt đầu bằng _). App không bao giờ dời hay xoá file của anh.`"
            >
                <IconFolder class="size-4" /> Thư mục
            </span>
            <!-- Bấm vào tên thư mục = lọc theo thư mục đó (bấm lần nữa để bỏ lọc); chỉ nút ba chấm mới mở tuỳ chọn. -->
            <button
                v-if="folders.length"
                type="button"
                :aria-pressed="!filters.folder"
                :class="
                    cn(
                        'flex items-center gap-1.5 rounded-lg border bg-background/60 px-3 py-1 text-sm transition hover:border-foreground/40 hover:bg-muted/60',
                        !filters.folder &&
                            'border-primary bg-primary-subtle',
                    )
                "
                data-testid="fork-rieng-folder-all"
                @click="go({ folder: 0 })"
            >
                <span class="font-medium">Tất cả</span>
                <span class="text-xs text-muted-foreground tabular-nums"
                    >{{ counts.all ?? 0 }} video</span
                >
            </button>
            <div
                v-for="f in folders"
                :key="f.id"
                :class="
                    cn(
                        'flex max-w-72 items-center rounded-lg border bg-background/60 transition hover:border-foreground/40',
                        filters.folder === f.id &&
                            'border-primary bg-primary-subtle',
                    )
                "
            >
                <button
                    type="button"
                    class="flex min-w-0 items-center gap-1.5 rounded-l-lg py-1 pr-1 pl-2.5 text-sm hover:bg-muted/60"
                    :aria-pressed="filters.folder === f.id"
                    :title="f.path"
                    :data-testid="`fork-rieng-folder-${f.id}`"
                    @click="go({ folder: filters.folder === f.id ? 0 : f.id })"
                >
                    <span
                        v-if="!f.exists"
                        class="size-2 shrink-0 rounded-full bg-destructive"
                        title="Không mở được thư mục này (ổ đĩa đang tắt hoặc đã đổi tên?)"
                    />
                    <span class="truncate font-medium">{{ f.name }}</span>
                    <IconMusic
                        v-if="f.music?.enabled"
                        class="size-3.5 shrink-0 text-muted-foreground"
                        aria-label="Đang ghép nhạc"
                    />
                    <span
                        class="shrink-0 text-xs text-muted-foreground tabular-nums"
                        >{{ f.count }} video</span
                    >
                </button>
                <Popover
                    :open="openMenu === f.id"
                    @update:open="(o: boolean) => (openMenu = o ? f.id : null)"
                >
                    <PopoverTrigger as-child>
                        <button
                            type="button"
                            class="flex items-center self-stretch rounded-r-lg px-1.5 text-foreground/60 hover:bg-muted/60 hover:text-foreground"
                            :aria-label="`Tuỳ chọn thư mục ${f.name}`"
                            :title="`Tuỳ chọn thư mục ${f.name}`"
                            :data-testid="`fork-rieng-folder-menu-${f.id}`"
                        >
                            <IconDots class="size-4 shrink-0" />
                        </button>
                    </PopoverTrigger>
                    <PopoverContent class="w-72 p-3" align="end">
                        <div
                            class="mb-2 text-xs break-all text-muted-foreground"
                        >
                            {{ f.path }}
                        </div>
                        <div
                            v-if="!f.exists"
                            class="mb-2 text-xs text-destructive-text"
                        >
                            Không mở được thư mục này (ổ đĩa đang tắt hoặc đã
                            đổi tên?).
                        </div>
                        <form
                            class="mb-2 flex gap-1.5"
                            @submit.prevent="renameFolder(f)"
                        >
                            <Input
                                v-model="renameVal"
                                class="h-8"
                                maxlength="80"
                                aria-label="Tên thư mục"
                                placeholder="Tên hiện trong app"
                            />
                            <Button
                                type="submit"
                                size="sm"
                                class="h-8 shrink-0"
                                :disabled="renameVal.trim() === f.name"
                            >
                                <IconPencil class="size-4" /> Đổi tên
                            </Button>
                        </form>
                        <Button
                            size="sm"
                            variant="ghost"
                            class="w-full justify-start"
                            :disabled="!f.exists"
                            @click="openUpload(f.id)"
                        >
                            <IconUpload class="size-4" /> Thêm video vào thư mục
                            này
                        </Button>
                        <Button
                            size="sm"
                            variant="ghost"
                            class="w-full justify-start"
                            :disabled="!f.exists"
                            @click="openFolderOnDisk(f)"
                        >
                            <IconFolderOpen class="size-4" /> Mở thư mục
                        </Button>
                        <Button
                            size="sm"
                            variant="ghost"
                            class="w-full justify-start"
                            :data-testid="`fork-rieng-folder-music-${f.id}`"
                            @click="openMusic(f)"
                        >
                            <IconMusic class="size-4" /> Ghép nhạc
                            <span
                                v-if="f.music?.enabled"
                                class="ml-auto text-xs text-success-text"
                                >{{
                                    f.music.mode === 'replace'
                                        ? 'Thay hẳn'
                                        : `Trộn ${f.music.gain_db} dB`
                                }}</span
                            >
                        </Button>
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
            <Button
                v-if="folders.length"
                size="sm"
                variant="outline"
                data-testid="fork-rieng-upload-open"
                @click="openUpload(null)"
            >
                <IconUpload class="size-4" /> Thêm video
            </Button>
            <!-- Cụm nút bên phải của dải thư mục. -->
            <div
                class="flex w-full flex-wrap items-center gap-2 border-t pt-3 xl:ml-auto xl:w-auto xl:border-t-0 xl:pt-0"
                data-testid="fork-rieng-header-actions"
            >
                <Button
                    v-if="accounts.some((a) => a.usable)"
                    size="sm"
                    variant="outline"
                    title="Đổi chỗ giờ các bài đã hẹn mà chưa gửi lên TikTok để hai bài liền nhau khác sản phẩm (có xem trước và hoàn tác)"
                    data-testid="fork-rieng-mix-open"
                    @click="mixOpen = true"
                >
                    <IconArrowsShuffle class="size-4" />
                    Trộn sản phẩm
                </Button>
                <Button
                    size="sm"
                    :variant="autoEnabled ? 'default' : 'outline'"
                    data-testid="fork-rieng-auto-open"
                    @click="autoOpen = true"
                >
                    Tự đăng theo khung: {{ autoEnabled ? 'Bật' : 'Tắt' }}
                </Button>
            </div>
            <span v-if="!folders.length" class="text-sm text-muted-foreground"
                >Chưa có thư mục nào: thêm thư mục chứa video của anh.</span
            >
        </section>

        <!-- Thư mục con của thư mục đang xem: lọc riêng từng thư mục con (chỉ hiện khi thư mục có thư mục con). -->
        <section
            v-if="
                !embedded &&
                filters.folder &&
                (subfolders ?? []).some((s) => s.dir !== '')
            "
            :class="cn(cardCls, 'flex flex-wrap items-center gap-2 p-3')"
            data-testid="fork-rieng-subfolders"
        >
            <span
                class="flex items-center gap-1.5 pr-1 text-sm font-semibold text-muted-foreground"
            >
                <IconFolder class="size-4" /> Thư mục con
            </span>
            <button
                v-for="s in [
                    {
                        key: '',
                        label: 'Tất cả',
                        count: (subfolders ?? []).reduce(
                            (n, x) => n + x.count,
                            0,
                        ),
                    },
                    ...(subfolders ?? []).map((x) => ({
                        key: x.dir === '' ? ':' : x.dir,
                        label:
                            x.dir === ''
                                ? 'Ngay thư mục gốc'
                                : x.dir.replaceAll('/', ' › '),
                        count: x.count,
                    })),
                ]"
                :key="s.key"
                type="button"
                :aria-pressed="(filters.sub ?? '') === s.key"
                :class="
                    cn(
                        'flex max-w-72 items-center gap-1.5 rounded-lg border bg-background/60 px-3 py-1 text-sm transition hover:border-foreground/40 hover:bg-muted/60',
                        (filters.sub ?? '') === s.key &&
                            'border-primary bg-primary-subtle',
                    )
                "
                :data-testid="`fork-rieng-sub-${s.key || 'all'}`"
                @click="go({ sub: s.key })"
            >
                <IconFolder
                    v-if="s.key && s.key !== ':'"
                    class="size-3.5 shrink-0 text-warning"
                />
                <span class="truncate font-medium">{{ s.label }}</span>
                <span
                    class="shrink-0 text-xs text-muted-foreground tabular-nums"
                    >{{ s.count }} video</span
                >
            </button>
        </section>

        <RiengAiStatus
            v-if="folders.length"
            @changed="reloadVideos"
            @settings="autoOpen = true"
        />

        <RiengUploadDialog
            v-model:open="uploadOpen"
            :folders="folders"
            :folder-id="uploadFolder"
            @done="reloadVideos"
        />

        <RiengMusicDialog
            v-model:open="musicOpen"
            :folder="musicFolder"
            @saved="reloadVideos"
        />

        <Dialog v-model:open="folderDialog">
            <DialogContent class="sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle>Thêm thư mục video</DialogTitle>
                    <DialogDescription>
                        App chỉ đọc video trong thư mục ({{ FORMATS }}; kể cả
                        thư mục con, trừ thư mục bắt đầu bằng _). App không bao
                        giờ dời hay xoá file của anh.
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
                        class="text-sm text-destructive-text"
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
        <!-- Dính trên cùng khi cuộn: chỉ từ màn hình lớn (màn nhỏ để cuộn theo trang cho đỡ chiếm chỗ). -->
        <section
            :class="
                cn(
                    cardCls,
                    'z-20 flex flex-wrap items-center gap-x-4 gap-y-2 bg-card/95 p-3 backdrop-blur',
                    embedded ? 'sticky top-2' : 'lg:sticky lg:top-2',
                )
            "
            data-testid="fork-rieng-filters"
            data-no-band
        >
            <RiengSteps v-if="folders.length" :current="currentStep" />
            <div class="ml-auto flex flex-wrap items-center gap-2">
                <div v-if="!embedded" class="relative">
                    <IconSearch
                        class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
                    />
                    <Input
                        v-model="search"
                        type="search"
                        placeholder="Tìm theo tên file…"
                        class="h-9 w-52 pl-9"
                        aria-label="Tìm video theo tên file"
                        data-testid="fork-rieng-search"
                    />
                </div>
                <NativeSelect
                    v-if="!embedded"
                    :model-value="sort"
                    aria-label="Sắp xếp"
                    data-testid="fork-rieng-sort"
                    @update:model-value="go({ sort: String($event) })"
                >
                    <option v-for="o in sorts" :key="o.key" :value="o.key">
                        {{ o.label }}
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
                <Button
                    v-if="hasFilter"
                    size="sm"
                    variant="ghost"
                    class="gap-1 text-muted-foreground"
                    data-testid="fork-rieng-clear-filters"
                    @click="clearFilters"
                >
                    <IconX class="size-3.5" /> Xoá bộ lọc
                </Button>
            </div>
            <div
                class="flex w-full flex-wrap items-center gap-x-3 gap-y-1 text-sm"
            >
                <label class="flex cursor-pointer items-center gap-2">
                    <input
                        type="checkbox"
                        class="size-5 cursor-pointer accent-[var(--primary)]"
                        :checked="allSelected"
                        :disabled="!selectableCount || selectingAll"
                        data-testid="fork-rieng-select-all"
                        @change="onSelectAllChange"
                    />
                    Chọn tất cả {{ selectableCount }} video chưa đăng (mọi
                    trang)
                </label>
                <button
                    v-if="pagePlain.length"
                    type="button"
                    class="text-primary underline-offset-2 hover:underline"
                    data-testid="fork-rieng-select-page"
                    @click="selectPage"
                >
                    Chọn {{ pagePlain.length }} video trong trang này
                </button>
                <span
                    v-if="selectAllSkipped"
                    class="text-xs text-muted-foreground"
                    data-testid="fork-rieng-select-all-note"
                    >· bỏ qua {{ selectAllSkipped }} video trùng (tự chọn nếu
                    muốn)</span
                >
                <span
                    v-if="capped"
                    class="text-xs text-warning"
                    data-testid="fork-rieng-select-cap"
                    >Chỉ chọn tối đa {{ SELECT_MAX }} video một lần</span
                >
            </div>
            <p
                v-if="selectMode"
                class="w-full text-xs text-muted-foreground"
                data-testid="fork-rieng-hint"
            >
                Mẹo: giữ Shift để chọn một dãy, kéo chuột để quét chọn, Ctrl+A
                chọn tất cả, Esc bỏ chọn.
            </p>
        </section>

        <!-- Khung chọn khi kéo -->
        <div
            v-if="band"
            class="pointer-events-none fixed z-50 rounded-sm border border-primary bg-primary/15"
            :style="{
                left: band.left + 'px',
                top: band.top + 'px',
                width: band.width + 'px',
                height: band.height + 'px',
            }"
            data-testid="fork-rieng-band"
        />

        <!-- Điểm neo đầu lưới + dòng "Trang X / Y · N video" -->
        <div
            v-if="videos.data.length || loading"
            ref="gridTop"
            class="scroll-mt-4 lg:scroll-mt-40"
        >
            <KhoPager
                v-if="videos.data.length"
                :page="videos.current_page"
                :last="videos.last_page"
                :total="videos.total"
                @go="(n: number) => go({ page: n })"
            />
        </div>

        <!-- Khung xương trong lúc tải trang / bộ lọc mới -->
        <div
            v-if="loading"
            class="grid grid-cols-2 gap-4 sm:grid-cols-[repeat(auto-fill,minmax(232px,1fr))]"
            data-testid="fork-rieng-skeleton"
        >
            <div v-for="i in 10" :key="i" class="flex flex-col gap-2">
                <Skeleton class="aspect-[9/16] w-full rounded-xl" />
                <Skeleton class="h-4 w-2/3" />
                <Skeleton class="h-3 w-full" />
            </div>
        </div>

        <!-- Lưới video: bấm để mở, nhấn giữ chuột và kéo (hoặc nhấn giữ trên điện thoại) để quét chọn -->
        <section
            v-else-if="videos.data.length"
            ref="grid"
            class="grid grid-cols-2 gap-4 select-none [-webkit-touch-callout:none] sm:grid-cols-[repeat(auto-fill,minmax(232px,1fr))]"
            :class="[
                barVisible && !embedded ? 'pb-28' : '',
                embedded ? 'gap-3! sm:grid-cols-5!' : '',
            ]"
            data-testid="fork-rieng-grid"
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
                @auto="openAutoEdit(v)"
                @forget="forgetVideo(v)"
            />
        </section>

        <EmptyState
            v-else-if="nothingYet"
            class="gap-2 py-6"
            :icon="IconVideoOff"
            title="Chưa có video nào trong thư mục này"
            :description="`App nhận video ${FORMATS} (kể cả thư mục con, trừ thư mục bắt đầu bằng _). Bỏ video vào thư mục, nó sẽ tự hiện ở đây trong khoảng 10 giây khi ghi xong, anh không cần bấm gì.`"
            data-testid="fork-rieng-empty"
        >
            <Button
                v-if="hasFilter"
                size="sm"
                variant="outline"
                @click="clearFilters"
            >
                <IconX class="size-4" /> Xoá bộ lọc
            </Button>
        </EmptyState>
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
                    : `Bấm Thêm thư mục rồi dán đường dẫn thư mục chứa video của anh, app sẽ tự tìm các file ${FORMATS}.`
            "
            :data-testid="
                folders.length ? 'fork-rieng-no-match' : 'fork-rieng-no-folder'
            "
        >
            <Button
                v-if="!folders.length"
                size="sm"
                data-testid="fork-rieng-empty-add"
                @click="folderDialog = true"
            >
                <IconFolderPlus class="size-4" /> Thêm thư mục
            </Button>
            <Button
                v-else-if="hasFilter"
                size="sm"
                variant="outline"
                data-testid="fork-rieng-empty-clear"
                @click="clearFilters"
            >
                <IconX class="size-4" /> Xoá bộ lọc
            </Button>
        </EmptyState>

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

        <KhoPager
            v-if="videos.last_page > 1 && !loading"
            :page="videos.current_page"
            :last="videos.last_page"
            :total="videos.total"
            @go="(n: number) => go({ page: n })"
        />

        <!-- Nút nổi: Giỏ chờ đăng (không phải giỏ hàng TikTok Shop) -->
        <button
            type="button"
            :class="
                cn(
                    'flex items-center gap-2 rounded-lg border bg-card px-4 py-3 text-sm font-semibold shadow-md transition hover:bg-muted',
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
            title="Giỏ chờ đăng: các video anh để dành đăng sau"
            @click="queueOpen = true"
        >
            <IconClipboardList class="size-5" />
            Giỏ chờ đăng
            <span
                class="flex min-w-6 items-center justify-center rounded-md bg-primary px-1.5 py-0.5 text-xs text-primary-foreground tabular-nums"
                data-testid="fork-rieng-queue-count"
                >{{ queue.length }}</span
            >
        </button>

        <!-- Thanh thao tác dính ở đáy: số video đã chọn + việc làm tiếp -->
        <div
            v-if="barVisible"
            :class="
                cn(
                    'flex flex-wrap items-center gap-2 rounded-xl border bg-card/95 p-3 shadow-xl backdrop-blur',
                    embedded
                        ? 'sticky bottom-3 z-30 w-full'
                        : 'fixed inset-x-3 bottom-3 z-40 mx-auto max-w-3xl',
                )
            "
            data-testid="fork-rieng-bar"
            data-no-band
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
                        class="ml-1 text-warning"
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

        <RiengAutoDialog v-model:open="autoOpen" @changed="onAutoChanged" />
        <RiengAutoEdit
            v-model:open="autoEditOpen"
            :video="autoVideo"
            :payload="autoPayload"
            @saved="onAutoSaved"
        />

        <MixDialog
            v-model:open="mixOpen"
            :accounts="
                accounts
                    .filter((a) => a.usable)
                    .map((a) => ({ id: a.id, display_name: a.name }))
            "
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

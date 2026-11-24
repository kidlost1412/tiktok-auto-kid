<script setup lang="ts">
// Thùng rác video: video anh đã xoá nằm đây 30 ngày, khôi phục được về kho. Xoá trong thùng rác là xoá hẳn
// (không khôi phục được nữa; file video gốc trên ổ đĩa vẫn còn).
import { router, usePage } from '@inertiajs/vue3';
import { IconRestore, IconTrash, IconTrashX } from '@tabler/icons-vue';
import { ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import { postJson } from '@/components/fork/auto/undo';
import CoverThumb from '@/components/fork/shared/CoverThumb.vue';
import SourceBadge from '@/components/fork/shared/SourceBadge.vue';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';

interface TrashItem {
    id: number;
    file_name: string;
    source: string | null;
    product_label: string | null;
    caption: string | null;
    trashed_at: string;
    days_left: number;
    file_ok: boolean;
}

const page = usePage();
const open = defineModel<boolean>('open', { default: false });

const items = ref<TrashItem[]>([]);
const days = ref(30);
const loading = ref(false);
const busyId = ref<number | 'all' | null>(null);
// Hỏi lại trước khi xoá hẳn: id đang chờ xác nhận, hoặc 'all' cho "Dọn sạch".
const confirming = ref<number | 'all' | null>(null);
const changed = ref(false);
// Tải không được thì báo lỗi + "Thử lại", không giả vờ là thùng rác trống.
const loadFailed = ref(false);
// Các video đang được tick để khôi phục một lượt.
const selected = ref<number[]>([]);
const restoringSel = ref(false);

async function load() {
    loading.value = true;
    loadFailed.value = false;

    try {
        const r = await fetch('/auto/thung-rac', {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });

        if (!r.ok) {
            throw new Error(String(r.status));
        }

        const data = (await r.json()) as { days: number; items: TrashItem[] };
        items.value = data.items;
        days.value = data.days;
        selected.value = [];
    } catch {
        loadFailed.value = true;
        items.value = [];
    } finally {
        loading.value = false;
    }
}

watch(open, (v) => {
    confirming.value = null;

    if (v) {
        changed.value = false;
        selected.value = [];
        void load();
    } else if (changed.value) {
        // Trang Tự động đăng: chỉ tải lại phần liên quan. Nơi khác (Kho, Kho riêng) tải lại cả trang để thấy video vừa khôi phục.
        router.reload(
            page.component === 'fork/Auto'
                ? { only: ['lich', 'stock', 'products'] }
                : {},
        );
    }
});

async function act(id: number | 'all', kind: 'restore' | 'purge') {
    busyId.value = id;
    const url =
        id === 'all'
            ? '/auto/thung-rac/don-sach'
            : `/auto/thung-rac/${id}/${kind === 'restore' ? 'khoi-phuc' : 'xoa'}`;
    const { ok, data } = await postJson(url);
    busyId.value = null;
    confirming.value = null;

    if (!ok) {
        toast.error(data?.message ?? 'Không làm được, hãy thử lại');

        return;
    }

    changed.value = true;
    toast.success(
        kind === 'restore'
            ? 'Đã khôi phục về kho'
            : (data?.message ?? 'Đã xong'),
    );
    items.value = id === 'all' ? [] : items.value.filter((i) => i.id !== id);
    selected.value = id === 'all' ? [] : selected.value.filter((x) => x !== id);
}

const toggleSel = (id: number) => {
    selected.value = selected.value.includes(id)
        ? selected.value.filter((x) => x !== id)
        : [...selected.value, id];
};

// Khôi phục các video đã tick, lần lượt từng cái.
async function restoreSelected() {
    const ids = [...selected.value];

    if (!ids.length || restoringSel.value) {
        return;
    }

    restoringSel.value = true;
    busyId.value = -1;
    let n = 0;
    let lastError: string | undefined;

    for (const id of ids) {
        const { ok, data } = await postJson(`/auto/thung-rac/${id}/khoi-phuc`);

        if (ok) {
            n++;
            changed.value = true;
            items.value = items.value.filter((i) => i.id !== id);
            selected.value = selected.value.filter((x) => x !== id);
        } else {
            lastError = data?.message;
        }
    }

    busyId.value = null;
    restoringSel.value = false;

    if (n === ids.length) {
        toast.success(`Đã khôi phục ${n} video về kho`);
    } else {
        toast.error(
            `Khôi phục được ${n}/${ids.length} video. ${lastError ?? 'Hãy thử lại.'}`,
        );
    }
}
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent class="sm:max-w-[640px]" data-testid="fork-auto-trash">
            <DialogHeader>
                <DialogTitle class="flex items-center gap-2"
                    ><IconTrash class="size-5 text-muted-foreground" />Thùng
                    rác</DialogTitle
                >
                <DialogDescription>
                    Khôi phục được trong {{ days }} ngày. Xoá ở đây là mất hẳn.
                </DialogDescription>
            </DialogHeader>

            <div
                v-if="loading && !items.length"
                class="flex justify-center py-10"
            >
                <Spinner class="size-5" />
            </div>
            <div
                v-else-if="loadFailed"
                class="flex flex-col items-center gap-3 py-10 text-center text-sm text-muted-foreground"
                data-testid="fork-auto-trash-error"
            >
                <p>Không tải được thùng rác</p>
                <Button
                    size="sm"
                    variant="outline"
                    data-testid="fork-auto-trash-retry"
                    @click="load"
                    >Thử lại</Button
                >
            </div>
            <p
                v-else-if="!items.length"
                class="py-10 text-center text-sm text-muted-foreground"
                data-testid="fork-auto-trash-empty"
            >
                Thùng rác trống
            </p>
            <ul
                v-else
                class="-mx-2 flex max-h-[60vh] flex-col gap-1 overflow-y-auto px-2"
            >
                <li
                    v-for="it in items"
                    :key="it.id"
                    class="grid grid-cols-[20px_32px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg border p-2"
                    :data-testid="`fork-auto-trash-item-${it.id}`"
                >
                    <input
                        type="checkbox"
                        class="size-4 cursor-pointer accent-primary"
                        :checked="selected.includes(it.id)"
                        :disabled="busyId !== null"
                        :aria-label="`Chọn ${it.product_label ?? it.file_name} để khôi phục`"
                        :data-testid="`fork-auto-trash-select-${it.id}`"
                        @change="toggleSel(it.id)"
                    />
                    <CoverThumb :id="it.id" class="h-14 w-8 rounded" />
                    <div class="min-w-0">
                        <div class="flex min-w-0 items-center gap-2">
                            <span class="truncate text-sm font-medium">{{
                                it.product_label ?? it.file_name
                            }}</span>
                            <SourceBadge :source="it.source" />
                        </div>
                        <p
                            class="truncate text-xs text-muted-foreground"
                            :title="it.caption ?? it.file_name"
                        >
                            {{ it.caption || it.file_name }}
                        </p>
                        <p class="text-xs text-muted-foreground">
                            Xoá lúc
                            {{ dayjs(it.trashed_at).format('HH:mm DD/MM') }} ·
                            còn {{ it.days_left }} ngày
                            <span v-if="!it.file_ok" class="text-warning">
                                · không thấy file trên ổ đĩa</span
                            >
                        </p>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <template v-if="confirming === it.id">
                            <Button
                                size="sm"
                                variant="destructive"
                                :disabled="busyId !== null"
                                :data-testid="`fork-auto-trash-purge-confirm-${it.id}`"
                                @click="act(it.id, 'purge')"
                            >
                                <Spinner
                                    v-if="busyId === it.id"
                                    class="size-4"
                                />
                                Xoá hẳn
                            </Button>
                            <Button
                                size="sm"
                                variant="ghost"
                                @click="confirming = null"
                                >Thôi</Button
                            >
                        </template>
                        <template v-else>
                            <Button
                                size="sm"
                                variant="outline"
                                :disabled="busyId !== null"
                                :data-testid="`fork-auto-trash-restore-${it.id}`"
                                @click="act(it.id, 'restore')"
                            >
                                <Spinner
                                    v-if="busyId === it.id"
                                    class="size-4"
                                />
                                <IconRestore v-else class="size-4" />
                                Khôi phục
                            </Button>
                            <Button
                                size="icon-sm"
                                variant="ghost"
                                class="text-muted-foreground hover:text-destructive-text"
                                title="Xoá hẳn (không khôi phục được)"
                                aria-label="Xoá hẳn"
                                :disabled="busyId !== null"
                                :data-testid="`fork-auto-trash-purge-${it.id}`"
                                @click="confirming = it.id"
                            >
                                <IconTrashX class="size-4" />
                            </Button>
                        </template>
                    </div>
                </li>
            </ul>

            <div
                v-if="items.length"
                class="flex flex-wrap items-center justify-between gap-2 border-t pt-3"
            >
                <span class="text-xs text-muted-foreground"
                    >{{ items.length }} video trong thùng rác</span
                >
                <div class="flex items-center gap-2">
                    <Button
                        v-if="selected.length"
                        size="sm"
                        variant="outline"
                        :disabled="busyId !== null"
                        data-testid="fork-auto-trash-restore-selected"
                        @click="restoreSelected"
                    >
                        <Spinner v-if="restoringSel" class="size-4" />
                        <IconRestore v-else class="size-4" />
                        Khôi phục đã chọn ({{ selected.length }})
                    </Button>
                    <template v-if="confirming === 'all'">
                        <span class="text-xs text-destructive-text"
                            >Xoá hẳn cả {{ items.length }} video, không lấy lại
                            được?</span
                        >
                        <Button
                            size="sm"
                            variant="destructive"
                            :disabled="busyId !== null"
                            data-testid="fork-auto-trash-empty-confirm"
                            @click="act('all', 'purge')"
                        >
                            <Spinner v-if="busyId === 'all'" class="size-4" />
                            Xoá hẳn tất cả
                        </Button>
                        <Button
                            size="sm"
                            variant="ghost"
                            @click="confirming = null"
                            >Thôi</Button
                        >
                    </template>
                    <Button
                        v-else
                        size="sm"
                        variant="outline"
                        class="text-destructive-text"
                        :disabled="busyId !== null"
                        data-testid="fork-auto-trash-empty-all"
                        @click="confirming = 'all'"
                    >
                        <IconTrashX class="size-4" /> Dọn sạch thùng rác
                    </Button>
                </div>
            </div>
        </DialogContent>
    </Dialog>
</template>

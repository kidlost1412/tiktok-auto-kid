<script setup lang="ts">
// Kho riêng: video bạn tự làm. Thêm thư mục, quét, chọn nhiều video rồi đăng hàng loạt (caption + giỏ hàng + hẹn giờ).
import { router } from '@inertiajs/vue3';
import {
    IconFolder,
    IconFolderPlus,
    IconMovie,
    IconRefresh,
    IconSend,
    IconTrash,
    IconVideoOff,
} from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import BatchDialog, { type BatchAccount } from '@/components/fork/kho/BatchDialog.vue';
import { fmtDuration } from '@/components/fork/kho/kho';
import KhoSwitch from '@/components/fork/kho/KhoSwitch.vue';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import { cardCls, toneClasses, type Tone } from '@/components/fork/shared/status';
import { openVideo as openViewer } from '@/components/fork/viewer';
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

interface RiengVideo {
    id: number;
    file_name: string;
    folder: string;
    rel_path: string | null;
    file_date: string | null;
    file_time: string | null;
    duration: number | null;
    status: string;
    gone: boolean;
    channel: string | null;
    scheduled_for: string | null;
    posted_at: string | null;
    tiktok_link: string | null;
    reason: string | null;
    can_retry: boolean;
    selectable: boolean;
    can_preview: boolean;
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
    selectable: { id: number; file_name: string }[];
    accounts: BatchAccount[];
    limits: { min_lead_minutes: number; gap_minutes: number; caption_max: number };
    last_scan_at: string | null;
}>();

const busy = ref('');
const folderPath = ref('');
const folderName = ref('');
const dialogOpen = ref(false);
// Các video đã chọn (nhớ cả khi sang trang khác): id -> tên file.
const picked = ref<Record<number, string>>({});

const pickedItems = computed(() =>
    Object.entries(picked.value).map(([id, file_name]) => ({
        id: Number(id),
        file_name,
    })),
);
const allSelected = computed(
    () =>
        props.selectable.length > 0 &&
        props.selectable.every((s) => s.id in picked.value),
);

const toggle = (v: RiengVideo) => {
    if (v.id in picked.value) {
        delete picked.value[v.id];
    } else if (v.selectable) {
        picked.value[v.id] = v.file_name;
    }
};

const toggleAll = () => {
    if (allSelected.value) {
        for (const s of props.selectable) {
            delete picked.value[s.id];
        }
    } else {
        for (const s of props.selectable) {
            picked.value[s.id] = s.file_name;
        }
    }
};

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
        const xsrf = decodeURIComponent(document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '');
        const r = await fetch('/auto/kho/rieng/chon-thu-muc', {
            method: 'POST',
            headers: { Accept: 'application/json', 'X-XSRF-TOKEN': xsrf },
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

const openVideo = (v: RiengVideo) =>
    openViewer(
        props.videos.data.map((x) => x.id),
        v.id,
    );

const fmt = (iso: string | null) => (iso ? dayjs(iso).format('HH:mm DD/MM') : '—');

const statusOf = (v: RiengVideo): { label: string; tone: Tone } => {
    if (v.gone && v.status === 'new') {
        return { label: 'Mất file', tone: 'warn' };
    }

    return (
        {
            new: { label: 'Chưa đăng', tone: 'neutral' as Tone },
            reserved: { label: 'Đã hẹn giờ', tone: 'info' as Tone },
            scheduled: { label: 'Đã hẹn giờ', tone: 'info' as Tone },
            posted: { label: 'Đã đăng', tone: 'success' as Tone },
            failed: { label: 'Lỗi', tone: 'danger' as Tone },
            skipped: { label: 'Bỏ qua', tone: 'warn' as Tone },
        }[v.status] ?? { label: v.status, tone: 'neutral' as Tone }
    );
};

const detail = (v: RiengVideo): string => {
    if (v.status === 'scheduled' || v.status === 'reserved') {
        return `${fmt(v.scheduled_for)}${v.channel ? ` · ${v.channel}` : ''}`;
    }

    if (v.status === 'posted') {
        return `${fmt(v.posted_at)}${v.channel ? ` · ${v.channel}` : ''}`;
    }

    return v.reason ?? '';
};

const statuses = [
    { key: '', label: 'Mọi trạng thái' },
    { key: 'chua', label: 'Chưa đăng' },
    { key: 'hen', label: 'Đã hẹn giờ' },
    { key: 'dang', label: 'Đã đăng' },
    { key: 'loi', label: 'Lỗi' },
];

const thumbFailed = ref<Record<number, boolean>>({});
</script>

<template>
    <AutoShell
        title="Kho riêng"
        :description="`Video bạn tự làm. Quét lần cuối ${fmt(last_scan_at)}.`"
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
                description="App chỉ đọc video trong các thư mục này (kể cả thư mục con, trừ thư mục bắt đầu bằng _). App không bao giờ dời hay xoá file của bạn."
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
                        <div v-if="!f.exists" class="text-xs text-red-600">Không mở được thư mục này (ổ đĩa đang tắt hoặc đã đổi tên?).</div>
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
            <p v-if="pickError" class="text-sm text-red-600" data-testid="fork-rieng-pick-error">{{ pickError }}</p>
        </section>

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

            <label class="ml-auto flex cursor-pointer items-center gap-2 text-sm">
                <input type="checkbox" :checked="allSelected" :disabled="!selectable.length" data-testid="fork-rieng-select-all" @change="toggleAll" />
                Chọn tất cả ({{ selectable.length }})
            </label>
            <Button :disabled="!pickedItems.length" data-testid="fork-rieng-batch-btn" @click="dialogOpen = true">
                <IconSend class="size-4" /> Đăng hàng loạt{{ pickedItems.length ? ` (${pickedItems.length})` : '' }}
            </Button>
            <Button v-if="pickedItems.length" variant="ghost" size="sm" @click="picked = {}">Bỏ chọn</Button>
        </section>

        <!-- Lưới video -->
        <section v-if="videos.data.length" class="grid grid-cols-2 gap-5 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6" data-testid="fork-rieng-grid">
            <div
                v-for="v in videos.data"
                :key="v.id"
                :class="cn('flex flex-col overflow-hidden rounded-[14px] border bg-card shadow-sm', v.id in picked && 'ring-2 ring-primary')"
                :data-testid="`fork-rieng-card-${v.id}`"
            >
                <div class="relative aspect-[9/16] w-full cursor-pointer overflow-hidden bg-muted" @click="openVideo(v)">
                    <img v-if="!thumbFailed[v.id] && !v.gone" :src="`/auto/kho/rieng/video/${v.id}/thumb`" :alt="v.file_name" loading="lazy" class="size-full object-cover" @error="thumbFailed[v.id] = true" />
                    <div v-else class="flex size-full flex-col items-center justify-center gap-2 text-muted-foreground">
                        <IconMovie class="size-10 opacity-50" />
                        <span class="text-xs">{{ v.gone ? 'Không còn file' : 'Chưa có ảnh xem trước' }}</span>
                    </div>
                    <span v-if="v.duration" class="absolute right-2 bottom-2 rounded bg-black/65 px-1.5 py-0.5 text-[0.75rem] font-medium text-white tabular-nums">{{ fmtDuration(v.duration) }}</span>
                    <span :class="cn('absolute top-2 left-2 rounded-full px-2.5 py-0.5 text-xs font-medium backdrop-blur', toneClasses[statusOf(v).tone].chip)">{{ statusOf(v).label }}</span>
                </div>
                <label v-if="v.selectable" class="flex cursor-pointer items-center gap-2 border-b px-3 py-2 text-xs" @click.stop>
                    <input type="checkbox" :checked="v.id in picked" :data-testid="`fork-rieng-check-${v.id}`" @change="toggle(v)" />
                    Chọn video này
                </label>
                <div class="flex flex-col gap-0.5 p-3 text-sm">
                    <div class="truncate font-medium" :title="v.file_name">{{ v.file_name }}</div>
                    <div class="truncate text-xs text-muted-foreground" :title="v.rel_path ?? ''">{{ v.folder }}</div>
                    <div class="text-xs text-muted-foreground">Làm lúc {{ v.file_time ? dayjs(v.file_time).format('HH:mm DD/MM/YYYY') : (v.file_date ?? '—') }}</div>
                    <div v-if="detail(v)" :class="cn('mt-1 text-xs', toneClasses[statusOf(v).tone].text)">{{ detail(v) }}</div>
                    <a v-if="v.tiktok_link" :href="v.tiktok_link" target="_blank" rel="noopener" class="text-xs text-primary underline">Mở trên TikTok</a>
                    <Button v-if="v.can_retry" size="sm" variant="outline" class="mt-1.5" @click="retry(v)">Thử lại</Button>
                </div>
            </div>
        </section>

        <EmptyState
            v-else
            :icon="IconVideoOff"
            :title="folders.length ? 'Không có video nào khớp bộ lọc' : 'Chưa có thư mục nào'"
            :description="folders.length ? 'Thử đổi bộ lọc, hoặc bấm Quét lại nếu vừa bỏ video mới vào thư mục.' : 'Dán đường dẫn thư mục chứa video của bạn ở trên, app sẽ tự tìm các file .mp4.'"
        />

        <Callout v-if="accounts.length && !accounts.some((a) => a.usable)" tone="warn">
            Chưa có kênh nào sẵn sàng đăng hàng loạt: {{ accounts.map((a) => `${a.name} (${a.unusable_reason})`).join('; ') }}.
        </Callout>

        <div v-if="videos.last_page > 1" class="flex items-center justify-center gap-3 text-sm">
            <Button size="sm" variant="outline" :disabled="videos.current_page <= 1" @click="go({ page: videos.current_page - 1 })">Trước</Button>
            <span class="tabular-nums">Trang {{ videos.current_page }} / {{ videos.last_page }}</span>
            <Button size="sm" variant="outline" :disabled="videos.current_page >= videos.last_page" @click="go({ page: videos.current_page + 1 })">Sau</Button>
        </div>

        <BatchDialog v-model:open="dialogOpen" :items="pickedItems" :accounts="accounts" :limits="limits" @done="picked = {}" />
    </AutoShell>
</template>

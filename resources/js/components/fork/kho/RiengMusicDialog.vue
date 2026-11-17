<script setup lang="ts">
// Hộp "Ghép nhạc" của một thư mục Kho riêng: mỗi video khi đăng được ghép ngẫu nhiên một bài trong thư mục nhạc.
// Thay hẳn = tắt tiếng gốc của video, chỉ còn nhạc. Trộn = giữ tiếng gốc, nhạc nhỏ đi theo mức dB chọn.
import { IconFolderOpen, IconMusic } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import {
    callJson,
    type Folder,
    type FolderMusic,
} from '@/components/fork/kho/rieng';
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
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

const props = defineProps<{ folder: Folder | null }>();
const open = defineModel<boolean>('open', { default: false });
const emit = defineEmits<{ saved: [] }>();

const DEFAULT: FolderMusic = {
    enabled: false,
    dir: null,
    mode: 'mix',
    gain_db: -12,
};

const form = ref<FolderMusic>({ ...DEFAULT });
const tracks = ref<number | null>(null);
const picking = ref(false);
const saving = ref(false);
const error = ref('');
let alive = true;

onBeforeUnmount(() => {
    alive = false;
});

const countTracks = async () => {
    tracks.value = null;
    error.value = '';

    if (!form.value.dir) {
        return;
    }

    const r = await callJson<{ tracks: number }>(
        'POST',
        '/auto/kho/rieng/nhac/dem',
        { dir: form.value.dir },
    );
    tracks.value = r.ok ? (r.data?.tracks ?? 0) : 0;
};

watch(open, (o) => {
    if (!o) {
        return;
    }

    form.value = { ...DEFAULT, ...(props.folder?.music ?? {}) };
    error.value = '';
    void countTracks();
});

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const pickDir = async () => {
    if (picking.value) {
        return;
    }

    picking.value = true;
    error.value = '';

    try {
        let r = await callJson<{
            ok?: boolean;
            pending?: boolean;
            id?: string;
            path?: string;
            cancelled?: boolean;
            error?: string;
        }>('POST', '/auto/kho/rieng/chon-thu-muc', { muc_dich: 'nhac' });
        const started = Date.now();

        while (alive && r.data?.pending && Date.now() - started < 11 * 60_000) {
            const id = r.data.id;
            await sleep(1000);

            if (id) {
                const next = await callJson<typeof r.data>(
                    'POST',
                    '/auto/kho/rieng/chon-thu-muc/ket-qua',
                    { id },
                );

                if (next.data === null) {
                    break;
                }

                r = { ok: next.ok, data: { ...next.data, id } };
            }
        }

        if (r.data?.ok && r.data.path) {
            form.value.dir = r.data.path;
            form.value.enabled = true;
            await countTracks();
        } else if (!r.data?.cancelled) {
            error.value =
                r.data?.error ?? 'Chưa mở được hộp chọn thư mục, anh thử lại.';
        }
    } finally {
        picking.value = false;
    }
};

const gainLabel = computed(() =>
    form.value.gain_db === 0
        ? 'Nhạc to bằng tiếng gốc'
        : `Nhạc nhỏ hơn ${-form.value.gain_db} dB`,
);

const save = async () => {
    if (!props.folder) {
        return;
    }

    saving.value = true;
    error.value = '';
    const r = await callJson<{ ok: boolean; error?: string; tracks?: number }>(
        'PATCH',
        `/auto/kho/rieng/thu-muc/${props.folder.id}/nhac`,
        form.value,
    );
    saving.value = false;

    if (r.ok && r.data?.ok) {
        open.value = false;
        toast.success(
            form.value.enabled
                ? `Đã bật ghép nhạc cho "${props.folder.name}" (${r.data.tracks ?? 0} bài).`
                : `Đã tắt ghép nhạc cho "${props.folder.name}".`,
        );
        emit('saved');
    } else {
        error.value = r.data?.error ?? 'Chưa lưu được, anh thử lại.';
    }
};
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent
            class="sm:max-w-md"
            data-testid="fork-rieng-music-dialog"
        >
            <DialogHeader>
                <DialogTitle class="flex items-center gap-2">
                    <IconMusic class="size-5" /> Ghép nhạc — {{ folder?.name }}
                </DialogTitle>
                <DialogDescription>
                    Mỗi video trong thư mục này khi đăng sẽ được ghép ngẫu nhiên
                    một bài trong thư mục nhạc (không lặp các bài vừa dùng).
                    File gốc của anh không bị sửa.
                </DialogDescription>
            </DialogHeader>

            <div class="flex flex-col gap-4">
                <label class="flex items-center justify-between gap-3">
                    <span class="text-sm font-medium">Bật ghép nhạc</span>
                    <Switch
                        v-model="form.enabled"
                        aria-label="Bật ghép nhạc"
                        data-testid="fork-rieng-music-enabled"
                    />
                </label>

                <div class="flex flex-col gap-1.5">
                    <span class="text-sm font-medium">Thư mục nhạc</span>
                    <div class="flex items-center gap-2">
                        <Input
                            :model-value="form.dir ?? ''"
                            class="h-8 min-w-0 flex-1"
                            placeholder="Bấm Chọn, hoặc dán đường dẫn thư mục nhạc"
                            aria-label="Thư mục nhạc"
                            :title="form.dir ?? ''"
                            data-testid="fork-rieng-music-dir"
                            @update:model-value="
                                (v: string | number) =>
                                    (form.dir = String(v).trim() || null)
                            "
                            @change="countTracks"
                        />
                        <Button
                            size="sm"
                            variant="outline"
                            :disabled="picking"
                            data-testid="fork-rieng-music-pick"
                            @click="pickDir"
                        >
                            <IconFolderOpen class="size-4" />
                            {{ picking ? 'Đang chờ chọn…' : 'Chọn' }}
                        </Button>
                    </div>
                    <span
                        v-if="form.dir && tracks !== null"
                        :class="
                            cn(
                                'text-xs',
                                tracks === 0
                                    ? 'text-red-600 dark:text-red-400'
                                    : 'text-muted-foreground',
                            )
                        "
                    >
                        {{
                            tracks === 0
                                ? 'Không thấy bài nhạc nào (mp3, m4a, wav, aac, ogg, flac).'
                                : `Có ${tracks} bài nhạc.`
                        }}
                    </span>
                </div>

                <div class="flex flex-col gap-2">
                    <span class="text-sm font-medium">Cách ghép</span>
                    <label class="flex items-start gap-2 text-sm">
                        <input
                            v-model="form.mode"
                            type="radio"
                            value="replace"
                            class="mt-1"
                            data-testid="fork-rieng-music-replace"
                        />
                        <span>
                            Thay hẳn tiếng gốc
                            <span class="block text-xs text-muted-foreground"
                                >Tắt hết tiếng của video, chỉ còn nhạc.</span
                            >
                        </span>
                    </label>
                    <label class="flex items-start gap-2 text-sm">
                        <input
                            v-model="form.mode"
                            type="radio"
                            value="mix"
                            class="mt-1"
                            data-testid="fork-rieng-music-mix"
                        />
                        <span>
                            Trộn với tiếng gốc
                            <span class="block text-xs text-muted-foreground"
                                >Giữ tiếng video, nhạc chạy nền nhỏ hơn.</span
                            >
                        </span>
                    </label>
                </div>

                <div v-if="form.mode === 'mix'" class="flex flex-col gap-1.5">
                    <div class="flex items-center justify-between text-sm">
                        <span class="font-medium">Âm lượng nhạc</span>
                        <span class="text-muted-foreground tabular-nums">{{
                            gainLabel
                        }}</span>
                    </div>
                    <input
                        v-model.number="form.gain_db"
                        type="range"
                        min="-30"
                        max="0"
                        step="1"
                        class="w-full accent-violet-600"
                        aria-label="Mức giảm âm lượng nhạc (dB)"
                        data-testid="fork-rieng-music-gain"
                    />
                    <span class="text-xs text-muted-foreground"
                        >Gợi ý: -12 dB nghe nền vừa phải; -18 dB khi video có
                        lời nói.</span
                    >
                </div>

                <p v-if="error" class="text-sm text-red-600 dark:text-red-400">
                    {{ error }}
                </p>
            </div>

            <DialogFooter>
                <Button variant="ghost" @click="open = false">Huỷ</Button>
                <Button
                    :disabled="saving"
                    data-testid="fork-rieng-music-save"
                    @click="save"
                    >Lưu</Button
                >
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

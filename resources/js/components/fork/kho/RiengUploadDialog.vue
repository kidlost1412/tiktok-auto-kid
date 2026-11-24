<script setup lang="ts">
// Thêm video vào một thư mục Kho riêng: chọn thư mục, kéo thả hoặc chọn file; app chép file vào thư mục rồi tự nhận.
import { IconCheck, IconLoader2, IconUpload, IconX } from '@tabler/icons-vue';
import { computed, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import { type Folder, xsrf } from '@/components/fork/kho/rieng';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { NativeSelect } from '@/components/ui/native-select';
import { cn } from '@/lib/utils';

const props = defineProps<{ folders: Folder[]; folderId: number | null }>();
const open = defineModel<boolean>('open', { default: false });
const emit = defineEmits<{ done: [] }>();

const EXT = ['mp4', 'mov', 'm4v', 'webm'];

interface Item {
    file: File;
    state: 'wait' | 'up' | 'ok' | 'err';
    pct: number;
    note: string;
}

const target = ref<string>('');
const items = ref<Item[]>([]);
const over = ref(false);
const running = ref(false);
const picker = ref<HTMLInputElement | null>(null);

watch(open, (o) => {
    if (o) {
        target.value = String(
            props.folderId ??
                props.folders.find((f) => f.exists)?.id ??
                props.folders[0]?.id ??
                '',
        );

        if (!running.value) {
            items.value = [];
        }
    }
});

const folderSel = computed({
    get: () => target.value,
    set: (v: string) => (target.value = v),
});

const fmtSize = (b: number) =>
    b >= 1024 ** 3
        ? `${(b / 1024 ** 3).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} GB`
        : `${Math.max(1, Math.round(b / 1024 ** 2))} MB`;

const add = (files: FileList | File[] | null) => {
    let skipped = 0;

    for (const f of Array.from(files ?? [])) {
        const ext = f.name.split('.').pop()?.toLowerCase() ?? '';

        if (!EXT.includes(ext)) {
            skipped++;
            continue;
        }

        if (
            !items.value.some(
                (i) => i.file.name === f.name && i.file.size === f.size,
            )
        ) {
            items.value.push({ file: f, state: 'wait', pct: 0, note: '' });
        }
    }

    if (skipped) {
        toast.error(
            `Bỏ qua ${skipped} file không phải video (.mp4, .mov, .m4v, .webm)`,
        );
    }
};

const onDrop = (e: DragEvent) => {
    over.value = false;
    add(e.dataTransfer?.files ?? null);
};

const onPick = (e: Event) => {
    const input = e.target as HTMLInputElement;
    add(input.files);
    input.value = '';
};

const remove = (i: Item) => {
    items.value = items.value.filter((x) => x !== i);
};

const sendOne = (it: Item, folderId: string) =>
    new Promise<void>((resolve) => {
        const xhr = new XMLHttpRequest();
        const body = new FormData();
        body.append('file', it.file);
        it.state = 'up';
        it.pct = 0;
        xhr.open('POST', `/auto/kho/rieng/thu-muc/${folderId}/video`);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.setRequestHeader('X-XSRF-TOKEN', xsrf());
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                it.pct = Math.round((e.loaded / e.total) * 100);
            }
        };
        xhr.onload = () => {
            let data: {
                ok?: boolean;
                name?: string;
                error?: string;
                message?: string;
            } = {};

            try {
                data = JSON.parse(xhr.responseText);
            } catch {
                // để trống
            }

            if (xhr.status >= 200 && xhr.status < 300 && data.ok) {
                it.state = 'ok';
                it.pct = 100;
                it.note =
                    data.name && data.name !== it.file.name
                        ? `lưu tên ${data.name}`
                        : '';
            } else {
                it.state = 'err';
                it.note = data.error ?? data.message ?? `Lỗi ${xhr.status}`;
            }

            resolve();
        };
        xhr.onerror = () => {
            it.state = 'err';
            it.note = 'Mất kết nối với app';
            resolve();
        };
        xhr.send(body);
    });

const start = async () => {
    const folderId = target.value;

    if (!folderId || running.value) {
        return;
    }

    running.value = true;

    for (const it of items.value) {
        if (it.state === 'wait' || it.state === 'err') {
            await sendOne(it, folderId);
        }
    }

    running.value = false;
    const ok = items.value.filter((i) => i.state === 'ok').length;
    const bad = items.value.filter((i) => i.state === 'err').length;

    if (ok) {
        toast.success(`Đã thêm ${ok} video vào thư mục`);
        emit('done');
    }

    if (!bad && ok) {
        open.value = false;
    }
};

const waiting = computed(
    () =>
        items.value.filter((i) => i.state === 'wait' || i.state === 'err')
            .length,
);
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent
            class="max-h-[90dvh] overflow-x-hidden overflow-y-auto sm:max-w-xl"
            data-testid="fork-rieng-upload"
        >
            <DialogHeader>
                <DialogTitle>Thêm video vào thư mục</DialogTitle>
                <DialogDescription class="text-sm text-foreground/70">
                    App chép video vào thư mục anh chọn (file gốc vẫn còn
                    nguyên) rồi tự hiện trong Kho riêng.
                </DialogDescription>
            </DialogHeader>

            <div class="flex min-w-0 flex-col gap-3 text-sm">
                <label class="flex flex-col gap-1.5">
                    <span class="font-medium">Thư mục</span>
                    <NativeSelect
                        v-model="folderSel"
                        class="w-full"
                        aria-label="Thư mục nhận video"
                        :disabled="running"
                    >
                        <option
                            v-for="f in folders"
                            :key="f.id"
                            :value="String(f.id)"
                            :disabled="!f.exists"
                        >
                            {{ f.name }} — {{ f.path
                            }}{{ f.exists ? '' : ' (không mở được)' }}
                        </option>
                    </NativeSelect>
                </label>

                <button
                    type="button"
                    :class="
                        cn(
                            'flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center transition',
                            over
                                ? 'border-primary bg-primary-subtle'
                                : 'border-foreground/25 hover:border-foreground/50 hover:bg-muted/50',
                        )
                    "
                    :disabled="running"
                    data-testid="fork-rieng-upload-drop"
                    @click="picker?.click()"
                    @dragover.prevent="over = true"
                    @dragleave="over = false"
                    @drop.prevent="onDrop"
                >
                    <IconUpload class="size-7 text-foreground/60" />
                    <span class="font-semibold"
                        >Kéo thả video vào đây, hoặc bấm để chọn file</span
                    >
                    <span class="text-sm text-foreground/70"
                        >.mp4, .mov, .m4v, .webm · chọn được nhiều file</span
                    >
                </button>
                <input
                    ref="picker"
                    type="file"
                    multiple
                    accept=".mp4,.mov,.m4v,.webm,video/*"
                    class="hidden"
                    @change="onPick"
                />

                <ul
                    v-if="items.length"
                    class="flex flex-col divide-y rounded-xl border"
                >
                    <li
                        v-for="(it, i) in items"
                        :key="i"
                        class="flex items-center gap-3 px-3 py-2"
                    >
                        <div class="min-w-0 flex-1">
                            <div class="truncate font-medium">
                                {{ it.file.name }}
                            </div>
                            <div
                                :class="
                                    cn(
                                        'text-xs',
                                        it.state === 'err'
                                            ? 'text-destructive-text'
                                            : 'text-foreground/70',
                                    )
                                "
                            >
                                {{ fmtSize(it.file.size) }}
                                <template v-if="it.state === 'up'">
                                    · đang chép {{ it.pct }}%</template
                                >
                                <template v-else-if="it.note">
                                    · {{ it.note }}</template
                                >
                            </div>
                            <div
                                v-if="it.state === 'up'"
                                class="mt-1 h-1.5 overflow-hidden rounded-full bg-muted"
                            >
                                <div
                                    class="h-full bg-primary transition-all"
                                    :style="{ width: it.pct + '%' }"
                                />
                            </div>
                        </div>
                        <IconLoader2
                            v-if="it.state === 'up'"
                            class="size-4 shrink-0 animate-spin"
                        />
                        <IconCheck
                            v-else-if="it.state === 'ok'"
                            class="size-5 shrink-0 text-success-text"
                        />
                        <Button
                            v-else-if="!running"
                            size="icon"
                            variant="ghost"
                            class="size-7 shrink-0"
                            :aria-label="`Bỏ ${it.file.name}`"
                            @click="remove(it)"
                        >
                            <IconX class="size-4" />
                        </Button>
                    </li>
                </ul>
            </div>

            <DialogFooter>
                <Button
                    variant="ghost"
                    :disabled="running"
                    @click="open = false"
                    >Đóng</Button
                >
                <Button
                    :disabled="!waiting || !target || running"
                    data-testid="fork-rieng-upload-start"
                    @click="start"
                >
                    <IconLoader2 v-if="running" class="size-4 animate-spin" />
                    <IconUpload v-else class="size-4" />
                    {{
                        running
                            ? 'Đang thêm…'
                            : `Thêm ${waiting || ''} video`.replace('  ', ' ')
                    }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

<script setup lang="ts">
// Mục "Nhạc" ở bước 2 của hộp Đăng hàng loạt: không ghép, hoặc bốc ngẫu nhiên từ một thư mục nhạc (trộn / thay hẳn + âm lượng).
import { IconFolderOpen } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref } from 'vue';

import { pickMusicDir, type BatchMusicCfg } from '@/components/fork/kho/music';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

defineProps<{ count: number | null }>();
const model = defineModel<BatchMusicCfg>({ required: true });
const emit = defineEmits<{ dir: [] }>();

const picking = ref(false);
const error = ref('');
let alive = true;

onBeforeUnmount(() => {
    alive = false;
});

const patch = (p: Partial<BatchMusicCfg>) => {
    model.value = { ...model.value, ...p };
};

const pick = async () => {
    picking.value = true;
    error.value = '';
    const r = await pickMusicDir(() => alive);
    picking.value = false;

    if (r.path) {
        patch({ dir: r.path });
        emit('dir');
    } else if (r.error) {
        error.value = r.error;
    }
};

const gainLabel = computed(() =>
    model.value.gain_db === 0
        ? 'Nhạc to bằng tiếng gốc'
        : `Nhạc nhỏ hơn ${-model.value.gain_db} dB`,
);
</script>

<template>
    <div class="flex flex-col gap-2" data-testid="fork-rieng-music">
        <span class="text-sm font-medium">Nhạc</span>
        <label class="flex items-center gap-2 text-sm">
            <input
                type="radio"
                :checked="model.kind === 'none'"
                data-testid="fork-rieng-music-none"
                @change="patch({ kind: 'none' })"
            />
            Không ghép nhạc
        </label>
        <label class="flex items-center gap-2 text-sm">
            <input
                type="radio"
                :checked="model.kind === 'random'"
                data-testid="fork-rieng-music-random"
                @change="patch({ kind: 'random' })"
            />
            Ngẫu nhiên từ thư mục nhạc
        </label>

        <div
            v-if="model.kind === 'random'"
            class="flex flex-col gap-2 rounded-lg border bg-muted/40 p-3"
        >
            <div class="flex items-center gap-2">
                <Input
                    :model-value="model.dir"
                    class="h-8 min-w-0 flex-1"
                    placeholder="Bấm Chọn, hoặc dán đường dẫn thư mục nhạc"
                    aria-label="Thư mục nhạc"
                    :title="model.dir"
                    data-testid="fork-rieng-music-dir"
                    @update:model-value="
                        (v: string | number) => patch({ dir: String(v).trim() })
                    "
                    @change="emit('dir')"
                />
                <Button
                    size="sm"
                    variant="outline"
                    :disabled="picking"
                    data-testid="fork-rieng-music-pick"
                    @click="pick"
                >
                    <IconFolderOpen class="size-4" />
                    {{ picking ? 'Đang chờ chọn…' : 'Chọn' }}
                </Button>
            </div>
            <span
                v-if="model.dir && count !== null"
                :class="
                    cn(
                        'text-xs',
                        count === 0
                            ? 'text-destructive-text'
                            : 'text-muted-foreground',
                    )
                "
                data-testid="fork-rieng-music-count"
            >
                {{
                    count === 0
                        ? 'Không thấy bài nhạc nào (mp3, m4a, wav, aac, ogg, flac).'
                        : `Có ${count} bài nhạc, mỗi video một bài khác nhau (đổi bài từng video ở dòng video).`
                }}
            </span>
            <div class="flex flex-wrap items-center gap-4 text-sm">
                <label class="flex items-center gap-1.5">
                    <input
                        type="radio"
                        :checked="model.mode === 'mix'"
                        data-testid="fork-rieng-music-mix"
                        @change="patch({ mode: 'mix' })"
                    />
                    Trộn với tiếng gốc
                </label>
                <label class="flex items-center gap-1.5">
                    <input
                        type="radio"
                        :checked="model.mode === 'replace'"
                        data-testid="fork-rieng-music-replace"
                        @change="patch({ mode: 'replace' })"
                    />
                    Thay hẳn tiếng gốc
                </label>
            </div>
            <div v-if="model.mode === 'mix'" class="flex flex-col gap-1">
                <div class="flex items-center justify-between text-sm">
                    <span>Âm lượng nhạc</span>
                    <span class="text-muted-foreground tabular-nums">{{
                        gainLabel
                    }}</span>
                </div>
                <input
                    type="range"
                    min="-30"
                    max="0"
                    step="1"
                    :value="model.gain_db"
                    class="w-full accent-violet-600"
                    aria-label="Mức giảm âm lượng nhạc (dB)"
                    data-testid="fork-rieng-music-gain"
                    @input="
                        patch({
                            gain_db: Number(
                                ($event.target as HTMLInputElement).value,
                            ),
                        })
                    "
                />
            </div>
            <p v-if="error" class="text-xs text-destructive-text">
                {{ error }}
            </p>
        </div>
    </div>
</template>

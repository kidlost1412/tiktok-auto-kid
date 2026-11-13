<script setup lang="ts">
// Ô nhập hashtag dạng thẻ nhỏ (chip): gõ rồi bấm Enter / Space / dấu phẩy để thêm, dán nhiều hashtag một lần cũng được,
// Backspace khi ô trống để xoá thẻ cuối. Giá trị là một chuỗi cách nhau bằng dấu cách ("#a #b"), đúng định dạng máy chủ nhận.
// Có thể kèm hàng gợi ý (hashtag đã dùng trước đây): bấm để thêm, cái đã thêm thì ẩn khỏi gợi ý.
import { IconPlus, IconX } from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import { parseTags, type TagSuggestion } from '@/components/fork/shared/hashtags';
import { cn } from '@/lib/utils';

const props = withDefaults(
    defineProps<{
        modelValue: string;
        suggestions?: TagSuggestion[];
        max?: number;
        placeholder?: string;
        inputId?: string;
        testid?: string;
    }>(),
    { suggestions: () => [], max: 50, placeholder: 'Gõ hashtag rồi bấm Enter', inputId: undefined, testid: undefined },
);

const emit = defineEmits<{ 'update:modelValue': [value: string] }>();

const list = computed(() => parseTags(props.modelValue, props.max));
const draft = ref('');
const showAll = ref(false);
const input = ref<HTMLInputElement | null>(null);

const full = computed(() => list.value.length >= props.max);

const commit = (next: string[]) => emit('update:modelValue', next.join(' '));

const add = (raw: string) => {
    const merged = parseTags([...list.value, raw].join(' '), props.max);

    if (merged.length !== list.value.length) {
        commit(merged);
    }
};

const flush = () => {
    if (draft.value.trim()) {
        add(draft.value);
    }

    draft.value = '';
};

const remove = (tag: string) => commit(list.value.filter((t) => t !== tag));

const onKey = (e: KeyboardEvent) => {
    if (e.isComposing) {
        return;
    }

    if (e.key === 'Enter' || e.key === ',' || e.key === ';' || e.key === ' ') {
        // Enter khi ô trống: để phím rơi qua (không chặn việc gửi form/hộp thoại).
        if (draft.value.trim() === '' && e.key === 'Enter') {
            return;
        }

        e.preventDefault();
        flush();
    } else if (e.key === 'Backspace' && draft.value === '' && list.value.length) {
        remove(list.value[list.value.length - 1]);
    }
};

const onPaste = (e: ClipboardEvent) => {
    const text = e.clipboardData?.getData('text') ?? '';

    if (/[\s,;#]/.test(text.trim())) {
        e.preventDefault();
        add(text);
    }
};

const have = computed(() => new Set(list.value.map((t) => t.toLowerCase())));
const pending = computed(() => props.suggestions.filter((s) => !have.value.has(s.tag.toLowerCase())));
const shown = computed(() => (showAll.value ? pending.value : pending.value.slice(0, 12)));
</script>

<template>
    <div class="flex flex-col gap-2" :data-testid="testid">
        <div
            :class="
                cn(
                    'flex min-h-11 cursor-text flex-wrap items-center gap-1.5 rounded-lg border bg-background px-2 py-1.5 transition-shadow',
                    'focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/40',
                )
            "
            @click="input?.focus()"
        >
            <span
                v-for="t in list"
                :key="t"
                class="group inline-flex items-center gap-0.5 rounded-full bg-primary-subtle py-0.5 pr-1 pl-2.5 text-xs font-medium text-primary-text"
            >
                {{ t }}
                <button
                    type="button"
                    class="flex size-4 items-center justify-center rounded-full text-primary-text/70 transition-colors hover:bg-primary-text/15 hover:text-primary-text focus-visible:outline-2 focus-visible:outline-ring"
                    :aria-label="`Xoá ${t}`"
                    @click.stop="remove(t)"
                >
                    <IconX class="size-3" />
                </button>
            </span>
            <input
                :id="inputId"
                ref="input"
                v-model="draft"
                type="text"
                :disabled="full"
                :placeholder="list.length ? (full ? '' : 'Thêm…') : placeholder"
                class="h-7 min-w-24 flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-muted-foreground"
                autocomplete="off"
                autocapitalize="off"
                spellcheck="false"
                @keydown="onKey"
                @paste="onPaste"
                @blur="flush"
            />
        </div>

        <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>Bấm Enter, Space hoặc dấu phẩy để thêm; dán cả danh sách cũng được.</span>
            <span :class="cn('shrink-0 tabular-nums', full && 'font-semibold text-amber-700 dark:text-amber-300')">
                {{ list.length }}/{{ max }} hashtag
            </span>
        </div>

        <div v-if="suggestions.length" class="flex flex-col gap-1.5" data-testid="fork-hashtag-suggestions">
            <div class="flex items-center justify-between gap-2">
                <span class="text-xs font-medium text-muted-foreground">Gợi ý từ các bài đã đăng (bấm để thêm)</span>
                <button
                    v-if="pending.length > 12"
                    type="button"
                    class="text-xs font-medium text-primary-text hover:underline"
                    @click="showAll = !showAll"
                >
                    {{ showAll ? 'Thu gọn' : `Xem thêm ${pending.length - 12}` }}
                </button>
            </div>
            <div v-if="shown.length" class="flex flex-wrap gap-1.5">
                <button
                    v-for="s in shown"
                    :key="s.tag"
                    type="button"
                    :disabled="full"
                    :title="s.uses > 1 ? `Đã dùng ${s.uses} lần` : 'Đã dùng 1 lần'"
                    class="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-2.5 py-1 text-xs transition-colors hover:border-primary hover:bg-primary-subtle hover:text-primary-text focus-visible:outline-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50"
                    :data-testid="`fork-hashtag-suggestion`"
                    @click="add(s.tag)"
                >
                    <IconPlus class="size-3 opacity-60" />
                    {{ s.tag }}
                </button>
            </div>
            <p v-else class="text-xs text-muted-foreground">Đã thêm hết các hashtag gợi ý.</p>
        </div>
    </div>
</template>

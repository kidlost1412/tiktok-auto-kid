<script setup lang="ts">
// Chọn sản phẩm gắn giỏ hàng: ô gọn hiện sản phẩm đang chọn (ảnh + tên); bấm mở danh sách có ô tìm kiếm.
// Bàn phím: ↑/↓ di chuyển, Enter chọn, Esc đóng. Tìm không cần gõ dấu tiếng Việt.
import { IconCheck, IconChevronDown, IconSearch } from '@tabler/icons-vue';
import { computed, nextTick, ref, watch } from 'vue';

import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

export interface PickerOption {
    key: string;
    name: string;
    label: string;
    image?: string | null;
}

const props = defineProps<{
    options: PickerOption[];
    modelValue: string;
    placeholder?: string;
    testid?: string;
}>();

const emit = defineEmits<{ 'update:modelValue': [value: string] }>();

const open = ref(false);
const query = ref('');
const active = ref(0);
const listEl = ref<HTMLElement | null>(null);
const searchEl = ref<HTMLInputElement | null>(null);

const plain = (s: string) =>
    s
        .normalize('NFD')
        .replace(/[̀-ͯ]/g, '')
        .replace(/đ/g, 'd')
        .replace(/Đ/g, 'D')
        .toLowerCase();

const selected = computed(() => props.options.find((o) => o.key === props.modelValue) ?? null);

const shown = computed(() => {
    const q = plain(query.value.trim());

    return q === '' ? props.options : props.options.filter((o) => plain(`${o.name} ${o.label}`).includes(q));
});

watch(open, async (isOpen) => {
    if (!isOpen) {
        return;
    }

    query.value = '';
    active.value = Math.max(0, props.options.findIndex((o) => o.key === props.modelValue));
    await nextTick();
    searchEl.value?.focus();
    scrollActive();
});

watch(query, () => {
    active.value = 0;
});

const scrollActive = () => {
    void nextTick(() => {
        listEl.value?.querySelector<HTMLElement>('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
    });
};

const choose = (o: PickerOption) => {
    emit('update:modelValue', o.key);
    open.value = false;
};

const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();

        if (shown.value.length) {
            active.value = (active.value + (e.key === 'ArrowDown' ? 1 : -1) + shown.value.length) % shown.value.length;
            scrollActive();
        }
    } else if (e.key === 'Enter') {
        e.preventDefault();
        const o = shown.value[active.value];

        if (o) {
            choose(o);
        }
    }
};
</script>

<template>
    <Popover v-model:open="open">
        <PopoverTrigger as-child>
            <button
                type="button"
                role="combobox"
                :aria-expanded="open"
                aria-haspopup="listbox"
                :data-testid="testid"
                :class="
                    cn(
                        'dark:bg-input/30 flex min-h-10 w-full min-w-0 cursor-pointer items-center gap-2.5 rounded-md border border-input bg-card px-2.5 py-1 text-left text-sm transition-[color,box-shadow] outline-none',
                        'hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring',
                        'data-[state=open]:border-ring data-[state=open]:outline-2 data-[state=open]:outline-offset-1 data-[state=open]:outline-ring',
                    )
                "
            >
                <template v-if="selected">
                    <ProductThumb :src="selected.image" class="size-8" />
                    <span class="min-w-0 flex-1">
                        <span class="block truncate font-medium" data-testid="fork-rieng-product-chosen">{{ selected.name }}</span>
                        <span v-if="selected.label !== selected.name" class="block truncate text-xs text-muted-foreground">{{ selected.label }}</span>
                    </span>
                </template>
                <span v-else class="flex-1 text-subtle-foreground">{{ placeholder ?? 'Chọn sản phẩm' }}</span>
                <IconChevronDown class="size-4 shrink-0 text-muted-foreground" />
            </button>
        </PopoverTrigger>

        <PopoverContent
            class="w-(--reka-popover-trigger-width) min-w-64 overflow-hidden p-0"
            :side-offset="4"
            data-testid="fork-rieng-product"
            @open-auto-focus.prevent="searchEl?.focus()"
        >
            <div class="flex items-center gap-2 border-b px-3">
                <IconSearch class="size-4 shrink-0 text-muted-foreground" />
                <input
                    ref="searchEl"
                    v-model="query"
                    type="text"
                    role="searchbox"
                    placeholder="Tìm sản phẩm…"
                    aria-label="Tìm sản phẩm"
                    class="h-10 w-full bg-transparent text-sm outline-none placeholder:text-subtle-foreground"
                    autocomplete="off"
                    @keydown="onKey"
                />
            </div>
            <div ref="listEl" role="listbox" aria-label="Sản phẩm gắn giỏ hàng" class="max-h-72 overflow-y-auto p-1">
                <button
                    v-for="(o, i) in shown"
                    :key="o.key"
                    type="button"
                    role="option"
                    tabindex="-1"
                    :aria-selected="o.key === modelValue"
                    :data-active="i === active"
                    :class="
                        cn(
                            'flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors',
                            i === active ? 'bg-accent' : 'hover:bg-accent/60',
                        )
                    "
                    :data-testid="`fork-rieng-product-opt-${o.key.split('|')[0]}`"
                    @mousemove="active = i"
                    @click="choose(o)"
                >
                    <ProductThumb :src="o.image" class="size-9" />
                    <span class="min-w-0 flex-1">
                        <span class="block truncate font-medium">{{ o.name }}</span>
                        <span v-if="o.label !== o.name" class="block truncate text-xs text-muted-foreground">{{ o.label }}</span>
                    </span>
                    <IconCheck v-if="o.key === modelValue" class="size-4 shrink-0 text-primary-text" />
                </button>
                <p v-if="!shown.length" class="px-3 py-6 text-center text-sm text-muted-foreground">
                    Không thấy sản phẩm nào khớp "{{ query }}".
                </p>
            </div>
        </PopoverContent>
    </Popover>
</template>

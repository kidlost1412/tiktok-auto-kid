<script setup lang="ts">
// Chọn kênh đăng: ô gọn hiện logo + tên kênh đang chọn; bấm mở danh sách kênh kèm logo (ảnh đại diện TikTok).
import { IconCheck, IconChevronDown } from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

export interface ChannelOption {
    id: string;
    name: string;
    avatar_url?: string | null;
    note?: string | null;
}

const props = defineProps<{
    options: ChannelOption[];
    modelValue: string;
    testid?: string;
}>();

const emit = defineEmits<{ 'update:modelValue': [value: string] }>();

const open = ref(false);
const selected = computed(() => props.options.find((o) => o.id === props.modelValue) ?? null);
const initial = (name: string) => name.replace(/^@/, '').slice(0, 1).toUpperCase() || '?';

const choose = (o: ChannelOption) => {
    emit('update:modelValue', o.id);
    open.value = false;
};
</script>

<template>
    <Popover v-model:open="open">
        <PopoverTrigger as-child>
            <button
                type="button"
                class="flex h-10 w-full min-w-0 items-center gap-3 rounded-md border bg-background px-3 text-left text-sm font-normal shadow-xs outline-none hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring"
                :data-testid="testid"
                aria-haspopup="listbox"
                :aria-expanded="open"
            >
                <Avatar class="size-7 shrink-0">
                    <AvatarImage v-if="selected?.avatar_url" :src="selected.avatar_url" alt="" />
                    <AvatarFallback class="text-xs font-semibold">{{ initial(selected?.name ?? '?') }}</AvatarFallback>
                </Avatar>
                <span class="min-w-0 flex-1 truncate">
                    {{ selected?.name ?? 'Chọn kênh' }}
                    <span v-if="selected?.note" class="text-xs text-muted-foreground"> · {{ selected.note }}</span>
                </span>
                <IconChevronDown class="size-4 shrink-0 text-muted-foreground" />
            </button>
        </PopoverTrigger>
        <PopoverContent align="start" class="w-(--reka-popover-trigger-width) min-w-64 p-1">
            <ul role="listbox" class="flex max-h-72 flex-col overflow-y-auto">
                <li v-for="o in options" :key="o.id">
                    <button
                        type="button"
                        role="option"
                        :aria-selected="o.id === modelValue"
                        :class="cn('flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted', o.id === modelValue && 'bg-muted/70')"
                        :data-testid="testid ? `${testid}-${o.id}` : undefined"
                        @click="choose(o)"
                    >
                        <Avatar class="size-8 shrink-0">
                            <AvatarImage v-if="o.avatar_url" :src="o.avatar_url" alt="" />
                            <AvatarFallback class="text-xs font-semibold">{{ initial(o.name) }}</AvatarFallback>
                        </Avatar>
                        <span class="min-w-0 flex-1">
                            <span class="block truncate font-medium">{{ o.name }}</span>
                            <span v-if="o.note" class="block truncate text-xs text-muted-foreground">{{ o.note }}</span>
                        </span>
                        <IconCheck v-if="o.id === modelValue" class="size-4 shrink-0 text-primary" />
                    </button>
                </li>
            </ul>
        </PopoverContent>
    </Popover>
</template>

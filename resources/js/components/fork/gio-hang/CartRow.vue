<script setup lang="ts">
// Một dòng của bảng Giỏ hàng: sản phẩm hub (theo quy cách) → sản phẩm TikTok Shop → tên giỏ trên video → bìa & hashtag.
// Sửa ngay trên dòng; nút "Lưu" chỉ hiện khi có thay đổi.
import {
    IconAlertTriangle,
    IconChevronRight,
    IconDots,
    IconHash,
    IconPencil,
    IconPhoto,
    IconShoppingCartPlus,
    IconTrash,
    IconX,
} from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import type { Persona, Row, ShopCard } from '@/components/fork/gio-hang/types';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { toneClasses } from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils';

const props = defineProps<{
    row: Row;
    card: ShopCard | null;
    name: string;
    nameMax: number;
    dirty: boolean;
    hasDraft: boolean;
    busy: boolean;
    persona?: Persona | null;
}>();

const emit = defineEmits<{
    pick: [];
    'update:name': [value: string];
    save: [];
    clear: [];
    personalise: [];
    rename: [];
    remove: [];
}>();

type State = 'need' | 'bad' | 'ok' | 'idle';

const state = computed<State>(() => {
    if (!props.row.link && props.row.new_videos > 0) {
        return 'need';
    }

    if (
        props.row.link &&
        (props.row.link.paused_reason || props.row.link.problem)
    ) {
        return 'bad';
    }

    return props.row.link ? 'ok' : 'idle';
});

const dot: Record<State, string> = {
    need: 'bg-amber-500',
    bad: 'bg-red-500',
    ok: 'bg-emerald-500',
    idle: 'bg-muted-foreground/40',
};

const stateText = computed(() => {
    switch (state.value) {
        case 'need':
            return 'Chưa chọn giỏ';
        case 'bad':
            return props.row.link?.paused_reason ? 'Tạm dừng' : 'Đang bị giữ';
        case 'ok':
            return 'Sẵn sàng';
        default:
            return 'Chưa chọn giỏ';
    }
});

const chipCls = computed(() => {
    switch (state.value) {
        case 'need':
            return toneClasses.warn.chip;
        case 'bad':
            return toneClasses.danger.chip;
        case 'ok':
            return toneClasses.success.chip;
        default:
            return toneClasses.neutral.chip;
    }
});

const persona = computed(() => {
    const p = props.persona;
    const cover =
        p && p.cover_mode !== 'default' && p.covers.length
            ? p.cover_mode === 'random'
                ? `${p.covers.length} bìa ngẫu nhiên`
                : '1 bìa cố định'
            : null;
    const tags = p && p.hashtags.length ? `${p.hashtags.length} hashtag` : null;

    return {
        cover,
        tags,
        thumb:
            p?.covers.find((c) => c.file === p.cover_fixed)?.url ??
            p?.covers[0]?.url ??
            null,
    };
});

const menuOpen = ref(false);
const nameLen = computed(() => [...props.name].length);
</script>

<template>
    <div
        :class="
            cn(
                'group/row grid gap-x-5 gap-y-2 px-5 py-2.5 transition-colors lg:grid-cols-[minmax(220px,1fr)_minmax(280px,1.4fr)_minmax(220px,1fr)_minmax(170px,0.7fr)_84px] lg:items-center',
                state === 'need' && 'bg-amber-50/70 dark:bg-amber-950/25',
                state === 'bad' && 'bg-red-50/50 dark:bg-red-950/20',
            )
        "
        :data-testid="`fork-gio-hang-row-${row.code}-${row.quy_cach ?? ''}`"
    >
        <!-- Sản phẩm hub -->
        <div class="flex min-w-0 items-center gap-3">
            <span
                :class="cn('size-2 shrink-0 rounded-full', dot[state])"
                :title="stateText"
            />
            <div class="min-w-0">
                <div class="flex min-w-0 items-center gap-1.5">
                    <span
                        class="truncate text-[14px] font-semibold"
                        :title="row.hub_name"
                        >{{ row.hub_name }}</span
                    >
                    <span
                        v-if="row.is_sample"
                        class="shrink-0 rounded bg-muted px-1.5 text-[11px] text-muted-foreground"
                        data-testid="fork-gio-hang-sample-note"
                        >ví dụ</span
                    >
                    <span
                        v-if="!row.enabled"
                        class="shrink-0 rounded bg-muted px-1.5 text-[11px] text-muted-foreground"
                        >hub tắt</span
                    >
                    <span
                        :class="
                            cn(
                                'inline-flex h-5 shrink-0 items-center rounded-full px-2 text-[11.5px] font-medium',
                                chipCls,
                            )
                        "
                        data-testid="fork-gio-hang-state"
                        >{{ stateText }}</span
                    >
                </div>
                <div class="truncate text-[12.5px] text-muted-foreground">
                    <template v-if="row.quy_cach_name"
                        >{{ row.quy_cach_name }} ·
                    </template>
                    <span
                        v-if="state === 'need'"
                        :class="cn('font-semibold', toneClasses.warn.text)"
                        data-testid="fork-gio-hang-need"
                        >{{ row.new_videos }} video đang chờ giỏ</span
                    >
                    <template v-else
                        >{{ row.new_videos }} video chờ đăng</template
                    >
                </div>
            </div>
        </div>

        <!-- Sản phẩm shop -->
        <button
            v-if="card"
            type="button"
            class="flex min-w-0 items-center gap-3 rounded-lg border border-transparent p-1 text-left transition-colors hover:border-border hover:bg-background/60 focus-visible:outline-2 focus-visible:outline-ring"
            title="Đổi sản phẩm shop"
            @click="emit('pick')"
        >
            <ProductThumb :src="card.image" class="size-10 rounded-lg" />
            <div class="min-w-0 flex-1">
                <div
                    class="truncate text-[13.5px] font-medium"
                    :title="card.title"
                >
                    {{ card.title }}
                </div>
                <div
                    class="mt-0.5 flex flex-wrap items-center gap-x-2 text-[12px] tabular-nums"
                >
                    <span class="font-semibold">{{ card.price ?? '—' }}</span>
                    <span v-if="card.missing" :class="toneClasses.danger.text"
                        >không còn trong shop</span
                    >
                    <span
                        v-else-if="card.stock_num <= 0"
                        :class="toneClasses.danger.text"
                        >hết hàng</span
                    >
                    <span v-else class="text-muted-foreground"
                        >còn {{ card.stock_num.toLocaleString('vi-VN') }}</span
                    >
                    <span v-if="card.hidden" class="text-muted-foreground"
                        >· đang ẩn</span
                    >
                </div>
            </div>
            <IconChevronRight
                class="size-4 shrink-0 text-muted-foreground opacity-0 transition group-hover/row:opacity-100"
            />
        </button>
        <button
            v-else
            type="button"
            :class="
                cn(
                    'flex h-12 items-center justify-center gap-2 rounded-lg border border-dashed text-[13.5px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring',
                    state === 'need'
                        ? 'border-amber-400 bg-background/70 text-amber-800 hover:bg-amber-100/60 dark:border-amber-700 dark:text-amber-200 dark:hover:bg-amber-900/30'
                        : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground',
                )
            "
            @click="emit('pick')"
        >
            <IconShoppingCartPlus class="size-[18px]" />
            Chọn sản phẩm shop
        </button>

        <!-- Tên giỏ trên video -->
        <label v-if="card" class="relative block min-w-0">
            <span class="sr-only">Tên giỏ hiện trên video</span>
            <input
                class="h-9 w-full rounded-lg border bg-background pr-14 pl-3 text-[13.5px] font-medium uppercase shadow-xs transition outline-none placeholder:font-normal placeholder:normal-case focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30"
                :maxlength="nameMax"
                placeholder="Tên giỏ hiện trên video"
                :value="name"
                @input="
                    emit(
                        'update:name',
                        ($event.target as HTMLInputElement).value,
                    )
                "
                @keydown.enter="dirty && name.trim() && !busy && emit('save')"
            />
            <span
                :class="
                    cn(
                        'pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-[11.5px] tabular-nums',
                        nameLen >= nameMax
                            ? cn('font-semibold', toneClasses.warn.text)
                            : 'text-muted-foreground',
                    )
                "
                >{{ nameLen }}/{{ nameMax }}</span
            >
        </label>
        <div v-else class="hidden text-[12.5px] text-muted-foreground lg:block">
            Chọn sản phẩm trước
        </div>

        <!-- Bìa & hashtag -->
        <button
            type="button"
            class="flex min-w-0 items-center gap-2.5 rounded-lg p-1.5 text-left transition-colors hover:bg-accent/50 focus-visible:outline-2 focus-visible:outline-ring"
            :data-testid="`fork-personalise-open-${row.code}-${row.quy_cach ?? ''}`"
            @click="emit('personalise')"
        >
            <span
                class="flex h-9 w-7 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted text-muted-foreground ring-1 ring-border"
            >
                <img
                    v-if="persona.thumb"
                    :src="persona.thumb"
                    alt=""
                    class="size-full object-cover"
                    loading="lazy"
                />
                <IconPhoto v-else class="size-4" />
            </span>
            <span class="min-w-0 text-[12.5px] leading-snug">
                <span
                    class="block truncate"
                    :class="
                        persona.cover ? 'font-medium' : 'text-muted-foreground'
                    "
                    >{{ persona.cover ?? 'Bìa mặc định' }}</span
                >
                <span
                    class="flex items-center gap-1 truncate text-muted-foreground"
                    ><IconHash class="size-3" />{{
                        persona.tags ?? 'hashtag chung'
                    }}</span
                >
            </span>
        </button>

        <!-- Hành động -->
        <div class="flex items-center justify-end gap-1">
            <Button
                v-if="card && (dirty || hasDraft)"
                size="sm"
                class="h-8"
                :disabled="!dirty || !name.trim() || busy"
                @click="emit('save')"
            >
                <Spinner v-if="busy" class="size-3.5" />
                Lưu
            </Button>
            <Popover v-model:open="menuOpen">
                <PopoverTrigger as-child>
                    <Button
                        size="icon-sm"
                        variant="ghost"
                        aria-label="Thêm thao tác"
                        :data-testid="`fork-gio-hang-menu-${row.code}`"
                    >
                        <IconDots class="size-4" />
                    </Button>
                </PopoverTrigger>
                <PopoverContent align="end" class="w-52 p-1">
                    <button
                        type="button"
                        class="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm hover:bg-accent"
                        :data-testid="`fork-gio-hang-rename-${row.code}`"
                        @click="((menuOpen = false), emit('rename'))"
                    >
                        <IconPencil class="size-4 text-muted-foreground" /> Đổi
                        tên sản phẩm
                    </button>
                    <button
                        v-if="row.link || hasDraft"
                        type="button"
                        class="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm hover:bg-accent"
                        :disabled="busy"
                        @click="((menuOpen = false), emit('clear'))"
                    >
                        <IconX class="size-4 text-muted-foreground" /> Bỏ chọn
                        giỏ
                    </button>
                    <button
                        type="button"
                        :class="
                            cn(
                                'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm hover:bg-accent',
                                toneClasses.danger.text,
                            )
                        "
                        :data-testid="`fork-gio-hang-delete-${row.code}`"
                        @click="((menuOpen = false), emit('remove'))"
                    >
                        <IconTrash class="size-4" /> Xoá sản phẩm
                    </button>
                </PopoverContent>
            </Popover>
        </div>

        <!-- Cảnh báo của dòng -->
        <div
            v-if="row.link?.paused_reason || row.link?.problem"
            :class="
                cn(
                    'flex items-start gap-2 rounded-lg border px-3 py-2 text-[12.5px] lg:col-span-5',
                    row.link?.paused_reason
                        ? toneClasses.danger.box
                        : toneClasses.warn.box,
                )
            "
        >
            <IconAlertTriangle class="mt-px size-4 shrink-0" />
            <span v-if="row.link?.paused_reason"
                >Đã tạm dừng: {{ row.link.paused_reason }} — bấm Lưu để chạy
                tiếp.</span
            >
            <span v-else
                >Video của dòng này đang được giữ trong kho:
                {{ row.link?.problem }}.</span
            >
        </div>
    </div>
</template>

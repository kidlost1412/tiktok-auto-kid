<script setup lang="ts">
// Thẻ một dòng ghép: sản phẩm hub (theo quy cách) với sản phẩm TikTok Shop của kênh.
import {
    IconAlertTriangle,
    IconCheck,
    IconPackage,
    IconPencil,
    IconPhoto,
    IconShoppingCartPlus,
    IconTrash,
} from '@tabler/icons-vue';
import { computed } from 'vue';

import type { Persona, Row, ShopCard } from '@/components/fork/gio-hang/types';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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

type Tone = 'need' | 'bad' | 'ok' | 'idle';

// need = có video chờ mà chưa chọn giỏ (nổi bật nhất); bad = đã chọn nhưng đang bị chặn.
const tone = computed<Tone>(() => {
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

const frame: Record<Tone, string> = {
    need: 'border-amber-400 bg-amber-50 ring-1 ring-amber-300/60 dark:border-amber-700 dark:bg-amber-950/40 dark:ring-amber-800/60',
    bad: 'border-red-300 bg-red-50/60 dark:border-red-900 dark:bg-red-950/30',
    ok: 'border-emerald-300/70 bg-card dark:border-emerald-900',
    idle: 'bg-card',
};

const left = computed(() => props.name.length);

// Tóm tắt cá nhân hoá hiện ở nút (chỉ xem nhanh, sửa trong hộp thoại).
const personaSummary = computed(() => {
    const p = props.persona;
    const parts: string[] = [];

    if (p && p.cover_mode !== 'default' && p.covers.length) {
        parts.push(
            p.cover_mode === 'random'
                ? `bìa ngẫu nhiên (${p.covers.length} ảnh)`
                : 'bìa cố định',
        );
    }

    if (p && p.hashtags.length) {
        parts.push(`${p.hashtags.length} hashtag`);
    }

    return parts.join(' · ');
});
</script>

<template>
    <div
        :class="cn('flex flex-col gap-4 rounded-[14px] border p-5 shadow-[0_1px_2px_rgba(28,25,23,.04),0_2px_6px_-1px_rgba(28,25,23,.06)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,.03),0_1px_2px_rgba(0,0,0,.35)]', frame[tone])"
        :data-testid="`fork-gio-hang-row-${row.code}-${row.quy_cach ?? ''}`"
    >
        <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
                <div class="flex items-center gap-2 text-base font-semibold">
                    <IconPackage
                        class="size-5 shrink-0 text-muted-foreground"
                    />
                    <span class="truncate">{{ row.hub_name }}</span>
                </div>
                <div
                    v-if="row.quy_cach_name"
                    class="text-sm text-muted-foreground"
                >
                    Quy cách: {{ row.quy_cach_name }}
                </div>
            </div>
            <div class="flex shrink-0 items-center gap-1">
                <Badge v-if="tone === 'ok'" variant="success">
                    <IconCheck class="size-4" />
                    Sẵn sàng
                </Badge>
                <Badge v-else-if="!row.enabled" variant="outline"
                    >Hub đã tắt</Badge
                >
                <Button
                    size="icon-sm"
                    variant="ghost"
                    title="Đổi tên sản phẩm"
                    aria-label="Đổi tên sản phẩm"
                    :data-testid="`fork-gio-hang-rename-${row.code}`"
                    @click="emit('rename')"
                >
                    <IconPencil class="size-4" />
                </Button>
                <Button
                    size="icon-sm"
                    variant="ghost"
                    title="Xoá sản phẩm"
                    aria-label="Xoá sản phẩm"
                    :data-testid="`fork-gio-hang-delete-${row.code}`"
                    @click="emit('remove')"
                >
                    <IconTrash class="size-4" />
                </Button>
            </div>
        </div>

        <div
            v-if="row.is_sample"
            class="rounded-lg border border-dashed p-3 text-sm text-muted-foreground"
            data-testid="fork-gio-hang-sample-note"
        >
            Đây là <b>sản phẩm ví dụ</b> để anh xem app hoạt động. Bấm nút bút
            để đổi tên, hoặc nút thùng rác để xoá khi đã có sản phẩm thật.
        </div>

        <div
            v-if="tone === 'need'"
            class="flex items-center gap-2 rounded-lg bg-amber-100 px-4 py-3 text-base font-semibold text-amber-900 dark:bg-amber-900/40 dark:text-amber-100"
            data-testid="fork-gio-hang-need"
        >
            <IconAlertTriangle class="size-5 shrink-0" />
            {{ row.new_videos }} video đang chờ — chọn giỏ ngay
        </div>
        <div
            v-else-if="row.new_videos > 0"
            class="text-sm text-muted-foreground"
        >
            {{ row.new_videos }} video đang chờ trong kho
        </div>

        <div
            v-if="row.link?.paused_reason"
            class="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
        >
            Đã tạm dừng: {{ row.link.paused_reason }} (lưu lại để chạy tiếp)
        </div>
        <div
            v-else-if="row.link?.problem"
            class="rounded-lg border border-orange-300 bg-orange-50 p-3 text-sm text-orange-900 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-200"
        >
            Video của dòng này đang được giữ trong kho: {{ row.link.problem }}.
        </div>

        <!-- Sản phẩm shop đã chọn -->
        <button
            v-if="card"
            type="button"
            class="flex items-center gap-3 rounded-xl bg-muted/50 p-3 text-left transition-colors hover:bg-muted"
            @click="emit('pick')"
        >
            <ProductThumb :src="card.image" class="size-24 rounded-lg" />
            <div class="min-w-0 flex-1 text-base">
                <div class="line-clamp-2 font-medium break-words">
                    {{ card.title }}
                </div>
                <div
                    class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground"
                >
                    <span class="font-medium text-foreground">{{
                        card.price ?? '—'
                    }}</span>
                    <Badge v-if="card.missing" variant="destructive-subtle"
                        >Không còn trong shop</Badge
                    >
                    <Badge
                        v-else-if="card.stock_num <= 0"
                        variant="destructive-subtle"
                        >Hết hàng</Badge
                    >
                    <Badge v-else variant="success"
                        >Còn {{ card.stock_num.toLocaleString('vi-VN') }}</Badge
                    >
                    <Badge v-if="card.hidden" variant="outline">Đang ẩn</Badge>
                </div>
            </div>
        </button>
        <button
            v-else
            type="button"
            :class="
                cn(
                    'flex items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-base font-medium transition-colors',
                    tone === 'need'
                        ? 'border-amber-400 text-amber-900 hover:bg-amber-100 dark:text-amber-200 dark:hover:bg-amber-900/30'
                        : 'text-muted-foreground hover:bg-muted/50',
                )
            "
            @click="emit('pick')"
        >
            <IconShoppingCartPlus class="size-6" />
            Chọn sản phẩm shop
        </button>

        <!-- Tên giỏ hiện trên video -->
        <label v-if="card" class="flex flex-col gap-1.5 text-sm">
            <span
                class="flex items-center justify-between text-muted-foreground"
            >
                <span>Tên giỏ hiện trên video</span>
                <span
                    :class="
                        left >= nameMax ? 'font-semibold text-amber-600' : ''
                    "
                    >{{ left }}/{{ nameMax }}</span
                >
            </span>
            <Input
                class="h-10"
                :maxlength="nameMax"
                placeholder="VD: MUA 5 TẶNG 3 MÓN"
                :model-value="name"
                @update:model-value="
                    (v: string | number) => emit('update:name', String(v))
                "
            />
        </label>

        <div class="flex min-w-0 flex-wrap items-center gap-2">
            <Button
                size="sm"
                variant="secondary"
                class="shrink-0"
                :data-testid="`fork-personalise-open-${row.code}-${row.quy_cach ?? ''}`"
                @click="emit('personalise')"
            >
                <IconPhoto class="size-4" />
                Ảnh bìa &amp; hashtag
            </Button>
            <span class="min-w-0 truncate text-sm text-muted-foreground">{{
                personaSummary || 'chưa đặt riêng — dùng mặc định'
            }}</span>
        </div>

        <div v-if="card" class="flex flex-wrap items-center gap-2">
            <Button
                size="sm"
                :disabled="!dirty || !name.trim() || busy"
                @click="emit('save')"
                >Lưu</Button
            >
            <Button size="sm" variant="outline" @click="emit('pick')"
                >Đổi giỏ</Button
            >
            <Button
                v-if="row.link || hasDraft"
                size="sm"
                variant="ghost"
                :disabled="busy"
                @click="emit('clear')"
                >Bỏ chọn</Button
            >
        </div>
    </div>
</template>

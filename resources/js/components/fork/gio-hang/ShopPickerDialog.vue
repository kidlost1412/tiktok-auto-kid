<script setup lang="ts">
// Hộp chọn sản phẩm TikTok Shop cho một dòng (sản phẩm hub x quy cách): ảnh, tên, giá, tồn kho, tìm kiếm.
import { IconCheck, IconEye, IconEyeOff, IconSearch } from '@tabler/icons-vue';
import { computed, ref, watch } from 'vue';

import type { ShopProduct } from '@/components/fork/gio-hang/types';
import ProductThumb from '@/components/fork/shared/ProductThumb.vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const props = defineProps<{
    open: boolean;
    rowLabel: string;
    products: ShopProduct[];
    currentId: string;
    busyId: string | null;
    /** 'add' = thêm sản phẩm mới vào hub từ sản phẩm shop (không có sản phẩm đang chọn). */
    mode?: 'pick' | 'add';
    adding?: boolean;
}>();

const emit = defineEmits<{
    'update:open': [value: boolean];
    select: [product: ShopProduct];
    'toggle-hidden': [product: ShopProduct, hidden: boolean];
}>();

const norm = (s: string) =>
    s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').toLowerCase();

const search = ref('');
const showHidden = ref(false);

watch(
    () => props.open,
    (open) => {
        if (open) {
            search.value = '';
            showHidden.value = false;
        }
    },
);

const hiddenCount = computed(
    () => props.products.filter((p) => p.hidden && !p.missing).length,
);

const shown = computed(() => {
    const q = norm(search.value.trim());

    return props.products.filter((p) => {
        if (p.missing) {
            return false;
        }

        if (p.hidden !== showHidden.value) {
            return false;
        }

        return (
            q === '' || norm(p.title).includes(q) || p.product_id.includes(q)
        );
    });
});

const fmtNum = (n: number) => n.toLocaleString('vi-VN');
</script>

<template>
    <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
        <DialogContent class="sm:max-w-3xl" data-testid="fork-gio-hang-picker">
            <DialogHeader>
                <DialogTitle>{{
                    mode === 'add'
                        ? 'Thêm sản phẩm từ shop'
                        : `Chọn giỏ hàng cho ${rowLabel}`
                }}</DialogTitle>
                <DialogDescription>
                    <template v-if="mode === 'add'">
                        Chọn sản phẩm TikTok Shop. App sẽ tạo sản phẩm tương
                        ứng trong Xưởng Video (tên lấy từ sản phẩm shop, anh
                        đổi tên được sau) và gắn luôn giỏ hàng cho kênh này.
                    </template>
                    <template v-else>
                        Chọn đúng sản phẩm TikTok Shop sẽ gắn vào video của
                        dòng này.
                    </template>
                </DialogDescription>
            </DialogHeader>

            <div class="flex flex-wrap items-center gap-2">
                <div class="relative min-w-0 flex-1">
                    <IconSearch
                        class="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
                    />
                    <Input
                        v-model="search"
                        class="h-11 pl-10"
                        placeholder="Tìm theo tên hoặc ID sản phẩm"
                        data-testid="fork-gio-hang-search"
                    />
                </div>
                <Button
                    size="sm"
                    :variant="showHidden ? 'default' : 'outline'"
                    @click="showHidden = !showHidden"
                >
                    <component
                        :is="showHidden ? IconEye : IconEyeOff"
                        class="size-4"
                    />
                    {{
                        showHidden
                            ? 'Đang xem sản phẩm đã ẩn'
                            : `Đã ẩn (${hiddenCount})`
                    }}
                </Button>
            </div>

            <ul class="flex max-h-[55vh] flex-col gap-2 overflow-y-auto pr-1">
                <li
                    v-for="p in shown"
                    :key="p.product_id"
                    :class="
                        cn(
                            'flex items-center gap-4 rounded-xl border p-3',
                            p.product_id === currentId &&
                                'border-primary bg-primary/5',
                            p.stock_num <= 0 && 'opacity-70',
                        )
                    "
                    :data-testid="`fork-gio-hang-shop-${p.product_id}`"
                >
                    <ProductThumb :src="p.image" class="size-20 rounded-lg" />

                    <div class="min-w-0 flex-1 text-base">
                        <div class="line-clamp-2 font-medium break-words">
                            {{ p.title }}
                        </div>
                        <div
                            class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground"
                        >
                            <span class="font-medium text-foreground">{{
                                p.price ?? '—'
                            }}</span>
                            <Badge
                                v-if="p.stock_num <= 0"
                                variant="destructive-subtle"
                                >Hết hàng</Badge
                            >
                            <span v-else>Tồn {{ fmtNum(p.stock_num) }}</span>
                            <Badge
                                v-for="u in p.used_by"
                                :key="u"
                                variant="info"
                                >Đang dùng cho {{ u }}</Badge
                            >
                        </div>
                    </div>

                    <div class="flex shrink-0 flex-col gap-1">
                        <Button
                            v-if="!p.hidden"
                            size="sm"
                            :variant="
                                p.product_id === currentId
                                    ? 'secondary'
                                    : 'default'
                            "
                            :disabled="adding"
                            :data-testid="`fork-gio-hang-choose-${p.product_id}`"
                            @click="emit('select', p)"
                        >
                            <IconCheck
                                v-if="p.product_id === currentId"
                                class="size-4"
                            />
                            {{
                                p.product_id === currentId
                                    ? 'Đang chọn'
                                    : mode === 'add'
                                      ? 'Thêm'
                                      : 'Chọn'
                            }}
                        </Button>
                        <Button
                            size="sm"
                            variant="ghost"
                            :disabled="busyId === p.product_id"
                            @click="emit('toggle-hidden', p, !p.hidden)"
                            >{{ p.hidden ? 'Hiện lại' : 'Ẩn' }}</Button
                        >
                    </div>
                </li>
                <li
                    v-if="!shown.length"
                    class="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground"
                >
                    {{
                        products.length
                            ? 'Không có sản phẩm nào khớp.'
                            : 'Chưa có sản phẩm nào. Đóng hộp này và bấm "Lấy sản phẩm từ shop".'
                    }}
                </li>
            </ul>

            <p class="text-xs text-muted-foreground">
                Ẩn chỉ có tác dụng trong ứng dụng này, không thay đổi gì trên
                TikTok Shop.
            </p>
        </DialogContent>
    </Dialog>
</template>

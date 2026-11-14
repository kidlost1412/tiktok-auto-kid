<script setup lang="ts">
// Nội dung bàn Chủ quầy: đọc /auto/gio-hang?kenh=… rồi dùng lại CartTable (cùng phần thân với trang Giỏ hàng).
// Đổi kênh: địa chỉ đổi theo `kenh`, dữ liệu tự tải lại và dữ liệu cũ vẫn hiện (mờ) trong lúc chờ.
import { IconHash, IconPlus } from '@tabler/icons-vue';
import { computed, onMounted, ref } from 'vue';

import CartTable from '@/components/fork/gio-hang/CartTable.vue';
import type {
    Persona,
    PersonaDefault,
    Row,
    ShopProduct,
    Sync,
} from '@/components/fork/gio-hang/types';
import { banBao } from '@/components/fork/nha/ban/bus';
import { useInertiaProps } from '@/components/fork/nha/ban/useInertiaProps';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

const props = defineProps<{ kenh: string | null }>();
const emit = defineEmits<{ kenh: [id: string] }>();

type GioHangProps = {
    channels: {
        id: string;
        username: string | null;
        display_name: string | null;
    }[];
    selected: string | null;
    sync: Sync | null;
    products: ShopProduct[];
    rows: Row[];
    name_max: number;
    sync_ttl_minutes: number;
    personalise?: Record<string, Persona>;
    personalise_default?: PersonaDefault;
    sample_hidden?: boolean;
    name_short_max?: number;
};

const url = computed(() =>
    props.kenh
        ? `/auto/gio-hang?kenh=${encodeURIComponent(props.kenh)}`
        : '/auto/gio-hang',
);
// Đúng các prop CartTable dùng (không có prop nào khác trên trang này).
const ONLY = [
    'channels',
    'selected',
    'sync',
    'products',
    'rows',
    'name_max',
    'name_short_max',
    'sync_ttl_minutes',
    'personalise',
    'personalise_default',
    'sample_hidden',
];
const {
    props: p,
    loading,
    error,
    reload,
} = useInertiaProps<GioHangProps>(url, 'fork/GioHang', ONLY);

const table = ref<InstanceType<typeof CartTable> | null>(null);

onMounted(() => reload());

const onChanged = (viec: 'luu-gio' | 'lay-lai' | 'khac') => {
    reload();

    if (viec !== 'khac') {
        banBao('chuquay', viec);
    }
};

const onChannel = (id: string) => emit('kenh', id);
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col gap-4" data-testid="ban-chuquay">
        <div
            v-if="error && !p"
            class="flex items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 text-sm"
        >
            <span class="text-muted-foreground">{{ error }}</span>
            <Button size="sm" variant="outline" @click="reload()"
                >Thử lại</Button
            >
        </div>

        <template v-else-if="!p">
            <div class="grid grid-cols-4 gap-3">
                <Skeleton v-for="i in 4" :key="i" class="h-16 rounded-[14px]" />
            </div>
            <Skeleton class="h-72 rounded-[14px]" />
        </template>

        <template v-else>
            <div v-if="p.channels.length" class="flex justify-end gap-2">
                <Button
                    variant="outline"
                    size="sm"
                    data-testid="ban-chuquay-hashtag"
                    @click="table?.openDefault()"
                >
                    <IconHash class="size-4" />
                    Hashtag mặc định{{
                        p.personalise_default?.tags.length
                            ? ` (${p.personalise_default.tags.length})`
                            : ''
                    }}
                </Button>
                <Button
                    size="sm"
                    data-testid="ban-chuquay-them"
                    @click="table?.openAdd()"
                >
                    <IconPlus class="size-4" />
                    Thêm sản phẩm
                </Button>
            </div>

            <CartTable
                ref="table"
                :class="loading && 'opacity-60 transition-opacity'"
                embedded
                :channels="p.channels"
                :selected="p.selected"
                :sync="p.sync"
                :products="p.products"
                :rows="p.rows"
                :name_max="p.name_max"
                :sync_ttl_minutes="p.sync_ttl_minutes"
                :personalise="p.personalise"
                :personalise_default="p.personalise_default"
                :sample_hidden="p.sample_hidden"
                :name_short_max="p.name_short_max"
                @channel="onChannel"
                @refresh="(only: string[]) => reload(only)"
                @changed="onChanged"
            />
        </template>
    </div>
</template>

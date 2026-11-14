<script setup lang="ts">
// Trang riêng của bản Việt hoá: chọn sản phẩm TikTok Shop cho từng sản phẩm của hub, từng quy cách, trên từng kênh.
// Phần thân (thanh kênh, lấy sản phẩm shop, tóm tắt, bảng, hộp thoại) nằm ở CartTable — dùng chung với bàn Chủ quầy.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en).
import { IconHash, IconPlus } from '@tabler/icons-vue';
import { ref } from 'vue';

import CartTable from '@/components/fork/gio-hang/CartTable.vue';
import type {
    Persona,
    PersonaDefault,
    Row,
    ShopProduct,
    Sync,
} from '@/components/fork/gio-hang/types';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import { Button } from '@/components/ui/button';

defineProps<{
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
}>();

const table = ref<InstanceType<typeof CartTable> | null>(null);
</script>

<template>
    <AutoShell
        title="Giỏ hàng"
        description="Gắn sản phẩm TikTok Shop cho video của từng sản phẩm, theo từng kênh. Sản phẩm chưa chọn giỏ thì video được giữ trong kho."
        testid="fork-gio-hang-page"
    >
        <template v-if="channels.length" #actions>
            <Button
                variant="outline"
                data-testid="fork-personalise-default"
                @click="table?.openDefault()"
            >
                <IconHash class="size-4" />
                Hashtag mặc định{{
                    personalise_default?.tags.length
                        ? ` (${personalise_default.tags.length})`
                        : ''
                }}
            </Button>
            <Button data-testid="fork-gio-hang-add" @click="table?.openAdd()">
                <IconPlus class="size-4" />
                Thêm sản phẩm
            </Button>
        </template>

        <CartTable
            ref="table"
            :channels="channels"
            :selected="selected"
            :sync="sync"
            :products="products"
            :rows="rows"
            :name_max="name_max"
            :sync_ttl_minutes="sync_ttl_minutes"
            :personalise="personalise"
            :personalise_default="personalise_default"
            :sample_hidden="sample_hidden"
            :name_short_max="name_short_max"
        />
    </AutoShell>
</template>

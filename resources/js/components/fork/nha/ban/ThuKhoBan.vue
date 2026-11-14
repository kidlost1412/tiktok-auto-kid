<script setup lang="ts">
// Bàn của Thủ kho: hai tab. "Kho video" (video sẵn sàng đăng của app) và "Sản phẩm xưởng" (tab Sản phẩm của hub Xưởng Video).
// Tab Kho giữ trạng thái đang xem (tab trạng thái, sản phẩm); nội dung ở ThuKhoKho (dựng lại khi đổi).
import { ref } from 'vue';

import HubEmbed from '@/components/fork/nha/ban/HubEmbed.vue';
import ThuKhoKho from '@/components/fork/nha/ban/ThuKhoKho.vue';
import type { NhaData } from '@/components/fork/nha/types';
import { cn } from '@/lib/utils';

defineProps<{ data: NhaData | null }>();

const main = ref<'kho' | 'san-pham'>('kho');
// Giữ iframe hub sau lần mở đầu (đổi tab qua lại không tải lại).
const sanPhamOpened = ref(false);

const tabs = [
    { key: 'kho' as const, label: 'Kho video' },
    { key: 'san-pham' as const, label: 'Sản phẩm xưởng' },
];

const setMain = (k: 'kho' | 'san-pham') => {
    main.value = k;

    if (k === 'san-pham') {
        sanPhamOpened.value = true;
    }
};

// null = tự chọn tab đầu tiên có video (như trang Kho).
const tab = ref<string | null>(null);
const product = ref('');
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col gap-4" data-testid="ban-thukho">
        <div
            class="flex w-fit gap-0.5 rounded-lg bg-muted p-1"
            role="tablist"
            aria-label="Phần của Thủ kho"
        >
            <button
                v-for="t in tabs"
                :key="t.key"
                type="button"
                role="tab"
                :aria-selected="main === t.key"
                :data-testid="`ban-thukho-tab-${t.key}`"
                :class="
                    cn(
                        'rounded-md px-3.5 py-1 text-sm font-medium transition',
                        main === t.key
                            ? 'bg-card text-foreground shadow-xs'
                            : 'text-muted-foreground hover:text-foreground',
                    )
                "
                @click="setMain(t.key)"
            >
                {{ t.label }}
            </button>
        </div>

        <ThuKhoKho
            v-if="main === 'kho'"
            :key="`${tab ?? 'tu-chon'}|${product}`"
            :tab="tab"
            :product="product"
            @tab="(k: string) => (tab = k)"
            @product="(code: string) => (product = code)"
        />

        <div
            v-if="sanPhamOpened"
            v-show="main === 'san-pham'"
            class="flex min-h-[560px] flex-1 flex-col"
        >
            <HubEmbed :hub-url="data?.hub?.url" tab="san-pham" />
        </div>
    </div>
</template>

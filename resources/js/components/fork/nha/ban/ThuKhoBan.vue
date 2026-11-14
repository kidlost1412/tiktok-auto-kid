<script setup lang="ts">
// Bàn của Thủ kho: ba tab. "Kho video" (video sẵn sàng đăng của app), "Kho riêng" (video bạn tự làm) và
// "Sản phẩm xưởng" (tab Sản phẩm của hub Xưởng Video). Mỗi tab giữ bộ lọc đang xem; nội dung ở ThuKhoKho / ThuKhoRieng
// (đổi bộ lọc thì tự tải lại, không dựng lại).
import { ref } from 'vue';

import type { RiengLoc } from '@/components/fork/kho/rieng';
import HubEmbed from '@/components/fork/nha/ban/HubEmbed.vue';
import ThuKhoKho from '@/components/fork/nha/ban/ThuKhoKho.vue';
import ThuKhoRieng from '@/components/fork/nha/ban/ThuKhoRieng.vue';
import type { NhaData } from '@/components/fork/nha/types';
import { cn } from '@/lib/utils';

defineProps<{ data: NhaData | null }>();

const main = ref<'kho' | 'rieng' | 'san-pham'>('kho');
// Giữ iframe hub sau lần mở đầu (đổi tab qua lại không tải lại).
const sanPhamOpened = ref(false);

const tabs = [
    { key: 'kho' as const, label: 'Kho video' },
    { key: 'rieng' as const, label: 'Kho riêng' },
    { key: 'san-pham' as const, label: 'Sản phẩm xưởng' },
];

const setMain = (k: 'kho' | 'rieng' | 'san-pham') => {
    main.value = k;

    if (k === 'san-pham') {
        sanPhamOpened.value = true;
    }
};

// null = tự chọn tab đầu tiên có video (như trang Kho).
const tab = ref<string | null>(null);
const product = ref('');

// Kho riêng: bộ lọc + các video đang chọn (giữ khi đổi bộ lọc).
const rieng = ref<RiengLoc>({ folder: 0, status: '', day: '' });
const riengPicked = ref<
    Record<number, { file_name: string; duplicate: string | null }>
>({});
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
            :tab="tab"
            :product="product"
            @tab="(k: string) => (tab = k)"
            @product="(code: string) => (product = code)"
        />

        <ThuKhoRieng
            v-if="main === 'rieng'"
            v-model:picked="riengPicked"
            :loc="rieng"
            @filter="(f) => (rieng = f)"
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

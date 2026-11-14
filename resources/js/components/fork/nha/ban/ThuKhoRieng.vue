<script setup lang="ts">
// Tab "Kho riêng" của bàn Thủ kho cho MỘT bộ lọc (thư mục / trạng thái / ngày / trang): đọc /auto/kho/rieng?…
// rồi dùng lại KhoRiengBody (cùng phần thân với trang Kho riêng). Đổi bộ lọc: địa chỉ đổi, dữ liệu tự tải lại;
// các video đang chọn (`picked`) được giữ ở bàn nên không mất.
import { IconRefresh } from '@tabler/icons-vue';
import { computed, onMounted } from 'vue';

import KhoRiengBody from '@/components/fork/kho/KhoRiengBody.vue';
import type { RiengLoc, RiengPageProps } from '@/components/fork/kho/rieng';
import { banBao } from '@/components/fork/nha/ban/bus';
import { useInertiaProps } from '@/components/fork/nha/ban/useInertiaProps';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

const props = defineProps<{ loc: RiengLoc }>();
const emit = defineEmits<{ filter: [q: RiengLoc] }>();

const picked = defineModel<
    Record<number, { file_name: string; duplicate: string | null }>
>('picked', { required: true });

// Địa chỉ đổi theo bộ lọc: useInertiaProps tự tải lại, dữ liệu cũ vẫn hiện trong lúc chờ.
const url = computed(() => {
    const q = new URLSearchParams();

    if (props.loc.folder) {
        q.set('folder', String(props.loc.folder));
    }

    if (props.loc.status) {
        q.set('status', props.loc.status);
    }

    if (props.loc.day) {
        q.set('day', props.loc.day);
    }

    if (props.loc.page) {
        q.set('page', String(props.loc.page));
    }

    return `/auto/kho/rieng${q.size ? `?${q.toString()}` : ''}`;
});

const {
    props: p,
    error,
    reload,
} = useInertiaProps<RiengPageProps>(url, 'fork/KhoRieng');

onMounted(() => reload());

const onChanged = (viec: 'quet' | 'xem') => {
    reload();
    banBao('thukho', viec);
};
</script>

<template>
    <div
        class="flex min-h-0 flex-1 flex-col gap-4"
        data-testid="ban-thukho-rieng"
    >
        <div
            v-if="error && !p"
            class="flex items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 text-sm"
        >
            <span class="text-muted-foreground">{{ error }}</span>
            <Button size="sm" variant="outline" @click="reload()">
                <IconRefresh class="size-4" />
                Thử lại
            </Button>
        </div>

        <template v-else-if="!p">
            <Skeleton class="h-14 rounded-[14px]" />
            <div class="grid grid-cols-5 gap-3">
                <Skeleton
                    v-for="i in 5"
                    :key="i"
                    class="aspect-[9/16] rounded-[14px]"
                />
            </div>
        </template>

        <KhoRiengBody
            v-else
            v-model:picked="picked"
            embedded
            v-bind="p"
            @filter="(f) => emit('filter', f)"
            @refresh="(only: string[]) => reload(only)"
            @changed="onChanged"
        />
    </div>
</template>

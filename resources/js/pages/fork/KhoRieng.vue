<script setup lang="ts">
// Kho riêng: video bạn tự làm. Thêm thư mục, chọn video (bấm, kéo, Shift) rồi đăng / hẹn giờ, hoặc cất vào "Giỏ chờ đăng".
// Trang tự cập nhật: video mới bỏ vào thư mục xuất hiện trong ~10 giây, không cần bấm gì.
// Phần thân nằm ở KhoRiengBody (dùng chung với bàn Thủ kho trong Khu Tự Trị).
import { IconRefresh } from '@tabler/icons-vue';
import { ref } from 'vue';

import KhoRiengBody from '@/components/fork/kho/KhoRiengBody.vue';
import type { RiengPageProps } from '@/components/fork/kho/rieng';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import { Button } from '@/components/ui/button';
import dayjs from '@/dayjs';

const props = defineProps<RiengPageProps>();

const body = ref<InstanceType<typeof KhoRiengBody> | null>(null);

const fmt = (iso: string | null) =>
    iso ? dayjs(iso).format('HH:mm DD/MM') : '—';
</script>

<template>
    <AutoShell
        title="Kho riêng"
        :description="`Video bạn tự làm. Quét lần cuối ${fmt(props.last_scan_at)}. Video mới bỏ vào thư mục sẽ tự hiện sau khoảng 10 giây.`"
        testid="fork-rieng-page"
    >
        <template #actions>
            <Button
                size="sm"
                :disabled="body?.busy === 'scan'"
                data-testid="fork-rieng-scan"
                @click="body?.scan()"
            >
                <IconRefresh
                    class="size-4"
                    :class="{ 'animate-spin': body?.busy === 'scan' }"
                />
                {{ body?.busy === 'scan' ? 'Đang quét…' : 'Quét lại' }}
            </Button>
        </template>

        <KhoRiengBody ref="body" v-bind="props" />
    </AutoShell>
</template>

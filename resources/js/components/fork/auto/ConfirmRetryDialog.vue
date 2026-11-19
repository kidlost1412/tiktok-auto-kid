<script setup lang="ts">
// Hộp hỏi lại trước khi đăng lại bài "chưa rõ đã lên TikTok chưa" (dùng chung cho khối "Bài không đăng được" và "Vừa đăng").
// Chủ app phải tự kiểm tra TikTok Studio rồi mới xác nhận, nếu không bài sẽ bị đăng trùng.
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';

defineProps<{
    /** Bài đang hỏi (null = đóng hộp). */
    target: { label: string; username: string | null } | null;
    busy: boolean;
    /** Gắn vào nút xác nhận để test. */
    okTestid?: string;
}>();

const emit = defineEmits<{ confirm: []; cancel: [] }>();
</script>

<template>
    <Dialog
        :open="target !== null"
        @update:open="
            (o) => {
                if (!o && !busy) emit('cancel');
            }
        "
    >
        <DialogContent class="sm:max-w-md">
            <DialogHeader>
                <DialogTitle>Bài này thật sự chưa lên TikTok?</DialogTitle>
                <DialogDescription>
                    Chrome không báo được kết quả nên app không biết bài
                    <b>{{ target?.label }}</b>
                    <template v-if="target?.username">
                        của @{{ target.username }}</template
                    >
                    đã lên hay chưa. Hãy mở TikTok Studio và xem cả mục bài đã
                    hẹn giờ. Chỉ bấm đăng lại khi chắc chắn không thấy bài, nếu
                    không sẽ bị đăng trùng.
                </DialogDescription>
            </DialogHeader>
            <DialogFooter class="gap-2">
                <Button
                    variant="outline"
                    :disabled="busy"
                    @click="emit('cancel')"
                    >Thôi</Button
                >
                <Button
                    :disabled="busy"
                    :data-testid="okTestid"
                    @click="emit('confirm')"
                >
                    <Spinner v-if="busy" class="size-4" />
                    Chưa lên, đăng lại
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

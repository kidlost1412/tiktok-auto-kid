<script setup lang="ts">
// Hộp "Xoá / bỏ xếp lịch" ngay trên dòng Lịch đăng: bỏ xếp lịch (video về kho để sửa rồi đăng sau) hoặc xoá hẳn
// (không bao giờ tự xếp lại; file trên ổ đĩa vẫn còn). Bài đã hẹn trên TikTok: app nhờ Chrome xoá bài hẹn và kiểm lại trước.
import { router } from '@inertiajs/vue3';
import { IconBrandTiktok, IconCalendarOff, IconTrash } from '@tabler/icons-vue';
import { computed } from 'vue';
import { toast } from 'vue-sonner';

import type { ScheduleEntry } from '@/components/fork/auto/types';
import {
    PENDING_REMOVE,
    pendingIds,
    postJson,
    undoable,
} from '@/components/fork/auto/undo';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import dayjs from '@/dayjs';

const props = defineProps<{ entry: ScheduleEntry | null }>();
const open = defineModel<boolean>('open', { default: false });

const onTikTok = computed(() => props.entry?.state === 'tiktok_scheduled');

// Có "Hoàn tác": hộp đóng ngay, vài giây sau mới gửi đi.
function run(kind: 'unschedule' | 'remove') {
    const e = props.entry;

    if (!e?.id || pendingIds.has(e.id)) {
        return;
    }

    const name = e.product_label ?? e.product_code ?? 'Video';
    const url = `/auto/videos/${e.id}/${kind === 'remove' ? 'xoa' : 'bo-xep-lich'}`;
    open.value = false;

    undoable(
        kind === 'remove'
            ? `Xoá ${name} (${dayjs(e.at).format('HH:mm DD/MM')}) vào thùng rác`
            : `Bỏ xếp lịch ${name} (${dayjs(e.at).format('HH:mm DD/MM')})`,
        async () => {
            const { ok, data } = await postJson(url);

            if (!ok) {
                toast.error(data?.message ?? 'Không làm được, hãy thử lại');
            } else if (data?.state === 'pending') {
                toast.info(
                    'Đang nhờ Chrome xoá bài hẹn trên TikTok và kiểm lại. Xong là lịch tự cập nhật; không xác minh được thì app giữ nguyên bài.',
                );
            } else {
                toast.success(data?.message ?? 'Đã xong');
            }

            router.reload({ only: ['lich', 'stock', 'products'] });
        },
        {
            id: e.id,
            label: kind === 'remove' ? PENDING_REMOVE : 'Đang chờ bỏ xếp lịch…',
        },
    );
}
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent class="sm:max-w-[460px]" data-testid="fork-auto-remove">
            <DialogHeader>
                <DialogTitle>Xoá bài khỏi lịch</DialogTitle>
                <DialogDescription v-if="entry">
                    {{ entry.product_label ?? entry.product_code ?? 'Video' }} ·
                    {{ dayjs(entry.at).format('HH:mm DD/MM') }}
                    <template v-if="entry.username">
                        · @{{ entry.username }}</template
                    >
                </DialogDescription>
            </DialogHeader>

            <div
                v-if="onTikTok"
                class="flex items-start gap-2 rounded-lg border bg-muted/50 p-3 text-sm text-foreground"
            >
                <IconBrandTiktok
                    class="mt-0.5 size-4 shrink-0 text-muted-foreground"
                />
                <span
                    >Đã hẹn trên TikTok: app xoá bài hẹn trước (cần Chrome đang
                    mở).</span
                >
            </div>

            <div class="grid gap-2">
                <button
                    type="button"
                    class="flex items-start gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-accent disabled:opacity-50"
                    data-testid="fork-auto-remove-unschedule"
                    @click="run('unschedule')"
                >
                    <IconCalendarOff class="mt-0.5 size-4 shrink-0" />
                    <span class="flex flex-col gap-0.5">
                        <b class="text-sm font-medium">Bỏ xếp lịch</b>
                        <span class="text-[0.8125rem] text-muted-foreground"
                            >Video về kho để anh sửa rồi đăng sau.</span
                        >
                    </span>
                </button>
                <button
                    type="button"
                    class="flex items-start gap-3 rounded-lg border border-destructive/30 p-3 text-left transition-colors hover:bg-critical-subtle disabled:opacity-50"
                    data-testid="fork-auto-remove-confirm"
                    @click="run('remove')"
                >
                    <IconTrash
                        class="mt-0.5 size-4 shrink-0 text-destructive-text"
                    />
                    <span class="flex flex-col gap-0.5">
                        <b class="text-sm font-medium text-destructive-text"
                            >Xoá video (vào thùng rác)</b
                        >
                        <span class="text-[0.8125rem] text-muted-foreground"
                            >Bỏ khỏi lịch và khỏi kho, không tự xếp lại. Khôi
                            phục được trong 30 ngày ở Thùng rác.</span
                        >
                    </span>
                </button>
            </div>

            <DialogFooter>
                <Button variant="ghost" @click="open = false">Thôi</Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

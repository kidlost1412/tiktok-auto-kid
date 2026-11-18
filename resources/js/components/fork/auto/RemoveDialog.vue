<script setup lang="ts">
// Hộp "Xoá / bỏ xếp lịch" ngay trên dòng Lịch đăng: bỏ xếp lịch (video về kho để sửa rồi đăng sau) hoặc xoá hẳn
// (không bao giờ tự xếp lại; file trên ổ đĩa vẫn còn). Bài đã hẹn trên TikTok: app nhờ Chrome xoá bài hẹn và kiểm lại trước.
import { router } from '@inertiajs/vue3';
import { IconBrandTiktok, IconCalendarOff, IconTrash } from '@tabler/icons-vue';
import { computed, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import type { ScheduleEntry } from '@/components/fork/auto/types';
import { postJson, undoable } from '@/components/fork/auto/undo';
import { toneClasses } from '@/components/fork/shared/status';
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
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{ entry: ScheduleEntry | null }>();
const open = defineModel<boolean>('open', { default: false });

const busy = ref<'unschedule' | 'remove' | null>(null);
const problem = ref('');
const done = ref('');
const changed = ref(false);

const onTikTok = computed(() => props.entry?.state === 'tiktok_scheduled');

watch(open, (v) => {
    if (v) {
        problem.value = '';
        done.value = '';
        changed.value = false;
    } else if (changed.value) {
        router.reload({ only: ['lich', 'stock', 'products'] });
    }
});

// Có "Hoàn tác": hộp đóng ngay, vài giây sau mới gửi đi.
function run(kind: 'unschedule' | 'remove') {
    const e = props.entry;

    if (!e?.id) {
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
                toast.error(data?.message ?? 'Không làm được, hãy thử lại.');
            } else if (data?.state === 'pending') {
                toast.info(
                    'Đang nhờ Chrome xoá bài hẹn trên TikTok và kiểm lại. Xong là lịch tự cập nhật; không xác minh được thì app giữ nguyên bài.',
                );
            } else {
                toast.success(data?.message ?? 'Đã xong.');
            }

            router.reload({ only: ['lich', 'stock', 'products'] });
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
                v-if="onTikTok && !done"
                :class="
                    cn(
                        'flex items-start gap-2 rounded-lg border p-2.5 text-sm',
                        toneClasses.info.box,
                    )
                "
            >
                <IconBrandTiktok class="mt-0.5 size-4 shrink-0" />
                <span
                    >Đã hẹn trên TikTok: app xoá bài hẹn trước (cần Chrome đang
                    mở).</span
                >
            </div>

            <div
                v-if="done"
                :class="
                    cn(
                        'rounded-lg border p-2.5 text-sm',
                        toneClasses.success.box,
                    )
                "
                data-testid="fork-auto-remove-done"
            >
                {{ done }}
            </div>
            <div
                v-if="problem"
                :class="
                    cn(
                        'rounded-lg border p-2.5 text-sm',
                        toneClasses.danger.box,
                    )
                "
                data-testid="fork-auto-remove-problem"
            >
                {{ problem }}
            </div>

            <div v-if="!done" class="grid gap-2">
                <button
                    type="button"
                    class="flex items-start gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-accent disabled:opacity-50"
                    :disabled="!!busy"
                    data-testid="fork-auto-remove-unschedule"
                    @click="run('unschedule')"
                >
                    <Spinner
                        v-if="busy === 'unschedule'"
                        class="mt-0.5 size-4"
                    />
                    <IconCalendarOff v-else class="mt-0.5 size-4 shrink-0" />
                    <span class="flex flex-col gap-0.5">
                        <b class="text-sm font-medium">Bỏ xếp lịch</b>
                        <span class="text-[0.8125rem] text-muted-foreground"
                            >Video về kho để anh sửa rồi đăng sau.</span
                        >
                    </span>
                </button>
                <button
                    type="button"
                    class="flex items-start gap-3 rounded-lg border border-red-200 p-3 text-left transition-colors hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:hover:bg-red-950/30"
                    :disabled="!!busy"
                    data-testid="fork-auto-remove-confirm"
                    @click="run('remove')"
                >
                    <Spinner v-if="busy === 'remove'" class="mt-0.5 size-4" />
                    <IconTrash
                        v-else
                        class="mt-0.5 size-4 shrink-0 text-red-600 dark:text-red-400"
                    />
                    <span class="flex flex-col gap-0.5">
                        <b
                            class="text-sm font-medium text-red-700 dark:text-red-400"
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
                <Button variant="ghost" @click="open = false">{{
                    done ? 'Đóng' : 'Thôi'
                }}</Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

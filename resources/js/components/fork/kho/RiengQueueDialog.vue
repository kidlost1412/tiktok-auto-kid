<script setup lang="ts">
// "Giỏ chờ đăng": các video riêng đã chọn sẵn, chưa hẹn giờ. Không phải giỏ hàng TikTok Shop.
import { IconAlertTriangle, IconClipboardList, IconMovie, IconX } from '@tabler/icons-vue';
import { ref } from 'vue';

import { fmtDuration } from '@/components/fork/kho/kho';
import type { QueueItem } from '@/components/fork/kho/rieng';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';

defineProps<{ open: boolean; queue: QueueItem[] }>();

const emit = defineEmits<{
    'update:open': [value: boolean];
    remove: [id: number];
    clear: [];
    post: [];
    view: [id: number];
}>();

const failed = ref<Record<number, boolean>>({});
</script>

<template>
    <Dialog :open="open" @update:open="emit('update:open', $event)">
        <DialogContent class="flex max-h-[88dvh] max-w-xl flex-col overflow-hidden" data-testid="fork-rieng-queue-dialog">
            <DialogHeader>
                <DialogTitle class="flex items-center gap-2">
                    <IconClipboardList class="size-5" /> Giỏ chờ đăng · {{ queue.length }} video
                </DialogTitle>
                <DialogDescription>
                    Nơi để dành các video bạn định đăng sau. Video được hẹn giờ xong sẽ tự rời khỏi giỏ. (Đây không phải giỏ hàng TikTok Shop.)
                </DialogDescription>
            </DialogHeader>

            <p v-if="!queue.length" class="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                Giỏ đang trống. Bấm “+ Giỏ chờ” trên video, hoặc chọn nhiều video rồi bấm “Thêm vào giỏ chờ”.
            </p>

            <ul v-else class="-mx-1 flex min-h-0 flex-1 flex-col divide-y overflow-y-auto rounded-lg border">
                <li v-for="q in queue" :key="q.id" class="flex items-center gap-3 p-2.5" :data-testid="`fork-rieng-queue-item-${q.id}`">
                    <button type="button" class="flex min-w-0 flex-1 items-center gap-3 text-left" @click="emit('view', q.id)">
                        <span class="relative h-14 w-10 shrink-0 overflow-hidden rounded border bg-muted">
                            <img v-if="!failed[q.id]" :src="`/auto/kho/rieng/video/${q.id}/thumb`" alt="" loading="lazy" class="size-full object-cover" @error="failed[q.id] = true" />
                            <IconMovie v-else class="absolute inset-0 m-auto size-5 text-muted-foreground" />
                        </span>
                        <span class="min-w-0 flex-1">
                            <span class="block truncate text-sm font-medium">{{ q.file_name }}</span>
                            <span v-if="q.duration" class="text-xs text-muted-foreground">{{ fmtDuration(q.duration) }}</span>
                            <span v-if="q.duplicate" class="mt-0.5 flex items-start gap-1 text-xs text-amber-800 dark:text-amber-300">
                                <IconAlertTriangle class="mt-px size-3.5 shrink-0" /> {{ q.duplicate }}
                            </span>
                        </span>
                    </button>
                    <Button size="icon" variant="ghost" class="size-8 shrink-0" :aria-label="`Bỏ ${q.file_name} khỏi giỏ`" title="Bỏ khỏi giỏ" @click="emit('remove', q.id)">
                        <IconX class="size-4" />
                    </Button>
                </li>
            </ul>

            <div class="flex flex-wrap items-center justify-end gap-2 pt-2">
                <Button variant="ghost" :disabled="!queue.length" @click="emit('clear')">Xoá hết giỏ</Button>
                <Button variant="outline" @click="emit('update:open', false)">Đóng</Button>
                <Button :disabled="!queue.length" data-testid="fork-rieng-queue-post" @click="emit('post')">
                    Đăng cả giỏ ({{ queue.length }})
                </Button>
            </div>
        </DialogContent>
    </Dialog>
</template>

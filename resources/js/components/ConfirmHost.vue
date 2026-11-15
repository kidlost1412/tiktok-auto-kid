<script setup lang="ts">
// Vẽ hộp xác nhận của useConfirm(). Gắn đúng một lần trong AppLayout.
import { IconAlertTriangle, IconHelp } from '@tabler/icons-vue';
import { nextTick, ref } from 'vue';

import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { useConfirmState } from '@/composables/useConfirm';

const { state, settle } = useConfirmState();

const cancelBtn = ref<InstanceType<typeof Button> | null>(null);
const okBtn = ref<InstanceType<typeof Button> | null>(null);

// Việc nguy hiểm thì mặc định dừng ở nút Huỷ để Enter không lỡ tay.
function focusDefault(ev: Event): void {
    ev.preventDefault();
    void nextTick(() => {
        const target = state.destructive ? cancelBtn.value : okBtn.value;
        (target?.$el as HTMLElement | undefined)?.focus();
    });
}

function onOpenChange(open: boolean): void {
    if (!open) settle(false);
}
</script>

<template>
    <Dialog :open="state.open" @update:open="onOpenChange">
        <DialogContent
            class="sm:max-w-md"
            :show-close-button="false"
            :fullscreen-on-mobile="false"
            data-testid="confirm-dialog"
            @open-auto-focus="focusDefault"
        >
            <DialogHeader>
                <div class="flex items-start gap-3">
                    <span
                        class="grid size-10 shrink-0 place-items-center rounded-full"
                        :class="
                            state.destructive
                                ? 'bg-critical/15 text-critical'
                                : 'bg-primary/15 text-primary-text'
                        "
                        aria-hidden="true"
                    >
                        <IconAlertTriangle
                            v-if="state.destructive"
                            class="size-5"
                        />
                        <IconHelp v-else class="size-5" />
                    </span>
                    <div class="flex min-w-0 flex-1 flex-col gap-1.5 text-left">
                        <DialogTitle>{{ state.title }}</DialogTitle>
                        <DialogDescription
                            v-if="state.description"
                            class="text-sm break-words text-muted-foreground"
                        >
                            {{ state.description }}
                        </DialogDescription>
                    </div>
                </div>
            </DialogHeader>
            <DialogFooter>
                <Button
                    ref="cancelBtn"
                    type="button"
                    variant="ghost"
                    @click="settle(false)"
                >
                    {{ state.cancelText ?? 'Huỷ' }}
                </Button>
                <Button
                    ref="okBtn"
                    type="button"
                    :variant="state.destructive ? 'destructive' : 'default'"
                    @click="settle(true)"
                >
                    {{ state.confirmText ?? 'Đồng ý' }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

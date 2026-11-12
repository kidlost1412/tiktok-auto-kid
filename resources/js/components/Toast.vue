<script setup lang="ts">
import { router, usePage } from '@inertiajs/vue3';
import { onBeforeUnmount, watch } from 'vue';
import { toast } from 'vue-sonner';

import { Toaster } from '@/components/ui/sonner';

type Flash = {
    banner?: string;
    bannerStyle?: 'success' | 'danger' | 'warning' | 'info';
    success?: string;
    error?: string;
    warning?: string;
    info?: string;
};

const page = usePage();

// Các lần tải lại một phần (usePoll / router.reload({ only })) làm Inertia gán lại props.flash dù
// nội dung không đổi; không được hiện lại toast cũ mỗi lần như vậy.
let lastKey = '';
let partialVisit = false;

const offStart = router.on('start', (event) => {
    partialVisit = (event.detail.visit.only?.length ?? 0) > 0;
});

onBeforeUnmount(() => offStart());

watch(
    () => page.props.flash as Flash | undefined,
    (flash) => {
        const key = JSON.stringify(flash ?? {});
        const repeated = key === lastKey;
        lastKey = key;

        if (!flash || (repeated && partialVisit)) {
            return;
        }

        if (flash.banner) {
            switch (flash.bannerStyle) {
                case 'danger':
                    toast.error(flash.banner, { id: 'flash-banner', testId: 'flash-banner-toast' });
                    break;
                case 'warning':
                    toast.warning(flash.banner, { id: 'flash-banner', testId: 'flash-banner-toast' });
                    break;
                case 'info':
                    toast.info(flash.banner, { id: 'flash-banner', testId: 'flash-banner-toast' });
                    break;
                case 'success':
                default:
                    toast.success(flash.banner, { id: 'flash-banner', testId: 'flash-banner-toast' });
            }
        }

        if (flash.success) {
            toast.success(flash.success, { id: 'flash-success' });
        }

        if (flash.error) {
            toast.error(flash.error, { id: 'flash-error' });
        }

        if (flash.warning) {
            toast.warning(flash.warning, { id: 'flash-warning' });
        }

        if (flash.info) {
            toast.info(flash.info, { id: 'flash-info' });
        }
    },
    { deep: true, immediate: true },
);
</script>

<template>
    <Toaster />
</template>

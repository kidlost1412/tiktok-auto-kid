<script setup lang="ts">
// Khung chung của khu "Tự động đăng": đầu trang thống nhất + thanh điều hướng 5 mục + hiệu ứng vào trang.
import { Head, Link, usePage } from '@inertiajs/vue3';
import {
    IconBuildingWarehouse,
    IconCalendarEvent,
    IconChartBar,
    IconPhotoEdit,
    IconRobot,
    IconShoppingCart,
} from '@tabler/icons-vue';
import { computed } from 'vue';

import VideoViewer from '@/components/fork/shared/VideoViewer.vue';
import AppLayout from '@/layouts/AppLayout.vue';
import { cn } from '@/lib/utils';

defineProps<{
    title: string;
    description?: string;
    testid?: string;
}>();

const page = usePage();
const buyBadge = computed(() =>
    Number(
        (page.props as { fork_badges?: { buy_comments?: number } | null })
            .fork_badges?.buy_comments ?? 0,
    ),
);
const path = computed(() => page.url.split('?')[0].replace(/\/+$/, '') || '/');

const items = [
    {
        href: '/auto',
        label: 'Tổng quan & Lịch',
        icon: IconCalendarEvent,
        exact: true,
    },
    { href: '/auto/kho', label: 'Kho video', icon: IconBuildingWarehouse },
    { href: '/auto/gio-hang', label: 'Giỏ hàng', icon: IconShoppingCart },
    {
        href: '/auto/anh-bia-hashtag',
        label: 'Ảnh bìa & hashtag',
        icon: IconPhotoEdit,
    },
    { href: '/auto/so-lieu', label: 'Số liệu', icon: IconChartBar },
];

const active = (i: (typeof items)[number]) =>
    i.exact ? path.value === i.href : path.value.startsWith(i.href);
</script>

<template>
    <Head :title="`${title} · Tự động đăng`" />

    <AppLayout title="Tự động đăng" :icon="IconRobot" full-width>
        <div
            class="mx-auto flex w-full max-w-[1600px] flex-col px-4 pb-16 sm:px-8"
            :data-testid="testid"
        >
            <header class="flex flex-col gap-4 pt-6">
                <div
                    class="flex flex-wrap items-start justify-between gap-x-6 gap-y-3"
                >
                    <div class="min-w-0">
                        <h1
                            class="font-heading text-3xl font-semibold tracking-tight"
                        >
                            {{ title }}
                        </h1>
                        <p
                            v-if="description"
                            class="mt-1.5 max-w-3xl text-base text-muted-foreground"
                        >
                            {{ description }}
                        </p>
                    </div>
                    <div
                        v-if="$slots.actions"
                        class="flex flex-wrap items-center gap-2"
                    >
                        <slot name="actions" />
                    </div>
                </div>

                <nav
                    class="-mx-4 flex gap-2 overflow-x-auto border-b px-4 sm:-mx-8 sm:px-8"
                    aria-label="Khu Tự động đăng"
                    data-testid="fork-auto-subnav"
                >
                    <Link
                        v-for="i in items"
                        :key="i.href"
                        :href="i.href"
                        :aria-current="active(i) ? 'page' : undefined"
                        :class="
                            cn(
                                'relative inline-flex shrink-0 items-center gap-2.5 px-4 py-3.5 text-base font-medium whitespace-nowrap transition-colors',
                                'after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:rounded-full after:bg-primary after:opacity-0 after:transition-opacity',
                                active(i)
                                    ? 'text-foreground after:opacity-100'
                                    : 'text-muted-foreground hover:text-foreground',
                            )
                        "
                    >
                        <component :is="i.icon" class="size-5" />
                        {{ i.label }}
                        <span
                            v-if="i.href === '/auto/so-lieu' && buyBadge > 0"
                            class="rounded-full bg-amber-500 px-2 text-xs leading-6 font-semibold text-white"
                            title="Bình luận hỏi mua trong 24 giờ qua"
                            data-testid="fork-badge-buy-comments"
                            >{{ buyBadge }}</span
                        >
                    </Link>
                </nav>
            </header>

            <main
                class="flex animate-in flex-col gap-10 pt-8 duration-300 fade-in slide-in-from-bottom-1"
            >
                <slot />
            </main>
        </div>
        <VideoViewer />
    </AppLayout>
</template>

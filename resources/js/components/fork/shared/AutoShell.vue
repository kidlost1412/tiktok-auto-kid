<script setup lang="ts">
// Khung chung của khu "Tự động đăng": đầu trang thống nhất + thanh điều hướng 5 mục + hiệu ứng vào trang.
import { Head, Link, usePage } from '@inertiajs/vue3';
import {
    IconBuildingWarehouse,
    IconCalendarEvent,
    IconChartBar,
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
    { href: '/auto/so-lieu', label: 'Số liệu', icon: IconChartBar },
];

const active = (i: (typeof items)[number]) =>
    i.exact ? path.value === i.href : path.value.startsWith(i.href);
</script>

<template>
    <Head :title="`${title} · Tự động đăng`" />

    <AppLayout title="Tự động đăng" :icon="IconRobot" full-width>
        <div
            class="flex w-full flex-col px-4 pb-20 sm:px-6"
            :data-testid="testid"
        >
            <header class="flex flex-col gap-5 pt-6">
                <div
                    class="flex flex-wrap items-end justify-between gap-x-6 gap-y-3"
                >
                    <div class="min-w-[min(100%,20rem)] flex-1 basis-0">
                        <h1
                            class="font-heading text-[1.375rem] leading-tight font-[650] tracking-[-0.022em]"
                        >
                            {{ title }}
                        </h1>
                        <p
                            v-if="description"
                            class="mt-1 max-w-3xl text-sm text-muted-foreground"
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
                    class="flex w-fit max-w-full gap-0.5 overflow-x-auto rounded-xl border bg-secondary/50 p-1 dark:bg-muted/60"
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
                                'inline-flex h-9 shrink-0 items-center gap-2 rounded-[9px] px-3.5 text-sm font-medium whitespace-nowrap transition-[background-color,color,box-shadow] focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none',
                                active(i)
                                    ? 'bg-card font-semibold text-foreground shadow-[0_1px_2px_rgba(28,25,23,.08),0_1px_1px_rgba(28,25,23,.04)] dark:bg-[#2a2e3a] dark:shadow-[inset_0_1px_0_rgba(255,255,255,.06),0_1px_3px_rgba(0,0,0,.5)]'
                                    : 'text-muted-foreground hover:text-foreground',
                            )
                        "
                    >
                        <component
                            :is="i.icon"
                            :class="
                                cn(
                                    'size-[18px]',
                                    active(i)
                                        ? 'text-primary-text'
                                        : 'opacity-80',
                                )
                            "
                        />
                        {{ i.label }}
                        <span
                            v-if="i.href === '/auto/so-lieu' && buyBadge > 0"
                            class="rounded-full bg-amber-500 px-2 text-xs leading-5 font-semibold text-amber-950"
                            title="Bình luận hỏi mua trong 24 giờ qua"
                            data-testid="fork-badge-buy-comments"
                            >{{ buyBadge }}</span
                        >
                    </Link>
                </nav>
            </header>

            <main
                class="flex animate-in flex-col gap-6 pt-6 duration-300 fade-in slide-in-from-bottom-1"
            >
                <slot />
            </main>
        </div>
        <VideoViewer />
    </AppLayout>
</template>

<script setup lang="ts">
// Khung chung của app: thanh trên cùng (Tự động đăng / Kết nối Chrome) + nội dung + thông báo.
import { Link, usePage } from '@inertiajs/vue3';
import {
    IconBrandChrome,
    IconBrandTelegram,
    IconBrandTiktok,
    IconCloudDownload,
    IconHome,
    IconMoon,
    IconMovie,
    IconRobot,
    IconSun,
} from '@tabler/icons-vue';
import { computed, ref, type Component } from 'vue';

import Toast from '@/components/Toast.vue';
import { cn } from '@/lib/utils';

defineProps<{
    fullWidth?: boolean;
    title?: string;
    icon?: Component;
}>();

const page = usePage();
const path = computed(() => page.url.split('?')[0]);
const links = [
    { href: '/nha', label: 'Xưởng nhỏ', icon: IconHome },
    { href: '/auto', label: 'Tự động đăng', icon: IconRobot },
    { href: '/xuong', label: 'Xưởng Video', icon: IconMovie },
    { href: '/settings/chrome', label: 'Kết nối Chrome', icon: IconBrandChrome },
    { href: '/settings/telegram', label: 'Telegram', icon: IconBrandTelegram },
    { href: '/settings/cap-nhat', label: 'Cập nhật', icon: IconCloudDownload },
];
const dark = ref(document.documentElement.classList.contains('dark'));
const setTheme = (isDark: boolean) => {
    dark.value = isDark;
    document.documentElement.classList.toggle('dark', isDark);

    try {
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    } catch {
        // không lưu được thì chỉ áp cho lần xem này
    }
};
const active = (href: string) => path.value.startsWith(href);
</script>

<template>
    <div class="flex min-h-screen flex-col bg-background text-foreground">
        <header
            class="sticky top-0 z-30 shrink-0 border-b border-border bg-background/85 backdrop-blur-md backdrop-saturate-150"
            data-testid="app-header"
        >
            <div
                class="mx-auto flex h-[62px] w-full max-w-[1880px] items-center gap-4 px-4 md:px-8"
            >
                <Link href="/nha" class="flex shrink-0 items-center gap-2.5">
                    <span
                        class="grid size-[34px] place-items-center rounded-[10px] bg-linear-to-br from-violet-500 to-violet-700 text-white shadow-[0_6px_14px_-4px_rgb(109_40_217/0.5),inset_0_1px_0_rgb(255_255_255/0.25)]"
                    >
                        <IconBrandTiktok class="size-[18px]" />
                    </span>
                    <span
                        class="hidden text-[17px] font-semibold tracking-[-0.015em] whitespace-nowrap sm:inline"
                        >TikTok Auto Kid</span
                    >
                </Link>
                <nav
                    class="flex items-center gap-0.5 overflow-x-auto rounded-xl border border-border bg-secondary/60 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
                    aria-label="Điều hướng chính"
                >
                    <Link
                        v-for="l in links"
                        :key="l.href"
                        :href="l.href"
                        :aria-current="active(l.href) ? 'page' : undefined"
                        :class="
                            cn(
                                'inline-flex h-9 items-center gap-1.5 rounded-[9px] px-2.5 text-[15px] font-medium whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground',
                                active(l.href) &&
                                    'bg-card font-semibold text-foreground shadow-[0_1px_2px_rgb(28_25_23/0.08),0_1px_1px_rgb(28_25_23/0.04)] dark:bg-accent dark:shadow-[inset_0_1px_0_rgb(255_255_255/0.06),0_1px_3px_rgb(0_0_0/0.5)]',
                            )
                        "
                    >
                        <component
                            :is="l.icon"
                            :class="
                                cn(
                                    'size-[17px] opacity-80',
                                    active(l.href) && 'text-primary-text opacity-100',
                                )
                            "
                        />
                        {{ l.label }}
                    </Link>
                </nav>
                <div
                    class="ml-auto inline-flex shrink-0 gap-0.5 rounded-xl border border-border bg-secondary/60 p-1"
                    role="group"
                    aria-label="Giao diện"
                    data-testid="theme-toggle"
                >
                    <button
                        v-for="o in [
                            { v: false, label: 'Sáng', icon: IconSun },
                            { v: true, label: 'Tối', icon: IconMoon },
                        ]"
                        :key="o.label"
                        type="button"
                        :aria-pressed="dark === o.v"
                        :class="
                            cn(
                                'inline-flex h-9 items-center gap-1.5 rounded-[9px] px-3 text-sm font-medium transition-colors',
                                dark === o.v
                                    ? 'bg-card font-semibold text-foreground shadow-[0_1px_2px_rgb(28_25_23/0.08)] dark:bg-accent'
                                    : 'text-muted-foreground hover:text-foreground',
                            )
                        "
                        @click="setTheme(o.v)"
                    >
                        <component
                            :is="o.icon"
                            :class="cn('size-4', dark === o.v && 'text-primary-text')"
                        />
                        {{ o.label }}
                    </button>
                </div>
            </div>
        </header>
        <main
            :class="cn('flex min-w-0 flex-1 flex-col', !fullWidth && 'mx-auto w-full max-w-[1880px]')"
            data-testid="app-layout-content"
        >
            <slot />
        </main>
        <Toast />
    </div>
</template>

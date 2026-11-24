<script setup lang="ts">
// Khung chung của app: thanh trên cùng (Tự động đăng / Kết nối Chrome) + nội dung + thông báo.
import { Link, usePage } from '@inertiajs/vue3';
import {
    IconBrandTiktok,
    IconHome,
    IconMoon,
    IconMovie,
    IconRobot,
    IconSearch,
    IconSettings,
    IconSun,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref, type Component } from 'vue';

import ConfirmHost from '@/components/ConfirmHost.vue';
import AttentionBell from '@/components/fork/shared/AttentionBell.vue';
import QuickSearch from '@/components/fork/shared/QuickSearch.vue';
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
    { href: '/nha', label: 'Khu Tự Trị', icon: IconHome },
    { href: '/auto', label: 'Tự động đăng', icon: IconRobot },
    { href: '/xuong', label: 'Xưởng Video', icon: IconMovie },
    { href: '/settings', label: 'Cài đặt', icon: IconSettings },
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

// Chấm đỏ trên "Cài đặt" khi Chrome mất kết nối hoặc có bản cập nhật đang chờ (số liệu từ `fork_badges`).
const settingsAlert = computed(() => {
    const b = (
        page.props as {
            fork_badges?: {
                chrome_offline?: number;
                update_available?: boolean;
            } | null;
        }
    ).fork_badges;

    if (!b) {
        return null;
    }

    const parts: string[] = [];

    if ((b.chrome_offline ?? 0) > 0) {
        parts.push('Chrome chưa kết nối');
    }

    if (b.update_available) {
        parts.push('có bản cập nhật mới');
    }

    return parts.length ? parts.join(', ') : null;
});

const linkTitle = (l: { href: string; label: string }) =>
    l.href === '/settings' && settingsAlert.value
        ? `${l.label} (${settingsAlert.value})`
        : l.label;

// "Tìm nhanh": Ctrl+K (hoặc Cmd+K) ở mọi trang.
const searchOpen = ref(false);
const onGlobalKey = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchOpen.value = !searchOpen.value;
    }
};
onMounted(() => window.addEventListener('keydown', onGlobalKey));
onBeforeUnmount(() => window.removeEventListener('keydown', onGlobalKey));
</script>

<template>
    <div class="flex min-h-screen flex-col bg-background text-foreground">
        <header
            class="sticky top-0 z-30 shrink-0 border-b border-border bg-background"
            data-testid="app-header"
        >
            <div
                class="flex h-[62px] w-full items-center gap-2 px-3 md:gap-4 md:px-6"
            >
                <Link href="/nha" class="flex shrink-0 items-center gap-2.5">
                    <span
                        class="grid size-8 place-items-center rounded-lg bg-primary-strong text-white"
                    >
                        <IconBrandTiktok class="size-[18px]" />
                    </span>
                    <span
                        class="hidden text-[1.0625rem] font-semibold whitespace-nowrap xl:inline"
                        >TikTok Auto Kid</span
                    >
                </Link>
                <nav
                    class="flex min-w-0 [scrollbar-width:none] items-center gap-0.5 overflow-x-auto rounded-xl border border-border bg-secondary/60 [mask-image:linear-gradient(to_right,transparent,#000_8px,#000_calc(100%-20px),transparent)] p-1 md:[mask-image:none] [&::-webkit-scrollbar]:hidden"
                    aria-label="Điều hướng chính"
                >
                    <Link
                        v-for="l in links"
                        :key="l.href"
                        :href="l.href"
                        :title="linkTitle(l)"
                        :aria-current="active(l.href) ? 'page' : undefined"
                        :class="
                            cn(
                                'relative inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg px-3 text-[0.9375rem] font-medium whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground',
                                active(l.href) &&
                                    'bg-card text-foreground shadow-[0_1px_2px_rgb(28_25_23/0.08)] dark:bg-accent dark:shadow-none',
                            )
                        "
                    >
                        <component :is="l.icon" class="size-4" />
                        <span :class="active(l.href) ? '' : 'max-md:sr-only'">{{
                            l.label
                        }}</span>
                        <span
                            v-if="l.href === '/settings' && settingsAlert"
                            class="absolute top-1 right-1 size-2 rounded-full bg-red-500 ring-2 ring-background"
                            data-testid="settings-alert-dot"
                            ><span class="sr-only">{{
                                settingsAlert
                            }}</span></span
                        >
                    </Link>
                </nav>
                <div class="ml-auto flex shrink-0 items-center gap-2">
                    <button
                        type="button"
                        class="inline-flex h-[38px] shrink-0 items-center gap-2 rounded-xl border border-border bg-secondary/60 px-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                        aria-label="Tìm nhanh (Ctrl+K)"
                        title="Tìm nhanh (Ctrl+K)"
                        data-testid="quick-search-open"
                        @click="searchOpen = true"
                    >
                        <IconSearch class="size-[17px]" />
                        <span class="hidden min-[1400px]:inline"
                            >Tìm nhanh</span
                        >
                        <kbd
                            class="hidden rounded border border-border bg-background px-1.5 text-[0.6875rem] leading-5 min-[1400px]:inline"
                            >Ctrl K</kbd
                        >
                    </button>
                    <AttentionBell />
                    <div
                        class="inline-flex shrink-0 gap-0.5 rounded-xl border border-border bg-secondary/60 p-1"
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
                            :aria-label="o.label"
                            :title="`Giao diện ${o.label.toLowerCase()}`"
                            :class="
                                cn(
                                    'inline-flex h-9 items-center gap-1.5 rounded-lg px-2 text-sm font-medium transition-colors sm:px-3',
                                    dark === o.v
                                        ? 'bg-card text-foreground shadow-[0_1px_2px_rgb(28_25_23/0.08)] dark:bg-accent dark:shadow-none'
                                        : 'text-muted-foreground hover:text-foreground',
                                )
                            "
                            @click="setTheme(o.v)"
                        >
                            <component :is="o.icon" class="size-4" />
                            <span class="hidden min-[1400px]:inline">{{
                                o.label
                            }}</span>
                        </button>
                    </div>
                </div>
            </div>
        </header>
        <main
            :class="cn('flex min-w-0 flex-1 flex-col', !fullWidth && 'w-full')"
            data-testid="app-layout-content"
        >
            <slot />
        </main>
        <Toast />
        <ConfirmHost />
        <QuickSearch v-model:open="searchOpen" />
    </div>
</template>

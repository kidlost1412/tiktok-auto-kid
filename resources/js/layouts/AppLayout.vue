<script setup lang="ts">
// Khung chung của app: thanh trên cùng (Tự động đăng / Kết nối Chrome) + nội dung + thông báo.
import { Link, usePage } from '@inertiajs/vue3';
import { IconMoon, IconSun } from '@tabler/icons-vue';
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
    { href: '/auto', label: 'Tự động đăng' },
    { href: '/xuong', label: 'Xưởng Video' },
    { href: '/settings/chrome', label: 'Kết nối Chrome' },
    { href: '/settings/telegram', label: 'Telegram' },
    { href: '/settings/cap-nhat', label: 'Cập nhật' },
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
            class="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-8 border-b border-border bg-background/90 px-4 backdrop-blur md:px-8"
            data-testid="app-header"
        >
            <span class="font-heading text-xl font-semibold tracking-tight">TikTok Auto Kid</span>
            <nav class="flex items-center gap-2 text-base">
                <Link
                    v-for="l in links"
                    :key="l.href"
                    :href="l.href"
                    :class="
                        cn(
                            'rounded-lg px-3.5 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                            active(l.href) && 'bg-accent font-medium text-foreground',
                        )
                    "
                >
                    {{ l.label }}
                </Link>
            </nav>
            <div
                class="ml-auto inline-flex rounded-lg border border-border-strong bg-card p-1"
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
                            'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                            dark === o.v
                                ? 'bg-primary text-primary-foreground'
                                : 'text-muted-foreground hover:text-foreground',
                        )
                    "
                    @click="setTheme(o.v)"
                >
                    <component :is="o.icon" class="size-4" />
                    {{ o.label }}
                </button>
            </div>
        </header>
        <main
            :class="cn('flex min-w-0 flex-1 flex-col', !fullWidth && 'mx-auto w-full max-w-[1600px]')"
            data-testid="app-layout-content"
        >
            <slot />
        </main>
        <Toast />
    </div>
</template>

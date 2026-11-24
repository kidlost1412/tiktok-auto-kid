<script setup lang="ts">
// Chuông "Cần chú ý" trên thanh trên cùng: gom những việc đáng xem ngay (Chrome mất kết nối, bài đăng lỗi,
// bản cập nhật, bình luận hỏi mua) và dẫn tới đúng trang. Số liệu lấy từ `fork_badges` (máy chủ giữ cache ngắn).
import { usePage } from '@inertiajs/vue3';
import { IconBell } from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import { goTo } from '@/components/fork/shared/nav';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';

interface Badges {
    buy_comments?: number;
    chrome_offline?: number;
    failed_24h?: number;
    update_available?: boolean;
}

const page = usePage();
const badges = computed(
    () => (page.props as { fork_badges?: Badges | null }).fork_badges ?? null,
);

const items = computed(() => {
    const b = badges.value;

    if (!b) {
        return [];
    }

    const out: {
        key: string;
        text: string;
        hint: string;
        href: string;
        tone: 'red' | 'amber' | 'sky';
    }[] = [];

    if ((b.chrome_offline ?? 0) > 0) {
        out.push({
            key: 'chrome',
            text: `${b.chrome_offline} kênh chưa có Chrome kết nối`,
            hint: 'Mở Chrome (đúng hồ sơ có tài khoản đó) để app đăng được bài.',
            href: '/settings#chrome',
            tone: 'red',
        });
    }

    if ((b.failed_24h ?? 0) > 0) {
        out.push({
            key: 'failed',
            text: `${b.failed_24h} bài đăng lỗi trong 24 giờ qua`,
            hint: 'Mở Kho video, mục Lỗi, để xem lý do và thử lại.',
            href: '/auto/kho?tab=loi',
            tone: 'red',
        });
    }

    if (b.update_available) {
        out.push({
            key: 'update',
            text: 'Có bản cập nhật mới',
            hint: 'Cập nhật một chạm trong Cài đặt, dữ liệu được sao lưu trước.',
            href: '/settings#cap-nhat',
            tone: 'sky',
        });
    }

    if ((b.buy_comments ?? 0) > 0) {
        out.push({
            key: 'buy',
            text: `${b.buy_comments} bình luận hỏi mua trong 24 giờ qua`,
            hint: 'Xem ở Số liệu để trả lời khách.',
            href: '/auto/so-lieu',
            tone: 'amber',
        });
    }

    return out;
});

const dot = {
    red: 'bg-red-500',
    amber: 'bg-amber-500',
    sky: 'bg-sky-500',
} as const;

const open = ref(false);

const go = (href: string) => {
    open.value = false;
    goTo(href);
};
</script>

<template>
    <Popover v-if="badges" v-model:open="open">
        <PopoverTrigger as-child>
            <button
                type="button"
                :class="
                    cn(
                        'relative inline-flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-secondary/60 text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none',
                    )
                "
                :aria-label="
                    items.length
                        ? `Cần chú ý (${items.length})`
                        : 'Cần chú ý (không có gì)'
                "
                title="Cần chú ý"
                data-testid="attention-bell"
            >
                <IconBell class="size-[18px]" />
                <span
                    v-if="items.length"
                    class="absolute -top-1 -right-1 grid min-w-[18px] place-items-center rounded-full bg-red-500 px-1 text-[0.6875rem] leading-[18px] font-semibold text-white"
                    data-testid="attention-bell-count"
                    >{{ items.length }}</span
                >
            </button>
        </PopoverTrigger>
        <PopoverContent
            align="end"
            class="w-80 p-1.5"
            data-testid="attention-bell-list"
        >
            <p
                v-if="!items.length"
                class="px-3 py-6 text-center text-sm text-muted-foreground"
            >
                Không có gì cần chú ý lúc này
            </p>
            <button
                v-for="i in items"
                :key="i.key"
                type="button"
                class="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-accent"
                :data-testid="`attention-${i.key}`"
                @click="go(i.href)"
            >
                <span
                    :class="
                        cn('mt-1.5 size-2 shrink-0 rounded-full', dot[i.tone])
                    "
                />
                <span class="min-w-0">
                    <span class="block text-sm font-medium">{{
                        i.text
                    }}</span>
                    <span class="block text-xs text-muted-foreground">{{
                        i.hint
                    }}</span>
                </span>
            </button>
        </PopoverContent>
    </Popover>
</template>

<script setup lang="ts">
// "Tìm nhanh" (Ctrl+K): gõ vài chữ rồi Enter để nhảy tới một trang, một mục Cài đặt hay một việc cần làm.
// Chỉ gồm các đường dẫn thường (không thao tác gì tự chạy). Tìm không phân biệt dấu.
import { IconSearch } from '@tabler/icons-vue';
import { computed, nextTick, ref, watch } from 'vue';

import { goTo } from '@/components/fork/shared/nav';
import { norm } from '@/components/fork/shared/text';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

const open = defineModel<boolean>('open', { default: false });

interface Item {
    label: string;
    href: string;
    group: string;
    /** Từ khoá thêm để tìm ra mục này. */
    keywords?: string;
}

const items: Item[] = [
    {
        group: 'Trang',
        label: 'Khu Tự Trị',
        href: '/nha',
        keywords: 'nhà đạo diễn',
    },
    {
        group: 'Trang',
        label: 'Xưởng Video',
        href: '/xuong',
        keywords: 'làm video sản xuất hub',
    },
    {
        group: 'Tự động đăng',
        label: 'Tổng quan & Lịch',
        href: '/auto',
        keywords: 'tự động đăng lịch đăng bài hẹn giờ',
    },
    {
        group: 'Tự động đăng',
        label: 'Kho video',
        href: '/auto/kho',
        keywords: 'video chờ đăng đã đăng',
    },
    {
        group: 'Tự động đăng',
        label: 'Kho riêng',
        href: '/auto/kho/rieng',
        keywords: 'video tự làm thư mục riêng',
    },
    {
        group: 'Tự động đăng',
        label: 'Giỏ hàng',
        href: '/auto/gio-hang',
        keywords: 'tiktok shop sản phẩm chọn giỏ',
    },
    {
        group: 'Tự động đăng',
        label: 'Số liệu',
        href: '/auto/so-lieu',
        keywords: 'thống kê lượt xem bình luận hỏi mua',
    },
    {
        group: 'Tự động đăng',
        label: 'Ảnh bìa & hashtag',
        href: '/auto/anh-bia-hashtag',
        keywords: 'cá nhân hoá hashtag mặc định',
    },
    {
        group: 'Tự động đăng',
        label: 'Thùng rác video',
        href: '/auto/thung-rac',
        keywords: 'khôi phục xoá',
    },
    { group: 'Cài đặt', label: 'Cài đặt', href: '/settings' },
    {
        group: 'Cài đặt',
        label: 'Cài đặt Chrome',
        href: '/settings#chrome',
        keywords: 'kết nối chrome tiện ích ghép nối kênh',
    },
    {
        group: 'Cài đặt',
        label: 'Cài đặt Telegram',
        href: '/settings#telegram',
        keywords: 'thông báo bot tin nhắn giờ yên tĩnh',
    },
    {
        group: 'Cài đặt',
        label: 'Cập nhật ứng dụng',
        href: '/settings#cap-nhat',
        keywords: 'phiên bản bản mới quay lại bản cũ',
    },
    {
        group: 'Việc cần làm',
        label: 'Chọn giỏ cho sản phẩm chưa có giỏ',
        href: '/auto/gio-hang',
        keywords: 'chưa chọn giỏ video chờ',
    },
    {
        group: 'Việc cần làm',
        label: 'Xem video đăng lỗi',
        href: '/auto/kho?tab=loi',
        keywords: 'thử lại bài lỗi',
    },
    {
        group: 'Việc cần làm',
        label: 'Kiểm tra Chrome đang kết nối',
        href: '/settings#chrome',
        keywords: 'chrome mất kết nối offline',
    },
    {
        group: 'Xưởng Video',
        label: 'Xưởng: Sản xuất',
        href: '/xuong?tab=san-xuat',
    },
    { group: 'Xưởng Video', label: 'Xưởng: Kho', href: '/xuong?tab=kho' },
    {
        group: 'Xưởng Video',
        label: 'Xưởng: Sản phẩm',
        href: '/xuong?tab=san-pham',
    },
    { group: 'Xưởng Video', label: 'Xưởng: Gu', href: '/xuong?tab=gu' },
    {
        group: 'Xưởng Video',
        label: 'Xưởng: Prompt AI',
        href: '/xuong?tab=prompt-ai',
    },
    {
        group: 'Xưởng Video',
        label: 'Xưởng: Cài đặt',
        href: '/xuong?tab=cai-dat',
    },
];

const query = ref('');
const active = ref(0);
const input = ref<HTMLInputElement | null>(null);
const listEl = ref<HTMLElement | null>(null);

const results = computed(() => {
    const q = norm(query.value.trim());

    if (q === '') {
        return items;
    }

    const words = q.split(/\s+/);

    return items.filter((i) => {
        const hay = norm(`${i.label} ${i.group} ${i.keywords ?? ''}`);

        return words.every((w) => hay.includes(w));
    });
});

// Nhóm theo thứ tự xuất hiện; chỉ số `idx` đếm xuyên các nhóm để mũi tên lên/xuống đi liền mạch.
const groups = computed(() => {
    const out: { name: string; rows: { item: Item; idx: number }[] }[] = [];

    results.value.forEach((item, idx) => {
        let g = out.find((x) => x.name === item.group);

        if (!g) {
            g = { name: item.group, rows: [] };
            out.push(g);
        }

        g.rows.push({ item, idx });
    });

    return out;
});

watch(query, () => {
    active.value = 0;
});

watch(open, (v) => {
    if (v) {
        query.value = '';
        active.value = 0;
        void nextTick(() => input.value?.focus());
    }
});

const choose = (item: Item) => {
    open.value = false;
    goTo(item.href);
};

const scrollActive = () =>
    void nextTick(() =>
        listEl.value
            ?.querySelector<HTMLElement>('[data-active="true"]')
            ?.scrollIntoView({ block: 'nearest' }),
    );

const onKey = (e: KeyboardEvent) => {
    const n = results.value.length;

    if (e.key === 'ArrowDown' && n) {
        e.preventDefault();
        active.value = (active.value + 1) % n;
        scrollActive();
    } else if (e.key === 'ArrowUp' && n) {
        e.preventDefault();
        active.value = (active.value - 1 + n) % n;
        scrollActive();
    } else if (e.key === 'Enter') {
        e.preventDefault();
        const item = results.value[active.value];

        if (item) {
            choose(item);
        }
    }
};
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent
            :show-close-button="false"
            :fullscreen-on-mobile="false"
            class="top-[14%] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-xl"
            data-testid="quick-search"
        >
            <DialogTitle class="sr-only">Tìm nhanh</DialogTitle>
            <div class="flex items-center gap-2 border-b px-4">
                <IconSearch class="size-4 shrink-0 text-muted-foreground" />
                <input
                    ref="input"
                    v-model="query"
                    type="text"
                    role="combobox"
                    aria-expanded="true"
                    aria-controls="quick-search-list"
                    :aria-activedescendant="
                        results.length ? `quick-search-${active}` : undefined
                    "
                    autocomplete="off"
                    spellcheck="false"
                    placeholder="Tìm trang hoặc việc cần làm"
                    class="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                    data-testid="quick-search-input"
                    @keydown="onKey"
                />
            </div>
            <div
                id="quick-search-list"
                ref="listEl"
                role="listbox"
                class="max-h-[50vh] overflow-y-auto p-2"
            >
                <template v-for="g in groups" :key="g.name">
                    <div
                        class="px-2 pt-2 pb-1 text-xs font-medium text-muted-foreground"
                    >
                        {{ g.name }}
                    </div>
                    <button
                        v-for="r in g.rows"
                        :id="`quick-search-${r.idx}`"
                        :key="r.item.href + r.item.label"
                        type="button"
                        role="option"
                        :aria-selected="r.idx === active"
                        :data-active="r.idx === active"
                        :class="
                            cn(
                                'flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm',
                                r.idx === active
                                    ? 'bg-accent text-accent-foreground'
                                    : 'hover:bg-accent/60',
                            )
                        "
                        @mousemove="active = r.idx"
                        @click="choose(r.item)"
                    >
                        <span>{{ r.item.label }}</span>
                        <span
                            class="truncate text-xs text-muted-foreground"
                            >{{ r.item.href }}</span
                        >
                    </button>
                </template>
                <p
                    v-if="!results.length"
                    class="px-3 py-8 text-center text-sm text-muted-foreground"
                    data-testid="quick-search-empty"
                >
                    Không có gì khớp “{{ query.trim() }}”
                </p>
            </div>
            <div
                class="flex items-center gap-3 border-t px-4 py-2 text-xs text-muted-foreground"
            >
                <span>↑ ↓ để chọn</span>
                <span>Enter để mở</span>
                <span>Esc để đóng</span>
            </div>
        </DialogContent>
    </Dialog>
</template>

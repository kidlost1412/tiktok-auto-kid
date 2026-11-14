<script setup lang="ts">
// Bàn của Mèo quản gia: Cài đặt gói gọn trong một popup. Dải tóm tắt (Chrome, kênh đang bật, Telegram, phiên bản) và
// bốn tab: Chrome · Tự động & kênh · Telegram · Cập nhật. Dùng lại nguyên các phần của trang Cài đặt
// (ChromeSection / TelegramSection / UpdateSection) và thẻ kênh của trang Tự động đăng (ChannelPanel).
import { IconRefresh } from '@tabler/icons-vue';
import { computed, onMounted, ref } from 'vue';

import ChannelPanel from '@/components/fork/auto/ChannelPanel.vue';
import type { AccountRow, Health, Lich } from '@/components/fork/auto/types';
import { banBao } from '@/components/fork/nha/ban/bus';
import { useInertiaProps } from '@/components/fork/nha/ban/useInertiaProps';
import type { NhaData } from '@/components/fork/nha/types';
import ChromeSection from '@/components/fork/settings/ChromeSection.vue';
import TelegramSection from '@/components/fork/settings/TelegramSection.vue';
import UpdateSection from '@/components/fork/settings/UpdateSection.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import { cardCls, toneClasses } from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

defineProps<{ data: NhaData | null }>();

type SettingsProps = {
    tab: string;
    chrome: InstanceType<typeof ChromeSection>['$props'];
    telegram: InstanceType<typeof TelegramSection>['$props'];
    update: InstanceType<typeof UpdateSection>['$props'];
};
type AutoProps = { accounts: AccountRow[]; health: Health; lich: Lich };

const {
    props: st,
    error,
    reload,
} = useInertiaProps<SettingsProps>('/settings', 'fork/Settings');
const { props: au, reload: reloadAuto } = useInertiaProps<AutoProps>(
    '/auto',
    'fork/Auto',
    ['accounts', 'health', 'lich'],
);

onMounted(() => {
    reload();
    reloadAuto();
});

type Tab = 'chrome' | 'kenh' | 'telegram' | 'cap-nhat';
const tab = ref<Tab>('chrome');
const tabs: { key: Tab; label: string }[] = [
    { key: 'chrome', label: 'Chrome' },
    { key: 'kenh', label: 'Tự động & kênh' },
    { key: 'telegram', label: 'Telegram' },
    { key: 'cap-nhat', label: 'Cập nhật' },
];

// Mỗi lần lưu xong: tải lại phần đã đổi và báo cho nhân vật trong cảnh.
const saved = (only: string[], auto = false) => {
    if (only.length) {
        reload(only);
    }

    if (auto) {
        reloadAuto();
    }

    banBao('meo', 'luu');
};

// ---- Dải tóm tắt
const chrome = computed(() => {
    const clients = st.value?.chrome.clients ?? [];
    const on = clients.filter((c) => c.status === 'ok').length;

    return {
        on,
        total: clients.length,
        ok: on > 0,
    };
});

const channels = computed(() => au.value?.accounts ?? []);
const channelsOn = computed(() => channels.value.filter((a) => a.enabled));

const telegram = computed(() => !!st.value?.telegram.configured);

const update = computed(() => st.value?.update ?? null);

// Video đã duyệt nhưng bị giữ vì chưa chọn giỏ, theo từng kênh (hiện ở thẻ kênh).
const blockedOf = (id: string) =>
    (au.value?.lich.channels[id]?.blocked ?? []).reduce(
        (s, g) => s + g.count,
        0,
    );

const labelCls =
    'text-xs font-medium tracking-[0.02em] text-muted-foreground uppercase';
const tileCls = cn(cardCls, 'flex min-w-0 flex-col gap-1 px-4 py-3.5');
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col gap-4" data-testid="ban-meo">
        <div
            v-if="error && !st"
            class="flex items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 text-sm"
        >
            <span class="text-muted-foreground">{{ error }}</span>
            <Button size="sm" variant="outline" @click="reload()">
                <IconRefresh class="size-4" />
                Thử lại
            </Button>
        </div>

        <template v-else-if="!st">
            <div class="grid grid-cols-4 gap-3">
                <Skeleton v-for="i in 4" :key="i" class="h-24 rounded-[14px]" />
            </div>
            <Skeleton class="h-72 rounded-[14px]" />
        </template>

        <template v-else>
            <!-- Dải tóm tắt -->
            <div class="grid grid-cols-4 gap-3" data-testid="ban-meo-tomtat">
                <div :class="tileCls">
                    <span :class="labelCls">Chrome</span>
                    <span
                        :class="
                            cn(
                                'font-heading text-2xl font-semibold',
                                !chrome.ok && toneClasses.warn.text,
                            )
                        "
                        >{{ chrome.ok ? 'Đang nối' : 'Chưa nối' }}</span
                    >
                    <span class="text-xs text-muted-foreground tabular-nums">{{
                        chrome.total
                            ? `${chrome.on}/${chrome.total} máy đang kết nối`
                            : 'Chưa ghép nối máy nào'
                    }}</span>
                </div>

                <div :class="tileCls">
                    <span :class="labelCls">Kênh TikTok đang bật</span>
                    <span class="flex items-baseline gap-1">
                        <span
                            class="font-heading text-2xl font-semibold tabular-nums"
                            >{{ channelsOn.length }}</span
                        >
                        <span class="text-sm text-muted-foreground tabular-nums"
                            >/ {{ channels.length }} kênh</span
                        >
                    </span>
                    <span class="text-xs text-muted-foreground">{{
                        channelsOn.length
                            ? 'Đang tự động đăng'
                            : 'Chưa kênh nào tự động đăng'
                    }}</span>
                </div>

                <div :class="tileCls">
                    <span :class="labelCls">Telegram báo tin</span>
                    <span
                        :class="
                            cn(
                                'font-heading text-2xl font-semibold',
                                !telegram && 'text-muted-foreground',
                            )
                        "
                        >{{ telegram ? 'Bật' : 'Tắt' }}</span
                    >
                    <span class="text-xs text-muted-foreground">{{
                        telegram
                            ? 'Có tin là báo về điện thoại'
                            : 'Chưa kết nối bot'
                    }}</span>
                </div>

                <div :class="tileCls">
                    <span :class="labelCls">Phiên bản</span>
                    <span
                        class="font-heading text-2xl font-semibold tabular-nums"
                        >{{ update?.current ?? '—' }}</span
                    >
                    <span
                        :class="
                            cn(
                                'text-xs',
                                update?.update_available
                                    ? toneClasses.info.text
                                    : 'text-muted-foreground',
                            )
                        "
                        >{{
                            update?.update_available && update.latest
                                ? `Có bản mới ${update.latest.version}`
                                : 'Đang dùng bản mới nhất'
                        }}</span
                    >
                </div>
            </div>

            <!-- Tab -->
            <div
                class="flex w-fit gap-0.5 rounded-lg bg-muted p-1"
                role="tablist"
                aria-label="Phần cài đặt"
            >
                <button
                    v-for="t in tabs"
                    :key="t.key"
                    type="button"
                    role="tab"
                    :aria-selected="tab === t.key"
                    :data-testid="`ban-meo-tab-${t.key}`"
                    :class="
                        cn(
                            'rounded-md px-3.5 py-1 text-sm font-medium transition',
                            tab === t.key
                                ? 'bg-card text-foreground shadow-xs'
                                : 'text-muted-foreground hover:text-foreground',
                        )
                    "
                    @click="tab = t.key"
                >
                    {{ t.label }}
                </button>
            </div>

            <ChromeSection
                v-if="tab === 'chrome'"
                v-bind="st.chrome"
                embedded
                @refresh="reload(['chrome'])"
                @changed="saved(['chrome'], true)"
            />

            <div
                v-else-if="tab === 'kenh'"
                class="flex flex-col gap-3"
                data-testid="ban-meo-kenh"
            >
                <p class="text-sm text-muted-foreground">
                    Bật / tắt tự động đăng và chỉnh hạn mức, khung giờ, số ngày
                    hẹn trước cho từng kênh (bấm Chỉnh trên thẻ kênh).
                </p>
                <Skeleton v-if="!au" class="h-40 rounded-[14px]" />
                <EmptyState
                    v-else-if="!channels.length"
                    title="Chưa có kênh TikTok nào"
                    description="Ghép nối Chrome ở tab Chrome để có kênh đăng bài."
                />
                <div v-else class="grid grid-cols-2 gap-3">
                    <ChannelPanel
                        v-for="a in channels"
                        :key="a.id"
                        :account="a"
                        :today="au?.lich.channels[a.id]?.today"
                        :chrome="au?.health.channels.find((c) => c.id === a.id)"
                        :blocked-count="blockedOf(a.id)"
                        in-place
                        @changed="saved([], true)"
                    />
                </div>
            </div>

            <TelegramSection
                v-else-if="tab === 'telegram'"
                v-bind="st.telegram"
                embedded
                @changed="saved(['telegram', 'chrome'])"
            />

            <UpdateSection
                v-else
                v-bind="st.update"
                embedded
                @changed="saved(['update'])"
            />
        </template>
    </div>
</template>

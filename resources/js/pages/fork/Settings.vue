<script setup lang="ts">
// Trang "Cài đặt" hợp nhất: gộp 3 trang cũ (Kết nối Chrome, Telegram, Cập nhật) vào một chỗ,
// chọn mục bằng tab bên trong trang. URL cũ (/settings/chrome, /settings/telegram,
// /settings/cap-nhat) tự chuyển hướng vào đây kèm # để mở đúng mục.
import { Head } from '@inertiajs/vue3';
import { IconBrandChrome, IconBrandTelegram, IconCloudDownload } from '@tabler/icons-vue';
import { computed, onMounted, ref, type Component } from 'vue';

import ChromeSection from '@/components/fork/settings/ChromeSection.vue';
import TelegramSection from '@/components/fork/settings/TelegramSection.vue';
import UpdateSection from '@/components/fork/settings/UpdateSection.vue';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import SettingsLayout from '@/layouts/SettingsLayout.vue';

type TabKey = 'chrome' | 'telegram' | 'cap-nhat';

const props = defineProps<{
    tab: TabKey;
    chrome: InstanceType<typeof ChromeSection>['$props'];
    telegram: InstanceType<typeof TelegramSection>['$props'];
    update: InstanceType<typeof UpdateSection>['$props'];
}>();

const tabs: { key: TabKey; label: string; icon: Component }[] = [
    { key: 'chrome', label: 'Kết nối Chrome', icon: IconBrandChrome },
    { key: 'telegram', label: 'Telegram', icon: IconBrandTelegram },
    { key: 'cap-nhat', label: 'Cập nhật', icon: IconCloudDownload },
];

const active = ref<TabKey>(props.tab);

// Bookmark/link cũ dùng #chrome, #telegram hoặc #cap-nhat: ưu tiên hơn giá trị mặc định từ server.
onMounted(() => {
    const hash = window.location.hash.replace('#', '') as TabKey;

    if (tabs.some((t) => t.key === hash)) {
        active.value = hash;
    }
});

function setTab(key: string): void {
    active.value = key as TabKey;
    history.replaceState(null, '', `#${key}`);
}

const description = computed(
    () =>
        ({
            chrome: 'Ghép nối tiện ích Chrome để đăng TikTok, xem Chrome nào đang kết nối và bài nào vừa được giao.',
            telegram: 'Nhận tin ngay trên điện thoại khi bài lên, bài lỗi, mất kết nối, và tổng kết mỗi ngày.',
            'cap-nhat': 'Cập nhật TikTok Auto Kid lên bản mới chỉ với một cú nhấp. Dữ liệu được sao lưu trước, lỗi thì tự quay về bản cũ.',
        })[active.value],
);
</script>

<template>
    <Head title="Cài đặt" />

    <SettingsLayout title="Cài đặt" :description="description">
        <div class="flex flex-col gap-5" data-testid="fork-settings-page">
            <div class="max-w-full overflow-x-auto">
                <Tabs :model-value="active" @update:model-value="setTab(String($event))">
                    <TabsList data-testid="fork-settings-tabs">
                        <TabsTrigger v-for="t in tabs" :key="t.key" :value="t.key" class="gap-1.5">
                            <component :is="t.icon" class="size-4" />
                            {{ t.label }}
                        </TabsTrigger>
                    </TabsList>
                </Tabs>
            </div>

            <ChromeSection v-if="active === 'chrome'" v-bind="props.chrome" />
            <TelegramSection v-else-if="active === 'telegram'" v-bind="props.telegram" />
            <UpdateSection v-else v-bind="props.update" />
        </div>
    </SettingsLayout>
</template>

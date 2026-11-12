<script setup lang="ts">
// Cài đặt Telegram ngay trong app: 3 bước nối bot, bật/tắt từng loại tin, giờ yên tĩnh, xem trước và gửi tin mẫu.
// Chữ viết thẳng bằng tiếng Việt (không qua lang/en).
import { Head, router } from '@inertiajs/vue3';
import {
    IconBrandTelegram,
    IconCheck,
    IconExternalLink,
    IconSend,
} from '@tabler/icons-vue';
import { reactive, ref, watch } from 'vue';

import SettingsSection from '@/components/settings/SettingsSection.vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import SettingsLayout from '@/layouts/SettingsLayout.vue';

interface TypeRow {
    key: string;
    label: string;
    urgent: boolean;
    on: boolean;
}

interface Preview {
    id: string;
    label: string;
    html: string;
}

const props = defineProps<{
    configured: boolean;
    has_token: boolean;
    token_masked: string | null;
    bot: { username: string; link: string } | null;
    chat: { id: string; name: string | null } | null;
    candidate: { id: string; name: string } | null;
    types: TypeRow[];
    summary_time: string;
    quiet: { enabled: boolean; start: string; end: string };
    previews: Preview[];
}>();

const busy = ref<string | null>(null);
const run = (key: string, fn: (done: () => void) => void): void => {
    busy.value = key;
    fn(() => (busy.value = null));
};
const opts = (done: () => void) => ({ preserveScroll: true, onFinish: done });

const token = ref('');
const chatId = ref('');
const replacingToken = ref(false);

const saveToken = (): void =>
    run('token', (done) =>
        router.put(
            '/settings/telegram/token',
            { token: token.value },
            {
                ...opts(done),
                onSuccess: () => {
                    token.value = '';
                    replacingToken.value = false;
                },
            },
        ),
    );

const detect = (): void =>
    run('detect', (done) =>
        router.post('/settings/telegram/detect-chat', {}, opts(done)),
    );

const saveChat = (id: string): void =>
    run('chat', (done) =>
        router.put(
            '/settings/telegram/chat',
            { chat_id: id },
            {
                ...opts(done),
                onSuccess: () => (chatId.value = ''),
            },
        ),
    );

const test = (): void =>
    run('test', (done) =>
        router.post('/settings/telegram/test', {}, opts(done)),
    );

const sample = (id: string): void =>
    run(`sample-${id}`, (done) =>
        router.post(`/settings/telegram/sample/${id}`, {}, opts(done)),
    );

const disconnect = (): void => {
    if (!window.confirm('Xoá token và chat id đã lưu trong app?')) return;
    run('disconnect', (done) =>
        router.delete('/settings/telegram', opts(done)),
    );
};

const form = reactive({
    toggles: {} as Record<string, boolean>,
    summary_time: props.summary_time,
    quiet: { ...props.quiet },
});

watch(
    () => props.types,
    (types) => {
        for (const t of types) form.toggles[t.key] = t.on;
    },
    { immediate: true },
);

const savePrefs = (): void =>
    run('prefs', (done) =>
        router.patch(
            '/settings/telegram/prefs',
            {
                toggles: form.toggles,
                summary_time: form.summary_time,
                quiet: form.quiet,
            },
            opts(done),
        ),
    );

const stepDone = {
    token: () => props.has_token,
    chat: () => !!props.chat,
};
</script>

<template>
    <Head title="Telegram" />

    <SettingsLayout
        title="Thông báo Telegram"
        description="Nhận tin ngay trên điện thoại khi bài lên, bài lỗi, mất kết nối, và tổng kết mỗi ngày. Làm 3 bước dưới đây, không cần sửa file."
    >
        <div class="flex flex-col gap-10" data-testid="fork-telegram-page">
            <SettingsSection
                title="Nối bot Telegram"
                description="Mỗi bước xong sẽ hiện dấu tích xanh."
            >
                <template #actions>
                    <Badge :variant="configured ? 'success' : 'warning'">
                        {{ configured ? 'Đã nối xong' : 'Chưa nối xong' }}
                    </Badge>
                </template>

                <ol class="flex flex-col gap-4">
                    <!-- Bước 1 -->
                    <li class="rounded-xl border p-5" data-testid="fork-telegram-step-1">
                        <div class="flex items-center gap-3">
                            <span
                                class="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground"
                            >
                                <IconCheck v-if="stepDone.token()" class="size-5" />
                                <template v-else>1</template>
                            </span>
                            <h3 class="text-base font-semibold">Tạo bot và dán token</h3>
                        </div>
                        <p class="mt-3 text-sm text-muted-foreground">
                            Mở
                            <a
                                href="https://t.me/BotFather"
                                target="_blank"
                                rel="noopener"
                                class="font-medium text-primary underline"
                                >BotFather</a
                            >
                            trên Telegram, gõ <code>/newbot</code>, đặt tên bot rồi
                            sao chép dòng token BotFather gửi (dạng
                            <code>123456789:AAH...</code>) và dán vào ô dưới.
                        </p>
                        <div class="mt-3 flex flex-wrap items-center gap-2">
                            <Button as-child variant="outline" size="sm">
                                <a href="https://t.me/BotFather" target="_blank" rel="noopener">
                                    <IconExternalLink class="size-4" />
                                    Mở BotFather
                                </a>
                            </Button>
                        </div>
                        <div
                            v-if="has_token && !replacingToken"
                            class="mt-3 flex flex-wrap items-center gap-3 text-sm"
                        >
                            <code class="rounded bg-muted px-2 py-1" data-testid="fork-telegram-token-masked">{{ token_masked }}</code>
                            <span v-if="bot" class="text-muted-foreground">Bot: <b>@{{ bot.username }}</b></span>
                            <Button variant="ghost" size="sm" @click="replacingToken = true">Đổi token</Button>
                        </div>
                        <form
                            v-else
                            class="mt-3 flex flex-wrap items-center gap-2"
                            @submit.prevent="saveToken"
                        >
                            <Input
                                v-model="token"
                                type="password"
                                autocomplete="off"
                                placeholder="Dán token bot vào đây"
                                class="max-w-md"
                                aria-label="Token bot"
                            />
                            <Button type="submit" size="sm" :disabled="!token.trim() || busy === 'token'">
                                <Spinner v-if="busy === 'token'" class="size-4" />
                                Lưu và kiểm tra
                            </Button>
                            <Button v-if="has_token" variant="ghost" size="sm" type="button" @click="replacingToken = false">Huỷ</Button>
                        </form>
                    </li>

                    <!-- Bước 2 -->
                    <li class="rounded-xl border p-5" :class="!has_token && 'opacity-60'" data-testid="fork-telegram-step-2">
                        <div class="flex items-center gap-3">
                            <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                                <IconCheck v-if="stepDone.chat()" class="size-5" />
                                <template v-else>2</template>
                            </span>
                            <h3 class="text-base font-semibold">Mở bot và nhấn Start</h3>
                        </div>
                        <p class="mt-3 text-sm text-muted-foreground">
                            Bấm “Mở bot”, trong Telegram nhấn nút <b>Start</b> (hoặc gửi một tin bất kỳ) để bot được phép nhắn cho bạn.
                        </p>
                        <div class="mt-3">
                            <Button v-if="bot" as-child size="sm">
                                <a :href="bot.link" target="_blank" rel="noopener" data-testid="fork-telegram-open-bot">
                                    <IconBrandTelegram class="size-4" />
                                    Mở bot @{{ bot.username }}
                                </a>
                            </Button>
                            <span v-else class="text-sm text-muted-foreground">Lưu token ở bước 1 trước.</span>
                        </div>
                    </li>

                    <!-- Bước 3 -->
                    <li class="rounded-xl border p-5" :class="!has_token && 'opacity-60'" data-testid="fork-telegram-step-3">
                        <div class="flex items-center gap-3">
                            <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                                <IconCheck v-if="stepDone.chat()" class="size-5" />
                                <template v-else>3</template>
                            </span>
                            <h3 class="text-base font-semibold">Lấy chat id và gửi thử</h3>
                        </div>

                        <div v-if="chat" class="mt-3 text-sm" data-testid="fork-telegram-chat">
                            Đang gửi tới: <b>{{ chat.name ?? 'Chat' }}</b>
                            <code class="ml-2 rounded bg-muted px-2 py-0.5">{{ chat.id }}</code>
                        </div>

                        <div class="mt-3 flex flex-wrap items-center gap-2">
                            <Button variant="outline" size="sm" :disabled="!has_token || busy === 'detect'" @click="detect">
                                <Spinner v-if="busy === 'detect'" class="size-4" />
                                Tự lấy chat id
                            </Button>
                            <Button size="sm" :disabled="!configured || busy === 'test'" data-testid="fork-telegram-test" @click="test">
                                <Spinner v-if="busy === 'test'" class="size-4" />
                                <IconSend v-else class="size-4" />
                                Gửi thử
                            </Button>
                        </div>

                        <div
                            v-if="candidate"
                            class="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-primary/40 bg-primary/5 p-3 text-sm"
                            data-testid="fork-telegram-candidate"
                        >
                            <span>Tìm thấy: <b>{{ candidate.name }}</b> ({{ candidate.id }}). Đúng là bạn?</span>
                            <Button size="sm" :disabled="busy === 'chat'" @click="saveChat(candidate.id)">Đúng, dùng chat này</Button>
                        </div>

                        <form class="mt-3 flex flex-wrap items-center gap-2" @submit.prevent="saveChat(chatId)">
                            <Input
                                v-model="chatId"
                                inputmode="numeric"
                                placeholder="Hoặc nhập chat id thủ công"
                                class="max-w-xs"
                                aria-label="Chat id"
                            />
                            <Button type="submit" variant="ghost" size="sm" :disabled="!chatId.trim() || busy === 'chat'">Lưu chat id</Button>
                        </form>
                    </li>
                </ol>

                <div v-if="has_token" class="text-right">
                    <Button variant="ghost" size="sm" class="text-destructive" :disabled="busy === 'disconnect'" @click="disconnect">
                        Xoá cấu hình Telegram
                    </Button>
                </div>
            </SettingsSection>

            <SettingsSection
                title="Loại thông báo"
                description="Mỗi sự kiện là một tin riêng. Quá 5 tin cùng loại trong một lượt sẽ được gộp thành một tin."
            >
                <ul class="divide-y rounded-xl border">
                    <li v-for="t in types" :key="t.key" class="flex items-center gap-3 px-4 py-3">
                        <div class="min-w-0 flex-1">
                            <div class="text-sm font-medium">{{ t.label }}</div>
                            <div v-if="t.urgent" class="text-xs text-muted-foreground">Khẩn cấp: luôn gửi ngay, kể cả giờ yên tĩnh</div>
                        </div>
                        <Switch
                            :model-value="form.toggles[t.key]"
                            :aria-label="t.label"
                            :data-testid="`fork-telegram-toggle-${t.key}`"
                            @update:model-value="(v: boolean) => (form.toggles[t.key] = v)"
                        />
                    </li>
                </ul>

                <div class="grid gap-4 sm:grid-cols-2">
                    <div class="rounded-xl border p-4">
                        <div class="text-sm font-medium">Giờ gửi tổng kết ngày</div>
                        <Input v-model="form.summary_time" type="time" class="mt-2 w-32" aria-label="Giờ gửi tổng kết" />
                    </div>
                    <div class="rounded-xl border p-4">
                        <div class="flex items-center justify-between gap-3">
                            <div class="text-sm font-medium">Giờ yên tĩnh</div>
                            <Switch
                                :model-value="form.quiet.enabled"
                                aria-label="Bật giờ yên tĩnh"
                                @update:model-value="(v: boolean) => (form.quiet.enabled = v)"
                            />
                        </div>
                        <p class="mt-1 text-xs text-muted-foreground">
                            Trong khoảng này chỉ gửi tin khẩn cấp; tin còn lại gửi bù sau khi hết giờ yên tĩnh.
                        </p>
                        <div class="mt-2 flex items-center gap-2 text-sm" :class="!form.quiet.enabled && 'opacity-50'">
                            <Input v-model="form.quiet.start" type="time" class="w-28" aria-label="Bắt đầu yên tĩnh" />
                            đến
                            <Input v-model="form.quiet.end" type="time" class="w-28" aria-label="Kết thúc yên tĩnh" />
                        </div>
                    </div>
                </div>

                <div>
                    <Button :disabled="busy === 'prefs'" data-testid="fork-telegram-save-prefs" @click="savePrefs">
                        <Spinner v-if="busy === 'prefs'" class="size-4" />
                        Lưu cài đặt thông báo
                    </Button>
                </div>
            </SettingsSection>

            <SettingsSection
                title="Xem trước tin nhắn"
                description="Đây là hình dạng từng loại tin (dữ liệu giả). Bấm “Gửi mẫu” để nhận thử một tin thật trên Telegram."
            >
                <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="fork-telegram-previews">
                    <article v-for="p in previews" :key="p.id" class="flex flex-col gap-3 rounded-xl border p-4" :data-testid="`fork-telegram-preview-${p.id}`">
                        <div class="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{{ p.label }}</div>
                        <!-- eslint-disable-next-line vue/no-v-html -- HTML do server dựng và đã escape, chỉ có thẻ b/i/code/a -->
                        <div
                            class="flex-1 rounded-2xl rounded-tl-sm bg-muted/60 p-3 text-sm leading-relaxed whitespace-pre-line [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-background/70 [&_code]:px-1"
                            @click.prevent
                            v-html="p.html"
                        />
                        <Button variant="outline" size="sm" class="self-start" :disabled="!configured || busy === `sample-${p.id}`" @click="sample(p.id)">
                            <Spinner v-if="busy === `sample-${p.id}`" class="size-4" />
                            <IconSend v-else class="size-4" />
                            Gửi mẫu
                        </Button>
                    </article>
                </div>
            </SettingsSection>
        </div>
    </SettingsLayout>
</template>

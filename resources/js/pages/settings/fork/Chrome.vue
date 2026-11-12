<script setup lang="ts">
// Trang riêng của bản Việt hoá: ghép nối tiện ích Chrome (TikTok Auto Kid) để đăng TikTok.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en) để không
// làm lệch bộ khoá dịch của các ngôn ngữ khác.
import { Head, Link, router, usePoll } from '@inertiajs/vue3';
import {
    IconBrandChrome,
    IconCopy,
    IconPlayerPlay,
    IconPlus,
    IconRefresh,
    IconTrash,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import SettingsSection from '@/components/settings/SettingsSection.vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import dayjs from '@/dayjs';
import SettingsLayout from '@/layouts/SettingsLayout.vue';

interface Pair {
    code: string;
    expires_at: string;
    valid_s: number;
}

interface ChromeClient {
    id: number;
    label: string;
    ext_version: string;
    tiktok_username: string | null;
    tiktok_user_id: string | null;
    chrome_profile_dir: string | null;
    chrome_browser?: 'chrome' | 'edge' | null;
    last_seen_at: string | null;
    status: string;
    profile_needs_choice?: boolean;
    profile_conflict_with?: string | null;
}

interface TikTokAccount {
    id: string;
    username: string | null;
    display_name: string | null;
    enabled: boolean;
    chrome_only: boolean;
    readiness: string | null;
}

interface ChromeJobRow {
    id: string;
    username: string | null;
    state: string;
    mode: string;
    caption: string;
    note: string | null;
    created_at: string | null;
    updated_at: string | null;
}

interface ChromeProfile {
    browser?: 'chrome' | 'edge';
    dir: string;
    name?: string;
    has_extension?: boolean;
    bundle_extension?: boolean;
}

/** Bản tiện ích mới nhất đi kèm app. */
const LATEST_EXTENSION = '1.4.1';

const props = defineProps<{
    pair: Pair | null;
    clients: ChromeClient[];
    accounts: TikTokAccount[];
    jobs: ChromeJobRow[];
    profiles: ChromeProfile[];
    telegram?: { configured: boolean };
    extensionPath: string;
    serverUrl: string;
    hasWorkspace: boolean;
}>();

const only = ['pair', 'clients', 'accounts', 'jobs', 'profiles', 'telegram'];
usePoll(5000, { only });

const busy = ref<string | null>(null);

const run = (key: string, fn: (done: () => void) => void): void => {
    busy.value = key;
    fn(() => (busy.value = null));
};

// Đếm ngược mã ghép nối: tính từ lúc nhận props để khỏi lệ thuộc đồng hồ máy.
const secondsLeft = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;
let receivedAt = Date.now();

const tick = (): void => {
    if (!props.pair) {
        secondsLeft.value = 0;
        return;
    }
    const gone = Math.floor((Date.now() - receivedAt) / 1000);
    secondsLeft.value = Math.max(0, props.pair.valid_s - gone);
};

watch(
    () => props.pair?.code,
    () => {
        receivedAt = Date.now();
        tick();
    },
    { immediate: true },
);

onMounted(() => {
    timer = setInterval(tick, 1000);
});
onBeforeUnmount(() => {
    if (timer) clearInterval(timer);
});

const countdown = computed(() => {
    const m = Math.floor(secondsLeft.value / 60);
    const s = String(secondsLeft.value % 60).padStart(2, '0');
    return `${m}:${s}`;
});
const pairActive = computed(() => props.pair !== null && secondsLeft.value > 0);

// Đã có Chrome ghép nối: hiện trạng thái thành công, không bắt tạo mã nữa (mã dùng xong là bị huỷ).
const connectedClients = computed(() =>
    props.clients.filter((c) => c.status === 'ok' || c.tiktok_username),
);
const paired = computed(() => connectedClients.value.length > 0);

const makeCode = (): void =>
    run('pair', (done) =>
        router.post(
            '/settings/chrome/pair-code',
            {},
            { preserveScroll: true, onFinish: done },
        ),
    );

const profileDraft = ref<Record<number, string>>({});

// Giá trị của ô chọn profile là "<trình duyệt>|<thư mục>", vd. "edge|Profile 2".
const optionValue = (browser: string | null | undefined, dir: string): string =>
    `${browser === 'edge' ? 'edge' : 'chrome'}|${dir}`;

const browserLabel = (browser?: string | null): string =>
    browser === 'edge' ? 'Edge' : 'Chrome';

const profileLabel = (profile: ChromeProfile): string =>
    `${browserLabel(profile.browser)} · ${profile.dir}` +
    (profile.name && profile.name !== profile.dir ? ` (${profile.name})` : '') +
    (profile.has_extension ? ' · có tiện ích' : '');

const selectedProfile = (client: ChromeClient): string =>
    client.chrome_profile_dir
        ? optionValue(client.chrome_browser, client.chrome_profile_dir)
        : '';

const profileOf = (client: ChromeClient): string =>
    profileDraft.value[client.id] ?? client.chrome_profile_dir ?? '';

const saveProfile = (
    client: ChromeClient,
    value: string,
    browser = 'chrome',
): void => {
    profileDraft.value[client.id] = value;
    run(`profile-${client.id}`, (done) =>
        router.patch(
            `/settings/chrome/clients/${client.id}`,
            { chrome_profile_dir: value, chrome_browser: browser },
            { preserveScroll: true, onFinish: done },
        ),
    );
};

const saveFromSelect = (client: ChromeClient, value: string): void => {
    const [browser, ...rest] = value.split('|');
    saveProfile(client, value === '' ? '' : rest.join('|'), browser);
};

const telegramTest = (): void =>
    run('telegram', (done) =>
        router.post(
            '/settings/chrome/telegram-test',
            {},
            { preserveScroll: true, onFinish: done },
        ),
    );

const revoke = (client: ChromeClient): void => {
    if (!window.confirm(`Thu hồi kết nối "${client.label}"?`)) return;
    run(`revoke-${client.id}`, (done) =>
        router.delete(`/settings/chrome/clients/${client.id}`, {
            preserveScroll: true,
            onFinish: done,
        }),
    );
};

const toggle = (account: TikTokAccount): void =>
    run(`toggle-${account.id}`, (done) =>
        router.post(
            `/settings/chrome/accounts/${account.id}/toggle`,
            {},
            { preserveScroll: true, onFinish: done },
        ),
    );

const addFromClient = (client: ChromeClient): void =>
    run(`add-${client.id}`, (done) =>
        router.post(
            `/settings/chrome/accounts/from-client/${client.id}`,
            {},
            { preserveScroll: true, onFinish: done },
        ),
    );

const clientStatus: Record<
    string,
    { label: string; variant: 'success' | 'warning' | 'destructive-subtle' }
> = {
    ok: { label: 'Đã kết nối', variant: 'success' },
    offline: { label: 'Chrome đang tắt hoặc mất kết nối', variant: 'warning' },
    no_identity: { label: 'Chưa đăng nhập TikTok', variant: 'warning' },
    conflict: { label: 'Trùng Chrome khác', variant: 'destructive-subtle' },
    need_reload: {
        label: 'Cần tải lại tiện ích',
        variant: 'destructive-subtle',
    },
};

const readiness: Record<string, string> = {
    ok: 'Sẵn sàng',
    chrome_unbound: 'Chưa có Chrome đăng nhập tài khoản này',
    chrome_offline: 'Chrome đang tắt: mở Chrome (profile này) để đăng tiếp',
    chrome_conflict: 'Có hai Chrome cùng tài khoản',
    chrome_need_reload: 'Cần tải lại tiện ích',
};

const jobState: Record<
    string,
    {
        label: string;
        variant:
            | 'success'
            | 'warning'
            | 'destructive-subtle'
            | 'info'
            | 'secondary';
    }
> = {
    queued: { label: 'Đang chờ Chrome', variant: 'info' },
    claimed: { label: 'Chrome đã nhận', variant: 'info' },
    uploading: { label: 'Đang tải video', variant: 'info' },
    ready: { label: 'Sẵn sàng đăng', variant: 'info' },
    authorized: { label: 'Đang đăng', variant: 'info' },
    posted: { label: 'Đã đăng', variant: 'success' },
    rejected: { label: 'TikTok từ chối', variant: 'destructive-subtle' },
    uncertain: { label: 'Chưa rõ kết quả', variant: 'warning' },
    revoked: { label: 'Đã huỷ', variant: 'secondary' },
    failed: { label: 'Lỗi', variant: 'destructive-subtle' },
};

const fromNow = (value?: string | null): string =>
    value ? dayjs(value).locale('vi').fromNow() : 'chưa thấy';

const copy = async (text: string): Promise<void> => {
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        // Trình duyệt chặn clipboard: người dùng tự chép tay.
    }
};

const clientsWithIdentity = computed(() =>
    props.clients.filter((c) => c.tiktok_user_id && c.tiktok_username),
);
const chromeOnlyCandidates = computed(() => {
    const names = new Set(
        props.accounts.map((a) => (a.username ?? '').toLowerCase()),
    );
    return clientsWithIdentity.value.filter(
        (c) =>
            !names.has(
                (c.tiktok_username ?? '').replace(/^@/, '').toLowerCase(),
            ),
    );
});
</script>

<template>
    <Head title="Kết nối Chrome" />

    <SettingsLayout title="Kết nối Chrome">
        <div class="flex flex-col gap-10" data-testid="fork-chrome-page">
            <SettingsSection
                title="Ghép nối tiện ích TikTok Auto Kid"
                description="TikTok chỉ cho đăng công khai khi đăng qua Chrome đang đăng nhập sẵn tài khoản của bạn. Cài tiện ích, rồi nhập mã 6 số bên dưới vào tiện ích."
            >
                <template #actions>
                    <Button :disabled="busy === 'pair'" @click="makeCode">
                        <Spinner v-if="busy === 'pair'" class="size-4" />
                        <IconPlus v-else class="size-4" />
                        {{
                            pairActive
                                ? 'Tạo mã mới'
                                : paired
                                  ? 'Ghép thêm Chrome'
                                  : 'Tạo mã ghép nối'
                        }}
                    </Button>
                </template>

                <div
                    class="grid gap-4 rounded-xl border bg-card p-5 sm:grid-cols-2"
                    data-testid="fork-chrome-connect-info"
                >
                    <div>
                        <p class="text-sm text-muted-foreground">
                            Địa chỉ máy chủ (nhập vào tiện ích)
                        </p>
                        <div class="mt-1 flex flex-wrap items-center gap-2">
                            <code class="text-xl font-semibold break-all">{{
                                serverUrl || 'http://localhost:8010'
                            }}</code>
                            <Button
                                variant="outline"
                                size="sm"
                                @click="copy(serverUrl || 'http://localhost:8010')"
                            >
                                <IconCopy class="size-4" />
                                Chép
                            </Button>
                        </div>
                    </div>
                    <div>
                        <p class="text-sm text-muted-foreground">
                            Phiên bản tiện ích TikTok Auto Kid
                        </p>
                        <p class="mt-1 text-xl font-semibold">
                            Mới nhất: v{{ LATEST_EXTENSION }}
                        </p>
                        <p
                            v-for="c in clients"
                            :key="c.id"
                            :class="
                                c.ext_version === LATEST_EXTENSION
                                    ? 'text-sm text-success-text'
                                    : 'text-sm text-amber-700 dark:text-amber-400'
                            "
                        >
                            {{ c.label }}: đang chạy v{{ c.ext_version }}{{
                                c.ext_version === LATEST_EXTENSION
                                    ? ' (đã mới nhất)'
                                    : ': hãy tải lại tiện ích ở chrome://extensions'
                            }}
                        </p>
                    </div>
                </div>

                <div
                    v-if="paired && !pairActive"
                    class="flex flex-wrap items-center gap-3 rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-4 text-sm"
                    data-testid="fork-chrome-paired"
                >
                    <Badge variant="success">Đã ghép nối</Badge>
                    <span>
                        Tiện ích TikTok Auto Kid đã kết nối<template
                            v-if="connectedClients[0]?.tiktok_username"
                        >
                            với tài khoản
                            <strong
                                >@{{
                                    connectedClients[0].tiktok_username.replace(
                                        /^@/,
                                        '',
                                    )
                                }}</strong
                            ></template
                        >. Không cần tạo mã nữa; chỉ tạo mã khi muốn ghép thêm
                        một Chrome khác.
                    </span>
                </div>
                <div
                    v-if="pairActive && pair"
                    class="flex flex-wrap items-center gap-4 rounded-lg border p-4"
                >
                    <code
                        class="text-3xl font-emphasis tracking-[0.3em]"
                        data-testid="fork-chrome-code"
                        >{{ pair.code }}</code
                    >
                    <Button
                        variant="outline"
                        size="sm"
                        @click="copy(pair.code)"
                    >
                        <IconCopy class="size-4" />
                        Chép mã
                    </Button>
                    <span class="text-sm text-muted-foreground">
                        Còn hiệu lực {{ countdown }}. Tạo mã mới sẽ làm mã cũ mất
                        hiệu lực.
                    </span>
                </div>
                <div
                    v-else-if="!paired"
                    class="rounded-lg border border-dashed p-4 text-sm text-muted-foreground"
                >
                    Bấm “Tạo mã ghép nối”. Mã chỉ dùng được trong 5 phút và tối
                    đa 5 lần nhập.
                </div>

                <details class="rounded-lg border p-4 text-sm">
                    <summary class="cursor-pointer font-emphasis">
                        Cách cài tiện ích
                    </summary>
                    <ol
                        class="mt-3 list-inside list-decimal space-y-2 text-muted-foreground"
                    >
                        <li>
                            Mở Chrome, vào <code>chrome://extensions</code> (Edge:
                            <code>edge://extensions</code>) và bật “Chế độ cho
                            nhà phát triển”.
                        </li>
                        <li>
                            Bấm “Tải tiện ích đã giải nén” rồi chọn thư mục:
                            <span class="mt-1 flex flex-wrap items-center gap-2">
                                <code class="break-all">{{ extensionPath }}</code>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    @click="copy(extensionPath)"
                                >
                                    <IconCopy class="size-4" />
                                    Chép đường dẫn
                                </Button>
                            </span>
                        </li>
                        <li>
                            Đăng nhập TikTok trong chính Chrome (profile) đó.
                        </li>
                        <li>
                            Mở tiện ích, nhập máy chủ
                            <code>{{ serverUrl }}</code> và mã 6 số ở trên.
                        </li>
                        <li>
                            Vào <code>chrome://settings/system</code> và bật
                            “Tiếp tục chạy ứng dụng nền khi đóng Google
                            Chrome”, để tiện ích vẫn nhận việc khi bạn đã đóng
                            cửa sổ Chrome.
                        </li>
                        <li>
                            Sau mỗi lần cập nhật tiện ích, bấm nút tải lại (⟳)
                            ở <code>chrome://extensions</code>.
                        </li>
                    </ol>
                </details>
            </SettingsSection>

            <SettingsSection
                title="Chrome đã ghép nối"
                description="Mỗi Chrome (profile) đăng nhập một tài khoản TikTok, và mỗi kênh cần một profile riêng."
            >
                <div
                    v-if="!clients.length"
                    class="rounded-lg border border-dashed p-4 text-sm text-muted-foreground"
                >
                    Chưa có Chrome nào được ghép nối.
                </div>

                <ul v-else class="divide-y rounded-lg border">
                    <li
                        v-for="client in clients"
                        :key="client.id"
                        class="flex flex-wrap items-center gap-x-4 gap-y-2 p-4 text-sm"
                    >
                        <IconBrandChrome class="size-5 shrink-0" />
                        <div class="min-w-0 flex-1">
                            <p class="font-emphasis">{{ client.label }}</p>
                            <p class="text-sm text-muted-foreground">
                                {{
                                    client.tiktok_username
                                        ? `@${client.tiktok_username.replace(/^@/, '')}`
                                        : 'Chưa biết tài khoản TikTok'
                                }}
                                · v{{ client.ext_version }} · thấy
                                {{ fromNow(client.last_seen_at) }}
                            </p>
                        </div>
                        <p
                            v-if="client.status === 'offline'"
                            class="w-full text-sm text-amber-700 dark:text-amber-400"
                        >
                            Chrome của profile này đang tắt hoặc tiện ích không
                            liên lạc được với app. Hãy mở Chrome (đã đăng nhập
                            TikTok). Bài đã hẹn giờ trên TikTok vẫn đăng đúng
                            giờ; bài chưa hẹn sẽ chờ Chrome bật lại.
                        </p>
                        <Badge
                            :variant="
                                clientStatus[client.status]?.variant ??
                                'secondary'
                            "
                        >
                            {{ clientStatus[client.status]?.label ?? client.status }}
                        </Badge>
                        <Badge
                            v-if="client.profile_needs_choice"
                            variant="warning"
                            data-testid="fork-chrome-profile-warning"
                        >
                            Chưa chọn profile
                        </Badge>
                        <Badge
                            v-if="client.profile_conflict_with"
                            variant="destructive-subtle"
                            data-testid="fork-chrome-profile-conflict"
                        >
                            Trùng profile với “{{ client.profile_conflict_with }}”
                        </Badge>

                        <NativeSelect
                            v-if="profiles.length"
                            :model-value="selectedProfile(client)"
                            :disabled="busy === `profile-${client.id}`"
                            @update:model-value="
                                saveFromSelect(client, String($event ?? ''))
                            "
                        >
                            <option value="">— Chọn profile —</option>
                            <option
                                v-for="profile in profiles"
                                :key="`${profile.browser}|${profile.dir}`"
                                :value="optionValue(profile.browser, profile.dir)"
                            >
                                {{ profileLabel(profile) }}
                            </option>
                        </NativeSelect>
                        <Input
                            v-else
                            class="w-44"
                            placeholder="Profile, vd: Default"
                            :model-value="profileOf(client)"
                            @update:model-value="
                                profileDraft[client.id] = String($event)
                            "
                            @change="saveProfile(client, profileOf(client))"
                        />

                        <Button
                            variant="ghost"
                            size="sm"
                            :disabled="busy === `revoke-${client.id}`"
                            @click="revoke(client)"
                        >
                            <IconTrash class="size-4" />
                            Thu hồi
                        </Button>
                    </li>
                </ul>
                <p v-if="clients.length" class="text-sm text-muted-foreground">
                    Profile Chrome để tự mở khi Chrome đang tắt: chọn profile
                    mà bạn đã cài tiện ích và đăng nhập TikTok của kênh đó. Nếu
                    chỉ có một lựa chọn, app tự chọn giúp.
                </p>
                <p
                    v-if="!profiles.length && clients.length"
                    class="text-sm text-muted-foreground"
                >
                    Chưa có danh sách profile từ trợ lý mở Chrome. Bạn có thể
                    gõ tên thư mục profile (Default, Profile 1, ...).
                </p>
            </SettingsSection>

            <SettingsSection
                title="Tài khoản TikTok đăng qua Chrome"
                description="Bật công tắc để bài của tài khoản đó được đăng qua Chrome."
            >
                <div
                    v-if="!accounts.length"
                    class="rounded-lg border border-dashed p-4 text-sm text-muted-foreground"
                >
                    Chưa có tài khoản TikTok nào. Bạn có thể thêm từ một Chrome
                    đã đăng nhập ở phần bên dưới.
                </div>

                <ul v-else class="divide-y rounded-lg border">
                    <li
                        v-for="account in accounts"
                        :key="account.id"
                        class="flex flex-wrap items-center gap-x-4 gap-y-2 p-4 text-sm"
                    >
                        <div class="min-w-0 flex-1">
                            <p class="font-emphasis">
                                {{ account.display_name || account.username }}
                            </p>
                            <p class="text-sm text-muted-foreground">
                                @{{ account.username }}
                                <template v-if="account.chrome_only">
                                    · chỉ đăng qua Chrome
                                </template>
                                <template
                                    v-if="account.enabled && account.readiness"
                                >
                                    ·
                                    {{
                                        readiness[account.readiness] ??
                                        account.readiness
                                    }}
                                </template>
                            </p>
                        </div>
                        <Switch
                            :model-value="account.enabled"
                            :disabled="busy === `toggle-${account.id}`"
                            :aria-label="`Đăng qua Chrome cho ${account.username}`"
                            @update:model-value="toggle(account)"
                        />
                    </li>
                </ul>

                <div
                    v-if="chromeOnlyCandidates.length"
                    class="flex flex-col gap-2 rounded-lg border p-4 text-sm"
                >
                    <p class="font-emphasis">
                        Thêm tài khoản chỉ đăng qua Chrome
                    </p>
                    <p class="text-muted-foreground">
                        Dành cho tài khoản TikTok chưa có trong app. App tạo tài
                        khoản từ danh tính mà Chrome báo về.
                    </p>
                    <div
                        v-for="client in chromeOnlyCandidates"
                        :key="client.id"
                        class="flex items-center gap-3"
                    >
                        <span class="flex-1">
                            @{{ (client.tiktok_username ?? '').replace(/^@/, '') }}
                            <span class="text-sm text-muted-foreground">
                                ({{ client.label }})
                            </span>
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            :disabled="
                                !hasWorkspace || busy === `add-${client.id}`
                            "
                            @click="addFromClient(client)"
                        >
                            <IconPlus class="size-4" />
                            Thêm tài khoản
                        </Button>
                    </div>
                </div>
            </SettingsSection>

            <SettingsSection
                title="Cảnh báo qua Telegram"
                description="Báo ngay khi bài lên, bài lỗi, Chrome hoặc hub mất kết nối, giỏ hàng tạm dừng, kho sắp hết, và tổng kết mỗi ngày."
            >
                <div
                    class="flex flex-wrap items-center gap-3 rounded-lg border p-4 text-sm"
                    data-testid="fork-chrome-telegram"
                >
                    <Badge
                        :variant="telegram?.configured ? 'success' : 'warning'"
                    >
                        {{
                            telegram?.configured
                                ? 'Đã cấu hình'
                                : 'Chưa cấu hình'
                        }}
                    </Badge>
                    <span class="min-w-0 flex-1 text-muted-foreground">
                        Nối bot, chọn loại tin và xem trước tin nhắn ở trang
                        Telegram (không cần sửa file).
                    </span>
                    <Button
                        variant="outline"
                        size="sm"
                        :disabled="!telegram?.configured || busy === 'telegram'"
                        @click="telegramTest"
                    >
                        <Spinner v-if="busy === 'telegram'" class="size-4" />
                        Gửi thử
                    </Button>
                    <Button as-child size="sm">
                        <Link href="/settings/telegram">Cài đặt Telegram</Link>
                    </Button>
                </div>
            </SettingsSection>

            <SettingsSection
                title="Bài gần đây giao cho Chrome"
                description="30 lần giao gần nhất. Bài “Chưa rõ kết quả” không bao giờ tự đăng lại, hãy kiểm tra trên TikTok."
            >
                <template #actions>
                    <Button
                        variant="outline"
                        size="sm"
                        @click="router.reload({ only })"
                    >
                        <IconRefresh class="size-4" />
                        Làm mới
                    </Button>
                </template>

                <div
                    v-if="!jobs.length"
                    class="rounded-lg border border-dashed p-4 text-sm text-muted-foreground"
                >
                    Chưa có bài nào được giao cho Chrome.
                </div>

                <ul v-else class="divide-y rounded-lg border">
                    <li
                        v-for="job in jobs"
                        :key="job.id"
                        class="flex flex-col gap-1 p-4 text-sm"
                    >
                        <div class="flex flex-wrap items-center gap-2">
                            <Badge
                                :variant="
                                    jobState[job.state]?.variant ?? 'secondary'
                                "
                            >
                                {{ jobState[job.state]?.label ?? job.state }}
                            </Badge>
                            <Badge variant="outline">
                                <IconPlayerPlay class="size-3" />
                                {{ job.mode === 'now' ? 'Đăng ngay' : 'Hẹn giờ' }}
                            </Badge>
                            <span class="text-sm text-muted-foreground">
                                @{{ job.username }} ·
                                {{ fromNow(job.updated_at ?? job.created_at) }}
                            </span>
                        </div>
                        <p class="truncate" :title="job.caption">
                            {{ job.caption || '(không có chú thích)' }}
                        </p>
                        <p
                            v-if="job.state === 'posted' && job.mode === 'scheduled'"
                            class="text-sm font-emphasis text-amber-700 dark:text-amber-400"
                        >
                            Đã hẹn trên TikTok — muốn đổi thì sửa/huỷ trong
                            TikTok Studio.
                        </p>
                        <p
                            v-if="job.note"
                            class="text-sm text-muted-foreground"
                        >
                            {{ job.note }}
                        </p>
                    </li>
                </ul>
            </SettingsSection>
        </div>
    </SettingsLayout>
</template>

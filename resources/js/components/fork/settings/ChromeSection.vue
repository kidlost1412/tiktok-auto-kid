<script setup lang="ts">
// Trang riêng của bản Việt hoá: ghép nối tiện ích Chrome (TikTok Auto Kid) để đăng TikTok.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en) để không
// làm lệch bộ khoá dịch của các ngôn ngữ khác.
import { Link, router, usePoll } from '@inertiajs/vue3';
import {
    IconBrandChrome,
    IconBrandTelegram,
    IconCopy,
    IconHistory,
    IconPlayerPlay,
    IconPlugConnected,
    IconPlus,
    IconRefresh,
    IconSend,
    IconSettings,
    IconTrash,
    IconUsers,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import PairProgress from '@/components/fork/chrome/PairProgress.vue';
import SettingsSection from '@/components/settings/SettingsSection.vue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import dayjs from '@/dayjs';

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
    keep_alive?: boolean;
    keepalive?: KeepAlive;
}

interface KeepAlive {
    state:
        | 'running'
        | 'starting'
        | 'failed'
        | 'waiting'
        | 'launcher_down'
        | 'off'
        | 'no_profile';
    message: string | null;
    last_start_at: string | null;
    failures: number;
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

const props = defineProps<{
    pair: Pair | null;
    clients: ChromeClient[];
    accounts: TikTokAccount[];
    jobs: ChromeJobRow[];
    profiles: ChromeProfile[];
    telegram?: { configured: boolean };
    extensionPath: string;
    /** Bản tiện ích đi kèm app (đọc từ extension/autotok/manifest.json). */
    latestExtension?: string | null;
    serverUrl: string;
    hasWorkspace: boolean;
    backgroundMode?: { chrome: boolean | null; edge: boolean | null };
}>();

/** So sánh phiên bản dạng số (1.4.10 > 1.4.9): âm nếu a < b. */
function compareVersions(a: string, b: string): number {
    const pa = a.split('.').map((x) => parseInt(x, 10) || 0);
    const pb = b.split('.').map((x) => parseInt(x, 10) || 0);

    for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
        const d = (pa[i] ?? 0) - (pb[i] ?? 0);

        if (d !== 0) {
            return d;
        }
    }

    return 0;
}

/** Tiện ích đang chạy cũ hơn bản đi kèm app (chỉ khi cả hai đều biết). */
function extensionOutdated(version: string | null | undefined): boolean {
    return (
        !!props.latestExtension &&
        !!version &&
        compareVersions(version, props.latestExtension) < 0
    );
}

const only = [
    'pair',
    'clients',
    'accounts',
    'jobs',
    'profiles',
    'telegram',
    'backgroundMode',
];
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

// Thanh tiến trình ghép nối. Nút tạo hồ sơ Chrome mới gọi
// pairProgress.value?.start({ mode: 'create', profile, browser }) sau khi app đã yêu cầu mở Chrome.
const pairProgress = ref<InstanceType<typeof PairProgress> | null>(null);

const onPairChanged = (): void => router.reload({ only });

const makeCode = (): void =>
    run('pair', (done) =>
        router.post(
            '/settings/chrome/pair-code',
            {},
            {
                preserveScroll: true,
                onSuccess: () => pairProgress.value?.start({ mode: 'code' }),
                onFinish: done,
            },
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

const setKeepAlive = (client: ChromeClient, value: boolean): void =>
    run(`keepalive-${client.id}`, (done) =>
        router.post(
            `/settings/chrome/clients/${client.id}/keep-alive`,
            { keep_alive: value },
            { preserveScroll: true, onFinish: done },
        ),
    );

const openNow = (client: ChromeClient): void =>
    run(`open-${client.id}`, (done) =>
        router.post(
            `/settings/chrome/clients/${client.id}/open-now`,
            {},
            { preserveScroll: true, onFinish: done },
        ),
    );

const keepAliveChip = (
    client: ChromeClient,
): {
    label: string;
    variant: 'success' | 'warning' | 'destructive-subtle' | 'secondary';
} | null => {
    const k = client.keepalive;
    if (!k) return null;
    switch (k.state) {
        case 'running':
            return { label: 'Đang chạy', variant: 'success' };
        case 'starting':
            return { label: 'Đang tự mở…', variant: 'warning' };
        case 'failed':
            return {
                label: `Không mở được: ${(k.message ?? 'lỗi không rõ').slice(0, 90)}`,
                variant: 'destructive-subtle',
            };
        case 'launcher_down':
            return { label: 'Trợ lý mở Chrome chưa chạy', variant: 'warning' };
        case 'waiting':
            return { label: 'Sắp tự mở…', variant: 'warning' };
        case 'off':
            return { label: 'Không tự mở (đang tắt)', variant: 'secondary' };
        default:
            return null;
    }
};

const offlineHint = (client: ChromeClient): string => {
    if (!client.chrome_profile_dir) {
        return 'Chọn profile Chrome bên dưới để app tự mở Chrome này khi cần.';
    }
    if (client.keep_alive === false) {
        return 'Bạn đã tắt “Giữ Chrome luôn chạy nền”: app chỉ mở Chrome (không hiện cửa sổ) khi có bài đang chờ. Số liệu và bình luận sẽ không được thu khi Chrome tắt.';
    }
    return 'App sẽ tự mở Chrome này ở chế độ nền (không hiện cửa sổ) sau khoảng 3 phút mất liên lạc; nếu chưa được sẽ thử lại mỗi 5 phút. Bài đã hẹn giờ trên TikTok vẫn đăng đúng giờ; bài chưa hẹn chờ Chrome bật lại.';
};

const clientsNeedBackgroundHint = computed(() => {
    const bm = props.backgroundMode;
    return connectedClients.value.some((c) => {
        const v = c.chrome_browser === 'edge' ? bm?.edge : bm?.chrome;
        return v !== true;
    });
});

const backgroundModeOff = computed(
    () =>
        props.backgroundMode?.chrome === false ||
        props.backgroundMode?.edge === false,
);

const settingsUrl = computed(() =>
    connectedClients.value.some((c) => c.chrome_browser === 'edge')
        ? 'edge://settings/system'
        : 'chrome://settings/system',
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
    chrome_offline: 'Chrome đang tắt: app sẽ tự mở Chrome nền để đăng tiếp',
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

// Màu nhãn trạng thái (chấm + nền) theo biến thể cũ.
const pillTone = (variant?: string): string =>
    ({
        success: 'is-green',
        warning: 'is-amber',
        'destructive-subtle': 'is-red',
        info: 'is-blue',
    })[variant ?? ''] ?? '';

const fromNow = (value?: string | null): string =>
    value ? dayjs(value).locale('vi').fromNow() : 'chưa thấy';

const copy = async (text: string): Promise<void> => {
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        // Trình duyệt chặn clipboard: người dùng tự chép tay.
    }
};

const stats = computed(() => [
    {
        icon: IconBrandChrome,
        tone: 'green',
        value: connectedClients.value.length,
        label: 'Chrome đã kết nối',
    },
    {
        icon: IconUsers,
        tone: 'blue',
        value: props.accounts.filter((a) => a.enabled).length,
        label: 'Tài khoản đăng qua Chrome',
    },
    {
        icon: IconSend,
        tone: 'primary',
        value: props.jobs.filter((j) =>
            ['queued', 'claimed', 'uploading', 'ready', 'authorized'].includes(
                j.state,
            ),
        ).length,
        label: 'Bài đang xử lý',
    },
    {
        icon: IconHistory,
        tone: 'amber',
        value: props.jobs.filter((j) => j.state === 'posted').length,
        label: 'Bài đã đăng (30 gần nhất)',
    },
]);

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
    <div class="flex flex-col gap-5" data-testid="fork-chrome-page">
            <!-- Ô số liệu nhanh -->
            <div class="grid grid-cols-2 gap-3 xl:grid-cols-4">
                <div
                    v-for="s in stats"
                    :key="s.label"
                    class="flex items-center gap-3.5 rounded-[14px] border border-border bg-card px-5 py-4 shadow-card"
                >
                    <span class="fk-chip" :class="s.tone !== 'primary' && `is-${s.tone}`">
                        <component :is="s.icon" />
                    </span>
                    <div class="min-w-0">
                        <b
                            class="block text-[26px] leading-none font-semibold tracking-[-0.025em] tabular-nums"
                            >{{ s.value }}</b
                        >
                        <span class="mt-1.5 block truncate text-[13px] text-muted-foreground">{{
                            s.label
                        }}</span>
                    </div>
                </div>
            </div>

            <div class="grid items-start gap-5 xl:grid-cols-2">
                <div class="flex min-w-0 flex-col gap-5">
                    <SettingsSection
                        title="Ghép nối tiện ích TikTok Auto Kid"
                        description="TikTok chỉ cho đăng công khai khi đăng qua Chrome đang đăng nhập sẵn tài khoản của bạn. Cài tiện ích, rồi nhập mã 6 số bên dưới vào tiện ích."
                        :icon="IconPlugConnected"
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
                            class="grid gap-4 rounded-xl border border-border bg-muted p-4 sm:grid-cols-2"
                            data-testid="fork-chrome-connect-info"
                        >
                            <div class="min-w-0">
                                <p class="text-[13px] font-medium text-muted-foreground">
                                    Địa chỉ máy chủ (nhập vào tiện ích)
                                </p>
                                <div class="mt-1.5 flex flex-wrap items-center gap-2">
                                    <code
                                        class="text-xl font-semibold tracking-tight break-all"
                                        >{{ serverUrl || 'http://localhost:8010' }}</code
                                    >
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
                            <div class="min-w-0">
                                <p class="text-[13px] font-medium text-muted-foreground">
                                    Phiên bản tiện ích TikTok Auto Kid
                                </p>
                                <p
                                    v-if="latestExtension"
                                    class="mt-1.5 text-xl font-semibold tabular-nums"
                                >
                                    Mới nhất: v{{ latestExtension }}
                                </p>
                                <p
                                    v-for="c in clients"
                                    :key="c.id"
                                    :class="
                                        extensionOutdated(c.ext_version)
                                            ? 'mt-0.5 text-sm text-amber-800 dark:text-amber-300'
                                            : 'mt-0.5 text-sm text-success-text'
                                    "
                                >
                                    {{ c.label }}: đang chạy v{{ c.ext_version
                                    }}{{
                                        extensionOutdated(c.ext_version)
                                            ? ': hãy tải lại tiện ích ở chrome://extensions'
                                            : ' (đã mới nhất)'
                                    }}
                                </p>
                            </div>
                        </div>

                        <div
                            v-if="paired && !pairActive"
                            class="flex flex-wrap items-center gap-3 rounded-xl border border-success-text/30 bg-success-subtle p-4 text-sm text-foreground"
                            data-testid="fork-chrome-paired"
                        >
                            <span class="fk-pill is-green">Đã ghép nối</span>
                            <span class="min-w-0 flex-1">
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
                            class="flex flex-wrap items-center gap-4 rounded-xl border border-primary-strong/30 bg-primary-subtle p-4"
                        >
                            <code
                                class="text-3xl font-semibold tracking-[0.3em] text-primary-text tabular-nums"
                                data-testid="fork-chrome-code"
                                >{{ pair.code }}</code
                            >
                            <Button variant="outline" size="sm" @click="copy(pair.code)">
                                <IconCopy class="size-4" />
                                Chép mã
                            </Button>
                            <span class="text-sm text-muted-foreground">
                                Còn hiệu lực {{ countdown }}. Tạo mã mới sẽ làm mã cũ
                                mất hiệu lực.
                            </span>
                        </div>
                        <div
                            v-else-if="!paired"
                            class="rounded-xl border border-dashed border-border-strong p-4 text-sm text-muted-foreground"
                        >
                            Bấm “Tạo mã ghép nối”. Mã chỉ dùng được trong 5 phút và tối
                            đa 5 lần nhập.
                        </div>

                        <PairProgress ref="pairProgress" @changed="onPairChanged" />

                        <details
                            class="group rounded-xl border border-border bg-muted p-4 text-sm"
                        >
                            <summary class="cursor-pointer font-semibold">
                                Cách cài tiện ích
                            </summary>
                            <ol
                                class="mt-3 list-inside list-decimal space-y-2 text-muted-foreground"
                            >
                                <li>
                                    Mở Chrome, vào
                                    <code>chrome://extensions</code> (Edge:
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
                                    “Tiếp tục chạy ứng dụng nền khi đóng Google Chrome”,
                                    để tiện ích vẫn nhận việc khi bạn đã đóng cửa sổ
                                    Chrome.
                                </li>
                                <li>
                                    Sau mỗi lần cập nhật tiện ích, bấm nút tải lại (⟳) ở
                                    <code>chrome://extensions</code>.
                                </li>
                            </ol>
                        </details>
                    </SettingsSection>

                    <SettingsSection
                        v-if="clients.length && clientsNeedBackgroundHint"
                        title="Cho Chrome chạy nền khi đóng cửa sổ"
                        description="Làm một lần: để tiện ích không tắt theo khi bạn đóng cửa sổ Chrome cuối cùng."
                        :icon="IconSettings"
                        tone="amber"
                    >
                        <div
                            class="flex flex-col gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm"
                            data-testid="fork-chrome-background-hint"
                        >
                            <p v-if="backgroundModeOff">
                                Trợ lý đọc thấy cài đặt này đang <b>TẮT</b> trong trình
                                duyệt của bạn.
                            </p>
                            <p v-else>
                                Chưa xác định được cài đặt này trên máy (trợ lý chưa báo
                                về). Hãy kiểm tra giúp.
                            </p>
                            <ol class="list-decimal space-y-1 pl-5">
                                <li>
                                    Mở một tab mới, dán địa chỉ
                                    <code>{{ settingsUrl }}</code> rồi Enter (trang web
                                    không mở được trang này giúp bạn).
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        class="ml-1"
                                        @click="copy(settingsUrl)"
                                    >
                                        <IconCopy class="size-4" />
                                        Chép địa chỉ
                                    </Button>
                                </li>
                                <li>
                                    Bật “Tiếp tục chạy ứng dụng nền khi đóng Google
                                    Chrome” (Edge: “Tiếp tục chạy tiện ích và ứng dụng
                                    nền khi Microsoft Edge đóng”).
                                </li>
                                <li>
                                    Xong. App không tự sửa cấu hình này của Chrome vì
                                    Chrome có thể ghi đè khi đang chạy.
                                </li>
                            </ol>
                        </div>
                    </SettingsSection>

                    <SettingsSection
                        title="Cảnh báo qua Telegram"
                        description="Báo ngay khi bài lên, bài lỗi, Chrome hoặc hub mất kết nối, giỏ hàng tạm dừng, kho sắp hết, và tổng kết mỗi ngày."
                        :icon="IconBrandTelegram"
                        tone="blue"
                    >
                        <div
                            class="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-muted p-4 text-sm"
                            data-testid="fork-chrome-telegram"
                        >
                            <span
                                class="fk-pill"
                                :class="telegram?.configured ? 'is-green' : 'is-amber'"
                            >
                                {{ telegram?.configured ? 'Đã cấu hình' : 'Chưa cấu hình' }}
                            </span>
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
                </div>

                <div class="flex min-w-0 flex-col gap-5">
                    <SettingsSection
                        title="Chrome đã ghép nối"
                        description="Mỗi Chrome (profile) đăng nhập một tài khoản TikTok, và mỗi kênh cần một profile riêng."
                        :icon="IconBrandChrome"
                        tone="green"
                    >
                        <div
                            v-if="!clients.length"
                            class="rounded-xl border border-dashed border-border-strong p-5 text-sm text-muted-foreground"
                        >
                            Chưa có Chrome nào được ghép nối.
                        </div>

                        <ul v-else class="flex flex-col gap-3">
                            <li
                                v-for="client in clients"
                                :key="client.id"
                                class="flex flex-wrap items-center gap-x-3 gap-y-2.5 rounded-xl border border-border bg-muted p-4 text-sm"
                            >
                                <span class="fk-chip is-neutral">
                                    <IconBrandChrome />
                                </span>
                                <div class="min-w-0 flex-1">
                                    <p class="text-[15px] font-semibold">{{ client.label }}</p>
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
                                <span
                                    class="fk-pill"
                                    :class="pillTone(clientStatus[client.status]?.variant)"
                                >
                                    {{ clientStatus[client.status]?.label ?? client.status }}
                                </span>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    class="text-destructive-text hover:bg-critical-subtle"
                                    :disabled="busy === `revoke-${client.id}`"
                                    @click="revoke(client)"
                                >
                                    <IconTrash class="size-4" />
                                    Thu hồi
                                </Button>

                                <p
                                    v-if="client.status === 'offline'"
                                    class="w-full text-sm text-amber-800 dark:text-amber-300"
                                    data-testid="fork-chrome-offline-hint"
                                >
                                    {{ offlineHint(client) }}
                                </p>
                                <p
                                    v-if="
                                        client.keepalive?.state === 'failed' &&
                                        client.keepalive.message
                                    "
                                    class="w-full text-sm text-destructive-text"
                                    data-testid="fork-chrome-keepalive-error"
                                >
                                    {{ client.keepalive.message }}
                                </p>
                                <div
                                    v-if="
                                        keepAliveChip(client) ||
                                        client.profile_needs_choice ||
                                        client.profile_conflict_with
                                    "
                                    class="flex w-full flex-wrap items-center gap-2"
                                >
                                    <span
                                        v-if="keepAliveChip(client)"
                                        class="fk-pill max-w-full !whitespace-normal"
                                        :class="pillTone(keepAliveChip(client)!.variant)"
                                        data-testid="fork-chrome-keepalive-chip"
                                    >
                                        {{ keepAliveChip(client)!.label }}
                                    </span>
                                    <span
                                        v-if="client.profile_needs_choice"
                                        class="fk-pill is-amber"
                                        data-testid="fork-chrome-profile-warning"
                                    >
                                        Chưa chọn profile
                                    </span>
                                    <span
                                        v-if="client.profile_conflict_with"
                                        class="fk-pill is-red"
                                        data-testid="fork-chrome-profile-conflict"
                                    >
                                        Trùng profile với “{{ client.profile_conflict_with }}”
                                    </span>
                                </div>

                                <div class="w-full">
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
                                        class="w-full max-w-xs"
                                        placeholder="Profile, vd: Default"
                                        :model-value="profileOf(client)"
                                        @update:model-value="
                                            profileDraft[client.id] = String($event)
                                        "
                                        @change="saveProfile(client, profileOf(client))"
                                    />
                                </div>

                                <div
                                    v-if="client.chrome_profile_dir"
                                    class="flex w-full flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-3 text-sm"
                                >
                                    <label class="flex items-center gap-2.5 font-medium">
                                        <Switch
                                            :model-value="client.keep_alive ?? true"
                                            :disabled="busy === `keepalive-${client.id}`"
                                            aria-label="Giữ Chrome luôn chạy nền"
                                            data-testid="fork-chrome-keepalive-toggle"
                                            @update:model-value="
                                                setKeepAlive(client, Boolean($event))
                                            "
                                        />
                                        Giữ Chrome luôn chạy nền
                                    </label>
                                    <span class="text-muted-foreground">
                                        <template v-if="client.keepalive?.last_start_at">
                                            Tự mở lần cuối
                                            {{ fromNow(client.keepalive.last_start_at) }}
                                        </template>
                                        <template v-else>Chưa tự mở lần nào</template>
                                    </span>
                                    <Button
                                        v-if="client.keepalive?.state !== 'running'"
                                        variant="outline"
                                        size="sm"
                                        class="ml-auto"
                                        :disabled="busy === `open-${client.id}`"
                                        data-testid="fork-chrome-open-now"
                                        @click="openNow(client)"
                                    >
                                        <IconPlayerPlay class="size-4" />
                                        Mở Chrome nền ngay
                                    </Button>
                                </div>
                            </li>
                        </ul>
                        <p v-if="clients.length" class="text-sm text-muted-foreground">
                            Profile Chrome để tự mở khi Chrome đang tắt: chọn profile mà
                            bạn đã cài tiện ích và đăng nhập TikTok của kênh đó. Nếu chỉ
                            có một lựa chọn, app tự chọn giúp.
                        </p>
                        <p
                            v-if="!profiles.length && clients.length"
                            class="text-sm text-muted-foreground"
                        >
                            Chưa có danh sách profile từ trợ lý mở Chrome. Bạn có thể gõ
                            tên thư mục profile (Default, Profile 1, ...).
                        </p>
                    </SettingsSection>

                    <SettingsSection
                        title="Tài khoản TikTok đăng qua Chrome"
                        description="Bật công tắc để bài của tài khoản đó được đăng qua Chrome."
                        :icon="IconUsers"
                        tone="blue"
                    >
                        <div
                            v-if="!accounts.length"
                            class="rounded-xl border border-dashed border-border-strong p-5 text-sm text-muted-foreground"
                        >
                            Chưa có tài khoản TikTok nào. Bạn có thể thêm từ một Chrome
                            đã đăng nhập ở phần bên dưới.
                        </div>

                        <ul
                            v-else
                            class="divide-y divide-border overflow-hidden rounded-xl border border-border"
                        >
                            <li
                                v-for="account in accounts"
                                :key="account.id"
                                class="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3.5 text-sm transition-colors hover:bg-accent/60"
                            >
                                <div class="min-w-0 flex-1">
                                    <p class="text-[15px] font-semibold">
                                        {{ account.display_name || account.username }}
                                    </p>
                                    <p class="text-sm text-muted-foreground">
                                        @{{ account.username }}
                                        <template v-if="account.chrome_only">
                                            · chỉ đăng qua Chrome
                                        </template>
                                        <template v-if="account.enabled && account.readiness">
                                            ·
                                            {{ readiness[account.readiness] ?? account.readiness }}
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
                            class="flex flex-col gap-2 rounded-xl border border-border bg-muted p-4 text-sm"
                        >
                            <p class="font-semibold">Thêm tài khoản chỉ đăng qua Chrome</p>
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
                                    :disabled="!hasWorkspace || busy === `add-${client.id}`"
                                    @click="addFromClient(client)"
                                >
                                    <IconPlus class="size-4" />
                                    Thêm tài khoản
                                </Button>
                            </div>
                        </div>
                    </SettingsSection>
                </div>
            </div>

            <SettingsSection
                title="Bài gần đây giao cho Chrome"
                description="30 lần giao gần nhất. Bài “Chưa rõ kết quả” không bao giờ tự đăng lại, hãy kiểm tra trên TikTok."
                :icon="IconHistory"
                tone="amber"
            >
                <template #actions>
                    <Button variant="outline" size="sm" @click="router.reload({ only })">
                        <IconRefresh class="size-4" />
                        Làm mới
                    </Button>
                </template>

                <div
                    v-if="!jobs.length"
                    class="rounded-xl border border-dashed border-border-strong p-5 text-sm text-muted-foreground"
                >
                    Chưa có bài nào được giao cho Chrome.
                </div>

                <div
                    v-else
                    class="overflow-auto rounded-xl border border-border bg-card"
                >
                    <table class="w-full border-separate border-spacing-0 text-sm tabular-nums">
                        <thead>
                            <tr>
                                <th
                                    v-for="h in ['Trạng thái', 'Kiểu đăng', 'Tài khoản', 'Thời gian', 'Chú thích']"
                                    :key="h"
                                    class="sticky top-0 border-b border-border bg-muted px-4 py-2.5 text-left text-[13px] font-medium whitespace-nowrap text-muted-foreground"
                                >
                                    {{ h }}
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="job in jobs"
                                :key="job.id"
                                class="group align-top"
                            >
                                <td
                                    class="border-b border-border px-4 py-3 whitespace-nowrap group-last:border-b-0 group-hover:bg-accent/60"
                                >
                                    <span
                                        class="fk-pill"
                                        :class="pillTone(jobState[job.state]?.variant)"
                                    >
                                        {{ jobState[job.state]?.label ?? job.state }}
                                    </span>
                                </td>
                                <td
                                    class="border-b border-border px-4 py-3 whitespace-nowrap group-last:border-b-0 group-hover:bg-accent/60"
                                >
                                    <span class="inline-flex items-center gap-1.5 text-muted-foreground">
                                        <IconPlayerPlay class="size-3.5" />
                                        {{ job.mode === 'now' ? 'Đăng ngay' : 'Hẹn giờ' }}
                                    </span>
                                </td>
                                <td
                                    class="border-b border-border px-4 py-3 font-medium whitespace-nowrap group-last:border-b-0 group-hover:bg-accent/60"
                                >
                                    @{{ job.username }}
                                </td>
                                <td
                                    class="border-b border-border px-4 py-3 whitespace-nowrap text-muted-foreground group-last:border-b-0 group-hover:bg-accent/60"
                                >
                                    {{ fromNow(job.updated_at ?? job.created_at) }}
                                </td>
                                <td
                                    class="w-full min-w-[260px] border-b border-border px-4 py-3 group-last:border-b-0 group-hover:bg-accent/60"
                                >
                                    <p class="line-clamp-2" :title="job.caption">
                                        {{ job.caption || '(không có chú thích)' }}
                                    </p>
                                    <p
                                        v-if="job.state === 'posted' && job.mode === 'scheduled'"
                                        class="mt-1 text-sm font-semibold text-amber-800 dark:text-amber-300"
                                    >
                                        Đã hẹn trên TikTok — muốn đổi thì sửa/huỷ trong
                                        TikTok Studio.
                                    </p>
                                    <p v-if="job.note" class="mt-1 text-sm text-muted-foreground">
                                        {{ job.note }}
                                    </p>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </SettingsSection>
        </div>
</template>

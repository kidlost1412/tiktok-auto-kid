<script setup lang="ts">
// Hộp "Tự đăng theo khung" của Kho riêng: bật/tắt, cách viết caption, video trùng, kênh theo thư mục, AI ChatGPT + tài khoản luân phiên.
import {
    IconAlertTriangle,
    IconBolt,
    IconBrandOpenai,
    IconCheck,
    IconCircleCheckFilled,
    IconDownload,
    IconExternalLink,
    IconFolder,
    IconLoader2,
    IconMicrophone,
    IconPlus,
    IconRefresh,
    IconTrash,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import {
    callJson,
    type AutoPayload,
    type AutoSettings,
    type ChatGptAccount,
    type CliStatus,
} from '@/components/fork/kho/rieng';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { confirm as confirmDialog } from '@/composables/useConfirm';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const open = defineModel<boolean>('open', { default: false });
const emit = defineEmits<{ changed: [payload: AutoPayload] }>();

const data = ref<AutoPayload | null>(null);
const loading = ref(false);
const saving = ref(false);
const adding = ref<string | null>(null);
const loginUrl = ref<string | null>(null);
const installing = ref(false);
let poll: ReturnType<typeof setInterval> | null = null;
let cliPoll: ReturnType<typeof setInterval> | null = null;

const s = computed(() => data.value?.settings);

const load = async () => {
    loading.value = true;
    const r = await callJson<AutoPayload>('GET', '/auto/kho/rieng/tu-dong');
    loading.value = false;

    if (r.ok && r.data) {
        data.value = r.data;

        if (r.data.cli.installing && !cliPoll) {
            watchInstall();
        }

        loadLimits();
    } else {
        toast.error('Không tải được cài đặt tự đăng.');
    }
};

// ---- Hạn mức từng tài khoản ChatGPT (hỏi Codex riêng từng tài khoản, không tốn lượt).
interface LimitWindow {
    used: number;
    minutes: number | null;
    resets_at: string | null;
}

const limits = ref<
    Record<string, { windows: LimitWindow[]; reached: boolean } | null>
>({});

const loadLimits = async () => {
    for (const a of data.value?.chatgpt ?? []) {
        if (!a.ready) {
            continue;
        }

        const r = await callJson<{
            limits: { windows: LimitWindow[]; reached: boolean } | null;
            models?: AutoPayload['models'];
            models_from_accounts?: boolean;
            model_effective?: string | null;
        }>('GET', `/auto/kho/rieng/tu-dong/chatgpt/${a.id}/han-muc`);
        limits.value = { ...limits.value, [a.id]: r.data?.limits ?? null };

        // Cùng lượt app biết luôn model tài khoản dùng được: cập nhật danh sách model.
        if (data.value && r.data?.models) {
            data.value.models = r.data.models;
            data.value.models_from_accounts = !!r.data.models_from_accounts;
            data.value.model_effective = r.data.model_effective ?? null;
        }
    }
};

const windowName = (m: number | null) => {
    if (!m) {
        return '';
    }

    if (m >= 60 * 24 * 25) {
        return 'tháng';
    }

    if (m >= 60 * 24 * 6) {
        return 'tuần';
    }

    if (m >= 60 * 24) {
        return `${Math.round(m / 1440)} ngày`;
    }

    return `${Math.round(m / 60)} giờ`;
};

const fmtReset = (iso: string) => {
    const d = new Date(iso);
    const days = (d.getTime() - Date.now()) / 86_400_000;
    const hm = d.toLocaleTimeString('vi-VN', {
        hour: '2-digit',
        minute: '2-digit',
    });

    return days < 1
        ? `lúc ${hm}`
        : `${d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })}`;
};

watch(open, (o) => {
    if (o) {
        limits.value = {};
        load();
    } else {
        stopPoll();
        stopCliPoll();
    }
});

const save = async (changes: Partial<AutoSettings>) => {
    if (!data.value) {
        return;
    }

    // Đổi ngay trên màn hình, máy chủ trả về bản đã lưu.
    data.value.settings = { ...data.value.settings, ...changes };
    saving.value = true;
    const r = await callJson<AutoPayload>(
        'PATCH',
        '/auto/kho/rieng/tu-dong',
        changes,
    );
    saving.value = false;

    if (r.ok && r.data) {
        data.value = r.data;
        emit('changed', r.data);
    } else {
        toast.error('Chưa lưu được, anh thử lại.');
        load();
    }
};

// ---- Cài ChatGPT CLI (Codex) vào thư mục của app.
const stopCliPoll = () => {
    if (cliPoll) {
        clearInterval(cliPoll);
        cliPoll = null;
    }

    installing.value = false;
};

const setCli = (cli: CliStatus) => {
    if (data.value) {
        data.value.cli = cli;
        data.value.codex_installed = cli.installed;
    }
};

const installCli = async () => {
    installing.value = true;
    const r = await callJson<{ cli: CliStatus; error: string | null }>(
        'POST',
        '/auto/kho/rieng/tu-dong/codex-cli',
    );

    if (r.data?.cli) {
        setCli(r.data.cli);
    }

    if (!r.ok) {
        installing.value = false;
        toast.error(r.data?.error ?? 'Chưa cài được ChatGPT CLI.');

        return;
    }

    if (r.data?.cli.installed) {
        installing.value = false;
        toast.success('Đã cài ChatGPT CLI.');

        return;
    }

    watchInstall();
};

const watchInstall = () => {
    installing.value = true;

    if (cliPoll) {
        clearInterval(cliPoll);
    }

    let ticks = 0;
    cliPoll = setInterval(async () => {
        ticks++;
        // GET riêng để hỏi tiến độ (POST cài đặt giới hạn 6 lần/phút, hỏi 3 giây một lần sẽ bị chặn).
        const r = await callJson<{ cli: CliStatus }>(
            'GET',
            '/auto/kho/rieng/tu-dong/codex-cli',
        );
        const cli = r.data?.cli;

        if (cli) {
            setCli(cli);
        }

        if (cli?.installed) {
            stopCliPoll();
            toast.success('Đã cài xong ChatGPT CLI.');
        } else if ((cli && !cli.installing) || ticks > 400) {
            stopCliPoll();
            toast.error(cli?.error ?? 'Cài ChatGPT CLI chưa xong.');
        }
    }, 3000);
};

// ---- Kênh theo thư mục: không chọn kênh nào = mọi kênh có giỏ của sản phẩm.
const folderHas = (folderId: number, channelId: string) =>
    (s.value?.folder_channels[String(folderId)] ?? []).includes(channelId);

const folderAll = (folderId: number) =>
    !(s.value?.folder_channels[String(folderId)] ?? []).length;

const toggleFolderChannel = (folderId: number, channelId: string) => {
    const map = { ...(s.value?.folder_channels ?? {}) };
    const cur = map[String(folderId)] ?? [];
    map[String(folderId)] = cur.includes(channelId)
        ? cur.filter((c) => c !== channelId)
        : [...cur, channelId];
    save({ folder_channels: map });
};

const setFolderAll = (folderId: number) => {
    const map = { ...(s.value?.folder_channels ?? {}) };
    map[String(folderId)] = [];
    save({ folder_channels: map });
};

const initial = (name: string) =>
    name.replace(/^@/, '').charAt(0).toUpperCase() || '?';

// ---- Tài khoản ChatGPT
const stopPoll = () => {
    if (poll) {
        clearInterval(poll);
        poll = null;
    }
};

const addAccount = async () => {
    const r = await callJson<{
        ok: boolean;
        id: string | null;
        error: string | null;
    }>('POST', '/auto/kho/rieng/tu-dong/chatgpt');

    if (!r.ok || !r.data?.id) {
        toast.error(r.data?.error ?? 'Không mở được đăng nhập ChatGPT.');

        if (r.data?.id) {
            watchLogin(r.data.id);
        }

        return;
    }

    toast.success('Đã mở trang đăng nhập ChatGPT trong trình duyệt.');
    watchLogin(r.data.id);
};

const watchLogin = (id: string) => {
    adding.value = id;
    loginUrl.value = null;
    stopPoll();
    let ticks = 0;
    poll = setInterval(async () => {
        ticks++;
        const r = await callJson<{
            account: ChatGptAccount | null;
            url: string | null;
        }>('GET', `/auto/kho/rieng/tu-dong/chatgpt/${id}`);
        loginUrl.value = r.data?.url ?? loginUrl.value;

        if (r.data?.account?.ready) {
            stopPoll();
            adding.value = null;
            toast.success(
                `Đã thêm tài khoản ${r.data.account.email ?? 'ChatGPT'}.`,
            );
            load();
        } else if (
            (r.data && !r.data.account?.logging_in && ticks > 5) ||
            ticks > 300
        ) {
            // Lượt đăng nhập đã đóng mà chưa xong (hoặc quá 15 phút).
            stopPoll();
            adding.value = null;
            load();
        }
    }, 3000);
};

const removeAccount = async (a: ChatGptAccount) => {
    if (
        !(await confirmDialog({
            title: `Bỏ tài khoản ${a.email ?? 'ChatGPT'}?`,
            description:
                'App sẽ không dùng tài khoản này nữa. Tài khoản ChatGPT của anh vẫn còn nguyên.',
            confirmText: 'Bỏ tài khoản',
            destructive: true,
        }))
    ) {
        return;
    }

    await callJson('DELETE', `/auto/kho/rieng/tu-dong/chatgpt/${a.id}`);

    if (adding.value === a.id) {
        stopPoll();
        adding.value = null;
    }

    load();
};

const accountStatus = (a: ChatGptAccount): { text: string; cls: string } => {
    if (!a.ready) {
        return a.logging_in || adding.value === a.id
            ? {
                  text: 'Đang chờ anh đăng nhập…',
                  cls: 'text-amber-700 dark:text-amber-300',
              }
            : {
                  text: 'Chưa đăng nhập xong',
                  cls: 'text-foreground/70',
              };
    }

    if (a.cooldown_until) {
        return {
            text: `Hết lượt, nghỉ tới ${dayjs(a.cooldown_until).format('HH:mm DD/MM')}`,
            cls: 'text-amber-700 dark:text-amber-300',
        };
    }

    if (a.last_error) {
        return { text: a.last_error, cls: 'text-red-600 dark:text-red-400' };
    }

    return { text: 'Sẵn sàng', cls: 'text-emerald-700 dark:text-emerald-400' };
};

const readyAccounts = computed(
    () => (data.value?.chatgpt ?? []).filter((a) => a.ready).length,
);

const countLine = computed(() => {
    const c = data.value?.counts ?? {};
    const parts = [
        c.ok ? `${c.ok} AI đã chọn sản phẩm` : '',
        c.unsure ? `${c.unsure} chờ anh chọn sản phẩm` : '',
        c.cho ? `${c.cho} chờ AI xem` : '',
        (c.error ?? 0) + (c.gave_up ?? 0)
            ? `${(c.error ?? 0) + (c.gave_up ?? 0)} AI chưa xem được`
            : '',
    ].filter(Boolean);

    return parts.length ? parts.join(' · ') : 'Chưa có video nào chờ đăng.';
});

onBeforeUnmount(() => {
    stopPoll();
    stopCliPoll();
});

// ---- Model + mức nghĩ: chỉ hiện mức nghĩ model đó có.
// Model đang dùng thật: model đã chọn, hoặc model app thay vào khi tài khoản không có model đã chọn.
const curModel = computed(
    () => data.value?.model_effective ?? s.value?.model ?? '',
);

const modelEfforts = computed(() => {
    const m = data.value?.models[curModel.value];

    return (m?.efforts ?? []).map((key) => ({
        key,
        label: data.value?.efforts[key] ?? key,
    }));
});

// Fast: chỉ bật được khi model đó có Fast với gói ChatGPT của anh (gói free không có).
const fastOk = computed(
    () =>
        data.value?.models[curModel.value]?.fast ??
        !data.value?.models_from_accounts,
);

// ---- Video AI chưa xem được: cho thử lại ngay.
const failed = computed(
    () => (data.value?.counts.error ?? 0) + (data.value?.counts.gave_up ?? 0),
);
const retrying = ref(false);

const retryAll = async () => {
    retrying.value = true;
    const r = await callJson<AutoPayload & { retried: number }>(
        'POST',
        '/auto/kho/rieng/tu-dong/ai-thu-lai',
    );
    retrying.value = false;

    if (r.ok && r.data) {
        const retried = r.data.retried;
        data.value = r.data;
        emit('changed', r.data);
        loadLimits();
        toast.success(
            retried
                ? `AI sẽ xem lại ${retried} video trong vòng 2 phút.`
                : 'Không có video nào cần xem lại.',
        );
    } else {
        toast.error('Chưa thử lại được, anh bấm lại nhé.');
    }
};

const pickModel = (key: string) => {
    const efforts = data.value?.models[key]?.efforts ?? [];
    const effort = efforts.includes(s.value?.effort ?? '')
        ? s.value?.effort
        : 'low';
    save({ model: key, effort });
};

// ---- Kiểu chung: lựa chọn dạng thẻ, đang chọn = viền đậm + chấm tròn đầy.
const optionCls = (on: boolean) =>
    cn(
        'flex min-w-0 flex-1 items-start gap-2.5 rounded-xl border-2 px-3 py-2.5 text-left transition',
        on
            ? 'border-violet-600 bg-violet-50 shadow-sm dark:border-primary dark:bg-primary/10'
            : 'border-border bg-background hover:border-foreground/40 hover:bg-muted/50',
    );

const dotCls = (on: boolean) =>
    cn(
        'mt-0.5 flex size-[18px] shrink-0 items-center justify-center rounded-full border-2',
        on
            ? 'border-violet-600 bg-violet-600 dark:border-primary dark:bg-primary'
            : 'border-foreground/40 bg-background',
    );

const chipCls = (on: boolean) =>
    cn(
        'inline-flex items-center gap-1.5 rounded-full border-2 py-0.5 pr-2.5 pl-0.5 text-[13px] font-medium transition',
        on
            ? 'border-violet-600 bg-violet-50 text-foreground dark:border-primary dark:bg-primary/10'
            : 'border-border bg-background text-foreground/80 hover:border-foreground/40',
    );

const sectionCls = 'flex flex-col gap-3 rounded-2xl border bg-card p-4';
const hintCls = 'text-[13px] leading-snug text-foreground/70';
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent
            class="max-h-[90dvh] overflow-x-hidden overflow-y-auto sm:max-w-2xl"
            data-testid="fork-rieng-auto-dialog"
        >
            <DialogHeader>
                <DialogTitle class="text-lg"
                    >Kho riêng tự đăng theo khung</DialogTitle
                >
                <DialogDescription class="text-[13px] text-foreground/70">
                    AI xem từng video mới (hình và chữ trên video), chọn sản
                    phẩm gắn giỏ và viết caption. Video sẵn sàng được xếp vào
                    giờ trống của khung đăng,
                    <b class="text-foreground">trước video Xưởng</b>. Mỗi video
                    chỉ đăng một lần trên một kênh.
                </DialogDescription>
            </DialogHeader>

            <div
                v-if="!data"
                class="flex items-center gap-2 py-8 text-sm text-foreground/70"
            >
                <IconLoader2 class="size-4 animate-spin" /> Đang tải…
            </div>

            <div v-else-if="s" class="flex min-w-0 flex-col gap-4 text-sm">
                <!-- Bật / tắt -->
                <label
                    :class="
                        cn(
                            'flex cursor-pointer items-center justify-between gap-3 rounded-2xl border-2 p-4 transition',
                            s.enabled
                                ? 'border-emerald-500 bg-emerald-50 dark:border-emerald-600 dark:bg-emerald-950/40'
                                : 'border-border bg-card',
                        )
                    "
                >
                    <span class="min-w-0">
                        <span
                            class="flex items-center gap-2 text-base font-semibold"
                        >
                            Tự đăng kho riêng
                            <span
                                :class="
                                    cn(
                                        'rounded-full px-2 py-0.5 text-xs font-semibold',
                                        s.enabled
                                            ? 'bg-emerald-600 text-white'
                                            : 'bg-muted text-foreground/70',
                                    )
                                "
                                >{{ s.enabled ? 'Đang bật' : 'Đang tắt' }}</span
                            >
                        </span>
                        <span :class="cn(hintCls, 'mt-0.5 block')">{{
                            countLine
                        }}</span>
                    </span>
                    <Switch
                        :model-value="s.enabled"
                        aria-label="Bật tự đăng kho riêng"
                        data-testid="fork-rieng-auto-enabled"
                        @update:model-value="
                            (v: boolean) => save({ enabled: v })
                        "
                    />
                </label>

                <div
                    v-if="failed"
                    class="-mt-1 flex flex-wrap items-center justify-between gap-2 rounded-xl border-2 border-amber-400 bg-amber-50 px-3 py-2 text-[13px] text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100"
                    data-testid="fork-rieng-ai-failed"
                >
                    <span
                        >{{ failed }} video AI chưa xem được. App tự thử lại sau
                        ít phút; sửa xong lỗi thì bấm để xem lại ngay.</span
                    >
                    <Button
                        size="sm"
                        :disabled="retrying"
                        data-testid="fork-rieng-ai-retry"
                        @click="retryAll"
                    >
                        <IconLoader2
                            v-if="retrying"
                            class="size-4 animate-spin"
                        />
                        <IconRefresh v-else class="size-4" />
                        Cho AI xem lại ngay
                    </Button>
                </div>

                <!-- Chuẩn bị: chỉ hiện việc còn thiếu, xong hết thì ẩn cả khung -->
                <section
                    v-if="!data.codex_installed || readyAccounts === 0"
                    class="flex flex-col gap-2.5 rounded-2xl border-2 border-amber-400 bg-amber-50 p-4 text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100"
                    data-testid="fork-rieng-auto-setup"
                >
                    <h3 class="flex items-center gap-1.5 font-semibold">
                        <IconAlertTriangle class="size-4" /> Cần chuẩn bị trước
                        khi AI xem được video
                    </h3>
                    <div
                        v-if="!data.codex_installed"
                        class="flex flex-wrap items-center gap-2"
                    >
                        <span
                            class="size-2.5 shrink-0 rounded-full bg-amber-600"
                        />
                        <span class="min-w-0 flex-1">
                            <b>Cài ChatGPT CLI (Codex)</b>
                            <template v-if="installing">
                                — đang tải và cài, khoảng 1–3 phút…</template
                            >
                            <template v-else-if="!data.cli.node">
                                — máy chưa có Node.js: anh cài Node.js bản LTS ở
                                nodejs.org trước rồi bấm Cài.</template
                            >
                            <span
                                v-if="data.cli.error && !installing"
                                class="block text-xs text-red-700 dark:text-red-300"
                                >{{ data.cli.error }}</span
                            >
                        </span>
                        <Button
                            size="sm"
                            :disabled="installing"
                            data-testid="fork-codex-install"
                            @click="installCli"
                        >
                            <IconLoader2
                                v-if="installing"
                                class="size-4 animate-spin"
                            />
                            <IconDownload v-else class="size-4" />
                            {{ installing ? 'Đang cài…' : 'Cài ChatGPT CLI' }}
                        </Button>
                    </div>
                    <div
                        v-if="readyAccounts === 0"
                        class="flex items-center gap-2"
                    >
                        <span
                            class="size-2.5 shrink-0 rounded-full bg-amber-600"
                        />
                        <span>
                            <b>Thêm tài khoản ChatGPT</b> — bấm "Thêm tài khoản
                            ChatGPT" ở cuối hộp này
                        </span>
                    </div>
                </section>

                <!-- Caption -->
                <section :class="sectionCls">
                    <h3 class="text-base font-semibold">Caption</h3>
                    <div class="flex flex-col gap-2 sm:flex-row">
                        <button
                            type="button"
                            :class="optionCls(s.caption_mode === 'ai')"
                            :aria-pressed="s.caption_mode === 'ai'"
                            @click="save({ caption_mode: 'ai' })"
                        >
                            <span :class="dotCls(s.caption_mode === 'ai')">
                                <span
                                    v-if="s.caption_mode === 'ai'"
                                    class="size-1.5 rounded-full bg-white dark:bg-primary-foreground"
                                />
                            </span>
                            <span class="min-w-0">
                                <span class="block font-semibold">AI viết</span>
                                <span :class="hintCls"
                                    >Từ nội dung video, kèm 3 hashtag</span
                                >
                            </span>
                        </button>
                        <button
                            type="button"
                            :class="optionCls(s.caption_mode === 'kid')"
                            :aria-pressed="s.caption_mode === 'kid'"
                            @click="save({ caption_mode: 'kid' })"
                        >
                            <span :class="dotCls(s.caption_mode === 'kid')">
                                <span
                                    v-if="s.caption_mode === 'kid'"
                                    class="size-1.5 rounded-full bg-white dark:bg-primary-foreground"
                                />
                            </span>
                            <span class="min-w-0">
                                <span class="block font-semibold">Tự viết</span>
                                <span :class="hintCls"
                                    >Viết trên thẻ từng video</span
                                >
                            </span>
                        </button>
                    </div>
                    <div class="flex flex-col divide-y rounded-xl border">
                        <label
                            class="flex cursor-pointer items-center justify-between gap-3 px-3 py-2.5"
                        >
                            <span>
                                <span class="block font-medium"
                                    >Chưa có caption vẫn đăng</span
                                >
                                <span :class="hintCls"
                                    >Đăng không chữ thay vì chờ</span
                                >
                            </span>
                            <Switch
                                :model-value="s.empty_caption_ok"
                                @update:model-value="
                                    (v: boolean) =>
                                        save({ empty_caption_ok: v })
                                "
                            />
                        </label>
                        <label
                            v-if="s.caption_mode === 'ai'"
                            class="flex cursor-pointer items-center justify-between gap-3 px-3 py-2.5"
                        >
                            <span>
                                <span class="block font-medium"
                                    >Duyệt caption AI trước khi đăng</span
                                >
                                <span :class="hintCls"
                                    >Bấm "Duyệt" trên thẻ video thì mới
                                    đăng</span
                                >
                            </span>
                            <Switch
                                :model-value="s.approve_first"
                                @update:model-value="
                                    (v: boolean) => save({ approve_first: v })
                                "
                            />
                        </label>
                    </div>
                    <p :class="hintCls">
                        Caption anh tự sửa trên thẻ video luôn được dùng.
                        Hashtag và ảnh bìa theo cài đặt của từng sản phẩm (mặc
                        định / một ảnh cố định / xoay vòng), giống video Xưởng.
                    </p>
                </section>

                <!-- Video trùng -->
                <section :class="sectionCls">
                    <h3 class="text-base font-semibold">
                        Video trùng video đã có
                    </h3>
                    <div class="flex flex-col gap-2 sm:flex-row">
                        <button
                            v-for="o in [
                                {
                                    key: 'ask' as const,
                                    title: 'Hỏi anh trước',
                                    note: 'Chờ anh bấm “Vẫn đăng” trên thẻ',
                                },
                                {
                                    key: 'allow' as const,
                                    title: 'Cứ đăng',
                                    note: 'Thẻ video vẫn hiện cảnh báo trùng',
                                },
                            ]"
                            :key="o.key"
                            type="button"
                            :class="optionCls(s.duplicates === o.key)"
                            :aria-pressed="s.duplicates === o.key"
                            @click="save({ duplicates: o.key })"
                        >
                            <span :class="dotCls(s.duplicates === o.key)">
                                <span
                                    v-if="s.duplicates === o.key"
                                    class="size-1.5 rounded-full bg-white dark:bg-primary-foreground"
                                />
                            </span>
                            <span class="min-w-0">
                                <span class="block font-semibold">{{
                                    o.title
                                }}</span>
                                <span :class="hintCls">{{ o.note }}</span>
                            </span>
                        </button>
                    </div>
                </section>

                <!-- Kênh theo thư mục -->
                <section :class="sectionCls">
                    <h3 class="text-base font-semibold">Kênh được đăng</h3>
                    <p :class="hintCls">
                        Mặc định kênh nào có giỏ hàng của sản phẩm đều được
                        đăng. Chọn kênh cho từng thư mục nếu muốn; riêng từng
                        video thì chỉnh trên thẻ video.
                    </p>
                    <div v-if="!data.channels.length" :class="hintCls">
                        Chưa có kênh TikTok nào bật tự động đăng.
                    </div>
                    <div
                        v-else
                        class="flex flex-col divide-y rounded-xl border"
                    >
                        <div
                            v-for="f in data.folders"
                            :key="f.id"
                            class="flex flex-col gap-2 px-3 py-2.5"
                            :data-testid="`fork-rieng-auto-folder-${f.id}`"
                        >
                            <div
                                class="flex min-w-0 items-center gap-1.5 font-semibold"
                            >
                                <IconFolder
                                    class="size-4 shrink-0 text-foreground/60"
                                />
                                <span class="truncate">{{ f.name }}</span>
                            </div>
                            <div class="flex flex-wrap gap-1.5">
                                <button
                                    type="button"
                                    :class="
                                        cn(chipCls(folderAll(f.id)), 'pl-2.5')
                                    "
                                    :aria-pressed="folderAll(f.id)"
                                    @click="setFolderAll(f.id)"
                                >
                                    <IconCheck
                                        v-if="folderAll(f.id)"
                                        class="size-3.5 text-violet-600 dark:text-primary"
                                        stroke-width="3"
                                    />
                                    Mọi kênh có giỏ
                                </button>
                                <button
                                    v-for="c in data.channels"
                                    :key="c.id"
                                    type="button"
                                    :class="chipCls(folderHas(f.id, c.id))"
                                    :aria-pressed="folderHas(f.id, c.id)"
                                    @click="toggleFolderChannel(f.id, c.id)"
                                >
                                    <Avatar class="size-6 shrink-0">
                                        <AvatarImage
                                            v-if="c.avatar_url"
                                            :src="c.avatar_url"
                                            alt=""
                                        />
                                        <AvatarFallback
                                            class="text-[11px] font-semibold"
                                            >{{
                                                initial(c.name)
                                            }}</AvatarFallback
                                        >
                                    </Avatar>
                                    {{ c.name }}
                                    <IconCheck
                                        v-if="folderHas(f.id, c.id)"
                                        class="size-3.5 text-violet-600 dark:text-primary"
                                        stroke-width="3"
                                    />
                                </button>
                            </div>
                        </div>
                    </div>
                </section>

                <!-- AI -->
                <section :class="sectionCls">
                    <h3
                        class="flex items-center gap-1.5 text-base font-semibold"
                    >
                        <IconBrandOpenai class="size-5" /> AI ChatGPT (Codex
                        CLI)
                    </h3>

                    <div class="flex flex-col gap-1.5">
                        <span class="font-medium">Model</span>
                        <div class="grid gap-2 sm:grid-cols-2">
                            <button
                                v-for="(m, key) in data.models"
                                :key="key"
                                type="button"
                                :class="optionCls(curModel === key)"
                                :aria-pressed="curModel === key"
                                :data-testid="`fork-rieng-model-${key}`"
                                @click="pickModel(String(key))"
                            >
                                <span :class="dotCls(curModel === key)">
                                    <span
                                        v-if="curModel === key"
                                        class="size-1.5 rounded-full bg-white dark:bg-primary-foreground"
                                    />
                                </span>
                                <span class="min-w-0">
                                    <span class="block font-semibold">{{
                                        m.name
                                    }}</span>
                                    <span :class="hintCls">{{ m.note }}</span>
                                </span>
                            </button>
                        </div>
                        <span
                            v-if="data.model_effective"
                            class="text-[13px] text-amber-700 dark:text-amber-400"
                            >Model chọn trước đây ({{ s.model }}) tài khoản của
                            anh không dùng được, app tự dùng
                            {{
                                data.models[data.model_effective]?.name ??
                                data.model_effective
                            }}
                            thay.</span
                        >
                        <span
                            v-else-if="data.models_from_accounts"
                            :class="hintCls"
                            >Chỉ hiện model tài khoản ChatGPT của anh dùng
                            được.</span
                        >
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <span class="font-medium"
                            >Mức nghĩ
                            <span class="font-normal text-foreground/70"
                                >(cao hơn = chậm hơn, tốn lượt hơn)</span
                            ></span
                        >
                        <div
                            class="flex flex-wrap gap-1 rounded-xl border-2 bg-muted/40 p-1"
                        >
                            <button
                                v-for="e in modelEfforts"
                                :key="e.key"
                                type="button"
                                :class="
                                    cn(
                                        'flex-1 rounded-lg px-3 py-1.5 text-[13px] font-semibold whitespace-nowrap transition',
                                        s.effort === e.key
                                            ? 'bg-violet-600 text-white shadow dark:bg-primary dark:text-primary-foreground'
                                            : 'text-foreground/80 hover:bg-background',
                                    )
                                "
                                :aria-pressed="s.effort === e.key"
                                @click="save({ effort: e.key })"
                            >
                                {{ e.label }}
                            </button>
                        </div>
                    </div>

                    <label
                        :class="
                            cn(
                                'flex cursor-pointer items-center justify-between gap-3 rounded-xl border-2 px-3 py-2.5 transition',
                                !fastOk && 'cursor-not-allowed opacity-60',
                                s.fast && fastOk
                                    ? 'border-amber-500 bg-amber-50 dark:border-amber-600 dark:bg-amber-950/40'
                                    : 'border-border',
                            )
                        "
                    >
                        <span class="flex items-start gap-2">
                            <IconBolt
                                :class="
                                    cn(
                                        'mt-0.5 size-5 shrink-0',
                                        s.fast && fastOk
                                            ? 'fill-amber-400 text-amber-600'
                                            : 'text-foreground/60',
                                    )
                                "
                            />
                            <span>
                                <span class="block font-semibold"
                                    >Chế độ Fast</span
                                >
                                <span :class="hintCls">{{
                                    fastOk
                                        ? 'Nhanh gấp 2 lần, tốn lượt ChatGPT hơn'
                                        : 'Gói ChatGPT của anh chưa có Fast cho model này (cần gói trả phí)'
                                }}</span>
                            </span>
                        </span>
                        <Switch
                            :model-value="s.fast && fastOk"
                            :disabled="!fastOk"
                            aria-label="Chế độ Fast"
                            data-testid="fork-rieng-auto-fast"
                            @update:model-value="
                                (v: boolean) => save({ fast: v })
                            "
                        />
                    </label>

                    <div
                        class="flex items-start gap-2 rounded-xl border-2 px-3 py-2.5"
                        data-testid="fork-rieng-speech"
                    >
                        <IconMicrophone
                            class="mt-0.5 size-5 shrink-0 text-foreground/70"
                        />
                        <span class="min-w-0">
                            <span class="block font-semibold"
                                >Nghe lời nói trong video
                                <span class="font-normal text-foreground/70"
                                    >(miễn phí, chạy trên máy)</span
                                ></span
                            >
                            <span
                                :class="
                                    cn(
                                        'block text-[13px]',
                                        data.speech.installed
                                            ? 'text-emerald-700 dark:text-emerald-400'
                                            : data.speech.error ||
                                                !data.speech.python
                                              ? 'text-amber-700 dark:text-amber-400'
                                              : 'text-foreground/70',
                                    )
                                "
                                >{{
                                    data.speech.installed
                                        ? 'Sẵn sàng. App nghe lời nói trong video để AI nhận sản phẩm chắc hơn.'
                                        : data.speech.installing
                                          ? 'Đang cài lần đầu (vài phút)…'
                                          : !data.speech.python
                                            ? 'Máy chưa có Python của Xưởng Video nên chưa nghe được.'
                                            : data.speech.error
                                              ? data.speech.error +
                                                ' (app sẽ thử cài lại)'
                                              : 'App tự cài lần đầu khi cần (khoảng 2 GB).'
                                }}</span
                            >
                        </span>
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <span class="font-medium">Tài khoản ChatGPT</span>
                        <div class="flex flex-col divide-y rounded-xl border">
                            <div
                                v-for="a in data.chatgpt"
                                :key="a.id"
                                class="flex items-center gap-3 px-3 py-2.5"
                                :data-testid="`fork-chatgpt-${a.id}`"
                            >
                                <IconCircleCheckFilled
                                    v-if="
                                        a.ready &&
                                        !a.cooldown_until &&
                                        !a.last_error
                                    "
                                    class="size-5 shrink-0 text-emerald-600"
                                />
                                <IconAlertTriangle
                                    v-else
                                    class="size-5 shrink-0 text-amber-600"
                                />
                                <div class="min-w-0 flex-1">
                                    <div class="truncate font-semibold">
                                        {{ a.email ?? 'Tài khoản mới' }}
                                        <span
                                            v-if="a.plan"
                                            class="ml-1 rounded bg-foreground/10 px-1.5 py-0.5 text-[11px] uppercase"
                                            >{{ a.plan }}</span
                                        >
                                    </div>
                                    <div
                                        :class="
                                            cn(
                                                'truncate text-[13px]',
                                                accountStatus(a).cls,
                                            )
                                        "
                                    >
                                        {{ accountStatus(a).text
                                        }}{{
                                            a.uses
                                                ? ` · đã dùng ${a.uses} lần`
                                                : ''
                                        }}
                                    </div>
                                    <div
                                        v-if="a.ready"
                                        class="mt-1.5 flex flex-col gap-1"
                                        :data-testid="`fork-chatgpt-limits-${a.id}`"
                                    >
                                        <div
                                            v-if="limits[a.id] === undefined"
                                            :class="cn(hintCls, 'text-xs')"
                                        >
                                            Đang xem hạn mức…
                                        </div>
                                        <div
                                            v-else-if="limits[a.id] === null"
                                            :class="cn(hintCls, 'text-xs')"
                                        >
                                            Chưa xem được hạn mức.
                                        </div>
                                        <div
                                            v-for="(w, wi) in limits[a.id]
                                                ?.windows ?? []"
                                            v-else
                                            :key="wi"
                                            class="flex flex-col gap-0.5"
                                        >
                                            <div
                                                class="flex justify-between gap-2 text-xs text-foreground/75"
                                            >
                                                <span
                                                    >Hạn mức
                                                    {{ windowName(w.minutes) }}:
                                                    còn
                                                    <b class="text-foreground"
                                                        >{{
                                                            Math.max(
                                                                0,
                                                                100 - w.used,
                                                            )
                                                        }}%</b
                                                    ></span
                                                >
                                                <span
                                                    v-if="w.resets_at"
                                                    class="shrink-0"
                                                    >đặt lại
                                                    {{
                                                        fmtReset(w.resets_at)
                                                    }}</span
                                                >
                                            </div>
                                            <div
                                                class="h-1.5 overflow-hidden rounded-full bg-muted"
                                            >
                                                <div
                                                    :class="
                                                        cn(
                                                            'h-full rounded-full',
                                                            w.used >= 90
                                                                ? 'bg-red-500'
                                                                : w.used >= 70
                                                                  ? 'bg-amber-500'
                                                                  : 'bg-emerald-500',
                                                        )
                                                    "
                                                    :style="{
                                                        width:
                                                            Math.max(
                                                                0,
                                                                100 - w.used,
                                                            ) + '%',
                                                    }"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <Button
                                    size="icon"
                                    variant="ghost"
                                    class="size-8"
                                    :aria-label="`Bỏ tài khoản ${a.email ?? ''}`"
                                    @click="removeAccount(a)"
                                >
                                    <IconTrash class="size-4" />
                                </Button>
                            </div>
                            <div
                                v-if="!data.chatgpt.length"
                                :class="cn(hintCls, 'px-3 py-3')"
                            >
                                Chưa có tài khoản nào.
                            </div>
                        </div>
                    </div>

                    <div
                        v-if="adding"
                        class="rounded-xl border-2 border-sky-400 bg-sky-50 p-3 text-[13px] text-sky-950 dark:border-sky-700 dark:bg-sky-950/40 dark:text-sky-100"
                    >
                        Đăng nhập ChatGPT trong trình duyệt vừa mở, xong quay
                        lại đây (app tự nhận).
                        <a
                            v-if="loginUrl"
                            :href="loginUrl"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="ml-1 inline-flex items-center gap-0.5 font-semibold underline"
                            >Trình duyệt không tự mở? Bấm vào đây
                            <IconExternalLink class="size-3"
                        /></a>
                    </div>

                    <div class="flex flex-wrap items-center gap-2">
                        <Button
                            size="sm"
                            :disabled="!data.codex_installed || !!adding"
                            data-testid="fork-chatgpt-add"
                            @click="addAccount"
                        >
                            <IconLoader2
                                v-if="adding"
                                class="size-4 animate-spin"
                            />
                            <IconPlus v-else class="size-4" />
                            Thêm tài khoản ChatGPT
                        </Button>
                        <span :class="cn(hintCls, 'min-w-0 flex-1')">{{
                            data.codex_installed
                                ? 'Nhiều tài khoản thì app dùng luân phiên; tài khoản hết lượt tự nghỉ, đổi sang tài khoản khác.'
                                : 'Cài ChatGPT CLI ở trên trước.'
                        }}</span>
                    </div>
                </section>

                <div
                    v-if="saving || loading"
                    class="text-xs text-foreground/70"
                >
                    Đang lưu…
                </div>
            </div>
        </DialogContent>
    </Dialog>
</template>

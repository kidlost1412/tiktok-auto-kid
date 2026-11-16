<script setup lang="ts">
// Hộp "Tự đăng theo khung" của Kho riêng: bật/tắt, cách viết caption, video trùng, kênh theo thư mục, AI ChatGPT + tài khoản luân phiên.
import {
    IconAlertTriangle,
    IconBrandOpenai,
    IconExternalLink,
    IconLoader2,
    IconPlus,
    IconTrash,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import {
    callJson,
    type AutoPayload,
    type AutoSettings,
    type ChatGptAccount,
} from '@/components/fork/kho/rieng';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { NativeSelect } from '@/components/ui/native-select';
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
let poll: ReturnType<typeof setInterval> | null = null;

const s = computed(() => data.value?.settings);

const load = async () => {
    loading.value = true;
    const r = await callJson<AutoPayload>('GET', '/auto/kho/rieng/tu-dong');
    loading.value = false;

    if (r.ok && r.data) {
        data.value = r.data;
    } else {
        toast.error('Không tải được cài đặt tự đăng.');
    }
};

watch(open, (o) => {
    if (o) {
        load();
    } else {
        stopPoll();
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

// ---- Kênh theo thư mục: không chọn kênh nào = mọi kênh có giỏ của sản phẩm.
const folderHas = (folderId: number, channelId: string) =>
    (s.value?.folder_channels[String(folderId)] ?? []).includes(channelId);

const toggleFolderChannel = (folderId: number, channelId: string) => {
    const map = { ...(s.value?.folder_channels ?? {}) };
    const cur = map[String(folderId)] ?? [];
    map[String(folderId)] = cur.includes(channelId)
        ? cur.filter((c) => c !== channelId)
        : [...cur, channelId];
    save({ folder_channels: map });
};

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
            : { text: 'Chưa đăng nhập xong', cls: 'text-muted-foreground' };
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
        (c.cho ?? 0) + (c.error ?? 0)
            ? `${(c.cho ?? 0) + (c.error ?? 0)} chờ AI xem`
            : '',
        c.gave_up ? `${c.gave_up} AI không xem được` : '',
    ].filter(Boolean);

    return parts.length ? parts.join(' · ') : 'Chưa có video nào chờ đăng.';
});

onBeforeUnmount(stopPoll);

const modelSel = computed({
    get: () => s.value?.model ?? '',
    set: (v: string) => save({ model: v }),
});
const effortSel = computed({
    get: () => s.value?.effort ?? '',
    set: (v: string) => save({ effort: v }),
});

const radioCls = (on: boolean) =>
    cn(
        'flex-1 rounded-lg border px-3 py-2 text-left text-sm transition',
        on ? 'border-primary bg-primary/10 font-medium' : 'hover:bg-muted/60',
    );
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent
            class="max-h-[90dvh] overflow-x-hidden overflow-y-auto sm:max-w-2xl"
            data-testid="fork-rieng-auto-dialog"
        >
            <DialogHeader>
                <DialogTitle>Kho riêng tự đăng theo khung</DialogTitle>
                <DialogDescription>
                    AI xem từng video mới (nhìn hình + nghe lời nói), chọn sản
                    phẩm gắn giỏ và viết caption. Video sẵn sàng được xếp vào
                    giờ trống của khung đăng,
                    <b>trước video Xưởng</b>. Mỗi video chỉ đăng một lần trên
                    một kênh.
                </DialogDescription>
            </DialogHeader>

            <div
                v-if="!data"
                class="flex items-center gap-2 py-8 text-sm text-muted-foreground"
            >
                <IconLoader2 class="size-4 animate-spin" /> Đang tải…
            </div>

            <div v-else-if="s" class="flex min-w-0 flex-col gap-5 text-sm">
                <!-- Bật / tắt -->
                <label
                    class="flex items-center justify-between gap-3 rounded-xl border p-3"
                >
                    <span>
                        <span class="block font-semibold"
                            >Tự đăng kho riêng</span
                        >
                        <span class="text-xs text-muted-foreground">{{
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
                    v-if="
                        !data.codex_installed ||
                        readyAccounts === 0 ||
                        !data.speech_ready
                    "
                    class="flex flex-col gap-1 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
                >
                    <div v-if="!data.codex_installed" class="flex gap-1.5">
                        <IconAlertTriangle class="size-4 shrink-0" />
                        Máy chưa cài ChatGPT CLI (Codex). Cần cài trước khi AI
                        xem được video.
                    </div>
                    <div v-else-if="readyAccounts === 0" class="flex gap-1.5">
                        <IconAlertTriangle class="size-4 shrink-0" />
                        Chưa có tài khoản ChatGPT nào: bấm "Thêm tài khoản
                        ChatGPT" ở dưới.
                    </div>
                    <div v-if="!data.speech_ready" class="flex gap-1.5">
                        <IconAlertTriangle class="size-4 shrink-0" />
                        Chưa có khoá ElevenLabs nên AI chỉ nhìn hình, không nghe
                        được lời nói (đoán sản phẩm khó hơn).
                    </div>
                </div>

                <!-- Caption -->
                <section class="flex flex-col gap-2">
                    <h3 class="font-semibold">Caption</h3>
                    <div class="flex gap-2">
                        <button
                            type="button"
                            :class="radioCls(s.caption_mode === 'ai')"
                            @click="save({ caption_mode: 'ai' })"
                        >
                            AI viết từ nội dung video
                        </button>
                        <button
                            type="button"
                            :class="radioCls(s.caption_mode === 'kid')"
                            @click="save({ caption_mode: 'kid' })"
                        >
                            Anh tự viết
                        </button>
                    </div>
                    <label class="flex items-center justify-between gap-3">
                        <span
                            >Video chưa có caption vẫn đăng (đăng không
                            chữ)</span
                        >
                        <Switch
                            :model-value="s.empty_caption_ok"
                            @update:model-value="
                                (v: boolean) => save({ empty_caption_ok: v })
                            "
                        />
                    </label>
                    <label
                        v-if="s.caption_mode === 'ai'"
                        class="flex items-center justify-between gap-3"
                    >
                        <span>Duyệt caption AI trước khi đăng</span>
                        <Switch
                            :model-value="s.approve_first"
                            @update:model-value="
                                (v: boolean) => save({ approve_first: v })
                            "
                        />
                    </label>
                    <p class="text-xs text-muted-foreground">
                        Caption anh tự sửa trên thẻ video luôn được dùng.
                        Hashtag và ảnh bìa theo cài đặt của từng sản phẩm (mặc
                        định / một ảnh cố định / xoay vòng), giống video Xưởng.
                    </p>
                </section>

                <!-- Video trùng -->
                <section class="flex flex-col gap-2">
                    <h3 class="font-semibold">Video trùng video đã có</h3>
                    <div class="flex gap-2">
                        <button
                            type="button"
                            :class="radioCls(s.duplicates === 'ask')"
                            @click="save({ duplicates: 'ask' })"
                        >
                            Hỏi anh trước (bấm "Vẫn đăng")
                        </button>
                        <button
                            type="button"
                            :class="radioCls(s.duplicates === 'allow')"
                            @click="save({ duplicates: 'allow' })"
                        >
                            Cứ đăng, chỉ cảnh báo
                        </button>
                    </div>
                </section>

                <!-- Kênh theo thư mục -->
                <section class="flex flex-col gap-2">
                    <h3 class="font-semibold">Kênh được đăng</h3>
                    <p class="text-xs text-muted-foreground">
                        Mặc định: kênh nào có giỏ hàng của sản phẩm đó đều được
                        đăng. Chọn kênh cho từng thư mục nếu muốn; muốn riêng
                        từng video thì chỉnh ngay trên thẻ video.
                    </p>
                    <div
                        v-if="!data.channels.length"
                        class="text-xs text-muted-foreground"
                    >
                        Chưa có kênh TikTok nào bật tự động đăng.
                    </div>
                    <div
                        v-for="f in data.folders"
                        :key="f.id"
                        class="flex flex-wrap items-center gap-1.5"
                    >
                        <span class="mr-1 max-w-48 truncate font-medium">{{
                            f.name
                        }}</span>
                        <span
                            v-if="
                                !(s.folder_channels[String(f.id)] ?? []).length
                            "
                            class="rounded-full bg-muted px-2 py-0.5 text-xs"
                            >Mọi kênh</span
                        >
                        <button
                            v-for="c in data.channels"
                            :key="c.id"
                            type="button"
                            :class="
                                cn(
                                    'rounded-full border px-2.5 py-0.5 text-xs transition',
                                    folderHas(f.id, c.id)
                                        ? 'border-primary bg-primary text-primary-foreground'
                                        : 'hover:bg-muted',
                                )
                            "
                            @click="toggleFolderChannel(f.id, c.id)"
                        >
                            {{ c.name }}
                        </button>
                    </div>
                </section>

                <!-- AI -->
                <section class="flex flex-col gap-2">
                    <h3 class="flex items-center gap-1.5 font-semibold">
                        <IconBrandOpenai class="size-4" /> AI ChatGPT
                    </h3>
                    <div class="flex flex-wrap gap-2">
                        <NativeSelect
                            v-model="modelSel"
                            aria-label="Model ChatGPT"
                        >
                            <option
                                v-for="(label, key) in data.models"
                                :key="key"
                                :value="key"
                            >
                                {{ label }}
                            </option>
                        </NativeSelect>
                        <NativeSelect
                            v-model="effortSel"
                            aria-label="Mức nghĩ"
                        >
                            <option
                                v-for="(label, key) in data.efforts"
                                :key="key"
                                :value="key"
                            >
                                {{ label }}
                            </option>
                        </NativeSelect>
                    </div>

                    <div class="flex flex-col divide-y rounded-xl border">
                        <div
                            v-for="a in data.chatgpt"
                            :key="a.id"
                            class="flex items-center gap-3 px-3 py-2"
                            :data-testid="`fork-chatgpt-${a.id}`"
                        >
                            <div class="min-w-0 flex-1">
                                <div class="truncate font-medium">
                                    {{ a.email ?? 'Tài khoản mới' }}
                                    <span
                                        v-if="a.plan"
                                        class="ml-1 rounded bg-muted px-1.5 py-0.5 text-[0.7rem] uppercase"
                                        >{{ a.plan }}</span
                                    >
                                </div>
                                <div
                                    :class="
                                        cn(
                                            'truncate text-xs',
                                            accountStatus(a).cls,
                                        )
                                    "
                                >
                                    {{ accountStatus(a).text
                                    }}{{
                                        a.uses ? ` · đã dùng ${a.uses} lần` : ''
                                    }}
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
                            class="px-3 py-3 text-xs text-muted-foreground"
                        >
                            Chưa có tài khoản nào.
                        </div>
                    </div>

                    <div
                        v-if="adding"
                        class="rounded-lg border border-sky-300 bg-sky-50 p-3 text-xs text-sky-900 dark:border-sky-800 dark:bg-sky-950/50 dark:text-sky-200"
                    >
                        Đăng nhập ChatGPT trong trình duyệt vừa mở, xong quay
                        lại đây (app tự nhận).
                        <a
                            v-if="loginUrl"
                            :href="loginUrl"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="ml-1 inline-flex items-center gap-0.5 font-medium underline"
                            >Trình duyệt không tự mở? Bấm vào đây
                            <IconExternalLink class="size-3"
                        /></a>
                    </div>

                    <div class="flex flex-wrap items-center gap-2">
                        <Button
                            size="sm"
                            variant="outline"
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
                        <span class="text-xs text-muted-foreground"
                            >Nhiều tài khoản thì app dùng luân phiên; tài khoản
                            hết lượt tự nghỉ, đổi sang tài khoản khác.</span
                        >
                    </div>
                </section>

                <div
                    v-if="saving || loading"
                    class="text-xs text-muted-foreground"
                >
                    Đang lưu…
                </div>
            </div>
        </DialogContent>
    </Dialog>
</template>

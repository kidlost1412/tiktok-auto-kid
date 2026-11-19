<script setup lang="ts">
// Hộp "Trộn xen kẽ sản phẩm": xem trước thứ tự sản phẩm của các bài chưa gửi lên TikTok, trộn, rồi cho "Hoàn tác".
// Dùng chung ở Lịch đăng, Chỉnh kênh và Kho riêng.
import { router } from '@inertiajs/vue3';
import { IconArrowsShuffle, IconLock, IconPin } from '@tabler/icons-vue';
import { computed, ref, watch } from 'vue';
import { toast } from 'vue-sonner';

import {
    mixApply,
    mixPreview,
    mixUndo,
} from '@/components/fork/auto/productMix';
import type { MixPreview, MixRow } from '@/components/fork/auto/productMix';
import { toneClasses } from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { NativeSelect } from '@/components/ui/native-select';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

const props = defineProps<{
    accounts: {
        id: string;
        username?: string | null;
        display_name?: string | null;
    }[];
    accountId?: string | null;
    /** Props Inertia cần tải lại sau khi trộn (mặc định: tải lại cả trang). */
    reloadOnly?: string[];
}>();
const open = defineModel<boolean>('open', { default: false });

const channel = ref<string>('');
const includePinned = ref(false);
const loading = ref(false);
const busy = ref(false);
const plan = ref<MixPreview | null>(null);
const error = ref<string | null>(null);

const name = (id: string) => {
    const a = props.accounts.find((x) => x.id === id);

    return a?.username ? `@${a.username}` : (a?.display_name ?? 'kênh');
};

const load = async () => {
    if (!channel.value) {
        return;
    }

    loading.value = true;
    error.value = null;
    const res = await mixPreview(channel.value, includePinned.value);
    loading.value = false;

    if (res.ok && res.data) {
        plan.value = res.data;
    } else {
        plan.value = null;
        error.value = res.error ?? 'Không xem trước được, hãy thử lại.';
    }
};

watch(open, (v) => {
    if (!v) {
        return;
    }

    channel.value = props.accountId ?? props.accounts[0]?.id ?? '';
    includePinned.value = false;
    plan.value = null;
    void load();
});

watch([channel, includePinned], () => {
    if (open.value) {
        void load();
    }
});

const reload = () =>
    router.reload(props.reloadOnly ? { only: props.reloadOnly } : {});

const apply = async () => {
    if (!plan.value || busy.value) {
        return;
    }

    busy.value = true;
    const id = channel.value;
    const res = await mixApply(id, includePinned.value);
    busy.value = false;

    if (!res.ok || !res.data) {
        error.value = res.error ?? 'Chưa trộn được, hãy thử lại.';

        return;
    }

    open.value = false;
    reload();
    const undo = res.data.undo;

    if (res.data.moved === 0 || undo.length === 0) {
        toast(res.data.message);

        return;
    }

    toast.success(`${res.data.message} (${name(id)})`, {
        duration: 12000,
        action: {
            label: 'Hoàn tác',
            onClick: async () => {
                const back = await mixUndo(id, undo);

                if (back.ok) {
                    toast(back.data?.message ?? 'Đã trả về giờ cũ.');
                } else {
                    toast.error(back.error ?? 'Không hoàn tác được.');
                }

                reload();
            },
        },
    });
};

// Mỗi sản phẩm một màu cố định (theo mã), để nhìn là thấy có bị dồn một loại hay không.
const PALETTE = [
    'bg-sky-500/15 text-sky-800 ring-sky-500/30 dark:text-sky-200',
    'bg-amber-500/15 text-amber-800 ring-amber-500/30 dark:text-amber-200',
    'bg-emerald-500/15 text-emerald-800 ring-emerald-500/30 dark:text-emerald-200',
    'bg-fuchsia-500/15 text-fuchsia-800 ring-fuchsia-500/30 dark:text-fuchsia-200',
    'bg-rose-500/15 text-rose-800 ring-rose-500/30 dark:text-rose-200',
    'bg-indigo-500/15 text-indigo-800 ring-indigo-500/30 dark:text-indigo-200',
    'bg-lime-500/15 text-lime-800 ring-lime-500/30 dark:text-lime-200',
];

const colorOf = computed(() => {
    const codes = [
        ...new Set((plan.value?.before ?? []).map((r) => r.product)),
    ].sort();

    return (code: string) =>
        PALETTE[Math.max(0, codes.indexOf(code)) % PALETTE.length];
});

// Chỉ hiện đoạn có bài đổi được: bắt đầu 2 bài trước bài đổi được đầu tiên (bài đã lên TikTok phía trước thì gộp lại).
const LIMIT = 24;
const start = computed(() => {
    const first = (plan.value?.before ?? []).findIndex((r) => !r.fixed);

    return first <= 2 ? 0 : first - 2;
});
const rows = (list: MixRow[] | undefined) =>
    (list ?? []).slice(start.value, start.value + LIMIT);
const more = computed(() =>
    Math.max(0, (plan.value?.before.length ?? 0) - start.value - LIMIT),
);
const time = (iso: string) => dayjs(iso).format('HH:mm DD/MM');
</script>

<template>
    <Dialog v-model:open="open">
        <DialogContent class="sm:max-w-2xl" data-testid="fork-mix-dialog">
            <DialogHeader>
                <DialogTitle class="flex items-center gap-2">
                    <IconArrowsShuffle class="size-5" /> Trộn xen kẽ sản phẩm
                </DialogTitle>
                <DialogDescription>
                    Đổi chỗ giờ đăng giữa các bài chưa gửi lên TikTok để hai bài
                    liền nhau khác sản phẩm. Không thêm bớt giờ, không đổi số
                    bài mỗi ngày.
                </DialogDescription>
            </DialogHeader>

            <div class="grid gap-4 text-sm">
                <label v-if="accounts.length > 1" class="grid gap-1.5">
                    <span class="font-medium">Kênh</span>
                    <NativeSelect
                        v-model="channel"
                        class="w-full"
                        data-testid="fork-mix-channel"
                    >
                        <option v-for="a in accounts" :key="a.id" :value="a.id">
                            {{ name(a.id) }}
                        </option>
                    </NativeSelect>
                </label>

                <div
                    v-if="loading && !plan"
                    class="flex items-center gap-2 text-muted-foreground"
                >
                    <Spinner class="size-4" /> Đang xem lịch của kênh…
                </div>

                <p
                    v-if="error"
                    :class="
                        cn(
                            'rounded-lg border px-3 py-2',
                            toneClasses.danger.box,
                        )
                    "
                >
                    {{ error }}
                </p>

                <template v-if="plan">
                    <p
                        :class="
                            cn(
                                'rounded-lg border px-3 py-2',
                                plan.changed > 0
                                    ? toneClasses.info.box
                                    : 'bg-muted/40',
                            )
                        "
                        data-testid="fork-mix-message"
                    >
                        {{ plan.message }}
                        <span class="mt-1 block text-xs text-muted-foreground">
                            {{ plan.movable }} bài đổi chỗ được ·
                            {{ plan.locked }} bài đã lên TikTok hoặc sắp tới giờ
                            giữ nguyên<template v-if="plan.pinned">
                                · {{ plan.pinned }} bài anh tự chỉnh giờ giữ
                                nguyên</template
                            >
                        </span>
                    </p>

                    <label
                        v-if="plan.pinned > 0 || includePinned"
                        class="flex items-center gap-2"
                    >
                        <input
                            v-model="includePinned"
                            type="checkbox"
                            class="size-4 accent-primary"
                            data-testid="fork-mix-include-pinned"
                        />
                        Đổi cả các bài anh đã tự chỉnh giờ
                    </label>

                    <div
                        v-if="plan.before.length"
                        class="grid gap-3"
                        :class="loading && 'opacity-60'"
                    >
                        <div
                            v-for="(list, idx) in [plan.before, plan.after]"
                            :key="idx"
                            class="grid gap-1.5"
                        >
                            <span
                                class="text-xs font-medium text-muted-foreground"
                                >{{
                                    idx === 0 ? 'Hiện tại' : 'Sau khi trộn'
                                }}</span
                            >
                            <ol class="flex flex-wrap gap-1">
                                <li
                                    v-if="start"
                                    class="px-1 text-xs text-muted-foreground"
                                    :title="`${start} bài sớm hơn đã lên TikTok hoặc sắp tới giờ, giữ nguyên`"
                                >
                                    {{ start }} bài trước…
                                </li>
                                <li
                                    v-for="r in rows(list)"
                                    :key="`${idx}-${r.at}`"
                                    :title="`${time(r.at)} · ${r.name}${r.fixed ? ' · giữ nguyên' : ''}`"
                                    :class="
                                        cn(
                                            'inline-flex max-w-[9rem] items-center gap-1 truncate rounded-md px-1.5 py-0.5 text-xs ring-1',
                                            colorOf(r.product),
                                            r.fixed && 'opacity-60',
                                        )
                                    "
                                >
                                    <IconLock
                                        v-if="r.fixed"
                                        class="size-3 shrink-0"
                                    />
                                    <span class="truncate">{{ r.name }}</span>
                                </li>
                                <li
                                    v-if="more"
                                    class="px-1 text-xs text-muted-foreground"
                                >
                                    +{{ more }} bài
                                </li>
                            </ol>
                        </div>
                        <p
                            class="flex items-center gap-1 text-xs text-muted-foreground"
                        >
                            <IconLock class="size-3" /> giữ nguyên giờ (đã lên
                            TikTok, sắp tới giờ<template v-if="!includePinned"
                                >, hoặc anh tự chỉnh
                                <IconPin class="inline size-3" /></template
                            >)
                        </p>
                    </div>
                </template>
            </div>

            <DialogFooter>
                <Button variant="outline" @click="open = false">Thôi</Button>
                <Button
                    :disabled="!plan || plan.changed === 0 || busy || loading"
                    data-testid="fork-mix-apply"
                    @click="apply"
                >
                    <Spinner v-if="busy" class="size-4" />
                    <IconArrowsShuffle v-else class="size-4" />
                    Trộn ngay
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>

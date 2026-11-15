<script setup lang="ts">
// Sửa bài ngay trong khung xem video: giờ đăng, kênh đăng, caption, hashtag, ảnh bìa; "Bỏ xếp lịch" (video về kho để sửa
// rồi đăng sau); "Cho xếp lịch lại" cho video AI đã bỏ. Bài đã hẹn trên TikTok: TikTok không cho sửa bài hẹn, nên app nhờ
// Chrome xoá bài cũ, kiểm lại rồi mới hẹn lại bản mới (không xác minh được thì không đổi gì).
import { router } from '@inertiajs/vue3';
import {
    IconBrandTiktok,
    IconCalendarOff,
    IconCalendarRepeat,
    IconCircleCheck,
    IconPencil,
    IconPhotoUp,
    IconRestore,
    IconVideo,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';

import ChannelPicker from '@/components/fork/kho/ChannelPicker.vue';
import type { ChannelOption } from '@/components/fork/kho/ChannelPicker.vue';
import { coverUrl } from '@/components/fork/kho/kho';
import DateTimePicker from '@/components/fork/shared/DateTimePicker.vue';
import { toneClasses } from '@/components/fork/shared/status';
import { loadVideo } from '@/components/fork/viewer';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';
import { cn } from '@/lib/utils';

interface EditInfo {
    id: number;
    kind: 'local' | 'tiktok' | null;
    reason: string | null;
    current_at: string | null;
    rules: {
        window_start: number;
        window_end: number;
        gap_minutes: number;
        min_lead_minutes: number;
        max_ahead_hours: number;
    } | null;
    request: { state: string; open: boolean; message: string; action?: string } | null;
    account_id: string | null;
    caption: string;
    hashtags: string[];
    cover: { own: boolean; url: string | null } | null;
    max_chars: number;
    accounts: { id: string; username: string | null; name: string | null; avatar: string | null; ok: boolean; reason: string | null }[];
    held: boolean;
    can_release: boolean;
}

const props = defineProps<{
    videoId: number;
    /** Giây đang phát của trình phát (để "Lấy khung đang xem"); null khi không có file video. */
    currentTime?: () => number | null;
}>();

const FORMAT = 'YYYY-MM-DDTHH:mm';
const info = ref<EditInfo | null>(null);
const editing = ref(false);
const busy = ref(false);
const coverBusy = ref(false);
const confirmUnschedule = ref(false);
const problem = ref('');
const success = ref('');

const at = ref('');
const account = ref('');
const caption = ref('');
const tags = ref('');
const coverToken = ref<string | null>(null);
const coverPreview = ref<string | null>(null);
const coverReset = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

let timer: ReturnType<typeof setTimeout> | null = null;
let pollUntil = 0;

const xsrf = () => decodeURIComponent(document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '');
const base = computed(() => `/auto/videos/${props.videoId}`);
const waiting = computed(() => !!info.value?.request?.open);
const isTikTok = computed(() => info.value?.kind === 'tiktok');
const canEdit = computed(() => !!info.value?.kind && !waiting.value);

const channelOptions = computed<ChannelOption[]>(() =>
    (info.value?.accounts ?? []).map((a) => ({
        id: a.id,
        name: `@${a.username ?? a.name ?? '—'}`,
        avatar_url: a.avatar,
        note: a.ok ? null : 'Chưa chọn giỏ hàng cho sản phẩm này',
    })),
);

const minAt = computed(() => {
    const lead = info.value?.rules?.min_lead_minutes ?? 45;
    const m = dayjs().add(lead + 1, 'minute');

    return m.minute(Math.ceil(m.minute() / 5) * 5).second(0).format(FORMAT);
});

const rulesText = computed(() => {
    const r = info.value?.rules;

    if (!r) {
        return '';
    }

    const hh = (h: number) => `${String(h).padStart(2, '0')}:00`;

    return `Trong khung ${hh(r.window_start)}–${hh(r.window_end)} của kênh, cách bây giờ ít nhất ${r.min_lead_minutes} phút và cách bài khác cùng kênh ít nhất ${r.gap_minutes} phút.`;
});

const splitTags = (s: string) =>
    s
        .split(/[\s,]+/)
        .map((t) => t.replace(/^#+/, '').trim())
        .filter(Boolean)
        .map((t) => `#${t}`);

const length = computed(() => {
    const t = splitTags(tags.value);

    return caption.value.trim().length + (t.length ? 2 + t.join(' ').length : 0);
});

const stop = () => {
    if (timer) {
        clearTimeout(timer);
        timer = null;
    }
};

onBeforeUnmount(stop);

async function load(): Promise<EditInfo | null> {
    try {
        const r = await fetch(`${base.value}/sua`, { headers: { Accept: 'application/json' }, credentials: 'same-origin' });

        return r.ok ? ((await r.json()) as EditInfo) : null;
    } catch {
        return null;
    }
}

const fill = () => {
    const i = info.value;

    if (!i) {
        return;
    }

    at.value = i.current_at ? dayjs(i.current_at).format(FORMAT) : '';
    account.value = i.account_id ?? '';
    caption.value = i.caption ?? '';
    tags.value = (i.hashtags ?? []).join(' ');
    coverToken.value = null;
    coverPreview.value = null;
    coverReset.value = false;
};

const refreshAll = () => {
    void loadVideo(props.videoId, true);
    router.reload({ only: ['lich', 'recent', 'upcoming'] });
};

const poll = () => {
    stop();
    timer = setTimeout(async () => {
        const next = await load();

        if (next) {
            info.value = next;
        }

        if (waiting.value && Date.now() < pollUntil) {
            poll();
        } else if (info.value?.request && !info.value.request.open) {
            if (info.value.request.state === 'done') {
                success.value = info.value.request.message;
                problem.value = '';
            } else {
                problem.value = info.value.request.message;
            }

            refreshAll();
        }
    }, 3000);
};

watch(
    () => props.videoId,
    async () => {
        stop();
        editing.value = false;
        confirmUnschedule.value = false;
        problem.value = '';
        success.value = '';
        info.value = await load();
        fill();

        if (waiting.value) {
            pollUntil = Date.now() + 17 * 60 * 1000;
            poll();
        }
    },
    { immediate: true },
);

async function send(url: string, body: Record<string, unknown> | null): Promise<void> {
    busy.value = true;
    problem.value = '';
    success.value = '';

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-XSRF-TOKEN': xsrf() },
            credentials: 'same-origin',
            body: JSON.stringify(body ?? {}),
        });
        const data = (await r.json().catch(() => null)) as (EditInfo & { ok?: boolean; message?: string; state?: string }) | null;

        if (data && 'kind' in data) {
            info.value = data;
        }

        if (!r.ok || !data?.ok) {
            problem.value = data?.message ?? 'Không lưu được, hãy thử lại.';

            return;
        }

        editing.value = false;
        confirmUnschedule.value = false;

        if (data.state === 'pending') {
            pollUntil = Date.now() + 17 * 60 * 1000;
            poll();
        } else {
            success.value = data.message ?? 'Đã lưu.';
            fill();
            refreshAll();
        }
    } catch {
        problem.value = 'Mất kết nối với app, hãy thử lại.';
    } finally {
        busy.value = false;
    }
}

const save = () => {
    const i = info.value;

    if (!i) {
        return;
    }

    const body: Record<string, unknown> = {};

    if (at.value && (!i.current_at || dayjs(at.value).format(FORMAT) !== dayjs(i.current_at).format(FORMAT))) {
        body.at = dayjs(at.value).format();
    }

    if (account.value && account.value !== i.account_id) {
        body.social_account_id = account.value;
    }

    if (caption.value.trim() !== (i.caption ?? '').trim()) {
        body.caption = caption.value;
    }

    const nextTags = splitTags(tags.value);

    if (nextTags.join(' ') !== (i.hashtags ?? []).join(' ')) {
        body.hashtags = nextTags;
    }

    if (coverToken.value) {
        body.cover_token = coverToken.value;
    } else if (coverReset.value) {
        body.cover_reset = true;
    }

    if (!Object.keys(body).length) {
        problem.value = 'Chưa có gì thay đổi.';

        return;
    }

    void send(`${base.value}/sua`, body);
};

async function postCover(url: string, body: FormData | string): Promise<void> {
    coverBusy.value = true;
    problem.value = '';

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'X-XSRF-TOKEN': xsrf(),
                ...(typeof body === 'string' ? { 'Content-Type': 'application/json' } : {}),
            },
            credentials: 'same-origin',
            body,
        });
        const data = (await r.json().catch(() => null)) as { ok?: boolean; token?: string; url?: string; error?: string; message?: string } | null;

        if (!r.ok || !data?.ok || !data.token) {
            problem.value = data?.error ?? data?.message ?? 'Không dùng được ảnh này.';

            return;
        }

        coverToken.value = data.token;
        coverPreview.value = data.url ?? `/auto/kho/rieng/anh-bia/tam/${data.token}`;
        coverReset.value = false;
    } catch {
        problem.value = 'Mất kết nối với app, hãy thử lại.';
    } finally {
        coverBusy.value = false;
    }
}

const onFile = (ev: Event) => {
    const f = (ev.target as HTMLInputElement).files?.[0];

    if (f) {
        const fd = new FormData();
        fd.append('image', f);
        void postCover('/auto/kho/rieng/anh-bia/tai-len', fd);
    }

    (ev.target as HTMLInputElement).value = '';
};

const grabFrame = () => {
    const t = props.currentTime?.() ?? 0;
    void postCover(`/auto/kho/rieng/video/${props.videoId}/khung`, JSON.stringify({ t: Math.max(0, t ?? 0) }));
};

const resetCover = () => {
    coverToken.value = null;
    coverPreview.value = null;
    coverReset.value = true;
};

const shownCover = computed(() => (coverReset.value ? null : (coverPreview.value ?? coverUrl(props.videoId))));
const coverBroken = ref(false);

watch(shownCover, () => {
    coverBroken.value = false;
});
</script>

<template>
    <div
        v-if="info && (info.kind || waiting || info.can_release || info.request)"
        class="flex flex-col gap-3 rounded-xl border p-3"
        data-testid="fork-viewer-edit"
    >
        <!-- Đang xoá bài hẹn cũ trên TikTok -->
        <div
            v-if="waiting"
            :class="cn('flex items-start gap-2 rounded-lg border p-2.5 text-sm', toneClasses.info.box)"
            data-testid="fork-viewer-edit-waiting"
        >
            <Spinner class="mt-0.5 size-4 shrink-0" />
            <span>{{ info.request?.message }} Chrome cần đang mở; không xác minh được thì app giữ nguyên bài cũ.</span>
        </div>

        <div
            v-if="success"
            :class="cn('flex items-start gap-2 rounded-lg border p-2.5 text-sm', toneClasses.success.box)"
        >
            <IconCircleCheck class="mt-0.5 size-4 shrink-0" />
            <span>{{ success }}</span>
        </div>
        <div
            v-if="problem"
            :class="cn('rounded-lg border p-2.5 text-sm', toneClasses.danger.box)"
            data-testid="fork-viewer-edit-problem"
        >
            {{ problem }}
        </div>

        <!-- Video AI đã bỏ xếp lịch -->
        <div v-if="info.can_release" class="flex flex-wrap items-center gap-2 text-sm">
            <span class="text-muted-foreground">Video đang tạm không tự xếp lịch (anh đã bỏ xếp lịch để sửa).</span>
            <Button size="sm" :disabled="busy" data-testid="fork-viewer-release" @click="send(`${base}/cho-xep-lai`, null)">
                <IconCalendarRepeat class="size-4" /> Cho xếp lịch lại
            </Button>
        </div>

        <template v-if="info.kind">
            <div v-if="!editing" class="flex flex-wrap items-center gap-2">
                <Button
                    size="sm"
                    variant="outline"
                    :disabled="!canEdit"
                    data-testid="fork-viewer-edit-open"
                    @click="
                        fill();
                        editing = true;
                        confirmUnschedule = false;
                    "
                >
                    <IconPencil class="size-4" /> Sửa bài
                </Button>
                <Button
                    v-if="!confirmUnschedule"
                    size="sm"
                    variant="outline"
                    :disabled="!canEdit"
                    data-testid="fork-viewer-unschedule"
                    @click="confirmUnschedule = true"
                >
                    <IconCalendarOff class="size-4" /> Bỏ xếp lịch
                </Button>
                <template v-else>
                    <Button
                        size="sm"
                        variant="destructive"
                        :disabled="busy"
                        data-testid="fork-viewer-unschedule-confirm"
                        @click="send(`${base}/bo-xep-lich`, null)"
                    >
                        <Spinner v-if="busy" class="size-4" />
                        {{ isTikTok ? 'Xoá trên TikTok rồi bỏ' : 'Chắc chắn bỏ xếp lịch' }}
                    </Button>
                    <Button size="sm" variant="ghost" :disabled="busy" @click="confirmUnschedule = false">Thôi</Button>
                </template>
                <span v-if="isTikTok" class="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <IconBrandTiktok class="size-3.5" /> Đã hẹn trên TikTok
                </span>
            </div>
            <p v-if="confirmUnschedule && !editing" class="text-xs text-muted-foreground">
                Video về kho để anh sửa rồi đăng sau.
                <template v-if="isTikTok">App nhờ Chrome xoá bài hẹn trên TikTok và kiểm lại trước, rồi mới bỏ.</template>
            </p>

            <!-- Form sửa -->
            <form v-if="editing" class="flex flex-col gap-3" data-testid="fork-viewer-edit-form" @submit.prevent="save">
                <p v-if="isTikTok" :class="cn('rounded-lg border p-2.5 text-xs', toneClasses.warn.box)">
                    Bài đã hẹn trên TikTok mà TikTok không cho sửa bài hẹn. Khi lưu, app nhờ Chrome xoá bài hẹn cũ, kiểm lại, rồi
                    hẹn lại bản mới. Không xác minh được thì không đổi gì.
                </p>

                <div class="grid gap-3 sm:grid-cols-2">
                    <label class="flex min-w-0 flex-col gap-1.5 text-sm">
                        <span class="font-medium">Giờ đăng</span>
                        <DateTimePicker v-model="at" :min="minAt" testid="fork-viewer-edit-at" aria-label="Giờ đăng" />
                    </label>
                    <div class="flex min-w-0 flex-col gap-1.5 text-sm">
                        <span class="font-medium">Kênh đăng</span>
                        <ChannelPicker v-model="account" :options="channelOptions" testid="fork-viewer-edit-channel" />
                    </div>
                </div>
                <span v-if="rulesText" class="-mt-1.5 text-xs text-muted-foreground">{{ rulesText }}</span>

                <label class="flex flex-col gap-1.5 text-sm">
                    <span class="flex items-baseline justify-between gap-2">
                        <span class="font-medium">Caption</span>
                        <span
                            :class="cn('text-xs tabular-nums', length > info.max_chars ? toneClasses.danger.text : 'text-muted-foreground')"
                            >{{ length }}/{{ info.max_chars }}</span
                        >
                    </span>
                    <textarea
                        v-model="caption"
                        rows="5"
                        class="min-h-24 w-full resize-y rounded-md border bg-background px-3 py-2 text-sm leading-relaxed shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        data-testid="fork-viewer-edit-caption"
                    />
                </label>
                <label class="flex flex-col gap-1.5 text-sm">
                    <span class="font-medium">Hashtag</span>
                    <input
                        v-model="tags"
                        type="text"
                        placeholder="#nongnghiep #phanbon"
                        class="h-9 w-full rounded-md border bg-background px-3 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        data-testid="fork-viewer-edit-tags"
                    />
                    <span class="text-xs text-muted-foreground">Cách nhau bằng dấu cách; dấu # tự thêm.</span>
                </label>

                <div class="flex flex-col gap-1.5 text-sm">
                    <span class="font-medium">Ảnh bìa</span>
                    <div class="flex items-start gap-3">
                        <div class="flex h-[96px] w-[54px] shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted">
                            <img
                                v-if="shownCover && !coverBroken"
                                :src="shownCover"
                                alt=""
                                class="size-full object-cover"
                                @error="coverBroken = true"
                            />
                            <span v-else class="px-1 text-center text-[0.625rem] text-muted-foreground">{{
                                coverReset ? 'Bìa sản phẩm' : 'Bìa hiện tại'
                            }}</span>
                        </div>
                        <div class="flex min-w-0 flex-col gap-1.5">
                            <div class="flex flex-wrap gap-1.5">
                                <Button type="button" size="sm" variant="outline" :disabled="coverBusy" @click="fileInput?.click()">
                                    <IconPhotoUp class="size-4" /> Tải ảnh lên
                                </Button>
                                <Button
                                    v-if="currentTime"
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    :disabled="coverBusy"
                                    title="Dừng video ở khung muốn dùng rồi bấm"
                                    @click="grabFrame"
                                >
                                    <IconVideo class="size-4" /> Lấy khung đang xem
                                </Button>
                                <Button
                                    v-if="info.cover?.own || coverToken"
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    :disabled="coverBusy"
                                    @click="resetCover"
                                >
                                    <IconRestore class="size-4" /> Về bìa sản phẩm
                                </Button>
                            </div>
                            <span class="text-xs text-muted-foreground">
                                <Spinner v-if="coverBusy" class="mr-1 inline size-3" />
                                {{ coverToken ? 'Ảnh mới sẽ được dùng khi lưu.' : coverReset ? 'Sẽ dùng bìa của sản phẩm.' : 'jpg, png hoặc webp, tối đa 5 MB; ảnh dọc 9:16 hoặc 3:4.' }}
                            </span>
                            <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" class="sr-only" @change="onFile" />
                        </div>
                    </div>
                </div>

                <div class="flex flex-wrap justify-end gap-2">
                    <Button type="button" variant="ghost" :disabled="busy" @click="editing = false">Huỷ</Button>
                    <Button type="submit" :disabled="busy || coverBusy || length > info.max_chars" data-testid="fork-viewer-edit-save">
                        <Spinner v-if="busy" class="size-4" />
                        {{ isTikTok ? 'Lưu (xoá bài hẹn cũ rồi hẹn lại)' : 'Lưu thay đổi' }}
                    </Button>
                </div>
            </form>
        </template>
        <p v-else-if="!waiting && !info.can_release && info.reason" class="text-xs text-muted-foreground">
            {{ info.reason }}
        </p>
    </div>
</template>

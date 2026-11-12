<script setup lang="ts">
// Cài đặt → Cập nhật: xem bản đang dùng / bản mới, ghi chú phát hành, cập nhật một chạm, quay lại bản trước.
// Việc tải/cài do launcher (TikTokAuto.exe) làm; trong lúc cập nhật app tạm dừng nên trang tự hỏi thẳng launcher.
// Chữ viết thẳng bằng tiếng Việt (không qua lang/en).
import { Head, router } from '@inertiajs/vue3';
import {
    IconArrowBackUp,
    IconCloudDownload,
    IconExternalLink,
    IconPackage,
    IconRefresh,
    IconSettings,
    IconSparkles,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import SettingsSection from '@/components/settings/SettingsSection.vue';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import SettingsLayout from '@/layouts/SettingsLayout.vue';

interface Job {
    state: string;
    busy: boolean;
    message: string;
    percent: number;
    error: string;
}

const props = defineProps<{
    configured: boolean;
    repo: string | null;
    launcher_ok: boolean;
    launcher_port: number;
    current: string;
    latest: {
        version: string;
        notes: string;
        page_url: string | null;
        published_at: string;
        size: number;
    } | null;
    update_available: boolean;
    check_error: string;
    checked_at: string;
    auto_check: boolean;
    can_rollback: boolean;
    rollback_version: string;
    launcher_pending: boolean;
    job: Job | null;
}>();

const busy = ref<string | null>(null);
const live = ref<Job | null>(props.job);
const reloading = ref(false);
let timer: ReturnType<typeof setInterval> | null = null;
let sawBusy = false;

const run = (key: string, fn: (done: () => void) => void): void => {
    busy.value = key;
    fn(() => (busy.value = null));
};

const opts = (done: () => void) => ({
    preserveScroll: true,
    onFinish: done,
});

// Hỏi thẳng launcher (cổng điều khiển trên 127.0.0.1) vì trong lúc cập nhật chính app này đang tắt.
const poll = async (): Promise<void> => {
    try {
        const r = await fetch(
            `http://127.0.0.1:${props.launcher_port}/api/update/status`,
            { cache: 'no-store' },
        );
        if (!r.ok) return;
        const s = await r.json();
        const job: Job = {
            state: s.state ?? 'idle',
            busy: !!s.busy,
            message: s.message ?? '',
            percent: s.percent ?? 0,
            error: s.error ?? '',
        };
        live.value = job;
        if (job.busy) sawBusy = true;
        if (sawBusy && !job.busy && !reloading.value) {
            reloading.value = true;
            stop();
            // xong (hoặc lỗi đã khôi phục): chờ app chạy lại rồi tải lại trang
            setTimeout(() => window.location.reload(), 1500);
        }
    } catch {
        // launcher chưa trả lời: thử lại ở nhịp sau
    }
};

const stop = (): void => {
    if (timer) clearInterval(timer);
    timer = null;
};
const start = (): void => {
    if (timer) return;
    timer = setInterval(poll, 1500);
    void poll();
};

onMounted(() => {
    if (props.job?.busy) {
        sawBusy = true;
        start();
    }
});
onBeforeUnmount(stop);

const working = computed(() => !!live.value?.busy);
const failed = computed(
    () => !working.value && live.value?.state === 'error' && live.value.error,
);

const check = (): void =>
    run('check', (done) =>
        router.post('/settings/cap-nhat/check', {}, opts(done)),
    );

const install = (): void => {
    if (
        !window.confirm(
            `Cập nhật lên bản ${props.latest?.version}? Ứng dụng sẽ tạm dừng vài phút, dữ liệu được sao lưu trước.`,
        )
    )
        return;
    run('install', (done) =>
        router.post(
            '/settings/cap-nhat/install',
            {},
            {
                ...opts(done),
                onSuccess: () => {
                    sawBusy = true;
                    start();
                },
            },
        ),
    );
};

const rollback = (): void => {
    if (
        !window.confirm(
            `Quay lại bản ${props.rollback_version}? Dữ liệu giữ nguyên, chỉ đổi mã chương trình.`,
        )
    )
        return;
    run('rollback', (done) =>
        router.post(
            '/settings/cap-nhat/rollback',
            {},
            {
                ...opts(done),
                onSuccess: () => {
                    sawBusy = true;
                    start();
                },
            },
        ),
    );
};

const setAuto = (v: boolean): void =>
    run('prefs', (done) =>
        router.patch(
            '/settings/cap-nhat/prefs',
            { auto_check: v },
            opts(done),
        ),
    );

const when = (iso: string): string => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('vi-VN');
};
const mb = (n: number): string => (n > 0 ? `${(n / 1048576).toFixed(0)} MB` : '');

// ---- Markdown rút gọn, dựng bằng nút Vue (không dùng v-html) nên không thể chèn HTML/script ----
type Inline = { t: 'text' | 'b' | 'code' | 'a'; v: string; href?: string };
type Block =
    | { k: 'h'; level: number; parts: Inline[] }
    | { k: 'p'; parts: Inline[] }
    | { k: 'ul'; items: Inline[][] };

const inline = (s: string): Inline[] => {
    const out: Inline[] = [];
    const re = /\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g;
    let last = 0;
    for (let m = re.exec(s); m; m = re.exec(s)) {
        if (m.index > last) out.push({ t: 'text', v: s.slice(last, m.index) });
        if (m[1] !== undefined) out.push({ t: 'b', v: m[1] });
        else if (m[2] !== undefined) out.push({ t: 'code', v: m[2] });
        else out.push({ t: 'a', v: m[3], href: m[4] });
        last = m.index + m[0].length;
    }
    if (last < s.length) out.push({ t: 'text', v: s.slice(last) });
    return out;
};

const blocks = computed<Block[]>(() => {
    const out: Block[] = [];
    let list: Inline[][] | null = null;
    let para: string[] = [];
    const flushPara = (): void => {
        if (para.length) out.push({ k: 'p', parts: inline(para.join(' ')) });
        para = [];
    };
    for (const raw of (props.latest?.notes ?? '').split(/\r?\n/)) {
        const line = raw.trim();
        const h = /^(#{1,4})\s+(.*)$/.exec(line);
        const li = /^[-*+]\s+(.*)$/.exec(line);
        if (li) {
            flushPara();
            if (!list) {
                list = [];
                out.push({ k: 'ul', items: list });
            }
            list.push(inline(li[1]));
            continue;
        }
        list = null;
        if (h) {
            flushPara();
            out.push({ k: 'h', level: h[1].length, parts: inline(h[2]) });
        } else if (line === '') {
            flushPara();
        } else {
            para.push(line);
        }
    }
    flushPara();
    return out;
});
</script>

<template>
    <Head title="Cập nhật" />

    <SettingsLayout
        title="Cập nhật"
        description="Cập nhật TikTok Auto Kid lên bản mới chỉ với một cú nhấp. Dữ liệu được sao lưu trước, lỗi thì tự quay về bản cũ."
    >
        <div class="grid items-start gap-5 xl:grid-cols-2" data-testid="fork-update-page">
            <div class="flex min-w-0 flex-col gap-5">
                <SettingsSection
                    title="Phiên bản"
                    description="Bản đang chạy trên máy và bản mới nhất trên kho phát hành."
                    :icon="IconCloudDownload"
                >
                    <template #actions>
                        <Button
                            variant="outline"
                            :disabled="busy === 'check' || working || !configured"
                            data-testid="fork-update-check"
                            @click="check"
                        >
                            <Spinner v-if="busy === 'check'" class="size-4" />
                            <IconRefresh v-else class="size-4" />
                            Kiểm tra lại
                        </Button>
                    </template>

                    <div class="grid gap-3 sm:grid-cols-2">
                        <div class="flex items-center gap-3.5 rounded-xl border border-border bg-muted px-5 py-4">
                            <span class="fk-chip is-green"><IconPackage /></span>
                            <div class="min-w-0">
                                <p class="text-[13px] text-muted-foreground">Đang dùng</p>
                                <p class="mt-0.5 text-[26px] leading-none font-semibold tracking-[-0.025em] tabular-nums" data-testid="fork-update-current">
                                    v{{ current }}
                                </p>
                            </div>
                        </div>
                        <div class="flex items-center gap-3.5 rounded-xl border border-border bg-muted px-5 py-4">
                            <span class="fk-chip"><IconSparkles /></span>
                            <div class="min-w-0">
                                <p class="text-[13px] text-muted-foreground">Bản mới nhất</p>
                                <p class="mt-0.5 text-[26px] leading-none font-semibold tracking-[-0.025em] tabular-nums" data-testid="fork-update-latest">
                                    <template v-if="latest">v{{ latest.version }}</template>
                                    <template v-else>—</template>
                                </p>
                                <p v-if="checked_at" class="mt-1 text-[13px] text-muted-foreground">
                                    Kiểm tra lúc {{ when(checked_at) }}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div
                        v-if="!configured"
                        class="rounded-xl border border-dashed border-border-strong p-4 text-sm text-muted-foreground"
                        data-testid="fork-update-unconfigured"
                    >
                        Chưa có kho cập nhật. Đặt
                        <code>UPDATE_REPO=chu-kho/ten-kho</code> trong file
                        <code>.env</code> (kho GitHub công khai có các bản phát hành) rồi khởi động lại ứng dụng.
                    </div>
                    <div
                        v-else-if="!launcher_ok"
                        class="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm"
                        data-testid="fork-update-no-launcher"
                    >
                        Không liên lạc được launcher. Cập nhật chỉ hoạt động khi ứng dụng được mở bằng
                        <code>TikTokAuto.exe</code>.
                    </div>
                    <div
                        v-else-if="check_error && !latest"
                        class="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm"
                    >
                        {{ check_error }}
                    </div>
                    <div
                        v-else-if="update_available && latest"
                        class="flex flex-wrap items-center gap-3 rounded-xl border border-success-text/30 bg-success-subtle p-4 text-sm"
                        data-testid="fork-update-available"
                    >
                        <span class="fk-pill is-green">Có bản mới</span>
                        <span>
                            Bản {{ latest.version }}<template v-if="mb(latest.size)"> ({{ mb(latest.size) }})</template>
                            đã sẵn sàng.
                        </span>
                        <Button
                            class="ml-auto"
                            :disabled="busy === 'install' || working"
                            data-testid="fork-update-install"
                            @click="install"
                        >
                            <Spinner v-if="busy === 'install'" class="size-4" />
                            <IconCloudDownload v-else class="size-4" />
                            Cập nhật ngay
                        </Button>
                    </div>
                    <div
                        v-else-if="latest"
                        class="flex items-center gap-3 rounded-xl border border-border bg-muted p-4 text-sm"
                        data-testid="fork-update-uptodate"
                    >
                        <span class="fk-pill is-green">Mới nhất</span>
                        Bạn đang dùng bản mới nhất.
                    </div>

                    <div
                        v-if="working && live"
                        class="rounded-xl border border-primary-strong/25 bg-primary-subtle p-4"
                        data-testid="fork-update-progress"
                    >
                        <div class="flex items-center gap-2 text-sm font-semibold">
                            <Spinner class="size-4" />
                            {{ live.message || 'Đang xử lý…' }}
                        </div>
                        <div class="mt-3 h-2 overflow-hidden rounded-full bg-secondary">
                            <div
                                class="h-full rounded-full bg-gradient-to-r from-violet-400 to-violet-700 transition-all"
                                :style="{ width: `${Math.max(3, live.percent)}%` }"
                            />
                        </div>
                        <p class="mt-2 text-[13px] text-muted-foreground">
                            Ứng dụng tạm dừng trong lúc cập nhật. Đừng tắt máy hay thoát TikTok Auto Kid; trang sẽ tự tải lại khi xong.
                        </p>
                    </div>
                    <div
                        v-else-if="failed && live"
                        class="rounded-xl border border-destructive/40 bg-critical-subtle p-4 text-sm text-destructive-text"
                        data-testid="fork-update-error"
                    >
                        <strong>Cập nhật thất bại.</strong> {{ live.error }}
                    </div>
                    <div
                        v-if="launcher_pending"
                        class="rounded-xl border border-border bg-muted p-4 text-sm text-muted-foreground"
                    >
                        Chương trình khởi chạy (launcher) mới sẽ được áp dụng ở lần mở TikTok Auto Kid tiếp theo
                        (thoát từ khay hệ thống rồi mở lại).
                    </div>
                </SettingsSection>

                <SettingsSection
                    title="Tuỳ chọn"
                    description="Kiểm tra bản mới tự động và quay lại bản trước khi cần."
                    :icon="IconSettings"
                    tone="neutral"
                >
                    <ul class="divide-y divide-border overflow-hidden rounded-xl border border-border">
                        <li class="flex items-center gap-3 px-4 py-3.5">
                            <div class="min-w-0 flex-1">
                                <div class="text-[15px] font-medium">Tự kiểm tra bản mới mỗi ngày</div>
                                <div class="text-[13px] text-muted-foreground">
                                    Khi có bản mới, menu ở khay hệ thống sẽ báo và gửi tin Telegram (nếu đã nối Telegram). Không tự cài.
                                </div>
                            </div>
                            <Switch
                                :model-value="auto_check"
                                aria-label="Tự kiểm tra bản mới mỗi ngày"
                                :disabled="!launcher_ok || busy === 'prefs'"
                                data-testid="fork-update-auto"
                                @update:model-value="(v: boolean) => setAuto(v)"
                            />
                        </li>
                        <li v-if="can_rollback" class="flex items-center gap-3 px-4 py-3.5">
                            <div class="min-w-0 flex-1">
                                <div class="text-[15px] font-medium">Quay lại bản trước (v{{ rollback_version }})</div>
                                <div class="text-[13px] text-muted-foreground">
                                    Dữ liệu giữ nguyên, chỉ đổi mã chương trình. Dùng khi bản mới có lỗi.
                                </div>
                            </div>
                            <Button
                                variant="outline"
                                :disabled="busy === 'rollback' || working"
                                data-testid="fork-update-rollback"
                                @click="rollback"
                            >
                                <Spinner v-if="busy === 'rollback'" class="size-4" />
                                <IconArrowBackUp v-else class="size-4" />
                                Quay lại bản trước
                            </Button>
                        </li>
                    </ul>
                </SettingsSection>
            </div>

            <SettingsSection
                v-if="latest && blocks.length"
                :title="`Có gì mới trong bản ${latest.version}`"
                description="Ghi chú phát hành do kho cập nhật cung cấp."
                :icon="IconSparkles"
                tone="amber"
            >
                <template v-if="latest.page_url" #actions>
                    <a
                        :href="latest.page_url"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="inline-flex items-center gap-1 text-sm font-medium text-primary-text hover:underline"
                    >
                        <IconExternalLink class="size-4" />
                        Xem trên GitHub
                    </a>
                </template>
                <div class="flex flex-col gap-3 rounded-xl border border-border bg-muted p-5 text-sm leading-relaxed" data-testid="fork-update-notes">
                    <template v-for="(b, i) in blocks" :key="i">
                        <component
                            :is="`h${Math.min(6, b.level + 2)}`"
                            v-if="b.k === 'h'"
                            class="font-semibold"
                        >
                            <template v-for="(p, j) in b.parts" :key="j">{{ p.v }}</template>
                        </component>
                        <ul v-else-if="b.k === 'ul'" class="list-disc space-y-1 pl-5">
                            <li v-for="(it, j) in b.items" :key="j">
                                <template v-for="(p, n) in it" :key="n">
                                    <strong v-if="p.t === 'b'">{{ p.v }}</strong>
                                    <code v-else-if="p.t === 'code'">{{ p.v }}</code>
                                    <a
                                        v-else-if="p.t === 'a'"
                                        :href="p.href"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        class="text-primary-text hover:underline"
                                        >{{ p.v }}</a
                                    >
                                    <template v-else>{{ p.v }}</template>
                                </template>
                            </li>
                        </ul>
                        <p v-else>
                            <template v-for="(p, n) in b.parts" :key="n">
                                <strong v-if="p.t === 'b'">{{ p.v }}</strong>
                                <code v-else-if="p.t === 'code'">{{ p.v }}</code>
                                <a
                                    v-else-if="p.t === 'a'"
                                    :href="p.href"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="text-primary-text hover:underline"
                                    >{{ p.v }}</a
                                >
                                <template v-else>{{ p.v }}</template>
                            </template>
                        </p>
                    </template>
                </div>
            </SettingsSection>
        </div>
    </SettingsLayout>
</template>

<script setup lang="ts">
// Thanh tiến trình ghép nối Chrome: hỏi /settings/chrome/pair-status mỗi 2 giây (tối đa 3 phút)
// sau khi tạo mã ghép nối hoặc tạo hồ sơ Chrome mới, để người dùng thấy đang tới bước nào.
import {
    IconAlertTriangle,
    IconCircleCheckFilled,
    IconCircleDashed,
    IconRefresh,
    IconX,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, ref } from 'vue';

import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';

export type PairStage = 'opening' | 'waiting_extension' | 'paired' | 'account';

export interface PairProgressStart {
    /** create = app vừa mở một hồ sơ Chrome mới (có bước "Đang mở Chrome"); code = người dùng tự nhập mã. */
    mode: 'create' | 'code';
    /** Thư mục profile vừa yêu cầu mở (vd. "Profile 3"), để biết Chrome đã mở chưa. */
    profile?: string | null;
    browser?: 'chrome' | 'edge' | null;
}

interface StatusResponse {
    since: number;
    stage: PairStage;
    pair_active: boolean;
    launcher_alive: boolean;
    profile_seen: boolean | null;
    client: {
        id: number;
        label: string;
        tiktok_username: string | null;
    } | null;
}

const emit = defineEmits<{
    /** Đã ghép nối hoặc đã nhận tài khoản: trang nên tải lại danh sách Chrome. */
    (e: 'changed', stage: PairStage): void;
}>();

const POLL_MS = 2000;
const TIMEOUT_MS = 3 * 60 * 1000;

const active = ref(false);
const running = ref(false);
const timedOut = ref(false);
const options = ref<PairProgressStart>({ mode: 'code' });
const status = ref<StatusResponse | null>(null);

let since: number | null = null;
let startedAt = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
let generation = 0;

const stop = (): void => {
    running.value = false;
    generation++;
    if (timer) {
        clearTimeout(timer);
        timer = null;
    }
};

const poll = async (gen: number): Promise<void> => {
    try {
        const params = new URLSearchParams();
        if (since !== null) params.set('since', String(since));
        if (options.value.profile) {
            params.set('profile', options.value.profile);
            params.set('browser', options.value.browser ?? 'chrome');
        }
        const r = await fetch(`/settings/chrome/pair-status?${params}`, {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        });
        if (gen !== generation) return;
        if (r.ok) {
            const data = (await r.json()) as StatusResponse;
            if (gen !== generation) return;
            const before = status.value?.stage;
            since = data.since;
            status.value = data;
            if (
                data.stage !== before &&
                (data.stage === 'paired' || data.stage === 'account')
            ) {
                emit('changed', data.stage);
            }
            if (data.stage === 'account') {
                stop();
                return;
            }
        }
    } catch {
        // Mất mạng thoáng qua: hỏi lại ở lượt sau.
    }

    if (gen !== generation) return;

    if (Date.now() - startedAt >= TIMEOUT_MS) {
        timedOut.value = true;
        stop();
        return;
    }

    timer = setTimeout(() => poll(gen), POLL_MS);
};

const start = (opts: PairProgressStart, keepSince = false): void => {
    stop();
    options.value = opts;
    timedOut.value = false;
    if (!keepSince) {
        status.value = null;
        since = null;
    }
    startedAt = Date.now();
    active.value = true;
    running.value = true;
    void poll(generation);
};

// Chờ thêm: giữ mốc thời gian cũ để Chrome ghép trong lúc chờ vẫn được nhận.
const retry = (): void => start(options.value, true);

const close = (): void => {
    stop();
    active.value = false;
};

defineExpose({ start: (opts: PairProgressStart) => start(opts), stop: close });
onBeforeUnmount(stop);

const stage = computed<PairStage>(
    () =>
        status.value?.stage ??
        (options.value.mode === 'create' ? 'opening' : 'waiting_extension'),
);

const order: PairStage[] = [
    'opening',
    'waiting_extension',
    'paired',
    'account',
];

const handle = computed(() =>
    (status.value?.client?.tiktok_username ?? '').replace(/^@/, ''),
);

type StepState = 'done' | 'active' | 'pending' | 'failed';

interface Step {
    key: PairStage;
    label: string;
    state: StepState;
}

const steps = computed<Step[]>(() => {
    const create = options.value.mode === 'create';
    const current = order.indexOf(stage.value);
    const at = (key: PairStage): StepState => {
        const i = order.indexOf(key);
        if (key === 'account' && stage.value === 'account') return 'done';
        if (i < current) return 'done';
        if (i === current) return timedOut.value ? 'failed' : 'active';
        return 'pending';
    };

    const list: Step[] = [];
    if (create) {
        list.push({
            key: 'opening',
            label:
                at('opening') === 'done' ? 'Đã mở Chrome' : 'Đang mở Chrome…',
            state: at('opening'),
        });
    }
    list.push({
        key: 'waiting_extension',
        label:
            at('waiting_extension') === 'done'
                ? 'Tiện ích đã kết nối với app'
                : create
                  ? 'Đang chờ tiện ích kết nối…'
                  : 'Đang chờ tiện ích kết nối… (nhập mã 6 số vào tiện ích)',
        state: at('waiting_extension'),
    });
    list.push({
        key: 'paired',
        label: create
            ? 'Đã ghép xong — hãy đăng nhập TikTok trong cửa sổ Chrome vừa mở'
            : 'Đã ghép xong — hãy đăng nhập TikTok trong Chrome đó',
        state: at('paired'),
    });
    list.push({
        key: 'account',
        label: handle.value
            ? `Đã nhận tài khoản @${handle.value}`
            : 'Nhận tài khoản TikTok',
        state: at('account'),
    });
    return list;
});

/** Hết giờ khi đã ghép xong nhưng chưa thấy tài khoản: không phải lỗi, chỉ là chưa đăng nhập. */
const waitingLogin = computed(() => timedOut.value && stage.value === 'paired');
const failed = computed(
    () =>
        timedOut.value &&
        (stage.value === 'opening' || stage.value === 'waiting_extension'),
);
const done = computed(() => stage.value === 'account');
</script>

<template>
    <div
        v-if="active"
        class="flex flex-col gap-3 rounded-xl border p-4 text-sm shadow-raised"
        :class="
            done
                ? 'border-success-text/30 bg-success-subtle'
                : failed
                  ? 'border-amber-500/40 bg-amber-500/10'
                  : 'border-primary-strong/25 bg-primary-subtle'
        "
        data-testid="fork-chrome-pair-progress"
        aria-live="polite"
    >
        <div class="flex items-start justify-between gap-3">
            <p class="text-[15px] font-semibold">
                {{
                    done
                        ? 'Kết nối xong'
                        : failed
                          ? 'Chưa kết nối được'
                          : 'Đang kết nối Chrome'
                }}
            </p>
            <button
                type="button"
                class="-m-1 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Ẩn tiến trình"
                @click="close"
            >
                <IconX class="size-4" />
            </button>
        </div>

        <ol class="flex flex-col gap-2">
            <li
                v-for="step in steps"
                :key="step.key"
                class="flex items-start gap-2"
                :data-state="step.state"
            >
                <IconCircleCheckFilled
                    v-if="step.state === 'done'"
                    class="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400"
                />
                <Spinner
                    v-else-if="step.state === 'active'"
                    class="mt-0.5 size-4 shrink-0"
                />
                <IconAlertTriangle
                    v-else-if="step.state === 'failed'"
                    class="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400"
                />
                <IconCircleDashed
                    v-else
                    class="mt-0.5 size-4 shrink-0 text-muted-foreground/60"
                />
                <span
                    :class="{
                        'text-muted-foreground': step.state === 'pending',
                        'font-emphasis': step.state === 'active',
                        'text-emerald-700 dark:text-emerald-400':
                            step.state === 'done' && step.key === 'account',
                    }"
                >
                    {{ step.label }}
                </span>
            </li>
        </ol>

        <p v-if="stage === 'paired' && !timedOut" class="text-muted-foreground">
            Đăng nhập xong, tiện ích sẽ tự báo tên tài khoản về đây trong vài
            giây.
        </p>

        <p v-if="waitingLogin" class="text-muted-foreground">
            Chrome đã ghép nối nhưng chưa thấy tài khoản TikTok. Hãy mở
            tiktok.com trong cửa sổ Chrome đó và đăng nhập; khi xong, tên tài
            khoản sẽ hiện ở mục “Chrome đã ghép nối” bên dưới.
        </p>

        <div v-if="failed" class="flex flex-col gap-2">
            <p>Đã chờ 3 phút mà chưa thấy tiện ích kết nối. Hãy kiểm tra:</p>
            <ul class="list-disc space-y-1 pl-5 text-muted-foreground">
                <li
                    v-if="
                        options.mode === 'create' &&
                        status &&
                        !status.launcher_alive
                    "
                    class="text-foreground"
                >
                    Trợ lý mở Chrome đang không chạy: thoát hẳn TikTok Auto Kid
                    (biểu tượng ở góc phải thanh tác vụ) rồi mở lại.
                </li>
                <li v-if="stage === 'opening'">
                    Có cửa sổ Chrome mới hiện ra không? Nếu không, kiểm tra máy
                    đã cài Google Chrome và thử lại.
                </li>
                <li>
                    Trên thanh công cụ Chrome có biểu tượng TikTok Auto Kid
                    không? Nếu không, vào <code>chrome://extensions</code>, bật
                    “Chế độ cho nhà phát triển” và kiểm tra tiện ích đang bật.
                </li>
                <li>
                    Địa chỉ máy chủ trong tiện ích phải là
                    <code>http://localhost:8010</code>.
                </li>
                <li
                    v-if="
                        options.mode === 'code' ||
                        (status && !status.pair_active)
                    "
                >
                    Mã ghép nối chỉ dùng được 5 phút<template
                        v-if="status && !status.pair_active"
                    >
                        và hiện đã hết hạn: bấm “Tạo mã mới” rồi nhập
                        lại</template
                    >.
                </li>
            </ul>
        </div>

        <div v-if="timedOut" class="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" @click="retry">
                <IconRefresh class="size-4" />
                Chờ thêm 3 phút
            </Button>
        </div>
    </div>
</template>

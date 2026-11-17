<script setup lang="ts">
// Dòng "AI xem video" trên trang Kho riêng: AI đang xem video nào, còn bao nhiêu video chờ, lỗi gì, khi nào thử lại.
// Hỏi lại máy chủ vài giây một lần khi AI đang làm; xong một video thì báo trang tải lại thẻ.
import {
    IconAlertTriangle,
    IconCircleCheck,
    IconLoader2,
    IconPlayerPlay,
    IconSparkles,
} from '@tabler/icons-vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { toast } from 'vue-sonner';

import { callJson, type AiStatus } from '@/components/fork/kho/rieng';
import { toneClasses } from '@/components/fork/shared/status';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const emit = defineEmits<{
    /** Có video vừa xem xong: trang tải lại thẻ video. */
    changed: [];
    /** Thiếu ChatGPT CLI / tài khoản: mở hộp "Tự đăng theo khung". */
    settings: [];
}>();

const st = ref<AiStatus | null>(null);
const starting = ref(false);
let timer: ReturnType<typeof setTimeout> | null = null;
let alive = true;

// Dấu vết để biết "có gì vừa xong": video đang xem đổi, hoặc số video chờ giảm.
const sig = (s: AiStatus | null) =>
    s
        ? `${s.running?.id ?? '-'}|${s.queued}|${s.waiting}|${s.gave_up}|${s.unsure}`
        : '';

// Vừa bấm "Cho AI xem ngay": hỏi dày trong 1 phút đầu để thấy AI bắt đầu.
let kickUntil = 0;
const busy = computed(() => !!st.value?.running || Date.now() < kickUntil);

const load = async () => {
    const r = await callJson<AiStatus>(
        'GET',
        '/auto/kho/rieng/tu-dong/ai-trang-thai',
    );

    if (r.ok && r.data) {
        const before = sig(st.value);
        st.value = r.data;

        if (before !== '' && before !== sig(r.data)) {
            emit('changed');
        }
    }
};

const schedule = () => {
    if (!alive) {
        return;
    }

    // Đang xem: 4 giây; còn việc: 15 giây; xong hết: 60 giây. Tab ẩn thì thưa hơn.
    const s = st.value;
    const base = !s
        ? 15000
        : busy.value
          ? 4000
          : s.queued + s.waiting > 0
            ? 15000
            : 60000;
    timer = setTimeout(
        async () => {
            await load();
            schedule();
        },
        document.hidden ? Math.max(base, 30000) : base,
    );
};

const runNow = async () => {
    starting.value = true;
    const r = await callJson<AiStatus>(
        'POST',
        '/auto/kho/rieng/tu-dong/ai-chay-ngay',
    );
    starting.value = false;

    if (r.ok && r.data) {
        st.value = r.data;
        kickUntil = Date.now() + 60000;
        toast.success('AI bắt đầu xem video, anh chờ chút nhé.');
        if (timer) {
            clearTimeout(timer);
        }
        schedule();
    } else {
        toast.error('Chưa cho AI chạy được, anh thử lại sau ít phút.');
    }
};

onMounted(async () => {
    await load();
    schedule();
});

onBeforeUnmount(() => {
    alive = false;

    if (timer) {
        clearTimeout(timer);
    }
});

defineExpose({ reload: load });
</script>

<template>
    <div
        v-if="st"
        :class="
            cn(
                'flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border px-3 py-2 text-sm',
                toneClasses[st.tone].box,
            )
        "
        role="status"
        data-testid="fork-rieng-ai-status"
    >
        <IconLoader2 v-if="st.running" class="size-4 shrink-0 animate-spin" />
        <IconAlertTriangle
            v-else-if="st.tone === 'warn'"
            class="size-4 shrink-0"
        />
        <IconCircleCheck
            v-else-if="st.tone === 'success'"
            class="size-4 shrink-0"
        />
        <IconSparkles v-else class="size-4 shrink-0" />
        <div class="min-w-0 flex-1">
            <div class="font-medium break-words">{{ st.title }}</div>
            <div v-if="st.detail" class="text-xs break-words opacity-80">
                {{ st.detail }}
            </div>
            <div
                v-if="st.running"
                class="mt-1.5 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-black/10 dark:bg-white/10"
            >
                <div
                    class="h-full rounded-full bg-current transition-all duration-500"
                    :style="{
                        width: `${Math.max(8, Math.round(((st.running.buoc - 0.5) / Math.max(1, st.running.tong)) * 100))}%`,
                    }"
                />
            </div>
        </div>
        <Button
            v-if="st.fix === 'settings'"
            size="sm"
            variant="outline"
            class="h-8 bg-background"
            @click="emit('settings')"
            >Mở cài đặt</Button
        >
        <Button
            v-else-if="st.can_run && !st.running"
            size="sm"
            variant="outline"
            class="h-8 bg-background"
            :disabled="starting"
            data-testid="fork-rieng-ai-run"
            @click="runNow"
        >
            <IconLoader2 v-if="starting" class="size-4 animate-spin" />
            <IconPlayerPlay v-else class="size-4" />
            Cho AI xem ngay
        </Button>
    </div>
</template>

<script setup lang="ts">
// Thẻ "Bắt đầu" cho máy mới cài: 4 bước kèm trạng thái thật, mỗi bước có nút tới đúng chỗ.
// Máy chủ tự ẩn thẻ khi xong cả 4 bước; chủ app cũng có thể bấm "Ẩn hướng dẫn".
import { Link, router } from '@inertiajs/vue3';
import {
    IconCheck,
    IconChevronRight,
    IconPlugConnectedX,
    IconRocket,
    IconX,
} from '@tabler/icons-vue';
import { computed, ref } from 'vue';

import type { Onboarding } from '@/components/fork/auto/types';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const props = defineProps<{ onboarding: Onboarding }>();

const hiding = ref(false);
const percent = computed(() =>
    Math.round((props.onboarding.done / props.onboarding.total) * 100),
);

const hide = () => {
    hiding.value = true;
    router.post(
        '/auto/huong-dan/an',
        {},
        {
            preserveScroll: true,
            onFinish: () => {
                hiding.value = false;
            },
        },
    );
};

// "#kenh" là chỗ trên cùng trang: cuộn tới thay vì tải trang.
const isAnchor = (href: string) => href.startsWith('#');
const scrollTo = (href: string) =>
    document
        .querySelector(href)
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
</script>

<template>
    <section
        class="rounded-2xl border bg-card p-5 shadow-xs"
        data-testid="fork-auto-onboarding"
    >
        <div class="flex items-start gap-3">
            <div
                class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
                <IconRocket class="size-5" />
            </div>
            <div class="min-w-0 flex-1">
                <h2 class="text-lg font-semibold">Bắt đầu tự động đăng</h2>
                <p class="text-sm text-muted-foreground">
                    Xong {{ onboarding.done }}/{{ onboarding.total }} bước. Làm
                    hết các bước là app tự sản xuất và đăng video.
                </p>
            </div>
            <Button
                variant="ghost"
                size="sm"
                class="shrink-0 text-muted-foreground"
                :disabled="hiding"
                data-testid="fork-auto-onboarding-hide"
                @click="hide"
            >
                <IconX class="size-4" />
                Ẩn hướng dẫn
            </Button>
        </div>

        <div class="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
            <div
                class="h-full rounded-full bg-primary transition-[width] duration-500"
                :style="{ width: `${percent}%` }"
            />
        </div>

        <ol class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <li
                v-for="(s, i) in onboarding.steps"
                :key="s.key"
                :class="
                    cn(
                        'flex flex-col gap-2 rounded-xl border p-3.5',
                        s.done
                            ? 'border-emerald-200 bg-emerald-50/60 dark:border-emerald-900 dark:bg-emerald-950/30'
                            : 'bg-background',
                    )
                "
                :data-testid="`fork-auto-onboarding-${s.key}`"
            >
                <div class="flex items-center gap-2.5">
                    <span
                        :class="
                            cn(
                                'flex size-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold',
                                s.done
                                    ? 'bg-emerald-500 text-white'
                                    : s.state === 'offline'
                                      ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
                                      : 'bg-muted text-muted-foreground',
                            )
                        "
                    >
                        <IconCheck v-if="s.done" class="size-4" />
                        <IconPlugConnectedX
                            v-else-if="s.state === 'offline'"
                            class="size-4"
                        />
                        <template v-else>{{ i + 1 }}</template>
                    </span>
                    <span class="font-medium">{{ s.title }}</span>
                </div>
                <p
                    :class="
                        cn(
                            'text-sm leading-snug',
                            s.done
                                ? 'text-emerald-700 dark:text-emerald-300'
                                : s.state === 'offline'
                                  ? 'text-amber-700 dark:text-amber-300'
                                  : 'text-muted-foreground',
                        )
                    "
                >
                    {{ s.detail }}
                </p>
                <div v-if="s.action" class="mt-auto pt-1">
                    <Button
                        v-if="isAnchor(s.action.href)"
                        size="sm"
                        variant="outline"
                        @click="scrollTo(s.action.href)"
                    >
                        {{ s.action.label }}
                        <IconChevronRight class="size-4" />
                    </Button>
                    <Button v-else as-child size="sm" variant="outline">
                        <Link :href="s.action.href">
                            {{ s.action.label }}
                            <IconChevronRight class="size-4" />
                        </Link>
                    </Button>
                </div>
            </li>
        </ol>
    </section>
</template>

<script setup lang="ts">
// Nhãn nhỏ phân biệt video AI (Xưởng Video) và video Kho riêng. Không biết nguồn thì không hiện gì.
import { IconFolder, IconSparkles } from '@tabler/icons-vue';
import { computed } from 'vue';

import { SOURCE_LABEL, SOURCE_TITLE, sourceKind } from '@/components/fork/shared/source';
import { cn } from '@/lib/utils';

const props = defineProps<{ source: string | null | undefined; class?: string }>();
const kind = computed(() => sourceKind(props.source));
</script>

<template>
    <span
        v-if="kind"
        :class="
            cn(
                'inline-flex h-5 shrink-0 items-center gap-1 rounded-full px-1.5 text-[0.6875rem] leading-none font-medium whitespace-nowrap',
                kind === 'ai'
                    ? 'bg-violet-50 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300'
                    : 'bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300',
                props.class,
            )
        "
        :title="SOURCE_TITLE[kind]"
        :data-source="kind"
    >
        <IconSparkles v-if="kind === 'ai'" class="size-3" />
        <IconFolder v-else class="size-3" />
        {{ SOURCE_LABEL[kind] }}
    </span>
</template>

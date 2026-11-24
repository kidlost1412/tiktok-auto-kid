<script setup lang="ts">
// Nhãn nhỏ phân biệt video AI (Xưởng Video) và video Kho riêng. Không biết nguồn thì không hiện gì.
import { IconFolder } from '@tabler/icons-vue';
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
                'inline-flex h-5 shrink-0 items-center gap-1 rounded-md bg-secondary px-1.5 text-xs leading-none font-medium whitespace-nowrap text-muted-foreground',
                props.class,
            )
        "
        :title="SOURCE_TITLE[kind]"
        :data-source="kind"
    >
        <IconFolder v-if="kind === 'rieng'" class="size-3" />
        {{ SOURCE_LABEL[kind] }}
    </span>
</template>

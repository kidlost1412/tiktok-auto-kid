<script setup lang="ts">
// Thanh chuyển trang dùng chung của hai kho: "Trang X / Y · N video" và nút Trước / Sau.
import { Button } from '@/components/ui/button';

defineProps<{
    page: number;
    last: number;
    total: number;
}>();

const emit = defineEmits<{ go: [page: number] }>();
</script>

<template>
    <div
        class="flex items-center justify-center gap-3 text-sm"
        data-testid="fork-kho-pager"
    >
        <Button
            v-if="last > 1"
            size="sm"
            variant="outline"
            :disabled="page <= 1"
            aria-label="Trang trước"
            @click="emit('go', page - 1)"
        >
            Trước
        </Button>
        <span class="tabular-nums">
            <template v-if="last > 1">Trang {{ page }} / {{ last }} · </template
            >{{ total }} video
        </span>
        <Button
            v-if="last > 1"
            size="sm"
            variant="outline"
            :disabled="page >= last"
            aria-label="Trang sau"
            @click="emit('go', page + 1)"
        >
            Sau
        </Button>
    </div>
</template>

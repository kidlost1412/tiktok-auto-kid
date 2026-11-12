<script setup lang="ts">
import AppLayout from '@/layouts/AppLayout.vue';

defineProps<{
    title?: string;
    description?: string;
}>();
</script>

<template>
    <AppLayout>
        <div
            class="mx-auto flex w-full max-w-[1880px] flex-col gap-5 px-4 pt-6 pb-20 md:px-8"
            data-testid="settings-page"
        >
            <header v-if="title" class="mb-1">
                <h1
                    class="text-[22px] leading-tight font-semibold tracking-[-0.022em] text-foreground"
                    data-testid="header-title"
                >
                    {{ title }}
                </h1>
                <p
                    v-if="description"
                    class="mt-1 max-w-4xl text-sm text-muted-foreground"
                    data-testid="settings-page-description"
                >
                    {{ description }}
                </p>
            </header>
            <slot />
        </div>
    </AppLayout>
</template>

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
            class="mx-auto flex w-full max-w-[1200px] flex-col gap-10 px-4 pt-8 pb-20 md:px-8 md:pt-12"
            data-testid="settings-page"
        >
            <header v-if="title">
                <h1
                    class="font-heading text-3xl leading-tight font-semibold text-foreground"
                    data-testid="header-title"
                >
                    {{ title }}
                </h1>
                <p
                    v-if="description"
                    class="mt-2 text-base text-muted-foreground"
                    data-testid="settings-page-description"
                >
                    {{ description }}
                </p>
            </header>
            <slot />
        </div>
    </AppLayout>
</template>

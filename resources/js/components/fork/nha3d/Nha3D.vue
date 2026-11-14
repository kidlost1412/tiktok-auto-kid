<script setup lang="ts">
// Khung ngôi nhà 3D: tải three.js lười (chỉ khi mở trang này), không có WebGL hoặc dựng lỗi thì báo `fallback`
// để trang quay về ngôi nhà 2D.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { onBanBao } from '@/components/fork/nha/ban/bus';
import type { NhaData } from '@/components/fork/nha/types';

import './nha3d.css';
import type { NhaWorld } from './index';

const props = defineProps<{
    data: NhaData | null;
    hour?: number | null;
    debug?: boolean;
    avatar?: Record<string, unknown> | null;
}>();
const emit = defineEmits<{ go: [key: string]; fallback: [] }>();

const host = ref<HTMLDivElement | null>(null);
const ready = ref(false);
let world: NhaWorld | null = null;
let gone = false;
// popup làm xong một việc → nhân vật tương ứng phản ứng
const offBao = onBanBao((b) => world?.react(b.vai, b.viec));

const fail = (err: unknown) => {
    console.error('[Khu Tự Trị 3D] chuyển về bản 2D:', err);
    world?.dispose();
    world = null;
    if (!gone) {
        emit('fallback');
    }
};

onMounted(async () => {
    try {
        const mod = await import('./index');
        if (gone || !host.value) {
            return;
        }
        if (!mod.webglOk()) {
            throw new Error('Trình duyệt không hỗ trợ WebGL');
        }
        world = mod.createNhaWorld({
            host: host.value,
            reduced:
                window.matchMedia?.('(prefers-reduced-motion: reduce)')
                    .matches ?? false,
            hour: props.hour ?? null,
            debug: props.debug,
            avatar: props.avatar ?? null,
            onGo: (k) => emit('go', k),
            onOpen: (url) =>
                url
                    ? window.open(url, '_blank', 'noopener')
                    : emit('go', 'giamkhao'),
            onFail: fail,
        });
        if (props.data) {
            world.update(props.data);
        }
        ready.value = true;
    } catch (err) {
        fail(err);
    }
});

watch(
    () => props.data,
    (d) => {
        if (d) {
            world?.update(d);
        }
    },
);

onBeforeUnmount(() => {
    gone = true;
    offBao();
    world?.dispose();
    world = null;
});
</script>

<template>
    <div
        ref="host"
        class="n3-host h-full"
        role="img"
        aria-label="Khu Tự Trị 3D: ngôi nhà và các nhân vật đang làm việc"
        data-testid="nha-3d"
    >
        <div
            v-if="!ready"
            class="absolute inset-0 grid place-items-center text-[0.9375rem] font-semibold text-[#4a3868]"
        >
            Đang dựng ngôi nhà…
        </div>
    </div>
</template>

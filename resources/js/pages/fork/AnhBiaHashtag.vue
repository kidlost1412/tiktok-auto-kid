<script setup lang="ts">
// Trang "Ảnh bìa & hashtag": mỗi sản phẩm hub đang bật một thẻ tóm tắt ảnh bìa + hashtag,
// sửa bằng đúng hộp thoại "Cá nhân hoá" của trang Giỏ hàng. Đầu trang: giải thích + hashtag mặc định chung.
import {
    IconHash,
    IconInfoCircle,
    IconPencil,
    IconPackageOff,
    IconPhoto,
    IconShoppingCart,
} from '@tabler/icons-vue';
import { computed } from 'vue';

import PersonaCard from '@/components/fork/anh-bia/PersonaCard.vue';
import type { PersonaProduct } from '@/components/fork/anh-bia/types';
import PersonaliseDialog from '@/components/fork/gio-hang/PersonaliseDialog.vue';
import type { Persona, PersonaDefault } from '@/components/fork/gio-hang/types';
import { usePersonalise } from '@/components/fork/gio-hang/usePersonalise';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

const props = defineProps<{
    products: PersonaProduct[];
    personalise?: Record<string, Persona>;
    personalise_default?: PersonaDefault;
}>();

const { personaOf, dialogProps, openProduct, openDefault, closePersonalise } =
    usePersonalise(() => props);

const defaults = computed<PersonaDefault>(
    () => props.personalise_default ?? { tags: [], mode: 'append', pick: 0 },
);

const defaultDetail = computed(() => {
    const d = defaults.value;

    if (!d.tags.length) {
        return 'Chưa đặt. Sản phẩm không có hashtag riêng sẽ giữ nguyên hashtag hub viết.';
    }

    const how =
        d.mode === 'replace'
            ? 'Thay toàn bộ hashtag cũ'
            : 'Thêm vào cuối caption';
    const pick =
        d.pick > 0 && d.pick < d.tags.length
            ? ` · mỗi bài chọn ngẫu nhiên ${d.pick}/${d.tags.length}`
            : '';

    return `${how}${pick}.`;
});

// Đếm nhanh cho dòng tóm tắt.
const customCovers = computed(
    () =>
        props.products.filter((p) => {
            const s = personaOf(p.code);

            return s.cover_mode !== 'default' && s.covers.length > 0;
        }).length,
);
const customTags = computed(
    () =>
        props.products.filter((p) => personaOf(p.code).hashtags.length > 0)
            .length,
);
</script>

<template>
    <AutoShell
        title="Ảnh bìa & hashtag"
        description="Đặt ảnh bìa và hashtag riêng cho từng sản phẩm. App tự áp vào mỗi bài khi đăng, cho mọi kênh và mọi quy cách."
        testid="fork-anh-bia-page"
    >
        <!-- Giải thích + hashtag mặc định chung -->
        <section class="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <div
                class="flex flex-col gap-4 rounded-[14px] border bg-card p-5 sm:p-6 shadow-[0_1px_2px_rgba(28,25,23,.04),0_2px_6px_-1px_rgba(28,25,23,.06)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,.03),0_1px_2px_rgba(0,0,0,.35)]"
                data-testid="fork-anh-bia-intro"
            >
                <SectionHeading
                    :icon="IconInfoCircle"
                    tone="info"
                    title="Cách hoạt động"
                />
                <ul class="flex flex-col gap-2.5 text-sm text-muted-foreground">
                    <li class="flex gap-2.5">
                        <IconPhoto
                            class="mt-0.5 size-4 shrink-0 text-foreground"
                        />
                        <span>
                            <b class="font-medium text-foreground">Ảnh bìa</b>:
                            để <i>Mặc định</i> thì TikTok lấy khung hình trong
                            video. Chọn <i>1 ảnh cố định</i> để mọi bài dùng
                            chung một ảnh, hoặc <i>Ngẫu nhiên</i> để xoay vòng
                            đều các ảnh trong bộ (ít ảnh vẫn dùng lặp lại,
                            không trùng ảnh bài trước).
                        </span>
                    </li>
                    <li class="flex gap-2.5">
                        <IconHash
                            class="mt-0.5 size-4 shrink-0 text-foreground"
                        />
                        <span>
                            <b class="font-medium text-foreground">Hashtag</b>:
                            sản phẩm có hashtag riêng thì dùng hashtag riêng;
                            không có thì dùng <i>hashtag mặc định chung</i> ở
                            bên cạnh. Có thể thêm vào cuối caption hoặc thay hẳn
                            hashtag cũ.
                        </span>
                    </li>
                    <li class="flex gap-2.5">
                        <IconShoppingCart
                            class="mt-0.5 size-4 shrink-0 text-foreground"
                        />
                        <span>
                            Chỉ áp cho bài
                            <b class="font-medium text-foreground"
                                >xếp lịch sau khi lưu</b
                            >; bài đã hẹn giờ giữ nguyên.
                        </span>
                    </li>
                </ul>
            </div>

            <div
                class="flex flex-col gap-4 rounded-[14px] border bg-card p-5 sm:p-6 shadow-[0_1px_2px_rgba(28,25,23,.04),0_2px_6px_-1px_rgba(28,25,23,.06)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,.03),0_1px_2px_rgba(0,0,0,.35)]"
                data-testid="fork-anh-bia-default"
            >
                <div class="flex items-start justify-between gap-3">
                    <SectionHeading
                        :icon="IconHash"
                        title="Hashtag mặc định chung"
                        description="Dùng cho sản phẩm chưa có hashtag riêng."
                        class="min-w-0"
                    />
                    <Button
                        size="sm"
                        variant="outline"
                        class="shrink-0"
                        data-testid="fork-personalise-default"
                        @click="openDefault"
                    >
                        <IconPencil class="size-4" />
                        Sửa
                    </Button>
                </div>
                <div v-if="defaults.tags.length" class="flex flex-wrap gap-1.5">
                    <span
                        v-for="t in defaults.tags"
                        :key="t"
                        class="rounded-full bg-primary-subtle px-2.5 py-0.5 text-xs font-medium text-primary-text"
                        >{{ t }}</span
                    >
                </div>
                <p class="text-sm text-muted-foreground">
                    {{ defaultDetail }}
                </p>
            </div>
        </section>

        <!-- Sản phẩm -->
        <section
            class="flex flex-col gap-4"
            data-testid="fork-anh-bia-products"
        >
            <SectionHeading
                :icon="IconPhoto"
                title="Sản phẩm đang bật"
                description="Bấm Chỉnh trên thẻ để tải ảnh bìa, chọn kiểu bìa và nhập hashtag; có xem trước caption."
            >
                <template v-if="products.length">
                    <Badge variant="outline"
                        >{{ products.length }} sản phẩm</Badge
                    >
                    <Badge variant="outline"
                        >{{ customCovers }} có ảnh bìa riêng</Badge
                    >
                    <Badge variant="outline"
                        >{{ customTags }} có hashtag riêng</Badge
                    >
                </template>
            </SectionHeading>

            <div
                v-if="products.length"
                class="grid gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
            >
                <PersonaCard
                    v-for="p in products"
                    :key="p.code"
                    :product="p"
                    :persona="personaOf(p.code)"
                    :defaults="defaults"
                    @edit="openProduct(p.code, p.name)"
                />
            </div>

            <EmptyState
                v-else
                :icon="IconPackageOff"
                title="Chưa có sản phẩm nào đang bật"
                description="Khi Xưởng Video gửi sản phẩm sang và sản phẩm đang bật, thẻ ảnh bìa & hashtag sẽ hiện ở đây."
                data-testid="fork-anh-bia-empty"
            >
                <Button as-child size="sm" variant="outline">
                    <a href="/auto/kho">Đến Kho video →</a>
                </Button>
            </EmptyState>
        </section>

        <PersonaliseDialog
            v-bind="dialogProps"
            @update:open="closePersonalise"
        />
    </AutoShell>
</template>

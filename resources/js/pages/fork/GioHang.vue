<script setup lang="ts">
// Trang riêng của bản Việt hoá: chọn sản phẩm TikTok Shop cho từng sản phẩm của hub, từng quy cách, trên từng kênh.
// Chữ trên trang viết thẳng bằng tiếng Việt (không qua lang/en).
import { router } from '@inertiajs/vue3';
import { IconHash, IconPlugConnectedX, IconRefresh } from '@tabler/icons-vue';
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';

import HubProductCard from '@/components/fork/gio-hang/HubProductCard.vue';
import PersonaliseDialog from '@/components/fork/gio-hang/PersonaliseDialog.vue';
import ShopPickerDialog from '@/components/fork/gio-hang/ShopPickerDialog.vue';
import type {
    Persona,
    PersonaDefault,
    Row,
    ShopCard,
    ShopProduct,
    Sync,
} from '@/components/fork/gio-hang/types';
import { usePersonalise } from '@/components/fork/gio-hang/usePersonalise';
import AutoShell from '@/components/fork/shared/AutoShell.vue';
import Callout from '@/components/fork/shared/Callout.vue';
import EmptyState from '@/components/fork/shared/EmptyState.vue';
import SectionHeading from '@/components/fork/shared/SectionHeading.vue';
import { useVisitLoading } from '@/components/fork/shared/useVisitLoading';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import dayjs from '@/dayjs';

const props = defineProps<{
    channels: {
        id: string;
        username: string | null;
        display_name: string | null;
    }[];
    selected: string | null;
    sync: Sync | null;
    products: ShopProduct[];
    rows: Row[];
    name_max: number;
    sync_ttl_minutes: number;
    personalise?: Record<string, Persona>;
    personalise_default?: PersonaDefault;
}>();

const busy = ref<string | null>(null);
const opts = {
    preserveScroll: true,
    onFinish: () => {
        busy.value = null;
    },
};

const fmtTime = (iso: string | null | undefined) =>
    iso ? dayjs(iso).format('DD/MM HH:mm') : 'chưa lần nào';

// ---- Chọn kênh ----
const { loading, callbacks } = useVisitLoading();

const chooseChannel = (id: string) => {
    router.get(
        '/auto/gio-hang',
        { kenh: id },
        { preserveScroll: false, ...callbacks },
    );
};

// ---- Lấy sản phẩm từ shop ----
const syncState = computed(() => props.sync?.state ?? 'idle');

const syncShop = () => {
    if (!props.selected) {
        return;
    }

    busy.value = 'sync';
    router.post(`/auto/accounts/${props.selected}/shop/sync`, {}, opts);
};

// Đang chờ tiện ích thì tự làm mới trạng thái mỗi 5 giây.
let timer: ReturnType<typeof setInterval> | null = null;
watch(
    syncState,
    (state) => {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }

        if (state === 'waiting') {
            timer = setInterval(() => {
                router.reload({
                    only: ['sync', 'products', 'rows'],
                });
            }, 5000);
        }
    },
    { immediate: true },
);
onBeforeUnmount(() => {
    if (timer) {
        clearInterval(timer);
    }
});

// ---- Ẩn / hiện sản phẩm shop ----
const setHidden = (p: ShopProduct, hidden: boolean) => {
    if (!props.selected) {
        return;
    }

    busy.value = `hide-${p.product_id}`;
    router.patch(
        `/auto/accounts/${props.selected}/shop-products/${p.product_id}`,
        { hidden },
        opts,
    );
};

// ---- Thẻ ghép: mỗi thẻ = sản phẩm hub x quy cách ----
interface Draft {
    shop_product_id?: string;
    display_name?: string;
    edited?: boolean; // đã sửa tên tay thì đổi sản phẩm không ghi đè tên
}

const draft = reactive<Record<string, Draft>>({});
const picking = ref<string | null>(null); // khoá dòng đang chọn sản phẩm cho nó

const pickedId = (r: Row) =>
    draft[r.key]?.shop_product_id ?? r.link?.shop_product_id ?? '';

const nameOf = (r: Row) =>
    draft[r.key]?.display_name ?? r.link?.display_name ?? '';

const cardOf = (r: Row): ShopCard | null => {
    const id = pickedId(r);

    if (id === '') {
        return null;
    }

    return (
        props.products.find((p) => p.product_id === id) ??
        (r.link?.shop_product_id === id ? r.link.product : null)
    );
};

const isDirty = (r: Row) =>
    pickedId(r) !== '' &&
    (pickedId(r) !== (r.link?.shop_product_id ?? '') ||
        nameOf(r) !== (r.link?.display_name ?? '') ||
        r.link?.paused_reason != null);

const pickingRow = computed(
    () => props.rows.find((r) => r.key === picking.value) ?? null,
);

const pickFor = (p: ShopProduct) => {
    const r = pickingRow.value;

    if (!r) {
        return;
    }

    const d = (draft[r.key] ??= {});
    d.shop_product_id = p.product_id;

    if (!d.edited) {
        d.display_name = p.suggested_name;
    }

    picking.value = null;
};

const editName = (r: Row, value: string) => {
    const d = (draft[r.key] ??= {});
    d.display_name = [...value].slice(0, props.name_max).join('');
    d.edited = true;
};

const saveRow = (r: Row) => {
    if (!props.selected) {
        return;
    }

    busy.value = `row-${r.key}`;
    router.put(
        `/auto/accounts/${props.selected}/links/${r.code}`,
        {
            quy_cach: r.quy_cach,
            shop_product_id: pickedId(r),
            display_name: nameOf(r),
        },
        {
            ...opts,
            onSuccess: () => {
                delete draft[r.key];
            },
        },
    );
};

const clearRow = (r: Row) => {
    if (!props.selected) {
        return;
    }

    if (!r.link) {
        delete draft[r.key];

        return;
    }

    busy.value = `row-${r.key}`;
    router.delete(`/auto/accounts/${props.selected}/links/${r.code}`, {
        ...opts,
        data: { quy_cach: r.quy_cach },
        onSuccess: () => {
            delete draft[r.key];
        },
    });
};

// ---- Cá nhân hoá (ảnh bìa, hashtag) theo sản phẩm hub; 'default' = hashtag mặc định chung ----
const { personaOf, dialogProps, openProduct, openDefault, closePersonalise } =
    usePersonalise(() => props);

// ---- Sắp xếp: thẻ có video chờ mà chưa có giỏ lên đầu ----
// Một thẻ đã chọn sản phẩm trong nháp (chưa lưu) vẫn tính là chưa có giỏ cho tới khi lưu.
const rank = (r: Row) => {
    if (!r.link && r.new_videos > 0) {
        return 0;
    }

    if (r.link && (r.link.paused_reason || r.link.problem)) {
        return 1;
    }

    return r.link ? 2 : 3;
};

const sortedRows = computed(() =>
    [...props.rows].sort(
        (a, b) =>
            rank(a) - rank(b) ||
            b.new_videos - a.new_videos ||
            a.label.localeCompare(b.label, 'vi'),
    ),
);

const needRows = computed(() => props.rows.filter((r) => rank(r) === 0));
const needVideos = computed(() =>
    needRows.value.reduce((s, r) => s + r.new_videos, 0),
);
const problemRows = computed(() => props.rows.filter((r) => rank(r) === 1));
const readyRows = computed(() => props.rows.filter((r) => rank(r) === 2));
</script>

<template>
    <AutoShell
        title="Giỏ hàng"
        description="Chọn sản phẩm TikTok Shop cho từng sản phẩm của hub, từng quy cách, trên từng kênh. Thẻ chưa chọn giỏ thì video được giữ trong kho."
        testid="fork-gio-hang-page"
    >
        <div class="flex flex-col gap-6">
            <EmptyState
                v-if="!channels.length"
                :icon="IconPlugConnectedX"
                title="Chưa có kênh TikTok nào bật đăng qua Chrome"
                description="Bật đăng qua Chrome cho kênh trong phần Kết nối Chrome, rồi quay lại đây chọn giỏ hàng."
                data-testid="fork-gio-hang-empty"
            >
                <Button as-child size="sm">
                    <a href="/settings/chrome">Kết nối Chrome →</a>
                </Button>
            </EmptyState>

            <template v-else>
                <!-- Chọn kênh + lấy sản phẩm -->
                <section
                    class="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs"
                >
                    <div class="flex flex-wrap items-center gap-2">
                        <span class="text-sm font-medium">Kênh</span>
                        <div
                            class="flex flex-wrap gap-1.5"
                            data-testid="fork-gio-hang-channel"
                        >
                            <Button
                                v-for="c in channels"
                                :key="c.id"
                                size="sm"
                                :variant="
                                    c.id === selected ? 'default' : 'outline'
                                "
                                @click="chooseChannel(c.id)"
                                >@{{ c.username }}</Button
                            >
                        </div>
                    </div>

                    <div class="flex flex-wrap items-center gap-3">
                        <Button
                            variant="outline"
                            :disabled="
                                busy === 'sync' || syncState === 'waiting'
                            "
                            data-testid="fork-gio-hang-sync"
                            @click="syncShop"
                        >
                            <Spinner
                                v-if="syncState === 'waiting'"
                                class="size-4"
                            />
                            <IconRefresh v-else class="size-4" />
                            {{
                                syncState === 'waiting'
                                    ? 'Đang chờ tiện ích…'
                                    : syncState === 'idle' ||
                                        syncState === 'done'
                                      ? 'Lấy sản phẩm từ shop'
                                      : 'Bấm lại để lấy sản phẩm từ shop'
                            }}
                        </Button>
                        <span
                            class="text-sm text-muted-foreground"
                            data-testid="fork-gio-hang-synced-at"
                        >
                            {{ products.length }} sản phẩm shop · lần lấy gần
                            nhất: {{ fmtTime(sync?.synced_at) }}
                        </span>
                    </div>

                    <Callout
                        v-if="syncState === 'waiting'"
                        tone="info"
                        data-testid="fork-gio-hang-sync-waiting"
                    >
                        Đang chờ tiện ích Chrome lấy sản phẩm từ shop. Chrome
                        cần đang mở và đã đăng nhập TikTok. Trang tự cập nhật;
                        nếu quá
                        {{ sync_ttl_minutes }} phút yêu cầu sẽ hết hạn.
                    </Callout>
                    <Callout
                        v-else-if="syncState === 'error'"
                        tone="danger"
                        data-testid="fork-gio-hang-sync-error"
                    >
                        Lấy sản phẩm bị lỗi: {{ sync?.reason }}. Tiện ích có thể
                        tự thử lại; nếu không được, bấm nút để gửi yêu cầu mới.
                    </Callout>
                    <Callout
                        v-else-if="syncState === 'expired'"
                        tone="warn"
                        data-testid="fork-gio-hang-sync-expired"
                    >
                        Yêu cầu đã hết hạn sau {{ sync_ttl_minutes }} phút mà
                        tiện ích chưa lấy được. Hãy kiểm tra Chrome đang mở rồi
                        bấm lại.
                    </Callout>
                    <Callout
                        v-else-if="syncState === 'done'"
                        tone="success"
                        data-testid="fork-gio-hang-sync-done"
                    >
                        Đã lấy xong sản phẩm lúc {{ fmtTime(sync?.synced_at) }}.
                    </Callout>
                </section>

                <!-- Tóm tắt -->
                <Callout
                    v-if="needRows.length"
                    tone="warn"
                    data-testid="fork-gio-hang-summary"
                >
                    <b>{{ needVideos }} video</b> thuộc
                    <b>{{ needRows.length }} sản phẩm</b> đang chờ vì chưa chọn
                    giỏ. Chọn giỏ ở các thẻ màu vàng bên dưới để app bắt đầu
                    đăng.
                </Callout>
                <Callout v-else-if="rows.length" tone="success">
                    Mọi video đang chờ đều đã có giỏ ({{ readyRows.length }} sản
                    phẩm sẵn sàng<template v-if="problemRows.length"
                        >, {{ problemRows.length }} đang gặp vấn đề</template
                    >).
                </Callout>

                <!-- Lưới thẻ sản phẩm hub -->
                <section
                    class="flex flex-col gap-3"
                    data-testid="fork-gio-hang-rows"
                >
                    <div class="flex justify-end">
                        <Button
                            size="sm"
                            variant="outline"
                            data-testid="fork-personalise-default"
                            @click="openDefault"
                        >
                            <IconHash class="size-4" />
                            Hashtag mặc định chung{{
                                personalise_default?.tags.length
                                    ? ` (${personalise_default.tags.length})`
                                    : ''
                            }}
                        </Button>
                    </div>
                    <SectionHeading
                        title="Video nào gắn sản phẩm nào"
                        description="Mỗi thẻ là một sản phẩm của hub theo từng quy cách. Phải chọn đúng một sản phẩm shop cho mỗi thẻ."
                    />

                    <div
                        v-if="loading"
                        class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
                    >
                        <Skeleton
                            v-for="i in 6"
                            :key="i"
                            class="h-56 rounded-xl"
                        />
                    </div>
                    <div
                        v-else
                        class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
                    >
                        <HubProductCard
                            v-for="r in sortedRows"
                            :key="r.key"
                            :row="r"
                            :card="cardOf(r)"
                            :name="nameOf(r)"
                            :name-max="name_max"
                            :dirty="isDirty(r)"
                            :has-draft="!!draft[r.key]"
                            :busy="busy === `row-${r.key}`"
                            :persona="personaOf(r.code)"
                            @personalise="openProduct(r.code, r.hub_name)"
                            @pick="picking = r.key"
                            @update:name="(v: string) => editName(r, v)"
                            @save="saveRow(r)"
                            @clear="clearRow(r)"
                        />
                    </div>

                    <EmptyState
                        v-if="!rows.length"
                        title="Hub chưa có sản phẩm nào đang bật"
                        description="Khi Xưởng Video gửi sản phẩm sang, thẻ chọn giỏ sẽ hiện ở đây. Bạn có thể quét kho ở trang Kho video."
                    >
                        <Button as-child size="sm" variant="outline">
                            <a href="/auto/kho">Đến Kho video →</a>
                        </Button>
                    </EmptyState>
                </section>
            </template>
        </div>

        <PersonaliseDialog
            v-bind="dialogProps"
            @update:open="closePersonalise"
        />

        <ShopPickerDialog
            :open="picking !== null"
            :row-label="pickingRow?.label ?? ''"
            :products="products"
            :current-id="pickingRow ? pickedId(pickingRow) : ''"
            :busy-id="
                busy?.startsWith('hide-') ? busy.slice('hide-'.length) : null
            "
            @update:open="(v: boolean) => !v && (picking = null)"
            @select="pickFor"
            @toggle-hidden="setHidden"
        />
    </AutoShell>
</template>

// Trạng thái hộp thoại "Cá nhân hoá" (PersonaliseDialog), dùng chung cho trang Giỏ hàng và trang Ảnh bìa & hashtag.
// Mở cho một sản phẩm hub (ảnh bìa + hashtag riêng) hoặc cho hashtag mặc định chung.
import { computed, ref } from 'vue';

import type { Persona, PersonaDefault } from '@/components/fork/gio-hang/types';

export const emptyPersona: Persona = {
    cover_mode: 'default',
    cover_fixed: null,
    covers: [],
    hashtags: [],
    hashtag_mode: 'append',
    hashtag_pick: 0,
};

export function usePersonalise(
    source: () => {
        personalise?: Record<string, Persona>;
        personalise_default?: PersonaDefault;
    },
) {
    const personaOf = (code: string): Persona =>
        source().personalise?.[code] ?? emptyPersona;

    const personalising = ref<{ code: string; label: string } | null>(null);
    const editingDefault = ref(false);

    const dialogState = computed<Persona>(() => {
        if (editingDefault.value) {
            const d = source().personalise_default;

            return {
                ...emptyPersona,
                hashtags: d?.tags ?? [],
                hashtag_mode: d?.mode ?? 'append',
                hashtag_pick: d?.pick ?? 0,
            };
        }

        return personalising.value
            ? personaOf(personalising.value.code)
            : emptyPersona;
    });

    const dialogOpen = computed(
        () => editingDefault.value || personalising.value !== null,
    );

    const openProduct = (code: string, label: string) => {
        editingDefault.value = false;
        personalising.value = { code, label };
    };

    const openDefault = () => {
        personalising.value = null;
        editingDefault.value = true;
    };

    const closePersonalise = (v: boolean) => {
        if (!v) {
            editingDefault.value = false;
            personalising.value = null;
        }
    };

    /** Props truyền thẳng vào <PersonaliseDialog v-bind="dialogProps" />. */
    const dialogProps = computed(() => ({
        open: dialogOpen.value,
        scope: (editingDefault.value ? 'default' : 'product') as
            | 'default'
            | 'product',
        code: personalising.value?.code ?? '',
        label: personalising.value?.label ?? '',
        state: dialogState.value,
    }));

    return {
        personaOf,
        personalising,
        editingDefault,
        dialogState,
        dialogOpen,
        dialogProps,
        openProduct,
        openDefault,
        closePersonalise,
    };
}

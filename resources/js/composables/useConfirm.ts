// Hộp xác nhận dùng chung, thay cho window.confirm. Gọi `confirm({...})` trả về Promise<boolean>;
// <ConfirmHost /> (gắn một lần trong AppLayout) vẽ hộp thoại.
import { reactive, readonly } from 'vue';

export type ConfirmOptions = {
    title: string;
    description?: string;
    confirmText?: string;
    cancelText?: string;
    destructive?: boolean;
};

type ConfirmState = ConfirmOptions & {
    open: boolean;
    resolve: ((ok: boolean) => void) | null;
};

const state = reactive<ConfirmState>({
    open: false,
    title: '',
    resolve: null,
});

function settle(ok: boolean): void {
    const resolve = state.resolve;
    state.resolve = null;
    state.open = false;
    resolve?.(ok);
}

export function confirm(options: ConfirmOptions): Promise<boolean> {
    // Đang có hộp mở thì coi như hộp cũ bị huỷ.
    settle(false);

    return new Promise<boolean>((resolve) => {
        state.title = options.title;
        state.description = options.description;
        state.confirmText = options.confirmText;
        state.cancelText = options.cancelText;
        state.destructive = options.destructive ?? false;
        state.resolve = resolve;
        state.open = true;
    });
}

export function useConfirm() {
    return { confirm };
}

export function useConfirmState() {
    return { state: readonly(state), settle };
}

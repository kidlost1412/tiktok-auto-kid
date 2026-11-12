// Trạng thái "đang tải" cho các lần lọc / chuyển trang: chỉ bật sau một nhịp ngắn để tránh nhấp nháy khi tải nhanh.
import { onBeforeUnmount, ref } from 'vue';

export function useVisitLoading(delay = 150) {
    const loading = ref(false);
    let timer: ReturnType<typeof setTimeout> | undefined;

    const callbacks = {
        onStart: () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                loading.value = true;
            }, delay);
        },
        onFinish: () => {
            clearTimeout(timer);
            loading.value = false;
        },
    };

    onBeforeUnmount(() => clearTimeout(timer));

    return { loading, callbacks };
}

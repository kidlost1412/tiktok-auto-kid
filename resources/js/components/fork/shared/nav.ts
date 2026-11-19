// Đi tới một địa chỉ trong app từ thanh trên cùng (Tìm nhanh, chuông). Địa chỉ chỉ khác phần #mục của trang đang mở
// (vd. đang ở Cài đặt, bấm "Telegram") thì đổi # tại chỗ thay vì tải lại trang: Cài đặt tự đổi mục theo #.
import { router } from '@inertiajs/vue3';

export function goTo(href: string): void {
    const url = new URL(href, window.location.origin);

    if (
        url.pathname === window.location.pathname &&
        url.search === window.location.search &&
        url.hash !== ''
    ) {
        window.location.hash = url.hash;

        return;
    }

    router.visit(href);
}

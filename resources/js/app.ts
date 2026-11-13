import { createInertiaApp, router } from '@inertiajs/vue3';
import { resolvePageComponent } from 'laravel-vite-plugin/inertia-helpers';
import type { DefineComponent } from 'vue';
import { createApp, h } from 'vue';

const appName = import.meta.env.VITE_APP_NAME || 'TikTok Auto Kid';

createInertiaApp({
    title: (title) => (title ? `${title} - ${appName}` : appName),
    resolve: (name) =>
        resolvePageComponent(
            `./pages/${name}.vue`,
            import.meta.glob<DefineComponent>('./pages/**/*.vue'),
        ),
    setup({ el, App, props, plugin }) {
        createApp({ render: () => h(App, props) })
            .use(plugin)
            .mount(el);

        // Chuyển trang mượt: chỉ khi ĐỔI TRANG thật (GET sang đường dẫn khác) mà máy chủ trả chậm hơn ~120ms
        // thì #app mờ nhẹ cho biết đang tải. Không mờ khi: tự làm mới số liệu (reload `only`), tải trước
        // (prefetch), gửi form (POST/PUT/PATCH/DELETE) hay đổi bộ lọc trên cùng trang — để trang không
        // "nháy" mỗi 30 giây. Chỉ đổi opacity (không transform: transform trên #app làm hỏng position:fixed).
        let showAt: number | undefined;
        let hideAt: number | undefined;
        router.on('start', (event) => {
            const v = event.detail.visit;
            const samePage = v.url.pathname === window.location.pathname;
            if (v.method !== 'get' || v.only.length > 0 || v.prefetch || v.async || samePage) {
                return;
            }
            window.clearTimeout(hideAt);
            window.clearTimeout(showAt);
            showAt = window.setTimeout(() => el.classList.add('nav-fade'), 120);
        });
        router.on('finish', () => {
            window.clearTimeout(showAt);
            // một nhịp để DOM mới kịp vào trước khi rõ lại
            hideAt = window.setTimeout(() => el.classList.remove('nav-fade'), 20);
        });
    },
    progress: {
        color: '#4B5563',
    },
});

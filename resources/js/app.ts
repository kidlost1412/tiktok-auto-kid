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

        // Chuyển trang mượt: mọi lượt điều hướng Inertia (đổi trang hoặc đổi tab trong trang,
        // vì các tab đều đi qua Inertia) được bọc trong một cú mờ-đi/rõ-lại ngắn trên #app,
        // tránh cảm giác giật/nhoáng khi nội dung đổi. Các vòng quét nền (health check, số liệu…)
        // trong app đều dùng fetch() thẳng, không qua router, nên không bị ảnh hưởng.
        let hideAt: number | undefined;
        router.on('start', () => {
            window.clearTimeout(hideAt);
            el.classList.add('nav-fade');
        });
        router.on('finish', () => {
            // một nhịp để DOM mới kịp vào trước khi mờ dần hiện lại
            hideAt = window.setTimeout(() => el.classList.remove('nav-fade'), 20);
        });
    },
    progress: {
        color: '#4B5563',
    },
});

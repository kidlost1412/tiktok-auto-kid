import tailwindcss from '@tailwindcss/vite';
import vue from '@vitejs/plugin-vue';
import laravel from 'laravel-vite-plugin';
import { defineConfig } from 'vite';

export default defineConfig({
    // Trình duyệt trên Windows chặn http://0.0.0.0:5173; đặt VITE_HMR_HOST=localhost để dùng địa chỉ khác.
    server: process.env.VITE_HMR_HOST ? { hmr: { host: process.env.VITE_HMR_HOST } } : undefined,
    plugins: [
        laravel({
            input: ['resources/js/app.ts', 'resources/css/app.css'],
            refresh: true,
        }),
        tailwindcss(),
        vue({
            template: {
                transformAssetUrls: {
                    base: null,
                    includeAbsolute: false,
                },
            },
        }),
    ],
});

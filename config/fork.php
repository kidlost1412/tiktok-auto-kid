<?php

declare(strict_types=1);

// Cấu hình của app tự động đăng TikTok.
return [
    // Chế độ một người dùng (app/Fork/SingleUser): không có đăng nhập, tự vào app với chủ duy nhất,
    // chỉ nhận request từ loopback. Mặc định tắt để code dùng chung an toàn; bản chạy trên máy bật bằng .env.
    'single_user' => (bool) env('APP_SINGLE_USER', false),

    // Đăng TikTok qua tiện ích Chrome (TikTok Auto Kid).
    'chrome' => [
        // Rỗng thì tự suy ra từ "key" trong extension/autotok/manifest.json (ID tiện ích cố định theo key,
        // không phụ thuộc thư mục cài), nên bản native không cần đặt FORK_CHROME_EXTENSION_ID.
        'extension_id' => $chromeExtensionId = (string) (env('FORK_CHROME_EXTENSION_ID') ?: (static function (): string {
            $file = dirname(__DIR__).'/extension/autotok/manifest.json';
            $key = is_file($file) ? (json_decode((string) file_get_contents($file), true)['key'] ?? null) : null;
            $der = is_string($key) ? base64_decode($key, true) : false;

            return $der === false ? '' : strtr(substr(hash('sha256', $der), 0, 32), '0123456789abcdef', 'abcdefghijklmnop');
        })()),
        // chrome-extension://<id>, rỗng khi chưa biết id (khi đó không origin nào được CORS).
        'extension_origin' => $chromeExtensionId !== '' ? 'chrome-extension://'.$chromeExtensionId : '',
        'launcher_secret' => env('FORK_CHROME_LAUNCHER_SECRET', ''),
        // Số giây tối đa một lần long-poll /api/ext/next.
        'next_max_wait' => 10,
        // Job đăng ngay chờ Chrome nhận tối đa bao nhiêu phút.
        'now_claim_within_minutes' => (int) env('FORK_CHROME_NOW_CLAIM_WITHIN_MINUTES', 120),
        // Ảnh bìa riêng của sản phẩm: false = không gửi cho tiện ích (công tắc an toàn).
        'cover_enabled' => (bool) env('FORK_CHROME_COVER_ENABLED', true),
    ],

    // Tự động đăng từ hub sản xuất.
    'auto' => [
        'hub_path' => env('FORK_HUB_PATH', str_replace(chr(92), '/', base_path('du-lieu/xuong-video'))),
        // true = PHP chỉ kiểm quyền rồi 302 tới /media/..., Caddy (scripts/native/Caddyfile) tự phát file mp4/ảnh bìa (hỗ trợ Range)
        // để video không giữ worker php-cgi. Chỉ bật khi chạy sau Caddy đó.
        'accel' => (bool) env('FORK_ACCEL', false),
        // Chế độ API (chính): hỏi hub "Xưởng Video" qua HTTP. Bật khi có key; không có key thì dùng thư mục (dự phòng).
        'hub_api' => [
            'url' => env('FORK_HUB_URL', 'http://127.0.0.1:8766'),
            'key' => env('FORK_HUB_KEY', ''),
            // Mã của máy này khi nhiều máy dùng chung một hub: hub dùng nó để biết ai đang giữ video nào.
            'may' => env('FORK_HUB_MAY', 'ban-chinh'),
            // true = hub phải giữ chỗ được mới đăng (bắt buộc cho máy phụ dùng chung hub).
            'require_claim' => (bool) env('FORK_HUB_REQUIRE_CLAIM', false),
        ],
        // Tối đa bao nhiêu bài đã xếp trong tương lai (chưa đăng) mỗi kênh, chặn tải quá nhiều bài hẹn giờ lên TikTok.
        'max_future_posts' => (int) env('FORK_AUTO_MAX_FUTURE_POSTS', 100),
        // Số ngày xếp trước mặc định (cột schedule_ahead_days). TikTok chỉ cho hẹn tối đa 10 ngày.
        'default_schedule_ahead_days' => 3,
        'min_gap_minutes' => 20,
        'jitter_minutes' => 7,
        // Bỏ qua file vừa được ghi trong vòng ngần này giây (hub có thể đang ghi dở).
        'settle_seconds' => 20,
        // Kho riêng: file mới được nhận ngay khi đã ghi xong (kích thước đứng yên giữa hai lần đo cách nhau ngần này mili giây
        // và đọc được thời lượng), không phải chờ settle_seconds.
        'rieng_gap_ms' => 1500,
        // Kho chuẩn mới: hub bỏ video sẵn sàng đăng vào <hub>/kho-dang/. Xem KHO-CHUAN.md.
        'kho_dir' => 'kho-dang',
        'done_dir' => 'da-dang',
        // Vẫn nhặt video kiểu cũ ra/<ngày>/ + bang-ghi.csv.
        'legacy_ra' => (bool) env('FORK_AUTO_LEGACY_RA', true),
        // Lưu giữ file đã đăng: xoa_ngay, 7, 30, vinh_vien.
        'retention_default' => '30',
        // File mp4 không có json đi kèm quá ngần này phút thì chuyển vào _loi.
        'json_wait_minutes' => 120,
    ],

    // Cảnh báo qua Telegram (app/Fork/Notify). Để trống token hoặc chat id thì tắt.
    'telegram' => [
        'bot_token' => env('FORK_TELEGRAM_BOT_TOKEN', ''),
        'chat_id' => env('FORK_TELEGRAM_CHAT_ID', ''),
        'timezone' => env('FORK_TELEGRAM_TIMEZONE', 'Asia/Ho_Chi_Minh'),
        // Giờ (theo timezone trên) gửi tổng kết ngày.
        'summary_hour' => 21,
        // Giãn cách tối thiểu giữa hai tin (Telegram cho khoảng 1 tin/giây mỗi chat) và độ lùi khi gửi lỗi tạm thời (ms).
        'min_interval_ms' => 1100,
        'backoff_ms' => [1000, 3000],
    ],

    // Xưởng Video (hub sản xuất): nhúng ở /xuong. Iframe trỏ thẳng cổng hub (không qua proxy) vì giao diện hub dùng đường dẫn /api tuyệt đối.
    'xuong' => [
        'url' => env('XUONG_URL', 'http://127.0.0.1:8765'),
        'health_url' => env('XUONG_HEALTH_URL', 'http://127.0.0.1:8765/health'),
        // Launcher: POST /api/restart?service=... với token trong runtime/control.token (launcher tạo mỗi lần chạy).
        'service' => 'xuong-video',
        'control_port' => (int) env('XUONG_CONTROL_PORT', 8009),
        'control_token_file' => base_path('runtime/control.token'),
    ],
];

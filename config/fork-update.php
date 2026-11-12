<?php

declare(strict_types=1);

return [
    // Kho GitHub công khai chứa bản phát hành (owner/repo). Mặc định: kho chính thức.
    'repo' => env('UPDATE_REPO', 'kidlost1412/tiktok-auto-kid'),
    // Launcher (TikTokAuto.exe) lắng nghe ở cổng này (cùng cổng trang trạng thái).
    'launcher_port' => (int) env('XUONG_CONTROL_PORT', 8009),
    'token_file' => base_path('runtime/control.token'),
    'version_file' => base_path('VERSION'),
];

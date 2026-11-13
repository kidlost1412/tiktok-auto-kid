<?php

declare(strict_types=1);

namespace App\Fork\Settings;

use Illuminate\Support\ServiceProvider;

/** Trang "Cài đặt" hợp nhất (Kết nối Chrome + Telegram + Cập nhật). */
final class SettingsServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        $this->loadRoutesFrom(base_path('routes/fork-settings.php'));
    }
}

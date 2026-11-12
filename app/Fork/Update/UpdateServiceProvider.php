<?php

declare(strict_types=1);

namespace App\Fork\Update;

use Illuminate\Support\ServiceProvider;

/** Trang Cài đặt → Cập nhật: nói chuyện với launcher (nơi thật sự tải, cài và quay lại bản cũ). */
final class UpdateServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        $this->loadRoutesFrom(base_path('routes/fork-update.php'));

        if ($this->app->runningInConsole()) {
            $this->commands([UpdateNotifyCommand::class]);
        }
    }
}

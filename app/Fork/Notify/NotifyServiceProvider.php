<?php

declare(strict_types=1);

namespace App\Fork\Notify;

use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Support\ServiceProvider;

/** Cảnh báo qua Telegram: lệnh `fork:alerts` chạy mỗi 5 phút. */
final class NotifyServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        $this->loadRoutesFrom(base_path('routes/fork-notify.php'));

        if ($this->app->runningInConsole()) {
            $this->commands([AlertsCommand::class]);
        }

        $this->callAfterResolving(Schedule::class, function (Schedule $schedule): void {
            $schedule->command(AlertsCommand::class)->everyFiveMinutes()->withoutOverlapping(10)->onOneServer();
        });
    }
}

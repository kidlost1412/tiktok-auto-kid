<?php

declare(strict_types=1);

namespace App\Fork\AutoPost;

use App\Fork\AutoPost\Console\AutoCleanupCommand;
use App\Fork\AutoPost\Console\AutoIngestCommand;
use App\Fork\AutoPost\Console\AutoPlanCommand;
use App\Fork\AutoPost\Console\AutoStatsCommand;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Support\ServiceProvider;

/** Tự động đăng từ hub sản xuất: lệnh, lịch chạy, route, theo dõi kết quả bài. */
final class AutoPostServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(VideoLibrary::class);
        $this->app->singleton(CaptionService::class);
    }

    public function boot(): void
    {
        $this->loadMigrationsFrom(__DIR__.'/../../../database/migrations/fork');

        // Bài đổi trạng thái thì video trong kho cập nhật ngay (fork:auto-plan vẫn đối soát mỗi 5 phút).
        Scheduling\ResultWatcher::register();

        $this->loadRoutesFrom(base_path('routes/fork-auto.php'));
        $this->loadRoutesFrom(base_path('routes/fork-xuong.php'));

        if ($this->app->runningInConsole()) {
            $this->commands([
                AutoIngestCommand::class,
                AutoPlanCommand::class,
                AutoStatsCommand::class,
                AutoCleanupCommand::class,
            ]);
        }

        $this->callAfterResolving(Schedule::class, function (Schedule $schedule): void {
            $schedule->command(AutoIngestCommand::class)->everyFiveMinutes()->withoutOverlapping(10)->onOneServer();
            $schedule->command(AutoPlanCommand::class)->everyFiveMinutes()->withoutOverlapping(10)->onOneServer();
            $schedule->command(AutoStatsCommand::class)->hourly()->withoutOverlapping(10)->onOneServer();
            // Mỗi ngày: xoá mp4/json quá hạn lưu giữ trong da-dang.
            $schedule->command(AutoCleanupCommand::class)->dailyAt('03:30')->withoutOverlapping(10)->onOneServer();
        });
    }
}

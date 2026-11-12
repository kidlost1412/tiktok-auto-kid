<?php

declare(strict_types=1);

namespace App\Fork\Chrome;

use App\Fork\Chrome\Console\ChromeDispatchCommand;
use App\Fork\Chrome\Console\ChromeReconcileCommand;
use App\Fork\Chrome\Http\Extension\ExtensionCors;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Contracts\Http\Kernel;
use Illuminate\Support\ServiceProvider;

/**
 * Đăng TikTok qua tiện ích Chrome (TikTok Auto Kid): route, lệnh, lịch chạy, CORS của tiện ích.
 * Kế hoạch và hợp đồng giữa các phần: app/Fork/Chrome/KE-HOACH.md.
 */
final class ChromeServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        $this->loadMigrationsFrom(__DIR__.'/../../../database/migrations/fork');

        // CORS của /api/ext/* chỉ cho origin của tiện ích. Lớp này tự bỏ qua mọi đường dẫn khác.
        $this->app->make(Kernel::class)->prependMiddleware(ExtensionCors::class);

        // Bài bị sửa/xoá thì thu hồi job Chrome chưa đăng.
        ChromePostWatcher::register();

        foreach (['fork-chrome-ext.php', 'fork-chrome-app.php', 'fork-chrome-launcher.php'] as $file) {
            $this->loadRoutesFrom(base_path('routes/'.$file));
        }

        if ($this->app->runningInConsole()) {
            $this->commands([ChromeDispatchCommand::class, ChromeReconcileCommand::class]);
        }

        $this->callAfterResolving(Schedule::class, function (Schedule $schedule): void {
            $schedule->command(ChromeDispatchCommand::class)->everyMinute()->withoutOverlapping(5)->onOneServer();
            $schedule->command(ChromeReconcileCommand::class)->everyMinute()->withoutOverlapping(5)->onOneServer();
        });
    }
}

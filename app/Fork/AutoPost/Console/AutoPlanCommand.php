<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Console;

use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\AutoPost\Scheduling\ResultWatcher;
use Illuminate\Console\Command;

class AutoPlanCommand extends Command
{
    protected $signature = 'fork:auto-plan';

    protected $description = 'Đối soát kết quả bài tự động, rồi xếp lịch và tạo bài TikTok mới cho các tài khoản bật tự động đăng';

    public function handle(ResultWatcher $watcher, Planner $planner): int
    {
        $synced = $watcher->sync();
        $this->info("Kết quả: {$synced['posted']} đã đăng, {$synced['failed']} lỗi.");

        foreach ($planner->planAll() as $accountId => $row) {
            $this->line("{$accountId}: tạo {$row['created']}, lỗi {$row['failed']}".($row['skipped'] ? " ({$row['skipped']})" : ''));
        }

        return self::SUCCESS;
    }
}

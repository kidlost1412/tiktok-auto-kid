<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Console;

use App\Fork\AutoPost\Stats\StatsCollector;
use Illuminate\Console\Command;

final class AutoStatsCommand extends Command
{
    protected $signature = 'fork:auto-stats';

    protected $description = 'Thu số liệu video đã đăng tự động và ghi ngược về hub';

    public function handle(StatsCollector $collector): int
    {
        $r = $collector->collect();

        $this->info(sprintf(
            'Đã kiểm tra %d video, cập nhật %d; ghi %d file so-lieu.csv, điền %d ô luot_xem.',
            $r['checked'],
            $r['updated'],
            $r['hub']['sheets'],
            $r['hub']['filled'],
        ));

        return self::SUCCESS;
    }
}

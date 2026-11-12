<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Console;

use App\Fork\Chrome\ChromeJobs;
use Illuminate\Console\Command;

class ChromeReconcileCommand extends Command
{
    protected $signature = 'fork:chrome-reconcile';

    protected $description = 'Xử lý hạn chót của các job đăng TikTok qua Chrome (quá hạn nhận, mất tín hiệu, không rõ kết quả)';

    public function handle(ChromeJobs $chrome): int
    {
        $chrome->reconcile();

        return self::SUCCESS;
    }
}

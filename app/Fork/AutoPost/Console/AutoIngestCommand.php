<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Console;

use App\Fork\AutoPost\Hub\HubApi;
use App\Fork\AutoPost\Hub\HubReporter;
use App\Fork\AutoPost\VideoLibrary;
use Illuminate\Console\Command;

final class AutoIngestCommand extends Command
{
    protected $signature = 'fork:auto-ingest';

    protected $description = 'Nhặt video mới từ hub sản xuất vào kho tự động đăng';

    public function handle(VideoLibrary $library): int
    {
        if (HubApi::enabled()) {
            // Gửi lại các lời báo da-dang/loi/so-lieu còn kẹt (hub tắt lần trước).
            $out = app(HubReporter::class)->flush();
            $this->line("Báo hub: gửi {$out['sent']}, bỏ {$out['dropped']}, còn chờ {$out['pending']}.");
        }

        $products = $library->syncProducts();
        $result = $library->ingest();

        $this->info("Sản phẩm: {$products}. Video mới: {$result['new']}, bỏ qua: {$result['skipped']}, đã biết: {$result['known']}.");
        if (HubApi::enabled()) {
            $r = $library->apiReport;
            $this->line("API hub: {$r['state']}, lỗi {$r['error']}, thiếu file {$r['missing']}, bỏ duyệt {$r['unapproved']}, máy khác giữ {$r['held']}.");
            $b = $r['backfill'] ?? ['claimed' => 0, 'conflicts' => 0, 'pending' => 0];
            $this->line("Giữ chỗ bù: xong {$b['claimed']}, xung đột {$b['conflicts']}, chờ {$b['pending']}.");

            return self::SUCCESS;
        }

        $this->line("Caption hub: cập nhật {$library->hubReport['updated']}, còn thiếu {$library->hubReport['waiting']}.");
        $this->line("Kho-dang: chờ {$library->khoReport['waiting']}, lỗi {$library->khoReport['error']}.");

        return self::SUCCESS;
    }
}

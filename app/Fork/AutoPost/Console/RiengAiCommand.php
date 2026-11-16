<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Console;

use App\Fork\AutoPost\Rieng\Ai\ChatGptAccounts;
use App\Fork\AutoPost\Rieng\Ai\RiengAnalyzer;
use App\Fork\AutoPost\Rieng\Ai\RiengAutoSettings;
use App\Fork\AutoPost\Rieng\RiengScanner;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Cache;
use Throwable;

/** Cho AI (ChatGPT) xem các video Kho riêng mới: đoán sản phẩm + viết caption. Chạy khi đã bật "Kho riêng tự đăng theo khung". */
class RiengAiCommand extends Command
{
    protected $signature = 'fork:rieng-ai {--limit=4 : số video tối đa mỗi lượt} {--force : chạy cả khi chưa bật tự đăng}';

    protected $description = 'AI xem video Kho riêng mới: đoán sản phẩm và viết caption';

    public function handle(RiengAnalyzer $analyzer, ChatGptAccounts $accounts): int
    {
        if (! RiengAutoSettings::get()['enabled'] && ! $this->option('force')) {
            $this->line('Chưa bật Kho riêng tự đăng theo khung.');

            return self::SUCCESS;
        }

        // Video mới bỏ vào thư mục mà chưa mở trang Kho riêng: quét ở nền để AI xem được ngay.
        try {
            if (app(RiengScanner::class)->scan()['busy'] === 0) {
                Cache::forever('fork-rieng:last-scan', now()->toIso8601String());
            }
        } catch (Throwable $e) {
            report($e);
        }

        // App vừa lên bản mới (có thể đã sửa đúng lỗi làm AI hỏng): cho video lỗi thử lại ngay, không đợi giờ hẹn.
        $version = trim((string) @file_get_contents((string) config('fork-update.version_file', base_path('VERSION'))));

        if ($version !== '' && Cache::get('fork-rieng:ai-version') !== $version) {
            Cache::forever('fork-rieng:ai-version', $version);
            $analyzer->retryNow();
        }

        foreach ($analyzer->pending(max(1, (int) $this->option('limit'))) as $video) {
            if ($accounts->pick() === null) {
                $this->line('Chưa có tài khoản ChatGPT nào sẵn sàng.');

                break;
            }

            $ai = $analyzer->analyze($video);
            $this->line("#{$video->id} {$video->file_name}: {$ai['state']} ".($ai['product_code'] ?? '-').' '.($ai['error'] ?? ($ai['caption'] ?? '')));
        }

        return self::SUCCESS;
    }
}

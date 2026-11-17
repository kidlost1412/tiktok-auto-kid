<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Console;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Rieng\Ai\ChatGptAccounts;
use App\Fork\AutoPost\Rieng\Ai\RiengAiStatus;
use App\Fork\AutoPost\Rieng\Ai\RiengAnalyzer;
use App\Fork\AutoPost\Rieng\RiengScanner;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Cache;
use Symfony\Component\Process\Process;
use Throwable;

/** Cho AI (ChatGPT) xem các video Kho riêng mới: đoán sản phẩm + viết caption. Chạy khi đã có tài khoản ChatGPT, kể cả chưa bật tự đăng (để anh xem trước AI nhận gì). */
class RiengAiCommand extends Command
{
    protected $signature = 'fork:rieng-ai
        {--limit=4 : số video tối đa mỗi lượt}
        {--video= : chỉ xem một video (nút "AI xem lại")}
        {--minutes=20 : dừng nhận video mới sau ngần này phút}
        {--force : (giữ cho tương thích, AI không còn chờ bật tự đăng)}';

    protected $description = 'AI xem video Kho riêng mới: đoán sản phẩm và viết caption';

    /** Chạy lệnh này ở nền ngay (không đợi lịch 2 phút), vd. khi chủ app bấm "AI xem lại". */
    public static function launch(?int $videoId = null): void
    {
        // Không bao giờ tự sinh tiến trình con khi chạy test (từng làm treo máy).
        if (app()->runningUnitTests()) {
            return;
        }

        $php = dirname(PHP_BINARY).DIRECTORY_SEPARATOR.(PHP_OS_FAMILY === 'Windows' ? 'php.exe' : 'php');
        $php = is_file($php) ? $php : PHP_BINARY;
        $args = ['fork:rieng-ai', '--force'];

        if ($videoId !== null) {
            $args[] = '--video='.$videoId;
        }

        if (PHP_OS_FAMILY === 'Windows') {
            // start /b: tách khỏi request web (nếu chỉ start() thì hết request là bị tắt theo).
            // Viết nguyên dòng lệnh: truyền mảng thì Symfony nhân đôi dấu " bên trong và Windows không chạy được (lỗi cũ: nút không làm gì).
            $cmd = 'start "" /b "'.$php.'" "'.base_path('artisan').'" '.implode(' ', $args).' > nul 2>&1';
            Process::fromShellCommandline($cmd, base_path())->setTimeout(15)->run();

            return;
        }

        (new Process(['sh', '-c', 'nohup '.escapeshellarg($php).' '.escapeshellarg(base_path('artisan')).' '.implode(' ', $args).' > /dev/null 2>&1 &'], base_path()))->setTimeout(15)->run();
    }

    public function handle(RiengAnalyzer $analyzer, ChatGptAccounts $accounts): int
    {
        if (filled($this->option('video'))) {
            $video = AutoVideo::query()->find((int) $this->option('video'));

            if ($video !== null && $video->isRieng() && $video->status === AutoVideo::NEW) {
                $ai = $analyzer->analyze($video);
                $this->line("#{$video->id}: ".($ai['state'] ?? '-').' '.($ai['product_code'] ?? '-'));
            }

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

        $until = microtime(true) + 60 * max(1, (int) $this->option('minutes'));
        $done = 0;
        $failed = 0;
        $note = null;
        RiengAiStatus::beat(['dang' => true]);

        foreach ($analyzer->pending(max(1, (int) $this->option('limit'))) as $video) {
            if (microtime(true) > $until) {
                break;
            }

            if ($accounts->pick() === null) {
                $note = 'chưa có tài khoản ChatGPT nào sẵn sàng';
                $this->line('Chưa có tài khoản ChatGPT nào sẵn sàng.');

                break;
            }

            RiengAiStatus::beat(['dang' => true, 'video' => $video->id]);
            $ai = $analyzer->analyze($video, null, (int) max(120, $until - microtime(true)));
            in_array($ai['state'] ?? null, ['ok', 'unsure'], true) ? $done++ : $failed++;
            $this->line("#{$video->id} {$video->file_name}: {$ai['state']} ".($ai['product_code'] ?? '-').' '.($ai['error'] ?? ($ai['caption'] ?? '')));
        }

        $note ??= $done + $failed === 0 ? 'không có video mới' : trim(($done ? "xem xong {$done} video" : '').($failed ? ($done ? ', ' : '')."{$failed} video chưa xem được" : ''));
        RiengAiStatus::beat(['dang' => false, 'note' => $note]);

        return self::SUCCESS;
    }
}

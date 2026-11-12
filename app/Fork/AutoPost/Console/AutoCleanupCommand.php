<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Console;

use App\Fork\AutoPost\Hub\HubApi;
use App\Fork\AutoPost\Hub\HubFiles;
use App\Fork\AutoPost\VideoLibrary;
use Illuminate\Console\Command;

final class AutoCleanupCommand extends Command
{
    protected $signature = 'fork:auto-cleanup';

    protected $description = 'Xoá mp4/json cũ trong da-dang theo cài đặt lưu giữ (giữ lại .ket-qua.json); chế độ API: xoá cache file tải từ hub';

    public function handle(VideoLibrary $library): int
    {
        if (HubApi::enabled()) {
            // Hub tự dọn file của nó; TikTok Auto Kid chỉ dọn bản cache do chính nó tải về (video đã đăng/lỗi quá hạn lưu giữ).
            $retention = $library->kho()->retention();
            $deleted = app(HubFiles::class)->cleanup($retention);

            $media = app(HubFiles::class)->cleanupPostedMedia($retention);

            $this->info("Chế độ API: hub tự dọn file của nó. Lưu giữ: {$retention}. Đã xoá {$deleted} file cache hub, {$media} file video của bài đã đăng.");

            return self::SUCCESS;
        }

        $result = $library->kho()->cleanup();

        $this->info("Lưu giữ: {$result['retention']}. Đã xoá {$result['deleted']} file.");

        return self::SUCCESS;
    }
}

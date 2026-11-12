<?php

declare(strict_types=1);

namespace App\Fork\Update;

use App\Fork\Notify\Messages;
use App\Fork\Notify\Telegram;
use Illuminate\Console\Command;

/** Launcher gọi lệnh này khi phát hiện bản mới: gửi một tin Telegram (nếu đã cấu hình), mỗi phiên bản một lần. */
final class UpdateNotifyCommand extends Command
{
    protected $signature = 'fork:update-notify {version}';

    protected $description = 'Báo qua Telegram rằng có bản TikTok Auto Kid mới';

    public function handle(): int
    {
        $v = (string) $this->argument('version');

        if (preg_match('/^v?\d+(\.\d+){0,2}([-+][0-9A-Za-z.]+)?$/', $v) !== 1) {
            return self::INVALID;
        }

        $text = '🆕 <b>Có bản TikTok Auto Kid mới: '.Messages::e($v).'</b>'."\n"
            .'Bạn đang dùng '.Messages::e(LauncherClient::currentVersion()).'. Vào Cài đặt → Cập nhật để cập nhật: '.Messages::e(Messages::appUrl('/settings/cap-nhat'));

        Telegram::send($text, 'update:'.$v, 7 * 86400);

        return self::SUCCESS;
    }
}

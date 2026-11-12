<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Notify\Telegram;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * Bài đã được tải lên TikTok hẹn giờ thì tắt kênh hay bỏ video cũng KHÔNG gỡ được lịch bên TikTok.
 * Lớp này đếm các bài như vậy và báo cho chủ app (log + Telegram) thay vì im lặng giả vờ đã huỷ.
 */
final class FutureUploads
{
    /**
     * Số video của kênh đã xếp giờ trong tương lai: đã nằm trên TikTok (job Chrome hẹn giờ đã posted) và còn chờ tải lên.
     *
     * @return array{uploaded: int, waiting: int}
     */
    public static function summarize(string $accountId): array
    {
        $videos = AutoVideo::query()
            ->where('social_account_id', $accountId)
            ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED])
            ->where('scheduled_for', '>', now())
            ->whereNotNull('post_id')
            ->get(['id', 'post_id']);

        if ($videos->isEmpty()) {
            return ['uploaded' => 0, 'waiting' => 0];
        }

        $uploaded = ChromeJob::query()
            ->whereIn('post_id', $videos->pluck('post_id'))
            ->where('mode', 'scheduled')
            ->where('state', 'posted')
            ->distinct()
            ->count('post_id');

        return ['uploaded' => $uploaded, 'waiting' => max(0, $videos->count() - $uploaded)];
    }

    /**
     * Ghi log và gửi Telegram (nếu có cấu hình) khi kênh còn bài đã hẹn trên TikTok.
     */
    public static function warn(string $accountId, string $why): bool
    {
        try {
            $count = self::summarize($accountId);

            if ($count['uploaded'] === 0 && $count['waiting'] === 0) {
                return false;
            }

            $text = "Tự động đăng: {$why}, nhưng còn {$count['uploaded']} bài đã hẹn giờ trên TikTok (không gỡ được từ đây — muốn huỷ phải xoá trong TikTok Studio)"
                .($count['waiting'] > 0 ? " và {$count['waiting']} bài chưa tải lên vẫn sẽ được đăng theo lịch." : '.');

            Log::warning($text, ['social_account_id' => $accountId] + $count);
            Telegram::send($text, 'future-uploads:'.$accountId.':'.$why, 600);

            return true;
        } catch (Throwable $e) {
            report($e);

            return false;
        }
    }
}

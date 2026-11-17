<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\DirectWindow;
use Illuminate\Support\Collection;

/**
 * Video đã xếp lịch đang ở đâu, dùng chung cho Kho / Kho riêng / xem video (Lịch đăng tự tính trong AutoController):
 * - tiktok: đã hẹn trên TikTok (TikTok giữ lịch; sửa/xoá thì app phải xoá bài hẹn trước)
 * - uploading: Chrome đang tải lên TikTok (khoá tạm vài phút)
 * - direct: trong khung giờ đăng thẳng, còn trong app, tới giờ Chrome đăng luôn
 * - in_app: đã xếp giờ, chưa gửi lên TikTok (sửa / xoá thoải mái)
 */
final class ScheduleState
{
    /**
     * @param  Collection<int, AutoVideo>  $videos
     * @return array<int, string> id video => trạng thái (chỉ video đã xếp mà chưa đăng)
     */
    public static function forVideos(Collection $videos): array
    {
        $open = $videos->filter(fn (AutoVideo $v): bool => in_array($v->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED], true)
            || ($v->status === AutoVideo::POSTED && $v->posted_at?->isFuture()));

        if ($open->isEmpty()) {
            return [];
        }

        $info = app(Reschedules::class)->calendarInfo($open->values());
        $window = DirectWindow::get();
        $out = [];

        foreach ($open as $v) {
            $i = $info[$v->id] ?? null;
            $out[$v->id] = match (true) {
                $v->status === AutoVideo::POSTED, (bool) ($i['on_tiktok'] ?? false) => 'tiktok',
                (bool) ($i['uploading'] ?? false) => 'uploading',
                $v->social_account_id !== null && DirectWindow::covers((string) $v->social_account_id, $v->scheduled_for, $window) => 'direct',
                default => 'in_app',
            };
        }

        return $out;
    }
}

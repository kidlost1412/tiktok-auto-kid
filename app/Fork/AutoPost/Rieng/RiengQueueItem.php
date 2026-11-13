<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\Models\AutoVideo;
use Illuminate\Database\Eloquent\Model;

/**
 * "Giỏ chờ đăng": video riêng chủ app chọn sẵn để đăng sau. Khác hẳn "giỏ hàng" của TikTok Shop.
 * Lưu trong CSDL nên còn nguyên sau khi tải lại trang; video đã hẹn giờ thì bị bỏ khỏi giỏ.
 */
class RiengQueueItem extends Model
{
    protected $table = 'fork_rieng_queue';

    protected $guarded = [];

    /** Mã video trong giỏ của một chủ app, chỉ gồm video còn đăng được (chưa hẹn, còn file) hoặc video lỗi có thể thử lại. */
    public static function idsFor(string $owner): array
    {
        return static::query()
            ->where('owner', $owner)
            ->whereIn('auto_video_id', AutoVideo::query()
                ->where('source', AutoVideo::SOURCE_RIENG)
                ->where(fn ($q) => $q->where(fn ($n) => $n->where('status', AutoVideo::NEW)->whereNull('files_deleted_at'))->orWhere('status', AutoVideo::FAILED))
                ->select('id'))
            ->orderBy('id')
            ->pluck('auto_video_id')
            ->map(fn ($id): int => (int) $id)
            ->all();
    }

    /** Video vừa được hẹn giờ: bỏ khỏi giỏ của mọi chủ app. */
    public static function forget(int $videoId): void
    {
        static::query()->where('auto_video_id', $videoId)->delete();
    }
}

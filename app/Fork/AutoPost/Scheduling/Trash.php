<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Shop\CartRules;
use Carbon\CarbonImmutable;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Facades\Log;
use RuntimeException;

/**
 * Thùng rác video: video anh "xoá" (PostEdits::remove) nằm đây DAYS ngày và khôi phục được về kho.
 * Xoá trong thùng rác (hoặc để quá DAYS ngày) là xoá hẳn khỏi app; dòng video vẫn giữ làm dấu để quét lại không nạp lại.
 * File video gốc của anh trên ổ đĩa không bao giờ bị xoá.
 */
final class Trash
{
    public const int DAYS = 30;

    /** @return Builder<AutoVideo> */
    public static function query(): Builder
    {
        return AutoVideo::query()
            ->whereNotNull('trashed_at')
            ->whereNull('purged_at')
            ->where('trashed_at', '>=', CarbonImmutable::now()->subDays(self::DAYS));
    }

    /** @return list<array<string, mixed>> */
    public function list(): array
    {
        $hub = AutoProduct::query()->get()->keyBy('code');
        $now = CarbonImmutable::now();

        return self::query()->orderByDesc('trashed_at')->limit(500)->get()
            ->map(function (AutoVideo $v) use ($hub, $now): array {
                $until = CarbonImmutable::instance($v->trashed_at)->addDays(self::DAYS);

                return [
                    'id' => $v->id,
                    'file_name' => $v->file_name,
                    'source' => $v->source,
                    'product_label' => $v->product_code ? CartRules::label($hub[$v->product_code] ?? null, (string) $v->product_code, $v->quy_cach) : null,
                    'caption' => $v->caption,
                    'trashed_at' => $v->trashed_at?->toIso8601String(),
                    'days_left' => max(0, (int) ceil($now->diffInHours($until, false) / 24)),
                    'file_ok' => is_file((string) $v->path),
                ];
            })->values()->all();
    }

    public function count(): int
    {
        return self::query()->count();
    }

    /** Khôi phục về kho (chưa xếp lịch). */
    public function restore(AutoVideo $video): string
    {
        $this->assertInTrash($video);
        $meta = (array) $video->meta;
        unset($meta['removed_by_owner']);

        $video->forceFill([
            'status' => AutoVideo::NEW,
            'skip_reason' => null,
            'trashed_at' => null,
            'meta' => $meta === [] ? null : $meta,
        ])->save();

        Log::info('Khôi phục video từ thùng rác.', ['video_id' => $video->id]);

        return is_file((string) $video->path)
            ? 'Đã khôi phục video về kho.'
            : 'Đã khôi phục video về kho, nhưng không thấy file video trên ổ đĩa (ổ đĩa đang tắt hoặc file đã bị xoá).';
    }

    /** Xoá hẳn khỏi app (không khôi phục được nữa). File gốc trên ổ đĩa vẫn còn. */
    public function purge(AutoVideo $video): void
    {
        $this->assertInTrash($video);
        $video->forceFill(['purged_at' => now(), 'skip_reason' => 'Anh đã xoá hẳn video này'])->save();
        Log::info('Xoá hẳn video trong thùng rác.', ['video_id' => $video->id]);
    }

    public function purgeAll(): int
    {
        return self::query()->update(['purged_at' => now(), 'skip_reason' => 'Anh đã xoá hẳn video này', 'updated_at' => now()]);
    }

    private function assertInTrash(AutoVideo $video): void
    {
        if (! self::query()->whereKey($video->id)->exists()) {
            throw new RuntimeException('Video này không còn trong thùng rác.');
        }
    }
}

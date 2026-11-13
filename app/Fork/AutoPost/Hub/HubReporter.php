<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Hub;

use App\Fork\AutoPost\Models\AutoVideo;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;

/**
 * Báo kết quả ngược về hub (đã đăng, lỗi, số liệu) qua hàng đợi `fork_hub_outbox`:
 * mỗi lời báo được ghi vào DB trước, gửi thử ngay, chưa được thì thử lại ở lượt `fork:auto-ingest` sau
 * (hub tắt không làm mất gì). Chỉ chạy ở chế độ API và với video có `hub_id`.
 */
final class HubReporter
{
    public const OFFLINE_CACHE_KEY = 'fork-hub:offline';

    /** Bỏ hẳn lời báo quá cũ (ngày). */
    private const int MAX_AGE_DAYS = 14;

    public function __construct(private readonly HubApi $api = new HubApi) {}

    public function posted(AutoVideo $video): void
    {
        if (! $this->applies($video)) {
            return;
        }

        $video->loadMissing('socialAccount');
        $username = (string) $video->socialAccount?->username;
        $tiktokId = filled($video->tiktok_video_id) ? (string) $video->tiktok_video_id : null;
        $link = data_get($video->stats, 'link');

        if (! is_string($link) && $tiktokId !== null && $username !== '') {
            $link = "https://www.tiktok.com/@{$username}/video/{$tiktokId}";
        }

        $this->queue('da-dang', (string) $video->hub_id, [
            'kenh' => $username !== '' ? '@'.$username : null,
            'tiktok_id' => $tiktokId,
            'link' => is_string($link) ? $link : null,
            'luc' => ($video->posted_at ?? now())->toIso8601String(),
        ]);
    }

    public function failed(AutoVideo $video, string $reason): void
    {
        if ($this->applies($video)) {
            $this->queue('loi', (string) $video->hub_id, ['ly_do' => Str::limit($reason, 200, '')]);
        }
    }

    /** Video đã giữ chỗ nhưng không đăng nữa (về kho): nhả chỗ trên hub để máy khác lấy được. */
    public function released(AutoVideo $video): void
    {
        if ($this->applies($video)) {
            $this->queue('nha', (string) $video->hub_id, ['may' => $this->api->may()]);
        }
    }

    /** Vừa giữ chỗ lại video: bỏ lời nhả cũ còn kẹt trong outbox để nó không nhả nhầm chỗ mới. */
    public function claimed(string $hubId): void
    {
        HubOutboxItem::query()->where('kind', 'nha')->where('hub_id', $hubId)->delete();
    }

    /** @param  array<string, mixed>  $stats  AutoVideo::stats */
    public function stats(AutoVideo $video, array $stats): void
    {
        if (! $this->applies($video)) {
            return;
        }

        $video->loadMissing('socialAccount');
        $username = (string) $video->socialAccount?->username;
        $last = $stats['h72'] ?? $stats['h24'] ?? $stats['latest'] ?? [];

        $this->queue('so-lieu', (string) $video->hub_id, [
            'id' => (string) $video->hub_id,
            'kenh' => $username !== '' ? '@'.$username : null,
            'luot_xem_24h' => $stats['h24']['views'] ?? null,
            'luot_xem_72h' => $stats['h72']['views'] ?? null,
            'thich' => $last['likes'] ?? null,
            'binh_luan' => $last['comments'] ?? null,
            'chia_se' => $last['shares'] ?? null,
            // TikTok Auto Kid không có số đơn hàng.
            'don' => null,
            'luc' => now()->toIso8601String(),
        ]);
    }

    /**
     * Gửi các lời báo đến hạn. Dừng ngay khi hub tắt hoặc sai khoá.
     *
     * @return array{sent: int, dropped: int, pending: int}
     */
    public function flush(int $limit = 200): array
    {
        $sent = 0;
        $dropped = 0;

        if (HubApi::enabled()) {
            HubOutboxItem::query()->where('created_at', '<', now()->subDays(self::MAX_AGE_DAYS))->delete();

            $items = HubOutboxItem::query()
                ->where(fn ($q) => $q->whereNull('next_attempt_at')->orWhere('next_attempt_at', '<=', now()))
                ->orderBy('id')
                ->limit($limit)
                ->get();

            foreach ($items as $item) {
                $result = $this->deliver($item);

                if ($result === 'sent') {
                    $sent++;
                } elseif ($result === 'dropped') {
                    $dropped++;
                } elseif ($result === 'stop') {
                    break;
                }
            }
        }

        return ['sent' => $sent, 'dropped' => $dropped, 'pending' => HubOutboxItem::query()->count()];
    }

    private function applies(AutoVideo $video): bool
    {
        return HubApi::enabled() && filled($video->hub_id) && ! $video->isRieng();
    }

    /** @param  array<string, mixed>  $payload */
    private function queue(string $kind, string $hubId, array $payload): void
    {
        // da-dang và loi chỉ cần bản mới nhất của mỗi video; so-lieu là append-only.
        if ($kind !== 'so-lieu') {
            HubOutboxItem::query()->where('kind', $kind)->where('hub_id', $hubId)->delete();
        }

        $item = HubOutboxItem::query()->create(['kind' => $kind, 'hub_id' => $hubId, 'payload' => $payload]);

        // Hub vừa báo tắt thì khỏi chờ timeout, để lượt sau gửi.
        if (! Cache::has(self::OFFLINE_CACHE_KEY)) {
            $this->deliver($item);
        }
    }

    /** @return 'sent'|'dropped'|'retry'|'stop' */
    private function deliver(HubOutboxItem $item): string
    {
        $payload = (array) $item->payload;

        $result = match ($item->kind) {
            'da-dang' => $this->api->markPosted($item->hub_id, $payload),
            'nha' => $this->api->release($item->hub_id),
            'loi' => $this->api->markFailed($item->hub_id, (string) ($payload['ly_do'] ?? '')),
            'so-lieu' => $this->api->sendStats($payload),
            default => HubApi::REJECTED,
        };

        if ($result === HubApi::OK) {
            Cache::forget(self::OFFLINE_CACHE_KEY);
            $item->delete();

            return 'sent';
        }

        // Hub không biết id này hoặc từ chối nội dung: gửi lại cũng vô ích.
        if (in_array($result, [HubApi::NOT_FOUND, HubApi::REJECTED], true)) {
            Log::warning('Hub API: bỏ lời báo không được hub nhận.', ['kind' => $item->kind, 'hub_id' => $item->hub_id, 'result' => $result]);
            $item->delete();

            return 'dropped';
        }

        $attempts = $item->attempts + 1;
        $item->forceFill([
            'attempts' => $attempts,
            'last_error' => $result,
            'next_attempt_at' => Carbon::now()->addSeconds(min(3600, 60 * (2 ** min($attempts, 6)))),
        ])->save();

        if ($result === HubApi::OFFLINE) {
            Cache::put(self::OFFLINE_CACHE_KEY, true, 60);

            return 'stop';
        }

        return $result === HubApi::BAD_KEY ? 'stop' : 'retry';
    }
}

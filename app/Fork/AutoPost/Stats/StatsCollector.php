<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Stats;

use App\Fork\AutoPost\Hub\HubApi;
use App\Fork\AutoPost\Hub\HubReporter;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Models\AnalyticsPublication;
use App\Models\AnalyticsPublicationDailySnapshot;
use App\Models\Post;
use Carbon\CarbonImmutable;

/**
 * Thu số liệu của video đã đăng từ dữ liệu TikTok Auto Kid đã thu sẵn (AnalyticsPublication),
 * ghi vào AutoVideo.stats rồi báo ngược về hub.
 */
final class StatsCollector
{
    /** Số ngày sau khi đăng còn làm mới mốc "latest". */
    private const int LATEST_DAYS = 14;

    /**
     * @return array{updated: int, checked: int, hub: array{sheets: int, filled: int}}
     */
    public function collect(?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();

        $videos = AutoVideo::query()
            ->where('status', 'posted')
            ->whereNotNull('posted_at')
            // Không đợi đủ 24 giờ: mốc "latest" có ngay khi đã có snapshot; h24/h72 tự chờ tới giờ trong refresh().
            ->where('posted_at', '<=', $now)
            ->where(fn ($q) => $q
                ->where('posted_at', '>=', $now->subDays(self::LATEST_DAYS))
                ->orWhereNull('stats')
                ->orWhereNull('stats->h24')
                ->orWhere(fn ($q2) => $q2->where('posted_at', '<=', $now->subHours(72))->whereNull('stats->h72')))
            ->get();

        $updated = 0;

        foreach ($videos as $video) {
            if ($this->refresh($video, $now)) {
                $updated++;
            }
        }

        // Ghi lại so-lieu.csv cho mọi ngày có video đã đăng đã có số liệu.
        $dates = AutoVideo::query()
            ->where('status', 'posted')
            ->whereNotNull('stats')
            ->distinct()
            ->pluck('batch_date')
            ->map(fn ($d) => $d instanceof \DateTimeInterface ? $d->format('Y-m-d') : substr((string) $d, 0, 10))
            ->unique()
            ->values()
            ->all();

        return [
            'updated' => $updated,
            'checked' => $videos->count(),
            'hub' => HubApi::enabled() ? ['sheets' => 0, 'filled' => 0] : app(HubFeedback::class)->sync($dates, $now),
        ];
    }

    private function refresh(AutoVideo $video, CarbonImmutable $now): bool
    {
        $publication = $this->publicationFor($video);

        if (! $publication) {
            return false;
        }

        $snapshots = $publication->dailySnapshots()->orderBy('date')->get();

        if ($snapshots->isEmpty()) {
            return false;
        }

        $stats = (array) ($video->stats ?? []);
        $posted = CarbonImmutable::instance($video->posted_at);
        $before = $stats;

        foreach (['h24' => 24, 'h72' => 72] as $key => $hours) {
            if (isset($stats[$key]) || $posted->addHours($hours)->greaterThan($now)) {
                continue;
            }

            $snapshot = $snapshots->first(
                fn (AnalyticsPublicationDailySnapshot $s): bool => $this->observedAt($s)->greaterThanOrEqualTo($posted->addHours($hours)),
            );

            if ($snapshot) {
                $stats[$key] = $this->metrics($snapshot);
            }
        }

        $stats['latest'] = $this->metrics($snapshots->last());

        if ($publication->permalink) {
            $stats['link'] = $publication->permalink;
        }

        if ($stats === $before) {
            return false;
        }

        $video->stats = $stats;
        $video->stats_written_at = $now;

        if (! $video->tiktok_video_id && $publication->remote_id) {
            $video->tiktok_video_id = (string) $publication->remote_id;
        }

        $video->save();

        // Báo số liệu về hub khi vừa có mốc 24h hoặc 72h mới.
        if (isset($stats['h24']) && ($before['h24'] ?? null) !== $stats['h24'] || isset($stats['h72']) && ($before['h72'] ?? null) !== $stats['h72']) {
            app(HubReporter::class)->stats($video, $stats);
        }

        return true;
    }

    private function publicationFor(AutoVideo $video): ?AnalyticsPublication
    {
        if ($video->post_id) {
            $found = AnalyticsPublication::query()->where('post_id', $video->post_id)->first();

            if ($found) {
                return $found;
            }
        }

        $remoteIds = array_values(array_filter([
            $video->tiktok_video_id,
            $video->post_id ? Post::query()->whereKey($video->post_id)->value('platform_post_id') : null,
        ], fn (mixed $id): bool => is_string($id) && $id !== ''));

        if ($remoteIds !== []) {
            $found = AnalyticsPublication::query()
                ->whereIn('remote_id', $remoteIds)
                ->when($video->social_account_id, fn ($q) => $q->where('social_account_id', $video->social_account_id))
                ->first();

            if ($found) {
                return $found;
            }
        }

        // Bài hẹn giờ Chrome: TikTok gán id video khi tới giờ, TikTok Auto Kid có thể chưa nối bài với video. Dò theo kênh và giờ đăng (sai số 10 phút).
        $at = $video->scheduled_for ?? $video->posted_at;

        if ($video->social_account_id && $at) {
            $at = CarbonImmutable::instance($at);

            return AnalyticsPublication::query()
                ->where('social_account_id', $video->social_account_id)
                ->whereBetween('provider_published_at', [$at->subMinutes(10), $at->addMinutes(10)])
                ->whereNotIn('remote_id', AutoVideo::query()->where('id', '!=', $video->id)->whereNotNull('tiktok_video_id')->select('tiktok_video_id'))
                ->orderBy('provider_published_at')
                ->first();
        }

        return null;
    }

    private function observedAt(AnalyticsPublicationDailySnapshot $s): CarbonImmutable
    {
        return CarbonImmutable::instance($s->provider_observed_at ?? $s->collected_at ?? $s->date);
    }

    /**
     * @return array{views: int, likes: int, comments: int, shares: int, at: string}
     */
    private function metrics(AnalyticsPublicationDailySnapshot $s): array
    {
        return [
            'views' => (int) $s->views_count,
            'likes' => (int) $s->reactions_count,
            'comments' => (int) $s->comments_count,
            'shares' => (int) $s->shares_count,
            'at' => $this->observedAt($s)->toIso8601String(),
        ];
    }
}

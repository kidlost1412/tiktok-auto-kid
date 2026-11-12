<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Stats;

use App\Fork\AutoPost\Hub\HubReporter;
use App\Fork\AutoPost\Models\AccountStat;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\VideoSnapshot;
use App\Fork\AutoPost\Models\VideoStat;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;

/**
 * Nhận số liệu video + số người theo dõi do tiện ích TikTok Auto Kid gửi (POST /api/ext/stats):
 * lưu số liệu mới nhất + lịch sử, ghép với video trong kho theo item_id, cập nhật AutoVideo.stats {h24, h72, latest, link, insight}
 * và báo hub (so-lieu) khi vừa có mốc 24h / 72h. Chỉ thêm và cập nhật, không bao giờ xoá gì.
 */
final class StatsIngest
{
    public const int MAX_VIDEOS = 400;

    /** Mốc 24h/72h chỉ lấy từ ảnh chụp trong khoảng này sau mốc (tiện ích tắt lâu thì để trống thay vì ghi số của ngày khác). */
    private const int MILESTONE_SLACK_HOURS = 12;

    /** Ảnh chụp mới nếu số liệu đổi (và cách ảnh trước ≥ 30 phút) hoặc đã quá 6 giờ. */
    private const int SNAPSHOT_MIN_MINUTES = 30;

    private const int SNAPSHOT_MAX_HOURS = 6;

    public function __construct(private readonly VideoMatcher $matcher) {}

    /**
     * @param  array<string, mixed>  $body
     * @return array{stored: int, matched: int, snapshots: int, milestones: int, followers: int|null}
     */
    public function ingest(SocialAccount $account, array $body, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $items = $this->normalize($body['videos'] ?? []);
        $matched = $this->matcher->match((string) $account->id, array_map(fn (array $i): array => ['item_id' => $i['item_id'], 'post_time' => $i['post_time']], $items));

        $stored = 0;
        $snapshots = 0;
        $milestones = 0;
        $username = (string) $account->username;

        foreach ($items as $item) {
            $stat = VideoStat::query()->firstOrNew(['social_account_id' => (string) $account->id, 'item_id' => $item['item_id']]);

            $stat->fill([
                'caption' => $item['desc'] !== '' ? $item['desc'] : $stat->caption,
                'posted_at' => $item['post_time'] > 0 ? CarbonImmutable::createFromTimestampUTC($item['post_time']) : $stat->posted_at,
                'duration_ms' => $item['duration_ms'] ?: $stat->duration_ms,
                'views' => $item['views'],
                'likes' => $item['likes'],
                'comments' => $item['comments'],
                'shares' => $item['shares'],
                'saves' => $item['saves'],
                'collected_at' => $now,
            ]);

            $insight = $item['insight'];

            if ($insight !== null) {
                $stat->fill([
                    'avg_watch_s' => $insight['avg_watch_s'] ?? $stat->avg_watch_s,
                    'finish_rate' => $insight['finish_rate'] ?? $stat->finish_rate,
                    'total_watch_s' => $insight['total_watch_s'] ?? $stat->total_watch_s,
                    'new_followers' => $insight['new_followers'] ?? $stat->new_followers,
                    'traffic' => $insight['traffic'] !== [] ? $insight['traffic'] : $stat->traffic,
                    'insight_at' => $now,
                ]);
            }

            $video = $matched[$item['item_id']] ?? null;
            $stat->auto_video_id = $video?->id ?? $stat->auto_video_id;
            $stat->save();
            $stored++;

            if ($this->snapshot($stat, $now)) {
                $snapshots++;
            }

            $video ??= $stat->auto_video_id ? AutoVideo::query()->find($stat->auto_video_id) : null;

            if ($video && $this->applyToVideo($video, $stat, $username, $now)) {
                $milestones++;
            }
        }

        $followers = $this->account($account, $body['account'] ?? null, $now);

        return ['stored' => $stored, 'matched' => count($matched), 'snapshots' => $snapshots, 'milestones' => $milestones, 'followers' => $followers];
    }

    /** Có ảnh chụp mới không: đổi số liệu hoặc đã lâu. */
    private function snapshot(VideoStat $stat, CarbonImmutable $now): bool
    {
        $last = VideoSnapshot::query()->where('item_id', $stat->item_id)->where('social_account_id', $stat->social_account_id)->orderByDesc('taken_at')->first();

        if ($last) {
            $age = $now->getTimestamp() - $last->taken_at->getTimestamp();
            $same = (int) $last->views === (int) $stat->views && (int) $last->likes === (int) $stat->likes && (int) $last->comments === (int) $stat->comments
                && (int) $last->shares === (int) $stat->shares && (int) $last->saves === (int) $stat->saves;

            // Giữ ảnh chụp cũ khi số liệu không đổi hoặc mới chụp xong; nhưng quá 6 giờ thì luôn chụp lại để không có khoảng trống.
            if (($same || $age < self::SNAPSHOT_MIN_MINUTES * 60) && $age < self::SNAPSHOT_MAX_HOURS * 3600) {
                return false;
            }
        }

        VideoSnapshot::query()->create([
            'social_account_id' => $stat->social_account_id,
            'item_id' => $stat->item_id,
            'taken_at' => $now,
            'views' => $stat->views,
            'likes' => $stat->likes,
            'comments' => $stat->comments,
            'shares' => $stat->shares,
            'saves' => $stat->saves,
        ]);

        return true;
    }

    /**
     * Ghi số liệu vào AutoVideo.stats. Trả true khi vừa có mốc 24h hoặc 72h mới.
     */
    private function applyToVideo(AutoVideo $video, VideoStat $stat, string $username, CarbonImmutable $now): bool
    {
        $stats = (array) ($video->stats ?? []);
        $before = $stats;

        $stats['latest'] = [
            'views' => (int) $stat->views,
            'likes' => (int) $stat->likes,
            'comments' => (int) $stat->comments,
            'shares' => (int) $stat->shares,
            'saves' => (int) $stat->saves,
            'at' => $now->toIso8601String(),
        ];

        if ($video->posted_at) {
            $posted = CarbonImmutable::instance($video->posted_at);

            foreach (['h24' => 24, 'h72' => 72] as $key => $hours) {
                if (isset($stats[$key]) || $posted->addHours($hours)->greaterThan($now)) {
                    continue;
                }

                $snap = VideoSnapshot::query()
                    ->where('social_account_id', $stat->social_account_id)
                    ->where('item_id', $stat->item_id)
                    ->whereBetween('taken_at', [$posted->addHours($hours), $posted->addHours($hours + self::MILESTONE_SLACK_HOURS)])
                    ->orderBy('taken_at')
                    ->first();

                if ($snap) {
                    $stats[$key] = [
                        'views' => (int) $snap->views,
                        'likes' => (int) $snap->likes,
                        'comments' => (int) $snap->comments,
                        'shares' => (int) $snap->shares,
                        'saves' => (int) $snap->saves,
                        'at' => $snap->taken_at->toIso8601String(),
                    ];
                }
            }
        }

        if ($stat->insight_at) {
            $stats['insight'] = array_filter([
                'avg_watch_s' => $stat->avg_watch_s,
                'finish_rate' => $stat->finish_rate,
                'total_watch_s' => $stat->total_watch_s,
                'new_followers' => $stat->new_followers,
                'traffic' => $stat->traffic,
                'at' => $stat->insight_at->toIso8601String(),
            ], fn (mixed $v): bool => $v !== null);
        }

        if ($username !== '') {
            $stats['link'] = "https://www.tiktok.com/@{$username}/video/{$stat->item_id}";
        }

        $video->stats = $stats;
        $video->stats_written_at = $now;

        if (blank($video->tiktok_video_id)) {
            $video->tiktok_video_id = $stat->item_id;
        }

        $video->save();

        $new = ($stats['h24'] ?? null) !== ($before['h24'] ?? null) || ($stats['h72'] ?? null) !== ($before['h72'] ?? null);

        if ($new) {
            app(HubReporter::class)->stats($video, $stats);
        }

        return $new;
    }

    /** @return int|null số người theo dõi đã ghi */
    private function account(SocialAccount $account, mixed $data, CarbonImmutable $now): ?int
    {
        if (! is_array($data) || ! is_numeric($data['followers'] ?? null) || (float) $data['followers'] < 0) {
            return null;
        }

        $tz = $account->timezone ?: 'Asia/Ho_Chi_Minh';
        $history = is_array($data['follower_history'] ?? null)
            ? array_slice(array_values(array_filter($data['follower_history'], 'is_numeric')), 0, 60)
            : [];

        AccountStat::query()->updateOrCreate(
            ['social_account_id' => (string) $account->id, 'date' => $now->setTimezone($tz)->format('Y-m-d')],
            ['followers' => (int) $data['followers'], 'history' => $history, 'collected_at' => $now],
        );

        return (int) $data['followers'];
    }

    /**
     * @return list<array{item_id: string, desc: string, post_time: int, duration_ms: int, views: int, likes: int, comments: int, shares: int, saves: int, insight: array<string, mixed>|null}>
     */
    private function normalize(mixed $videos): array
    {
        if (! is_array($videos)) {
            return [];
        }

        $out = [];
        $int = fn (mixed $v): int => is_numeric($v) && $v >= 0 ? (int) $v : 0;
        $float = fn (mixed $v): ?float => is_numeric($v) && $v >= 0 ? (float) $v : null;

        foreach (array_slice(array_values($videos), 0, self::MAX_VIDEOS) as $v) {
            $id = is_array($v) ? ($v['item_id'] ?? null) : null;

            if (! is_string($id) || preg_match('/^[0-9]{5,25}$/', $id) !== 1) {
                continue;
            }

            $in = is_array($v['insight'] ?? null) ? $v['insight'] : null;
            $traffic = [];

            foreach (is_array($in['traffic'] ?? null) ? array_slice($in['traffic'], 0, 12) : [] as $t) {
                if (is_array($t) && is_string($t['key'] ?? null) && is_numeric($t['value'] ?? null)) {
                    $traffic[] = ['key' => mb_substr($t['key'], 0, 40), 'value' => round((float) $t['value'], 4)];
                }
            }

            $finish = $float($in['finish_rate'] ?? null);

            $out[] = [
                'item_id' => $id,
                'desc' => is_string($v['desc'] ?? null) ? mb_substr($v['desc'], 0, 2200) : '',
                'post_time' => $int($v['post_time'] ?? 0),
                'duration_ms' => $int($v['duration_ms'] ?? 0),
                'views' => $int($v['views'] ?? 0),
                'likes' => $int($v['likes'] ?? 0),
                'comments' => $int($v['comments'] ?? 0),
                'shares' => $int($v['shares'] ?? 0),
                'saves' => $int($v['saves'] ?? 0),
                'insight' => $in === null ? null : [
                    'avg_watch_s' => $float($in['avg_watch_s'] ?? null),
                    'finish_rate' => $finish !== null ? min(1.0, $finish) : null,
                    'total_watch_s' => $float($in['total_watch_s'] ?? null),
                    'new_followers' => is_numeric($in['new_followers'] ?? null) ? (int) $in['new_followers'] : null,
                    'traffic' => $traffic,
                ],
            ];
        }

        return $out;
    }
}

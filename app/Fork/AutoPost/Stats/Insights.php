<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Stats;

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Support\Collection;

/**
 * Phân tích lượt xem 24 giờ theo giờ đăng, sản phẩm và các thuộc tính video,
 * rồi đề xuất khung giờ đăng tốt nhất cho từng tài khoản.
 */
final class Insights
{
    public const int MIN_DAYS = 7;

    public const int MIN_VIDEOS = 40;

    /** Một giờ cần ít nhất ngần này bài mới được xét. */
    public const int MIN_PER_HOUR = 2;

    private const string DEFAULT_TZ = 'Asia/Ho_Chi_Minh';

    /** @var list<string> */
    private const array DIMENSIONS = ['product_code', 'goc', 'giong', 'nhac', 'font', 'chuyen_canh', 'mau'];

    /**
     * @return array<string, list<array{key: string, avg_views: float, samples: int}>>
     */
    public function breakdowns(?AutoAccount $account = null): array
    {
        $rows = $this->rows($account);
        $out = ['hour' => $this->group($rows, fn (array $r): string => sprintf('%02d', $r['hour']))];

        foreach (self::DIMENSIONS as $dim) {
            $out[$dim] = $this->group($rows, fn (array $r): string => (string) ($r[$dim] ?? ''));
        }

        // Giờ sắp theo giờ; các nhóm còn lại theo lượt xem giảm dần (group() đã sắp).
        usort($out['hour'], fn (array $a, array $b): int => strcmp($a['key'], $b['key']));

        return $out;
    }

    /**
     * @return array{hours: list<array{hour: int, avg_views: float, samples: int, delta_pct: float}>|null, reason: string|null, videos: int, days: int, overall_avg: float}
     */
    public function recommendHours(AutoAccount $account): array
    {
        $rows = $this->rows($account);
        $videos = count($rows);
        $days = count(array_unique(array_column($rows, 'day')));
        $overall = $videos > 0 ? array_sum(array_column($rows, 'views')) / $videos : 0.0;

        $base = ['videos' => $videos, 'days' => $days, 'overall_avg' => round($overall, 1)];

        if ($days < self::MIN_DAYS || $videos < self::MIN_VIDEOS) {
            return $base + [
                'hours' => null,
                'reason' => sprintf(
                    'Chưa đủ dữ liệu: cần ít nhất %d ngày và %d bài có số liệu 24 giờ (hiện có %d ngày, %d bài).',
                    self::MIN_DAYS,
                    self::MIN_VIDEOS,
                    $days,
                    $videos,
                ),
            ];
        }

        $start = (int) ($account->window_start ?? 6);
        $end = (int) ($account->window_end ?? 23);

        $byHour = collect($this->group($rows, fn (array $r): string => (string) $r['hour']))
            ->filter(fn (array $g): bool => $g['samples'] >= self::MIN_PER_HOUR
                && (int) $g['key'] >= $start && (int) $g['key'] < $end);

        if ($byHour->isEmpty()) {
            return $base + ['hours' => null, 'reason' => 'Chưa có giờ nào đủ số bài để so sánh trong khung giờ đang dùng.'];
        }

        // Số giờ đề xuất: đủ để xếp phần lớn daily_cap (mỗi giờ nhận khoảng 2 bài), tối thiểu 3.
        $take = max(3, (int) ceil(((int) ($account->daily_cap ?? 8)) / 2));

        $hours = $byHour
            ->sortByDesc('avg_views')
            ->take($take)
            ->map(fn (array $g): array => [
                'hour' => (int) $g['key'],
                'avg_views' => $g['avg_views'],
                'samples' => $g['samples'],
                'delta_pct' => $overall > 0 ? round(($g['avg_views'] - $overall) / $overall * 100, 1) : 0.0,
            ])
            ->values()
            ->all();

        return $base + ['hours' => $hours, 'reason' => null];
    }

    /**
     * Các video đã đăng có số liệu 24 giờ.
     *
     * @return list<array<string, mixed>>
     */
    private function rows(?AutoAccount $account): array
    {
        $videos = AutoVideo::query()
            ->where('status', 'posted')
            ->whereNotNull('posted_at')
            ->whereNotNull('stats->h24')
            ->when($account, fn ($q) => $q->where('social_account_id', $account->social_account_id))
            ->get();

        $timezones = SocialAccount::query()
            ->whereIn('id', $videos->pluck('social_account_id')->filter()->unique()->all())
            ->pluck('timezone', 'id');

        return $videos->map(function (AutoVideo $v) use ($timezones): array {
            $local = CarbonImmutable::instance($v->posted_at)
                ->setTimezone(($timezones[$v->social_account_id] ?? null) ?: self::DEFAULT_TZ);

            return [
                'hour' => (int) $local->format('G'),
                'day' => $local->format('Y-m-d'),
                'views' => (int) data_get($v->stats, 'h24.views', 0),
                'product_code' => $v->product_code,
                'goc' => $v->goc,
                'giong' => $v->giong,
                'nhac' => $v->nhac,
                'font' => $v->font,
                'chuyen_canh' => $v->chuyen_canh,
                'mau' => $v->mau,
            ];
        })->all();
    }

    /**
     * @param  list<array<string, mixed>>  $rows
     * @return list<array{key: string, avg_views: float, samples: int}>
     */
    private function group(array $rows, callable $keyOf): array
    {
        /** @var Collection<string, Collection<int, array<string, mixed>>> $groups */
        $groups = collect($rows)->groupBy($keyOf)->reject(fn ($g, $key): bool => (string) $key === '');

        return $groups
            ->map(fn (Collection $g, $key): array => [
                'key' => (string) $key,
                'avg_views' => round($g->avg('views'), 1),
                'samples' => $g->count(),
            ])
            ->sortByDesc('avg_views')
            ->values()
            ->all();
    }
}

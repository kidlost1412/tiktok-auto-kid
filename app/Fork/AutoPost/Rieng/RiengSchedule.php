<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\Chrome\ChromeJobs;
use App\Models\Post;
use Carbon\CarbonImmutable;
use DateTimeZone;

/**
 * Giờ đăng cho video riêng (luôn tự đề xuất, chủ app sửa được từng giờ).
 *
 * Luật: chỉ tránh bài CÙNG KÊNH (kênh khác không tính); cách mỗi bài cùng kênh ít nhất Planner::gapSeconds() (mặc định 20 phút);
 * LUÔN trong khung giờ đăng của kênh (window_start..window_end, giờ địa phương), hết khung thì sang khung của ngày hôm sau;
 * cách hiện tại ít nhất self::MIN_LEAD; không xa quá giới hạn hẹn giờ của TikTok; KHÔNG vượt số bài/ngày (daily_cap) của kênh
 * (tính chung mọi video đã giữ chỗ/xếp/đăng của kênh trong ngày địa phương, như Planner), ngày đủ thì sang ngày sau.
 */
final class RiengSchedule
{
    /** Trạng thái video làm bận giờ (giống Planner). */
    private const array COUNTED = ['reserved', 'scheduled', 'posted'];

    /**
     * Giờ sớm nhất cho video riêng: cách bây giờ 5 phút. Bài gần hơn ChromeJobs::SCHEDULE_LEAD không được gửi trước lên
     * TikTok dạng hẹn giờ; tới giờ posts:process-scheduled giao Chrome đăng thẳng (đường 'now').
     */
    public const int MIN_LEAD = 5 * 60;

    public function __construct(private readonly Planner $planner) {}

    /**
     * Khung giờ đăng của kênh, theo phút kể từ 0h địa phương: [đầu, cuối]. Khung lỗi (cuối <= đầu) thì coi như cả ngày.
     *
     * @return array{0: int, 1: int}
     */
    public function window(AutoAccount $a): array
    {
        $start = max(0, min(24, (int) $a->window_start));
        $end = max(0, min(24, (int) $a->window_end));

        return $end > $start ? [$start * 60, $end * 60] : [0, 24 * 60];
    }

    /** "06:00–23:00" để hiện cho người dùng. */
    public function windowLabel(AutoAccount $a): string
    {
        [$s, $e] = $this->window($a);

        return sprintf('%02d:%02d–%02d:%02d', intdiv($s, 60), $s % 60, intdiv($e, 60), $e % 60);
    }

    /** Giờ $ts có nằm trong khung giờ đăng của kênh không (tính cả đúng giờ kết thúc, ví dụ 23:00). */
    public function inWindow(AutoAccount $a, int $ts): bool
    {
        [$s, $e] = $this->window($a);
        $local = CarbonImmutable::createFromTimestampUTC($ts)->setTimezone($this->planner->timezoneFor($a));
        $minute = $local->hour * 60 + $local->minute + ($local->second > 0 ? 1 : 0);

        return $minute >= $s && $minute <= $e;
    }

    /** Giờ sớm nhất được phép hẹn (đã làm tròn lên phút). */
    public function earliest(CarbonImmutable $now): int
    {
        return $this->ceilMinute($now->getTimestamp() + self::MIN_LEAD);
    }

    /** Giờ xa nhất TikTok cho hẹn (chừa 1 giờ an toàn như Planner). */
    public function latest(CarbonImmutable $now): int
    {
        return $now->getTimestamp() + ChromeJobs::SCHEDULE_MAX_AHEAD - 3600;
    }

    /**
     * Mốc (giây UTC) mọi bài đã xếp của CÙNG KÊNH trong khoảng: video tự động/riêng đã giữ chỗ/xếp/đăng và bài TikTok đang hẹn.
     *
     * @param  list<int>  $exceptVideoIds  video không tính (đang được xếp lại)
     * @return list<int>
     */
    public function busy(AutoAccount $a, int $from, int $to, array $exceptVideoIds = []): array
    {
        $fromAt = CarbonImmutable::createFromTimestampUTC($from);
        $toAt = CarbonImmutable::createFromTimestampUTC($to);

        $videos = AutoVideo::query()
            ->where('social_account_id', $a->social_account_id)
            ->whereIn('status', self::COUNTED)
            ->when($exceptVideoIds !== [], fn ($q) => $q->whereNotIn('id', $exceptVideoIds))
            ->whereBetween('scheduled_for', [$fromAt, $toAt])
            ->pluck('scheduled_for');

        $posts = Post::query()
            ->where('social_account_id', $a->social_account_id)
            ->where('status', PostStatus::Scheduled)
            ->whereBetween('scheduled_at', [$fromAt, $toAt])
            ->pluck('scheduled_at');

        return $videos->merge($posts)
            ->filter()
            ->map(fn ($t): int => CarbonImmutable::parse($t)->getTimestamp())
            ->unique()
            ->values()
            ->all();
    }

    /**
     * Số bài đã chiếm chỗ của kênh theo từng ngày địa phương ('Y-m-d' => số), cùng cách đếm với Planner::usedOn
     * (bài "đăng ngay" không có scheduled_for cũng tính theo posted_at/updated_at).
     *
     * @return array<string, int>
     */
    public function dayCounts(AutoAccount $a, int $from, int $to): array
    {
        $tz = $this->planner->timezoneFor($a);
        $out = [];

        AutoVideo::query()
            ->where('social_account_id', $a->social_account_id)
            ->whereIn('status', self::COUNTED)
            ->whereRaw('COALESCE(scheduled_for, posted_at, updated_at) >= ? AND COALESCE(scheduled_for, posted_at, updated_at) < ?', [
                CarbonImmutable::createFromTimestampUTC($from), CarbonImmutable::createFromTimestampUTC($to),
            ])
            ->get(['scheduled_for', 'posted_at', 'updated_at'])
            ->each(function (AutoVideo $v) use (&$out, $tz): void {
                $at = $v->scheduled_for ?? $v->posted_at ?? $v->updated_at;

                if ($at !== null) {
                    $k = CarbonImmutable::parse($at)->setTimezone($tz)->format('Y-m-d');
                    $out[$k] = ($out[$k] ?? 0) + 1;
                }
            });

        return $out;
    }

    /** Ngày địa phương của kênh ('Y-m-d') chứa $ts. */
    public function dayKey(AutoAccount $a, int $ts): string
    {
        return CarbonImmutable::createFromTimestampUTC($ts)->setTimezone($this->planner->timezoneFor($a))->format('Y-m-d');
    }

    /** Số bài/ngày tối đa của kênh; 0 = không giới hạn. */
    public function cap(AutoAccount $a): int
    {
        return max(0, (int) $a->daily_cap);
    }

    /**
     * Giờ trống sớm nhất từ $from: trong khung giờ (hết khung thì sang khung ngày sau), cách mọi mốc trong $busy ít nhất $gap giây,
     * và ngày đó chưa đủ số bài/ngày của kênh theo $dayCounts (null = không xét). null nếu vượt $max.
     *
     * @param  list<int>  $busy
     * @param  array<string, int>|null  $dayCounts
     */
    public function next(AutoAccount $a, int $from, int $max, array $busy, ?int $gap = null, ?array $dayCounts = null): ?int
    {
        $cap = $dayCounts === null ? 0 : $this->cap($a);
        $gap ??= $this->planner->gapSeconds();
        $tz = $this->planner->timezoneFor($a);
        [$ws, $we] = $this->window($a);
        $t = $this->ceilMinute($from);
        sort($busy);

        for ($guard = 0; $guard < 20000; $guard++) {
            if ($t > $max) {
                return null;
            }

            [$dayStart, $winStart, $winEnd] = $this->dayBounds($t, $tz, $ws, $we);

            if ($t < $winStart) {
                $t = $winStart;

                continue;
            }

            $full = $cap > 0 && ($dayCounts[CarbonImmutable::createFromTimestampUTC($t)->setTimezone($tz)->format('Y-m-d')] ?? 0) >= $cap;

            if ($t > $winEnd || $full) {
                // Hết khung hoặc ngày đã đủ bài: sang khung của ngày hôm sau (mốc 0h ngày sau theo giờ địa phương, đúng cả khi đổi giờ mùa hè).
                [, $t] = $this->dayBounds($dayStart + 36 * 3600, $tz, $ws, $we);

                continue;
            }

            $clash = null;

            foreach ($busy as $b) {
                if (abs($b - $t) < $gap) {
                    $clash = max($clash ?? $b, $b);
                }
            }

            if ($clash === null) {
                return $t;
            }

            $t = $this->ceilMinute($clash + $gap);
        }

        return null;
    }

    /**
     * Đầu và cuối khung giờ đăng (giây UTC) của ngày chứa $ts.
     *
     * @return array{0: int, 1: int}
     */
    public function dayWindow(AutoAccount $a, int $ts): array
    {
        [$ws, $we] = $this->window($a);
        [, $s, $e] = $this->dayBounds($ts, $this->planner->timezoneFor($a), $ws, $we);

        return [$s, $e];
    }

    /**
     * Mốc 0h địa phương, đầu khung, cuối khung (giây UTC) của ngày chứa $ts.
     *
     * @return array{0: int, 1: int, 2: int}
     */
    private function dayBounds(int $ts, DateTimeZone $tz, int $ws, int $we): array
    {
        $day = CarbonImmutable::createFromTimestampUTC($ts)->setTimezone($tz)->startOfDay();

        return [$day->getTimestamp(), $day->addMinutes($ws)->getTimestamp(), $day->addMinutes($we)->getTimestamp()];
    }

    private function ceilMinute(int $ts): int
    {
        return $ts % 60 === 0 ? $ts : $ts + (60 - $ts % 60);
    }
}

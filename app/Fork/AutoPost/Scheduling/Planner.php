<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Platform;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\CaptionService;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\VideoLibrary;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Post;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use DateTimeZone;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Random\Engine\Mt19937;
use Random\Randomizer;
use Throwable;

/**
 * Tự xếp giờ và tạo bài TikTok cho từng tài khoản bật tự động đăng.
 *
 * Giờ đăng của một ngày địa phương được sinh theo hạt giống cố định (tài khoản + ngày),
 * nên chạy lại nhiều lần cho cùng kết quả: các giờ đã có bài bị coi là "bận" và
 * không xếp lại, vì vậy không bao giờ tạo trùng.
 */
final class Planner
{
    /** Giờ đăng phải cách hiện tại ít nhất ngần này giây: Chrome phải nhận bài trước giờ đăng 35 phút (ChromeJobs::SCHEDULE_LEAD) + dự phòng; TikTok cần hẹn cách ít nhất 15 phút. */
    public const int MIN_LEAD = 45 * 60;

    public const int MAX_AHEAD_DAYS = 9;

    public const string DEFAULT_TIMEZONE = 'Asia/Ho_Chi_Minh';

    /** Trạng thái video tính vào hạn mức ngày và làm bận giờ. */
    private const array COUNTED = ['reserved', 'scheduled', 'posted'];

    /** Hai kênh không được đăng gần như cùng lúc: cách nhau ít nhất ngần này giây, nếu trùng thì đẩy lùi 2 đến 5 phút. */
    public const int CHANNEL_CLEARANCE = 2 * 60;

    public const int NUDGE_MIN = 2 * 60;

    public const int NUDGE_MAX = 5 * 60;

    public function __construct(
        private readonly VideoLibrary $library,
        private readonly CaptionService $captions,
        private readonly PostBuilder $builder,
        private readonly CartRules $cart,
    ) {}

    /**
     * @param  list<string>|null  $onlyAccountIds  chỉ xếp cho các tài khoản này (null = tất cả, như cron)
     * @return array<string, array{created: int, failed: int, skipped: ?string}> khoá là social_account_id
     */
    public function planAll(?CarbonImmutable $now = null, ?array $onlyAccountIds = null): array
    {
        $now ??= CarbonImmutable::now();
        $report = [];

        $accounts = AutoAccount::query()->where('enabled', true)
            ->when($onlyAccountIds !== null, fn ($q) => $q->whereIn('social_account_id', $onlyAccountIds))
            ->get();

        foreach ($accounts as $auto) {
            $id = (string) $auto->social_account_id;
            $why = $this->ineligible($auto);

            if ($why !== null) {
                $report[$id] = ['created' => 0, 'failed' => 0, 'skipped' => $why];

                continue;
            }

            $lock = Cache::lock('fork:auto-plan:'.$id, 300);

            if (! $lock->get()) {
                $report[$id] = ['created' => 0, 'failed' => 0, 'skipped' => 'đang được xếp lịch bởi lượt khác'];

                continue;
            }

            try {
                $report[$id] = $this->planAccount($auto, $now);
            } catch (Throwable $e) {
                report($e);
                $report[$id] = ['created' => 0, 'failed' => 1, 'skipped' => 'lỗi: '.$e->getMessage()];
            } finally {
                $lock->release();
            }
        }

        return $report;
    }

    /** Số ngày xếp trước của kênh, kẹp 1..9 (TikTok chỉ cho hẹn giờ tối đa 10 ngày). */
    public function aheadDays(AutoAccount $a): int
    {
        $days = (int) ($a->schedule_ahead_days ?? 0);

        return $days >= 1 ? min(self::MAX_AHEAD_DAYS, $days) : max(1, min(self::MAX_AHEAD_DAYS, (int) config('fork.auto.default_schedule_ahead_days', 3)));
    }

    /**
     * Mốc cuối (UTC) của khoảng được xếp giờ: hết ngày địa phương của (hôm nay + schedule_ahead_days - 1),
     * không vượt quá giới hạn hẹn giờ của TikTok (ChromeJobs::SCHEDULE_MAX_AHEAD).
     */
    public function horizonFor(AutoAccount $a, CarbonImmutable $now): CarbonImmutable
    {
        $end = $now->setTimezone($this->timezoneFor($a))->startOfDay()->addDays($this->aheadDays($a))->subSecond()->utc();
        $max = $now->addSeconds(ChromeJobs::SCHEDULE_MAX_AHEAD - 3600);

        return $end->greaterThan($max) ? $max : $end;
    }

    /** Còn được xếp thêm bao nhiêu bài tương lai (giới hạn fork.auto.max_future_posts). */
    public function futureRoom(AutoAccount $a, CarbonImmutable $now): int
    {
        $max = max(1, (int) config('fork.auto.max_future_posts', 30));
        $used = AutoVideo::query()
            ->where('social_account_id', $a->social_account_id)
            // Video đã hẹn giờ sẵn trên TikTok là posted có giờ hẹn ở tương lai: vẫn là bài chờ đăng.
            ->whereIn('status', ['reserved', 'scheduled', 'posted'])
            ->where('scheduled_for', '>', $now)
            ->count();

        return $max - $used;
    }

    /**
     * Các giờ đăng (UTC) còn trống trong [from, to]: không vượt daily_cap của ngày địa phương,
     * cách mọi bài khác của tài khoản ít nhất min_gap_minutes. Chỉ đọc DB, không ghi gì.
     *
     * @return list<CarbonImmutable>
     */
    public function slotsFor(AutoAccount $a, CarbonImmutable $from, CarbonImmutable $to): array
    {
        $cap = max(0, (int) $a->daily_cap);

        if ($cap === 0 || $to->lessThanOrEqualTo($from)) {
            return [];
        }

        $tz = $this->timezoneFor($a);
        $gap = $this->gapSeconds();
        $first = $from->setTimezone($tz)->startOfDay();
        $last = $to->setTimezone($tz)->startOfDay();

        $busy = $this->busyTimestamps($a, $first->utc()->subSeconds($gap), $last->addDay()->utc()->addSeconds($gap));
        $others = $this->otherChannelTimestamps($a, $first->utc()->subSeconds($gap), $last->addDay()->utc()->addSeconds($gap + self::NUDGE_MAX * 4));
        $slots = [];

        for ($day = $first; $day->lessThanOrEqualTo($last); $day = $day->addDay()->startOfDay()) {
            $remaining = $cap - $this->usedOn($a, $day->utc(), $day->addDay()->startOfDay()->utc());
            $daySlots = [];

            foreach ($this->dayPlan($a, $day) as $slot) {
                if ($remaining <= 0) {
                    break;
                }

                if ($slot->lessThan($from) || $slot->greaterThan($to)) {
                    continue;
                }

                if ($this->conflicts($busy, $slot->getTimestamp(), $gap)) {
                    continue;
                }

                // Kênh khác đã có bài sát giờ này: đẩy lùi 2..5 phút cho tới khi hết trùng (vẫn trong khung giờ và cách bài cùng kênh đủ xa).
                $ts = $this->clearOtherChannels($a, $slot->getTimestamp(), $others, $day->addMinutes((int) $a->window_end * 60)->getTimestamp());

                if ($ts === null || $ts > $to->getTimestamp() || $this->conflicts($busy, $ts, $gap)) {
                    continue;
                }

                $daySlots[] = CarbonImmutable::createFromTimestampUTC($ts);
                $busy[] = $ts;
                $others[] = $ts;
                $remaining--;
            }

            // Nâng daily_cap giữa chừng: lịch ngày được sinh lại nên nhiều giờ mới trùng giờ cũ, còn thiếu thì chèn vào khoảng trống lớn nhất.
            if ($remaining > 0 && $day->lessThan($to)) {
                $windowStart = $day->addMinutes((int) $a->window_start * 60)->getTimestamp();
                $windowEnd = $day->addMinutes((int) $a->window_end * 60)->getTimestamp() - 1;

                foreach ($this->fillGaps($a, max($from->getTimestamp(), $windowStart), min($to->getTimestamp(), $windowEnd), $remaining, $gap, $busy, $others) as $ts) {
                    $daySlots[] = CarbonImmutable::createFromTimestampUTC($ts);
                }
            }

            usort($daySlots, fn (CarbonImmutable $x, CarbonImmutable $y): int => $x->getTimestamp() <=> $y->getTimestamp());
            array_push($slots, ...$daySlots);
        }

        return $slots;
    }

    /**
     * Chèn tối đa $count giờ vào khoảng trống lớn nhất trong [$lower, $upper] (giây UTC), luôn cách mọi bài khác >= $gap.
     * $busy và $others được cập nhật tại chỗ.
     *
     * @param  list<int>  $busy
     * @param  list<int>  $others
     * @return list<int>
     */
    private function fillGaps(AutoAccount $a, int $lower, int $upper, int $count, int $gap, array &$busy, array &$others): array
    {
        $added = [];

        while ($count > 0 && $upper >= $lower) {
            $points = array_values(array_filter($busy, fn (int $t): bool => $t > $lower - $gap && $t < $upper + $gap));
            sort($points);
            array_unshift($points, $lower - $gap);
            $points[] = $upper + $gap;

            $best = null;
            $bestWidth = -1;

            for ($i = 0; $i < count($points) - 1; $i++) {
                $lo = max($points[$i] + $gap, $lower);
                $hi = min($points[$i + 1] - $gap, $upper);

                if ($hi < $lo || $hi - $lo <= $bestWidth) {
                    continue;
                }

                $ts = intdiv($lo + $hi, 2);
                $ts -= $ts % 60;

                if ($ts < $lo) {
                    $ts += 60;
                }

                if ($ts > $hi) {
                    continue;
                }

                $ts = $this->clearOtherChannels($a, $ts, $others, $hi + 1);

                if ($ts === null || $this->conflicts($busy, $ts, $gap)) {
                    continue;
                }

                $best = $ts;
                $bestWidth = $hi - $lo;
            }

            if ($best === null) {
                break;
            }

            $added[] = $best;
            $busy[] = $best;
            $others[] = $best;
            $count--;
        }

        return $added;
    }

    /**
     * @return array{created: int, failed: int, skipped: ?string}
     */
    private function planAccount(AutoAccount $auto, CarbonImmutable $now): array
    {
        $id = (string) $auto->social_account_id;

        // K4: gắn sai sản phẩm tệ hơn không gắn. Chưa có mã nào được chọn sản phẩm hợp lệ thì không xếp gì, giữ video trong kho.
        // Mẫu anchor KHÔNG bắt buộc: tiện ích tự dựng anchor mặc định, mẫu chỉ là thông tin.
        $cart = $this->cart->evaluate($id);

        foreach ($cart['warnings'] as $warning) {
            Log::warning('Tự động đăng: '.$warning, ['social_account_id' => $id]);
        }

        if ($cart['allowed'] === []) {
            return ['created' => 0, 'failed' => 0, 'skipped' => 'chưa có sản phẩm hub nào được chọn sản phẩm giỏ hàng hợp lệ'.($cart['warnings'] === [] ? '' : ': '.implode('; ', $cart['warnings']))];
        }

        $from = $now->addSeconds(self::MIN_LEAD)->startOfMinute()->addMinute();
        $slots = $this->slotsFor($auto, $from, $this->horizonFor($auto, $now));

        // Chặn số bài đã xếp mà chưa đăng: tránh tải quá nhiều bài hẹn giờ lên TikTok.
        $room = $this->futureRoom($auto, $now);

        if ($room <= 0) {
            return ['created' => 0, 'failed' => 0, 'skipped' => 'đã đủ '.max(1, (int) config('fork.auto.max_future_posts', 30)).' bài chờ đăng'];
        }

        $slots = array_slice($slots, 0, $room);

        if ($slots === []) {
            return ['created' => 0, 'failed' => 0, 'skipped' => 'không còn giờ trống'];
        }

        $social = SocialAccount::query()->with('workspace')->findOrFail($auto->social_account_id);
        $created = 0;
        $failed = 0;

        foreach ($slots as $slot) {
            $video = $this->library->reserveClaimed($social, $cart['allowed'], $slot);

            if ($video === null) {
                if ($this->library->claimBlock !== null) {
                    // An toàn trên hết: hub không xác nhận giữ chỗ thì không đăng, lượt sau thử lại.
                    Log::warning('Tự động đăng: không giữ chỗ được video trên hub, chưa xếp.', ['social_account_id' => $social->id, 'reason' => $this->library->claimBlock]);

                    return ['created' => $created, 'failed' => $failed, 'skipped' => 'chưa giữ chỗ được video trên hub: '.$this->library->claimBlock];
                }

                Log::info('Tự động đăng: hết video cho tài khoản.', ['social_account_id' => $social->id]);

                return ['created' => $created, 'failed' => $failed, 'skipped' => $created === 0 ? 'hết video' : null];
            }

            try {
                $caption = $this->captions->captionFor($video);
                $this->builder->build($social, $video, $caption, $slot);
                $created++;
            } catch (MissingVideoFile|CaptionRefused $e) {
                // Lỗi của riêng video này (file biến mất, caption không hợp lệ): thử lại cũng vậy — đánh dấu lỗi để
                // người dùng thấy rồi xếp tiếp video khác, không để một video hỏng chặn cả kênh mãi.
                $this->library->fail($video, $e->getMessage());
                $failed++;
                Log::warning('Tự động đăng: '.$e->getMessage(), ['video_id' => $video->id]);
            } catch (Throwable $e) {
                $failed++;
                Log::error('Tự động đăng: tạo bài lỗi, trả video về kho.', ['video_id' => $video->id, 'error' => $e->getMessage()]);
                $this->safeRelease($video, 'Tạo bài lỗi: '.mb_substr($e->getMessage(), 0, 200));

                // Lỗi có thể là của hệ thống (ổ đĩa, DB): dừng tài khoản này, lượt sau thử lại.
                break;
            }
        }

        return ['created' => $created, 'failed' => $failed, 'skipped' => null];
    }

    private function safeRelease(AutoVideo $video, string $reason): void
    {
        try {
            $this->library->release($video, $reason);
        } catch (Throwable $e) {
            report($e);
        }
    }

    public function ineligible(AutoAccount $auto): ?string
    {
        if (filled($auto->paused_reason)) {
            return 'đang tạm dừng: '.$auto->paused_reason;
        }

        $social = SocialAccount::query()->find($auto->social_account_id);

        if ($social === null || $social->platform !== Platform::TikTok) {
            return 'không phải tài khoản TikTok';
        }

        if ($social->status !== AccountStatus::Connected) {
            return 'tài khoản chưa kết nối';
        }

        $chrome = ChromeAccount::query()->where('social_account_id', $social->id)->where('enabled', true)->exists();

        return $chrome ? null : 'chưa bật đăng qua Chrome';
    }

    // ---------------------------------------------------------------- Sinh giờ trong một ngày

    /**
     * Giờ đăng (UTC, đã sắp xếp, đã giữ khoảng cách tối thiểu) của một ngày địa phương.
     *
     * @return list<CarbonImmutable>
     */
    private function dayPlan(AutoAccount $a, CarbonImmutable $day): array
    {
        $cap = max(0, (int) $a->daily_cap);
        $startHour = max(0, min(24, (int) $a->window_start));
        $endHour = max(0, min(24, (int) $a->window_end));

        if ($cap === 0 || $endHour <= $startHour) {
            return [];
        }

        $start = $day->startOfDay()->addMinutes($startHour * 60);
        $minutes = ($endHour - $startHour) * 60;
        $endTs = $start->addMinutes($minutes)->getTimestamp();
        $gap = $this->gapSeconds();
        $jitter = max(0, (int) config('fork.auto.jitter_minutes', 7));
        $rand = new Randomizer(new Mt19937(crc32($a->social_account_id.'|'.$day->format('Y-m-d'))));

        $offsets = []; // phút kể từ đầu khung
        $preferred = 0;
        $hours = $this->preferredHours($a, $startHour, $endHour);

        if ($a->mode === 'optimized' && $hours !== []) {
            $ratio = min(1.0, max(0.0, (float) $a->explore_ratio));
            $perHourMax = max(1, intdiv(3600, $gap));
            $preferred = min((int) round($cap * (1 - $ratio)), count($hours) * $perHourMax);

            $perHour = array_fill_keys($hours, 0);
            for ($k = 0; $k < $preferred; $k++) {
                $perHour[$hours[$k % count($hours)]]++;
            }

            foreach ($perHour as $hour => $count) {
                $width = $count > 0 ? intdiv(60, $count) : 60;
                for ($j = 0; $j < $count; $j++) {
                    $offsets[] = ($hour - $startHour) * 60 + $j * $width + $rand->getInt(0, max(0, $width - 1));
                }
            }
        }

        $explore = $cap - $preferred;
        for ($i = 0; $i < $explore; $i++) {
            $offsets[] = (int) round(($i + 0.5) * $minutes / $explore + $rand->getInt(-$jitter, $jitter));
        }

        sort($offsets);
        $plan = [];
        $previous = null;

        foreach ($offsets as $offset) {
            $time = $start->addMinutes(max(0, min($minutes - 1, $offset)))->getTimestamp();

            if ($previous !== null && $time < $previous + $gap) {
                $time = $previous + $gap;
            }

            if ($time >= $endTs) {
                break;
            }

            $previous = $time;
            $plan[] = CarbonImmutable::createFromTimestampUTC($time);
        }

        return $plan;
    }

    /**
     * @return list<int>
     */
    private function preferredHours(AutoAccount $a, int $startHour, int $endHour): array
    {
        return collect((array) $a->preferred_hours)
            ->filter(fn (mixed $h): bool => is_numeric($h))
            ->map(fn (mixed $h): int => (int) $h)
            ->filter(fn (int $h): bool => $h >= $startHour && $h < $endHour)
            ->unique()
            ->sort()
            ->values()
            ->all();
    }

    // ---------------------------------------------------------------- Dữ liệu đã có

    public function timezoneFor(AutoAccount $a): DateTimeZone
    {
        $name = SocialAccount::query()->whereKey($a->social_account_id)->value('timezone');

        try {
            return new DateTimeZone(filled($name) ? (string) $name : self::DEFAULT_TIMEZONE);
        } catch (Throwable) {
            return new DateTimeZone(self::DEFAULT_TIMEZONE);
        }
    }

    public function gapSeconds(): int
    {
        return max(1, (int) config('fork.auto.min_gap_minutes', 20)) * 60;
    }

    private function usedOn(AutoAccount $a, CarbonImmutable $from, CarbonImmutable $to): int
    {
        return AutoVideo::query()
            ->where('social_account_id', $a->social_account_id)
            ->whereIn('status', self::COUNTED)
            // Cùng mốc với trần bài/ngày của VideoLibrary: bài "đăng ngay" (scheduled_for null) cũng tính.
            ->whereRaw('COALESCE(scheduled_for, posted_at, updated_at) >= ? AND COALESCE(scheduled_for, posted_at, updated_at) < ?', [$from, $to])
            ->count();
    }

    /**
     * Mốc thời gian của mọi bài đã xếp trong khoảng: video tự động và cả bài TikTok khác đang hẹn giờ.
     *
     * @return list<int>
     */
    private function busyTimestamps(AutoAccount $a, CarbonImmutable $from, CarbonImmutable $to): array
    {
        $videos = AutoVideo::query()
            ->where('social_account_id', $a->social_account_id)
            ->whereIn('status', self::COUNTED)
            ->whereBetween('scheduled_for', [$from, $to])
            ->pluck('scheduled_for');

        $posts = Post::query()
            ->where('social_account_id', $a->social_account_id)
            ->where('status', PostStatus::Scheduled)
            ->whereBetween('scheduled_at', [$from, $to])
            ->pluck('scheduled_at');

        return $videos->merge($posts)
            ->filter()
            ->map(fn ($t): int => CarbonImmutable::parse($t)->getTimestamp())
            ->values()
            ->all();
    }

    /**
     * Mốc thời gian bài đã xếp của CÁC KÊNH KHÁC (video tự động và bài TikTok Auto Kid hẹn giờ), để hai kênh không đăng cùng lúc.
     *
     * @return list<int>
     */
    private function otherChannelTimestamps(AutoAccount $a, CarbonImmutable $from, CarbonImmutable $to): array
    {
        $videos = AutoVideo::query()
            ->where('social_account_id', '!=', $a->social_account_id)
            ->whereIn('status', self::COUNTED)
            ->whereBetween('scheduled_for', [$from, $to])
            ->pluck('scheduled_for');

        $posts = Post::query()
            ->where('social_account_id', '!=', $a->social_account_id)
            ->where('status', PostStatus::Scheduled)
            ->whereBetween('scheduled_at', [$from, $to])
            ->pluck('scheduled_at');

        return $videos->merge($posts)
            ->filter()
            ->map(fn ($t): int => CarbonImmutable::parse($t)->getTimestamp())
            ->values()
            ->all();
    }

    /**
     * Đẩy giờ lùi 2..5 phút (ngẫu nhiên theo hạt giống cố định, nên chạy lại cho cùng kết quả) cho tới khi cách mọi kênh khác ít nhất 2 phút.
     * null nếu vượt quá giờ kết thúc khung.
     *
     * @param  list<int>  $others
     */
    private function clearOtherChannels(AutoAccount $a, int $ts, array $others, int $endTs): ?int
    {
        if (! $this->conflictsWithin($others, $ts, self::CHANNEL_CLEARANCE)) {
            return $ts;
        }

        $rand = new Randomizer(new Mt19937(crc32($a->social_account_id.'|nudge|'.$ts)));

        for ($i = 0; $i < 8; $i++) {
            $ts += $rand->getInt(self::NUDGE_MIN, self::NUDGE_MAX);

            if ($ts >= $endTs) {
                return null;
            }

            if (! $this->conflictsWithin($others, $ts, self::CHANNEL_CLEARANCE)) {
                return $ts;
            }
        }

        return null;
    }

    /**
     * @param  list<int>  $times
     */
    private function conflictsWithin(array $times, int $ts, int $seconds): bool
    {
        foreach ($times as $other) {
            if (abs($other - $ts) < $seconds) {
                return true;
            }
        }

        return false;
    }

    /**
     * @param  list<int>  $busy
     */
    private function conflicts(array $busy, int $timestamp, int $gap): bool
    {
        foreach ($busy as $other) {
            if (abs($other - $timestamp) < $gap) {
                return true;
            }
        }

        return false;
    }
}

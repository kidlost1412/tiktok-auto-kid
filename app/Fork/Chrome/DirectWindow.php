<?php

declare(strict_types=1);

namespace App\Fork\Chrome;

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Platform;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * "Khung giờ đăng thẳng" (tuỳ chọn, mặc định TẮT): trong khung (vd 8:00–17:00 thứ 2–6, lúc máy công ty bật) bài KHÔNG
 * được gửi trước lên TikTok dưới dạng hẹn giờ; tới giờ Chrome đăng ngay (đường đăng 'now' có sẵn). Ngoài khung giữ
 * nguyên cách cũ: gửi trước, TikTok giữ lịch. Nhờ vậy bài trong khung vẫn nằm trong app tới phút chót, sửa/xoá thoải mái.
 *
 * - margin_minutes: bài trong N phút cuối khung coi như ngoài khung (hẹn trước), để không kẹt lúc tắt máy.
 * - catch_up_minutes: máy tắt / Chrome đóng lúc tới giờ: khi bật lại, bài trễ không quá N phút thì đăng bù (từng bài
 *   một theo kênh); trễ hơn thì dời sang giờ trống kế tiếp của kênh.
 * - off_channels: kênh không áp khung (vẫn hẹn hết như cũ).
 */
final class DirectWindow
{
    public const string KEY = 'chrome.direct_window';

    /** Bài đăng thẳng sắp tới giờ trong chừng này giây: kênh không nhận việc gửi bài hẹn mới (ưu tiên bài đăng thẳng). */
    public const int PRIORITY_SECONDS = 10 * 60;

    public const array DEFAULTS = [
        'enabled' => false,
        'start' => '08:00',
        'end' => '17:00',
        'days' => [1, 2, 3, 4, 5],
        'margin_minutes' => 40,
        'catch_up_minutes' => 120,
        'off_channels' => [],
    ];

    /** @return array{enabled: bool, start: string, end: string, days: list<int>, margin_minutes: int, catch_up_minutes: int, off_channels: list<string>} */
    public static function get(): array
    {
        $raw = json_decode((string) AutoSetting::read(self::KEY, '{}'), true);

        return self::normalize(is_array($raw) ? $raw : []);
    }

    /** @param array<string, mixed> $input */
    public static function save(array $input): array
    {
        $s = self::normalize(array_merge(self::get(), $input));
        AutoSetting::write(self::KEY, (string) json_encode($s));

        return $s;
    }

    /**
     * @param  array<string, mixed>  $raw
     * @return array{enabled: bool, start: string, end: string, days: list<int>, margin_minutes: int, catch_up_minutes: int, off_channels: list<string>}
     */
    public static function normalize(array $raw): array
    {
        $d = self::DEFAULTS;
        $time = fn (mixed $v, string $def): string => is_string($v) && preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $v) ? $v : $def;
        $days = array_values(array_unique(array_filter(array_map('intval', (array) ($raw['days'] ?? $d['days'])), fn (int $x): bool => $x >= 1 && $x <= 7)));
        sort($days);

        return [
            'enabled' => (bool) ($raw['enabled'] ?? $d['enabled']),
            'start' => $time($raw['start'] ?? null, $d['start']),
            'end' => $time($raw['end'] ?? null, $d['end']),
            'days' => $days,
            'margin_minutes' => max(0, min(180, (int) ($raw['margin_minutes'] ?? $d['margin_minutes']))),
            'catch_up_minutes' => max(0, min(720, (int) ($raw['catch_up_minutes'] ?? $d['catch_up_minutes']))),
            'off_channels' => array_values(array_unique(array_map('strval', array_filter((array) ($raw['off_channels'] ?? []), 'is_scalar')))),
        ];
    }

    /** Giờ đăng này (của kênh này) nằm trong khung đăng thẳng? */
    public static function covers(string $accountId, ?\DateTimeInterface $at, ?array $s = null): bool
    {
        $s ??= self::get();

        if (! $s['enabled'] || $at === null || in_array($accountId, $s['off_channels'], true)) {
            return false;
        }

        $local = CarbonImmutable::instance($at)->setTimezone(Planner::zone());

        if (! in_array($local->dayOfWeekIso, $s['days'], true)) {
            return false;
        }

        $min = $local->hour * 60 + $local->minute;
        [$sh, $sm] = array_map('intval', explode(':', $s['start']));
        [$eh, $em] = array_map('intval', explode(':', $s['end']));

        return $min >= $sh * 60 + $sm && $min < $eh * 60 + $em - $s['margin_minutes'];
    }

    /**
     * Có bài đăng thẳng của kênh tới giờ (hoặc đã quá giờ mà chưa giao Chrome) trong PRIORITY_SECONDS tới?
     * Khi đó không giao việc tải bài hẹn tối lên TikTok cho kênh, để bài đăng thẳng không phải xếp hàng sau.
     */
    public function dueSoon(string $accountId, CarbonImmutable $now): bool
    {
        $s = self::get();

        if (! $s['enabled'] || in_array($accountId, $s['off_channels'], true)) {
            return false;
        }

        $posts = Post::query()
            ->where('social_account_id', $accountId)
            ->where('platform', Platform::TikTok)
            ->whereIn('status', [PostStatus::Scheduled, PostStatus::Publishing])
            ->whereBetween('scheduled_at', [$now->subSeconds(max(60, $s['catch_up_minutes'] * 60)), $now->addSeconds(self::PRIORITY_SECONDS)])
            ->whereNotIn('id', ChromeJob::query()->where('mode', 'scheduled')->whereIn('state', ['posted', 'authorized', 'uncertain'])->select('post_id'))
            ->get(['id', 'scheduled_at']);

        return $posts->contains(fn (Post $p): bool => self::covers($accountId, $p->scheduled_at, $s));
    }

    /**
     * Máy vừa bật lại sau khi tắt: bài đăng thẳng trễ quá catch_up_minutes (chưa từng giao Chrome) được dời sang giờ
     * trống kế tiếp của kênh thay vì đăng dồn. Gọi ngay trước khi đưa bài tới giờ vào hàng đợi đăng.
     *
     * @return int số bài đã dời
     */
    public function deferStale(?CarbonImmutable $now = null): int
    {
        $s = self::get();

        if (! $s['enabled']) {
            return 0;
        }

        $now ??= CarbonImmutable::now();
        $limit = $now->subMinutes($s['catch_up_minutes']);
        $moved = 0;

        $posts = Post::query()
            ->where('platform', Platform::TikTok)
            ->where('status', PostStatus::Scheduled)
            ->where('scheduled_at', '<', $limit)
            ->where('scheduled_at', '>', $now->subDays(3))
            ->whereNotIn('id', ChromeJob::query()->select('post_id'))
            ->orderBy('scheduled_at')
            ->limit(200)
            ->get();

        foreach ($posts as $post) {
            if (! self::covers((string) $post->social_account_id, $post->scheduled_at, $s)) {
                continue;
            }

            $video = AutoVideo::query()->where('post_id', $post->id)->where('status', AutoVideo::SCHEDULED)->first();
            $auto = AutoAccount::query()->find($post->social_account_id);

            // Chỉ dời bài do app tự xếp (có video, kênh còn tự động). Bài tạo tay: để nguyên, đăng như cũ.
            if ($video === null || $auto === null) {
                continue;
            }

            $planner = app(Planner::class);
            $slot = $planner->slotsFor($auto, $now->addMinutes(10), $planner->horizonFor($auto, $now))[0] ?? null;

            if ($slot === null) {
                continue;
            }

            $from = CarbonImmutable::instance($post->scheduled_at);

            DB::transaction(function () use ($post, $video, $slot, $from): void {
                $meta = $post->meta ?? [];
                $meta['fork_direct_deferred_from'] = $from->toIso8601String();
                $post->forceFill(['scheduled_at' => $slot, 'meta' => $meta])->save();
                $video->forceFill(['scheduled_for' => $slot])->save();
            });

            Log::info('Đăng thẳng: máy tắt quá lâu lúc tới giờ, dời bài sang giờ trống kế tiếp.', [
                'post_id' => $post->id, 'from' => $from->toIso8601String(), 'to' => $slot->toIso8601String(),
            ]);
            $moved++;
        }

        return $moved;
    }
}

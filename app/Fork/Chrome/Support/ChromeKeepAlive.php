<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Support;

use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeClient;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;

/**
 * "Giữ Chrome luôn chạy nền": quyết định khi nào trợ lý Windows phải mở lại profile Chrome
 * (không cửa sổ) dù không có bài nào đang chờ, để tiện ích còn thu số liệu và bình luận.
 *
 * Quy tắc: tiện ích im lặng quá STALE giây; không mở lại thường hơn BACKOFF giây;
 * sau MAX_FAILURES lần mở mà tiện ích không báo về thì dừng và báo lỗi
 * (bấm "Mở Chrome nền ngay" để thử lại).
 */
final class ChromeKeepAlive
{
    public const int STALE = 180;

    public const int BACKOFF = 300;

    public const int MAX_FAILURES = 5;

    public const string LAUNCHER_SEEN_KEY = 'fork:chrome:launcher_seen';

    public const string BROWSER_SETTINGS_KEY = 'fork:chrome:browser_settings';

    /** Sau khi mở, chờ tiện ích báo về trong khoảng này trước khi coi là hỏng. */
    private const int GRACE = 120;

    /**
     * Danh sách profile cần mở nền (ngoài các yêu cầu mở vì có bài chờ).
     *
     * @param  list<int>  $excludeClientIds
     * @return list<array{client_id: int, profile_dir: string, browser: string, reason: string}>
     */
    public function requests(?CarbonImmutable $now = null, array $excludeClientIds = []): array
    {
        $now ??= CarbonImmutable::now();
        $out = [];
        $seenProfiles = [];

        $clients = ChromeClient::query()
            ->whereNull('revoked_at')
            ->whereNotNull('chrome_profile_dir')
            ->where('chrome_profile_dir', '!=', '')
            ->orderByDesc('last_seen_at')
            ->get();

        foreach ($clients as $c) {
            $this->reconcile($c);
            $manual = $c->keepalive_requested_at !== null;

            if (in_array($c->id, $excludeClientIds, true) || $this->online($c, $now)) {
                continue;
            }

            if (! $manual) {
                if (! $c->keep_alive || $this->silentFor($c, $now) < self::STALE) {
                    continue;
                }
                if ($this->effectiveFailures($c, $now) >= self::MAX_FAILURES) {
                    continue;
                }
                $last = $this->lastAttempt($c);
                if ($last !== null && $last->greaterThan($now->subSeconds(self::BACKOFF))) {
                    continue;
                }
            }

            // Mỗi profile chỉ mở một lần mỗi vòng.
            $key = ($c->chrome_browser ?: 'chrome').'|'.$c->chrome_profile_dir;
            if (isset($seenProfiles[$key])) {
                continue;
            }
            $seenProfiles[$key] = true;

            // Ghi nhận lần mở trước đã hỏng (nếu có) rồi đánh dấu lần mở mới ngay lúc giao việc,
            // để thời gian chờ có tác dụng kể cả khi trợ lý không kịp báo lại.
            $this->countPending($c, $now);
            $c->forceFill(['keepalive_last_start_at' => $now, 'keepalive_requested_at' => null])->save();

            $out[] = [
                'client_id' => (int) $c->id,
                'profile_dir' => (string) $c->chrome_profile_dir,
                'browser' => $c->chrome_browser ?: 'chrome',
                'reason' => $manual ? 'manual' : 'keepalive',
            ];
        }

        return $out;
    }

    /** Trợ lý báo kết quả một lần mở nền. */
    public function recordResult(int $clientId, bool $ok, ?string $error): bool
    {
        $c = ChromeClient::query()->whereKey($clientId)->first();

        if (! $c instanceof ChromeClient) {
            return false;
        }

        $now = CarbonImmutable::now();
        $c->forceFill([
            'keepalive_last_start_at' => $now,
            'keepalive_error' => $ok ? null : mb_substr(trim((string) $error) !== '' ? trim((string) $error) : 'Không mở được trình duyệt.', 0, 250),
        ]);

        if ($ok) {
            $c->last_launch_at = $now;
        }

        $c->save();

        return true;
    }

    /** Nút "Mở Chrome nền ngay": thử lại ngay, xoá bộ đếm lỗi. */
    public function requestNow(ChromeClient $c): void
    {
        $c->forceFill([
            'keepalive_requested_at' => CarbonImmutable::now(),
            'keepalive_failures' => 0,
            'keepalive_error' => null,
        ])->save();
    }

    public function markLauncherSeen(): void
    {
        Cache::put(self::LAUNCHER_SEEN_KEY, time(), 86400);
    }

    public function launcherAlive(): bool
    {
        return time() - (int) Cache::get(self::LAUNCHER_SEEN_KEY, 0) < 120;
    }

    /**
     * Trạng thái hiển thị trên trang Kết nối Chrome.
     * state: running | starting | failed | waiting | launcher_down | off | no_profile
     *
     * @return array{state: string, message: string|null, last_start_at: string|null, failures: int}
     */
    public function state(ChromeClient $c, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $this->reconcile($c);
        $failures = $this->effectiveFailures($c, $now);
        $start = $c->keepalive_last_start_at;
        $seenSinceStart = $start !== null && $c->last_seen_at !== null && $c->last_seen_at->greaterThanOrEqualTo($start);

        $state = match (true) {
            $this->online($c, $now) => 'running',
            blank($c->chrome_profile_dir) => 'no_profile',
            $failures >= self::MAX_FAILURES => 'failed',
            $c->keepalive_requested_at !== null => 'starting',
            filled($c->keepalive_error) => 'failed',
            $start !== null && ! $seenSinceStart && $start->greaterThan($now->subSeconds(self::GRACE)) => 'starting',
            ! $c->keep_alive => 'off',
            ! $this->launcherAlive() => 'launcher_down',
            default => 'waiting',
        };

        $message = match ($state) {
            'failed' => $failures >= self::MAX_FAILURES
                ? 'Đã thử mở '.self::MAX_FAILURES.' lần nhưng tiện ích không báo về'.(filled($c->keepalive_error) ? ' ('.$c->keepalive_error.')' : '').'. App đã dừng thử; bấm "Mở Chrome nền ngay" để thử lại.'
                : (string) $c->keepalive_error,
            'launcher_down' => 'Trợ lý mở Chrome (dịch vụ chrome-launcher) chưa chạy nên app chưa tự mở được Chrome.',
            default => null,
        };

        return [
            'state' => $state,
            'message' => $message,
            'last_start_at' => $this->lastAttempt($c)?->toIso8601String(),
            'failures' => $failures,
        ];
    }

    /** Tiện ích đã báo về sau lần mở gần nhất: xoá lỗi và bộ đếm. */
    public function reconcile(ChromeClient $c): void
    {
        if (($c->keepalive_failures > 0 || filled($c->keepalive_error))
            && $this->online($c, CarbonImmutable::now())
            && ($c->keepalive_last_start_at === null || $c->last_seen_at->greaterThanOrEqualTo($c->keepalive_last_start_at))) {
            $c->forceFill(['keepalive_failures' => 0, 'keepalive_error' => null])->save();
        }
    }

    private function online(ChromeClient $c, CarbonImmutable $now): bool
    {
        return $c->last_seen_at !== null && $c->last_seen_at->greaterThan($now->subSeconds(ChromeJobs::ONLINE_WINDOW));
    }

    private function silentFor(ChromeClient $c, CarbonImmutable $now): int
    {
        return $c->last_seen_at === null ? PHP_INT_MAX : max(0, (int) $c->last_seen_at->diffInSeconds($now, true));
    }

    private function lastAttempt(ChromeClient $c): ?CarbonImmutable
    {
        $times = array_filter([$c->keepalive_last_start_at, $c->last_launch_at]);

        return $times === [] ? null : CarbonImmutable::instance(max($times));
    }

    /** Lần mở trước đã quá hạn chờ mà tiện ích vẫn chưa báo về (và chưa được đếm). */
    private function pendingUncounted(ChromeClient $c, CarbonImmutable $now): bool
    {
        $start = $c->keepalive_last_start_at;

        return $start !== null
            && $start->lessThan($now->subSeconds(self::GRACE))
            && ($c->last_seen_at === null || $c->last_seen_at->lessThan($start));
    }

    private function effectiveFailures(ChromeClient $c, CarbonImmutable $now): int
    {
        return (int) $c->keepalive_failures + ($this->pendingUncounted($c, $now) ? 1 : 0);
    }

    /** Cộng một lỗi cho lần mở trước. Gọi ngay trước khi đổi keepalive_last_start_at nên không đếm trùng. */
    private function countPending(ChromeClient $c, CarbonImmutable $now): void
    {
        if (! $this->pendingUncounted($c, $now)) {
            return;
        }

        $c->forceFill([
            'keepalive_failures' => (int) $c->keepalive_failures + 1,
            'keepalive_error' => $c->keepalive_error ?: 'Tiện ích chưa báo về sau khi mở',
        ])->save();
    }
}

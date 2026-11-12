<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Support;

use App\Fork\Chrome\Models\ChromeClient;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Cache;

/**
 * Profile trình duyệt (Chrome hoặc Edge) mà trợ lý mở trình duyệt (Windows) báo lên, và việc gán profile
 * cho từng Chrome đã ghép nối. Mỗi kênh phải ứng với một profile riêng; một profile là cặp (trình duyệt, thư mục).
 */
final class ChromeProfiles
{
    public const string CACHE_KEY = 'fork:chrome:profiles';

    public const array BROWSERS = ['chrome', 'edge'];

    public static function normalizeBrowser(?string $browser): string
    {
        $browser = mb_strtolower(trim((string) $browser));

        return in_array($browser, self::BROWSERS, true) ? $browser : 'chrome';
    }

    /**
     * @return list<array{browser: string, dir: string, name: string, has_extension: bool, bundle_extension: bool, tiktok_username: string|null}>
     */
    public static function reported(): array
    {
        return array_values(array_map(fn (array $p): array => [
            'browser' => self::normalizeBrowser($p['browser'] ?? null),
            'dir' => (string) $p['dir'],
            'name' => (string) ($p['name'] ?? $p['dir']),
            'has_extension' => (bool) ($p['has_extension'] ?? false),
            'bundle_extension' => (bool) ($p['bundle_extension'] ?? false),
            'tiktok_username' => filled($p['tiktok_username'] ?? null) ? ltrim((string) $p['tiktok_username'], '@') : null,
        ], array_filter((array) Cache::get(self::CACHE_KEY, []), fn ($p): bool => is_array($p) && isset($p['dir']))));
    }

    /**
     * Profile còn trống để gán cho một Chrome: bỏ profile đã gán cho Chrome khác. Thứ tự ưu tiên của nhóm còn lại:
     * profile báo đúng tên TikTok của Chrome này > profile cài tiện ích từ chính thư mục của bản cài này >
     * profile có cài tiện ích > mọi profile (Chrome chưa cài tiện ích thì không thể là kênh).
     *
     * @return list<array{browser: string, dir: string}>
     */
    public static function candidates(string $accountId, ?ChromeClient $for = null): array
    {
        $taken = self::clients($accountId)
            ->filter(fn (ChromeClient $c): bool => filled($c->chrome_profile_dir) && $c->id !== $for?->id)
            ->map(fn (ChromeClient $c): string => self::key($c->chrome_browser, (string) $c->chrome_profile_dir))
            ->all();

        $free = array_values(array_filter(
            self::reported(),
            fn (array $p): bool => ! in_array(self::key($p['browser'], $p['dir']), $taken, true),
        ));

        $username = $for ? mb_strtolower(ltrim((string) $for->tiktok_username, '@')) : '';
        $tiers = [
            $username !== '' ? fn (array $p): bool => mb_strtolower((string) $p['tiktok_username']) === $username : null,
            fn (array $p): bool => $p['bundle_extension'],
            fn (array $p): bool => $p['has_extension'],
        ];

        foreach (array_filter($tiers) as $match) {
            $hit = array_values(array_filter($free, $match));

            if ($hit !== []) {
                $free = $hit;
                break;
            }
        }

        return array_map(fn (array $p): array => ['browser' => $p['browser'], 'dir' => $p['dir']], $free);
    }

    /**
     * Tự gán khi không còn gì để chọn. Với mỗi Chrome chưa có profile: nếu đúng một profile báo cùng tên TikTok
     * thì gán; nếu không, chỉ gán khi đúng một Chrome chưa có profile và đúng một profile ứng viên.
     * Trả true nếu đã gán ít nhất một Chrome.
     */
    public static function autoAssign(string $accountId): bool
    {
        $assigned = false;

        foreach (self::clients($accountId)->filter(fn (ChromeClient $c): bool => blank($c->chrome_profile_dir)) as $client) {
            $username = mb_strtolower(ltrim((string) $client->tiktok_username, '@'));
            $byName = $username === '' ? [] : array_values(array_filter(
                self::candidates($accountId, $client),
                fn (array $c): bool => self::reportedUsername($c['browser'], $c['dir']) === $username,
            ));

            if (count($byName) === 1) {
                $client->update(['chrome_browser' => $byName[0]['browser'], 'chrome_profile_dir' => $byName[0]['dir']]);
                $assigned = true;
            }
        }

        $unassigned = self::clients($accountId)->filter(fn (ChromeClient $c): bool => blank($c->chrome_profile_dir));
        $candidates = self::candidates($accountId);

        if ($unassigned->count() !== 1 || count($candidates) !== 1) {
            return $assigned;
        }

        $unassigned->first()->update(['chrome_browser' => $candidates[0]['browser'], 'chrome_profile_dir' => $candidates[0]['dir']]);

        return true;
    }

    /**
     * Chrome khác (cùng chủ) đang dùng cùng profile này, nếu có.
     */
    public static function conflictFor(ChromeClient $client): ?ChromeClient
    {
        if (blank($client->chrome_profile_dir)) {
            return null;
        }

        $mine = self::key($client->chrome_browser, (string) $client->chrome_profile_dir);

        return self::clients((string) $client->account_id)
            ->first(fn (ChromeClient $c): bool => $c->id !== $client->id
                && self::key($c->chrome_browser, (string) $c->chrome_profile_dir) === $mine);
    }

    public static function key(?string $browser, string $dir): string
    {
        return self::normalizeBrowser($browser).'|'.mb_strtolower($dir);
    }

    private static function reportedUsername(string $browser, string $dir): string
    {
        foreach (self::reported() as $p) {
            if ($p['browser'] === $browser && $p['dir'] === $dir) {
                return mb_strtolower((string) $p['tiktok_username']);
            }
        }

        return '';
    }

    /**
     * @return Collection<int, ChromeClient>
     */
    private static function clients(string $accountId): Collection
    {
        return ChromeClient::query()
            ->where('account_id', $accountId)
            ->whereNull('revoked_at')
            ->orderBy('id')
            ->get();
    }
}

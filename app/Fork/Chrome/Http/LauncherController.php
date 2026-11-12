<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Http;

use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Support\ChromeKeepAlive;
use App\Fork\Chrome\Support\ChromeProfiles;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;

final class LauncherController extends Controller
{
    public const PROFILES_KEY = 'fork:chrome:profiles';

    /**
     * requests = mở vì có bài đang chờ; keepalive = "Giữ Chrome luôn chạy nền" (tiện ích im lặng quá lâu
     * hoặc người dùng bấm "Mở Chrome nền ngay"). Cả hai mở profile không cửa sổ.
     */
    public function launchRequests(ChromeJobs $jobs, ChromeKeepAlive $keepAlive): JsonResponse
    {
        $keepAlive->markLauncherSeen();
        $requests = $jobs->launchRequests();
        $exclude = array_map(fn (array $r): int => (int) $r['client_id'], $requests);

        return response()->json([
            'ok' => true,
            'requests' => $requests,
            'keepalive' => $keepAlive->requests(null, $exclude),
        ]);
    }

    public function keepaliveResult(Request $request, ChromeKeepAlive $keepAlive): JsonResponse
    {
        $data = $request->validate([
            'client_id' => ['required', 'integer'],
            'ok' => ['required', 'boolean'],
            'error' => ['nullable', 'string', 'max:500'],
        ]);

        if (! $keepAlive->recordResult((int) $data['client_id'], (bool) $data['ok'], $data['error'] ?? null)) {
            return response()->json(['ok' => false, 'error' => 'not_found', 'message' => 'Không có Chrome này.'], 404);
        }

        return response()->json(['ok' => true]);
    }

    public function launched(Request $request, ChromeJobs $jobs): JsonResponse
    {
        $data = $request->validate([
            'client_id' => ['required', 'integer'],
            'job_id' => ['required', 'string', 'max:64'],
        ]);

        if (! ChromeClient::query()->whereKey($data['client_id'])->exists()) {
            return response()->json(['ok' => false, 'error' => 'not_found', 'message' => 'Không có Chrome này.'], 404);
        }

        $jobs->markLaunched((int) $data['client_id'], $data['job_id']);

        return response()->json(['ok' => true]);
    }

    public function profiles(Request $request): JsonResponse
    {
        $data = $request->validate([
            'profiles' => ['present', 'array', 'max:200'],
            'browser_settings' => ['nullable', 'array'],
            'browser_settings.chrome.background_mode' => ['nullable', 'boolean'],
            'browser_settings.edge.background_mode' => ['nullable', 'boolean'],
            'profiles.*.dir' => ['required', 'string', 'regex:/^(Default|Profile \d+|[A-Za-z0-9 _.\-]{1,64})$/'],
            'profiles.*.name' => ['nullable', 'string', 'max:128'],
            'profiles.*.has_extension' => ['nullable', 'boolean'],
            'profiles.*.browser' => ['nullable', 'string', 'in:chrome,edge'],
            'profiles.*.bundle_extension' => ['nullable', 'boolean'],
            'profiles.*.extension_id' => ['nullable', 'string', 'regex:/^[a-p]{32}$/'],
            'profiles.*.tiktok_username' => ['nullable', 'string', 'max:128'],
        ]);

        $profiles = collect($data['profiles'])
            ->map(fn (array $p): array => [
                'dir' => $p['dir'],
                'name' => (string) ($p['name'] ?? $p['dir']),
                'browser' => ChromeProfiles::normalizeBrowser($p['browser'] ?? null),
                'has_extension' => (bool) ($p['has_extension'] ?? false),
                'bundle_extension' => (bool) ($p['bundle_extension'] ?? false),
                'extension_id' => $p['extension_id'] ?? null,
                'tiktok_username' => $p['tiktok_username'] ?? null,
            ])
            ->values()
            ->all();

        Cache::put(self::PROFILES_KEY, $profiles, now()->addDay());

        // Chỉ đọc "Tiếp tục chạy ứng dụng nền" từ Local State; app không tự sửa cấu hình của Chrome.
        if (is_array($data['browser_settings'] ?? null)) {
            $settings = [];
            foreach (['chrome', 'edge'] as $browser) {
                $value = $data['browser_settings'][$browser]['background_mode'] ?? null;
                $settings[$browser] = ['background_mode' => $value === null ? null : (bool) $value];
            }
            Cache::put(ChromeKeepAlive::BROWSER_SETTINGS_KEY, $settings, now()->addDay());
        }

        // Chrome nào chưa có profile mà chỉ còn một lựa chọn thì gán luôn.
        ChromeClient::query()->whereNull('revoked_at')->whereNull('chrome_profile_dir')
            ->distinct()->pluck('account_id')
            ->each(fn ($accountId) => ChromeProfiles::autoAssign((string) $accountId));

        return response()->json(['ok' => true, 'count' => count($profiles)]);
    }
}

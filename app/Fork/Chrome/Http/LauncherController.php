<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Http;

use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Support\ChromeProfiles;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;

final class LauncherController extends Controller
{
    public const PROFILES_KEY = 'fork:chrome:profiles';

    public function launchRequests(ChromeJobs $jobs): JsonResponse
    {
        return response()->json(['ok' => true, 'requests' => $jobs->launchRequests()]);
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

        // Chrome nào chưa có profile mà chỉ còn một lựa chọn thì gán luôn.
        ChromeClient::query()->whereNull('revoked_at')->whereNull('chrome_profile_dir')
            ->distinct()->pluck('account_id')
            ->each(fn ($accountId) => ChromeProfiles::autoAssign((string) $accountId));

        return response()->json(['ok' => true, 'count' => count($profiles)]);
    }
}

<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Http;

use App\Enums\SocialAccount\Platform;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeAccountLinker;
use App\Fork\Chrome\Support\ChromeProfiles;
use App\Fork\Notify\Telegram;
use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use App\Models\Workspace;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Inertia\Inertia;
use Inertia\Response;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

/**
 * Trang "Kết nối Chrome": ghép nối tiện ích TikTok Auto Kid, chọn tài khoản TikTok đăng
 * qua Chrome và xem các bài đã giao cho Chrome.
 */
final class ChromeSettingsController extends Controller
{
    private const string PROFILE_DIR_RE = '/^(Default|Profile \d+|[A-Za-z0-9 _.\-]{1,64})$/';

    public function index(Request $request): Response
    {
        $accountId = $this->authorizeOwner($request);

        // Chế độ một người dùng: kênh TikTok tự xuất hiện từ Chrome đã ghép nối, không cần "Kết nối kênh".
        ChromeAccountLinker::linkAll($accountId);

        // Chỉ có một Chrome chưa chọn profile và một profile ứng viên thì khỏi bắt chọn.
        ChromeProfiles::autoAssign($accountId);

        return Inertia::render('settings/fork/Chrome', [
            'pair' => fn (): ?array => $this->currentPair($accountId),
            'clients' => fn (): array => $this->clients($accountId),
            'accounts' => fn (): array => $this->accounts($accountId),
            'jobs' => fn (): array => $this->jobList($accountId),
            'profiles' => fn (): array => ChromeProfiles::reported(),
            'telegram' => fn (): array => ['configured' => Telegram::configured()],
            'extensionPath' => $this->extensionPath(),
            'serverUrl' => rtrim((string) config('app.url'), '/'),
            'hasWorkspace' => (bool) $request->user()?->current_workspace_id,
        ]);
    }

    public function jobs(Request $request): JsonResponse
    {
        $accountId = $this->authorizeOwner($request);

        return response()->json(['jobs' => $this->jobList($accountId)]);
    }

    public function pairCode(Request $request): RedirectResponse
    {
        $accountId = $this->authorizeOwner($request);

        app(ChromeJobs::class)->newPairCode($accountId);

        return back()->with('flash.success', 'Đã tạo mã ghép nối mới. Nhập mã này vào tiện ích TikTok Auto Kid trong 5 phút.');
    }

    public function updateClient(Request $request, int $client): RedirectResponse
    {
        $accountId = $this->authorizeOwner($request);
        $model = $this->findClient($accountId, $client);

        $dir = trim((string) $request->input('chrome_profile_dir', ''));

        if ($dir !== '' && ! self::validProfileDir($dir)) {
            return back()->with('flash.error', 'Tên profile Chrome không hợp lệ (ví dụ: Default hoặc Profile 1).');
        }

        $model->update([
            'chrome_profile_dir' => $dir === '' ? null : $dir,
            'chrome_browser' => $dir === '' ? null : ChromeProfiles::normalizeBrowser((string) $request->input('chrome_browser', 'chrome')),
        ]);

        $other = ChromeProfiles::conflictFor($model->refresh());

        if ($other) {
            return back()->with('flash.error', 'Đã lưu, nhưng profile này cũng đang gán cho "'.$other->label.'". Mỗi kênh cần một profile Chrome riêng.');
        }

        return back()->with('flash.success', 'Đã lưu profile Chrome.');
    }

    public function telegramTest(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        if (! Telegram::configured()) {
            return back()->with('flash.error', 'Chưa cấu hình Telegram: vào Cài đặt > Telegram để nhập token bot và chat id.');
        }

        return Telegram::send('✅ TikTok Auto Kid: tin thử. Telegram đã nối thành công.')
            ? back()->with('flash.success', 'Đã gửi tin thử, hãy kiểm tra Telegram.')
            : back()->with('flash.error', 'Gửi thất bại. Kiểm tra lại token bot và chat id (đã nhắn /start cho bot chưa?).');
    }

    public function revokeClient(Request $request, int $client): RedirectResponse
    {
        $accountId = $this->authorizeOwner($request);
        $model = $this->findClient($accountId, $client);

        $model->update(['revoked_at' => now()]);

        return back()->with('flash.success', 'Đã thu hồi kết nối Chrome này.');
    }

    public function toggleAccount(Request $request, string $socialAccount): RedirectResponse
    {
        $accountId = $this->authorizeOwner($request);

        $account = SocialAccount::query()
            ->whereIn('workspace_id', $this->workspaceIds($accountId))
            ->where('platform', Platform::TikTok->value)
            ->findOrFail($socialAccount);

        $chrome = ChromeAccount::query()->find($account->id);

        if ($chrome?->enabled) {
            $chrome->update(['enabled' => false]);

            return back()->with('flash.success', 'Đã tắt đăng qua Chrome cho @'.$account->username.'.');
        }

        $client = $this->clientForUsername($accountId, (string) $account->username);

        if (! $client) {
            return back()->with('flash.error', 'Mở Chrome đăng nhập đúng tài khoản rồi thử lại.');
        }

        ChromeAccount::query()->updateOrCreate(
            ['social_account_id' => $account->id],
            ['enabled' => true, 'tiktok_user_id' => $client->tiktok_user_id],
        );

        return back()->with('flash.success', 'Đã bật đăng qua Chrome cho @'.$account->username.'.');
    }

    public function accountFromClient(Request $request, int $client): RedirectResponse
    {
        $accountId = $this->authorizeOwner($request);
        $model = $this->findClient($accountId, $client);

        $workspace = $request->user()?->currentWorkspace;

        if (! $workspace instanceof Workspace || $workspace->account_id !== $accountId) {
            return back()->with('flash.error', 'Hãy chọn một không gian làm việc trước.');
        }

        $userId = (string) $model->tiktok_user_id;
        $username = ltrim((string) $model->tiktok_username, '@');

        if ($userId === '' || $username === '') {
            return back()->with('flash.error', 'Mở Chrome đăng nhập đúng tài khoản rồi thử lại.');
        }

        ChromeAccountLinker::create($workspace, $userId, $username);

        return back()->with('flash.success', 'Đã thêm tài khoản @'.$username.' (chỉ đăng qua Chrome).');
    }

    public static function validProfileDir(string $value): bool
    {
        return preg_match(self::PROFILE_DIR_RE, $value) === 1
            && trim($value, ' .') === $value
            && ! in_array($value, ['.', '..'], true);
    }

    /**
     * Trả id Account của chủ tài khoản; 403 nếu không phải chủ hoặc không tự host.
     */
    private function authorizeOwner(Request $request): string
    {
        abort_unless(
            $request->user()?->isAccountOwner(),
            SymfonyResponse::HTTP_FORBIDDEN,
        );

        return (string) $request->user()->account_id;
    }

    private function extensionPath(): string
    {
        $path = base_path('extension/autotok');

        return PHP_OS_FAMILY === 'Windows' ? str_replace('/', '\\', $path) : $path;
    }

    private function findClient(string $accountId, int $id): ChromeClient
    {
        return ChromeClient::query()
            ->where('account_id', $accountId)
            ->whereNull('revoked_at')
            ->findOrFail($id);
    }

    /**
     * Chrome đã ghép nối, đang đăng nhập đúng tài khoản có username này.
     */
    private function clientForUsername(string $accountId, string $username): ?ChromeClient
    {
        $needle = mb_strtolower(ltrim($username, '@'));

        return ChromeClient::query()
            ->where('account_id', $accountId)
            ->whereNull('revoked_at')
            ->whereNotNull('tiktok_user_id')
            ->whereNotNull('tiktok_username')
            ->orderByDesc('last_seen_at')
            ->get()
            ->first(fn (ChromeClient $c): bool => mb_strtolower(ltrim((string) $c->tiktok_username, '@')) === $needle);
    }

    /**
     * @return list<string>
     */
    private function workspaceIds(string $accountId): array
    {
        return Workspace::query()->where('account_id', $accountId)->pluck('id')->all();
    }

    /**
     * @return array{code: string, expires_at: string, valid_s: int}|null
     */
    private function currentPair(string $accountId): ?array
    {
        $pair = Cache::get('fork:chrome:pair');

        if (! is_array($pair) || ($pair['account_id'] ?? null) !== $accountId) {
            return null;
        }

        $expires = strtotime((string) ($pair['expires_at'] ?? ''));

        if ($expires === false || $expires <= time()) {
            return null;
        }

        return [
            'code' => (string) $pair['code'],
            'expires_at' => (string) $pair['expires_at'],
            'valid_s' => $expires - time(),
        ];
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function clients(string $accountId): array
    {
        $jobs = app(ChromeJobs::class);
        return ChromeClient::query()
            ->where('account_id', $accountId)
            ->whereNull('revoked_at')
            ->orderByDesc('last_seen_at')
            ->get()
            ->map(fn (ChromeClient $c): array => [
                // Chưa chọn profile và còn từ 2 profile ứng viên trở lên: cần chủ app chọn.
                'profile_needs_choice' => blank($c->chrome_profile_dir) && count(ChromeProfiles::candidates($accountId, $c)) > 1,
                'profile_conflict_with' => ChromeProfiles::conflictFor($c)?->label,
                'id' => $c->id,
                'label' => $c->label,
                'ext_version' => $c->ext_version,
                'tiktok_username' => $c->tiktok_username,
                'tiktok_user_id' => $c->tiktok_user_id,
                'chrome_profile_dir' => $c->chrome_profile_dir,
                'chrome_browser' => $c->chrome_profile_dir ? ChromeProfiles::normalizeBrowser($c->chrome_browser) : null,
                'last_seen_at' => $c->last_seen_at?->toIso8601String(),
                'status' => $jobs->clientStatus($c),
            ])
            ->values()
            ->all();
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function accounts(string $accountId): array
    {
        $accounts = SocialAccount::query()
            ->whereIn('workspace_id', $this->workspaceIds($accountId))
            ->where('platform', Platform::TikTok->value)
            ->get();

        $chrome = ChromeAccount::query()
            ->whereIn('social_account_id', $accounts->pluck('id'))
            ->get()
            ->keyBy('social_account_id');

        $jobs = app(ChromeJobs::class);

        return $accounts->map(function (SocialAccount $a) use ($chrome, $jobs): array {
            $row = $chrome->get($a->id);
            $enabled = (bool) $row?->enabled;

            return [
                'id' => $a->id,
                'username' => $a->username,
                'display_name' => $a->display_name,
                'enabled' => $enabled,
                'chrome_only' => (bool) $row?->chrome_only,
                'readiness' => $enabled ? $jobs->readiness($a)['reason'] : null,
            ];
        })->values()->all();
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function jobList(string $accountId): array
    {
        $usernames = SocialAccount::query()
            ->whereIn('workspace_id', $this->workspaceIds($accountId))
            ->pluck('username', 'id');

        return ChromeJob::query()
            ->whereIn('social_account_id', $usernames->keys())
            ->orderByDesc('created_at')
            ->limit(30)
            ->get()
            ->map(fn (ChromeJob $j): array => [
                'id' => $j->id,
                'username' => $usernames->get($j->social_account_id),
                'state' => $j->state,
                'mode' => $j->mode,
                'caption' => mb_strimwidth((string) $j->caption, 0, 80, '…'),
                'note' => $j->note,
                'created_at' => $j->created_at?->toIso8601String(),
                'updated_at' => $j->updated_at?->toIso8601String(),
            ])
            ->values()
            ->all();
    }
}

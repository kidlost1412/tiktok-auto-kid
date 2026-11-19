<?php

declare(strict_types=1);

namespace App\Http\Middleware\App;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\VideoComment;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Update\LauncherClient;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Inertia\Middleware;
use Throwable;

class HandleInertiaRequests extends Middleware
{
    protected $rootView = 'app';

    /**
     * @return array<string, mixed>
     */
    public function share(Request $request): array
    {
        return [
            ...parent::share($request),
            'name' => config('app.name'),
            'flash' => $request->session()->get('flash', []),
            // Chấm số / chấm đỏ trên thanh trên cùng: bình luận hỏi mua, Chrome mất kết nối, bài lỗi, bản cập nhật.
            'fork_badges' => fn (): ?array => $request->user()?->isAccountOwner() ? $this->forkBadges() : null,
        ];
    }

    /**
     * Mọi số đều rẻ (đếm có điều kiện) hoặc được giữ cache ngắn, vì chạy ở mọi lần mở trang.
     *
     * @return array{buy_comments: int, chrome_offline: int, failed_24h: int, update_available: bool}
     */
    private function forkBadges(): array
    {
        return [
            // Số bình luận "hỏi mua" trong 24 giờ qua, hiện thành chấm số cạnh mục Số liệu.
            'buy_comments' => VideoComment::query()->where('is_buy_intent', true)->where('commented_at', '>=', now()->subDay())->count(),
            // Số kênh đã bật đăng qua Chrome nhưng không có Chrome nào đang kết nối.
            'chrome_offline' => $this->cached('chrome_offline', 30, $this->chromeOffline(...)),
            // Số bài đăng lỗi trong 24 giờ qua.
            'failed_24h' => $this->cached('failed_24h', 60, fn (): int => AutoVideo::query()->where('status', AutoVideo::FAILED)->where('updated_at', '>=', now()->subDay())->count()),
            // Có bản mới hơn bản đang chạy (hỏi launcher nội bộ, giữ 60 giây kể cả khi launcher không trả lời).
            'update_available' => (bool) $this->cached('update_available', 60, fn (): bool => $this->updateAvailable()),
        ];
    }

    /**
     * @template T of int|bool
     *
     * @param  callable(): T  $compute
     * @return T|int
     */
    private function cached(string $key, int $seconds, callable $compute): mixed
    {
        try {
            return Cache::remember('fork_badges:'.$key, $seconds, $compute);
        } catch (Throwable) {
            return 0;
        }
    }

    private function chromeOffline(): int
    {
        $wanted = ChromeAccount::query()->where('enabled', true)->whereNotNull('tiktok_user_id')->pluck('tiktok_user_id')->unique();

        if ($wanted->isEmpty()) {
            return 0;
        }

        $online = ChromeClient::query()
            ->whereNull('revoked_at')
            ->whereIn('tiktok_user_id', $wanted)
            ->where('last_seen_at', '>=', now()->subSeconds(ChromeJobs::ONLINE_WINDOW))
            ->pluck('tiktok_user_id')
            ->unique();

        return $wanted->diff($online)->count();
    }

    private function updateAvailable(): bool
    {
        // Chỉ hỏi khi máy có launcher (có file token): bản dev / test không có launcher thì không gọi mạng trên mỗi trang.
        $token = (string) config('fork-update.token_file');

        if (! LauncherClient::repoConfigured() || $token === '' || ! is_file($token)) {
            return false;
        }

        return (bool) (LauncherClient::status()['update_available'] ?? false);
    }
}

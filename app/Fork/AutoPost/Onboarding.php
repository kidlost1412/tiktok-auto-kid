<?php

declare(strict_types=1);

namespace App\Fork\AutoPost;

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Xuong\XuongController;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Throwable;

/**
 * Thẻ "Bắt đầu" cho máy mới cài: 4 bước kèm trạng thái thật và nút tới đúng chỗ.
 * Tự ẩn khi xong cả 4 bước hoặc khi chủ app bấm "Ẩn hướng dẫn" (lưu ở fork_auto_settings).
 */
final class Onboarding
{
    public const string HIDDEN_KEY = 'onboarding_hidden';

    public const string HUB_CACHE_KEY = 'fork-onboarding:xuong';

    /**
     * @param  list<string>  $accountIds  kênh TikTok của chủ app
     * @return array{steps: list<array<string, mixed>>, done: int, total: int}|null null = không hiện thẻ
     */
    public function forAccounts(array $accountIds): ?array
    {
        if (AutoSetting::read(self::HIDDEN_KEY) === '1') {
            return null;
        }

        $steps = [$this->xuong(), $this->chrome(), $this->stock($accountIds), $this->autoOn($accountIds)];
        $done = count(array_filter($steps, fn (array $s): bool => $s['done']));

        return $done === count($steps) ? null : ['steps' => $steps, 'done' => $done, 'total' => count($steps)];
    }

    public static function hide(): void
    {
        AutoSetting::write(self::HIDDEN_KEY, '1');
    }

    /** ① Xưởng Video: Claude đã đăng nhập và đã có khoá giọng ElevenLabs. */
    private function xuong(): array
    {
        $hub = $this->hubState();
        $base = ['key' => 'xuong', 'title' => 'Xưởng Video sẵn sàng'];

        if ($hub['state'] === 'offline') {
            return $base + ['done' => false, 'state' => 'offline', 'detail' => 'Xưởng chưa chạy. Mở Xưởng Video để kiểm tra đăng nhập Claude và khoá giọng.',
                'action' => ['label' => 'Mở Xưởng Video', 'href' => '/xuong']];
        }

        $missing = [];

        if ($hub['claude'] === false) {
            $missing[] = 'đăng nhập Claude';
        }

        if ($hub['voice'] === false) {
            $missing[] = 'khoá giọng ElevenLabs';
        }

        if ($missing === [] && $hub['claude'] === true && $hub['voice'] === true) {
            return $base + ['done' => true, 'state' => 'done', 'detail' => 'Claude đã đăng nhập, đã có khoá giọng ElevenLabs.', 'action' => null];
        }

        if ($missing === []) {
            return $base + ['done' => false, 'state' => 'waiting', 'detail' => 'Xưởng đang kiểm tra đăng nhập Claude và khoá giọng, lát nữa tải lại trang.',
                'action' => ['label' => 'Mở cài đặt Xưởng', 'href' => '/xuong?tab=cai-dat']];
        }

        return $base + ['done' => false, 'state' => 'todo', 'detail' => 'Còn thiếu: '.implode(', ', $missing).'.',
            'action' => ['label' => 'Mở cài đặt Xưởng', 'href' => '/xuong?tab=cai-dat']];
    }

    /** ② Đã ghép ít nhất một Chrome có tiện ích. */
    private function chrome(): array
    {
        $clients = ChromeClient::query()->whereNull('revoked_at')->get();
        $jobs = app(ChromeJobs::class);
        $online = $clients->filter(fn (ChromeClient $c): bool => $jobs->isOnline($c))->count();
        $base = ['key' => 'chrome', 'title' => 'Ghép Chrome', 'action' => ['label' => 'Kết nối Chrome', 'href' => '/settings/chrome']];

        if ($clients->isEmpty()) {
            return $base + ['done' => false, 'state' => 'todo', 'detail' => 'Cài tiện ích AutoTok trong Chrome rồi nhập mã ghép 6 số.'];
        }

        return array_merge($base, ['done' => true, 'state' => 'done', 'action' => null,
            'detail' => $online > 0 ? 'Đã ghép, Chrome đang mở.' : 'Đã ghép (Chrome đang tắt, mở lại trước giờ đăng).']);
    }

    /**
     * ③ Có ít nhất một sản phẩm đang bật, còn video đủ điều kiện đăng và đã chọn giỏ hàng.
     *
     * @param  list<string>  $accountIds
     */
    private function stock(array $accountIds): array
    {
        $base = ['key' => 'stock', 'title' => 'Có sản phẩm, video và giỏ hàng'];
        $enabled = AutoProduct::query()->where('enabled', true)->select('code');
        $linked = ProductLink::query()->whereIn('social_account_id', $accountIds)->whereNull('paused_reason')->select('auto_product_id');

        // Video chưa xếp lịch (đủ điều kiện) hoặc đã xếp lịch/giữ chỗ nhưng chưa đăng đều tính là "có video".
        $withVideos = AutoVideo::query()->whereIn('product_code', $enabled)->where(function ($q): void {
            $q->where(fn ($n) => $n->eligibleNew())
                ->orWhere(fn ($s) => $s->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED])->whereNotNull('hub_id'));
        });

        if (! (clone $withVideos)->exists()) {
            return $base + ['done' => false, 'state' => 'todo', 'detail' => 'Chưa có video đã duyệt trong kho. Sản xuất và duyệt video trong Xưởng.',
                'action' => ['label' => 'Mở Xưởng Video', 'href' => '/xuong']];
        }

        if (! (clone $withVideos)->whereIn('product_code', $linked)->exists()) {
            return $base + ['done' => false, 'state' => 'todo', 'detail' => 'Đã có video nhưng sản phẩm chưa được gắn giỏ hàng TikTok Shop.',
                'action' => ['label' => 'Chọn giỏ hàng', 'href' => '/auto/gio-hang']];
        }

        return $base + ['done' => true, 'state' => 'done', 'detail' => 'Đã có video sẵn sàng và đã gắn giỏ hàng.', 'action' => null];
    }

    /**
     * ④ Bật tự động đăng trên ít nhất một kênh.
     *
     * @param  list<string>  $accountIds
     */
    private function autoOn(array $accountIds): array
    {
        $on = AutoAccount::query()->whereIn('social_account_id', $accountIds)->where('enabled', true)->exists();
        $base = ['key' => 'auto', 'title' => 'Bật tự động đăng'];

        return $on
            ? $base + ['done' => true, 'state' => 'done', 'detail' => 'Đã bật trên ít nhất một kênh.', 'action' => null]
            : $base + ['done' => false, 'state' => 'todo', 'detail' => 'Bật công tắc trên thẻ kênh để app bắt đầu xếp lịch.',
                'action' => ['label' => 'Tới thẻ kênh', 'href' => '#kenh']];
    }

    /**
     * Hỏi hub (cổng giao diện 8765) từ phía máy chủ, thời gian chờ ngắn, nhớ 60 giây.
     * Không bao giờ ném lỗi: hub tắt thì state = offline; chưa biết thì giá trị null.
     *
     * @return array{state: string, claude: bool|null, voice: bool|null}
     */
    private function hubState(): array
    {
        $cached = Cache::get(self::HUB_CACHE_KEY);

        if (is_array($cached)) {
            return $cached;
        }

        $result = $this->probeHub();
        // Chưa biết đăng nhập Claude (hub đang chạy "claude auth status") thì hỏi lại sớm hơn.
        Cache::put(self::HUB_CACHE_KEY, $result, $result['state'] === 'ok' && $result['claude'] === null ? 15 : 60);

        return $result;
    }

    /** @return array{state: string, claude: bool|null, voice: bool|null} */
    private function probeHub(): array
    {
        if (! XuongController::probe()['up']) {
            return ['state' => 'offline', 'claude' => null, 'voice' => null];
        }

        $url = rtrim((string) config('fork.xuong.url'), '/');
        $voice = null;
        $claude = null;

        try {
            $r = Http::timeout(3)->connectTimeout(1)->acceptJson()->get($url.'/api/khoa-giong');
            // Chỉ đọc cờ "có khoá", không giữ phần đuôi khoá.
            $voice = $r->successful() && is_bool($r->json('co')) ? (bool) $r->json('co') : null;
        } catch (Throwable) {
            $voice = null;
        }

        try {
            // Danh sách tài khoản Claude trong hub (hub tự nhớ kết quả "claude auth status" vài phút).
            $r = Http::timeout(4)->connectTimeout(1)->acceptJson()->get($url.'/api/tai-khoan-ds');
            $list = $r->successful() ? $r->json() : null;

            if (is_array($list)) {
                $claude = collect($list)->contains(fn ($tk): bool => is_array($tk) && ($tk['dang_nhap'] ?? false) === true);
            }
        } catch (Throwable) {
            $claude = null;
        }

        return ['state' => 'ok', 'claude' => $claude, 'voice' => $voice];
    }
}

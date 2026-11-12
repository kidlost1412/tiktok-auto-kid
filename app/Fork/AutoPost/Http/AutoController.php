<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Hub\HubApi;
use App\Fork\AutoPost\Media\ProductImageLookup;
use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Scheduling\FutureUploads;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\AutoPost\Scheduling\PlanPreview;
use App\Fork\AutoPost\Scheduling\ResultWatcher;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\AutoPost\Stats\Insights;
use App\Fork\AutoPost\VideoLibrary;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Notify\Telegram;
use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Inertia\Inertia;
use Inertia\Response;

/**
 * Trang "Tự động đăng": kho video, tài khoản, hàng chờ, số liệu và đề xuất giờ đăng.
 */
final class AutoController extends Controller
{
    use ScopesToOwner;

    private const string DEFAULT_TZ = 'Asia/Ho_Chi_Minh';

    public function index(Request $request): Response
    {
        $accountId = $this->authorizeOwner($request);
        $accounts = $this->tiktokAccounts($accountId);
        $insights = app(Insights::class);

        $autoAccounts = AutoAccount::query()->whereIn('social_account_id', $accounts->pluck('id'))->get()->keyBy('social_account_id');
        $chromeRows = ChromeAccount::query()->whereIn('social_account_id', $accounts->pluck('id'))->get()->keyBy('social_account_id');
        $chrome = $chromeRows->map(fn (ChromeAccount $c): bool => (bool) $c->enabled);

        $shopCounts = ShopProduct::query()->whereIn('social_account_id', $accounts->pluck('id'))->where('missing', false)->where('hidden', false)
            ->select('social_account_id', DB::raw('count(*) as total'))->groupBy('social_account_id')->pluck('total', 'social_account_id');
        $linkCounts = ProductLink::query()->whereIn('social_account_id', $accounts->pluck('id'))
            ->select('social_account_id', DB::raw('count(*) as total'))->groupBy('social_account_id')->pluck('total', 'social_account_id');
        $sync = app(ShopSync::class);

        $rows = $accounts->map(function (SocialAccount $a) use ($autoAccounts, $chrome, $insights, $shopCounts, $linkCounts, $sync): array {
            $auto = $autoAccounts[$a->id] ?? null;
            $rec = $auto ? $insights->recommendHours($auto) : null;
            $status = $sync->status($auto);

            return [
                'cart' => [
                    'sync_state' => $status['state'],
                    'synced_at' => $status['synced_at'],
                    'products_count' => (int) ($shopCounts[$a->id] ?? 0),
                    'linked_count' => (int) ($linkCounts[$a->id] ?? 0),
                ],
                'id' => $a->id,
                'username' => $a->username,
                'display_name' => $a->display_name,
                'timezone' => $a->timezone ?: self::DEFAULT_TZ,
                'avatar_url' => $a->avatar_url,
                'chrome_enabled' => (bool) ($chrome[$a->id] ?? false),
                'enabled' => (bool) ($auto?->enabled ?? false),
                'daily_cap' => (int) ($auto?->daily_cap ?? 8),
                'schedule_ahead_days' => (int) ($auto?->schedule_ahead_days ?? config('fork.auto.default_schedule_ahead_days', 3)),
                'window_start' => (int) ($auto?->window_start ?? 6),
                'window_end' => (int) ($auto?->window_end ?? 23),
                'mode' => (string) ($auto?->mode ?? AutoAccount::EXPLORE),
                'preferred_hours' => array_values((array) ($auto?->preferred_hours ?? [])),
                'explore_ratio' => (float) ($auto?->explore_ratio ?? 0.2),
                'paused_reason' => $auto?->paused_reason,
                'recommendation' => $rec,
            ];
        })->values()->all();

        $dailyCap = collect($rows)->where('enabled', true)->sum('daily_cap');
        $images = ProductImages::lookup($accounts->pluck('id')->map(fn ($id): string => (string) $id)->all());
        $products = $this->productRows($images->byCode());
        // Chỉ đếm video thật sự giữ chỗ được (cùng bộ lọc với reserveNext và cảnh báo sắp hết kho).
        $newTotal = AutoVideo::query()
            ->eligibleNew()
            ->whereIn('product_code', AutoProduct::query()->where('enabled', true)->select('code'))
            ->count();

        return Inertia::render('fork/Auto', [
            'products' => $products,
            'stock' => [
                'new_total' => $newTotal,
                'daily_cap' => (int) $dailyCap,
                'days_left' => $dailyCap > 0 ? round($newTotal / $dailyCap, 1) : null,
                'low' => $dailyCap > 0 ? $newTotal < $dailyCap : $newTotal === 0,
                // Số liệu đọc trực tiếp từ DB lúc này; trang tự làm mới mỗi 30 giây.
                'updated_at' => now()->toIso8601String(),
                'last_ingest_at' => Cache::get(VideoLibrary::LAST_INGEST_CACHE_KEY),
            ],
            'accounts' => $rows,
            'health' => $this->health($accounts, $chromeRows),
            'hub' => Inertia::defer(fn (): array => $this->hubStatus()),
            'lich' => $this->lich($accounts, $autoAccounts, $images),
            'plan_ahead_hours' => (int) config('fork.auto.plan_ahead_hours', 6),
            'upcoming' => $this->upcoming($accounts),
            'recent' => $this->recent($accounts, $images),
            'insights' => $insights->breakdowns(),
            'hasWorkspace' => (bool) $request->user()?->current_workspace_id,
        ]);
    }

    public function updateAccount(Request $request, string $socialAccount): RedirectResponse
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);

        $data = $request->validate([
            'enabled' => ['sometimes', 'boolean'],
            'daily_cap' => ['sometimes', 'integer', 'min:1', 'max:100'],
            'schedule_ahead_days' => ['sometimes', 'integer', 'min:1', 'max:9'],
            'window_start' => ['sometimes', 'integer', 'min:0', 'max:23'],
            'window_end' => ['sometimes', 'integer', 'min:1', 'max:24'],
            'mode' => ['sometimes', 'in:explore,optimized'],
            'explore_ratio' => ['sometimes', 'numeric', 'min:0', 'max:1'],
        ]);

        $auto = AutoAccount::query()->find($account->id);
        $start = (int) ($data['window_start'] ?? $auto?->window_start ?? 6);
        $end = (int) ($data['window_end'] ?? $auto?->window_end ?? 23);

        if ($end <= $start) {
            return back()->with('flash.error', 'Giờ kết thúc phải lớn hơn giờ bắt đầu.');
        }

        if (($data['enabled'] ?? false) === true) {
            $data['paused_reason'] = null;
        }

        $wasEnabled = (bool) $auto?->enabled;
        AutoAccount::query()->updateOrCreate(['social_account_id' => $account->id], $data);

        if ($wasEnabled && ($data['enabled'] ?? true) === false) {
            FutureUploads::warn((string) $account->id, 'kênh đã tắt tự động đăng');
        }

        return back()->with('flash.success', 'Đã lưu cài đặt tự động đăng.');
    }

    /**
     * "Xếp lịch ngay": chạy đúng như `php artisan fork:auto-plan` nhưng chỉ cho các kênh của chủ tài khoản này.
     * Planner vẫn tuân theo mọi luật thường (khung giờ, hạn mức, giỏ hàng, chỉ tạo bài trong vài tiếng tới).
     */
    public function planNow(Request $request): RedirectResponse
    {
        $accounts = $this->tiktokAccounts($this->authorizeOwner($request));
        $ids = $accounts->pluck('id')->map(fn ($id): string => (string) $id)->all();

        app(ResultWatcher::class)->sync();
        $report = app(Planner::class)->planAll(null, $ids);

        if ($report === []) {
            return back()->with('flash.error', 'Chưa có kênh nào bật tự động đăng để xếp lịch.');
        }

        $created = (int) collect($report)->sum('created');
        $lines = collect($report)->map(function (array $row, string $id) use ($accounts): string {
            $name = '@'.($accounts->firstWhere('id', $id)?->username ?? $id);

            return $name.': tạo '.$row['created'].' bài'.($row['failed'] > 0 ? ', lỗi '.$row['failed'] : '').($row['skipped'] ? ' ('.$row['skipped'].')' : '');
        })->implode('; ');

        return back()->with($created > 0 ? 'flash.success' : 'flash.error', ($created > 0 ? 'Đã xếp lịch xong. ' : 'Chưa tạo thêm bài nào. ').$lines.'.');
    }

    public function pause(Request $request, string $socialAccount): RedirectResponse
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);

        AutoAccount::query()->updateOrCreate(
            ['social_account_id' => $account->id],
            ['enabled' => false, 'paused_reason' => 'Tạm dừng thủ công'],
        );
        FutureUploads::warn((string) $account->id, 'kênh bị tạm dừng thủ công');

        return back()->with('flash.success', 'Đã tạm dừng tự động đăng cho @'.$account->username.'.');
    }

    public function applyHours(Request $request, string $socialAccount): RedirectResponse
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);
        $auto = AutoAccount::query()->find($account->id);

        if (! $auto) {
            return back()->with('flash.error', 'Chưa có dữ liệu để đề xuất giờ đăng.');
        }

        $rec = app(Insights::class)->recommendHours($auto);

        if ($rec['hours'] === null) {
            return back()->with('flash.error', (string) $rec['reason']);
        }

        $hours = collect($rec['hours'])->pluck('hour')->map(fn ($h): int => (int) $h)->sort()->values()->all();

        $auto->update(['mode' => AutoAccount::OPTIMIZED, 'preferred_hours' => $hours]);

        return back()->with('flash.success', 'Đã áp dụng khung giờ đề xuất: '.implode(', ', array_map(fn (int $h): string => $h.'h', $hours)).'.');
    }

    public function updateProduct(Request $request, string $code): RedirectResponse
    {
        $this->authorizeOwner($request);

        $product = AutoProduct::query()->findOrFail($code);

        // Sản phẩm giỏ hàng không còn nhập tay ở đây: chọn theo từng kênh (xem saveLink).
        $data = $request->validate([
            'enabled' => ['sometimes', 'boolean'],
        ]);

        $product->update($data);

        return back()->with('flash.success', 'Đã lưu sản phẩm '.$product->short_name.'.');
    }

    /**
     * Sức khoẻ hệ thống: Chrome từng kênh và Telegram. Hub được tải sau (xem hubStatus).
     *
     * @param  Collection<int, SocialAccount>  $accounts
     * @param  Collection<string, ChromeAccount>  $chromeRows
     * @return array<string, mixed>
     */
    private function health($accounts, $chromeRows): array
    {
        $jobs = app(ChromeJobs::class);

        return [
            'telegram' => Telegram::configured(),
            'hub_api' => HubApi::enabled(),
            'channels' => $accounts->map(function (SocialAccount $a) use ($chromeRows, $jobs): array {
                $chrome = $chromeRows[$a->id] ?? null;
                $clients = $chrome === null || blank($chrome->tiktok_user_id)
                    ? collect()
                    : ChromeClient::query()->where('tiktok_user_id', $chrome->tiktok_user_id)->whereNull('revoked_at')->get();
                $lastSeen = $clients->pluck('last_seen_at')->filter()->max();

                return [
                    'id' => $a->id,
                    'chrome_enabled' => (bool) ($chrome?->enabled ?? false),
                    'chrome_online' => $clients->contains(fn (ChromeClient $c): bool => $jobs->isOnline($c)),
                    'chrome_last_seen' => $lastSeen?->toIso8601String(),
                ];
            })->values()->all(),
        ];
    }

    /** @return array{state: string, label: string} */
    private function hubStatus(): array
    {
        if (! HubApi::enabled()) {
            return ['state' => 'off', 'label' => 'Đọc video từ thư mục (chưa dùng API hub)'];
        }

        $state = Cache::remember('fork-hub:ping', 60, fn (): string => (new HubApi)->ping());

        return ['state' => $state, 'label' => match ($state) {
            HubApi::OK => 'Hub đang hoạt động',
            HubApi::OFFLINE => 'Hub đang tắt (mở Xưởng Video để lấy video mới)',
            HubApi::BAD_KEY => 'Sai khoá kết nối hub',
            default => 'Hub trả lời lỗi',
        }];
    }

    /**
     * Lịch 3 ngày tới của từng kênh: bài thật (đã xếp/đã đăng) cộng giờ dự kiến từ chạy thử Planner (chỉ đọc).
     *
     * @param  Collection<int, SocialAccount>  $accounts
     * @param  Collection<string, AutoAccount>  $autoAccounts
     * @return array{days: list<array<string, string>>, channels: array<string, array<string, mixed>>}
     */
    private function lich($accounts, $autoAccounts, ProductImageLookup $images): array
    {
        $now = CarbonImmutable::now();
        $firstTz = $accounts->first()?->timezone ?: self::DEFAULT_TZ;
        $labels = ['Hôm nay', 'Ngày mai', 'Ngày kia'];
        $days = [];

        foreach ($labels as $i => $label) {
            $d = $now->setTimezone($firstTz)->startOfDay()->addDays($i);
            $days[] = ['key' => $d->format('Y-m-d'), 'label' => $label, 'date' => $d->format('d/m')];
        }

        $preview = app(PlanPreview::class)->forAccounts($autoAccounts->values(), $now, count($labels));
        $hub = AutoProduct::query()->get()->keyBy('code');
        $channels = [];

        foreach ($accounts as $a) {
            $tz = $a->timezone ?: self::DEFAULT_TZ;
            $start = $now->setTimezone($tz)->startOfDay();
            $end = $start->addDays(count($labels));
            $auto = $autoAccounts[$a->id] ?? null;

            $videos = AutoVideo::query()
                ->where('social_account_id', $a->id)
                ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED, AutoVideo::POSTED, AutoVideo::FAILED])
                ->whereRaw('COALESCE(scheduled_for, posted_at) >= ? AND COALESCE(scheduled_for, posted_at) < ?', [$start->utc(), $end->utc()])
                ->with('post')
                ->get();

            $items = $videos->map(function (AutoVideo $v) use ($hub, $tz, $images, $a): array {
                $at = $v->scheduled_for ?? $v->posted_at;
                $postStatus = $v->post?->status;
                $state = match (true) {
                    // Video đã hẹn giờ sẵn trên TikTok (posted_at là giờ hẹn, chưa tới): chưa đăng, chỉ là đã hẹn.
                    $v->status === AutoVideo::POSTED && $v->posted_at?->isFuture() => 'tiktok_scheduled',
                    $v->status === AutoVideo::POSTED => 'posted',
                    $v->status === AutoVideo::FAILED, $postStatus === PostStatus::Failed => 'failed',
                    $v->status === AutoVideo::RESERVED => 'reserved',
                    $postStatus === PostStatus::Publishing => 'publishing',
                    default => 'scheduled',
                };

                return [
                    'id' => $v->id,
                    'state' => $state,
                    'at' => $at?->toIso8601String(),
                    'day' => $at?->setTimezone($tz)->format('Y-m-d'),
                    'product_code' => $v->product_code,
                    'product_label' => CartRules::label($hub[$v->product_code] ?? null, (string) $v->product_code, $v->quy_cach),
                    'cart_name' => data_get($v->post?->meta, 'fork_shop_product_name') ?: $v->product_name,
                    'product_image' => $images->forSlot((string) $a->id, $v->product_code, $v->quy_cach),
                    'caption' => $this->snippet($v->caption),
                    'link' => in_array($state, ['posted', 'tiktok_scheduled'], true) ? $this->safeLink(data_get($v->stats, 'link')) : null,
                    'error' => $state === 'failed' ? $v->skip_reason : null,
                ];
            })->all();

            $p = $preview[$a->id] ?? ['slots' => [], 'note' => null, 'blocked' => [], 'warnings' => [], 'allowed_count' => 0];

            foreach ($p['slots'] as $slot) {
                $at = CarbonImmutable::parse($slot['at']);
                $items[] = [
                    'id' => null,
                    'state' => 'projected',
                    'at' => $slot['at'],
                    'day' => $at->setTimezone($tz)->format('Y-m-d'),
                    'product_code' => $slot['video']['product_code'] ?? null,
                    'product_label' => $slot['video']['product_label'] ?? null,
                    'cart_name' => $slot['video']['cart_name'] ?? null,
                    'product_image' => $images->forSlot((string) $a->id, $slot['video']['product_code'] ?? null, $slot['video']['quy_cach'] ?? null),
                    'caption' => $this->snippet($slot['video']['caption'] ?? null),
                    'video_id' => $slot['video']['id'] ?? null,
                    'empty_reason' => $slot['reason'],
                    'link' => null,
                    'error' => null,
                ];
            }

            usort($items, fn (array $x, array $y): int => strcmp((string) $x['at'], (string) $y['at']));

            // Cùng mốc thời gian với trần bài/ngày của VideoLibrary (COALESCE(scheduled_for, posted_at, updated_at)):
            // bài đăng "ngay" không có scheduled_for vẫn được tính vào hôm nay.
            $counted = AutoVideo::query()
                ->where('social_account_id', $a->id)
                ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED, AutoVideo::POSTED])
                ->whereRaw('COALESCE(scheduled_for, posted_at, updated_at) >= ? AND COALESCE(scheduled_for, posted_at, updated_at) < ?', [$start->utc(), $start->addDay()->utc()])
                ->get(['id', 'status', 'posted_at']);

            $channels[$a->id] = [
                'items' => $items,
                'note' => $p['note'],
                'blocked' => collect($p['blocked'])->map(fn (array $b): array => [...$b, 'image' => $images->forCode($b['code'] ?? null)])->all(),
                'warnings' => array_slice($p['warnings'], 0, 6),
                'today' => [
                    'planned' => $counted->count(),
                    'posted' => $counted->filter(fn (AutoVideo $v): bool => $v->status === AutoVideo::POSTED && ! $v->posted_at?->isFuture())->count(),
                    'cap' => (int) ($auto?->daily_cap ?? 8),
                ],
            ];
        }

        return ['days' => $days, 'channels' => $channels];
    }

    /**
     * @param  array<string, string>  $images  mã hub => URL ảnh sản phẩm
     * @return list<array<string, mixed>>
     */
    private function productRows(array $images): array
    {
        // Video posted có giờ đăng ở tương lai (đã hẹn sẵn trên TikTok) tính là "đã xếp", không phải "đã đăng".
        $counts = AutoVideo::query()
            ->selectRaw('product_code, '.AutoVideo::effectiveStatusSql().' as eff, count(*) as total')
            ->groupByRaw('product_code, eff')
            ->get()
            ->groupBy('product_code');

        return AutoProduct::query()->orderBy('short_name')->get()->map(function (AutoProduct $p) use ($counts, $images): array {
            $c = ($counts[$p->code] ?? collect())->pluck('total', 'eff');
            $scheduled = (int) ($c[AutoVideo::SCHEDULED] ?? 0) + (int) ($c[AutoVideo::RESERVED] ?? 0);

            return [
                'code' => $p->code,
                'name' => $p->name,
                'short_name' => $p->short_name,
                'enabled' => (bool) $p->enabled,
                'image' => $images[$p->code] ?? null,
                'counts' => [
                    'new' => (int) ($c[AutoVideo::NEW] ?? 0),
                    'scheduled' => $scheduled,
                    'posted' => (int) ($c[AutoVideo::POSTED] ?? 0),
                    'skipped' => (int) ($c[AutoVideo::SKIPPED] ?? 0),
                    'failed' => (int) ($c[AutoVideo::FAILED] ?? 0),
                ],
            ];
        })->all();
    }

    /**
     * @param  Collection<int, SocialAccount>  $accounts
     * @return list<array<string, mixed>>
     */
    private function upcoming($accounts): array
    {
        return AutoVideo::query()
            ->where('status', AutoVideo::SCHEDULED)
            ->whereIn('social_account_id', $accounts->pluck('id'))
            ->orderBy('scheduled_for')
            ->limit(20)
            ->get()
            ->map(fn (AutoVideo $v): array => [
                'id' => $v->id,
                'file_name' => $v->file_name,
                'product_code' => $v->product_code,
                'username' => $accounts->firstWhere('id', $v->social_account_id)?->username,
                'scheduled_for' => $v->scheduled_for?->toIso8601String(),
                'caption' => $v->caption,
            ])->all();
    }

    /**
     * Chỉ bài đã thật sự lên TikTok (giờ đăng không ở tương lai). Bài hẹn sẵn trên TikTok nằm ở lịch, không ở đây.
     *
     * @param  Collection<int, SocialAccount>  $accounts
     * @return list<array<string, mixed>>
     */
    private function recent($accounts, ProductImageLookup $images): array
    {
        return AutoVideo::query()
            ->livePosted()
            ->whereNotNull('posted_at')
            ->whereIn('social_account_id', $accounts->pluck('id'))
            ->orderByDesc('posted_at')
            ->limit(30)
            ->get()
            ->map(fn (AutoVideo $v): array => [
                'id' => $v->id,
                'file_name' => $v->file_name,
                'product_code' => $v->product_code,
                'product_image' => $images->forSlot((string) $v->social_account_id, $v->product_code, $v->quy_cach),
                'cart_name' => $v->product_name,
                'caption' => $this->snippet($v->caption),
                'username' => $accounts->firstWhere('id', $v->social_account_id)?->username,
                'posted_at' => $v->posted_at?->toIso8601String(),
                'views' => data_get($v->stats, 'latest.views'),
                'views_24h' => data_get($v->stats, 'h24.views'),
                'link' => $this->safeLink(data_get($v->stats, 'link')),
            ])->all();
    }

    private function snippet(?string $text): ?string
    {
        $text = trim((string) preg_replace('/\s+/u', ' ', (string) $text));

        return $text === '' ? null : mb_strimwidth($text, 0, 140, '…');
    }

    private function safeLink(mixed $link): ?string
    {
        return is_string($link) && preg_match('#^https://#i', $link) === 1 ? $link : null;
    }
}

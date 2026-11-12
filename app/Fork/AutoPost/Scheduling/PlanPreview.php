<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Shop\CartRules;
use Carbon\CarbonImmutable;
use Illuminate\Support\Collection;

/**
 * Chạy thử (chỉ đọc) việc xếp lịch cho các ngày tới: lấy các giờ trống từ Planner::slotsFor và ghép với video
 * mà VideoLibrary::reserveNext nhiều khả năng sẽ chọn. KHÔNG giữ chỗ, không đổi trạng thái video, không tạo bài.
 * Kết quả chỉ là ước lượng để hiển thị; việc xếp thật vẫn do Planner làm.
 */
final class PlanPreview
{
    public function __construct(
        private readonly Planner $planner,
        private readonly CartRules $cart,
    ) {}

    /**
     * @param  iterable<AutoAccount>  $accounts
     * @return array<string, array{slots: list<array<string, mixed>>, note: ?string, blocked: list<array<string, mixed>>, warnings: list<string>, allowed_count: int}> khoá là social_account_id
     */
    public function forAccounts(iterable $accounts, ?CarbonImmutable $now = null, ?int $days = null): array
    {
        $now ??= CarbonImmutable::now();
        $taken = []; // video đã "ghép" cho kênh trước đó, kênh sau không dùng lại
        $result = [];

        foreach ($accounts as $auto) {
            $result[(string) $auto->social_account_id] = $this->forAccount($auto, $now, $days, $taken);
        }

        return $result;
    }

    /**
     * @param  array<int, true>  $taken
     * @return array{slots: list<array<string, mixed>>, note: ?string, blocked: list<array<string, mixed>>, warnings: list<string>, allowed_count: int}
     */
    public function forAccount(AutoAccount $auto, CarbonImmutable $now, ?int $days = null, array &$taken = []): array
    {
        $id = (string) $auto->social_account_id;
        $cart = $this->cart->evaluate($id);
        $out = ['slots' => [], 'note' => null, 'blocked' => $this->blocked($cart['allowed']), 'warnings' => $cart['warnings'], 'allowed_count' => count($cart['allowed'])];

        if (! $auto->enabled) {
            $out['note'] = 'Kênh đang tắt tự động đăng nên chưa có lịch dự kiến.';

            return $out;
        }

        if (filled($auto->paused_reason)) {
            $out['note'] = 'Kênh đang tạm dừng: '.$auto->paused_reason;

            return $out;
        }

        $tz = $auto->timezone();
        $local = $now->setTimezone($tz);
        $from = $now->addSeconds(Planner::MIN_LEAD)->startOfMinute()->addMinute();
        // Cùng khoảng với Planner (schedule_ahead_days); $days chỉ để thu hẹp thêm khi giao diện chỉ hiện vài ngày.
        $to = $this->planner->horizonFor($auto, $now);

        if ($days !== null) {
            $limit = $local->startOfDay()->addDays(max(1, $days))->subSecond()->utc();
            $to = $limit->lessThan($to) ? $limit : $to;
        }

        $slots = array_slice($this->planner->slotsFor($auto, $from, $to), 0, max(0, $this->planner->futureRoom($auto, $now)));

        if ($cart['allowed'] === []) {
            $out['note'] = 'Chưa có sản phẩm nào được chọn giỏ hàng hợp lệ nên chưa xếp được video.';
        }

        $pool = $cart['allowed'] === [] ? collect() : $this->candidates($cart['allowed'], $taken);
        $recent = $this->recentOf($id);
        $today = $this->doneToday($id, $tz);
        $links = $this->linksOf($id);
        $hub = AutoProduct::query()->get()->keyBy('code');

        foreach ($slots as $slot) {
            $video = $this->pick($pool, $recent, $today);

            if ($video === null) {
                $out['slots'][] = ['at' => $slot->toIso8601String(), 'video' => null, 'reason' => $cart['allowed'] === [] ? 'chưa chọn giỏ hàng' : 'hết video có giỏ'];

                continue;
            }

            $pool = $pool->reject(fn (AutoVideo $c): bool => $c->id === $video->id)->values();
            $taken[$video->id] = true;
            array_unshift($recent, ['product_code' => $video->product_code, 'goc' => $video->goc]);
            $today[$video->product_code] = ($today[$video->product_code] ?? 0) + 1;

            $link = $links[$video->product_code.'|'.($video->quy_cach ?? '')] ?? null;

            $out['slots'][] = [
                'at' => $slot->toIso8601String(),
                'video' => [
                    'id' => $video->id,
                    'product_code' => $video->product_code,
                    'product_label' => CartRules::label($hub[$video->product_code] ?? null, (string) $video->product_code, $video->quy_cach),
                    'cart_name' => filled($video->product_name) ? (string) $video->product_name : ($link?->display_name),
                    'quy_cach' => $video->quy_cach,
                    'caption' => $video->caption,
                ],
                'reason' => null,
            ];
        }

        return $out;
    }

    /**
     * Video `new` đủ điều kiện (cùng bộ lọc với reserveNext), theo thứ tự lô cũ trước.
     *
     * @param  array<string, list<?string>>  $allowed
     * @param  array<int, true>  $taken
     * @return Collection<int, AutoVideo>
     */
    private function candidates(array $allowed, array $taken): Collection
    {
        $enabled = AutoProduct::query()->where('enabled', true)->pluck('code')->all();

        return AutoVideo::query()
            ->eligibleNew()
            ->whereIn('product_code', $enabled)
            ->whereIn('product_code', array_keys($allowed))
            ->orderBy('batch_date')
            ->orderBy('id')
            ->limit(500)
            ->get(['id', 'batch_date', 'product_code', 'quy_cach', 'goc', 'product_name', 'caption'])
            ->filter(fn (AutoVideo $v): bool => ! isset($taken[$v->id]) && in_array(filled($v->quy_cach) ? (string) $v->quy_cach : null, $allowed[$v->product_code], true))
            ->values();
    }

    /**
     * Cùng luật nới dần của reserveNext: tránh sản phẩm 2 bài gần nhất và góc 3 bài gần nhất, rồi nới dần.
     *
     * @param  Collection<int, AutoVideo>  $pool
     * @param  list<array{product_code: ?string, goc: ?string}>  $recent  mới nhất ở đầu
     * @param  array<string, int>  $today
     */
    private function pick(Collection $pool, array $recent, array $today): ?AutoVideo
    {
        if ($pool->isEmpty()) {
            return null;
        }

        $recent = array_slice($recent, 0, 3);
        $products = array_column($recent, 'product_code');
        $gocs = array_values(array_filter(array_column($recent, 'goc')));

        $levels = [
            [array_slice($products, 0, 2), $gocs],
            [array_slice($products, 0, 2), []],
            [array_slice($products, 0, 1), []],
            [[], []],
        ];

        foreach ($levels as [$avoidProducts, $avoidGoc]) {
            $ordered = $pool
                ->reject(fn (AutoVideo $c): bool => in_array($c->product_code, $avoidProducts, true) || ($c->goc !== null && in_array($c->goc, $avoidGoc, true)))
                ->sortBy([
                    fn (AutoVideo $x, AutoVideo $y): int => $x->batch_date <=> $y->batch_date,
                    fn (AutoVideo $x, AutoVideo $y): int => ($today[$x->product_code] ?? 0) <=> ($today[$y->product_code] ?? 0),
                    fn (AutoVideo $x, AutoVideo $y): int => $x->id <=> $y->id,
                ]);

            if ($ordered->isNotEmpty()) {
                return $ordered->first();
            }
        }

        return null;
    }

    /**
     * @return list<array{product_code: ?string, goc: ?string}>
     */
    private function recentOf(string $accountId): array
    {
        return AutoVideo::query()
            ->where('social_account_id', $accountId)
            ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED, AutoVideo::POSTED])
            ->orderByRaw('COALESCE(scheduled_for, posted_at, updated_at) DESC')
            ->orderByDesc('id')
            ->limit(3)
            ->get(['product_code', 'goc'])
            ->map(fn (AutoVideo $v): array => ['product_code' => $v->product_code, 'goc' => $v->goc])
            ->all();
    }

    /**
     * @return array<string, int>
     */
    private function doneToday(string $accountId, string $tz): array
    {
        $start = CarbonImmutable::now($tz)->startOfDay()->utc();

        return AutoVideo::query()
            ->where('social_account_id', $accountId)
            ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED, AutoVideo::POSTED])
            ->whereRaw('COALESCE(scheduled_for, posted_at, updated_at) >= ?', [$start])
            ->selectRaw('product_code, count(*) as total')
            ->groupBy('product_code')
            ->pluck('total', 'product_code')
            ->map(fn ($n): int => (int) $n)
            ->all();
    }

    /**
     * @return array<string, ProductLink>
     */
    private function linksOf(string $accountId): array
    {
        return ProductLink::query()->where('social_account_id', $accountId)->get()
            ->keyBy(fn (ProductLink $l): string => $l->auto_product_id.'|'.($l->quy_cach ?? ''))
            ->all();
    }

    /**
     * Video đang chờ trong kho nhưng không được phép đăng vì chưa có giỏ hợp lệ, gom theo sản phẩm/quy cách.
     *
     * @param  array<string, list<?string>>  $allowed
     * @return list<array<string, mixed>>
     */
    private function blocked(array $allowed): array
    {
        $hub = AutoProduct::query()->where('enabled', true)->get()->keyBy('code');

        return AutoVideo::query()
            ->where('status', AutoVideo::NEW)
            ->whereIn('product_code', $hub->keys())
            ->selectRaw('product_code, quy_cach, count(*) as total')
            ->groupBy('product_code', 'quy_cach')
            ->get()
            ->reject(fn ($r): bool => in_array(filled($r->quy_cach) ? (string) $r->quy_cach : null, $allowed[$r->product_code] ?? [], true))
            ->map(fn ($r): array => [
                'code' => (string) $r->product_code,
                'quy_cach' => filled($r->quy_cach) ? (string) $r->quy_cach : null,
                'label' => CartRules::label($hub[$r->product_code], (string) $r->product_code, filled($r->quy_cach) ? (string) $r->quy_cach : null),
                'count' => (int) $r->total,
            ])
            ->sortByDesc('count')
            ->values()
            ->all();
    }
}

<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\AccountStat;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\VideoComment;
use App\Fork\AutoPost\Models\VideoStat;
use App\Fork\Chrome\Models\ChromeClient;
use App\Http\Controllers\Controller;
use App\Models\AnalyticsPublication;
use App\Models\AnalyticsPublicationDailySnapshot;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Http\Request;
use Illuminate\Support\Collection;
use Inertia\Inertia;
use Inertia\Response;

/**
 * Trang "Số liệu": video đã đăng cùng lượt xem / tương tác đọc thẳng từ các ảnh chụp số liệu của TikTok Auto Kid
 * (AutoVideo.stats chỉ là dự phòng khi chưa có ảnh chụp).
 */
final class StatsController extends Controller
{
    use ScopesToOwner;

    private const string DEFAULT_TZ = 'Asia/Ho_Chi_Minh';

    private const int MAX_DAYS = 120;

    private const int LIST_LIMIT = 60;

    private const array RANGES = ['today', '7d', '30d', 'custom'];

    private const array SORTS = ['moi', 'view', 'tuong-tac'];

    /** Tiện ích từ bản này trở lên mới thu được số liệu + bình luận từ TikTok Studio. */
    public const string MIN_EXTENSION_VERSION = '1.4.0';

    private const int COMMENT_LIMIT = 40;

    public function index(Request $request): Response
    {
        $accounts = $this->tiktokAccounts($this->authorizeOwner($request));
        $accountIds = $accounts->pluck('id')->map(fn ($id): string => (string) $id)->all();
        $tz = $accounts->first()?->timezone ?: self::DEFAULT_TZ;

        $range = $request->query('range');
        $range = is_string($range) && in_array($range, self::RANGES, true) ? $range : '7d';
        $sort = $request->query('sort');
        $sort = is_string($sort) && in_array($sort, self::SORTS, true) ? $sort : 'moi';

        [$from, $to] = $this->period($request, $range, $tz);
        $days = (int) $from->diffInDays($to);
        $prevFrom = $from->subDays($days);

        $filters = [
            'range' => $range,
            'from' => $from->format('Y-m-d'),
            'to' => $to->subDay()->format('Y-m-d'),
            'channel' => $this->scalar($request, 'channel'),
            'product' => $this->scalar($request, 'product'),
            'goc' => $this->scalar($request, 'goc'),
            'giong' => $this->scalar($request, 'giong'),
            'sort' => $sort,
            'cm' => $request->query('cm') === 'mua' ? 'mua' : 'all',
        ];

        $base = fn () => AutoVideo::query()
            ->with('socialAccount:id,username,display_name,timezone')
            ->where('status', AutoVideo::POSTED)
            ->whereNotNull('posted_at')
            // Bài đã hẹn giờ sẵn có posted_at ở tương lai: chưa đăng, chưa có số liệu.
            ->where('posted_at', '<=', now())
            ->whereIn('social_account_id', $accountIds)
            ->when($filters['channel'] !== '', fn ($q) => $q->where('social_account_id', $filters['channel']))
            ->when($filters['product'] !== '', fn ($q) => $q->where('product_code', $filters['product']))
            ->when($filters['goc'] !== '', fn ($q) => $q->where('goc', $filters['goc']))
            ->when($filters['giong'] !== '', fn ($q) => $q->where('giong', $filters['giong']));

        $current = $base()->where('posted_at', '>=', $from->utc())->where('posted_at', '<', $to->utc())->get();
        $previous = $base()->where('posted_at', '>=', $prevFrom->utc())->where('posted_at', '<', $from->utc())->get();

        $metrics = $this->metricsFor($current->concat($previous));

        $rows = $current->map(fn (AutoVideo $v): array => $this->row($v, $metrics[$v->id], $tz));
        $prevRows = $previous->map(fn (AutoVideo $v): array => $this->row($v, $metrics[$v->id], $tz));

        $products = AutoProduct::query()->orderBy('short_name')->get()->keyBy('code');

        $sorted = $this->sorted($rows, $sort);
        $ranked = $rows->filter(fn (array $r): bool => $r['has_metrics'])->sortByDesc('views')->values();

        return Inertia::render('fork/SoLieu', [
            'filters' => $filters,
            'options' => $this->options($accounts, $accountIds, $products),
            'kpis' => $this->kpis($rows, $prevRows),
            'daily' => $this->daily($rows, $from, $days),
            'breakdowns' => [
                'product' => $this->group($rows, fn (array $r): string => (string) ($r['product_code'] ?? ''), fn (string $k): string => (string) ($products[$k]?->short_name ?? $k)),
                'goc' => $this->group($rows, fn (array $r): string => (string) ($r['goc'] ?? '')),
                'hour' => $this->group($rows, fn (array $r): string => sprintf('%02d', $r['hour']), fn (string $k): string => (int) $k.'h', 'key'),
                'giong' => $this->group($rows, fn (array $r): string => (string) ($r['giong'] ?? '')),
                'nhac' => $this->group($rows, fn (array $r): string => (string) ($r['nhac'] ?? '')),
            ],
            'videos' => $sorted->take(self::LIST_LIMIT)->values()->all(),
            'videos_total' => $rows->count(),
            'top' => $ranked->take(5)->values()->all(),
            'bottom' => $ranked->count() > 5 ? $ranked->reverse()->take(5)->values()->all() : [],
            'metrics_count' => $ranked->count(),
            'updated_at' => now()->toIso8601String(),
            'collected_at' => $this->collectedAt($accountIds),
            'followers' => $this->followers($accountIds, $filters['channel'], $from, $to, $tz),
            'comments' => $this->comments($accountIds, $filters['channel'], $filters['cm']),
            'extension' => $this->extension($this->authorizeOwner($request)),
        ]);
    }

    private function scalar(Request $request, string $key): string
    {
        $v = $request->query($key);

        return is_string($v) ? trim($v) : '';
    }

    /**
     * Khoảng [từ, đến) theo múi giờ kênh; "đến" là đầu ngày kế tiếp.
     *
     * @return array{0: CarbonImmutable, 1: CarbonImmutable}
     */
    private function period(Request $request, string $range, string $tz): array
    {
        $today = CarbonImmutable::now($tz)->startOfDay();

        if ($range === 'custom') {
            try {
                $from = CarbonImmutable::createFromFormat('Y-m-d', $this->scalar($request, 'from'), $tz)->startOfDay();
                $to = CarbonImmutable::createFromFormat('Y-m-d', $this->scalar($request, 'to'), $tz)->startOfDay()->addDay();
            } catch (\Throwable) {
                return [$today->subDays(6), $today->addDay()];
            }

            if ($to <= $from) {
                return [$today->subDays(6), $today->addDay()];
            }

            if ($from->diffInDays($to) > self::MAX_DAYS) {
                $from = $to->subDays(self::MAX_DAYS);
            }

            return [$from, $to];
        }

        return match ($range) {
            'today' => [$today, $today->addDay()],
            '30d' => [$today->subDays(29), $today->addDay()],
            default => [$today->subDays(6), $today->addDay()],
        };
    }

    /**
     * Số liệu mới nhất, mốc 24h và 72h của từng video: ảnh chụp trước, AutoVideo.stats làm dự phòng.
     *
     * @param  Collection<int, AutoVideo>  $videos
     * @return array<int, array{latest: array<string, int>|null, h24: int|null, h72: int|null, link: string|null, insight: array<string, mixed>|null, collected_at: string|null}>
     */
    private function metricsFor(Collection $videos): array
    {
        $postIds = $videos->pluck('post_id')->filter()->unique()->values()->all();
        $remoteIds = $videos->pluck('tiktok_video_id')->filter()->unique()->values()->all();

        $publications = ($postIds === [] && $remoteIds === []) ? collect() : AnalyticsPublication::query()
            ->where(fn ($q) => $q
                ->when($postIds !== [], fn ($q2) => $q2->whereIn('post_id', $postIds))
                ->when($remoteIds !== [], fn ($q2) => $q2->orWhereIn('remote_id', $remoteIds)))
            ->get();

        $byPost = $publications->filter(fn ($p) => $p->post_id)->keyBy('post_id');
        $byRemote = $publications->filter(fn ($p) => $p->remote_id)->groupBy(fn ($p): string => (string) $p->remote_id);

        $snapshots = $publications->isEmpty() ? collect() : AnalyticsPublicationDailySnapshot::query()
            ->whereIn('publication_id', $publications->pluck('id')->all())
            ->orderBy('date')
            ->get()
            ->groupBy('publication_id');

        $vstats = $videos->isEmpty() ? collect() : VideoStat::query()->whereIn('auto_video_id', $videos->pluck('id')->all())->get()->keyBy('auto_video_id');

        $out = [];

        foreach ($videos as $v) {
            $pub = ($v->post_id ? $byPost[$v->post_id] ?? null : null)
                ?? ($v->tiktok_video_id ? ($byRemote[(string) $v->tiktok_video_id] ?? collect())->first(
                    fn ($p): bool => $v->social_account_id === null || (string) $p->social_account_id === (string) $v->social_account_id,
                ) : null);
            /** @var Collection<int, AnalyticsPublicationDailySnapshot> $snaps */
            $snaps = $pub ? ($snapshots[$pub->id] ?? collect()) : collect();

            $latest = null;
            $h24 = null;
            $h72 = null;

            if ($snaps->isNotEmpty()) {
                $last = $snaps->last();
                $latest = [
                    'views' => (int) $last->views_count,
                    'likes' => (int) $last->reactions_count,
                    'comments' => (int) $last->comments_count,
                    'shares' => (int) $last->shares_count,
                    'saves' => (int) $last->saves_count,
                ];

                $posted = CarbonImmutable::instance($v->posted_at);

                foreach ([24 => 'h24', 72 => 'h72'] as $hours => $key) {
                    $hit = $snaps->first(fn (AnalyticsPublicationDailySnapshot $s): bool => CarbonImmutable::instance($s->provider_observed_at ?? $s->collected_at ?? $s->date)->greaterThanOrEqualTo($posted->addHours($hours)));
                    ${$key} = $hit ? (int) $hit->views_count : null;
                }
            }

            // Số liệu do tiện ích đọc từ TikTok Studio là nguồn chính (mới nhất, có đủ lưu / thời gian xem).
            $vs = $vstats->get($v->id);

            if ($vs) {
                $latest = [
                    'views' => (int) $vs->views,
                    'likes' => (int) $vs->likes,
                    'comments' => (int) $vs->comments,
                    'shares' => (int) $vs->shares,
                    'saves' => (int) $vs->saves,
                ];
            }

            $stats = (array) ($v->stats ?? []);

            if ($latest === null && is_array($stats['latest'] ?? null)) {
                $l = $stats['latest'];
                $latest = [
                    'views' => (int) ($l['views'] ?? 0),
                    'likes' => (int) ($l['likes'] ?? 0),
                    'comments' => (int) ($l['comments'] ?? 0),
                    'shares' => (int) ($l['shares'] ?? 0),
                    'saves' => (int) ($l['saves'] ?? 0),
                ];
            }

            $h24 ??= isset($stats['h24']['views']) ? (int) $stats['h24']['views'] : null;
            $h72 ??= isset($stats['h72']['views']) ? (int) $stats['h72']['views'] : null;

            $link = $this->safeLink($pub?->permalink) ?? $this->safeLink($stats['link'] ?? null);

            $out[$v->id] = [
                'latest' => $latest,
                'h24' => $h24,
                'h72' => $h72,
                'link' => $link,
                'insight' => $vs?->insight_at ? [
                    'avg_watch_s' => $vs->avg_watch_s,
                    'finish_rate' => $vs->finish_rate,
                    'new_followers' => $vs->new_followers,
                    'traffic' => (array) ($vs->traffic ?? []),
                ] : null,
                'collected_at' => $vs?->collected_at?->toIso8601String(),
            ];
        }

        return $out;
    }

    /**
     * @param  array{latest: array<string, int>|null, h24: int|null, h72: int|null, link: string|null, insight: array<string, mixed>|null, collected_at: string|null}  $m
     * @return array<string, mixed>
     */
    private function row(AutoVideo $v, array $m, string $tz): array
    {
        $local = CarbonImmutable::instance($v->posted_at)->setTimezone($v->socialAccount?->timezone ?: $tz);
        $l = $m['latest'];
        $views = (int) ($l['views'] ?? 0);
        $likes = (int) ($l['likes'] ?? 0);
        $comments = (int) ($l['comments'] ?? 0);
        $shares = (int) ($l['shares'] ?? 0);
        $inter = $likes + $comments + $shares;

        return [
            'id' => $v->id,
            'file_name' => $v->file_name,
            'posted_at' => $v->posted_at->toIso8601String(),
            'date' => $local->format('Y-m-d'),
            'hour' => (int) $local->format('G'),
            'social_account_id' => $v->social_account_id,
            'channel' => $v->socialAccount ? '@'.($v->socialAccount->username ?: $v->socialAccount->display_name) : null,
            'product_code' => $v->product_code,
            'quy_cach' => $v->quy_cach,
            'cart_name' => $v->product_name,
            'goc' => $v->goc,
            'giong' => $v->giong,
            'nhac' => $v->nhac,
            'diem' => data_get($v->meta, 'diem'),
            'thoi_luong' => data_get($v->meta, 'thoi_luong') ?? $v->duration,
            'caption' => $v->caption,
            'has_metrics' => $l !== null,
            'views' => $views,
            'likes' => $likes,
            'comments' => $comments,
            'shares' => $shares,
            'saves' => (int) ($l['saves'] ?? 0),
            'interactions' => $inter,
            'engagement' => $views > 0 ? round($inter / $views * 100, 2) : 0.0,
            'views_24h' => $m['h24'],
            'views_72h' => $m['h72'],
            'link' => $m['link'],
            'avg_watch_s' => $m['insight']['avg_watch_s'] ?? null,
            'finish_rate' => isset($m['insight']['finish_rate']) ? round($m['insight']['finish_rate'] * 100, 1) : null,
            'new_followers' => $m['insight']['new_followers'] ?? null,
            'traffic' => $m['insight']['traffic'] ?? [],
            'collected_at' => $m['collected_at'],
        ];
    }

    /**
     * @param  Collection<int, array<string, mixed>>  $rows
     * @return Collection<int, array<string, mixed>>
     */
    private function sorted(Collection $rows, string $sort): Collection
    {
        $rows = match ($sort) {
            'view' => $rows->sortByDesc('views'),
            'tuong-tac' => $rows->sortByDesc('interactions'),
            default => $rows->sortByDesc('posted_at'),
        };

        $videos = AutoVideo::query()
            ->whereIn('id', $rows->take(self::LIST_LIMIT)->pluck('id')->all())->get()->keyBy('id');

        $images = ProductImages::lookup();

        return $rows->values()->map(function (array $r) use ($videos, $images): array {
            $v = $videos[$r['id']] ?? null;
            $r['product_image'] = $images->forSlot($r['social_account_id'] ? (string) $r['social_account_id'] : null, $r['product_code'], $r['quy_cach']);

            if ($v) {
                if (! filled($r['cart_name']) && $v->social_account_id && $v->product_code) {
                    $r['cart_name'] = ProductLink::slot((string) $v->social_account_id, (string) $v->product_code, $v->quy_cach)->value('display_name');
                }
            }

            return $r;
        });
    }

    /**
     * @param  Collection<int, array<string, mixed>>  $rows
     * @param  Collection<int, array<string, mixed>>  $prev
     * @return array<string, array{value: float|int, prev: float|int, delta_pct: float|null}>
     */
    private function kpis(Collection $rows, Collection $prev): array
    {
        $sum = function (Collection $c): array {
            $m = $c->filter(fn (array $r): bool => $r['has_metrics']);
            $views = (int) $m->sum('views');
            $inter = (int) $m->sum('interactions');

            return [
                'posts' => $c->count(),
                'views' => $views,
                'avg_views' => $m->count() > 0 ? round($views / $m->count(), 1) : 0,
                'likes' => (int) $m->sum('likes'),
                'comments' => (int) $m->sum('comments'),
                'shares' => (int) $m->sum('shares'),
                'saves' => (int) $m->sum('saves'),
                'engagement' => $views > 0 ? round($inter / $views * 100, 2) : 0,
                // Trung bình các video đã có chỉ số chi tiết (video ≤ 7 ngày).
                'avg_watch_s' => ($w = $m->filter(fn (array $r): bool => $r['avg_watch_s'] !== null))->isNotEmpty() ? round((float) $w->avg('avg_watch_s'), 1) : 0,
                'finish_rate' => ($f = $m->filter(fn (array $r): bool => $r['finish_rate'] !== null))->isNotEmpty() ? round((float) $f->avg('finish_rate'), 1) : 0,
            ];
        };

        $a = $sum($rows);
        $b = $sum($prev);
        $out = [];

        foreach ($a as $key => $value) {
            $out[$key] = [
                'value' => $value,
                'prev' => $b[$key],
                'delta_pct' => $b[$key] > 0 ? round(($value - $b[$key]) / $b[$key] * 100, 1) : null,
            ];
        }

        return $out;
    }

    /**
     * @param  Collection<int, array<string, mixed>>  $rows
     * @return list<array{date: string, posts: int, views: int}>
     */
    private function daily(Collection $rows, CarbonImmutable $from, int $days): array
    {
        $by = $rows->groupBy('date');
        $out = [];

        for ($i = 0; $i < min($days, self::MAX_DAYS); $i++) {
            $d = $from->addDays($i)->format('Y-m-d');
            $g = $by[$d] ?? collect();
            $out[] = ['date' => $d, 'posts' => $g->count(), 'views' => (int) $g->sum('views')];
        }

        return $out;
    }

    /**
     * @param  Collection<int, array<string, mixed>>  $rows
     * @return list<array{key: string, label: string, posts: int, views: int, avg_views: float, engagement: float}>
     */
    private function group(Collection $rows, callable $keyOf, ?callable $label = null, string $order = 'avg'): array
    {
        $groups = $rows->filter(fn (array $r): bool => $r['has_metrics'])
            ->groupBy($keyOf)->reject(fn ($g, $k): bool => (string) $k === '');

        $out = $groups->map(function (Collection $g, $key) use ($label): array {
            $views = (int) $g->sum('views');

            return [
                'key' => (string) $key,
                'label' => $label ? (string) $label((string) $key) : (string) $key,
                'posts' => $g->count(),
                'views' => $views,
                'avg_views' => round($views / $g->count(), 1),
                'engagement' => $views > 0 ? round($g->sum('interactions') / $views * 100, 2) : 0.0,
            ];
        });

        return ($order === 'key' ? $out->sortBy('key') : $out->sortByDesc('avg_views'))->values()->all();
    }

    /**
     * @param  Collection<int, SocialAccount>  $accounts
     * @param  list<string>  $accountIds
     * @param  Collection<string, AutoProduct>  $products
     * @return array<string, list<array<string, string|null>>>
     */
    private function options($accounts, array $accountIds, $products): array
    {
        $posted = fn () => AutoVideo::query()->livePosted()
            ->whereIn('social_account_id', $accountIds);

        $distinct = fn (string $col): array => $posted()->whereNotNull($col)->where($col, '!=', '')->distinct()->orderBy($col)->pluck($col)->all();
        $images = ProductImages::lookup();
        $codes = $posted()->whereNotNull('product_code')->distinct()->pluck('product_code')->all();

        return [
            'channels' => $accounts->map(fn (SocialAccount $a): array => ['id' => (string) $a->id, 'name' => '@'.($a->username ?: $a->display_name)])->values()->all(),
            'products' => collect($codes)->map(fn (string $c): array => ['code' => $c, 'name' => (string) ($products[$c]?->short_name ?? $c), 'image' => $images->forCode($c)])->sortBy('name')->values()->all(),
            'goc' => $distinct('goc'),
            'giong' => $distinct('giong'),
        ];
    }

    /** Lần thu số liệu gần nhất của các kênh đang xem. */
    private function collectedAt(array $accountIds): ?string
    {
        $at = VideoStat::query()->whereIn('social_account_id', $accountIds)->max('collected_at');

        return $at ? CarbonImmutable::parse($at, 'UTC')->toIso8601String() : null;
    }

    /**
     * Số người theo dõi: hiện tại, thay đổi trong kỳ và chuỗi theo ngày (nhiều kênh thì cộng lại).
     *
     * @param  list<string>  $accountIds
     * @return array{current: int, change: int|null, series: list<array{date: string, followers: int, gain: int|null}>, at: string|null}|null
     */
    private function followers(array $accountIds, string $channel, CarbonImmutable $from, CarbonImmutable $to, string $tz): ?array
    {
        $ids = $channel !== '' ? [$channel] : $accountIds;

        $rows = AccountStat::query()
            ->whereIn('social_account_id', $ids)
            ->whereNotNull('followers')
            ->where('date', '<=', $to->subDay()->format('Y-m-d'))
            ->where('date', '>=', $from->subDays(1)->format('Y-m-d'))
            ->orderBy('date')
            ->get();

        if ($rows->isEmpty()) {
            return null;
        }

        $byAccount = $rows->groupBy('social_account_id');
        $series = [];
        $prev = null;
        $days = (int) $from->diffInDays($to);

        for ($i = -1; $i < min($days, self::MAX_DAYS); $i++) {
            $d = $from->addDays($i)->format('Y-m-d');
            $sum = 0;
            $known = 0;

            foreach ($byAccount as $list) {
                $hit = $list->last(fn (AccountStat $r): bool => $r->date->format('Y-m-d') <= $d);

                if ($hit) {
                    $sum += (int) $hit->followers;
                    $known++;
                }
            }

            if ($known < $byAccount->count()) {
                continue;
            }

            if ($i >= 0) {
                $series[] = ['date' => $d, 'followers' => $sum, 'gain' => $prev === null ? null : $sum - $prev];
            }

            $prev = $sum;
        }

        if ($series === []) {
            return null;
        }

        $first = $series[0];
        $last = $series[count($series) - 1];

        return [
            'current' => $last['followers'],
            'change' => count($series) > 1 ? $last['followers'] - $first['followers'] : null,
            'series' => $series,
            'at' => $rows->max('collected_at')?->toIso8601String(),
        ];
    }

    /**
     * Bình luận mới nhất (mới nhất trước) và số đếm cho huy hiệu.
     *
     * @param  list<string>  $accountIds
     * @return array{counts: array{total: int, buy: int, buy_24h: int}, rows: list<array<string, mixed>>}
     */
    private function comments(array $accountIds, string $channel, string $filter): array
    {
        $base = fn () => VideoComment::query()
            ->whereIn('social_account_id', $accountIds)
            ->when($channel !== '', fn ($q) => $q->where('social_account_id', $channel));

        $counts = [
            'total' => $base()->count(),
            'buy' => $base()->where('is_buy_intent', true)->count(),
            'buy_24h' => $base()->where('is_buy_intent', true)->where('commented_at', '>=', now()->subDay())->count(),
        ];

        $list = $base()
            ->when($filter === 'mua', fn ($q) => $q->where('is_buy_intent', true))
            ->orderByDesc('commented_at')->orderByDesc('id')
            ->limit(self::COMMENT_LIMIT)
            ->get();

        $names = SocialAccount::query()->whereIn('id', $list->pluck('social_account_id')->filter()->unique())->pluck('username', 'id');
        $captions = VideoStat::query()->whereIn('item_id', $list->pluck('item_id')->unique())->pluck('caption', 'item_id');
        $products = AutoProduct::query()->get()->keyBy('code');
        $videos = AutoVideo::query()->whereIn('id', $list->pluck('auto_video_id')->filter()->unique())->get(['id', 'product_code'])->keyBy('id');

        $rows = $list->map(function (VideoComment $c) use ($names, $captions, $videos, $products): array {
            $user = (string) ($names[$c->social_account_id] ?? '');
            $code = $c->auto_video_id ? $videos->get($c->auto_video_id)?->product_code : null;
            $caption = trim((string) preg_replace('/\s+/u', ' ', (string) ($captions[$c->item_id] ?? '')));

            return [
                'id' => $c->id,
                'text' => $c->text,
                'author' => $c->author_name ?: $c->author_handle,
                'handle' => $c->author_handle,
                'likes' => $c->like_count,
                'replies' => $c->reply_count,
                'at' => ($c->commented_at ?? $c->created_at)?->toIso8601String(),
                'buy' => $c->is_buy_intent,
                'keywords' => $c->intent_keywords,
                'video_id' => $c->auto_video_id,
                'video_label' => $code ? (string) ($products[$code]?->short_name ?? $code) : ($caption !== '' ? mb_strimwidth($caption, 0, 60, '…') : null),
                'channel' => $user !== '' ? '@'.$user : null,
                'link' => $user !== '' ? "https://www.tiktok.com/@{$user}/video/{$c->item_id}" : null,
            ];
        })->values()->all();

        return ['counts' => $counts, 'rows' => $rows];
    }

    /**
     * Tiện ích Chrome đang kết nối: bản cũ hơn 1.4.0 không thu được số liệu, trang hiện banner "Tải lại tiện ích".
     *
     * @return array{connected: bool, version: string|null, outdated: bool, min: string, last_seen_at: string|null}
     */
    private function extension(string $accountId): array
    {
        $clients = ChromeClient::query()->where('account_id', $accountId)->whereNull('revoked_at')->orderByDesc('last_seen_at')->get();
        $client = $clients->first();
        $outdated = $clients->contains(fn (ChromeClient $c): bool => version_compare((string) ($c->ext_version ?: '0'), self::MIN_EXTENSION_VERSION, '<'));

        return [
            'connected' => $client !== null,
            'version' => $client?->ext_version,
            'outdated' => $outdated,
            'min' => self::MIN_EXTENSION_VERSION,
            'last_seen_at' => $client?->last_seen_at?->toIso8601String(),
        ];
    }

    private function safeLink(mixed $link): ?string
    {
        return is_string($link) && preg_match('#^https://#i', $link) === 1 ? $link : null;
    }
}

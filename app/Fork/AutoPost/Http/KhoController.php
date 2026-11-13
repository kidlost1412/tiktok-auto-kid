<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Hub\HubApi;
use App\Fork\AutoPost\Hub\HubFiles;
use App\Fork\AutoPost\Hub\HubOutboxItem;
use App\Fork\AutoPost\KhoStore;
use App\Fork\AutoPost\Media\ProductImageLookup;
use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\VideoComment;
use App\Fork\AutoPost\Paths;
use App\Fork\AutoPost\Rieng\RiengFolder;
use App\Fork\AutoPost\Rieng\RiengInfo;
use App\Fork\AutoPost\Rieng\RiengReady;
use App\Fork\AutoPost\Rieng\RiengThumbs;
use App\Fork\AutoPost\Scheduling\Readiness;
use App\Fork\AutoPost\Scheduling\RetryFailed;
use App\Fork\AutoPost\Shop\HubCartAttach;
use App\Fork\AutoPost\Sidecar;
use App\Fork\AutoPost\VideoLibrary;
use App\Http\Controllers\Controller;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Inertia\Inertia;
use Inertia\Response;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;
use Throwable;

/**
 * Trang "Kho video": chuẩn kho-dang, cài đặt lưu giữ, số lượng theo sản phẩm x quy cách, danh sách video.
 */
final class KhoController extends Controller
{
    private const int PER_PAGE = 30;

    /** Tab trạng thái → các trạng thái video. */
    private const array TABS = [
        'cho' => [AutoVideo::NEW],
        'xep' => [AutoVideo::RESERVED, AutoVideo::SCHEDULED],
        'dang' => [AutoVideo::POSTED],
        'loi' => [AutoVideo::FAILED, AutoVideo::SKIPPED],
    ];

    /**
     * Lọc theo tab. Video posted có giờ đăng ở tương lai (đã hẹn sẵn trên TikTok) thuộc tab "xếp", không thuộc "đã đăng".
     *
     * @param  Builder<AutoVideo>  $q
     */
    private function applyTab($q, string $tab): void
    {
        if ($tab === 'all') {
            return;
        }

        match ($tab) {
            'xep' => $q->where(fn ($w) => $w->whereIn('status', self::TABS['xep'])->orWhere(fn ($h) => $h->heldOnTikTok())),
            'dang' => $q->livePosted(),
            default => $q->whereIn('status', self::TABS[$tab]),
        };
    }

    /** Biểu thức SQL "ngày" (giờ VN, dạng date) theo tab: ngày đăng / ngày hẹn / ngày làm video. Cột timestamp lưu UTC. */
    private function dayExpression(string $tab): string
    {
        $vn = fn (string $col): string => "(({$col} at time zone 'UTC') at time zone 'Asia/Ho_Chi_Minh')::date";

        return match ($tab) {
            'dang' => $vn('posted_at'),
            'xep' => $vn('coalesce(scheduled_for, posted_at)'),
            default => 'batch_date',
        };
    }

    public function index(Request $request): Response
    {
        $this->authorizeOwner($request);
        $kho = app(KhoStore::class);

        $tab = $request->query('tab');
        $tab = is_string($tab) && ($tab === 'all' || isset(self::TABS[$tab])) ? $tab : 'cho';
        $product = $request->query('product');
        $product = is_string($product) ? $product : '';
        $showLegacy = $request->boolean('legacy');
        $sort = $request->query('sort') === 'sap-dang' ? 'sap-dang' : 'moi';
        $search = $request->query('q');
        $search = is_string($search) ? trim(mb_substr($search, 0, 100)) : '';
        $like = '%'.addcslashes($search, '%_'.chr(92)).'%';

        // Bản ghi cũ (nguồn `ra`) ẩn mặc định.
        // Video riêng của chủ app có trang "Kho riêng" riêng, không lẫn vào kho hub.
        $base = fn () => AutoVideo::query()->notRieng()->when(! $showLegacy, fn ($q) => $q->where('source', '!=', 'ra'));
        $day = $request->query('day');
        $day = is_string($day) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $day) === 1 ? $day : '';
        $dayExpr = $this->dayExpression($tab);

        // Số trên tab KHÔNG phụ thuộc sản phẩm đang chọn; số trên chip sản phẩm tính trong tab đang chọn.
        $statusCounts = $base()
            ->selectRaw(AutoVideo::effectiveStatusSql().' as eff, count(*) as total')->groupByRaw('eff')->pluck('total', 'eff');
        $counts = ['all' => (int) $statusCounts->sum()];

        foreach (self::TABS as $key => $statuses) {
            $counts[$key] = (int) collect($statuses)->sum(fn (string $s): int => (int) ($statusCounts[$s] ?? 0));
        }

        // Số theo sản phẩm tính trong tab đang chọn .
        $productCounts = $base()
            ->tap(fn ($q) => $this->applyTab($q, $tab))
            ->select('product_code', DB::raw('count(*) as total'))->groupBy('product_code')->pluck('total', 'product_code');

        $legacyCount = AutoVideo::query()->where('source', 'ra')->count();

        // Các ngày để chọn trong bộ lọc ngày (mặc định "Tất cả ngày" = không lọc).
        $days = $base()->tap(fn ($q) => $this->applyTab($q, $tab))
            ->selectRaw($dayExpr.' as d')->whereRaw($dayExpr.' is not null')->groupByRaw($dayExpr)->orderByRaw($dayExpr.' desc')->limit(120)->pluck('d')
            ->map(fn ($d): string => (string) $d)->values()->all();

        $videos = $base()
            ->with('socialAccount:id,username,display_name,avatar_url')
            ->tap(fn ($q) => $this->applyTab($q, $tab))
            ->when($day !== '', fn ($q) => $q->whereRaw($dayExpr.' = ?', [$day]))
            ->when($product !== '', fn ($q) => $q->where('product_code', $product))
            ->when($search !== '', fn ($q) => $q->where(fn ($w) => $w
                ->where('caption', 'ilike', $like)
                ->orWhere('file_name', 'ilike', $like)))
            ->when(
                $sort === 'sap-dang',
                fn ($q) => $q->orderByRaw('scheduled_for asc nulls last'),
                fn ($q) => $q->orderByDesc($tab === 'dang' ? 'posted_at' : 'id'),
            )
            ->orderByDesc('id')
            ->paginate(self::PER_PAGE)
            ->withQueryString();

        $products = AutoProduct::query()->orderBy('short_name')->get()->keyBy('code');

        $images = ProductImages::lookup();
        $readiness = app(Readiness::class);
        $waiting = $base()->where('status', AutoVideo::NEW)->get();
        $assessed = $readiness->assess($waiting);

        return Inertia::render('fork/Kho', [
            'kho' => [
                'path' => $kho->khoPath(),
                'done_path' => $kho->donePath(),
                'error_path' => $kho->khoPath().'/_loi',
                'exists' => is_dir($kho->khoPath()),
                'legacy_ra' => (bool) config('fork.auto.legacy_ra', true),
                ...$kho->folderCounts(),
            ],
            'retention' => [
                'value' => $kho->retention(),
                'options' => [
                    ['value' => 'xoa_ngay', 'label' => 'Xoá file ngay khi đã đăng (chỉ giữ kết quả)'],
                    ['value' => '7', 'label' => 'Giữ 7 ngày'],
                    ['value' => '30', 'label' => 'Giữ 30 ngày'],
                    ['value' => 'vinh_vien', 'label' => 'Giữ vĩnh viễn'],
                ],
            ],
            'hub' => $this->hubStatus(false),
            'matrix' => $this->matrix($products, $images),
            'products' => $products->map(fn (AutoProduct $p): array => [
                'code' => $p->code,
                'name' => $p->short_name,
                'image' => $images->forCode($p->code),
                'count' => (int) ($productCounts[$p->code] ?? 0),
            ])->values()->all(),
            'filters' => ['tab' => $tab, 'product' => $product, 'legacy' => $showLegacy, 'sort' => $sort, 'q' => $search, 'day' => $day],
            'days' => $days,
            'counts' => $counts,
            'legacy_count' => $legacyCount,
            'blockers' => $readiness->summarize($assessed, $waiting),
            'videos' => [
                'data' => $videos->getCollection()->map(fn (AutoVideo $v): array => $this->videoRow($v, $products, $assessed[$v->id] ?? $this->singleAssessment($readiness, $v), $images))->values()->all(),
                'current_page' => $videos->currentPage(),
                'last_page' => $videos->lastPage(),
                'total' => $videos->total(),
            ],
            'updated_at' => now()->toIso8601String(),
            'last_ingest_at' => Cache::get(VideoLibrary::LAST_INGEST_CACHE_KEY),
        ]);
    }

    public function settings(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        abort_if(HubApi::enabled(), SymfonyResponse::HTTP_CONFLICT, 'Hub tự dọn file sau 30 ngày.');

        $data = $request->validate(['retention' => ['required', 'in:'.implode(',', KhoStore::RETENTIONS)]]);
        AutoSetting::write(KhoStore::RETENTION_KEY, $data['retention']);

        return back()->with('flash.success', 'Đã lưu cài đặt lưu giữ.');
    }

    /** Kiểm tra kết nối hub ngay (bỏ qua bộ nhớ đệm 1 phút). */
    public function ping(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);
        $hub = $this->hubStatus(true);

        return back()->with('flash.success', 'Kết nối hub: '.$hub['label']);
    }

    /**
     * @return array{enabled: bool, url: string, state: string, label: string, pending: int}
     */
    private function hubStatus(bool $fresh): array
    {
        $api = new HubApi;
        $state = 'off';

        if (HubApi::enabled()) {
            $key = 'fork-hub:ping';
            $fresh && Cache::forget($key);
            $state = Cache::remember($key, 60, fn (): string => $api->ping());
        }

        $label = match ($state) {
            HubApi::OK => 'đang hoạt động',
            HubApi::OFFLINE => 'hub đang tắt',
            HubApi::BAD_KEY => 'sai khoá',
            'off' => 'chưa bật chế độ API (đang dùng thư mục hub)',
            default => 'hub trả lời lỗi',
        };

        return [
            'enabled' => HubApi::enabled(),
            'url' => $api->url(),
            'state' => $state,
            'label' => $label,
            'pending' => HubApi::enabled() ? HubOutboxItem::query()->count() : 0,
        ];
    }

    /** Quét kho ngay (không đợi lịch 5 phút). */
    public function scan(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);
        set_time_limit(300);

        $library = app(VideoLibrary::class);
        $library->syncProducts();
        try {
            app(HubCartAttach::class)->run();   // sản phẩm Shop chọn ở Xưởng → gắn giỏ ngay, không chờ 5 phút
        } catch (Throwable) {
        }
        $r = $library->ingest();

        if (HubApi::enabled()) {
            return back()->with('flash.success', "Đã lấy từ hub: {$r['new']} video mới, {$r['skipped']} bỏ duyệt, trạng thái {$library->apiReport['state']}.");
        }

        return back()->with('flash.success', "Đã quét kho: {$r['new']} video mới, {$library->khoReport['error']} lỗi, {$library->khoReport['waiting']} đang chờ.");
    }

    /** Phát video cho khung xem trước. Chỉ phục vụ file nằm dưới thư mục hub, tra bằng id trong DB. */
    public function video(Request $request, AutoVideo $video): BinaryFileResponse|SymfonyResponse
    {
        $this->authorizeOwner($request);

        // Video riêng: chỉ phát file nằm dưới thư mục Kho riêng đã đăng ký.
        if ($video->isRieng()) {
            $own = RiengController::safeVideoPath($video);
            abort_if($own === null, SymfonyResponse::HTTP_NOT_FOUND);

            return response()->file($own, ['Content-Type' => RiengReady::mimeFor($own), 'Cache-Control' => 'private, max-age=300']);
        }

        $hub = realpath(app(KhoStore::class)->hub());
        $file = $video->files_deleted_at === null ? realpath((string) $video->path) : false;

        if ($hub !== false && $file !== false && Paths::isUnder($file, $hub)
            && strtolower(pathinfo($file, PATHINFO_EXTENSION)) === 'mp4' && is_file($file)) {
            return $this->serve($file, 'video/mp4', 'private, max-age=300', $hub);
        }

        // Máy không gắn thư mục hub: dùng/tải bản cache (tên cache do ta đặt từ hub_id đã kiểm tra, nằm trong hub-cache).
        $cached = $video->files_deleted_at === null ? $this->cachedVideo($video) : null;

        abort_if($cached === null, SymfonyResponse::HTTP_NOT_FOUND);

        return $this->serve($cached, 'video/mp4', 'private, max-age=300', $hub);
    }

    /** Thông tin đầy đủ của một video cho khung xem (mở từ lịch, bài vừa đăng, số liệu, kho). */
    public function info(Request $request, AutoVideo $video): JsonResponse
    {
        $this->authorizeOwner($request);
        $video->load('socialAccount:id,username,display_name,avatar_url');

        $readiness = app(Readiness::class);
        $products = AutoProduct::query()->get()->keyBy('code');

        $row = $this->videoRow($video, $products, $this->singleAssessment($readiness, $video), ProductImages::lookup());
        $row['comments'] = $this->commentsOf($video);

        return response()->json($row);
    }

    /** Ảnh bìa do hub gửi (đường dẫn tương đối trong meta.anh_bia). Chỉ phục vụ ảnh nằm dưới thư mục hub. */
    public function cover(Request $request, AutoVideo $video): BinaryFileResponse|SymfonyResponse
    {
        $this->authorizeOwner($request);

        if ($video->isRieng()) {
            $thumb = app(RiengThumbs::class)->get($video);
            abort_if($thumb === null, SymfonyResponse::HTTP_NOT_FOUND);

            return response()->file($thumb, ['Content-Type' => 'image/jpeg', 'Cache-Control' => 'private, max-age=86400']);
        }

        $rel = data_get($video->meta, 'anh_bia');
        $hub = realpath(app(KhoStore::class)->hub());
        $file = false;

        if ($hub !== false && is_string($rel) && $rel !== '' && ! str_contains($rel, "\0")) {
            $rel = ltrim(str_replace('\\', '/', $rel), '/');
            // Hub chuyển file đi kèm vào <thư mục ngày>/_kem/: tìm ở đó trước, rồi mới tới chỗ cũ.
            $kem = dirname($rel) === '.' ? Sidecar::DIR.'/'.basename($rel) : dirname($rel).'/'.Sidecar::DIR.'/'.basename($rel);

            foreach ([$kem, $rel] as $candidate) {
                $real = realpath($hub.DIRECTORY_SEPARATOR.$candidate);

                if ($real !== false && is_file($real)) {
                    $file = $real;
                    break;
                }
            }
        }
        $types = ['jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg', 'png' => 'image/png', 'webp' => 'image/webp'];
        $ext = $file === false ? '' : strtolower(pathinfo($file, PATHINFO_EXTENSION));

        if ($hub !== false && $file !== false && Paths::isUnder($file, $hub) && isset($types[$ext]) && is_file($file)) {
            return $this->serve($file, $types[$ext], 'private, max-age=3600', $hub);
        }

        $cached = app(HubFiles::class)->cover($video);

        abort_if($cached === null, SymfonyResponse::HTTP_NOT_FOUND);

        return $this->serve($cached, 'image/jpeg', 'private, max-age=3600', $hub);
    }

    /**
     * Trả file đã được kiểm quyền. Chạy sau Caddy (fork.auto.accel) thì chỉ trả 302 tới /media/ra/... (thư mục hub/ra)
     * hoặc /media/cache/... (storage/app/hub-cache) để Caddy phát file (Range, không giữ worker PHP); file ngoài hai thư mục đó
     * vẫn do PHP phát.
     */
    private function serve(string $file, string $type, string $cache, string|false $hub): BinaryFileResponse|SymfonyResponse
    {
        if (config('fork.auto.accel') && ! str_contains($file, "\0")) {
            $real = realpath($file);
            $roots = [
                '/media/ra/' => $hub !== false ? realpath($hub.'/ra') : false,
                '/media/cache/' => realpath(app(HubFiles::class)->cacheDir()),
            ];

            foreach ($roots as $prefix => $root) {
                if ($real !== false && $root !== false && Paths::isUnder($real, $root)) {
                    $rel = substr(Paths::slash($real), strlen(rtrim(Paths::slash($root), '/')) + 1);

                    if (! preg_match('#(^|/)\.\.?(/|$)#', $rel)) {
                        return response('', 302, [
                            'Location' => $prefix.implode('/', array_map('rawurlencode', explode('/', $rel))),
                            'Cache-Control' => $cache,
                        ]);
                    }
                }
            }
        }

        return response()->file($file, ['Content-Type' => $type, 'Cache-Control' => $cache]);
    }

    private function cachedVideo(AutoVideo $video): ?string
    {
        try {
            return app(HubFiles::class)->cachedVideo($video);
        } catch (Throwable) {
            return null;
        }
    }

    /**
     * @param  Collection<string, AutoProduct>  $products
     * @return list<array<string, mixed>>
     */
    private function matrix($products, ProductImageLookup $images): array
    {
        $rows = AutoVideo::query()->notRieng()
            ->selectRaw('product_code, quy_cach, '.AutoVideo::effectiveStatusSql().' as eff, count(*) as total')
            ->groupByRaw('product_code, quy_cach, eff')
            ->get();

        $out = [];

        foreach ($rows as $r) {
            $key = $r->product_code.'|'.($r->quy_cach ?? '');
            $out[$key] ??= [
                'code' => $r->product_code,
                'name' => $products[$r->product_code]?->short_name ?? ($r->product_code ?? '(chưa rõ sản phẩm)'),
                'image' => $images->forCode($r->product_code),
                'quy_cach' => $r->quy_cach,
                'quy_cach_name' => $this->quyCachName($products[$r->product_code] ?? null, $r->quy_cach),
                'new' => 0, 'scheduled' => 0, 'posted' => 0, 'failed' => 0, 'skipped' => 0,
            ];
            $bucket = match ($r->eff) {
                AutoVideo::NEW => 'new',
                AutoVideo::RESERVED, AutoVideo::SCHEDULED => 'scheduled',
                AutoVideo::POSTED => 'posted',
                AutoVideo::FAILED => 'failed',
                default => 'skipped',
            };
            $out[$key][$bucket] += (int) $r->total;
        }

        // Sản phẩm chưa có video nào vẫn hiện một dòng 0.
        foreach ($products as $p) {
            if (! collect($out)->contains(fn (array $x): bool => $x['code'] === $p->code)) {
                $out[$p->code.'|'] = [
                    'code' => $p->code, 'name' => $p->short_name, 'image' => $images->forCode($p->code), 'quy_cach' => null, 'quy_cach_name' => null,
                    'new' => 0, 'scheduled' => 0, 'posted' => 0, 'failed' => 0, 'skipped' => 0,
                ];
            }
        }

        ksort($out);

        return array_values($out);
    }

    private function quyCachName(?AutoProduct $product, ?string $code): ?string
    {
        if ($code === null) {
            return null;
        }

        foreach ((array) $product?->quy_cach as $q) {
            if (($q['ma'] ?? null) === $code) {
                return (string) ($q['ten'] ?? $code);
            }
        }

        return $code;
    }

    /**
     * Video `new` ngoài danh sách tải sẵn: đánh giá riêng.
     *
     * @return array<string, mixed>|null
     */
    private function singleAssessment(Readiness $readiness, AutoVideo $v): ?array
    {
        // Video riêng không có "sẵn sàng" kiểu hub (không kiểm sản phẩm hub): chỉ gợi ý trung tính nếu chưa gắn sản phẩm.
        if ($v->isRieng()) {
            return $v->status === AutoVideo::NEW && ! filled($v->product_code)
                ? ['code' => Readiness::RIENG, 'severity' => 'muted', 'reason' => 'Chưa gắn sản phẩm — chọn khi đăng', 'next_slot' => null]
                : null;
        }

        return $v->status === AutoVideo::NEW ? ($readiness->assess(collect([$v]))[$v->id] ?? null) : null;
    }

    /**
     * @param  Collection<string, AutoProduct>  $products
     * @param  array<string, mixed>|null  $assessment
     * @return array<string, mixed>
     */
    /**
     * Bình luận gần nhất của một video (khung xem video).
     *
     * @return array{total: int, buy: int, rows: list<array<string, mixed>>}
     */
    private function commentsOf(AutoVideo $video): array
    {
        $q = fn () => VideoComment::query()->where(fn ($w) => $w
            ->where('auto_video_id', $video->id)
            ->when(filled($video->tiktok_video_id), fn ($w2) => $w2->orWhere('item_id', (string) $video->tiktok_video_id)));

        return [
            'total' => $q()->count(),
            'buy' => $q()->where('is_buy_intent', true)->count(),
            'rows' => $q()->orderByDesc('commented_at')->orderByDesc('id')->limit(12)->get()->map(fn (VideoComment $c): array => [
                'id' => $c->id,
                'text' => $c->text,
                'author' => $c->author_name ?: $c->author_handle,
                'likes' => $c->like_count,
                'at' => $c->commented_at?->toIso8601String(),
                'buy' => $c->is_buy_intent,
            ])->values()->all(),
        ];
    }

    private function videoRow(AutoVideo $v, $products, ?array $assessment, ProductImageLookup $images): array
    {
        $tz = 'Asia/Ho_Chi_Minh';
        $held = $v->status === AutoVideo::POSTED && $v->posted_at?->isFuture();
        $stats = (array) data_get($v->stats, 'latest', []);
        $link = data_get($v->stats, 'link');
        $channel = $v->socialAccount ? '@'.($v->socialAccount->username ?: $v->socialAccount->display_name) : null;

        $cartName = $v->product_name;

        if (! filled($cartName) && $v->social_account_id && $v->product_code) {
            $cartName = ProductLink::slot((string) $v->social_account_id, (string) $v->product_code, $v->quy_cach)->value('display_name');
        }

        return [
            'id' => $v->id,
            'file_name' => $v->file_name,
            'product' => $products[$v->product_code]?->short_name ?? $v->product_code,
            'product_code' => $v->product_code,
            'quy_cach' => $this->quyCachName($products[$v->product_code] ?? null, $v->quy_cach),
            'goc' => $v->goc,
            'ngay_lam' => $v->batch_date?->format('Y-m-d'),
            'status' => $v->effectiveStatus(),
            'on_tiktok_schedule' => $held,
            'product_image' => $images->forSlot($v->social_account_id ? (string) $v->social_account_id : null, $v->product_code, $v->quy_cach),
            'channel_avatar' => $v->socialAccount?->avatar_url,
            'stats' => $stats === [] ? null : [
                'views' => data_get($stats, 'views'), 'likes' => data_get($stats, 'likes'),
                'comments' => data_get($stats, 'comments'), 'shares' => data_get($stats, 'shares'),
                'saves' => data_get($stats, 'saves'),
                'views_24h' => data_get($v->stats, 'h24.views'),
                'views_72h' => data_get($v->stats, 'h72.views'),
                // Chỉ số chi tiết của video ≤ 7 ngày do tiện ích đọc từ TikTok Studio.
                'avg_watch_s' => data_get($v->stats, 'insight.avg_watch_s'),
                'finish_rate' => is_numeric(data_get($v->stats, 'insight.finish_rate')) ? round((float) data_get($v->stats, 'insight.finish_rate') * 100, 1) : null,
                'new_followers' => data_get($v->stats, 'insight.new_followers'),
                'traffic' => array_values((array) data_get($v->stats, 'insight.traffic', [])),
                'collected_at' => data_get($stats, 'at'),
            ],
            'legacy' => $v->source === 'ra',
            'caption' => $v->caption,
            'hashtags' => array_values(array_filter((array) $v->hashtags, 'is_string')),
            'cart_name' => filled($cartName) ? (string) $cartName : null,
            'channel' => $channel,
            'scheduled_for' => ($held ? $v->posted_at : $v->scheduled_for)?->copy()->timezone($tz)->toIso8601String(),
            'posted_at' => $held ? null : $v->posted_at?->copy()->timezone($tz)->toIso8601String(),
            'reason' => $v->skip_reason,
            // Bài lỗi chắc chắn chưa lên TikTok thì hiện nút "Thử lại" (máy chủ vẫn kiểm lại khi bấm).
            'can_retry' => $v->status === AutoVideo::FAILED && app(RetryFailed::class)->refusal($v) === null,
            'readiness' => $assessment,
            'has_cover' => $v->isRieng() || (is_string(data_get($v->meta, 'anh_bia')) && data_get($v->meta, 'anh_bia') !== '') || app(HubFiles::class)->hasCoverUrl($v),
            'duration' => $v->duration,
            'tiktok_link' => is_string($link) && preg_match('#^https://#i', $link) === 1 ? $link : null,
            'can_preview' => $v->files_deleted_at === null && (($v->path !== '' && is_file($v->path)) || app(HubFiles::class)->available($v)),
            ...($v->isRieng() ? $this->riengExtras($v, $products, $images) : []),
        ];
    }

    /**
     * Phần riêng của video Kho riêng trong khung xem: không áp kiểm tra sản phẩm hub; có cờ trùng, sản phẩm đã gắn và liên kết.
     *
     * @param  Collection<string, AutoProduct>  $products
     * @return array<string, mixed>
     */
    private function riengExtras(AutoVideo $v, $products, ProductImageLookup $images): array
    {
        $info = new RiengInfo;
        $of = data_get($v->meta, 'duplicate_of');

        return [
            'rieng' => true,
            'rieng_selectable' => ($v->status === AutoVideo::NEW && $v->files_deleted_at === null) || $v->status === AutoVideo::FAILED,
            'duplicate' => is_numeric($of) ? ($info->duplicates([$v])[(int) $v->id] ?? null) : null,
            'rieng_product' => $info->product($v, $products, $images),
            'folder' => RiengFolder::query()->find((int) data_get($v->meta, 'folder_id'))?->displayName(),
        ];
    }

    private function authorizeOwner(Request $request): void
    {
        abort_unless(
            $request->user()?->isAccountOwner(),
            SymfonyResponse::HTTP_FORBIDDEN,
        );
    }
}

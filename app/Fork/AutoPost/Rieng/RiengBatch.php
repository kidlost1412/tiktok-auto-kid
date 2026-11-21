<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Media\ProductImageLookup;
use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductCover;
use App\Fork\AutoPost\Persona\CoverStore;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Scheduling\MissingVideoFile;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\AutoPost\Scheduling\PostBuilder;
use App\Fork\AutoPost\Scheduling\ProductMix;
use App\Fork\AutoPost\Scheduling\RetryFailed;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\VideoLibrary;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Closure;
use Illuminate\Contracts\Cache\LockTimeoutException;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use InvalidArgumentException;
use Throwable;

/**
 * Đăng hàng loạt video riêng: chọn kênh + sản phẩm giỏ hàng + caption, rồi hẹn giờ tự động (giờ trống gần nhất theo Planner)
 * hoặc thủ công (kiểm trùng giờ). Mỗi video: giữ chỗ như reserveClaimed (không qua hub) rồi PostBuilder::build; lỗi thì nhả video.
 *
 * Không bao giờ đụng bài đã giữ chỗ/xếp lịch/đăng của người khác: chỉ lấy giờ còn trống (Planner::slotsFor đã loại giờ bận).
 */
final class RiengBatch
{
    public const MODE_AUTO = 'auto';

    public const MODE_MANUAL = 'manual';

    /** Cách chọn ảnh bìa: bìa của sản phẩm (xoay vòng), ảnh tải lên, hoặc một khung trong video. */
    public const COVER_PRODUCT = 'product';

    /** Số ảnh bìa sản phẩm báo trước cho giao diện (đủ cho một lượt đăng hàng loạt). */
    private const int COVER_PLAN_MAX = 60;

    public const COVER_UPLOAD = 'upload';

    public const COVER_FRAME = 'frame';

    /** product_code của lượt = "theo sản phẩm của từng video" (AI đã nhận ra / chủ app đã chọn cho video). */
    public const string PER_VIDEO = 'theo-video';

    /** Hai bài cùng kênh cách nhau dưới ngần này giây coi là trùng giờ y hệt (không cho đăng dù đã xác nhận). */
    public const int EXACT_SECONDS = 60;

    /** Đã giữ chỗ/xếp lịch/đăng: các trạng thái làm bận giờ (giống Planner). */
    private const array COUNTED = ['reserved', 'scheduled', 'posted'];

    public function __construct(
        private readonly Planner $planner,
        private readonly VideoLibrary $library,
        private readonly PostBuilder $builder,
        private readonly CartRules $cart,
        private readonly RetryFailed $retry,
    ) {}

    /**
     * Các cặp (sản phẩm, quy cách) dùng được cho một kênh: có liên kết giỏ hàng hợp lệ (CartRules) và sản phẩm đang bật.
     *
     * @return list<array{code: string, quy_cach: ?string, label: string, name: string, tags: list<string>, image: ?string}>
     */
    public function productOptions(string $socialAccountId, ?ProductImageLookup $images = null): array
    {
        $allowed = $this->cart->evaluate($socialAccountId)['allowed'];
        $products = AutoProduct::query()->where('enabled', true)->whereIn('code', array_keys($allowed))->get()->keyBy('code');
        $images ??= ProductImages::lookup([$socialAccountId]);
        $out = [];

        foreach ($allowed as $code => $quyCaches) {
            $product = $products[$code] ?? null;

            if ($product === null) {
                continue;
            }

            foreach ($quyCaches as $qc) {
                $out[] = [
                    'code' => (string) $code,
                    'quy_cach' => $qc,
                    'label' => CartRules::label($product, (string) $code, $qc),
                    'name' => (string) ($product->short_name ?: $code),
                    // Ảnh sản phẩm TikTok Shop đã gắn giỏ trên kênh này (ảnh có sẵn của app, không tải thêm).
                    'image' => $images->forSlot($socialAccountId, (string) $code, $qc),
                    'tags' => app(Hashtags::class)->configFor($product)['tags'],
                    ...(fn (array $c): array => ['cover_count' => $c['count'], 'cover_plan' => $c['plan']])($this->productCoverInfo($product, (string) $socialAccountId, self::COVER_PLAN_MAX)),
                ];
            }
        }

        return $out;
    }

    /**
     * @param  array<string, mixed>  $in
     * @return array<string, mixed>
     */
    public function preview(array $in, ?CarbonImmutable $now = null): array
    {
        return $this->evaluate($in, $now ?? CarbonImmutable::now());
    }

    /**
     * Chỉ đề xuất giờ (không cần sản phẩm/caption, không ghi gì): để hộp đăng điền sẵn giờ cho từng video ngay khi mở.
     * `items.*.at` = giờ chủ app đã sửa (giữ nguyên và kiểm), còn lại tự xếp.
     *
     * @param  array<string, mixed>  $in
     * @return array{ok: bool, error: ?string, rows: list<array{id: int, at: ?string, status: string, messages: list<string>, edited: bool}>, left: int, window: ?string, gap_minutes: int}
     */
    public function propose(array $in, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $gapMinutes = intdiv($this->planner->gapSeconds(), 60);
        $auto = AutoAccount::query()->find((string) ($in['social_account_id'] ?? ''));

        if ($auto === null) {
            return ['ok' => false, 'error' => 'Hãy chọn kênh TikTok.', 'rows' => [], 'left' => 0, 'window' => null, 'gap_minutes' => $gapMinutes];
        }

        $tz = $this->planner->timezoneFor($auto);
        $fmt = fn (int $ts): string => CarbonImmutable::createFromTimestampUTC($ts)->setTimezone($tz)->format('H:i d/m');
        $rows = [];
        $seen = [];

        foreach (array_values(array_filter((array) ($in['items'] ?? []), 'is_array')) as $item) {
            $id = (int) ($item['id'] ?? 0);

            if ($id <= 0 || isset($seen[$id])) {
                continue;
            }

            $seen[$id] = true;
            $rows[] = ['id' => $id, 'status' => 'ok', 'messages' => [], 'at' => null, '_at' => $this->parseAt($item['at'] ?? null)];
        }

        $products = $this->videoProducts(array_column($rows, 'id'), (string) $auto->social_account_id);

        // Sản phẩm của từng dòng giống lúc đăng thật (để giờ xen kẽ ở bước xem trước khớp bước đăng):
        // chọn riêng trong hộp > sản phẩm chung của lượt > sản phẩm của chính video.
        $shared = (string) ($in['product_code'] ?? '');
        $own = [];

        foreach ((array) ($in['items'] ?? []) as $item) {
            if (is_array($item) && is_string($item['product'] ?? null) && $item['product'] !== '') {
                $own[(int) ($item['id'] ?? 0)] = explode('|', $item['product'], 2)[0];
            }
        }

        foreach ($rows as &$r) {
            $r['_code'] = $own[$r['id']] ?? ($shared !== '' && $shared !== self::PER_VIDEO ? $shared : ($products[$r['id']]['code'] ?? null));
        }

        unset($r);
        $mix = $this->wantsMix($in, $auto);
        $left = $this->schedule($rows, $auto, $now, $fmt, $mix);

        return [
            'ok' => true,
            'error' => null,
            'rows' => array_map(fn (array $r): array => ['id' => $r['id'], 'at' => $r['at'], 'status' => $r['status'], 'messages' => $r['messages'], 'edited' => (bool) $r['edited'], 'product' => $products[$r['id']] ?? null], $rows),
            'left' => $left,
            'window' => app(RiengSchedule::class)->windowLabel($auto),
            'gap_minutes' => $gapMinutes,
            'daily_cap' => app(RiengSchedule::class)->cap($auto),
            'mix' => $mix,
            'mix_default' => ProductMix::enabledFor($auto),
        ];
    }

    /**
     * @param  array<string, mixed>  $in
     * @return array<string, mixed>
     */
    public function commit(array $in, bool $acceptWarnings, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $accountId = (string) ($in['social_account_id'] ?? '');
        $lock = Cache::lock('fork:auto-plan:'.$accountId, 300);

        try {
            $lock->block(15);
        } catch (LockTimeoutException) {
            return ['ok' => false, 'error' => 'Kênh đang được xếp lịch bởi lượt khác, hãy thử lại sau ít phút.', 'rows' => []];
        }

        try {
            $plan = $this->evaluate($in, $now);

            if (! $plan['ok']) {
                return $plan;
            }

            $hasWarn = collect($plan['rows'])->contains(fn (array $r): bool => $r['status'] === 'warn');

            if ($hasWarn && ! $acceptWarnings) {
                return $plan + ['committed' => false, 'needs_confirm' => true];
            }

            return $this->apply($plan, $in, $now);
        } finally {
            $lock->release();
        }
    }

    // ------------------------------------------------------------------ Kiểm tra + xếp giờ (không ghi gì)

    /**
     * @param  array<string, mixed>  $in
     * @return array<string, mixed>
     */
    private function evaluate(array $in, CarbonImmutable $now): array
    {
        $fail = fn (string $error): array => ['ok' => false, 'error' => $error, 'rows' => [], 'left' => 0, 'needs_confirm' => false];

        $auto = AutoAccount::query()->find((string) ($in['social_account_id'] ?? ''));

        if ($auto === null) {
            return $fail('Hãy chọn kênh TikTok.');
        }

        if (($why = $this->planner->ineligible($auto)) !== null) {
            return $fail('Kênh này chưa dùng được: '.$why.'.');
        }

        $social = SocialAccount::query()->with('workspace')->find($auto->social_account_id);

        if ($social === null) {
            return $fail('Không tìm thấy kênh.');
        }

        $code = (string) ($in['product_code'] ?? '');
        $qc = filled($in['quy_cach'] ?? null) ? (string) $in['quy_cach'] : null;
        $perVideo = $code === self::PER_VIDEO;
        $options = collect($this->productOptions((string) $auto->social_account_id))->keyBy(fn (array $o): string => $o['code'].'|'.($o['quy_cach'] ?? ''));
        $allowed = $this->cart->evaluate((string) $auto->social_account_id)['allowed'];

        if ($code === '') {
            return $fail('Hãy chọn sản phẩm gắn giỏ hàng (bắt buộc).');
        }

        if (! $perVideo && ! $options->has($code.'|'.($qc ?? ''))) {
            return $fail('Sản phẩm này chưa có giỏ hàng hợp lệ trên kênh đã chọn.');
        }

        $productsByCode = AutoProduct::query()->get()->keyBy('code');
        $coverInfo = [];
        // Không còn chia "tự động / thủ công": giờ luôn được tự đề xuất, giờ nào chủ app sửa (items.*.at) thì giữ và kiểm.
        $mode = self::MODE_AUTO;
        $sharedCaption = trim((string) ($in['caption'] ?? ''));
        $sharedTags = Hashtags::normalize($in['hashtags'] ?? []);
        $items = array_values(array_filter((array) ($in['items'] ?? []), 'is_array'));
        $coverMode = in_array($in['cover_mode'] ?? null, [self::COVER_UPLOAD, self::COVER_FRAME], true) ? (string) $in['cover_mode'] : self::COVER_PRODUCT;
        $batchToken = filled($in['cover_token'] ?? null) ? (string) $in['cover_token'] : null;

        if ($items === []) {
            return $fail('Chưa chọn video nào.');
        }

        // Nhạc: không gửi `music` = theo cài đặt từng thư mục (như tự đăng); kind none = không ghép; kind random = bốc từ thư mục nhạc đã chọn.
        $musicIn = is_array($in['music'] ?? null) ? $in['music'] : null;
        $musicCfg = null;
        $musicPlan = [];
        $musicI = 0;

        if (($musicIn['kind'] ?? null) === 'random') {
            $musicDir = trim((string) ($musicIn['dir'] ?? ''));
            $tracks = $musicDir !== '' ? app(RiengMusic::class)->list($musicDir) : [];

            if ($tracks === []) {
                return $fail($musicDir === '' ? 'Chưa chọn thư mục nhạc (hoặc chọn "Không ghép nhạc").' : 'Thư mục nhạc "'.$musicDir.'" không có bài nhạc nào (hoặc ổ đĩa đang tắt), hãy chọn thư mục khác hoặc "Không ghép nhạc".');
            }

            $musicCfg = [
                'dir' => $musicDir,
                'mode' => ($musicIn['mode'] ?? null) === RiengMusic::MODE_REPLACE ? RiengMusic::MODE_REPLACE : RiengMusic::MODE_MIX,
                'gain_db' => max(-40, min(0, (int) ($musicIn['gain_db'] ?? RiengMusic::DEFAULT_GAIN_DB))),
            ];
            $musicPlan = RiengMusic::plan(array_column($tracks, 'rel'), (int) ($musicIn['seed'] ?? 0));
        }

        $tz = $this->planner->timezoneFor($auto);
        $fmt = fn (int $ts): string => CarbonImmutable::createFromTimestampUTC($ts)->setTimezone($tz)->format('H:i d/m');

        $rows = [];
        $seen = [];
        $dups = (new RiengInfo)->duplicates(AutoVideo::query()->whereIn('id', array_filter(array_map(fn (array $i): int => (int) ($i['id'] ?? 0), $items)))->where('source', AutoVideo::SOURCE_RIENG)->get());

        foreach ($items as $item) {
            $id = (int) ($item['id'] ?? 0);
            $video = $id > 0 && ! isset($seen[$id]) ? AutoVideo::query()->whereKey($id)->where('source', AutoVideo::SOURCE_RIENG)->first() : null;
            $seen[$id] = true;
            // `duplicate`: chỉ để báo (video trùng nội dung vẫn đăng được nếu chủ app chọn).
            $row = ['id' => $id, 'file_name' => $video?->file_name, 'status' => 'ok', 'messages' => [], 'at' => null, 'caption' => null, 'hashtags' => [], 'duplicate' => $dups[$id]['text'] ?? null];

            if ($video === null) {
                $row['status'] = 'error';
                $row['messages'][] = 'Không tìm thấy video này.';
                $rows[] = $row;

                continue;
            }

            if ($video->status === AutoVideo::FAILED) {
                if (($refusal = $this->retry->refusal($video)) !== null) {
                    $row['status'] = 'error';
                    $row['messages'][] = $refusal;
                }
            } elseif ($video->status !== AutoVideo::NEW) {
                $row['status'] = 'error';
                $row['messages'][] = 'Video này đã được hẹn giờ hoặc đã đăng.';
            }

            if ($video->files_deleted_at !== null || ! is_file((string) $video->path)) {
                $row['status'] = 'error';
                $row['messages'][] = 'Không còn thấy file video trong thư mục.';
            }

            // Sản phẩm gắn giỏ của dòng: chọn riêng trong hộp > theo video (AI / chủ app) > sản phẩm chung của lượt.
            $pick = $this->rowProduct($item, $video, $perVideo, $code, $qc, $options, $allowed, $productsByCode, $row);
            $product = $pick === null ? null : ($productsByCode[$pick['code']] ?? null);
            $row['_code'] = $pick['code'] ?? null;
            $row['_qc'] = $pick['quy_cach'] ?? null;

            $ownTags = array_key_exists('hashtags', $item) && $item['hashtags'] !== null && $item['hashtags'] !== '' && $item['hashtags'] !== [];
            $caption = filled($item['caption'] ?? null) ? trim((string) $item['caption']) : $sharedCaption;
            $tags = $ownTags ? Hashtags::normalize($item['hashtags']) : $sharedTags;

            // Không viết caption chung / riêng: dùng caption của chính video (anh đã viết, hoặc AI viết) nếu có.
            if ($caption === '' && ($videoCaption = $this->videoCaption($video)) !== null) {
                $caption = $videoCaption['caption'];
                $row['caption_from'] = $videoCaption['from'];

                if (! $ownTags && $sharedTags === []) {
                    $tags = $videoCaption['hashtags'];
                }
            }

            $row['caption'] = $caption;
            $row['hashtags'] = $tags;

            // Caption và hashtag có thể trống: TikTok cho hẹn giờ bài không có chữ.
            $final = app(Hashtags::class)->apply($caption, $tags, $product);

            if (mb_strlen(HubText::compose($final['caption'], $final['hashtags'])) > HubText::MAX_CHARS) {
                $row['status'] = 'error';
                $row['messages'][] = 'Caption dài quá '.HubText::MAX_CHARS.' ký tự (giới hạn TikTok).';
            }

            $ownToken = filled($item['cover_token'] ?? null) ? (string) $item['cover_token'] : null;
            $ck = $pick['code'] ?? '';
            $coverInfo[$ck] ??= $this->productCoverInfo($product, (string) $social->id, count($items)) + ['i' => 0];
            // Bìa sản phẩm: mỗi dòng nhận ảnh kế tiếp của vòng xoay theo thứ tự danh sách (giống giao diện), lúc đăng dùng đúng ảnh đó.
            $planned = $coverMode === self::COVER_PRODUCT && $ownToken === null ? ($coverInfo[$ck]['plan'][$coverInfo[$ck]['i']++] ?? null) : null;
            $row['cover'] = $this->coverFor($coverMode, $ownToken, $batchToken, $video, ['planned' => $planned] + $coverInfo[$ck], $row);
            $row['music'] = $this->musicFor($musicIn, $musicCfg, $musicPlan, $musicI, $item, $row);
            $row['_at'] = $this->parseAt($item['at'] ?? null);
            $rows[] = $row;
        }

        $mix = $this->wantsMix($in, $auto);
        $left = $this->schedule($rows, $auto, $now, $fmt, $mix);

        return [
            'music_cfg' => $musicCfg,
            'mix' => $mix,
            'ok' => true,
            'error' => null,
            'mode' => $mode,
            'cover_mode' => $coverMode,
            'rows' => $rows,
            'left' => $left,
            'needs_confirm' => collect($rows)->contains(fn (array $r): bool => $r['status'] === 'warn'),
            'channel' => '@'.($social->username ?: $social->display_name),
        ];
    }

    /**
     * Bài nhạc của một dòng: bài chủ app chọn riêng cho video (items.*.music), không thì bài kế tiếp của thứ tự bốc cố định
     * (giống giao diện). null = không gửi cách chọn nhạc (theo cài đặt thư mục).
     *
     * @param  array<string, mixed>|null  $in
     * @param  array{dir: string, mode: string, gain_db: int}|null  $cfg
     * @param  list<string>  $plan
     * @param  array<string, mixed>  $item
     * @param  array<string, mixed>  $row
     * @return array{kind: string, rel: ?string, name: ?string}|null
     */
    private function musicFor(?array $in, ?array $cfg, array $plan, int &$i, array $item, array &$row): ?array
    {
        if ($in === null) {
            return null;
        }

        if ($cfg === null) {
            return ['kind' => 'none', 'rel' => null, 'name' => null];
        }

        // Mỗi dòng giữ chỗ của mình trong thứ tự bốc (kể cả khi chọn riêng), nên đổi bài một video không làm đổi bài video khác.
        $planned = $plan[$i++ % count($plan)];
        $rel = is_string($item['music'] ?? null) && $item['music'] !== '' ? $item['music'] : $planned;

        if (app(RiengMusic::class)->resolveIn($cfg['dir'], $rel) === null) {
            $row['status'] = 'error';
            $row['messages'][] = 'Bài nhạc đã chọn không còn trong thư mục nhạc, hãy chọn lại.';
        }

        return ['kind' => 'random', 'rel' => $rel, 'name' => pathinfo($rel, PATHINFO_FILENAME)];
    }

    /**
     * Lựa chọn nhạc đưa cho PostBuilder: null = theo thư mục; false = không ghép; mảng = đúng bài đã hiện cho video.
     *
     * @param  array<string, mixed>  $row
     * @param  array{dir: string, mode: string, gain_db: int}|null  $cfg
     * @return array{dir: string, mode: string, gain_db: int, rel: string}|false|null
     */
    private function musicChoice(array $row, ?array $cfg): array|false|null
    {
        return match ($row['music']['kind'] ?? null) {
            'none' => false,
            'random' => $cfg + ['rel' => (string) $row['music']['rel']],
            default => null,
        };
    }

    /**
     * Bìa sản phẩm sẽ dùng khi chọn "Ảnh bìa của sản phẩm": có ảnh dùng được thì xoay vòng, không thì bìa mặc định của TikTok.
     *
     * @return array{active: bool, count: int, url: ?string}
     */
    private function productCoverInfo(?AutoProduct $product, string $accountId, int $n = 0): array
    {
        // Bộ ảnh bìa của sản phẩm trên đúng kênh đang đăng (kênh khác cùng sản phẩm có bộ riêng).
        $product = $product === null || $accountId === '' ? null : ProductCover::for($accountId, (string) $product->code);

        if ($product === null || CoverStore::normalizeMode($product->cover_mode) === CoverStore::DEFAULT) {
            return ['active' => false, 'count' => 0, 'url' => null, 'plan' => []];
        }

        $files = collect(app(CoverStore::class)->describe($product))->filter(fn (array $c): bool => CoverStore::pathFor($product, $c['file']) !== null)->values();
        $url = fn (string $f): string => '/auto/anh-bia/'.rawurlencode((string) $product->code).'/'.$f;
        // Ảnh của $n bài kế tiếp (đúng thứ tự xoay vòng), để hộp đăng hàng loạt hiện trước đúng ảnh từng video sẽ dùng.
        $plan = array_map(fn (string $f): array => ['file' => $f, 'url' => $url($f)], app(CoverStore::class)->plan($product, $n));

        return ['active' => $files->isNotEmpty(), 'count' => $files->count(), 'url' => $files->first()['url'] ?? null, 'plan' => $plan];
    }

    /**
     * Ảnh bìa của một dòng (để hiện ở bước xem trước). Lỗi ảnh bìa làm dòng không hẹn được (status error).
     *
     * @param  array{active: bool, count: int, url: ?string}  $productCover
     * @param  array<string, mixed>  $row
     * @return array{kind: string, url: ?string, note: string, token: ?string}
     */
    private function coverFor(string $mode, ?string $ownToken, ?string $batchToken, AutoVideo $video, array $productCover, array &$row): array
    {
        $covers = app(RiengCovers::class);
        $tmpUrl = fn (string $t): string => '/auto/kho/rieng/anh-bia/tam/'.$t;

        // Ảnh riêng của video (tải lên / khung đã chọn / ảnh đã nhớ từ lần trước) luôn thắng, ở mọi cách chọn bìa.
        if ($ownToken !== null) {
            if ($covers->tmpPath($ownToken) === null) {
                $row['status'] = 'error';
                $row['messages'][] = 'Ảnh bìa đã chọn không còn nữa, hãy chọn lại.';

                return ['kind' => 'own', 'url' => null, 'token' => null, 'note' => 'Lỗi ảnh bìa'];
            }

            return ['kind' => 'own', 'url' => $tmpUrl($ownToken), 'token' => $ownToken, 'note' => 'Ảnh riêng của video này'];
        }

        $token = $mode === self::COVER_PRODUCT ? null : $batchToken;

        if ($mode === self::COVER_PRODUCT) {
            $planned = $productCover['planned'] ?? null;

            return [
                'kind' => 'product',
                'url' => $planned['url'] ?? null,
                'token' => null,
                'file' => $planned['file'] ?? null,
                'note' => $planned !== null ? 'Bìa của sản phẩm' : 'Sản phẩm chưa có ảnh bìa, dùng bìa mặc định của TikTok',
            ];
        }

        if ($token !== null && $covers->tmpPath($token) === null) {
            $row['status'] = 'error';
            $row['messages'][] = 'Ảnh bìa đã chọn không còn nữa, hãy chọn lại.';

            return ['kind' => $mode, 'url' => null, 'token' => null, 'note' => 'Lỗi ảnh bìa'];
        }

        if ($token !== null) {
            return ['kind' => $mode, 'url' => $tmpUrl($token), 'token' => $token, 'note' => $mode === self::COVER_UPLOAD ? 'Ảnh tải lên' : 'Khung đã chọn'];
        }

        if ($mode === self::COVER_UPLOAD) {
            $row['status'] = 'error';
            $row['messages'][] = 'Chưa có ảnh bìa: hãy tải một ảnh lên.';

            return ['kind' => $mode, 'url' => null, 'token' => null, 'note' => 'Chưa có ảnh'];
        }

        // Khung mặc định = thời điểm của ảnh nhỏ hiện trong lưới.
        if (! $covers->canExtract()) {
            $row['status'] = 'error';
            $row['messages'][] = 'Máy chưa có ffmpeg nên không lấy được khung hình làm ảnh bìa.';

            return ['kind' => $mode, 'url' => null, 'token' => null, 'note' => 'Không có ffmpeg'];
        }

        return ['kind' => $mode, 'url' => '/auto/kho/rieng/video/'.$video->id.'/thumb', 'token' => null, 'note' => 'Khung mặc định của video'];
    }

    /**
     * Sản phẩm riêng của video: chủ app đã chọn (kid), AI nhận ra chắc chắn (ai), hoặc AI chỉ đoán chưa chắc (guess, chưa gắn).
     *
     * @return array{code: ?string, by: ?string, guess: ?string}
     */
    public static function ownProduct(AutoVideo $v): array
    {
        $code = filled($v->product_code) ? (string) $v->product_code : null;
        $guess = data_get($v->meta, 'ai.product_code');

        return [
            'code' => $code,
            'by' => $code === null ? null : (data_get($v->meta, 'product_by') === 'kid' ? 'kid' : 'ai'),
            'guess' => $code === null && is_string($guess) && $guess !== '' ? $guess : null,
        ];
    }

    /**
     * Sản phẩm của từng video trên một kênh, cho hộp đăng hàng loạt (để chọn sẵn "theo từng video" và hiện tên).
     *
     * @param  list<int>  $ids
     * @return array<int, array{code: ?string, quy_cach: ?string, label: ?string, by: ?string, guess: ?string, guess_label: ?string, cart: bool}>
     */
    public function videoProducts(array $ids, string $socialAccountId): array
    {
        if ($ids === []) {
            return [];
        }

        $allowed = $this->cart->evaluate($socialAccountId)['allowed'];
        $products = AutoProduct::query()->get()->keyBy('code');
        $poster = app(Ai\RiengAutoPoster::class);
        $out = [];

        foreach (AutoVideo::query()->whereIn('id', $ids)->where('source', AutoVideo::SOURCE_RIENG)->get() as $v) {
            $own = self::ownProduct($v);
            $qc = $own['code'] !== null ? $poster->quyCachFor($v, $allowed) : false;
            $out[(int) $v->id] = [
                'code' => $own['code'],
                'quy_cach' => $qc === false ? null : $qc,
                'label' => $own['code'] !== null ? CartRules::label($products[$own['code']] ?? null, $own['code'], $qc === false ? null : $qc) : null,
                'by' => $own['by'],
                'guess' => $own['guess'],
                'guess_label' => $own['guess'] !== null ? CartRules::label($products[$own['guess']] ?? null, $own['guess'], null) : null,
                'cart' => $own['code'] !== null && $qc !== false,
            ];
        }

        return $out;
    }

    /**
     * Chọn sản phẩm gắn giỏ cho một dòng và ghi lỗi / cảnh báo vào dòng. null = không gắn được (dòng thành lỗi).
     *
     * Chủ app chọn một sản phẩm chung mà video đã có sản phẩm khác (AI nhận ra hoặc chính anh chọn) thì dòng thành
     * "cần xem lại" (warn): phải thấy và bấm "Vẫn hẹn" mới gắn — tránh gắn nhầm giỏ hàng loạt.
     *
     * @param  array<string, mixed>  $item
     * @param  Collection<string, array<string, mixed>>  $options  khoá "mã|quy cách"
     * @param  array<string, list<string|null>>  $allowed
     * @param  Collection<string, AutoProduct>  $products
     * @param  array<string, mixed>  $row
     * @return array{code: string, quy_cach: ?string}|null
     */
    private function rowProduct(array $item, AutoVideo $video, bool $perVideo, string $code, ?string $qc, $options, array $allowed, $products, array &$row): ?array
    {
        $name = fn (?string $c): string => (string) ($c === null ? '?' : ($products[$c]?->short_name ?: $c));
        $own = self::ownProduct($video);
        $fail = function (string $message) use (&$row): null {
            $row['status'] = 'error';
            $row['messages'][] = $message;
            $row['product'] = null;

            return null;
        };
        $use = function (string $c, ?string $q, string $from) use (&$row, $options, $products): array {
            $row['product'] = ['code' => $c, 'quy_cach' => $q, 'label' => $options[$c.'|'.($q ?? '')]['label'] ?? CartRules::label($products[$c] ?? null, $c, $q), 'from' => $from];

            return ['code' => $c, 'quy_cach' => $q];
        };

        // 1) Chủ app chọn riêng cho video này ngay trong hộp ("mã|quy cách").
        if (is_string($item['product'] ?? null) && $item['product'] !== '') {
            if (! $options->has($item['product'])) {
                return $fail('Sản phẩm chọn cho video này chưa có giỏ hàng hợp lệ trên kênh.');
            }

            [$c, $q] = explode('|', $item['product'], 2);

            return $use($c, $q === '' ? null : $q, 'chosen');
        }

        // 2) Theo sản phẩm của từng video.
        if ($perVideo) {
            if ($own['code'] === null) {
                return $fail($own['guess'] !== null
                    ? 'AI đoán là '.$name($own['guess']).' nhưng chưa chắc: hãy chọn sản phẩm cho video này.'
                    : 'Video chưa có sản phẩm: hãy chọn sản phẩm cho video này.');
            }

            $q = app(Ai\RiengAutoPoster::class)->quyCachFor($video, $allowed);

            if ($q === false) {
                return $fail(isset($allowed[$own['code']])
                    ? 'Hãy chọn quy cách của '.$name($own['code']).' cho video này.'
                    : $name($own['code']).' chưa được chọn giỏ hàng trên kênh này (vào Giỏ hàng để chọn), hoặc chọn sản phẩm khác cho video.');
            }

            return $use($own['code'], $q, 'video');
        }

        // 3) Sản phẩm chung của lượt: khác với sản phẩm của video thì phải xem lại.
        if ($own['code'] !== null && $own['code'] !== $code) {
            $row['status'] = $row['status'] === 'error' ? 'error' : 'warn';
            $row['messages'][] = ($own['by'] === 'kid' ? 'Anh đã chọn video này là ' : 'AI nhận ra video này là ').$name($own['code'])
                .', nhưng lượt này sẽ gắn giỏ '.$name($code).'. Kiểm tra kỹ, hoặc chọn "Theo sản phẩm của từng video".';
            $row['product_mismatch'] = true;
        } elseif ($own['guess'] !== null && $own['guess'] !== $code) {
            $row['status'] = $row['status'] === 'error' ? 'error' : 'warn';
            $row['messages'][] = 'AI đoán video này là '.$name($own['guess']).' (chưa chắc), lượt này sẽ gắn giỏ '.$name($code).'. Kiểm tra kỹ trước khi hẹn.';
            $row['product_mismatch'] = true;
        }

        return $use($code, $qc, 'shared');
    }

    /**
     * Caption sẵn có của video: anh đã tự viết, hoặc AI đã viết. null = chưa có.
     *
     * @return array{caption: string, hashtags: list<string>, from: string}|null
     */
    private function videoCaption(AutoVideo $video): ?array
    {
        $poster = app(Ai\RiengAutoPoster::class);

        if ($video->caption_source === 'kid' && filled($video->caption)) {
            $c = trim((string) $video->caption);

            return ['caption' => $c, 'hashtags' => $poster->hashtagsFor($video, $c), 'from' => 'kid'];
        }

        $ai = (array) data_get($video->meta, 'ai', []);

        if (in_array($ai['state'] ?? null, ['ok', 'unsure'], true) && filled($ai['caption'] ?? null)) {
            $c = trim((string) $ai['caption']);

            return ['caption' => $c, 'hashtags' => $poster->hashtagsFor($video, $c), 'from' => 'ai'];
        }

        return null;
    }

    private function parseAt(mixed $raw): ?CarbonImmutable
    {
        if (! is_string($raw) || trim($raw) === '') {
            return null;
        }

        try {
            return CarbonImmutable::parse($raw)->utc();
        } catch (Throwable) {
            return null;
        }
    }

    /**
     * Đặt giờ cho các dòng (gán `at` + bỏ `_at`). Giờ chủ app đã sửa (`_at`) được giữ và kiểm; dòng chưa có giờ được tự đề xuất
     * giờ trống sớm nhất (RiengSchedule). Lỗi cứng (status `error`): gần hơn 5 phút, quá xa theo TikTok, ngoài khung giờ đăng,
     * trùng giờ y hệt trên cùng kênh, vượt hạn mức bài chờ. Cảnh báo (status `warn`, cho phép "Vẫn hẹn"): cách bài cùng kênh
     * chưa đủ giãn cách, hoặc ngày đó kênh đã đủ số bài/ngày. Giờ tự đề xuất không bao giờ vượt số bài/ngày (đủ thì sang ngày sau). Kênh khác không tính. Trả số video không còn giờ (status `skip`).
     *
     * @param  list<array<string, mixed>>  $rows
     */
    private function schedule(array &$rows, AutoAccount $auto, CarbonImmutable $now, Closure $fmt, bool $mix = false): int
    {
        $sched = app(RiengSchedule::class);
        $tz = $this->planner->timezoneFor($auto);
        $gap = $this->planner->gapSeconds();
        $gapMin = intdiv($gap, 60);
        $minTs = $now->getTimestamp() + RiengSchedule::MIN_LEAD;
        $maxTs = $sched->latest($now);
        $room = $this->planner->futureRoom($auto, $now);
        $busy = $sched->busy($auto, $now->getTimestamp() - $gap, $maxTs + $gap);
        // Đếm bài từng ngày (giờ địa phương) để không vượt số bài/ngày của kênh; bài trong lượt này cộng dồn vào.
        $counts = $sched->dayCounts($auto, $now->getTimestamp() - 2 * 86400, $maxTs + 2 * 86400);
        $cap = $sched->cap($auto);
        $window = $sched->windowLabel($auto);
        $iso = fn (int $ts): string => CarbonImmutable::createFromTimestampUTC($ts)->setTimezone($tz)->toIso8601String();
        $batch = [];
        $used = 0;
        $left = 0;

        // 1) Giờ chủ app tự sửa.
        foreach ($rows as &$r) {
            $r['edited'] = false;

            /** @var CarbonImmutable|null $at */
            $at = $r['_at'] ?? null;

            if ($at === null) {
                continue;
            }

            $r['edited'] = true;

            if ($r['status'] === 'error') {
                continue;
            }

            $ts = $at->getTimestamp();
            $r['at'] = $iso($ts);

            if ($ts < $minTs) {
                $r['status'] = 'error';
                $r['messages'][] = 'Giờ đăng phải cách bây giờ ít nhất '.intdiv(RiengSchedule::MIN_LEAD, 60).' phút.';

                continue;
            }

            if ($ts > $maxTs) {
                $r['status'] = 'error';
                $r['messages'][] = 'TikTok chỉ cho hẹn giờ tối đa khoảng 9 ngày tới.';

                continue;
            }

            if (! $sched->inWindow($auto, $ts)) {
                $r['status'] = 'error';
                $r['messages'][] = 'Ngoài khung giờ đăng của kênh ('.$window.'). Hãy chọn giờ trong khung, hoặc đổi khung giờ ở Cài đặt kênh.';

                continue;
            }

            if ($used >= $room) {
                $r['status'] = 'error';
                $r['messages'][] = 'Kênh đã đủ số bài chờ đăng, không hẹn thêm được.';

                continue;
            }

            $exact = null;

            foreach ([...$busy, ...$batch] as $b) {
                if (abs($b - $ts) < self::EXACT_SECONDS) {
                    $exact = $b;
                    break;
                }
            }

            if ($exact !== null) {
                $r['status'] = 'error';
                $r['messages'][] = 'Đã có bài đúng giờ '.$fmt($exact).' trên kênh này, hãy chọn giờ khác.';

                continue;
            }

            foreach ($busy as $b) {
                if (abs($b - $ts) < $gap) {
                    $r['status'] = 'warn';
                    $r['messages'][] = 'Gần bài '.$fmt($b).' của kênh này (nên cách nhau ít nhất '.$gapMin.' phút).';
                }
            }

            foreach ($batch as $b) {
                if (abs($b - $ts) < $gap) {
                    $r['status'] = 'warn';
                    $r['messages'][] = 'Gần giờ '.$fmt($b).' của một video khác trong lượt này (nên cách nhau ít nhất '.$gapMin.' phút).';
                }
            }

            $day = $sched->dayKey($auto, $ts);

            if ($cap > 0 && ($counts[$day] ?? 0) >= $cap) {
                $r['status'] = 'warn';
                $r['messages'][] = 'Ngày '.CarbonImmutable::createFromTimestampUTC($ts)->setTimezone($tz)->format('d/m').' kênh đã đủ '.$cap.' bài (số bài mỗi ngày trong Cài đặt kênh).';
            }

            $counts[$day] = ($counts[$day] ?? 0) + 1;
            $batch[] = $ts;
            $used++;
        }

        unset($r);

        // 2) Tự đề xuất giờ trống sớm nhất cho các dòng còn lại: theo thứ tự chọn, hoặc xen kẽ sản phẩm khi bật "Trộn xen kẽ".
        $auto2 = array_keys(array_filter($rows, fn (array $r): bool => $r['status'] !== 'error' && ! $r['edited']));

        if ($mix && count($auto2) > 1) {
            $items = [];

            foreach ($auto2 as $i) {
                $items[$i] = (string) ($rows[$i]['_code'] ?? '');
            }

            $auto2 = ProductMix::order($items, $this->recentProducts($auto, $minTs), crc32($auto->social_account_id.'|'.implode(',', array_map(fn (int $i): int => (int) $rows[$i]['id'], $auto2))));
        }

        // Giờ tự đề xuất của từng ngày (để chia đều trong khung giờ sau khi biết mỗi ngày có mấy bài); giờ đã có sẵn trước đó.
        $placed = [];
        $fixedCount = count($batch);

        foreach ($auto2 as $i) {
            $r = &$rows[$i];

            $ts = $used < $room ? $sched->next($auto, $minTs, $maxTs, [...$busy, ...$batch], $gap, $counts) : null;

            if ($ts === null) {
                $r['status'] = 'skip';
                $r['messages'][] = $used >= $room
                    ? 'Kênh đã đủ số bài chờ đăng.'
                    : 'Không còn giờ trống trong khung giờ đăng ('.$window.') và số bài mỗi ngày của kênh tới ngày xa nhất TikTok cho hẹn, video này để lại.';
                $left++;

                continue;
            }

            $r['at'] = $iso($ts);
            $day = $sched->dayKey($auto, $ts);
            $counts[$day] = ($counts[$day] ?? 0) + 1;
            $batch[] = $ts;
            $placed[$day][$i] = $ts;
            $used++;
        }

        unset($r);
        $this->spreadDays($placed, $rows, $auto, $sched, [...$busy, ...array_slice($batch, 0, $fixedCount)], $gap, $iso);

        foreach ($rows as &$r) {
            unset($r['_at']);
        }

        unset($r);

        return $left;
    }

    /**
     * Chia đều các giờ tự đề xuất của mỗi ngày từ giờ sớm nhất tới cuối khung giờ đăng (vd 9 bài, khung 6h–20h: 6:00, 7:45 … 20:00)
     * thay vì dồn sát nhau đầu khung. Giờ chia đều nào vướng bài sẵn có (gần hơn giãn cách) thì cả ngày đó giữ giờ cũ.
     *
     * @param  array<string, array<int, int>>  $placed  ngày => [chỉ số dòng => giờ]
     * @param  list<array<string, mixed>>  $rows
     * @param  list<int>  $fixed  giờ bài sẵn có + giờ chủ app tự sửa
     */
    private function spreadDays(array $placed, array &$rows, AutoAccount $auto, RiengSchedule $sched, array $fixed, int $gap, Closure $iso): void
    {
        foreach ($placed as $day) {
            $k = count($day);

            if ($k < 2) {
                continue;
            }

            asort($day);
            $lo = (int) reset($day);
            [, $hi] = $sched->dayWindow($auto, $lo);
            $times = [];

            for ($j = 0; $j < $k; $j++) {
                $t = $lo + intdiv(($hi - $lo) * $j, $k - 1);
                $t -= $t % 60;

                foreach ($fixed as $b) {
                    if (abs($b - $t) < $gap) {
                        continue 3;
                    }
                }

                $times[] = $t;
            }

            if ($gap > $times[1] - $times[0]) {
                continue;
            }

            foreach (array_keys($day) as $n => $i) {
                $rows[$i]['at'] = $iso($times[$n]);
            }
        }
    }

    /** Lượt này có trộn xen kẽ sản phẩm không: chủ app chọn trong hộp (mix), mặc định theo cài đặt kênh. */
    private function wantsMix(array $in, AutoAccount $auto): bool
    {
        return array_key_exists('mix', $in) && $in['mix'] !== null
            ? filter_var($in['mix'], FILTER_VALIDATE_BOOLEAN)
            : ProductMix::enabledFor($auto);
    }

    /**
     * Sản phẩm 2 bài gần nhất của kênh trước mốc $beforeTs (cũ → mới), để bài đầu của lượt không trùng bài vừa xếp.
     *
     * @return list<string>
     */
    private function recentProducts(AutoAccount $auto, int $beforeTs): array
    {
        return AutoVideo::query()->where('social_account_id', $auto->social_account_id)
            ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED, AutoVideo::POSTED])
            ->whereNotNull('scheduled_for')->where('scheduled_for', '<', CarbonImmutable::createFromTimestampUTC($beforeTs))
            ->orderByDesc('scheduled_for')->limit(2)->pluck('product_code')
            ->reverse()->map(fn (?string $c): string => (string) $c)->values()->all();
    }

    // ------------------------------------------------------------------ Ghi

    /**
     * @param  array<string, mixed>  $plan
     * @param  array<string, mixed>  $in
     * @return array<string, mixed>
     */
    private function apply(array $plan, array $in, CarbonImmutable $now): array
    {
        $social = SocialAccount::query()->with('workspace')->findOrFail((string) $in['social_account_id']);
        $done = 0;
        $failed = 0;
        $rows = [];

        foreach ($plan['rows'] as $row) {
            if (! in_array($row['status'], ['ok', 'warn'], true) || $row['at'] === null || ! filled($row['_code'] ?? null)) {
                $rows[] = $row + ['result' => $row['status'] === 'skip' ? 'skip' : 'error'];

                continue;
            }

            $error = $this->postOne($social, (int) $row['id'], (string) $row['_code'], $row['_qc'] ?? null, (string) $row['caption'], (array) $row['hashtags'], CarbonImmutable::parse($row['at'])->utc(), (string) $plan['cover_mode'], $row['cover']['token'] ?? null, $row['cover']['file'] ?? null, $this->musicChoice($row, $plan['music_cfg'] ?? null));

            if ($error === null) {
                $done++;
                $rows[] = $row + ['result' => 'done'];

                // Giờ chủ app tự sửa trong hộp: trộn xen kẽ về sau không đổi bài này.
                if ($row['edited'] ?? false) {
                    $posted = AutoVideo::query()->find((int) $row['id']);

                    if ($posted !== null) {
                        ProductMix::pin($posted);
                    }
                }
            } else {
                $failed++;
                $rows[] = $row + ['result' => 'error', 'error' => $error];
            }
        }

        // Nhớ cách chọn bìa cho kênh + sản phẩm (và kênh), cùng ảnh riêng của từng video, để lần sau tự dùng lại.
        if ($done > 0) {
            try {
                $memory = app(RiengCoverMemory::class);
                $pairs = collect($rows)->where('result', 'done')->map(fn (array $r): array => [(string) $r['_code'], $r['_qc'] ?? null])->unique(fn (array $p): string => $p[0].'|'.($p[1] ?? ''));

                foreach ($pairs as [$doneCode, $doneQc]) {
                    $memory->rememberChoice((string) $social->id, $doneCode, $doneQc, (string) $plan['cover_mode'], filled($in['cover_token'] ?? null) ? (string) $in['cover_token'] : null);
                }

                foreach ($rows as $r) {
                    if (($r['result'] ?? null) === 'done' && ($r['cover']['kind'] ?? null) === 'own' && filled($r['cover']['token'] ?? null)) {
                        $memory->rememberVideo((int) $r['id'], (string) $r['cover']['token']);
                    }
                }
            } catch (Throwable $e) {
                report($e);
            }
        }

        // Kênh bật tự trộn: xếp lại xen kẽ cả các bài cũ chưa gửi lên TikTok (đang trong khoá xếp lịch của kênh).
        // Anh bỏ chọn "Trộn xen kẽ" trong hộp thì lượt này không trộn gì.
        $autoAccount = AutoAccount::query()->find((string) $social->id);
        $mixed = $done > 0 && $autoAccount !== null && $this->wantsMix($in, $autoAccount) ? app(ProductMix::class)->autoMix($autoAccount) : 0;

        return ['ok' => true, 'error' => null, 'committed' => true, 'needs_confirm' => false, 'mode' => $plan['mode'], 'channel' => $plan['channel'], 'rows' => $rows, 'left' => $plan['left'], 'done' => $done, 'failed' => $failed, 'mixed' => $mixed];
    }

    /**
     * Giữ chỗ một video riêng rồi tạo bài hẹn giờ (dùng cho Đăng hàng loạt và Kho riêng tự đăng theo khung).
     *
     * @return string|null lỗi (tiếng Việt) hoặc null khi đã hẹn xong
     */
    public function postOne(SocialAccount $social, int $id, string $code, ?string $qc, string $caption, array $tags, CarbonImmutable $slot, string $coverMode = self::COVER_PRODUCT, ?string $coverToken = null, ?string $productCover = null, array|false|null $music = null): ?string
    {
        $video = AutoVideo::query()->whereKey($id)->where('source', AutoVideo::SOURCE_RIENG)->first();

        if ($video === null) {
            return 'Không tìm thấy video.';
        }

        if ($video->status === AutoVideo::FAILED) {
            if (($refusal = $this->retry->retry($video)) !== null) {
                return $refusal;
            }

            $video->refresh();
        }

        $previous = $video->only(['product_code', 'quy_cach', 'caption', 'hashtags', 'caption_source', 'meta']);
        unset($previous['meta']['cover']);

        // Giữ chỗ như reserveNext (nhưng không qua hub): chỉ video `new` còn file mới giữ được.
        $won = AutoVideo::query()->whereKey($video->id)->where('status', AutoVideo::NEW)->whereNull('files_deleted_at')->update([
            'status' => AutoVideo::RESERVED,
            'social_account_id' => $social->id,
            'updated_at' => now(),
        ]);

        if ($won !== 1) {
            return 'Video vừa đổi trạng thái, hãy tải lại trang.';
        }

        $video->refresh();
        $video->forceFill(['product_code' => $code, 'quy_cach' => $qc, 'caption' => $caption, 'hashtags' => $tags, 'caption_source' => 'rieng'])->save();

        // Ảnh bìa riêng của video (mỗi video giữ bản của mình); chế độ "sản phẩm" thì PostBuilder tự xoay vòng bìa sản phẩm.
        $meta = (array) $video->meta;
        unset($meta['cover']);
        $ownCover = null;

        try {
            $covers = app(RiengCovers::class);

            if ($coverMode === self::COVER_PRODUCT && ($coverToken === null || $coverToken === '')) {
                $covers->forget((int) $video->id);
            } else {
                $c = $covers->attach($video, $coverToken);
                $ownCover = $c['file'];
                $meta['cover'] = ['file' => $c['file'], 'kind' => $coverToken !== null && $coverToken !== '' && $coverMode === self::COVER_PRODUCT ? 'own' : $coverMode, 'w' => $c['w'], 'h' => $c['h']];
            }

            $video->forceFill(['meta' => $meta])->save();
        } catch (InvalidArgumentException $e) {
            $this->restore($video, $previous, []);

            return 'Ảnh bìa lỗi: '.$e->getMessage();
        }

        try {
            $this->builder->build($social, $video, ['caption' => $caption, 'hashtags' => $tags, 'source' => 'rieng', 'product_name' => null], $slot, $ownCover, $productCover, $music);
            // Đã hẹn giờ thì không còn nằm trong "Giỏ chờ đăng".
            RiengQueueItem::forget((int) $video->id);

            return null;
        } catch (MissingVideoFile $e) {
            $this->restore($video, $previous, ['files_deleted_at' => now(), 'skip_reason' => RiengScanner::REASON_GONE]);

            return $e->getMessage();
        } catch (Throwable $e) {
            Log::error('Kho riêng: tạo bài lỗi, trả video về kho.', ['video_id' => $video->id, 'error' => $e->getMessage()]);
            $this->restore($video, $previous, []);

            return 'Tạo bài lỗi: '.mb_substr($e->getMessage(), 0, 200);
        }
    }

    /**
     * Nhả video (reserved -> new) và trả lại chữ/sản phẩm như trước khi chọn.
     *
     * @param  array<string, mixed>  $previous
     * @param  array<string, mixed>  $extra
     */
    private function restore(AutoVideo $video, array $previous, array $extra): void
    {
        try {
            app(RiengCovers::class)->forget((int) $video->id);
            $this->library->release($video, 'Đăng hàng loạt lỗi');
            $video->refresh();
            $video->forceFill($previous + $extra)->save();
        } catch (Throwable $e) {
            report($e);
        }
    }
}

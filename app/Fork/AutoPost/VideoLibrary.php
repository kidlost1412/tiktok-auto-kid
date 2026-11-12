<?php

declare(strict_types=1);

namespace App\Fork\AutoPost;

use App\Fork\AutoPost\Hub\HubApi;
use App\Fork\AutoPost\Hub\HubReporter;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Notify\Telegram;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Carbon\CarbonInterface;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;

/**
 * Kho video của tự động đăng: nhặt từ hub, giữ chỗ cho tài khoản, đánh dấu đã đăng.
 * Hub chỉ được đọc, ngoại trừ việc chuyển video đã đăng sang ra/_da-dang/.
 */
final class VideoLibrary
{
    /** Phần tử đặc biệt trong danh sách quy cách: khớp mọi quy cách (từ dạng cũ list<string>). */
    private const ANY = '*';

    public const LAST_INGEST_CACHE_KEY = 'fork-auto:last-ingest';

    public const REASON_UNAPPROVED = 'hub bỏ duyệt';

    public const REASON_HELD = 'máy khác đã giữ';

    public const REASON_POSTED = 'hub báo đã đăng';

    /** Số video tối đa thử giữ chỗ cho một giờ đăng (video bị máy khác giữ bị bỏ qua, thử video kế). */
    private const int MAX_CLAIM_TRIES = 30;

    /** Lý do reserveClaimed() trả null vì không giữ chỗ được trên hub (hub tắt/từ chối); null = chỉ là hết video. */
    public ?string $claimBlock = null;

    /** Báo cáo lượt ingest gần nhất của kho-dang (ingest() giữ nguyên 3 khoá new/skipped/known). */
    public array $khoReport = ['error' => 0, 'waiting' => 0];

    /** Lượt đọc lại chữ của hub: updated = video new được ghi/sửa caption, waiting = còn thiếu caption. */
    public array $hubReport = ['updated' => 0, 'waiting' => 0];

    /** Báo cáo lượt ingest qua API hub: state = ok|offline|off. */
    public array $apiReport = ['state' => 'off', 'error' => 0, 'missing' => 0, 'unapproved' => 0, 'held' => 0];

    public function __construct(private readonly KhoStore $kho = new KhoStore) {}

    public function kho(): KhoStore
    {
        return $this->kho;
    }

    /** Cột của AutoVideo lấy thẳng từ cột cùng tên trong bang-ghi.csv. */
    private const CSV_COLUMNS = ['goc', 'giong', 'nhac', 'font', 'phu_de', 'chuyen_canh', 'chuyen_dong', 'mau'];

    /** @var array<string, string>|null chuẩn hoá(tiền tố) => code */
    private ?array $prefixMap = null;

    public function hubPath(): string
    {
        return Paths::root((string) config('fork.auto.hub_path'));
    }

    /** Đọc san-pham/<ma>/san-pham.json, upsert AutoProduct. Giữ nguyên enabled và sản phẩm TikTok Shop đã gắn. */
    public function syncProducts(): int
    {
        $count = 0;
        $seen = [];

        foreach ($this->subDirectories($this->hubPath().'/san-pham') as $dir) {
            $file = $dir.'/san-pham.json';
            $facts = is_file($file) ? json_decode((string) file_get_contents($file), true) : null;

            if (! is_array($facts)) {
                continue;
            }

            $code = (string) ($facts['ma'] ?? basename($dir));
            $short = (string) ($facts['ten_ngan'] ?? $facts['ten_goi'] ?? $code);

            $product = AutoProduct::query()->find($code) ?? new AutoProduct(['code' => $code]);
            $product->fill([
                'name' => (string) ($facts['ten_goi'] ?? $short),
                'short_name' => $short,
                'facts' => $facts,
                'quy_cach' => $this->parseQuyCach($facts['quy_cach'] ?? null),
            ]);
            if ($code === 'video-vuon') {
                // Kho cảnh của hub, không bao giờ ra video bán.
                $product->enabled = false;
            }

            $product->save();
            $seen[] = $code;
            $count++;
        }

        // Mã hub đã bỏ (thư mục biến mất) → tắt, để trang Giỏ hàng không còn hiện và không đăng nhầm.
        if ($seen !== []) {
            AutoProduct::query()->whereNotIn('code', $seen)->where('enabled', true)->update(['enabled' => false]);
        }

        $this->prefixMap = null;

        return $count;
    }

    /** @return array{new: int, skipped: int, known: int} */
    public function ingest(): array
    {
        if (HubApi::enabled()) {
            $result = $this->ingestApi();
            Cache::forever(self::LAST_INGEST_CACHE_KEY, now()->toIso8601String());

            return $result;
        }

        $kho = $this->kho->ingest();
        $this->khoReport = ['error' => $kho['error'], 'waiting' => $kho['waiting']];
        $result = ['new' => $kho['new'], 'skipped' => $kho['skipped'], 'known' => $kho['known']];

        if (config('fork.auto.legacy_ra', true)) {
            foreach ($this->ingestLegacy() as $key => $n) {
                $result[$key] += $n;
            }
        }

        $this->resolveMissingProducts();
        $this->refreshHubText();
        Cache::forever(self::LAST_INGEST_CACHE_KEY, now()->toIso8601String());

        return $result;
    }

    /**
     * Chế độ API: lấy video chủ đã duyệt (status=ung) từ hub. Hub tắt thì giữ nguyên dữ liệu, lượt sau thử lại.
     * Không đọc ra/ hay kho-dang, không chuyển hay xoá file của hub.
     *
     * @return array{new: int, skipped: int, known: int}
     */
    private function ingestApi(): array
    {
        $result = ['new' => 0, 'skipped' => 0, 'known' => 0];
        $this->apiReport = ['state' => HubApi::OFFLINE, 'error' => 0, 'missing' => 0, 'unapproved' => 0, 'held' => 0];
        $this->khoReport = ['error' => 0, 'waiting' => 0];

        $videos = (new HubApi)->videos('ung');

        if ($videos === null) {
            return $result;
        }

        $this->apiReport['state'] = HubApi::OK;
        $seen = [];

        foreach ($videos as $item) {
            $id = $item['id'] ?? null;

            if (! is_string($id) || $id === '') {
                $this->apiReport['error']++;

                continue;
            }

            $seen[$id] = true;

            try {
                $outcome = $this->upsertHubVideo($id, $item);
            } catch (UniqueConstraintViolationException) {
                $outcome = 'known';
            }

            match ($outcome) {
                'new' => $result['new']++,
                'known' => $result['known']++,
                default => $this->apiReport['error']++,
            };
        }

        // Chủ bỏ duyệt khi video còn `new` thì bỏ qua; video đã giữ chỗ/xếp lịch/đăng thì không đụng.
        AutoVideo::query()
            ->where('status', AutoVideo::NEW)
            ->whereNotNull('hub_id')
            ->orderBy('id')
            ->each(function (AutoVideo $v) use ($seen, &$result): void {
                if (! isset($seen[$v->hub_id])) {
                    $v->forceFill(['status' => AutoVideo::SKIPPED, 'skip_reason' => self::REASON_UNAPPROVED])->save();
                    $this->apiReport['unapproved']++;
                    $result['skipped']++;
                }
            });

        $this->khoReport['waiting'] = AutoVideo::query()->where('status', AutoVideo::NEW)->whereNotNull('hub_id')
            ->where(fn ($q) => $q->whereNull('caption')->orWhereNotNull('files_deleted_at'))->count();
        $this->khoReport['error'] = $this->apiReport['error'];
        $this->apiReport['backfill'] = $this->backfillClaims();

        return $result;
    }

    /**
     * @param  array<string, mixed>  $item
     * @return 'new'|'known'|'error'
     */
    private function upsertHubVideo(string $id, array $item): string
    {
        $existing = AutoVideo::query()->where('hub_id', $id)->first();

        // Đã giữ chỗ, xếp lịch, đăng, lỗi từ trước thì không bao giờ nạp lại.
        if ($existing !== null && ! in_array($existing->status, [AutoVideo::NEW, AutoVideo::SKIPPED], true)) {
            return 'known';
        }

        // Bị bỏ qua vì lý do khác "hub bỏ duyệt"/"máy khác đã giữ" thì giữ nguyên; được duyệt lại hoặc máy kia nhả thì nhận lại.
        if ($existing !== null && $existing->status === AutoVideo::SKIPPED
            && $existing->skip_reason !== self::REASON_UNAPPROVED && ! str_starts_with((string) $existing->skip_reason, self::REASON_HELD)) {
            return 'known';
        }

        // Máy khác (dùng chung hub) đang giữ video này: không lấy; video `new` của ta thì bỏ qua.
        $holder = is_string($item['giu_boi'] ?? null) && $item['giu_boi'] !== '' ? $item['giu_boi'] : null;

        if ($holder !== null && $holder !== (new HubApi)->may()) {
            if ($existing !== null && $existing->status === AutoVideo::NEW) {
                $existing->forceFill(['status' => AutoVideo::SKIPPED, 'skip_reason' => self::REASON_HELD.': '.$holder])->save();
                $this->apiReport['held']++;
            }

            return 'known';
        }

        $hash = is_string($item['sha256'] ?? null) ? strtolower($item['sha256']) : '';
        $file = is_string($item['file'] ?? null) ? ltrim(str_replace('\\', '/', $item['file']), '/') : '';

        if (preg_match('/^[0-9a-f]{64}$/', $hash) !== 1 || $file === '' || str_contains($file, '..')) {
            Log::warning('AutoPost: video từ hub thiếu sha256/file, bỏ qua.', ['hub_id' => $id]);

            return 'error';
        }

        $quyCach = is_string($item['quy_cach'] ?? null) && $item['quy_cach'] !== '' ? $item['quy_cach'] : null;
        $ngayLam = is_string($item['ngay_lam'] ?? null) ? $item['ngay_lam'] : null;
        $problem = $this->kho->validate(['ma' => $item['ma'] ?? null, 'quy_cach' => $quyCach] + ($ngayLam !== null ? ['ngay_lam' => $ngayLam] : []));

        if ($problem !== null) {
            Log::warning('AutoPost: video từ hub không hợp lệ: '.$problem, ['hub_id' => $id]);
            $this->reportRejected($id, $problem);

            return 'error';
        }

        // Cùng nội dung (sha256) với video khác đã có thì không thêm.
        $sameHash = AutoVideo::query()->where('hash', $hash)->first(['id', 'hub_id']);

        if ($sameHash !== null && ($existing === null || $sameHash->id !== $existing->id)) {
            if ($sameHash->hub_id === null && $existing === null) {
                AutoVideo::query()->whereKey($sameHash->id)->update(['hub_id' => $id]);
            }

            return 'known';
        }

        $path = $this->hubPath().'/'.$file;
        $url = is_string($item['url_file'] ?? null) && $item['url_file'] !== '' ? $item['url_file'] : null;
        // Có url_file thì máy không gắn thư mục hub vẫn tải được qua HTTP khi cần.
        $present = (is_file($path) && (int) filesize($path) > 0) || $url !== null;
        $text = HubText::resolve($path, [
            'caption' => $item['caption'] ?? null,
            'hashtag' => is_array($item['hashtag'] ?? null) ? implode(' ', array_filter($item['hashtag'], 'is_string')) : ($item['hashtag'] ?? null),
        ]);
        $meta = array_filter([
            'anh_bia' => is_string($item['anh_bia'] ?? null) ? $item['anh_bia'] : null,
            'diem' => $item['diem'] ?? null,
            'anh_ung' => $item['anh_ung'] ?? null,
            'giu_boi' => $holder,
            'url_file' => $url,
            'url_anh_bia' => is_string($item['url_anh_bia'] ?? null) && $item['url_anh_bia'] !== '' ? $item['url_anh_bia'] : null,
            'kich_thuoc' => isset($item['kich_thuoc']) && is_numeric($item['kich_thuoc']) ? (int) $item['kich_thuoc'] : null,
        ], fn ($v): bool => $v !== null);

        $attributes = [
            'hub_id' => $id,
            'hash' => $hash,
            'path' => $path,
            'source' => 'hub',
            'batch_date' => $ngayLam ?? now('Asia/Ho_Chi_Minh')->format('Y-m-d'),
            'file_name' => basename($file),
            'product_code' => (string) $item['ma'],
            'quy_cach' => $quyCach,
            'duration' => isset($item['thoi_luong']) && is_numeric($item['thoi_luong']) ? (float) $item['thoi_luong'] : null,
            'status' => AutoVideo::NEW,
            'caption' => $text['caption'],
            'hashtags' => $text['hashtags'],
            'caption_source' => $text['caption'] === null ? null : HubText::SOURCE,
            'product_name' => HubText::cartName($item['ten_gio'] ?? null),
            'meta' => $meta ?: null,
            // File mp4 chưa có trên đĩa thì chưa cho giữ chỗ (dùng cột files_deleted_at làm cờ), có rồi thì mở lại.
            'files_deleted_at' => $present ? null : ($existing?->files_deleted_at ?? now()),
            'skip_reason' => $text['reason'] ?? ($present ? null : 'chưa thấy file mp4 trong hub'),
        ];

        foreach (['goc', 'giong', 'nhac'] as $column) {
            $attributes[$column] = isset($item[$column]) && is_scalar($item[$column]) && $item[$column] !== '' ? (string) $item[$column] : null;
        }

        if (! $present) {
            $this->apiReport['missing']++;
            Log::warning('AutoPost: hub báo video nhưng không thấy file mp4 trong thư mục hub.', ['hub_id' => $id, 'path' => $path]);
        }

        if ($existing === null) {
            AutoVideo::query()->create($attributes);

            return 'new';
        }

        $existing->forceFill($attributes)->save();

        return 'known';
    }

    /** Báo hub (một lần mỗi ngày cho mỗi lý do) rằng video của nó không nhận được. */
    private function reportRejected(string $id, string $reason): void
    {
        if (Cache::add('fork-hub:rejected:'.sha1($id.'|'.$reason), true, 86400)) {
            app(HubReporter::class)->failed(new AutoVideo(['hub_id' => $id]), 'TikTok Auto Kid không nhận: '.$reason);
        }
    }

    /**
     * Kiểu cũ: ra/<ngày>/*.mp4 + bang-ghi.csv.
     *
     * @return array{new: int, skipped: int, known: int}
     */
    private function ingestLegacy(): array
    {
        $result = ['new' => 0, 'skipped' => 0, 'known' => 0];
        $settle = (int) config('fork.auto.settle_seconds', 20);

        foreach ($this->subDirectories($this->hubPath().'/ra') as $dir) {
            $date = basename($dir);

            if (! preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) {
                continue;
            }

            $rows = $this->readCsv($dir.'/bang-ghi.csv');

            foreach (Paths::glob($dir.'/*.mp4') as $path) {
                $name = basename($path);

                if (AutoVideo::query()->where('path', $path)->exists()) {
                    $result['known']++;

                    continue;
                }

                // Hub có thể đang ghi dở file.
                if ($settle > 0 && time() - (int) filemtime($path) < $settle) {
                    continue;
                }

                $hash = hash_file('sha256', $path);

                if ($hash === false) {
                    continue;
                }

                if (AutoVideo::query()->where('hash', $hash)->exists()) {
                    $result['known']++;

                    continue;
                }

                $attributes = $this->attributesFor($path, $name, $date, $hash, $rows[$name] ?? []);

                try {
                    AutoVideo::query()->create($attributes);
                } catch (UniqueConstraintViolationException) {
                    $result['known']++;

                    continue;
                }

                $result[$attributes['status'] === AutoVideo::SKIPPED ? 'skipped' : 'new']++;
            }
        }

        return $result;
    }

    /** @return list<array{ma: string, ten: string}>|null */
    private function parseQuyCach(mixed $raw): ?array
    {
        if (! is_array($raw)) {
            return null;
        }

        $list = [];

        foreach ($raw as $item) {
            if (is_array($item) && isset($item['ma']) && is_scalar($item['ma']) && (string) $item['ma'] !== '') {
                $list[(string) $item['ma']] = ['ma' => (string) $item['ma'], 'ten' => (string) ($item['ten'] ?? $item['ma'])];
            }
        }

        return $list === [] ? null : array_values($list);
    }

    /** Tiền tố trước dấu `_` đầu tiên, so với code hoặc short_name (bỏ dấu, bỏ dấu cách và gạch). */
    public function productCodeForFile(string $fileName): ?string
    {
        $prefix = $this->normalize(Str::before(basename($fileName), '_'));

        if ($prefix === '') {
            return null;
        }

        return $this->prefixMap()[$prefix] ?? null;
    }

    /**
     * Chọn và giữ một video `new` cho tài khoản. Trả null khi hết video hợp lệ.
     *
     * `$allowed`: `array<string $code, list<?string $quyCach>>`. Video khớp khi mã là khoá và quy cách của
     * nó nằm trong danh sách (quy cách null khớp phần tử null). null = không giới hạn; `[]` = không lấy gì;
     * mã có danh sách rỗng = không lấy mã đó. Dạng cũ `list<string>` (chỉ mã) coi như mã => mọi quy cách.
     *
     * Ràng buộc nới dần: (1) tránh sản phẩm của 2 bài gần nhất và góc của 3 bài gần nhất,
     * (2) chỉ tránh sản phẩm 2 bài gần nhất, (3) chỉ tránh sản phẩm bài gần nhất, (4) không ràng buộc.
     *
     * @param  array<int|string, mixed>|null  $allowed
     */
    public function reserveNext(SocialAccount $a, ?array $allowed = null): ?AutoVideo
    {
        $map = $allowed === null ? null : $this->normalizeAllowed($allowed);

        if ($map === []) {
            return null;
        }

        $recent = AutoVideo::query()
            ->where('social_account_id', $a->id)
            ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED, AutoVideo::POSTED])
            ->orderByRaw('COALESCE(scheduled_for, posted_at, updated_at) DESC')
            ->orderByDesc('id')
            ->limit(3)
            ->get(['product_code', 'goc']);

        $recentProducts = $recent->pluck('product_code')->all();
        $recentGoc = $recent->pluck('goc')->filter()->all();

        $candidates = AutoVideo::query()
            ->eligibleNew()
            ->whereIn('product_code', AutoProduct::query()->where('enabled', true)->select('code'))
            ->when($map !== null, fn ($q) => $q->where(function ($q) use ($map): void {
                foreach ($map as $code => $quyCaches) {
                    $q->orWhere(function ($w) use ($code, $quyCaches): void {
                        $w->where('product_code', $code);

                        if (in_array(self::ANY, $quyCaches, true)) {
                            return;
                        }

                        $named = array_values(array_filter($quyCaches, fn ($x): bool => $x !== null));
                        $w->where(function ($w2) use ($named, $quyCaches): void {
                            if ($named !== []) {
                                $w2->whereIn('quy_cach', $named);
                            }

                            if (in_array(null, $quyCaches, true)) {
                                $w2->orWhereNull('quy_cach');
                            }
                        });
                    });
                }
            }))
            ->orderBy('batch_date')
            ->orderBy('id')
            ->limit(500)
            ->get(['id', 'batch_date', 'product_code', 'goc']);

        if ($candidates->isEmpty()) {
            return null;
        }

        $today = $this->postedTodayByProduct($a);

        $levels = [
            [array_slice($recentProducts, 0, 2), $recentGoc],
            [array_slice($recentProducts, 0, 2), []],
            [array_slice($recentProducts, 0, 1), []],
            [[], []],
        ];

        foreach ($levels as [$avoidProducts, $avoidGoc]) {
            $pool = $candidates->reject(
                fn (AutoVideo $c): bool => in_array($c->product_code, $avoidProducts, true)
                    || ($c->goc !== null && in_array($c->goc, $avoidGoc, true))
            );

            // Lô cũ trước, trong cùng lô thì sản phẩm nào hôm nay đăng ít nhất lên trước.
            $ordered = $pool->sortBy([
                fn (AutoVideo $x, AutoVideo $y): int => $x->batch_date <=> $y->batch_date,
                fn (AutoVideo $x, AutoVideo $y): int => ($today[$x->product_code] ?? 0) <=> ($today[$y->product_code] ?? 0),
                fn (AutoVideo $x, AutoVideo $y): int => $x->id <=> $y->id,
            ]);

            foreach ($ordered as $candidate) {
                $claimed = AutoVideo::query()
                    ->whereKey($candidate->id)
                    ->where('status', AutoVideo::NEW)
                    ->update([
                        'status' => AutoVideo::RESERVED,
                        'social_account_id' => $a->id,
                        'updated_at' => now(),
                    ]);

                if ($claimed === 1) {
                    return AutoVideo::query()->find($candidate->id);
                }
            }
        }

        return null;
    }

    /**
     * reserveNext + giữ chỗ trên hub cho đúng giờ đăng `$slot`. Video hub bị máy khác giữ/đã đăng thì bỏ qua và thử
     * video kế. Hub tắt hoặc từ chối giữ chỗ thì KHÔNG đăng video đó: trả null, đặt `claimBlock`, video về kho.
     * Hub bản cũ chưa có route /giu thì đăng như trước (một máy).
     *
     * @param  array<int|string, mixed>|null  $allowed
     */
    public function reserveClaimed(SocialAccount $a, ?array $allowed, CarbonInterface $slot): ?AutoVideo
    {
        $this->claimBlock = null;
        $api = new HubApi;

        for ($try = 0; $try < self::MAX_CLAIM_TRIES; $try++) {
            $video = $this->reserveNext($a, $allowed);

            if ($video === null) {
                return null;
            }

            if (! HubApi::enabled() || blank($video->hub_id)) {
                return $video;
            }

            $channel = '@'.($a->username ?: $a->display_name);
            $claim = $api->claim((string) $video->hub_id, $channel, CarbonImmutable::instance($slot)->addDay());

            switch ($claim['state']) {
                case HubApi::CLAIM_OK:
                    app(HubReporter::class)->claimed((string) $video->hub_id);
                    $this->markClaimed($video);

                    return $video;

                case HubApi::CLAIM_NO_ROUTE:
                    if (config('fork.auto.hub_api.require_claim')) {
                        // Máy phụ dùng chung hub: hub cũ không giữ chỗ được thì KHÔNG đăng, tránh trùng với máy chính.
                        $this->claimBlock = 'hub chưa có tính năng giữ chỗ — mở lại app Xưởng Video bản mới';
                        $this->release($video, $this->claimBlock);

                        return null;
                    }

                    if (Cache::add('fork-hub:claim-no-route', true, 3600)) {
                        Log::warning('Hub API: hub chưa có route giữ chỗ (/giu), đăng như một máy. Hãy khởi động lại hub bản mới.');
                    }

                    return $video;

                case HubApi::CLAIM_HELD:
                    $this->skipClaimed($video, self::REASON_HELD.': '.$claim['by']);

                    break;

                case HubApi::CLAIM_POSTED:
                    $this->skipClaimed($video, self::REASON_POSTED);

                    break;

                case HubApi::CLAIM_NOT_FOUND:
                    $this->skipClaimed($video, 'hub không còn video này');

                    break;

                default:
                    $this->claimBlock = $claim['status'] === null ? 'hub không trả lời (đang tắt?)' : 'hub từ chối giữ chỗ (HTTP '.$claim['status'].')';
                    // Có thể hub đã nhận lệnh giữ nhưng ta không nhận được trả lời: nhả để khỏi giữ ma.
                    $this->release($video, $this->claimBlock);

                    return null;
            }
        }

        $this->claimBlock = 'quá '.self::MAX_CLAIM_TRIES.' video liên tiếp bị máy khác giữ';

        return null;
    }

    private function markClaimed(AutoVideo $v): void
    {
        $v->forceFill(['meta' => [...(array) $v->meta, 'hub_claimed_at' => now()->toIso8601String()]])->save();
    }

    /**
     * Video đã giữ chỗ/xếp lịch từ trước khi có tính năng giữ chỗ: giữ chỗ bù trên hub. Hub cũ (thiếu route) hoặc tắt thì
     * để lượt sau. Bị máy khác giữ/đã đăng thì KHÔNG huỷ gì (bài đã hẹn trên TikTok), chỉ ghi log và báo Telegram.
     *
     * @return array{claimed: int, conflicts: int, pending: int}
     */
    public function backfillClaims(): array
    {
        $out = ['claimed' => 0, 'conflicts' => 0, 'pending' => 0];

        if (! HubApi::enabled()) {
            return $out;
        }

        $api = new HubApi;
        $videos = AutoVideo::query()
            ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED])
            ->whereNotNull('hub_id')
            ->with('socialAccount')
            ->orderBy('id')
            ->get();

        foreach ($videos as $v) {
            if (data_get($v->meta, 'hub_claimed_at') !== null || data_get($v->meta, 'hub_claim_conflict') !== null) {
                continue;
            }

            $a = $v->socialAccount;
            $channel = '@'.($a?->username ?: $a?->display_name ?: '?');
            $until = $v->scheduled_for !== null ? CarbonImmutable::instance($v->scheduled_for)->addDay() : now()->addDays(2);
            $claim = $api->claim((string) $v->hub_id, $channel, $until);

            if ($claim['state'] === HubApi::CLAIM_OK) {
                $this->markClaimed($v);
                app(HubReporter::class)->claimed((string) $v->hub_id);
                $out['claimed']++;
            } elseif (in_array($claim['state'], [HubApi::CLAIM_HELD, HubApi::CLAIM_POSTED], true)) {
                $holder = $claim['state'] === HubApi::CLAIM_HELD ? 'máy '.$claim['by'].' giữ' : 'hub báo đã đăng';
                $v->forceFill(['meta' => [...(array) $v->meta, 'hub_claim_conflict' => $claim['by'] ?? 'posted']])->save();
                Log::warning('Tự động đăng: video đã xếp lịch nhưng hub không cho giữ chỗ, kiểm tra trùng.', ['hub_id' => $v->hub_id, 'state' => $claim['state'], 'by' => $claim['by']]);
                Telegram::send(
                    "Video {$v->hub_id} đã bị {$holder} nhưng bài đã hẹn trên TikTok ở kênh {$channel} — kiểm tra trùng.",
                    'fork-hub:dup:'.$v->hub_id,
                    86400,
                );
                $out['conflicts']++;
            } else {
                // Hub cũ thiếu route, không có video, hub tắt: thử lại lượt sau.
                $out['pending']++;

                if ($claim['state'] === HubApi::CLAIM_NO_ROUTE || $claim['state'] === HubApi::CLAIM_UNKNOWN) {
                    break;
                }
            }
        }

        return $out;
    }

    /** Video bị hub từ chối giữ chỗ (máy khác giữ/đã đăng): bỏ qua, không bao giờ đăng. */
    private function skipClaimed(AutoVideo $v, string $reason): void
    {
        $v->forceFill([
            'status' => AutoVideo::SKIPPED,
            'social_account_id' => null,
            'post_id' => null,
            'scheduled_for' => null,
            'skip_reason' => Str::limit($reason, 250, ''),
        ])->save();

        Log::info('Tự động đăng: bỏ qua video vì hub không cho giữ chỗ.', ['hub_id' => $v->hub_id, 'reason' => $reason]);
    }

    /**
     * @param  array<int|string, mixed>  $allowed
     * @return array<string, list<string|null>> mã => danh sách quy cách (self::ANY = mọi quy cách); mã rỗng bị bỏ
     */
    private function normalizeAllowed(array $allowed): array
    {
        $map = [];

        foreach ($allowed as $key => $value) {
            if (is_array($value)) {
                $list = array_values(array_filter($value, fn ($x): bool => $x === null || is_string($x)));
                $code = (string) $key;
            } else {
                // Dạng cũ: list<string> các mã.
                $code = (string) $value;
                $list = [self::ANY];
            }

            if ($code !== '' && $list !== []) {
                $map[$code] = array_values(array_unique([...($map[$code] ?? []), ...$list], SORT_REGULAR));
            }
        }

        return $map;
    }

    /**
     * Trả video về kho. Mới chỉ `reserved` thì quay về `new`; đã `scheduled` thì KHÔNG bao giờ quay
     * về `new` (kết quả có thể không rõ, đăng lại sẽ trùng) mà chuyển `failed` kèm lý do.
     */
    public function release(AutoVideo $v, string $reason): void
    {
        $v->refresh();

        if ($v->status === AutoVideo::RESERVED) {
            $v->forceFill([
                'status' => AutoVideo::NEW,
                'social_account_id' => null,
                'post_id' => null,
                'scheduled_for' => null,
                'skip_reason' => null,
            ])->save();

            // Đã giữ chỗ trên hub thì nhả để máy khác (hoặc lượt sau) lấy được.
            app(HubReporter::class)->released($v);

            return;
        }

        if ($v->status === AutoVideo::SCHEDULED) {
            $this->fail($v, $reason);
        }
    }

    /** Đánh dấu thất bại hẳn. Video `failed` không tự quay lại `new`. */
    public function fail(AutoVideo $v, string $reason): void
    {
        if ($v->status === AutoVideo::POSTED) {
            return;
        }

        $v->forceFill(['status' => AutoVideo::FAILED, 'skip_reason' => Str::limit($reason, 250, '')])->save();
        app(HubReporter::class)->failed($v, $reason);
    }

    /** Đánh dấu đã đăng và chuyển file sang <hub>/ra/_da-dang/<batch_date>/. */
    public function markPosted(AutoVideo $v, ?string $tiktokVideoId): void
    {
        $v->refresh();

        $v->forceFill([
            'status' => AutoVideo::POSTED,
            'posted_at' => $v->posted_at ?? now(),
            'tiktok_video_id' => $tiktokVideoId ?? $v->tiktok_video_id,
            'skip_reason' => null,
        ]);

        // Chế độ API: hub tự dọn file của nó (30 ngày), TikTok Auto Kid không chuyển hay xoá file nào.
        // Kho chuẩn mới: da-dang/<ngày> + .ket-qua.json + lưu giữ theo cài đặt. Kiểu cũ: ra/_da-dang/.
        if (! HubApi::enabled()) {
            if ($v->source === 'kho') {
                $this->kho->archive($v);
            } else {
                $this->archiveFile($v);
            }
        }

        $v->save();
        app(HubReporter::class)->posted($v);
    }

    private function archiveFile(AutoVideo $v): void
    {
        $target = $this->hubPath().'/ra/_da-dang/'.$v->batch_date->format('Y-m-d');

        if (dirname($v->path) === $target) {
            return;
        }

        if (! is_file($v->path)) {
            Log::warning('AutoPost: không thấy file để chuyển sang _da-dang', ['path' => $v->path]);

            return;
        }

        if (! is_dir($target) && ! @mkdir($target, 0775, true) && ! is_dir($target)) {
            Log::warning('AutoPost: không tạo được thư mục _da-dang', ['dir' => $target]);

            return;
        }

        $destination = $target.'/'.basename($v->path);

        if (file_exists($destination)) {
            $destination = $target.'/'.pathinfo($v->path, PATHINFO_FILENAME).'-'.$v->id.'.mp4';
        }

        if (@rename($v->path, $destination)) {
            $v->path = $destination;
        } else {
            Log::warning('AutoPost: không chuyển được file sang _da-dang', ['from' => $v->path, 'to' => $destination]);
        }
    }

    /** Số bài (đã giữ, xếp lịch, đăng) từ đầu ngày địa phương của tài khoản, theo sản phẩm. */
    private function postedTodayByProduct(SocialAccount $a): array
    {
        $tz = $a->timezone ?: 'Asia/Ho_Chi_Minh';
        $start = CarbonImmutable::now($tz)->startOfDay()->utc();

        return AutoVideo::query()
            ->where('social_account_id', $a->id)
            ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED, AutoVideo::POSTED])
            ->whereRaw('COALESCE(scheduled_for, posted_at, updated_at) >= ?', [$start])
            ->selectRaw('product_code, count(*) as total')
            ->groupBy('product_code')
            ->pluck('total', 'product_code')
            ->map(fn ($n): int => (int) $n)
            ->all();
    }

    /** @return array<string, mixed> */
    private function attributesFor(string $path, string $name, string $date, string $hash, array $row): array
    {
        $attributes = [
            'hash' => $hash,
            'path' => $path,
            'batch_date' => $date,
            'file_name' => $name,
            'product_code' => $this->productCodeForFile($name),
            'duration' => isset($row['thoi_luong']) && is_numeric($row['thoi_luong']) ? (float) $row['thoi_luong'] : null,
            'script' => ($row['loi'] ?? '') !== '' ? $row['loi'] : null,
            'status' => AutoVideo::NEW,
        ];

        foreach (self::CSV_COLUMNS as $column) {
            $attributes[$column] = ($row[$column] ?? '') !== '' ? $row[$column] : null;
        }

        $text = HubText::resolve($path);
        $attributes['caption'] = $text['caption'];
        $attributes['hashtags'] = $text['hashtags'];
        $attributes['caption_source'] = $text['caption'] === null ? null : HubText::SOURCE;
        $attributes['skip_reason'] = $text['reason'];

        if (str_contains($name, '_CHON-NHAC-TIKTOK_')) {
            $attributes['status'] = AutoVideo::SKIPPED;
            $attributes['skip_reason'] = 'chưa có nhạc';
        } elseif (! str_contains($name, '_MIXKIT_')) {
            $attributes['status'] = AutoVideo::SKIPPED;
            $attributes['skip_reason'] = 'không phải bản MIXKIT';
        }

        return $attributes;
    }

    /**
     * Video `new` đã biết: đọc lại chữ của hub. Có caption thì ghi (hub là nguồn đúng, kể cả khi sửa chữ);
     * chưa có thì giữ nguyên và ghi lý do chờ. Không đụng video đã giữ chỗ/xếp lịch/đăng.
     */
    private function refreshHubText(): void
    {
        $this->hubReport = ['updated' => 0, 'waiting' => 0];

        AutoVideo::query()->where('status', AutoVideo::NEW)->orderBy('id')->each(function (AutoVideo $v): void {
            // Video từ API hub: chữ do API cấp, không đọc .txt/.csv cạnh file.
            if ($v->hub_id !== null || ! is_file($v->path)) {
                return;
            }

            $json = null;

            if ($v->source === 'kho' && $v->json_path && is_file($v->json_path)) {
                $decoded = json_decode((string) file_get_contents($v->json_path), true);
                $json = is_array($decoded) && ! array_is_list($decoded) ? $decoded : null;
            }

            $text = HubText::resolve($v->path, $json);

            if ($text['caption'] === null) {
                if (blank($v->caption)) {
                    $this->hubReport['waiting']++;
                    $v->forceFill(['skip_reason' => $text['reason']]);
                    $v->isDirty() && $v->save();
                }

                return;
            }

            $v->forceFill([
                'caption' => $text['caption'],
                'hashtags' => $text['hashtags'],
                'caption_source' => HubText::SOURCE,
                'product_name' => $v->source === 'kho' ? $text['ten_gio'] : $v->product_name,
                'skip_reason' => null,
            ]);

            if ($v->isDirty()) {
                $v->save();
                $this->hubReport['updated']++;
            }
        });
    }

    /** Video nhặt trước khi sản phẩm được đồng bộ thì gắn lại sản phẩm ở lần sau. */
    private function resolveMissingProducts(): void
    {
        AutoVideo::query()->whereNull('product_code')->get(['id', 'file_name'])->each(function (AutoVideo $v): void {
            if ($code = $this->productCodeForFile($v->file_name)) {
                AutoVideo::query()->whereKey($v->id)->update(['product_code' => $code]);
            }
        });
    }

    /** @return array<string, string> */
    private function prefixMap(): array
    {
        if ($this->prefixMap !== null) {
            return $this->prefixMap;
        }

        $map = [];

        foreach (AutoProduct::query()->get(['code', 'short_name']) as $product) {
            $map[$this->normalize($product->short_name)] ??= $product->code;
            $map[$this->normalize($product->code)] ??= $product->code;
        }

        return $this->prefixMap = $map;
    }

    private function normalize(string $text): string
    {
        return preg_replace('/[^a-z0-9]/', '', Str::lower(Str::ascii($text))) ?? '';
    }

    /** @return list<string> */
    private function subDirectories(string $parent): array
    {
        if (! is_dir($parent)) {
            return [];
        }

        $dirs = [];

        foreach (scandir($parent) ?: [] as $entry) {
            if ($entry === '.' || $entry === '..' || str_starts_with($entry, '_')) {
                continue;
            }

            if (is_dir($parent.'/'.$entry)) {
                $dirs[] = $parent.'/'.$entry;
            }
        }

        sort($dirs);

        return $dirs;
    }

    /** @return array<string, array<string, string>> tên file => hàng (khoá theo tên cột) */
    private function readCsv(string $file): array
    {
        return HubText::readCsv($file);
    }
}

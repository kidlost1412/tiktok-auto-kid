<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Paths;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Rieng\RiengThumbs;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use RuntimeException;
use Symfony\Component\Process\Process;
use Throwable;

/**
 * "AI xem video" cho Kho riêng: app tự cắt 18 khung thành 2 ảnh lưới, kèm ảnh mẫu từng sản phẩm, rồi hỏi ChatGPT
 * (Codex CLI, tài khoản luân phiên) đoán sản phẩm và viết caption. Chưa chắc thì nghe thêm lời nói (Whisper trên máy),
 * nâng mức nghĩ, rồi đổi model (xem analyze()).
 *
 * Kết quả nằm ở meta.ai của video:
 *   state: ok (chắc sản phẩm) | unsure (chủ app phải chọn sản phẩm) | error (sẽ thử lại) | gave_up
 *   product_code, chac, ly_do, tom_tat, caption, model, at, tries, next_try_at, error
 * AI chắc chắn ("cao") thì gắn luôn product_code cho video, trừ khi chủ app đã tự chọn (meta.product_by = kid).
 */
class RiengAnalyzer
{
    public const int MAX_TRIES = 5;

    /** Cả bậc thang đều lỗi thì thử lại sau: 2 phút, 10 phút, 30 phút, 2 giờ. */
    private const array BACKOFF = [2, 10, 30, 120];

    public const int CAPTION_MAX = 90;

    /** Model thật đã dùng ở lần hỏi gần nhất (có thể khác model đã chọn nếu tài khoản không có). */
    private ?string $usedModel = null;

    public function __construct(
        private readonly ChatGptAccounts $accounts,
        private readonly CodexRunner $codex,
        private readonly RiengThumbs $thumbs,
        private readonly ?RiengSpeech $speech = null,
    ) {}

    /** Video riêng cần AI xem: chưa đăng, còn file, chưa có kết quả hoặc lỗi đã tới giờ thử lại. Cũ trước. */
    public function pending(int $limit, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();

        return AutoVideo::query()
            ->where('source', AutoVideo::SOURCE_RIENG)
            ->where('status', AutoVideo::NEW)
            ->whereNull('files_deleted_at')
            ->where(fn ($q) => $q->whereRaw("(meta->'ai') is null")->orWhereRaw("(meta->'ai'->>'state') is null")
                ->orWhere(fn ($e) => $e->whereRaw("meta->'ai'->>'state' = 'error'")->whereRaw("(meta->'ai'->>'next_try_at') <= ?", [$now->utc()->toIso8601String()])))
            ->orderBy('id')
            ->limit($limit)
            ->get()
            ->all();
    }

    /**
     * Cho các video AI đã lỗi (kể cả đã bỏ cuộc) được xem lại ngay ở lượt tới, đếm lại số lần thử từ đầu.
     * Dùng khi chủ app bấm "Thử lại ngay", đổi model/mức nghĩ/Fast, hoặc app vừa lên bản mới (có thể đã sửa lỗi).
     */
    public function retryNow(?CarbonImmutable $now = null): int
    {
        $now ??= CarbonImmutable::now();
        $n = 0;

        AutoVideo::query()
            ->where('source', AutoVideo::SOURCE_RIENG)
            ->where('status', AutoVideo::NEW)
            ->whereNull('files_deleted_at')
            ->whereRaw("meta->'ai'->>'state' in ('error', 'gave_up')")
            ->each(function (AutoVideo $v) use ($now, &$n): void {
                $meta = (array) $v->meta;
                $meta['ai'] = array_merge((array) ($meta['ai'] ?? []), ['state' => 'error', 'tries' => 0, 'next_try_at' => $now->utc()->toIso8601String()]);
                $v->forceFill(['meta' => $meta])->save();
                $n++;
            });

        $this->accounts->clearErrors();

        return $n;
    }

    /**
     * Cho AI xem một video và lưu kết quả vào meta.ai. Trả về meta.ai mới.
     *
     * Đi theo bậc thang, dừng ngay khi AI chắc chắn sản phẩm:
     *   1. model + mức nghĩ đã chọn, xem khung hình + ảnh sản phẩm mẫu;
     *   2. nghe thêm lời nói trong video (Whisper trên máy);
     *   3. cùng model, nâng mức nghĩ lên cao nhất model đó có;
     *   4. lần lượt các model khác của tài khoản, mức nghĩ cao nhất.
     * Bậc nào lỗi (trả sai định dạng...) thì sang bậc kế ngay, không đợi. Hết bậc vẫn không chắc thì giữ kết quả tốt nhất.
     *
     * @return array<string, mixed>
     */
    public function analyze(AutoVideo $video, ?CarbonImmutable $now = null, int $budgetSeconds = 1500): array
    {
        $now ??= CarbonImmutable::now();
        $lock = Cache::lock('fork-rieng:ai-video:'.$video->id, $budgetSeconds + 300);

        if (! $lock->get()) {
            return (array) data_get($video->meta, 'ai', []);
        }

        $started = microtime(true);
        $prev = (array) data_get($video->meta, 'ai', []);
        $tries = (int) ($prev['tries'] ?? 0) + 1;
        $settings = RiengAutoSettings::get();
        $work = storage_path('app/rieng-ai/'.$video->id);
        $loi = is_string($prev['loi'] ?? null) ? $prev['loi'] : null;
        $steps = [];

        try {
            if (! is_file((string) $video->path)) {
                throw new RuntimeException('Không còn thấy file video.');
            }

            @mkdir($work, 0775, true);
            $grids = $this->grids($video, $work);
            $products = $this->products();

            if ($products === []) {
                throw new RuntimeException('Chưa có sản phẩm nào đang bật để AI chọn.');
            }

            [$photos, $photoCodes] = $this->productPhotos($products, $work);
            $plan = $this->plan($settings);
            $best = null;
            $lastError = null;

            // Bộ nghe đã cài thì nghe ngay từ bậc 1 (miễn phí, chạy trên máy): tránh AI nhìn chai giống nhau mà đoán sai.
            $hearFirst = $loi !== null || $this->speech()->ready();

            foreach ($plan as $i => $step) {
                if ($i > 0 && microtime(true) - $started > $budgetSeconds) {
                    break;
                }

                if ($hearFirst) {
                    if ($step['chi_loi']) {
                        continue; // bậc 1 đã nghe rồi: bậc "nghe thêm" thừa
                    }

                    $step['loi'] = true;
                    $step['ten'] = str_replace(' · xem hình', ' · xem hình + nghe lời nói', $step['ten']);
                }

                if ($step['loi'] && $loi === null) {
                    $this->progress($video, $prev, $i + 1, count($plan), 'Đang nghe lời nói trong video', $now);
                    $loi = $this->speech()->transcribe((string) $video->path);

                    if ($loi === null) {
                        $steps[] = ['buoc' => $step['ten'], 'ket_qua' => 'bỏ qua: bộ nghe lời nói chưa sẵn sàng'];

                        // Không có lời nói thì bậc "nghe thêm" giống hệt bậc 1: bỏ qua, sang bậc kế.
                        if ($step['chi_loi']) {
                            continue;
                        }
                    }
                }

                $this->progress($video, $prev, $i + 1, count($plan), $step['ten'], $now);
                $prompt = $this->prompt($products, count($grids), $photoCodes, $step['loi'] ? $loi : null);

                try {
                    [$answer, $account] = $this->askAny($step['model'], $step['effort'], (bool) $settings['fast'], $prompt, [...$grids, ...$photos], $work);
                    $parsed = $this->parse($answer, array_column($products, 'ma'));
                } catch (CodexLimited|NoAccount $e) {
                    // Hết lượt / chưa có tài khoản: bậc sau cũng không chạy được.
                    $lastError = $e;
                    $steps[] = ['buoc' => $step['ten'], 'ket_qua' => 'lỗi: '.$e->getMessage()];
                    break;
                } catch (Throwable $e) {
                    $lastError = $e;
                    $steps[] = ['buoc' => $step['ten'], 'ket_qua' => 'lỗi: '.mb_substr($e->getMessage(), 0, 160)];
                    Log::info('Kho riêng: AI chưa xem được, sang bậc kế.', ['video_id' => $video->id, 'buoc' => $step['ten'], 'error' => $e->getMessage()]);

                    continue;
                }

                $ai = [
                    'state' => $parsed['ma'] !== null && $parsed['chac'] === 'cao' ? 'ok' : 'unsure',
                    'product_code' => $parsed['ma'],
                    'chac' => $parsed['chac'],
                    'ly_do' => $parsed['ly_do'],
                    'tom_tat' => $parsed['tom_tat'],
                    'caption' => $parsed['caption'],
                    'hashtags' => $parsed['hashtags'],
                    'model' => $this->usedModel ?? $step['model'],
                    'effort' => $step['effort'],
                    'fast' => (bool) $settings['fast'],
                    'account' => $account,
                ];
                $steps[] = ['buoc' => $step['ten'], 'ket_qua' => $ai['product_code'] === null ? 'không nhận ra sản phẩm' : $ai['product_code'].' ('.$ai['chac'].')'];

                if ($best === null || self::score($ai) > self::score($best)) {
                    $best = $ai;
                }

                if ($ai['state'] === 'ok') {
                    break;
                }
            }

            if ($best === null) {
                throw $lastError ?? new RuntimeException('AI chưa xem được video.');
            }

            $ai = $best + [
                'at' => $now->toIso8601String(),
                'tries' => $tries,
                'approved' => false,
                'loi' => $loi,
                'buoc' => $steps,
            ];
        } catch (Throwable $e) {
            $msg = mb_substr($e->getMessage(), 0, 300);
            $giveUp = $tries >= self::MAX_TRIES;
            $ai = array_merge($prev, [
                'state' => $giveUp ? 'gave_up' : 'error',
                'error' => $msg,
                'tries' => $tries,
                'at' => $now->toIso8601String(),
                'loi' => $loi,
                'buoc' => $steps,
                'next_try_at' => $giveUp ? null : $now->addMinutes(self::BACKOFF[min($tries - 1, count(self::BACKOFF) - 1)])->utc()->toIso8601String(),
            ]);
            unset($ai['dang']);
            Log::warning('Kho riêng: AI chưa xem được video.', ['video_id' => $video->id, 'error' => $msg]);
        } finally {
            $this->cleanup($work);
            $lock->release();
        }

        $this->store($video, $ai);

        return $ai;
    }

    /** Kết quả nào tốt hơn: chắc chắn > đoán "vừa" > đoán "thấp" > không nhận ra. */
    private static function score(array $ai): int
    {
        if ($ai['product_code'] === null) {
            return 0;
        }

        return match ($ai['chac']) {
            'cao' => 3,
            'vua' => 2,
            default => 1,
        };
    }

    /**
     * Các bậc thử cho một video (xem analyze()).
     *
     * @return list<array{ten: string, model: string, effort: string, loi: bool, chi_loi: bool}>
     */
    public function plan(array $settings): array
    {
        $acct = $this->accounts->pick();
        $list = $acct !== null ? ($this->accounts->knownModels($acct) ?? $this->accounts->models($acct)) : null;
        $list = is_array($list) && $list !== [] ? $list : RiengAutoSettings::MODELS;
        $base = $acct !== null ? $this->accounts->modelFor($acct, (string) $settings['model'])[0] : (string) $settings['model'];
        $effortsOf = fn (string $m): array => array_values((array) ($list[$m]['efforts'] ?? RiengAutoSettings::MODELS[$m]['efforts'] ?? array_keys(RiengAutoSettings::EFFORTS)));
        $top = function (string $m) use ($effortsOf): string {
            $e = $effortsOf($m);

            return (string) (end($e) ?: 'high');
        };
        $name = fn (string $m): string => (string) ($list[$m]['name'] ?? RiengAutoSettings::MODELS[$m]['name'] ?? $m);
        $label = fn (string $e): string => RiengAutoSettings::EFFORTS[$e] ?? $e;
        $effort = self::nearestEffort($effortsOf($base), (string) $settings['effort']);

        $plan = [
            ['ten' => "{$name($base)} · {$label($effort)} · xem hình", 'model' => $base, 'effort' => $effort, 'loi' => false, 'chi_loi' => false],
            ['ten' => "{$name($base)} · {$label($effort)} · nghe thêm lời nói", 'model' => $base, 'effort' => $effort, 'loi' => true, 'chi_loi' => true],
        ];

        if ($top($base) !== $effort) {
            $plan[] = ['ten' => "{$name($base)} · {$label($top($base))} (nghĩ kỹ nhất)", 'model' => $base, 'effort' => $top($base), 'loi' => true, 'chi_loi' => false];
        }

        foreach (array_keys($list) as $m) {
            if ($m !== $base) {
                $plan[] = ['ten' => "Đổi model {$name((string) $m)} · {$label($top((string) $m))}", 'model' => (string) $m, 'effort' => $top((string) $m), 'loi' => true, 'chi_loi' => false];
            }
        }

        return $plan;
    }

    /** Ghi "AI đang xem, bậc mấy" để trang hiện tiến độ; không đụng kết quả cũ. */
    private function progress(AutoVideo $video, array $prev, int $step, int $total, string $what, CarbonImmutable $now): void
    {
        $fresh = AutoVideo::query()->find($video->id);

        if ($fresh === null) {
            return;
        }

        $meta = (array) $fresh->meta;
        $meta['ai'] = array_merge($prev, ['dang' => ['buoc' => $step, 'tong' => $total, 'viec' => $what, 'tu' => $now->toIso8601String(), 'luc' => now()->toIso8601String()]]);
        $fresh->forceFill(['meta' => $meta])->save();
    }

    /**
     * Ảnh sản phẩm mẫu (san-pham/<mã>/anh.jpg của Xưởng), thu nhỏ cho AI so với bao bì trong video.
     *
     * @param  list<array<string, mixed>>  $products
     * @return array{0: list<string>, 1: list<string>} [đường dẫn ảnh, mã sản phẩm theo đúng thứ tự]
     */
    protected function productPhotos(array $products, string $work): array
    {
        $root = Paths::root((string) config('fork.auto.hub_path'));
        $ffmpeg = $this->thumbs->ffmpegPath();
        $paths = [];
        $codes = [];

        foreach ($products as $i => $p) {
            $src = $root.'/san-pham/'.$p['ma'].'/anh.jpg';

            if (! is_file($src)) {
                continue;
            }

            $dst = $work.DIRECTORY_SEPARATOR.'sp-'.$i.'.jpg';

            if ($ffmpeg !== null) {
                (new Process([$ffmpeg, '-y', '-v', 'error', '-i', $src, '-vf', "scale='min(384,iw)':-2", '-q:v', '4', $dst]))->setTimeout(30)->run();
            }

            if (! is_file($dst)) {
                @copy($src, $dst);
            }

            if (is_file($dst)) {
                $paths[] = $dst;
                $codes[] = (string) $p['ma'];
            }
        }

        return [$paths, $codes];
    }

    private function speech(): RiengSpeech
    {
        return $this->speech ?? app(RiengSpeech::class);
    }

    /** Ghi meta.ai và (khi AI chắc chắn, chủ app chưa tự chọn) gắn sản phẩm. Đọc lại video để không đè thay đổi vừa có. */
    private function store(AutoVideo $video, array $ai): void
    {
        $fresh = AutoVideo::query()->find($video->id);

        if ($fresh === null) {
            return;
        }

        $meta = (array) $fresh->meta;
        $meta['ai'] = $ai;
        $changes = ['meta' => $meta];

        if (in_array($ai['state'], ['ok', 'unsure'], true) && ($meta['product_by'] ?? null) !== 'kid' && $fresh->status === AutoVideo::NEW) {
            $changes['product_code'] = $ai['state'] === 'ok' ? $ai['product_code'] : null;
            $changes['quy_cach'] = null;
        }

        $fresh->forceFill($changes)->save();
        $video->setRawAttributes($fresh->getAttributes(), true);
    }

    /**
     * Thử lần lượt các tài khoản ChatGPT (luân phiên); tài khoản hết lượt thì nghỉ và đổi tài khoản khác.
     *
     * @param  list<string>  $images
     * @return array{0: string, 1: string}
     */
    /** Mức nghĩ model đó có; không có mức đã chọn thì lấy mức gần nhất thấp hơn. */
    private function effortFor(string $id, string $model, string $effort): string
    {
        $efforts = $this->accounts->knownModels($id)[$model]['efforts'] ?? null;

        return is_array($efforts) ? self::nearestEffort(array_values($efforts), $effort) : $effort;
    }

    /** @param  list<string>  $efforts */
    private static function nearestEffort(array $efforts, string $effort): string
    {
        if ($efforts === [] || in_array($effort, $efforts, true)) {
            return $effort;
        }

        $order = array_keys(RiengAutoSettings::EFFORTS);
        $want = (int) array_search($effort, $order, true);
        $best = $efforts[0];

        foreach ($efforts as $e) {
            if ((int) array_search($e, $order, true) <= $want) {
                $best = $e;
            }
        }

        return $best;
    }

    private function askAny(string $model, string $effort, bool $fast, string $prompt, array $images, string $work): array
    {
        $tried = [];

        while (($id = $this->accounts->pick(null, $tried)) !== null) {
            $tried[] = $id;

            try {
                // Tài khoản không có model đã chọn (vd gói free) thì dùng model mặc định của tài khoản đó.
                [$use, $canFast] = $this->accounts->modelFor($id, $model);

                try {
                    $answer = $this->codex->ask($id, $use, $this->effortFor($id, $use, $effort), $prompt, $images, $work, $fast && $canFast);
                } catch (RuntimeException $e) {
                    if (! $e instanceof CodexLimited && preg_match('/không dùng được model|model is not supported|model .* not (?:supported|available|found)|does not exist/iu', $e->getMessage()) === 1) {
                        $alt = $this->accounts->fallbackModel($id, $use);

                        if ($alt === null || $alt[0] === $use) {
                            throw $e;
                        }

                        [$use, $canFast] = $alt;
                        $answer = $this->codex->ask($id, $use, $this->effortFor($id, $use, $effort), $prompt, $images, $work, $fast && $canFast);
                    } else {
                        throw $e;
                    }
                }

                $this->accounts->markUsed($id);
                $this->usedModel = $use;

                return [$answer, $id];
            } catch (CodexLimited $e) {
                $this->accounts->markLimited($id, $e->minutes !== null ? CarbonImmutable::now()->addMinutes($e->minutes) : null);
            } catch (RuntimeException $e) {
                $this->accounts->markError($id, $e->getMessage());

                throw $e;
            }
        }

        throw new NoAccount($tried === [] ? 'Chưa có tài khoản ChatGPT nào sẵn sàng (chưa đăng nhập hoặc đang hết lượt).' : 'Mọi tài khoản ChatGPT đang hết lượt.');
    }

    /**
     * 2 ảnh lưới 3x3 = 18 khung cắt đều cả video, khung đủ to để ChatGPT đọc được chữ trên video và nhãn chai.
     *
     * @return list<string>
     */
    protected function grids(AutoVideo $video, string $work): array
    {
        $ffmpeg = $this->thumbs->ffmpegPath() ?? throw new RuntimeException('Không tìm thấy ffmpeg.');
        $dur = max(1.0, (float) ($video->duration ?: 30));
        $fps = number_format(18 / $dur, 4, '.', '');
        $pattern = $work.DIRECTORY_SEPARATOR.'luoi-%d.jpg';
        $p = new Process([$ffmpeg, '-y', '-v', 'error', '-i', (string) $video->path, '-vf', "fps={$fps},scale=420:-2,tile=3x3", '-frames:v', '2', '-q:v', '3', $pattern]);
        $p->setTimeout(120)->run();
        $out = array_values(array_filter([1, 2], fn (int $i): bool => is_file(sprintf($pattern, $i))));

        if ($out === []) {
            throw new RuntimeException('Không cắt được khung hình từ video.');
        }

        return array_map(fn (int $i): string => sprintf($pattern, $i), $out);
    }

    /**
     * Sản phẩm đang bật, kèm sự thật từ hồ sơ Xưởng (san-pham/<mã>/san-pham.json).
     *
     * @return list<array{ma: string, ten: string, nhan_dien: ?string, su_that: list<string>, khong_duoc_noi: list<string>}>
     */
    public function products(): array
    {
        $root = Paths::root((string) config('fork.auto.hub_path'));
        $out = [];

        foreach (AutoProduct::query()->where('enabled', true)->orderBy('code')->get() as $p) {
            $profile = json_decode((string) @file_get_contents($root.'/san-pham/'.$p->code.'/san-pham.json'), true);
            $profile = is_array($profile) ? $profile : [];
            $out[] = [
                'ma' => (string) $p->code,
                'ten' => (string) ($profile['ten_goi'] ?? ($p->short_name ?: $p->code)),
                'nhan_dien' => is_string($profile['nhan_dien_chai'] ?? null) ? $profile['nhan_dien_chai'] : null,
                'su_that' => array_slice(array_values(array_filter((array) ($profile['su_that_duoc_noi'] ?? []), 'is_string')), 0, 10),
                'khong_duoc_noi' => array_values(array_filter((array) ($profile['khong_duoc_noi'] ?? []), 'is_string')),
            ];
        }

        return $out;
    }

    /** @param  list<array<string, mixed>>  $products */
    /**
     * @param  list<array<string, mixed>>  $products
     * @param  list<string>  $photoCodes  mã sản phẩm của các ảnh mẫu đính kèm sau ảnh lưới, đúng thứ tự
     * @param  ?string  $loi  lời nói trong video (Whisper), null nếu không nghe
     */
    public function prompt(array $products, int $images = 2, array $photoCodes = [], ?string $loi = null): string
    {
        $list = json_encode($products, JSON_UNESCAPED_UNICODE);
        $max = self::CAPTION_MAX;
        $what = $images > 1 ? "{$images} ẢNH LƯỚI, mỗi ảnh 9 khung" : 'ẢNH LƯỚI 9 khung';
        $photos = '';

        if ($photoCodes !== []) {
            $lines = [];

            foreach ($photoCodes as $i => $code) {
                $lines[] = '- Ảnh '.($images + $i + 1).": sản phẩm `{$code}`";
            }

            $photos = "\n\nSau các ảnh lưới là ẢNH MẪU của từng sản phẩm (chai/bao bì thật), dùng để so với bao bì xuất hiện trong video:\n".implode("\n", $lines);
        }

        $sound = $loi === null
            ? 'Không có tiếng: hãy đọc kỹ CHỮ trên video (phụ đề, tiêu đề), chữ trên nhãn/bao bì và xem cảnh để hiểu video nói gì.'
            : ($loi === ''
                ? 'Video không có lời nói: hãy đọc kỹ CHỮ trên video (phụ đề, tiêu đề), chữ trên nhãn/bao bì và xem cảnh.'
                : "LỜI NÓI trong video (máy tự nghe, có thể sai vài chữ, tên sản phẩm có thể bị nghe nhầm gần giống):\n\"\"\"{$loi}\"\"\"\nKết hợp lời nói với chữ trên video, nhãn/bao bì và cảnh để hiểu video nói gì.");

        return <<<TXT
Bạn là người làm nội dung TikTok bán vật tư nông nghiệp, am hiểu nhà vườn. Ảnh đính kèm đầu tiên là {$what}, cắt đều theo thời gian từ đầu đến cuối một video (ảnh 1 trước ảnh 2; trong mỗi ảnh đọc trái→phải, trên→dưới).{$photos}

{$sound}

Việc 1 — Video đang bán SẢN PHẨM nào trong DANH SÁCH?
- Bằng chứng mạnh nhất là TÊN sản phẩm: đọc được trên nhãn, trong chữ trên video, hoặc nghe trong lời nói. Lời nói/chữ nói về công dụng nào (vd. "bám dính, loang trải", "kích rễ", "đạm cá") thì ưu tiên sản phẩm có công dụng đó.
- Nhiều sản phẩm CÙNG HÃNG có chai, logo, màu nhãn giống nhau: KHÔNG được chọn "cao" chỉ vì màu chai/logo/hình dáng. Ảnh mẫu chỉ để tham khảo (có thể là ảnh quảng cáo hoặc cảnh dùng sản phẩm, không phải chai).
- "chac": "cao" chỉ khi có tên sản phẩm (nhãn đọc rõ, chữ trên video hoặc lời nói) và không mâu thuẫn với nội dung video; chỉ khớp hình thì tối đa "vua". Không thấy sản phẩm nào trong danh sách → "ma": null.
- Hai sản phẩm gần giống nhau (vd. cùng loại nhưng khác dung tích/bao bì) mà video không cho phân biệt được → "chac": "thap".

Việc 2 — Viết 1 caption TikTok tiếng Việt, tối đa {$max} ký tự, KHÔNG hashtag, KHÔNG emoji:
- Bám đúng nội dung video (chữ trên video, cảnh trong video), như người làm vườn nói với bà con; có lực, gợi tò mò hoặc nói trúng nỗi lo của nhà vườn.
- Chỉ nói điều video nói rõ hoặc điều có trong `su_that` của sản phẩm đã chọn. Tuyệt đối tránh mọi điều trong `khong_duoc_noi` (giá tiền, "chữa khỏi", "số 1", "nhất", cam kết 100%...).
- Không chắc sản phẩm thì viết caption theo nội dung chung của video, không nêu tên sản phẩm.

Việc 3 — Đúng 3 hashtag tiếng Việt KHÔNG DẤU, viết liền (vd. #nanodongtoancau #vuoncaphe #ruavuon): 1 cái tên sản phẩm (nếu chắc), còn lại theo cây trồng / việc trong video.

Trả về DUY NHẤT một JSON, không giải thích thêm:
{"ma": "mã sản phẩm hoặc null", "chac": "cao|vua|thap", "ly_do": "1 câu vì sao chọn", "tom_tat": "1-2 câu video có gì", "caption": "...", "hashtag": ["#...", "#...", "#..."]}

DANH SÁCH SẢN PHẨM:
{$list}
TXT;
    }

    /**
     * @param  list<string>  $codes
     * @return array{ma: ?string, chac: string, ly_do: string, tom_tat: string, caption: string, hashtags: list<string>}
     */
    public function parse(string $answer, array $codes): array
    {
        $json = null;

        if (preg_match('/\{.*\}/s', $answer, $m) === 1) {
            $json = json_decode($m[0], true);
        }

        if (! is_array($json)) {
            throw new RuntimeException('ChatGPT trả lời sai định dạng.');
        }

        $ma = is_string($json['ma'] ?? null) && in_array($json['ma'], $codes, true) ? $json['ma'] : null;
        $chac = in_array($json['chac'] ?? null, ['cao', 'vua', 'thap'], true) ? $json['chac'] : 'thap';
        $caption = trim(preg_replace('/\s+/u', ' ', str_replace('#', '', (string) ($json['caption'] ?? ''))) ?? '');

        if (mb_strlen($caption) > self::CAPTION_MAX) {
            $cut = mb_substr($caption, 0, self::CAPTION_MAX);
            $space = mb_strrpos($cut, ' ');
            $caption = rtrim($space !== false && $space > 40 ? mb_substr($cut, 0, $space) : $cut, ' ,;:-');
        }

        return [
            'ma' => $ma,
            'chac' => $ma === null ? 'thap' : $chac,
            'ly_do' => mb_substr(trim((string) ($json['ly_do'] ?? '')), 0, 300),
            'tom_tat' => mb_substr(trim((string) ($json['tom_tat'] ?? '')), 0, 400),
            'caption' => $caption,
            'hashtags' => array_slice(Hashtags::normalize(array_map(
                fn ($t): string => '#'.(preg_replace('/[^A-Za-z0-9]/', '', Str::ascii((string) $t)) ?? ''),
                array_filter((array) ($json['hashtag'] ?? $json['hashtags'] ?? []), 'is_string'),
            )), 0, 3),
        ];
    }

    private function cleanup(string $work): void
    {
        foreach (glob($work.DIRECTORY_SEPARATOR.'*') ?: [] as $f) {
            @unlink($f);
        }

        @rmdir($work);
    }
}

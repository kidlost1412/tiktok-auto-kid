<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Paths;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Rieng\RiengThumbs;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use RuntimeException;
use Symfony\Component\Process\Process;
use Throwable;

/**
 * "AI xem video" cho Kho riêng: app tự cắt 18 khung thành 2 ảnh lưới (không chép lời nói: tránh tốn tiền dịch vụ ngoài),
 * rồi hỏi ChatGPT (Codex CLI, tài khoản luân phiên) đoán sản phẩm và viết caption từ hình + chữ trên video.
 *
 * Kết quả nằm ở meta.ai của video:
 *   state: ok (chắc sản phẩm) | unsure (chủ app phải chọn sản phẩm) | error (sẽ thử lại) | gave_up
 *   product_code, chac, ly_do, tom_tat, caption, model, at, tries, next_try_at, error
 * AI chắc chắn ("cao") thì gắn luôn product_code cho video, trừ khi chủ app đã tự chọn (meta.product_by = kid).
 */
class RiengAnalyzer
{
    public const int MAX_TRIES = 5;

    /** Thử lại sau lỗi: 10 phút, 30 phút, 2 giờ, 6 giờ. */
    private const array BACKOFF = [10, 30, 120, 360];

    public const int CAPTION_MAX = 90;

    public function __construct(
        private readonly ChatGptAccounts $accounts,
        private readonly CodexRunner $codex,
        private readonly RiengThumbs $thumbs,
    ) {}

    /** Video riêng cần AI xem: chưa đăng, còn file, chưa có kết quả hoặc lỗi đã tới giờ thử lại. Cũ trước. */
    public function pending(int $limit, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();

        return AutoVideo::query()
            ->where('source', AutoVideo::SOURCE_RIENG)
            ->where('status', AutoVideo::NEW)
            ->whereNull('files_deleted_at')
            ->where(fn ($q) => $q->whereRaw("(meta->'ai') is null")
                ->orWhere(fn ($e) => $e->whereRaw("meta->'ai'->>'state' = 'error'")->whereRaw("(meta->'ai'->>'next_try_at') <= ?", [$now->utc()->toIso8601String()])))
            ->orderBy('id')
            ->limit($limit)
            ->get()
            ->all();
    }

    /**
     * Cho AI xem một video và lưu kết quả vào meta.ai. Trả về meta.ai mới.
     *
     * @return array<string, mixed>
     */
    public function analyze(AutoVideo $video, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $prev = (array) data_get($video->meta, 'ai', []);
        $tries = (int) ($prev['tries'] ?? 0) + 1;
        $settings = RiengAutoSettings::get();
        $work = storage_path('app/rieng-ai/'.$video->id);

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

            $prompt = $this->prompt($products, count($grids));
            [$answer, $account] = $this->askAny($settings['model'], $settings['effort'], (bool) $settings['fast'], $prompt, $grids, $work);
            $parsed = $this->parse($answer, array_column($products, 'ma'));

            $ai = [
                'state' => $parsed['ma'] !== null && $parsed['chac'] === 'cao' ? 'ok' : 'unsure',
                'product_code' => $parsed['ma'],
                'chac' => $parsed['chac'],
                'ly_do' => $parsed['ly_do'],
                'tom_tat' => $parsed['tom_tat'],
                'caption' => $parsed['caption'],
                'hashtags' => $parsed['hashtags'],
                'model' => $settings['model'],
                'effort' => $settings['effort'],
                'fast' => (bool) $settings['fast'],
                'account' => $account,
                'at' => $now->toIso8601String(),
                'tries' => $tries,
                'approved' => false,
            ];
        } catch (Throwable $e) {
            $msg = mb_substr($e->getMessage(), 0, 300);
            $giveUp = $tries >= self::MAX_TRIES;
            $ai = array_merge($prev, [
                'state' => $giveUp ? 'gave_up' : 'error',
                'error' => $msg,
                'tries' => $tries,
                'at' => $now->toIso8601String(),
                'next_try_at' => $giveUp ? null : $now->addMinutes(self::BACKOFF[min($tries - 1, count(self::BACKOFF) - 1)])->utc()->toIso8601String(),
            ]);
            Log::warning('Kho riêng: AI chưa xem được video.', ['video_id' => $video->id, 'error' => $msg]);
        } finally {
            $this->cleanup($work);
        }

        $this->store($video, $ai);

        return $ai;
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
    private function askAny(string $model, string $effort, bool $fast, string $prompt, array $images, string $work): array
    {
        $tried = [];

        while (($id = $this->accounts->pick(null, $tried)) !== null) {
            $tried[] = $id;

            try {
                $answer = $this->codex->ask($id, $model, $effort, $prompt, $images, $work, $fast);
                $this->accounts->markUsed($id);

                return [$answer, $id];
            } catch (CodexLimited $e) {
                $this->accounts->markLimited($id, $e->minutes !== null ? CarbonImmutable::now()->addMinutes($e->minutes) : null);
            } catch (RuntimeException $e) {
                $this->accounts->markError($id, $e->getMessage());

                throw $e;
            }
        }

        throw new RuntimeException($tried === [] ? 'Chưa có tài khoản ChatGPT nào sẵn sàng (chưa đăng nhập hoặc đang hết lượt).' : 'Mọi tài khoản ChatGPT đang hết lượt.');
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
    public function prompt(array $products, int $images = 2): string
    {
        $list = json_encode($products, JSON_UNESCAPED_UNICODE);
        $max = self::CAPTION_MAX;
        $what = $images > 1 ? "{$images} ẢNH LƯỚI, mỗi ảnh 9 khung" : 'ẢNH LƯỚI 9 khung';

        return <<<TXT
Bạn là người làm nội dung TikTok bán vật tư nông nghiệp, am hiểu nhà vườn. Ảnh đính kèm là {$what}, cắt đều theo thời gian từ đầu đến cuối một video (ảnh 1 trước ảnh 2; trong mỗi ảnh đọc trái→phải, trên→dưới). Không có tiếng: hãy đọc kỹ CHỮ trên video (phụ đề, tiêu đề), chữ trên nhãn/bao bì và xem cảnh để hiểu video nói gì.

Việc 1 — Video đang bán SẢN PHẨM nào trong DANH SÁCH?
- Chỉ chọn khi thấy bao bì/nhãn khớp `nhan_dien`, hoặc chữ trên video nêu rõ tên sản phẩm.
- Hai sản phẩm gần giống nhau (vd. cùng loại nhưng khác dung tích/bao bì) mà video không cho phân biệt được → "chac": "thap".
- "chac": "cao" chỉ khi chắc chắn; không chắc thì "vua"/"thap"; không thấy sản phẩm nào trong danh sách → "ma": null.

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
                fn ($t): string => '#'.ltrim(Str::ascii(str_replace(' ', '', (string) $t)), '#'),
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

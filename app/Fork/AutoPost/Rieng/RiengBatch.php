<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Scheduling\MissingVideoFile;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\AutoPost\Scheduling\PostBuilder;
use App\Fork\AutoPost\Scheduling\RetryFailed;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\VideoLibrary;
use App\Fork\Chrome\ChromeJobs;
use App\Models\Post;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Contracts\Cache\LockTimeoutException;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
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
     * @return list<array{code: string, quy_cach: ?string, label: string, name: string, tags: list<string>}>
     */
    public function productOptions(string $socialAccountId): array
    {
        $allowed = $this->cart->evaluate($socialAccountId)['allowed'];
        $products = AutoProduct::query()->where('enabled', true)->whereIn('code', array_keys($allowed))->get()->keyBy('code');
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
                    'tags' => app(Hashtags::class)->configFor($product)['tags'],
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
        $option = collect($this->productOptions((string) $auto->social_account_id))->first(fn (array $o): bool => $o['code'] === $code && $o['quy_cach'] === $qc);

        if ($code === '') {
            return $fail('Hãy chọn sản phẩm gắn giỏ hàng (bắt buộc).');
        }

        if ($option === null) {
            return $fail('Sản phẩm này chưa có giỏ hàng hợp lệ trên kênh đã chọn.');
        }

        $product = AutoProduct::query()->find($code);
        $mode = ($in['mode'] ?? self::MODE_AUTO) === self::MODE_MANUAL ? self::MODE_MANUAL : self::MODE_AUTO;
        $sharedCaption = trim((string) ($in['caption'] ?? ''));
        $sharedTags = Hashtags::normalize($in['hashtags'] ?? []);
        $items = array_values(array_filter((array) ($in['items'] ?? []), 'is_array'));

        if ($items === []) {
            return $fail('Chưa chọn video nào.');
        }

        $tz = $this->planner->timezoneFor($auto);
        $fmt = fn (int $ts): string => CarbonImmutable::createFromTimestampUTC($ts)->setTimezone($tz)->format('H:i d/m');
        $gap = $this->planner->gapSeconds();
        $horizon = $this->planner->horizonFor($auto, $now);
        $hardMax = $now->addSeconds(ChromeJobs::SCHEDULE_MAX_AHEAD - 3600);
        $minAt = $now->addSeconds(Planner::MIN_LEAD);
        $room = $this->planner->futureRoom($auto, $now);

        $rows = [];
        $seen = [];

        foreach ($items as $item) {
            $id = (int) ($item['id'] ?? 0);
            $video = $id > 0 && ! isset($seen[$id]) ? AutoVideo::query()->whereKey($id)->where('source', AutoVideo::SOURCE_RIENG)->first() : null;
            $seen[$id] = true;
            $row = ['id' => $id, 'file_name' => $video?->file_name, 'status' => 'ok', 'messages' => [], 'at' => null, 'caption' => null, 'hashtags' => []];

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

            $caption = filled($item['caption'] ?? null) ? trim((string) $item['caption']) : $sharedCaption;
            $tags = array_key_exists('hashtags', $item) && $item['hashtags'] !== null && $item['hashtags'] !== '' && $item['hashtags'] !== []
                ? Hashtags::normalize($item['hashtags']) : $sharedTags;
            $row['caption'] = $caption;
            $row['hashtags'] = $tags;

            if ($caption === '') {
                $row['status'] = 'error';
                $row['messages'][] = 'Chưa có caption.';
            } else {
                $final = app(Hashtags::class)->apply($caption, $tags, $product);

                if (mb_strlen(HubText::compose($final['caption'], $final['hashtags'])) > HubText::MAX_CHARS) {
                    $row['status'] = 'error';
                    $row['messages'][] = 'Caption dài quá '.HubText::MAX_CHARS.' ký tự (giới hạn TikTok).';
                }
            }

            $row['_at'] = $mode === self::MODE_MANUAL ? $this->parseAt($item['at'] ?? null) : null;
            $rows[] = $row;
        }

        $left = 0;

        if ($mode === self::MODE_AUTO) {
            $left = $this->assignAuto($rows, $auto, $now, $horizon, $room, $tz);
        } else {
            $this->checkManual($rows, $auto, $now, $minAt, $horizon, $hardMax, $gap, $room, $tz, $fmt);
        }

        foreach ($rows as &$r) {
            unset($r['_at']);
        }

        unset($r);

        return [
            'ok' => true,
            'error' => null,
            'mode' => $mode,
            'rows' => $rows,
            'left' => $left,
            'needs_confirm' => collect($rows)->contains(fn (array $r): bool => $r['status'] === 'warn'),
            'channel' => '@'.($social->username ?: $social->display_name),
        ];
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
     * Tự động: video (theo thứ tự chọn) lấy các giờ trống gần nhất của Planner, trong hạn mức bài chờ đăng.
     * Gán `_at` thẳng vào $rows; video không còn giờ trống để status `skip`. Trả số video còn lại.
     *
     * @param  list<array<string, mixed>>  $rows
     */
    private function assignAuto(array &$rows, AutoAccount $auto, CarbonImmutable $now, CarbonImmutable $horizon, int $room, \DateTimeZone $tz): int
    {
        $from = $now->addSeconds(Planner::MIN_LEAD)->startOfMinute()->addMinute();
        $slots = array_slice($this->planner->slotsFor($auto, $from, $horizon), 0, max(0, $room));
        $left = 0;
        $i = 0;

        foreach ($rows as &$r) {
            if ($r['status'] === 'error') {
                continue;
            }

            if (! isset($slots[$i])) {
                $r['status'] = 'skip';
                $r['messages'][] = $room <= 0 ? 'Kênh đã đủ số bài chờ đăng.' : 'Chưa có giờ trống trong '.$this->planner->aheadDays($auto).' ngày tới, video này để lại.';
                $left++;

                continue;
            }

            $r['_at'] = $slots[$i++];
            $r['at'] = $r['_at']->setTimezone($tz)->toIso8601String();
        }

        unset($r);

        return $left;
    }

    /**
     * Thủ công: kiểm từng giờ do chủ chọn. Lỗi cứng (status `error`): thiếu giờ, gần hơn 45 phút, quá xa theo TikTok, trùng giờ y hệt
     * trên cùng kênh, vượt hạn mức bài chờ. Cảnh báo (status `warn`, cho phép "Vẫn hẹn"): sát giờ bài khác của kênh,
     * sát giờ kênh khác, ngoài số ngày xếp trước của kênh.
     *
     * @param  list<array<string, mixed>>  $rows
     */
    private function checkManual(array &$rows, AutoAccount $auto, CarbonImmutable $now, CarbonImmutable $minAt, CarbonImmutable $horizon, CarbonImmutable $hardMax, int $gap, int $room, \DateTimeZone $tz, \Closure $fmt): void
    {
        $times = array_filter(array_map(fn (array $r): ?CarbonImmutable => $r['_at'] ?? null, $rows));
        $stamps = array_map(fn (CarbonImmutable $t): int => $t->getTimestamp(), $times) ?: [$now->getTimestamp()];
        $from = CarbonImmutable::createFromTimestampUTC(min($stamps) - $gap - 3600);
        $to = CarbonImmutable::createFromTimestampUTC(max($stamps) + $gap + 3600);

        $mine = $this->entries($auto, $from, $to, true);
        $others = $this->entries($auto, $from, $to, false);
        $batch = [];
        $used = 0;

        foreach ($rows as &$r) {
            if ($r['status'] === 'error') {
                continue;
            }

            /** @var CarbonImmutable|null $at */
            $at = $r['_at'] ?? null;

            if ($at === null) {
                $r['status'] = 'error';
                $r['messages'][] = 'Chưa chọn giờ đăng.';

                continue;
            }

            $r['at'] = $at->setTimezone($tz)->toIso8601String();
            $ts = $at->getTimestamp();

            if ($at->lessThan($minAt)) {
                $r['status'] = 'error';
                $r['messages'][] = 'Giờ đăng phải cách bây giờ ít nhất '.intdiv(Planner::MIN_LEAD, 60).' phút (để Chrome kịp nhận bài).';

                continue;
            }

            if ($at->greaterThan($hardMax)) {
                $r['status'] = 'error';
                $r['messages'][] = 'TikTok chỉ cho hẹn giờ tối đa khoảng 9 ngày tới.';

                continue;
            }

            if ($used >= $room) {
                $r['status'] = 'error';
                $r['messages'][] = 'Kênh đã đủ số bài chờ đăng, không hẹn thêm được.';

                continue;
            }

            $exact = false;

            foreach ([...$mine, ...array_map(fn (int $t): array => ['ts' => $t, 'what' => 'một video khác trong lượt này'], $batch)] as $e) {
                if (abs($e['ts'] - $ts) < self::EXACT_SECONDS) {
                    $exact = true;
                    $r['messages'][] = 'Đã có bài đúng giờ '.$fmt($e['ts']).' trên kênh này ('.($e['what'] ?? 'bài khác').').';
                    break;
                }
            }

            if ($exact) {
                $r['status'] = 'error';

                continue;
            }

            foreach ($mine as $e) {
                if (abs($e['ts'] - $ts) < $gap) {
                    $r['status'] = 'warn';
                    $r['messages'][] = 'Trùng giờ với bài '.$fmt($e['ts']).' của kênh này (cần cách nhau ít nhất '.intdiv($gap, 60).' phút).';
                }
            }

            foreach ($batch as $t) {
                if (abs($t - $ts) < $gap) {
                    $r['status'] = 'warn';
                    $r['messages'][] = 'Gần giờ '.$fmt($t).' của một video khác trong lượt này (cần cách nhau ít nhất '.intdiv($gap, 60).' phút).';
                }
            }

            foreach ($others as $e) {
                if (abs($e['ts'] - $ts) < Planner::CHANNEL_CLEARANCE) {
                    $r['status'] = 'warn';
                    $r['messages'][] = 'Trùng giờ với bài '.$fmt($e['ts']).' của kênh '.$e['what'].' (hai kênh nên cách nhau ít nhất '.intdiv(Planner::CHANNEL_CLEARANCE, 60).' phút).';
                }
            }

            if ($at->greaterThan($horizon)) {
                $r['status'] = 'warn';
                $r['messages'][] = 'Xa hơn '.$this->planner->aheadDays($auto).' ngày xếp trước của kênh này.';
            }

            $batch[] = $ts;
            $used++;
        }

        unset($r);
    }

    /**
     * Bài đã xếp trong khoảng: video tự động/riêng và bài TikTok hẹn giờ. $same = cùng kênh; không thì các kênh khác.
     *
     * @return list<array{ts: int, what: string}>
     */
    private function entries(AutoAccount $auto, CarbonImmutable $from, CarbonImmutable $to, bool $same): array
    {
        $op = $same ? '=' : '!=';
        $out = [];
        $names = SocialAccount::query()->get(['id', 'username', 'display_name'])->mapWithKeys(fn (SocialAccount $s): array => [$s->id => '@'.($s->username ?: $s->display_name)]);

        $videos = AutoVideo::query()->where('social_account_id', $op, $auto->social_account_id)->whereIn('status', self::COUNTED)
            ->whereBetween('scheduled_for', [$from, $to])->get(['social_account_id', 'scheduled_for']);

        foreach ($videos as $v) {
            $out[] = ['ts' => $v->scheduled_for->getTimestamp(), 'what' => $same ? 'bài khác' : (string) ($names[$v->social_account_id] ?? 'khác')];
        }

        $posts = Post::query()->where('social_account_id', $op, $auto->social_account_id)->where('status', PostStatus::Scheduled)
            ->whereBetween('scheduled_at', [$from, $to])->get(['social_account_id', 'scheduled_at']);

        foreach ($posts as $p) {
            $ts = CarbonImmutable::parse($p->scheduled_at)->getTimestamp();

            // Bài của video tự động đã có dòng AutoVideo ở trên: không đếm hai lần.
            if (! collect($out)->contains(fn (array $e): bool => $e['ts'] === $ts)) {
                $out[] = ['ts' => $ts, 'what' => $same ? 'bài khác' : (string) ($names[$p->social_account_id] ?? 'khác')];
            }
        }

        return $out;
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
        $code = (string) $in['product_code'];
        $qc = filled($in['quy_cach'] ?? null) ? (string) $in['quy_cach'] : null;
        $done = 0;
        $failed = 0;
        $rows = [];

        foreach ($plan['rows'] as $row) {
            if (! in_array($row['status'], ['ok', 'warn'], true) || $row['at'] === null) {
                $rows[] = $row + ['result' => $row['status'] === 'skip' ? 'skip' : 'error'];

                continue;
            }

            $error = $this->applyOne($social, (int) $row['id'], $code, $qc, (string) $row['caption'], (array) $row['hashtags'], CarbonImmutable::parse($row['at'])->utc());

            if ($error === null) {
                $done++;
                $rows[] = $row + ['result' => 'done'];
            } else {
                $failed++;
                $rows[] = $row + ['result' => 'error', 'error' => $error];
            }
        }

        return ['ok' => true, 'error' => null, 'committed' => true, 'needs_confirm' => false, 'mode' => $plan['mode'], 'channel' => $plan['channel'], 'rows' => $rows, 'left' => $plan['left'], 'done' => $done, 'failed' => $failed];
    }

    /** @return string|null lỗi (tiếng Việt) hoặc null khi đã hẹn xong */
    private function applyOne(SocialAccount $social, int $id, string $code, ?string $qc, string $caption, array $tags, CarbonImmutable $slot): ?string
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

        $previous = $video->only(['product_code', 'quy_cach', 'caption', 'hashtags', 'caption_source']);

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

        try {
            $this->builder->build($social, $video, ['caption' => $caption, 'hashtags' => $tags, 'source' => 'rieng', 'product_name' => null], $slot);

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
            $this->library->release($video, 'Đăng hàng loạt lỗi');
            $video->refresh();
            $video->forceFill($previous + $extra)->save();
        } catch (Throwable $e) {
            report($e);
        }
    }
}

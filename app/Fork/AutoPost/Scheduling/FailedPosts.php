<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Media\ProductImageLookup;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\FailureReasons;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeRefusal;
use App\Models\Post;
use App\Models\SocialAccount;
use Illuminate\Support\Collection;

/**
 * "Bài không đăng được": bài đã xếp lịch mà Chrome báo lỗi (hết hàng, sai tài khoản...) hoặc đã chốt lỗi,
 * kèm lý do tiếng Việt (FailureReasons) và việc có thể làm. Trước đây bài hẹn giờ có job Chrome lỗi vẫn hiện là
 * "đã xếp" cho tới tận giờ đăng nên chủ app không biết.
 *
 *  - `job`: bài còn hẹn giờ, lượt giao Chrome gần nhất lỗi. "Đăng lại" giao lượt mới cho Chrome, chỉ khi lượt cũ
 *    CHẮC CHẮN chưa gửi gì lên TikTok (failed + not_sent, hoặc chưa được cấp quyền) và bài chưa có mã TikTok;
 *  - `video`: bài đã chốt lỗi (AutoVideo failed). "Thử lại" dùng RetryFailed (video về kho).
 */
final class FailedPosts
{
    public const int DAYS = 3;

    public const array BAD_STATES = ['failed', 'rejected', 'uncertain'];

    /** Post meta: chủ app đã bấm "Đăng lại" lúc kênh bận, chờ kênh rảnh thì app tự giao. */
    public const string RETRY_WANTED = 'fork_retry_wanted';

    public function __construct(private readonly ChromeJobs $chrome, private readonly RetryFailed $retry) {}

    /**
     * @param  Collection<int, SocialAccount>  $accounts
     * @return list<array<string, mixed>>
     */
    public function forAccounts(Collection $accounts, ProductImageLookup $images, int $days = self::DAYS): array
    {
        $ids = $accounts->pluck('id')->map(fn ($id): string => (string) $id)->all();

        if ($ids === []) {
            return [];
        }

        $since = now()->subDays($days);

        $jobs = ChromeJob::query()
            ->whereIn('social_account_id', $ids)
            ->whereIn('state', self::BAD_STATES)
            ->where('updated_at', '>=', $since)
            ->whereNotExists(fn ($q) => $q->selectRaw('1')->from('fork_chrome_jobs as later')
                ->whereColumn('later.post_id', 'fork_chrome_jobs.post_id')
                ->whereColumn('later.attempt', '>', 'fork_chrome_jobs.attempt'))
            ->get()
            ->reject(fn (ChromeJob $j): bool => ChromeJobs::isQuotaRejection($j));

        $videos = AutoVideo::query()
            ->whereIn('social_account_id', $ids)
            ->where(fn ($q) => $q
                ->where(fn ($j) => $j->whereIn('post_id', $jobs->pluck('post_id')->all())->whereIn('status', [AutoVideo::SCHEDULED, AutoVideo::RESERVED, AutoVideo::FAILED]))
                ->orWhere(fn ($f) => $f->where('status', AutoVideo::FAILED)->where('updated_at', '>=', $since)))
            ->get();

        $hub = AutoProduct::query()->get()->keyBy('code');
        $postIds = $videos->pluck('post_id')->filter()->all();
        $posts = Post::query()->whereIn('id', $postIds)->get()->keyBy('id');
        $latest = $postIds === [] ? collect() : ChromeJob::query()->whereIn('post_id', $postIds)->orderBy('attempt')->get()->keyBy('post_id');

        $rows = [];

        foreach ($videos as $v) {
            $post = $v->post_id !== null ? ($posts[$v->post_id] ?? null) : null;

            if ($post !== null && ($post->status === PostStatus::Published || filled($post->platform_post_id))) {
                continue;
            }

            $row = $this->describe($v, $post, $latest[$v->post_id] ?? null);

            if ($row === null) {
                continue;
            }

            $rows[] = [
                ...$row,
                'id' => $v->id,
                'username' => $accounts->firstWhere('id', $v->social_account_id)?->username,
                'product_code' => $v->product_code,
                'product_label' => CartRules::label($hub[$v->product_code] ?? null, (string) $v->product_code, $v->quy_cach),
                'product_image' => $images->forSlot((string) $v->social_account_id, $v->product_code, $v->quy_cach),
                'source' => $v->source,
                'caption' => $this->snippet($v->caption),
            ];
        }

        usort($rows, fn (array $a, array $b): int => strcmp((string) $a['at'], (string) $b['at']));

        return $rows;
    }

    /**
     * Lỗi của MỘT video (khung xem video). Null = không có lỗi cần báo.
     *
     * @return array<string, mixed>|null
     */
    public function forVideo(AutoVideo $video): ?array
    {
        if (! in_array($video->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED, AutoVideo::FAILED], true)) {
            return null;
        }

        $post = $video->post_id !== null ? Post::query()->find($video->post_id) : null;

        if ($post !== null && ($post->status === PostStatus::Published || filled($post->platform_post_id))) {
            return null;
        }

        return $this->describe($video, $post, $post !== null ? $this->chrome->latestForPost($post) : null);
    }

    /** @return array<string, mixed>|null */
    private function describe(AutoVideo $v, ?Post $post, ?ChromeJob $job): ?array
    {
        $jobBad = $job !== null && in_array($job->state, self::BAD_STATES, true) && ! ChromeJobs::isQuotaRejection($job);
        $product = self::productName($v, $post);

        if ($v->status === AutoVideo::FAILED) {
            $failure = $jobBad
                ? FailureReasons::forJob($job, $product)
                : (FailureReasons::fromText($v->skip_reason, $product) ?? $this->rawFailure($v->skip_reason));
            $refusal = $this->retry->refusal($v);

            return [
                ...$failure,
                'kind' => 'video',
                'state' => $job?->state === 'uncertain' ? 'uncertain' : 'failed',
                'at' => ($v->scheduled_for ?? $v->updated_at)?->toIso8601String(),
                'failed_at' => ($job?->result_at ?? $v->updated_at)?->toIso8601String(),
                'can_retry' => $refusal === null,
                'retry_note' => $refusal,
                'can_confirm_retry' => $refusal !== null && $this->retry->refusal($v, true) === null,
            ];
        }

        if (! $jobBad || $post === null) {
            return null;
        }

        $refusal = $this->jobRefusal($v, $post, $job);

        return [
            ...FailureReasons::forJob($job, $product),
            'kind' => 'job',
            'state' => $job->state === 'uncertain' ? 'uncertain' : 'failed',
            'at' => ($post->scheduled_at ?? $v->scheduled_for)?->toIso8601String(),
            'failed_at' => ($job->result_at ?? $job->updated_at)?->toIso8601String(),
            'can_retry' => $refusal === null,
            'retry_note' => $refusal,
            'can_confirm_retry' => false,
        ];
    }

    /** Tên sản phẩm trong giỏ của bài (tên giỏ hiện trên video). */
    public static function productName(AutoVideo $v, ?Post $post): ?string
    {
        $name = data_get($post?->meta, 'fork_shop_product_name') ?: $v->product_name;

        return filled($name) ? (string) $name : null;
    }

    /**
     * Lý do không "Đăng lại" được, hoặc null nếu an toàn: lượt Chrome gần nhất lỗi và CHẮC CHẮN chưa gửi gì lên TikTok.
     */
    private function jobRefusal(AutoVideo $v, ?Post $post, ?ChromeJob $job, bool $ignoreWanted = false): ?string
    {
        if (! $ignoreWanted && $post !== null && filled(data_get($post->meta, self::RETRY_WANTED)) && $job !== null && $job->state === 'failed') {
            return 'Đã xếp hàng đăng lại: kênh đang bận bài khác, app tự giao bài này cho Chrome ngay khi kênh rảnh.';
        }

        if (! in_array($v->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED], true)) {
            return 'Bài này không còn ở trạng thái chờ đăng.';
        }

        if ($post === null) {
            return 'Bài không còn tồn tại.';
        }

        if (filled($post->platform_post_id) || filled($post->platform_url) || $post->status === PostStatus::Published) {
            return 'Bài này đã lên TikTok, không đăng lại để tránh trùng.';
        }

        if ($post->status !== PostStatus::Scheduled) {
            return 'Bài này đã tới giờ và app đang xử lý. Hãy chờ kết quả.';
        }

        if ($job === null) {
            return 'Bài này chưa giao cho Chrome; app sẽ tự giao ở lượt kế tiếp.';
        }

        if (in_array($job->state, ChromeJob::OPEN, true)) {
            return 'Chrome đang xử lý bài này. Hãy chờ vài phút.';
        }

        return match (true) {
            $job->state === 'posted' => 'Bài đã được hẹn trên TikTok, không cần đăng lại.',
            $job->state === 'uncertain' => 'Chưa chắc bài đã lên TikTok chưa. Mở TikTok Studio kiểm tra trước, app không tự đăng lại để khỏi trùng bài.',
            $job->state === 'rejected' && ! ChromeJobs::isQuotaRejection($job) => 'TikTok đã từ chối bài này. Hãy sửa bài hoặc dùng video khác, không đăng lại nguyên bản.',
            $job->state !== 'failed' => 'Bài đang chờ app giao lại cho Chrome.',
            data_get($job->result, 'not_sent') !== true && $job->authorized_at !== null => 'Chưa chắc Chrome chưa gửi bài lên TikTok. Mở TikTok Studio kiểm tra trước.',
            default => null,
        };
    }

    /**
     * "Đăng lại" bài hẹn giờ có lượt Chrome lỗi: giao lượt mới (đăng hẹn giờ). Kiểm tra an toàn ở jobRefusal và
     * ChromeJobs::queueForPost (số lần thử tối đa, giờ hẹn đủ xa, mỗi kênh một job mở).
     *
     * @return string|null lý do từ chối, null khi đã giao lượt mới
     */
    public function retryJob(AutoVideo $video): ?string
    {
        return $this->retryOrQueue($video)['error'];
    }

    /**
     * Như retryJob, nhưng kênh đang bận một bài khác thì KHÔNG bắt chủ app bấm lại: đánh dấu bài "chờ đăng lại"
     * (post meta fork_retry_wanted), ScheduledDispatcher giao ngay khi kênh rảnh.
     *
     * @return array{error: ?string, queued: bool}
     */
    public function retryOrQueue(AutoVideo $video): array
    {
        $video = AutoVideo::query()->find($video->id) ?? $video;
        $post = $video->post_id !== null ? Post::query()->find($video->post_id) : null;
        $job = $post !== null ? $this->chrome->latestForPost($post) : null;
        $refusal = $this->jobRefusal($video, $post, $job);

        if ($refusal !== null) {
            return ['error' => $refusal, 'queued' => false];
        }

        try {
            $this->chrome->queueForPost($post, 'scheduled');
        } catch (ChromeRefusal $e) {
            if (! $e->busy) {
                return ['error' => $e->getMessage(), 'queued' => false];
            }

            // Ghi thẳng (không qua sự kiện model): ChromePostWatcher coi mọi lần lưu bài là "sửa bài" và thu hồi job.
            Post::query()->whereKey($post->id)->update(['meta' => json_encode([...(array) $post->meta, self::RETRY_WANTED => now()->toIso8601String()], JSON_UNESCAPED_UNICODE)]);

            return ['error' => null, 'queued' => true];
        }

        self::clearRetryWanted($post);

        return ['error' => null, 'queued' => false];
    }

    /**
     * Bài đã bấm "Đăng lại" lúc kênh bận: giao một bài cho Chrome khi kênh rảnh (ScheduledDispatcher gọi, trước bài thường).
     * Bài không còn đăng lại an toàn thì bỏ dấu. true = đã giao một job.
     */
    public function dispatchWanted(string $accountId): bool
    {
        $posts = Post::query()->where('social_account_id', $accountId)
            ->whereNotNull('meta->'.self::RETRY_WANTED)
            ->orderBy('scheduled_at')->limit(20)->get();

        foreach ($posts as $post) {
            $video = AutoVideo::query()->where('post_id', $post->id)->first();
            $refusal = $video === null ? 'no video' : $this->jobRefusal($video, $post, $this->chrome->latestForPost($post), ignoreWanted: true);

            if ($refusal !== null) {
                self::clearRetryWanted($post);

                continue;
            }

            try {
                $this->chrome->queueForPost($post, 'scheduled');
            } catch (ChromeRefusal $e) {
                if ($e->busy) {
                    return false;
                }

                self::clearRetryWanted($post);

                continue;
            }

            self::clearRetryWanted($post);

            return true;
        }

        return false;
    }

    private static function clearRetryWanted(Post $post): void
    {
        $meta = (array) $post->meta;

        if (array_key_exists(self::RETRY_WANTED, $meta)) {
            unset($meta[self::RETRY_WANTED]);
            $post->setRawAttributes(['meta' => json_encode($meta, JSON_UNESCAPED_UNICODE)] + $post->getAttributes(), true);
            Post::query()->whereKey($post->id)->update(['meta' => json_encode($meta, JSON_UNESCAPED_UNICODE)]);
        }
    }

    /**
     * Cảnh báo sớm theo dữ liệu shop app đã có (không gọi mạng): giỏ của bài đã hết hàng hoặc không còn trong shop.
     *
     * @param  Collection<int, AutoVideo>  $videos  đã nạp quan hệ `post`
     * @return array<int, string> video id => câu cảnh báo
     */
    public function cartWarnings(Collection $videos): array
    {
        $wanted = [];

        foreach ($videos as $v) {
            $pid = data_get($v->post?->meta, 'fork_shop_product_id');

            if ($v->social_account_id !== null && is_string($pid) && $pid !== '') {
                $wanted[(string) $v->social_account_id][$pid] = true;
            }
        }

        if ($wanted === []) {
            return [];
        }

        $products = ShopProduct::query()
            ->where(function ($q) use ($wanted): void {
                foreach ($wanted as $acc => $pids) {
                    $q->orWhere(fn ($w) => $w->where('social_account_id', (string) $acc)->whereIn('product_id', array_map('strval', array_keys($pids))));
                }
            })
            ->get()
            ->keyBy(fn (ShopProduct $p): string => $p->social_account_id.'|'.$p->product_id);

        // Kênh đã có dữ liệu shop: giỏ của bài không có trong đó là giỏ đã bị gỡ khỏi shop (kênh chưa lấy sản phẩm lần nào thì không đoán).
        $hasShop = ShopProduct::query()->whereIn('social_account_id', array_map('strval', array_keys($wanted)))
            ->distinct()->pluck('social_account_id')->map(fn ($id): string => (string) $id)->flip();

        $out = [];

        foreach ($videos as $v) {
            $pid = data_get($v->post?->meta, 'fork_shop_product_id');

            if (! is_string($pid) || $pid === '') {
                continue;
            }

            $p = $products[$v->social_account_id.'|'.$pid] ?? null;

            if ($p === null) {
                if (isset($hasShop[(string) $v->social_account_id])) {
                    $out[$v->id] = 'Không thấy giỏ này trong shop của kênh — lấy lại sản phẩm hoặc đổi giỏ trước giờ đăng';
                }

                continue;
            }

            if ($p->missing) {
                $out[$v->id] = 'Giỏ không còn trong shop — đổi giỏ trước giờ đăng';
            } elseif ($p->stock_num !== null && $p->stock_num <= 0) {
                $out[$v->id] = 'Giỏ hết hàng — nhập hàng hoặc đổi giỏ trước giờ đăng';
            }
        }

        return $out;
    }

    /** @return array{code: string, title: string, short: string, fix: string, text: string} */
    private function rawFailure(?string $raw): array
    {
        $raw = trim((string) $raw);
        $failure = FailureReasons::describe(null);

        if ($raw !== '') {
            $failure['title'] = mb_strimwidth($raw, 0, 160, '…');
            $failure['text'] = $failure['title'];
            $failure['code'] = 'raw';
        }

        return $failure;
    }

    private function snippet(?string $text): ?string
    {
        $text = trim((string) preg_replace('/\s+/u', ' ', (string) $text));

        return $text === '' ? null : mb_strimwidth($text, 0, 140, '…');
    }
}

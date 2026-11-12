<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Hub\HubReporter;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\VideoLibrary;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Log;
use Throwable;
use WeakMap;

/**
 * Theo dõi kết quả bài TikTok Auto Kid của video tự động.
 *
 *  - Bài Published thì markPosted (nhả file sang _da-dang);
 *  - bài Failed (hoặc bị xoá) thì video failed, KHÔNG tự về new để khỏi đăng trùng;
 *  - bài Failed nhưng job Chrome đã "posted" thì chờ: fork:chrome-dispatch sẽ sửa bài thành Published.
 *
 * Việc "ChromeJob posted" với bài hẹn giờ chỉ nghĩa TikTok đã nhận lịch, chưa đăng,
 * nên không dùng làm tín hiệu đã đăng: chỉ trạng thái bài Published mới đáng tin.
 */
final class ResultWatcher
{
    /** Chỉ xét lại video lỗi trong ngần này ngày (bài lỗi có thể được Chrome xác nhận muộn). */
    private const int RECHECK_FAILED_DAYS = 14;

    /** Thông báo hiện trên /auto khi mã hub bị tạm dừng vì lỗi giỏ hàng, theo lý do tiện ích báo. */
    private const array CART_MESSAGES = [
        'product-unavailable' => 'Sản phẩm không còn hoặc đã hết hàng trên TikTok Shop khi đăng (chưa đăng gì). Hãy lấy lại sản phẩm từ shop, chọn lại rồi lưu.',
        'anchor-build-failed' => 'Tiện ích không dựng được giỏ hàng từ mẫu (chưa đăng gì). Hãy đăng tay lại 1 bài mẫu có gắn giỏ trong TikTok Studio, rồi lưu lại liên kết.',
    ];

    /** @var WeakMap<object, true>|null */
    private static ?WeakMap $registered = null;

    /** Đăng ký lắng nghe khi bài đổi trạng thái (gọi từ provider); chạy lại nhiều lần vẫn chỉ đăng ký một lần. */
    public static function register(): void
    {
        $events = Event::getFacadeRoot();

        if (! is_object($events)) {
            return;
        }

        self::$registered ??= new WeakMap;

        if (isset(self::$registered[$events])) {
            return;
        }

        self::$registered[$events] = true;

        $events->listen('eloquent.updated: '.Post::class, function (Post $post): void {
            if (! $post->wasChanged('status')) {
                return;
            }

            try {
                (new self)->syncPost($post);
            } catch (Throwable $e) {
                report($e);
            }
        });
    }

    /**
     * Đối soát mọi video đang chờ kết quả.
     *
     * @return array{posted: int, failed: int}
     */
    public function sync(): array
    {
        $count = ['posted' => 0, 'failed' => 0];

        AutoVideo::query()
            ->where(fn ($q) => $q
                ->where('status', 'scheduled')
                ->orWhere(fn ($f) => $f->where('status', 'failed')
                    ->whereNotNull('post_id')
                    ->where('updated_at', '>=', now()->subDays(self::RECHECK_FAILED_DAYS))))
            ->whereNotNull('post_id')
            ->orderBy('id')
            ->each(function (AutoVideo $video) use (&$count): void {
                try {
                    $result = $this->syncVideo($video, Post::query()->find($video->post_id));
                } catch (Throwable $e) {
                    report($e);

                    return;
                }

                if ($result !== null) {
                    $count[$result]++;
                }
            });

        return $count;
    }

    /** Dùng cho listener: chỉ đối soát video của đúng bài này. */
    public function syncPost(Post $post): void
    {
        AutoVideo::query()
            ->where('post_id', $post->id)
            ->whereIn('status', ['scheduled', 'failed'])
            ->each(fn (AutoVideo $video) => $this->syncVideo($video, $post));
    }

    /**
     * @return 'posted'|'failed'|null
     */
    private function syncVideo(AutoVideo $video, ?Post $post): ?string
    {
        if ($video->status === 'scheduled' && $post === null) {
            return $this->fail($video, 'Bài TikTok Auto Kid đã bị xoá trước khi đăng.');
        }

        if ($post === null) {
            return null;
        }

        if ($post->status === PostStatus::Published) {
            return $this->posted($video, $post);
        }

        if ($video->status === 'scheduled' && $post->status === PostStatus::Failed) {
            if (ChromeJob::query()->where('post_id', $post->id)->where('state', 'posted')->exists()) {
                return null; // chờ fork:chrome-dispatch sửa bài thành Published
            }

            // K4: Chrome chặn vì giỏ hàng (chắc chắn chưa đăng) thì video về kho, mã hub bị tạm dừng trên kênh.
            $cartReason = $this->cartFailureReason($post);

            if ($cartReason === CartRules::RETRY_REASON) {
                return $this->requeueForRetry($video);
            }

            if ($cartReason !== null) {
                return $this->requeueForCart($video, $cartReason);
            }

            return $this->fail($video, mb_substr((string) ($post->error_message ?: 'Đăng bài thất bại.'), 0, 500));
        }

        return null;
    }

    /** Lý do giỏ hàng (product-unavailable, ...) của job Chrome thất bại gần nhất của bài, hoặc null. */
    private function cartFailureReason(Post $post): ?string
    {
        $job = ChromeJob::query()->where('post_id', $post->id)->orderByDesc('attempt')->first();

        if ($job === null || $job->state !== 'failed') {
            return null;
        }

        $reason = is_array($job->result) ? ($job->result['reason'] ?? null) : null;

        return is_string($reason) && in_array($reason, [...CartRules::FAIL_REASONS, CartRules::RETRY_REASON], true) ? $reason : null;
    }

    /** Không đọc được API shop: video về kho để đăng lại sau, không tạm dừng liên kết. */
    private function requeueForRetry(AutoVideo $video): string
    {
        $video->forceFill([
            'status' => AutoVideo::NEW,
            'social_account_id' => null,
            'post_id' => null,
            'scheduled_for' => null,
            'skip_reason' => null,
        ])->save();

        app(HubReporter::class)->released($video);

        Log::warning('Tự động đăng: tiện ích không đọc được API sản phẩm TikTok Shop (chưa gửi gì), video về kho để thử lại sau.', ['video_id' => $video->id]);

        return 'failed';
    }

    private function requeueForCart(AutoVideo $video, string $reason): string
    {
        $message = self::CART_MESSAGES[$reason];

        DB::transaction(function () use ($video, $message): void {
            if ($video->product_code !== null && $video->social_account_id !== null) {
                ProductLink::slot((string) $video->social_account_id, (string) $video->product_code, $video->quy_cach)
                    ->update(['paused_reason' => $message, 'updated_at' => now()]);
            }

            // Chưa đăng chắc chắn nên video quay về kho như video chưa từng được xếp.
            $video->forceFill([
                'status' => AutoVideo::NEW,
                'social_account_id' => null,
                'post_id' => null,
                'scheduled_for' => null,
                'skip_reason' => null,
            ])->save();
        });

        app(HubReporter::class)->failed($video, 'Giỏ hàng TikTok Shop bị chặn: '.$reason.' (chưa đăng gì)');

        Log::warning('Tự động đăng: Chrome chặn vì giỏ hàng, video về kho và mã hub bị tạm dừng trên kênh.', ['video_id' => $video->id, 'reason' => $reason]);

        return 'failed';
    }

    private function posted(AutoVideo $video, Post $post): ?string
    {
        // Bài hẹn giờ native trên TikTok: giờ đăng thật là giờ hẹn. Máy có thể tắt lúc đó và TikTok Auto Kid chỉ ghi nhận khi bật lại,
        // nên không dùng giờ ghi nhận làm giờ đăng (số liệu 24h/72h tính theo posted_at).
        if ($video->posted_at === null && $video->scheduled_for !== null && $video->scheduled_for->isPast()
            && ChromeJob::query()->where('post_id', $post->id)->where('mode', 'scheduled')->where('state', 'posted')->exists()) {
            $video->forceFill(['posted_at' => $video->scheduled_for])->save();
        }

        $platformId = (string) $post->platform_post_id;
        $tiktokId = $platformId !== '' && ctype_digit($platformId) ? $platformId : null;

        try {
            app(VideoLibrary::class)->markPosted($video, $tiktokId);
        } catch (Throwable $e) {
            Log::error('Tự động đăng: markPosted lỗi, sẽ thử lại lượt sau.', ['video_id' => $video->id, 'error' => $e->getMessage()]);

            return null;
        }

        $video->refresh();

        if ($video->posted_at === null) {
            $video->forceFill(['posted_at' => $post->published_at ?? now()])->save();
        }

        return 'posted';
    }

    private function fail(AutoVideo $video, string $reason): string
    {
        if ($video->status === 'scheduled') {
            $video->forceFill(['status' => 'failed', 'skip_reason' => $reason])->save();
            app(HubReporter::class)->failed($video, $reason);
        }

        return 'failed';
    }
}

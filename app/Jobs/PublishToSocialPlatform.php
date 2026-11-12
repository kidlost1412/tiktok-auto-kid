<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Actions\Post\FinalizePostPublication;
use App\Enums\Post\PublishStatus;
use App\Enums\SocialAccount\Status;
use App\Exceptions\PlatformUnavailableException;
use App\Exceptions\Social\ErrorCategory;
use App\Exceptions\Social\TikTokPublishException;
use App\Fork\Chrome\Publishing\ChromeAwareTikTokPublisher;
use App\Models\Post;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Queue\Middleware\WithoutOverlapping;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\Log;
use Throwable;

/** Đăng một bài TikTok: giao cho Chrome (ChromeAwareTikTokPublisher) và ghi kết quả; chưa xong thì hẹn thử lại. */
class PublishToSocialPlatform implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $tries = 20;

    public int $maxExceptions = 1;

    public int $timeout = 900;

    public int $uniqueFor = 960;

    /** Số lần thử lại mặc định khi chưa đăng được (mỗi lần 10 phút, khoảng 1 giờ). */
    public const MAX_PLATFORM_UNAVAILABLE_RETRIES = 6;

    private const int DEFAULT_RETRY_DELAY_SECONDS = 600;

    public function __construct(
        public Post $post,
        public int $uniqueAttempt = 0,
    ) {
        $this->onQueue('social-tiktok');
    }

    public function uniqueId(): string
    {
        return "{$this->post->id}:{$this->uniqueAttempt}";
    }

    /**
     * @return array<int, object>
     */
    public function middleware(): array
    {
        return [
            (new WithoutOverlapping("social-publish:{$this->post->id}"))
                ->releaseAfter(60)
                ->expireAfter($this->timeout + 60),
        ];
    }

    public function handle(): void
    {
        $this->post->refresh();

        if ($this->post->publish_status->isClosed()) {
            return;
        }

        if ($this->post->socialAccount->status !== Status::Connected) {
            $this->failAndFinalize('Tài khoản TikTok đang ngắt kết nối.');

            return;
        }

        $this->post->markPublicationPublishing();

        try {
            $result = app(ChromeAwareTikTokPublisher::class)->publish($this->post);

            $this->post->markPublicationPublished((string) data_get($result, 'id'), data_get($result, 'url'));
        } catch (PlatformUnavailableException $e) {
            $this->rescheduleForRetry($e);
        } catch (TikTokPublishException $e) {
            $this->reportCaughtPublishFailure($e);
            $this->markPlatformAsFailed($e->userMessage, $this->failureContext([
                'category' => $e->category->value,
                'platform_error_code' => $e->platformErrorCode,
                'raw_response' => $e->context()['raw_response'],
            ]));
        } catch (Throwable $e) {
            $this->reportCaughtPublishFailure($e);
            $this->markPlatformAsFailed('Lỗi không mong muốn khi đăng bài. Hãy thử lại.', $this->failureContext([
                'category' => ErrorCategory::Unknown->value,
            ]));
        }

        $this->updatePostStatus();
    }

    private function rescheduleForRetry(PlatformUnavailableException $e): void
    {
        $previousContext = $this->post->error_context ?? [];
        $hasOwnPolicy = $e->maxRetries !== null || $e->retryDelaySeconds !== null;
        $counterKey = $hasOwnPolicy ? 'processing_retry_count' : 'retry_count';
        $retryCount = (int) data_get($previousContext, $counterKey, 0) + 1;
        $maxRetries = $e->maxRetries ?? self::MAX_PLATFORM_UNAVAILABLE_RETRIES;
        $retryDelaySeconds = $e->retryDelaySeconds ?? self::DEFAULT_RETRY_DELAY_SECONDS;
        $context = [
            ...Arr::except($previousContext, ['max_retries', 'retry_delay_seconds']),
            ...$e->context,
            'category' => ErrorCategory::PlatformUnavailable->value,
            'http_status' => $e->httpStatus,
            $counterKey => $retryCount,
            ...($hasOwnPolicy ? ['max_retries' => $maxRetries, 'retry_delay_seconds' => $retryDelaySeconds] : []),
            'detail' => $e->getMessage(),
        ];

        if ($retryCount > $maxRetries) {
            $this->reportCaughtPublishFailure($e, [
                'retry_count' => $retryCount,
                'max_retries' => $maxRetries,
            ]);

            $this->markPlatformAsFailed(
                'Chrome chưa đăng được bài sau nhiều lần thử.',
                [...$context, 'failed_at' => now()->toIso8601String()],
            );

            return;
        }

        $nextAttemptAt = now()->addSeconds($retryDelaySeconds);

        Log::warning('Publish rescheduled: platform unavailable', [
            'post_id' => $this->post->id,
            'next_attempt_at' => $nextAttemptAt->toIso8601String(),
            ...$context,
        ]);

        $this->post->writePublication([
            'publish_status' => PublishStatus::Retrying,
            'error_message' => 'Đang chờ Chrome đăng bài.',
            'error_context' => [
                ...$context,
                'last_attempt_at' => now()->toIso8601String(),
                'next_attempt_at' => $nextAttemptAt->toIso8601String(),
            ],
        ]);

        self::dispatch(
            $this->post,
            (int) data_get($context, 'retry_count', 0) + (int) data_get($context, 'processing_retry_count', 0),
        )->delay($nextAttemptAt);
    }

    /**
     * @param  array<string, mixed>  $context
     */
    private function reportCaughtPublishFailure(Throwable $e, array $context = []): void
    {
        Log::error('Social publish failed', [
            ...($e instanceof TikTokPublishException ? $e->context() : []),
            'post_id' => $this->post->id,
            'exception' => $e::class,
            'message' => $e->getMessage(),
            ...$context,
        ]);

        if ($e instanceof TikTokPublishException && $e->isNetworkRejection()) {
            return;
        }

        report($e);
    }

    /**
     * @param  array<string, mixed>|null  $context
     */
    private function markPlatformAsFailed(string $message, ?array $context = null): void
    {
        $failureContext = [...($this->post->error_context ?? []), ...($context ?? [])];

        $this->post->markPublicationFailed($message, $failureContext === [] ? null : $failureContext);
    }

    /**
     * @param  array<string, mixed>  $extra
     * @return array<string, mixed>
     */
    private function failureContext(array $extra = []): array
    {
        return [
            ...$extra,
            'failed_at' => now()->toIso8601String(),
            'content_length' => mb_strlen($this->post->content ?? ''),
            'media_count' => count($this->post->media ?? []),
        ];
    }

    /**
     * @param  array<string, mixed>|null  $context
     */
    private function failAndFinalize(string $message, ?array $context = null): void
    {
        $this->markPlatformAsFailed($message, $context);
        $this->updatePostStatus();
    }

    private function updatePostStatus(): void
    {
        app(FinalizePostPublication::class)->handle($this->post);
    }

    public function failed(?Throwable $exception): void
    {
        Log::error('PublishToSocialPlatform job failed permanently', [
            'post_id' => $this->post->id,
            'error' => $exception?->getMessage(),
        ]);

        $this->post->refresh();

        if ($this->post->publish_status->isClosed()) {
            return;
        }

        $this->failAndFinalize('Lỗi không mong muốn khi đăng bài. Hãy thử lại.', [
            'category' => ErrorCategory::JobFailed->value,
            'failed_at' => now()->toIso8601String(),
        ]);
    }
}

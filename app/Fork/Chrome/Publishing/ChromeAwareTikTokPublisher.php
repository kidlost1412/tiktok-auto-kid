<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Publishing;

use App\Exceptions\PlatformUnavailableException;
use App\Exceptions\Social\ErrorCategory;
use App\Exceptions\Social\TikTokPublishException;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeRefusal;
use App\Models\Post;
use App\Models\SocialAccount;

/**
 * Bài TikTok được giao cho tiện ích Chrome (TikTok Auto Kid) thành một job; publisher chỉ đọc kết quả của job.
 * Không có đường đăng qua API TikTok.
 */
class ChromeAwareTikTokPublisher
{
    /** Chờ Chrome: 60 giây một lần, tối đa 420 lần (7 giờ, hơn hạn nhận 6 giờ của job đăng ngay). */
    public const int WAIT_RETRY_SECONDS = 60;

    public const int WAIT_MAX_RETRIES = 420;

    public function publish(Post $post): array
    {
        $chrome = app(ChromeJobs::class);
        $account = $post->socialAccount;
        $enabled = $account !== null && $chrome->isChromeAccount($account);
        $job = $chrome->latestForPost($post);

        // Bài chưa từng giao cho Chrome.
        if ($job === null) {
            if (! $enabled) {
                throw new TikTokPublishException(
                    userMessage: 'Tài khoản này chưa bật đăng qua Chrome.',
                    category: ErrorCategory::ContentPolicy,
                );
            }

            throw $this->waiting($this->queueNow($chrome, $post));
        }

        // Từ đây bài đã có job Chrome.
        if (! $enabled && $this->surelyNotSent($job)) {
            throw new TikTokPublishException(
                userMessage: 'Tài khoản đã tắt đăng qua Chrome; bài này từng được giao cho Chrome — hãy tạo lại bài.',
                category: ErrorCategory::ContentPolicy,
            );
        }

        if ($enabled && $this->mayQueueAgain($job)) {
            throw $this->waiting($this->queueNow($chrome, $post));
        }

        return match ($job->state) {
            'queued', 'claimed', 'uploading', 'ready', 'authorized' => throw $this->waiting($job),
            'posted' => $this->published($chrome, $post, $job),
            'uncertain' => throw $this->uncertain($chrome, $job),
            default => throw $this->refused($chrome, $job),
        };
    }

    public static function postUrl(SocialAccount $account, ?string $postId = null): ?string
    {
        $username = $account->username;

        if ($username && $postId) {
            return "https://www.tiktok.com/@{$username}/video/{$postId}";
        }

        return $username ? "https://www.tiktok.com/@{$username}" : null;
    }

    /**
     * Job chắc chắn chưa gửi gì lên TikTok và không do người dùng huỷ:
     * revoked (hết hạn nhận, đứng im, quá dài, claim mồ côi, bài được sửa) hoặc
     * failed với not_sent / chưa authorize. Huỷ, rejected, uncertain, posted, authorized thì không.
     */
    private function surelyNotSent(ChromeJob $job): bool
    {
        if ($job->cancel_requested) {
            return false;
        }

        if ($job->state === 'revoked') {
            return ! str_starts_with((string) $job->note, ChromeJobs::CANCEL_TEXT);
        }

        if ($job->state === 'failed') {
            return data_get($job->result, 'not_sent') === true || $job->authorized_at === null;
        }

        return false;
    }

    /**
     * Được tạo attempt mới với mọi thất bại chắc chắn chưa gửi. Số lần thử tối đa
     * (ChromeJobs::MAX_ATTEMPTS) do queueForPost chặn bằng ChromeRefusal.
     */
    private function mayQueueAgain(ChromeJob $job): bool
    {
        return $this->surelyNotSent($job);
    }

    private function queueNow(ChromeJobs $chrome, Post $post): ChromeJob
    {
        try {
            return $chrome->queueForPost($post, 'now');
        } catch (ChromeRefusal $refusal) {
            // Tài khoản đang có job mở của bài khác: chờ, không fail.
            if (property_exists($refusal, 'busy') && isset($refusal->busy) && $refusal->busy) {
                throw new PlatformUnavailableException(
                    message: 'Đang chờ Chrome đăng bài lên TikTok.',
                    context: ['chrome_busy' => true],
                    retryDelaySeconds: self::WAIT_RETRY_SECONDS,
                    maxRetries: self::WAIT_MAX_RETRIES,
                );
            }

            throw (new TikTokPublishException(
                userMessage: $refusal->getMessage(),
                category: ErrorCategory::ContentPolicy,
            ))->asNetworkRejection();
        }
    }

    private function waiting(ChromeJob $job): PlatformUnavailableException
    {
        return new PlatformUnavailableException(
            message: 'Đang chờ Chrome đăng bài lên TikTok.',
            context: ['chrome_job_id' => $job->id, 'chrome_job_state' => $job->state],
            retryDelaySeconds: self::WAIT_RETRY_SECONDS,
            maxRetries: self::WAIT_MAX_RETRIES,
        );
    }

    /**
     * @return array{id: string, url: ?string}
     */
    private function published(ChromeJobs $chrome, Post $post, ChromeJob $job): array
    {
        $videoId = $chrome->outcome($job)->videoId;

        return [
            'id' => $videoId ?? $job->id,
            'url' => self::postUrl($post->socialAccount, $videoId),
        ];
    }

    /**
     * Không bao giờ đăng lại: kết quả không rõ thì chỉ người dùng mới biết bài đã lên chưa.
     */
    private function uncertain(ChromeJobs $chrome, ChromeJob $job): TikTokPublishException
    {
        return new TikTokPublishException(
            userMessage: $chrome->outcome($job)->message,
            category: ErrorCategory::Unknown,
        );
    }

    private function refused(ChromeJobs $chrome, ChromeJob $job): TikTokPublishException
    {
        return (new TikTokPublishException(
            userMessage: $chrome->outcome($job)->message,
            category: ErrorCategory::ContentPolicy,
        ))->asNetworkRejection();
    }
}

<?php

declare(strict_types=1);

namespace App\Exceptions\Social;

use Carbon\CarbonInterface;
use RuntimeException;

/** Bài TikTok không đăng được (do Chrome từ chối, lỗi không rõ...). `userMessage` hiển thị cho chủ app. */
class TikTokPublishException extends RuntimeException
{
    public ?CarbonInterface $retryAt = null;

    private bool $rejectedByNetwork = false;

    public function __construct(
        public readonly string $userMessage,
        public readonly ErrorCategory $category,
        public readonly ?string $platformErrorCode = null,
        public readonly ?string $rawResponse = null,
    ) {
        parent::__construct($userMessage);
    }

    /**
     * @return array{platform: string, category: string, platform_error_code: ?string, user_message: string, raw_response: ?string}
     */
    public function context(): array
    {
        return [
            'platform' => 'tiktok',
            'category' => $this->category->value,
            'platform_error_code' => $this->platformErrorCode,
            'user_message' => $this->userMessage,
            'raw_response' => $this->rawResponse,
        ];
    }

    public function isLimit(): bool
    {
        return $this->category === ErrorCategory::RateLimit;
    }

    /** Lỗi do nội dung/tài khoản của chủ app, chỉ chủ app sửa được (không báo như lỗi của hệ thống). */
    public function asNetworkRejection(): static
    {
        $this->rejectedByNetwork = $this->category->needsUserAction();

        return $this;
    }

    public function isNetworkRejection(): bool
    {
        return $this->rejectedByNetwork;
    }
}

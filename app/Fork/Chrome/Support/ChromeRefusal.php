<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Support;

use RuntimeException;

/**
 * Bài không thể giao cho Chrome. Message là tiếng Việt, chắc chắn chưa đăng gì.
 * busy = true: tài khoản đang có job mở của bài khác, nên chờ chứ không fail.
 */
final class ChromeRefusal extends RuntimeException
{
    public function __construct(string $message = '', public readonly bool $busy = false)
    {
        parent::__construct($message);
    }
}

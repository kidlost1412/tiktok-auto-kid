<?php

declare(strict_types=1);

namespace App\Enums\Post;

enum Status: string
{
    case Draft = 'draft';
    case PendingApproval = 'pending_approval';
    case Scheduled = 'scheduled';
    case Publishing = 'publishing';
    case Published = 'published';
    case Failed = 'failed';

    /** Đã đăng hoặc đã lỗi: bài đã chốt, không xử lý lại. */
    public function isSettled(): bool
    {
        return match ($this) {
            self::Published, self::Failed => true,
            default => false,
        };
    }
}

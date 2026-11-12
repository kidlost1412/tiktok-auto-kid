<?php

declare(strict_types=1);

namespace App\Enums\SocialAccount;

/** Chỉ TikTok: app đăng video qua tiện ích Chrome (TikTok Auto Kid). */
enum Platform: string
{
    case TikTok = 'tiktok';

    public function label(): string
    {
        return 'TikTok';
    }
}

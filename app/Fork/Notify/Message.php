<?php

declare(strict_types=1);

namespace App\Fork\Notify;

/** Một tin Telegram đã dựng: loại, khoá chống trùng, dòng đầu (để gộp nhóm) và nội dung HTML. */
final readonly class Message
{
    public function __construct(
        public string $type,
        public string $key,
        public string $headline,
        public string $text,
        public int $ttl = 604800,
    ) {}
}

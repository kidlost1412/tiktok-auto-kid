<?php

declare(strict_types=1);

namespace App\Fork\Notify;

/**
 * Một tin Telegram đã dựng: loại, khoá chống trùng, dòng đầu (để gộp nhóm) và nội dung HTML.
 * `data` là số liệu thô của tin (để dựng tin gộp riêng cho từng loại, vd. nhiều bài không đăng được).
 */
final readonly class Message
{
    /** @param  array<string, mixed>  $data */
    public function __construct(
        public string $type,
        public string $key,
        public string $headline,
        public string $text,
        public int $ttl = 604800,
        public array $data = [],
    ) {}
}

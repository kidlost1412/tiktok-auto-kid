<?php

declare(strict_types=1);

namespace App\Enums\Media;

use Illuminate\Support\Str;

enum Type: string
{
    case Image = 'image';
    case Video = 'video';
    case Document = 'document';

    /** Phân loại theo MIME (image/*, video/*, application/pdf), không có MIME thì theo đuôi file. */
    public static function classify(?string $mimeType, ?string $path = null): ?self
    {
        $mime = Str::lower(trim((string) $mimeType));

        if ($mime === '') {
            return match (Str::lower(pathinfo((string) $path, PATHINFO_EXTENSION))) {
                'mp4', 'mov', 'webm', 'mkv', 'avi' => self::Video,
                'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic' => self::Image,
                'pdf' => self::Document,
                default => null,
            };
        }

        return match (true) {
            Str::startsWith($mime, 'video/') => self::Video,
            Str::startsWith($mime, 'image/') => self::Image,
            $mime === 'application/pdf' => self::Document,
            default => null,
        };
    }
}

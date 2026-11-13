<?php

declare(strict_types=1);

namespace App\Fork\AutoPost;

/**
 * File đi kèm mp4 của hub (json, jpg, txt, bang-ghi*.csv, so-lieu.csv). Hub đang chuyển chúng từ ra/<ngày>/ sang
 * ra/<ngày>/_kem/: luôn tìm trong _kem/ trước, không có mới tìm chỗ cũ. Đường dẫn mp4 không đổi.
 */
final class Sidecar
{
    public const DIR = '_kem';

    /** Đường dẫn file đi kèm đang có thật (_kem trước, chỗ cũ sau), null nếu không có. */
    public static function find(string $dir, string $name): ?string
    {
        $dir = rtrim(Paths::slash($dir), '/');

        foreach ([$dir.'/'.self::DIR.'/'.$name, $dir.'/'.$name] as $candidate) {
            if (is_file($candidate)) {
                return $candidate;
            }
        }

        return null;
    }

    /** Như find() nhưng luôn trả một đường dẫn: file đang có, hoặc chỗ cũ (để đọc báo "không có" / ghi mới). */
    public static function path(string $dir, string $name): string
    {
        return self::find($dir, $name) ?? rtrim(Paths::slash($dir), '/').'/'.$name;
    }

    /** File đi kèm của một mp4 (cùng tên, đổi đuôi). */
    public static function forVideo(string $videoPath, string $extension): ?string
    {
        $videoPath = Paths::slash($videoPath);

        return self::find(dirname($videoPath), pathinfo($videoPath, PATHINFO_FILENAME).'.'.ltrim($extension, '.'));
    }
}

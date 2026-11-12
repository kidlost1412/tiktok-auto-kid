<?php

declare(strict_types=1);

namespace App\Fork\AutoPost;

/**
 * Đường dẫn file của kho video, chạy trên Windows.
 *
 * Quy ước: mọi đường dẫn lưu trong DB và so sánh trong code đều dùng '/' (Windows chấp nhận '/'),
 * để `dirname()`, `where path = ...` và `like 'dir/%'` không lệch vì '\' lẫn '/'.
 */
final class Paths
{
    /** Đổi '\' thành '/'. Tên file Linux không có '\' hợp lệ trong kho nên an toàn. */
    public static function slash(string $path): string
    {
        return str_replace('\\', '/', $path);
    }

    /** `glob()` nhưng trả đường dẫn đã chuẩn hoá '/' (Windows trộn '\' và '/'). Tên file UTF-8 giữ nguyên. */
    public static function glob(string $pattern): array
    {
        return array_map(self::slash(...), glob($pattern) ?: []);
    }

    /** Đường dẫn gốc thư mục hub, chuẩn hoá '/', không có '/' cuối. */
    public static function root(string $configured): string
    {
        return rtrim(self::slash($configured), '/');
    }

    /** `$file` có nằm dưới thư mục `$root` không (cả hai đã qua realpath; Windows không phân biệt hoa thường). */
    public static function isUnder(string $file, string $root): bool
    {
        $file = self::slash($file);
        $root = rtrim(self::slash($root), '/').'/';

        if (DIRECTORY_SEPARATOR === '\\') {
            return str_starts_with(mb_strtolower($file), mb_strtolower($root));
        }

        return str_starts_with($file, $root);
    }
}

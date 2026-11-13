<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Shop;

use Illuminate\Support\Str;

/**
 * Đặt tên/mã sản phẩm hub từ tên sản phẩm TikTok Shop khi chủ app bấm "+ Thêm sản phẩm".
 * Tên chỉ là gợi ý (chủ app sửa được); mã là chữ thường/số/gạch ngang, đúng luật mã của hub.
 */
final class ProductNaming
{
    public const int SHORT_MAX = 40;

    public const int FULL_MAX = 120;

    public const int CODE_MAX = 30;

    /** Bỏ các cụm [LIVESTREAM], (HOT)... ở đầu và khoảng trắng thừa. */
    public static function clean(string $title): string
    {
        $t = (string) preg_replace('/\[[^\]]*\]|\((?:livestream|hot|sale|new)[^)]*\)/iu', ' ', $title);
        $t = trim((string) preg_replace('/\s+/u', ' ', $t));

        return $t !== '' ? $t : trim((string) preg_replace('/\s+/u', ' ', $title));
    }

    /** Tên gọi ngắn (hub đọc trong video, hiện ở thẻ): vài từ đầu của tên sản phẩm, tối đa 40 ký tự. */
    public static function shortName(string $title): string
    {
        $words = preg_split('/\s+/u', self::clean($title), -1, PREG_SPLIT_NO_EMPTY) ?: [];
        $out = '';

        foreach (array_slice($words, 0, 4) as $w) {
            $next = $out === '' ? $w : $out.' '.$w;

            if (mb_strlen($next) > self::SHORT_MAX) {
                break;
            }

            $out = $next;
        }

        return $out !== '' ? $out : 'Sản phẩm mới';
    }

    /** Tên đầy đủ (ten_goi của hub). */
    public static function fullName(string $title): string
    {
        $clean = self::clean($title);

        if (mb_strlen($clean) <= self::FULL_MAX) {
            return $clean !== '' ? $clean : 'Sản phẩm mới';
        }

        $cut = mb_substr($clean, 0, self::FULL_MAX);
        $space = mb_strrpos($cut, ' ');

        return rtrim($space !== false && $space > 20 ? mb_substr($cut, 0, $space) : $cut);
    }

    /**
     * Mã hub từ tên gọi ngắn, không trùng mã đã có.
     *
     * @param  callable(string): bool  $taken  true nếu mã đã dùng
     */
    public static function code(string $shortName, callable $taken): string
    {
        $base = trim(mb_substr(Str::slug($shortName), 0, self::CODE_MAX), '-');
        $base = $base !== '' ? $base : 'san-pham';
        $code = $base;

        for ($i = 2; $taken($code); $i++) {
            $suffix = '-'.$i;
            $code = rtrim(mb_substr($base, 0, self::CODE_MAX - strlen($suffix)), '-').$suffix;
        }

        return $code;
    }

    /** Mã hub hợp lệ (cùng luật với hub: chữ thường, số, gạch ngang). */
    public static function validCode(string $code): bool
    {
        return preg_match('/^[a-z0-9-]{1,40}$/', $code) === 1;
    }
}

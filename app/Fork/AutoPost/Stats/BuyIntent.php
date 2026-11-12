<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Stats;

/**
 * Nhận ra bình luận "hỏi mua / hỏi giá" bằng từ khoá tiếng Việt đơn giản (giá, bao nhiêu, mua, ship, còn hàng, inbox, sđt/zalo...).
 * Hai lớp: (1) chữ có dấu, khớp nguyên từ, cho các từ dễ nhầm khi bỏ dấu (mua/mùa, giá/gia); (2) chữ đã bỏ dấu, chỉ cho các cụm
 * đủ rõ nghĩa, để bắt người gõ không dấu ("gia bao nhieu", "con hang ko").
 */
final class BuyIntent
{
    /** Khớp trên chữ thường, có dấu, nguyên từ. */
    private const array ACCENTED = [
        'giá', 'báo giá', 'xin giá', 'hỏi giá', 'bao nhiêu', 'bn', 'mua', 'muốn mua', 'đặt hàng', 'đặt', 'order', 'ship', 'freeship', 'còn hàng', 'hết hàng',
        'còn không', 'còn ko', 'còn k', 'inbox', 'ib', 'sđt', 'sdt', 'số điện thoại', 'zalo', 'xin link', 'link mua', 'cod', 'chốt đơn', 'chốt',
    ];

    /** Khớp trên chữ đã bỏ dấu và chữ thường. */
    private const array STRIPPED = [
        'bao nhieu', 'bao gia', 'xin gia', 'hoi gia', 'gia bn', 'gia bao', 'gia sao', 'gia nhieu', 'gia the nao', 'gia ntn', 'gia ban',
        'mua o dau', 'mua dau', 'muon mua', 'mua sao', 'mua ntn', 'cach mua', 'dat hang', 'con hang', 'het hang', 'ship', 'freeship',
        'inbox', 'sdt', 'zalo', 'xin link', 'link mua', 'cod', 'chot don', 'bn tien', 'check ib',
    ];

    /**
     * @return array{buy: bool, keywords: list<string>}
     */
    public static function detect(string $text): array
    {
        $nfc = \Normalizer::normalize($text, \Normalizer::FORM_C);
        $lower = mb_strtolower($nfc === false ? $text : $nfc);
        $found = [];

        foreach (self::ACCENTED as $kw) {
            if (self::contains($lower, $kw)) {
                $found[$kw] = true;
            }
        }

        $stripped = self::strip($lower);

        foreach (self::STRIPPED as $kw) {
            if (self::contains($stripped, $kw)) {
                $found[$kw] = true;
            }
        }

        return ['buy' => $found !== [], 'keywords' => array_slice(array_keys($found), 0, 6)];
    }

    /** Bỏ dấu tiếng Việt (đ → d). */
    public static function strip(string $text): string
    {
        $map = ['đ' => 'd', 'Đ' => 'd'];
        $text = strtr($text, $map);
        $decomposed = \Normalizer::normalize($text, \Normalizer::FORM_D);

        return mb_strtolower(preg_replace('/\p{Mn}+/u', '', $decomposed === false ? $text : $decomposed) ?? $text);
    }

    private static function contains(string $haystack, string $keyword): bool
    {
        // Nguyên từ: trước và sau không phải chữ hoặc số. "ship" khớp "ship ko?" nhưng không khớp "relationship".
        return preg_match('/(?<![\p{L}\p{N}])'.preg_quote($keyword, '/').'(?![\p{L}\p{N}])/u', $haystack) === 1;
    }
}

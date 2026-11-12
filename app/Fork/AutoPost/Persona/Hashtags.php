<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Persona;

use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoSetting;

/**
 * Hashtag riêng của từng sản phẩm (và mặc định chung), áp vào caption lúc dựng bài (PostBuilder).
 * Không có hashtag riêng thì dùng mặc định chung; cả hai trống thì giữ nguyên chữ hub viết.
 * Giới hạn 2200 ký tự của TikTok luôn được giữ: thiếu chỗ thì bỏ bớt hashtag thêm vào, không cắt caption.
 */
final class Hashtags
{
    public const string APPEND = 'append';

    public const string REPLACE = 'replace';

    public const int MAX_TAGS = 50;

    public const int MAX_TAG_LENGTH = 100;

    private const string TAG_IN_TEXT = '/(?<![\p{L}\p{N}_#&\/])#([\p{L}\p{N}_]+)/u';

    /** @return list<string> các hashtag hợp lệ (có # đứng đầu), không trùng (không phân biệt hoa thường). */
    public static function normalize(mixed $raw): array
    {
        $parts = is_array($raw) ? $raw : (is_string($raw) ? [$raw] : []);
        $out = [];
        $seen = [];

        foreach ($parts as $part) {
            if (! is_string($part)) {
                continue;
            }

            foreach (preg_split('/[\s,;]+/u', $part, -1, PREG_SPLIT_NO_EMPTY) ?: [] as $word) {
                $word = preg_replace('/[^\p{L}\p{N}_]+/u', '', ltrim($word, '#')) ?? '';

                if ($word === '' || mb_strlen($word) > self::MAX_TAG_LENGTH - 1) {
                    continue;
                }

                $key = mb_strtolower($word);

                if (isset($seen[$key])) {
                    continue;
                }

                $seen[$key] = true;
                $out[] = '#'.$word;

                if (count($out) >= self::MAX_TAGS) {
                    break 2;
                }
            }
        }

        return $out;
    }

    public static function normalizeMode(mixed $mode): string
    {
        return $mode === self::REPLACE ? self::REPLACE : self::APPEND;
    }

    /** @return array{tags: list<string>, mode: string, pick: int, source: string} source: product | default | none */
    public function configFor(?AutoProduct $product): array
    {
        $own = self::normalize($product?->hashtags);

        if ($own !== []) {
            return ['tags' => $own, 'mode' => self::normalizeMode($product->hashtag_mode), 'pick' => max(0, (int) $product->hashtag_pick), 'source' => 'product'];
        }

        $default = self::defaults();

        return $default['tags'] === []
            ? ['tags' => [], 'mode' => self::APPEND, 'pick' => 0, 'source' => 'none']
            : $default + ['source' => 'default'];
    }

    /** @return array{tags: list<string>, mode: string, pick: int} */
    public static function defaults(): array
    {
        $decoded = json_decode((string) AutoSetting::read('persona.hashtags', '[]'), true);

        return [
            'tags' => self::normalize(is_array($decoded) ? $decoded : []),
            'mode' => self::normalizeMode(AutoSetting::read('persona.hashtag_mode')),
            'pick' => max(0, (int) AutoSetting::read('persona.hashtag_pick', '0')),
        ];
    }

    /** @param  list<string>|string  $tags */
    public static function saveDefaults(array|string $tags, string $mode, int $pick): void
    {
        AutoSetting::write('persona.hashtags', json_encode(self::normalize($tags), JSON_UNESCAPED_UNICODE));
        AutoSetting::write('persona.hashtag_mode', self::normalizeMode($mode));
        AutoSetting::write('persona.hashtag_pick', (string) max(0, $pick));
    }

    /**
     * @param  list<string>  $hubTags  hashtag hub viết riêng (ngoài caption)
     * @return array{caption: string, hashtags: list<string>}
     */
    public function apply(string $caption, array $hubTags, ?AutoProduct $product): array
    {
        $caption = trim($caption);
        $cfg = $this->configFor($product);

        if ($cfg['tags'] === []) {
            return ['caption' => $caption, 'hashtags' => array_values($hubTags)];
        }

        $base = array_values($hubTags);

        if ($cfg['mode'] === self::REPLACE) {
            $stripped = self::stripTags($caption);

            // Caption chỉ toàn hashtag thì giữ nguyên (TikTok/ứng dụng không nhận caption rỗng).
            if ($stripped !== '') {
                $caption = $stripped;
                $base = [];
            }
        }

        $have = [];

        foreach ([...self::tagsIn($caption), ...$base] as $tag) {
            $have[mb_strtolower(ltrim($tag, '#'))] = true;
        }

        $pool = array_values(array_filter($cfg['tags'], fn (string $t): bool => ! isset($have[mb_strtolower(ltrim($t, '#'))])));
        $added = self::pick($pool, $cfg['pick']);

        // Giữ giới hạn TikTok: bỏ bớt hashtag vừa thêm (từ cuối), không đụng vào caption và hashtag hub.
        while ($added !== [] && mb_strlen(HubText::compose($caption, [...$base, ...$added])) > HubText::MAX_CHARS) {
            array_pop($added);
        }

        return ['caption' => $caption, 'hashtags' => [...$base, ...$added]];
    }

    /** @return list<string> hashtag có trong chữ (kèm #). */
    public static function tagsIn(string $text): array
    {
        preg_match_all(self::TAG_IN_TEXT, $text, $m);

        return array_map(fn (string $w): string => '#'.$w, $m[1]);
    }

    /** Bỏ mọi #hashtag khỏi caption, gọn lại khoảng trắng và dòng trống. */
    public static function stripTags(string $caption): string
    {
        $text = preg_replace(self::TAG_IN_TEXT, '', $caption) ?? $caption;
        $text = preg_replace('/[ \t]{2,}/u', ' ', $text) ?? $text;
        $text = preg_replace('/[ \t]+(\R|$)/u', '$1', $text) ?? $text;
        $text = preg_replace('/(\R){3,}/u', "\n\n", $text) ?? $text;

        return trim($text);
    }

    /**
     * Chọn ngẫu nhiên $n cái (giữ thứ tự gốc); n = 0 hoặc n >= số cái thì lấy hết.
     *
     * @param  list<string>  $pool
     * @return list<string>
     */
    public static function pick(array $pool, int $n): array
    {
        if ($n <= 0 || $n >= count($pool)) {
            return $pool;
        }

        $keys = array_rand($pool, $n);
        $keys = is_array($keys) ? $keys : [$keys];
        sort($keys);

        return array_values(array_map(fn (int $k): string => $pool[$k], $keys));
    }
}

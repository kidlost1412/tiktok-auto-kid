<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Media;

use Illuminate\Support\Facades\Http;
use Throwable;

/**
 * Tải ảnh từ CDN của TikTok về máy (CDN hết hạn và chặn hotlink nên không dùng link gốc trên giao diện).
 * Chỉ nhận https và host của TikTok/ByteDance để không thành đường đi tới địa chỉ nội bộ.
 */
final class RemoteImage
{
    private const array HOST_SUFFIXES = [
        'tiktok.com', 'tiktokcdn.com', 'tiktokcdn-us.com', 'tiktokv.com', 'ibyteimg.com', 'byteimg.com',
        'ibytedtos.com', 'muscdn.com', 'ttwstatic.com', 'bytedance.com', 'tiktokw.us',
    ];

    private const int MAX_BYTES = 3_000_000;

    private const array TYPES = ['image/jpeg' => 'jpg', 'image/png' => 'png', 'image/webp' => 'webp', 'image/gif' => 'gif'];

    public static function allowed(?string $url): bool
    {
        if (! is_string($url) || strlen($url) > 2000 || preg_match('#^https://#i', $url) !== 1) {
            return false;
        }

        $host = strtolower((string) parse_url($url, PHP_URL_HOST));

        foreach (self::HOST_SUFFIXES as $suffix) {
            if ($host === $suffix || str_ends_with($host, '.'.$suffix)) {
                return true;
            }
        }

        return false;
    }

    /**
     * @return array{body: string, ext: string}|null
     */
    public static function fetch(string $url): ?array
    {
        if (! self::allowed($url)) {
            return null;
        }

        try {
            $res = Http::timeout(8)->connectTimeout(4)->withoutRedirecting()
                ->withHeaders(['User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36', 'Referer' => 'https://www.tiktok.com/'])
                ->get($url);
        } catch (Throwable) {
            return null;
        }

        $body = $res->successful() ? $res->body() : '';

        if ($body === '' || strlen($body) > self::MAX_BYTES) {
            return null;
        }

        $info = @getimagesizefromstring($body);
        $mime = is_array($info) ? (string) ($info['mime'] ?? '') : '';

        return isset(self::TYPES[$mime]) ? ['body' => $body, 'ext' => self::TYPES[$mime]] : null;
    }

    public static function mime(string $ext): string
    {
        return array_search($ext, self::TYPES, true) ?: 'application/octet-stream';
    }
}

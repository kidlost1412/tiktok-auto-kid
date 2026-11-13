<?php

declare(strict_types=1);

namespace App\Fork\AutoPost;

use App\Fork\AutoPost\Shop\CartRules;

/**
 * Caption, hashtag và tên giỏ hàng do hub viết sẵn. App không tự sinh chữ: chỉ đọc, cắt khoảng trắng đầu cuối,
 * và kiểm giới hạn của TikTok. Thứ tự nguồn: json trong kho-dang, file X.txt cạnh video, hàng trong bang-ghi-ekip.csv.
 */
final class HubText
{
    public const SOURCE = 'hub';

    /** Giới hạn caption TikTok (tính theo ký tự), gồm cả hashtag và dòng trống giữa. */
    public const MAX_CHARS = 2200;

    public const REASON_MISSING = 'thiếu caption từ hub';

    public const CSV_NAME = 'bang-ghi-ekip.csv';

    /**
     * @param  array<string, mixed>|null  $json  nội dung .json đã giải mã (kho-dang), null nếu không có
     * @return array{caption: ?string, hashtags: list<string>, ten_gio: ?string, reason: ?string}
     */
    public static function resolve(string $videoPath, ?array $json = null): array
    {
        $found = null;

        if ($json !== null && is_string($json['caption'] ?? null) && trim($json['caption']) !== '') {
            $found = ['caption' => trim($json['caption']), 'hashtags' => self::tags($json['hashtag'] ?? null)];
        }

        $found ??= self::fromTxt(Sidecar::path(pathinfo($videoPath, PATHINFO_DIRNAME), pathinfo($videoPath, PATHINFO_FILENAME).'.txt'));
        $found ??= self::fromCsv($videoPath);

        $tenGio = $json === null ? null : self::cartName($json['ten_gio'] ?? null);

        if ($found === null) {
            return ['caption' => null, 'hashtags' => [], 'ten_gio' => $tenGio, 'reason' => self::REASON_MISSING];
        }

        if (mb_strlen(self::compose($found['caption'], $found['hashtags'])) > self::MAX_CHARS) {
            return ['caption' => null, 'hashtags' => [], 'ten_gio' => $tenGio, 'reason' => 'caption từ hub dài quá '.self::MAX_CHARS.' ký tự'];
        }

        return $found + ['ten_gio' => $tenGio, 'reason' => null];
    }

    /** Nội dung bài đăng: caption + dòng trống + hashtag, nguyên văn. */
    public static function compose(string $caption, array $hashtags): string
    {
        $caption = trim($caption);

        return $hashtags === [] ? $caption : $caption."\n\n".implode(' ', $hashtags);
    }

    /** Tên giỏ hàng hợp lệ: 1..30 ký tự (code point) sau khi cắt khoảng trắng; không hợp lệ trả null. */
    public static function cartName(mixed $raw): ?string
    {
        if (! is_string($raw)) {
            return null;
        }

        $name = trim($raw);
        $len = mb_strlen($name);

        return $len >= 1 && $len <= CartRules::NAME_MAX ? $name : null;
    }

    /** @return list<string> */
    public static function tags(mixed $raw): array
    {
        $parts = is_array($raw) ? $raw : (is_string($raw) ? [$raw] : []);
        $tags = [];

        foreach ($parts as $part) {
            if (is_string($part)) {
                foreach (preg_split('/\s+/u', trim($part), -1, PREG_SPLIT_NO_EMPTY) ?: [] as $tag) {
                    $tags[] = $tag;
                }
            }
        }

        return $tags;
    }

    /** @return array{caption: string, hashtags: list<string>}|null */
    private static function fromTxt(string $file): ?array
    {
        if (! is_file($file)) {
            return null;
        }

        $content = (string) file_get_contents($file);
        $content = preg_replace('/^\xEF\xBB\xBF/', '', $content) ?? $content;
        $lines = preg_split('/\R/u', $content) ?: [];
        $caption = trim($lines[0] ?? '');

        return $caption === '' ? null : ['caption' => $caption, 'hashtags' => self::tags($lines[1] ?? '')];
    }

    /** @return array{caption: string, hashtags: list<string>}|null */
    private static function fromCsv(string $videoPath): ?array
    {
        $row = self::readCsv(Sidecar::path(dirname($videoPath), self::CSV_NAME))[basename($videoPath)] ?? null;

        if ($row === null || trim($row['caption'] ?? '') === '') {
            return null;
        }

        return ['caption' => trim($row['caption']), 'hashtags' => self::tags($row['hashtag'] ?? '')];
    }

    /** @return array<string, array<string, string>> tên file => hàng (khoá theo tên cột) */
    public static function readCsv(string $file): array
    {
        if (! is_file($file)) {
            return [];
        }

        $content = (string) file_get_contents($file);
        $content = preg_replace('/^\xEF\xBB\xBF/', '', $content) ?? $content;

        $stream = fopen('php://memory', 'r+');
        fwrite($stream, $content);
        rewind($stream);

        $header = fgetcsv($stream, escape: '');
        $rows = [];

        if (is_array($header)) {
            $header = array_map(fn ($h): string => trim((string) $h), $header);

            while (($line = fgetcsv($stream, escape: '')) !== false) {
                if ($line === [null]) {
                    continue;
                }

                $row = [];

                foreach ($header as $i => $column) {
                    $row[$column] = trim((string) ($line[$i] ?? ''));
                }

                if (($row['file'] ?? '') !== '') {
                    $rows[basename($row['file'])] = $row;
                }
            }
        }

        fclose($stream);

        return $rows;
    }
}

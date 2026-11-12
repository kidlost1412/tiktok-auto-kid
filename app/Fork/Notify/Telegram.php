<?php

declare(strict_types=1);

namespace App\Fork\Notify;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Response;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * Gửi tin cho chủ app qua Telegram Bot API (HTML). Chưa cấu hình thì không làm gì cả.
 * Chống trùng theo khoá, tôn trọng bật/tắt từng loại tin và giờ yên tĩnh, giãn cách 1 tin/giây, thử lại có lùi dần.
 */
final class Telegram
{
    private const string LAST_SENT = 'fork:telegram:last_sent_at';

    public static function configured(): bool
    {
        return TelegramSettings::configured();
    }

    /**
     * Gửi một tin. Có $dedupeKey thì cùng khoá chỉ được gửi một lần trong $ttl giây (gửi lỗi thì nhả khoá).
     * Có $type thì loại tin đó phải đang bật, và tin không khẩn cấp bị giữ lại (không dùng khoá) trong giờ yên tĩnh:
     * lượt kiểm tra sau giờ yên tĩnh sẽ gửi.
     */
    public static function send(string $text, ?string $dedupeKey = null, int $ttl = 3600, ?string $type = null, bool $force = false): bool
    {
        if (! self::configured()) {
            return false;
        }

        if (! $force && $type !== null && ! self::allowed($type)) {
            return false;
        }

        $key = null;

        if ($dedupeKey !== null) {
            $key = 'fork:telegram:sent:'.hash('sha256', $dedupeKey);

            if (! Cache::add($key, 1, $ttl)) {
                return false;
            }
        }

        if (self::post($text)) {
            return true;
        }

        if ($key !== null) {
            Cache::forget($key);
        }

        return false;
    }

    /** Loại tin đang bật và (nếu không khẩn cấp) không nằm trong giờ yên tĩnh? */
    public static function allowed(string $type): bool
    {
        if (! TelegramSettings::enabled($type)) {
            return false;
        }

        return TelegramSettings::urgent($type) || ! TelegramSettings::inQuietHours();
    }

    public static function wasSent(string $dedupeKey): bool
    {
        return Cache::has('fork:telegram:sent:'.hash('sha256', $dedupeKey));
    }

    public static function markSent(string $dedupeKey, int $ttl): void
    {
        Cache::put('fork:telegram:sent:'.hash('sha256', $dedupeKey), 1, $ttl);
    }

    /** Gửi một Message đã dựng sẵn (xem Messages). */
    public static function sendMessage(Message $m): bool
    {
        return self::send($m->text, $m->key, $m->ttl, $m->type);
    }

    /** Xoá mọi thứ trông như token bot khỏi văn bản trước khi gửi hoặc ghi log. */
    public static function scrub(string $text): string
    {
        return (string) preg_replace('/\b\d{6,}:[A-Za-z0-9_-]{30,}\b/', '***', $text);
    }

    private static function post(string $text): bool
    {
        $payload = [
            'chat_id' => TelegramSettings::chatId(),
            'text' => mb_substr(self::scrub($text), 0, 4000),
            'parse_mode' => 'HTML',
            'disable_web_page_preview' => true,
        ];
        $backoff = (array) config('fork.telegram.backoff_ms', [1000, 3000]);

        for ($attempt = 0; $attempt <= count($backoff); $attempt++) {
            self::throttle();

            try {
                $response = Http::timeout(10)->asJson()->post(self::url('sendMessage'), $payload);
            } catch (ConnectionException) {
                $response = null;
            } catch (Throwable $e) {
                Log::warning('Telegram: gửi lỗi.', ['error' => self::scrub($e->getMessage())]);

                return false;
            }

            if ($response?->successful()) {
                return true;
            }

            // Lỗi do mình (400/401/403/404...) thì thử lại cũng vô ích; chỉ thử lại khi quá tải (429) hoặc lỗi máy chủ/mạng.
            if ($response !== null && $response->status() !== 429 && $response->status() < 500) {
                Log::warning('Telegram: bị từ chối.', ['status' => $response->status(), 'body' => self::scrub(mb_substr($response->body(), 0, 300))]);

                return false;
            }

            if ($attempt < count($backoff)) {
                self::sleepMs(self::retryAfterMs($response) ?? (int) $backoff[$attempt]);
            }
        }

        return false;
    }

    private static function retryAfterMs(?Response $r): ?int
    {
        $s = $r?->json('parameters.retry_after');

        return is_numeric($s) ? min(30, max(1, (int) $s)) * 1000 : null;
    }

    /** Telegram cho khoảng 1 tin mỗi giây cho mỗi cuộc trò chuyện: chờ đủ khoảng cách kể từ tin trước. */
    private static function throttle(): void
    {
        $gap = (int) config('fork.telegram.min_interval_ms', 1100);
        $last = (float) Cache::get(self::LAST_SENT, 0);

        if ($gap > 0 && $last > 0) {
            $wait = (int) ceil($gap - (microtime(true) - $last) * 1000);

            if ($wait > 0) {
                self::sleepMs(min($wait, $gap));
            }
        }

        Cache::put(self::LAST_SENT, microtime(true), 60);
    }

    private static function sleepMs(int $ms): void
    {
        if ($ms > 0) {
            usleep($ms * 1000);
        }
    }

    private static function url(string $method): string
    {
        return 'https://api.telegram.org/bot'.TelegramSettings::token().'/'.$method;
    }
}

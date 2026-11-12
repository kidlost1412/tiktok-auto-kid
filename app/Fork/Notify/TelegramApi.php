<?php

declare(strict_types=1);

namespace App\Fork\Notify;

use Illuminate\Support\Facades\Http;
use Throwable;

/** Gọi Bot API để thiết lập: getMe (kiểm tra token, lấy tên bot) và getUpdates (tự tìm chat id). */
final class TelegramApi
{
    /** @return array{id: int, username: string, name: string}|null null khi token sai hoặc không gọi được */
    public static function getMe(string $token): ?array
    {
        try {
            $r = Http::timeout(10)->get("https://api.telegram.org/bot{$token}/getMe");
        } catch (Throwable) {
            return null;
        }

        if (! $r->successful() || $r->json('ok') !== true) {
            return null;
        }

        return [
            'id' => (int) $r->json('result.id'),
            'username' => (string) $r->json('result.username', ''),
            'name' => (string) $r->json('result.first_name', ''),
        ];
    }

    /**
     * Chat riêng (private) mới nhất đã nhắn cho bot.
     *
     * @return array{id: string, name: string}|null
     */
    public static function latestPrivateChat(string $token): ?array
    {
        try {
            $r = Http::timeout(10)->get("https://api.telegram.org/bot{$token}/getUpdates", ['limit' => 100, 'timeout' => 0]);
        } catch (Throwable) {
            return null;
        }

        if (! $r->successful() || $r->json('ok') !== true) {
            return null;
        }

        $best = null;

        foreach ((array) $r->json('result', []) as $u) {
            $msg = $u['message'] ?? $u['edited_message'] ?? $u['my_chat_member'] ?? null;
            $chat = is_array($msg) ? ($msg['chat'] ?? null) : null;

            if (! is_array($chat) || ($chat['type'] ?? '') !== 'private' || ! isset($chat['id'])) {
                continue;
            }

            if ($best === null || (int) ($u['update_id'] ?? 0) >= $best['update_id']) {
                $name = trim(($chat['first_name'] ?? '').' '.($chat['last_name'] ?? ''));
                $best = [
                    'update_id' => (int) ($u['update_id'] ?? 0),
                    'id' => (string) $chat['id'],
                    'name' => $name !== '' ? $name : (isset($chat['username']) ? '@'.$chat['username'] : (string) $chat['id']),
                ];
            }
        }

        return $best === null ? null : ['id' => $best['id'], 'name' => $best['name']];
    }
}

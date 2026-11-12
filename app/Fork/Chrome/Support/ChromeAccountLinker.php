<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Support;

use App\Enums\SocialAccount\Platform;
use App\Enums\SocialAccount\Status;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\SingleUser\SingleUser;
use App\Models\SocialAccount;
use App\Models\Workspace;
use Illuminate\Support\Facades\DB;

/**
 * Tạo tài khoản TikTok "chỉ đăng qua Chrome" từ danh tính mà tiện ích TikTok Auto Kid báo về.
 * Bản chạy một người dùng / bản gọn không dùng API chính thức của TikTok nên không có bước "Kết nối kênh":
 * kênh xuất hiện tự động ngay khi Chrome ghép nối và báo tên TikTok.
 */
final class ChromeAccountLinker
{
    /** Có tự tạo tài khoản từ Chrome không (chế độ một người dùng hoặc bản gọn). */
    public static function automatic(): bool
    {
        return SingleUser::enabled() || (bool) config('fork.slim.enabled');
    }

    /**
     * Tạo tài khoản (nếu chưa có) cho danh tính của Chrome này. Tài khoản đã có (kể cả đang tắt) giữ nguyên.
     */
    public static function link(Workspace $workspace, ChromeClient $client): ?SocialAccount
    {
        $userId = (string) $client->tiktok_user_id;
        $username = ltrim((string) $client->tiktok_username, '@');

        if ($userId === '' || $username === '') {
            return null;
        }

        $exists = SocialAccount::query()
            ->whereIn('workspace_id', Workspace::query()->where('account_id', $workspace->account_id)->pluck('id'))
            ->where('platform', Platform::TikTok->value)
            ->where('platform_user_id', $userId)
            ->exists();

        if ($exists) {
            return null;
        }

        return self::create($workspace, $userId, $username);
    }

    /** Ép tạo/cập nhật (nút thủ công "Thêm tài khoản"). */
    public static function create(Workspace $workspace, string $userId, string $username): SocialAccount
    {
        return DB::transaction(function () use ($workspace, $userId, $username): SocialAccount {
            $account = $workspace->socialAccounts()->updateOrCreate(
                ['platform' => Platform::TikTok->value, 'platform_user_id' => $userId],
                [
                    'username' => $username,
                    'display_name' => $username,
                    // Cột access_token không cho null; tài khoản chỉ-Chrome không có token API nên để rỗng.
                    'access_token' => '',
                    'scopes' => [],
                    'meta' => ['chrome_only' => true],
                    'status' => Status::Connected,
                    'error_message' => null,
                    'disconnected_at' => null,
                ],
            );

            ChromeAccount::query()->updateOrCreate(
                ['social_account_id' => $account->id],
                ['enabled' => true, 'tiktok_user_id' => $userId, 'chrome_only' => true],
            );

            return $account;
        });
    }

    /** Tự liên kết mọi Chrome đã ghép nối của chủ tài khoản này (khi bật chế độ tự động). */
    public static function linkAll(string $accountId): void
    {
        if (! self::automatic()) {
            return;
        }

        $workspace = Workspace::query()->where('account_id', $accountId)->oldest()->first();

        if (! $workspace) {
            return;
        }

        ChromeClient::query()
            ->where('account_id', $accountId)
            ->whereNull('revoked_at')
            ->whereNotNull('tiktok_user_id')
            ->whereNotNull('tiktok_username')
            ->get()
            ->each(fn (ChromeClient $c) => self::link($workspace, $c));
    }
}

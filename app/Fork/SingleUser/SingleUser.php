<?php

declare(strict_types=1);

namespace App\Fork\SingleUser;

use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Chế độ một người dùng (APP_SINGLE_USER): app chạy trên máy của chủ, không có đăng nhập.
 * Giữ một user + account + workspace nội bộ để phân quyền và gom tài khoản TikTok.
 */
final class SingleUser
{
    public const OWNER_EMAIL = 'owner@tiktok-auto.local';

    public static function enabled(): bool
    {
        return (bool) config('fork.single_user');
    }

    /** Địa chỉ socket thật (không tin X-Forwarded-For) có phải loopback không. */
    public static function isLoopback(Request $request): bool
    {
        $ip = (string) $request->server->get('REMOTE_ADDR', '');

        if (str_starts_with($ip, '::ffff:')) {
            $ip = substr($ip, 7);
        }

        return $ip === '::1' || str_starts_with($ip, '127.');
    }

    public static function owner(): ?User
    {
        $account = Account::query()->whereNotNull('owner_id')->oldest()->first();

        return ($account ? User::query()->find($account->owner_id) : null)
            ?? User::query()->oldest()->first();
    }

    /** Tạo (nếu chưa có) chủ + account + workspace. An toàn khi chạy nhiều lần. */
    public static function ensureOwner(): User
    {
        $user = self::owner() ?? DB::transaction(function (): User {
            $account = Account::query()->forceCreate(['name' => 'TikTok Auto Kid']);

            $user = User::query()->create([
                'name' => 'Chủ tài khoản',
                'email' => self::OWNER_EMAIL,
                'password' => Str::random(64),
                'email_verified_at' => now(),
                'account_id' => $account->id,
                'locale' => 'vi',
                'timezone' => 'Asia/Ho_Chi_Minh',
            ]);

            $account->update(['owner_id' => $user->id]);

            return $user;
        });

        if ($user->email_verified_at === null) {
            $user->forceFill(['email_verified_at' => now()])->save();
        }

        if ($user->account_id && $user->account?->owner_id === null) {
            $user->account->update(['owner_id' => $user->id]);
        }

        if (! $user->currentWorkspace) {
            $workspace = $user->accountWorkspaces()->first() ?? self::createWorkspace($user);

            $user->update(['current_workspace_id' => $workspace->id]);
            $user->unsetRelation('currentWorkspace');
        }

        return $user;
    }

    private static function createWorkspace(User $user): Workspace
    {
        $workspace = Workspace::query()->create([
            'name' => 'TikTok Auto Kid',
            'account_id' => $user->account_id,
            'user_id' => $user->id,
        ]);

        $workspace->members()->attach($user->id, ['is_admin' => true, 'requires_approval' => false]);

        return $workspace;
    }
}

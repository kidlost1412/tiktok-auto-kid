<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Media;

use App\Models\SocialAccount;
use Illuminate\Support\Facades\Storage;

/**
 * Ảnh đại diện kênh TikTok do tiện ích báo về: tải vào storage/app/public/avatars (Caddy phục vụ /storage/*)
 * rồi ghi đường dẫn vào social_accounts.avatar_url, nơi mọi thành phần ảnh đại diện của app đã đọc.
 */
final class ChannelAvatars
{
    /** Làm mới ảnh nhiều nhất mỗi chừng này giờ (tiện ích gửi hello mỗi ~1 phút). */
    private const int REFRESH_HOURS = 24;

    public static function needsRefresh(SocialAccount $account): bool
    {
        if (blank($account->getRawOriginal('avatar_url'))) {
            return true;
        }

        $at = data_get($account->meta, 'avatar_synced_at');

        return ! is_string($at) || now()->diffInHours($at, false) < -self::REFRESH_HOURS;
    }

    public function store(SocialAccount $account, ?string $url): bool
    {
        if (! RemoteImage::allowed($url)) {
            return false;
        }

        $img = RemoteImage::fetch((string) $url);

        if ($img === null) {
            return false;
        }

        $disk = Storage::disk('public');
        $path = 'avatars/tiktok-'.$account->id.'-'.substr(md5($img['body']), 0, 8).'.'.$img['ext'];
        $old = $account->getRawOriginal('avatar_url');

        $disk->put($path, $img['body']);

        if (is_string($old) && $old !== $path && str_starts_with($old, 'avatars/tiktok-')) {
            $disk->delete($old);
        }

        $account->forceFill([
            'avatar_url' => $path,
            'meta' => [...(array) $account->meta, 'avatar_synced_at' => now()->toIso8601String()],
        ])->save();

        return true;
    }
}

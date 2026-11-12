<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\SocialAccount\Platform;
use App\Enums\SocialAccount\Status;
use Database\Factories\SocialAccountFactory;
use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Facades\Storage;

/** Một kênh TikTok. Chỉ đăng qua Chrome nên không có token API (cột access_token để rỗng). */
class SocialAccount extends Model
{
    /** @use HasFactory<SocialAccountFactory> */
    use HasFactory, HasUuids;

    protected $fillable = [
        'workspace_id',
        'platform',
        'platform_user_id',
        'username',
        'display_name',
        'avatar_url',
        'access_token',
        'scopes',
        'meta',
        'status',
        'error_message',
        'disconnected_at',
        'timezone',
    ];

    protected $hidden = [
        'access_token',
        'refresh_token',
        'meta',
    ];

    protected function casts(): array
    {
        return [
            'platform' => Platform::class,
            'status' => Status::class,
            'access_token' => 'encrypted',
            'disconnected_at' => 'datetime',
            'scopes' => 'array',
            'meta' => 'array',
            'position' => 'integer',
        ];
    }

    protected static function booted(): void
    {
        static::creating(function (SocialAccount $account): void {
            if ($account->position !== null) {
                return;
            }

            $last = static::query()->where('workspace_id', $account->workspace_id)->max('position');
            $account->position = $last === null ? 0 : ((int) $last) + 1;
        });
    }

    public function workspace(): BelongsTo
    {
        return $this->belongsTo(Workspace::class);
    }

    public function posts(): HasMany
    {
        return $this->hasMany(Post::class);
    }

    protected function avatarUrl(): Attribute
    {
        return Attribute::make(
            get: fn (?string $value) => $value ? Storage::url($value) : null,
        );
    }

    /** Tên hiển thị: ưu tiên display_name, rồi username. */
    public function accountDisplayName(): string
    {
        return $this->display_name ?: $this->username ?: $this->platform->label();
    }

    /**
     * Danh tính kênh mà bài giữ lại, để bài vẫn biết đã đi tới ai sau khi kênh bị đổi tên hay xoá.
     *
     * @return array{platform_name: string, platform_username: ?string, platform_avatar: ?string}
     */
    public function channelSnapshot(): array
    {
        return [
            'platform_name' => $this->accountDisplayName(),
            'platform_username' => $this->username,
            'platform_avatar' => $this->getRawOriginal('avatar_url'),
        ];
    }

    public function markAsConnected(): void
    {
        $this->update([
            'status' => Status::Connected,
            'error_message' => null,
            'disconnected_at' => null,
        ]);
    }

    public function isDisconnected(): bool
    {
        return $this->status === Status::Disconnected || $this->status === Status::TokenExpired;
    }
}

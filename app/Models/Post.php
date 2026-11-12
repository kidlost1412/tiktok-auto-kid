<?php

declare(strict_types=1);

namespace App\Models;

use App\Dto\MediaItem;
use App\Enums\Post\CreatedVia;
use App\Enums\Post\Origin;
use App\Enums\Post\PublishStatus;
use App\Enums\Post\ScheduleMode;
use App\Enums\Post\Status as PostStatus;
use App\Enums\PostPlatform\ContentType;
use App\Enums\SocialAccount\Platform;
use Database\Factories\PostFactory;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Collection;

/** Một bài TikTok hẹn giờ, đăng qua Chrome. `status` là vòng đời của bài, `publish_status` là kết quả đăng. */
class Post extends Model
{
    /** @use HasFactory<PostFactory> */
    use HasFactory, HasUuids;

    protected $fillable = [
        'workspace_id',
        'post_group_id',
        'user_id',
        'content',
        'media',
        'status',
        'schedule_mode',
        'created_via',
        'origin',
        'scheduled_at',
        'published_at',
        'platform',
        'content_type',
        'platform_name',
        'platform_username',
        'platform_avatar',
        'meta',
        'platform_url',
        'error_message',
        'error_context',
        'retry_at',
        'publication_updated_at',
    ];

    /**
     * @var list<string>
     */
    protected $hidden = [
        'error_context',
        'publication_updated_at',
        'platform_avatar',
    ];

    /**
     * @var array<string, mixed>
     */
    protected $attributes = [
        'origin' => Origin::DEFAULT->value,
        'publish_status' => PublishStatus::DEFAULT->value,
    ];

    protected function casts(): array
    {
        return [
            'status' => PostStatus::class,
            'schedule_mode' => ScheduleMode::class,
            'created_via' => CreatedVia::class,
            'origin' => Origin::class,
            'media' => 'array',
            'scheduled_at' => 'datetime',
            'published_at' => 'datetime',
            'publish_status' => PublishStatus::class,
            'platform' => Platform::class,
            'content_type' => ContentType::class,
            'meta' => 'array',
            'error_context' => 'array',
            'submitted_at' => 'datetime',
            'retry_at' => 'datetime',
            'publication_updated_at' => 'datetime',
        ];
    }

    /**
     * @return Collection<int, MediaItem>
     */
    protected function mediaItems(): Attribute
    {
        return Attribute::make(
            get: fn () => collect($this->media ?? [])->map(fn (array $item) => MediaItem::fromArray($item)),
        );
    }

    public function workspace(): BelongsTo
    {
        return $this->belongsTo(Workspace::class);
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function socialAccount(): BelongsTo
    {
        return $this->belongsTo(SocialAccount::class);
    }

    public function ownedMedia(): HasMany
    {
        return $this->hasMany(Media::class, 'post_id')->orderBy('order');
    }

    public function scopeScheduled(Builder $query): Builder
    {
        return $query->where('status', PostStatus::Scheduled);
    }

    public function scopeDue(Builder $query): Builder
    {
        return $query->scheduled()->where('scheduled_at', '<=', now());
    }

    public function scopePublished(Builder $query): Builder
    {
        return $query->where('status', PostStatus::Published);
    }

    public function scopeFailed(Builder $query): Builder
    {
        return $query->where('status', PostStatus::Failed);
    }

    /** Bài bị TikTok từ chối vì giới hạn, đã tới giờ thử lại. */
    public function scopeDueForLimitRetry(Builder $query): Builder
    {
        return $query->where('posts.publish_status', PublishStatus::Retrying)
            ->whereNotNull('posts.retry_at')
            ->where('posts.retry_at', '<=', now());
    }

    public function markAsPublishing(): void
    {
        $this->update(['status' => PostStatus::Publishing]);
    }

    public function markAsPublished(): void
    {
        $this->update([
            'status' => PostStatus::Published,
            'published_at' => $this->published_at ?? now(),
        ]);
    }

    public function markAsFailed(): void
    {
        $this->update(['status' => PostStatus::Failed]);
    }

    /** Kênh của bài còn tồn tại. */
    public function hasChannel(): bool
    {
        return filled($this->social_account_id);
    }

    public function isPublicationWaitingForLimitRetry(): bool
    {
        return $this->publish_status === PublishStatus::Retrying && $this->retry_at?->isFuture() === true;
    }

    public function markPublicationPublishing(): void
    {
        $this->writePublication(['publish_status' => PublishStatus::Publishing, 'retry_at' => null]);
    }

    public function markPublicationPublished(string $platformPostId, ?string $platformUrl = null): void
    {
        $this->writePublication([
            'publish_status' => PublishStatus::Published,
            'platform_post_id' => $platformPostId,
            'platform_url' => $platformUrl,
            'published_at' => now(),
            'retry_at' => null,
            'error_message' => null,
            'error_context' => null,
        ]);
    }

    /**
     * @param  array<string, mixed>|null  $errorContext
     */
    public function markPublicationFailed(string $errorMessage, ?array $errorContext = null): void
    {
        $this->writePublication([
            'publish_status' => PublishStatus::Failed,
            'retry_at' => null,
            'error_message' => $errorMessage,
            'error_context' => $errorContext,
            'platform_post_id' => null,
            'platform_url' => null,
        ]);
    }

    /**
     * Ghi các trường kết quả đăng bằng đồng hồ riêng, để một lần thử đăng không làm đổi `updated_at`.
     *
     * @param  array<string, mixed>  $attributes
     */
    public function writePublication(array $attributes): void
    {
        static::withoutTimestamps(fn () => $this->forceFill([...$attributes, 'publication_updated_at' => now()])->save());
    }
}

<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Enums\Post\PublishStatus;
use App\Enums\Post\ScheduleMode;
use App\Enums\Post\Status as PostStatus;
use App\Enums\PostPlatform\ContentType;
use App\Enums\SocialAccount\Platform;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * Bài không có kênh là bản nháp chưa gửi đi đâu. Dùng forAccount() hoặc tiktok() cho bài có kênh.
 *
 * @extends Factory<Post>
 */
class PostFactory extends Factory
{
    /**
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'workspace_id' => Workspace::factory(),
            'user_id' => User::factory(),
            'content' => '',
            'media' => [],
            'status' => PostStatus::Draft,
        ];
    }

    public function forAccount(SocialAccount $account, ?ContentType $contentType = null): static
    {
        return $this->state(fn (array $attributes) => [
            'workspace_id' => $account->workspace_id,
            'social_account_id' => $account->id,
            'platform' => $account->platform,
            'content_type' => $contentType ?? ContentType::TikTokVideo,
            'meta' => $attributes['meta'] ?? [],
        ]);
    }

    /** Bài TikTok; nếu chưa có kênh thì tạo kênh TikTok trong workspace của bài. */
    public function tiktok(): static
    {
        return $this->state(fn (array $attributes) => [
            'platform' => Platform::TikTok,
            'content_type' => ContentType::TikTokVideo,
            'meta' => ['privacy_level' => 'SELF_ONLY', ...($attributes['meta'] ?? [])],
            'social_account_id' => isset($attributes['social_account_id'])
                ? $attributes['social_account_id']
                : fn (array $resolved) => SocialAccount::factory()->tiktok()->state(['workspace_id' => $resolved['workspace_id']]),
        ]);
    }

    public function draft(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => PostStatus::Draft,
        ]);
    }

    public function scheduled(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => PostStatus::Scheduled,
            'schedule_mode' => ScheduleMode::Custom,
            'scheduled_at' => now()->addDay(),
        ]);
    }

    public function publishing(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => PostStatus::Publishing,
            'publish_status' => PublishStatus::Publishing,
        ]);
    }

    public function published(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => PostStatus::Published,
            'publish_status' => PublishStatus::Published,
            'platform_post_id' => $this->faker->uuid(),
            'platform_url' => $this->faker->url(),
            'published_at' => now(),
        ]);
    }

    public function failed(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => PostStatus::Failed,
            'publish_status' => PublishStatus::Failed,
            'error_message' => 'Failed to publish',
        ]);
    }
}

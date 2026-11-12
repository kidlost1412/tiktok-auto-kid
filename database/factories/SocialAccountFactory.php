<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Enums\SocialAccount\Platform;
use App\Enums\SocialAccount\Status;
use App\Models\SocialAccount;
use App\Models\Workspace;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<SocialAccount>
 */
class SocialAccountFactory extends Factory
{
    /**
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'workspace_id' => Workspace::factory(),
            'platform' => Platform::TikTok,
            'platform_user_id' => $this->faker->uuid(),
            'username' => $this->faker->userName(),
            'display_name' => $this->faker->name(),
            'access_token' => $this->faker->sha256(),
            'scopes' => [],
            'meta' => [],
            'status' => Status::Connected,
            'timezone' => 'Asia/Ho_Chi_Minh',
        ];
    }

    public function tiktok(): static
    {
        return $this->state(fn (array $attributes) => ['platform' => Platform::TikTok]);
    }
}

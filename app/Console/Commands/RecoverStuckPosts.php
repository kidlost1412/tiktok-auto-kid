<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Post\FinalizePostPublication;
use App\Enums\Post\PublishStatus;
use App\Enums\Post\Status as PostStatus;
use App\Exceptions\Social\ErrorCategory;
use App\Models\Post;
use Illuminate\Console\Command;

class RecoverStuckPosts extends Command
{
    protected $signature = 'social:recover-stuck-posts';

    protected $description = 'Cứu các bài kẹt ở trạng thái đang đăng hơn 1 giờ';

    public function handle(): void
    {
        Post::query()
            ->where('status', PostStatus::Publishing)
            ->where('updated_at', '<=', now()->subHour())
            ->each(function (Post $post): void {
                $stale = $post->publish_status->isInFlight()
                    && blank($post->retry_at)
                    && (blank($post->publication_updated_at) || $post->publication_updated_at->lessThanOrEqualTo(now()->subHour()));

                if ($stale) {
                    $post->writePublication([
                        'publish_status' => PublishStatus::Failed,
                        'error_message' => 'Đăng bài quá lâu nên bị huỷ.',
                        'error_context' => [
                            ...($post->error_context ?? []),
                            'category' => ErrorCategory::Timeout->value,
                            'failed_at' => now()->toIso8601String(),
                        ],
                    ]);
                }

                // Một lần thử lại đang chờ giữ bài ở Retrying với đồng hồ mới: chưa chốt khi việc đó còn sống.
                if (! $post->publish_status->isFinished()) {
                    return;
                }

                app(FinalizePostPublication::class)->handle($post);
            });
    }
}

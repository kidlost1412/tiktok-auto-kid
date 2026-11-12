<?php

declare(strict_types=1);

namespace App\Actions\Post;

use App\Enums\Post\PublishStatus;
use App\Enums\Post\Status as PostStatus;
use App\Models\Post;
use Illuminate\Support\Facades\DB;

/**
 * Chốt bài khi kết quả đăng đã ở trạng thái cuối. Dùng chung cho PublishToSocialPlatform,
 * PublishPost::failed và RecoverStuckPosts.
 */
class FinalizePostPublication
{
    public function handle(Post $post): void
    {
        DB::transaction(function () use ($post): void {
            $post = Post::query()
                ->whereKey($post->id)
                ->lockForUpdate()
                ->first();

            if (! $post instanceof Post || $post->status->isSettled()) {
                return;
            }

            if (! $post->hasChannel() && $post->publish_status->isInFlight()) {
                if ($post->status !== PostStatus::Publishing) {
                    return;
                }

                $post->markPublicationFailed('Bài không còn kênh để đăng.');
                $post->markAsFailed();

                return;
            }

            if (! $post->publish_status->isFinished()) {
                return;
            }

            if ($post->publish_status === PublishStatus::Published) {
                $post->markAsPublished();
            } else {
                $post->markAsFailed();
            }
        });
    }
}

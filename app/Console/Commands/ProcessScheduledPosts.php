<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Enums\Post\Status as PostStatus;
use App\Jobs\PublishPost;
use App\Models\Post;
use Illuminate\Console\Command;
use Throwable;

class ProcessScheduledPosts extends Command
{
    protected $signature = 'posts:process-scheduled';

    protected $description = 'Đưa các bài hẹn giờ đã tới giờ vào hàng đợi đăng';

    public function handle(): void
    {
        Post::query()
            ->due()
            ->each(function (Post $post) {
                try {
                    $claimed = Post::where('id', $post->id)
                        ->where('status', PostStatus::Scheduled)
                        ->update(['status' => PostStatus::Publishing]);

                    if ($claimed) {
                        PublishPost::dispatch($post);
                    }
                } catch (Throwable $exception) {
                    report($exception);
                }
            });
    }
}

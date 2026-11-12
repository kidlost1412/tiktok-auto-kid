<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Console;

use App\Enums\Post\Status as PostStatus;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\ScheduledDispatcher;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use App\Fork\Chrome\Publishing\ChromeAwareTikTokPublisher;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * Giao bài hẹn giờ cho Chrome ngay khi bài tồn tại (ScheduledDispatcher), để TikTok tự giữ lịch.
 * Không đổi trạng thái bài trong TikTok Auto Kid: tới giờ, TikTok Auto Kid chạy publisher như thường.
 */
class ChromeDispatchCommand extends Command
{
    protected $signature = 'fork:chrome-dispatch';

    protected $description = 'Giao bài TikTok hẹn giờ cho Chrome sớm, và đánh dấu đã đăng những bài báo "không rõ" nhưng Chrome xác nhận đã đăng';

    /** Chỉ xét lại các job posted trong ngần này ngày gần đây. */
    private const int RECOVER_DAYS = 14;

    public function handle(ChromeJobs $chrome): int
    {
        try {
            ChromePostWatcher::reconcileSchedules();
        } catch (Throwable $e) {
            report($e);
        }

        try {
            app(ScheduledDispatcher::class)->dispatchAll();
        } catch (Throwable $e) {
            report($e);
        }

        $this->recoverLatePosted($chrome);

        return self::SUCCESS;
    }

    /**
     * Job báo "không rõ" làm bài thành thất bại; nếu sau đó Chrome xác nhận đã đăng thì sửa lại bài thành đã đăng.
     */
    private function recoverLatePosted(ChromeJobs $chrome): void
    {
        ChromeJob::query()
            ->where('state', 'posted')
            ->where('result_at', '>=', now()->subDays(self::RECOVER_DAYS))
            ->whereIn('post_id', Post::query()->where('status', PostStatus::Failed)->select('id'))
            ->each(function (ChromeJob $job) use ($chrome): void {
                try {
                    $this->markPosted($chrome, $job);
                } catch (Throwable $e) {
                    report($e);
                }
            });
    }

    private function markPosted(ChromeJobs $chrome, ChromeJob $job): void
    {
        DB::transaction(function () use ($chrome, $job): void {
            $post = Post::query()->with('socialAccount')->whereKey($job->post_id)->lockForUpdate()->first();

            if ($post === null || $post->status !== PostStatus::Failed || $chrome->latestForPost($post)?->id !== $job->id) {
                return;
            }

            $outcome = $chrome->outcome($job);

            if (! $outcome->ok) {
                return;
            }

            $post->markPublicationPublished(
                $outcome->videoId ?? $job->id,
                ChromeAwareTikTokPublisher::postUrl($post->socialAccount, $outcome->videoId),
            );
            $post->markAsPublished();

            Log::info('Bài báo "không rõ" đã được Chrome xác nhận đăng; đánh dấu đã đăng.', [
                'post_id' => $post->id,
                'chrome_job_id' => $job->id,
            ]);
        });
    }
}

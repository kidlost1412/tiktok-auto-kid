<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Listeners;

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Platform;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Log;
use Throwable;
use WeakMap;

/**
 * Bài TikTok bị sửa (nội dung, video, giờ đăng, quyền riêng tư), chuyển về nháp hoặc bị xoá:
 * job Chrome còn trước bước cấp quyền bị thu hồi để Chrome không đăng bản cũ.
 * Job đã hẹn giờ xong trên TikTok thì không gỡ được lịch: chỉ ghi cảnh báo vào job.
 *
 * Lớp tự đăng ký vào bộ phát sự kiện của Eloquent (không sửa provider hay upstream);
 * register() chạy lại nhiều lần cũng chỉ đăng ký một lần cho mỗi bộ phát sự kiện.
 */
final class ChromePostWatcher
{
    public const string EDIT_NOTE = 'Bài đã được sửa nên lượt giao cũ bị huỷ.';

    public const string DELETE_NOTE = 'Bài đã bị xoá nên lượt giao cũ bị huỷ.';

    public const string SCHEDULED_WARNING = 'Đã hẹn trên TikTok — muốn đổi thì sửa/huỷ trong TikTok Studio';

    /** @var WeakMap<object, true>|null */
    private static ?WeakMap $registered = null;

    public static function register(): void
    {
        $events = Event::getFacadeRoot();

        if (! is_object($events)) {
            return;
        }

        self::$registered ??= new WeakMap;

        if (isset(self::$registered[$events])) {
            return;
        }

        self::$registered[$events] = true;

        $events->listen('eloquent.updated: '.Post::class, fn (Post $post) => self::safely(fn () => self::onUpdated($post)));
        $events->listen('eloquent.deleting: '.Post::class, fn (Post $post) => self::safely(fn () => self::onDeleting($post)));
    }

    public static function isEditNote(?string $note): bool
    {
        return $note !== null && str_starts_with($note, 'Bài đã được sửa');
    }

    public static function onUpdated(Post $post): void
    {
        if (! self::isChromeCandidate($post)) {
            return;
        }

        $changed = $post->wasChanged(['content', 'media', 'scheduled_at', 'meta']);
        $leftSchedule = $post->wasChanged('status')
            && in_array($post->status, [PostStatus::Draft, PostStatus::PendingApproval], true);

        if ($changed || $leftSchedule) {
            self::revokeFor($post, self::EDIT_NOTE);
        }
    }

    public static function onDeleting(Post $post): void
    {
        if (self::isChromeCandidate($post)) {
            self::revokeFor($post, self::DELETE_NOTE);
        }
    }

    /**
     * Đối soát giờ: upstream đổi scheduled_at bằng Builder::update() (không phát sự kiện Eloquent),
     * nên dispatch gọi hàm này mỗi phút. Job hẹn giờ mà giờ đã lệch (hoặc bài không còn Scheduled)
     * thì thu hồi nếu còn trước authorize, hoặc ghi cảnh báo nếu đã posted.
     *
     * @return int số job bị thu hồi hoặc bị cảnh báo
     */
    public static function reconcileSchedules(): int
    {
        $count = 0;
        $chrome = app(ChromeJobs::class);

        $jobs = ChromeJob::query()
            ->where('mode', 'scheduled')
            ->where(fn ($q) => $q->whereIn('state', ChromeJob::PRE_AUTH)
                ->orWhere(fn ($p) => $p->where('state', 'posted')->where('result_at', '>=', now()->subDays(14))))
            ->get();

        foreach ($jobs as $job) {
            $post = Post::query()->find($job->post_id);

            if ($post === null) {
                continue;
            }

            $wanted = $job->options['schedule_time'] ?? null;
            $current = $post->scheduled_at?->copy()->utc()->format('Y-m-d\TH:i:s\Z');
            $stale = $post->status !== PostStatus::Scheduled || $wanted === null || $wanted !== $current;

            if (! $stale) {
                continue;
            }

            if ($job->state === 'posted') {
                if ($job->note === self::SCHEDULED_WARNING) {
                    continue;
                }

                ChromeJob::query()->whereKey($job->id)->update(['note' => self::SCHEDULED_WARNING]);
                Log::warning('Giờ bài đã đổi sau khi TikTok nhận lịch đăng qua Chrome; không gỡ được lịch trên TikTok.', [
                    'post_id' => $post->getKey(),
                    'chrome_job_id' => $job->id,
                ]);
                $count++;
            } elseif ($chrome->revoke($job->id, self::EDIT_NOTE)) {
                $count++;
            }
        }

        return $count;
    }

    private static function isChromeCandidate(Post $post): bool
    {
        return $post->platform === Platform::TikTok && filled($post->social_account_id);
    }

    private static function revokeFor(Post $post, string $note): void
    {
        $chrome = app(ChromeJobs::class);

        $jobs = ChromeJob::query()
            ->where('post_id', $post->getKey())
            ->whereIn('state', [...ChromeJob::OPEN, 'posted'])
            ->get();

        foreach ($jobs as $job) {
            if ($job->state === 'posted') {
                if ($job->mode === 'scheduled') {
                    ChromeJob::query()->whereKey($job->id)->update(['note' => self::SCHEDULED_WARNING]);

                    Log::warning('Bài đã sửa/xoá sau khi TikTok nhận lịch đăng qua Chrome; không gỡ được lịch trên TikTok.', [
                        'post_id' => $post->getKey(),
                        'chrome_job_id' => $job->id,
                    ]);
                }

                continue;
            }

            if (! $chrome->revoke($job->id, $note)) {
                Log::warning('Bài đã sửa nhưng job Chrome đã được cấp quyền đăng, không thu hồi được.', [
                    'post_id' => $post->getKey(),
                    'chrome_job_id' => $job->id,
                    'state' => $job->state,
                ]);
            }
        }
    }

    /**
     * Lỗi ở đây không được làm hỏng việc lưu bài.
     */
    private static function safely(callable $callback): void
    {
        try {
            $callback();
        } catch (Throwable $e) {
            report($e);
        }
    }
}

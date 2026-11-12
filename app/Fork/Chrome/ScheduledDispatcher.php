<?php

declare(strict_types=1);

namespace App\Fork\Chrome;

use App\Enums\SocialAccount\Platform;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeRefusal;
use App\Models\Post;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;

/**
 * Giao bài TikTok hẹn giờ cho Chrome NGAY khi bài tồn tại (không đợi tới sát giờ đăng), để TikTok tự giữ lịch
 * và giờ đăng không còn phụ thuộc máy tính có bật hay không.
 *
 * Mỗi tài khoản chỉ có một job mở tại một thời điểm; job nào xong (posted) thì việc giao bài kế tiếp
 * được gọi ngay (ChromeJobs::ingestResult), cron mỗi phút chỉ là lưới an toàn.
 * Bài có giờ đăng gần hơn SCHEDULE_LEAD + 2 phút thì không giao nữa (giữ hành vi cũ: Chrome không kịp).
 */
class ScheduledDispatcher
{
    /** Số bài xét tối đa mỗi tài khoản mỗi lượt (đã loại bài từng có job). */
    private const int CANDIDATES_PER_ACCOUNT = 50;

    public function __construct(private readonly ChromeJobs $chrome) {}

    /** Mọi tài khoản TikTok đã bật đăng qua Chrome. */
    public function dispatchAll(?CarbonImmutable $now = null): int
    {
        $now ??= CarbonImmutable::now();
        $queued = 0;

        $accounts = SocialAccount::query()
            ->where('platform', Platform::TikTok)
            ->where('status', AccountStatus::Connected)
            ->whereIn('id', ChromeAccount::query()->where('enabled', true)->select('social_account_id'))
            ->get();

        foreach ($accounts as $account) {
            $queued += $this->dispatchForAccount($account, $now);
        }

        return $queued;
    }

    /** @return int số job đã tạo (0 hoặc 1) */
    public function dispatchForAccount(SocialAccount $account, ?CarbonImmutable $now = null): int
    {
        $now ??= CarbonImmutable::now();

        if ($this->chrome->openJobFor($account) !== null) {
            return 0;
        }

        $from = $now->addSeconds(ChromeJobs::SCHEDULE_LEAD + 120);
        $to = $now->addSeconds(ChromeJobs::SCHEDULE_MAX_AHEAD);

        $posts = Post::query()
            ->with('socialAccount')
            ->scheduled()
            ->where('social_account_id', $account->id)
            ->where('platform', Platform::TikTok)
            ->whereBetween('scheduled_at', [$from, $to])
            // Bài đã có job (đã tải lên, đang lỗi...) không chiếm chỗ trong danh sách xét; riêng job bị thu hồi vì sửa bài thì xét lại.
            ->whereNotIn('id', ChromeJob::query()->where('state', '!=', 'revoked')->select('post_id'))
            ->orderBy('scheduled_at')
            ->limit(self::CANDIDATES_PER_ACCOUNT)
            ->get();

        foreach ($posts as $post) {
            if ($this->needsScheduledJob($post) && $this->queueScheduled($post)) {
                return 1;
            }
        }

        return 0;
    }

    private function needsScheduledJob(Post $post): bool
    {
        $latest = $this->chrome->latestForPost($post);

        return $latest === null
            || ($latest->state === 'revoked' && ! $latest->cancel_requested && ChromePostWatcher::isEditNote($latest->note));
    }

    private function queueScheduled(Post $post): bool
    {
        try {
            $this->chrome->queueForPost($post, 'scheduled');

            return true;
        } catch (ChromeRefusal $refusal) {
            if ($refusal->busy) {
                return false;
            }

            if (Cache::add("fork:chrome:dispatch-refusal:{$post->id}", 1, 3600)) {
                Log::info('Bài hẹn giờ không giao được cho Chrome: '.$refusal->getMessage(), ['post_id' => $post->id]);
            }

            return false;
        }
    }
}

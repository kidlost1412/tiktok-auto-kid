<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Enums\Post\PublishStatus;
use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Hub\HubReporter;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * "Thử lại" bài lỗi: trả video `failed` về kho (`new`) để lần xếp lịch sau đăng lại.
 *
 * Chỉ làm khi CHẮC CHẮN chưa có gì lên TikTok: bài TikTok Auto Kid đã chốt lỗi, không có mã video TikTok,
 * và mọi job Chrome của bài đều kết thúc rõ ràng là chưa gửi (failed / rejected / revoked).
 * Còn nghi ngờ (job đang chạy, "uncertain", "posted", bài đang đăng/chờ thử lại, hub báo máy khác giữ) thì từ chối.
 */
final class RetryFailed
{
    /** Job Chrome kết thúc mà chắc chắn chưa đăng gì. */
    private const array SAFE_JOB_STATES = ['failed', 'rejected', 'revoked'];

    /**
     * Lý do không thử lại được (câu tiếng Việt cho chủ app), hoặc null nếu an toàn.
     *
     * @param  bool  $ownerChecked  chủ app đã tự mở TikTok Studio xác nhận bài CHƯA lên: job "uncertain" (Chrome không
     *                              báo kết quả) được coi như chưa gửi. Job "posted" (TikTok đã nhận) thì vẫn từ chối.
     */
    public function refusal(AutoVideo $video, bool $ownerChecked = false): ?string
    {
        if ($video->status !== AutoVideo::FAILED) {
            return 'Video này không ở trạng thái lỗi nên không cần thử lại.';
        }

        if (filled($video->tiktok_video_id) || filled(data_get($video->stats, 'link'))) {
            return 'Video này đã có trên TikTok, không thử lại để tránh đăng trùng.';
        }

        if (data_get($video->meta, 'hub_claim_conflict') !== null) {
            return 'Xưởng Video báo video này đã được máy khác giữ hoặc đã đăng, không thử lại để tránh đăng trùng.';
        }

        if ($video->post_id === null) {
            return null;
        }

        $jobs = ChromeJob::query()->where('post_id', $video->post_id)->pluck('state');
        $safe = $ownerChecked ? [...self::SAFE_JOB_STATES, 'uncertain'] : self::SAFE_JOB_STATES;

        if ($jobs->contains(fn ($s): bool => ! in_array($s, $safe, true))) {
            return $jobs->contains('posted') || $jobs->contains('uncertain')
                ? 'Chưa chắc bài này đã đăng hay chưa (Chrome có thể đã gửi lên TikTok). Hãy kiểm tra trên TikTok Studio trước, app không tự đăng lại để tránh trùng.'
                : 'Chrome vẫn đang xử lý bài này. Hãy chờ vài phút rồi thử lại.';
        }

        $post = Post::query()->find($video->post_id);

        if ($post === null) {
            return null;
        }

        if (filled($post->platform_post_id) || filled($post->platform_url) || $post->status === PostStatus::Published) {
            return 'Bài này đã lên TikTok, không thử lại để tránh đăng trùng.';
        }

        if ($post->status !== PostStatus::Failed) {
            return 'Bài này chưa chốt lỗi (vẫn đang chờ đăng). Hãy chờ kết quả rồi thử lại.';
        }

        if (in_array($post->publish_status, [PublishStatus::Publishing, PublishStatus::Retrying, PublishStatus::PendingReview, PublishStatus::Published], true)) {
            return 'Bài này vẫn đang được đăng hoặc chờ thử lại tự động. Hãy chờ kết quả.';
        }

        return null;
    }

    /**
     * Chỉ vướng vì Chrome không rõ đã gửi hay chưa ("uncertain"): chủ app có thể kiểm tra TikTok rồi xác nhận
     * "chưa lên" để đăng lại (nút riêng, có hộp xác nhận).
     */
    public function needsOwnerCheck(AutoVideo $video): bool
    {
        return $this->refusal($video) !== null && $this->refusal($video, true) === null;
    }

    /**
     * Trả video về kho như video chưa từng được xếp (giống ResultWatcher::requeueForRetry).
     *
     * @return string|null lý do từ chối, null khi đã trả về kho
     */
    public function retry(AutoVideo $video, bool $ownerChecked = false): ?string
    {
        $refusal = DB::transaction(function () use ($video, $ownerChecked): ?string {
            $locked = AutoVideo::query()->whereKey($video->id)->lockForUpdate()->first();

            if ($locked === null) {
                return 'Không tìm thấy video này nữa.';
            }

            $refusal = $this->refusal($locked, $ownerChecked);

            if ($refusal !== null) {
                return $refusal;
            }

            $meta = (array) $locked->meta;
            unset($meta['hub_claimed_at']);

            if ($ownerChecked && $this->refusal($locked) !== null) {
                $meta['owner_confirmed_not_posted_at'] = now()->toIso8601String();
            }

            $won = AutoVideo::query()->whereKey($locked->id)->where('status', AutoVideo::FAILED)->update([
                'status' => AutoVideo::NEW,
                'social_account_id' => null,
                'post_id' => null,
                'scheduled_for' => null,
                'posted_at' => null,
                'skip_reason' => null,
                'meta' => $meta === [] ? null : json_encode($meta, JSON_UNESCAPED_UNICODE),
                'updated_at' => now(),
            ]);

            return $won === 1 ? null : 'Video vừa đổi trạng thái, hãy tải lại trang.';
        });

        if ($refusal !== null) {
            return $refusal;
        }

        $video->refresh();
        // Nhả chỗ trên hub (nếu còn) để lượt xếp lịch sau giữ lại; hub vẫn liệt kê video "lỗi" là chưa đăng.
        app(HubReporter::class)->released($video);

        Log::info('Tự động đăng: chủ app bấm "Thử lại", video lỗi về kho.', ['video_id' => $video->id, 'owner_checked' => $ownerChecked]);

        return null;
    }
}

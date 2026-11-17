<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\Reschedule;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\ScheduledDispatcher;
use App\Models\Post;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use DateTimeZone;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use InvalidArgumentException;
use RuntimeException;
use Throwable;

/**
 * "Đổi giờ" một bài đã xếp lịch nhưng chưa đăng (Lịch đăng ở trang Tổng quan).
 *
 *  A. Bài chưa lên TikTok (chưa có job Chrome xong): đổi Post.scheduled_at + AutoVideo.scheduled_for trong một giao dịch;
 *     job Chrome còn xếp hàng bị thu hồi (ghi chú "Bài đã được sửa") và bộ giao bài gửi lại với giờ mới.
 *     Chrome đang tải bài lên thì từ chối (tránh đăng trùng).
 *  B. Bài đã hẹn sẵn trên TikTok (job hẹn giờ đã posted): TikTok không cho sửa giờ hẹn, nên app nhờ tiện ích Chrome
 *     XOÁ HẲN bài hẹn cũ rồi KIỂM LẠI bằng danh sách bài của TikTok Studio (PROTOCOL.md mục 12). Chỉ khi máy chủ nhận
 *     kết quả "đã xoá, đã xác minh" mới đặt giờ mới và để bộ giao bài tải lên lại. Không xác minh được thì không đổi gì:
 *     lịch cũ trên TikTok vẫn còn hiệu lực. Không bao giờ để bài thành 0 hoặc 2 bản.
 *
 * Luật giờ mới (chỉ luật của TikTok): cách bây giờ >= NEW_MIN_LEAD, không quá ChromeJobs::SCHEDULE_MAX_AHEAD. App KHÔNG ép
 * khung giờ đăng hay khoảng cách giữa các bài cùng kênh; chỉ báo giờ các bài khác của kênh (channel_times) để chủ app tự quyết.
 */
final class Reschedules
{
    /** Bài hẹn sẵn trên TikTok phải còn cách giờ đăng cũ ít nhất ngần này mới cho xoá (xoá sát giờ có thể đụng bài đã đăng). */
    public const int OLD_MIN_AHEAD = 5 * 60;

    /** Việc xoá chỉ được giao/nhận khi giờ đăng cũ còn xa hơn ngần này. */
    public const int OFFER_UNTIL = 3 * 60;

    /** Giờ mới phải cách bây giờ ít nhất ngần này (TikTok đòi >= 15 phút, cộng thời gian tải video lên). */
    public const int NEW_MIN_LEAD = 20 * 60;

    /** Chrome không nhận việc xoá trong ngần này giây thì yêu cầu hết hạn (không đổi gì). */
    public const int PENDING_TTL = 15 * 60;

    /** Chrome nhận việc mà không báo kết quả trong ngần này giây thì chuyển "chưa rõ". */
    public const int CLAIMED_TTL = 15 * 60;

    /** Bài chưa lên TikTok: giờ cũ phải còn cách ít nhất ngần này (tránh đụng posts:process-scheduled). */
    public const int LOCAL_MIN_AHEAD = 5 * 60;

    public const string BUSY_TEXT = 'Chrome đang tải bài này lên TikTok — chờ khoảng một phút rồi thử lại (tránh đăng trùng).';

    public const string NOTE_DELETED = 'Bài đã được sửa giờ: bài hẹn cũ trên TikTok đã được xoá và kiểm lại, app sẽ tải lên lại với giờ mới.';

    private const array COUNTED = ['reserved', 'scheduled', 'posted'];

    /** Lý do tiện ích báo -> câu tiếng Việt cho chủ app. Mọi lý do ở đây đều nghĩa là KHÔNG đổi gì. */
    private const array REASONS = [
        'not_found' => 'Không thấy bài hẹn này trong TikTok Studio — chưa xoá gì, giữ nguyên lịch cũ. Hãy mở TikTok Studio kiểm tra.',
        'not_scheduled' => 'Bài trên TikTok không còn ở trạng thái hẹn giờ (hoặc đã quá sát giờ đăng) — không xoá, giữ nguyên.',
        'not_deleted' => 'TikTok chưa xoá bài hẹn cũ (vẫn thấy trong danh sách bài) — giữ nguyên lịch cũ, chưa đổi giờ.',
        'identity' => 'Chrome đang đăng nhập một tài khoản TikTok khác — không xoá gì, giữ nguyên lịch cũ.',
        'list_failed' => 'Chrome không đọc được danh sách bài của TikTok Studio — chưa xoá gì, giữ nguyên lịch cũ.',
        'ui_failed' => 'TikTok không nhận lệnh xoá bài hẹn cũ (và Chrome cũng không bấm được nút Xoá trong TikTok Studio) — chưa xoá gì, giữ nguyên lịch cũ.',
        'delete_failed' => 'TikTok từ chối lệnh xoá bài hẹn cũ — giữ nguyên lịch cũ, chưa đổi giờ.',
        'unknown' => 'Đã gửi lệnh xoá nhưng không kiểm lại được danh sách bài — CHƯA đổi giờ. Hãy mở TikTok Studio xem bài hẹn cũ còn hay không trước khi làm gì thêm.',
    ];

    public function __construct(private readonly ChromeJobs $chrome) {}

    // ---------------------------------------------------------------- Đọc cho giao diện

    /**
     * Bài này đổi giờ theo cách nào. kind: local (chưa lên TikTok) | tiktok (đã hẹn trên TikTok) | null (không đổi được, xem reason).
     *
     * @return array{kind: ?string, reason: ?string, post: ?Post, job: ?ChromeJob}
     */
    public function inspect(AutoVideo $video): array
    {
        $no = fn (string $reason, ?Post $post = null, ?ChromeJob $job = null): array => ['kind' => null, 'reason' => $reason, 'post' => $post, 'job' => $job];

        if ($video->status === AutoVideo::POSTED) {
            return $no($video->posted_at?->isFuture()
                ? 'Bài này được ghi nhận đã hẹn từ nơi khác (hub/máy khác) — muốn đổi giờ hãy sửa trong TikTok Studio.'
                : 'Bài đã đăng rồi.');
        }

        if (! in_array($video->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED], true)) {
            return $no('Chỉ đổi giờ được bài đã xếp lịch mà chưa đăng.');
        }

        $post = $video->post_id ? Post::query()->find($video->post_id) : null;

        if ($post === null) {
            return $no('Bài đang được tạo — thử lại sau một phút.');
        }

        if ($post->status !== PostStatus::Scheduled || $post->scheduled_at === null) {
            return $no($post->status === PostStatus::Publishing ? 'Bài đang được đăng.' : 'Bài không còn ở trạng thái hẹn giờ.', $post);
        }

        $job = $this->chrome->latestForPost($post);

        if ($job !== null && $job->state === 'posted' && $job->mode === 'scheduled') {
            return ['kind' => 'tiktok', 'reason' => null, 'post' => $post, 'job' => $job];
        }

        if ($job === null || in_array($job->state, ['queued', 'revoked', 'failed'], true) || ChromeJobs::isQuotaRejection($job)) {
            return ['kind' => 'local', 'reason' => null, 'post' => $post, 'job' => $job];
        }

        return $no(match ($job->state) {
            'claimed', 'uploading', 'ready', 'authorized' => self::BUSY_TEXT,
            'uncertain' => 'Không rõ bài đã lên TikTok hay chưa — kiểm tra TikTok Studio trước, không đổi giờ được.',
            'rejected' => 'TikTok đã từ chối bài này — không đổi giờ được.',
            default => 'Bài đã được giao cho TikTok — không đổi giờ được.',
        }, $post, $job);
    }

    /**
     * Thông tin cho hộp "Đổi giờ": cách đổi, luật giờ, yêu cầu gần nhất.
     *
     * @return array<string, mixed>
     */
    public function describe(AutoVideo $video): array
    {
        $this->reconcile();
        $info = $this->inspect($video);
        $open = $this->openFor($video);

        if ($open !== null) {
            $info['kind'] = 'tiktok';
            $info['reason'] = null;
        }

        return [
            'id' => $video->id,
            'kind' => $info['kind'],
            'reason' => $info['reason'],
            'current_at' => ($info['post']?->scheduled_at ?? $video->scheduled_for)?->toIso8601String(),
            'rules' => $this->rules($video),
            'channel_times' => $this->channelTimes($video, $info['post']),
            'request' => $this->latestSummary($video),
        ];
    }

    /** @return array<string, mixed> */
    public function rules(AutoVideo $video): array
    {
        return [
            'timezone' => $this->tz((string) $video->social_account_id)->getName(),
            'min_lead_minutes' => intdiv(self::NEW_MIN_LEAD, 60),
            'max_ahead_hours' => intdiv(ChromeJobs::SCHEDULE_MAX_AHEAD, 3600),
        ];
    }

    /**
     * Giờ (ISO) các bài khác CÙNG kênh trong khoảng -2..+12 ngày quanh bây giờ, để hộp đổi giờ báo bài trước/sau.
     *
     * @return list<string>
     */
    public function channelTimes(AutoVideo $video, ?Post $post = null): array
    {
        $post ??= $video->post_id ? Post::query()->find($video->post_id) : null;
        $now = CarbonImmutable::now();
        $from = $now->subDays(2);
        $to = $now->addSeconds(ChromeJobs::SCHEDULE_MAX_AHEAD)->addDays(2);

        $ts = $post !== null
            ? $this->busy($video, $post, $from, $to)
            : $this->busyFor($video, null, $from, $to);
        sort($ts);

        return array_map(fn (int $t): string => CarbonImmutable::createFromTimestampUTC($t)->toIso8601String(), array_values(array_unique($ts)));
    }

    /**
     * Dữ liệu gộp cho Lịch đăng: mỗi video -> bài đã nằm trên TikTok chưa, đổi giờ được không, yêu cầu đổi giờ gần nhất.
     *
     * @param  Collection<int, AutoVideo>  $videos
     * @return array<int, array{on_tiktok: bool, held: bool, can_reschedule: bool, reschedule: ?array<string, mixed>}>
     */
    public function calendarInfo(Collection $videos): array
    {
        $postIds = $videos->pluck('post_id')->filter()->unique()->values();

        if ($postIds->isEmpty()) {
            return [];
        }

        $latest = ChromeJob::query()->whereIn('post_id', $postIds)->orderByDesc('attempt')->get(['id', 'post_id', 'state', 'mode', 'attempt', 'result'])
            ->unique('post_id')->keyBy('post_id');
        $requests = Reschedule::query()->whereIn('auto_video_id', $videos->pluck('id'))->where('created_at', '>=', now()->subDay())
            ->orderByDesc('created_at')->get()->unique('auto_video_id')->keyBy('auto_video_id');
        $out = [];

        foreach ($videos as $v) {
            $job = $v->post_id ? ($latest[$v->post_id] ?? null) : null;
            $onTikTok = $job !== null && $job->state === 'posted' && $job->mode === 'scheduled';
            $req = $requests[$v->id] ?? null;
            $future = $v->scheduled_for?->isFuture() ?? false;
            $can = $future && $v->post_id !== null && in_array($v->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED], true)
                && ($job === null || $onTikTok || in_array($job->state, ['queued', 'revoked', 'failed'], true) || ChromeJobs::isQuotaRejection($job));

            $out[$v->id] = [
                'on_tiktok' => $onTikTok || ($req !== null && $req->isOpen()),
                // TikTok đã từ chối vì kênh đầy lịch hẹn: bài vẫn giữ trong app, chờ chỗ trống.
                'held' => ChromeJobs::isQuotaRejection($job),
                'can_reschedule' => $can || ($req !== null && $req->isOpen()),
                'reschedule' => $req ? $this->summary($req) : null,
            ];
        }

        return $out;
    }

    // ---------------------------------------------------------------- Yêu cầu đổi giờ

    /**
     * Kiểm giờ mới theo luật. null = hợp lệ, ngược lại là câu tiếng Việt.
     */
    public function timeRefusal(AutoVideo $video, Post $post, CarbonImmutable $at, ?CarbonImmutable $now = null): ?string
    {
        $now ??= CarbonImmutable::now();
        $at = $at->utc()->second(0);

        if ($post->scheduled_at !== null && CarbonImmutable::instance($post->scheduled_at)->utc()->second(0)->equalTo($at)) {
            return 'Giờ mới trùng giờ hiện tại của bài.';
        }

        if ($at->lessThan($now->addSeconds(self::NEW_MIN_LEAD))) {
            return 'Giờ mới phải cách bây giờ ít nhất '.intdiv(self::NEW_MIN_LEAD, 60).' phút (TikTok đòi hẹn trước tối thiểu 15 phút, Chrome cần thời gian tải video lên).';
        }

        if ($at->greaterThan($now->addSeconds(ChromeJobs::SCHEDULE_MAX_AHEAD))) {
            return 'TikTok chỉ cho hẹn trong vòng 10 ngày — giờ mới tối đa là 9 ngày rưỡi kể từ bây giờ.';
        }

        return null;
    }

    /**
     * Đổi giờ. Trả {state: done|pending, message, id?}. Ném RuntimeException (câu tiếng Việt) khi từ chối; khi đó không đổi gì.
     *
     * @return array{state: string, message: string, id?: string}
     */
    public function request(AutoVideo $video, CarbonImmutable $at): array
    {
        $this->reconcile();
        $at = $at->utc()->second(0);

        if ($this->openFor($video) !== null) {
            throw new RuntimeException('Bài này đang chờ xoá bài hẹn cũ trên TikTok để đổi giờ — chờ xong rồi hãy đổi tiếp.');
        }

        $info = $this->inspect($video);

        if ($info['kind'] === null) {
            throw new RuntimeException((string) $info['reason']);
        }

        $post = $info['post'];

        if (($refusal = $this->timeRefusal($video, $post, $at)) !== null) {
            throw new RuntimeException($refusal);
        }

        if ($info['job'] !== null && (int) ChromeJob::query()->where('post_id', $post->id)->max('attempt') >= ChromeJobs::MAX_ATTEMPTS) {
            throw new RuntimeException('Bài này đã được giao cho Chrome '.ChromeJobs::MAX_ATTEMPTS.' lần — không đổi giờ thêm được (giới hạn chống đăng trùng).');
        }

        return $info['kind'] === 'local'
            ? $this->changeLocal($video, $post, $at)
            : $this->requestDelete($video, $post, $info['job'], $at);
    }

    /**
     * Xoá bài hẹn trên TikTok để sửa bài / bỏ xếp lịch (PostEdits). Cùng an toàn như đổi giờ: chỉ áp thay đổi khi
     * Chrome báo đã xoá VÀ đã kiểm lại. Ném RuntimeException (câu tiếng Việt) khi từ chối.
     *
     * @param  array<string, mixed>  $changes
     * @return array{state: string, message: string, id: string}
     */
    public function requestDeleteFor(AutoVideo $video, Post $post, ChromeJob $job, CarbonImmutable $newAt, string $action, array $changes = []): array
    {
        $this->reconcile();

        if ($this->openFor($video) !== null) {
            throw new RuntimeException('Bài này đang chờ xoá bài hẹn cũ trên TikTok — chờ xong rồi hãy sửa tiếp.');
        }

        return $this->requestDelete($video, $post, $job, $newAt->utc()->second(0), $action, $changes);
    }

    /** @return array{state: string, message: string} */
    private function changeLocal(AutoVideo $video, Post $post, CarbonImmutable $at): array
    {
        if (CarbonImmutable::instance($post->scheduled_at)->lessThan(CarbonImmutable::now()->addSeconds(self::LOCAL_MIN_AHEAD))) {
            throw new RuntimeException('Bài sắp tới giờ đăng — không đổi giờ được nữa.');
        }

        DB::transaction(function () use ($video, $post, $at): void {
            $post = Post::query()->whereKey($post->id)->lockForUpdate()->first();
            $video = AutoVideo::query()->whereKey($video->id)->lockForUpdate()->first();

            if ($post === null || $video === null || $post->status !== PostStatus::Scheduled
                || ! in_array($video->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED], true)) {
                throw new RuntimeException('Bài vừa thay đổi trạng thái — tải lại trang rồi thử lại.');
            }

            $job = $this->chrome->latestForPost($post);

            if ($job !== null && $job->state === 'queued') {
                // Thu hồi có điều kiện: Chrome vừa nhận việc thì thua, và từ chối luôn (đang tải lên).
                $won = ChromeJob::query()->whereKey($job->id)->where('state', 'queued')
                    ->update(['state' => 'revoked', 'note' => ChromePostWatcher::EDIT_NOTE, 'updated_at' => now()]);

                if ($won !== 1) {
                    throw new RuntimeException(self::BUSY_TEXT);
                }
            } elseif ($job !== null && ! in_array($job->state, ['revoked', 'failed'], true) && ! ChromeJobs::isQuotaRejection($job)) {
                throw new RuntimeException($job->state === 'posted' ? 'Bài vừa được hẹn lên TikTok — tải lại trang rồi thử lại.' : self::BUSY_TEXT);
            }

            $post->scheduled_at = $at;
            $post->save();
            $video->forceFill(['scheduled_for' => $at])->save();
        });

        Log::info('Đổi giờ bài chưa lên TikTok.', ['video_id' => $video->id, 'post_id' => $post->id, 'new_at' => $at->toIso8601String()]);
        $this->dispatch((string) $post->social_account_id);

        return ['state' => 'done', 'message' => 'Đã đổi giờ. App sẽ hẹn lên TikTok với giờ mới.'];
    }

    /** @return array{state: string, message: string, id: string} */
    private function requestDelete(AutoVideo $video, Post $post, ChromeJob $job, CarbonImmutable $at, string $action = 'time', array $changes = []): array
    {
        $itemId = (string) data_get($job->result, 'item_id', '');

        if (preg_match('/^[0-9]{5,25}$/', $itemId) !== 1) {
            throw new RuntimeException('App không có mã bài (item id) của bài hẹn này trên TikTok nên không xoá được an toàn — muốn đổi giờ hãy sửa trong TikTok Studio.');
        }

        $oldAt = CarbonImmutable::instance($post->scheduled_at)->utc();

        if ($oldAt->lessThan(CarbonImmutable::now()->addSeconds(self::OLD_MIN_AHEAD))) {
            throw new RuntimeException('Bài sắp tới giờ đăng trên TikTok (dưới '.intdiv(self::OLD_MIN_AHEAD, 60).' phút) — không xoá để đổi giờ được nữa.');
        }

        $social = SocialAccount::query()->find($post->social_account_id);
        $ready = $social ? $this->chrome->readiness($social) : ['ok' => false];

        if (! $ready['ok']) {
            throw new RuntimeException('Chrome của kênh này chưa sẵn sàng (đang tắt, chưa ghép hoặc cần tải lại tiện ích) — mở Chrome rồi thử lại. Chưa đổi gì.');
        }

        $sent = data_get($job->result, 'schedule_time');
        $unix = is_numeric($sent) ? (int) $sent : (($opt = data_get($job->options, 'schedule_time')) ? CarbonImmutable::parse($opt)->getTimestamp() : $oldAt->getTimestamp());

        try {
            $row = Reschedule::query()->create([
                'id' => 'rs_'.bin2hex(random_bytes(12)),
                'auto_video_id' => $video->id,
                'post_id' => $post->id,
                'social_account_id' => $post->social_account_id,
                'chrome_job_id' => $job->id,
                'item_id' => $itemId,
                'expect_user_id' => $job->expect_user_id,
                'old_at' => $oldAt,
                'new_at' => $at,
                'schedule_unix' => $unix,
                'state' => 'pending',
                'nonce' => bin2hex(random_bytes(16)),
                'action' => $action,
                'changes' => $changes === [] ? null : $changes,
            ]);
        } catch (UniqueConstraintViolationException) {
            throw new RuntimeException('Bài này đang chờ xoá bài hẹn cũ trên TikTok — chờ xong rồi hãy sửa tiếp.');
        }

        Log::info('Sửa bài đã hẹn trên TikTok: chờ Chrome xoá bài hẹn cũ.', ['reschedule' => $row->id, 'action' => $action, 'video_id' => $video->id, 'item_id' => $itemId]);

        return ['state' => 'pending', 'message' => 'Đang xoá bài hẹn cũ trên TikTok…', 'id' => $row->id];
    }

    // ---------------------------------------------------------------- Phía tiện ích Chrome (PROTOCOL.md mục 12)

    /**
     * Việc xoá đang chờ Chrome này (kênh gắn với danh tính TikTok của nó), hoặc null.
     *
     * @return array<string, mixed>|null
     */
    public function taskFor(ChromeClient $client): ?array
    {
        if (blank($client->tiktok_user_id)) {
            return null;
        }

        $this->reconcile();
        $bound = $this->chrome->boundAccount((string) $client->tiktok_user_id);

        if ($bound === null) {
            return null;
        }

        $row = Reschedule::query()
            ->where('social_account_id', $bound->social_account_id)
            ->where('expect_user_id', $client->tiktok_user_id)
            ->where(fn ($q) => $q->where('state', 'pending')->orWhere(fn ($c) => $c->where('state', 'claimed')->where('claim_client_id', $client->id)))
            ->orderBy('created_at')
            ->first();

        if ($row === null) {
            return null;
        }

        return [
            'id' => $row->id,
            'nonce' => $row->nonce,
            'item_id' => $row->item_id,
            'expect_user_id' => $row->expect_user_id,
            'expect_account' => $client->tiktok_username,
            'schedule_unix' => $row->schedule_unix,
            'state' => $row->state,
        ];
    }

    /** @return array{ok: bool, state: string, reason?: string} */
    public function claim(string $id, string $nonce, ChromeClient $client): array
    {
        $this->reconcile();
        $row = $this->owned($id, $nonce);

        if ($row->state === 'claimed' && (int) $row->claim_client_id === (int) $client->id) {
            return ['ok' => true, 'state' => 'claimed'];
        }

        if ((string) $client->tiktok_user_id !== $row->expect_user_id) {
            return ['ok' => false, 'state' => $row->state, 'reason' => 'identity-mismatch'];
        }

        if ($row->old_at->lessThan(now()->addSeconds(self::OFFER_UNTIL))) {
            return ['ok' => false, 'state' => $row->state, 'reason' => 'too-late'];
        }

        $won = Reschedule::query()->whereKey($row->id)->where('state', 'pending')->update([
            'state' => 'claimed', 'claim_client_id' => $client->id, 'claimed_at' => now(), 'updated_at' => now(),
        ]);

        return $won === 1 ? ['ok' => true, 'state' => 'claimed'] : ['ok' => false, 'state' => (string) $row->refresh()->state, 'reason' => 'not-pending'];
    }

    /**
     * Kết quả từ tiện ích. Chỉ "deleted" + verified + đúng item_id mới đổi giờ; mọi kết quả khác giữ nguyên tất cả.
     *
     * @param  array<string, mixed>  $body
     * @return array{state: string, duplicate: bool}
     */
    public function ingestResult(string $id, string $nonce, array $body): array
    {
        $row = $this->owned($id, $nonce);
        $outcome = is_string($body['outcome'] ?? null) ? $body['outcome'] : '';
        $keep = [];

        foreach (['outcome', 'verified', 'delete_sent', 'item_id', 'reason', 'detail', 'http', 'status_code', 'status_msg', 'endpoint', 'checks', 'elapsed_ms'] as $k) {
            if (array_key_exists($k, $body) && (is_scalar($body[$k]) || $body[$k] === null)) {
                $keep[$k] = is_string($body[$k]) ? mb_substr($body[$k], 0, 300) : $body[$k];
            }
        }

        $verified = $outcome === 'deleted' && ($body['verified'] ?? null) === true && (string) ($body['item_id'] ?? '') === $row->item_id;
        $applied = null;

        $state = DB::transaction(function () use ($row, $verified, $outcome, $keep, &$applied): ?string {
            $row = Reschedule::query()->whereKey($row->id)->lockForUpdate()->first();

            if (! in_array($row->state, ['claimed', 'unknown', 'pending'], true)) {
                return null;   // kết quả trùng hoặc yêu cầu đã đóng
            }

            if (! $verified) {
                $reason = $outcome === 'unknown' ? 'unknown' : (string) ($keep['reason'] ?? $outcome);
                $state = $outcome === 'unknown' ? 'unknown' : 'failed';
                $text = self::REASONS[$reason] ?? ('Chrome không xoá được bài hẹn cũ ('.mb_substr($reason !== '' ? $reason : 'lỗi', 0, 80).') — giữ nguyên lịch cũ, chưa đổi giờ.');
                $row->forceFill(['state' => $state, 'result' => $keep, 'message' => $text, 'finished_at' => now()])->save();

                return $state;
            }

            $applied = $this->applyDeleted($row);
            $row->forceFill([
                'state' => $applied === null ? 'done' : 'failed',
                'result' => $keep,
                'message' => $applied ?? match ((string) ($row->action ?: 'time')) {
                    'unschedule' => 'Đã xoá bài hẹn trên TikTok (đã kiểm lại) và bỏ xếp lịch — video đã về kho.',
                    'edit' => 'Đã xoá bài hẹn cũ trên TikTok (đã kiểm lại) và lưu thay đổi. App sẽ tải lên lại bản mới.',
                    default => 'Đã xoá bài hẹn cũ trên TikTok (đã kiểm lại). App sẽ tải lên lại với giờ mới.',
                },
                'finished_at' => now(),
            ])->save();

            return (string) $row->state;
        });

        if ($state === null) {
            return ['state' => (string) $row->refresh()->state, 'duplicate' => true];
        }

        Log::info('Đổi giờ: kết quả xoá bài hẹn cũ', ['reschedule' => $row->id, 'outcome' => $outcome, 'verified' => $verified, 'state' => $state]);

        if ($state === 'done') {
            // Sửa bài có thể đã chuyển sang kênh khác: giao bài cho kênh hiện tại của bài.
            $this->dispatch((string) (Post::query()->whereKey($row->post_id)->value('social_account_id') ?? $row->social_account_id));
        }

        return ['state' => $state, 'duplicate' => false];
    }

    /**
     * Bài hẹn cũ ĐÃ được xoá và xác minh: thu hồi job cũ (để bộ giao bài tạo lượt mới) và đặt giờ mới. Gọi trong giao dịch.
     * null = xong; ngược lại là câu cảnh báo (bài trong app đã đổi khác).
     */
    private function applyDeleted(Reschedule $row): ?string
    {
        $job = ChromeJob::query()->whereKey($row->chrome_job_id)->lockForUpdate()->first();
        $post = Post::query()->whereKey($row->post_id)->lockForUpdate()->first();
        $video = AutoVideo::query()->whereKey($row->auto_video_id)->lockForUpdate()->first();

        // Bản trên TikTok đã mất, nên job cũ không còn là "đã hẹn" nữa dù chuyện gì xảy ra tiếp theo.
        $revoked = $job !== null
            ? ChromeJob::query()->whereKey($job->id)->where('state', 'posted')
                ->update(['state' => 'revoked', 'note' => self::NOTE_DELETED.' (item '.$row->item_id.')', 'updated_at' => now()])
            : 0;

        if ($revoked !== 1 || $post === null || $video === null || $post->status !== PostStatus::Scheduled
            || ($job !== null && $this->chrome->latestForPost($post)?->id !== $job->id)
            || ! in_array($video->status, [AutoVideo::SCHEDULED, AutoVideo::RESERVED], true)) {
            Log::error('Đổi giờ: đã xoá bài hẹn cũ trên TikTok nhưng bài trong app đã thay đổi.', ['reschedule' => $row->id]);

            return 'Đã xoá bài hẹn cũ trên TikTok nhưng bài trong app vừa thay đổi nên chưa đặt giờ mới — hãy kiểm tra bài này (có thể cần đăng lại).';
        }

        $action = (string) ($row->action ?: 'time');

        if ($action === 'unschedule') {
            app(PostEdits::class)->unscheduleNow($video, $post);

            return null;
        }

        if ($action === 'edit') {
            return app(PostEdits::class)->applyNow($video, $post, (array) $row->changes, CarbonImmutable::instance($row->new_at));
        }

        $post->scheduled_at = $row->new_at;
        $post->save();
        $video->forceFill(['scheduled_for' => $row->new_at])->save();

        return null;
    }

    /** Hạn chót của các yêu cầu đang mở. Idempotent. */
    public function reconcile(?CarbonImmutable $now = null): void
    {
        $now ??= CarbonImmutable::now();

        Reschedule::query()->where('state', 'pending')
            ->where(fn ($q) => $q->where('created_at', '<', $now->subSeconds(self::PENDING_TTL))->orWhere('old_at', '<', $now->addSeconds(self::OFFER_UNTIL)))
            ->update(['state' => 'expired', 'finished_at' => $now, 'updated_at' => $now,
                'message' => 'Chrome không nhận việc xoá bài hẹn cũ kịp (Chrome tắt hoặc đang bận) — chưa đổi gì, lịch cũ trên TikTok vẫn giữ.']);

        Reschedule::query()->where('state', 'claimed')->where('claimed_at', '<', $now->subSeconds(self::CLAIMED_TTL))
            ->update(['state' => 'unknown', 'finished_at' => $now, 'updated_at' => $now,
                'message' => 'Chrome nhận việc xoá nhưng không báo kết quả — CHƯA đổi giờ. Hãy mở TikTok Studio xem bài hẹn cũ còn hay không.']);
    }

    // ---------------------------------------------------------------- Nội bộ

    public function openFor(AutoVideo $video): ?Reschedule
    {
        return Reschedule::query()->where('auto_video_id', $video->id)->whereIn('state', Reschedule::OPEN)->first();
    }

    /** @return array<string, mixed>|null */
    private function latestSummary(AutoVideo $video): ?array
    {
        $row = Reschedule::query()->where('auto_video_id', $video->id)->orderByDesc('created_at')->first();

        return $row ? $this->summary($row) : null;
    }

    /** @return array<string, mixed> */
    private function summary(Reschedule $row): array
    {
        return [
            'id' => $row->id,
            'state' => $row->state,
            'open' => $row->isOpen(),
            'message' => $row->message ?? ($row->state === 'claimed' ? 'Chrome đang xoá bài hẹn cũ trên TikTok…' : 'Đang chờ Chrome xoá bài hẹn cũ trên TikTok…'),
            'new_at' => $row->new_at?->toIso8601String(),
            'action' => (string) ($row->action ?: 'time'),
            'old_at' => $row->old_at?->toIso8601String(),
            'at' => $row->updated_at?->toIso8601String(),
        ];
    }

    /** Ném InvalidArgumentException với message 'unknown_job' hoặc 'bad_nonce' (bộ điều khiển đổi thành lỗi giao thức). */
    private function owned(string $id, string $nonce): Reschedule
    {
        $row = $id !== '' ? Reschedule::query()->find($id) : null;

        if ($row === null) {
            throw new InvalidArgumentException('unknown_job');
        }

        if ($nonce === '' || ! hash_equals((string) $row->nonce, $nonce)) {
            throw new InvalidArgumentException('bad_nonce');
        }

        return $row;
    }

    private function tz(string $accountId): DateTimeZone
    {
        // Luôn giờ Việt Nam như Planner (múi giờ lưu trên kênh có thể là UTC).
        return Planner::zone();
    }

    /**
     * Mốc giờ của các bài khác CÙNG kênh (video tự động, bài hẹn giờ, giờ mới của yêu cầu đổi giờ đang chạy).
     *
     * @return list<int>
     */
    private function busy(AutoVideo $video, Post $post, CarbonImmutable $from, CarbonImmutable $to): array
    {
        return $this->busyFor($video, $post, $from, $to);
    }

    /** @return list<int> */
    private function busyFor(AutoVideo $video, ?Post $post, CarbonImmutable $from, CarbonImmutable $to): array
    {
        $account = (string) $video->social_account_id;

        $videos = AutoVideo::query()->where('social_account_id', $account)->whereKeyNot($video->id)
            ->whereIn('status', self::COUNTED)->whereBetween('scheduled_for', [$from, $to])->pluck('scheduled_for');
        $posts = Post::query()->where('social_account_id', $account)->when($post !== null, fn ($q) => $q->whereKeyNot($post->id))
            ->where('status', PostStatus::Scheduled)->whereBetween('scheduled_at', [$from, $to])->pluck('scheduled_at');
        $pending = Reschedule::query()->where('social_account_id', $account)->where('auto_video_id', '!=', $video->id)
            ->whereIn('state', Reschedule::OPEN)->whereBetween('new_at', [$from, $to])->pluck('new_at');

        return $videos->merge($posts)->merge($pending)->filter()
            ->map(fn ($t): int => CarbonImmutable::parse($t)->getTimestamp())->values()->all();
    }

    private function dispatch(string $accountId): void
    {
        try {
            $account = SocialAccount::query()->find($accountId);

            if ($account !== null) {
                app(ScheduledDispatcher::class)->dispatchForAccount($account);
            }
        } catch (Throwable $e) {
            report($e);
        }
    }
}

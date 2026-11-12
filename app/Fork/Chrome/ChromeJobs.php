<?php

declare(strict_types=1);

namespace App\Fork\Chrome;

use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeOutcome;
use App\Fork\Chrome\Support\ChromeRefusal;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Services\Social\ContentSanitizer;
use Carbon\CarbonImmutable;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;

/**
 * Máy trạng thái của việc đăng TikTok qua tiện ích Chrome (TikTok Auto Kid), chuyển từ
 * src/web/api/services/ext.py của hệ cũ. Giao thức: extension/autotok/PROTOCOL.md.
 *
 * Luật an toàn:
 *  - authorize và revoke là hai UPDATE có điều kiện, chỉ một bên thắng;
 *  - kết quả đầu tiên được giữ, kết quả trùng chỉ tăng bộ đếm;
 *  - job đã authorized mà quá hạn không có kết quả thì thành uncertain, không bao giờ tự đăng lại;
 *  - không bao giờ đăng thay bằng API TikTok.
 *
 * Mọi hằng số thời gian tính bằng GIÂY.
 */
final class ChromeJobs
{
    public const int PROTOCOL_MIN = 1;

    public const int PROTOCOL_MAX = 1;

    public const int ONLINE_WINDOW = 90;

    public const int SCHEDULE_LEAD = 35 * 60;

    /** Job claimed quá lâu mà chưa có progress thì trả về queued (claim mồ côi). */
    public const int ORPHAN_CLAIM_AFTER = 60;

    /** TikTok chỉ cho hẹn giờ tối đa 10 ngày; giữ 9,5 ngày để còn dư cho thời gian tải video. */
    public const int SCHEDULE_MAX_AHEAD = 9 * 86400 + 43200;

    public const int STALE_AFTER = 120;

    public const int UPLOAD_WITHIN = 15 * 60;

    public const int RESULT_WITHIN = 180;

    public const int PAIR_VALID = 5 * 60;

    public const int PAIR_MAX_TRIES = 5;

    public const int LAUNCH_EVERY = 3 * 60;

    /** Số lần tối đa mở Chrome cho cùng một job. */
    public const int LAUNCH_MAX_PER_JOB = 3;

    /** Số lần tối đa giao cùng một bài cho Chrome. */
    public const int MAX_ATTEMPTS = 3;

    /** Độ dài caption tối đa tiện ích chấp nhận (extension/autotok/lib.js MAX_CAPTION_LENGTH). */
    public const int MAX_CAPTION_LENGTH = 2200;

    /** TikTok cần hẹn giờ cách hiện tại ít nhất 15 phút; tiện ích được phép đẩy lùi tối đa 10 phút. */
    public const int SCHEDULE_MIN_AHEAD = 15 * 60;

    public const int SCHEDULE_MAX_SHIFT = 10 * 60;

    public const string PAIR_CACHE_KEY = 'fork:chrome:pair';

    public const string NO_RESULT_TEXT = 'Chrome đã được phép đăng nhưng không báo kết quả trong 3 phút — có thể đã đăng hoặc chưa; kiểm tra TikTok trước khi thử lại';

    public const string CANCEL_TEXT = 'Chrome đã hủy việc trước khi đăng — chưa đăng';

    public const string STALLED_TEXT = 'Chrome ngừng giữa chừng (không có tín hiệu 2 phút) — chưa đăng';

    public const string TOO_LONG_TEXT = 'Chrome tải quá 15 phút — đã dừng, chưa đăng';

    public const string MISSED_SCHEDULED_TEXT = 'Chrome không mở kịp trước giờ hẹn (cần nhận việc trước giờ hẹn 35 phút) — chưa đăng';

    public const string MISSED_NOW_TEXT = 'Chrome không mở kịp trong thời gian chờ — chưa đăng';

    public const string ANOMALY_TEXT = 'Chrome báo đã đăng khi chưa được cấp quyền — không rõ đã đăng hay chưa; kiểm tra TikTok trước khi thử lại';

    /** Giây một job đăng ngay được chờ Chrome nhận (config fork.chrome.now_claim_within_minutes, mặc định 120 phút). */
    public static function nowClaimWithin(): int
    {
        return max(1, (int) config('fork.chrome.now_claim_within_minutes', 120)) * 60;
    }

    // ---------------------------------------------------------------- Ghép nối và Chrome

    /** @return array{code: string, expires_at: string, valid_s: int} */
    public function newPairCode(string $accountId): array
    {
        $now = CarbonImmutable::now();
        $expires = $now->addSeconds(self::PAIR_VALID);
        $code = sprintf('%06d', random_int(0, 999999));

        Cache::lock(self::PAIR_CACHE_KEY.':lock', 5)->block(3, function () use ($code, $accountId, $expires): void {
            Cache::put(self::PAIR_CACHE_KEY, [
                'code' => $code,
                'account_id' => $accountId,
                'expires_at' => $expires->toIso8601String(),
                'tries' => 0,
            ], $expires);
        });

        return [
            'code' => $code,
            'expires_at' => $expires->utc()->format('Y-m-d\TH:i:s\Z'),
            'valid_s' => self::PAIR_VALID,
        ];
    }

    /** @return array{ok: bool, error: ?string, tries_left: int, account_id: ?string} */
    public function usePairCode(string $code): array
    {
        return Cache::lock(self::PAIR_CACHE_KEY.':lock', 5)->block(3, function () use ($code): array {
            $pair = Cache::get(self::PAIR_CACHE_KEY);
            $now = CarbonImmutable::now();

            if (! is_array($pair) || ! isset($pair['code'], $pair['expires_at']) || $now->greaterThanOrEqualTo(CarbonImmutable::parse($pair['expires_at']))) {
                Cache::forget(self::PAIR_CACHE_KEY);

                return ['ok' => false, 'error' => 'no_code', 'tries_left' => 0, 'account_id' => null];
            }

            if (hash_equals((string) $pair['code'], $code)) {
                Cache::forget(self::PAIR_CACHE_KEY);

                return ['ok' => true, 'error' => null, 'tries_left' => 0, 'account_id' => $pair['account_id'] ?? null];
            }

            $pair['tries'] = (int) ($pair['tries'] ?? 0) + 1;
            $left = self::PAIR_MAX_TRIES - $pair['tries'];

            if ($left <= 0) {
                Cache::forget(self::PAIR_CACHE_KEY);

                return ['ok' => false, 'error' => 'no_code', 'tries_left' => 0, 'account_id' => null];
            }

            Cache::put(self::PAIR_CACHE_KEY, $pair, CarbonImmutable::parse($pair['expires_at']));

            return ['ok' => false, 'error' => 'bad_code', 'tries_left' => $left, 'account_id' => null];
        });
    }

    /** @return array{client: ChromeClient, token: string} */
    public function createClient(string $accountId, string $label, string $extVersion, int $protocol): array
    {
        $token = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');

        $client = ChromeClient::create([
            'account_id' => $accountId,
            'label' => mb_substr($label, 0, 128),
            'token_hash' => hash('sha256', $token),
            'ext_version' => mb_substr($extVersion, 0, 32),
            'protocol' => $protocol,
            'last_seen_at' => CarbonImmutable::now(),
        ]);

        return ['client' => $client, 'token' => $token];
    }

    public function clientForToken(string $token): ?ChromeClient
    {
        if ($token === '') {
            return null;
        }

        return ChromeClient::query()
            ->where('token_hash', hash('sha256', $token))
            ->whereNull('revoked_at')
            ->first();
    }

    /** @param array<string, mixed> $fields */
    public function touch(ChromeClient $c, int $protocol, array $fields = []): void
    {
        $c->forceFill(['last_seen_at' => CarbonImmutable::now(), 'protocol' => $protocol, ...$fields])->save();
    }

    public function protocolOk(int $protocol): bool
    {
        return $protocol >= self::PROTOCOL_MIN && $protocol <= self::PROTOCOL_MAX;
    }

    public function isOnline(ChromeClient $c): bool
    {
        return $c->revoked_at === null
            && $c->last_seen_at !== null
            && CarbonImmutable::now()->diffInSeconds($c->last_seen_at, false) > -self::ONLINE_WINDOW;
    }

    public function inConflict(ChromeClient $c): bool
    {
        return $c->tiktok_user_id !== null
            && $this->onlineClientsFor($c->tiktok_user_id)->contains(fn (ChromeClient $other): bool => $other->id !== $c->id);
    }

    public function boundAccount(?string $tiktokUserId): ?ChromeAccount
    {
        if (blank($tiktokUserId)) {
            return null;
        }

        return ChromeAccount::query()
            ->where('enabled', true)
            ->where('tiktok_user_id', $tiktokUserId)
            ->first();
    }

    /** ok|offline|no_identity|conflict|need_reload */
    public function clientStatus(ChromeClient $c): string
    {
        return match (true) {
            ! $this->protocolOk((int) $c->protocol) => 'need_reload',
            ! $this->isOnline($c) => 'offline',
            blank($c->tiktok_user_id) => 'no_identity',
            $this->inConflict($c) => 'conflict',
            default => 'ok',
        };
    }

    /** @return array{ok: bool, reason: string} */
    public function readiness(SocialAccount $a): array
    {
        $chrome = ChromeAccount::query()->where('social_account_id', $a->id)->where('enabled', true)->first();

        if ($chrome === null || blank($chrome->tiktok_user_id)) {
            return ['ok' => false, 'reason' => 'chrome_unbound'];
        }

        $online = $this->onlineClientsFor($chrome->tiktok_user_id);

        if ($online->isEmpty()) {
            return ['ok' => false, 'reason' => 'chrome_offline'];
        }

        if ($online->count() > 1) {
            return ['ok' => false, 'reason' => 'chrome_conflict'];
        }

        if (! $this->protocolOk((int) $online->first()->protocol)) {
            return ['ok' => false, 'reason' => 'chrome_need_reload'];
        }

        return ['ok' => true, 'reason' => 'ok'];
    }

    public function isChromeAccount(SocialAccount $a): bool
    {
        return ChromeAccount::query()->where('social_account_id', $a->id)->where('enabled', true)->exists();
    }

    // ---------------------------------------------------------------- Job: tạo và đọc

    /**
     * Tạo job ở trạng thái queued. Ném ChromeRefusal (chắc chắn chưa đăng) khi bài không hợp lệ.
     */
    public function queueForPost(Post $post, string $mode): ChromeJob
    {
        if (! in_array($mode, ['scheduled', 'now'], true)) {
            throw new ChromeRefusal('Chế độ giao việc cho Chrome không hợp lệ.');
        }

        // Luôn đọc lại bản mới nhất: bài có thể vừa được sửa sau khi caller nạp nó.
        $post = Post::query()->with('socialAccount')->find($post->id)
            ?? throw new ChromeRefusal('Bài không còn tồn tại — chưa đăng.');

        $account = $post->socialAccount;
        $chrome = $account === null ? null : ChromeAccount::query()
            ->where('social_account_id', $account->id)->where('enabled', true)->first();

        if ($chrome === null || blank($chrome->tiktok_user_id)) {
            throw new ChromeRefusal('Tài khoản này chưa được gắn với Chrome — chưa đăng; hãy bật đăng qua Chrome trong Cài đặt → Kết nối Chrome.');
        }

        $item = $post->media_items->first();

        if ($item === null) {
            throw new ChromeRefusal('Bài không có video — chưa đăng.');
        }

        if ($item->isImage()) {
            throw new ChromeRefusal('Đăng ảnh (photo) qua Chrome chưa được hỗ trợ — chưa đăng.');
        }

        if (! $item->isVideo()) {
            throw new ChromeRefusal('Đăng qua Chrome chỉ hỗ trợ video — chưa đăng.');
        }

        $name = $item->original_filename ?: basename($item->path);
        $ext = strtolower(pathinfo($item->path, PATHINFO_EXTENSION) ?: pathinfo($name, PATHINFO_EXTENSION));
        $mime = ['mp4' => 'video/mp4', 'mov' => 'video/quicktime', 'webm' => 'video/webm'][$ext] ?? null;

        if ($mime === null) {
            throw new ChromeRefusal('Đăng qua Chrome chỉ nhận video mp4, mov hoặc webm — chưa đăng.');
        }

        $latest = $this->latestForPost($post);

        if ($latest !== null && in_array($latest->state, ['authorized', 'uncertain', 'posted'], true)) {
            throw new ChromeRefusal('Chrome đã được cấp quyền hoặc đã đăng bài này (trạng thái '.$latest->state.') — không giao lại để tránh đăng trùng; kiểm tra TikTok trước.');
        }

        if ((int) ChromeJob::query()->where('post_id', $post->id)->max('attempt') >= self::MAX_ATTEMPTS) {
            throw new ChromeRefusal('Đã thử giao cho Chrome '.self::MAX_ATTEMPTS.' lần mà chưa đăng được — kiểm tra Chrome rồi bấm thử lại bằng cách nhân bản bài.');
        }

        $meta = $post->meta ?? [];
        $visibility = match ((string) data_get($meta, 'privacy_level')) {
            'PUBLIC_TO_EVERYONE' => 0,
            'SELF_ONLY' => 1,
            'MUTUAL_FOLLOW_FRIENDS', 'FOLLOWER_OF_CREATOR' => throw new ChromeRefusal('Chế độ hiển thị này chưa hỗ trợ khi đăng qua Chrome (chỉ công khai hoặc riêng tư) — chưa đăng.'),
            default => throw new ChromeRefusal('Chưa chọn chế độ hiển thị cho bài TikTok — chưa đăng.'),
        };

        $now = CarbonImmutable::now();
        $scheduleTime = null;

        if ($mode === 'scheduled') {
            if ($post->scheduled_at === null) {
                throw new ChromeRefusal('Bài chưa có giờ hẹn — chưa đăng.');
            }

            if ($visibility === 1) {
                throw new ChromeRefusal('TikTok không cho hẹn giờ bài ở chế độ riêng tư — chưa đăng; hãy chọn công khai hoặc đăng ngay.');
            }

            $when = CarbonImmutable::instance($post->scheduled_at)->utc();

            if ($when->greaterThan($now->addSeconds(self::SCHEDULE_MAX_AHEAD))) {
                throw new ChromeRefusal('TikTok chỉ cho hẹn giờ trong vòng 10 ngày tới (tối đa 9 ngày rưỡi) — chưa đăng.');
            }

            $deliverBy = $when->subSeconds(self::SCHEDULE_LEAD);

            if ($deliverBy->lessThanOrEqualTo($now)) {
                throw new ChromeRefusal('Giờ hẹn quá gần: TikTok cần hẹn trước ít nhất 15 phút và Chrome cần thời gian tải video — chưa đăng.');
            }

            $scheduleTime = $when->format('Y-m-d\TH:i:s\Z');
        } else {
            $deliverBy = $now->addSeconds(self::nowClaimWithin());
        }

        try {
            $disk = Storage::disk();
            $size = $disk->exists($item->path) ? (int) $disk->size($item->path) : 0;
        } catch (\Throwable) {
            $size = 0;
        }

        if ($size <= 0) {
            throw new ChromeRefusal('Không tìm thấy file video hoặc file rỗng — chưa đăng.');
        }

        $caption = app(ContentSanitizer::class)->forPost($post) ?? '';

        if (trim($caption) === '') {
            throw new ChromeRefusal('Bài không có nội dung (caption) — tiện ích Chrome từ chối caption rỗng; chưa đăng.');
        }

        if (mb_strlen($caption) > self::MAX_CAPTION_LENGTH) {
            throw new ChromeRefusal('Caption dài quá '.self::MAX_CAPTION_LENGTH.' ký tự — chưa đăng.');
        }

        try {
            return DB::transaction(function () use ($post, $account, $chrome, $mode, $item, $name, $mime, $size, $caption, $visibility, $meta, $scheduleTime, $deliverBy): ChromeJob {
                $attempt = (int) ChromeJob::query()->where('post_id', $post->id)->max('attempt') + 1;

                return ChromeJob::create([
                    'id' => 'ej_'.bin2hex(random_bytes(12)),
                    'post_id' => $post->id,
                    'social_account_id' => $account->id,
                    'attempt' => $attempt,
                    'mode' => $mode,
                    'expect_user_id' => $chrome->tiktok_user_id,
                    'media_path' => $item->path,
                    'video_name' => $name,
                    'video_size' => $size,
                    'video_mime' => $mime,
                    'caption' => $caption,
                    'options' => [
                        'visibility_type' => $visibility,
                        'allow_comment' => (int) (bool) data_get($meta, 'allow_comments', false),
                        'allow_duet' => (int) (bool) data_get($meta, 'allow_duet', false),
                        'allow_stitch' => (int) (bool) data_get($meta, 'allow_stitch', false),
                        'ai_label' => (int) (bool) data_get($meta, 'is_aigc', false),
                        'schedule_time' => $scheduleTime,
                    ],
                    'state' => 'queued',
                    'nonce' => bin2hex(random_bytes(16)),
                    'deliver_by' => $deliverBy,
                ])->refresh();
            });
        } catch (UniqueConstraintViolationException) {
            throw new ChromeRefusal('Tài khoản này đang có một bài khác chờ Chrome đăng — chưa đăng bài này.', busy: true);
        }
    }

    public function latestForPost(Post $post): ?ChromeJob
    {
        return ChromeJob::query()->where('post_id', $post->id)->orderByDesc('attempt')->first();
    }

    public function openJobFor(SocialAccount $a): ?ChromeJob
    {
        return ChromeJob::query()
            ->where('social_account_id', $a->id)
            ->whereIn('state', ChromeJob::OPEN)
            ->first();
    }

    /** @return array<string, mixed> */
    public function jobPayload(ChromeJob $j, ChromeClient $c): array
    {
        $opts = $j->options ?? [];
        $when = $opts['schedule_time'] ?? null;

        return [
            'id' => $j->id,
            'nonce' => $j->nonce,
            'claim_token' => $j->claim_token,
            'mode' => 'post',
            'attempt' => $j->attempt,
            'caption' => (string) $j->caption,
            'visibility' => ($opts['visibility_type'] ?? 0) === 1 ? 'private' : 'public',
            'visibility_type' => $opts['visibility_type'] ?? 0,
            'schedule_time' => $when,
            'schedule_unix' => $when ? CarbonImmutable::parse($when)->getTimestamp() : null,
            'options' => [
                'allow_comment' => $opts['allow_comment'] ?? 0,
                'allow_duet' => $opts['allow_duet'] ?? 0,
                'allow_stitch' => $opts['allow_stitch'] ?? 0,
                'ai_label' => $opts['ai_label'] ?? 0,
            ],
            'expect_account' => $c->tiktok_username,
            'expect_user_id' => $j->expect_user_id,
            'video' => ['name' => $j->video_name, 'size' => $j->video_size, 'type' => $j->video_mime ?: 'video/mp4'],
            // K4: sản phẩm giỏ hàng (tuỳ chọn, null nếu bài không gắn sản phẩm). Hợp đồng: AutoPost/KE-HOACH.md.
            'product' => app(ShopSync::class)->payloadFor($j),
            'limits' => [
                'claim_within_s' => 120,
                'heartbeat_every_s' => 60,
                'stale_after_s' => self::STALE_AFTER,
                'upload_within_s' => self::UPLOAD_WITHIN,
                'result_within_s' => self::RESULT_WITHIN,
                'schedule_min_ahead_s' => self::SCHEDULE_MIN_AHEAD,
                'schedule_max_shift_s' => self::SCHEDULE_MAX_SHIFT,
            ],
        ];
    }

    public function outcome(ChromeJob $j): ChromeOutcome
    {
        $r = is_array($j->result) ? $j->result : [];
        $reason = mb_substr((string) ($r['reason'] ?? ''), 0, 200);
        $detail = mb_substr((string) ($r['detail'] ?? ''), 0, 300);

        switch ($j->state) {
            case 'posted':
                $scheduledOpt = $j->options['schedule_time'] ?? null;
                $when = $scheduledOpt ? ($this->parseWhen($r['schedule_time'] ?? null) ?? $this->parseWhen($scheduledOpt)) : null;
                $item = $r['item_id'] ?? null;

                return new ChromeOutcome(
                    ok: true,
                    uncertain: false,
                    message: $when ? 'Đã hẹn giờ đăng trên TikTok' : 'Đã đăng lên TikTok',
                    videoId: ($item !== null && $item !== '') ? (string) $item : null,
                    scheduledFor: $when,
                );
            case 'rejected':
                $code = $r['status_code'] ?? null;
                $msg = mb_substr((string) ($r['status_msg'] ?? ''), 0, 200);

                return new ChromeOutcome(false, false, $code !== null
                    ? 'TikTok từ chối bài đăng (status_code '.$code.($msg !== '' ? ': '.$msg : '').')'
                    : 'TikTok từ chối bài đăng ('.($reason !== '' ? $reason : 'http '.($r['http'] ?? '?')).')');
            case 'uncertain':
                return new ChromeOutcome(false, true, $j->result === null
                    ? self::NO_RESULT_TEXT
                    : 'Không rõ đã đăng hay chưa (Chrome: '.($reason !== '' ? $reason : 'uncertain').') — kiểm tra TikTok trước khi thử lại');
            case 'revoked':
                return new ChromeOutcome(false, false, $j->note ?: self::CANCEL_TEXT);
            case 'failed':
                return new ChromeOutcome(false, false, 'Chrome báo lỗi, chưa đăng: '.($reason !== '' ? $reason : 'failed').($detail !== '' ? ': '.$detail : ''));
            default:
                return new ChromeOutcome(false, false, 'Đang chờ Chrome đăng bài…');
        }
    }

    // ---------------------------------------------------------------- Job: chuyển trạng thái

    public function claimNext(ChromeClient $c): ?ChromeJob
    {
        if ($c->revoked_at !== null || blank($c->tiktok_user_id) || $this->inConflict($c)) {
            return null;
        }

        $accountIds = ChromeAccount::query()
            ->where('enabled', true)
            ->where('tiktok_user_id', $c->tiktok_user_id)
            ->pluck('social_account_id');

        if ($accountIds->isEmpty()) {
            return null;
        }

        $now = CarbonImmutable::now();

        $job = ChromeJob::query()
            ->whereIn('social_account_id', $accountIds)
            ->where('state', 'queued')
            ->where('expect_user_id', $c->tiktok_user_id)
            ->where(fn ($q) => $q->whereNull('deliver_by')->orWhere('deliver_by', '>', $now))
            ->orderBy('created_at')
            ->first();

        if ($job === null) {
            return null;
        }

        $won = ChromeJob::query()->where('id', $job->id)->where('state', 'queued')->update([
            'state' => 'claimed',
            'claim_client_id' => $c->id,
            'claim_token' => bin2hex(random_bytes(16)),
            'claimed_at' => $now,
            'heartbeat_at' => $now,
            'updated_at' => $now,
        ]);

        if ($won !== 1) {
            return null;
        }

        $this->logTransition($job->id, 'queued', 'claimed');

        return $job->refresh();
    }

    /** Hoàn tác một lần nhận mà phản hồi không giao được. */
    public function releaseClaim(ChromeJob $j): bool
    {
        $won = ChromeJob::query()
            ->where('id', $j->id)->where('state', 'claimed')->where('claim_token', $j->claim_token)
            ->update([
                'state' => 'queued',
                'claim_client_id' => null,
                'claim_token' => null,
                'claimed_at' => null,
                'heartbeat_at' => null,
                'updated_at' => CarbonImmutable::now(),
            ]);

        if ($won === 1) {
            $this->logTransition($j->id, 'claimed', 'queued');
        }

        return $won === 1;
    }

    public function heartbeat(ChromeJob $j, bool $ready = false): string
    {
        $now = CarbonImmutable::now();

        // Rào bằng claim_token và nonce: client cũ (token đã xoay) không đẩy được job của client mới.
        $owned = fn () => ChromeJob::query()->where('id', $j->id)
            ->where('claim_token', $j->claim_token)->where('nonce', $j->nonce);

        $owned()->whereIn('state', ChromeJob::RUNNING)
            ->update(['heartbeat_at' => $now, 'updated_at' => $now]);

        $new = $ready ? 'ready' : 'uploading';
        $moved = $owned()
            ->whereIn('state', $ready ? ['claimed', 'uploading'] : ['claimed'])
            ->update(['state' => $new]);

        if ($moved === 1) {
            $this->logTransition($j->id, (string) $j->state, $new);
        }

        return (string) ChromeJob::query()->where('id', $j->id)->value('state');
    }

    public function stateRefusal(ChromeJob $j): ?string
    {
        $j->refresh();

        if ($j->state === 'authorized') {
            return 'already-authorized';
        }

        if ($j->state === 'revoked') {
            return 'revoked';
        }

        if (in_array($j->state, ChromeJob::TERMINAL, true)) {
            return 'terminal';
        }

        if ((int) ChromeJob::query()->where('post_id', $j->post_id)->max('attempt') !== $j->attempt) {
            return 'superseded';
        }

        if ($j->state !== 'ready') {
            return 'not-ready';
        }

        return null;
    }

    /** @param array<string, mixed> $body */
    public function authorizeRefusal(ChromeJob $j, ChromeClient $c, array $body, int $protocol): ?string
    {
        if (! $this->protocolOk($protocol)) {
            return 'need-reload';
        }

        if (($refusal = $this->stateRefusal($j)) !== null) {
            return $refusal;
        }

        $sha = $body['body_sha256'] ?? null;
        $cid = $body['creation_id'] ?? null;

        if (! (is_string($sha) && preg_match('/^[0-9a-f]{64}$/', $sha) === 1) || ! (is_string($cid) && $cid !== '')) {
            return 'bad-binding';
        }

        $identity = is_array($body['identity'] ?? null) ? $body['identity'] : [];

        if ((string) ($identity['user_id'] ?? '') !== $j->expect_user_id || $c->tiktok_user_id !== $j->expect_user_id) {
            return 'identity-mismatch';
        }

        if ($this->inConflict($c)) {
            return 'identity-conflict';
        }

        $opts = $j->options ?? [];

        if (($body['visibility_type'] ?? null) !== ($opts['visibility_type'] ?? null)) {
            return 'visibility-mismatch';
        }

        $sent = $body['schedule_time'] ?? null;
        $wanted = $opts['schedule_time'] ?? null;

        if ($wanted === null) {
            if ($sent !== null) {
                return 'schedule-mismatch';
            }
        } else {
            $target = CarbonImmutable::parse($wanted)->getTimestamp();

            if (! is_int($sent)) {
                return 'schedule-mismatch';
            }

            $earliest = CarbonImmutable::now()->getTimestamp() + self::SCHEDULE_MIN_AHEAD - 60;

            if (! ($sent >= $target && $sent <= $target + self::SCHEDULE_MAX_SHIFT) || $sent < $earliest) {
                return 'schedule-mismatch';
            }
        }

        return null;
    }

    /** Một UPDATE có điều kiện duy nhất cấp quyền đăng. */
    public function authorize(ChromeJob $j, string $sha, string $creationId): bool
    {
        $now = CarbonImmutable::now();

        $won = ChromeJob::query()
            ->where('id', $j->id)
            ->where('state', 'ready')
            ->where('claim_token', $j->claim_token)
            ->where('nonce', $j->nonce)
            ->whereRaw('attempt = (select max(x.attempt) from fork_chrome_jobs x where x.post_id = fork_chrome_jobs.post_id)')
            ->update([
                'state' => 'authorized',
                'authorized_at' => $now,
                'auth_sha' => $sha,
                'auth_creation_id' => $creationId,
                'updated_at' => $now,
            ]);

        if ($won === 1) {
            $this->logTransition($j->id, 'ready', 'authorized');
        }

        return $won === 1;
    }

    /**
     * Lưu kết quả đầu tiên. Kết quả sau chỉ tăng bộ đếm. Báo "đã đăng" khi chưa được cấp quyền
     * thì KHÔNG BAO GIỜ thành posted mà thành uncertain.
     *
     * @param  array<string, mixed>  $body
     * @return array{duplicate: bool, state: string}
     */
    public function ingestResult(string $jobId, array $body): array
    {
        $outcome = (string) ($body['outcome'] ?? '');
        $notSent = ($body['not_sent'] ?? null) === true || ($body['notSent'] ?? null) === true;

        $keep = [];
        foreach (['outcome', 'definite', 'reason', 'detail', 'http', 'status_code', 'status_msg', 'item_id', 'creation_id', 'video_id', 'schedule_time', 'elapsed_ms', 'authorized'] as $key) {
            if (array_key_exists($key, $body) && (is_scalar($body[$key]) || $body[$key] === null)) {
                $keep[$key] = $body[$key];
            }
        }
        $keep['not_sent'] = $notSent;

        for ($try = 0; $try < 3; $try++) {
            $job = ChromeJob::query()->find($jobId) ?? throw (new ModelNotFoundException)->setModel(ChromeJob::class, [$jobId]);

            if ($job->result !== null) {
                ChromeJob::query()->where('id', $jobId)->increment('duplicate_results');
                Log::info('chrome: kết quả trùng bị bỏ qua', ['job' => $jobId, 'outcome' => $outcome]);

                return ['duplicate' => true, 'state' => (string) $job->state];
            }

            $old = (string) $job->state;

            if (in_array($old, ['authorized', 'uncertain'], true)) {
                $new = match ($outcome) {
                    'posted' => 'posted',
                    'rejected' => 'rejected',
                    'uncertain' => 'uncertain',
                    'failed' => $notSent ? 'failed' : 'uncertain',
                    default => 'uncertain',
                };
            } elseif (in_array($old, ChromeJob::PRE_AUTH, true)) {
                if (in_array($outcome, ['posted', 'uncertain'], true)) {
                    // Cổng bị vượt: có thể đã đăng thật. Không bao giờ coi là posted, cũng không đăng lại.
                    $new = 'uncertain';
                    Log::error('chrome: job báo kết quả khi chưa được cấp quyền', ['job' => $jobId, 'outcome' => $outcome, 'state' => $old]);
                } else {
                    $new = 'failed';
                }
            } else {
                $new = $old;

                if ($old === 'revoked' && in_array($outcome, ['posted', 'uncertain'], true)) {
                    $new = 'uncertain';
                    Log::error('chrome: job đã thu hồi nhưng Chrome báo đã đăng', ['job' => $jobId, 'outcome' => $outcome]);
                }
            }

            $set = ['state' => $new, 'result' => json_encode($keep, JSON_UNESCAPED_UNICODE), 'result_at' => CarbonImmutable::now(), 'updated_at' => CarbonImmutable::now()];

            if ($new === 'uncertain' && ! in_array($old, ['authorized', 'uncertain'], true)) {
                $set['note'] = self::ANOMALY_TEXT;
            }

            $won = ChromeJob::query()->where('id', $jobId)->where('state', $old)->whereNull('result')->update($set);

            if ($won !== 1) {
                continue;
            }

            if ($new !== $old) {
                $this->logTransition($jobId, $old, $new);
            }

            if ($new === 'posted' && $job->mode === 'scheduled') {
                $this->dispatchNext((string) $job->social_account_id);
            }

            return ['duplicate' => false, 'state' => $new];
        }

        throw new \RuntimeException("Không lưu được kết quả của job {$jobId} sau nhiều lần thử.");
    }

    /** Job hẹn giờ vừa xong: giao ngay bài hẹn kế tiếp của tài khoản (không đợi cron mỗi phút). Lỗi ở đây không được làm hỏng việc lưu kết quả. */
    private function dispatchNext(string $accountId): void
    {
        try {
            $account = SocialAccount::query()->find($accountId);

            if ($account !== null) {
                app(ScheduledDispatcher::class)->dispatchForAccount($account);
            }
        } catch (\Throwable $e) {
            report($e);
        }
    }

    /** Chỉ thắng khi job còn trước bước cấp quyền. */
    public function revoke(string $jobId, string $note): bool
    {
        $won = ChromeJob::query()->where('id', $jobId)->whereIn('state', ChromeJob::PRE_AUTH)
            ->update(['state' => 'revoked', 'note' => $note, 'updated_at' => CarbonImmutable::now()]);

        if ($won === 1) {
            Log::info('chrome-transition', ['job' => $jobId, 'to' => 'revoked', 'note' => $note]);
        }

        return $won === 1;
    }

    /** @return array{state: string, cancel_recorded: bool} */
    public function requestCancel(ChromeJob $j, ?string $reason): array
    {
        $reason = trim((string) $reason);
        $note = str_starts_with($reason, self::CANCEL_TEXT)
            ? $reason
            : self::CANCEL_TEXT.($reason !== '' ? ' ('.mb_substr($reason, 0, 120).')' : '');

        if ($this->revoke($j->id, $note)) {
            return ['state' => 'revoked', 'cancel_recorded' => false];
        }

        $j->refresh();

        if ($j->state === 'authorized' && ! $j->cancel_requested) {
            // Chỉ ghi lại: quyền đã cấp thì không thu hồi được.
            ChromeJob::query()->where('id', $j->id)->where('state', 'authorized')->update(['cancel_requested' => true]);
            $j->refresh();
        }

        return ['state' => (string) $j->state, 'cancel_recorded' => $j->state === 'authorized'];
    }

    /** Xử lý các hạn chót. Idempotent, an toàn khi chạy đồng thời. */
    public function reconcile(?CarbonImmutable $now = null): void
    {
        $now ??= CarbonImmutable::now();

        // Job nhận không kịp.
        foreach (['scheduled' => self::MISSED_SCHEDULED_TEXT, 'now' => self::MISSED_NOW_TEXT] as $mode => $text) {
            ChromeJob::query()->where('state', 'queued')->where('mode', $mode)->where('deliver_by', '<', $now)
                ->update(['state' => 'revoked', 'note' => $text, 'updated_at' => $now]);
        }

        // Claim mồ côi: đã nhận mà 60 giây chưa có progress. Chưa tới authorize nên an toàn;
        // xoay claim_token và nonce để client cũ gọi lại sẽ bị 403.
        ChromeJob::query()->where('state', 'claimed')
            ->where('claimed_at', '<', $now->subSeconds(self::ORPHAN_CLAIM_AFTER))
            ->where('deliver_by', '>', $now)
            ->get(['id', 'claim_token'])
            ->each(function (ChromeJob $o) use ($now): void {
                $won = ChromeJob::query()->where('id', $o->id)->where('state', 'claimed')->where('claim_token', $o->claim_token)
                    ->update([
                        'state' => 'queued',
                        'claim_client_id' => null,
                        'claim_token' => null,
                        'nonce' => bin2hex(random_bytes(16)),
                        'claimed_at' => null,
                        'heartbeat_at' => null,
                        'updated_at' => $now,
                    ]);

                if ($won === 1) {
                    $this->logTransition($o->id, 'claimed', 'queued');
                }
            });

        // Đang chạy mà quá lâu hoặc mất tín hiệu.
        ChromeJob::query()->whereIn('state', ChromeJob::RUNNING)
            ->where('claimed_at', '<', $now->subSeconds(self::UPLOAD_WITHIN))
            ->update(['state' => 'revoked', 'note' => self::TOO_LONG_TEXT, 'updated_at' => $now]);

        ChromeJob::query()->whereIn('state', ChromeJob::RUNNING)
            ->whereRaw('coalesce(heartbeat_at, claimed_at, created_at) < ?', [$now->subSeconds(self::STALE_AFTER)->toDateTimeString()])
            ->update(['state' => 'revoked', 'note' => self::STALLED_TEXT, 'updated_at' => $now]);

        // Đã cấp quyền mà không có kết quả: có thể đã đăng, không bao giờ đăng lại.
        $uncertain = ChromeJob::query()->where('state', 'authorized')->whereNull('result')
            ->where('authorized_at', '<', $now->subSeconds(self::RESULT_WITHIN))
            ->update(['state' => 'uncertain', 'note' => self::NO_RESULT_TEXT, 'updated_at' => $now]);

        if ($uncertain > 0) {
            Log::warning('chrome: job đã cấp quyền nhưng không có kết quả, chuyển uncertain', ['count' => $uncertain]);
        }
    }

    // ---------------------------------------------------------------- Mở Chrome (trợ lý Windows)

    /** @return list<array{client_id: int, profile_dir: string, browser: string, job_id: string}> */
    public function launchRequests(?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $requests = [];
        $usedClients = [];

        $jobs = ChromeJob::query()
            ->where('state', 'queued')
            ->where(fn ($q) => $q->whereNull('deliver_by')->orWhere('deliver_by', '>', $now))
            ->where(fn ($q) => $q->whereNull('launched_at')->orWhere('launched_at', '<', $now->subSeconds(self::LAUNCH_EVERY)))
            ->orderBy('created_at')
            ->get();

        foreach ($jobs as $job) {
            if ((int) Cache::get($this->launchCountKey($job->id), 0) >= self::LAUNCH_MAX_PER_JOB) {
                continue;
            }

            $clients = ChromeClient::query()
                ->where('tiktok_user_id', $job->expect_user_id)
                ->whereNull('revoked_at')
                ->get();

            if ($clients->contains(fn (ChromeClient $c): bool => $this->isOnline($c))) {
                continue;
            }

            $known = $clients->filter(fn (ChromeClient $c): bool => filled($c->chrome_profile_dir))
                ->sortByDesc(fn (ChromeClient $c) => $c->last_seen_at?->getTimestamp() ?? 0)
                ->first();

            if ($known === null || isset($usedClients[$known->id])) {
                continue;
            }

            if ($known->last_launch_at !== null && $known->last_launch_at->greaterThan($now->subSeconds(self::LAUNCH_EVERY))) {
                continue;
            }

            $usedClients[$known->id] = true;
            $requests[] = ['client_id' => (int) $known->id, 'profile_dir' => (string) $known->chrome_profile_dir, 'browser' => $known->chrome_browser ?: 'chrome', 'job_id' => $job->id];
        }

        return $requests;
    }

    public function markLaunched(int $clientId, string $jobId): void
    {
        $now = CarbonImmutable::now();

        ChromeClient::query()->where('id', $clientId)->update(['last_launch_at' => $now]);
        ChromeJob::query()->where('id', $jobId)->where('state', 'queued')->update(['launched_at' => $now]);

        $key = $this->launchCountKey($jobId);
        Cache::put($key, (int) Cache::get($key, 0) + 1, 86400);
    }

    // ---------------------------------------------------------------- Nội bộ

    /** @return Collection<int, ChromeClient> */
    private function onlineClientsFor(?string $userId): Collection
    {
        if (blank($userId)) {
            return collect();
        }

        return ChromeClient::query()
            ->where('tiktok_user_id', $userId)
            ->whereNull('revoked_at')
            ->get()
            ->filter(fn (ChromeClient $c): bool => $this->isOnline($c))
            ->values();
    }

    private function launchCountKey(string $jobId): string
    {
        return 'fork:chrome:launches:'.$jobId;
    }

    private function logTransition(string $jobId, string $old, string $new): void
    {
        Log::info('chrome-transition', ['job' => $jobId, 'from' => $old, 'to' => $new]);
    }

    private function parseWhen(mixed $raw): ?CarbonImmutable
    {
        if ($raw === null || $raw === '') {
            return null;
        }

        try {
            return is_int($raw) || (is_string($raw) && ctype_digit($raw))
                ? CarbonImmutable::createFromTimestampUTC((int) $raw)
                : CarbonImmutable::parse((string) $raw)->utc();
        } catch (\Throwable) {
            return null;
        }
    }
}

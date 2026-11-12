<?php

declare(strict_types=1);

use App\Enums\Post\PublishStatus;
use App\Enums\Post\Status as PostStatus;
use App\Enums\PostPlatform\ContentType;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Exceptions\PlatformUnavailableException;
use App\Exceptions\Social\TikTokPublishException;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Publishing\ChromeAwareTikTokPublisher;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;

beforeEach(function () {
    ChromePostWatcher::register();
    Storage::fake();
    Storage::put('media/v.mp4', 'video-bytes');

    $this->user = User::factory()->create();
    $this->workspace = Workspace::factory()->create(['user_id' => $this->user->id]);
    $this->chrome = app(ChromeJobs::class);

    $this->makeAccount = function (bool $chromeEnabled = true, bool $chromeOnly = false): SocialAccount {
        $account = SocialAccount::factory()->tiktok()->create([
            'workspace_id' => $this->workspace->id,
            'username' => 'tiktoker',
            'status' => AccountStatus::Connected,
        ]);

        if ($chromeEnabled) {
            ChromeAccount::create([
                'social_account_id' => $account->id,
                'enabled' => true,
                'tiktok_user_id' => '777'.random_int(100, 999),
                'chrome_only' => $chromeOnly,
            ]);
        }

        return $account;
    };

    $this->makePost = function (SocialAccount $account, array $attributes = [], array $meta = []): Post {
        $post = Post::factory()->forAccount($account)->tiktok()->create([
            'user_id' => $this->user->id,
            'content' => 'Xin chào TikTok',
            'content_type' => ContentType::TikTokVideo,
            'media' => [[
                'id' => 'm1',
                'path' => 'media/v.mp4',
                'url' => 'https://example.com/media/v.mp4',
                'mime_type' => 'video/mp4',
                'original_filename' => 'v.mp4',
            ]],
            'meta' => ['privacy_level' => 'PUBLIC_TO_EVERYONE', ...$meta],
            ...$attributes,
        ]);
        $post->setRelation('socialAccount', $account);

        return $post;
    };

    $this->publisher = fn (): ChromeAwareTikTokPublisher => app(ChromeAwareTikTokPublisher::class);
});

test('a Chrome account with no job gets a now job and waits for Chrome', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);

    try {
        ($this->publisher)()->publish($post);
        $this->fail('Phải ném PlatformUnavailableException');
    } catch (PlatformUnavailableException $e) {
        expect($e->retryDelaySeconds)->toBe(60)
            ->and($e->maxRetries)->toBe(420)
            ->and($e->getMessage())->toContain('Đang chờ Chrome');
    }

    $job = $this->chrome->latestForPost($post);
    expect($job)->not->toBeNull()
        ->and($job->mode)->toBe('now')
        ->and($job->state)->toBe('queued');
});

test('an open job keeps the post waiting without creating another job', function (string $state) {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => $state]);

    expect(fn () => ($this->publisher)()->publish($post))->toThrow(PlatformUnavailableException::class);
    expect(ChromeJob::query()->count())->toBe(1);
})->with(['queued', 'claimed', 'uploading', 'ready', 'authorized']);

test('a posted job returns the video id and url', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'posted', 'result' => ['item_id' => '7300000000000000001']]);

    $result = ($this->publisher)()->publish($post);

    expect($result['id'])->toBe('7300000000000000001')
        ->and($result['url'])->toBe('https://www.tiktok.com/@tiktoker/video/7300000000000000001');
});

test('a posted job without an item id falls back to the job id', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'posted', 'result' => []]);

    $result = ($this->publisher)()->publish($post);

    expect($result['id'])->toBe($job->id)
        ->and($result['url'])->toBe('https://www.tiktok.com/@tiktoker');
});

test('an uncertain job fails for good and never creates a new job', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'uncertain', 'note' => ChromeJobs::NO_RESULT_TEXT]);

    expect(fn () => ($this->publisher)()->publish($post))
        ->toThrow(TikTokPublishException::class, 'kiểm tra TikTok');

    expect(ChromeJob::query()->count())->toBe(1);
});

test('a rejected or failed job fails for good with the outcome message', function (string $state) {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => $state, 'authorized_at' => now(), 'result' => ['reason' => 'boom', 'status_code' => 10]]);

    expect(fn () => ($this->publisher)()->publish($post))->toThrow(TikTokPublishException::class);
    expect(ChromeJob::query()->count())->toBe(1);
})->with(['rejected', 'failed']);

test('a Chrome refusal becomes a definite publish failure', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, [], ['privacy_level' => 'MUTUAL_FOLLOW_FRIENDS']);

    expect(fn () => ($this->publisher)()->publish($post))
        ->toThrow(TikTokPublishException::class, 'chưa hỗ trợ');
});

test('a scheduled job that expired is replaced by a now job', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(2)]);
    $old = $this->chrome->queueForPost($post, 'scheduled');
    $old->update(['state' => 'revoked', 'note' => ChromeJobs::MISSED_SCHEDULED_TEXT]);

    expect(fn () => ($this->publisher)()->publish($post))->toThrow(PlatformUnavailableException::class);

    $latest = $this->chrome->latestForPost($post);
    expect($latest->id)->not->toBe($old->id)
        ->and($latest->mode)->toBe('now')
        ->and($latest->attempt)->toBe(2);
});

test('a scheduled job Chrome reports as schedule-expired is replaced by a now job', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(2)]);
    $old = $this->chrome->queueForPost($post, 'scheduled');
    $old->update(['state' => 'failed', 'result' => ['not_sent' => true, 'reason' => 'schedule-expired']]);

    expect(fn () => ($this->publisher)()->publish($post))->toThrow(PlatformUnavailableException::class);
    expect($this->chrome->latestForPost($post)->mode)->toBe('now');
});

test('a failed job that sent nothing gets a new attempt', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(2)]);
    $old = $this->chrome->queueForPost($post, 'scheduled');
    $old->update(['state' => 'failed', 'result' => ['not_sent' => true, 'reason' => 'upload-error']]);

    expect(fn () => ($this->publisher)()->publish($post))->toThrow(PlatformUnavailableException::class);
    expect(ChromeJob::query()->count())->toBe(2);
});

test('a job the user cancelled is not queued again', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(2)]);
    $old = $this->chrome->queueForPost($post, 'scheduled');
    $this->chrome->requestCancel($old, 'người dùng huỷ');

    expect(fn () => ($this->publisher)()->publish($post))->toThrow(TikTokPublishException::class);
    expect(ChromeJob::query()->count())->toBe(1);
});

test('a now job that was not picked up in time gets a new attempt', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'revoked', 'note' => ChromeJobs::MISSED_NOW_TEXT]);

    expect(fn () => ($this->publisher)()->publish($post))->toThrow(PlatformUnavailableException::class);
    expect(ChromeJob::query()->where('post_id', $post->id)->count())->toBe(2);
});

test('dispatch queues the earliest scheduled post inside the window as a scheduled job', function () {
    $account = ($this->makeAccount)();
    $tooSoon = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addMinutes(30)]);
    $inWindow = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    $later = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addDays(2)]);
    $tooFar = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addDays(40)]);

    $this->artisan('fork:chrome-dispatch')->assertExitCode(0);

    expect(ChromeJob::query()->count())->toBe(1);
    $job = $this->chrome->latestForPost($inWindow);
    expect($job)->not->toBeNull()
        ->and($job->mode)->toBe('scheduled')
        ->and($job->options['schedule_time'])->not->toBeNull()
        ->and($this->chrome->latestForPost($tooSoon))->toBeNull()
        ->and($this->chrome->latestForPost($later))->toBeNull()
        ->and($this->chrome->latestForPost($tooFar))->toBeNull()
        ->and($inWindow->fresh()->status)->toBe(PostStatus::Scheduled);
});

test('dispatch gives an account with an open job nothing new', function () {
    $account = ($this->makeAccount)();
    $first = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(5)]);

    $this->artisan('fork:chrome-dispatch');
    $this->artisan('fork:chrome-dispatch');

    expect(ChromeJob::query()->count())->toBe(1)
        ->and($this->chrome->latestForPost($first))->not->toBeNull();
});

test('dispatch moves on to the next post once the earlier one has its job', function () {
    $account = ($this->makeAccount)();
    $first = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    $second = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(5)]);

    $this->artisan('fork:chrome-dispatch');
    $this->chrome->latestForPost($first)->update(['state' => 'posted', 'result' => ['schedule_time' => now()->addHours(3)->toIso8601ZuluString()]]);
    $this->artisan('fork:chrome-dispatch');

    expect($this->chrome->latestForPost($second))->not->toBeNull()
        ->and(ChromeJob::query()->count())->toBe(2);
});

test('dispatch skips posts Chrome cannot take without creating a job', function () {
    $account = ($this->makeAccount)();
    ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)], ['privacy_level' => 'SELF_ONLY']);
    $ok = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(5)]);

    $this->artisan('fork:chrome-dispatch')->assertExitCode(0);

    expect(ChromeJob::query()->count())->toBe(1)
        ->and($this->chrome->latestForPost($ok))->not->toBeNull();
});

test('dispatch ignores accounts that do not use Chrome', function () {
    $account = ($this->makeAccount)(chromeEnabled: false);
    ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);

    $this->artisan('fork:chrome-dispatch');

    expect(ChromeJob::query()->count())->toBe(0);
});

test('dispatch queues an edited post again', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    $this->artisan('fork:chrome-dispatch');
    $post->update(['content' => 'Đã sửa']);
    expect($this->chrome->latestForPost($post)->state)->toBe('revoked');

    $this->artisan('fork:chrome-dispatch');

    $latest = $this->chrome->latestForPost($post);
    expect($latest->attempt)->toBe(2)
        ->and($latest->state)->toBe('queued')
        ->and($latest->caption)->toBe('Đã sửa');
});

test('dispatch marks a failed post as published when Chrome later confirms the post', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Failed, 'publish_status' => PublishStatus::Failed]);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'posted', 'result' => ['item_id' => '7300000000000000002'], 'result_at' => now()]);

    $this->artisan('fork:chrome-dispatch')->assertExitCode(0);

    $post->refresh();
    expect($post->status)->toBe(PostStatus::Published)
        ->and($post->publish_status)->toBe(PublishStatus::Published)
        ->and($post->platform_post_id)->toBe('7300000000000000002')
        ->and($post->platform_url)->toBe('https://www.tiktok.com/@tiktoker/video/7300000000000000002');
});

test('dispatch leaves a failed post alone when the job is not posted', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Failed, 'publish_status' => PublishStatus::Failed]);
    $this->chrome->queueForPost($post, 'now')->update(['state' => 'uncertain']);

    $this->artisan('fork:chrome-dispatch');

    expect($post->fresh()->status)->toBe(PostStatus::Failed);
});

test('the reconcile command runs the deadlines', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['deliver_by' => now()->subMinute()]);

    $this->artisan('fork:chrome-reconcile')->assertExitCode(0);

    expect($job->fresh()->state)->toBe('revoked');
});

test('editing a post revokes a job that is still before authorization', function (string $field) {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    $job = $this->chrome->queueForPost($post, 'scheduled');

    match ($field) {
        'content' => $post->update(['content' => 'Bản mới']),
        'scheduled_at' => $post->update(['scheduled_at' => now()->addHours(6)]),
        'meta' => $post->update(['meta' => ['privacy_level' => 'SELF_ONLY']]),
        'media' => $post->update(['media' => []]),
    };

    $job->refresh();
    expect($job->state)->toBe('revoked')
        ->and($job->note)->toStartWith('Bài đã được sửa');
})->with(['content', 'scheduled_at', 'meta', 'media']);

test('saving a post without changing what is published keeps the job', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    $job = $this->chrome->queueForPost($post, 'scheduled');

    $post->update(['platform_name' => 'Tên khác']);

    expect($job->fresh()->state)->toBe('queued');
});

test('editing does not take back an authorized job', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    $job = $this->chrome->queueForPost($post, 'scheduled');
    $job->update(['state' => 'authorized']);

    $post->update(['content' => 'Bản mới']);

    expect($job->fresh()->state)->toBe('authorized');
});

test('editing a post already scheduled on TikTok only adds a warning to the job', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    $job = $this->chrome->queueForPost($post, 'scheduled');
    $job->update(['state' => 'posted', 'result' => ['item_id' => '1']]);

    $post->update(['content' => 'Bản mới']);

    $job->refresh();
    expect($job->state)->toBe('posted')
        ->and($job->note)->toContain('TikTok Studio');
});

test('moving a scheduled post back to draft revokes its job', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    $job = $this->chrome->queueForPost($post, 'scheduled');

    $post->update(['status' => PostStatus::Draft]);

    expect($job->fresh()->state)->toBe('revoked');
});

test('deleting a post revokes its job before the row goes', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(3)]);
    $job = $this->chrome->queueForPost($post, 'scheduled');
    $revoked = null;
    Event::listen('eloquent.deleted: '.Post::class, function () use ($job, &$revoked) {
        $revoked = $job->fresh()?->state;
    });

    $post->delete();

    expect($revoked)->toBeIn(['revoked', null]);
    expect(ChromeJob::query()->whereKey($job->id)->exists())->toBeFalse();
});

test('a post with a Chrome job never falls back to the API when the switch is turned off', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'authorized', 'authorized_at' => now()]);
    ChromeAccount::query()->where('social_account_id', $account->id)->update(['enabled' => false]);
    Http::fake();

    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($post->refresh()->setRelation('socialAccount', $account->refresh())))
        ->toThrow(PlatformUnavailableException::class);
    Http::assertNothingSent();
});

test('switch off with a surely-unsent latest job fails firmly without the API', function () {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'revoked', 'note' => ChromeJobs::STALLED_TEXT]);
    ChromeAccount::query()->where('social_account_id', $account->id)->update(['enabled' => false]);
    Http::fake();

    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($post->refresh()->setRelation('socialAccount', $account->refresh())))
        ->toThrow(TikTokPublishException::class, 'tạo lại bài');
    Http::assertNothingSent();
    expect(ChromeJob::query()->where('post_id', $post->id)->count())->toBe(1);
});

test('a busy refusal waits instead of failing', function () {
    $account = ($this->makeAccount)();
    $this->chrome->queueForPost(($this->makePost)($account), 'now');
    $second = ($this->makePost)($account);

    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($second))->toThrow(PlatformUnavailableException::class);
});

test('now jobs that surely sent nothing get a new attempt, user cancel and rejected do not', function (string $state, array $extra, bool $again) {
    $account = ($this->makeAccount)();
    $post = ($this->makePost)($account);
    $this->chrome->queueForPost($post, 'now')->update(['state' => $state, ...$extra]);

    try {
        app(ChromeAwareTikTokPublisher::class)->publish($post);
    } catch (PlatformUnavailableException|TikTokPublishException) {
    }

    expect(ChromeJob::query()->where('post_id', $post->id)->count())->toBe($again ? 2 : 1);
})->with([
    'missed' => ['revoked', ['note' => ChromeJobs::MISSED_NOW_TEXT], true],
    'stalled' => ['revoked', ['note' => ChromeJobs::STALLED_TEXT], true],
    'too long' => ['revoked', ['note' => ChromeJobs::TOO_LONG_TEXT], true],
    'failed not sent' => ['failed', ['result' => ['not_sent' => true]], true],
    'cancelled' => ['revoked', ['note' => ChromeJobs::CANCEL_TEXT], false],
    'rejected' => ['rejected', ['result' => ['outcome' => 'rejected']], false],
    'uncertain' => ['uncertain', [], false],
]);

describe('dispatch đồng bộ giờ', function () {
    $iso = fn ($t) => $t->copy()->utc()->format('Y-m-d\TH:i:s\Z');

    test('đổi scheduled_at bằng Builder::update thì dispatch thu hồi job cũ và giao lại đúng giờ mới', function () use ($iso) {
        $account = ($this->makeAccount)();
        $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(5)->startOfMinute()]);
        $this->artisan('fork:chrome-dispatch')->assertSuccessful();
        $job = $this->chrome->latestForPost($post);
        expect($job->state)->toBe('queued');

        $new = now()->addHours(9)->startOfMinute();
        Post::query()->whereKey($post->id)->update(['scheduled_at' => $new]);

        $this->artisan('fork:chrome-dispatch')->assertSuccessful();

        $old = ChromeJob::find($job->id);
        expect($old->state)->toBe('revoked')->and(ChromePostWatcher::isEditNote($old->note))->toBeTrue();
        $latest = $this->chrome->latestForPost($post);
        expect($latest->attempt)->toBe(2)->and($latest->state)->toBe('queued')
            ->and($latest->options['schedule_time'])->toBe($iso($new));
    });

    test('bài không còn Scheduled (update thẳng) thì job trước authorize bị thu hồi', function () {
        $account = ($this->makeAccount)();
        $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(5)->startOfMinute()]);
        $this->artisan('fork:chrome-dispatch');
        $job = $this->chrome->latestForPost($post);
        $job->update(['state' => 'ready']);

        Post::query()->whereKey($post->id)->update(['status' => PostStatus::Draft]);
        $this->artisan('fork:chrome-dispatch');

        expect(ChromeJob::find($job->id)->state)->toBe('revoked')
            ->and(ChromeJob::where('post_id', $post->id)->count())->toBe(1);
    });

    test('giờ không đổi thì không thu hồi', function () {
        $account = ($this->makeAccount)();
        $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(5)->startOfMinute()]);
        $this->artisan('fork:chrome-dispatch');
        $this->artisan('fork:chrome-dispatch');

        expect(ChromeJob::where('post_id', $post->id)->count())->toBe(1)
            ->and($this->chrome->latestForPost($post)->state)->toBe('queued');
    });

    test('job đã posted mà giờ lệch thì chỉ ghi cảnh báo, không thu hồi', function () {
        $account = ($this->makeAccount)();
        $post = ($this->makePost)($account, ['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHours(5)->startOfMinute()]);
        $this->artisan('fork:chrome-dispatch');
        $job = $this->chrome->latestForPost($post);
        $job->update(['state' => 'posted', 'result_at' => now()]);

        Post::query()->whereKey($post->id)->update(['scheduled_at' => now()->addHours(9)->startOfMinute()]);
        $this->artisan('fork:chrome-dispatch');
        $this->artisan('fork:chrome-dispatch');

        $fresh = ChromeJob::find($job->id);
        expect($fresh->state)->toBe('posted')->and($fresh->note)->toBe(ChromePostWatcher::SCHEDULED_WARNING)
            ->and(ChromeJob::where('post_id', $post->id)->count())->toBe(1);
    });
});

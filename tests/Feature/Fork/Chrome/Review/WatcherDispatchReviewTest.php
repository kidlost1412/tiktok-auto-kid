<?php

declare(strict_types=1);

use App\Enums\Post\PublishStatus;
use App\Fork\Chrome\Publishing\ChromeAwareTikTokPublisher;
use App\Enums\Post\Status as PostStatus;
use App\Exceptions\PlatformUnavailableException;
use App\Exceptions\Social\TikTokPublishException;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use Illuminate\Support\Facades\Artisan;

require_once __DIR__.'/ReviewHelpers.php';

beforeEach(function () {
    rvEnv($this);
    $this->social = rvSocial($this);
});

test('AN TOAN: sua bai khi job scheduled con truoc authorize -> thu hoi, dispatch giao lai dung 1 job voi noi dung moi', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    Artisan::call('fork:chrome-dispatch');
    $j1 = $this->chrome->latestForPost($post);
    $j1->update(['state' => 'ready']);

    $post->update(['content' => 'Noi dung moi']);
    expect(ChromeJob::find($j1->id)->state)->toBe('revoked')->and(ChromeJob::find($j1->id)->note)->toBe(ChromePostWatcher::EDIT_NOTE);

    Artisan::call('fork:chrome-dispatch');
    Artisan::call('fork:chrome-dispatch');

    $jobs = ChromeJob::query()->where('post_id', $post->id)->orderBy('attempt')->get();
    expect($jobs)->toHaveCount(2)->and($jobs[1]->caption)->toBe('Noi dung moi')->and($jobs[1]->state)->toBe('queued');
});

test('AN TOAN: sua scheduled_at sang gan hon 37 phut -> dispatch khong giao lai, den gio publisher tao job now', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    Artisan::call('fork:chrome-dispatch');

    $post->update(['scheduled_at' => now()->addMinutes(10)]);
    Artisan::call('fork:chrome-dispatch');
    expect(ChromeJob::query()->where('post_id', $post->id)->count())->toBe(1);

    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($post->refresh()->setRelation('socialAccount', $this->social)))->toThrow(PlatformUnavailableException::class);
    $latest = $this->chrome->latestForPost($post);
    expect($latest->attempt)->toBe(2)->and($latest->mode)->toBe('now');
});

test('AN TOAN: huy lich (ve nhap) thu hoi job; len lich lai thi dispatch giao job moi, khong trung', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    Artisan::call('fork:chrome-dispatch');
    $this->chrome->latestForPost($post)->update(['state' => 'uploading']);

    $post->update(['status' => PostStatus::Draft]);
    expect($this->chrome->latestForPost($post)->state)->toBe('revoked');
    Artisan::call('fork:chrome-dispatch');
    expect(ChromeJob::query()->where('post_id', $post->id)->count())->toBe(1);

    $post->update(['status' => PostStatus::Scheduled]);
    Artisan::call('fork:chrome-dispatch');
    expect(ChromeJob::query()->where('post_id', $post->id)->count())->toBe(2);
    expect(ChromeJob::query()->where('social_account_id', $this->social->id)->whereIn('state', ChromeJob::OPEN)->count())->toBe(1);
});

test('AN TOAN: TikTok Auto Kid chuyen bai sang Publishing/Published khong lam watcher thu hoi job', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    Artisan::call('fork:chrome-dispatch');
    $job = $this->chrome->latestForPost($post);

    $post->markAsPublishing();
    $post->markPublicationPublishing();

    expect(ChromeJob::find($job->id)->state)->toBe('queued');
});

test('AN TOAN: sua bai khi job da authorized -> khong thu hoi duoc, publisher van cho (khong tao job moi)', function () {
    $post = rvPost($this, $this->social);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'authorized', 'authorized_at' => now()]);

    $post->update(['content' => 'sua muon']);

    expect(ChromeJob::find($job->id)->state)->toBe('authorized');
    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($post->refresh()->setRelation('socialAccount', $this->social)))->toThrow(PlatformUnavailableException::class);
    expect(ChromeJob::query()->count())->toBe(1);
});

test('AN TOAN: job uncertain roi Chrome bao posted muon -> dispatch danh dau bai failed thanh published, mot lan', function () {
    $post = rvPost($this, $this->social);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'uncertain']);
    $post->update(['status' => PostStatus::Failed]);

    ChromeJob::query()->whereKey($job->id)->update(['state' => 'posted', 'result' => json_encode(['item_id' => '7300000000000000009']), 'result_at' => now()]);
    Artisan::call('fork:chrome-dispatch');
    Artisan::call('fork:chrome-dispatch');

    $post->refresh();
    expect($post->status)->toBe(PostStatus::Published)->and($post->platform_post_id)->toBe('7300000000000000009');
});

test('AN TOAN: bai da published bang tay khong bi dispatch ghi de; job posted cu hon 14 ngay khong duoc xet', function () {
    $post = rvPost($this, $this->social);
    $job = $this->chrome->queueForPost($post, 'now');
    $job->update(['state' => 'posted', 'result' => ['item_id' => '1'], 'result_at' => now()->subDays(20)]);
    $post->update(['status' => PostStatus::Failed]);

    Artisan::call('fork:chrome-dispatch');

    expect($post->refresh()->status)->toBe(PostStatus::Failed);
});

test('GHI NHAN: bam "Dang ngay" khi job hen gio da posted tren TikTok -> publisher bao thanh cong ngay (TikTok chi dang vao gio hen)', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    $job = $this->chrome->queueForPost($post, 'scheduled');
    $job->update(['state' => 'posted', 'result' => ['item_id' => '77']]);

    $post->update(['scheduled_at' => now()]);
    $res = app(ChromeAwareTikTokPublisher::class)->publish($post->refresh()->setRelation('socialAccount', $this->social));

    // Hanh vi hien tai: tra ve thanh cong. Test nay chi ghi nhan (pass) de bao cao chung cu.
    expect($res['id'])->toBe('77');
    expect(ChromeJob::find($job->id)->note)->toBe(ChromePostWatcher::SCHEDULED_WARNING);
});


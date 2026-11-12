<?php

declare(strict_types=1);

use App\Exceptions\PlatformUnavailableException;
use App\Exceptions\Social\TikTokPublishException;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Publishing\ChromeAwareTikTokPublisher;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Artisan;

require_once __DIR__.'/ReviewHelpers.php';

beforeEach(function () {
    rvEnv($this);
    $this->social = rvSocial($this);
    $this->post = rvPost($this, $this->social);
    [$this->client, $this->token] = rvClient($this);
});

// ---------------------------------------------------------------- thu lai sau that bai chac chan chua dang

test('LOI(trung binh): job now bi revoke/failed CHAC CHAN chua dang thi thu lai van bi chan vinh vien (khong co attempt moi)', function (array $attrs) {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $job->update($attrs);

    // Nguoi dung sua bai / dat lai lich roi cho TikTok Auto Kid goi publisher lan nua.
    $threw = null;
    try {
        app(ChromeAwareTikTokPublisher::class)->publish($this->post->refresh()->setRelation('socialAccount', $this->social));
    } catch (Throwable $e) {
        $threw = $e;
    }

    $count = ChromeJob::query()->where('post_id', $this->post->id)->count();
    expect($count)->toBe(2, 'khong tao attempt moi; publisher nem '.($threw ? $threw::class.': '.$threw->getMessage() : 'khong gi'));
})->with([
    'MISSED_NOW (Chrome offline > 2h)' => [['state' => 'revoked', 'note' => ChromeJobs::MISSED_NOW_TEXT]],
    'STALLED' => [['state' => 'revoked', 'note' => ChromeJobs::STALLED_TEXT]],
    'TOO_LONG' => [['state' => 'revoked', 'note' => ChromeJobs::TOO_LONG_TEXT]],
    'failed truoc authorize' => [['state' => 'failed', 'result' => ['outcome' => 'failed', 'not_sent' => true, 'reason' => 'tab-closed-before-authorization']]],
]);

// ---------------------------------------------------------------- tai khoan dang ban

test('LOI(trung binh): tai khoan dang co job mo cua bai khac thi bai den gio bi that bai dut khoat thay vi cho', function () {
    // Bai B da duoc dispatch som va dang cho/tai len (job mo).
    $postB = rvPost($this, $this->social, ['scheduled_at' => now()->addDays(3)]);
    $this->chrome->queueForPost($postB, 'scheduled');

    // Bai A den gio dang (publisher).
    $threw = null;
    try {
        app(ChromeAwareTikTokPublisher::class)->publish($this->post);
    } catch (Throwable $e) {
        $threw = $e;
    }

    expect($threw)->toBeInstanceOf(PlatformUnavailableException::class, 'nem '.($threw ? $threw::class.': '.$threw->getMessage() : 'khong gi'));
});

// ---------------------------------------------------------------- han chot, don vi

test('AN TOAN: don vi cua cac han chot (giay, khong phai phut)', function () {
    expect(ChromeJobs::RESULT_WITHIN)->toBe(180)
        ->and(ChromeJobs::STALE_AFTER)->toBe(120)
        ->and(ChromeJobs::ORPHAN_CLAIM_AFTER)->toBe(60)
        ->and(ChromeJobs::UPLOAD_WITHIN)->toBe(900)
        ->and(ChromeJobs::SCHEDULE_LEAD)->toBe(2100)
        ->and(ChromeJobs::SCHEDULE_MAX_AHEAD)->toBe(9 * 86400 + 43200)
        ->and(ChromeJobs::ONLINE_WINDOW)->toBe(90)
        ->and(ChromeJobs::nowClaimWithin())->toBe(7200)
        ->and(ChromeAwareTikTokPublisher::WAIT_RETRY_SECONDS * ChromeAwareTikTokPublisher::WAIT_MAX_RETRIES)->toBeGreaterThan(ChromeJobs::nowClaimWithin());
});

test('AN TOAN: authorized qua 180s thanh uncertain, 179s chua; reconcile idempotent', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $job->update(['state' => 'authorized', 'authorized_at' => now()->subSeconds(179)]);
    $this->chrome->reconcile();
    expect(ChromeJob::find($job->id)->state)->toBe('authorized');

    ChromeJob::query()->whereKey($job->id)->update(['authorized_at' => now()->subSeconds(181)]);
    $this->chrome->reconcile();
    $this->chrome->reconcile();
    expect(ChromeJob::find($job->id)->state)->toBe('uncertain')->and(ChromeJob::find($job->id)->note)->toBe(ChromeJobs::NO_RESULT_TEXT);
});

test('AN TOAN: claimed khong progress: 59s giu, 61s requeue; ready/uploading khong heartbeat 121s bi revoke', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->assertOk();

    ChromeJob::query()->whereKey($job->id)->update(['claimed_at' => now()->subSeconds(59), 'heartbeat_at' => now()->subSeconds(59)]);
    $this->chrome->reconcile();
    expect(ChromeJob::find($job->id)->state)->toBe('claimed');

    ChromeJob::query()->whereKey($job->id)->update(['claimed_at' => now()->subSeconds(61), 'heartbeat_at' => now()->subSeconds(61)]);
    $this->chrome->reconcile();
    expect(ChromeJob::find($job->id)->state)->toBe('queued');

    ChromeJob::query()->whereKey($job->id)->update(['state' => 'ready', 'claimed_at' => now()->subSeconds(300), 'heartbeat_at' => now()->subSeconds(121)]);
    $this->chrome->reconcile();
    expect(ChromeJob::find($job->id)->state)->toBe('revoked')->and(ChromeJob::find($job->id)->note)->toBe(ChromeJobs::STALLED_TEXT);
});

test('AN TOAN: job claimed da qua deliver_by van bi don (stale 120s) - khong ket vinh vien', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->assertOk();
    ChromeJob::query()->whereKey($job->id)->update(['deliver_by' => now()->subMinute(), 'claimed_at' => now()->subSeconds(130), 'heartbeat_at' => now()->subSeconds(130)]);

    $this->chrome->reconcile();

    expect(ChromeJob::find($job->id)->state)->toBe('revoked');
});

test('AN TOAN: job queued qua deliver_by bi revoke theo mode; running > 15 phut bi revoke', function () {
    $now = $this->chrome->queueForPost($this->post, 'now');
    $now->update(['deliver_by' => now()->subSecond()]);
    $this->chrome->reconcile();
    expect(ChromeJob::find($now->id)->note)->toBe(ChromeJobs::MISSED_NOW_TEXT);

    $post2 = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    $sch = $this->chrome->queueForPost($post2, 'scheduled');
    $sch->update(['deliver_by' => now()->subSecond()]);
    $this->chrome->reconcile();
    expect(ChromeJob::find($sch->id)->note)->toBe(ChromeJobs::MISSED_SCHEDULED_TEXT);

    $post3 = rvPost($this, $this->social);
    $run = $this->chrome->queueForPost($post3, 'now');
    $run->update(['state' => 'uploading', 'claimed_at' => now()->subSeconds(ChromeJobs::UPLOAD_WITHIN + 5), 'heartbeat_at' => now()]);
    $this->chrome->reconcile();
    expect(ChromeJob::find($run->id)->note)->toBe(ChromeJobs::TOO_LONG_TEXT);
});

test('AN TOAN: job hen gio het han (Chrome khong mo kip) -> den gio publisher tao job now, khong mat bai', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    $sch = $this->chrome->queueForPost($post, 'scheduled');
    $sch->update(['deliver_by' => now()->subSecond()]);
    $this->chrome->reconcile();
    expect(ChromeJob::find($sch->id)->state)->toBe('revoked');

    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($post))->toThrow(PlatformUnavailableException::class);
    $latest = $this->chrome->latestForPost($post);
    expect($latest->attempt)->toBe(2)->and($latest->mode)->toBe('now');
});

test('AN TOAN: schedule-expired (not_sent) -> publisher tao job now; cancel cua nguoi dung thi khong', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    $sch = $this->chrome->queueForPost($post, 'scheduled');
    $sch->update(['state' => 'failed', 'result' => ['outcome' => 'failed', 'not_sent' => true, 'reason' => 'schedule-expired']]);
    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($post))->toThrow(PlatformUnavailableException::class);
    expect($this->chrome->latestForPost($post)->attempt)->toBe(2);

    $post2 = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(6)]);
    ChromeJob::query()->where('post_id', $post->id)->update(['state' => 'revoked']);
    $c = $this->chrome->queueForPost($post2, 'scheduled');
    $c->update(['state' => 'revoked', 'note' => ChromeJobs::CANCEL_TEXT]);
    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($post2))->toThrow(TikTokPublishException::class);
});

test('AN TOAN: dispatch khong giao bai < 37 phut; queueForPost scheduled tu choi < 35 phut', function () {
    $near = rvPost($this, $this->social, ['scheduled_at' => now()->addMinutes(30)]);
    Artisan::call('fork:chrome-dispatch');
    expect(ChromeJob::query()->where('post_id', $near->id)->count())->toBe(0);

    $edge = rvPost($this, $this->social, ['scheduled_at' => now()->addMinutes(34)]);
    expect(fn () => $this->chrome->queueForPost($edge, 'scheduled'))->toThrow(App\Fork\Chrome\Support\ChromeRefusal::class);
});

test('LOI(thap): ghi chu cancel bi lap chuoi CANCEL_TEXT hai lan va cat cut', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $p = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->json();

    $this->postJson('/api/ext/cancel', ['id' => $p['id'], 'nonce' => $p['nonce'], 'claim_token' => $p['claim_token'], 'reason' => 'owner-cleared'], rvHeaders($this->token))->assertOk();

    expect(ChromeJob::find($job->id)->note)->toBe(ChromeJobs::CANCEL_TEXT.' (owner-cleared)');
});

test('AN TOAN: isOnline dung don vi giay: 80s online, 100s offline', function () {
    [$c] = rvClient($this);
    $c->forceFill(['last_seen_at' => now()->subSeconds(80)])->save();
    expect($this->chrome->isOnline($c->refresh()))->toBeTrue();
    $c->forceFill(['last_seen_at' => now()->subSeconds(100)])->save();
    expect($this->chrome->isOnline($c->refresh()))->toBeFalse();
});

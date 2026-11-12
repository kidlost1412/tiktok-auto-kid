<?php

declare(strict_types=1);

use App\Exceptions\PlatformUnavailableException;
use App\Fork\Chrome\Publishing\ChromeAwareTikTokPublisher;
use App\Exceptions\Social\TikTokPublishException;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeRefusal;
use App\Models\Post;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Http;

require_once __DIR__.'/ReviewHelpers.php';

beforeEach(function () {
    rvEnv($this);
    $this->social = rvSocial($this);
    $this->post = rvPost($this, $this->social);
    [$this->client, $this->token] = rvClient($this);
});

// ---------------------------------------------------------------- authorize / revoke

test('AN TOAN: authorize hai lan chi thang mot, lan hai bao already-authorized', function () {
    $this->chrome->queueForPost($this->post, 'now');
    $p = rvClaimAndReady($this, $this->token);

    $this->postJson('/api/ext/authorize', rvAuthBody($p), rvHeaders($this->token))->assertJsonPath('ok', true);
    $at = ChromeJob::find($p['id'])->authorized_at;

    $this->postJson('/api/ext/authorize', rvAuthBody($p, ['body_sha256' => str_repeat('b', 64)]), rvHeaders($this->token))
        ->assertJsonPath('ok', false)->assertJsonPath('reason', 'already-authorized');

    $j = ChromeJob::find($p['id']);
    expect($j->state)->toBe('authorized')->and($j->authorized_at->equalTo($at))->toBeTrue()
        ->and($j->auth_sha)->toBe(str_repeat('a', 64));
});

test('AN TOAN: revoke thang thi authorize bi tu choi; authorize thang thi revoke thua', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $p = rvClaimAndReady($this, $this->token);

    expect($this->chrome->revoke($job->id, 'x'))->toBeTrue();
    $this->postJson('/api/ext/authorize', rvAuthBody($p), rvHeaders($this->token))
        ->assertJsonPath('ok', false)->assertJsonPath('reason', 'revoked');
    expect(ChromeJob::find($job->id)->state)->toBe('revoked');

    $post2 = rvPost($this, $this->social);
    $job2 = $this->chrome->queueForPost($post2, 'now');
    $p2 = rvClaimAndReady($this, $this->token);
    $this->postJson('/api/ext/authorize', rvAuthBody($p2), rvHeaders($this->token))->assertJsonPath('ok', true);
    expect($this->chrome->revoke($job2->id, 'x'))->toBeFalse()
        ->and(ChromeJob::find($job2->id)->state)->toBe('authorized');
});

test('AN TOAN: ket qua posted den sau khi job da revoke khong bao gio thanh posted', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $p = rvClaimAndReady($this, $this->token);
    $this->chrome->revoke($job->id, 'x');

    $this->postJson('/api/ext/result', ['id' => $p['id'], 'nonce' => $p['nonce'], 'claim_token' => $p['claim_token'], 'outcome' => 'posted'], rvHeaders($this->token))->assertOk();

    expect(ChromeJob::find($job->id)->state)->toBe('uncertain');
});

// ---------------------------------------------------------------- claim mo coi

test('AN TOAN: claim mo coi bi xoay token thi client cu khong progress/authorize/result/cancel duoc', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $old = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->assertOk()->json();
    $staleModel = ChromeJob::find($job->id);

    ChromeJob::query()->whereKey($job->id)->update(['claimed_at' => now()->subSeconds(ChromeJobs::ORPHAN_CLAIM_AFTER + 1)]);
    $this->chrome->reconcile();

    $j = ChromeJob::find($job->id);
    expect($j->state)->toBe('queued')->and($j->claim_token)->toBeNull()->and($j->nonce)->not->toBe($old['nonce']);

    $body = ['id' => $old['id'], 'nonce' => $old['nonce'], 'claim_token' => $old['claim_token']];
    foreach (['progress', 'authorize', 'result', 'cancel'] as $ep) {
        $this->postJson("/api/ext/{$ep}", $ep === 'authorize' ? rvAuthBody($old) : [...$body, 'phase' => 'ready', 'outcome' => 'posted'], rvHeaders($this->token))
            ->assertStatus(403)->assertJsonPath('error', 'bad_nonce');
    }

    expect($this->chrome->authorize($staleModel, str_repeat('a', 64), 'c'))->toBeFalse();

    $new = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->assertOk()->json();
    expect($new['claim_token'])->not->toBe($old['claim_token'])->and($new['nonce'])->not->toBe($old['nonce']);
    $this->postJson('/api/ext/progress', [...$body, 'phase' => 'ready'], rvHeaders($this->token))->assertStatus(403);
    $this->postJson('/api/ext/progress', ['id' => $new['id'], 'nonce' => $new['nonce'], 'claim_token' => $new['claim_token'], 'phase' => 'ready'], rvHeaders($this->token))->assertOk();
    $this->postJson('/api/ext/authorize', rvAuthBody($old), rvHeaders($this->token))->assertStatus(403);
    expect(ChromeJob::find($job->id)->state)->toBe('ready');
});

test('AN TOAN: claim mo coi KHONG bi xoay khi da co progress (da sang uploading)', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $p = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->json();
    $this->postJson('/api/ext/progress', ['id' => $p['id'], 'nonce' => $p['nonce'], 'claim_token' => $p['claim_token'], 'phase' => 'upload'], rvHeaders($this->token))->assertOk();

    ChromeJob::query()->whereKey($job->id)->update(['claimed_at' => now()->subSeconds(500), 'heartbeat_at' => now()]);
    $this->chrome->reconcile();

    $j = ChromeJob::find($job->id);
    expect($j->state)->toBe('uploading')->and($j->claim_token)->toBe($p['claim_token']);
});

test('LOI(thap): heartbeat khong bi rao boi claim_token - client cu day duoc job cua client moi sang ready', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $a = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->json();
    $staleJobA = ChromeJob::find($job->id);

    ChromeJob::query()->whereKey($job->id)->update(['claimed_at' => now()->subSeconds(61)]);
    $this->chrome->reconcile();
    $b = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->json();
    expect($b['claim_token'])->not->toBe($a['claim_token']);

    $this->chrome->heartbeat($staleJobA, true);

    expect(ChromeJob::find($job->id)->state)->toBe('claimed');
});

// ---------------------------------------------------------------- publisher: khong tao job trung

test('AN TOAN: publisher khong tao job moi khi job moi nhat la authorized/uncertain/posted/rejected/failed', function (string $state, array $extra) {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $job->update(['state' => $state, ...$extra]);

    for ($i = 0; $i < 3; $i++) {
        try {
            app(ChromeAwareTikTokPublisher::class)->publish($this->post);
        } catch (Throwable) {
        }
    }

    expect(ChromeJob::query()->where('post_id', $this->post->id)->count())->toBe(1);
})->with([
    'authorized' => ['authorized', ['authorized_at' => '2026-01-01 00:00:00']],
    'uncertain' => ['uncertain', []],
    'posted' => ['posted', ['result' => ['item_id' => '730']]],
    'rejected' => ['rejected', ['result' => ['outcome' => 'rejected']]],
    // failed với not_sent=true mà chưa authorize được phép thử lại (tối đa MAX_ATTEMPTS),
    // nên ca "chắc chắn chưa gửi" nằm ở StuckReviewTest. Ở đây chỉ giữ failed SAU authorize.
    'failed sau authorize' => ['failed', ['authorized_at' => '2026-01-01 00:00:00', 'result' => ['outcome' => 'failed']]],
]);

test('AN TOAN: uncertain roi nguoi dung thu lai nhieu lan - nem loi dut khoat, khong job moi', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    ChromeJob::query()->whereKey($job->id)->update(['state' => 'authorized', 'authorized_at' => now()->subSeconds(ChromeJobs::RESULT_WITHIN + 5)]);
    $this->chrome->reconcile();
    expect(ChromeJob::find($job->id)->state)->toBe('uncertain');

    foreach (range(1, 3) as $_) {
        expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($this->post))->toThrow(TikTokPublishException::class);
    }
    $this->post->update(['content' => 'da sua']);
    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($this->post->refresh()->setRelation('socialAccount', $this->social)))->toThrow(TikTokPublishException::class);
    expect(ChromeJob::query()->where('post_id', $this->post->id)->count())->toBe(1);
});

test('AN TOAN: job revoked (scheduled) nhan ket qua posted muon thi thanh uncertain, publisher khong tao job moi', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $job->update(['mode' => 'scheduled', 'state' => 'revoked', 'note' => ChromeJobs::STALLED_TEXT, 'claim_token' => 'tok']);

    $this->postJson('/api/ext/result', ['id' => $job->id, 'nonce' => $job->nonce, 'claim_token' => 'tok', 'outcome' => 'posted'], rvHeaders($this->token))->assertOk();
    expect(ChromeJob::find($job->id)->state)->toBe('uncertain');

    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($this->post))->toThrow(TikTokPublishException::class);
    expect(ChromeJob::query()->where('post_id', $this->post->id)->count())->toBe(1);
});

test('AN TOAN: publisher + dispatch cung bai: khong tao hai job', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);

    Artisan::call('fork:chrome-dispatch');
    Artisan::call('fork:chrome-dispatch');
    expect(ChromeJob::query()->where('post_id', $post->id)->count())->toBe(1);

    expect(fn () => app(ChromeAwareTikTokPublisher::class)->publish($post))->toThrow(PlatformUnavailableException::class);
    expect(ChromeJob::query()->where('post_id', $post->id)->count())->toBe(1);

    ChromeJob::query()->where('post_id', $post->id)->update(['state' => 'posted', 'result' => json_encode(['item_id' => '1'])]);
    Artisan::call('fork:chrome-dispatch');
    expect(ChromeJob::query()->where('post_id', $post->id)->count())->toBe(1);
});

test('AN TOAN: hai lan queueForPost cho cung mot bai: lan hai bi tu choi (unique)', function () {
    $this->chrome->queueForPost($this->post, 'now');
    expect(fn () => $this->chrome->queueForPost($this->post, 'now'))->toThrow(ChromeRefusal::class);
    expect(ChromeJob::query()->count())->toBe(1);
});

test('PHONG THU: queueForPost tu no phai tu choi khi job moi nhat cua bai la uncertain/posted (hien chi caller giu rao)', function (string $state) {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $job->update(['state' => $state]);

    expect(fn () => $this->chrome->queueForPost($this->post, 'now'))->toThrow(ChromeRefusal::class);
})->with(['uncertain', 'posted']);

test('LOI(thap): dispatch giu ban Post cu - bai sua giua luc SELECT va INSERT van ra job mang noi dung cu, khong ai thu hoi', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    $stale = Post::with('socialAccount')->find($post->id);

    Post::find($post->id)->update(['content' => 'NOI DUNG MOI']);
    $job = $this->chrome->queueForPost($stale, 'scheduled');

    $fresh = ChromeJob::find($job->id);
    expect($fresh->state === 'revoked' || str_contains((string) $fresh->caption, 'NOI DUNG MOI'))->toBeTrue(
        'job mang caption cu "'.$fresh->caption.'" o trang thai '.$fresh->state
    );
});

// ---------------------------------------------------------------- tat Chrome roi roi ve API

test('LOI(cao): tat dang-qua-Chrome khi bai da co job mo/uncertain/posted thi publisher roi ve API TikTok', function (string $state) {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $job->update(['state' => $state]);
    ChromeAccount::query()->where('social_account_id', $this->social->id)->update(['enabled' => false]);

    Http::fake(['*' => Http::response(['data' => ['publish_id' => 'v_pub_file~v2.123'], 'error' => ['code' => 'ok']], 200)]);

    $threw = null;
    try {
        app(ChromeAwareTikTokPublisher::class)->publish($this->post->refresh()->setRelation('socialAccount', $this->social->refresh()));
    } catch (Throwable $e) {
        $threw = $e::class.': '.$e->getMessage();
    }

    expect(Http::recorded())->toHaveCount(0, 'publisher da goi API TikTok cho bai co job Chrome o trang thai '.$state.' (exception: '.$threw.')');
})->with(['queued', 'authorized', 'uncertain', 'posted']);

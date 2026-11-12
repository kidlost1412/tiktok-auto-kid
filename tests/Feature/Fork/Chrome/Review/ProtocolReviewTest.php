<?php

declare(strict_types=1);

use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeRefusal;
use Carbon\CarbonImmutable;

require_once __DIR__.'/ReviewHelpers.php';

beforeEach(function () {
    rvEnv($this);
    $this->social = rvSocial($this);
    $this->post = rvPost($this, $this->social);
    [$this->client, $this->token] = rvClient($this);
});

function rvKeys(array $a): array
{
    $k = array_keys($a);
    sort($k);

    return $k;
}

test('GIAO THUC: payload /next co dung tung truong cua PROTOCOL.md 3.3 va sw.js/lib.js doc duoc', function () {
    $post = rvPost($this, $this->social, ['scheduled_at' => now()->addHours(5)]);
    $this->chrome->queueForPost($post, 'scheduled');

    $j = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->assertOk()->json();

    expect(rvKeys($j))->toBe(rvKeys(array_flip([
        'id', 'nonce', 'claim_token', 'mode', 'attempt', 'caption', 'visibility', 'visibility_type', 'schedule_time',
        'schedule_unix', 'options', 'expect_account', 'expect_user_id', 'video', 'limits', 'product',
    ])))
        ->and($j['mode'])->toBe('post')
        ->and($j['id'])->toStartWith('ej_')->and(strlen($j['id']))->toBe(27)
        ->and(strlen($j['nonce']))->toBe(32)->and(strlen($j['claim_token']))->toBe(32)
        ->and($j['attempt'])->toBeInt()
        ->and($j['visibility'])->toBe('public')->and($j['visibility_type'])->toBe(0)
        ->and($j['schedule_time'])->toMatch('/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/')
        ->and($j['schedule_unix'])->toBeInt()
        ->and(rvKeys($j['options']))->toBe(['ai_label', 'allow_comment', 'allow_duet', 'allow_stitch'])
        ->and($j['options']['allow_comment'])->toBeInt()
        ->and($j['expect_account'])->toBe('tiktoker')->and($j['expect_user_id'])->toBe(RV_USER_ID)
        ->and(rvKeys($j['video']))->toBe(['name', 'size', 'type'])
        ->and($j['video']['size'])->toBeInt()->and($j['video']['type'])->toBe('video/mp4')
        ->and($j['limits'])->toBe([
            'claim_within_s' => 120, 'heartbeat_every_s' => 60, 'stale_after_s' => 120, 'upload_within_s' => 900,
            'result_within_s' => 180, 'schedule_min_ahead_s' => 900, 'schedule_max_shift_s' => 600,
        ]);
    expect(CarbonImmutable::parse($j['schedule_time'])->getTimestamp())->toBe($j['schedule_unix']);
});

test('GIAO THUC: job dang ngay co schedule_time va schedule_unix la null (khong phai chuoi rong)', function () {
    $this->chrome->queueForPost($this->post, 'now');
    $j = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->assertOk()->json();

    expect($j['schedule_time'])->toBeNull()->and($j['schedule_unix'])->toBeNull();
});

test('GIAO THUC: /hello /progress /authorize /result /cancel /job_state dung hinh dang', function () {
    $this->postJson('/api/ext/hello', ['protocol' => 1, 'ext_version' => '1.0.0', 'identity' => ['username' => 'tiktoker', 'user_id' => RV_USER_ID]], rvHeaders($this->token))
        ->assertOk()
        ->assertJsonStructure(['ok', 'client_id', 'protocol_min', 'protocol_max', 'need_reload', 'message', 'server_time', 'account' => ['id', 'username', 'publisher'], 'conflict'])
        ->assertJsonPath('server_time', fn ($v) => preg_match('/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/', $v) === 1);

    $this->chrome->queueForPost($this->post, 'now');
    $p = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->json();
    $b = ['id' => $p['id'], 'nonce' => $p['nonce'], 'claim_token' => $p['claim_token']];

    $r = $this->postJson('/api/ext/progress', [...$b, 'phase' => 'upload'], rvHeaders($this->token))->assertOk()->json();
    expect(rvKeys($r))->toBe(['ok', 'state'])->and($r['ok'])->toBeTrue()->and($r['state'])->toBe('uploading');

    $this->postJson('/api/ext/progress', [...$b, 'phase' => 'ready'], rvHeaders($this->token));

    $deny = $this->postJson('/api/ext/authorize', rvAuthBody($p, ['visibility_type' => 1]), rvHeaders($this->token))->assertOk()->json();
    expect($deny)->toBe(['ok' => false, 'reason' => 'visibility-mismatch']);
    $ok = $this->postJson('/api/ext/authorize', rvAuthBody($p), rvHeaders($this->token))->assertOk()->json();
    expect($ok)->toBe(['ok' => true]);

    $res = $this->postJson('/api/ext/result', [...$b, 'outcome' => 'posted', 'item_id' => '7701245450858351893', 'schedule_time' => null, 'response' => ['x' => 1], 'elapsed_ms' => 5], rvHeaders($this->token))->assertOk()->json();
    expect($res)->toBe(['ok' => true, 'duplicate' => false, 'state' => 'posted']);
    $dup = $this->postJson('/api/ext/result', [...$b, 'outcome' => 'failed'], rvHeaders($this->token))->assertOk()->json();
    expect($dup)->toBe(['ok' => true, 'duplicate' => true, 'state' => 'posted']);

    $cancel = $this->postJson('/api/ext/cancel', $b, rvHeaders($this->token))->assertOk()->json();
    expect($cancel)->toBe(['ok' => true, 'state' => 'posted', 'cancel_recorded' => false]);

    $st = $this->getJson('/api/ext/job_state?id='.$p['id'], rvHeaders($this->token))->assertOk()->json();
    expect($st)->toBe(['ok' => true, 'state' => 'posted', 'authorized' => true]);
    $this->getJson('/api/ext/job_state?id=ej_nope', rvHeaders($this->token))->assertStatus(404)->assertJsonPath('error', 'unknown_job');
});

test('GIAO THUC: progress cua job da bi revoke tra {ok:false,state:revoked,cancelled:true}', function () {
    $job = $this->chrome->queueForPost($this->post, 'now');
    $p = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->json();
    $this->chrome->revoke($job->id, 'x');

    $r = $this->postJson('/api/ext/progress', ['id' => $p['id'], 'nonce' => $p['nonce'], 'claim_token' => $p['claim_token'], 'phase' => 'upload'], rvHeaders($this->token))->json();
    expect($r)->toBe(['ok' => false, 'state' => 'revoked', 'cancelled' => true]);
});

test('GIAO THUC: ma loi va ma HTTP (401, 409 need_reload/no_identity/identity_conflict, 400, 204)', function () {
    $this->getJson('/api/ext/next', ['X-Autotok-Protocol' => '1'])->assertStatus(401)->assertJsonStructure(['ok', 'error', 'message'])->assertJsonPath('error', 'unauthorized');
    $this->getJson('/api/ext/next', [...rvHeaders($this->token), 'X-Autotok-Protocol' => '2'])->assertStatus(409)->assertJsonPath('error', 'need_reload')->assertJsonPath('need_reload', true);
    $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->assertNoContent();
    $this->postJson('/api/ext/progress', [], rvHeaders($this->token))->assertStatus(404)->assertJsonPath('error', 'unknown_job');
    $this->post('/api/ext/hello', [], [...rvHeaders($this->token), 'Content-Type' => 'application/json'])->assertStatus(400)->assertJsonPath('error', 'bad_request');

    [$other, $otherToken] = rvClient($this, RV_USER_ID); // hai Chrome cung user_id dang online
    $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->assertStatus(409)->assertJsonPath('error', 'identity_conflict');
    $other->update(['revoked_at' => now()]);

    $made = $this->chrome->createClient($this->tpAccount->id, 'x', '1', 1);
    $this->getJson('/api/ext/next?wait=0', rvHeaders($made['token']))->assertStatus(409)->assertJsonPath('error', 'no_identity');
});

test('GIAO THUC: pair 403 bad_code co tries_left, 410 no_code', function () {
    $this->postJson('/api/ext/pair', ['code' => '000000', 'protocol' => 1], rvHeaders(''))->assertStatus(410)->assertJsonPath('error', 'no_code');
    $this->chrome->newPairCode($this->tpAccount->id);
    $this->postJson('/api/ext/pair', ['code' => 'zzzzzz', 'protocol' => 1], rvHeaders(''))->assertStatus(403)->assertJsonPath('error', 'bad_code')->assertJsonPath('tries_left', 4);
});

test('GIAO THUC: long-poll bi chan o next_max_wait, nho hon timeout 30s cua sw.js (wait=20)', function () {
    config()->set('fork.chrome.next_max_wait', 10);
    expect(config('fork.chrome.next_max_wait'))->toBeLessThan(20);
    // Gia tri mac dinh trong config/fork.php
    $cfg = require base_path('config/fork.php');
    expect($cfg['chrome']['next_max_wait'])->toBe(10);
});

test('LOI(thap): job khong co chu thich (caption rong) van duoc xep hang nhung tien ich se tu choi (caption is required) - nen tu choi tu dau', function () {
    $post = rvPost($this, $this->social, ['content' => '']);

    expect(fn () => $this->chrome->queueForPost($post, 'now'))->toThrow(ChromeRefusal::class);
});

test('LOI(thap): caption dai hon 2200 ky tu van duoc xep hang nhung tien ich se tu choi', function () {
    $post = rvPost($this, $this->social, ['content' => str_repeat('a', 2300)]);

    expect(fn () => $this->chrome->queueForPost($post, 'now'))->toThrow(ChromeRefusal::class);
});

test('GIAO THUC: video 206/416 theo Range, Content-Range dung', function () {
    $this->chrome->queueForPost($this->post, 'now');
    $p = $this->getJson('/api/ext/next?wait=0', rvHeaders($this->token))->json();
    $size = strlen('video-bytes');

    $r = $this->get('/api/ext/video?id='.$p['id'], [...rvHeaders($this->token), 'Range' => 'bytes=2-5']);
    $r->assertStatus(206)->assertHeader('Content-Range', "bytes 2-5/{$size}")->assertHeader('Content-Length', '4');
    $this->get('/api/ext/video?id='.$p['id'], [...rvHeaders($this->token), 'Range' => 'bytes=999-'])->assertStatus(416);
    $this->getJson('/api/ext/video/meta?id='.$p['id'], rvHeaders($this->token))->assertOk()->assertExactJson(['name' => 'v.mp4', 'size' => $size, 'type' => 'video/mp4']);

    ChromeJob::query()->whereKey($p['id'])->update(['state' => 'authorized']);
    $this->get('/api/ext/video?id='.$p['id'], rvHeaders($this->token))->assertStatus(403);
});

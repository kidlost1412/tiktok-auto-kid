<?php

declare(strict_types=1);

use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeRefusal;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Storage;

const CHROME_UID = '7012345678901234567';

function chromeJobs(): ChromeJobs
{
    return app(ChromeJobs::class);
}

/** @return array{0: SocialAccount, 1: ChromeClient} */
function chromeSetup(?Workspace $workspace = null, string $uid = CHROME_UID): array
{
    $workspace ??= Workspace::factory()->create();
    $sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $workspace->id]);
    ChromeAccount::create(['social_account_id' => $sa->id, 'enabled' => true, 'tiktok_user_id' => $uid, 'chrome_only' => false]);
    $client = chromeJobs()->createClient($workspace->account_id, 'Chrome test', '1.0.0', 1)['client'];
    chromeJobs()->touch($client, 1, ['tiktok_user_id' => $uid, 'tiktok_username' => 'tester']);

    return [$sa, $client->refresh()];
}

function chromePost(SocialAccount $sa, array $meta = [], array $attrs = [], string $file = 'v/clip.mp4'): Post
{
    Storage::put($file, 'video-bytes');

    return Post::factory()->forAccount($sa)->create([
        'content' => 'xin chào',
        'media' => [['id' => 'm1', 'path' => $file, 'url' => 'http://x/'.$file, 'type' => 'video', 'mime_type' => 'video/mp4', 'original_filename' => 'clip.mp4', 'size' => 11]],
        'meta' => $meta + ['privacy_level' => 'PUBLIC_TO_EVERYONE', 'allow_comments' => true, 'allow_duet' => false, 'allow_stitch' => true, 'is_aigc' => true],
        ...$attrs,
    ]);
}

/** Đưa job tới trạng thái ready (đã nhận, tải xong). */
function chromeReady(ChromeJob $job, ChromeClient $client): ChromeJob
{
    $claimed = chromeJobs()->claimNext($client);
    expect($claimed?->id)->toBe($job->id);
    chromeJobs()->heartbeat($claimed, true);

    return $claimed->refresh();
}

beforeEach(function () {
    // Đĩa riêng cho mỗi test: các agent khác chạy song song và Storage::fake() dùng chung một thư mục.
    $this->chromeDisk = 'chrome_test_'.bin2hex(random_bytes(4));
    $this->chromeRoot = storage_path('framework/testing/disks/'.$this->chromeDisk);
    config([
        'filesystems.disks.'.$this->chromeDisk => ['driver' => 'local', 'root' => $this->chromeRoot, 'throw' => false],
        'filesystems.default' => $this->chromeDisk,
    ]);
    Cache::flush();
});

afterEach(function () {
    File::deleteDirectory($this->chromeRoot);
});

test('map dữ liệu từ bài: riêng tư, cờ và caption', function () {
    [$sa] = chromeSetup();
    $post = chromePost($sa, ['privacy_level' => 'SELF_ONLY']);

    $job = chromeJobs()->queueForPost($post, 'now');

    expect($job->state)->toBe('queued')
        ->and($job->attempt)->toBe(1)
        ->and($job->options)->toMatchArray([
            'visibility_type' => 1, 'allow_comment' => 1, 'allow_duet' => 0, 'allow_stitch' => 1, 'ai_label' => 1, 'schedule_time' => null,
        ])
        ->and($job->caption)->toBe('xin chào')
        ->and($job->video_mime)->toBe('video/mp4')
        ->and($job->id)->toStartWith('ej_')
        ->and($job->deliver_by->greaterThan(now()->addMinutes(100)))->toBeTrue();
});

test('chế độ bạn bè, riêng tư kèm hẹn giờ, không video, ảnh, hẹn quá xa đều bị từ chối', function () {
    [$sa] = chromeSetup();

    $friends = chromePost($sa, ['privacy_level' => 'MUTUAL_FOLLOW_FRIENDS']);
    expect(fn () => chromeJobs()->queueForPost($friends, 'now'))->toThrow(ChromeRefusal::class, 'chưa hỗ trợ');

    $private = chromePost($sa, ['privacy_level' => 'SELF_ONLY'], ['scheduled_at' => now()->addDay()]);
    expect(fn () => chromeJobs()->queueForPost($private, 'scheduled'))->toThrow(ChromeRefusal::class, 'riêng tư');

    $none = Post::factory()->forAccount($sa)->create(['media' => [], 'meta' => ['privacy_level' => 'PUBLIC_TO_EVERYONE']]);
    expect(fn () => chromeJobs()->queueForPost($none, 'now'))->toThrow(ChromeRefusal::class, 'không có video');

    Storage::put('p/a.jpg', 'x');
    $photo = Post::factory()->forAccount($sa)->create([
        'media' => [['id' => 'i', 'path' => 'p/a.jpg', 'url' => 'u', 'type' => 'image', 'mime_type' => 'image/jpeg']],
        'meta' => ['privacy_level' => 'PUBLIC_TO_EVERYONE'],
    ]);
    expect(fn () => chromeJobs()->queueForPost($photo, 'now'))->toThrow(ChromeRefusal::class, 'ảnh');

    $far = chromePost($sa, [], ['scheduled_at' => now()->addDays(31)]);
    expect(fn () => chromeJobs()->queueForPost($far, 'scheduled'))->toThrow(ChromeRefusal::class, "10 ngày");
});

test('video sai định dạng, thiếu file hoặc file rỗng bị từ chối', function () {
    [$sa] = chromeSetup();

    $avi = chromePost($sa, [], [], 'v/clip.avi');
    expect(fn () => chromeJobs()->queueForPost($avi, 'now'))->toThrow(ChromeRefusal::class, 'mp4');

    $missing = chromePost($sa, [], [], 'v/gone.mp4');
    Storage::delete('v/gone.mp4');
    expect(fn () => chromeJobs()->queueForPost($missing, 'now'))->toThrow(ChromeRefusal::class, 'file');

    $empty = chromePost($sa, [], [], 'v/empty.mp4');
    Storage::put('v/empty.mp4', '');
    expect(fn () => chromeJobs()->queueForPost($empty, 'now'))->toThrow(ChromeRefusal::class, 'rỗng');
});

test('hẹn giờ: schedule_time, deliver_by trước giờ hẹn 35 phút', function () {
    [$sa] = chromeSetup();
    $at = CarbonImmutable::now()->addDays(2)->startOfMinute();
    $post = chromePost($sa, [], ['scheduled_at' => $at]);

    $job = chromeJobs()->queueForPost($post, 'scheduled');

    expect($job->mode)->toBe('scheduled')
        ->and($job->options['schedule_time'])->toBe($at->utc()->format('Y-m-d\TH:i:s\Z'))
        ->and($job->deliver_by->equalTo($at->subMinutes(35)))->toBeTrue();

    $payload = chromeJobs()->jobPayload($job, ChromeClient::first());
    expect($payload['schedule_unix'])->toBe($at->getTimestamp())->and($payload['visibility'])->toBe('public')->and($payload)->toHaveKey('product')->and($payload['product'])->toBeNull();
});

test('mỗi tài khoản chỉ có một job mở', function () {
    [$sa] = chromeSetup();
    $first = chromeJobs()->queueForPost(chromePost($sa), 'now');

    expect(fn () => chromeJobs()->queueForPost(chromePost($sa, [], [], 'v/b.mp4'), 'now'))
        ->toThrow(ChromeRefusal::class);

    expect(chromeJobs()->openJobFor($sa)->id)->toBe($first->id);
    expect(ChromeJob::count())->toBe(1);
});

test('attempt tăng dần theo bài', function () {
    [$sa] = chromeSetup();
    $post = chromePost($sa);
    $a = chromeJobs()->queueForPost($post, 'now');
    chromeJobs()->revoke($a->id, 'thử');
    $b = chromeJobs()->queueForPost($post, 'now');

    expect($b->attempt)->toBe(2)->and(chromeJobs()->latestForPost($post)->id)->toBe($b->id);
});

test('claimNext không nhận job của user_id khác và chỉ nhận một lần', function () {
    [$sa, $client] = chromeSetup();
    $job = chromeJobs()->queueForPost(chromePost($sa), 'now');

    $other = chromeJobs()->createClient($client->account_id, 'khác', '1', 1)['client'];
    chromeJobs()->touch($other, 1, ['tiktok_user_id' => '999']);
    expect(chromeJobs()->claimNext($other))->toBeNull();

    $claimed = chromeJobs()->claimNext($client);
    expect($claimed->id)->toBe($job->id)->and($claimed->state)->toBe('claimed')->and($claimed->claim_token)->not->toBeNull();
    expect(chromeJobs()->claimNext($client))->toBeNull();
});

test('claimNext xét mọi tài khoản cùng tiktok_user_id', function () {
    [, $client] = chromeSetup();
    $sa2 = SocialAccount::factory()->tiktok()->create();
    ChromeAccount::create(['social_account_id' => $sa2->id, 'enabled' => true, 'tiktok_user_id' => CHROME_UID, 'chrome_only' => false]);
    $job = chromeJobs()->queueForPost(chromePost($sa2), 'now');

    expect(chromeJobs()->claimNext($client)?->id)->toBe($job->id);
});

test('authorize hai lần chỉ thắng một', function () {
    [$sa, $client] = chromeSetup();
    $job = chromeReady(chromeJobs()->queueForPost(chromePost($sa), 'now'), $client);

    expect(chromeJobs()->authorize($job, str_repeat('a', 64), 'cid'))->toBeTrue();
    expect(chromeJobs()->authorize($job, str_repeat('a', 64), 'cid'))->toBeFalse();
    expect($job->refresh()->state)->toBe('authorized')->and($job->auth_creation_id)->toBe('cid');
});

test('authorize và revoke tranh nhau: chỉ một bên thắng', function () {
    [$sa, $client] = chromeSetup();

    // revoke trước: authorize thua và không bao giờ cấp quyền
    $job = chromeReady(chromeJobs()->queueForPost(chromePost($sa), 'now'), $client);
    expect(chromeJobs()->revoke($job->id, 'huỷ'))->toBeTrue();
    expect(chromeJobs()->authorize($job, str_repeat('b', 64), 'c'))->toBeFalse();
    expect($job->refresh()->state)->toBe('revoked');

    // authorize trước: revoke thua
    $post2 = chromePost($sa, [], [], 'v/two.mp4');
    $job2 = chromeReady(chromeJobs()->queueForPost($post2, 'now'), $client);
    expect(chromeJobs()->authorize($job2, str_repeat('b', 64), 'c'))->toBeTrue();
    expect(chromeJobs()->revoke($job2->id, 'muộn'))->toBeFalse();
    expect($job2->refresh()->state)->toBe('authorized');
});

test('authorize chỉ thắng khi job đang ready và attempt mới nhất', function () {
    [$sa, $client] = chromeSetup();
    $post = chromePost($sa);
    $job = chromeJobs()->queueForPost($post, 'now');
    $claimed = chromeJobs()->claimNext($client);

    expect(chromeJobs()->authorize($claimed, str_repeat('a', 64), 'c'))->toBeFalse(); // chưa ready
    expect(chromeJobs()->stateRefusal($job))->toBe('not-ready');
});

test('kết quả trùng không đổi trạng thái, chỉ tăng bộ đếm', function () {
    [$sa, $client] = chromeSetup();
    $job = chromeReady(chromeJobs()->queueForPost(chromePost($sa), 'now'), $client);
    chromeJobs()->authorize($job, str_repeat('a', 64), 'c');

    $first = chromeJobs()->ingestResult($job->id, ['outcome' => 'posted', 'item_id' => '7300000000000000001']);
    expect($first)->toBe(['duplicate' => false, 'state' => 'posted']);

    $second = chromeJobs()->ingestResult($job->id, ['outcome' => 'rejected', 'status_code' => 5]);
    expect($second)->toBe(['duplicate' => true, 'state' => 'posted']);

    $job->refresh();
    expect($job->state)->toBe('posted')->and($job->duplicate_results)->toBe(1)->and($job->result['item_id'])->toBe('7300000000000000001');

    $outcome = chromeJobs()->outcome($job);
    expect($outcome->ok)->toBeTrue()->and($outcome->videoId)->toBe('7300000000000000001')->and($outcome->scheduledFor)->toBeNull();
});

test('báo posted khi chưa được cấp quyền không bao giờ thành posted', function () {
    [$sa, $client] = chromeSetup();

    foreach (['queued', 'ready', 'revoked'] as $i => $state) {
        $post = chromePost($sa, [], [], "v/x{$i}.mp4");
        $job = chromeJobs()->queueForPost($post, 'now');

        if ($state !== 'queued') {
            $job = chromeReady($job, $client);
        }
        if ($state === 'revoked') {
            chromeJobs()->revoke($job->id, 'thu hồi');
        }

        $result = chromeJobs()->ingestResult($job->id, ['outcome' => 'posted', 'item_id' => '1']);

        expect($result['state'])->not->toBe('posted')->and($result['state'])->toBe('uncertain');
        expect(chromeJobs()->outcome($job->refresh())->uncertain)->toBeTrue();
    }
});

test('báo failed khi chưa cấp quyền là lỗi dứt khoát', function () {
    [$sa, $client] = chromeSetup();
    $job = chromeReady(chromeJobs()->queueForPost(chromePost($sa), 'now'), $client);

    expect(chromeJobs()->ingestResult($job->id, ['outcome' => 'failed', 'reason' => 'no-upload'])['state'])->toBe('failed');
    $o = chromeJobs()->outcome($job->refresh());
    expect($o->ok)->toBeFalse()->and($o->uncertain)->toBeFalse();
});

test('authorized quá hạn thành uncertain và bài uncertain không tự đăng lại', function () {
    [$sa, $client] = chromeSetup();
    $post = chromePost($sa);
    $job = chromeReady(chromeJobs()->queueForPost($post, 'now'), $client);
    chromeJobs()->authorize($job, str_repeat('a', 64), 'c');

    chromeJobs()->reconcile(CarbonImmutable::now()->addSeconds(ChromeJobs::RESULT_WITHIN - 5));
    expect($job->refresh()->state)->toBe('authorized');

    chromeJobs()->reconcile(CarbonImmutable::now()->addSeconds(ChromeJobs::RESULT_WITHIN + 5));
    expect($job->refresh()->state)->toBe('uncertain');
    expect(chromeJobs()->revoke($job->id, 'x'))->toBeFalse();
    expect(chromeJobs()->claimNext($client))->toBeNull();
    expect(chromeJobs()->outcome($job)->uncertain)->toBeTrue();

    // kết quả muộn là kết quả thật
    expect(chromeJobs()->ingestResult($job->id, ['outcome' => 'posted'])['state'])->toBe('posted');
});

test('reconcile thu hồi job queued quá hạn nhận, ghi chú khác nhau theo chế độ', function () {
    [$sa] = chromeSetup();
    $now = chromeJobs()->queueForPost(chromePost($sa), 'now');

    chromeJobs()->reconcile(CarbonImmutable::now()->addMinutes(60));
    expect($now->refresh()->state)->toBe('queued');

    chromeJobs()->reconcile(CarbonImmutable::now()->addHours(3));
    expect($now->refresh()->state)->toBe('revoked')->and($now->note)->toBe(ChromeJobs::MISSED_NOW_TEXT);

    $at = CarbonImmutable::now()->addDays(1);
    $sched = chromeJobs()->queueForPost(chromePost($sa, [], ['scheduled_at' => $at], 'v/s.mp4'), 'scheduled');
    chromeJobs()->reconcile($at->subMinutes(30));
    expect($sched->refresh()->state)->toBe('revoked')->and($sched->note)->toBe(ChromeJobs::MISSED_SCHEDULED_TEXT);
});

test('reconcile thu hồi job mất heartbeat hoặc tải quá lâu', function () {
    [$sa, $client] = chromeSetup();
    $job = chromeJobs()->queueForPost(chromePost($sa), 'now');
    $claimed = chromeJobs()->claimNext($client);
    chromeJobs()->heartbeat($claimed);

    chromeJobs()->reconcile(CarbonImmutable::now()->addSeconds(ChromeJobs::STALE_AFTER + 10));
    expect($job->refresh()->state)->toBe('revoked')->and($job->note)->toBe(ChromeJobs::STALLED_TEXT);

    $post2 = chromePost($sa, [], [], 'v/long.mp4');
    $job2 = chromeJobs()->queueForPost($post2, 'now');
    chromeJobs()->heartbeat(chromeJobs()->claimNext($client));
    ChromeJob::query()->where('id', $job2->id)->update(['heartbeat_at' => now()->addMinutes(20)]);
    chromeJobs()->reconcile(CarbonImmutable::now()->addSeconds(ChromeJobs::UPLOAD_WITHIN + 10));
    expect($job2->refresh()->state)->toBe('revoked')->and($job2->note)->toBe(ChromeJobs::TOO_LONG_TEXT);
});

test('claim mồ côi quay về queued với token và nonce mới', function () {
    [$sa, $client] = chromeSetup();
    $job = chromeJobs()->queueForPost(chromePost($sa), 'now');
    $claimed = chromeJobs()->claimNext($client);
    $oldNonce = $claimed->nonce;

    chromeJobs()->reconcile(CarbonImmutable::now()->addSeconds(ChromeJobs::ORPHAN_CLAIM_AFTER - 5));
    expect($job->refresh()->state)->toBe('claimed');

    chromeJobs()->reconcile(CarbonImmutable::now()->addSeconds(ChromeJobs::ORPHAN_CLAIM_AFTER + 5));
    $job->refresh();
    expect($job->state)->toBe('queued')->and($job->claim_token)->toBeNull()->and($job->nonce)->not->toBe($oldNonce);

    // client cũ không còn authorize được
    expect(chromeJobs()->authorize($claimed, str_repeat('a', 64), 'c'))->toBeFalse();
});

test('releaseClaim chỉ hoàn tác khi còn claimed', function () {
    [$sa, $client] = chromeSetup();
    chromeJobs()->queueForPost(chromePost($sa), 'now');
    $claimed = chromeJobs()->claimNext($client);

    expect(chromeJobs()->releaseClaim($claimed))->toBeTrue();
    $again = chromeJobs()->claimNext($client);
    chromeJobs()->heartbeat($again);
    expect(chromeJobs()->releaseClaim($again->refresh()))->toBeFalse();
});

test('requestCancel: trước authorize thì thu hồi, sau authorize chỉ ghi nhận', function () {
    [$sa, $client] = chromeSetup();
    $job = chromeReady(chromeJobs()->queueForPost(chromePost($sa), 'now'), $client);
    expect(chromeJobs()->requestCancel($job, 'người dùng'))->toBe(['state' => 'revoked', 'cancel_recorded' => false]);

    $job2 = chromeReady(chromeJobs()->queueForPost(chromePost($sa, [], [], 'v/c.mp4'), 'now'), $client);
    chromeJobs()->authorize($job2, str_repeat('a', 64), 'c');
    expect(chromeJobs()->requestCancel($job2, null))->toBe(['state' => 'authorized', 'cancel_recorded' => true]);
    expect($job2->refresh()->cancel_requested)->toBeTrue();
});

test('authorizeRefusal kiểm tra danh tính, ràng buộc và lịch', function () {
    [$sa, $client] = chromeSetup();
    $job = chromeReady(chromeJobs()->queueForPost(chromePost($sa), 'now'), $client);
    $ok = ['body_sha256' => str_repeat('a', 64), 'creation_id' => 'c', 'identity' => ['user_id' => CHROME_UID], 'visibility_type' => 0, 'schedule_time' => null];

    expect(chromeJobs()->authorizeRefusal($job, $client, $ok, 1))->toBeNull();
    expect(chromeJobs()->authorizeRefusal($job, $client, $ok, 9))->toBe('need-reload');
    expect(chromeJobs()->authorizeRefusal($job, $client, [...$ok, 'body_sha256' => 'x'], 1))->toBe('bad-binding');
    expect(chromeJobs()->authorizeRefusal($job, $client, [...$ok, 'identity' => ['user_id' => '1']], 1))->toBe('identity-mismatch');
    expect(chromeJobs()->authorizeRefusal($job, $client, [...$ok, 'visibility_type' => 1], 1))->toBe('visibility-mismatch');
    expect(chromeJobs()->authorizeRefusal($job, $client, [...$ok, 'schedule_time' => time() + 3600], 1))->toBe('schedule-mismatch');

    $dup = chromeJobs()->createClient($client->account_id, 'trùng', '1', 1)['client'];
    chromeJobs()->touch($dup, 1, ['tiktok_user_id' => CHROME_UID]);
    expect(chromeJobs()->authorizeRefusal($job, $client, $ok, 1))->toBe('identity-conflict');
    expect(chromeJobs()->clientStatus($client))->toBe('conflict');
    expect(chromeJobs()->readiness($sa)['reason'])->toBe('chrome_conflict');
});

test('authorizeRefusal cho job hẹn giờ so khớp schedule_time', function () {
    [$sa, $client] = chromeSetup();
    $at = CarbonImmutable::now()->addDays(2)->startOfMinute();
    $job = chromeReady(chromeJobs()->queueForPost(chromePost($sa, [], ['scheduled_at' => $at]), 'scheduled'), $client);
    $ok = ['body_sha256' => str_repeat('a', 64), 'creation_id' => 'c', 'identity' => ['user_id' => CHROME_UID], 'visibility_type' => 0];

    expect(chromeJobs()->authorizeRefusal($job, $client, [...$ok, 'schedule_time' => $at->getTimestamp()], 1))->toBeNull();
    expect(chromeJobs()->authorizeRefusal($job, $client, [...$ok, 'schedule_time' => $at->getTimestamp() + 300], 1))->toBeNull();
    expect(chromeJobs()->authorizeRefusal($job, $client, [...$ok, 'schedule_time' => $at->getTimestamp() + 900], 1))->toBe('schedule-mismatch');
    expect(chromeJobs()->authorizeRefusal($job, $client, [...$ok, 'schedule_time' => null], 1))->toBe('schedule-mismatch');
});

test('mã ghép nối: đúng thì dùng một lần, sai 5 lần thì mất mã, hết hạn thì no_code', function () {
    $pair = chromeJobs()->newPairCode('acc-1');
    expect($pair['code'])->toMatch('/^\d{6}$/')->and($pair['valid_s'])->toBe(300);

    expect(chromeJobs()->usePairCode($pair['code']))->toMatchArray(['ok' => true, 'account_id' => 'acc-1']);
    expect(chromeJobs()->usePairCode($pair['code'])['error'])->toBe('no_code');

    $pair = chromeJobs()->newPairCode('acc-1');
    $wrong = $pair['code'] === '000000' ? '111111' : '000000';
    expect(chromeJobs()->usePairCode($wrong))->toMatchArray(['ok' => false, 'error' => 'bad_code', 'tries_left' => 4]);
    foreach ([3, 2, 1] as $left) {
        expect(chromeJobs()->usePairCode($wrong)['tries_left'])->toBe($left);
    }
    expect(chromeJobs()->usePairCode($wrong)['error'])->toBe('no_code');
    expect(chromeJobs()->usePairCode($pair['code'])['ok'])->toBeFalse(); // mã đã cháy

    $pair = chromeJobs()->newPairCode('acc-1');
    $old = chromeJobs()->newPairCode('acc-1'); // mã mới thay mã cũ
    expect($old['code'])->toBeString();
    $this->travel(6)->minutes();
    expect(chromeJobs()->usePairCode($old['code'])['error'])->toBe('no_code');
});

test('token: chỉ client chưa thu hồi mới hợp lệ', function () {
    $workspace = Workspace::factory()->create();
    ['client' => $client, 'token' => $token] = chromeJobs()->createClient($workspace->account_id, 'x', '1.0', 1);

    expect(chromeJobs()->clientForToken($token)?->id)->toBe($client->id);
    expect(chromeJobs()->clientForToken($token.'x'))->toBeNull();
    expect(chromeJobs()->clientForToken(''))->toBeNull();

    $client->update(['revoked_at' => now()]);
    expect(chromeJobs()->clientForToken($token))->toBeNull();
});

test('trạng thái Chrome và readiness', function () {
    [$sa, $client] = chromeSetup();

    expect(chromeJobs()->isOnline($client))->toBeTrue()
        ->and(chromeJobs()->clientStatus($client))->toBe('ok')
        ->and(chromeJobs()->readiness($sa))->toBe(['ok' => true, 'reason' => 'ok'])
        ->and(chromeJobs()->isChromeAccount($sa))->toBeTrue()
        ->and(chromeJobs()->boundAccount(CHROME_UID)?->social_account_id)->toBe($sa->id)
        ->and(chromeJobs()->boundAccount('nope'))->toBeNull();

    $client->update(['last_seen_at' => now()->subMinutes(5)]);
    expect(chromeJobs()->clientStatus($client->refresh()))->toBe('offline')
        ->and(chromeJobs()->readiness($sa)['reason'])->toBe('chrome_offline');

    $client->update(['last_seen_at' => now(), 'protocol' => 2]);
    expect(chromeJobs()->clientStatus($client->refresh()))->toBe('need_reload');

    $client->update(['protocol' => 1, 'tiktok_user_id' => null]);
    expect(chromeJobs()->clientStatus($client->refresh()))->toBe('no_identity');

    ChromeAccount::query()->update(['tiktok_user_id' => null]);
    expect(chromeJobs()->readiness($sa)['reason'])->toBe('chrome_unbound');
});

test('launchRequests: chỉ khi Chrome offline, biết profile, chưa mở trong 3 phút', function () {
    [$sa, $client] = chromeSetup();
    $job = chromeJobs()->queueForPost(chromePost($sa), 'now');

    expect(chromeJobs()->launchRequests())->toBe([]); // đang online

    $client->update(['last_seen_at' => now()->subMinutes(10)]);
    expect(chromeJobs()->launchRequests())->toBe([]); // chưa biết profile

    $client->update(['chrome_profile_dir' => 'Profile 1']);
    expect(chromeJobs()->launchRequests())->toBe([['client_id' => $client->id, 'profile_dir' => 'Profile 1', 'browser' => 'chrome', 'job_id' => $job->id]]);

    chromeJobs()->markLaunched($client->id, $job->id);
    expect(chromeJobs()->launchRequests())->toBe([]);

    expect(chromeJobs()->launchRequests(CarbonImmutable::now()->addMinutes(4)))->toHaveCount(1);
});

test('outcome cho job hẹn giờ đã đăng và job bị từ chối', function () {
    [$sa, $client] = chromeSetup();
    $at = CarbonImmutable::now()->addDays(2)->startOfMinute();
    $job = chromeReady(chromeJobs()->queueForPost(chromePost($sa, [], ['scheduled_at' => $at]), 'scheduled'), $client);
    chromeJobs()->authorize($job, str_repeat('a', 64), 'c');
    chromeJobs()->ingestResult($job->id, ['outcome' => 'posted', 'item_id' => 5]);

    $o = chromeJobs()->outcome($job->refresh());
    expect($o->ok)->toBeTrue()->and($o->videoId)->toBe('5')->and($o->scheduledFor?->equalTo($at))->toBeTrue();

    $job2 = chromeReady(chromeJobs()->queueForPost(chromePost($sa, [], [], 'v/r.mp4'), 'now'), $client);
    chromeJobs()->authorize($job2, str_repeat('a', 64), 'c');
    chromeJobs()->ingestResult($job2->id, ['outcome' => 'rejected', 'status_code' => 7, 'status_msg' => 'spam']);
    expect(chromeJobs()->outcome($job2->refresh())->message)->toContain('status_code 7: spam');
});

test('queueForPost báo busy khi tài khoản có job mở của bài khác, refusal khác thì không', function () {
    [$sa] = chromeSetup();
    chromeJobs()->queueForPost(chromePost($sa), 'now');

    try {
        chromeJobs()->queueForPost(chromePost($sa, [], [], 'v/b.mp4'), 'now');
        $this->fail('phải ném ChromeRefusal');
    } catch (ChromeRefusal $e) {
        expect($e->busy)->toBeTrue();
    }

    try {
        chromeJobs()->queueForPost(chromePost($sa, [], ['content' => '']), 'now');
        $this->fail('phải ném ChromeRefusal');
    } catch (ChromeRefusal $e) {
        expect($e->busy)->toBeFalse();
    }
});

test('queueForPost từ chối caption rỗng hoặc dài hơn 2200 ký tự', function () {
    [$sa] = chromeSetup();

    expect(fn () => chromeJobs()->queueForPost(chromePost($sa, [], ['content' => '']), 'now'))->toThrow(ChromeRefusal::class);
    expect(fn () => chromeJobs()->queueForPost(chromePost($sa, [], ['content' => str_repeat('a', 2201)]), 'now'))->toThrow(ChromeRefusal::class);
});

test('queueForPost đọc lại bài mới nhất từ DB', function () {
    [$sa] = chromeSetup();
    $stale = chromePost($sa);
    Post::find($stale->id)->update(['content' => 'NOI DUNG MOI']);

    expect(chromeJobs()->queueForPost($stale, 'now')->caption)->toContain('NOI DUNG MOI');
});

test('queueForPost tự từ chối khi job mới nhất là authorized/uncertain/posted', function (string $state) {
    [$sa] = chromeSetup();
    $post = chromePost($sa);
    chromeJobs()->queueForPost($post, 'now')->update(['state' => $state]);

    expect(fn () => chromeJobs()->queueForPost($post, 'now'))->toThrow(ChromeRefusal::class);
})->with(['authorized', 'uncertain', 'posted']);

test('queueForPost dừng khi đã đạt MAX_ATTEMPTS', function () {
    [$sa] = chromeSetup();
    $post = chromePost($sa);

    for ($i = 1; $i <= ChromeJobs::MAX_ATTEMPTS; $i++) {
        chromeJobs()->queueForPost($post, 'now')->update(['state' => 'revoked', 'note' => ChromeJobs::MISSED_NOW_TEXT]);
    }

    expect(fn () => chromeJobs()->queueForPost($post, 'now'))->toThrow(ChromeRefusal::class, 'thử lại bằng cách nhân bản bài');
});

test('requestCancel chỉ nối CANCEL_TEXT một lần', function () {
    [$sa] = chromeSetup();
    $job = chromeJobs()->queueForPost(chromePost($sa), 'now');

    chromeJobs()->requestCancel($job, 'owner-cleared');

    expect($job->refresh()->note)->toBe(ChromeJobs::CANCEL_TEXT.' (owner-cleared)');
});

test('heartbeat của client cũ (claim_token đã xoay) không đẩy được job', function () {
    [$sa, $client] = chromeSetup();
    chromeJobs()->queueForPost(chromePost($sa), 'now');
    $stale = chromeJobs()->claimNext($client);
    $old = ChromeJob::find($stale->id);

    ChromeJob::query()->whereKey($stale->id)->update(['claim_token' => 'tokenmoi', 'nonce' => 'noncemoi']);
    chromeJobs()->heartbeat($old, true);

    expect(ChromeJob::find($stale->id)->state)->toBe('claimed');
});

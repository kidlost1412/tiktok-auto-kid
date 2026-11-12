<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AnchorTemplate;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use Illuminate\Testing\TestResponse;

const EXT_ORIGIN = 'chrome-extension://poffpbdhahodnkoandkagilkbhaipolo';
const EXT_USER_ID = '7012345678901234567';
const EXT_VIDEO_BYTES = '0123456789abcdefghij';

beforeEach(function () {
    config()->set('fork.chrome.extension_origin', EXT_ORIGIN);
    config()->set('fork.chrome.next_max_wait', 10);
    Cache::forget('fork:chrome:pair');
    Storage::fake();

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create([
        'account_id' => $this->account->id,
        'user_id' => $this->owner->id,
    ]);
    $this->social = SocialAccount::factory()->tiktok()->create([
        'workspace_id' => $this->workspace->id,
        'username' => 'mt.tri.2.pin',
    ]);
    ChromeAccount::query()->create([
        'social_account_id' => $this->social->id,
        'enabled' => true,
        'tiktok_user_id' => EXT_USER_ID,
        'chrome_only' => false,
    ]);

    $this->chrome = app(ChromeJobs::class);
});

function extHeaders(?string $token = null, int $protocol = 1): array
{
    return array_filter([
        'Authorization' => $token ? 'Bearer '.$token : null,
        'X-Autotok-Protocol' => (string) $protocol,
        'X-Requested-With' => 'autotok',
    ]);
}

/** Ghép nối thật qua API rồi trả token. */
function pairExtension(object $test, ?string $label = 'Chrome Vườn'): string
{
    $code = $test->chrome->newPairCode($test->account->id)['code'];

    $response = $test->postJson('/api/ext/pair', [
        'code' => $code, 'label' => $label, 'ext_version' => '1.0.0', 'protocol' => 1,
    ], extHeaders());

    $response->assertOk()->assertJsonPath('ok', true);

    return $response->json('token');
}

function helloAs(object $test, string $token, bool $identity = true): TestResponse
{
    return $test->postJson('/api/ext/hello', [
        'protocol' => 1,
        'ext_version' => '1.0.0',
        'identity' => $identity ? ['username' => 'mt.tri.2.pin', 'user_id' => EXT_USER_ID] : null,
    ], extHeaders($token));
}

function makeQueuedJob(object $test, string $state = 'queued', array $overrides = []): ChromeJob
{
    $post = Post::factory()->create(['workspace_id' => $test->workspace->id, 'user_id' => $test->owner->id]);
    Storage::put('fork-chrome/test.mp4', EXT_VIDEO_BYTES);

    return ChromeJob::query()->create(array_merge([
        'id' => 'ej_'.Str::random(24),
        'post_id' => $post->id,
        'social_account_id' => $test->social->id,
        'attempt' => 1,
        'mode' => 'now',
        'expect_user_id' => EXT_USER_ID,
        'media_path' => 'fork-chrome/test.mp4',
        'video_name' => 'test.mp4',
        'video_size' => strlen(EXT_VIDEO_BYTES),
        'video_mime' => 'video/mp4',
        'caption' => 'xin chào #tag',
        'options' => ['visibility_type' => 0, 'allow_comment' => 1, 'allow_duet' => 0, 'allow_stitch' => 0, 'ai_label' => 0, 'schedule_time' => null],
        'state' => $state,
        'nonce' => bin2hex(random_bytes(16)),
        'deliver_by' => now()->addHours(5),
    ], $overrides));
}

test('full cycle: pair, hello, next, progress ready, authorize, result posted', function () {
    $token = pairExtension($this);

    helloAs($this, $token)
        ->assertOk()
        ->assertJsonPath('ok', true)
        ->assertJsonPath('need_reload', false)
        ->assertJsonPath('conflict', false)
        ->assertJsonPath('account.id', $this->social->id)
        ->assertJsonPath('account.username', 'mt.tri.2.pin')
        ->assertJsonPath('account.publisher', 'chrome')
        ->assertJsonPath('protocol_min', 1)
        ->assertJsonPath('protocol_max', 1);

    $job = makeQueuedJob($this);

    $next = $this->getJson('/api/ext/next?wait=0', extHeaders($token));
    $next->assertOk()
        ->assertJsonPath('id', $job->id)
        ->assertJsonPath('mode', 'post')
        ->assertJsonPath('caption', 'xin chào #tag')
        ->assertJsonPath('expect_user_id', EXT_USER_ID)
        ->assertJsonPath('expect_account', 'mt.tri.2.pin')
        ->assertJsonPath('visibility', 'public');

    $nonce = $next->json('nonce');
    $claim = $next->json('claim_token');
    expect($nonce)->toBeString()->and($claim)->toBeString();

    // Không cấp lại lần hai.
    $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertNoContent();

    $own = ['id' => $job->id, 'nonce' => $nonce, 'claim_token' => $claim];

    $this->postJson('/api/ext/progress', $own + ['phase' => 'upload', 'pct' => 40], extHeaders($token))
        ->assertOk()->assertJsonPath('ok', true)->assertJsonPath('state', 'uploading');

    $this->getJson('/api/ext/job_state?id='.$job->id, extHeaders($token))
        ->assertOk()->assertJsonPath('state', 'uploading')->assertJsonPath('authorized', false);

    $this->postJson('/api/ext/progress', $own + ['phase' => 'ready'], extHeaders($token))
        ->assertOk()->assertJsonPath('state', 'ready');

    $this->postJson('/api/ext/authorize', $own + [
        'body_sha256' => str_repeat('a', 64),
        'creation_id' => 'c-1',
        'visibility_type' => 0,
        'schedule_time' => null,
        'identity' => ['username' => 'mt.tri.2.pin', 'user_id' => EXT_USER_ID],
    ], extHeaders($token))->assertOk()->assertExactJson(['ok' => true]);

    // Cấp quyền lần hai không thắng.
    $this->postJson('/api/ext/authorize', $own + [
        'body_sha256' => str_repeat('a', 64),
        'creation_id' => 'c-1',
        'visibility_type' => 0,
        'schedule_time' => null,
        'identity' => ['username' => 'mt.tri.2.pin', 'user_id' => EXT_USER_ID],
    ], extHeaders($token))->assertOk()->assertJsonPath('ok', false)->assertJsonPath('reason', 'already-authorized');

    $this->getJson('/api/ext/job_state?id='.$job->id, extHeaders($token))
        ->assertJsonPath('state', 'authorized')->assertJsonPath('authorized', true);

    $this->postJson('/api/ext/result', $own + [
        'outcome' => 'posted', 'definite' => true, 'item_id' => '7701245450858351893', 'http' => 200,
    ], extHeaders($token))
        ->assertOk()
        ->assertExactJson(['ok' => true, 'duplicate' => false, 'state' => 'posted']);

    // Kết quả trùng không đổi gì.
    $this->postJson('/api/ext/result', $own + ['outcome' => 'failed', 'definite' => true], extHeaders($token))
        ->assertOk()
        ->assertExactJson(['ok' => true, 'duplicate' => true, 'state' => 'posted']);

    expect($job->fresh()->state)->toBe('posted');
});

test('requests without a valid token get 401', function () {
    $this->getJson('/api/ext/next?wait=0', extHeaders())
        ->assertStatus(401)
        ->assertJsonPath('ok', false)
        ->assertJsonPath('error', 'unauthorized');

    $this->postJson('/api/ext/hello', [], extHeaders('khong-co-token'))
        ->assertStatus(401)
        ->assertJsonPath('error', 'unauthorized');
});

test('a revoked client token is refused', function () {
    $token = pairExtension($this);
    $client = $this->chrome->clientForToken($token);
    $client->update(['revoked_at' => now()]);

    $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertStatus(401);
});

test('pairing reports bad code with tries left and no code', function () {
    $this->postJson('/api/ext/pair', ['code' => '123456', 'protocol' => 1], extHeaders())
        ->assertStatus(410)->assertJsonPath('error', 'no_code');

    $code = $this->chrome->newPairCode($this->account->id)['code'];
    $wrong = $code === '000000' ? '111111' : '000000';

    $this->postJson('/api/ext/pair', ['code' => $wrong, 'protocol' => 1], extHeaders())
        ->assertStatus(403)
        ->assertJsonPath('error', 'bad_code')
        ->assertJsonPath('tries_left', 4);

    $this->postJson('/api/ext/pair', ['code' => $code, 'protocol' => 2], extHeaders())
        ->assertStatus(409)->assertJsonPath('error', 'need_reload')->assertJsonPath('need_reload', true);
});

test('a job body must be a JSON object', function () {
    $token = pairExtension($this);

    $this->call('POST', '/api/ext/progress', [], [], [], [
        'CONTENT_TYPE' => 'application/json',
        'HTTP_AUTHORIZATION' => 'Bearer '.$token,
        'HTTP_X_AUTOTOK_PROTOCOL' => '1',
    ], '[1,2]')->assertStatus(400)->assertJsonPath('error', 'bad_request');
});

test('wrong nonce or claim token gives 403 bad_nonce and unknown job gives 404', function () {
    $token = pairExtension($this);
    helloAs($this, $token);
    $job = makeQueuedJob($this);
    $next = $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertOk();

    $this->postJson('/api/ext/progress', [
        'id' => $job->id, 'nonce' => 'sai', 'claim_token' => $next->json('claim_token'), 'phase' => 'upload',
    ], extHeaders($token))->assertStatus(403)->assertJsonPath('error', 'bad_nonce');

    $this->postJson('/api/ext/result', [
        'id' => $job->id, 'nonce' => $next->json('nonce'), 'claim_token' => 'sai', 'outcome' => 'posted',
    ], extHeaders($token))->assertStatus(403)->assertJsonPath('error', 'bad_nonce');

    expect($job->fresh()->state)->toBe('claimed');

    $this->postJson('/api/ext/progress', [
        'id' => 'ej_khongco', 'nonce' => 'x', 'claim_token' => 'y',
    ], extHeaders($token))->assertStatus(404)->assertJsonPath('error', 'unknown_job');

    $this->getJson('/api/ext/job_state?id=ej_khongco', extHeaders($token))->assertStatus(404);
});

test('authorize with the wrong nonce is refused and never granted', function () {
    $token = pairExtension($this);
    helloAs($this, $token);
    $job = makeQueuedJob($this);
    $next = $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertOk();
    $own = ['id' => $job->id, 'nonce' => $next->json('nonce'), 'claim_token' => $next->json('claim_token')];

    $this->postJson('/api/ext/progress', $own + ['phase' => 'ready'], extHeaders($token))->assertOk();

    $this->postJson('/api/ext/authorize', ['id' => $job->id, 'nonce' => 'sai', 'claim_token' => $own['claim_token'],
        'body_sha256' => str_repeat('b', 64), 'creation_id' => 'c'], extHeaders($token))
        ->assertStatus(403)->assertJsonPath('error', 'bad_nonce');

    expect($job->fresh()->state)->toBe('ready')->and($job->fresh()->authorized_at)->toBeNull();
});

test('a protocol outside the range gives need_reload', function () {
    $token = pairExtension($this);

    helloAs($this, $token)->assertOk();

    $this->getJson('/api/ext/next?wait=0', extHeaders($token, 7))
        ->assertStatus(409)
        ->assertJsonPath('error', 'need_reload')
        ->assertJsonPath('need_reload', true);

    // hello vẫn 200 nhưng báo cần tải lại.
    $this->postJson('/api/ext/hello', ['protocol' => 7, 'ext_version' => '9.9.9', 'identity' => null], extHeaders($token, 7))
        ->assertOk()
        ->assertJsonPath('need_reload', true)
        ->assertJsonPath('message', 'Cần tải lại tiện ích (chrome://extensions → ⟳)');
});

test('next refuses a client that has no TikTok identity', function () {
    $token = pairExtension($this);
    helloAs($this, $token, identity: false)->assertOk()->assertJsonPath('account', null);

    $this->getJson('/api/ext/next?wait=0', extHeaders($token))
        ->assertStatus(409)->assertJsonPath('error', 'no_identity');
});

test('hello rejects a malformed identity', function () {
    $token = pairExtension($this);

    $this->postJson('/api/ext/hello', [
        'protocol' => 1, 'identity' => ['username' => 'mt.tri', 'user_id' => 'abc'],
    ], extHeaders($token))->assertStatus(400)->assertJsonPath('error', 'bad_request');
});

test('cancel before authorization revokes the job and progress then reports cancelled', function () {
    $token = pairExtension($this);
    helloAs($this, $token);
    $job = makeQueuedJob($this);
    $next = $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertOk();
    $own = ['id' => $job->id, 'nonce' => $next->json('nonce'), 'claim_token' => $next->json('claim_token')];

    $this->postJson('/api/ext/cancel', $own + ['reason' => 'owner-cleared'], extHeaders($token))
        ->assertOk()
        ->assertExactJson(['ok' => true, 'state' => 'revoked', 'cancel_recorded' => false]);

    $this->postJson('/api/ext/progress', $own + ['phase' => 'upload'], extHeaders($token))
        ->assertOk()
        ->assertJsonPath('ok', false)
        ->assertJsonPath('state', 'revoked')
        ->assertJsonPath('cancelled', true);
});

test('cancel after authorization is only recorded', function () {
    $token = pairExtension($this);
    helloAs($this, $token);
    $job = makeQueuedJob($this);
    $next = $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertOk();
    $own = ['id' => $job->id, 'nonce' => $next->json('nonce'), 'claim_token' => $next->json('claim_token')];

    $this->postJson('/api/ext/progress', $own + ['phase' => 'ready'], extHeaders($token))->assertOk();
    $this->postJson('/api/ext/authorize', $own + [
        'body_sha256' => str_repeat('c', 64), 'creation_id' => 'c', 'visibility_type' => 0, 'schedule_time' => null,
        'identity' => ['username' => 'mt.tri.2.pin', 'user_id' => EXT_USER_ID],
    ], extHeaders($token))->assertJsonPath('ok', true);

    $this->postJson('/api/ext/cancel', $own, extHeaders($token))
        ->assertOk()
        ->assertExactJson(['ok' => true, 'state' => 'authorized', 'cancel_recorded' => true]);

    expect($job->fresh()->state)->toBe('authorized');
});

test('video meta and ranged video stream for the claiming client', function () {
    $token = pairExtension($this);
    helloAs($this, $token);
    $job = makeQueuedJob($this);
    $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertOk();

    $this->getJson('/api/ext/video/meta?id='.$job->id, extHeaders($token))
        ->assertOk()
        ->assertExactJson(['name' => 'test.mp4', 'size' => strlen(EXT_VIDEO_BYTES), 'type' => 'video/mp4']);

    $range = $this->get('/api/ext/video?id='.$job->id, extHeaders($token) + ['Range' => 'bytes=2-5']);
    $range->assertStatus(206);
    expect($range->headers->get('Content-Range'))->toBe('bytes 2-5/20')
        ->and($range->headers->get('Content-Length'))->toBe('4')
        ->and($range->headers->get('Accept-Ranges'))->toBe('bytes')
        ->and($range->streamedContent())->toBe('2345');

    $suffix = $this->get('/api/ext/video?id='.$job->id, extHeaders($token) + ['Range' => 'bytes=-3']);
    $suffix->assertStatus(206);
    expect($suffix->streamedContent())->toBe('hij');

    $open = $this->get('/api/ext/video?id='.$job->id, extHeaders($token) + ['Range' => 'bytes=15-']);
    expect($open->streamedContent())->toBe('fghij');

    $full = $this->get('/api/ext/video?id='.$job->id, extHeaders($token));
    $full->assertOk();
    expect($full->streamedContent())->toBe(EXT_VIDEO_BYTES);

    $this->get('/api/ext/video?id='.$job->id, extHeaders($token) + ['Range' => 'bytes=99-120'])
        ->assertStatus(416);
    $bad = $this->get('/api/ext/video?id='.$job->id, extHeaders($token) + ['Range' => 'items=1-2']);
    $bad->assertStatus(416);
    expect($bad->headers->get('Content-Range'))->toBe('bytes */20');
});

test('video is only served to the client that claimed the job', function () {
    $token = pairExtension($this);
    $other = pairExtension($this, 'Chrome khác');
    helloAs($this, $token);
    $job = makeQueuedJob($this);
    $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertOk();

    $this->getJson('/api/ext/video/meta?id='.$job->id, extHeaders($other))
        ->assertStatus(403)->assertJsonPath('error', 'bad_nonce');
});

test('video of a queued job that nobody claimed is refused', function () {
    $token = pairExtension($this);
    $job = makeQueuedJob($this);

    $this->getJson('/api/ext/video/meta?id='.$job->id, extHeaders($token))->assertStatus(403);
});

test('CORS headers only appear for the extension origin', function () {
    $token = pairExtension($this);

    $ok = $this->withHeaders(extHeaders($token) + ['Origin' => EXT_ORIGIN])->getJson('/api/ext/next?wait=0');
    expect($ok->headers->get('Access-Control-Allow-Origin'))->toBe(EXT_ORIGIN)
        ->and($ok->headers->get('Access-Control-Expose-Headers'))->toBe('Content-Range, Content-Length, Accept-Ranges');

    $bad = $this->withHeaders(extHeaders($token) + ['Origin' => 'https://evil.example'])->getJson('/api/ext/next?wait=0');
    expect($bad->headers->has('Access-Control-Allow-Origin'))->toBeFalse();

    $none = $this->withHeaders(extHeaders($token))->getJson('/api/ext/next?wait=0');
    expect($none->headers->has('Access-Control-Allow-Origin'))->toBeFalse();
});

test('preflight answers 204 for the extension origin only', function () {
    $preflight = fn (string $origin): array => [
        'HTTP_ORIGIN' => $origin,
        'HTTP_ACCESS_CONTROL_REQUEST_METHOD' => 'POST',
        'HTTP_ACCESS_CONTROL_REQUEST_HEADERS' => 'authorization,content-type,x-autotok-protocol,x-requested-with',
    ];

    $ok = $this->call('OPTIONS', '/api/ext/hello', [], [], [], $preflight(EXT_ORIGIN));
    $ok->assertNoContent();
    expect($ok->headers->get('Access-Control-Allow-Origin'))->toBe(EXT_ORIGIN)
        ->and($ok->headers->get('Access-Control-Allow-Methods'))->toBe('GET, POST, OPTIONS')
        ->and($ok->headers->get('Access-Control-Allow-Headers'))
        ->toBe('Authorization, Content-Type, X-Requested-With, X-Autotok-Protocol, Range');

    $bad = $this->call('OPTIONS', '/api/ext/hello', [], [], [], $preflight('https://evil.example'));
    expect($bad->headers->has('Access-Control-Allow-Origin'))->toBeFalse();
});

test('CORS is never granted when no extension id is configured', function () {
    config()->set('fork.chrome.extension_origin', '');
    $token = pairExtension($this);

    $response = $this->withHeaders(extHeaders($token) + ['Origin' => EXT_ORIGIN])->getJson('/api/ext/next?wait=0');
    expect($response->headers->has('Access-Control-Allow-Origin'))->toBeFalse();
});

// ---------- K4: giỏ hàng ----------

function cartHello(object $test): string
{
    $token = pairExtension($test);
    helloAs($test, $token)->assertOk();

    return $token;
}

function shopBody(array $override = []): array
{
    return array_merge([
        'request_id' => 'req-1', 'user_id' => EXT_USER_ID, 'username' => 'mt.tri.2.pin', 'source' => 'my_shop', 'complete' => true,
        'products' => [
            ['product_id' => '1729384756001234567', 'title' => 'Nano Đồng 500ml', 'price' => '99.000đ', 'cover_url' => 'https://img.example/a.jpg', 'stock_num' => 12, 'stock_status' => 'in_stock'],
            ['product_id' => '1729384756001234568', 'title' => '[LIVESTREAM] Nano Đồng', 'price' => '89.000đ', 'cover_url' => 'http://insecure.example/b.jpg', 'stock_num' => 0, 'stock_status' => 'out_of_stock'],
        ],
    ], $override);
}

test('tasks returns the sync request flag for the bound account only', function () {
    $token = cartHello($this);

    $this->getJson('/api/ext/tasks', extHeaders($token))->assertOk()->assertExactJson(['sync_products' => null]);

    $id = app(ShopSync::class)->requestSync($this->social->id);
    $this->getJson('/api/ext/tasks', extHeaders($token))->assertOk()->assertExactJson(['sync_products' => $id]);

    $this->getJson('/api/ext/tasks')->assertUnauthorized();

    // Chrome chưa khai báo danh tính thì không nhận việc.
    $anon = pairExtension($this, 'Chrome 2');
    $this->getJson('/api/ext/tasks', extHeaders($anon))->assertOk()->assertExactJson(['sync_products' => null]);
});

test('products upsert keeps ids as strings, marks missing and clears the request flag', function () {
    $token = cartHello($this);
    $id = app(ShopSync::class)->requestSync($this->social->id);

    $this->postJson('/api/ext/products', shopBody(['request_id' => $id]), extHeaders($token))
        ->assertOk()->assertJsonPath('ok', true)->assertJsonPath('received', 2)->assertJsonPath('missing', 0);

    $rows = ShopProduct::query()->where('social_account_id', $this->social->id)->orderBy('product_id')->get();
    expect($rows)->toHaveCount(2)
        ->and($rows[0]->product_id)->toBe('1729384756001234567')
        ->and($rows[0]->stock_num)->toBe(12)
        ->and($rows[0]->cover_url)->toBe('https://img.example/a.jpg')
        ->and($rows[1]->cover_url)->toBeNull()
        ->and($rows[1]->stock_num)->toBe(0);

    $auto = AutoAccount::query()->find($this->social->id);
    expect($auto->products_sync_request)->toBeNull()->and($auto->products_synced_at)->not->toBeNull();

    // Ẩn một sản phẩm, rồi đồng bộ lại chỉ với sản phẩm đầu: sản phẩm kia thành missing, cờ ẩn giữ nguyên.
    ShopProduct::query()->where('product_id', '1729384756001234568')->update(['hidden' => true]);
    $body = shopBody();
    $body['products'] = [$body['products'][0]];
    $body['products'][0]['title'] = 'Nano Đồng 500ml (mới)';
    $this->postJson('/api/ext/products', $body, extHeaders($token))->assertOk()->assertJsonPath('missing', 1);

    $gone = ShopProduct::query()->where('product_id', '1729384756001234568')->first();
    $kept = ShopProduct::query()->where('product_id', '1729384756001234567')->first();
    expect($gone->missing)->toBeTrue()->and($gone->hidden)->toBeTrue()
        ->and($kept->missing)->toBeFalse()->and($kept->title)->toBe('Nano Đồng 500ml (mới)')
        ->and(ShopProduct::query()->count())->toBe(2);

    // Sản phẩm trở lại thì hết missing.
    $this->postJson('/api/ext/products', shopBody(), extHeaders($token))->assertOk();
    expect(ShopProduct::query()->where('missing', true)->count())->toBe(0);
});

test('an incomplete or showcase batch never marks other products missing', function () {
    $token = cartHello($this);
    $this->postJson('/api/ext/products', shopBody(), extHeaders($token))->assertOk();

    $partial = shopBody(['complete' => false]);
    $partial['products'] = [$partial['products'][0]];
    $this->postJson('/api/ext/products', $partial, extHeaders($token))->assertOk();

    $showcase = shopBody(['source' => 'showcase', 'products' => [['product_id' => '1729384756005555555', 'title' => 'Showcase', 'stock_num' => 3]]]);
    $this->postJson('/api/ext/products', $showcase, extHeaders($token))->assertOk();

    expect(ShopProduct::query()->where('missing', true)->count())->toBe(0)
        ->and(ShopProduct::query()->where('product_id', '1729384756005555555')->value('source'))->toBe('showcase');
});

test('products and anchor_template reject a mismatching user_id or username with 409', function () {
    $token = cartHello($this);

    $this->postJson('/api/ext/products', shopBody(['user_id' => '999999999']), extHeaders($token))
        ->assertStatus(409)->assertJsonPath('error', 'identity_mismatch');
    $this->postJson('/api/ext/products', shopBody(['username' => 'ai.do.khac']), extHeaders($token))->assertStatus(409);
    $this->postJson('/api/ext/anchor_template', ['user_id' => '999999999', 'username' => 'mt.tri.2.pin', 'product_id' => '1729384756001234567', 'anchors' => [['x' => 1]]], extHeaders($token))->assertStatus(409);

    // Chrome chưa có danh tính.
    $anon = pairExtension($this, 'Chrome 2');
    $this->postJson('/api/ext/products', shopBody(), extHeaders($anon))->assertStatus(409)->assertJsonPath('error', 'no_identity');

    expect(ShopProduct::query()->count())->toBe(0)->and(AnchorTemplate::query()->count())->toBe(0);
});

test('products rejects non-string, malformed ids and a bad source', function () {
    $token = cartHello($this);

    foreach ([1729384756001234567, '123', 'abc1234567', '1729384756001234567890123456'] as $bad) {
        $body = shopBody();
        $body['products'][0]['product_id'] = $bad;
        $this->postJson('/api/ext/products', $body, extHeaders($token))->assertStatus(400);
    }

    $this->postJson('/api/ext/products', shopBody(['source' => 'other']), extHeaders($token))->assertStatus(400);
    $this->postJson('/api/ext/products', shopBody(['products' => 'x']), extHeaders($token))->assertStatus(400);

    expect(ShopProduct::query()->count())->toBe(0);
});

test('anchor_template stores the newest template verbatim', function () {
    $token = cartHello($this);
    $raw = '{"user_id":"'.EXT_USER_ID.'","username":"mt.tri.2.pin","product_id":"1729384756001234567","captured_at":"2026-11-10T03:00:00Z",'
        .'"anchors":[{"type":1,"id":"1729384756001234567","extra":"{\"product_id\":\"1729384756001234567\"}","empty":{},"list":[],"big":9223372036854775808}]}';

    $this->call('POST', '/api/ext/anchor_template', [], [], [], [
        'HTTP_AUTHORIZATION' => 'Bearer '.$token, 'HTTP_X_AUTOTOK_PROTOCOL' => '1', 'CONTENT_TYPE' => 'application/json', 'HTTP_ACCEPT' => 'application/json',
    ], $raw)->assertOk()->assertJsonPath('ok', true);

    $tpl = AnchorTemplate::query()->where('social_account_id', $this->social->id)->firstOrFail();
    $stored = (string) $tpl->getRawOriginal('anchors');
    expect($tpl->product_id)->toBe('1729384756001234567')
        ->and($tpl->captured_at->toIso8601String())->toContain('2026-11-10T03:00:00')
        ->and(preg_replace('/\s+/', '', $stored))->toContain('"empty":{}')
        ->and(preg_replace('/\s+/', '', $stored))->toContain('"big":"9223372036854775808"')
        ->and($stored)->toContain('1729384756001234567');

    // Bản mới nhất thay bản cũ (mỗi kênh một mẫu).
    $this->postJson('/api/ext/anchor_template', ['user_id' => EXT_USER_ID, 'username' => 'mt.tri.2.pin', 'product_id' => '1729384756001234999', 'anchors' => [['id' => '1729384756001234999']]], extHeaders($token))->assertOk();
    expect(AnchorTemplate::query()->count())->toBe(1)->and(AnchorTemplate::query()->first()->product_id)->toBe('1729384756001234999');
});

test('anchor_template rejects empty anchors and bad product ids', function () {
    $token = cartHello($this);
    $base = ['user_id' => EXT_USER_ID, 'username' => 'mt.tri.2.pin', 'product_id' => '1729384756001234567', 'anchors' => [['a' => 1]]];

    $this->postJson('/api/ext/anchor_template', [...$base, 'anchors' => []], extHeaders($token))->assertStatus(400);
    $this->postJson('/api/ext/anchor_template', [...$base, 'anchors' => ['a' => 1]], extHeaders($token))->assertStatus(400);
    $this->postJson('/api/ext/anchor_template', [...$base, 'product_id' => 123], extHeaders($token))->assertStatus(400);
    $this->postJson('/api/ext/anchor_template', [...$base, 'product_id' => 'abc'], extHeaders($token))->assertStatus(400);

    expect(AnchorTemplate::query()->count())->toBe(0);
});

test('the /next payload has product null when the post has no shop product', function () {
    $token = cartHello($this);
    makeQueuedJob($this);

    $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertOk()->assertJsonPath('product', null);
});

test('the /next payload carries product with the account template, name cut to 30', function () {
    $token = cartHello($this);
    $job = makeQueuedJob($this);
    Post::query()->whereKey($job->post_id)->update(['meta' => json_encode(['fork_shop_product_id' => '1729384756001234567', 'fork_shop_product_name' => str_repeat('Đ', 40)])]);
    app(ShopSync::class)->saveTemplate($this->social->id, '1729384756000000001', [json_decode('{"id":"1729384756000000001","e":{}}')], null);

    $with = $this->getJson('/api/ext/next?wait=0', extHeaders($token));
    $with->assertOk()
        ->assertJsonPath('product.product_id', '1729384756001234567')
        ->assertJsonPath('product.template_product_id', '1729384756000000001')
        ->assertJsonPath('product.anchor_template.0.id', '1729384756000000001');
    expect(mb_strlen($with->json('product.product_name')))->toBe(30)
        ->and($with->getContent())->toContain('"e":{}');
});

test('payload product has a null template when the account never captured one', function () {
    $token = cartHello($this);
    $job = makeQueuedJob($this);
    Post::query()->whereKey($job->post_id)->update(['meta' => json_encode(['fork_shop_product_id' => '1729384756001234567', 'fork_shop_product_name' => 'Nano'])]);

    $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertOk()
        ->assertJsonPath('product.product_id', '1729384756001234567')
        ->assertJsonPath('product.product_name', 'Nano')
        ->assertJsonPath('product.anchor_template', null)
        ->assertJsonPath('product.template_product_id', null);
});

test('a post with an invalid shop product id yields no product', function () {
    $token = cartHello($this);
    $job = makeQueuedJob($this);
    Post::query()->whereKey($job->post_id)->update(['meta' => json_encode(['fork_shop_product_id' => 'abc'])]);

    $this->getJson('/api/ext/next?wait=0', extHeaders($token))->assertOk()->assertJsonPath('product', null);
});

test('hello with an avatar_url downloads it once onto the bound channel', function () {
    Storage::fake('public');
    Http::fake(['https://p16-sign.tiktokcdn.com/*' => Http::response(base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='), 200)]);
    $token = pairExtension($this);

    $body = ['protocol' => 1, 'ext_version' => '1.3.0', 'identity' => ['username' => 'mt.tri.2.pin', 'user_id' => EXT_USER_ID, 'avatar_url' => 'https://p16-sign.tiktokcdn.com/a.png']];
    $this->postJson('/api/ext/hello', $body, extHeaders($token))->assertOk()->assertJsonPath('avatar_ok', true);
    $this->postJson('/api/ext/hello', $body, extHeaders($token))->assertOk();

    expect($this->social->fresh()->getRawOriginal('avatar_url'))->toStartWith('avatars/tiktok-');
    Http::assertSentCount(1);

    // Bản cũ không gửi avatar: hello vẫn chạy bình thường.
    helloAs($this, $token)->assertOk();
});

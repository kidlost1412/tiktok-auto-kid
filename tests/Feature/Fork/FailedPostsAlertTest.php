<?php

declare(strict_types=1);

// "Bài không đăng được": lý do tiếng Việt (FailureReasons), khối ở Tổng quan, nhãn trong Lịch, khung xem video,
// "Đăng lại" an toàn và tin Telegram (mỗi job một tin, gộp khi nhiều).

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Scheduling\FailedPosts;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\FailureReasons;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\ScheduledDispatcher;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Inertia\Testing\AssertableInertia;

const FA_OOS = ['detail' => 'out-of-stock', 'reason' => 'product-unavailable', 'outcome' => 'failed', 'definite' => true, 'not_sent' => true, 'elapsed_ms' => 800, 'schedule_time' => null];
const FA_PRODUCT = 'Đạm cá amino 5L';

beforeEach(function () {
    Cache::flush();
    $this->faDisk = 'fa_test_'.bin2hex(random_bytes(4));
    $this->faRoot = storage_path('framework/testing/disks/'.$this->faDisk);
    config([
        'filesystems.disks.'.$this->faDisk => ['driver' => 'local', 'root' => $this->faRoot, 'throw' => false],
        'filesystems.default' => $this->faDisk,
        'trypost.self_hosted' => true,
        'fork.auto.hub_api.key' => '',
        'fork.telegram.bot_token' => '123:TEST',
        'fork.telegram.chat_id' => '999',
        'fork.telegram.min_interval_ms' => 0,
        'fork.telegram.backoff_ms' => [0, 0],
    ]);
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => true])]);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->social = SocialAccount::factory()->tiktok()->create([
        'workspace_id' => $this->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh1',
    ]);
    ChromeAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'tiktok_user_id' => '7012345678901234567', 'chrome_only' => false]);
    AutoAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'daily_cap' => 8]);
    AutoProduct::query()->create(['code' => 'dam-ca', 'name' => 'Đạm cá', 'short_name' => 'Đạm cá', 'facts' => [], 'enabled' => true]);
});

afterEach(function () {
    File::deleteDirectory($this->faRoot);
});

/** Bài hẹn giờ + video AI đang "scheduled" + job Chrome (mặc định lỗi hết hàng, chắc chắn chưa gửi). */
function faMake(object $t, int $n, array $result = FA_OOS, string $state = 'failed', array $job = [], array $post = [], bool $withJob = true): AutoVideo
{
    $file = "v/fa{$n}.mp4";
    Storage::put($file, 'video-bytes');

    $p = Post::factory()->forAccount($t->social)->create(array_merge([
        'content' => "Chú thích số {$n}",
        'status' => PostStatus::Scheduled,
        'scheduled_at' => now()->addHours(5)->addMinutes($n),
        'media' => [['id' => "m{$n}", 'path' => $file, 'url' => 'http://x/'.$file, 'type' => 'video', 'mime_type' => 'video/mp4', 'original_filename' => 'clip.mp4', 'size' => 11]],
        'meta' => ['privacy_level' => 'PUBLIC_TO_EVERYONE', 'allow_comments' => true, 'fork_shop_product_id' => '1729384756000001', 'fork_shop_product_name' => FA_PRODUCT],
    ], $post));

    if ($withJob) {
        ChromeJob::query()->create(array_merge([
            'id' => 'ej_'.str_pad((string) $n, 24, 'a'), 'post_id' => $p->id, 'social_account_id' => $t->social->id, 'attempt' => 1,
            'expect_user_id' => '7012345678901234567', 'nonce' => 'n'.$n, 'media_path' => $file, 'video_name' => 'clip.mp4', 'video_size' => 11,
            'video_mime' => 'video/mp4', 'mode' => 'scheduled', 'caption' => "Chú thích số {$n}", 'options' => [], 'state' => $state, 'result' => $result,
        ], $job));
    }

    return AutoVideo::query()->create([
        'hash' => hash('sha256', "fa{$n}"), 'path' => "/x/fa{$n}.mp4", 'batch_date' => '2026-01-05', 'file_name' => "fa{$n}.mp4",
        'product_code' => 'dam-ca', 'source' => 'hub', 'status' => AutoVideo::SCHEDULED, 'caption' => "Chú thích số {$n}",
        'social_account_id' => $t->social->id, 'post_id' => $p->id, 'scheduled_for' => $p->scheduled_at,
    ]);
}

function faTexts(): array
{
    // Chỉ tin lỗi đăng bài (các tin khác như "kho sắp hết" không thuộc phạm vi các test này).
    return Http::recorded()->map(fn ($pair) => $pair[0]->data()['text'] ?? '')->filter(fn (string $t): bool => str_contains($t, 'không đăng được'))->values()->all();
}

// ---------------------------------------------------------------- Ánh xạ lý do

test('out-of-stock maps to a plain Vietnamese sentence with the product name and what to do', function () {
    $d = FailureReasons::describe('product-unavailable', 'out-of-stock', null, FA_PRODUCT);

    expect($d['title'])->toBe('Sản phẩm trong giỏ (Đạm cá amino 5L) đã hết hàng trên shop')
        ->and($d['fix'])->toContain('Đăng lại')
        ->and($d['short'])->toBe('Hết hàng')
        ->and($d['text'])->toContain('nhập thêm hàng hoặc đổi giỏ');

    expect(FailureReasons::describe('product-unavailable', 'out-of-stock')['title'])->toBe('Sản phẩm trong giỏ đã hết hàng trên shop');
});

test('every reason code the extension can send has a Vietnamese text, unknown codes keep the raw code', function () {
    $known = ['already-authorized', 'anchor-build-failed', 'authorize-timeout', 'bad-dimensions', 'bad-id', 'bad-mime', 'bad-sha256', 'bad-size', 'bad-url',
        'bad_task', 'blocked-by-hook', 'cancelled', 'error-after-send', 'exception', 'gave-up', 'http-403', 'identity', 'identity-mismatch', 'identity-missing',
        'identity-unknown', 'incomplete', 'job-tab', 'mode-disabled', 'mode-unsupported', 'no-active-job', 'no-cover', 'no-identity', 'no-time', 'not-a-post-job',
        'open-window-failed', 'owner-cleared', 'post-disabled', 'product-check-failed', 'product-id-unclear', 'product-unavailable', 'publish-setup-failed',
        'ready-not-confirmed', 'server-unreachable:x', 'status_code', 'step:identity', 'step:upload', 'sync-timeout', 'tab-closed', 'tab-closed-after-authorization',
        'tab-closed-before-authorization', 'tab-reloaded-after-authorization', 'time-mismatch', 'too-big', 'too-late', 'too-close-or-published', 'unpaired', 'xhr-timeout'];

    foreach ($known as $code) {
        $d = FailureReasons::describe($code);
        expect($d['short'])->not->toBe('Lỗi khác', $code)->and($d['title'])->not->toBe('')->and($d['fix'])->not->toBe('');
    }

    $unknown = FailureReasons::describe('zzz-new-code');
    expect($unknown['title'])->toContain('zzz-new-code')->and($unknown['short'])->toBe('Lỗi khác');
    expect(FailureReasons::describe('whatever', null, 'uncertain')['short'])->toBe('Chưa rõ kết quả');
});

test('the Post error text for a failed Chrome job is no longer a raw code', function () {
    $v = faMake($this, 1);
    $job = ChromeJob::query()->where('post_id', $v->post_id)->first();

    $msg = app(ChromeJobs::class)->outcome($job)->message;

    expect($msg)->toContain('hết hàng')->toContain(FA_PRODUCT)->not->toContain('product-unavailable');
});

// ---------------------------------------------------------------- Tổng quan, Lịch, khung xem

test('overview lists failed posts with the reason, the Lich row is red, early cart warning shows', function () {
    $failed = faMake($this, 1);
    $ok = faMake($this, 2, withJob: false);
    $stock = faMake($this, 3, withJob: false, post: ['meta' => ['privacy_level' => 'PUBLIC_TO_EVERYONE', 'fork_shop_product_id' => '1729384756000009', 'fork_shop_product_name' => 'Giỏ B']]);
    ShopProduct::query()->create(['social_account_id' => $this->social->id, 'product_id' => '1729384756000009', 'source' => 'my_shop', 'title' => 'SP', 'stock_num' => 0, 'synced_at' => now()]);

    $props = (array) $this->actingAs($this->owner)->get('/auto')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/Auto')
        ->has('failed_posts', 1)
        ->where('failed_posts.0.id', $failed->id)
        ->where('failed_posts.0.kind', 'job')
        ->where('failed_posts.0.title', 'Sản phẩm trong giỏ (Đạm cá amino 5L) đã hết hàng trên shop')
        ->where('failed_posts.0.can_retry', true)
        ->where('failed_posts.0.username', 'kenh1'))->viewData('page')['props'];

    $items = collect($props['lich']['channels'][$this->social->id]['items'])->keyBy('id');
    expect($items[$failed->id]['state'])->toBe('failed')
        ->and($items[$failed->id]['error'])->toBe('Lỗi: Hết hàng')
        ->and($items[$ok->id]['state'])->toBe('scheduled')
        ->and($items[$ok->id]['note'])->toBeNull()
        ->and($items[$stock->id]['cart_warn'])->toContain('Giỏ hết hàng');

    $info = $this->actingAs($this->owner)->getJson("/auto/kho/video/{$failed->id}/info")->assertOk()->json('failure');
    expect($info['kind'])->toBe('job')->and($info['can_retry'])->toBeTrue()->and($info['fix'])->toContain('Đăng lại');
    expect($this->actingAs($this->owner)->getJson("/auto/kho/video/{$ok->id}/info")->json('failure'))->toBeNull();
});

test('a quota rejection or an old failure is not shown as a failed post', function () {
    faMake($this, 1, ['status_code' => 3013021, 'reason' => 'status_code', 'not_sent' => false], 'rejected');
    $old = faMake($this, 2);
    ChromeJob::query()->where('post_id', $old->post_id)->update(['updated_at' => now()->subDays(5)]);

    $this->actingAs($this->owner)->get('/auto')->assertInertia(fn (AssertableInertia $p) => $p->has('failed_posts', 0));
});

test('a failed job that was already retried (newer attempt) is resolved', function () {
    $v = faMake($this, 1);
    ChromeJob::query()->create([
        'id' => 'ej_'.str_repeat('z', 24), 'post_id' => $v->post_id, 'social_account_id' => $this->social->id, 'attempt' => 2,
        'expect_user_id' => '7012345678901234567', 'nonce' => 'nz', 'media_path' => 'x', 'video_name' => 'x', 'video_size' => 1,
        'video_mime' => 'video/mp4', 'mode' => 'scheduled', 'caption' => 'c', 'options' => [], 'state' => 'queued',
    ]);

    $this->actingAs($this->owner)->get('/auto')->assertInertia(fn (AssertableInertia $p) => $p->has('failed_posts', 0));
});

// ---------------------------------------------------------------- Đăng lại an toàn

test('retry queues a new Chrome attempt when the failed job surely sent nothing', function () {
    $v = faMake($this, 1);

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/dang-lai")->assertRedirect()->assertSessionHas('flash.success');

    $jobs = ChromeJob::query()->where('post_id', $v->post_id)->orderBy('attempt')->get();
    expect($jobs)->toHaveCount(2)->and($jobs[1]->state)->toBe('queued')->and($jobs[1]->mode)->toBe('scheduled');

    // Bấm lần nữa: đang có lượt mới, không giao thêm.
    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/dang-lai")->assertSessionHas('flash.error');
    expect(ChromeJob::query()->where('post_id', $v->post_id)->count())->toBe(2);
});

test('retry refuses whenever it is not certain nothing was sent', function (string $case) {
    $v = match ($case) {
        'uncertain' => faMake($this, 1, ['outcome' => 'uncertain', 'reason' => 'error-after-send'], 'uncertain'),
        'rejected' => faMake($this, 1, ['status_code' => 7, 'reason' => 'status_code'], 'rejected'),
        'authorized-and-unsure' => faMake($this, 1, ['outcome' => 'failed', 'reason' => 'exception', 'not_sent' => false], 'failed', ['authorized_at' => now()]),
        'has-tiktok-id' => faMake($this, 1, post: ['platform_post_id' => '7300000000000000001']),
        'post-failed' => faMake($this, 1, post: ['status' => PostStatus::Failed]),
        'running' => faMake($this, 1, [], 'uploading'),
        'no-job' => faMake($this, 1, withJob: false),
    };

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/dang-lai")->assertRedirect()->assertSessionHas('flash.error');

    expect(ChromeJob::query()->where('post_id', $v->post_id)->count())->toBe($case === 'no-job' ? 0 : 1);
})->with(['uncertain', 'rejected', 'authorized-and-unsure', 'has-tiktok-id', 'post-failed', 'running', 'no-job']);

test('retry respects the attempt cap', function () {
    $v = faMake($this, 1);

    foreach ([2, 3] as $attempt) {
        ChromeJob::query()->create([
            'id' => 'ej_'.str_repeat((string) $attempt, 24), 'post_id' => $v->post_id, 'social_account_id' => $this->social->id, 'attempt' => $attempt,
            'expect_user_id' => '7012345678901234567', 'nonce' => 'nn'.$attempt, 'media_path' => 'x', 'video_name' => 'x', 'video_size' => 1,
            'video_mime' => 'video/mp4', 'mode' => 'scheduled', 'caption' => 'c', 'options' => [], 'state' => 'failed', 'result' => FA_OOS,
        ]);
    }

    $this->actingAs($this->owner)->post("/auto/videos/{$v->id}/dang-lai")->assertSessionHas('flash.error');
    expect(ChromeJob::query()->where('post_id', $v->post_id)->count())->toBe(3);
});

// ---------------------------------------------------------------- Telegram

test('an out-of-stock failure is sent once, in Vietnamese with product name, time, channel and the fix', function () {
    faMake($this, 1);

    $this->artisan('fork:alerts')->assertSuccessful();
    $this->artisan('fork:alerts')->assertSuccessful();

    $texts = faTexts();
    expect($texts)->toHaveCount(1)
        ->and($texts[0])->toContain('Bài không đăng được')->toContain('@kenh1')->toContain('hết hàng')->toContain(FA_PRODUCT)
        ->toContain('Giờ hẹn')->toContain('Chú thích số 1')->toContain('Cách xử lý')->toContain('Đăng lại')
        ->not->toContain('product-unavailable');
});

test('several failures in one run become ONE message, then are not repeated', function () {
    foreach ([1, 2, 3] as $n) {
        faMake($this, $n);
    }
    faMake($this, 4, ['status_code' => 3013021, 'reason' => 'status_code'], 'rejected');

    $this->artisan('fork:alerts')->assertSuccessful();

    $texts = faTexts();
    expect($texts)->toHaveCount(1)
        ->and($texts[0])->toContain('3 bài không đăng được')->toContain('Hết hàng')->toContain(FA_PRODUCT)->toContain('Chú thích số 2');

    // Thêm một bài lỗi mới: chỉ tin của bài mới được gửi.
    faMake($this, 5);
    $this->artisan('fork:alerts')->assertSuccessful();

    $texts = faTexts();
    expect($texts)->toHaveCount(2)->and($texts[1])->toContain('Chú thích số 5')->not->toContain('Chú thích số 1');
});

test('pressing retry on several posts of a busy channel queues them and the app hands each one to Chrome when the channel is free', function () {
    $a = faMake($this, 1);
    $b = faMake($this, 2);

    $this->actingAs($this->owner)->post("/auto/videos/{$a->id}/dang-lai")->assertSessionHas('flash.success');
    // Kênh đang bận lượt mới của bài a: bài b không báo lỗi, được xếp hàng.
    $this->actingAs($this->owner)->post("/auto/videos/{$b->id}/dang-lai")->assertSessionHas('flash.success', fn (string $m) => str_contains($m, 'xếp hàng'));
    expect(ChromeJob::query()->where('post_id', $b->post_id)->count())->toBe(1)
        ->and(data_get(Post::query()->find($b->post_id)->meta, FailedPosts::RETRY_WANTED))->not->toBeNull();

    // Thẻ của bài b ghi đã xếp hàng, không còn nút Đăng lại.
    $row = app(FailedPosts::class)->forVideo($b);
    expect($row['can_retry'])->toBeFalse()->and($row['retry_note'])->toContain('xếp hàng');

    // Bài a xong: kênh rảnh, app tự giao bài b.
    ChromeJob::query()->where('post_id', $a->post_id)->where('attempt', 2)->update(['state' => 'posted']);
    expect(app(ScheduledDispatcher::class)->dispatchForAccount($this->social))->toBe(1);
    $jobs = ChromeJob::query()->where('post_id', $b->post_id)->orderBy('attempt')->get();
    expect($jobs)->toHaveCount(2)->and($jobs[1]->state)->toBe('queued')
        ->and(data_get(Post::query()->find($b->post_id)->meta, FailedPosts::RETRY_WANTED))->toBeNull();
});

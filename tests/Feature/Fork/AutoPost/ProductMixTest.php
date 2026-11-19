<?php

declare(strict_types=1);

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Scheduling\ProductMix;
use App\Fork\Chrome\Listeners\ChromePostWatcher;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.auto.hub_api.key', '');
    Cache::flush();

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->social = SocialAccount::factory()->tiktok()->create([
        'workspace_id' => $this->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh_mix',
    ]);
    ChromeAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'tiktok_user_id' => '70000000001', 'chrome_only' => false]);
    $this->auto = AutoAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'daily_cap' => 40, 'window_start' => 0, 'window_end' => 24]);

    foreach (['bo' => 'Bọ', 'tc' => 'TC', 'dam' => 'Đạm'] as $code => $name) {
        AutoProduct::query()->create(['code' => $code, 'name' => $name, 'short_name' => $name, 'facts' => [], 'enabled' => true]);
    }
});

/** Bài đã xếp lịch, chưa gửi lên TikTok. */
function mixPost(object $t, string $code, CarbonImmutable $at, array $meta = []): AutoVideo
{
    static $n = 0;
    $n++;
    $post = Post::factory()->forAccount($t->social)->create([
        'content' => 'mix '.$n, 'status' => PostStatus::Scheduled, 'scheduled_at' => $at->utc(),
        'meta' => ['privacy_level' => 'PUBLIC_TO_EVERYONE'],
    ]);

    return AutoVideo::query()->create([
        'hash' => hash('sha256', 'mix'.$n.random_int(0, 99999)), 'path' => "/nonexistent/mix{$n}.mp4", 'batch_date' => '2026-11-18', 'file_name' => "mix{$n}.mp4",
        'product_code' => $code, 'status' => AutoVideo::SCHEDULED, 'source' => 'hub', 'caption' => 'Cap '.$n,
        'social_account_id' => $t->social->id, 'post_id' => $post->id, 'scheduled_for' => $at->utc(), 'meta' => $meta === [] ? null : $meta,
    ]);
}

function mixJob(AutoVideo $v, string $state, string $mode = 'scheduled'): ChromeJob
{
    return ChromeJob::query()->create([
        'id' => 'cj_'.bin2hex(random_bytes(8)), 'post_id' => $v->post_id, 'social_account_id' => $v->social_account_id, 'attempt' => 1,
        'mode' => $mode, 'state' => $state, 'expect_user_id' => '70000000001', 'media_path' => 'v/x.mp4', 'video_name' => 'x.mp4', 'caption' => 'c', 'options' => [], 'nonce' => bin2hex(random_bytes(8)), 'result' => $state === 'posted' ? ['item_id' => '7570000000000000001'] : null,
    ]);
}

/** Mã sản phẩm các bài tương lai của kênh, theo giờ. */
function mixSequence(object $t): array
{
    return AutoVideo::query()->where('social_account_id', $t->social->id)->where('scheduled_for', '>', now())
        ->orderBy('scheduled_for')->pluck('product_code')->all();
}

test('arrange spreads 10 + 10 + 10 so no two neighbours share a product, the same seed gives the same order', function () {
    $timeline = [];

    foreach (['bo', 'tc', 'dam'] as $p) {
        for ($i = 0; $i < 10; $i++) {
            $timeline[] = ['fixed' => false, 'product' => $p, 'key' => count($timeline)];
        }
    }

    $a = ProductMix::arrange($timeline, 42);
    $b = ProductMix::arrange($timeline, 42);
    $products = array_map(fn (int $k): string => $timeline[$k]['product'], array_values($a));

    expect($a)->toBe($b)->and(count($a))->toBe(30)->and(count(array_unique(array_values($a))))->toBe(30);

    for ($i = 1; $i < 30; $i++) {
        expect($products[$i])->not->toBe($products[$i - 1]);
    }
});

test('arrange respects fixed neighbours: right after a fixed bo the first free slot is not bo', function () {
    $order = ProductMix::order([10 => 'bo', 11 => 'bo', 12 => 'tc'], ['bo'], 7);

    expect($order[0])->toBe(12)->and($order)->toBe([12, 10, 11]);
});

test('mixing a channel swaps only the times of posts not yet on TikTok and can be undone exactly', function () {
    $base = CarbonImmutable::now()->addHours(2)->startOfMinute();
    $videos = [];

    foreach (['bo', 'bo', 'bo', 'tc', 'tc', 'tc'] as $i => $code) {
        $videos[] = mixPost($this, $code, $base->addMinutes(30 * $i));
    }

    $times = collect($videos)->map(fn ($v) => $v->scheduled_for->toIso8601String())->sort()->values()->all();
    $plan = app(ProductMix::class)->plan($this->auto);
    expect($plan['movable'])->toBe(6)->and($plan['changed'])->toBeGreaterThan(0);

    $res = app(ProductMix::class)->apply($this->auto);
    $seq = mixSequence($this);

    for ($i = 1; $i < count($seq); $i++) {
        expect($seq[$i])->not->toBe($seq[$i - 1]);
    }

    // Không thêm/bớt giờ nào, Post và video luôn khớp nhau.
    $after = AutoVideo::query()->whereIn('id', collect($videos)->pluck('id'))->get();
    expect($after->map(fn ($v) => $v->scheduled_for->toIso8601String())->sort()->values()->all())->toBe($times);

    foreach ($after as $v) {
        expect(Post::query()->find($v->post_id)->scheduled_at->equalTo($v->scheduled_for))->toBeTrue();
    }

    app(ProductMix::class)->restore($this->auto, $res['undo']);
    expect(mixSequence($this))->toBe(['bo', 'bo', 'bo', 'tc', 'tc', 'tc']);
});

test('posts already on TikTok, pinned by the owner or too close stay put; a queued Chrome job is revoked so it is sent again', function () {
    $base = CarbonImmutable::now()->addHours(2)->startOfMinute();
    $soon = mixPost($this, 'bo', CarbonImmutable::now()->addMinutes(10));
    $onTikTok = mixPost($this, 'bo', $base);
    mixJob($onTikTok, 'posted');
    $pinned = mixPost($this, 'bo', $base->addMinutes(30), [ProductMix::PIN => true]);
    $queued = mixPost($this, 'bo', $base->addMinutes(60));
    $job = mixJob($queued, 'queued');
    $free1 = mixPost($this, 'bo', $base->addMinutes(90));
    $tc = mixPost($this, 'tc', $base->addMinutes(120));

    $plan = app(ProductMix::class)->plan($this->auto);
    expect($plan['movable'])->toBe(3)->and($plan['pinned'])->toBe(1)->and($plan['locked'])->toBeGreaterThanOrEqual(2);

    app(ProductMix::class)->apply($this->auto);

    foreach ([$soon, $onTikTok, $pinned] as $v) {
        expect(AutoVideo::query()->find($v->id)->scheduled_for->equalTo($v->scheduled_for))->toBeTrue();
    }

    // tc lên chỗ sớm nhất còn đổi được (sau bài bọ đã ghim), hai bài bọ lùi lại.
    expect(AutoVideo::query()->find($tc->id)->scheduled_for->equalTo($queued->scheduled_for))->toBeTrue()
        ->and($job->refresh()->state)->toBe('revoked')
        ->and(ChromePostWatcher::isEditNote($job->note))->toBeTrue();

    // Chọn "đổi cả bài anh đã tự chỉnh giờ" thì bài ghim cũng được tính.
    expect(app(ProductMix::class)->plan($this->auto, true)['pinned'])->toBe(0);
});

test('auto mix only runs for channels that turned it on, and owner reschedules pin the post', function () {
    $base = CarbonImmutable::now()->addHours(2)->startOfMinute();

    foreach (['dam', 'dam', 'tc', 'tc'] as $i => $code) {
        mixPost($this, $code, $base->addMinutes(30 * $i));
    }

    expect(app(ProductMix::class)->autoMix($this->auto))->toBe(0)
        ->and(mixSequence($this))->toBe(['dam', 'dam', 'tc', 'tc']);

    $this->auto->update(['mix_products' => true]);
    expect(app(ProductMix::class)->autoMix($this->auto->refresh()))->toBeGreaterThan(0)
        ->and(mixSequence($this))->not->toBe(['dam', 'dam', 'tc', 'tc']);

    // Đã xen kẽ rồi thì các lượt sau để yên, không đảo lịch liên tục.
    $settled = mixSequence($this);
    expect(app(ProductMix::class)->autoMix($this->auto->refresh()))->toBe(0)
        ->and(mixSequence($this))->toBe($settled)
        ->and(app(ProductMix::class)->plan($this->auto)['message'])->toBe('Các bài đã xen kẽ sản phẩm rồi.');
});

test('the mix endpoints are owner only, preview writes nothing, apply returns an undo list', function () {
    $base = CarbonImmutable::now()->addHours(2)->startOfMinute();

    foreach (['bo', 'bo', 'tc', 'tc'] as $i => $code) {
        mixPost($this, $code, $base->addMinutes(30 * $i));
    }

    $this->actingAs($this->owner)->getJson("/auto/accounts/{$this->social->id}/tron-san-pham")
        ->assertOk()->assertJson(['ok' => true, 'movable' => 4])->assertJsonMissing(['changes']);
    expect(mixSequence($this))->toBe(['bo', 'bo', 'tc', 'tc']);

    $res = $this->actingAs($this->owner)->postJson("/auto/accounts/{$this->social->id}/tron-san-pham")->assertOk()->json();
    expect($res['moved'])->toBeGreaterThan(0)->and($res['undo'])->not->toBeEmpty();

    $this->actingAs($this->owner)->postJson("/auto/accounts/{$this->social->id}/tron-san-pham/hoan-tac", ['undo' => $res['undo']])->assertOk();
    expect(mixSequence($this))->toBe(['bo', 'bo', 'tc', 'tc']);

    $stranger = User::factory()->create();
    $this->actingAs($stranger)->getJson("/auto/accounts/{$this->social->id}/tron-san-pham")->assertNotFound();
});

test('turning the channel setting on mixes right away and says how many posts moved', function () {
    $base = CarbonImmutable::now()->addHours(2)->startOfMinute();

    foreach (['bo', 'bo', 'tc', 'tc'] as $i => $code) {
        mixPost($this, $code, $base->addMinutes(30 * $i));
    }

    $this->actingAs($this->owner)->patch("/auto/accounts/{$this->social->id}", ['mix_products' => true])
        ->assertSessionHas('flash.success', fn (string $m): bool => str_contains($m, 'trộn xen kẽ'));

    expect($this->auto->refresh()->mix_products)->toBeTrue()
        ->and(mixSequence($this))->not->toBe(['bo', 'bo', 'tc', 'tc']);
});

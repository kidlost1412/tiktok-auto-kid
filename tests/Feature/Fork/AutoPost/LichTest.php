<?php

declare(strict_types=1);

use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Scheduling\PlanPreview;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Inertia\Testing\AssertableInertia;

/** @return array{owner: User, social: SocialAccount} */
function lichOwner(string $username): array
{
    $account = Account::factory()->create();
    $owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $owner->id]);
    $workspace = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $owner->id]);
    $owner->update(['current_workspace_id' => $workspace->id]);
    $social = SocialAccount::factory()->tiktok()->create([
        'workspace_id' => $workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => $username,
    ]);
    ChromeAccount::query()->create(['social_account_id' => $social->id, 'enabled' => true, 'tiktok_user_id' => 'u'.$username]);
    AutoAccount::query()->create(['social_account_id' => $social->id, 'enabled' => true, 'daily_cap' => 40, 'window_start' => 0, 'window_end' => 24]);

    return ['owner' => $owner, 'social' => $social];
}

function lichCart(SocialAccount $social, string $code = 'nano-dong'): void
{
    $id = '17293847560000'.str_pad((string) random_int(10000, 99999), 5, '0');
    ShopProduct::query()->create(['social_account_id' => $social->id, 'product_id' => $id, 'source' => 'my_shop', 'title' => 'SP', 'stock_num' => 5, 'synced_at' => now()]);
    ProductLink::query()->create(['social_account_id' => $social->id, 'auto_product_id' => $code, 'shop_product_id' => $id, 'display_name' => 'MUA 5 TẶNG 3']);
}

function lichVideo(string $code = 'nano-dong', array $o = []): AutoVideo
{
    static $n = 0;
    $n++;

    return AutoVideo::query()->create(array_merge([
        'hash' => hash('sha256', 'lich'.$n), 'path' => "/nonexistent/lich{$n}.mp4", 'batch_date' => '2026-01-05',
        'file_name' => "lich{$n}.mp4", 'product_code' => $code, 'status' => 'new', 'source' => 'hub',
        'caption' => "Caption {$n}", 'goc' => "g{$n}",
    ], $o));
}

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.auto.hub_api.key', '');
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
    AutoProduct::query()->create(['code' => 'bo-tri', 'name' => 'Bổ trì', 'short_name' => 'Bổ trì', 'facts' => [], 'enabled' => true]);
    $this->a = lichOwner('kenh_a');
});

test('preview pairs free slots with the videos that would be picked and changes nothing', function (): void {
    lichCart($this->a['social']);
    $videos = collect(range(1, 5))->map(fn () => lichVideo());
    $statusBefore = AutoVideo::query()->orderBy('id')->pluck('status', 'id')->all();

    $auto = AutoAccount::query()->find($this->a['social']->id);
    $result = app(PlanPreview::class)->forAccounts([$auto], CarbonImmutable::now())[$auto->social_account_id];

    $withVideo = collect($result['slots'])->filter(fn ($s) => $s['video'] !== null);
    $empty = collect($result['slots'])->filter(fn ($s) => $s['video'] === null);

    expect($result['slots'])->not->toBeEmpty()
        ->and($withVideo)->toHaveCount(5)
        ->and($withVideo->pluck('video.id')->unique())->toHaveCount(5)
        ->and($withVideo->first()['video']['cart_name'])->toBe('MUA 5 TẶNG 3')
        ->and($empty)->not->toBeEmpty()
        ->and($empty->first()['reason'])->toBe('hết video có giỏ');

    // Chạy thử không được ghi gì.
    expect(AutoVideo::query()->orderBy('id')->pluck('status', 'id')->all())->toBe($statusBefore)
        ->and(AutoVideo::query()->whereNotNull('social_account_id')->count())->toBe(0)
        ->and(Post::query()->count())->toBe(0)
        ->and($videos)->toHaveCount(5);
});

test('preview explains slots left empty when no cart is chosen and lists blocked videos', function (): void {
    foreach (range(1, 4) as $i) {
        lichVideo('bo-tri');
    }

    $auto = AutoAccount::query()->find($this->a['social']->id);
    $result = app(PlanPreview::class)->forAccount($auto, CarbonImmutable::now());

    expect($result['allowed_count'])->toBe(0)
        ->and($result['slots'])->not->toBeEmpty()
        ->and(collect($result['slots'])->every(fn ($s) => $s['video'] === null && $s['reason'] === 'chưa chọn giỏ hàng'))->toBeTrue()
        ->and($result['blocked'][0]['count'])->toBe(4)
        ->and($result['blocked'][0]['code'])->toBe('bo-tri')
        ->and($result['note'])->not->toBeNull()
        ->and(AutoVideo::query()->where('status', 'new')->count())->toBe(4);
});

test('preview of a disabled channel is empty', function (): void {
    lichCart($this->a['social']);
    lichVideo();
    AutoAccount::query()->find($this->a['social']->id)->update(['enabled' => false]);

    $auto = AutoAccount::query()->find($this->a['social']->id);
    $result = app(PlanPreview::class)->forAccount($auto, CarbonImmutable::now());

    expect($result['slots'])->toBe([])->and($result['note'])->toContain('tắt');
});

test('auto page exposes health, the 3-day schedule and the plan-ahead hint', function (): void {
    lichCart($this->a['social']);
    lichVideo();

    $this->actingAs($this->a['owner'])->get('/auto')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/Auto')
        ->has('lich.days', 3)
        ->where('lich.days.0.label', 'Hôm nay')
        ->has("lich.channels.{$this->a['social']->id}.items")
        ->where("lich.channels.{$this->a['social']->id}.today.cap", 40)
        ->where('health.channels.0.chrome_enabled', true)
        ->where('health.channels.0.chrome_online', false)
        ->where('health.telegram', false)
        ->where('plan_ahead_hours', 6));
});

test('today counts include posts made with mode now (no scheduled_for)', function (): void {
    $this->travelTo(CarbonImmutable::now('Asia/Ho_Chi_Minh')->setTime(12, 0)->utc());
    $id = $this->a['social']->id;

    // Đăng "ngay": không có scheduled_for, chỉ có posted_at.
    lichVideo('nano-dong', ['status' => AutoVideo::POSTED, 'social_account_id' => $id, 'posted_at' => now()->subHour()]);
    // Vừa giữ chỗ cho bài đăng ngay: chưa có scheduled_for lẫn posted_at (mốc là updated_at, như trần bài/ngày).
    lichVideo('nano-dong', ['status' => AutoVideo::RESERVED, 'social_account_id' => $id]);
    // Hẹn giờ hôm nay.
    lichVideo('nano-dong', ['status' => AutoVideo::SCHEDULED, 'social_account_id' => $id, 'scheduled_for' => now()->addHours(2)]);
    // Hẹn ngày mai: không tính vào hôm nay.
    lichVideo('nano-dong', ['status' => AutoVideo::SCHEDULED, 'social_account_id' => $id, 'scheduled_for' => now()->addDay()]);

    $this->actingAs($this->a['owner'])->get('/auto')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->where("lich.channels.{$id}.today.planned", 3)
        ->where("lich.channels.{$id}.today.posted", 1));
});

test('plan-now only plans the channels of the signed-in owner', function (): void {
    $b = lichOwner('kenh_b');
    lichCart($this->a['social']);
    lichCart($b['social'], 'bo-tri');
    // File không tồn tại: nếu Planner đụng tới kênh nào thì video của kênh đó chuyển sang "failed".
    $va = lichVideo(o: ['batch_date' => '2026-01-01']);
    $vb = lichVideo('bo-tri', ['batch_date' => '2026-01-01']);

    $this->actingAs($this->a['owner'])->post('/auto/plan-now')->assertRedirect()->assertSessionHas('flash.error');

    expect(AutoVideo::query()->find($va->id)->status)->not->toBe('new')
        ->and(AutoVideo::query()->find($va->id)->social_account_id)->toBe($this->a['social']->id)
        ->and(AutoVideo::query()->find($vb->id)->status)->toBe('new')
        ->and(AutoVideo::query()->find($vb->id)->social_account_id)->toBeNull();
});

test('plan-now rejects non owners and guests', function (): void {
    $member = User::factory()->create(['account_id' => $this->a['owner']->account_id]);

    $this->actingAs($member)->post('/auto/plan-now')->assertForbidden();
    auth()->logout();
    $this->post('/auto/plan-now')->assertRedirect();
});

test('plan-now reports when no channel has auto enabled', function (): void {
    AutoAccount::query()->update(['enabled' => false]);

    $this->actingAs($this->a['owner'])->post('/auto/plan-now')->assertSessionHas('flash.error');
});

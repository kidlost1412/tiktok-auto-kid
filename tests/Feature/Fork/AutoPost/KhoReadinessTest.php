<?php

declare(strict_types=1);

use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Scheduling\Readiness;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\File;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    $this->hub = str_replace('\\', '/', sys_get_temp_dir()).'/hub-rdy-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/ra/2026-11-10');
    config(['fork.auto.hub_path' => $this->hub, 'trypost.self_hosted' => true, 'fork.auto.hub_api.key' => null]);

    $this->product = AutoProduct::create(['code' => 'bo-tri-top-one', 'name' => 'Bộ trị Top One', 'short_name' => 'Bộ trị Top One', 'facts' => [], 'enabled' => true]);

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);

    $this->channel = function (bool $enabled = true, bool $chrome = true): SocialAccount {
        $sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh']);
        AutoAccount::create(['social_account_id' => $sa->id, 'enabled' => $enabled, 'daily_cap' => 8, 'window_start' => 0, 'window_end' => 24]);
        $chrome && ChromeAccount::create(['social_account_id' => $sa->id, 'enabled' => true, 'tiktok_user_id' => '777']);

        return $sa;
    };

    $this->cart = function (SocialAccount $sa): void {
        ShopProduct::create(['social_account_id' => $sa->id, 'product_id' => '1729384756001234567', 'source' => 'my_shop', 'title' => 'Top One', 'stock_num' => 5, 'synced_at' => now()]);
        ProductLink::create(['social_account_id' => $sa->id, 'auto_product_id' => 'bo-tri-top-one', 'shop_product_id' => '1729384756001234567', 'display_name' => 'Top One']);
    };

    $this->video = function (array $attrs = []): AutoVideo {
        static $n = 0;
        $n++;

        return AutoVideo::create($attrs + [
            'hash' => hash('sha256', "rdy{$n}"), 'path' => $this->hub."/rdy{$n}.mp4", 'batch_date' => '2026-11-10', 'file_name' => "rdy{$n}.mp4",
            'product_code' => 'bo-tri-top-one', 'quy_cach' => null, 'source' => 'hub', 'status' => 'new', 'caption' => 'Caption', 'hashtags' => ['#a'],
        ]);
    };
});

afterEach(function (): void {
    File::deleteDirectory($this->hub);
});

function rdy(AutoVideo $v): array
{
    return app(Readiness::class)->assess(collect([$v]))[$v->id];
}

it('báo chưa chọn giỏ cho sản phẩm trên kênh nào', function (): void {
    ($this->channel)();
    $v = ($this->video)();

    $r = rdy($v);

    expect($r['code'])->toBe(Readiness::NO_CART)
        ->and($r['severity'])->toBe('error')
        ->and($r['reason'])->toContain('Chưa chọn giỏ cho Bộ trị Top One')->toContain('Giỏ hàng');
});

it('sẵn sàng thì cho biết lượt kế tiếp', function (): void {
    $sa = ($this->channel)();
    ($this->cart)($sa);

    $r = rdy(($this->video)());

    expect($r['code'])->toBe(Readiness::READY)
        ->and($r['reason'])->toContain('Sẵn sàng — chờ tới lượt')->toContain('~')
        ->and($r['next_slot'])->not->toBeNull();
});

it('báo kênh tắt tự động đăng', function (): void {
    $sa = ($this->channel)(enabled: false);
    ($this->cart)($sa);

    expect(rdy(($this->video)())['code'])->toBe(Readiness::CHANNEL_OFF);
});

it('báo chưa bật Chrome cho kênh', function (): void {
    $sa = ($this->channel)(chrome: false);
    ($this->cart)($sa);

    $r = rdy(($this->video)());

    expect($r['code'])->toBe(Readiness::CHANNEL_OFF)->and($r['reason'])->toContain('Chrome');
});

it('báo thiếu caption, thiếu file, bản ghi cũ', function (): void {
    $sa = ($this->channel)();
    ($this->cart)($sa);

    expect(rdy(($this->video)(['caption' => null]))['code'])->toBe(Readiness::NO_CAPTION)
        ->and(rdy(($this->video)(['files_deleted_at' => now()]))['code'])->toBe(Readiness::NO_FILE)
        ->and(rdy(($this->video)(['source' => 'ra']))['code'])->toBe(Readiness::LEGACY);
});

it('báo giỏ đã chọn nhưng hết hàng', function (): void {
    $sa = ($this->channel)();
    ($this->cart)($sa);
    ShopProduct::query()->update(['stock_num' => 0]);

    $r = rdy(($this->video)());

    expect($r['code'])->toBe(Readiness::CART_BROKEN)->and($r['reason'])->toContain('hết hàng');
});

it('trang Kho hiện banner chặn, ẩn bản ghi cũ mặc định và có tab đếm', function (): void {
    ($this->channel)();
    ($this->video)();
    ($this->video)();
    ($this->video)(['source' => 'ra', 'status' => 'skipped', 'skip_reason' => 'chế độ API hub: bản ghi cũ']);

    $this->actingAs($this->owner)->get('/auto/kho')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/Kho')
        ->where('filters.tab', 'cho')
        ->where('counts.cho', 2)->where('counts.all', 2)->where('legacy_count', 1)
        ->where('blockers.0.count', 2)->where('blockers.0.code', Readiness::NO_CART)
        ->where('blockers.0.message', fn (string $m) => str_contains($m, '2 video Bộ trị Top One') && str_contains($m, 'chưa chọn giỏ hàng'))
        ->where('blockers.0.href', route('fork.auto.gio-hang'))
        ->has('videos.data', 2)
        ->where('videos.data.0.readiness.code', Readiness::NO_CART));

    $this->actingAs($this->owner)->get('/auto/kho?tab=all&legacy=1')->assertInertia(fn (AssertableInertia $p) => $p->where('counts.all', 3));
});

it('route ảnh bìa chỉ phục vụ ảnh dưới thư mục hub, chỉ cho chủ tài khoản', function (): void {
    file_put_contents($this->hub.'/ra/2026-11-10/X.jpg', 'jpgdata');
    file_put_contents($this->hub.'/ra/2026-11-10/X.jpg.txt', 'x');
    $outside = sys_get_temp_dir().'/ngoai-bia-'.bin2hex(random_bytes(3)).'.jpg';
    file_put_contents($outside, 'secret');

    $ok = ($this->video)(['meta' => ['anh_bia' => 'ra/2026-11-10/X.jpg']]);
    $trav = ($this->video)(['meta' => ['anh_bia' => '../'.basename($outside)]]);
    $badExt = ($this->video)(['meta' => ['anh_bia' => 'ra/2026-11-10/X.jpg.txt']]);
    $none = ($this->video)();

    expect(route('fork.auto.kho.cover', $ok->id, false))->toBe("/auto/kho/video/{$ok->id}/cover");

    $this->actingAs($this->owner)->get("/auto/kho/video/{$ok->id}/cover")->assertOk()->assertHeader('content-type', 'image/jpeg');
    $this->actingAs($this->owner)->get("/auto/kho/video/{$trav->id}/cover")->assertNotFound();
    $this->actingAs($this->owner)->get("/auto/kho/video/{$badExt->id}/cover")->assertNotFound();
    $this->actingAs($this->owner)->get("/auto/kho/video/{$none->id}/cover")->assertNotFound();
    $this->actingAs($this->owner)->get('/auto/kho/video/999999/cover')->assertNotFound();
    $this->actingAs(User::factory()->create(['account_id' => $this->owner->account_id]))->get("/auto/kho/video/{$ok->id}/cover")->assertForbidden();

    @unlink($outside);
});

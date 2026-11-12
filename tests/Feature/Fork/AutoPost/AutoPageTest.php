<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh']);

    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
});

function pageVideo(string $status, array $o = []): AutoVideo
{
    static $n = 0;
    $n++;

    return AutoVideo::query()->create(array_merge([
        'hash' => hash('sha256', 'p'.$n),
        'path' => "/x/{$n}.mp4",
        'batch_date' => '2026-01-05',
        'file_name' => "f{$n}.mp4",
        'product_code' => 'nano-dong',
        'status' => $status,
    ], $o));
}

test('owner sees the auto page with stock counts and low stock warning', function (): void {
    AutoAccount::query()->create(['social_account_id' => $this->sa->id, 'enabled' => true, 'daily_cap' => 20]);
    pageVideo('new');
    pageVideo('new');
    pageVideo('scheduled', ['social_account_id' => $this->sa->id, 'scheduled_for' => now()->addHour()]);
    pageVideo('posted', ['social_account_id' => $this->sa->id, 'posted_at' => now()->subHour(), 'stats' => ['latest' => ['views' => 77], 'link' => 'https://www.tiktok.com/@a/video/1']]);

    $this->actingAs($this->owner)->get('/auto')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/Auto')
        ->where('products.0.counts.new', 2)
        ->where('products.0.counts.scheduled', 1)
        ->where('products.0.counts.posted', 1)
        ->where('stock.low', true)
        ->has('upcoming', 1)
        ->where('recent.0.views', 77)
        ->where('recent.0.link', 'https://www.tiktok.com/@a/video/1')
        ->has('accounts', 1)
        ->where('accounts.0.recommendation.hours', null));
});

test('non owners and guests are rejected', function (): void {
    $member = User::factory()->create(['account_id' => $this->account->id]);

    $this->actingAs($member)->get('/auto')->assertForbidden();
});

test('guests are redirected', function (): void {
    $this->get('/auto')->assertRedirect();
});

test('owner can enable, configure and pause an account', function (): void {
    $this->actingAs($this->owner)->patch("/auto/accounts/{$this->sa->id}", ['enabled' => true, 'daily_cap' => 12, 'window_start' => 7, 'window_end' => 22, 'mode' => 'explore'])->assertRedirect();

    $a = AutoAccount::query()->find($this->sa->id);
    expect($a->enabled)->toBeTrue()->and($a->daily_cap)->toBe(12)->and($a->window_start)->toBe(7);

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/pause")->assertRedirect();
    $a->refresh();
    expect($a->enabled)->toBeFalse()->and($a->paused_reason)->not->toBeNull();
});

test('invalid window is rejected and other accounts cannot be touched', function (): void {
    $this->actingAs($this->owner)->patch("/auto/accounts/{$this->sa->id}", ['window_start' => 20, 'window_end' => 10])
        ->assertSessionHas('flash.error');
    expect(AutoAccount::query()->find($this->sa->id)?->window_start)->not->toBe(20);

    $foreign = SocialAccount::factory()->tiktok()->create();
    $this->actingAs($this->owner)->patch("/auto/accounts/{$foreign->id}", ['enabled' => true])->assertNotFound();
});

test('apply recommended hours switches to optimized', function (): void {
    $auto = AutoAccount::query()->create(['social_account_id' => $this->sa->id, 'daily_cap' => 6]);
    $base = CarbonImmutable::parse('2026-01-01 00:00:00', 'Asia/Ho_Chi_Minh');

    foreach (range(0, 7) as $d) {
        foreach ([8 => 100, 10 => 100, 12 => 100, 15 => 100, 19 => 900, 20 => 700] as $h => $views) {
            pageVideo('posted', ['social_account_id' => $this->sa->id, 'posted_at' => $base->addDays($d)->setTime($h, 0)->utc(), 'stats' => ['h24' => ['views' => $views]]]);
        }
    }

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/apply-hours")->assertSessionHas('flash.success');

    $auto->refresh();
    expect($auto->mode)->toBe('optimized')->and($auto->preferred_hours)->toContain(19, 20);
});

test('apply hours without enough data reports an error and changes nothing', function (): void {
    $auto = AutoAccount::query()->create(['social_account_id' => $this->sa->id]);

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/apply-hours")->assertSessionHas('flash.error');

    expect($auto->fresh()->mode)->not->toBe('optimized');
});

function shopProduct(object $t, string $id = '1729384756001234567', array $o = []): ShopProduct
{
    return ShopProduct::query()->create(array_merge([
        'social_account_id' => $t->sa->id, 'product_id' => $id, 'source' => 'my_shop', 'title' => '[LIVESTREAM] Nano Đồng 500ml',
        'price' => '99.000đ', 'cover_url' => 'https://img.example/a.jpg', 'stock_num' => 7, 'synced_at' => now(),
    ], $o));
}

test('owner can save, re-save and clear a cart link', function (): void {
    shopProduct($this);
    $url = "/auto/accounts/{$this->sa->id}/links/nano-dong";

    $this->actingAs($this->owner)->put($url, ['shop_product_id' => '1729384756001234567', 'display_name' => 'Nano Đồng 500ml'])
        ->assertSessionHas('flash.success');

    $link = ProductLink::query()->where('social_account_id', $this->sa->id)->firstOrFail();
    expect($link->shop_product_id)->toBe('1729384756001234567')->and($link->display_name)->toBe('Nano Đồng 500ml');

    // Lưu lại thì mã hết bị tạm dừng.
    $link->update(['paused_reason' => 'Sản phẩm không còn']);
    $this->actingAs($this->owner)->put($url, ['shop_product_id' => '1729384756001234567', 'display_name' => 'Nano Đồng'])->assertSessionHas('flash.success');
    expect($link->fresh()->paused_reason)->toBeNull()->and($link->fresh()->display_name)->toBe('Nano Đồng');

    $this->actingAs($this->owner)->delete($url)->assertRedirect();
    expect(ProductLink::query()->count())->toBe(0);
});

test('link validation: id format, name length, ownership, missing and hidden products', function (): void {
    shopProduct($this);
    shopProduct($this, '1729384756001234999', ['missing' => true]);
    shopProduct($this, '1729384756001234888', ['hidden' => true]);
    $other = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id]);
    ShopProduct::query()->create(['social_account_id' => $other->id, 'product_id' => '1729384756009999999', 'title' => 'khác', 'stock_num' => 1]);
    $url = "/auto/accounts/{$this->sa->id}/links/nano-dong";
    $put = fn (array $d) => $this->actingAs($this->owner)->put($url, $d);

    $put(['shop_product_id' => 'abc', 'display_name' => 'x'])->assertSessionHasErrors('shop_product_id');
    $put(['shop_product_id' => '1729384756001234567', 'display_name' => str_repeat('a', 31)])->assertSessionHasErrors('display_name');
    $put(['shop_product_id' => '1729384756001234567', 'display_name' => ''])->assertSessionHasErrors('display_name');
    $put(['shop_product_id' => '1729384756009999999', 'display_name' => 'x'])->assertSessionHas('flash.error');
    $put(['shop_product_id' => '1729384756001234999', 'display_name' => 'x'])->assertSessionHas('flash.error');
    $put(['shop_product_id' => '1729384756001234888', 'display_name' => 'x'])->assertSessionHas('flash.error');
    $put(['shop_product_id' => '1729384756000000000', 'display_name' => 'x'])->assertSessionHas('flash.error');

    expect(ProductLink::query()->count())->toBe(0);
    $this->actingAs($this->owner)->put("/auto/accounts/{$this->sa->id}/links/khong-co", ['shop_product_id' => '1729384756001234567', 'display_name' => 'x'])->assertNotFound();
});

test('owner can hide and unhide a shop product and request a sync', function (): void {
    shopProduct($this);
    ChromeAccount::query()->create(['social_account_id' => $this->sa->id, 'enabled' => true, 'tiktok_user_id' => '777']);

    $this->actingAs($this->owner)->patch("/auto/accounts/{$this->sa->id}/shop-products/1729384756001234567", ['hidden' => true])->assertRedirect();
    expect(ShopProduct::query()->first()->hidden)->toBeTrue();
    $this->actingAs($this->owner)->patch("/auto/accounts/{$this->sa->id}/shop-products/1729384756001234567", ['hidden' => false])->assertRedirect();
    expect(ShopProduct::query()->first()->hidden)->toBeFalse();
    $this->actingAs($this->owner)->patch("/auto/accounts/{$this->sa->id}/shop-products/1729384756000000042", ['hidden' => true])->assertNotFound();

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/shop/sync")->assertSessionHas('flash.success');
    expect(AutoAccount::query()->find($this->sa->id)->products_sync_request)->not->toBeNull();
});

test('sync request is refused for a channel without Chrome', function (): void {
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/shop/sync")->assertSessionHas('flash.error');
    expect(AutoAccount::query()->find($this->sa->id))->toBeNull();
});

test('the page exposes a one-line cart status per account', function (): void {
    shopProduct($this, '1729384756001234567');
    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => '1729384756001234567', 'display_name' => 'Nano']);
    AutoAccount::query()->create(['social_account_id' => $this->sa->id, 'products_sync_request' => 'r1', 'products_sync_requested_at' => now()]);

    $this->actingAs($this->owner)->get('/auto')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('accounts.0.cart.sync_state', 'waiting')
        ->where('accounts.0.cart.products_count', 1)
        ->where('accounts.0.cart.linked_count', 1)
        ->missing('accounts.0.cart.products')
        ->missing('accounts.0.cart.links'));
});

test('daily cap defaults to 8', function (): void {
    $auto = AutoAccount::query()->create(['social_account_id' => $this->sa->id]);

    expect($auto->fresh()->daily_cap)->toBe(8);
    $this->actingAs($this->owner)->get('/auto')->assertInertia(fn (AssertableInertia $p) => $p->where('accounts.0.daily_cap', 8));
});

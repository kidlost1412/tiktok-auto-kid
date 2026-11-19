<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;

const GB_1L = '1729384756000000001';
const GB_5L = '1729384756000000005';
const GB_NANO = '1729384756000000009';

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->a = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'username' => 'kenh_a']);
    $this->b = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'username' => 'kenh_b']);
    ChromeAccount::query()->create(['social_account_id' => $this->a->id, 'enabled' => true, 'tiktok_user_id' => '777']);
    ChromeAccount::query()->create(['social_account_id' => $this->b->id, 'enabled' => true, 'tiktok_user_id' => '888']);

    AutoProduct::query()->create([
        'code' => 'dam-ca', 'name' => 'Đạm cá', 'short_name' => 'Đạm cá', 'facts' => [], 'enabled' => true,
        'quy_cach' => [['ma' => '1l', 'ten' => 'Chai 1L'], ['ma' => '5l', 'ten' => 'Can 5L']],
    ]);
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);

    $this->shop = fn (SocialAccount $sa, string $id, array $o = []): ShopProduct => ShopProduct::query()->create(array_merge([
        'social_account_id' => $sa->id, 'product_id' => $id, 'source' => 'my_shop', 'title' => 'Sản phẩm '.$id,
        'price' => '99.000đ', 'cover_url' => 'https://img.example/a.jpg', 'stock_num' => 7, 'synced_at' => now(),
    ], $o));

    $this->link = fn (SocialAccount $sa, string $code, ?string $qc, string $id, string $name): ProductLink => ProductLink::query()->create([
        'social_account_id' => $sa->id, 'auto_product_id' => $code, 'quy_cach' => $qc, 'shop_product_id' => $id, 'display_name' => $name,
    ]);
});

// ---- Lưu tất cả ----

test('save-all saves several rows in one go', function (): void {
    ($this->shop)($this->a, GB_1L);
    ($this->shop)($this->a, GB_NANO);

    $this->actingAs($this->owner)->put("/auto/accounts/{$this->a->id}/links", ['items' => [
        ['code' => 'dam-ca', 'quy_cach' => '1l', 'shop_product_id' => GB_1L, 'display_name' => 'ĐẠM CÁ 1L'],
        ['code' => 'nano-dong', 'quy_cach' => null, 'shop_product_id' => GB_NANO, 'display_name' => 'NANO ĐỒNG'],
    ]])->assertRedirect()->assertSessionHas('flash.success', fn (string $m): bool => str_contains($m, 'Đã lưu 2 giỏ hàng'));

    expect(ProductLink::query()->count())->toBe(2)
        ->and(ProductLink::slot($this->a->id, 'dam-ca', '1l')->value('display_name'))->toBe('ĐẠM CÁ 1L')
        ->and(ProductLink::slot($this->a->id, 'nano-dong', null)->value('shop_product_id'))->toBe(GB_NANO);
});

test('save-all is all-or-nothing: one bad row saves nothing', function (): void {
    ($this->shop)($this->a, GB_1L);

    $this->actingAs($this->owner)->put("/auto/accounts/{$this->a->id}/links", ['items' => [
        ['code' => 'dam-ca', 'quy_cach' => '1l', 'shop_product_id' => GB_1L, 'display_name' => 'ĐẠM CÁ 1L'],
        ['code' => 'dam-ca', 'quy_cach' => '5l', 'shop_product_id' => GB_5L, 'display_name' => 'ĐẠM CÁ 5L'], // không có trong shop của kênh
    ]])->assertRedirect()->assertSessionHas('flash.error');

    expect(ProductLink::query()->count())->toBe(0);
});

test('save-all refuses a shop product of another channel, an unknown quy cach and an empty list', function (): void {
    ($this->shop)($this->b, GB_1L);
    $put = fn (array $items) => $this->actingAs($this->owner)->put("/auto/accounts/{$this->a->id}/links", ['items' => $items]);

    $put([['code' => 'dam-ca', 'quy_cach' => '1l', 'shop_product_id' => GB_1L, 'display_name' => 'x']])->assertSessionHas('flash.error');
    $put([['code' => 'dam-ca', 'quy_cach' => '20l', 'shop_product_id' => GB_1L, 'display_name' => 'x']])->assertSessionHas('flash.error');
    $put([])->assertSessionHasErrors('items');

    expect(ProductLink::query()->count())->toBe(0);
});

test('save-all is owner-only and cannot touch a channel of another account', function (): void {
    ($this->shop)($this->a, GB_1L);
    $item = [['code' => 'dam-ca', 'quy_cach' => '1l', 'shop_product_id' => GB_1L, 'display_name' => 'x']];

    $member = User::factory()->create(['account_id' => $this->account->id]);
    $this->actingAs($member)->put("/auto/accounts/{$this->a->id}/links", ['items' => $item])->assertForbidden();

    $otherAccount = Account::factory()->create();
    $other = User::factory()->create(['account_id' => $otherAccount->id]);
    $otherAccount->update(['owner_id' => $other->id]);
    $this->actingAs($other)->put("/auto/accounts/{$this->a->id}/links", ['items' => $item])->assertNotFound();

    expect(ProductLink::query()->count())->toBe(0);
});

// ---- Sao chép giỏ sang kênh khác ----

test('copy fills the other channel for rows whose shop product exists there and skips the rest', function (): void {
    ($this->shop)($this->a, GB_1L);
    ($this->shop)($this->a, GB_5L);
    ($this->shop)($this->a, GB_NANO);
    ($this->link)($this->a, 'dam-ca', '1l', GB_1L, 'ĐẠM CÁ 1L');
    ($this->link)($this->a, 'dam-ca', '5l', GB_5L, 'ĐẠM CÁ 5L');
    ($this->link)($this->a, 'nano-dong', null, GB_NANO, 'NANO ĐỒNG');
    // Kênh B chỉ có 2 trong 3 sản phẩm shop.
    ($this->shop)($this->b, GB_1L);
    ($this->shop)($this->b, GB_NANO);

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->a->id}/links/copy", ['to' => [$this->b->id], 'overwrite' => false])
        ->assertRedirect()
        ->assertSessionHas('flash.success', fn (string $m): bool => str_contains($m, 'Đã sao chép 2 dòng sang @kenh_b') && str_contains($m, 'bỏ qua 1 dòng'));

    expect(ProductLink::query()->where('social_account_id', $this->b->id)->count())->toBe(2)
        ->and(ProductLink::slot($this->b->id, 'dam-ca', '1l')->value('display_name'))->toBe('ĐẠM CÁ 1L')
        ->and(ProductLink::slot($this->b->id, 'dam-ca', '5l')->exists())->toBeFalse()
        ->and(ProductLink::slot($this->b->id, 'nano-dong', null)->value('shop_product_id'))->toBe(GB_NANO)
        ->and(ProductLink::query()->where('social_account_id', $this->a->id)->count())->toBe(3); // nguồn không đổi
});

test('copy keeps rows the target already has unless overwrite is on', function (): void {
    ($this->shop)($this->a, GB_1L);
    ($this->shop)($this->b, GB_1L);
    ($this->shop)($this->b, GB_5L);
    ($this->link)($this->a, 'dam-ca', '1l', GB_1L, 'TÊN KÊNH A');
    ($this->link)($this->b, 'dam-ca', '1l', GB_5L, 'TÊN KÊNH B');
    $post = fn (bool $overwrite) => $this->actingAs($this->owner)->post("/auto/accounts/{$this->a->id}/links/copy", ['to' => [$this->b->id], 'overwrite' => $overwrite]);

    $post(false)->assertRedirect()->assertSessionHas('flash.warning'); // không chép được dòng nào
    expect(ProductLink::slot($this->b->id, 'dam-ca', '1l')->value('display_name'))->toBe('TÊN KÊNH B');

    $post(true)->assertRedirect()->assertSessionHas('flash.success');
    expect(ProductLink::slot($this->b->id, 'dam-ca', '1l')->first())
        ->display_name->toBe('TÊN KÊNH A')
        ->shop_product_id->toBe(GB_1L)
        ->and(ProductLink::query()->where('social_account_id', $this->b->id)->count())->toBe(1);
});

test('copy never uses a hidden or missing shop product on the target', function (): void {
    ($this->shop)($this->a, GB_1L);
    ($this->shop)($this->a, GB_NANO);
    ($this->link)($this->a, 'dam-ca', '1l', GB_1L, 'ĐẠM CÁ 1L');
    ($this->link)($this->a, 'nano-dong', null, GB_NANO, 'NANO ĐỒNG');
    ($this->shop)($this->b, GB_1L, ['hidden' => true]);
    ($this->shop)($this->b, GB_NANO, ['missing' => true]);

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->a->id}/links/copy", ['to' => [$this->b->id]])
        ->assertRedirect()->assertSessionHas('flash.warning');

    expect(ProductLink::query()->where('social_account_id', $this->b->id)->count())->toBe(0);
});

test('copy checks ownership of both channels and refuses copying onto itself', function (): void {
    ($this->shop)($this->a, GB_1L);
    ($this->link)($this->a, 'dam-ca', '1l', GB_1L, 'ĐẠM CÁ 1L');

    $otherAccount = Account::factory()->create();
    $other = User::factory()->create(['account_id' => $otherAccount->id]);
    $otherAccount->update(['owner_id' => $other->id]);
    $otherWs = Workspace::factory()->create(['account_id' => $otherAccount->id, 'user_id' => $other->id]);
    $foreign = SocialAccount::factory()->tiktok()->create(['workspace_id' => $otherWs->id, 'username' => 'kenh_la']);
    ($this->shop)($foreign, GB_1L);

    // Đích là kênh của người khác: 404, không chép gì.
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->a->id}/links/copy", ['to' => [$this->b->id, $foreign->id]])->assertNotFound();
    // Nguồn là kênh của người khác: 404.
    $this->actingAs($this->owner)->post("/auto/accounts/{$foreign->id}/links/copy", ['to' => [$this->b->id]])->assertNotFound();
    // Không phải chủ app: 403.
    $member = User::factory()->create(['account_id' => $this->account->id]);
    $this->actingAs($member)->post("/auto/accounts/{$this->a->id}/links/copy", ['to' => [$this->b->id]])->assertForbidden();
    // Chép vào chính nó.
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->a->id}/links/copy", ['to' => [$this->a->id]])->assertSessionHas('flash.error');

    expect(ProductLink::query()->where('social_account_id', '!=', $this->a->id)->count())->toBe(0);
});

test('copy reports an error when the source channel has no cart rows yet', function (): void {
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->a->id}/links/copy", ['to' => [$this->b->id]])
        ->assertRedirect()->assertSessionHas('flash.error');
});

// ---- Chấm báo ở thanh trên cùng ----

test('fork_badges carries the attention counts', function (): void {
    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn ($p) => $p
        ->where('fork_badges.chrome_offline', 2) // hai kênh bật Chrome, chưa có Chrome nào kết nối
        ->where('fork_badges.failed_24h', 0)
        ->where('fork_badges.update_available', false)
        ->where('fork_badges.buy_comments', 0));
});

<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.auto.hub_api.key', 'khoa-thu');
    File::deleteDirectory(storage_path('app/product-covers'));

    $account = Account::factory()->create();
    $owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $owner->id]);
    $owner->update(['current_workspace_id' => $ws->id]);
    $sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $ws->id]);
    AutoProduct::query()->create(['code' => 'tc01', 'name' => 'TC01', 'short_name' => 'TC01', 'facts' => [], 'enabled' => true]);

    $this->shop = ShopProduct::query()->create(['social_account_id' => $sa->id, 'product_id' => '7600000000000000009', 'title' => '[Hot] Nano Đồng 1L', 'price' => '99000', 'cover_url' => 'https://p16-oec-sg.ibyteimg.com/x.png', 'stock_num' => 5, 'synced_at' => now()]);
    ProductLink::query()->create(['social_account_id' => $sa->id, 'auto_product_id' => 'tc01', 'shop_product_id' => '7600000000000000009', 'display_name' => 'NANO']);
});

afterEach(fn () => File::deleteDirectory(storage_path('app/product-covers')));

test('shop feed needs the hub key', function (): void {
    $this->getJson('/api/xuong/shop-products')->assertStatus(401);
    $this->getJson('/api/xuong/shop-products', ['X-Key' => 'sai'])->assertStatus(401);
    $this->get('/api/xuong/shop-products/7600000000000000009/image', ['X-Key' => 'sai'])->assertStatus(401);

    config()->set('fork.auto.hub_api.key', '');
    $this->getJson('/api/xuong/shop-products', ['X-Key' => ''])->assertStatus(401);
});

test('shop feed lists products with linked codes and image url', function (): void {
    $this->getJson('/api/xuong/shop-products', ['X-Key' => 'khoa-thu'])->assertOk()
        ->assertJsonPath('ok', true)
        ->assertJsonPath('items.0.shop_product_id', '7600000000000000009')
        ->assertJsonPath('items.0.title', '[Hot] Nano Đồng 1L')
        ->assertJsonPath('items.0.price', '99000')
        ->assertJsonPath('items.0.linked_codes', ['tc01'])
        ->assertJson(fn ($j) => $j->where('items.0.image_url', fn ($u) => str_starts_with((string) $u, '/api/xuong/shop-products/7600000000000000009/image'))->etc());
});

test('shop feed streams the cached image', function (): void {
    Http::fake(['*' => Http::response(base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='), 200, ['Content-Type' => 'image/png'])]);

    $this->get('/api/xuong/shop-products/7600000000000000009/image', ['X-Key' => 'khoa-thu'])->assertOk()->assertHeader('Content-Type', 'image/png');
    $this->get('/api/xuong/shop-products/1234/image', ['X-Key' => 'khoa-thu'])->assertNotFound();
});

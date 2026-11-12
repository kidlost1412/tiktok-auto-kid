<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Database\QueryException;
use Inertia\Testing\AssertableInertia;

const GH_1L = '1729384756000000001';
const GH_5L = '1729384756000000005';

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh_a']);
    ChromeAccount::query()->create(['social_account_id' => $this->sa->id, 'enabled' => true, 'tiktok_user_id' => '777']);

    $this->hub = AutoProduct::query()->create([
        'code' => 'dam-ca', 'name' => 'Đạm cá', 'short_name' => 'Đạm cá', 'facts' => [], 'enabled' => true,
        'quy_cach' => [['ma' => '1l', 'ten' => 'Chai 1L'], ['ma' => '5l', 'ten' => 'Can 5L']],
    ]);
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);

    $this->shop = fn (string $id, array $o = [], ?SocialAccount $sa = null): ShopProduct => ShopProduct::query()->create(array_merge([
        'social_account_id' => ($sa ?? $this->sa)->id, 'product_id' => $id, 'source' => 'my_shop', 'title' => '[LIVESTREAM] Đạm cá 1L',
        'price' => '99.000đ', 'cover_url' => 'https://img.example/a.jpg', 'stock_num' => 7, 'synced_at' => now(),
    ], $o));
});

test('page lists only Chrome-enabled channels and builds one row per hub product x quy cach', function (): void {
    SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'username' => 'khong_chrome']);
    ($this->shop)(GH_1L);
    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'dam-ca', 'quy_cach' => '1l', 'shop_product_id' => GH_1L, 'display_name' => 'ĐẠM CÁ 1L']);
    AutoVideo::query()->create(['hash' => 'h1', 'path' => '/x.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'x.mp4', 'product_code' => 'dam-ca', 'quy_cach' => '5l', 'status' => 'new']);

    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/GioHang')
        ->has('channels', 1)
        ->where('selected', $this->sa->id)
        ->where('sync.state', 'idle')
        ->has('rows', 3)
        ->where('rows', function ($rows): bool {
            $by = collect($rows)->keyBy('label');

            return $by->keys()->sort()->values()->all() === collect(['Đạm cá – Can 5L', 'Đạm cá – Chai 1L', 'NanoĐồng'])->sort()->values()->all()
                && $by['Đạm cá – Chai 1L']['link']['shop_product_id'] === GH_1L
                && $by['Đạm cá – Chai 1L']['link']['product']['title'] === '[LIVESTREAM] Đạm cá 1L'
                && $by['Đạm cá – Can 5L']['link'] === null
                && $by['Đạm cá – Can 5L']['new_videos'] === 1
                && $by['NanoĐồng']['quy_cach'] === null;
        })
        ->where('products.0.suggested_name', 'ĐẠM CÁ 1L')
        ->where('products.0.used_by.0', 'Đạm cá – Chai 1L'));
});

test('the page is owner-only', function (): void {
    $member = User::factory()->create(['account_id' => $this->account->id]);
    $this->actingAs($member)->get('/auto/gio-hang')->assertForbidden();

});

test('links are saved per quy cach and one never overwrites another', function (): void {
    ($this->shop)(GH_1L);
    ($this->shop)(GH_5L, ['title' => 'Đạm cá 5L']);
    $url = "/auto/accounts/{$this->sa->id}/links/dam-ca";
    $put = fn (string $qc, string $id) => $this->actingAs($this->owner)->put($url, ['quy_cach' => $qc, 'shop_product_id' => $id, 'display_name' => 'Đạm cá '.$qc]);

    $put('1l', GH_1L)->assertSessionHas('flash.success');
    $put('5l', GH_5L)->assertSessionHas('flash.success');
    $put('5l', GH_1L)->assertSessionHas('flash.success'); // lưu lại cùng quy cách: cập nhật, không nhân đôi

    expect(ProductLink::query()->count())->toBe(2)
        ->and(ProductLink::slot($this->sa->id, 'dam-ca', '1l')->value('shop_product_id'))->toBe(GH_1L)
        ->and(ProductLink::slot($this->sa->id, 'dam-ca', '5l')->value('shop_product_id'))->toBe(GH_1L);

    $this->actingAs($this->owner)->delete($url, ['quy_cach' => '5l'])->assertRedirect();
    expect(ProductLink::query()->count())->toBe(1)->and(ProductLink::slot($this->sa->id, 'dam-ca', '1l')->exists())->toBeTrue();
});

test('quy cach must belong to the hub product; products without quy cach use null only', function (): void {
    ($this->shop)(GH_1L);
    $dam = ['shop_product_id' => GH_1L, 'display_name' => 'x'];
    $put = fn (string $code, array $d) => $this->actingAs($this->owner)->put("/auto/accounts/{$this->sa->id}/links/{$code}", $d);

    $put('dam-ca', $dam + ['quy_cach' => '20l'])->assertSessionHas('flash.error');
    $put('dam-ca', $dam)->assertSessionHas('flash.error');                       // sản phẩm có quy cách thì phải chọn quy cách
    $put('nano-dong', $dam + ['quy_cach' => '1l'])->assertSessionHas('flash.error');
    expect(ProductLink::query()->count())->toBe(0);

    $put('nano-dong', $dam)->assertSessionHas('flash.success');
    expect(ProductLink::slot($this->sa->id, 'nano-dong', null)->exists())->toBeTrue();
    $put('nano-dong', $dam)->assertSessionHas('flash.success');
    expect(ProductLink::query()->count())->toBe(1);
});

test('the database refuses two links for the same (channel, product, quy cach), including null', function (): void {
    $row = ['social_account_id' => $this->sa->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => GH_1L, 'display_name' => 'x'];
    ProductLink::query()->create($row);
    expect(fn () => ProductLink::query()->create($row))->toThrow(QueryException::class);
});

test('a shop product of another channel, missing or hidden cannot be chosen', function (): void {
    $other = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id]);
    ($this->shop)(GH_5L, [], $other);
    ($this->shop)('1729384756000000009', ['missing' => true]);
    ($this->shop)('1729384756000000008', ['hidden' => true]);
    $put = fn (string $id) => $this->actingAs($this->owner)->put("/auto/accounts/{$this->sa->id}/links/nano-dong", ['shop_product_id' => $id, 'display_name' => 'x']);

    foreach ([GH_5L, '1729384756000000009', '1729384756000000008'] as $id) {
        $put($id)->assertSessionHas('flash.error');
    }

    expect(ProductLink::query()->count())->toBe(0);
});

test('eligible() returns only valid pairs and warns about unlinked quy cach with waiting videos', function (): void {
    ($this->shop)(GH_1L);
    ($this->shop)(GH_5L, ['stock_num' => 0]);
    $mk = fn (string $qc, string $id) => ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'dam-ca', 'quy_cach' => $qc, 'shop_product_id' => $id, 'display_name' => 'x']);
    $mk('1l', GH_1L);
    $mk('5l', GH_5L);
    $rules = app(CartRules::class);

    expect($rules->eligible($this->sa->id))->toBe(['dam-ca' => ['1l']]);

    // quy cách 20l có video nhưng chưa chọn sản phẩm
    $this->hub->update(['quy_cach' => [['ma' => '1l', 'ten' => 'Chai 1L'], ['ma' => '5l', 'ten' => 'Can 5L'], ['ma' => '20l', 'ten' => 'Phuy 20L']]]);
    AutoVideo::query()->create(['hash' => 'h20', 'path' => '/x.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'x.mp4', 'product_code' => 'dam-ca', 'quy_cach' => '20l', 'status' => 'new']);

    $warnings = implode("\n", $rules->evaluate($this->sa->id)['warnings']);
    expect($warnings)->toContain('Đạm cá – Phuy 20L chưa chọn sản phẩm: video giữ trong kho')
        ->and($warnings)->toContain('hết hàng');
});

test('eligible() skips hidden, paused, and quy cach no longer in the hub', function (): void {
    ($this->shop)(GH_1L, ['hidden' => true]);
    ($this->shop)(GH_5L);
    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'dam-ca', 'quy_cach' => '1l', 'shop_product_id' => GH_1L, 'display_name' => 'x']);
    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'dam-ca', 'quy_cach' => '5l', 'shop_product_id' => GH_5L, 'display_name' => 'x', 'paused_reason' => 'dừng']);
    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'nano-dong', 'quy_cach' => '9l', 'shop_product_id' => GH_5L, 'display_name' => 'x']);
    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'dam-ca', 'quy_cach' => null, 'shop_product_id' => GH_5L, 'display_name' => 'x']);

    expect(app(CartRules::class)->eligible($this->sa->id))->toBe([]);
});

test('suggestName strips [..] tags, uppercases and keeps 30 characters', function (): void {
    expect(CartRules::suggestName('[LIVESTREAM] Đạm cá 1L'))->toBe('ĐẠM CÁ 1L')
        ->and(CartRules::suggestName('[HÀNG TẶNG 1] Phân bón lá siêu dưỡng chất cao cấp nhập khẩu'))->toBe('PHÂN BÓN LÁ SIÊU DƯỠNG CHẤT CA')
        ->and(mb_strlen(CartRules::suggestName(str_repeat('a', 80))))->toBe(30)
        ->and(CartRules::suggestName('[ONLY TAG]'))->toBe('[ONLY TAG]');
});

// ---------------------------------------------------------------- trạng thái lấy sản phẩm

test('every sync click issues a fresh request id and clears the old error', function (): void {
    $sync = app(ShopSync::class);
    $first = $sync->requestSync($this->sa->id);
    $sync->reportFailure($this->sa->id, $first, 'sync-timeout');
    $second = $sync->requestSync($this->sa->id);

    $auto = AutoAccount::query()->find($this->sa->id);
    expect($second)->not->toBe($first)
        ->and($auto->products_sync_request)->toBe($second)
        ->and($auto->products_sync_error)->toBeNull()
        ->and($sync->pendingRequest($this->sa->id))->toBe($second);
});

test('sync status: waiting, error, expired after 10 minutes (tasks stop offering it), done', function (): void {
    $sync = app(ShopSync::class);
    expect($sync->status(null)['state'])->toBe('idle');

    $id = $sync->requestSync($this->sa->id);
    expect($sync->status(AutoAccount::query()->find($this->sa->id))['state'])->toBe('waiting');

    expect($sync->reportFailure($this->sa->id, 'khac', 'x'))->toBeFalse()   // yêu cầu cũ/khác không ghi đè
        ->and($sync->reportFailure($this->sa->id, $id, 'tab-closed'))->toBeTrue();
    $st = $sync->status(AutoAccount::query()->find($this->sa->id));
    expect($st['state'])->toBe('error')->and($st['reason'])->toBe('tab-closed');

    AutoAccount::query()->find($this->sa->id)->update(['products_sync_requested_at' => CarbonImmutable::now()->subMinutes(11)]);
    expect($sync->status(AutoAccount::query()->find($this->sa->id))['state'])->toBe('expired')
        ->and($sync->pendingRequest($this->sa->id))->toBeNull();

    $again = $sync->requestSync($this->sa->id);
    $sync->ingestProducts($this->sa->id, $again, 'my_shop', [], true);
    $done = $sync->status(AutoAccount::query()->find($this->sa->id));
    expect($done['state'])->toBe('done')->and($done['synced_at'])->not->toBeNull();
});

test('the page shows the sync state and the extension can report a failure', function (): void {
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/shop/sync")->assertSessionHas('flash.success');
    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn (AssertableInertia $p) => $p->where('sync.state', 'waiting'));

    $chrome = app(ChromeJobs::class);
    $paired = $chrome->createClient((string) $this->account->id, 'Chrome', '1.1.0', 1);
    $paired['client']->forceFill(['tiktok_user_id' => '777', 'tiktok_username' => 'kenh_a'])->save();
    $headers = ['Authorization' => 'Bearer '.$paired['token'], 'X-Autotok-Protocol' => '1'];
    $id = AutoAccount::query()->find($this->sa->id)->products_sync_request;

    $this->postJson('/api/ext/sync_status', ['request_id' => 'sai', 'ok' => false, 'reason' => 'sync-timeout'], $headers)->assertOk()->assertJson(['recorded' => false]);
    $this->postJson('/api/ext/sync_status', ['request_id' => $id, 'ok' => false, 'reason' => 'sync-timeout'], $headers)->assertOk()->assertJson(['recorded' => true]);
    $this->postJson('/api/ext/sync_status', ['request_id' => $id, 'ok' => false, 'reason' => 'x'])->assertStatus(401);

    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('sync.state', 'error')
        ->where('sync.reason', fn (string $r) => str_contains($r, '4 phút')));
});

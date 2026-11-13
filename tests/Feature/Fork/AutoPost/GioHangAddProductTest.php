<?php

declare(strict_types=1);

use App\Fork\AutoPost\Jobs\PrefetchProductCovers;
use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Rieng\RiengBatch;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\Shop\ProductNaming;
use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Factory;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Facade;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;
use Inertia\Testing\AssertableInertia;

const AP_ID = '1729384756000000101';
const AP_TITLE = '[LIVESTREAM] Đạm Cá Amino 1L Chất Hữu Cơ 20% Amino Acid Giúp Cây Bật Mầm Xanh Lá';

function resetHttpFake(): void
{
    app()->forgetInstance(Factory::class);
    Facade::clearResolvedInstance(Factory::class);
}

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $this->hubDir = sys_get_temp_dir().'/tta-hub-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hubDir.'/san-pham');
    config(['fork.auto.hub_path' => $this->hubDir, 'fork.xuong.url' => 'http://127.0.0.1:8765']);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'kenh_a']);
    ChromeAccount::query()->create(['social_account_id' => $this->sa->id, 'enabled' => true, 'tiktok_user_id' => '777']);

    // Hub mới cài chỉ có sản phẩm ví dụ (thư mục san-pham/vi-du có thật, như bản cài).
    File::ensureDirectoryExists($this->hubDir.'/san-pham/vi-du');
    File::put($this->hubDir.'/san-pham/vi-du/san-pham.json', json_encode(['ma' => 'vi-du', 'ten_goi' => 'Sản phẩm ví dụ', 'ten_ngan' => 'Ví dụ', 'quy_cach' => []], JSON_UNESCAPED_UNICODE));
    AutoProduct::query()->create(['code' => 'vi-du', 'name' => 'Sản phẩm ví dụ', 'short_name' => 'Ví dụ', 'facts' => ['ma' => 'vi-du'], 'enabled' => true, 'quy_cach' => []]);

    $this->shop = fn (string $id = AP_ID, array $o = []): ShopProduct => ShopProduct::query()->create(array_merge([
        'social_account_id' => $this->sa->id, 'product_id' => $id, 'source' => 'my_shop', 'title' => AP_TITLE,
        'price' => '249.000đ', 'cover_url' => 'https://p16.ibyteimg.com/a~tplv-x-resize-image:48:48.image', 'stock_num' => 9, 'synced_at' => now(),
    ], $o));

    // Hub giả: nhận /api/san-pham-moi và ghi hồ sơ như hub thật (san-pham/<mã>/san-pham.json).
    // Http::fake() chỉ cộng dồn các mẫu trả lời (mẫu đầu thắng), nên mỗi lần giả lập lại phải bỏ bản cũ.
    $this->fakeHub = function (array $over = []): void {
        resetHttpFake();
        Http::fake(array_merge([
            '127.0.0.1:8765/api/san-pham-moi' => function (Request $r) {
                $b = $r->data();
                File::ensureDirectoryExists($this->hubDir.'/san-pham/'.$b['ma']);
                File::put($this->hubDir.'/san-pham/'.$b['ma'].'/san-pham.json', json_encode([
                    'ma' => $b['ma'], 'ten_goi' => $b['ten'], 'ten_ngan' => $b['ten_ngan'], 'shop_product_id' => $b['shop_id'], 'quy_cach' => [],
                ], JSON_UNESCAPED_UNICODE));

                return Http::response(['ok' => true, 'ma' => $b['ma']]);
            },
            '127.0.0.1:8765/api/san-pham/*' => Http::response(['ok' => true]),
            '127.0.0.1:8765/api/xoa-san-pham/*' => Http::response(['ok' => true, 'bo_canh_qua' => []]),
        ], $over));
    };
});

afterEach(function (): void {
    File::deleteDirectory($this->hubDir);
});

test('naming: tags are stripped, short name is the first words, code is a hub-valid slug and never collides', function (): void {
    expect(ProductNaming::clean(AP_TITLE))->toStartWith('Đạm Cá Amino 1L')
        ->and(ProductNaming::shortName(AP_TITLE))->toBe('Đạm Cá Amino 1L')
        ->and(mb_strlen(ProductNaming::fullName(str_repeat('Rất dài ', 40))))->toBeLessThanOrEqual(ProductNaming::FULL_MAX)
        ->and(ProductNaming::shortName('[HOT]'))->not->toBe('')
        ->and(ProductNaming::code('Đạm Cá Amino 1L', fn () => false))->toBe('dam-ca-amino-1l')
        ->and(ProductNaming::code('Đạm Cá Amino 1L', fn (string $c) => in_array($c, ['dam-ca-amino-1l', 'dam-ca-amino-1l-2'], true)))->toBe('dam-ca-amino-1l-3')
        ->and(ProductNaming::validCode(ProductNaming::code('Kích Rễ Cực Mạnh!!! ', fn () => false)))->toBeTrue()
        ->and(strlen(ProductNaming::code(str_repeat('abc ', 30), fn () => false)))->toBeLessThanOrEqual(ProductNaming::CODE_MAX);
});

test('add product: one click creates the hub product through the hub API, maps it for the channel and it is usable for posting and Kho riêng', function (): void {
    ($this->shop)();
    ($this->fakeHub)();

    $this->actingAs($this->owner)
        ->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => AP_ID, 'display_name' => 'ĐẠM CÁ AMINO 1L'])
        ->assertSessionHas('flash.success');

    Http::assertSent(fn (Request $r) => str_ends_with($r->url(), '/api/san-pham-moi')
        && $r['ma'] === 'dam-ca-amino-1l' && $r['ten_ngan'] === 'Đạm Cá Amino 1L' && $r['shop_id'] === AP_ID
        && str_starts_with($r['ten'], 'Đạm Cá Amino 1L'));

    $product = AutoProduct::query()->find('dam-ca-amino-1l');
    expect($product)->not->toBeNull()->and($product->short_name)->toBe('Đạm Cá Amino 1L')->and($product->enabled)->toBeTrue();

    $link = ProductLink::query()->where('auto_product_id', 'dam-ca-amino-1l')->first();
    expect($link->social_account_id)->toBe($this->sa->id)
        ->and($link->shop_product_id)->toBe(AP_ID)
        ->and($link->display_name)->toBe('ĐẠM CÁ AMINO 1L')
        ->and($link->quy_cach)->toBeNull();

    // Đăng được (luật giỏ hàng) và hiện trong hộp "Đặt lịch hàng loạt" của Kho riêng (liệt kê sản phẩm đã gắn giỏ của kênh).
    expect(app(CartRules::class)->eligible($this->sa->id))->toHaveKey('dam-ca-amino-1l');
    expect(collect(app(RiengBatch::class)->productOptions($this->sa->id))->pluck('code')->all())->toContain('dam-ca-amino-1l');
});

test('add product: the chosen name is used, a taken code gets a suffix, and no hub file is written by the app itself', function (): void {
    ($this->shop)();
    ($this->shop)('1729384756000000102');
    ($this->fakeHub)();

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => AP_ID, 'name' => 'Đạm cá'])->assertSessionHas('flash.success');
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => '1729384756000000102', 'name' => 'Đạm cá'])->assertSessionHas('flash.success');

    expect(AutoProduct::query()->whereIn('code', ['dam-ca', 'dam-ca-2'])->count())->toBe(2);
    // Chỉ hub (giả lập) ghi san-pham/<mã>/: cả hai thư mục đều do callback của hub giả tạo ra qua API.
    Http::assertSentCount(2);
});

test('add product: hub offline or refusing shows a clear message and creates nothing', function (): void {
    ($this->shop)();
    Http::fake(['127.0.0.1:8765/*' => fn () => throw new ConnectionException('refused')]);

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => AP_ID])
        ->assertSessionHas('flash.error', fn (string $m) => str_contains($m, 'Xưởng Video'));
    expect(AutoProduct::query()->count())->toBe(1)->and(ProductLink::query()->count())->toBe(0);

    resetHttpFake();
    Http::fake(['127.0.0.1:8765/*' => Http::response(['ok' => false, 'loi' => 'Thiếu tên sản phẩm'], 200)]);
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => AP_ID])
        ->assertSessionHas('flash.error', fn (string $m) => str_contains($m, 'Thiếu tên sản phẩm'));
    expect(ProductLink::query()->count())->toBe(0);
});

test('add product: only a visible product of this channel shop can be added', function (): void {
    ($this->fakeHub)();
    ($this->shop)(AP_ID, ['missing' => true]);
    ($this->shop)('1729384756000000103', ['hidden' => true]);

    foreach ([AP_ID, '1729384756000000103', '1729384756000000999'] as $id) {
        $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => $id])->assertSessionHas('flash.error');
    }

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => 'abc'])->assertSessionHasErrors('shop_product_id');
    Http::assertNothingSent();
    expect(ProductLink::query()->count())->toBe(0);
});

test('sample product: hidden once a real product exists (unless it has a cart or waiting videos), always listed alone for a new user', function (): void {
    ($this->shop)();

    $rows = fn () => $this->actingAs($this->owner)->get('/auto/gio-hang');

    // Người mới: chỉ có thẻ ví dụ, đánh dấu is_sample.
    $rows()->assertInertia(fn (AssertableInertia $p) => $p->has('rows', 1)->where('rows.0.is_sample', true)->where('sample_hidden', false));

    ($this->fakeHub)();
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => AP_ID]);

    $rows()->assertInertia(fn (AssertableInertia $p) => $p->has('rows', 1)->where('rows.0.code', 'dam-ca-amino-1l')->where('rows.0.is_sample', false)->where('sample_hidden', true));

    // Có video chờ cho sản phẩm ví dụ thì vẫn hiện.
    AutoVideo::query()->create(['hash' => 'h1', 'path' => '/x.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'x.mp4', 'product_code' => 'vi-du', 'status' => 'new']);
    $rows()->assertInertia(fn (AssertableInertia $p) => $p->has('rows', 2)->where('sample_hidden', false));
});

test('sample product with a cart chosen by the owner stays visible next to the new one', function (): void {
    ($this->shop)();
    ($this->shop)('1729384756000000104');
    ($this->fakeHub)();
    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'vi-du', 'quy_cach' => null, 'shop_product_id' => '1729384756000000104', 'display_name' => 'X']);

    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => AP_ID]);

    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn (AssertableInertia $p) => $p->has('rows', 2)->where('sample_hidden', false));
});

test('rename goes through the hub API and refreshes the app copy; empty name is refused', function (): void {
    ($this->shop)();
    ($this->fakeHub)();
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => AP_ID]);

    $this->actingAs($this->owner)->patch('/auto/hub-products/dam-ca-amino-1l', ['name' => '  '])->assertSessionHasErrors('name');

    // Hub thật ghi ten_ngan vào san-pham.json; giả lập điều đó rồi để app đọc lại.
    ($this->fakeHub)(['127.0.0.1:8765/api/san-pham/*' => function (Request $r) {
        $f = $this->hubDir.'/san-pham/dam-ca-amino-1l/san-pham.json';
        File::put($f, json_encode([...json_decode(File::get($f), true), 'ten_ngan' => $r['ten_ngan']], JSON_UNESCAPED_UNICODE));

        return Http::response(['ok' => true]);
    }]);
    $this->actingAs($this->owner)->patch('/auto/hub-products/dam-ca-amino-1l', ['name' => 'Đạm cá chai 1 lít'])->assertSessionHas('flash.success');

    expect(AutoProduct::query()->find('dam-ca-amino-1l')->short_name)->toBe('Đạm cá chai 1 lít');
    $this->actingAs($this->owner)->patch('/auto/hub-products/khong-co', ['name' => 'A'])->assertNotFound();
});

test('delete: refused while videos wait or are scheduled; otherwise the hub is asked, the cart links go and the product is switched off', function (): void {
    ($this->shop)();
    ($this->fakeHub)();
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/hub-products", ['shop_product_id' => AP_ID]);

    $video = AutoVideo::query()->create(['hash' => 'h2', 'path' => '/y.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'y.mp4', 'product_code' => 'dam-ca-amino-1l', 'status' => 'scheduled']);
    $this->actingAs($this->owner)->delete('/auto/hub-products/dam-ca-amino-1l')->assertSessionHas('flash.error');
    Http::assertNotSent(fn (Request $r) => str_contains($r->url(), 'xoa-san-pham'));
    expect(ProductLink::query()->count())->toBe(1);

    $video->update(['status' => 'posted']);
    $this->actingAs($this->owner)->delete('/auto/hub-products/dam-ca-amino-1l')->assertSessionHas('flash.success');

    Http::assertSent(fn (Request $r) => str_ends_with($r->url(), '/api/xoa-san-pham/dam-ca-amino-1l'));
    expect(ProductLink::query()->count())->toBe(0)->and(AutoProduct::query()->find('dam-ca-amino-1l')->enabled)->toBeFalse();
});

test('delete the sample: the hub is asked and the hub refusing leaves everything as it was', function (): void {
    Http::fake(['127.0.0.1:8765/*' => Http::response(['ok' => false, 'loi' => 'Không xoá được'], 200)]);
    $this->actingAs($this->owner)->delete('/auto/hub-products/vi-du')->assertSessionHas('flash.error', fn (string $m) => str_contains($m, 'Không xoá được'));
    expect(AutoProduct::query()->find('vi-du')->enabled)->toBeTrue();

    ($this->fakeHub)();
    $this->actingAs($this->owner)->delete('/auto/hub-products/vi-du')->assertSessionHas('flash.success');
    expect(AutoProduct::query()->find('vi-du')->enabled)->toBeFalse();
});

test('sync progress: only the pending request can report it, the page shows got/total, and finishing clears it', function (): void {
    $this->actingAs($this->owner)->post("/auto/accounts/{$this->sa->id}/shop/sync")->assertSessionHas('flash.success');
    $id = AutoAccount::query()->find($this->sa->id)->products_sync_request;

    $paired = app(ChromeJobs::class)->createClient((string) $this->account->id, 'Chrome', '1.1.0', 1);
    $paired['client']->forceFill(['tiktok_user_id' => '777', 'tiktok_username' => 'kenh_a'])->save();
    $headers = ['Authorization' => 'Bearer '.$paired['token'], 'X-Autotok-Protocol' => '1'];

    $this->postJson('/api/ext/sync_status', ['request_id' => 'sai', 'ok' => true, 'progress' => ['got' => 5, 'total' => 58]], $headers)->assertOk()->assertJson(['recorded' => false]);
    $this->postJson('/api/ext/sync_status', ['request_id' => $id, 'ok' => true, 'progress' => ['got' => 20, 'total' => 58]], $headers)->assertOk()->assertJson(['recorded' => true]);

    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('sync.state', 'waiting')->where('sync.progress.got', 20)->where('sync.progress.total', 58));

    // Tổng nhỏ hơn số đã lấy thì nâng tổng lên; số âm / quá lớn bị chặn.
    $this->postJson('/api/ext/sync_status', ['request_id' => $id, 'ok' => true, 'progress' => ['got' => 30, 'total' => 10]], $headers)->assertJson(['recorded' => true]);
    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn (AssertableInertia $p) => $p->where('sync.progress.got', 30)->where('sync.progress.total', 30));
    $this->postJson('/api/ext/sync_status', ['request_id' => $id, 'ok' => true, 'progress' => ['got' => 'x']], $headers)->assertJson(['recorded' => false]);

    Queue::fake();
    $sync = app(ShopSync::class);
    $sync->ingestProducts((string) $this->sa->id, $id, 'my_shop', $sync->normalizeProducts([['product_id' => AP_ID, 'title' => 'A', 'cover_url' => 'https://p16.ibyteimg.com/a.jpg']]), true);

    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn (AssertableInertia $p) => $p->where('sync.state', 'done')->where('sync.progress', null));
    Queue::assertPushed(PrefetchProductCovers::class, fn (PrefetchProductCovers $j) => $j->socialAccountId === (string) $this->sa->id);
});

test('covers: prefetch downloads all missing images at once, shrinks them, and the picker image route serves them without a second download', function (): void {
    $one = ($this->shop)();
    $two = ($this->shop)('1729384756000000105', ['cover_url' => 'https://p16.ibyteimg.com/b~tplv-x-resize-image:48:48.image']);
    $bad = ($this->shop)('1729384756000000106', ['cover_url' => 'https://evil.example.com/c.png']);

    // Ảnh gốc 900x600 như shop thật (nặng), phải được thu về <= 360px.
    $im = imagecreatetruecolor(900, 600);
    imagefill($im, 0, 0, (int) imagecolorallocate($im, 200, 30, 30));
    ob_start();
    imagepng($im, null, 0);
    $png = (string) ob_get_clean();
    Http::fake(['p16.ibyteimg.com/*' => Http::response($png, 200, ['Content-Type' => 'image/png'])]);

    $images = app(ProductImages::class);
    $saved = $images->prefetch(ShopProduct::query()->get());

    expect($saved)->toBe(2);
    // Bản lớn 400:400 được xin trước; chỉ 2 lần tải (host lạ bị bỏ qua).
    Http::assertSentCount(2);
    Http::assertSent(fn (Request $r) => str_contains($r->url(), 'resize-image:400:400.image'));

    foreach ([$one, $two] as $p) {
        $file = $images->cached($p);
        expect($file)->not->toBeNull();
        [$w, $h] = getimagesize($file);
        expect(max($w, $h))->toBeLessThanOrEqual(ProductImages::MAX_SIDE)->and(filesize($file))->toBeLessThan(strlen($png));
    }

    expect($images->cached($bad))->toBeNull();

    // Route nội bộ phục vụ ảnh có sẵn, không tải lại.
    $this->actingAs($this->owner)->get(ProductImages::url($one))->assertOk()->assertHeader('Content-Type', 'image/jpeg');
    Http::assertSentCount(2);

    // Lần prefetch sau không còn gì để tải.
    expect($images->prefetch(ShopProduct::query()->get()))->toBe(0);

    foreach ([$one, $two] as $p) {
        foreach (glob(ProductImages::dir().'/'.$p->id.'-*') ?: [] as $f) {
            @unlink($f);
        }
    }
});

test('covers: a failed download is remembered so the page does not hammer the CDN, and the picker gets a 404 (placeholder icon)', function (): void {
    $p = ($this->shop)();
    Http::fake(['p16.ibyteimg.com/*' => Http::response('', 403)]);
    Cache::flush();

    $this->actingAs($this->owner)->get(ProductImages::url($p))->assertNotFound();
    $this->actingAs($this->owner)->get(ProductImages::url($p))->assertNotFound();

    // Lần 1: bản lớn + link gốc (2 lần thử); lần 2 đọc từ bộ nhớ đệm lỗi nên không gọi thêm.
    Http::assertSentCount(2);
});

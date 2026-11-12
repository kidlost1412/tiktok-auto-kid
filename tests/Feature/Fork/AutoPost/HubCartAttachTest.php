<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Shop\HubCartAttach;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\File;

const HCA_ID = '1729384756000000111';
const HCA_ID2 = '1729384756000000222';

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);

    $this->channel = function (string $username, bool $chrome = true): SocialAccount {
        $sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'username' => $username]);
        ChromeAccount::query()->create(['social_account_id' => $sa->id, 'enabled' => $chrome, 'tiktok_user_id' => (string) random_int(1000, 999999)]);

        return $sa;
    };
    $this->sa = ($this->channel)('kenh_a');

    $this->shop = fn (SocialAccount $sa, string $id = HCA_ID, array $o = []): ShopProduct => ShopProduct::query()->create(array_merge([
        'social_account_id' => $sa->id, 'product_id' => $id, 'source' => 'my_shop', 'title' => '[LIVESTREAM] Nano Đồng 500ml',
        'price' => '99.000đ', 'stock_num' => 7, 'synced_at' => now(),
    ], $o));

    $this->hubProduct = fn (string $code, array $facts = [], array $o = []): AutoProduct => AutoProduct::query()->create(array_merge([
        'code' => $code, 'name' => $code, 'short_name' => $code, 'enabled' => true,
        'facts' => ['ma' => $code, ...$facts],
    ], $o));

    $this->run = fn (): int => app(HubCartAttach::class)->run();
});

test('attaches the hub-chosen shop product only on channels whose shop owns it', function (): void {
    $other = ($this->channel)('kenh_b');
    $off = ($this->channel)('kenh_tat', false);
    ($this->shop)($this->sa);
    ($this->shop)($other, HCA_ID2);      // shop kênh B không có sản phẩm hub chọn
    ($this->shop)($off);                 // kênh tắt Chrome: không gắn
    ($this->hubProduct)('nano-dong', ['shop_product_id' => HCA_ID, 'ten_gio' => 'NANO ĐỒNG']);

    expect(($this->run)())->toBe(1);

    $link = ProductLink::query()->sole();
    expect($link->social_account_id)->toBe($this->sa->id)
        ->and($link->auto_product_id)->toBe('nano-dong')
        ->and($link->quy_cach)->toBeNull()
        ->and($link->shop_product_id)->toBe(HCA_ID)
        ->and($link->display_name)->toBe('NANO ĐỒNG')
        ->and($link->paused_reason)->toBeNull();
});

test('falls back to the suggested name from the shop title when the hub has no ten_gio', function (): void {
    ($this->shop)($this->sa);
    ($this->hubProduct)('nano-dong', ['shop_product_id' => HCA_ID]);

    ($this->run)();

    expect(ProductLink::query()->sole()->display_name)->toBe('NANO ĐỒNG 500ML');
});

test('never overwrites a link the owner set, and does not take over the slot later', function (): void {
    ($this->shop)($this->sa);
    ($this->shop)($this->sa, HCA_ID2, ['title' => 'Khác']);
    ($this->hubProduct)('nano-dong', ['shop_product_id' => HCA_ID]);
    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => HCA_ID2, 'display_name' => 'CHỌN TAY']);

    expect(($this->run)())->toBe(0);
    expect(ProductLink::query()->sole()->only(['shop_product_id', 'display_name']))->toBe(['shop_product_id' => HCA_ID2, 'display_name' => 'CHỌN TAY']);

    // Chủ app bỏ chọn: lựa chọn của hub đã được xét rồi, không tự gắn lại.
    ProductLink::query()->delete();
    expect(($this->run)())->toBe(0)->and(ProductLink::query()->count())->toBe(0);
});

test('is idempotent and respects the owner clearing an auto link; a new hub choice is attached', function (): void {
    ($this->shop)($this->sa);
    ($this->shop)($this->sa, HCA_ID2, ['title' => 'Nano Đồng 1L']);
    $p = ($this->hubProduct)('nano-dong', ['shop_product_id' => HCA_ID]);

    expect(($this->run)())->toBe(1)
        ->and(($this->run)())->toBe(0)
        ->and(ProductLink::query()->count())->toBe(1);

    ProductLink::query()->delete();     // chủ app bấm "Bỏ chọn"
    expect(($this->run)())->toBe(0)->and(ProductLink::query()->count())->toBe(0);

    $p->update(['facts' => ['ma' => 'nano-dong', 'shop_product_id' => HCA_ID2]]);   // chủ app đổi sản phẩm Shop trong hub
    expect(($this->run)())->toBe(1)
        ->and(ProductLink::query()->sole()->shop_product_id)->toBe(HCA_ID2);
});

test('variants: one quy cach is attached on that quy cach, several are left for the owner', function (): void {
    ($this->shop)($this->sa);
    ($this->hubProduct)('mot-qc', ['shop_product_id' => HCA_ID, 'ten_gio' => ['1l' => 'CHAI 1L', '' => 'CHUNG']], ['quy_cach' => [['ma' => '1l', 'ten' => 'Chai 1L']]]);
    ($this->hubProduct)('hai-qc', ['shop_product_id' => HCA_ID], ['quy_cach' => [['ma' => '1l', 'ten' => 'Chai 1L'], ['ma' => '5l', 'ten' => 'Can 5L']]]);

    expect(($this->run)())->toBe(1);

    $link = ProductLink::query()->sole();
    expect($link->auto_product_id)->toBe('mot-qc')
        ->and($link->quy_cach)->toBe('1l')
        ->and($link->display_name)->toBe('CHAI 1L');
});

test('skips missing or hidden shop products, disabled or shared-scene hub products and bad ids', function (): void {
    ($this->shop)($this->sa, HCA_ID, ['missing' => true]);
    ($this->shop)($this->sa, HCA_ID2, ['hidden' => true]);
    ($this->hubProduct)('mat', ['shop_product_id' => HCA_ID]);
    ($this->hubProduct)('an', ['shop_product_id' => HCA_ID2]);
    ($this->hubProduct)('tat', ['shop_product_id' => HCA_ID2], ['enabled' => false]);
    ($this->hubProduct)('kho', ['shop_product_id' => HCA_ID2, 'loai' => 'kho-chung']);
    ($this->hubProduct)('sai', ['shop_product_id' => '12']);

    expect(($this->run)())->toBe(0)->and(ProductLink::query()->count())->toBe(0);

    // Hiện lại sản phẩm: lượt sau gắn (chưa từng bị "xét" khi còn ẩn).
    ShopProduct::query()->where('product_id', HCA_ID2)->update(['hidden' => false]);
    expect(($this->run)())->toBe(1)
        ->and(ProductLink::query()->sole()->auto_product_id)->toBe('an');
});

test('fork:auto-ingest picks up shop_product_id from the hub san-pham.json and attaches the cart', function (): void {
    $hub = str_replace('\\', '/', sys_get_temp_dir()).'/hub-cart-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($hub.'/san-pham/nano-dong');
    File::ensureDirectoryExists($hub.'/ra');
    file_put_contents($hub.'/san-pham/nano-dong/san-pham.json', json_encode(['ma' => 'nano-dong', 'ten_goi' => 'Nano Đồng', 'ten_ngan' => 'Nano Đồng', 'shop_product_id' => HCA_ID, 'ten_gio' => 'NANO ĐỒNG']));
    config(['fork.auto.hub_path' => $hub, 'fork.auto.hub_api.key' => '', 'fork.auto.settle_seconds' => 0]);
    ($this->shop)($this->sa);

    try {
        $this->artisan('fork:auto-ingest')->assertSuccessful();
    } finally {
        File::deleteDirectory($hub);
    }

    expect(ProductLink::query()->sole()->only(['auto_product_id', 'shop_product_id', 'display_name']))
        ->toBe(['auto_product_id' => 'nano-dong', 'shop_product_id' => HCA_ID, 'display_name' => 'NANO ĐỒNG']);
});

<?php

declare(strict_types=1);

// Bàn làm việc trong Khu Tự Trị đọc props của các trang có sẵn bằng partial reload (X-Inertia-Partial-Data).
// Các prop nặng nằm trong closure nên máy chủ chỉ tính phần được xin; tải trang đầy đủ vẫn có đủ prop như cũ.

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Http\Middleware\App\HandleInertiaRequests;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\DB;
use Inertia\Inertia;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $ws->id]);
    $sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $ws->id, 'timezone' => 'Asia/Ho_Chi_Minh']);
    AutoAccount::query()->create(['social_account_id' => $sa->id, 'enabled' => true, 'daily_cap' => 8]);
    ChromeAccount::query()->create(['social_account_id' => $sa->id, 'enabled' => true]);
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
    AutoVideo::query()->create([
        'hash' => hash('sha256', 'partial-1'),
        'path' => '/x/partial-1.mp4',
        'batch_date' => '2026-01-05',
        'file_name' => 'partial-1.mp4',
        'product_code' => 'nano-dong',
        'status' => 'new',
    ]);
});

/**
 * Gọi trang như bàn làm việc: header Inertia + partial reload. Trả về mảng props.
 *
 * @param  list<string>  $only
 * @return array<string, mixed>
 */
function partialProps(object $test, string $url, string $component, array $only): array
{
    $res = $test->actingAs($test->owner)->get($url, [
        'X-Inertia' => 'true',
        'X-Inertia-Version' => (string) app(HandleInertiaRequests::class)->version(request()),
        'X-Inertia-Partial-Component' => $component,
        'X-Inertia-Partial-Data' => implode(',', $only),
    ])->assertOk();

    return (array) $res->json('props');
}

dataset('trang-ban', [
    'auto' => ['/auto', 'fork/Auto', ['stock', 'accounts'], ['lich', 'recent', 'failed_recent', 'trend', 'upcoming', 'products', 'health', 'insights'], ['products', 'stock', 'accounts', 'health', 'lich', 'upcoming', 'recent', 'failed_recent', 'trend', 'insights']],
    'gio-hang' => ['/auto/gio-hang', 'fork/GioHang', ['channels', 'selected'], ['rows', 'products', 'sync', 'personalise', 'personalise_default', 'sample_hidden'], ['channels', 'selected', 'sync', 'products', 'rows', 'sample_hidden', 'name_max', 'personalise', 'personalise_default', 'sync_ttl_minutes']],
    'so-lieu' => ['/auto/so-lieu?range=7d', 'fork/SoLieu', ['filters', 'kpis'], ['daily', 'top', 'comments', 'followers', 'breakdowns', 'videos', 'options', 'extension'], ['filters', 'options', 'kpis', 'daily', 'breakdowns', 'videos', 'top', 'comments', 'extension']],
    'kho' => ['/auto/kho', 'fork/Kho', ['counts'], ['videos', 'matrix', 'products', 'blockers', 'days', 'hub', 'retention'], ['kho', 'retention', 'hub', 'matrix', 'products', 'filters', 'days', 'counts', 'blockers', 'videos']],
    'kho-rieng' => ['/auto/kho/rieng', 'fork/KhoRieng', ['counts'], ['videos', 'folders', 'selectable', 'queue', 'accounts', 'days'], ['folders', 'filters', 'counts', 'days', 'videos', 'selectable', 'queue', 'scan_sig', 'accounts', 'limits']],
]);

test('partial reload returns only the requested props', function (string $url, string $component, array $only, array $absent): void {
    $props = partialProps($this, $url, $component, $only);

    foreach ($only as $key) {
        expect($props)->toHaveKey($key);
    }

    foreach ($absent as $key) {
        expect($props)->not->toHaveKey($key);
    }
})->with('trang-ban');

test('full page load still carries every prop', function (string $url, string $component, array $only, array $absent, array $all): void {
    $this->actingAs($this->owner)->get($url)->assertOk()->assertInertia(function (AssertableInertia $p) use ($component, $all): void {
        $p->component($component);

        foreach ($all as $key) {
            $p->has($key);
        }
    });
})->with('trang-ban');

test('settings page serves each tab only when asked', function (): void {
    $props = partialProps($this, '/settings', 'fork/Settings', ['update']);

    expect($props)->toHaveKey('update')->and($props)->not->toHaveKey('chrome')->and($props)->not->toHaveKey('telegram');

    $this->actingAs($this->owner)->get('/settings')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/Settings')->has('chrome')->has('telegram')->has('update'));
});

test('asking for one prop of /auto does not run the heavy queries', function (): void {
    $count = function (?array $only): int {
        DB::flushQueryLog();
        DB::enableQueryLog();

        if ($only === null) {
            $this->actingAs($this->owner)->get('/auto')->assertOk();
        } else {
            partialProps($this, '/auto', 'fork/Auto', $only);
        }

        $n = count(DB::getQueryLog());
        DB::disableQueryLog();

        return $n;
    };

    $full = $count(null);
    $lean = $count(['health']);

    expect($lean)->toBeLessThan($full);
});

test('stock and accounts of /auto agree between a partial and a full load', function (): void {
    $partial = partialProps($this, '/auto', 'fork/Auto', ['stock', 'accounts']);
    $full = $this->actingAs($this->owner)->get('/auto', ['X-Inertia' => 'true', 'X-Inertia-Version' => (string) app(HandleInertiaRequests::class)->version(request())])
        ->assertOk()->json('props');

    expect($partial['stock']['new_total'])->toBe($full['stock']['new_total'])
        ->and($partial['stock']['days_left'])->toBe($full['stock']['days_left'])
        ->and($partial['accounts'])->toBe($full['accounts']);
});

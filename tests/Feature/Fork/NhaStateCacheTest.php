<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoVideo;
use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.xuong.url', 'http://127.0.0.1:8765');

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $ws->id]);
});

test('a hub that does not answer is asked once, then treated as down for a few seconds', function (): void {
    $calls = 0;
    $down = true;
    Http::fake(['127.0.0.1:8765/*' => function () use (&$calls, &$down) {
        $calls++;

        if ($down) {
            throw new ConnectionException('timeout');
        }

        return Http::response(['ok' => true, 'dang_chay' => false, 'tien_do' => [], 'su_kien' => [], 'bay_gio' => 1_800_000_000.0]);
    }]);

    $first = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();
    // Hết thời gian: KHÔNG thử thêm đường /api/trang-thai.
    expect($first['hub']['up'])->toBeFalse()->and($calls)->toBe(1);

    // Đệm 2 giây của trạng thái hết hạn, nhưng "hub tắt" còn nhớ 10 giây: không gọi hub nữa.
    Cache::forget('nha.state');
    $second = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();
    expect($second['hub']['up'])->toBeFalse()->and($calls)->toBe(1);

    // Hub sống lại và hết thời gian nhớ: hỏi lại bình thường.
    Cache::forget('nha.state');
    Cache::forget('nha.hub-down');
    $down = false;
    $third = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();
    expect($third['hub']['up'])->toBeTrue();
});

test('an older hub (404 on the event book) still falls back to the status endpoint', function (): void {
    $urls = [];
    Http::fake([
        '127.0.0.1:8765/api/su-kien*' => function ($req) use (&$urls) {
            $urls[] = 'su-kien';

            return Http::response('nope', 404);
        },
        '127.0.0.1:8765/api/trang-thai' => function ($req) use (&$urls) {
            $urls[] = 'trang-thai';

            return Http::response(['dang_chay' => false, 'tien_do' => ['xong' => 2, 'tong' => 2]]);
        },
    ]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();

    expect($j['hub']['up'])->toBeTrue()->and($urls)->toBe(['su-kien', 'trang-thai']);
});

test('failed posts are counted over 14 days, the same window as the failed list on the Sảnh desk', function (): void {
    Http::fake(['127.0.0.1:8765/*' => Http::response([], 500)]);

    $make = function (string $n, int $daysAgo): void {
        $v = AutoVideo::query()->create([
            'hash' => hash('sha256', 'nf'.$n), 'path' => "/x/nf{$n}.mp4", 'batch_date' => '2026-01-05',
            'file_name' => "nf{$n}.mp4", 'status' => AutoVideo::FAILED,
        ]);
        AutoVideo::query()->whereKey($v->id)->update(['updated_at' => now()->subDays($daysAgo)]);
    };
    $make('a', 1);
    $make('b', 10);
    $make('c', 13);
    $make('d', 20); // quá 14 ngày: không tính

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();

    expect($j['viec']['buuta']['so'])->toBe(3);
});

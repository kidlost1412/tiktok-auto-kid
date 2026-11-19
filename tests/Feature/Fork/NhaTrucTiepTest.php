<?php

declare(strict_types=1);

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeLiveProgress;
use App\Fork\Nha\NhaTrucTiep;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Schema;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.xuong.url', 'http://127.0.0.1:8765');
    Cache::flush();
    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $ws->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $ws->id, 'username' => 'vuonxanh', 'timezone' => 'Asia/Ho_Chi_Minh']);
});

function ttJob(object $t, string $id, string $state, array $extra = []): ChromeJob
{
    $p = Post::factory()->forAccount($t->sa)->create(['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addHour()]);

    return ChromeJob::query()->create(array_merge([
        'id' => str_pad($id, 26, 'x'), 'post_id' => $p->id, 'social_account_id' => $t->sa->id, 'attempt' => 1,
        'expect_user_id' => '777123', 'nonce' => 'n'.$id, 'media_path' => 'x.mp4', 'video_name' => 'nano-dong_9.mp4', 'video_size' => 20 * 1048576,
        'video_mime' => 'video/mp4', 'mode' => 'scheduled', 'caption' => 'c', 'options' => [], 'state' => $state,
    ], $extra));
}

function ttItems(string $vai): Collection
{
    return collect(NhaTrucTiep::app(CarbonImmutable::now()))->where('vai', $vai)->values();
}

test('an uploading Chrome job is a live postman item with real details', function (): void {
    ttJob($this, 'u1', 'uploading', ['claimed_at' => now()->subMinute(), 'heartbeat_at' => now()->subSeconds(20)]);

    $it = ttItems('buuta')->first();

    expect($it['nguon'])->toBe('app')
        ->and($it['viec'])->toBe('Đang tải video lên TikTok')
        ->and($it['kenh'])->toBe('@vuonxanh')
        ->and($it['video'])->toBe('nano-dong_9.mp4')
        ->and($it['xong'])->toBeFalse()
        ->and($it['tien_do'])->toBeNull()
        ->and($it['chi_tiet']['mb'])->toBe(20.0)
        ->and($it['bat_dau'])->toBeLessThan($it['cap_nhat'])
        ->and($it['id'])->toBe('buuta-'.str_pad('u1', 26, 'x'));
});

test('a job finished 10 seconds ago is kept as done, an old one is not', function (): void {
    ttJob($this, 'p1', 'posted', ['claimed_at' => now()->subMinutes(2), 'result_at' => now()->subSeconds(10)]);
    $old = ttJob($this, 'p2', 'posted', ['result_at' => now()->subMinutes(5)]);
    ChromeJob::query()->whereKey($old->id)->update(['updated_at' => now()->subMinutes(5)]);

    $items = ttItems('buuta');

    expect($items)->toHaveCount(1)
        ->and($items[0]['xong'])->toBeTrue()
        ->and($items[0]['ket_qua'])->toBe('ok');
});

test('a stuck open job (no movement for 20+ minutes) is not shown as working', function (): void {
    $j = ttJob($this, 's1', 'claimed', ['claimed_at' => now()->subHour()]);
    ChromeJob::query()->whereKey($j->id)->update(['updated_at' => now()->subMinutes(40)]);

    expect(ttItems('buuta'))->toBeEmpty();
});

test('a scheduled post due within minutes shows as "Sắp đăng"', function (): void {
    AutoVideo::query()->create([
        'hash' => hash('sha256', 'tt1'), 'path' => '/x/tt1.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'tt1.mp4', 'product_name' => 'Nano Đồng',
        'status' => AutoVideo::SCHEDULED, 'social_account_id' => $this->sa->id, 'scheduled_for' => now()->addMinutes(4),
    ]);

    $it = ttItems('buuta')->first();

    expect($it['viec'])->toStartWith('Sắp đăng')->and($it['viec'])->toContain('@vuonxanh')->and($it['sp'])->toBe('Nano Đồng');
});

test('a running shop sync shows the real got/total progress', function (): void {
    AutoAccount::query()->create(['social_account_id' => $this->sa->id, 'products_sync_request' => 'req-1', 'products_sync_requested_at' => now()->subMinute()]);
    Cache::put('fork-shop-sync-progress:'.$this->sa->id, ['request_id' => 'req-1', 'got' => 12, 'total' => 48], 900);

    $it = ttItems('chuquay')->first();

    expect($it['viec'])->toContain('sản phẩm')
        ->and($it['buoc'])->toBe('Đã lấy 12/48 sản phẩm')
        ->and($it['tien_do'])->toBe(0.25)
        ->and($it['kenh'])->toBe('@vuonxanh')
        ->and($it['xong'])->toBeFalse();
});

test('a failed shop sync shows once as done with an error', function (): void {
    AutoAccount::query()->create([
        'social_account_id' => $this->sa->id, 'products_sync_request' => 'req-2', 'products_sync_requested_at' => now()->subSeconds(30),
        'products_sync_error' => 'not_logged_in',
    ]);

    $it = ttItems('chuquay')->first();

    expect($it['xong'])->toBeTrue()->and($it['ket_qua'])->toBe('loi');
});

test('kho rieng AI in progress exposes step and what it is doing; finished is kept briefly', function (): void {
    AutoVideo::query()->create([
        'hash' => hash('sha256', 'tt2'), 'path' => '/x/tt2.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'vuon-tieu.mp4',
        'source' => AutoVideo::SOURCE_RIENG, 'status' => AutoVideo::NEW,
        'meta' => ['ai' => ['dang' => ['buoc' => 2, 'tong' => 4, 'viec' => 'Xem lại video với model mạnh hơn', 'tu' => now()->subMinute()->toIso8601String(), 'luc' => now()->subSeconds(5)->toIso8601String()]]],
    ]);
    AutoVideo::query()->create([
        'hash' => hash('sha256', 'tt3'), 'path' => '/x/tt3.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'xong.mp4', 'product_name' => 'Nano Đồng',
        'source' => AutoVideo::SOURCE_RIENG, 'status' => AutoVideo::NEW,
        'meta' => ['ai' => ['state' => 'ok', 'chac' => 'cao', 'ly_do' => 'thấy chai nhãn trắng', 'at' => now()->subSeconds(15)->toIso8601String()]],
    ]);

    $items = ttItems('thukho')->keyBy('video');

    expect($items['vuon-tieu.mp4']['buoc'])->toBe('Bước 2/4')
        ->and($items['vuon-tieu.mp4']['dong'])->toBe(['Xem lại video với model mạnh hơn'])
        ->and($items['vuon-tieu.mp4']['xong'])->toBeFalse()
        ->and($items['xong.mp4']['xong'])->toBeTrue()
        ->and($items['xong.mp4']['ket_qua'])->toBe('ok')
        ->and($items['xong.mp4']['sp'])->toBe('Nano Đồng');
});

test('hub passthrough returns items with nguon hub, ignores junk', function (): void {
    Http::fake(['127.0.0.1:8765/api/truc-tiep*' => Http::response(['bay_gio' => 1.0, 'ds' => [
        ['id' => 'bien-kich-1', 'nguon' => 'app', 'vai' => 'bien-kich', 'viec' => 'Đang viết', 'dong' => ['a']],
        ['viec' => 'no id'], 'rac',
    ]])]);

    $items = NhaTrucTiep::hub();

    expect($items)->toHaveCount(1)->and($items[0]['nguon'])->toBe('hub')->and($items[0]['id'])->toBe('bien-kich-1');
});

test('hub 404 (old hub) and timeouts give no hub items and no exception', function (): void {
    Http::fake(['127.0.0.1:8765/api/truc-tiep*' => Http::response('nope', 404)]);
    expect(NhaTrucTiep::hub())->toBe([]);

    Cache::flush();
    Http::fake(['127.0.0.1:8765/api/truc-tiep*' => fn () => throw new ConnectionException('timeout')]);
    expect(NhaTrucTiep::hub())->toBe([]);
});

test('state carries truc_tiep with app items plus hub items', function (): void {
    ttJob($this, 'z1', 'uploading', ['claimed_at' => now()->subMinute(), 'heartbeat_at' => now()]);
    Http::fake([
        '127.0.0.1:8765/api/su-kien*' => Http::response(['ok' => true, 'dang_chay' => false, 'tien_do' => [], 'san_pham' => [], 'su_kien' => [], 'bay_gio' => 1_800_000_000.0]),
        '127.0.0.1:8765/api/truc-tiep*' => Http::response(['bay_gio' => 1.0, 'ds' => [['id' => 'dung-9', 'vai' => 'dung', 'viec' => 'Đang dựng']]]),
    ]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json('truc_tiep');

    expect(collect($j)->pluck('nguon')->all())->toBe(['app', 'hub'])
        ->and(collect($j)->pluck('vai')->all())->toBe(['buuta', 'dung']);
});

test('state still renders with only app items when the hub is down', function (): void {
    ttJob($this, 'z2', 'authorized', ['claimed_at' => now()->subMinute()]);
    Http::fake(['127.0.0.1:8765/*' => fn () => throw new ConnectionException('down')]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();

    expect($j['truc_tiep'])->toHaveCount(1)->and($j['truc_tiep'][0]['viec'])->toContain('đăng');
});

test('missing tables yield no app items instead of an error', function (): void {
    Schema::dropIfExists('fork_chrome_jobs');
    Schema::dropIfExists('fork_auto_accounts');

    expect(fn () => NhaTrucTiep::app(CarbonImmutable::now()))->not->toThrow(Throwable::class);
});

test('recorder stores pct and a readable message, deduplicating repeats', function (): void {
    $j = ttJob($this, 'g1', 'claimed', ['claimed_at' => now()->subMinute(), 'claim_token' => 'ct1', 'nonce' => 'nn1']);
    ChromeLiveProgress::record($j->id, ['phase' => 'transfer', 'msg' => 'part 2/5', 'pct' => 40]);
    ChromeLiveProgress::record($j->id, ['phase' => 'transfer', 'msg' => 'part 2/5', 'pct' => 40]);
    ChromeLiveProgress::record($j->id, ['phase' => 'step', 'msg' => 'sts', 'pct' => null]);

    $p = ChromeLiveProgress::get($j->id);

    expect($p['pct'])->toBe(40.0)
        ->and($p['msg'])->toBe('Đang tải phần 2/5 của video lên TikTok')
        ->and($p['hist'])->toBe(['Đang tải phần 2/5 của video lên TikTok']);
});

test('junk pct and msg are ignored', function (): void {
    $r = fn (array $b) => ChromeLiveProgress::record('j-junk', $b);
    $r(['pct' => 'abc', 'msg' => ['x']]);
    $r(['pct' => 150, 'msg' => str_repeat('a', 200), 'phase' => 'cover']);
    $r(['pct' => -1, 'msg' => null]);
    $r(['pct' => NAN]);
    expect(ChromeLiveProgress::get('j-junk'))->toBeNull();

    $r(['pct' => 30]);
    $r(['pct' => 'zzz', 'phase' => 'cover', 'msg' => 'đã tải ảnh bìa lên TikTok']);
    $p = ChromeLiveProgress::get('j-junk');
    expect($p['pct'])->toBe(30.0)->and($p['msg'])->toBe('Đã tải ảnh bìa lên TikTok');
});

test('live item shows tien_do and the real message from the extension', function (): void {
    $j = ttJob($this, 'g2', 'uploading', ['claimed_at' => now()->subMinute(), 'heartbeat_at' => now()]);
    ChromeLiveProgress::record($j->id, ['phase' => 'start', 'msg' => 'scheduled, 20.0 MB', 'pct' => 0]);
    ChromeLiveProgress::record($j->id, ['phase' => 'transfer', 'msg' => 'part 3/4', 'pct' => 75]);

    $it = ttItems('buuta')->first();

    expect($it['tien_do'])->toBe(0.75)
        ->and($it['dang_go'])->toBe('Đang tải phần 3/4 của video lên TikTok')
        ->and($it['dong'])->toContain('Bắt đầu tải video lên TikTok')
        ->and(count($it['dong']))->toBeLessThanOrEqual(8);
});

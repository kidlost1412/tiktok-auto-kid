<?php

declare(strict_types=1);

use App\Fork\AutoPost\Hub\HubOutboxItem;
use App\Fork\AutoPost\Hub\HubReporter;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Stats\StatsCollector;
use App\Fork\AutoPost\VideoLibrary;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Factory;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;

beforeEach(function (): void {
    Cache::flush();
    $this->hub = str_replace('\\', '/', sys_get_temp_dir()).'/hub-api-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/san-pham/tc01');
    File::ensureDirectoryExists($this->hub.'/ra/2026-11-10');
    file_put_contents($this->hub.'/san-pham/tc01/san-pham.json', json_encode(['ma' => 'tc01', 'ten_goi' => 'Kích rễ', 'ten_ngan' => 'TC01']));
    config([
        'fork.auto.hub_path' => $this->hub, 'fork.auto.settle_seconds' => 0, 'trypost.self_hosted' => true,
        'fork.auto.hub_api.key' => 'k', 'fork.auto.hub_api.url' => 'http://hub.test',
    ]);
    $this->lib = app(VideoLibrary::class);
    $this->lib->syncProducts();
});

afterEach(fn () => File::deleteDirectory($this->hub));

function apiVideo(object $t, string $id, array $over = [], bool $file = true): array
{
    $rel = "ra/2026-11-10/{$id}.mp4";
    $file && file_put_contents($t->hub.'/'.$rel, 'v-'.$id);

    return $over + [
        'id' => $id, 'file' => $rel, 'sha256' => hash('sha256', $id), 'ma' => 'tc01', 'quy_cach' => null,
        'caption' => 'Rễ khoẻ', 'hashtag' => ['#a', '#b'], 'ten_gio' => '', 'anh_bia' => "ra/2026-11-10/{$id}.jpg",
        'goc' => 'bo-re', 'giong' => 'X', 'nhac' => 'N', 'diem' => 6, 'ngay_lam' => '2026-11-10', 'thoi_luong' => 20.3, 'anh_ung' => false,
    ];
}

function fakeUng(array $videos): void
{
    hubFake(['hub.test/trypost/videos*' => Http::response(['videos' => $videos])]);
}

it('nhặt video đã duyệt từ API: mới, cập nhật, bỏ duyệt', function (): void {
    fakeUng([apiVideo($this, 'v1'), apiVideo($this, 'v2', ['ten_gio' => 'KÍCH RỄ'])]);
    $r = $this->lib->ingest();
    $v = AutoVideo::where('hub_id', 'v1')->first();

    expect($r['new'])->toBe(2)
        ->and($v->path)->toBe($this->hub.'/ra/2026-11-10/v1.mp4')
        ->and($v->caption)->toBe('Rễ khoẻ')->and($v->hashtags)->toBe(['#a', '#b'])
        ->and($v->caption_source)->toBe('hub')->and($v->product_name)->toBeNull()
        ->and($v->meta['anh_bia'])->toBe('ra/2026-11-10/v1.jpg')
        ->and(AutoVideo::where('hub_id', 'v2')->value('product_name'))->toBe('KÍCH RỄ');

    fakeUng([apiVideo($this, 'v1', ['caption' => 'Mới'])]);
    $this->lib->ingest();
    $v2 = AutoVideo::where('hub_id', 'v2')->first();
    expect(AutoVideo::where('hub_id', 'v1')->value('caption'))->toBe('Mới')
        ->and($v2->status)->toBe('skipped')->and($v2->skip_reason)->toBe('hub bỏ duyệt');

    fakeUng([apiVideo($this, 'v1'), apiVideo($this, 'v2')]);
    $this->lib->ingest();
    expect(AutoVideo::where('hub_id', 'v2')->value('status'))->toBe('new');
});

it('không nạp lại video đã đăng', function (): void {
    fakeUng([apiVideo($this, 'v1')]);
    $this->lib->ingest();
    AutoVideo::where('hub_id', 'v1')->update(['status' => 'posted']);
    $this->lib->ingest();
    fakeUng([]);
    $this->lib->ingest();

    expect(AutoVideo::count())->toBe(1)->and(AutoVideo::first()->status)->toBe('posted');
});

it('thiếu file mp4 thì chưa cho giữ chỗ, có file rồi thì mở lại', function (): void {
    fakeUng([apiVideo($this, 'v1', [], false)]);
    $this->lib->ingest();
    $v = AutoVideo::where('hub_id', 'v1')->first();
    $acc = SocialAccount::factory()->create();

    expect($this->lib->apiReport['missing'])->toBe(1)->and($v->files_deleted_at)->not->toBeNull()
        ->and($this->lib->reserveNext($acc))->toBeNull();

    fakeUng([apiVideo($this, 'v1')]);
    $this->lib->ingest();
    expect($v->fresh()->files_deleted_at)->toBeNull()->and($this->lib->reserveNext($acc)?->hub_id)->toBe('v1');
});

it('hub tắt: giữ dữ liệu, không đổi gì', function (): void {
    fakeUng([apiVideo($this, 'v1')]);
    $this->lib->ingest();
    hubFake(fn () => throw new ConnectionException('down'));
    $r = $this->lib->ingest();

    expect($r)->toBe(['new' => 0, 'skipped' => 0, 'known' => 0])->and($this->lib->apiReport['state'])->toBe('offline')
        ->and(AutoVideo::where('hub_id', 'v1')->value('status'))->toBe('new');
});

it('đăng xong báo da-dang, không chuyển file; lỗi báo loi', function (): void {
    hubFake(['hub.test/*' => Http::response(['ok' => true])]);
    $acc = SocialAccount::factory()->create(['username' => 'shop1']);
    $path = $this->hub.'/ra/2026-11-10/v1.mp4';
    file_put_contents($path, 'x');
    $v = AutoVideo::create(['hub_id' => 'v1', 'hash' => 'h1', 'path' => $path, 'batch_date' => '2026-11-10', 'file_name' => 'v1.mp4', 'source' => 'hub', 'status' => 'scheduled', 'social_account_id' => $acc->id]);

    $this->lib->markPosted($v, '7300000000000000001');
    expect(is_file($path))->toBeTrue()->and(is_dir($this->hub.'/ra/_da-dang'))->toBeFalse();
    Http::assertSent(fn ($r) => str_ends_with($r->url(), '/videos/v1/da-dang') && $r['kenh'] === '@shop1'
        && $r['tiktok_id'] === '7300000000000000001' && $r['link'] === 'https://www.tiktok.com/@shop1/video/7300000000000000001'
        && $r->hasHeader('X-Key', 'k'));
    expect(HubOutboxItem::count())->toBe(0);

    $v2 = AutoVideo::create(['hub_id' => 'v2', 'hash' => 'h2', 'path' => $path, 'batch_date' => '2026-11-10', 'file_name' => 'v2.mp4', 'source' => 'hub', 'status' => 'scheduled']);
    $this->lib->fail($v2, 'Đăng bài thất bại.');
    Http::assertSent(fn ($r) => str_ends_with($r->url(), '/videos/v2/loi') && $r['ly_do'] === 'Đăng bài thất bại.');
});

it('hub tắt thì lời báo nằm trong outbox và được gửi lại với backoff', function (): void {
    hubFake(fn () => throw new ConnectionException('down'));
    $v = AutoVideo::create(['hub_id' => 'v1', 'hash' => 'h1', 'path' => '/x.mp4', 'batch_date' => '2026-11-10', 'file_name' => 'v1.mp4', 'source' => 'hub', 'status' => 'posted', 'posted_at' => now()]);
    app(HubReporter::class)->posted($v);

    $item = HubOutboxItem::first();
    expect($item->kind)->toBe('da-dang')->and($item->attempts)->toBe(1)->and($item->next_attempt_at)->not->toBeNull();

    hubFake(['hub.test/*' => Http::response(['ok' => true])]);
    Cache::flush();
    expect(app(HubReporter::class)->flush()['sent'])->toBe(0);

    $this->travel(2)->hours();
    expect(app(HubReporter::class)->flush()['sent'])->toBe(1)->and(HubOutboxItem::count())->toBe(0);

    hubFake(['hub.test/*' => Http::response([], 404)]);
    app(HubReporter::class)->failed($v, 'lỗi');
    expect(HubOutboxItem::count())->toBe(0);
});

it('số liệu 24h/72h được gửi lên hub, không ghi so-lieu.csv', function (): void {
    hubFake(['hub.test/*' => Http::response(['ok' => true])]);
    $acc = SocialAccount::factory()->create(['username' => 's']);
    $v = AutoVideo::create(['hub_id' => 'v1', 'hash' => 'h1', 'path' => $this->hub.'/ra/2026-11-10/v1.mp4', 'batch_date' => '2026-11-10', 'file_name' => 'v1.mp4', 'source' => 'hub', 'status' => 'posted', 'social_account_id' => $acc->id, 'posted_at' => now()->subDays(4)]);

    app(HubReporter::class)->stats($v, ['h24' => ['views' => 10, 'likes' => 1, 'comments' => 2, 'shares' => 3], 'h72' => ['views' => 50, 'likes' => 5, 'comments' => 6, 'shares' => 7]]);

    Http::assertSent(fn ($r) => str_ends_with($r->url(), '/so-lieu') && $r['id'] === 'v1' && $r['luot_xem_24h'] === 10
        && $r['luot_xem_72h'] === 50 && $r['thich'] === 5 && $r['kenh'] === '@s');
    app(StatsCollector::class)->collect();
    expect(is_file($this->hub.'/ra/2026-11-10/so-lieu.csv'))->toBeFalse();
});

it('trang Kho hiện trạng thái hub và ẩn lưu giữ', function (): void {
    $account = Account::factory()->create();
    $owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $owner->id]);
    $owner->update(['current_workspace_id' => $ws->id]);

    hubFake(['hub.test/trypost/ping' => Http::response(['ok' => true, 'hub' => 'xuong-video'])]);
    $this->actingAs($owner)->get('/auto/kho')->assertInertia(fn ($p) => $p->where('hub.enabled', true)->where('hub.state', 'ok')->where('hub.url', 'http://hub.test'));

    hubFake(['hub.test/trypost/ping' => Http::response([], 401)]);
    $this->actingAs($owner)->post('/auto/kho/ping')->assertRedirect();
    $this->actingAs($owner)->get('/auto/kho')->assertInertia(fn ($p) => $p->where('hub.state', 'bad_key'));
    $this->actingAs($owner)->patch('/auto/kho/settings', ['retention' => '7'])->assertStatus(409);

    $member = User::factory()->create(['account_id' => $account->id]);
    $this->actingAs($member)->post('/auto/kho/ping')->assertForbidden();
});

/** Http::fake không ghi đè stub cũ, nên mỗi lần dựng lại Factory mới. */
function hubFake(array|Closure $stubs): void
{
    Http::swap(new Factory);
    Http::fake($stubs);
}

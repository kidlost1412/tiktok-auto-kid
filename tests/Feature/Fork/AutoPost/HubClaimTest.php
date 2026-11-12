<?php

declare(strict_types=1);

use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Hub\HubApi;
use App\Fork\AutoPost\Hub\HubFiles;
use App\Fork\AutoPost\Hub\HubOutboxItem;
use App\Fork\AutoPost\Models\AnchorTemplate;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Scheduling\MissingVideoFile;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\AutoPost\VideoLibrary;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Media;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Factory;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;

beforeEach(function (): void {
    Cache::flush();
    Storage::fake();
    $this->hub = sys_get_temp_dir().'/hub-claim-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/san-pham/tc01');
    file_put_contents($this->hub.'/san-pham/tc01/san-pham.json', json_encode(['ma' => 'tc01', 'ten_goi' => 'Kích rễ', 'ten_ngan' => 'TC01']));
    config([
        'fork.auto.hub_path' => $this->hub, 'fork.auto.settle_seconds' => 0, 'trypost.self_hosted' => true,
        'fork.auto.hub_api.key' => 'k', 'fork.auto.hub_api.url' => 'http://hub.test', 'fork.auto.hub_api.may' => 'may-1',
    ]);
    $this->lib = app(VideoLibrary::class);
    $this->lib->syncProducts();
    $this->cacheIds = [];
});

afterEach(function (): void {
    File::deleteDirectory($this->hub);

    foreach ($this->cacheIds as $id) {
        foreach (['mp4', 'jpg'] as $ext) {
            @unlink(storage_path("app/hub-cache/{$id}.{$ext}"));
        }
    }
});

/** Http::fake không ghi đè stub cũ, nên mỗi lần dựng lại Factory mới. */
function claimFake(array|Closure $stubs): void
{
    Http::swap(new Factory);
    Http::fake($stubs);
}

/** Video hub trong DB, mp4 có thật trên đĩa (trừ khi $file = false). */
function claimVideo(object $t, string $id, array $over = [], bool $file = true): AutoVideo
{
    $path = $t->hub.'/'.$id.'.mp4';
    $file && file_put_contents($path, 'bytes-'.$id);

    return AutoVideo::create($over + [
        'hub_id' => $id, 'hash' => hash('sha256', 'bytes-'.$id), 'path' => $path, 'batch_date' => '2026-11-10', 'file_name' => $id.'.mp4',
        'source' => 'hub', 'status' => 'new', 'product_code' => 'tc01', 'caption' => 'Rễ khoẻ', 'hashtags' => ['#a'], 'caption_source' => 'hub',
        'goc' => 'g-'.$id,
    ]);
}

function claimSent(string $suffix): ?array
{
    $found = null;
    Http::assertSent(function ($r) use ($suffix, &$found): bool {
        if (str_ends_with($r->url(), $suffix)) {
            $found = $r->data();

            return true;
        }

        return false;
    });

    return $found;
}

it('giữ chỗ thành công: gửi may, kenh, han = giờ đăng + 1 ngày rồi dùng video', function (): void {
    claimFake(['hub.test/trypost/videos/*/giu' => Http::response(['ok' => true, 'giu_boi' => 'may-1'])]);
    $acc = SocialAccount::factory()->create(['username' => 'shop1']);
    claimVideo($this, 'v1');
    $slot = CarbonImmutable::parse('2026-11-20 03:00:00', 'UTC');

    $v = $this->lib->reserveClaimed($acc, null, $slot);

    expect($v?->hub_id)->toBe('v1')->and($v->status)->toBe('reserved')->and($this->lib->claimBlock)->toBeNull();
    Http::assertSent(fn ($r) => str_ends_with($r->url(), '/trypost/videos/v1/giu') && $r['may'] === 'may-1' && $r['kenh'] === '@shop1'
        && CarbonImmutable::parse($r['han'])->getTimestamp() === $slot->addDay()->getTimestamp() && $r->hasHeader('X-Key', 'k'));
});

it('409 máy khác giữ: bỏ qua video đó, dùng video kế cho cùng giờ', function (): void {
    claimFake([
        'hub.test/trypost/videos/v1/giu' => Http::response(['ok' => false, 'giu_boi' => 'may-2'], 409),
        'hub.test/trypost/videos/v2/giu' => Http::response(['ok' => true, 'giu_boi' => 'may-1']),
    ]);
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1', ['batch_date' => '2026-11-09']);
    claimVideo($this, 'v2');

    $v = $this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDays(2));

    expect($v?->hub_id)->toBe('v2');
    $v1 = AutoVideo::where('hub_id', 'v1')->first();
    expect($v1->status)->toBe('skipped')->and($v1->skip_reason)->toBe('máy khác đã giữ: may-2')->and($v1->social_account_id)->toBeNull();
});

it('409 hub báo đã đăng: video bị bỏ qua, không dùng', function (): void {
    claimFake(['hub.test/trypost/videos/v1/giu' => Http::response(['ok' => false, 'loi' => 'video đã đăng', 'giu_boi' => null], 409)]);
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1');

    expect($this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDay()))->toBeNull()
        ->and($this->lib->claimBlock)->toBeNull();
    $v1 = AutoVideo::where('hub_id', 'v1')->first();
    expect($v1->status)->toBe('skipped')->and($v1->skip_reason)->toBe('hub báo đã đăng');
});

it('hub tắt: không dùng video, về kho, xếp lời nhả vào outbox', function (): void {
    claimFake(fn () => throw new ConnectionException('down'));
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1');

    expect($this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDay()))->toBeNull()
        ->and($this->lib->claimBlock)->toContain('không trả lời');
    $v1 = AutoVideo::where('hub_id', 'v1')->first();
    expect($v1->status)->toBe('new')->and($v1->social_account_id)->toBeNull()
        ->and(HubOutboxItem::where('kind', 'nha')->where('hub_id', 'v1')->count())->toBe(1);
});

it('hub bản cũ 404 không có route /giu: chạy tiếp như một máy, chỉ cảnh báo một lần', function (): void {
    claimFake(['hub.test/trypost/videos/*/giu' => Http::response('Not Found', 404)]);
    Log::spy();
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1', ['batch_date' => '2026-11-09']);
    claimVideo($this, 'v2');

    expect($this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDay())?->hub_id)->toBe('v1')
        ->and($this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDay())?->hub_id)->toBe('v2');
    Log::shouldHaveReceived('warning')->withArgs(fn ($m) => str_contains((string) $m, 'chưa có route giữ chỗ'))->once();
});

it('hub bản cũ 404 không có route /giu, bật require_claim: không đăng, video về kho', function (): void {
    config(['fork.auto.hub_api.require_claim' => true]);
    claimFake(['hub.test/trypost/videos/*/giu' => Http::response('Not Found', 404)]);
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1');

    expect($this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDay()))->toBeNull()
        ->and($this->lib->claimBlock)->toContain('hub chưa có tính năng giữ chỗ');
    $v1 = AutoVideo::where('hub_id', 'v1')->first();
    expect($v1->status)->toBe('new')->and($v1->social_account_id)->toBeNull();
});

it('404 do không có video (JSON ok=false) khác 404 thiếu route: bỏ video, thử video kế', function (): void {
    claimFake([
        'hub.test/trypost/videos/v1/giu' => Http::response(['ok' => false, 'loi' => 'không có video'], 404),
        'hub.test/trypost/videos/v2/giu' => Http::response(['ok' => true]),
    ]);
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1', ['batch_date' => '2026-11-09']);
    claimVideo($this, 'v2');

    expect($this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDay())?->hub_id)->toBe('v2')
        ->and(AutoVideo::where('hub_id', 'v1')->value('status'))->toBe('skipped');
});

it('nhả chỗ khi trả video về kho: gửi /nha qua outbox; giữ chỗ lại xoá lời nhả kẹt', function (): void {
    claimFake(['hub.test/*' => Http::response(['ok' => true, 'giu_boi' => null])]);
    $acc = SocialAccount::factory()->create();
    $v = claimVideo($this, 'v1', ['status' => 'reserved', 'social_account_id' => $acc->id]);

    $this->lib->release($v, 'Tạo bài lỗi');

    expect($v->fresh()->status)->toBe('new');
    Http::assertSent(fn ($r) => str_ends_with($r->url(), '/trypost/videos/v1/nha') && $r['may'] === 'may-1');
    expect(HubOutboxItem::count())->toBe(0);

    // Nhả kẹt (hub tắt) rồi lại giữ chỗ được: lời nhả cũ phải bị bỏ.
    claimFake(fn () => throw new ConnectionException('down'));
    $v->forceFill(['status' => 'reserved'])->save();
    $this->lib->release($v, 'x');
    expect(HubOutboxItem::where('kind', 'nha')->count())->toBe(1);

    claimFake(['hub.test/*' => Http::response(['ok' => true])]);
    $this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDay());
    expect(HubOutboxItem::where('kind', 'nha')->count())->toBe(0);
});

it('video đã giữ chỗ bị đánh dấu lỗi: báo loi (hub tự bỏ chỗ), không cần nha', function (): void {
    claimFake(['hub.test/*' => Http::response(['ok' => true])]);
    $v = claimVideo($this, 'v1', ['status' => 'scheduled']);

    $this->lib->fail($v, 'Đăng lỗi');

    Http::assertSent(fn ($r) => str_ends_with($r->url(), '/videos/v1/loi'));
    Http::assertNotSent(fn ($r) => str_ends_with($r->url(), '/nha'));
});

it('ingest gửi may, lưu giu_boi/url_file/url_anh_bia/kich_thuoc, bỏ video máy khác giữ', function (): void {
    $item = fn (string $id, array $over = []): array => $over + [
        'id' => $id, 'file' => "ra/{$id}.mp4", 'sha256' => hash('sha256', 'bytes-'.$id), 'ma' => 'tc01', 'quy_cach' => null,
        'caption' => 'Rễ khoẻ', 'hashtag' => ['#a'], 'ngay_lam' => '2026-11-10', 'giu_boi' => null,
        'url_file' => "/trypost/videos/{$id}/file", 'url_anh_bia' => "/trypost/videos/{$id}/anh-bia", 'kich_thuoc' => 11,
    ];

    claimFake(['hub.test/trypost/videos*' => Http::response(['videos' => [$item('v1', ['giu_boi' => 'may-1']), $item('v2')]])]);
    $r = $this->lib->ingest();

    expect($r['new'])->toBe(2);
    Http::assertSent(fn ($req) => str_contains($req->url(), 'status=ung') && str_contains($req->url(), 'may=may-1'));
    $v1 = AutoVideo::where('hub_id', 'v1')->first();
    expect($v1->files_deleted_at)->toBeNull()->and($v1->meta['giu_boi'])->toBe('may-1')
        ->and($v1->meta['url_file'])->toBe('/trypost/videos/v1/file')->and($v1->meta['url_anh_bia'])->toBe('/trypost/videos/v1/anh-bia')
        ->and($v1->meta['kich_thuoc'])->toBe(11);

    // v2 giờ bị máy khác giữ: video new của ta bị bỏ qua; v3 máy khác giữ từ đầu thì không nạp.
    claimFake(['hub.test/trypost/videos*' => Http::response(['videos' => [$item('v1', ['giu_boi' => 'may-1']), $item('v2', ['giu_boi' => 'may-2']), $item('v3', ['giu_boi' => 'may-2'])]])]);
    $this->lib->ingest();
    $v2 = AutoVideo::where('hub_id', 'v2')->first();
    expect($v2->status)->toBe('skipped')->and($v2->skip_reason)->toBe('máy khác đã giữ: may-2')
        ->and(AutoVideo::where('hub_id', 'v3')->exists())->toBeFalse()
        ->and($v1->fresh()->status)->toBe('new');

    // Máy kia nhả: nhận lại.
    claimFake(['hub.test/trypost/videos*' => Http::response(['videos' => [$item('v1'), $item('v2')]])]);
    $this->lib->ingest();
    expect($v2->fresh()->status)->toBe('new');
});

it('tải file qua HTTP: sai sha256 bị từ chối, không để lại file', function (): void {
    $this->cacheIds[] = 'dl1';
    claimFake(['hub.test/trypost/videos/dl1/file' => Http::response('noi-dung-khac', 200)]);
    $v = claimVideo($this, 'dl1', ['meta' => ['url_file' => '/trypost/videos/dl1/file', 'kich_thuoc' => 13]], file: false);

    expect(fn () => app(HubFiles::class)->video($v))->toThrow(MissingVideoFile::class, 'sha256');
    expect(is_file(storage_path('app/hub-cache/dl1.mp4')))->toBeFalse()
        ->and(glob(storage_path('app/hub-cache/dl1.mp4*')))->toBe([]);
});

it('tải file qua HTTP: sai kích thước bị từ chối', function (): void {
    $this->cacheIds[] = 'dl2';
    claimFake(['hub.test/trypost/videos/dl2/file' => Http::response('bytes-dl2', 200)]);
    $v = claimVideo($this, 'dl2', ['meta' => ['url_file' => '/trypost/videos/dl2/file', 'kich_thuoc' => 999]], file: false);

    expect(fn () => app(HubFiles::class)->video($v))->toThrow(MissingVideoFile::class, 'kích thước');
});

it('tải file qua HTTP: đúng thì lưu vào hub-cache và dùng lại, không tải lần hai; đĩa luôn được ưu tiên', function (): void {
    $this->cacheIds[] = 'dl3';
    claimFake(['hub.test/trypost/videos/dl3/file' => Http::response('bytes-dl3', 200)]);
    $v = claimVideo($this, 'dl3', ['meta' => ['url_file' => '/trypost/videos/dl3/file', 'kich_thuoc' => 9]], file: false);

    $path = app(HubFiles::class)->video($v);
    expect($path)->toBe(storage_path('app/hub-cache/dl3.mp4'))->and(file_get_contents($path))->toBe('bytes-dl3');
    Http::assertSent(fn ($r) => $r->hasHeader('X-Key', 'k'));

    claimFake(fn () => throw new ConnectionException('down'));
    expect(app(HubFiles::class)->video($v))->toBe($path);

    // Có file trên đĩa thì dùng đĩa.
    file_put_contents($v->path, 'bytes-dl3');
    expect(app(HubFiles::class)->video($v))->toBe($v->path);
});

it('hub tắt khi tải file: lỗi thường (không phải MissingVideoFile) để video về kho thử lại', function (): void {
    claimFake(fn () => throw new ConnectionException('down'));
    $v = claimVideo($this, 'dl4', ['meta' => ['url_file' => '/trypost/videos/dl4/file']], file: false);

    expect(fn () => app(HubFiles::class)->video($v))->toThrow(RuntimeException::class)
        ->and(fn () => app(HubFiles::class)->video($v))->not->toThrow(MissingVideoFile::class);
});

it('không gửi X-Key tới máy chủ khác hub', function (): void {
    claimFake(['*' => Http::response('x')]);
    $v = claimVideo($this, 'dl5', ['meta' => ['url_file' => 'http://evil.test/file']], file: false);

    expect(fn () => app(HubFiles::class)->video($v))->toThrow(RuntimeException::class);
    Http::assertNothingSent();
});

it('cleanup xoá cache video đã đăng quá hạn, giữ video đang chờ', function (): void {
    $this->cacheIds = ['old1', 'wait1'];
    File::ensureDirectoryExists(storage_path('app/hub-cache'));
    file_put_contents(storage_path('app/hub-cache/old1.mp4'), 'x');
    file_put_contents(storage_path('app/hub-cache/wait1.mp4'), 'x');
    claimVideo($this, 'old1', ['status' => 'posted', 'posted_at' => now()->subDays(40)], file: false);
    claimVideo($this, 'wait1', ['status' => 'scheduled'], file: false);

    expect(app(HubFiles::class)->cleanup('30'))->toBeGreaterThanOrEqual(1)
        ->and(is_file(storage_path('app/hub-cache/old1.mp4')))->toBeFalse()
        ->and(is_file(storage_path('app/hub-cache/wait1.mp4')))->toBeTrue();
});

it('cleanupPostedMedia xoá file video của bài đã đăng quá hạn, không đụng bài chưa đăng hay mới đăng', function (): void {
    Queue::fake();
    $user = User::factory()->create();
    $workspace = Workspace::factory()->create(['user_id' => $user->id]);
    $social = SocialAccount::factory()->tiktok()->create(['workspace_id' => $workspace->id]);

    $make = function (string $id, string $kind, ?CarbonImmutable $postedAt) use ($workspace, $social): array {
        $post = Post::factory()->forAccount($social)->{$kind}()->create(['workspace_id' => $workspace->id]);

        if ($kind === 'published') {
            $post->update(['published_at' => $postedAt]);
        }

        $media = Media::factory()->video()->ownedByPost($post)->create();
        claimVideo($this, $id, ['status' => $postedAt ? 'posted' : 'scheduled', 'posted_at' => $postedAt, 'post_id' => $post->id], file: false);

        return [$post, $media];
    };

    [, $old] = $make('m-old', 'published', CarbonImmutable::now()->subDays(40));
    [, $fresh] = $make('m-fresh', 'published', CarbonImmutable::now()->subDays(3));
    [, $waiting] = $make('m-wait', 'scheduled', null);
    [, $futurePosted] = $make('m-fut', 'scheduled', CarbonImmutable::now()->addDays(2));
    AutoVideo::query()->where('hub_id', 'm-fut')->update(['status' => 'posted', 'posted_at' => CarbonImmutable::now()->addDays(2)]);

    $hub = app(HubFiles::class);

    expect($hub->cleanupPostedMedia('vinh_vien'))->toBe(0)
        ->and(Media::query()->count())->toBe(4)
        ->and($hub->cleanupPostedMedia('30'))->toBe(1)
        ->and(Media::query()->whereKey($old->id)->exists())->toBeFalse()
        ->and(Media::query()->whereKey([$fresh->id, $waiting->id, $futurePosted->id])->count())->toBe(3)
        ->and($hub->cleanupPostedMedia('30'))->toBe(0);
});

// ------------------------------------------------------------------ Planner đầu-cuối

function claimPlannerSetup(object $t): SocialAccount
{
    $user = User::factory()->create();
    $workspace = Workspace::factory()->create(['user_id' => $user->id]);
    AutoProduct::query()->where('code', 'tc01')->update(['enabled' => true]);
    $account = SocialAccount::factory()->tiktok()->create(['workspace_id' => $workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh', 'username' => 'shop1']);
    ChromeAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'tiktok_user_id' => '777123']);
    AutoAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'daily_cap' => 1, 'window_start' => 0, 'window_end' => 24]);
    AnchorTemplate::create(['social_account_id' => $account->id, 'product_id' => '1729384756000000001', 'anchors' => json_encode([['id' => '1729384756000000001']]), 'captured_at' => now()]);
    ShopProduct::create(['social_account_id' => $account->id, 'product_id' => '1729384756001234567', 'source' => 'my_shop', 'title' => 'Kích rễ 1L', 'stock_num' => 5, 'synced_at' => now()]);
    ProductLink::create(['social_account_id' => $account->id, 'auto_product_id' => 'tc01', 'shop_product_id' => '1729384756001234567', 'display_name' => 'Kích rễ 1L']);
    $t->now = CarbonImmutable::now('UTC')->addDays(2)->setTime(3, 0);

    return $account;
}

it('Planner: máy khác giữ video đầu thì dùng video sau, tải file qua HTTP rồi tạo bài', function (): void {
    $this->cacheIds = ['p1', 'p2'];
    $account = claimPlannerSetup($this);
    claimFake([
        'hub.test/trypost/videos/p1/giu' => Http::response(['ok' => false, 'giu_boi' => 'may-2'], 409),
        'hub.test/trypost/videos/p2/giu' => Http::response(['ok' => true, 'giu_boi' => 'may-1']),
        'hub.test/trypost/videos/p2/file' => Http::response('bytes-p2', 200),
        '*' => Http::response([]),
    ]);
    claimVideo($this, 'p1', ['batch_date' => '2026-11-09'], file: false);
    claimVideo($this, 'p2', ['meta' => ['url_file' => '/trypost/videos/p2/file', 'kich_thuoc' => 8]], file: false);

    $report = app(Planner::class)->planAll($this->now);

    expect($report[$account->id]['created'])->toBe(1)
        ->and(AutoVideo::where('hub_id', 'p1')->value('status'))->toBe('skipped')
        ->and(AutoVideo::where('hub_id', 'p2')->value('status'))->toBe('scheduled')
        ->and(Post::query()->count())->toBe(1);
});

it('Planner: hub tắt thì không đăng video chưa giữ chỗ được', function (): void {
    $account = claimPlannerSetup($this);
    claimFake(fn () => throw new ConnectionException('down'));
    claimVideo($this, 'p1');

    $report = app(Planner::class)->planAll($this->now);

    expect($report[$account->id]['created'])->toBe(0)->and($report[$account->id]['skipped'])->toContain('giữ chỗ')
        ->and(Post::query()->count())->toBe(0)
        ->and(AutoVideo::where('hub_id', 'p1')->value('status'))->toBe('new');
});

it('Planner: hub cũ không có /giu vẫn đăng như một máy', function (): void {
    $account = claimPlannerSetup($this);
    claimFake(['hub.test/trypost/videos/p1/giu' => Http::response('Not Found', 404), '*' => Http::response([])]);
    claimVideo($this, 'p1');

    $report = app(Planner::class)->planAll($this->now);

    expect($report[$account->id]['created'])->toBe(1)->and(Post::query()->count())->toBe(1);
});

it('Planner: tạo bài lỗi thì trả video về kho và nhả chỗ', function (): void {
    $account = claimPlannerSetup($this);
    claimFake(['hub.test/trypost/videos/p1/giu' => Http::response(['ok' => true]), 'hub.test/trypost/videos/p1/nha' => Http::response(['ok' => true]), '*' => Http::response([])]);
    $v = claimVideo($this, 'p1', ['caption' => str_repeat('a', 2300)]);

    app(Planner::class)->planAll($this->now);

    expect($v->fresh()->status)->toBe('new');
    Http::assertSent(fn ($r) => str_ends_with($r->url(), '/trypost/videos/p1/nha') && $r['may'] === 'may-1');
});

it('HubApi tắt (không có key) thì không gọi hub khi giữ chỗ', function (): void {
    config(['fork.auto.hub_api.key' => '']);
    Http::preventStrayRequests();
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1', ['source' => 'kho']);

    expect(HubApi::enabled())->toBeFalse()
        ->and($this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDay())?->hub_id)->toBe('v1');
});

// ------------------------------------------------------------------ Giữ chỗ bù cho video đã xếp trước đây

it('giữ chỗ thành công đặt dấu hub_claimed_at nên không bị giữ bù lại', function (): void {
    claimFake(['hub.test/trypost/videos/v1/giu' => Http::response(['ok' => true])]);
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1');

    $v = $this->lib->reserveClaimed($acc, null, CarbonImmutable::now()->addDay());
    expect($v->fresh()->meta['hub_claimed_at'])->not->toBeNull();

    claimFake(fn () => throw new RuntimeException('không được gọi hub'));
    expect($this->lib->backfillClaims())->toBe(['claimed' => 0, 'conflicts' => 0, 'pending' => 0]);
});

it('giữ chỗ bù: video reserved/scheduled chưa có dấu được giữ với han = giờ hẹn + 1 ngày', function (): void {
    claimFake(['hub.test/trypost/videos/*/giu' => Http::response(['ok' => true])]);
    $acc = SocialAccount::factory()->create(['username' => 'shop1']);
    $when = CarbonImmutable::parse('2026-11-20 03:00:00', 'UTC');
    claimVideo($this, 'v1', ['status' => 'scheduled', 'social_account_id' => $acc->id, 'scheduled_for' => $when]);
    claimVideo($this, 'v2', ['status' => 'reserved', 'social_account_id' => $acc->id]);
    claimVideo($this, 'v3'); // new: không đụng

    expect($this->lib->backfillClaims())->toBe(['claimed' => 2, 'conflicts' => 0, 'pending' => 0])
        ->and(AutoVideo::where('hub_id', 'v1')->first()->meta['hub_claimed_at'])->not->toBeNull()
        ->and(AutoVideo::where('hub_id', 'v3')->first()->meta)->toBeNull();
    Http::assertSent(fn ($r) => str_ends_with($r->url(), '/v1/giu') && $r['kenh'] === '@shop1'
        && CarbonImmutable::parse($r['han'])->getTimestamp() === $when->addDay()->getTimestamp());
});

it('giữ chỗ bù: hub cũ thiếu route thì không đổi gì, lượt sau thử lại', function (): void {
    claimFake(['hub.test/trypost/videos/*/giu' => Http::response('Not Found', 404)]);
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1', ['status' => 'scheduled', 'social_account_id' => $acc->id, 'scheduled_for' => now()->addDay()]);

    expect($this->lib->backfillClaims()['pending'])->toBe(1);
    expect(AutoVideo::where('hub_id', 'v1')->first()->meta)->toBeNull()->and(AutoVideo::where('hub_id', 'v1')->value('status'))->toBe('scheduled');

    claimFake(['hub.test/trypost/videos/*/giu' => Http::response(['ok' => true])]);
    expect($this->lib->backfillClaims()['claimed'])->toBe(1);
});

it('giữ chỗ bù: máy khác đang giữ thì không huỷ gì, chỉ báo Telegram một lần', function (): void {
    config(['fork.telegram.bot_token' => 't', 'fork.telegram.chat_id' => '1']);
    claimFake([
        'hub.test/trypost/videos/v1/giu' => Http::response(['ok' => false, 'giu_boi' => 'may-2'], 409),
        'api.telegram.org/*' => Http::response(['ok' => true]),
    ]);
    $acc = SocialAccount::factory()->create(['username' => 'shop1']);
    claimVideo($this, 'v1', ['status' => 'scheduled', 'social_account_id' => $acc->id, 'scheduled_for' => now()->addDay()]);

    expect($this->lib->backfillClaims())->toBe(['claimed' => 0, 'conflicts' => 1, 'pending' => 0])
        ->and(AutoVideo::where('hub_id', 'v1')->value('status'))->toBe('scheduled')
        ->and($this->lib->backfillClaims()['conflicts'])->toBe(0);
    Http::assertSent(fn ($r) => str_contains($r->url(), 'api.telegram.org') && str_contains((string) $r['text'], 'v1')
        && str_contains((string) $r['text'], 'may-2') && str_contains((string) $r['text'], '@shop1') && str_contains((string) $r['text'], 'kiểm tra trùng'));
});

it('ingest chạy giữ chỗ bù ở chế độ API', function (): void {
    $acc = SocialAccount::factory()->create();
    claimVideo($this, 'v1', ['status' => 'scheduled', 'social_account_id' => $acc->id, 'scheduled_for' => now()->addDay()]);
    claimFake(['hub.test/trypost/videos/v1/giu' => Http::response(['ok' => true]), 'hub.test/trypost/videos*' => Http::response(['videos' => []])]);

    $this->lib->ingest();

    expect($this->lib->apiReport['backfill']['claimed'])->toBe(1);
});

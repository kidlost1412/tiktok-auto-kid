<?php

declare(strict_types=1);

use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Hub\HubOutboxItem;
use App\Fork\AutoPost\Hub\HubReporter;
use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\KhoStore;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Rieng\RiengBatch;
use App\Fork\AutoPost\Rieng\RiengFolder;
use App\Fork\AutoPost\Rieng\RiengInfo;
use App\Fork\AutoPost\Rieng\RiengMusic;
use App\Fork\AutoPost\Rieng\RiengQueueItem;
use App\Fork\AutoPost\Rieng\RiengReady;
use App\Fork\AutoPost\Rieng\RiengScanner;
use App\Fork\AutoPost\Rieng\RiengThumbs;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\AutoPost\Scheduling\PostBuilder;
use App\Fork\AutoPost\Scheduling\PostEdits;
use App\Fork\AutoPost\Scheduling\Readiness;
use App\Fork\AutoPost\Sidecar;
use App\Fork\AutoPost\Stats\HubFeedback;
use App\Fork\AutoPost\VideoLibrary;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\Account;
use App\Models\Media;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Inertia\Testing\AssertableInertia;
use Symfony\Component\Process\Process;

beforeEach(function (): void {
    Storage::fake();
    Cache::flush();
    $tmp = str_replace('\\', '/', sys_get_temp_dir());
    $this->hub = $tmp.'/rieng-hub-'.bin2hex(random_bytes(4));
    $this->own = $tmp.'/rieng-own-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/ra/2026-11-09');
    File::ensureDirectoryExists($this->own);
    config(['fork.auto.hub_path' => $this->hub, 'fork.auto.settle_seconds' => 0, 'fork.auto.hub_api.key' => '', 'trypost.self_hosted' => true]);

    // Kiểm "ghi xong": giả lập đọc thời lượng (file test chỉ là chữ) và không chờ thật giữa hai lần đo kích thước.
    $this->incomplete = [];
    app()->instance(RiengReady::class, new RiengReady(
        fn (string $p): ?float => in_array(basename($p), $this->incomplete, true) ? null : 5.0,
        fn () => null,
    ));

    $this->user = User::factory()->create();
    $this->workspace = Workspace::factory()->create(['user_id' => $this->user->id]);
    $this->now = CarbonImmutable::now('UTC')->addDays(2)->setTime(3, 0);

    AutoProduct::create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);

    $this->account = function (array $auto = []): SocialAccount {
        $account = SocialAccount::factory()->tiktok()->create([
            'workspace_id' => $this->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh',
        ]);
        ChromeAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'tiktok_user_id' => '777'.random_int(100, 999)]);
        AutoAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'daily_cap' => 20, 'window_start' => 6, 'window_end' => 23, ...$auto]);
        $pid = '17293847560'.random_int(10000000, 99999999);
        ShopProduct::create(['social_account_id' => $account->id, 'product_id' => $pid, 'source' => 'my_shop', 'title' => 'Nano Đồng 1L', 'stock_num' => 5, 'synced_at' => now()]);
        ProductLink::create(['social_account_id' => $account->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => $pid, 'display_name' => 'Nano Đồng 1L']);

        return $account;
    };

    // Tạo video riêng trực tiếp trong DB (file thật trong thư mục tạm).
    $this->rieng = function (string $name, ?string $content = null, array $attrs = []): AutoVideo {
        $path = $this->own.'/'.$name;
        $content ??= 'video-'.$name;
        File::ensureDirectoryExists(dirname($path));
        file_put_contents($path, $content);

        return AutoVideo::create([
            'hash' => hash('sha256', $content), 'path' => $path, 'source' => 'rieng', 'batch_date' => '2026-11-09',
            'file_name' => basename($name), 'status' => 'new', 'meta' => ['folder_id' => 1, 'rel_path' => $name], ...$attrs,
        ]);
    };

    $this->batch = fn (): RiengBatch => app(RiengBatch::class);
    $this->input = fn (SocialAccount $a, array $items, array $extra = []): array => [
        'social_account_id' => $a->id, 'product_code' => 'nano-dong', 'quy_cach' => null,
        'caption' => 'Caption chung', 'hashtags' => '#chung #nano', 'mode' => 'auto',
        'items' => array_map(fn ($i) => is_array($i) ? $i : ['id' => $i->id], $items), ...$extra,
    ];
});

afterEach(function (): void {
    File::deleteDirectory($this->hub);
    File::deleteDirectory($this->own);
});

// ---------------------------------------------------------------- Quét

test('scan picks up mp4 recursively, skips underscore folders, other extensions and keeps file time', function () {
    $folder = RiengFolder::create(['path' => $this->own, 'name' => 'Của tôi']);
    File::ensureDirectoryExists($this->own.'/ngay-1');
    File::ensureDirectoryExists($this->own.'/_da-xong');
    file_put_contents($this->own.'/a.mp4', 'aaa');
    file_put_contents($this->own.'/ngay-1/b.MP4', 'bbb');
    file_put_contents($this->own.'/_da-xong/c.mp4', 'ccc');
    file_put_contents($this->own.'/note.txt', 'x');

    $r = app(RiengScanner::class)->scan();

    expect($r['new'])->toBe(2);
    $videos = AutoVideo::query()->orderBy('file_name')->get();
    expect($videos->pluck('file_name')->all())->toBe(['a.mp4', 'b.MP4'])
        ->and($videos->every(fn ($v) => $v->source === 'rieng' && $v->status === 'new' && $v->product_code === null && $v->caption === null))->toBeTrue()
        ->and($videos[1]->meta['rel_path'])->toBe('ngay-1/b.MP4')
        ->and($videos[1]->meta['folder_id'])->toBe($folder->id);

    // Quét lại không tạo thêm.
    expect(app(RiengScanner::class)->scan()['new'])->toBe(0)->and(AutoVideo::query()->count())->toBe(2);
});

test('scan takes mov, m4v and webm in any letter case, and still ignores other formats', function () {
    RiengFolder::create(['path' => $this->own]);
    foreach (['a.MOV', 'b.m4v', 'c.WebM', 'd.avi', 'e.mkv', 'f.txt'] as $n) {
        file_put_contents($this->own.'/'.$n, 'x-'.$n);
    }

    $r = app(RiengScanner::class)->scan();

    expect($r['new'])->toBe(3)
        ->and(AutoVideo::query()->orderBy('file_name')->pluck('file_name')->all())->toBe(['a.MOV', 'b.m4v', 'c.WebM']);
});

test('an unfinished file waits (no readable duration) and is taken on the very next scan without any long wait', function () {
    RiengFolder::create(['path' => $this->own]);
    file_put_contents($this->own.'/dang-chep.mov', 'part');
    $this->incomplete = ['dang-chep.mov'];

    $started = microtime(true);
    expect(app(RiengScanner::class)->scan())->toMatchArray(['new' => 0, 'waiting' => 1]);
    expect(AutoVideo::query()->count())->toBe(0);

    // Chép xong (đọc được thời lượng): nhận ngay ở lượt quét kế, không phải chờ 20 giây.
    $this->incomplete = [];
    expect(app(RiengScanner::class)->scan())->toMatchArray(['new' => 1, 'waiting' => 0]);
    expect(microtime(true) - $started)->toBeLessThan(5)
        ->and(AutoVideo::query()->firstOrFail()->duration)->toBe(5.0);
});

test('a file whose size changes between the two reads in the same scan waits', function () {
    RiengFolder::create(['path' => $this->own]);
    $file = $this->own.'/lon-len.mp4';
    file_put_contents($file, 'aaaa');

    // Trong lúc "chờ giữa hai lần đo" file được ghi thêm, như đang chép dở.
    app()->instance(RiengReady::class, new RiengReady(fn (): float => 5.0, function () use ($file): void {
        file_put_contents($file, 'bbbb', FILE_APPEND);
    }));
    expect(app(RiengScanner::class)->scan())->toMatchArray(['new' => 0, 'waiting' => 1]);

    // Ngừng ghi: hai lần đo bằng nhau thì nhận.
    app()->instance(RiengReady::class, new RiengReady(fn (): float => 5.0, fn () => null));
    expect(app(RiengScanner::class)->scan())->toMatchArray(['new' => 1, 'waiting' => 0]);

    // File rỗng không bao giờ được nhận.
    file_put_contents($this->own.'/rong.mp4', '');
    expect(app(RiengScanner::class)->scan()['new'])->toBe(0);
});

test('temporary download names are skipped', function () {
    RiengFolder::create(['path' => $this->own]);
    foreach (['video.mp4.crdownload', 'video2.mp4.part', '~$video3.mp4', 'video4.tmp.mp4', '.video5.mp4', 'tot.mp4'] as $n) {
        file_put_contents($this->own.'/'.$n, 'x-'.$n);
    }

    $r = app(RiengScanner::class)->scan();

    expect($r['new'])->toBe(1)->and($r['skipped'])->toBe(5)
        ->and(AutoVideo::query()->pluck('file_name')->all())->toBe(['tot.mp4'])
        ->and(RiengReady::isTempName('a.mp4.crdownload'))->toBeTrue()
        ->and(RiengReady::isTempName('Unconfirmed 123.crdownload'))->toBeTrue()
        ->and(RiengReady::isTempName('a.MOV'))->toBeFalse();
});

test('a duplicate is still taken in, flagged with its original, and the unique hash is kept', function () {
    RiengFolder::create(['path' => $this->own]);
    File::ensureDirectoryExists($this->own.'/copy');
    file_put_contents($this->own.'/x.mp4', 'same-content');
    touch($this->own.'/x.mp4', time() - 100);   // file cũ hơn là bản gốc, dù tên xếp sau
    file_put_contents($this->own.'/copy/x-copy.mp4', 'same-content');
    file_put_contents($this->own.'/hubdup.mp4', 'hub-content');
    $hub = AutoVideo::create(['hash' => hash('sha256', 'hub-content'), 'path' => $this->hub.'/h.mp4', 'source' => 'hub', 'hub_id' => 'h1', 'batch_date' => '2026-11-09', 'file_name' => 'h.mp4', 'status' => 'scheduled', 'scheduled_for' => now()->addDay()]);

    $r = app(RiengScanner::class)->scan();

    // Cả ba file đều vào kho; hai file trùng được đánh dấu.
    expect($r['new'])->toBe(3)->and($r['duplicate'])->toBe(2)
        ->and(AutoVideo::query()->where('source', 'rieng')->count())->toBe(3);

    $orig = AutoVideo::query()->where('file_name', 'x.mp4')->firstOrFail();
    $copy = AutoVideo::query()->where('file_name', 'x-copy.mp4')->firstOrFail();
    $hubCopy = AutoVideo::query()->where('file_name', 'hubdup.mp4')->firstOrFail();

    expect($orig->hash)->toBe(hash('sha256', 'same-content'))->and($orig->meta)->not->toHaveKey('duplicate_of')
        ->and($copy->hash)->not->toBe($orig->hash)->and($copy->content_hash)->toBe(hash('sha256', 'same-content'))
        ->and($copy->meta['duplicate_of'])->toBe($orig->id)
        ->and($hubCopy->meta['duplicate_of'])->toBe($hub->id)
        ->and($hubCopy->content_hash)->toBe($hub->hash);

    // Quét lại: không tạo thêm bản nào.
    expect(app(RiengScanner::class)->scan())->toMatchArray(['new' => 0])->and(AutoVideo::query()->count())->toBe(4);

    // Thêm bản thứ ba của cùng nội dung: vẫn trùng với bản gốc đầu tiên.
    file_put_contents($this->own.'/x3.mp4', 'same-content');
    expect(app(RiengScanner::class)->scan()['duplicate'])->toBe(1)
        ->and(AutoVideo::query()->where('file_name', 'x3.mp4')->firstOrFail()->meta['duplicate_of'])->toBe($orig->id);

    $dups = (new RiengInfo)->duplicates(AutoVideo::query()->where('source', 'rieng')->get());
    expect($dups[$hubCopy->id]['text'])->toStartWith('Trùng video #'.$hub->id.' · Kho Xưởng Video · đã hẹn ')
        ->and($dups[$copy->id]['text'])->toBe('Trùng video #'.$orig->id.' · trùng video riêng khác')
        ->and($dups)->not->toHaveKey($orig->id);

    // Trang hiện cờ trùng, và "Chọn tất cả" biết video nào trùng.
    $this->actingAs(ownerUser())->get('/auto/kho/rieng')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('videos.total', 4)
        ->where('selectable', fn ($rows) => collect($rows)->whereNotNull('duplicate')->count() === 3));

    // Đã đăng thì ghi "đã đăng" kèm liên kết.
    $hub->forceFill(['status' => 'posted', 'posted_at' => now()->subHour(), 'stats' => ['link' => 'https://www.tiktok.com/@a/video/1']])->save();
    $info = (new RiengInfo)->duplicates([$hubCopy->refresh()]);
    expect($info[$hubCopy->id]['text'])->toBe('Trùng video #'.$hub->id.' · Kho Xưởng Video · đã đăng')
        ->and($info[$hubCopy->id]['link'])->toBe('https://www.tiktok.com/@a/video/1');
});

test('quick scan picks up new files but is throttled to one real scan per window', function () {
    $owner = ownerUser();
    RiengFolder::create(['path' => $this->own]);
    file_put_contents($this->own.'/a.mp4', 'aaa');

    $first = $this->actingAs($owner)->postJson('/auto/kho/rieng/quet-nhanh')->assertOk()->json();
    expect($first)->toMatchArray(['ok' => true, 'scanned' => true, 'new' => 1, 'total' => 1]);

    // Gọi dồn dập: không quét thật nữa (file mới chưa được nhặt), nhưng vẫn trả dấu hiệu hiện tại.
    file_put_contents($this->own.'/b.mov', 'bbb');
    $second = $this->actingAs($owner)->postJson('/auto/kho/rieng/quet-nhanh')->assertOk()->json();
    expect($second)->toMatchArray(['scanned' => false, 'new' => 0, 'total' => 1])->and($second['sig'])->toBe($first['sig']);

    // Hết khung throttle: nhặt file mới, dấu hiệu đổi (trang biết cần tải lại).
    Cache::forget('fork-rieng:quick');
    $third = $this->actingAs($owner)->postJson('/auto/kho/rieng/quet-nhanh')->json();
    expect($third)->toMatchArray(['scanned' => true, 'new' => 1, 'total' => 2])->and($third['sig'])->not->toBe($first['sig']);

    // Chỉ chủ app.
    app('auth')->forgetGuards();
    $this->postJson('/auto/kho/rieng/quet-nhanh')->assertStatus(401);
});

test('a scan already running makes a second scan back off instead of overlapping', function () {
    RiengFolder::create(['path' => $this->own]);
    file_put_contents($this->own.'/a.mp4', 'aaa');
    $lock = Cache::lock('fork-rieng:scan', 60);
    expect($lock->get())->toBeTrue();

    expect(app(RiengScanner::class)->scan())->toMatchArray(['busy' => 1, 'new' => 0]);

    $lock->release();
    expect(app(RiengScanner::class)->scan())->toMatchArray(['busy' => 0, 'new' => 1]);
});

test('the waiting basket keeps videos per owner, ignores unusable ones and empties when a video gets scheduled', function () {
    $owner = ownerUser();
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');
    $b = ($this->rieng)('b.mp4');
    $posted = ($this->rieng)('p.mp4', null, ['status' => 'posted']);
    $hubVideo = AutoVideo::create(['hash' => 'hb', 'path' => '/hb', 'source' => 'hub', 'hub_id' => 'hb', 'batch_date' => '2026-11-09', 'file_name' => 'hb.mp4', 'status' => 'new']);

    $r = $this->actingAs($owner)->postJson('/auto/kho/rieng/gio-cho/them', ['ids' => [$a->id, $b->id, $posted->id, $hubVideo->id]])->assertOk()->json();
    expect($r['added'])->toBe(2)->and(collect($r['queue'])->pluck('id')->all())->toBe([$a->id, $b->id]);

    // Thêm lần nữa không nhân đôi; trang trả giỏ trong props (sống qua tải lại).
    $this->actingAs($owner)->postJson('/auto/kho/rieng/gio-cho/them', ['ids' => [$a->id]])->assertOk();
    $this->actingAs($owner)->get('/auto/kho/rieng')->assertInertia(fn (AssertableInertia $p) => $p
        ->has('queue', 2)->where('queue.0.file_name', 'a.mp4'));

    // Bỏ một video khỏi giỏ.
    $r = $this->actingAs($owner)->postJson('/auto/kho/rieng/gio-cho/bo', ['ids' => [$b->id]])->assertOk()->json();
    expect(collect($r['queue'])->pluck('id')->all())->toBe([$a->id]);

    // Giỏ của người khác không lẫn vào.
    expect(RiengQueueItem::idsFor('someone-else'))->toBe([]);

    // Thêm lại b; hẹn giờ a thì a rời giỏ, b ở lại.
    $this->actingAs($owner)->postJson('/auto/kho/rieng/gio-cho/them', ['ids' => [$b->id]])->assertOk();
    $done = ($this->batch)()->commit(($this->input)($account, [$a]), false, $this->now);
    expect($done['done'])->toBe(1);
    $this->actingAs($owner)->get('/auto/kho/rieng')->assertInertia(fn (AssertableInertia $p) => $p
        ->has('queue', 1)->where('queue.0.id', $b->id));

    // Xoá cả giỏ.
    $r = $this->actingAs($owner)->postJson('/auto/kho/rieng/gio-cho/bo', ['all' => true])->assertOk()->json();
    expect($r['queue'])->toBe([])->and(RiengQueueItem::query()->count())->toBe(0);

    // Video bị xoá khỏi app thì dòng trong giỏ tự mất (khoá ngoại).
    $this->actingAs($owner)->postJson('/auto/kho/rieng/gio-cho/them', ['ids' => [$b->id]])->assertOk();
    $b->delete();
    expect(RiengQueueItem::query()->count())->toBe(0);
});

test('a private video detail shows a neutral hint, never the hub product error', function () {
    $owner = ownerUser();
    $v = ($this->rieng)('chua-san-pham.mp4');

    $json = $this->actingAs($owner)->getJson('/auto/kho/video/'.$v->id.'/info')->assertOk()->json();

    expect($json['rieng'])->toBeTrue()
        ->and($json['readiness']['reason'])->toBe('Chưa gắn sản phẩm — chọn khi đăng')
        ->and($json['readiness']['severity'])->toBe('muted')
        ->and(json_encode($json, JSON_UNESCAPED_UNICODE))->not->toContain('đang tắt hoặc không còn trong hub')
        ->and($json['rieng_selectable'])->toBeTrue()->and($json['duplicate'])->toBeNull();

    // Kể cả khi dùng bộ đánh giá chung: không có kiểm tra sản phẩm hub cho video riêng.
    $assessed = app(Readiness::class)->assess(collect([$v]));
    expect($assessed[$v->id]['reason'])->not->toContain('đang tắt');

    // Video hub vẫn bị kiểm sản phẩm hub như cũ.
    $hub = AutoVideo::create(['hash' => 'hh', 'path' => '/hh', 'source' => 'hub', 'hub_id' => 'hh', 'batch_date' => '2026-11-09', 'file_name' => 'hh.mp4', 'status' => 'new']);
    $hubJson = $this->actingAs($owner)->getJson('/auto/kho/video/'.$hub->id.'/info')->json();
    expect($hubJson['readiness']['reason'])->toContain('đang tắt hoặc không còn trong hub');

    // Sau khi hẹn giờ, chi tiết có sản phẩm kèm ảnh.
    $account = ($this->account)();
    ShopProduct::query()->update(['cover_url' => 'https://example.test/a.jpg']);
    ($this->batch)()->commit(($this->input)($account, [$v]), false, $this->now);
    $after = $this->actingAs($owner)->getJson('/auto/kho/video/'.$v->id.'/info')->json();
    expect($after['rieng_product']['name'])->toBe('NanoĐồng')->and($after['rieng_product']['image'])->toStartWith('/auto/anh-san-pham/');
});

test('batch product options carry the product image and the preview carries the duplicate note', function () {
    $account = ($this->account)();
    ShopProduct::query()->update(['cover_url' => 'https://example.test/a.jpg']);

    $options = ($this->batch)()->productOptions($account->id);
    expect($options)->toHaveCount(1)->and($options[0]['image'])->toStartWith('/auto/anh-san-pham/');

    RiengFolder::create(['path' => $this->own]);
    $orig = ($this->rieng)('o.mp4', 'same');
    $dup = ($this->rieng)('d.mp4', 'same', ['hash' => 'derived-hash', 'content_hash' => hash('sha256', 'same'), 'meta' => ['folder_id' => 1, 'duplicate_of' => $orig->id]]);

    $preview = ($this->batch)()->preview(($this->input)($account, [$orig, $dup]), $this->now);
    expect($preview['rows'][0]['duplicate'])->toBeNull()
        ->and($preview['rows'][1]['duplicate'])->toBe('Trùng video #'.$orig->id.' · trùng video riêng khác')
        ->and($preview['rows'][1]['status'])->toBe('ok');
});

test('a mov or webm private video is posted with its own file type and an m4v goes out as mp4', function () {
    $account = ($this->account)();
    $mov = ($this->rieng)('quay-tay.MOV');
    $webm = ($this->rieng)('web.webm');
    $m4v = ($this->rieng)('apple.m4v');

    $done = ($this->batch)()->commit(($this->input)($account, [$mov, $webm, $m4v]), false, $this->now);
    expect($done['done'])->toBe(3);

    $media = Post::query()->get()->mapWithKeys(fn (Post $p) => [$p->meta['fork_auto_video_id'] => Media::query()->where('post_id', $p->id)->firstOrFail()]);

    expect($media[$mov->id]->mime_type)->toBe('video/quicktime')->and($media[$mov->id]->path)->toEndWith('.mov')
        ->and($media[$mov->id]->original_filename)->toBe('quay-tay.MOV')
        ->and($media[$webm->id]->mime_type)->toBe('video/webm')->and($media[$webm->id]->path)->toEndWith('.webm')
        ->and($media[$m4v->id]->mime_type)->toBe('video/mp4')->and($media[$m4v->id]->path)->toEndWith('.mp4')
        ->and($media[$m4v->id]->original_filename)->toBe('apple.mp4');
});

test('the preview stream answers with the right video type for mov and webm', function () {
    $owner = ownerUser();
    RiengFolder::create(['path' => $this->own]);
    $mov = ($this->rieng)('a.mov');
    $webm = ($this->rieng)('b.webm');
    $mp4 = ($this->rieng)('c.mp4');

    expect($this->actingAs($owner)->get('/auto/kho/video/'.$mov->id)->assertOk()->headers->get('Content-Type'))->toBe('video/quicktime')
        ->and($this->actingAs($owner)->get('/auto/kho/video/'.$webm->id)->assertOk()->headers->get('Content-Type'))->toBe('video/webm')
        ->and($this->actingAs($owner)->get('/auto/kho/video/'.$mp4->id)->assertOk()->headers->get('Content-Type'))->toBe('video/mp4');
});

test('a file deleted from a folder that still opens is dropped from the list; on an unplugged drive it is only flagged and comes back', function () {
    RiengFolder::create(['path' => $this->own]);
    file_put_contents($this->own.'/gone.mp4', 'gone');
    file_put_contents($this->own.'/copy.mp4', 'gone');
    touch($this->own.'/gone.mp4', time() - 100);
    app(RiengScanner::class)->scan();
    $video = AutoVideo::query()->where('file_name', 'gone.mp4')->firstOrFail();
    $copy = AutoVideo::query()->where('file_name', 'copy.mp4')->firstOrFail();
    expect(data_get($copy->meta, 'duplicate_of'))->toBe($video->id);

    // Thư mục còn mở được mà file mất: bỏ video khỏi danh sách, bản trùng hết bị gắn cờ trùng.
    unlink($this->own.'/gone.mp4');
    expect(app(RiengScanner::class)->scan()['gone'])->toBe(1)
        ->and(AutoVideo::query()->find($video->id))->toBeNull()
        ->and(data_get($copy->refresh()->meta, 'duplicate_of'))->toBeNull();

    // Ổ rời chưa cắm (thư mục không mở được): chỉ đánh dấu mất file, cắm lại thì có lại.
    $usb = $this->own.'/../usb-'.bin2hex(random_bytes(3));
    File::ensureDirectoryExists($usb);
    RiengFolder::create(['path' => $usb]);
    file_put_contents($usb.'/u.mp4', 'usb');
    app(RiengScanner::class)->scan();
    $u = AutoVideo::query()->where('file_name', 'u.mp4')->firstOrFail();
    File::moveDirectory($usb, $usb.'-x');
    app(RiengScanner::class)->scan();
    expect($u->refresh()->files_deleted_at)->not->toBeNull()->and($u->skip_reason)->toBe(RiengScanner::REASON_FOLDER_GONE);

    File::moveDirectory($usb.'-x', $usb);
    app(RiengScanner::class)->scan();
    expect($u->refresh()->files_deleted_at)->toBeNull();

    // Nút "Bỏ khỏi danh sách" cho thẻ mất file.
    File::moveDirectory($usb, $usb.'-x');
    app(RiengScanner::class)->scan();
    $this->actingAs(ownerUser())->delete("/auto/kho/rieng/video/{$u->id}")->assertRedirect();
    expect(AutoVideo::query()->find($u->id))->toBeNull()->and(is_file($usb.'-x/u.mp4'))->toBeTrue();
    // Video còn file thì không bỏ được bằng nút này.
    $this->actingAs(ownerUser())->delete("/auto/kho/rieng/video/{$copy->id}")->assertNotFound();
});

test('a file moved to another watched folder keeps its video (AI result, product) and shows where it came from', function () {
    $a = RiengFolder::create(['path' => $this->own]);
    $other = $this->own.'/../moi-'.bin2hex(random_bytes(3));
    File::ensureDirectoryExists($other);
    RiengFolder::create(['path' => $other]);
    file_put_contents($this->own.'/clip.mp4', 'clip');
    app(RiengScanner::class)->scan();
    $v = AutoVideo::query()->firstOrFail();
    $v->forceFill(['product_code' => 'nano-dong', 'meta' => ['ai' => ['state' => 'ok']] + (array) $v->meta])->save();

    rename($this->own.'/clip.mp4', $other.'/clip-moi.mp4');
    app(RiengScanner::class)->scan();

    expect(AutoVideo::query()->count())->toBe(1);
    $v->refresh();
    expect(str_replace('\\', '/', $v->path))->toEndWith('/clip-moi.mp4')
        ->and($v->files_deleted_at)->toBeNull()
        ->and($v->product_code)->toBe('nano-dong')
        ->and(data_get($v->meta, 'ai.state'))->toBe('ok')
        ->and(data_get($v->meta, 'duplicate_of'))->toBeNull()
        ->and(data_get($v->meta, 'moved_from.folder_id'))->toBe($a->id)
        ->and(data_get($v->meta, 'moved_from.rel_path'))->toBe('clip.mp4');
});

// ---------------------------------------------------------------- Planner không bao giờ lấy video riêng

test('the normal planner never picks a private video, even with a MIXKIT name and a caption', function () {
    $account = ($this->account)();
    $v = ($this->rieng)('NanoĐồng_x_Y_MIXKIT_1.mp4', null, ['product_code' => 'nano-dong', 'caption' => 'Có caption', 'hashtags' => []]);

    expect(AutoVideo::query()->eligibleNew()->count())->toBe(0);

    app(Planner::class)->planAll($this->now);

    expect($v->refresh()->status)->toBe('new')->and(Post::query()->count())->toBe(0);

    // API hub bật cũng không lấy (có hub_id giả).
    config(['fork.auto.hub_api.key' => 'k']);
    $v->forceFill(['hub_id' => 'weird'])->save();
    expect(AutoVideo::query()->eligibleNew()->count())->toBe(0)
        ->and(app(VideoLibrary::class)->reserveNext(SocialAccount::query()->findOrFail($account->id)))->toBeNull();
});

// ---------------------------------------------------------------- Đăng hàng loạt: tự động

test('auto batch takes the earliest free slots and skips busy ones, never touching existing videos', function () {
    $account = ($this->account)();
    $auto = AutoAccount::query()->findOrFail($account->id);
    $busyAt = collect(app(Planner::class)->slotsFor($auto, $this->now->addMinutes(46), $this->now->addDays(2)))->first();
    // Một bài hub đã hẹn đúng giờ đầu tiên.
    $hub = AutoVideo::create(['hash' => 'hubx', 'path' => '/x', 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'h.mp4', 'status' => 'scheduled', 'social_account_id' => $account->id, 'scheduled_for' => $busyAt]);

    $a = ($this->rieng)('a.mp4');
    $b = ($this->rieng)('b.mp4');
    $input = ($this->input)($account, [$a, $b]);

    $preview = ($this->batch)()->preview($input, $this->now);
    $times = array_map(fn ($r) => CarbonImmutable::parse($r['at'])->getTimestamp(), $preview['rows']);

    expect($preview['ok'])->toBeTrue()->and($preview['left'])->toBe(0)
        ->and($times)->not->toContain($busyAt->getTimestamp())
        ->and($times[0])->toBeGreaterThanOrEqual($this->now->addMinutes(5)->getTimestamp())
        ->and($times[1] - $times[0])->toBeGreaterThanOrEqual(20 * 60);
    // Preview không ghi gì.
    expect(Post::query()->count())->toBe(0)->and($a->refresh()->status)->toBe('new');

    $done = ($this->batch)()->commit($input, false, $this->now);

    expect($done['done'])->toBe(2)->and($done['failed'])->toBe(0);
    $a->refresh();
    expect($a->status)->toBe('scheduled')->and($a->social_account_id)->toBe($account->id)->and($a->product_code)->toBe('nano-dong')
        ->and($a->caption)->toBe('Caption chung')->and($a->hashtags)->toBe(['#chung', '#nano'])
        ->and($a->scheduled_for->getTimestamp())->toBe($times[0])
        ->and($hub->refresh()->status)->toBe('scheduled')->and($hub->scheduled_for->getTimestamp())->toBe($busyAt->getTimestamp());

    $post = Post::query()->findOrFail($a->post_id);
    expect($post->meta['fork_shop_product_id'])->toStartWith('17293847560')
        ->and($post->content)->toBe(HubText::compose('Caption chung', ['#chung', '#nano']));

    // Chạy planner hub sau đó không đụng hay trùng giờ.
    app(Planner::class)->planAll($this->now);
    expect($a->refresh()->status)->toBe('scheduled');
});

test('auto batch keeps the channel daily cap (spilling to later days) and is not limited by ahead days, only by the pending-post limit', function () {
    // Số bài/ngày của kênh luôn giữ: ngày đủ thì sang ngày sau. Số ngày xếp trước là của Xưởng Video, không áp cho video riêng.
    $account = ($this->account)(['daily_cap' => 2, 'window_start' => 6, 'window_end' => 23, 'schedule_ahead_days' => 1]);
    $videos = [($this->rieng)('1.mp4'), ($this->rieng)('2.mp4'), ($this->rieng)('3.mp4'), ($this->rieng)('4.mp4'), ($this->rieng)('5.mp4')];

    $result = ($this->batch)()->commit(($this->input)($account, $videos), false, $this->now);
    expect($result['done'])->toBe(5)->and($result['left'])->toBe(0);
    $perDay = AutoVideo::query()->where('status', 'scheduled')->get()
        ->countBy(fn ($v) => $v->scheduled_for->setTimezone('Asia/Ho_Chi_Minh')->format('Y-m-d'));
    expect($perDay->max())->toBeLessThanOrEqual(2)->and($perDay->count())->toBeGreaterThanOrEqual(3);

    config(['fork.auto.max_future_posts' => 7]);
    $more = [($this->rieng)('6.mp4'), ($this->rieng)('7.mp4'), ($this->rieng)('8.mp4')];
    $result = ($this->batch)()->commit(($this->input)($account, $more), false, $this->now);

    expect($result['done'])->toBe(2)->and($result['left'])->toBe(1)
        ->and(AutoVideo::query()->where('status', 'new')->count())->toBe(1);
});

test('auto times always stay inside the posting window and spill to the next day, 20 minutes apart on the same channel only', function () {
    $account = ($this->account)(['window_start' => 6, 'window_end' => 23]);
    $other = ($this->account)();
    // 22:50 giờ VN: bài đầu 22:55, bài kế (23:15) quá 23:00 => phải sang 06:00 sáng hôm sau, không bao giờ 01:00–02:00.
    $now = CarbonImmutable::parse('2026-11-20 22:50', 'Asia/Ho_Chi_Minh')->utc();
    $sixAm = CarbonImmutable::parse('2026-11-21 06:00', 'Asia/Ho_Chi_Minh');
    // Kênh khác đăng đúng 06:00: không ảnh hưởng. Cùng kênh có bài 06:30: bài kế phải cách >= 20 phút.
    AutoVideo::create(['hash' => 'o1', 'path' => '/o1', 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'o1.mp4', 'status' => 'scheduled', 'social_account_id' => $other->id, 'scheduled_for' => $sixAm->utc()]);
    AutoVideo::create(['hash' => 'm1', 'path' => '/m1', 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'm1.mp4', 'status' => 'scheduled', 'social_account_id' => $account->id, 'scheduled_for' => $sixAm->addMinutes(30)->utc()]);

    $v = [($this->rieng)('1.mp4'), ($this->rieng)('2.mp4'), ($this->rieng)('3.mp4')];
    $r = ($this->batch)()->propose(['social_account_id' => $account->id, 'items' => array_map(fn ($x) => ['id' => $x->id], $v)], $now);
    $local = array_map(fn ($row) => CarbonImmutable::parse($row['at'])->setTimezone('Asia/Ho_Chi_Minh')->format('Y-m-d H:i'), $r['rows']);

    expect($r['ok'])->toBeTrue()->and($r['window'])->toBe('06:00–23:00')
        ->and($local)->toBe(['2026-11-20 22:55', '2026-11-21 06:00', '2026-11-21 06:50']);
});

test('a batch never goes over the channel daily cap: 10 videos with 9 per day put 9 today from now + 5 minutes and 1 tomorrow', function () {
    $account = ($this->account)(['daily_cap' => 9, 'window_start' => 5, 'window_end' => 22]);
    $now = CarbonImmutable::parse('2026-11-20 10:00', 'Asia/Ho_Chi_Minh')->utc();
    $v = array_map(fn ($i) => ($this->rieng)($i.'.mp4'), range(1, 10));

    $r = ($this->batch)()->propose(['social_account_id' => $account->id, 'items' => array_map(fn ($x) => ['id' => $x->id], $v)], $now);
    $local = array_map(fn ($row) => CarbonImmutable::parse($row['at'])->setTimezone('Asia/Ho_Chi_Minh'), $r['rows']);
    $days = collect($local)->countBy(fn ($t) => $t->format('Y-m-d'))->all();

    expect($r['ok'])->toBeTrue()
        ->and($local[0]->format('Y-m-d H:i'))->toBe('2026-11-20 10:05')
        ->and($local[1]->format('H:i'))->toBe('10:25')
        ->and($days)->toBe(['2026-11-20' => 9, '2026-11-21' => 1])
        ->and($local[9]->format('Y-m-d H:i'))->toBe('2026-11-21 05:00');
});

test('posts already on the channel that day count toward the daily cap, and an edited time on a full day is only a warning', function () {
    $account = ($this->account)(['daily_cap' => 3, 'window_start' => 5, 'window_end' => 22]);
    $now = CarbonImmutable::parse('2026-11-20 10:00', 'Asia/Ho_Chi_Minh')->utc();
    $seven = CarbonImmutable::parse('2026-11-20 07:00', 'Asia/Ho_Chi_Minh')->utc();
    // Hôm nay kênh đã có 2 bài (1 đã đăng sáng nay, 1 hẹn chiều).
    AutoVideo::create(['hash' => 'd1', 'path' => '/d1', 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'd1.mp4', 'status' => 'posted', 'social_account_id' => $account->id, 'scheduled_for' => $seven, 'posted_at' => $seven]);
    AutoVideo::create(['hash' => 'd2', 'path' => '/d2', 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'd2.mp4', 'status' => 'scheduled', 'social_account_id' => $account->id, 'scheduled_for' => CarbonImmutable::parse('2026-11-20 15:00', 'Asia/Ho_Chi_Minh')->utc()]);
    $v = [($this->rieng)('1.mp4'), ($this->rieng)('2.mp4'), ($this->rieng)('3.mp4')];

    $r = ($this->batch)()->propose(['social_account_id' => $account->id, 'items' => [
        ['id' => $v[0]->id],
        ['id' => $v[1]->id],
        ['id' => $v[2]->id, 'at' => CarbonImmutable::parse('2026-11-20 18:00', 'Asia/Ho_Chi_Minh')->toIso8601String()],
    ]], $now);
    $at = fn (int $i) => CarbonImmutable::parse($r['rows'][$i]['at'])->setTimezone('Asia/Ho_Chi_Minh')->format('Y-m-d H:i');

    // Giờ sửa tay 18:00 chiếm chỗ thứ 3 của hôm nay => hai video tự xếp sang ngày mai.
    expect($r['rows'][2]['status'])->toBe('ok')->and($at(2))->toBe('2026-11-20 18:00')
        ->and($at(0))->toBe('2026-11-21 05:00')->and($at(1))->toBe('2026-11-21 05:20');

    // Sửa tay vào một ngày đã đủ: chỉ cảnh báo (vẫn hẹn được).
    $r = ($this->batch)()->propose(['social_account_id' => $account->id, 'items' => [
        ['id' => $v[0]->id, 'at' => CarbonImmutable::parse('2026-11-20 12:00', 'Asia/Ho_Chi_Minh')->toIso8601String()],
        ['id' => $v[1]->id, 'at' => CarbonImmutable::parse('2026-11-20 13:00', 'Asia/Ho_Chi_Minh')->toIso8601String()],
    ]], $now);
    expect($r['rows'][0]['status'])->toBe('ok')
        ->and($r['rows'][1]['status'])->toBe('warn')->and(implode(' ', $r['rows'][1]['messages']))->toContain('đã đủ 3 bài');
});

test('posting times always use Vietnam time even when the channel was saved with UTC (fresh install)', function () {
    $account = ($this->account)(['window_start' => 5, 'window_end' => 23]);
    SocialAccount::query()->whereKey($account->id)->update(['timezone' => 'UTC']);
    // 9:00 sáng giờ VN: giờ đầu tiên phải ngay sau 9:00 (không phải 12:00 trưa = 05:00 UTC), không bao giờ 0h–5h sáng.
    $now = CarbonImmutable::parse('2026-11-20 09:00', 'Asia/Ho_Chi_Minh')->utc();
    $v = [($this->rieng)('1.mp4'), ($this->rieng)('2.mp4')];
    $r = ($this->batch)()->propose(['social_account_id' => $account->id, 'items' => array_map(fn ($x) => ['id' => $x->id], $v)], $now);
    $local = array_map(fn ($row) => CarbonImmutable::parse($row['at'])->setTimezone('Asia/Ho_Chi_Minh'), $r['rows']);

    expect($r['window'])->toBe('05:00–23:00')
        ->and($local[0]->format('Y-m-d'))->toBe('2026-11-20')->and($local[0]->hour)->toBe(9)
        ->and($local[1]->hour)->toBeIn([9, 10]);

    // Xưởng cũng vậy: mọi giờ trong ngày nằm trong 05:00–23:00 giờ VN.
    $slots = app(Planner::class)->slotsFor(AutoAccount::query()->findOrFail($account->id), $now, $now->addDay());
    foreach ($slots as $s) {
        $h = $s->setTimezone('Asia/Ho_Chi_Minh');
        expect($h->hour * 60 + $h->minute)->toBeGreaterThanOrEqual(5 * 60)->toBeLessThanOrEqual(23 * 60);
    }
});

test('an edited time is kept and checked; outside the window it is refused, the others are proposed around it', function () {
    $account = ($this->account)(['window_start' => 6, 'window_end' => 23]);
    $now = CarbonImmutable::parse('2026-11-20 09:00', 'Asia/Ho_Chi_Minh')->utc();
    $v = [($this->rieng)('1.mp4'), ($this->rieng)('2.mp4'), ($this->rieng)('3.mp4')];
    $tenAm = CarbonImmutable::parse('2026-11-20 10:00', 'Asia/Ho_Chi_Minh');
    $oneAm = CarbonImmutable::parse('2026-11-21 01:00', 'Asia/Ho_Chi_Minh');

    $r = ($this->batch)()->propose(['social_account_id' => $account->id, 'items' => [
        ['id' => $v[0]->id, 'at' => $tenAm->toIso8601String()],
        ['id' => $v[1]->id],
        ['id' => $v[2]->id, 'at' => $oneAm->toIso8601String()],
    ]], $now);
    $at = fn (int $i) => CarbonImmutable::parse($r['rows'][$i]['at'])->setTimezone('Asia/Ho_Chi_Minh')->format('H:i');

    expect($r['rows'][0]['status'])->toBe('ok')->and($r['rows'][0]['edited'])->toBeTrue()->and($at(0))->toBe('10:00')
        // Đề xuất sớm nhất là 09:05 (bây giờ + 5 phút), cách 10:00 đủ 20 phút => giữ 09:05.
        ->and($r['rows'][1]['status'])->toBe('ok')->and($r['rows'][1]['edited'])->toBeFalse()->and($at(1))->toBe('09:05')
        ->and($r['rows'][2]['status'])->toBe('error')->and(implode(' ', $r['rows'][2]['messages']))->toContain('Ngoài khung giờ');
});

test('the batch requires a cart product available on the channel', function () {
    $account = ($this->account)();
    $v = ($this->rieng)('a.mp4');
    ProductLink::query()->delete();

    $r = ($this->batch)()->preview(($this->input)($account, [$v]), $this->now);
    expect($r['ok'])->toBeFalse()->and($r['error'])->toContain('giỏ hàng');

    $r = ($this->batch)()->preview(($this->input)($account, [$v], ['product_code' => '']), $this->now);
    expect($r['ok'])->toBeFalse();
});

// ---------------------------------------------------------------- Thủ công

test('edited times refuse under the minimum lead and exact duplicates, warn on the same-channel gap and ignore other channels', function () {
    $a1 = ($this->account)();
    $a2 = ($this->account)();
    $t = $this->now->addHours(10)->startOfMinute();
    // Bài của kênh 1 lúc t, bài của kênh 2 lúc t+30 phút.
    AutoVideo::create(['hash' => 'e1', 'path' => '/e1', 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'e1.mp4', 'status' => 'scheduled', 'social_account_id' => $a1->id, 'scheduled_for' => $t]);
    AutoVideo::create(['hash' => 'e2', 'path' => '/e2', 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'e2.mp4', 'status' => 'scheduled', 'social_account_id' => $a2->id, 'scheduled_for' => $t->addMinutes(30)]);

    $v = [($this->rieng)('1.mp4'), ($this->rieng)('2.mp4'), ($this->rieng)('3.mp4'), ($this->rieng)('4.mp4'), ($this->rieng)('5.mp4')];
    $items = [
        ['id' => $v[0]->id, 'at' => $this->now->addMinutes(2)->toIso8601String()],       // quá gần
        ['id' => $v[1]->id, 'at' => $t->toIso8601String()],                               // y hệt bài của kênh
        ['id' => $v[2]->id, 'at' => $t->addMinutes(10)->toIso8601String()],               // trong 20 phút
        ['id' => $v[3]->id, 'at' => $t->addMinutes(30)->addSeconds(30)->toIso8601String()], // sát kênh khác
        ['id' => $v[4]->id, 'at' => $t->addHours(3)->toIso8601String()],                  // sạch
    ];

    $r = ($this->batch)()->preview(($this->input)($a1, $items, ['mode' => 'manual']), $this->now);
    $rows = $r['rows'];

    expect($rows[0]['status'])->toBe('error')->and($rows[0]['messages'][0])->toContain('5 phút')
        ->and($rows[1]['status'])->toBe('error')->and($rows[1]['messages'][0])->toContain('đúng giờ')
        ->and($rows[2]['status'])->toBe('warn')->and(implode(' ', $rows[2]['messages']))->toContain('Gần bài')
        // Sát giờ kênh khác: không sao (chỉ tránh bài cùng kênh).
        ->and($rows[3]['status'])->toBe('ok')->and($rows[3]['messages'])->toBe([])
        ->and($rows[4]['status'])->toBe('ok')->and($r['needs_confirm'])->toBeTrue();

    // Chưa xác nhận: không ghi gì.
    $no = ($this->batch)()->commit(($this->input)($a1, $items, ['mode' => 'manual']), false, $this->now);
    expect($no['needs_confirm'])->toBeTrue()->and(Post::query()->count())->toBe(0);

    // "Vẫn hẹn": các dòng warn/ok được hẹn, dòng lỗi cứng thì không.
    $yes = ($this->batch)()->commit(($this->input)($a1, $items, ['mode' => 'manual']), true, $this->now);
    expect($yes['done'])->toBe(3)
        ->and($v[0]->refresh()->status)->toBe('new')->and($v[1]->refresh()->status)->toBe('new')
        ->and($v[2]->refresh()->status)->toBe('scheduled')->and($v[4]->refresh()->status)->toBe('scheduled');
});

test('edited duplicates inside the same batch are refused', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');
    $b = ($this->rieng)('b.mp4');
    $t = $this->now->addHours(5)->startOfMinute()->toIso8601String();

    $r = ($this->batch)()->preview(($this->input)($account, [['id' => $a->id, 'at' => $t], ['id' => $b->id, 'at' => $t]], ['mode' => 'manual']), $this->now);

    expect($r['rows'][0]['status'])->toBe('ok')->and($r['rows'][1]['status'])->toBe('error');
});

test('a per-video caption override is used and the 2200 limit is enforced per row', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');
    $b = ($this->rieng)('b.mp4');

    $r = ($this->batch)()->preview(($this->input)($account, [['id' => $a->id, 'caption' => 'Riêng cho a'], ['id' => $b->id, 'caption' => str_repeat('x', 2300)]]), $this->now);

    expect($r['rows'][0]['caption'])->toBe('Riêng cho a')->and($r['rows'][0]['status'])->toBe('ok')
        ->and($r['rows'][1]['status'])->toBe('error')->and($r['rows'][1]['messages'][0])->toContain('2200');
});

test('caption and hashtags are optional: an empty caption schedules fine and the post may be empty', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');
    $input = ($this->input)($account, [$a], ['caption' => '', 'hashtags' => '']);

    $preview = ($this->batch)()->preview($input, $this->now);
    expect($preview['ok'])->toBeTrue()->and($preview['rows'][0]['status'])->toBe('ok')->and($preview['rows'][0]['messages'])->toBe([]);

    $done = ($this->batch)()->commit($input, false, $this->now);
    expect($done['done'])->toBe(1)->and($done['failed'])->toBe(0);

    $post = Post::query()->findOrFail($a->refresh()->post_id);
    expect($post->content)->toBe('')->and($post->meta['fork_caption_optional'])->toBeTrue()->and($a->caption)->toBe('');

    // Chrome nhận bài không caption và gửi chuỗi rỗng (không phải null).
    $account->refresh();
    $job = app(ChromeJobs::class)->queueForPost($post, 'scheduled');
    expect($job->caption)->toBe('');
});

// ---------------------------------------------------------------- Lỗi khi dựng bài

test('a build failure releases the video, restores its fields and reports the error', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');
    $b = ($this->rieng)('b.mp4');

    // PostBuilder từ chối vì liên kết giỏ hàng không còn tên hợp lệ (qua được bước xem trước, hỏng lúc dựng bài).
    ProductLink::query()->update(['display_name' => ' ']);

    $r = ($this->batch)()->commit(($this->input)($account, [$a, $b]), false, $this->now);

    expect($r['failed'])->toBe(2)->and($r['done'])->toBe(0)->and($r['rows'][0]['error'])->toContain('Tạo bài lỗi');
    $a->refresh();
    expect($a->status)->toBe('new')->and($a->social_account_id)->toBeNull()->and($a->product_code)->toBeNull()->and($a->caption)->toBeNull()
        ->and($b->refresh()->status)->toBe('new')->and(Post::query()->count())->toBe(0);
});

test('a video whose file vanished is refused and never reserved', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');
    unlink($a->path);

    // Preview đã chặn (không còn file).
    $r = ($this->batch)()->preview(($this->input)($account, [$a]), $this->now);
    expect($r['rows'][0]['status'])->toBe('error');

    $r = ($this->batch)()->commit(($this->input)($account, [$a]), false, $this->now);
    expect($r['done'])->toBe(0)->and($a->refresh()->status)->toBe('new')->and(Post::query()->count())->toBe(0);
});

test('a failed private video can go through the batch flow again via retry', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4', null, ['status' => 'failed', 'skip_reason' => 'lỗi', 'social_account_id' => $account->id]);

    $r = ($this->batch)()->commit(($this->input)($account, [$a]), false, $this->now);

    expect($r['done'])->toBe(1)->and($a->refresh()->status)->toBe('scheduled');
});

// ---------------------------------------------------------------- Không bao giờ đụng file của chủ

test('marking a private video posted never moves or deletes its file, with or without the hub API', function () {
    $account = ($this->account)();
    $v = ($this->rieng)('keep/me.mp4', null, ['status' => 'scheduled', 'social_account_id' => $account->id, 'batch_date' => '2026-11-09']);
    config(['fork.auto.retention_default' => 'xoa_ngay']);

    foreach (['', 'key'] as $key) {
        config(['fork.auto.hub_api.key' => $key]);
        app(VideoLibrary::class)->markPosted($v, '123');
        $v->forceFill(['status' => 'scheduled'])->save();
    }

    expect(is_file($v->refresh()->path))->toBeTrue()->and($v->path)->toBe($this->own.'/keep/me.mp4');
    app(KhoStore::class)->archive($v);
    expect(is_file($v->path))->toBeTrue();

    // Dọn dẹp hằng ngày (da-dang + cache hub).
    File::ensureDirectoryExists($this->hub.'/da-dang/2020-01-01');
    $r = app(KhoStore::class)->cleanup();
    expect(is_file($v->path))->toBeTrue()->and($r['deleted'])->toBe(0);
    $this->artisan('fork:auto-cleanup')->assertSuccessful();
    expect(is_file($v->path))->toBeTrue();
    expect(is_dir($this->hub.'/ra/_da-dang'))->toBeFalse();
});

test('hub outbox reports and so-lieu writing skip private videos', function () {
    config(['fork.auto.hub_api.key' => 'k']);
    $account = ($this->account)();
    $v = ($this->rieng)('a.mp4', null, ['status' => 'posted', 'posted_at' => now()->subDay(), 'social_account_id' => $account->id, 'batch_date' => '2026-11-09', 'hub_id' => 'oops']);
    Http::fake();

    $reporter = app(HubReporter::class);
    $reporter->posted($v);
    $reporter->failed($v, 'x');
    $reporter->stats($v, ['h24' => ['views' => 5]]);
    expect(HubOutboxItem::query()->count())->toBe(0);

    app(HubFeedback::class)->sync(['2026-11-09'], CarbonImmutable::now());
    expect(is_file($this->hub.'/ra/2026-11-09/so-lieu.csv'))->toBeFalse()->and(is_dir($this->hub.'/ra/2026-11-09/_kem'))->toBeFalse();
});

test('removing a folder keeps the files and drops only the unposted rows', function () {
    $folder = RiengFolder::create(['path' => $this->own]);
    file_put_contents($this->own.'/a.mp4', 'a');
    app(RiengScanner::class)->scan();
    $posted = ($this->rieng)('p.mp4', null, ['status' => 'posted', 'meta' => ['folder_id' => $folder->id]]);

    $owner = ownerUser();
    $this->actingAs($owner)->delete('/auto/kho/rieng/thu-muc/'.$folder->id)->assertRedirect();

    expect(is_file($this->own.'/a.mp4'))->toBeTrue()->and(is_file($posted->path))->toBeTrue()
        ->and(RiengFolder::query()->count())->toBe(0)
        ->and(AutoVideo::query()->pluck('file_name')->all())->toBe(['p.mp4']);
});

function ownerUser(): User
{
    $account = Account::factory()->create();
    $owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $owner->id]);
    $owner->update(['current_workspace_id' => $ws->id]);

    return $owner;
}

// ---------------------------------------------------------------- Trang

test('folder add validates the path and the page lists private videos only on the rieng page', function () {
    $owner = ownerUser();

    $this->actingAs($owner)->post('/auto/kho/rieng/thu-muc', ['path' => $this->own.'/khong-co'])
        ->assertSessionHas('flash.error');
    $this->actingAs($owner)->post('/auto/kho/rieng/thu-muc', ['path' => $this->hub])
        ->assertSessionHas('flash.error');
    expect(RiengFolder::query()->count())->toBe(0);

    file_put_contents($this->own.'/a.mp4', 'aaa');
    $this->actingAs($owner)->post('/auto/kho/rieng/thu-muc', ['path' => '"'.str_replace('/', '\\', $this->own).'"', 'name' => 'Video nhà'])
        ->assertSessionHas('flash.success');
    expect(RiengFolder::query()->count())->toBe(1)->and(AutoVideo::query()->count())->toBe(1);
    // Thêm lần nữa: báo trùng.
    $this->actingAs($owner)->post('/auto/kho/rieng/thu-muc', ['path' => $this->own])->assertSessionHas('flash.error');

    $this->actingAs($owner)->get('/auto/kho/rieng')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/KhoRieng')
        ->where('folders.0.name', 'Video nhà')->where('folders.0.count', 1)
        ->where('videos.total', 1)->has('days', 1)
        ->where('filters.day', ''));

    // Kho hub không hiện video riêng.
    $this->actingAs($owner)->get('/auto/kho?tab=all')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->where('videos.total', 0)->where('counts.all', 0));
});

test('the hub Kho page has an all-days option and filters by day', function () {
    $owner = ownerUser();
    AutoVideo::create(['hash' => 'd1', 'path' => '/d1', 'source' => 'hub', 'hub_id' => 'd1', 'batch_date' => '2026-11-01', 'file_name' => 'd1.mp4', 'status' => 'new']);
    AutoVideo::create(['hash' => 'd2', 'path' => '/d2', 'source' => 'hub', 'hub_id' => 'd2', 'batch_date' => '2026-11-02', 'file_name' => 'd2.mp4', 'status' => 'new']);

    $this->actingAs($owner)->get('/auto/kho')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('videos.total', 2)->where('days', ['2026-11-02', '2026-11-01'])->where('filters.day', ''));
    $this->actingAs($owner)->get('/auto/kho?day=2026-11-01')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('videos.total', 1)->where('filters.day', '2026-11-01'));
});

// ---------------------------------------------------------------- _kem

test('sidecars are read from _kem first and fall back to the old place', function () {
    $dir = $this->hub.'/ra/2026-11-09';
    $mp4 = $dir.'/clip.mp4';
    file_put_contents($mp4, 'v');

    // Chỗ cũ.
    file_put_contents($dir.'/clip.txt', "Caption cũ\n#cu");
    expect(HubText::resolve($mp4)['caption'])->toBe('Caption cũ');

    // _kem thắng khi có cả hai.
    File::ensureDirectoryExists($dir.'/_kem');
    file_put_contents($dir.'/_kem/clip.txt', "Caption mới\n#moi");
    expect(HubText::resolve($mp4)['caption'])->toBe('Caption mới')->and(Sidecar::forVideo($mp4, 'txt'))->toBe($dir.'/_kem/clip.txt');

    // CSV.
    unlink($dir.'/clip.txt');
    unlink($dir.'/_kem/clip.txt');
    file_put_contents($dir.'/_kem/'.HubText::CSV_NAME, "file,caption,hashtag\nclip.mp4,Từ csv kem,#k\n");
    expect(HubText::resolve($mp4)['caption'])->toBe('Từ csv kem');
    unlink($dir.'/_kem/'.HubText::CSV_NAME);
    file_put_contents($dir.'/'.HubText::CSV_NAME, "file,caption,hashtag\nclip.mp4,Từ csv cũ,#c\n");
    expect(HubText::resolve($mp4)['caption'])->toBe('Từ csv cũ');
});

test('legacy ingest reads bang-ghi.csv from _kem', function () {
    config(['fork.auto.legacy_ra' => true]);
    AutoProduct::query()->update(['short_name' => 'NanoĐồng']);
    $dir = $this->hub.'/ra/2026-11-09';
    File::ensureDirectoryExists($dir.'/_kem');
    $name = 'NanoĐồng_goc1_Giong_MIXKIT_1.mp4';
    file_put_contents($dir.'/'.$name, 'legacy-video');
    file_put_contents($dir.'/_kem/bang-ghi.csv', "file,goc,thoi_luong,loi\n{$name},gocA,12.5,Lời thoại\n");
    file_put_contents($dir.'/_kem/clip.txt', '');
    file_put_contents($dir.'/_kem/'.pathinfo($name, PATHINFO_FILENAME).'.txt', "Cap từ kem\n#a");

    app(VideoLibrary::class)->ingest();

    $v = AutoVideo::query()->where('file_name', $name)->firstOrFail();
    expect($v->goc)->toBe('gocA')->and($v->duration)->toBe(12.5)->and($v->caption)->toBe('Cap từ kem');
});

// ---------------------------------------------------------------- Chọn thư mục (qua launcher)

test('pick folder opens the dialog in the background and the page polls for the result', function () {
    $owner = ownerUser();
    $tokenFile = sys_get_temp_dir().'/rieng-token-'.bin2hex(random_bytes(4));
    file_put_contents($tokenFile, 'tok-test');
    config(['fork-update.token_file' => $tokenFile, 'fork-update.launcher_port' => 8009]);

    Http::fake([
        '127.0.0.1:8009/api/chon-thu-muc/mo' => Http::sequence()
            ->push(['ok' => true, 'id' => 'abc-1'])
            ->push(['ok' => false, 'error' => 'đang mở hộp chọn'], 409),
        '127.0.0.1:8009/api/chon-thu-muc/ket-qua' => Http::sequence()
            ->push(['xong' => false])
            ->push(['xong' => true, 'ok' => true, 'duong_dan' => 'D:\Video\Cua-toi'])
            ->push(['xong' => true, 'ok' => false, 'huy' => true])
            ->push(['ok' => false, 'xong' => true, 'error' => 'Không tìm thấy'], 404),
    ]);

    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc')
        ->assertOk()->assertExactJson(['ok' => true, 'pending' => true, 'id' => 'abc-1']);
    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc')
        ->assertStatus(422)->assertJsonPath('ok', false);

    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc/ket-qua', ['id' => 'abc-1'])
        ->assertOk()->assertExactJson(['pending' => true]);
    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc/ket-qua', ['id' => 'abc-1'])
        ->assertOk()->assertJson(['ok' => true, 'path' => 'D:\Video\Cua-toi', 'name' => 'Cua-toi']);
    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc/ket-qua', ['id' => 'abc-1'])
        ->assertOk()->assertJson(['ok' => false, 'cancelled' => true]);
    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc/ket-qua', ['id' => 'abc-1'])
        ->assertStatus(422)->assertJsonPath('error', 'Không mở được hộp chọn thư mục, hãy dán đường dẫn.');

    // id lạ bị chặn trước khi tới launcher
    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc/ket-qua', ['id' => '../x'])->assertStatus(422);
    Http::assertSent(fn ($r) => $r->hasHeader('X-TTA-Token', 'tok-test'));
    Http::assertNotSent(fn ($r) => str_contains($r->url(), '../x'));

    @unlink($tokenFile);
});

test('pick folder falls back to the blocking call when the launcher is older', function () {
    $owner = ownerUser();
    $tokenFile = sys_get_temp_dir().'/rieng-token-'.bin2hex(random_bytes(4));
    file_put_contents($tokenFile, 'tok-test');
    config(['fork-update.token_file' => $tokenFile, 'fork-update.launcher_port' => 8009]);

    Http::fake(['127.0.0.1:8009/api/chon-thu-muc/mo' => Http::response('404 page not found', 404), '127.0.0.1:8009/api/chon-thu-muc' => Http::sequence()
        ->push(['ok' => true, 'duong_dan' => 'D:\Video\Video-cua-toi'])
        ->push(['ok' => false, 'huy' => true])
        ->push(['ok' => false, 'error' => 'đang mở hộp chọn'], 409)]);

    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc')
        ->assertOk()->assertJson(['ok' => true, 'path' => 'D:\Video\Video-cua-toi', 'name' => 'Video-cua-toi']);
    Http::assertSent(fn ($r) => $r->hasHeader('X-TTA-Token', 'tok-test'));

    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc')
        ->assertOk()->assertJson(['ok' => false, 'cancelled' => true]);

    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc')
        ->assertStatus(422)->assertJson(['ok' => false, 'error' => 'Không mở được hộp chọn thư mục, hãy dán đường dẫn.']);

    Http::fake(fn () => throw new RuntimeException('down'));
    $this->actingAs($owner)->postJson('/auto/kho/rieng/chon-thu-muc')
        ->assertStatus(422)->assertJsonPath('error', 'Không mở được hộp chọn thư mục, hãy dán đường dẫn.');

    @unlink($tokenFile);
});

test('pick folder is owner only', function () {
    $this->postJson('/auto/kho/rieng/chon-thu-muc')->assertStatus(401);
    $this->postJson('/auto/kho/rieng/chon-thu-muc/ket-qua', ['id' => 'abc-1'])->assertStatus(401);
});

// ---------------------------------------------------------------- Ghép nhạc hàng loạt

test('music settings are saved per folder; turning it on needs a music folder with tracks', function () {
    $owner = ownerUser();
    $folder = RiengFolder::create(['path' => $this->own]);
    $music = $this->own.'/_nhac';
    File::ensureDirectoryExists($music.'/them');
    file_put_contents($music.'/a.mp3', 'x');
    file_put_contents($music.'/them/b.M4A', 'x');
    file_put_contents($music.'/ghi-chu.txt', 'x');
    $url = '/auto/kho/rieng/thu-muc/'.$folder->id.'/nhac';

    $this->actingAs($owner)->patchJson($url, ['enabled' => true, 'dir' => $this->own.'/rong', 'mode' => 'mix', 'gain_db' => -12])->assertStatus(422);
    $this->actingAs($owner)->patchJson($url, ['enabled' => true, 'dir' => $music, 'mode' => 'mix', 'gain_db' => -50])->assertStatus(422);
    $this->actingAs($owner)->patchJson($url, ['enabled' => true, 'dir' => $music, 'mode' => 'replace', 'gain_db' => -18])
        ->assertOk()->assertJson(['ok' => true, 'tracks' => 2, 'music' => ['enabled' => true, 'mode' => 'replace', 'gain_db' => -18]]);
    $this->actingAs($owner)->postJson('/auto/kho/rieng/nhac/dem', ['dir' => $music])->assertOk()->assertJson(['tracks' => 2]);

    expect(RiengMusic::settings($folder->fresh()))->toBe(['enabled' => true, 'dir' => $music, 'mode' => 'replace', 'gain_db' => -18])
        ->and(RiengMusic::settings(RiengFolder::create(['path' => $this->own.'/khac']))['enabled'])->toBeFalse();

    // tắt thì không cần thư mục nhạc
    $this->actingAs($owner)->patchJson($url, ['enabled' => false, 'dir' => null, 'mode' => 'mix', 'gain_db' => -12])->assertOk();
    expect(RiengMusic::settings($folder->fresh())['enabled'])->toBeFalse();
});

test('random track pick avoids the tracks used just before', function () {
    $m = app(RiengMusic::class);
    $tracks = ['a.mp3', 'b.mp3', 'c.mp3', 'd.mp3', 'e.mp3', 'f.mp3', 'g.mp3'];
    $seen = [];

    for ($i = 0; $i < 40; $i++) {
        $t = $m->pick(9, $tracks);
        expect(array_slice($seen, -5))->not->toContain($t);
        $seen[] = $t;
    }

    expect($m->pick(9, ['only.mp3']))->toBe('only.mp3')->and($m->pick(9, []))->toBeNull();
});

test('posting a private video from a music folder uploads a new file with the music, never touching the original', function () {
    $ffmpeg = app(RiengThumbs::class)->ffmpegPath();

    if ($ffmpeg === null) {
        $this->markTestSkipped('ffmpeg not installed');
    }

    $run = function (array $args) use ($ffmpeg): string {
        $p = new Process([$ffmpeg, '-hide_banner', ...$args]);
        $p->setTimeout(60);
        $p->run();

        return $p->getErrorOutput();
    };
    $music = $this->own.'/_nhac';
    File::ensureDirectoryExists($music);
    $run(['-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=880:duration=20', $music.'/nhac-1.mp3']);
    $folder = RiengFolder::create(['path' => $this->own, 'music' => ['enabled' => true, 'dir' => $music, 'mode' => 'mix', 'gain_db' => -12]]);
    $quiet = RiengFolder::create(['path' => $this->own.'/q', 'music' => ['enabled' => true, 'dir' => $music, 'mode' => 'replace', 'gain_db' => 0]]);

    $make = function (string $name, int $folderId, bool $withAudio) use ($run): AutoVideo {
        $v = ($this->rieng)($name, null, ['meta' => ['folder_id' => $folderId, 'rel_path' => $name]]);
        $run(['-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=25:duration=4',
            ...($withAudio ? ['-f', 'lavfi', '-i', 'sine=frequency=440:duration=4'] : []),
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', ...($withAudio ? ['-c:a', 'aac'] : []), '-shortest', $v->path]);

        return $v;
    };
    $mixed = $make('co-tieng.mp4', $folder->id, true);
    $silent = $make('khong-tieng.MOV', $folder->id, false);
    $replaced = $make('thay.mp4', $quiet->id, true);
    $before = md5_file($mixed->path);

    $done = ($this->batch)()->commit(($this->input)(($this->account)(), [$mixed, $silent, $replaced]), false, $this->now);
    expect($done['done'])->toBe(3);

    $postOf = fn (AutoVideo $v): Post => Post::query()->get()->first(fn (Post $p) => $p->meta['fork_auto_video_id'] === $v->id);

    foreach ([$mixed, $silent, $replaced] as $v) {
        $media = Media::query()->where('post_id', $postOf($v)->id)->firstOrFail();
        $info = $run(['-i', Storage::path($media->path)]);

        expect($postOf($v)->meta['fork_music'])->toBe('nhac-1.mp3')
            ->and($info)->toMatch('/Audio: aac/')->toMatch('/Video: h264/')->toMatch('/Duration: 00:00:0[34]/')
            ->and($media->path)->toEndWith('.mp4')->and($media->mime_type)->toBe('video/mp4');
    }

    expect(md5_file($mixed->path))->toBe($before)
        ->and($postOf($replaced)->meta['fork_music_mode'])->toBe('replace')
        ->and(Media::query()->where('post_id', $postOf($silent)->id)->value('original_filename'))->toBe('khong-tieng.mp4')
        ->and(glob(storage_path('app/rieng-music/*')) ?: [])->toBe([]);
});

test('a folder with music on but an empty music folder never posts the video without music', function () {
    $folder = RiengFolder::create(['path' => $this->own, 'music' => ['enabled' => true, 'dir' => $this->own.'/khong-co', 'mode' => 'mix', 'gain_db' => -12]]);
    $v = ($this->rieng)('a.mp4', null, ['meta' => ['folder_id' => $folder->id, 'rel_path' => 'a.mp4']]);

    $done = ($this->batch)()->commit(($this->input)(($this->account)(), [$v]), false, $this->now);

    expect($done['done'])->toBe(0)->and(Post::query()->count())->toBe(0)->and($v->fresh()->status)->toBe('new');
});

// ---------------------------------------------------------------- Sản phẩm theo từng video khi đăng hàng loạt

test('batch "per video" attaches each video its own AI or owner product and never a shared one', function () {
    $account = ($this->account)();
    AutoProduct::create(['code' => 'tc01', 'name' => 'Kích rễ TC01', 'short_name' => 'TC01', 'facts' => [], 'enabled' => true]);
    $pid = '17293847561'.random_int(10000000, 99999999);
    ShopProduct::create(['social_account_id' => $account->id, 'product_id' => $pid, 'source' => 'my_shop', 'title' => 'TC01', 'stock_num' => 5, 'synced_at' => now()]);
    ProductLink::create(['social_account_id' => $account->id, 'auto_product_id' => 'tc01', 'shop_product_id' => $pid, 'display_name' => 'Kích rễ TC01']);

    $byAi = ($this->rieng)('ai.mp4', null, ['product_code' => 'tc01', 'meta' => ['folder_id' => 1, 'ai' => ['state' => 'ok', 'product_code' => 'tc01', 'caption' => 'Cap AI viết', 'hashtags' => ['#kichre']]]]);
    $byKid = ($this->rieng)('kid.mp4', null, ['product_code' => 'nano-dong', 'meta' => ['folder_id' => 1, 'product_by' => 'kid']]);
    $unsure = ($this->rieng)('doan.mp4', null, ['meta' => ['folder_id' => 1, 'ai' => ['state' => 'unsure', 'product_code' => 'tc01']]]);

    // gợi ý giờ trả kèm sản phẩm từng video để hộp chọn sẵn "theo từng video"
    $p = ($this->batch)()->propose(['social_account_id' => $account->id, 'items' => [['id' => $byAi->id], ['id' => $byKid->id], ['id' => $unsure->id]]], $this->now);
    $byId = collect($p['rows'])->keyBy('id');
    expect($byId[$byAi->id]['product'])->toMatchArray(['code' => 'tc01', 'by' => 'ai', 'cart' => true])
        ->and($byId[$byKid->id]['product'])->toMatchArray(['code' => 'nano-dong', 'by' => 'kid'])
        ->and($byId[$unsure->id]['product'])->toMatchArray(['code' => null, 'guess' => 'tc01']);

    $in = ($this->input)($account, [$byAi, $byKid, $unsure], ['product_code' => RiengBatch::PER_VIDEO, 'caption' => '', 'hashtags' => '']);
    $done = ($this->batch)()->commit($in, false, $this->now);
    $rows = collect($done['rows'])->keyBy('id');

    expect($done['done'])->toBe(2)
        ->and($rows[$unsure->id]['status'])->toBe('error')
        ->and($rows[$unsure->id]['messages'][0])->toContain('chưa chắc')
        ->and($byAi->fresh()->product_code)->toBe('tc01')
        ->and($byKid->fresh()->product_code)->toBe('nano-dong')
        ->and($unsure->fresh()->status)->toBe('new');

    $post = Post::query()->get()->first(fn (Post $p) => $p->meta['fork_auto_video_id'] === $byAi->id);
    expect($post->meta['fork_shop_product_id'])->toBe($pid)
        // không viết caption chung: dùng caption AI của chính video
        ->and($post->content)->toContain('Cap AI viết')->toContain('#kichre');

    // chọn riêng sản phẩm cho video AI chưa chắc
    $again = ($this->batch)()->commit(($this->input)($account, [['id' => $unsure->id, 'product' => 'tc01|']], ['product_code' => RiengBatch::PER_VIDEO]), false, $this->now);
    expect($again['done'])->toBe(1)->and($unsure->fresh()->product_code)->toBe('tc01');
});

test('a shared product that differs from what the AI found must be confirmed, row by row', function () {
    $account = ($this->account)();
    AutoProduct::create(['code' => 'tc01', 'name' => 'Kích rễ TC01', 'short_name' => 'TC01', 'facts' => [], 'enabled' => true]);
    $v = ($this->rieng)('ai.mp4', null, ['product_code' => 'tc01', 'meta' => ['folder_id' => 1, 'ai' => ['state' => 'ok', 'product_code' => 'tc01']]]);
    $same = ($this->rieng)('dung.mp4', null, ['product_code' => 'nano-dong', 'meta' => ['folder_id' => 1]]);

    $first = ($this->batch)()->commit(($this->input)($account, [$v, $same]), false, $this->now);
    $rows = collect($first['rows'])->keyBy('id');

    expect($first['committed'] ?? false)->toBeFalse()->and($first['needs_confirm'])->toBeTrue()
        ->and($rows[$v->id]['status'])->toBe('warn')
        ->and(implode(' ', $rows[$v->id]['messages']))->toContain('AI nhận ra video này là TC01')
        ->and($rows[$same->id]['status'])->toBe('ok')
        ->and(Post::query()->count())->toBe(0);

    // chủ app thấy cảnh báo và vẫn hẹn: gắn đúng sản phẩm chung đã chọn
    $ok = ($this->batch)()->commit(($this->input)($account, [$v, $same]), true, $this->now);
    expect($ok['done'])->toBe(2)->and($v->fresh()->product_code)->toBe('nano-dong');
});

test('owner can swap the music of a scheduled private video: remixed from the original, old upload file removed', function () {
    $ffmpeg = app(RiengThumbs::class)->ffmpegPath();

    if ($ffmpeg === null) {
        $this->markTestSkipped('ffmpeg not installed');
    }

    $run = function (array $args) use ($ffmpeg): string {
        $p = new Process([$ffmpeg, '-hide_banner', ...$args]);
        $p->setTimeout(60);
        $p->run();

        return $p->getErrorOutput();
    };
    $music = $this->own.'/_nhac';
    File::ensureDirectoryExists($music);
    $run(['-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=880:duration=20', $music.'/nhac-1.mp3']);
    $run(['-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=330:duration=20', $music.'/nhac-2.mp3']);
    $folder = RiengFolder::create(['path' => $this->own, 'music' => ['enabled' => true, 'dir' => $music, 'mode' => 'mix', 'gain_db' => -12]]);
    $v = ($this->rieng)('goc.mp4', null, ['meta' => ['folder_id' => $folder->id, 'rel_path' => 'goc.mp4']]);
    $run(['-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=25:duration=4', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', $v->path]);
    $before = md5_file($v->path);

    expect(($this->batch)()->commit(($this->input)(($this->account)(), [$v]), false, $this->now)['done'])->toBe(1);
    $v->refresh();
    $post = Post::query()->findOrFail($v->post_id);
    $first = (string) $post->meta['fork_music'];
    $oldFile = (string) Media::query()->where('post_id', $post->id)->value('path');
    $other = $first === 'nhac-1.mp3' ? 'nhac-2.mp3' : 'nhac-1.mp3';

    $edits = app(PostEdits::class);
    $info = $edits->describe($v);
    expect($info['music']['current'])->toBe($first)->and(array_column($info['music']['tracks'], 'rel'))->toContain($other);

    // "*" = bốc bài khác bài đang dùng.
    expect($edits->edit($v, ['music' => '*'])['state'])->toBe('done');
    $post->refresh();
    $newFile = (string) Media::query()->where('post_id', $post->id)->value('path');

    expect($post->meta['fork_music'])->toBe($other)
        ->and($newFile)->not->toBe($oldFile)->toEndWith('.mp4')
        ->and(Storage::exists($newFile))->toBeTrue()->and(Storage::exists($oldFile))->toBeFalse()
        ->and(data_get($post->media, '0.path'))->toBe($newFile)
        ->and($run(['-i', Storage::path($newFile)]))->toMatch('/Audio: aac/')
        ->and(md5_file($v->path))->toBe($before);

    // Bài ngoài thư mục nhạc bị từ chối.
    expect(fn () => $edits->edit($v->refresh(), ['music' => '../goc.mp4']))->toThrow(RuntimeException::class);
});

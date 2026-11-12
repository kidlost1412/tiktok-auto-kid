<?php

declare(strict_types=1);

use App\Fork\AutoPost\KhoStore;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\VideoLibrary;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    Cache::flush();
    $this->hub = str_replace('\\', '/', sys_get_temp_dir()).'/hub-kho-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/san-pham/dam-ca');
    File::ensureDirectoryExists($this->hub.'/san-pham/nano-dong');
    File::ensureDirectoryExists($this->hub.'/kho-dang');

    file_put_contents($this->hub.'/san-pham/dam-ca/san-pham.json', json_encode([
        'ma' => 'dam-ca', 'ten_goi' => 'Đạm cá', 'ten_ngan' => 'Đạm Cá',
        'quy_cach' => [['ma' => '1l', 'ten' => 'Chai 1L'], ['ma' => '5l', 'ten' => 'Can 5L']],
    ]));
    file_put_contents($this->hub.'/san-pham/nano-dong/san-pham.json', json_encode(['ma' => 'nano-dong', 'ten_goi' => 'Nano Đồng', 'ten_ngan' => 'Nano Đồng']));

    config(['fork.auto.hub_path' => $this->hub, 'fork.auto.settle_seconds' => 0, 'fork.auto.legacy_ra' => true, 'trypost.self_hosted' => true]);
    $this->lib = app(VideoLibrary::class);
    $this->lib->syncProducts();
});

afterEach(function (): void {
    File::deleteDirectory($this->hub);
});

function khoItem(string $hub, string $stem, ?array $json, string $dir = ''): string
{
    $folder = $hub.'/kho-dang'.($dir !== '' ? "/{$dir}" : '');
    File::ensureDirectoryExists($folder);
    file_put_contents("{$folder}/{$stem}.mp4", 'video-'.$stem.random_bytes(8));

    if ($json !== null) {
        file_put_contents("{$folder}/{$stem}.json", json_encode($json));
    }

    return "{$folder}/{$stem}.mp4";
}

function khoMember(User $owner): User
{
    return User::factory()->create(['account_id' => $owner->account_id]);
}

function khoOwner(): User
{
    $account = Account::factory()->create();
    $owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $owner->id]);
    $workspace = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $owner->id]);
    $owner->update(['current_workspace_id' => $workspace->id]);

    return $owner;
}

it('lưu quy cách của sản phẩm từ san-pham.json', function (): void {
    expect(AutoProduct::find('dam-ca')->quy_cach)->toBe([['ma' => '1l', 'ten' => 'Chai 1L'], ['ma' => '5l', 'ten' => 'Can 5L']])
        ->and(AutoProduct::find('nano-dong')->quy_cach)->toBeNull();
});

it('nhặt video kho-dang hợp lệ, lưu quy cách, giữ khoá lạ trong meta', function (): void {
    khoItem($this->hub, 'a', ['ma' => 'dam-ca', 'quy_cach' => '5l', 'goc' => 'chu-hang', 'giong' => 'Xuan', 'loi_thoai' => 'Xin chào', 'ngay_lam' => '2026-11-09', 'phien_ban' => 2, 'nhac' => 'N1', 'bo_cuc' => 'x'], 'dam-ca');
    khoItem($this->hub, 'b', ['ma' => 'nano-dong', 'quy_cach' => null]);

    expect($this->lib->ingest())->toBe(['new' => 2, 'skipped' => 0, 'known' => 0]);

    $a = AutoVideo::where('file_name', 'a.mp4')->first();
    expect($a->source)->toBe('kho')->and($a->product_code)->toBe('dam-ca')->and($a->quy_cach)->toBe('5l')
        ->and($a->goc)->toBe('chu-hang')->and($a->script)->toBe('Xin chào')->and($a->nhac)->toBe('N1')
        ->and($a->batch_date->format('Y-m-d'))->toBe('2026-11-09')->and($a->phien_ban)->toBe(2)
        ->and($a->meta)->toBe(['bo_cuc' => 'x'])->and($a->status)->toBe('new');
    expect(AutoVideo::where('file_name', 'b.mp4')->first()->quy_cach)->toBeNull();

    expect($this->lib->ingest())->toBe(['new' => 0, 'skipped' => 0, 'known' => 2]);
});

it('mp4 thiếu json thì chờ, quá hạn thì vào _loi', function (): void {
    $path = khoItem($this->hub, 'c', null);

    expect($this->lib->ingest()['new'])->toBe(0)->and(is_file($path))->toBeTrue()->and($this->lib->khoReport['waiting'])->toBe(1);

    touch($path, time() - 3 * 3600);
    $this->lib->ingest();

    expect(is_file($path))->toBeFalse()
        ->and(file_get_contents($this->hub.'/kho-dang/_loi/c.loi.txt'))->toContain('thiếu file .json')
        ->and(AutoVideo::count())->toBe(0);
});

it('json hỏng hoặc sai quy cách thì chuyển cả hai file vào _loi kèm lý do', function (): void {
    khoItem($this->hub, 'bad', null);
    file_put_contents($this->hub.'/kho-dang/bad.json', '{khong hop le');
    khoItem($this->hub, 'qc', ['ma' => 'dam-ca', 'quy_cach' => '9l']);
    khoItem($this->hub, 'noqc', ['ma' => 'dam-ca', 'quy_cach' => null]);
    khoItem($this->hub, 'lạ', ['ma' => 'khong-co', 'quy_cach' => null]);
    khoItem($this->hub, 'thua', ['ma' => 'nano-dong', 'quy_cach' => '1l']);

    $this->lib->ingest();

    expect(AutoVideo::count())->toBe(0)->and($this->lib->khoReport['error'])->toBe(5);

    foreach (['bad', 'qc', 'noqc', 'lạ', 'thua'] as $stem) {
        expect(is_file("{$this->hub}/kho-dang/_loi/{$stem}.mp4"))->toBeTrue()
            ->and(is_file("{$this->hub}/kho-dang/_loi/{$stem}.json"))->toBeTrue()
            ->and(is_file("{$this->hub}/kho-dang/_loi/{$stem}.loi.txt"))->toBeTrue()
            ->and(is_file("{$this->hub}/kho-dang/{$stem}.mp4"))->toBeFalse();
    }
});

it('file chưa ổn định (kích thước còn đổi hoặc chưa đủ settle_seconds) thì chưa nhặt', function (): void {
    config(['fork.auto.settle_seconds' => 60]);
    $path = khoItem($this->hub, 'u', ['ma' => 'nano-dong', 'quy_cach' => null]);

    expect($this->lib->ingest()['new'])->toBe(0);
    file_put_contents($path, 'dai hon nhieu '.str_repeat('x', 50));
    expect($this->lib->ingest()['new'])->toBe(0);

    // Cùng kích thước nhưng mới thấy vài giây: vẫn chưa.
    expect($this->lib->ingest()['new'])->toBe(0);

    // Đã thấy cùng kích thước đủ lâu.
    foreach ([$path, substr($path, 0, -4).'.json'] as $f) {
        Cache::put('fork-auto:size:'.sha1($f), ['size' => filesize($f), 'since' => time() - 120], 3600);
    }

    expect($this->lib->ingest()['new'])->toBe(1);
});

it('dedupe theo sha256: bản trùng nội dung vào _loi', function (): void {
    $a = khoItem($this->hub, 'd1', ['ma' => 'nano-dong', 'quy_cach' => null]);
    $this->lib->ingest();
    $b = khoItem($this->hub, 'd2', ['ma' => 'nano-dong', 'quy_cach' => null]);
    file_put_contents($b, file_get_contents($a));

    $this->lib->ingest();

    expect(AutoVideo::count())->toBe(1)->and(file_get_contents($this->hub.'/kho-dang/_loi/d2.loi.txt'))->toContain('trùng');
});

it('cờ legacy_ra tắt thì không nhặt ra/<ngày>', function (): void {
    File::ensureDirectoryExists($this->hub.'/ra/2026-11-09');
    file_put_contents($this->hub.'/ra/2026-11-09/NanoĐồng_a_X_MIXKIT_1.mp4', 'legacy');

    config(['fork.auto.legacy_ra' => false]);
    expect($this->lib->ingest()['new'])->toBe(0);

    config(['fork.auto.legacy_ra' => true]);
    expect($this->lib->ingest()['new'])->toBe(1)->and(AutoVideo::first()->quy_cach)->toBeNull()->and(AutoVideo::first()->source)->toBe('ra');
});

function khoVideo(array $attrs = []): AutoVideo
{
    static $n = 0;
    $n++;

    return AutoVideo::create($attrs + [
        'hash' => hash('sha256', "kv{$n}"), 'path' => "/nonexistent/kv{$n}.mp4", 'batch_date' => '2026-11-10',
        'file_name' => "kv{$n}.mp4", 'product_code' => 'dam-ca', 'quy_cach' => '1l', 'goc' => "g{$n}",
        'source' => 'kho', 'status' => 'new', 'caption' => 'Caption hub', 'hashtags' => [], 'caption_source' => 'hub',
    ]);
}

it('reserveNext khớp cặp mã x quy cách, kể cả null và dạng cũ list<string>', function (): void {
    $sa = SocialAccount::factory()->tiktok()->create();
    $l1 = khoVideo(['quy_cach' => '1l']);
    $l5 = khoVideo(['quy_cach' => '5l', 'batch_date' => '2026-11-11']);
    $nano = khoVideo(['product_code' => 'nano-dong', 'quy_cach' => null, 'batch_date' => '2026-11-12']);

    expect($this->lib->reserveNext($sa, []))->toBeNull()
        ->and($this->lib->reserveNext($sa, ['dam-ca' => []]))->toBeNull()
        ->and($this->lib->reserveNext($sa, ['dam-ca' => ['9l']]))->toBeNull()
        ->and($this->lib->reserveNext($sa, ['dam-ca' => [null]]))->toBeNull();

    // Chỉ 5l (l1 cũ hơn nhưng không được phép).
    expect($this->lib->reserveNext($sa, ['dam-ca' => ['5l']])->id)->toBe($l5->id);
    // Nano quy cách null khớp phần tử null.
    expect($this->lib->reserveNext($sa, ['dam-ca' => ['9l'], 'nano-dong' => [null]])->id)->toBe($nano->id);
    // Dạng cũ: mã => mọi quy cách.
    expect($this->lib->reserveNext($sa, ['dam-ca'])->id)->toBe($l1->id);
    // Không giới hạn: hết video thì null.
    expect($this->lib->reserveNext($sa))->toBeNull();
});

it('markPosted kiểu kho: dời vào da-dang/<ngày> kèm ket-qua.json, giữ file khi retention 30', function (): void {
    $sa = SocialAccount::factory()->tiktok()->create(['username' => 'kenh1']);
    $mp4 = khoItem($this->hub, 'p1', ['ma' => 'dam-ca', 'quy_cach' => '1l']);
    $this->lib->ingest();
    $v = AutoVideo::first();
    $v->forceFill(['social_account_id' => $sa->id, 'status' => 'scheduled', 'stats' => ['link' => 'https://www.tiktok.com/@k/video/1']])->save();

    $this->lib->markPosted($v, '711');
    $v->refresh();
    $day = $v->posted_at->copy()->timezone('Asia/Ho_Chi_Minh')->format('Y-m-d');
    $dir = "{$this->hub}/da-dang/{$day}";

    expect($v->status)->toBe('posted')->and($v->path)->toBe("{$dir}/p1.mp4")
        ->and(is_file("{$dir}/p1.mp4"))->toBeTrue()->and(is_file("{$dir}/p1.json"))->toBeTrue()
        ->and(is_file($mp4))->toBeFalse()->and($v->files_deleted_at)->toBeNull();

    $result = json_decode(file_get_contents("{$dir}/p1.ket-qua.json"), true);
    expect($result)->toMatchArray(['ma' => 'dam-ca', 'quy_cach' => '1l', 'kenh' => 'kenh1', 'tiktok_video_id' => '711', 'tiktok_link' => 'https://www.tiktok.com/@k/video/1']);
});

it('retention xoa_ngay xoá mp4 và json ngay, chỉ giữ ket-qua.json', function (): void {
    AutoSetting::write(KhoStore::RETENTION_KEY, 'xoa_ngay');
    khoItem($this->hub, 'p2', ['ma' => 'nano-dong', 'quy_cach' => null]);
    $this->lib->ingest();
    $v = AutoVideo::first();
    $v->forceFill(['status' => 'scheduled'])->save();

    $this->lib->markPosted($v, null);
    $v->refresh();
    $dir = dirname($v->path);

    expect(is_file("{$dir}/p2.mp4"))->toBeFalse()->and(is_file("{$dir}/p2.json"))->toBeFalse()
        ->and(is_file("{$dir}/p2.ket-qua.json"))->toBeTrue()->and($v->files_deleted_at)->not->toBeNull();
});

it('fork:auto-cleanup xoá mp4/json quá hạn, không bao giờ xoá ket-qua.json', function (): void {
    $today = CarbonImmutable::now('Asia/Ho_Chi_Minh');
    $make = function (string $day) {
        $dir = "{$this->hub}/da-dang/{$day}";
        File::ensureDirectoryExists($dir);

        foreach (['x.mp4', 'x.json', 'x.ket-qua.json'] as $f) {
            file_put_contents("{$dir}/{$f}", '1');
        }

        return $dir;
    };
    $old = $make($today->subDays(40)->format('Y-m-d'));
    $mid = $make($today->subDays(10)->format('Y-m-d'));
    $new = $make($today->subDays(2)->format('Y-m-d'));

    // Mặc định 30 ngày.
    Artisan::call('fork:auto-cleanup');
    expect(is_file("{$old}/x.mp4"))->toBeFalse()->and(is_file("{$old}/x.json"))->toBeFalse()->and(is_file("{$old}/x.ket-qua.json"))->toBeTrue()
        ->and(is_file("{$mid}/x.mp4"))->toBeTrue();

    AutoSetting::write(KhoStore::RETENTION_KEY, '7');
    Artisan::call('fork:auto-cleanup');
    expect(is_file("{$mid}/x.mp4"))->toBeFalse()->and(is_file("{$mid}/x.ket-qua.json"))->toBeTrue()->and(is_file("{$new}/x.mp4"))->toBeTrue();

    AutoSetting::write(KhoStore::RETENTION_KEY, 'vinh_vien');
    $keep = $make($today->subDays(400)->format('Y-m-d'));
    Artisan::call('fork:auto-cleanup');
    expect(is_file("{$keep}/x.mp4"))->toBeTrue();

    AutoSetting::write(KhoStore::RETENTION_KEY, 'xoa_ngay');
    Artisan::call('fork:auto-cleanup');
    expect(is_file("{$new}/x.mp4"))->toBeFalse()->and(is_file("{$new}/x.ket-qua.json"))->toBeTrue();
});

it('fork:auto-cleanup được đăng ký trong lịch', function (): void {
    $commands = collect(app(Schedule::class)->events())->map(fn ($e) => $e->command);

    expect($commands->contains(fn ($c) => str_contains((string) $c, 'fork:auto-cleanup')))->toBeTrue();
});

it('trang Kho: chỉ chủ tài khoản, hiện ma trận sản phẩm x quy cách và cập nhật lúc', function (): void {
    khoVideo(['quy_cach' => '1l']);
    khoVideo(['quy_cach' => '1l']);
    khoVideo(['quy_cach' => '5l', 'status' => 'posted']);

    $owner = khoOwner();
    $this->actingAs(khoMember($owner))->get('/auto/kho')->assertForbidden();

    $this->actingAs($owner)->get('/auto/kho?tab=all')
        ->assertOk()
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->component('fork/Kho')
            ->where('retention.value', '30')
            ->where('videos.total', 3)
            ->has('updated_at')
            ->has('matrix', 3)
            ->where('matrix.0.quy_cach', '1l')->where('matrix.0.new', 2)
            ->where('matrix.1.quy_cach', '5l')->where('matrix.1.posted', 1));
});

it('lưu cài đặt lưu giữ, từ chối giá trị lạ', function (): void {
    $owner = khoOwner();

    $this->actingAs($owner)->patch('/auto/kho/settings', ['retention' => '7'])->assertRedirect();
    expect(app(KhoStore::class)->retention())->toBe('7');

    $this->actingAs($owner)->patch('/auto/kho/settings', ['retention' => '999'])->assertSessionHasErrors('retention');
    expect(app(KhoStore::class)->retention())->toBe('7');
    $this->actingAs(khoMember($owner))->patch('/auto/kho/settings', ['retention' => '30'])->assertForbidden();
});

it('route video chỉ phục vụ file dưới /hub theo id trong DB, chỉ cho chủ tài khoản', function (): void {
    $inside = khoItem($this->hub, 'v1', ['ma' => 'nano-dong', 'quy_cach' => null]);
    $outside = sys_get_temp_dir().'/ngoai-hub-'.bin2hex(random_bytes(3)).'.mp4';
    file_put_contents($outside, 'secret');
    $traversal = $this->hub.'/kho-dang/../../'.basename($outside);

    $ok = khoVideo(['path' => $inside]);
    $bad = khoVideo(['path' => $outside]);
    $dots = khoVideo(['path' => $traversal]);
    $gone = khoVideo(['path' => $inside, 'files_deleted_at' => now()]);
    $owner = khoOwner();

    $this->actingAs($owner)->get("/auto/kho/video/{$ok->id}")->assertOk()->assertHeader('content-type', 'video/mp4');
    $this->actingAs($owner)->get("/auto/kho/video/{$bad->id}")->assertNotFound();
    $this->actingAs($owner)->get("/auto/kho/video/{$dots->id}")->assertNotFound();
    $this->actingAs($owner)->get("/auto/kho/video/{$gone->id}")->assertNotFound();
    $this->actingAs($owner)->get('/auto/kho/video/999999')->assertNotFound();
    $this->actingAs($owner)->get('/auto/kho/video/abc')->assertNotFound();
    $this->actingAs(khoMember($owner))->get("/auto/kho/video/{$ok->id}")->assertForbidden();
    auth()->logout();
    $this->get("/auto/kho/video/{$ok->id}")->assertRedirect();

    @unlink($outside);
});

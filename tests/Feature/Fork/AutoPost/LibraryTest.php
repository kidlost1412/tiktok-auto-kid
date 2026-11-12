<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\VideoLibrary;
use App\Models\SocialAccount;
use Illuminate\Support\Facades\File;

beforeEach(function (): void {
    $this->hub = str_replace('\\', '/', sys_get_temp_dir()).'/hub-test-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/san-pham/nano-dong');
    File::ensureDirectoryExists($this->hub.'/san-pham/kali-bo');
    File::ensureDirectoryExists($this->hub.'/san-pham/_mau');
    File::ensureDirectoryExists($this->hub.'/ra');

    file_put_contents($this->hub.'/san-pham/nano-dong/san-pham.json', json_encode(['ma' => 'nano-dong', 'ten_goi' => 'Nano Đồng Toàn Cầu', 'ten_ngan' => 'Nano Đồng', 'cong_dung' => 'Rửa vườn']));
    file_put_contents($this->hub.'/san-pham/kali-bo/san-pham.json', json_encode(['ma' => 'kali-bo', 'ten_goi' => 'Kali Bo', 'ten_ngan' => 'Kali Bo']));
    file_put_contents($this->hub.'/san-pham/_mau/san-pham.json', json_encode(['ma' => 'mau', 'ten_goi' => 'Mẫu', 'ten_ngan' => 'Mẫu']));

    config(['fork.auto.hub_path' => $this->hub, 'fork.auto.settle_seconds' => 0]);
});

afterEach(function (): void {
    File::deleteDirectory($this->hub);
});

function hubVideo(string $hub, string $date, string $name, ?string $content = null): string
{
    File::ensureDirectoryExists("{$hub}/ra/{$date}");
    $path = "{$hub}/ra/{$date}/{$name}";
    file_put_contents($path, $content ?? $name.random_bytes(8));

    return $path;
}

function hubCsv(string $hub, string $date, array $rows): void
{
    $header = 'file,goc,giong,nhac,thoi_luong,font,phu_de,karaoke,chuyen_canh,chuyen_dong,mau,the_mo,the_chot,loi,luot_xem,don,ghi_chu';
    $lines = [$header];

    foreach ($rows as $file => $row) {
        $lines[] = sprintf(
            '%s,%s,%s,%s,%s,%s,%s,,%s,%s,%s,,,"%s",,,',
            $file, $row['goc'] ?? '', $row['giong'] ?? '', $row['nhac'] ?? '', $row['thoi_luong'] ?? '',
            $row['font'] ?? '', $row['phu_de'] ?? '', $row['chuyen_canh'] ?? '', $row['chuyen_dong'] ?? '',
            $row['mau'] ?? '', str_replace('"', '""', $row['loi'] ?? ''),
        );
    }

    file_put_contents("{$hub}/ra/{$date}/bang-ghi.csv", "\xEF\xBB\xBF".implode("\r\n", $lines)."\r\n");
}

function library(): VideoLibrary
{
    return app(VideoLibrary::class);
}

function makeVideo(array $attrs = []): AutoVideo
{
    static $n = 0;
    $n++;

    return AutoVideo::create($attrs + [
        'hash' => hash('sha256', "v{$n}"),
        'path' => "/nonexistent/v{$n}.mp4",
        'batch_date' => '2026-11-10',
        'file_name' => "NanoĐồng_g{$n}_X_MIXKIT_{$n}.mp4",
        'product_code' => 'nano-dong',
        'goc' => "g{$n}",
        'status' => 'new',
        'hashtags' => ['#a'], 'caption' => 'Caption hub', 'caption_source' => 'hub',
    ]);
}

it('đồng bộ sản phẩm, bỏ qua thư mục bắt đầu bằng gạch dưới và giữ cấu hình đã gắn', function (): void {
    expect(library()->syncProducts())->toBe(2);

    AutoProduct::find('nano-dong')->update(['enabled' => false, 'shop_product_id' => '123']);
    library()->syncProducts();

    $p = AutoProduct::find('nano-dong');
    expect($p->short_name)->toBe('Nano Đồng')
        ->and($p->facts['cong_dung'])->toBe('Rửa vườn')
        ->and($p->enabled)->toBeFalse()
        ->and($p->shop_product_id)->toBe('123')
        ->and(AutoProduct::find('mau'))->toBeNull();
});

it('nhận ra sản phẩm theo tiền tố tên file (bỏ dấu, bỏ dấu cách)', function (): void {
    library()->syncProducts();

    expect(library()->productCodeForFile('NanoĐồng_chu-hang_X_MIXKIT_1.mp4'))->toBe('nano-dong')
        ->and(library()->productCodeForFile('nano-dong_chu-hang_X_MIXKIT_1.mp4'))->toBe('nano-dong')
        ->and(library()->productCodeForFile('KaliBo_a_b_MIXKIT_1.mp4'))->toBe('kali-bo')
        ->and(library()->productCodeForFile('LaMa_a_b_MIXKIT_1.mp4'))->toBeNull();
});

it('đọc bang-ghi.csv có BOM và ngoặc kép, bỏ qua bản CHON-NHAC', function (): void {
    library()->syncProducts();

    $keep = 'NanoĐồng_chu-hang_XuanLuong_MIXKIT_20261109-161356-2.mp4';
    $skip = 'NanoĐồng_chu-hang_XuanLuong_CHON-NHAC-TIKTOK_20261109-161340-1.mp4';
    hubVideo($this->hub, '2026-11-09', $keep);
    hubVideo($this->hub, '2026-11-09', $skip);
    hubVideo($this->hub, '_ban-nhap', 'x.mp4');
    hubCsv($this->hub, '2026-11-09', [
        $keep => ['goc' => 'chu-hang', 'giong' => 'XuanLuong', 'nhac' => 'The Hamptons', 'thoi_luong' => '20.3', 'phu_de' => 'gach_chay', 'loi' => 'Hái xong, "phun" ngay Nano, có dấu phẩy.'],
    ]);

    expect(library()->ingest())->toBe(['new' => 1, 'skipped' => 1, 'known' => 0]);

    $v = AutoVideo::where('file_name', $keep)->first();
    expect($v->status)->toBe('new')
        ->and($v->product_code)->toBe('nano-dong')
        ->and($v->goc)->toBe('chu-hang')
        ->and($v->nhac)->toBe('The Hamptons')
        ->and($v->duration)->toBe(20.3)
        ->and($v->script)->toBe('Hái xong, "phun" ngay Nano, có dấu phẩy.')
        ->and($v->batch_date->toDateString())->toBe('2026-11-09')
        ->and(strlen($v->hash))->toBe(64);

    $s = AutoVideo::where('file_name', $skip)->first();
    expect($s->status)->toBe('skipped')->and($s->skip_reason)->toBe('chưa có nhạc');
});

it('video có hash trùng hoặc đã biết không tạo bản ghi mới', function (): void {
    library()->syncProducts();

    hubVideo($this->hub, '2026-11-09', 'NanoĐồng_a_X_MIXKIT_1.mp4', 'cung-noi-dung');
    expect(library()->ingest()['new'])->toBe(1);

    // Chạy lại: file cũ đã biết.
    expect(library()->ingest())->toBe(['new' => 0, 'skipped' => 0, 'known' => 1]);

    // Bản sao cùng nội dung ở tên khác.
    hubVideo($this->hub, '2026-11-10', 'NanoĐồng_b_X_MIXKIT_2.mp4', 'cung-noi-dung');
    $r = library()->ingest();

    expect($r['new'])->toBe(0)->and($r['known'])->toBe(2)->and(AutoVideo::count())->toBe(1);
});

it('không nhặt file vừa được ghi trong khoảng chờ', function (): void {
    library()->syncProducts();
    config(['fork.auto.settle_seconds' => 3600]);

    hubVideo($this->hub, '2026-11-09', 'NanoĐồng_a_X_MIXKIT_1.mp4');

    expect(library()->ingest()['new'])->toBe(0)->and(AutoVideo::count())->toBe(0);
});

it('xoay vòng sản phẩm và góc, lô cũ trước', function (): void {
    AutoProduct::create(['code' => 'nano-dong', 'name' => 'N', 'short_name' => 'Nano Đồng']);
    AutoProduct::create(['code' => 'kali-bo', 'name' => 'K', 'short_name' => 'Kali Bo']);
    AutoProduct::create(['code' => 'lan', 'name' => 'L', 'short_name' => 'Lan']);
    $sa = SocialAccount::factory()->tiktok()->create();

    $old = makeVideo(['batch_date' => '2026-11-08', 'product_code' => 'nano-dong', 'goc' => 'a']);
    makeVideo(['batch_date' => '2026-11-09', 'product_code' => 'nano-dong', 'goc' => 'b']);
    $kali = makeVideo(['batch_date' => '2026-11-09', 'product_code' => 'kali-bo', 'goc' => 'a']);
    $lan = makeVideo(['batch_date' => '2026-11-09', 'product_code' => 'lan', 'goc' => 'c']);

    $first = library()->reserveNext($sa);
    expect($first->id)->toBe($old->id)->and($first->status)->toBe('reserved')->and($first->social_account_id)->toBe($sa->id);

    // Sau Nano: tránh Nano và góc a -> chỉ còn Lan (Kali bo trùng góc a).
    $second = library()->reserveNext($sa);
    expect($second->id)->toBe($lan->id);

    // Còn Kali (góc a trùng bài 1) và Nano: tránh sản phẩm 2 bài gần nhất (lan, nano) -> Kali dù trùng góc.
    $third = library()->reserveNext($sa);
    expect($third->id)->toBe($kali->id);

    // Chỉ còn Nano góc b: nới ràng buộc vẫn trả về.
    $fourth = library()->reserveNext($sa);
    expect($fourth->product_code)->toBe('nano-dong')->and($fourth->goc)->toBe('b');

    expect(library()->reserveNext($sa))->toBeNull();
});

it('chỉ lấy video MIXKIT của sản phẩm đang bật và trạng thái new', function (): void {
    AutoProduct::create(['code' => 'nano-dong', 'name' => 'N', 'short_name' => 'Nano Đồng']);
    AutoProduct::create(['code' => 'off', 'name' => 'O', 'short_name' => 'Off', 'enabled' => false]);
    $sa = SocialAccount::factory()->tiktok()->create();

    makeVideo(['product_code' => 'off']);
    makeVideo(['file_name' => 'NanoĐồng_a_X_CHON-NHAC-TIKTOK_1.mp4']);
    makeVideo(['status' => 'skipped']);
    makeVideo(['product_code' => null]);

    expect(library()->reserveNext($sa))->toBeNull();
});

it('hai lần reserveNext không lấy cùng một video, kể cả giữa hai tài khoản', function (): void {
    AutoProduct::create(['code' => 'nano-dong', 'name' => 'N', 'short_name' => 'Nano Đồng']);
    [$a, $b] = [SocialAccount::factory()->tiktok()->create(), SocialAccount::factory()->tiktok()->create()];
    makeVideo();
    makeVideo();

    $x = library()->reserveNext($a);
    $y = library()->reserveNext($b);

    expect($x->id)->not->toBe($y->id)
        ->and(library()->reserveNext($a))->toBeNull();
});

it('release trả video đã giữ về new, còn video đã xếp lịch thì thành failed', function (): void {
    AutoProduct::create(['code' => 'nano-dong', 'name' => 'N', 'short_name' => 'Nano Đồng']);
    $sa = SocialAccount::factory()->tiktok()->create();
    makeVideo();

    $v = library()->reserveNext($sa);
    $v->update(['caption' => 'x']); // chữ của hub được giữ lại khi trả kho
    library()->release($v, 'lỗi tạo bài');
    $v->refresh();
    expect($v->status)->toBe('new')->and($v->social_account_id)->toBeNull()->and($v->caption)->toBe('x');

    $v = library()->reserveNext($sa);
    $v->update(['status' => 'scheduled']);
    library()->release($v, 'bài bị xoá');
    $v->refresh();
    expect($v->status)->toBe('failed')->and($v->skip_reason)->toBe('bài bị xoá')->and(library()->reserveNext($sa))->toBeNull();
});

it('markPosted chuyển file sang ra/_da-dang/<ngày> và ghi nhận bài đã đăng', function (): void {
    library()->syncProducts();
    $name = 'NanoĐồng_a_X_MIXKIT_1.mp4';
    $path = hubVideo($this->hub, '2026-11-09', $name);
    library()->ingest();

    $v = AutoVideo::first();
    library()->markPosted($v, '7123');

    $v->refresh();
    $moved = $this->hub.'/ra/_da-dang/2026-11-09/'.$name;

    expect($v->status)->toBe('posted')
        ->and($v->tiktok_video_id)->toBe('7123')
        ->and($v->posted_at)->not->toBeNull()
        ->and($v->path)->toBe($moved)
        ->and(is_file($moved))->toBeTrue()
        ->and(is_file($path))->toBeFalse();

    // Gọi lại không lỗi và không làm mất file; lần ingest sau không nhặt lại.
    library()->markPosted($v, null);
    expect(is_file($moved))->toBeTrue()->and($v->fresh()->tiktok_video_id)->toBe('7123')
        ->and(library()->ingest()['new'])->toBe(0);
});

it('lệnh fork:auto-ingest đồng bộ sản phẩm rồi nhặt video', function (): void {
    hubVideo($this->hub, '2026-11-09', 'NanoĐồng_a_X_MIXKIT_1.mp4');

    $this->artisan('fork:auto-ingest')->assertSuccessful();

    expect(AutoProduct::count())->toBe(2)->and(AutoVideo::first()->product_code)->toBe('nano-dong');
});

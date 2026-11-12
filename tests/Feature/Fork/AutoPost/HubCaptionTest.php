<?php

declare(strict_types=1);

use App\Fork\AutoPost\CaptionService;
use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\VideoLibrary;
use App\Models\SocialAccount;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;

beforeEach(function (): void {
    Cache::flush();
    Http::preventStrayRequests();
    Http::fake();

    $this->hub = str_replace('\\', '/', sys_get_temp_dir()).'/hub-cap-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/san-pham/nano-dong');
    File::ensureDirectoryExists($this->hub.'/kho-dang');
    File::ensureDirectoryExists($this->hub.'/ra/2026-11-09');
    file_put_contents($this->hub.'/san-pham/nano-dong/san-pham.json', json_encode(['ma' => 'nano-dong', 'ten_goi' => 'Nano Đồng', 'ten_ngan' => 'Nano Đồng']));

    config(['fork.auto.hub_path' => $this->hub, 'fork.auto.settle_seconds' => 0, 'fork.auto.legacy_ra' => true]);
    $this->lib = app(VideoLibrary::class);
    $this->lib->syncProducts();
    $this->account = SocialAccount::factory()->tiktok()->create(); // observer của factory gọi API follower (đã fake)
    $this->requestsBefore = count(Http::recorded());
});

afterEach(function (): void {
    File::deleteDirectory($this->hub);
    // Đường đăng không được gọi AI hay bất kỳ dịch vụ ngoài nào.
    expect(Http::recorded())->toHaveCount($this->requestsBefore);
});

function capKho(string $stem, array $json, ?string $txt = null): string
{
    $dir = config('fork.auto.hub_path').'/kho-dang';
    file_put_contents("{$dir}/{$stem}.mp4", 'v-'.$stem.random_bytes(8));
    file_put_contents("{$dir}/{$stem}.json", json_encode(['ma' => 'nano-dong', 'quy_cach' => null] + $json, JSON_UNESCAPED_UNICODE));

    if ($txt !== null) {
        file_put_contents("{$dir}/{$stem}.txt", $txt);
    }

    return "{$dir}/{$stem}.mp4";
}

function capLegacy(string $stem, ?string $txt = null, ?string $csvLine = null): string
{
    $dir = config('fork.auto.hub_path').'/ra/2026-11-09';
    $name = "NanoĐồng_{$stem}_X_MIXKIT_1.mp4";
    file_put_contents("{$dir}/{$name}", 'v-'.$stem.random_bytes(8));

    if ($txt !== null) {
        file_put_contents("{$dir}/".pathinfo($name, PATHINFO_FILENAME).'.txt', $txt);
    }

    if ($csvLine !== null) {
        $csv = "\xEF\xBB\xBFfile,goc,caption,hashtag,danh_gia_kid\r\n".sprintf($csvLine, $name)."\r\n";
        file_put_contents("{$dir}/".HubText::CSV_NAME, $csv);
    }

    return $name;
}

it('kho json: caption + hashtag (chuỗi) nguyên văn, ten_gio hợp lệ vào product_name, danh_gia giữ trong meta', function (): void {
    capKho('a', ['caption' => '  Kích rễ TC01 của Toàn Cầu. Bấm giỏ hàng!  ', 'hashtag' => '#kichre   #tc01 #giamcanh', 'ten_gio' => '  KÍCH RỄ TC01  ', 'danh_gia' => 'ung']);

    $this->lib->ingest();
    $v = AutoVideo::firstOrFail();

    expect($v->status)->toBe('new')
        ->and($v->caption)->toBe('Kích rễ TC01 của Toàn Cầu. Bấm giỏ hàng!')
        ->and($v->hashtags)->toBe(['#kichre', '#tc01', '#giamcanh'])
        ->and($v->caption_source)->toBe('hub')
        ->and($v->product_name)->toBe('KÍCH RỄ TC01')
        ->and($v->meta)->toBe(['danh_gia' => 'ung'])
        ->and($v->skip_reason)->toBeNull();

    expect(app(CaptionService::class)->captionFor($v))->toBe([
        'caption' => 'Kích rễ TC01 của Toàn Cầu. Bấm giỏ hàng!',
        'hashtags' => ['#kichre', '#tc01', '#giamcanh'],
        'product_name' => 'KÍCH RỄ TC01',
        'source' => 'hub',
    ]);
    expect(HubText::compose($v->caption, $v->hashtags))->toBe("Kích rễ TC01 của Toàn Cầu. Bấm giỏ hàng!\n\n#kichre #tc01 #giamcanh");
});

it('kho json: hashtag dạng list; ten_gio rỗng hoặc dài hơn 30 ký tự bị bỏ', function (): void {
    capKho('b', ['caption' => 'Câu một.', 'hashtag' => ['#a', '#b'], 'ten_gio' => str_repeat('Ê', 31)]);
    capKho('c', ['caption' => 'Câu hai.', 'ten_gio' => '   ']);
    capKho('d', ['caption' => 'Câu ba.', 'ten_gio' => str_repeat('Ê', 30)]);

    $this->lib->ingest();
    $byCaption = AutoVideo::query()->get()->keyBy('caption');

    expect($byCaption['Câu một.']->hashtags)->toBe(['#a', '#b'])
        ->and($byCaption['Câu một.']->product_name)->toBeNull()
        ->and($byCaption['Câu hai.']->hashtags)->toBe([])
        ->and($byCaption['Câu hai.']->product_name)->toBeNull()
        ->and(mb_strlen($byCaption['Câu ba.']->product_name))->toBe(30);
});

it('kho: json thiếu caption thì lấy từ X.txt cạnh video', function (): void {
    capKho('e', ['goc' => 'chu-hang'], "Caption từ txt.\n#x #y\n");

    $this->lib->ingest();
    $v = AutoVideo::firstOrFail();

    expect($v->caption)->toBe('Caption từ txt.')->and($v->hashtags)->toBe(['#x', '#y'])->and($v->caption_source)->toBe('hub');
});

it('json có caption thì thắng txt', function (): void {
    $path = capKho('f', ['caption' => 'Từ json.', 'hashtag' => '#j'], "Từ txt.\n#t");

    expect(HubText::resolve($path, ['caption' => 'Từ json.', 'hashtag' => '#j']))->toMatchArray(['caption' => 'Từ json.', 'hashtags' => ['#j']]);
});

it('kiểu cũ: X.txt dòng 1 = caption, dòng 2 = hashtag (CRLF và BOM đều được)', function (): void {
    capLegacy('a', "\xEF\xBB\xBFKích rễ TC01 của Toàn Cầu: nhanh rễ. Bấm giỏ hàng để nhận quà theo đơn!\r\n#kichre #kichretc01 #tc01 #nongduoctoancau #giamcanh\r\n");

    $result = $this->lib->ingest();
    $v = AutoVideo::firstOrFail();

    expect($result['new'])->toBe(1)
        ->and($v->caption)->toBe('Kích rễ TC01 của Toàn Cầu: nhanh rễ. Bấm giỏ hàng để nhận quà theo đơn!')
        ->and($v->hashtags)->toBe(['#kichre', '#kichretc01', '#tc01', '#nongduoctoancau', '#giamcanh'])
        ->and($v->caption_source)->toBe('hub')
        ->and($this->lib->reserveNext($this->account)?->id)->toBe($v->id);
});

it('kiểu cũ: không có txt thì lấy hàng bang-ghi-ekip.csv (BOM, ngoặc kép)', function (): void {
    capLegacy('b', null, '%s,goc1,"Caption, có dấu phẩy ""kép"".",#a #b #c,ung');

    $this->lib->ingest();
    $v = AutoVideo::firstOrFail();

    expect($v->caption)->toBe('Caption, có dấu phẩy "kép".')->and($v->hashtags)->toBe(['#a', '#b', '#c'])->and($v->caption_source)->toBe('hub');
});

it('không có caption ở đâu: video MIXKIT chờ (new, chưa giữ chỗ được), có txt sau đó thì lần ingest sau cập nhật và giữ chỗ được', function (): void {
    $name = capLegacy('c');

    $result = $this->lib->ingest();
    $v = AutoVideo::firstOrFail();

    expect($result['new'])->toBe(1)
        ->and($v->status)->toBe('new')->and($v->caption)->toBeNull()->and($v->skip_reason)->toBe('thiếu caption từ hub')
        ->and($this->lib->reserveNext($this->account))->toBeNull()
        ->and($this->lib->hubReport)->toBe(['updated' => 0, 'waiting' => 1]);

    // Hub bổ sung .txt sau: video đã biết được cập nhật, không tạo bản ghi mới.
    file_put_contents($this->hub.'/ra/2026-11-09/'.pathinfo($name, PATHINFO_FILENAME).'.txt', "Có caption rồi.\n#moi");
    $again = $this->lib->ingest();
    $v->refresh();

    expect($again['known'])->toBe(1)->and(AutoVideo::count())->toBe(1)
        ->and($this->lib->hubReport)->toBe(['updated' => 1, 'waiting' => 0])
        ->and($v->caption)->toBe('Có caption rồi.')->and($v->skip_reason)->toBeNull()
        ->and($this->lib->reserveNext($this->account)?->id)->toBe($v->id);
});

it('kho thiếu caption cũng chờ, không vào _loi; caption xuất hiện trong json thì được cập nhật', function (): void {
    $path = capKho('g', ['goc' => 'x']);

    $this->lib->ingest();
    $v = AutoVideo::firstOrFail();

    expect($v->status)->toBe('new')->and($v->caption)->toBeNull()
        ->and(is_file($path))->toBeTrue()
        ->and($this->lib->reserveNext($this->account))->toBeNull();

    file_put_contents(substr($path, 0, -4).'.json', json_encode(['ma' => 'nano-dong', 'quy_cach' => null, 'caption' => 'Đã có.', 'ten_gio' => 'GIỎ RIÊNG']));
    $this->lib->ingest();
    $v->refresh();

    expect($v->caption)->toBe('Đã có.')->and($v->product_name)->toBe('GIỎ RIÊNG')
        ->and($this->lib->reserveNext($this->account)?->id)->toBe($v->id);
});

it('bản không phải MIXKIT kiểu cũ vẫn bị skipped như trước, kể cả khi có txt', function (): void {
    $dir = $this->hub.'/ra/2026-11-09';
    file_put_contents($dir.'/NanoĐồng_x_Y_Z_1.mp4', 'abc');
    file_put_contents($dir.'/NanoĐồng_x_Y_Z_1.txt', "Có caption.\n#a");

    $result = $this->lib->ingest();

    expect($result['skipped'])->toBe(1)->and(AutoVideo::firstOrFail()->skip_reason)->toBe('không phải bản MIXKIT');
});

it('hub sửa caption khi video còn new thì ingest ghi đè; video đã giữ chỗ thì không đụng', function (): void {
    $name = capLegacy('d', "Bản một.\n#a");
    $this->lib->ingest();
    $txt = $this->hub.'/ra/2026-11-09/'.pathinfo($name, PATHINFO_FILENAME).'.txt';

    file_put_contents($txt, "Bản hai.\n#b #c");
    $this->lib->ingest();
    expect(AutoVideo::firstOrFail()->caption)->toBe('Bản hai.')->and(AutoVideo::firstOrFail()->hashtags)->toBe(['#b', '#c']);

    $reserved = $this->lib->reserveNext($this->account);
    file_put_contents($txt, "Bản ba.\n#z");
    $this->lib->ingest();
    expect($reserved->refresh()->caption)->toBe('Bản hai.')->and($reserved->status)->toBe('reserved');
});

it('giới hạn 2200 ký tự gồm hashtag: đúng 2200 nhận, 2201 coi như thiếu caption', function (): void {
    $tags = '#a #b';
    $ok = str_repeat('Ê', 2200 - mb_strlen("\n\n{$tags}"));
    capKho('h', ['caption' => $ok, 'hashtag' => $tags]);
    capKho('i', ['caption' => $ok.'Ê', 'hashtag' => $tags]);

    $this->lib->ingest();
    $videos = AutoVideo::query()->orderBy('id')->get();
    $byLength = $videos->sortByDesc(fn (AutoVideo $v): int => (int) mb_strlen((string) $v->caption))->values();

    expect(mb_strlen(HubText::compose($byLength[0]->caption, $byLength[0]->hashtags)))->toBe(2200)
        ->and($byLength[1]->caption)->toBeNull()
        ->and($byLength[1]->skip_reason)->toContain('2200')
        ->and($this->lib->reserveNext($this->account)?->id)->toBe($byLength[0]->id)
        ->and($this->lib->reserveNext($this->account))->toBeNull();
});

it('CaptionService từ chối video không có caption và lớp AI đã bị xoá', function (): void {
    $v = AutoVideo::create([
        'hash' => 'h1', 'path' => '/x.mp4', 'batch_date' => '2026-11-10', 'file_name' => 'x.mp4', 'product_code' => 'nano-dong', 'status' => 'new', 'hashtags' => [],
    ]);

    expect(fn () => app(CaptionService::class)->captionFor($v))->toThrow(RuntimeException::class, 'thiếu caption từ hub')
        ->and(class_exists('App\\Fork\\AutoPost\\Ai\\CaptionWriter'))->toBeFalse();
});

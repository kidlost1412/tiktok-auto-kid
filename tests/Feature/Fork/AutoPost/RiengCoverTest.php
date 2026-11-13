<?php

declare(strict_types=1);

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Hub\HubFiles;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Persona\CoverStore;
use App\Fork\AutoPost\Rieng\RiengBatch;
use App\Fork\AutoPost\Rieng\RiengCovers;
use App\Fork\AutoPost\Rieng\RiengFolder;
use App\Fork\AutoPost\Rieng\RiengThumbs;
use App\Fork\AutoPost\Scheduling\PostBuilder;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Storage;
use Symfony\Component\Process\Process;

/** Ảnh thật nhỏ (GD) để tải lên. */
function rcImage(string $type = 'jpg', int $w = 540, int $h = 960, ?int $red = null): UploadedFile
{
    $im = imagecreatetruecolor($w, $h);
    imagefill($im, 0, 0, (int) imagecolorallocate($im, $red ?? random_int(0, 255), 80, 120));
    $file = tempnam(sys_get_temp_dir(), 'rc').'.'.$type;
    match ($type) {
        'png' => imagepng($im, $file),
        'webp' => imagewebp($im, $file),
        default => imagejpeg($im, $file),
    };

    return new UploadedFile($file, 'bia.'.$type, null, null, true);
}

function rcOwner(): User
{
    $account = Account::factory()->create();
    $owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $owner->id]);
    $owner->update(['current_workspace_id' => $ws->id]);

    return $owner;
}

/** Tạo mp4 thật 2 giây bằng ffmpeg; null nếu máy không có ffmpeg. */
function rcRealVideo(string $dir): ?string
{
    $ffmpeg = app(RiengThumbs::class)->ffmpegPath();

    if ($ffmpeg === null) {
        return null;
    }

    $out = $dir.'/real.mp4';
    $p = new Process([$ffmpeg, '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=540x960:rate=10:duration=2', '-pix_fmt', 'yuv420p', $out]);
    $p->setTimeout(60);
    $p->run();

    return is_file($out) && filesize($out) > 0 ? $out : null;
}

beforeEach(function (): void {
    Storage::fake();
    Cache::flush();
    $tmp = str_replace('\\', '/', sys_get_temp_dir());
    $this->own = $tmp.'/rc-own-'.bin2hex(random_bytes(4));
    $this->covers = $tmp.'/rc-covers-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->own);
    config([
        'fork.auto.hub_path' => $tmp.'/rc-hub-'.bin2hex(random_bytes(4)), 'fork.auto.settle_seconds' => 0, 'fork.auto.hub_api.key' => '',
        'fork.auto.rieng_covers_dir' => $this->covers, 'trypost.self_hosted' => true,
    ]);

    $this->user = User::factory()->create();
    $this->workspace = Workspace::factory()->create(['user_id' => $this->user->id]);
    $this->now = CarbonImmutable::now('UTC')->addDays(2)->setTime(3, 0);
    $this->code = 'rc-'.bin2hex(random_bytes(3));
    $this->product = AutoProduct::create(['code' => $this->code, 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);

    $this->account = function (): SocialAccount {
        $account = SocialAccount::factory()->tiktok()->create([
            'workspace_id' => $this->workspace->id, 'status' => AccountStatus::Connected, 'timezone' => 'Asia/Ho_Chi_Minh',
        ]);
        ChromeAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'tiktok_user_id' => '777'.random_int(100, 999)]);
        AutoAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'daily_cap' => 20, 'window_start' => 6, 'window_end' => 23]);
        $pid = '17293847560'.random_int(10000000, 99999999);
        ShopProduct::create(['social_account_id' => $account->id, 'product_id' => $pid, 'source' => 'my_shop', 'title' => 'Nano Đồng 1L', 'stock_num' => 5, 'synced_at' => now()]);
        ProductLink::create(['social_account_id' => $account->id, 'auto_product_id' => $this->code, 'shop_product_id' => $pid, 'display_name' => 'Nano Đồng 1L']);

        return $account;
    };

    $this->rieng = function (string $name, ?string $content = null, array $attrs = []): AutoVideo {
        $path = $this->own.'/'.$name;
        $content ??= 'video-'.$name;
        file_put_contents($path, $content);

        return AutoVideo::create([
            'hash' => hash('sha256', $content), 'path' => $path, 'source' => 'rieng', 'batch_date' => '2026-11-09',
            'file_name' => $name, 'status' => 'new', 'meta' => ['folder_id' => 1, 'rel_path' => $name], ...$attrs,
        ]);
    };

    $this->input = fn (SocialAccount $a, array $items, array $extra = []): array => [
        'social_account_id' => $a->id, 'product_code' => $this->code, 'quy_cach' => null,
        'caption' => 'Caption chung', 'hashtags' => '#chung', 'mode' => 'auto',
        'items' => array_map(fn ($i) => is_array($i) ? $i : ['id' => $i->id], $items), ...$extra,
    ];
    $this->stage = fn (UploadedFile $f): string => app(RiengCovers::class)->stageUpload($f);
});

afterEach(function (): void {
    File::deleteDirectory($this->own);
    File::deleteDirectory($this->covers);
    File::deleteDirectory(CoverStore::dir($this->code));
});

// ---------------------------------------------------------------- Mặc định: bìa của sản phẩm

test('default mode keeps the product cover rotation and says so in the preview', function () {
    $account = ($this->account)();
    $res = app(CoverStore::class)->add($this->product, rcImage());
    $this->product->forceFill(['cover_images' => [$res['entry']], 'cover_mode' => 'fixed', 'cover_fixed' => $res['entry']['file']])->save();
    $a = ($this->rieng)('a.mp4');

    $options = app(RiengBatch::class)->productOptions((string) $account->id);
    $preview = app(RiengBatch::class)->preview(($this->input)($account, [$a]), $this->now);
    $done = app(RiengBatch::class)->commit(($this->input)($account, [$a]), false, $this->now);

    $post = Post::query()->findOrFail($a->refresh()->post_id);
    expect($options[0]['cover_count'])->toBe(1)
        ->and($preview['rows'][0]['cover']['kind'])->toBe('product')->and($preview['rows'][0]['cover']['url'])->toContain('/auto/anh-bia/')
        ->and($done['done'])->toBe(1)
        ->and($post->meta['fork_cover'])->toBe($res['entry']['file'])->and($post->meta)->not->toHaveKey('fork_cover_src')
        ->and(is_dir($this->covers.'/'.$a->id))->toBeFalse();
});

test('a product without covers falls back to the TikTok default cover and the dialog data says so', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');

    $options = app(RiengBatch::class)->productOptions((string) $account->id);
    $preview = app(RiengBatch::class)->preview(($this->input)($account, [$a]), $this->now);
    app(RiengBatch::class)->commit(($this->input)($account, [$a]), false, $this->now);

    $post = Post::query()->findOrFail($a->refresh()->post_id);
    expect($options[0]['cover_count'])->toBe(0)
        ->and($preview['rows'][0]['cover']['url'])->toBeNull()->and($preview['rows'][0]['cover']['note'])->toContain('chưa có ảnh bìa')
        ->and($post->meta)->not->toHaveKey('fork_cover');
});

// ---------------------------------------------------------------- Tải ảnh lên

test('an uploaded batch cover plus a per-video override reach the built posts and the chrome job', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');
    $b = ($this->rieng)('b.mp4');
    $shared = ($this->stage)(rcImage('jpg', 540, 960, 10));
    $own = ($this->stage)(rcImage('png', 800, 800, 200));

    $input = ($this->input)($account, [['id' => $a->id], ['id' => $b->id, 'cover_token' => $own]], ['cover_mode' => 'upload', 'cover_token' => $shared]);
    $preview = app(RiengBatch::class)->preview($input, $this->now);

    expect($preview['rows'][0]['cover'])->toMatchArray(['kind' => 'upload', 'url' => '/auto/kho/rieng/anh-bia/tam/'.$shared])
        ->and($preview['rows'][1]['cover']['url'])->toBe('/auto/kho/rieng/anh-bia/tam/'.$own)
        ->and(Post::query()->count())->toBe(0);

    $done = app(RiengBatch::class)->commit($input, false, $this->now);
    expect($done['done'])->toBe(2)->and($done['failed'])->toBe(0);

    $a->refresh();
    $b->refresh();
    $postA = Post::query()->findOrFail($a->post_id);
    $postB = Post::query()->findOrFail($b->post_id);
    $covers = app(RiengCovers::class);
    $fileA = $covers->path($a->id, $postA->meta['fork_cover']);
    $fileB = $covers->path($b->id, $postB->meta['fork_cover']);

    expect($postA->meta['fork_cover_src'])->toBe('rieng')->and($fileA)->not->toBeNull()->and($fileB)->not->toBeNull()
        ->and($a->meta['cover']['file'])->toBe($postA->meta['fork_cover'])->and($a->meta['cover']['kind'])->toBe('upload')
        ->and(hash_file('sha256', $fileA))->not->toBe(hash_file('sha256', $fileB))
        ->and(getimagesize($fileA)[0])->toBe(540)->and(getimagesize($fileA)[1])->toBe(720)      // 9:16 -> cắt giữa 3:4
        ->and(getimagesize($fileB)[0])->toBe(600)->and(getimagesize($fileB)[1])->toBe(800)      // png vuông -> jpg 3:4
        ->and(getimagesize($fileA)['mime'])->toBe('image/jpeg');

    // Đi cùng đường với bìa sản phẩm: payload job Chrome có options.cover trỏ tới /api/ext/cover.
    $job = app(ChromeJobs::class)->queueForPost($postA, 'now');
    $cover = app(ChromeJobs::class)->jobPayload($job, new ChromeClient(['tiktok_username' => 'u']))['options']['cover'];
    expect($cover)->toMatchArray(['url' => '/api/ext/cover?id='.$job->id, 'mime' => 'image/jpeg', 'size' => filesize($fileA), 'sha256' => hash_file('sha256', $fileA), 'width' => 540, 'height' => 720])
        ->and($job->options['cover']['src'])->toBe('rieng')->and($job->options['cover']['video'])->toBe($a->id);
});

test('upload mode without any picture refuses the row, and a vanished staged picture too', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');

    $none = app(RiengBatch::class)->preview(($this->input)($account, [$a], ['cover_mode' => 'upload']), $this->now);
    $gone = app(RiengBatch::class)->preview(($this->input)($account, [$a], ['cover_mode' => 'upload', 'cover_token' => '00000000-0000-0000-0000-000000000000.jpg']), $this->now);

    expect($none['rows'][0]['status'])->toBe('error')->and($none['rows'][0]['messages'][0])->toContain('Chưa có ảnh bìa')
        ->and($gone['rows'][0]['status'])->toBe('error')->and($gone['rows'][0]['messages'][0])->toContain('không còn');
});

test('the upload endpoint accepts jpg, png and webp and rejects other files, huge and tiny pictures', function () {
    $owner = rcOwner();

    foreach (['jpg', 'png', 'webp'] as $type) {
        $r = $this->actingAs($owner)->post('/auto/kho/rieng/anh-bia/tai-len', ['image' => rcImage($type)], ['Accept' => 'application/json']);
        $r->assertOk()->assertJsonPath('ok', true);
        $token = $r->json('token');
        expect(RiengCovers::validName($token))->toBeTrue()->and(is_file($this->covers.'/_tmp/'.$token))->toBeTrue();
        $this->actingAs($owner)->get($r->json('url'))->assertOk()->assertHeader('Content-Type', 'image/jpeg');
    }

    $text = UploadedFile::fake()->createWithContent('bia.jpg', 'not an image at all');
    $this->actingAs($owner)->post('/auto/kho/rieng/anh-bia/tai-len', ['image' => $text], ['Accept' => 'application/json'])->assertStatus(422);

    $gif = UploadedFile::fake()->create('bia.gif', 10, 'image/gif');
    $this->actingAs($owner)->post('/auto/kho/rieng/anh-bia/tai-len', ['image' => $gif], ['Accept' => 'application/json'])->assertStatus(422)->assertJsonValidationErrors('image');

    $big = UploadedFile::fake()->create('bia.jpg', 6 * 1024, 'image/jpeg');
    $this->actingAs($owner)->post('/auto/kho/rieng/anh-bia/tai-len', ['image' => $big], ['Accept' => 'application/json'])->assertStatus(422);

    // Quá nhỏ sau khi cắt 3:4 (cùng luật với ảnh bìa sản phẩm).
    $this->actingAs($owner)->post('/auto/kho/rieng/anh-bia/tai-len', ['image' => rcImage('jpg', 200, 300)], ['Accept' => 'application/json'])
        ->assertStatus(422)->assertJsonPath('ok', false);

    $this->actingAs($owner)->get('/auto/kho/rieng/anh-bia/tam/khong-hop-le.jpg')->assertNotFound();
    expect(glob($this->covers.'/_tmp/*.jpg'))->toHaveCount(3);
});

// ---------------------------------------------------------------- Chọn khung trong video

test('frame mode extracts a full-size frame at the chosen second, and the default frame when untouched', function () {
    $real = rcRealVideo($this->own);

    if ($real === null) {
        $this->markTestSkipped('Máy không có ffmpeg.');
    }

    $account = ($this->account)();
    $a = AutoVideo::create(['hash' => 'h-a', 'path' => $real, 'source' => 'rieng', 'batch_date' => '2026-11-09', 'file_name' => 'real.mp4', 'status' => 'new', 'duration' => 2.0, 'meta' => ['folder_id' => 1]]);
    copy($real, $this->own.'/real2.mp4');
    $b = AutoVideo::create(['hash' => 'h-b', 'path' => $this->own.'/real2.mp4', 'source' => 'rieng', 'batch_date' => '2026-11-09', 'file_name' => 'real2.mp4', 'status' => 'new', 'duration' => 2.0, 'meta' => ['folder_id' => 1]]);

    $r = $this->actingAs(rcOwner())->postJson("/auto/kho/rieng/video/{$a->id}/khung", ['t' => 1.5]);
    $r->assertOk()->assertJsonPath('ok', true);
    $token = $r->json('token');
    $size = getimagesize($this->covers.'/_tmp/'.$token);
    expect($size[0])->toBe(540)->and($size[1])->toBe(720);

    // Video a: khung đã chọn; video b: không đụng gì => khung mặc định (giây 1).
    $input = ($this->input)($account, [['id' => $a->id, 'cover_token' => $token], ['id' => $b->id]], ['cover_mode' => 'frame']);
    $preview = app(RiengBatch::class)->preview($input, $this->now);
    expect($preview['rows'][0]['cover']['note'])->toBe('Khung đã chọn')
        ->and($preview['rows'][1]['cover']['url'])->toBe("/auto/kho/rieng/video/{$b->id}/thumb");

    $done = app(RiengBatch::class)->commit($input, false, $this->now);
    expect($done['done'])->toBe(2);

    foreach ([$a, $b] as $v) {
        $post = Post::query()->findOrFail($v->refresh()->post_id);
        $file = app(RiengCovers::class)->path($v->id, $post->meta['fork_cover']);
        expect($post->meta['fork_cover_src'])->toBe('rieng')->and($file)->not->toBeNull()->and($v->meta['cover']['kind'])->toBe('frame');
    }

    // Một t âm bị chặn.
    $this->actingAs(rcOwner())->postJson("/auto/kho/rieng/video/{$a->id}/khung", ['t' => -1])->assertStatus(422);
});

test('frame mode with an unreadable video fails that row cleanly and returns the video to the store', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('fake.mp4');   // nội dung không phải video

    $input = ($this->input)($account, [$a], ['cover_mode' => 'frame']);
    $preview = app(RiengBatch::class)->preview($input, $this->now);
    $done = app(RiengBatch::class)->commit($input, false, $this->now);

    // Có ffmpeg: lỗi lúc lấy khung (dòng 'Ảnh bìa lỗi'); không có ffmpeg: bị chặn ngay ở bước xem trước.
    expect($done['done'])->toBe(0)->and($a->refresh()->status)->toBe('new')->and($a->meta)->not->toHaveKey('cover')
        ->and(Post::query()->count())->toBe(0)->and(is_dir($this->covers.'/'.$a->id))->toBeFalse()
        ->and($preview['rows'][0]['status'] === 'error' || str_contains((string) ($done['rows'][0]['error'] ?? ''), 'Ảnh bìa lỗi'))->toBeTrue();
});

// ---------------------------------------------------------------- Dọn dẹp

test('removing the folder or deleting a private video deletes its cover files', function () {
    $folder = RiengFolder::create(['path' => $this->own]);
    $a = ($this->rieng)('a.mp4', null, ['meta' => ['folder_id' => $folder->id]]);
    $b = ($this->rieng)('b.mp4', null, ['meta' => ['folder_id' => $folder->id]]);
    $c = ($this->rieng)('c.mp4', null, ['meta' => ['folder_id' => 99]]);
    $covers = app(RiengCovers::class);

    foreach ([$a, $b, $c] as $v) {
        $covers->attach($v, ($this->stage)(rcImage()));
        expect(glob($this->covers.'/'.$v->id.'/*.jpg'))->toHaveCount(1);
    }

    $this->actingAs(rcOwner())->delete('/auto/kho/rieng/thu-muc/'.$folder->id)->assertRedirect();
    expect(is_dir($this->covers.'/'.$a->id))->toBeFalse()->and(is_dir($this->covers.'/'.$b->id))->toBeFalse()
        ->and(is_dir($this->covers.'/'.$c->id))->toBeTrue();

    $c->delete();
    expect(is_dir($this->covers.'/'.$c->id))->toBeFalse();
});

test('covers of a posted private video are kept exactly as long as its post media', function () {
    $account = ($this->account)();
    $a = ($this->rieng)('a.mp4');
    app(RiengBatch::class)->commit(($this->input)($account, [$a], ['cover_mode' => 'upload', 'cover_token' => ($this->stage)(rcImage())]), false, $this->now);
    $a->refresh();
    $post = Post::query()->findOrFail($a->post_id);

    // Mới đăng xong: chưa quá hạn => còn bìa.
    $post->forceFill(['status' => PostStatus::Published, 'published_at' => now()])->save();
    $a->forceFill(['status' => 'posted', 'posted_at' => now()])->save();
    app(HubFiles::class)->cleanupPostedMedia('7');
    expect(glob($this->covers.'/'.$a->id.'/*.jpg'))->toHaveCount(1);

    // Quá hạn lưu giữ => media và bìa cùng bị dọn.
    $post->forceFill(['published_at' => now()->subDays(10)])->save();
    $a->forceFill(['posted_at' => now()->subDays(10)])->save();
    app(HubFiles::class)->cleanupPostedMedia('7');
    expect(is_dir($this->covers.'/'.$a->id))->toBeFalse();
});

// ---------------------------------------------------------------- Video hub không đổi

test('a hub video built without an override never gets a rieng cover source', function () {
    $account = ($this->account)();
    $res = app(CoverStore::class)->add($this->product, rcImage());
    $this->product->forceFill(['cover_images' => [$res['entry']], 'cover_mode' => 'fixed', 'cover_fixed' => $res['entry']['file']])->save();
    $path = $this->own.'/hub.mp4';
    file_put_contents($path, 'hub-bytes');
    $video = AutoVideo::create(['hash' => 'hubv', 'path' => $path, 'source' => 'hub', 'batch_date' => '2026-11-09', 'file_name' => 'hub.mp4', 'product_code' => $this->code, 'status' => 'new', 'caption' => 'Cap hub', 'hashtags' => []]);

    $post = app(PostBuilder::class)->build($account->load('workspace'), $video, ['caption' => 'Cap hub', 'hashtags' => [], 'source' => 'hub'], $this->now);

    expect($post->meta['fork_cover'])->toBe($res['entry']['file'])->and($post->meta)->not->toHaveKey('fork_cover_src');
    $cover = app(CoverStore::class)->forPost($post);
    expect($cover['code'])->toBe($this->code)->and($cover)->not->toHaveKey('src');
});

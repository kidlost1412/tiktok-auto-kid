<?php

declare(strict_types=1);

use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductCover;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Persona\CoverStore;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Scheduling\PostBuilder;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Storage;
use Illuminate\Testing\TestResponse;

/** Ảnh thật nhỏ (GD) để tải lên. */
function pnImage(string $type = 'jpg', int $w = 540, int $h = 960, string $name = 'bia'): UploadedFile
{
    $im = imagecreatetruecolor($w, $h);
    imagefill($im, 0, 0, (int) imagecolorallocate($im, random_int(0, 255), 80, 120));
    $file = tempnam(sys_get_temp_dir(), 'pn').'.'.$type;
    match ($type) {
        'png' => imagepng($im, $file),
        'webp' => imagewebp($im, $file),
        default => imagejpeg($im, $file),
    };

    return new UploadedFile($file, $name.'.'.$type, null, null, true);
}

/** Bộ ảnh bìa của sản phẩm trên một kênh (mặc định kênh $t->sa). */
function pnCover(object $t, ?SocialAccount $sa = null): ProductCover
{
    return ProductCover::for(($sa ?? $t->sa)->id, $t->code);
}

/** Tải ảnh lên cho một kênh. */
function pnUpload(object $t, array $images, ?SocialAccount $sa = null): TestResponse
{
    return $t->actingAs($t->owner)->post("/auto/products/{$t->code}/covers", ['kenh' => ($sa ?? $t->sa)->id, 'images' => $images]);
}

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    Storage::fake();

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);

    $this->code = 'pn-'.bin2hex(random_bytes(4));
    $this->product = AutoProduct::query()->create(['code' => $this->code, 'name' => 'Đạm cá', 'short_name' => 'Đạm cá', 'facts' => [], 'enabled' => true]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh']);
});

afterEach(function (): void {
    File::deleteDirectory(CoverStore::dir($this->code));
});

// ---------------------------------------------------------------- hashtag

test('append adds product hashtags after the hub ones and dedupes case-insensitively against caption and hub tags', function (): void {
    $this->product->update(['hashtags' => ['#DamCa', '#phanbon', '#moi'], 'hashtag_mode' => 'append']);

    $out = app(Hashtags::class)->apply('Cây khoẻ #damca nhé', ['#PHANBON', '#hub'], $this->product->fresh());

    expect($out['caption'])->toBe('Cây khoẻ #damca nhé')
        ->and($out['hashtags'])->toBe(['#PHANBON', '#hub', '#moi']);
});

test('replace strips the caption hashtags and hub hashtags, keeping the sentence text', function (): void {
    $this->product->update(['hashtags' => ['#a', '#b'], 'hashtag_mode' => 'replace']);

    $out = app(Hashtags::class)->apply("Dòng một #cu1 giữ chữ C#\n\nDòng hai #cu2", ['#hub'], $this->product->fresh());

    expect($out['caption'])->toBe("Dòng một giữ chữ C#\n\nDòng hai")
        ->and($out['hashtags'])->toBe(['#a', '#b'])
        ->and(HubText::compose($out['caption'], $out['hashtags']))->toBe("Dòng một giữ chữ C#\n\nDòng hai\n\n#a #b");
});

test('replace keeps a hashtag-only caption instead of making it empty', function (): void {
    $this->product->update(['hashtags' => ['#a'], 'hashtag_mode' => 'replace']);

    $out = app(Hashtags::class)->apply('#chi #hashtag', [], $this->product->fresh());

    expect($out['caption'])->toBe('#chi #hashtag')->and($out['hashtags'])->toBe(['#a']);
});

test('pick N chooses N distinct tags from the list each time, 0 means all', function (): void {
    $tags = ['#a', '#b', '#c', '#d', '#e', '#f'];
    $this->product->update(['hashtags' => $tags, 'hashtag_mode' => 'append', 'hashtag_pick' => 2]);
    $seen = [];

    for ($i = 0; $i < 40; $i++) {
        $out = app(Hashtags::class)->apply('x', [], $this->product->fresh());
        expect($out['hashtags'])->toHaveCount(2)->and(array_unique($out['hashtags']))->toHaveCount(2)->and(array_diff($out['hashtags'], $tags))->toBe([]);
        $seen[implode(' ', $out['hashtags'])] = true;
    }

    expect(count($seen))->toBeGreaterThan(1);

    $this->product->update(['hashtag_pick' => 0]);
    expect(app(Hashtags::class)->apply('x', [], $this->product->fresh())['hashtags'])->toBe($tags);
});

test('without own hashtags the global default applies, and with neither the text is untouched', function (): void {
    $plain = app(Hashtags::class)->apply('Caption #hub', ['#h2'], $this->product);
    expect($plain)->toBe(['caption' => 'Caption #hub', 'hashtags' => ['#h2']]);

    Hashtags::saveDefaults('#chung1 #chung2', 'append', 0);

    $out = app(Hashtags::class)->apply('Caption', [], $this->product->fresh());
    expect($out['hashtags'])->toBe(['#chung1', '#chung2']);

    $this->product->update(['hashtags' => ['#rieng']]);
    expect(app(Hashtags::class)->apply('Caption', [], $this->product->fresh())['hashtags'])->toBe(['#rieng']);
});

test('normalize cleans input: leading #, symbols, commas, duplicates, empties', function (): void {
    expect(Hashtags::normalize("#Đạm-cá, ##phan_bon  #phan_bon\n#  #@@ cay"))->toBe(['#Đạmcá', '#phan_bon', '#cay']);
});

test('the 2200 character limit is kept by dropping added tags, never caption text', function (): void {
    $this->product->update(['hashtags' => ['#aaaa', '#bbbb', '#cccc'], 'hashtag_mode' => 'append']);
    $caption = str_repeat('a', 2185);

    $out = app(Hashtags::class)->apply($caption, [], $this->product->fresh());

    expect($out['caption'])->toBe($caption)
        ->and(mb_strlen(HubText::compose($out['caption'], $out['hashtags'])))->toBeLessThanOrEqual(2200)
        ->and($out['hashtags'])->toBe(['#aaaa', '#bbbb']);
});

test('preview endpoint returns the final caption for a draft config, owner only', function (): void {
    $this->actingAs($this->owner)->postJson("/auto/products/{$this->code}/personalise/preview", [
        'sample' => 'Chào #cu', 'hashtags' => '#moi1 #moi2', 'hashtag_mode' => 'replace', 'hashtag_pick' => 0,
    ])->assertOk()->assertJsonPath('text', "Chào\n\n#moi1 #moi2");

    $member = User::factory()->create(['account_id' => $this->account->id]);
    $this->actingAs($member)->postJson("/auto/products/{$this->code}/personalise/preview", ['sample' => 'x'])->assertForbidden();
});

// ---------------------------------------------------------------- upload + storage

test('upload validates, converts png/webp to jpg, warns about non 9:16 and lists previews', function (): void {
    pnUpload($this, [pnImage('png', 540, 960, 'a'), pnImage('webp', 600, 600, 'b'), pnImage('jpg', 540, 960, 'c')])
        ->assertRedirect()->assertSessionHas('flash.success');

    $p = pnCover($this);
    expect($p->cover_images)->toHaveCount(3);

    foreach ($p->cover_images as $img) {
        $path = CoverStore::pathFor($p, $img['file']);
        expect($path)->not->toBeNull()->and(getimagesize($path)[2])->toBe(IMAGETYPE_JPEG)->and($img['file'])->toEndWith('.jpg');
    }

    $this->actingAs($this->owner)->get($p->cover_images[0]['file'] ? '/auto/anh-bia/'.$this->code.'/'.$p->cover_images[0]['file'] : '/x')
        ->assertOk()->assertHeader('Content-Type', 'image/jpeg');
});

test('upload refuses non-images, tiny images and files over 5 MB; nothing is stored', function (): void {
    $txt = UploadedFile::fake()->create('x.txt', 5, 'text/plain');
    pnUpload($this, [$txt])->assertSessionHasErrors('images.0');

    $big = UploadedFile::fake()->create('big.jpg', 5121, 'image/jpeg');
    pnUpload($this, [$big])->assertSessionHasErrors('images.0');

    pnUpload($this, [pnImage('jpg', 100, 100)])->assertSessionHas('flash.error');

    expect(pnCover($this)->cover_images ?? [])->toBe([]);
});

test('only the account owner can upload, delete or change settings', function (): void {
    $member = User::factory()->create(['account_id' => $this->account->id]);

    $this->actingAs($member)->post("/auto/products/{$this->code}/covers", ['kenh' => $this->sa->id, 'images' => [pnImage()]])->assertForbidden();
    $this->actingAs($member)->put("/auto/products/{$this->code}/personalise", ['kenh' => $this->sa->id, 'cover_mode' => 'random'])->assertForbidden();
    $this->actingAs($member)->put('/auto/hashtag-mac-dinh', ['hashtag_mode' => 'append', 'hashtag_pick' => 0])->assertForbidden();
    $this->actingAs($member)->get("/auto/anh-bia/{$this->code}/x.jpg")->assertForbidden();
    expect(pnCover($this)->cover_mode)->toBe('default');
});

test('delete removes the file and clears fixed/last references; settings save normalises hashtags', function (): void {
    pnUpload($this, [pnImage('jpg', 540, 960, 'a'), pnImage('jpg', 540, 960, 'b')]);
    $p = pnCover($this);
    [$one, $two] = array_column($p->cover_images, 'file');
    $path = CoverStore::pathFor($p, $one);
    $k = $this->sa->id;

    $this->actingAs($this->owner)->put("/auto/products/{$this->code}/personalise", [
        'kenh' => $k, 'cover_mode' => 'fixed', 'cover_fixed' => $one, 'hashtags' => '#A, b  #a', 'hashtag_mode' => 'replace', 'hashtag_pick' => 1,
    ])->assertRedirect();

    $p = pnCover($this);
    $prod = $this->product->fresh();
    expect($p->cover_mode)->toBe('fixed')->and($p->cover_fixed)->toBe($one)->and($prod->hashtags)->toBe(['#A', '#b'])
        ->and($prod->hashtag_mode)->toBe('replace')->and($prod->hashtag_pick)->toBe(1);

    $this->actingAs($this->owner)->delete("/auto/products/{$this->code}/covers/{$one}?kenh={$k}")->assertRedirect();

    $p = pnCover($this);
    expect(file_exists($path))->toBeFalse()->and($p->cover_fixed)->toBeNull()->and(array_column($p->cover_images, 'file'))->toBe([$two]);
    $this->actingAs($this->owner)->delete("/auto/products/{$this->code}/covers/nope.jpg?kenh={$k}")->assertNotFound();
});

// ---------------------------------------------------------------- selection

test('default mode picks nothing; fixed always returns the chosen image', function (): void {
    $store = app(CoverStore::class);
    pnUpload($this, [pnImage('jpg', 540, 960, 'a'), pnImage('jpg', 540, 960, 'b')]);
    $p = pnCover($this);
    [$one, $two] = array_column($p->cover_images, 'file');

    expect($store->pick($p))->toBeNull();

    $p->update(['cover_mode' => 'fixed', 'cover_fixed' => $two]);
    expect($store->pick($p->fresh()))->toBe($two)->and($store->pick($p->fresh()))->toBe($two);

    $p->update(['cover_fixed' => null]);
    expect($store->pick($p->fresh()))->toBe($one);
});

test('random never repeats the previous image when there are two or more, and works with one', function (): void {
    $store = app(CoverStore::class);
    pnUpload($this, [pnImage('jpg', 540, 960, 'a'), pnImage('jpg', 540, 960, 'b'), pnImage('jpg', 540, 960, 'c')]);
    pnCover($this)->update(['cover_mode' => 'random']);

    $prev = null;
    $seen = [];

    for ($i = 0; $i < 60; $i++) {
        $f = $store->pick(pnCover($this));
        expect($f)->not->toBeNull()->and($f)->not->toBe($prev);
        $seen[$f] = true;
        $prev = $f;
    }

    expect($seen)->toHaveCount(3);

    $only = pnCover($this);
    $keep = $only->cover_images[0];
    $only->update(['cover_images' => [$keep], 'cover_last' => $keep['file']]);
    expect($store->pick($only->fresh()))->toBe($keep['file'])->and($store->pick($only->fresh()))->toBe($keep['file']);
});

test('random spreads picks evenly over a small set (repeats allowed, never back-to-back)', function (): void {
    $store = app(CoverStore::class);

    foreach ([2, 3] as $n) {
        AutoProduct::query()->create(['code' => $this->code.'-'.$n, 'name' => 'X', 'short_name' => 'X', 'facts' => [], 'enabled' => true]);
        $p = ProductCover::for($this->sa->id, $this->code.'-'.$n);
        $images = [];

        for ($k = 0; $k < $n; $k++) {
            $images[] = $store->add($p, pnImage('jpg', 540, 960, 'i'.$k))['entry'];
            $p->forceFill(['cover_images' => $images])->save();
        }

        $p->update(['cover_mode' => 'random']);
        $counts = array_fill_keys(array_column($images, 'file'), 0);
        $prev = null;

        for ($i = 0; $i < 10 * $n + 1; $i++) {
            $f = $store->pick($p->fresh());
            expect($f)->not->toBe($prev);
            $counts[$f]++;
            $prev = $f;
        }

        // 10n+1 lần bốc: chênh lệch giữa ảnh dùng nhiều nhất và ít nhất tối đa 1.
        expect(max($counts) - min($counts))->toBeLessThanOrEqual(1);
        File::deleteDirectory(CoverStore::dir($this->code.'-'.$n));
    }
});

// ---------------------------------------------------------------- build + job

function pnBuild(object $t, ?SocialAccount $sa = null): array
{
    $hub = str_replace('\\', '/', sys_get_temp_dir()).'/pn-hub-'.bin2hex(random_bytes(4));
    mkdir($hub, 0777, true);
    file_put_contents($hub.'/v.mp4', 'video-bytes');

    $sa ??= $t->sa;
    ChromeAccount::query()->firstOrCreate(['social_account_id' => $sa->id], ['enabled' => true, 'tiktok_user_id' => '7'.random_int(100000000000, 999999999999)]);
    AutoAccount::query()->firstOrCreate(['social_account_id' => $sa->id], ['enabled' => true, 'daily_cap' => 20]);
    ShopProduct::query()->firstOrCreate(['social_account_id' => $sa->id, 'product_id' => '1729384756001234567'], ['source' => 'my_shop', 'title' => 'SP', 'stock_num' => 5, 'synced_at' => now()]);
    ProductLink::query()->firstOrCreate(['social_account_id' => $sa->id, 'auto_product_id' => $t->code], ['shop_product_id' => '1729384756001234567', 'display_name' => 'SP']);

    $video = AutoVideo::create([
        'hash' => bin2hex(random_bytes(8)), 'path' => $hub.'/v.mp4', 'batch_date' => '2026-11-09', 'file_name' => 'v.mp4',
        'product_code' => $t->code, 'goc' => 'g', 'status' => 'new', 'caption' => 'Caption hub', 'hashtags' => ['#hub'], 'caption_source' => 'hub',
    ]);

    $post = app(PostBuilder::class)->build($sa->load('workspace'), $video, ['caption' => 'Caption hub #cu', 'hashtags' => ['#hub'], 'source' => 'hub'], CarbonImmutable::now('UTC')->addDays(2));
    $post->forceFill(['meta' => [...$post->meta, 'privacy_level' => 'PUBLIC_TO_EVERYONE']])->save();

    return [$post, $video, $sa];
}

test('the post builder applies the hashtags to the post text and records the chosen cover, keeping hub text on the video', function (): void {
    pnUpload($this, [pnImage()]);
    pnCover($this)->update(['cover_mode' => 'random']);
    $this->product->update(['hashtags' => ['#moi'], 'hashtag_mode' => 'replace']);

    [$post, $video] = pnBuild($this);

    expect($post->content)->toBe("Caption hub\n\n#moi")
        ->and($post->meta['fork_cover'])->toBe(pnCover($this)->cover_images[0]['file'])
        ->and($video->fresh()->caption)->toBe('Caption hub #cu')
        ->and($video->fresh()->hashtags)->toBe(['#hub']);
});

test('without personalisation the post text and meta are exactly as before', function (): void {
    [$post] = pnBuild($this);

    expect($post->content)->toBe("Caption hub #cu\n\n#hub")->and($post->meta)->not->toHaveKey('fork_cover');
});

test('the chrome job payload carries options.cover for a personalised post and none otherwise', function (): void {
    pnUpload($this, [pnImage()]);
    pnCover($this)->update(['cover_mode' => 'fixed']);
    [$post] = pnBuild($this);

    $job = app(ChromeJobs::class)->queueForPost($post, 'now');
    $client = new ChromeClient(['tiktok_username' => 'u']);
    $cover = app(ChromeJobs::class)->jobPayload($job, $client)['options']['cover'];
    $path = CoverStore::pathFor(pnCover($this), $post->meta['fork_cover']);

    expect($cover)->toMatchArray(['url' => '/api/ext/cover?id='.$job->id, 'mime' => 'image/jpeg', 'size' => filesize($path), 'sha256' => hash_file('sha256', $path), 'width' => 540, 'height' => 960])
        ->and($cover)->not->toHaveKey('field')
        ->and($job->options['cover']['code'])->toBe($this->code)
        ->and($job->options['cover']['account'])->toBe($this->sa->id);

    // Công tắc an toàn: tắt thì không gửi bìa.
    $job->delete(); // một kênh chỉ có một bài chờ Chrome tại một thời điểm
    pnCover($this)->update(['cover_mode' => 'default']);
    [$post2] = pnBuild($this);
    $job2 = app(ChromeJobs::class)->queueForPost($post2, 'now');
    expect(app(ChromeJobs::class)->jobPayload($job2, $client)['options'])->not->toHaveKey('cover');
});

test('the default hashtags page props and save work', function (): void {
    $this->actingAs($this->owner)->put('/auto/hashtag-mac-dinh', ['hashtags' => '#x #y', 'hashtag_mode' => 'replace', 'hashtag_pick' => 1])->assertRedirect();

    expect(Hashtags::defaults())->toBe(['tags' => ['#x', '#y'], 'mode' => 'replace', 'pick' => 1])
        ->and(AutoSetting::read('persona.hashtag_mode'))->toBe('replace');
});

test('the Giỏ hàng page exposes the per-product state and the default hashtags to the owner', function (): void {
    $sa = $this->sa;
    ChromeAccount::query()->create(['social_account_id' => $sa->id, 'enabled' => true, 'tiktok_user_id' => '777']);
    $this->product->update(['hashtags' => ['#a']]);
    pnCover($this)->forceFill(['cover_mode' => 'random'])->save();
    Hashtags::saveDefaults('#chung', 'append', 2);

    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn ($p) => $p
        ->where("personalise.{$this->code}.cover_mode", 'random')
        ->where("personalise.{$this->code}.hashtags", ['#a'])
        ->where('personalise_default.tags', ['#chung'])
        ->where('personalise_default.pick', 2));
});

test('covers keep 3:4 / 9:16, otherwise are center-cropped to the nearest, stored as jpg with the final size', function (): void {
    pnUpload($this, [
        pnImage('jpg', 1080, 1920, 'tall'), pnImage('png', 1600, 900, 'wide'), pnImage('webp', 2160, 2880, 'big'), pnImage('jpg', 540, 720, 'exact'),
        pnImage('png', 1000, 1000, 'square'), pnImage('jpg', 1000, 3000, 'verytall'), pnImage('jpg', 2160, 3840, 'big916'),
    ])->assertRedirect()->assertSessionHas('flash.success');

    $p = pnCover($this);
    $dims = collect($p->cover_images)->map(fn ($i): array => [$i['w'], $i['h']])->all();

    // 9:16 giữ nguyên; 16:9 -> 3:4; 3:4 lớn thu nhỏ; 3:4 đúng giữ; vuông -> 3:4; rất cao 1:3 -> cắt trên dưới còn 9:16; 9:16 lớn thu về 1080x1920.
    expect($dims)->toBe([[1080, 1920], [675, 900], [1080, 1440], [540, 720], [750, 1000], [1000, 1778], [1080, 1920]]);

    foreach ($p->cover_images as $img) {
        $size = getimagesize(CoverStore::pathFor($p, $img['file']));
        expect([$size[0], $size[1]])->toBe([$img['w'], $img['h']])->and($size[2])->toBe(IMAGETYPE_JPEG);
    }

    expect($p->cover_images[0])->toMatchArray(['orig_w' => 1080, 'orig_h' => 1920]);
});

test('planCrop keeps 3:4 and 9:16 within 3 percent, else crops to the closer one', function (): void {
    expect(CoverStore::planCrop(1080, 1920))->toBe([1080, 1920])
        ->and(CoverStore::planCrop(600, 800))->toBe([600, 800])
        ->and(CoverStore::planCrop(1080, 1900))->toBe([1080, 1900])      // 1,1% lệch 9:16: giữ
        ->and(CoverStore::planCrop(1000, 1000))->toBe([750, 1000])
        ->and(CoverStore::planCrop(1000, 3000))->toBe([1000, 1778])
        ->and(CoverStore::planCrop(1080, 1500))->toBe([1080, 1440]);    // 0,72: lệch 4% so với 3:4, gần 3:4 hơn
});

test('cropSize keeps 3:4 for tall and wide sources', function (): void {
    expect(CoverStore::cropSize(1080, 1920))->toBe([1080, 1440])
        ->and(CoverStore::cropSize(1600, 900))->toBe([675, 900])
        ->and(CoverStore::cropSize(600, 800))->toBe([600, 800]);
});

test('Studio minimum 324x432 is enforced on the cropped result, by exact boundary', function (): void {
    $try = fn (int $w, int $h): bool => pnUpload($this, [pnImage('jpg', $w, $h)])->getSession()->has('flash.success');

    expect($try(324, 432))->toBeTrue()
        ->and($try(323, 432))->toBeFalse()      // 323x431 after the crop
        ->and($try(324, 431))->toBeFalse()
        ->and($try(1000, 431))->toBeFalse()     // wide but too short: crop is 323x431
        ->and($try(540, 960))->toBeTrue()
        ->and($try(324, 576))->toBeTrue()       // 9:16 tối thiểu
        ->and($try(324, 575))->toBeFalse()
        ->and($try(323, 575))->toBeFalse();
    expect(count(pnCover($this)->cover_images))->toBe(3);

    pnUpload($this, [pnImage('jpg', 300, 400)])
        ->assertSessionHas('flash.error', fn ($m): bool => str_contains($m, '324×432'));
});

test('describe exposes the original size so the dialog can show what was cropped', function (): void {
    pnUpload($this, [
        pnImage('jpg', 1080, 1500, 'tall'),
    ])->assertRedirect();

    $p = pnCover($this);
    $p->update(['cover_images' => [...$p->cover_images, ['file' => 'old.jpg', 'name' => 'old', 'w' => 540, 'h' => 720]]]);

    $described = app(CoverStore::class)->describe($p->fresh());

    expect($described[0])->toMatchArray(['w' => 1080, 'h' => 1440, 'orig_w' => 1080, 'orig_h' => 1500])
        ->and($described[1])->toMatchArray(['orig_w' => null, 'orig_h' => null]);
});

// ---------------------------------------------------------------- ảnh bìa theo kênh

/** Kênh thứ hai của chủ app, cùng liên kết sản phẩm. */
function pnSecondChannel(object $t): SocialAccount
{
    return SocialAccount::factory()->tiktok()->create(['workspace_id' => $t->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh']);
}

test('covers are per channel: two channels with the same product never share or overwrite each other', function (): void {
    $b = pnSecondChannel($this);
    $url = "/auto/products/{$this->code}/personalise";

    pnUpload($this, [pnImage()])->assertRedirect()->assertSessionHas('flash.success');
    $a1 = pnCover($this)->cover_images[0]['file'];
    $this->actingAs($this->owner)->put($url, ['kenh' => $this->sa->id, 'cover_mode' => 'fixed', 'cover_fixed' => $a1])->assertRedirect();

    // B chưa đụng gì: không có ảnh, chế độ mặc định.
    expect(pnCover($this, $b)->exists)->toBeFalse()->and(pnCover($this, $b)->cover_mode)->toBe('default');

    [$postA] = pnBuild($this, $this->sa);
    [$postB] = pnBuild($this, $b);
    expect($postA->meta['fork_cover'])->toBe($a1)->and($postB->meta)->not->toHaveKey('fork_cover');

    // B tải ảnh riêng và chọn cố định: B dùng ảnh của B, A giữ nguyên.
    pnUpload($this, [pnImage('jpg', 540, 960, 'b')], $b)->assertRedirect()->assertSessionHas('flash.success');
    $b1 = pnCover($this, $b)->cover_images[0]['file'];
    $this->actingAs($this->owner)->put($url, ['kenh' => $b->id, 'cover_mode' => 'fixed', 'cover_fixed' => $b1])->assertRedirect();

    expect($b1)->not->toBe($a1)->and(pnCover($this)->cover_images)->toHaveCount(1)->and(pnCover($this)->cover_fixed)->toBe($a1);

    [$postA2] = pnBuild($this, $this->sa);
    [$postB2] = pnBuild($this, $b);
    expect($postA2->meta['fork_cover'])->toBe($a1)->and($postB2->meta['fork_cover'])->toBe($b1);

    // Bìa gửi cho tiện ích mang theo kênh của bài.
    expect(app(CoverStore::class)->forPost($postB2))->toMatchArray(['code' => $this->code, 'account' => $b->id, 'file' => $b1]);

    // Xoá ảnh của A không ảnh hưởng B; B không xoá được ảnh của A.
    $this->actingAs($this->owner)->delete("/auto/products/{$this->code}/covers/{$a1}?kenh={$b->id}")->assertNotFound();
    $this->actingAs($this->owner)->delete("/auto/products/{$this->code}/covers/{$a1}?kenh={$this->sa->id}")->assertRedirect();
    expect(pnCover($this)->cover_images)->toBe([])->and(pnCover($this, $b)->cover_images)->toHaveCount(1);

    // Ảnh phục vụ theo tên file riêng của từng kênh.
    $this->actingAs($this->owner)->get("/auto/anh-bia/{$this->code}/{$b1}")->assertOk()->assertHeader('Content-Type', 'image/jpeg');
});

test('cover endpoints need a channel: 422 without kenh, 404 for a channel the owner does not have', function (): void {
    $other = Account::factory()->create();
    $otherOwner = User::factory()->create(['account_id' => $other->id]);
    $other->update(['owner_id' => $otherOwner->id]);
    $otherWs = Workspace::factory()->create(['account_id' => $other->id, 'user_id' => $otherOwner->id]);
    $foreign = SocialAccount::factory()->tiktok()->create(['workspace_id' => $otherWs->id]);
    $url = "/auto/products/{$this->code}/personalise";

    $this->actingAs($this->owner)->postJson("/auto/products/{$this->code}/covers", ['images' => [pnImage()]])->assertStatus(422);
    $this->actingAs($this->owner)->putJson($url, ['cover_mode' => 'random'])->assertStatus(422);
    $this->actingAs($this->owner)->putJson($url, ['cover_fixed' => null])->assertStatus(422);
    $this->actingAs($this->owner)->deleteJson("/auto/products/{$this->code}/covers/x.jpg")->assertStatus(422);

    $this->actingAs($this->owner)->postJson("/auto/products/{$this->code}/covers", ['kenh' => $foreign->id, 'images' => [pnImage()]])->assertNotFound();
    $this->actingAs($this->owner)->putJson($url, ['kenh' => $foreign->id, 'cover_mode' => 'random'])->assertNotFound();
    $this->actingAs($this->owner)->deleteJson("/auto/products/{$this->code}/covers/x.jpg?kenh={$foreign->id}")->assertNotFound();
    $this->actingAs($this->owner)->postJson("/auto/products/{$this->code}/covers", ['kenh' => 'khong-co', 'images' => [pnImage()]])->assertNotFound();

    expect(ProductCover::query()->count())->toBe(0);

    // Chỉ lưu hashtag (không đụng bìa) vẫn không cần kênh.
    $this->actingAs($this->owner)->put($url, ['hashtags' => '#x', 'hashtag_mode' => 'append', 'hashtag_pick' => 0])->assertRedirect();
    expect($this->product->fresh()->hashtags)->toBe(['#x']);
});

test('the Giỏ hàng page shows the covers of the selected channel only', function (): void {
    $b = pnSecondChannel($this);

    foreach ([$this->sa, $b] as $ch) {
        ChromeAccount::query()->create(['social_account_id' => $ch->id, 'enabled' => true, 'tiktok_user_id' => '77'.random_int(1000, 9999)]);
    }

    pnUpload($this, [pnImage()]);
    pnUpload($this, [pnImage('jpg', 540, 960, 'b')], $b);
    pnCover($this)->update(['cover_mode' => 'fixed']);
    pnCover($this, $b)->update(['cover_mode' => 'random']);
    $fileA = pnCover($this)->cover_images[0]['file'];
    $fileB = pnCover($this, $b)->cover_images[0]['file'];

    $this->actingAs($this->owner)->get('/auto/gio-hang?kenh='.$b->id)->assertInertia(fn ($p) => $p
        ->where('selected', $b->id)
        ->where("personalise.{$this->code}.cover_mode", 'random')
        ->has("personalise.{$this->code}.covers", 1)
        ->where("personalise.{$this->code}.covers.0.file", $fileB));

    $this->actingAs($this->owner)->get('/auto/gio-hang?kenh='.$this->sa->id)->assertInertia(fn ($p) => $p
        ->where("personalise.{$this->code}.cover_mode", 'fixed')
        ->where("personalise.{$this->code}.covers.0.file", $fileA));
});

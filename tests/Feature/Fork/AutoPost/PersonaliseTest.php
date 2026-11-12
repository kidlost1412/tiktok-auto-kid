<?php

declare(strict_types=1);

use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\AutoPost\Models\AutoVideo;
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
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", [
        'images' => [pnImage('png', 540, 960, 'a'), pnImage('webp', 600, 600, 'b'), pnImage('jpg', 540, 960, 'c')],
    ])->assertRedirect()->assertSessionHas('flash.success');

    $p = $this->product->fresh();
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
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [$txt]])->assertSessionHasErrors('images.0');

    $big = UploadedFile::fake()->create('big.jpg', 5121, 'image/jpeg');
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [$big]])->assertSessionHasErrors('images.0');

    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [pnImage('jpg', 100, 100)]])->assertSessionHas('flash.error');

    expect($this->product->fresh()->cover_images ?? [])->toBe([]);
});

test('only the account owner can upload, delete or change settings', function (): void {
    $member = User::factory()->create(['account_id' => $this->account->id]);

    $this->actingAs($member)->post("/auto/products/{$this->code}/covers", ['images' => [pnImage()]])->assertForbidden();
    $this->actingAs($member)->put("/auto/products/{$this->code}/personalise", ['cover_mode' => 'random'])->assertForbidden();
    $this->actingAs($member)->put('/auto/hashtag-mac-dinh', ['hashtag_mode' => 'append', 'hashtag_pick' => 0])->assertForbidden();
    $this->actingAs($member)->get("/auto/anh-bia/{$this->code}/x.jpg")->assertForbidden();
    expect($this->product->fresh()->cover_mode)->toBe('default');
});

test('delete removes the file and clears fixed/last references; settings save normalises hashtags', function (): void {
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [pnImage('jpg', 540, 960, 'a'), pnImage('jpg', 540, 960, 'b')]]);
    $p = $this->product->fresh();
    [$one, $two] = array_column($p->cover_images, 'file');
    $path = CoverStore::pathFor($p, $one);

    $this->actingAs($this->owner)->put("/auto/products/{$this->code}/personalise", [
        'cover_mode' => 'fixed', 'cover_fixed' => $one, 'hashtags' => '#A, b  #a', 'hashtag_mode' => 'replace', 'hashtag_pick' => 1,
    ])->assertRedirect();

    $p = $this->product->fresh();
    expect($p->cover_mode)->toBe('fixed')->and($p->cover_fixed)->toBe($one)->and($p->hashtags)->toBe(['#A', '#b'])
        ->and($p->hashtag_mode)->toBe('replace')->and($p->hashtag_pick)->toBe(1);

    $this->actingAs($this->owner)->delete("/auto/products/{$this->code}/covers/{$one}")->assertRedirect();

    $p = $this->product->fresh();
    expect(file_exists($path))->toBeFalse()->and($p->cover_fixed)->toBeNull()->and(array_column($p->cover_images, 'file'))->toBe([$two]);
    $this->actingAs($this->owner)->delete("/auto/products/{$this->code}/covers/nope.jpg")->assertNotFound();
});

// ---------------------------------------------------------------- selection

test('default mode picks nothing; fixed always returns the chosen image', function (): void {
    $store = app(CoverStore::class);
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [pnImage('jpg', 540, 960, 'a'), pnImage('jpg', 540, 960, 'b')]]);
    $p = $this->product->fresh();
    [$one, $two] = array_column($p->cover_images, 'file');

    expect($store->pick($p))->toBeNull();

    $p->update(['cover_mode' => 'fixed', 'cover_fixed' => $two]);
    expect($store->pick($p->fresh()))->toBe($two)->and($store->pick($p->fresh()))->toBe($two);

    $p->update(['cover_fixed' => null]);
    expect($store->pick($p->fresh()))->toBe($one);
});

test('random never repeats the previous image when there are two or more, and works with one', function (): void {
    $store = app(CoverStore::class);
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [pnImage('jpg', 540, 960, 'a'), pnImage('jpg', 540, 960, 'b'), pnImage('jpg', 540, 960, 'c')]]);
    $this->product->update(['cover_mode' => 'random']);

    $prev = null;
    $seen = [];

    for ($i = 0; $i < 60; $i++) {
        $f = $store->pick($this->product->fresh());
        expect($f)->not->toBeNull()->and($f)->not->toBe($prev);
        $seen[$f] = true;
        $prev = $f;
    }

    expect($seen)->toHaveCount(3);

    $only = $this->product->fresh();
    $keep = $only->cover_images[0];
    $only->update(['cover_images' => [$keep], 'cover_last' => $keep['file']]);
    expect($store->pick($only->fresh()))->toBe($keep['file'])->and($store->pick($only->fresh()))->toBe($keep['file']);
});

test('random spreads picks evenly over a small set (repeats allowed, never back-to-back)', function (): void {
    $store = app(CoverStore::class);

    foreach ([2, 3] as $n) {
        $p = AutoProduct::query()->create(['code' => $this->code.'-'.$n, 'name' => 'X', 'short_name' => 'X', 'facts' => [], 'enabled' => true]);
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

function pnBuild(object $t): array
{
    $hub = str_replace('\\', '/', sys_get_temp_dir()).'/pn-hub-'.bin2hex(random_bytes(4));
    mkdir($hub, 0777, true);
    file_put_contents($hub.'/v.mp4', 'video-bytes');

    $sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $t->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh']);
    ChromeAccount::query()->create(['social_account_id' => $sa->id, 'enabled' => true, 'tiktok_user_id' => '7012345678901234567']);
    AutoAccount::create(['social_account_id' => $sa->id, 'enabled' => true, 'daily_cap' => 20]);
    ShopProduct::create(['social_account_id' => $sa->id, 'product_id' => '1729384756001234567', 'source' => 'my_shop', 'title' => 'SP', 'stock_num' => 5, 'synced_at' => now()]);
    ProductLink::create(['social_account_id' => $sa->id, 'auto_product_id' => $t->code, 'shop_product_id' => '1729384756001234567', 'display_name' => 'SP']);

    $video = AutoVideo::create([
        'hash' => bin2hex(random_bytes(8)), 'path' => $hub.'/v.mp4', 'batch_date' => '2026-11-09', 'file_name' => 'v.mp4',
        'product_code' => $t->code, 'goc' => 'g', 'status' => 'new', 'caption' => 'Caption hub', 'hashtags' => ['#hub'], 'caption_source' => 'hub',
    ]);

    $post = app(PostBuilder::class)->build($sa->load('workspace'), $video, ['caption' => 'Caption hub #cu', 'hashtags' => ['#hub'], 'source' => 'hub'], CarbonImmutable::now('UTC')->addDays(2));
    $post->forceFill(['meta' => [...$post->meta, 'privacy_level' => 'PUBLIC_TO_EVERYONE']])->save();

    return [$post, $video, $sa];
}

test('the post builder applies the hashtags to the post text and records the chosen cover, keeping hub text on the video', function (): void {
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [pnImage()]]);
    $this->product->update(['cover_mode' => 'random', 'hashtags' => ['#moi'], 'hashtag_mode' => 'replace']);

    [$post, $video] = pnBuild($this);

    expect($post->content)->toBe("Caption hub\n\n#moi")
        ->and($post->meta['fork_cover'])->toBe($this->product->fresh()->cover_images[0]['file'])
        ->and($video->fresh()->caption)->toBe('Caption hub #cu')
        ->and($video->fresh()->hashtags)->toBe(['#hub']);
});

test('without personalisation the post text and meta are exactly as before', function (): void {
    [$post] = pnBuild($this);

    expect($post->content)->toBe("Caption hub #cu\n\n#hub")->and($post->meta)->not->toHaveKey('fork_cover');
});

test('the chrome job payload carries options.cover for a personalised post and none otherwise', function (): void {
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [pnImage()]]);
    $this->product->update(['cover_mode' => 'fixed']);
    [$post] = pnBuild($this);

    $job = app(ChromeJobs::class)->queueForPost($post, 'now');
    $client = new ChromeClient(['tiktok_username' => 'u']);
    $cover = app(ChromeJobs::class)->jobPayload($job, $client)['options']['cover'];
    $path = CoverStore::pathFor($this->product->fresh(), $post->meta['fork_cover']);

    expect($cover)->toMatchArray(['url' => '/api/ext/cover?id='.$job->id, 'mime' => 'image/jpeg', 'size' => filesize($path), 'sha256' => hash_file('sha256', $path), 'width' => 540, 'height' => 720])
        ->and($cover)->not->toHaveKey('field')
        ->and($job->options['cover']['code'])->toBe($this->code);

    // Công tắc an toàn: tắt thì không gửi bìa.
    $this->product->update(['cover_mode' => 'default']);
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
    $sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id]);
    ChromeAccount::query()->create(['social_account_id' => $sa->id, 'enabled' => true, 'tiktok_user_id' => '777']);
    $this->product->update(['hashtags' => ['#a'], 'cover_mode' => 'random']);
    Hashtags::saveDefaults('#chung', 'append', 2);

    $this->actingAs($this->owner)->get('/auto/gio-hang')->assertInertia(fn ($p) => $p
        ->where("personalise.{$this->code}.cover_mode", 'random')
        ->where("personalise.{$this->code}.hashtags", ['#a'])
        ->where('personalise_default.tags', ['#chung'])
        ->where('personalise_default.pick', 2));
});

test('covers are center-cropped to 3:4 (max 1080x1440) and stored as jpg with the cropped size', function (): void {
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [
        pnImage('jpg', 1080, 1920, 'tall'), pnImage('png', 1600, 900, 'wide'), pnImage('webp', 2160, 2880, 'big'), pnImage('jpg', 540, 720, 'exact'),
    ]])->assertRedirect()->assertSessionHas('flash.success');

    $p = $this->product->fresh();
    $dims = collect($p->cover_images)->map(fn ($i): array => [$i['w'], $i['h']])->all();

    expect($dims)->toBe([[1080, 1440], [675, 900], [1080, 1440], [540, 720]]);

    foreach ($p->cover_images as $img) {
        $size = getimagesize(CoverStore::pathFor($p, $img['file']));
        expect([$size[0], $size[1]])->toBe([$img['w'], $img['h']])->and($size[2])->toBe(IMAGETYPE_JPEG);
    }

    expect($p->cover_images[0])->toMatchArray(['orig_w' => 1080, 'orig_h' => 1920]);
});

test('cropSize keeps 3:4 for tall and wide sources', function (): void {
    expect(CoverStore::cropSize(1080, 1920))->toBe([1080, 1440])
        ->and(CoverStore::cropSize(1600, 900))->toBe([675, 900])
        ->and(CoverStore::cropSize(600, 800))->toBe([600, 800]);
});

test('Studio minimum 324x432 is enforced on the cropped result, by exact boundary', function (): void {
    $try = fn (int $w, int $h): bool => $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [pnImage('jpg', $w, $h)]])->getSession()->has('flash.success');

    expect($try(324, 432))->toBeTrue()
        ->and($try(323, 432))->toBeFalse()      // 323x431 after the crop
        ->and($try(324, 431))->toBeFalse()
        ->and($try(1000, 431))->toBeFalse()     // wide but too short: crop is 323x431
        ->and($try(540, 960))->toBeTrue();
    expect(count($this->product->fresh()->cover_images))->toBe(2);

    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [pnImage('jpg', 300, 400)]])
        ->assertSessionHas('flash.error', fn ($m): bool => str_contains($m, '324×432'));
});

test('describe exposes the original size so the dialog can show what was cropped', function (): void {
    $this->actingAs($this->owner)->post("/auto/products/{$this->code}/covers", ['images' => [
        pnImage('jpg', 1080, 1920, 'tall'),
    ]])->assertRedirect();

    $p = $this->product->fresh();
    $p->update(['cover_images' => [...$p->cover_images, ['file' => 'old.jpg', 'name' => 'old', 'w' => 540, 'h' => 720]]]);

    $described = app(CoverStore::class)->describe($p->fresh());

    expect($described[0])->toMatchArray(['w' => 1080, 'h' => 1440, 'orig_w' => 1080, 'orig_h' => 1920])
        ->and($described[1])->toMatchArray(['orig_w' => null, 'orig_h' => null]);
});

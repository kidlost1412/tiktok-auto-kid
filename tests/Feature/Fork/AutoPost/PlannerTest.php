<?php

declare(strict_types=1);

use App\Enums\Post\Status as PostStatus;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Models\AnchorTemplate;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\AutoPost\Scheduling\PostBuilder;
use App\Fork\AutoPost\Scheduling\ResultWatcher;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;

beforeEach(function (): void {
    Storage::fake();
    $this->hub = str_replace('\\', '/', sys_get_temp_dir()).'/k2-hub-'.bin2hex(random_bytes(4));
    mkdir($this->hub.'/ra/2026-11-09', 0777, true);
    config(['fork.auto.hub_path' => $this->hub, 'fork.auto.settle_seconds' => 0]);

    $this->user = User::factory()->create();
    $this->workspace = Workspace::factory()->create(['user_id' => $this->user->id]);
    // 10:00 giờ VN của 2 ngày sau: luôn ở tương lai so với đồng hồ thật (CreatePosts đòi giờ hẹn sau hiện tại).
    $this->now = CarbonImmutable::now('UTC')->addDays(2)->setTime(3, 0);

    $this->product = AutoProduct::create([
        'code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true,
    ]);

    $this->account = function (bool $chrome = true, array $auto = [], bool $cart = true): SocialAccount {
        $account = SocialAccount::factory()->tiktok()->create([
            'workspace_id' => $this->workspace->id,
            'status' => AccountStatus::Connected,
            'timezone' => 'Asia/Ho_Chi_Minh',
        ]);

        if ($chrome) {
            ChromeAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'tiktok_user_id' => '777123']);
        }

        AutoAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'daily_cap' => 20, ...$auto]);

        if ($cart) {
            cartFor($account);
        }

        return $account;
    };

    $this->videos = function (int $n): void {
        for ($i = 0; $i < $n; $i++) {
            $name = "NanoĐồng_goc{$i}_Giong_MIXKIT_20261109-16{$i}-1.mp4";
            $path = $this->hub.'/ra/2026-11-09/'.$name;
            file_put_contents($path, "video-$i");
            AutoVideo::create([
                'hash' => hash('sha256', "video-$i"), 'path' => $path, 'batch_date' => '2026-11-09',
                'file_name' => $name, 'product_code' => 'nano-dong', 'goc' => "goc{$i}", 'status' => 'new',
                'caption' => "Caption hub số {$i}.", 'hashtags' => ['#nongnghiep', '#nanodong'], 'caption_source' => 'hub',
            ]);
        }
    };

    $this->planner = fn (): Planner => app(Planner::class);
});

afterEach(function (): void {
    if (is_dir($this->hub)) {
        foreach (glob($this->hub.'/ra/*/*') ?: [] as $f) {
            @unlink($f);
        }
        foreach (glob($this->hub.'/ra/*') ?: [] as $d) {
            @rmdir($d);
        }
        @rmdir($this->hub.'/ra');
        @rmdir($this->hub);
    }
});

test('does not exceed daily cap and keeps minimum gap', function () {
    $account = ($this->account)(auto: ['daily_cap' => 5, 'window_start' => 0, 'window_end' => 24]);
    ($this->videos)(30);
    config(['fork.auto.plan_ahead_hours' => 30]);

    ($this->planner)()->planAll($this->now);

    $times = AutoVideo::query()->where('social_account_id', $account->id)->whereNotNull('scheduled_for')
        ->orderBy('scheduled_for')->pluck('scheduled_for')->map(fn ($t) => CarbonImmutable::parse($t))->all();

    $perDay = collect($times)->groupBy(fn ($t) => $t->setTimezone('Asia/Ho_Chi_Minh')->format('Y-m-d'));
    expect($perDay->every(fn ($d) => $d->count() <= 5))->toBeTrue()
        ->and(count($times))->toBeGreaterThan(5);

    for ($i = 1; $i < count($times); $i++) {
        expect($times[$i]->getTimestamp() - $times[$i - 1]->getTimestamp())->toBeGreaterThanOrEqual(20 * 60);
    }
});

test('never schedules within 45 minutes from now', function () {
    ($this->account)(auto: ['daily_cap' => 40, 'window_start' => 0, 'window_end' => 24]);
    ($this->videos)(40);

    ($this->planner)()->planAll($this->now);

    $earliest = AutoVideo::query()->whereNotNull('scheduled_for')->min('scheduled_for');
    expect($earliest)->not->toBeNull()
        ->and(CarbonImmutable::parse($earliest)->getTimestamp())->toBeGreaterThanOrEqual($this->now->addMinutes(45)->getTimestamp());
});

test('running again does not create duplicates', function () {
    ($this->account)(auto: ['daily_cap' => 10, 'window_start' => 6, 'window_end' => 23]);
    ($this->videos)(20);

    ($this->planner)()->planAll($this->now);
    $first = [Post::query()->count(), AutoVideo::query()->where('status', 'scheduled')->count()];
    ($this->planner)()->planAll($this->now->addMinutes(5));
    ($this->planner)()->planAll($this->now);

    expect($first[0])->toBeGreaterThan(0)
        ->and(Post::query()->count())->toBe($first[0])
        ->and(AutoVideo::query()->where('status', 'scheduled')->count())->toBe($first[1])
        ->and(AutoVideo::query()->whereNotNull('post_id')->distinct('post_id')->count('post_id'))->toBe($first[1]);
});

test('disabled accounts and accounts without Chrome are skipped', function () {
    $off = ($this->account)(auto: ['enabled' => false]);
    $noChrome = ($this->account)(chrome: false);
    ($this->videos)(5);

    $report = ($this->planner)()->planAll($this->now);

    expect(Post::query()->count())->toBe(0)
        ->and(AutoVideo::query()->where('status', 'new')->count())->toBe(5)
        ->and($report)->not->toHaveKey($off->id)
        ->and($report[$noChrome->id]['skipped'])->toContain('Chrome');
});

test('creates a post with the right meta, caption and media', function () {
    Http::preventStrayRequests();
    Http::fake();
    $account = ($this->account)(auto: ['daily_cap' => 3, 'window_start' => 6, 'window_end' => 23]);
    ($this->videos)(3);

    ($this->planner)()->planAll($this->now);

    $video = AutoVideo::query()->where('status', 'scheduled')->orderBy('scheduled_for')->firstOrFail();
    $post = Post::query()->findOrFail($video->post_id);

    expect($post->status)->toBe(PostStatus::Scheduled)
        ->and($post->social_account_id)->toBe($account->id)
        ->and($post->scheduled_at->getTimestamp())->toBe($video->scheduled_for->getTimestamp())
        ->and($post->content)->toBe($video->caption."\n\n".implode(' ', $video->hashtags))
        ->and($post->meta['privacy_level'])->toBe('PUBLIC_TO_EVERYONE')
        ->and($post->meta['allow_comments'])->toBeTrue()
        ->and($post->meta['allow_duet'])->toBeFalse()
        ->and($post->meta['allow_stitch'])->toBeFalse()
        ->and($post->meta['fork_shop_product_id'])->toBe('1729384756001234567')
        ->and($post->meta['fork_shop_product_name'])->toBe('Nano Đồng 1L')
        ->and($post->media)->toHaveCount(1)
        ->and($post->media[0]['mime_type'])->toBe('video/mp4')
        ->and($post->ownedMedia()->count())->toBe(1)
        ->and($video->social_account_id)->toBe($account->id);

    // Chữ của hub đi nguyên văn; không có lời gọi AI hay mạng nào (chỉ có truy vấn follower của factory tài khoản).
    expect($post->content)->toBe("Caption hub số {$video->goc[3]}.\n\n#nongnghiep #nanodong");
    Http::assertNotSent(fn ($request): bool => ! str_contains($request->url(), 'open.tiktokapis.com/v2/user/info'));

    Storage::assertExists($post->media[0]['path']);
});

test('the post builder refuses text over the 2200 character TikTok limit', function () {
    $account = ($this->account)(auto: ['daily_cap' => 3]);
    ($this->videos)(1);
    $video = AutoVideo::query()->firstOrFail();

    expect(fn () => app(PostBuilder::class)->build($account->load('workspace'), $video, ['caption' => str_repeat('a', 2198), 'hashtags' => ['#a'], 'source' => 'hub'], $this->now->addHours(2)))
        ->toThrow(RuntimeException::class, '2200');
    expect(Post::query()->count())->toBe(0);

    $post = app(PostBuilder::class)->build($account->load('workspace'), $video, ['caption' => str_repeat('a', 2196), 'hashtags' => ['#a'], 'source' => 'hub'], $this->now->addHours(2));
    expect(mb_strlen($post->content))->toBe(2200);
});

test('a failure while building releases the video and leaves no post', function () {
    ($this->account)(auto: ['daily_cap' => 3]);
    ($this->videos)(1);
    // Ép lỗi bằng cách làm mất file sau khi giữ chỗ.
    $video = AutoVideo::query()->firstOrFail();
    unlink($video->path);

    ($this->planner)()->planAll($this->now);

    expect(Post::query()->count())->toBe(0)
        ->and($video->refresh()->status)->toBe('failed')
        ->and($video->post_id)->toBeNull();
});

test('a published post turns the video into posted and archives the file', function () {
    ($this->account)(auto: ['daily_cap' => 8, 'window_start' => 6, 'window_end' => 23]);
    ($this->videos)(10);
    ($this->planner)()->planAll($this->now);

    $video = AutoVideo::query()->where('status', 'scheduled')->firstOrFail();
    Post::query()->whereKey($video->post_id)->update(['status' => PostStatus::Published, 'published_at' => now()]);

    $result = app(ResultWatcher::class)->sync();
    $video->refresh();

    expect($result['posted'])->toBe(1)
        ->and($video->status)->toBe('posted')
        ->and($video->path)->toContain('/ra/_da-dang/2026-11-09/')
        ->and(file_exists($video->path))->toBeTrue();
    @unlink($video->path);
    @rmdir(dirname($video->path));
    @rmdir($this->hub.'/ra/_da-dang');
});

test('a failed post marks the video failed and it never returns to new', function () {
    ($this->account)(auto: ['daily_cap' => 8]);
    ($this->videos)(10);
    ($this->planner)()->planAll($this->now);

    $video = AutoVideo::query()->where('status', 'scheduled')->firstOrFail();
    Post::query()->whereKey($video->post_id)->update(['status' => PostStatus::Failed, 'error_message' => 'TikTok từ chối']);

    app(ResultWatcher::class)->sync();

    expect($video->refresh()->status)->toBe('failed')
        ->and($video->skip_reason)->toContain('TikTok từ chối');
});

test('explore slots stay inside the window and optimized mode favours preferred hours', function () {
    $a = ($this->account)(auto: ['mode' => 'optimized', 'preferred_hours' => [18, 19, 20], 'explore_ratio' => 0.2, 'daily_cap' => 10, 'window_start' => 6, 'window_end' => 23]);
    $auto = AutoAccount::query()->findOrFail($a->id);
    $from = CarbonImmutable::parse('2026-11-10 17:00:00', 'UTC'); // 00:00 VN ngày 11
    $slots = ($this->planner)()->slotsFor($auto, $from, $from->addDay());

    $hours = collect($slots)->map(fn ($s) => (int) $s->setTimezone('Asia/Ho_Chi_Minh')->format('G'));
    expect($slots)->toHaveCount(10)
        ->and($hours->min())->toBeGreaterThanOrEqual(6)
        ->and($hours->max())->toBeLessThan(23)
        ->and($hours->filter(fn ($h) => in_array($h, [18, 19, 20], true))->count())->toBeGreaterThanOrEqual(7);
});

/** Giỏ hàng hợp lệ cho một kênh: mẫu anchor, sản phẩm shop còn hàng, và liên kết mã nano-dong. */
function cartFor(SocialAccount $account, string $productId = '1729384756001234567', int $stock = 5): void
{
    AnchorTemplate::create(['social_account_id' => $account->id, 'product_id' => '1729384756000000001', 'anchors' => json_encode([['id' => '1729384756000000001']]), 'captured_at' => now()]);
    ShopProduct::create(['social_account_id' => $account->id, 'product_id' => $productId, 'source' => 'my_shop', 'title' => 'Nano Đồng 1L chính hãng', 'stock_num' => $stock, 'synced_at' => now()]);
    ProductLink::create(['social_account_id' => $account->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => $productId, 'display_name' => 'Nano Đồng 1L']);
}

test('without an anchor template the account is still planned (extension builds the default anchor)', function () {
    $account = ($this->account)(auto: ['daily_cap' => 5], cart: false);
    ShopProduct::create(['social_account_id' => $account->id, 'product_id' => '1729384756001234567', 'title' => 'x', 'stock_num' => 5]);
    ProductLink::create(['social_account_id' => $account->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => '1729384756001234567', 'display_name' => 'x']);
    ($this->videos)(5);

    $report = ($this->planner)()->planAll($this->now);

    expect(AnchorTemplate::query()->count())->toBe(0)
        ->and($report[$account->id]['created'])->toBeGreaterThan(0)
        ->and(Post::query()->first()->meta['fork_shop_product_id'])->toBe('1729384756001234567');
});

test('codes without a link are held back in the library', function () {
    $account = ($this->account)(auto: ['daily_cap' => 5]);
    AutoProduct::create(['code' => 'kali-bo', 'name' => 'Kali Bo', 'short_name' => 'KaliBo', 'facts' => [], 'enabled' => true]);
    ($this->videos)(3);
    $path = $this->hub.'/ra/2026-11-09/KaliBo_x_Y_MIXKIT_1.mp4';
    file_put_contents($path, 'kali');
    AutoVideo::create(['hash' => hash('sha256', 'kali'), 'path' => $path, 'batch_date' => '2026-11-09', 'file_name' => 'KaliBo_x_Y_MIXKIT_1.mp4', 'product_code' => 'kali-bo', 'status' => 'new', 'caption' => 'Kali hub.', 'hashtags' => []]);
    config(['fork.auto.plan_ahead_hours' => 30]);

    ($this->planner)()->planAll($this->now);

    expect(AutoVideo::query()->where('product_code', 'kali-bo')->value('status'))->toBe('new')
        ->and(AutoVideo::query()->where('product_code', 'nano-dong')->where('status', 'scheduled')->count())->toBeGreaterThan(0);
});

test('a link to a missing or out-of-stock product skips that code with a warning', function () {
    $account = ($this->account)(auto: ['daily_cap' => 5]);
    ($this->videos)(3);

    ShopProduct::query()->where('social_account_id', $account->id)->update(['stock_num' => 0]);
    $report = ($this->planner)()->planAll($this->now);

    expect(Post::query()->count())->toBe(0)
        ->and($report[$account->id]['skipped'])->toContain('hết hàng');

    ShopProduct::query()->where('social_account_id', $account->id)->update(['stock_num' => 5, 'missing' => true]);
    $report = ($this->planner)()->planAll($this->now);

    expect(Post::query()->count())->toBe(0)
        ->and($report[$account->id]['skipped'])->toContain('không còn trong shop');
});

test('a paused link is skipped until it is saved again', function () {
    $account = ($this->account)(auto: ['daily_cap' => 5]);
    ($this->videos)(3);
    ProductLink::query()->where('social_account_id', $account->id)->update(['paused_reason' => 'Sản phẩm không còn']);

    $report = ($this->planner)()->planAll($this->now);

    expect(Post::query()->count())->toBe(0)->and($report[$account->id]['skipped'])->toContain('tạm dừng');
});

test('a cart failure from Chrome returns the video to new and pauses the code on that account', function (string $reason) {
    $account = ($this->account)(auto: ['daily_cap' => 8]);
    ($this->videos)(10);
    ($this->planner)()->planAll($this->now);

    $video = AutoVideo::query()->where('status', 'scheduled')->firstOrFail();
    $postId = $video->post_id;
    ChromeJob::create([
        'id' => 'ej_'.bin2hex(random_bytes(8)), 'post_id' => $postId, 'social_account_id' => $account->id, 'attempt' => 1, 'mode' => 'scheduled',
        'expect_user_id' => '777123', 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1, 'state' => 'failed', 'options' => [],
        'result' => ['outcome' => 'failed', 'reason' => $reason, 'not_sent' => true], 'nonce' => 'n', 'deliver_by' => now(),
    ]);
    Post::query()->whereKey($postId)->update(['status' => PostStatus::Failed, 'error_message' => 'Chrome báo lỗi']);

    app(ResultWatcher::class)->sync();
    $video->refresh();
    $link = ProductLink::query()->where('social_account_id', $account->id)->where('auto_product_id', 'nano-dong')->firstOrFail();

    expect($video->status)->toBe('new')->and($video->post_id)->toBeNull()->and($video->social_account_id)->toBeNull()
        ->and($link->paused_reason)->not->toBeNull();

    // Mã bị tạm dừng nên lượt xếp lịch sau không lấy lại video này.
    $report = ($this->planner)()->planAll($this->now->addMinutes(5));
    expect($report[$account->id]['skipped'])->toContain('tạm dừng');
})->with(['product-unavailable', 'anchor-build-failed']);

test('another failure reason still marks the video failed', function () {
    $account = ($this->account)(auto: ['daily_cap' => 8]);
    ($this->videos)(10);
    ($this->planner)()->planAll($this->now);
    $video = AutoVideo::query()->where('status', 'scheduled')->firstOrFail();
    ChromeJob::create([
        'id' => 'ej_'.bin2hex(random_bytes(8)), 'post_id' => $video->post_id, 'social_account_id' => $account->id, 'attempt' => 1, 'mode' => 'scheduled',
        'expect_user_id' => '777123', 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1, 'state' => 'failed', 'options' => [],
        'result' => ['outcome' => 'failed', 'reason' => 'upload-failed', 'not_sent' => true], 'nonce' => 'n', 'deliver_by' => now(),
    ]);
    Post::query()->whereKey($video->post_id)->update(['status' => PostStatus::Failed, 'error_message' => 'lỗi']);

    app(ResultWatcher::class)->sync();

    expect($video->refresh()->status)->toBe('failed')
        ->and(ProductLink::query()->whereNotNull('paused_reason')->count())->toBe(0);
});

test('ten_gio của hub vào video và meta bài; ten_gio không hợp lệ thì dùng tên hiển thị của liên kết', function () {
    ($this->account)(auto: ['daily_cap' => 1, 'window_start' => 6, 'window_end' => 23]);
    ($this->videos)(2);
    $ids = AutoVideo::query()->orderBy('id')->pluck('id');
    // Video đầu không có ten_gio: dùng tên hiển thị của liên kết.
    AutoVideo::query()->whereKey($ids[1])->update(['product_name' => 'MUA 1 TẶNG 1', 'goc' => 'khac']);

    ($this->planner)()->planAll($this->now);
    $video = AutoVideo::query()->where('status', 'scheduled')->firstOrFail();
    $post = Post::query()->findOrFail($video->post_id);

    expect($video->id)->toBe($ids[0])
        ->and($post->meta['fork_shop_product_name'])->toBe('Nano Đồng 1L');

    ($this->planner)()->planAll($this->now->addDay());
    $second = AutoVideo::query()->where('status', 'scheduled')->where('id', '!=', $video->id)->firstOrFail();

    expect($second->product_name)->toBe('MUA 1 TẶNG 1')
        ->and(Post::query()->findOrFail($second->post_id)->meta['fork_shop_product_name'])->toBe('MUA 1 TẶNG 1');
});

test('product-check-failed returns the video to new without pausing the link', function () {
    $account = ($this->account)(auto: ['daily_cap' => 8]);
    ($this->videos)(10);
    ($this->planner)()->planAll($this->now);

    $video = AutoVideo::query()->where('status', 'scheduled')->firstOrFail();
    $postId = $video->post_id;
    ChromeJob::create([
        'id' => 'ej_'.bin2hex(random_bytes(8)), 'post_id' => $postId, 'social_account_id' => $account->id, 'attempt' => 1, 'mode' => 'scheduled',
        'expect_user_id' => '777123', 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1, 'state' => 'failed', 'options' => [],
        'result' => ['outcome' => 'failed', 'reason' => 'product-check-failed', 'not_sent' => true], 'nonce' => 'n', 'deliver_by' => now(),
    ]);
    Post::query()->whereKey($postId)->update(['status' => PostStatus::Failed, 'error_message' => 'Chrome báo lỗi']);

    app(ResultWatcher::class)->sync();
    $video->refresh();
    $link = ProductLink::query()->where('social_account_id', $account->id)->where('auto_product_id', 'nano-dong')->firstOrFail();

    expect($video->status)->toBe('new')->and($video->post_id)->toBeNull()->and($video->product_name)->toBeNull()
        ->and($link->paused_reason)->toBeNull();
});

// ---------------------------------------------------------------- quy cách + lệch giờ giữa các kênh

/** Sản phẩm hub "dam-ca" có 2 quy cách, mỗi quy cách có sản phẩm shop riêng; $link = các quy cách đã chọn sản phẩm. */
function quyCachSetup(object $t, SocialAccount $account, array $link): array
{
    AutoProduct::create(['code' => 'dam-ca', 'name' => 'Đạm cá', 'short_name' => 'ĐạmCá', 'facts' => [], 'enabled' => true, 'quy_cach' => [['ma' => '1l', 'ten' => 'Chai 1L'], ['ma' => '5l', 'ten' => 'Can 5L']]]);
    $ids = ['1l' => '1729384756000000011', '5l' => '1729384756000000055'];

    foreach ($ids as $qc => $id) {
        ShopProduct::create(['social_account_id' => $account->id, 'product_id' => $id, 'source' => 'my_shop', 'title' => 'Đạm cá '.$qc, 'stock_num' => 5, 'synced_at' => now()]);

        if (in_array($qc, $link, true)) {
            ProductLink::create(['social_account_id' => $account->id, 'auto_product_id' => 'dam-ca', 'quy_cach' => $qc, 'shop_product_id' => $id, 'display_name' => 'ĐẠM CÁ '.strtoupper($qc)]);
        }
    }

    foreach (['1l', '5l'] as $qc) {
        for ($i = 0; $i < 3; $i++) {
            $name = "ĐạmCá_goc{$qc}{$i}_Giong_MIXKIT_20261109-{$qc}{$i}-1.mp4";
            $path = $t->hub.'/ra/2026-11-09/'.$name;
            file_put_contents($path, "dam-$qc-$i");
            AutoVideo::create(['hash' => hash('sha256', "dam-$qc-$i"), 'path' => $path, 'batch_date' => '2026-11-09', 'file_name' => $name,
                'product_code' => 'dam-ca', 'quy_cach' => $qc, 'goc' => "g{$qc}{$i}", 'status' => 'new', 'caption' => "Đạm cá {$qc}{$i}.", 'hashtags' => []]);
        }
    }

    return $ids;
}

test('a quy cach without a chosen product keeps its videos in the library', function () {
    $account = ($this->account)(auto: ['daily_cap' => 8], cart: false);
    $ids = quyCachSetup($this, $account, ['1l']);
    config(['fork.auto.plan_ahead_hours' => 30]);

    ($this->planner)()->planAll($this->now);

    expect(AutoVideo::query()->where('quy_cach', '5l')->where('status', 'new')->count())->toBe(3)
        ->and(AutoVideo::query()->where('quy_cach', '1l')->where('status', 'scheduled')->count())->toBeGreaterThan(0);

    foreach (AutoVideo::query()->where('status', 'scheduled')->get() as $video) {
        expect(Post::query()->findOrFail($video->post_id)->meta['fork_shop_product_id'])->toBe($ids['1l']);
    }
});

test('each quy cach is posted with its own shop product', function () {
    $account = ($this->account)(auto: ['daily_cap' => 8], cart: false);
    $ids = quyCachSetup($this, $account, ['1l', '5l']);
    config(['fork.auto.plan_ahead_hours' => 30]);

    ($this->planner)()->planAll($this->now);

    $scheduled = AutoVideo::query()->where('status', 'scheduled')->get();
    expect($scheduled->pluck('quy_cach')->unique()->sort()->values()->all())->toBe(['1l', '5l']);

    foreach ($scheduled as $video) {
        expect(Post::query()->findOrFail($video->post_id)->meta['fork_shop_product_id'])->toBe($ids[$video->quy_cach]);
    }
});

test('the post builder never falls back to another quy cach product', function () {
    $account = ($this->account)(auto: ['daily_cap' => 8], cart: false);
    quyCachSetup($this, $account, ['1l']);
    $video = AutoVideo::query()->where('quy_cach', '5l')->firstOrFail();

    expect(fn () => app(PostBuilder::class)->build($account->load('workspace'), $video, ['caption' => 'x', 'hashtags' => [], 'source' => 'hub'], $this->now->addHours(2)))
        ->toThrow(RuntimeException::class, 'chưa được chọn sản phẩm');

    expect(Post::query()->count())->toBe(0);
});

test('a cart failure pauses only the link of that video quy cach', function () {
    $account = ($this->account)(auto: ['daily_cap' => 8], cart: false);
    quyCachSetup($this, $account, ['1l', '5l']);
    AutoVideo::query()->where('quy_cach', '1l')->delete();
    config(['fork.auto.plan_ahead_hours' => 30]);
    ($this->planner)()->planAll($this->now);

    $video = AutoVideo::query()->where('status', 'scheduled')->firstOrFail();
    expect($video->quy_cach)->toBe('5l');
    ChromeJob::create([
        'id' => 'ej_'.bin2hex(random_bytes(8)), 'post_id' => $video->post_id, 'social_account_id' => $account->id, 'attempt' => 1, 'mode' => 'scheduled',
        'expect_user_id' => '777123', 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1, 'state' => 'failed', 'options' => [],
        'result' => ['outcome' => 'failed', 'reason' => 'product-unavailable', 'not_sent' => true], 'nonce' => 'n', 'deliver_by' => now(),
    ]);
    Post::query()->whereKey($video->post_id)->update(['status' => PostStatus::Failed, 'error_message' => 'Chrome báo lỗi']);

    app(ResultWatcher::class)->sync();

    expect(ProductLink::slot($account->id, 'dam-ca', '5l')->value('paused_reason'))->not->toBeNull()
        ->and(ProductLink::slot($account->id, 'dam-ca', '1l')->value('paused_reason'))->toBeNull();
});

test('a channel never posts within 2 minutes of another channel, nudged by 2 to 5 minutes, keeping its own gap', function () {
    $a = ($this->account)(auto: ['daily_cap' => 6, 'window_start' => 0, 'window_end' => 24]);
    $auto = AutoAccount::query()->findOrFail($a->id);
    $from = $this->now;
    $planner = ($this->planner)();

    $before = $planner->slotsFor($auto, $from, $from->addDay());
    $target = $before[0]->addSeconds(30);

    // Kênh khác đã có một video hẹn đúng sát giờ đầu tiên của kênh A, và một bài TikTok Auto Kid hẹn giờ sát giờ thứ hai.
    $b = ($this->account)(auto: ['daily_cap' => 6, 'window_start' => 0, 'window_end' => 24]);
    AutoVideo::create(['hash' => 'other', 'path' => '/x.mp4', 'batch_date' => '2026-11-09', 'file_name' => 'o.mp4', 'product_code' => 'nano-dong',
        'status' => 'scheduled', 'social_account_id' => $b->id, 'scheduled_for' => $target]);
    $second = $before[1]->addSeconds(-45);
    Post::factory()->forAccount($b)->scheduled()->create(['scheduled_at' => $second]);

    $after = $planner->slotsFor($auto, $from, $from->addDay());
    $again = $planner->slotsFor($auto, $from, $from->addDay());

    expect($after)->toEqual($again) // cùng hạt giống nên chạy lại cho cùng kết quả
        ->and($after[0]->getTimestamp())->toBeGreaterThan($before[0]->getTimestamp());

    foreach ($after as $slot) {
        expect(abs($slot->getTimestamp() - $target->getTimestamp()))->toBeGreaterThanOrEqual(120)
            ->and(abs($slot->getTimestamp() - $second->getTimestamp()))->toBeGreaterThanOrEqual(120);
    }

    for ($i = 1; $i < count($after); $i++) {
        expect($after[$i]->getTimestamp() - $after[$i - 1]->getTimestamp())->toBeGreaterThanOrEqual(20 * 60);
    }
});

test('raising daily_cap on a fully scheduled day fills the extra slots in free gaps', function () {
    $account = ($this->account)(auto: ['daily_cap' => 15, 'window_start' => 8, 'window_end' => 23]);
    $auto = AutoAccount::where('social_account_id', $account->id)->first();
    $planner = ($this->planner)();
    $day = $this->now->setTimezone('Asia/Ho_Chi_Minh')->startOfDay()->addDay()->utc();
    $from = $day;
    $to = $day->addHours(24)->subSecond();

    // Ngày đã xếp đủ 15 bài theo cap cũ.
    $old = $planner->slotsFor($auto, $from, $to);
    expect($old)->toHaveCount(15);

    foreach ($old as $i => $slot) {
        AutoVideo::create([
            'hash' => "h$i", 'path' => "p$i", 'batch_date' => '2026-11-09', 'file_name' => "f$i.mp4", 'product_code' => 'nano-dong',
            'status' => 'scheduled', 'social_account_id' => $account->id, 'scheduled_for' => $slot,
        ]);
    }

    expect($planner->slotsFor($auto, $from, $to))->toBe([]);

    AutoAccount::where('social_account_id', $account->id)->update(['daily_cap' => 20]);

    $extra = $planner->slotsFor($auto->refresh(), $from, $to);
    expect($extra)->toHaveCount(5);

    $all = collect($old)->merge($extra)->map(fn ($t) => $t->getTimestamp())->sort()->values()->all();
    expect($all)->toHaveCount(20);

    for ($i = 1; $i < count($all); $i++) {
        expect($all[$i] - $all[$i - 1])->toBeGreaterThanOrEqual(20 * 60);
    }

    foreach ($extra as $slot) {
        $h = (int) $slot->setTimezone('Asia/Ho_Chi_Minh')->format('G');
        expect($h)->toBeGreaterThanOrEqual(8)->toBeLessThan(23);
    }
});

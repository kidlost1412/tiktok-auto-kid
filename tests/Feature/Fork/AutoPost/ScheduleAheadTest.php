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
use App\Fork\AutoPost\Scheduling\FutureUploads;
use App\Fork\AutoPost\Scheduling\PlanPreview;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\AutoPost\Scheduling\ResultWatcher;
use App\Fork\AutoPost\Stats\StatsCollector;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Publishing\ChromeAwareTikTokPublisher;
use App\Fork\Chrome\ScheduledDispatcher;
use App\Models\AnalyticsPublication;
use App\Models\AnalyticsPublicationDailySnapshot;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;

beforeEach(function (): void {
    Storage::fake();
    $this->hub = str_replace('\\', '/', sys_get_temp_dir()).'/ahead-hub-'.bin2hex(random_bytes(4));
    mkdir($this->hub.'/ra/2026-11-09', 0777, true);
    config(['fork.auto.hub_path' => $this->hub, 'fork.auto.settle_seconds' => 0]);

    $this->user = User::factory()->create();
    $this->workspace = Workspace::factory()->create(['user_id' => $this->user->id]);
    // 10:00 giờ VN của 2 ngày sau (luôn ở tương lai so với đồng hồ thật).
    $this->now = CarbonImmutable::now('UTC')->addDays(2)->setTime(3, 0);

    AutoProduct::create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);

    $this->account = function (array $auto = []): SocialAccount {
        $account = SocialAccount::factory()->tiktok()->create([
            'workspace_id' => $this->workspace->id,
            'status' => AccountStatus::Connected,
            'timezone' => 'Asia/Ho_Chi_Minh',
        ]);
        ChromeAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'tiktok_user_id' => '777123']);
        AutoAccount::create(['social_account_id' => $account->id, 'enabled' => true, 'daily_cap' => 5, 'window_start' => 0, 'window_end' => 24, ...$auto]);

        AnchorTemplate::create(['social_account_id' => $account->id, 'product_id' => '1729384756000000001', 'anchors' => json_encode([['id' => '1729384756000000001']]), 'captured_at' => now()]);
        ShopProduct::create(['social_account_id' => $account->id, 'product_id' => '1729384756001234567', 'source' => 'my_shop', 'title' => 'Nano Đồng 1L', 'stock_num' => 5, 'synced_at' => now()]);
        ProductLink::create(['social_account_id' => $account->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => '1729384756001234567', 'display_name' => 'Nano Đồng 1L']);

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
                'caption' => "Caption hub số {$i}.", 'hashtags' => ['#nongnghiep'], 'caption_source' => 'hub',
            ]);
        }
    };
});

afterEach(function (): void {
    foreach (glob($this->hub.'/ra/*/*') ?: [] as $f) {
        @unlink($f);
    }
    foreach (glob($this->hub.'/ra/*') ?: [] as $d) {
        @rmdir($d);
    }
    @rmdir($this->hub.'/ra');
    @rmdir($this->hub);
});

function aheadLocalDays(string $accountId): array
{
    return AutoVideo::query()->where('social_account_id', $accountId)->whereNotNull('scheduled_for')->pluck('scheduled_for')
        ->map(fn ($t): string => CarbonImmutable::parse($t)->setTimezone('Asia/Ho_Chi_Minh')->format('Y-m-d'))
        ->unique()->sort()->values()->all();
}

function aheadJob(string $postId, string $accountId, string $state = 'posted', array $extra = []): ChromeJob
{
    static $n = 0;
    $n++;

    return ChromeJob::query()->create($extra + [
        'id' => 'ej_'.str_pad((string) $n, 24, 'f'), 'post_id' => $postId, 'social_account_id' => $accountId, 'attempt' => 1,
        'expect_user_id' => '777123', 'nonce' => 'n'.$n, 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1,
        'video_mime' => 'video/mp4', 'mode' => 'scheduled', 'caption' => 'c', 'options' => [], 'state' => $state,
    ]);
}

test('planner fills every day up to schedule_ahead_days and stops at the end of that day', function (): void {
    $account = ($this->account)(['schedule_ahead_days' => 3]);
    ($this->videos)(40);

    app(Planner::class)->planAll($this->now);

    $today = $this->now->setTimezone('Asia/Ho_Chi_Minh')->startOfDay();
    $days = aheadLocalDays($account->id);

    expect($days)->toBe([$today->format('Y-m-d'), $today->addDay()->format('Y-m-d'), $today->addDays(2)->format('Y-m-d')]);

    // hai ngày sau đủ hạn mức 5 bài/ngày
    $perDay = AutoVideo::query()->where('social_account_id', $account->id)->pluck('scheduled_for')
        ->countBy(fn ($t): string => CarbonImmutable::parse($t)->setTimezone('Asia/Ho_Chi_Minh')->format('Y-m-d'));
    expect($perDay[$today->addDay()->format('Y-m-d')])->toBe(5)->and($perDay[$today->addDays(2)->format('Y-m-d')])->toBe(5);

    // giờ sớm nhất nhận video đầu tiên (id nhỏ nhất)
    $first = AutoVideo::query()->where('social_account_id', $account->id)->orderBy('scheduled_for')->first();
    expect($first->id)->toBe((int) AutoVideo::query()->where('social_account_id', $account->id)->min('id'));
});

test('schedule_ahead_days = 1 plans only the rest of today', function (): void {
    $account = ($this->account)(['schedule_ahead_days' => 1]);
    ($this->videos)(40);

    app(Planner::class)->planAll($this->now);

    expect(aheadLocalDays($account->id))->toHaveCount(1);
});

test('horizon never goes beyond what TikTok accepts', function (): void {
    $account = ($this->account)(['schedule_ahead_days' => 9]);
    $auto = AutoAccount::query()->find($account->id);
    $now = CarbonImmutable::parse('2026-11-10 17:30:00', 'UTC'); // 00:30 giờ VN: ngày xếp trước dài nhất

    $end = app(Planner::class)->horizonFor($auto, $now);

    expect($end->getTimestamp() - $now->getTimestamp())->toBeLessThan(ChromeJobs::SCHEDULE_MAX_AHEAD)
        ->and(ChromeJobs::SCHEDULE_MAX_AHEAD)->toBeLessThanOrEqual((int) (9.5 * 86400));
});

test('plan preview and planner use the same horizon', function (): void {
    $account = ($this->account)(['schedule_ahead_days' => 2]);
    ($this->videos)(40);
    $auto = AutoAccount::query()->find($account->id);

    $preview = app(PlanPreview::class)->forAccount($auto, $this->now);
    app(Planner::class)->planAll($this->now);
    $planned = AutoVideo::query()->where('social_account_id', $account->id)->orderBy('scheduled_for')->pluck('scheduled_for')
        ->map(fn ($t): string => CarbonImmutable::parse($t)->toIso8601String())->all();

    expect(collect($preview['slots'])->pluck('at')->map(fn ($t): string => CarbonImmutable::parse($t)->toIso8601String())->all())->toBe($planned);
});

test('never more than max_future_posts unpublished posts per channel', function (): void {
    config(['fork.auto.max_future_posts' => 4]);
    $account = ($this->account)(['schedule_ahead_days' => 5, 'daily_cap' => 10]);
    ($this->videos)(40);

    $report = app(Planner::class)->planAll($this->now);
    app(Planner::class)->planAll($this->now->addMinutes(10));

    expect($report[$account->id]['created'])->toBe(4)
        ->and(AutoVideo::query()->where('social_account_id', $account->id)->count())->toBe(4);
});

test('posts days ahead are handed to Chrome right away, not 35 minutes before', function (): void {
    $account = ($this->account)(['schedule_ahead_days' => 3]);
    ($this->videos)(15);
    app(Planner::class)->planAll($this->now);

    $queued = app(ScheduledDispatcher::class)->dispatchForAccount($account);

    $job = ChromeJob::query()->where('social_account_id', $account->id)->first();
    $post = Post::query()->find($job->post_id);

    expect($queued)->toBe(1)
        ->and($job->state)->toBe('queued')->and($job->mode)->toBe('scheduled')
        ->and($post->scheduled_at->getTimestamp() - $job->deliver_by->getTimestamp())->toBe(ChromeJobs::SCHEDULE_LEAD)
        ->and($job->deliver_by->isFuture())->toBeTrue()
        // chỉ một job mở mỗi tài khoản
        ->and(app(ScheduledDispatcher::class)->dispatchForAccount($account))->toBe(0);
});

test('finishing one scheduled upload hands the next post over immediately', function (): void {
    $account = ($this->account)(['schedule_ahead_days' => 3]);
    ($this->videos)(15);
    app(Planner::class)->planAll($this->now);
    app(ScheduledDispatcher::class)->dispatchForAccount($account);

    $job = ChromeJob::query()->first();
    $job->forceFill(['state' => 'authorized', 'authorized_at' => now()])->save();

    app(ChromeJobs::class)->ingestResult($job->id, ['outcome' => 'posted', 'item_id' => '7700000000000000001', 'schedule_time' => $job->options['schedule_time']]);

    expect(ChromeJob::query()->count())->toBe(2)
        ->and(ChromeJob::query()->where('state', 'queued')->count())->toBe(1);
});

test('already uploaded posts do not block newer ones from being dispatched', function (): void {
    $account = ($this->account)(['schedule_ahead_days' => 5, 'daily_cap' => 20]);
    config(['fork.auto.max_future_posts' => 100]);
    ($this->videos)(80);
    app(Planner::class)->planAll($this->now);

    $posts = Post::query()->where('social_account_id', $account->id)->orderBy('scheduled_at')->get();
    expect($posts->count())->toBeGreaterThan(60);

    // 55 bài đầu đã có job posted (đã nằm trên TikTok)
    foreach ($posts->take(55) as $p) {
        aheadJob($p->id, $account->id);
    }

    expect(app(ScheduledDispatcher::class)->dispatchForAccount($account))->toBe(1)
        ->and(ChromeJob::query()->where('state', 'queued')->value('post_id'))->toBe($posts[55]->id);
});

test('a video scheduled days ahead becomes posted at its scheduled time even if the app only wakes up later', function (): void {
    $account = ($this->account)();
    $at = CarbonImmutable::now()->subHours(3)->startOfMinute();
    $post = Post::factory()->forAccount($account)->create(['status' => PostStatus::Published, 'scheduled_at' => $at, 'published_at' => now(), 'platform_post_id' => '7700000000000000009']);
    $video = AutoVideo::create([
        'hash' => 'hh', 'path' => '/x.mp4', 'batch_date' => '2026-11-09', 'file_name' => 'a_MIXKIT_1.mp4', 'product_code' => 'nano-dong',
        'status' => 'scheduled', 'social_account_id' => $account->id, 'post_id' => $post->id, 'scheduled_for' => $at,
    ]);
    aheadJob($post->id, $account->id);

    $result = app(ResultWatcher::class)->sync();

    $video->refresh();
    expect($result['posted'])->toBe(1)
        ->and($video->status)->toBe('posted')
        ->and($video->posted_at->getTimestamp())->toBe($at->getTimestamp()); // không phải giờ máy bật lại
});

test('publishing a post whose job is already posted needs no Chrome', function (): void {
    $account = ($this->account)();
    $post = Post::factory()->forAccount($account)->create(['status' => PostStatus::Scheduled, 'scheduled_at' => now()->subMinute()]);
    aheadJob($post->id, $account->id, 'posted', ['options' => ['schedule_time' => now()->toIso8601ZuluString()], 'result' => ['item_id' => '7700000000000000010']]);

    $result = app(ChromeAwareTikTokPublisher::class)->publish($post->fresh(['socialAccount']));

    expect($result['id'])->toBe('7700000000000000010')
        ->and(ChromeJob::query()->count())->toBe(1); // không tạo job mới
});

test('disabling a channel with posts already on TikTok warns the owner instead of pretending to cancel', function (): void {
    config(['fork.telegram.bot_token' => '123:T', 'fork.telegram.chat_id' => '9', 'trypost.self_hosted' => true]);
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => true])]);
    $account = ($this->account)();
    $post = Post::factory()->forAccount($account)->create(['status' => PostStatus::Scheduled, 'scheduled_at' => now()->addDays(2)]);
    AutoVideo::create([
        'hash' => 'zz', 'path' => '/x.mp4', 'batch_date' => '2026-11-09', 'file_name' => 'b_MIXKIT_1.mp4', 'product_code' => 'nano-dong',
        'status' => 'scheduled', 'social_account_id' => $account->id, 'post_id' => $post->id, 'scheduled_for' => now()->addDays(2),
    ]);
    aheadJob($post->id, $account->id);

    expect(FutureUploads::summarize($account->id))->toBe(['uploaded' => 1, 'waiting' => 0]);

    $owner = User::query()->find($this->workspace->user_id);
    $owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->actingAs($owner)->patch("/auto/accounts/{$account->id}", ['enabled' => false])->assertRedirect();

    Http::assertSent(fn ($r): bool => str_contains((string) $r['text'], '1 bài đã hẹn giờ trên TikTok'));
});

test('schedule_ahead_days is validated between 1 and 9', function (): void {
    config(['trypost.self_hosted' => true]);
    $account = ($this->account)();
    $owner = User::query()->find($this->workspace->user_id);
    $owner->update(['current_workspace_id' => $this->workspace->id]);
    $url = "/auto/accounts/{$account->id}";

    $this->actingAs($owner)->patch($url, ['schedule_ahead_days' => 10])->assertSessionHasErrors('schedule_ahead_days');
    $this->actingAs($owner)->patch($url, ['schedule_ahead_days' => 0])->assertSessionHasErrors('schedule_ahead_days');
    $this->actingAs($owner)->patch($url, ['schedule_ahead_days' => 7])->assertSessionHasNoErrors();

    expect(AutoAccount::query()->find($account->id)->schedule_ahead_days)->toBe(7);
});

test('stats are filled before 24h and linked through the post or the scheduled time', function (): void {
    $account = ($this->account)();
    $now = CarbonImmutable::parse('2026-11-10 12:00:00');

    $mk = function (array $video, array $pub) use ($account, $now): AutoVideo {
        static $n = 0;
        $n++;
        $v = AutoVideo::create($video + [
            'hash' => 'st'.$n, 'path' => '/x.mp4', 'batch_date' => '2026-11-09', 'file_name' => "s{$n}_MIXKIT_1.mp4", 'product_code' => 'nano-dong',
            'status' => 'posted', 'social_account_id' => $account->id,
        ]);
        $p = AnalyticsPublication::factory()->create($pub + ['workspace_id' => $this->workspace->id, 'social_account_id' => $account->id, 'remote_id' => 'rid'.$n]);
        AnalyticsPublicationDailySnapshot::factory()->create([
            'publication_id' => $p->id, 'date' => $now->toDateString(), 'provider_observed_at' => $now->subHour(), 'collected_at' => $now->subHour(),
            'views_count' => 10 * $n, 'reactions_count' => 1,
        ]);

        return $v;
    };

    $post = Post::factory()->forAccount($account)->create(['platform_post_id' => 'rid1']);
    $byPost = $mk(['posted_at' => $now->subHours(5), 'post_id' => $post->id], ['post_id' => null]);
    $byTime = $mk(['posted_at' => $now->subHours(5), 'scheduled_for' => $now->subHours(5)], ['provider_published_at' => $now->subHours(5)->addMinutes(2), 'post_id' => null]);

    $r = app(StatsCollector::class)->collect($now);

    expect($r['updated'])->toBe(2)
        ->and($byPost->fresh()->stats['latest']['views'])->toBe(10)
        ->and($byPost->fresh()->stats)->not->toHaveKey('h24')
        ->and($byTime->fresh()->stats['latest']['views'])->toBe(20);
});

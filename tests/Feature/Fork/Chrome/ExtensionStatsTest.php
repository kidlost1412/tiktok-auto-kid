<?php

declare(strict_types=1);

use App\Fork\AutoPost\Hub\HubOutboxItem;
use App\Fork\AutoPost\Models\AccountStat;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\VideoComment;
use App\Fork\AutoPost\Models\VideoSnapshot;
use App\Fork\AutoPost\Models\VideoStat;
use App\Fork\AutoPost\Stats\BuyIntent;
use App\Fork\AutoPost\Stats\StatsIngest;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Notify\Telegram;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

const ST_USER_ID = '7012345678901234567';
const ST_ORIGIN = 'chrome-extension://poffpbdhahodnkoandkagilkbhaipolo';

beforeEach(function () {
    config()->set('fork.chrome.extension_origin', ST_ORIGIN);
    Cache::forget('fork:chrome:pair');

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->social = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'username' => 'shop.demo', 'timezone' => 'Asia/Ho_Chi_Minh']);
    ChromeAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'tiktok_user_id' => ST_USER_ID, 'chrome_only' => false]);

    $chrome = app(ChromeJobs::class);
    $code = $chrome->newPairCode($this->account->id)['code'];
    $this->token = $this->postJson('/api/ext/pair', ['code' => $code, 'label' => 'Chrome', 'ext_version' => '1.4.0', 'protocol' => 1], stHeaders())->json('token');
    $this->postJson('/api/ext/hello', ['protocol' => 1, 'ext_version' => '1.4.0', 'identity' => ['username' => 'shop.demo', 'user_id' => ST_USER_ID]], stHeaders($this->token))->assertOk();
});

function stHeaders(?string $token = null): array
{
    return array_filter(['Authorization' => $token ? 'Bearer '.$token : null, 'X-Autotok-Protocol' => '1', 'X-Requested-With' => 'autotok']);
}

function stBody(array $extra): array
{
    return array_merge(['user_id' => ST_USER_ID, 'username' => 'shop.demo'], $extra);
}

function stVideo(object $t, array $o = []): AutoVideo
{
    static $n = 0;
    $n++;

    return AutoVideo::query()->create(array_merge([
        'hash' => hash('sha256', 'sv'.$n.random_bytes(4)),
        'path' => '/x/'.$n.'.mp4',
        'batch_date' => '2026-11-01',
        'file_name' => "NanoDong_a_b_MIXKIT_{$n}.mp4",
        'status' => 'posted',
        'social_account_id' => $t->social->id,
    ], $o));
}

test('stats endpoint stores per-video numbers, snapshots, followers and matches by tiktok_video_id', function () {
    $video = stVideo($this, ['tiktok_video_id' => '7570000000000000001', 'posted_at' => now()->subHours(2)]);

    $this->postJson('/api/ext/stats', stBody([
        'account' => ['followers' => 1500, 'follower_history' => [1400, 1450]],
        'videos' => [
            ['item_id' => '7570000000000000001', 'desc' => 'hello', 'post_time' => now()->subHours(2)->timestamp, 'duration_ms' => 20000, 'views' => 120, 'likes' => 9, 'comments' => 2, 'shares' => 1, 'saves' => 3,
                'insight' => ['avg_watch_s' => 3.26, 'finish_rate' => 0.0207, 'total_watch_s' => 400.5, 'new_followers' => 2, 'traffic' => [['key' => 'For You', 'value' => 0.9]]]],
            ['item_id' => '7570000000000000002', 'post_time' => now()->subDays(3)->timestamp, 'views' => 5],
            ['item_id' => 'bad'],
        ],
    ]), stHeaders($this->token))->assertOk()->assertJsonPath('stored', 2)->assertJsonPath('matched', 1)->assertJsonPath('followers', 1500);

    $stat = VideoStat::query()->where('item_id', '7570000000000000001')->first();
    expect($stat->views)->toBe(120)->and($stat->saves)->toBe(3)->and($stat->auto_video_id)->toBe($video->id)->and($stat->avg_watch_s)->toBe(3.26);
    expect(VideoSnapshot::query()->count())->toBe(2);
    expect(AccountStat::query()->first()->followers)->toBe(1500);

    $s = $video->fresh()->stats;
    expect($s['latest']['views'])->toBe(120)->and($s['insight']['finish_rate'])->toBe(0.0207)
        ->and($s['link'])->toBe('https://www.tiktok.com/@shop.demo/video/7570000000000000001');
});

test('stats endpoint refuses another identity and missing auth', function () {
    $this->postJson('/api/ext/stats', ['user_id' => '999', 'username' => 'other', 'videos' => []], stHeaders($this->token))->assertStatus(409);
    $this->postJson('/api/ext/stats', stBody(['videos' => []]), stHeaders())->assertStatus(401);
    $this->postJson('/api/ext/comments', stBody(['comments' => 'x']), stHeaders($this->token))->assertStatus(400);
});

test('matching falls back to the chrome job result item_id and then to posting time, and adopts the id', function () {
    $viaTime = stVideo($this, ['posted_at' => CarbonImmutable::now()->subHours(5)]);
    $far = stVideo($this, ['posted_at' => CarbonImmutable::now()->subHours(9)]);

    $this->postJson('/api/ext/stats', stBody(['videos' => [
        ['item_id' => '7570000000000000010', 'post_time' => CarbonImmutable::now()->subHours(5)->subMinutes(6)->timestamp, 'views' => 1],
    ]]), stHeaders($this->token))->assertOk()->assertJsonPath('matched', 1);

    expect($viaTime->fresh()->tiktok_video_id)->toBe('7570000000000000010')->and($far->fresh()->tiktok_video_id)->toBeNull();
});

test('24h and 72h milestones come from snapshots inside the window and are reported to the hub once', function () {
    config()->set('fork.auto.hub_api.key', 'k');
    $posted = CarbonImmutable::now()->subHours(30);
    $video = stVideo($this, ['tiktok_video_id' => '7570000000000000003', 'posted_at' => $posted, 'hub_id' => 'h1']);
    $ingest = app(StatsIngest::class);
    $item = fn (int $views) => ['videos' => [['item_id' => '7570000000000000003', 'post_time' => $posted->timestamp, 'views' => $views, 'likes' => 4]]];

    $ingest->ingest($this->social, $item(100), $posted->addHours(25));
    $ingest->ingest($this->social, $item(150), $posted->addHours(29));

    $s = $video->fresh()->stats;
    expect($s['h24']['views'])->toBe(100)->and($s)->not->toHaveKey('h72')->and($s['latest']['views'])->toBe(150);
    expect(HubOutboxItem::query()->where('kind', 'so-lieu')->count())->toBe(1);

    // Thu lần đầu quá muộn (ngoài khoảng bù 12 giờ) thì để trống, không ghi số của ngày khác.
    $late = stVideo($this, ['tiktok_video_id' => '7570000000000000004', 'posted_at' => $posted]);
    $ingest->ingest($this->social, ['videos' => [['item_id' => '7570000000000000004', 'post_time' => $posted->timestamp, 'views' => 900]]], $posted->addHours(60));
    expect($late->fresh()->stats)->not->toHaveKey('h24');
});

test('comments endpoint dedupes by comment_id, flags buy intent and links the video', function () {
    $video = stVideo($this, ['tiktok_video_id' => '7570000000000000001']);
    $row = fn (string $id, string $text, string $handle = 'khach') => ['comment_id' => $id, 'item_id' => '7570000000000000001', 'text' => $text, 'created_at' => now()->timestamp, 'like_count' => 1, 'reply_count' => 0, 'author_handle' => $handle, 'author_name' => 'K'];

    $body = stBody(['comments' => [
        $row('7571000000000000001', 'Giá bao nhiêu shop?'),
        $row('7571000000000000002', 'đẹp quá'),
        $row('7571000000000000003', 'giá 99k ship toàn quốc', 'shop.demo'),
        ['comment_id' => 'x', 'text' => 'bad'],
    ]]);

    $this->postJson('/api/ext/comments', $body, stHeaders($this->token))->assertOk()->assertJsonPath('new', 3)->assertJsonPath('buy_new', 1);
    $this->postJson('/api/ext/comments', $body, stHeaders($this->token))->assertOk()->assertJsonPath('new', 0);

    expect(VideoComment::query()->count())->toBe(3);
    $buy = VideoComment::query()->where('is_buy_intent', true)->first();
    expect($buy->comment_id)->toBe('7571000000000000001')->and($buy->auto_video_id)->toBe($video->id)->and($buy->intent_keywords)->toContain('giá');
});

test('buy intent keyword rules', function (string $text, bool $buy) {
    expect(BuyIntent::detect($text)['buy'])->toBe($buy);
})->with([
    ['Giá bao nhiêu vậy shop', true],
    ['gia bao nhieu a', true],
    ['còn hàng không ạ', true],
    ['con hang ko', true],
    ['ship về Đà Nẵng bao lâu', true],
    ['để lại sđt zalo nhé', true],
    ['inbox mình với', true],
    ['mua ở đâu vậy', true],
    ['Mình muốn mua 2 cái', true],
    ['video hay quá', false],
    ['đẹp quá chị ơi', false],
    ['gia đình mình rất thích', false],
    ['mùa đông mặc ấm', false],
    ['relationship goals', false],
]);

test('buy comments are sent to Telegram once and marked', function () {
    config()->set('fork.telegram.bot_token', 't');
    config()->set('fork.telegram.chat_id', '1');
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => true])]);

    if (! Telegram::configured()) {
        $this->markTestSkipped('Telegram config keys differ');
    }

    VideoComment::query()->create(['comment_id' => '7571000000000000009', 'social_account_id' => $this->social->id, 'item_id' => '7570000000000000001', 'text' => 'giá bao nhiêu', 'is_buy_intent' => true, 'commented_at' => now()]);

    Artisan::call('fork:alerts');
    Artisan::call('fork:alerts');

    Http::assertSentCount(1);
    expect(VideoComment::query()->first()->notified_at)->not->toBeNull();
});

test('so-lieu page shows real numbers, comments, followers and the old-extension banner', function () {
    $video = stVideo($this, ['tiktok_video_id' => '7570000000000000001', 'posted_at' => now()->subHours(3)]);
    app(StatsIngest::class)->ingest($this->social, ['account' => ['followers' => 10], 'videos' => [['item_id' => '7570000000000000001', 'post_time' => now()->subHours(3)->timestamp, 'views' => 321, 'likes' => 5, 'saves' => 2,
        'insight' => ['avg_watch_s' => 4.5, 'finish_rate' => 0.25]]]]);
    VideoComment::query()->create(['comment_id' => '7571000000000000009', 'social_account_id' => $this->social->id, 'item_id' => '7570000000000000001', 'auto_video_id' => $video->id, 'text' => 'giá bao nhiêu', 'is_buy_intent' => true, 'commented_at' => now()]);
    ChromeClient::query()->where('account_id', $this->account->id)->update(['ext_version' => '1.1.0']);

    $this->actingAs($this->owner)->get('/auto/so-lieu?range=7d')->assertOk()->assertInertia(fn ($p) => $p
        ->component('fork/SoLieu')
        ->where('videos.0.views', 321)->where('videos.0.saves', 2)->where('videos.0.avg_watch_s', 4.5)->where('videos.0.finish_rate', 25)
        ->where('comments.counts.buy', 1)->where('comments.rows.0.buy', true)
        ->where('followers.current', 10)
        ->where('extension.outdated', true)->where('extension.min', '1.4.0')
        ->whereNot('collected_at', null));

    $this->actingAs($this->owner)->get('/auto/kho/video/'.$video->id.'/info')->assertOk()->assertJsonPath('stats.saves', 2)->assertJsonPath('comments.total', 1);
});

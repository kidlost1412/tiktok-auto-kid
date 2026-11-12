<?php

declare(strict_types=1);

use App\Enums\SocialAccount\Platform;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\VideoStat;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Notify\Telegram;
use App\Fork\Notify\TelegramSettings;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Http\Client\Factory;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

function sentTexts(): array
{
    return Http::recorded()->map(fn ($pair) => $pair[0]->data()['text'] ?? '')->values()->all();
}

function fakeTelegram(): void
{
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => true])]);
}

beforeEach(function () {
    Cache::flush();
    config()->set('trypost.self_hosted', true);
    config()->set('fork.slim.enabled', false);
    config()->set('fork.telegram.bot_token', '123:TEST');
    config()->set('fork.telegram.chat_id', '999');
    config()->set('fork.telegram.min_interval_ms', 0);
    config()->set('fork.telegram.backoff_ms', [0, 0]);
    fakeTelegram();

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->social = SocialAccount::factory()->create([
        'workspace_id' => $this->workspace->id,
        'platform' => Platform::TikTok,
        'username' => 'kenh1',
    ]);
});

test('telegram is a no-op when not configured', function () {
    config()->set('fork.telegram.bot_token', '');

    expect(Telegram::configured())->toBeFalse();
    expect(Telegram::send('x'))->toBeFalse();
    $this->artisan('fork:alerts')->assertSuccessful();
    Http::assertNothingSent();
});

test('send posts to the bot api and rate limits duplicates by key', function () {
    expect(Telegram::send('xin chào', 'k1'))->toBeTrue();
    expect(Telegram::send('xin chào', 'k1'))->toBeFalse();
    expect(Telegram::send('khác', 'k2'))->toBeTrue();

    Http::assertSentCount(2);
    Http::assertSent(fn ($r) => str_contains($r->url(), 'bot123:TEST/sendMessage') && $r['chat_id'] === '999');
});

test('a failed send releases the dedupe key so it is retried', function () {
    Http::swap(new Factory);
    Http::fake(['api.telegram.org/*' => Http::sequence()->push(['ok' => false], 400)->push(['ok' => true])]);

    expect(Telegram::send('a', 'k'))->toBeFalse();
    expect(Telegram::send('a', 'k'))->toBeTrue();
});

test('an offline chrome with queued work is reported once an hour', function () {
    $client = ChromeClient::query()->create([
        'account_id' => $this->account->id, 'label' => 'C', 'token_hash' => hash('sha256', 'a'), 'ext_version' => '1', 'protocol' => 1,
        'tiktok_user_id' => '77', 'tiktok_username' => 'kenh1', 'last_seen_at' => now()->subMinutes(20),
    ]);
    ChromeAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'tiktok_user_id' => '77']);

    $this->artisan('fork:alerts')->assertSuccessful();
    expect(sentTexts())->toBe([]);

    $post = Post::factory()->create(['workspace_id' => $this->workspace->id]);
    ChromeJob::query()->create([
        'id' => 'ej_'.str_repeat('a', 24), 'post_id' => $post->id, 'social_account_id' => $this->social->id, 'attempt' => 1,
        'expect_user_id' => '77', 'nonce' => 'n1', 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1, 'video_mime' => 'video/mp4', 'mode' => 'now', 'caption' => 'c', 'options' => [], 'state' => 'queued',
    ]);

    $this->artisan('fork:alerts')->assertSuccessful();
    $this->artisan('fork:alerts')->assertSuccessful();

    expect(sentTexts())->toHaveCount(1)->and(sentTexts()[0])->toContain('@kenh1')->toContain('mất kết nối');

    $client->update(['last_seen_at' => now()]);
    Cache::flush();
    fakeTelegram();
    $this->artisan('fork:alerts')->assertSuccessful();
    expect(sentTexts())->toBe([]);
});

test('failed chrome jobs are reported once with reason and caption', function () {
    $post = Post::factory()->create(['workspace_id' => $this->workspace->id]);
    ChromeJob::query()->create([
        'id' => 'ej_'.str_repeat('b', 24), 'post_id' => $post->id, 'social_account_id' => $this->social->id, 'attempt' => 1,
        'expect_user_id' => '77', 'nonce' => 'n1', 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1, 'video_mime' => 'video/mp4', 'mode' => 'now', 'caption' => 'Chú thích rất hay #nongnghiep', 'options' => [], 'state' => 'rejected',
        'note' => 'TikTok từ chối: video trùng',
    ]);

    $this->artisan('fork:alerts')->assertSuccessful();
    $this->artisan('fork:alerts')->assertSuccessful();

    $texts = sentTexts();
    expect($texts)->toHaveCount(1);
    expect($texts[0])->toContain('Đăng lỗi')->toContain('video trùng')->toContain('Chú thích rất hay')->toContain('@kenh1')->toContain('Cách xử lý');
});

test('failed auto videos and paused cart links are reported', function () {
    AutoVideo::query()->create([
        'hash' => 'h1', 'path' => '/x.mp4', 'batch_date' => now()->toDateString(), 'file_name' => 'a_MIXKIT_1.mp4',
        'status' => AutoVideo::FAILED, 'skip_reason' => 'file mất', 'social_account_id' => $this->social->id, 'caption' => 'cap',
    ]);
    ProductLink::query()->create([
        'social_account_id' => $this->social->id, 'auto_product_id' => 'SP1', 'shop_product_id' => '123', 'display_name' => 'Phân bón',
        'paused_reason' => 'Sản phẩm hết hàng',
    ]);

    $this->artisan('fork:alerts')->assertSuccessful();

    $all = implode("\n", sentTexts());
    expect($all)->toContain('file mất')->toContain('Giỏ hàng hết hàng')->toContain('Sản phẩm hết hàng')->toContain('Phân bón');
});

test('low stock is reported when new videos are fewer than the daily cap', function () {
    config()->set('fork.auto.hub_api.key', '');
    // Tránh 21:00 (giờ gửi tổng kết ngày) để chỉ có đúng 1 tin cảnh báo.
    $this->travelTo(now('Asia/Ho_Chi_Minh')->setTime(15, 0)->utc());
    AutoAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'daily_cap' => 5]);
    AutoProduct::query()->create(['code' => 'SP1', 'name' => 'SP1', 'short_name' => 'SP1', 'enabled' => true]);

    foreach (range(1, 3) as $i) {
        AutoVideo::query()->create([
            'hash' => "s{$i}", 'path' => '/x.mp4', 'batch_date' => now()->toDateString(), 'file_name' => "v{$i}_MIXKIT_1.mp4",
            'product_code' => 'SP1', 'status' => AutoVideo::NEW, 'caption' => "Caption {$i}",
        ]);
    }

    $this->artisan('fork:alerts')->assertSuccessful();
    expect(sentTexts())->toHaveCount(1)->and(sentTexts()[0])->toContain('Kho sắp hết video')->toContain('<code>3</code> video')->toContain('<code>5</code> bài/ngày')->toContain('<code>0,6</code> ngày');

    AutoAccount::query()->update(['daily_cap' => 3]);
    Cache::flush();
    fakeTelegram();
    $this->artisan('fork:alerts')->assertSuccessful();
    expect(sentTexts())->toBe([]);
});

test('low stock counts the same eligible videos as reserveNext', function () {
    config()->set('fork.auto.hub_api.key', '');
    $this->travelTo(now('Asia/Ho_Chi_Minh')->setTime(15, 0)->utc());
    AutoAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'daily_cap' => 10]);
    AutoProduct::query()->create(['code' => 'SP1', 'name' => 'SP1', 'short_name' => 'SP1', 'enabled' => true]);
    AutoProduct::query()->create(['code' => 'OFF', 'name' => 'OFF', 'short_name' => 'OFF', 'enabled' => false]);

    $make = function (string $hash, array $o = []): void {
        AutoVideo::query()->create(array_merge([
            'hash' => $hash, 'path' => "/{$hash}.mp4", 'batch_date' => now()->toDateString(), 'file_name' => "{$hash}.mp4",
            'product_code' => 'SP1', 'status' => AutoVideo::NEW, 'source' => 'hub', 'caption' => 'Caption',
        ], $o));
    };

    // Đủ điều kiện: video hub/kho (không cần tên MIXKIT) và bản MIXKIT kiểu cũ.
    $make('e1');
    $make('e2', ['source' => 'kho']);
    $make('e3', ['source' => 'ra', 'file_name' => 'e3_MIXKIT_1.mp4']);
    // Không đủ điều kiện: thiếu caption, file đã xoá, kiểu cũ không MIXKIT, sản phẩm tắt, không còn new.
    $make('x1', ['caption' => null]);
    $make('x2', ['files_deleted_at' => now()]);
    $make('x3', ['source' => 'ra']);
    $make('x4', ['product_code' => 'OFF']);
    $make('x5', ['status' => AutoVideo::POSTED]);

    expect(AutoVideo::query()->eligibleNew()->whereIn('product_code', ['SP1'])->count())->toBe(3);

    $this->artisan('fork:alerts')->assertSuccessful();
    expect(sentTexts())->toHaveCount(1)->and(sentTexts()[0])->toContain('Kho sắp hết video')->toContain('<code>3</code> video');
});

test('the daily summary does not count imported posts still scheduled in the future', function () {
    AutoAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'daily_cap' => 0]);
    config()->set('fork.telegram.timezone', 'Asia/Ho_Chi_Minh');
    TelegramSettings::savePrefsFromForm(['posted' => false, 'highlight' => false], '21:00', false, '23:00', '06:00');

    $this->travelTo(now('Asia/Ho_Chi_Minh')->setTime(21, 10)->utc());
    foreach ([['f1', now()->subHour()], ['f2', now()->addDays(2)], ['f3', now()->addMinutes(30)]] as [$hash, $at]) {
        AutoVideo::query()->create([
            'hash' => $hash, 'path' => "/{$hash}.mp4", 'batch_date' => now()->toDateString(), 'file_name' => "{$hash}_MIXKIT_1.mp4",
            'status' => AutoVideo::POSTED, 'social_account_id' => $this->social->id, 'posted_at' => $at,
        ]);
    }

    $this->artisan('fork:alerts')->assertSuccessful();

    expect(sentTexts())->toHaveCount(1)->and(sentTexts()[0])->toContain('<code>1/0</code>');
});

test('the daily summary goes out only at 21:00 local time and once', function () {
    AutoAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'daily_cap' => 0]);
    config()->set('fork.telegram.timezone', 'Asia/Ho_Chi_Minh');
    TelegramSettings::savePrefsFromForm(['posted' => false, 'highlight' => false], '21:00', false, '23:00', '06:00');

    $this->travelTo(now('Asia/Ho_Chi_Minh')->setTime(21, 10)->utc());
    AutoVideo::query()->create([
        'hash' => 'd1', 'path' => '/x.mp4', 'batch_date' => now()->toDateString(), 'file_name' => 'd1_MIXKIT_1.mp4',
        'status' => AutoVideo::POSTED, 'social_account_id' => $this->social->id, 'posted_at' => now()->subHour(),
    ]);
    VideoStat::query()->create(['social_account_id' => $this->social->id, 'item_id' => '700', 'caption' => 'Video hay', 'posted_at' => now()->subHour(), 'views' => 1500, 'collected_at' => now()]);

    $this->artisan('fork:alerts')->assertSuccessful();
    $this->artisan('fork:alerts')->assertSuccessful();

    expect(sentTexts())->toHaveCount(1)->and(sentTexts()[0])->toContain('Tổng kết')->toContain('<code>1/0</code>')->toContain('1.500')->toContain('Video hay')->toContain('@kenh1');

    Cache::flush();
    fakeTelegram();
    $this->travelTo(now('Asia/Ho_Chi_Minh')->setTime(15, 0)->utc());
    $this->artisan('fork:alerts')->assertSuccessful();
    expect(sentTexts())->toBe([]);
});

test('only the owner can send a test message and the page shows the state', function () {
    $member = User::factory()->create(['account_id' => $this->account->id]);

    $this->actingAs($member)->post('/settings/chrome/telegram-test')->assertForbidden();

    $this->actingAs($this->owner)->get('/settings/chrome')
        ->assertInertia(fn ($page) => $page->where('telegram.configured', true));

    $this->actingAs($this->owner)->post('/settings/chrome/telegram-test')->assertSessionHas('flash.success');
    Http::assertSentCount(1);

    config()->set('fork.telegram.chat_id', '');
    $this->actingAs($this->owner)->post('/settings/chrome/telegram-test')->assertSessionHas('flash.error');
    Http::assertSentCount(1);
});

test('the alerts command is scheduled every five minutes', function () {
    $events = collect(app(Schedule::class)->events())
        ->filter(fn ($e) => str_contains((string) $e->command, 'fork:alerts'));

    expect($events)->toHaveCount(1)->and($events->first()->expression)->toBe('*/5 * * * *');
});

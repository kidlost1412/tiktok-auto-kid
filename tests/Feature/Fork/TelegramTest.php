<?php

declare(strict_types=1);

use App\Enums\SocialAccount\Platform;
use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\AutoPost\Models\VideoComment;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Notify\Message;
use App\Fork\Notify\Messages;
use App\Fork\Notify\Notifier;
use App\Fork\Notify\Telegram;
use App\Fork\Notify\TelegramApi;
use App\Fork\Notify\TelegramSettings;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Http\Client\Factory;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

const FAKE_TOKEN = '123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw0';

function texts(): array
{
    return Http::recorded()->filter(fn ($p) => str_contains($p[0]->url(), 'sendMessage'))->map(fn ($p) => $p[0]->data()['text'] ?? '')->values()->all();
}

beforeEach(function () {
    Cache::flush();
    config()->set('trypost.self_hosted', true);
    config()->set('fork.slim.enabled', false);
    config()->set('fork.telegram.bot_token', '');
    config()->set('fork.telegram.chat_id', '');
    config()->set('fork.telegram.min_interval_ms', 0);
    config()->set('fork.telegram.backoff_ms', [0, 0]);
    config()->set('fork.telegram.timezone', 'Asia/Ho_Chi_Minh');
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => true])]);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->social = SocialAccount::factory()->create(['workspace_id' => $this->workspace->id, 'platform' => Platform::TikTok, 'username' => 'kenh1']);
});

function connect(): void
{
    TelegramSettings::saveToken(FAKE_TOKEN, 'bot_test');
    TelegramSettings::saveChat('555', 'Chủ App');
}

test('the token is stored encrypted, masked in the page and env is only a fallback', function () {
    config()->set('fork.telegram.bot_token', '999999:ENVTOKENENVTOKENENVTOKENENVTOKENXX');
    config()->set('fork.telegram.chat_id', '42');
    expect(TelegramSettings::token())->toStartWith('999999:')->and(TelegramSettings::chatId())->toBe('42');

    connect();
    expect(TelegramSettings::token())->toBe(FAKE_TOKEN)->and(TelegramSettings::chatId())->toBe('555');
    expect(AutoSetting::read('telegram.bot_token'))->not->toContain('AAHdqTcv')->not->toContain('123456789');
    expect(TelegramSettings::maskedToken())->not->toContain('AAHdqTcv')->toEndWith('saw0');

    $res = $this->actingAs($this->owner)->get('/settings/telegram')->assertOk();
    expect($res->getContent())->not->toContain('AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw0');
    $res->assertInertia(fn ($p) => $p->component('settings/fork/Telegram')->where('has_token', true)->where('configured', true)->where('bot.link', 'https://t.me/bot_test')->has('previews', 10)->has('types', 9));

    TelegramSettings::clear();
    expect(TelegramSettings::token())->toStartWith('999999:');
});

test('saving a token calls getMe and rejects bad tokens', function () {
    Http::swap(new Factory);
    Http::fake(['api.telegram.org/*/getMe' => Http::response(['ok' => true, 'result' => ['id' => 1, 'username' => 'bot_test', 'first_name' => 'B']])]);

    $this->actingAs($this->owner)->put('/settings/telegram/token', ['token' => 'nonsense'])->assertSessionHas('flash.error');
    expect(TelegramSettings::hasToken())->toBeFalse();

    $this->actingAs($this->owner)->put('/settings/telegram/token', ['token' => FAKE_TOKEN])->assertSessionHas('flash.success');
    expect(TelegramSettings::botUsername())->toBe('bot_test')->and(TelegramSettings::token())->toBe(FAKE_TOKEN);

    Http::swap(new Factory);
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => false], 401)]);
    expect(TelegramApi::getMe(FAKE_TOKEN))->toBeNull();
    $this->actingAs($this->owner)->put('/settings/telegram/token', ['token' => '555555:'.str_repeat('B', 35)])->assertSessionHas('flash.error');
    expect(TelegramSettings::token())->toBe(FAKE_TOKEN);
});

test('getUpdates picks the latest private chat and the owner confirms it', function () {
    TelegramSettings::saveToken(FAKE_TOKEN, 'bot_test');
    Http::swap(new Factory);
    Http::fake(['api.telegram.org/*/getUpdates*' => Http::response(['ok' => true, 'result' => [
        ['update_id' => 1, 'message' => ['chat' => ['id' => 11, 'type' => 'private', 'first_name' => 'Cũ']]],
        ['update_id' => 2, 'message' => ['chat' => ['id' => -100, 'type' => 'group', 'title' => 'Nhóm']]],
        ['update_id' => 3, 'message' => ['chat' => ['id' => 2200123, 'type' => 'private', 'first_name' => 'Minh', 'last_name' => 'Nguyễn']]],
    ]])]);

    $this->actingAs($this->owner)->post('/settings/telegram/detect-chat')->assertSessionHas('flash.success');
    $this->actingAs($this->owner)->get('/settings/telegram')->assertInertia(fn ($p) => $p->where('candidate.id', '2200123')->where('candidate.name', 'Minh Nguyễn'));

    $this->actingAs($this->owner)->put('/settings/telegram/chat', ['chat_id' => 'abc'])->assertSessionHas('flash.error');
    $this->actingAs($this->owner)->put('/settings/telegram/chat', ['chat_id' => '2200123'])->assertSessionHas('flash.success');
    expect(TelegramSettings::chatId())->toBe('2200123')->and(TelegramSettings::chatName())->toBe('Minh Nguyễn');

    Http::swap(new Factory);
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => true, 'result' => []])]);
    $this->actingAs($this->owner)->post('/settings/telegram/detect-chat')->assertSessionHas('flash.error');
});

test('sends use HTML parse mode, scrub tokens, retry on 5xx and not on 4xx', function () {
    connect();
    expect(Telegram::send('xin chào '.FAKE_TOKEN))->toBeTrue();
    Http::assertSent(fn ($r) => $r['parse_mode'] === 'HTML' && $r['chat_id'] === '555' && ! str_contains($r['text'], 'AAHdqTcv'));

    Http::swap(new Factory);
    Http::fake(['api.telegram.org/*' => Http::sequence()->push([], 500)->push(['ok' => true, 'parameters' => []], 429)->push(['ok' => true])]);
    expect(Telegram::send('a'))->toBeTrue();
    Http::assertSentCount(3);

    Http::swap(new Factory);
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => false], 400)]);
    expect(Telegram::send('b'))->toBeFalse();
    Http::assertSentCount(1);
});

test('each message builder has a strong first line, key facts and escaped content', function () {
    $m = Messages::samples();

    expect($m['posted']['message']->text)->toStartWith('✅ <b>Đã lên TikTok</b> · <b>@kenh_mau</b>')->toContain('Giờ đăng')->toContain('Phân bón hữu cơ')->toContain('tiktok.com/@kenh_mau/video/7000000000000000000')->toContain('/auto/kho?tab=dang&amp;video=1');
    expect($m['failed']['message']->text)->toStartWith('❌ <b>Đăng lỗi</b>')->toContain('Sản phẩm trong giỏ đã hết hàng')->toContain('Cách xử lý');
    expect($m['chrome_offline']['message']->text)->toStartWith('🔌 <b>Chrome mất kết nối</b>')->toContain('25 phút');
    expect($m['chrome_back']['message']->text)->toStartWith('✅ <b>Chrome đã kết nối lại</b>')->toContain('38 phút');
    expect($m['hub_offline']['message']->text)->toStartWith('🔌 <b>Hub Xưởng Video mất kết nối</b>');
    expect($m['cart']['message']->text)->toStartWith('🛒 <b>Giỏ hàng hết hàng</b>')->toContain('SP01');
    expect($m['stock']['message']->text)->toStartWith('📦 <b>Kho sắp hết video</b>')->toContain('<code>0,8</code> ngày');
    expect($m['buy_comment']['message']->text)->toStartWith('💬 <b>Khách hỏi mua</b>')->toContain('Chị Lan')->toContain('Trả lời trên TikTok');
    expect($m['highlight']['message']->text)->toStartWith('📈 <b>Video nổi bật sau 24 giờ</b>')->toContain('<code>12.400</code>')->toContain('3,1×');
    expect($m['daily']['message']->text)->toStartWith('📊 <b>Tổng kết ngày')->toContain('<code>6/8</code>')->toContain('1. <code>12.400</code>')->toContain('Ngày mai')->toContain('08:15');

    $evil = Messages::buyComment(['user' => 'a', 'author' => '<b>x</b>', 'text' => '<script>alert(1)</script>'], 'k');
    expect($evil->text)->not->toContain('<script>')->toContain('&lt;script&gt;');

    [$why] = Messages::friendlyReason('', 'uncertain');
    expect($why)->toContain('Chưa rõ');
});

test('more than five events of a type in one run become one grouped message and dedupe', function () {
    connect();
    $make = fn (int $n) => collect(range(1, $n))->map(fn ($i) => new Message('posted', "p:{$i}", "Bài {$i}", "tin {$i}"));

    expect(Notifier::dispatch('posted', $make(12)))->toBe(1);
    expect(texts())->toHaveCount(1)->and(texts()[0])->toContain('12 bài đã lên')->toContain('Bài 1')->toContain('… và 2 mục');
    expect(Notifier::dispatch('posted', $make(12)))->toBe(0);

    Http::swap(new Factory);
    Http::fake(['api.telegram.org/*' => Http::response(['ok' => true])]);
    expect(Notifier::dispatch('posted', $make(17)->slice(12)->values()))->toBe(5);
    expect(texts())->toHaveCount(5);
});

test('disabled types are not sent and keep their dedupe key for later', function () {
    connect();
    TelegramSettings::savePrefsFromForm(['failed' => false], '21:00', false, '23:00', '06:00');
    $m = new Message('failed', 'f1', 'x', 'lỗi');

    expect(Notifier::dispatch('failed', [$m]))->toBe(0);
    Http::assertNothingSent();

    TelegramSettings::savePrefsFromForm([], '21:00', false, '23:00', '06:00');
    expect(TelegramSettings::enabled('failed'))->toBeTrue()->and(Notifier::dispatch('failed', [$m]))->toBe(1);
});

test('quiet hours hold non-urgent messages and release them in the morning', function () {
    connect();
    TelegramSettings::savePrefsFromForm([], '21:00', true, '23:00', '06:00');
    $normal = new Message('posted', 'q1', 'a', 'đã lên');
    $urgent = new Message('failed', 'q2', 'b', 'lỗi');

    $this->travelTo(now('Asia/Ho_Chi_Minh')->setTime(1, 30)->utc());
    expect(TelegramSettings::inQuietHours())->toBeTrue();
    expect(Notifier::dispatch('posted', [$normal]))->toBe(0)->and(Notifier::dispatch('failed', [$urgent]))->toBe(1);

    $this->travelTo(now('Asia/Ho_Chi_Minh')->setTime(7, 0)->utc());
    expect(TelegramSettings::inQuietHours())->toBeFalse();
    expect(Notifier::dispatch('posted', [$normal]))->toBe(1);

    $this->travelTo(now('Asia/Ho_Chi_Minh')->setTime(23, 30)->utc());
    expect(TelegramSettings::inQuietHours())->toBeTrue();
});

test('chrome offline is paired with a reconnect message with the duration', function () {
    connect();
    $client = ChromeClient::query()->create([
        'account_id' => $this->account->id, 'label' => 'C', 'token_hash' => hash('sha256', 'a'), 'ext_version' => '1', 'protocol' => 1,
        'tiktok_user_id' => '77', 'tiktok_username' => 'kenh1', 'last_seen_at' => now()->subMinutes(20),
    ]);
    ChromeAccount::query()->create(['social_account_id' => $this->social->id, 'enabled' => true, 'tiktok_user_id' => '77']);
    $post = Post::factory()->create(['workspace_id' => $this->workspace->id]);
    ChromeJob::query()->create([
        'id' => 'ej_'.str_repeat('c', 24), 'post_id' => $post->id, 'social_account_id' => $this->social->id, 'attempt' => 1,
        'expect_user_id' => '77', 'nonce' => 'n1', 'media_path' => 'x.mp4', 'video_name' => 'x.mp4', 'video_size' => 1, 'video_mime' => 'video/mp4', 'mode' => 'now', 'caption' => 'c', 'options' => [], 'state' => 'queued',
    ]);

    $this->artisan('fork:alerts')->assertSuccessful();
    expect(texts())->toHaveCount(1)->and(texts()[0])->toContain('Chrome mất kết nối');

    $client->update(['last_seen_at' => now()]);
    $this->artisan('fork:alerts')->assertSuccessful();
    expect(texts())->toHaveCount(2)->and(texts()[1])->toContain('đã kết nối lại')->toContain('20 phút');

    $this->artisan('fork:alerts')->assertSuccessful();
    expect(texts())->toHaveCount(2);
});

test('buy comments are sent one per comment with the reply link and marked notified', function () {
    connect();
    TelegramSettings::since();
    VideoComment::query()->create([
        'comment_id' => 'c1', 'social_account_id' => $this->social->id, 'item_id' => '700', 'author_name' => 'Chị Lan',
        'text' => 'giá bao nhiêu shop', 'is_buy_intent' => true, 'commented_at' => now(),
    ]);

    $this->artisan('fork:alerts')->assertSuccessful();
    expect(texts())->toHaveCount(1)->and(texts()[0])->toContain('Khách hỏi mua')->toContain('giá bao nhiêu')->toContain('tiktok.com/@kenh1/video/700');
    expect(VideoComment::query()->first()->notified_at)->not->toBeNull();
});

test('sample messages and the test message are owner only and sent unconditionally', function () {
    connect();
    TelegramSettings::savePrefsFromForm(['daily' => false], '21:00', true, '00:00', '23:59');
    $member = User::factory()->create(['account_id' => $this->account->id]);

    $this->actingAs($member)->post('/settings/telegram/sample/daily')->assertForbidden();
    $this->actingAs($this->owner)->post('/settings/telegram/sample/nope')->assertNotFound();
    $this->actingAs($this->owner)->post('/settings/telegram/sample/daily')->assertSessionHas('flash.success');
    $this->actingAs($this->owner)->post('/settings/telegram/test')->assertSessionHas('flash.success');
    expect(texts())->toHaveCount(2)->and(texts()[0])->toContain('Tin mẫu')->toContain('Tổng kết ngày');

    $this->actingAs($this->owner)->patch('/settings/telegram/prefs', ['summary_time' => '25:99'])->assertSessionHas('flash.error');
    $this->actingAs($this->owner)->patch('/settings/telegram/prefs', ['summary_time' => '20:30', 'toggles' => ['posted' => false], 'quiet' => ['enabled' => true, 'start' => '22:00', 'end' => '05:00']])->assertSessionHas('flash.success');
    expect(TelegramSettings::summaryTime())->toBe('20:30')->and(TelegramSettings::enabled('posted'))->toBeFalse()->and(TelegramSettings::quiet()['start'])->toBe('22:00');

    $this->actingAs($this->owner)->delete('/settings/telegram')->assertSessionHas('flash.success');
    expect(TelegramSettings::hasToken())->toBeFalse();
});

test('the health strip chips link to their settings pages', function () {
    $src = file_get_contents(base_path('resources/js/components/fork/auto/HealthStrip.vue'));

    expect($src)->toContain("href: '/settings/telegram'")->toContain("href: '/settings/chrome'")->toContain("href: '/xuong'")->toContain("href: '/auto#kenh'");
});

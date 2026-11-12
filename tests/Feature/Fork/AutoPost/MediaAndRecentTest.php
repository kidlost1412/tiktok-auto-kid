<?php

declare(strict_types=1);

use App\Fork\AutoPost\Media\ChannelAvatars;
use App\Fork\AutoPost\Media\RemoteImage;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Inertia\Testing\AssertableInertia;

const PNG_1PX = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    Storage::fake('public');

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh']);
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
});

function mvideo(object $test, string $status, array $o = []): AutoVideo
{
    static $n = 0;
    $n++;

    return AutoVideo::query()->create(array_merge([
        'hash' => hash('sha256', 'm'.$n), 'path' => "/x/m{$n}.mp4", 'batch_date' => '2026-01-05',
        'file_name' => "m{$n}.mp4", 'product_code' => 'nano-dong', 'source' => 'kho', 'status' => $status, 'social_account_id' => $test->sa->id,
    ], $o));
}

test('recent posts exclude imported videos whose posted_at is still in the future', function (): void {
    AutoAccount::query()->create(['social_account_id' => $this->sa->id, 'enabled' => true]);
    $past = mvideo($this, 'posted', ['posted_at' => now()->subHour()]);
    $future = mvideo($this, 'posted', ['posted_at' => now()->addDays(2)]);

    $this->actingAs($this->owner)->get('/auto')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->has('recent', 1)
        ->where('recent.0.id', $past->id)
        ->where('products.0.counts.posted', 1)
        ->where('products.0.counts.scheduled', 1));

    expect($future->fresh()->effectiveStatus())->toBe('scheduled');
});

test('kho tabs and counts treat future posted videos as scheduled, not posted', function (): void {
    $past = mvideo($this, 'posted', ['posted_at' => now()->subHour()]);
    $future = mvideo($this, 'posted', ['posted_at' => now()->addDays(2), 'scheduled_for' => now()->addDays(2)]);

    $this->actingAs($this->owner)->get('/auto/kho?tab=dang')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->where('counts.dang', 1)->where('counts.xep', 1)
        ->has('videos.data', 1)->where('videos.data.0.id', $past->id));

    $this->actingAs($this->owner)->get('/auto/kho?tab=xep')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->has('videos.data', 1)->where('videos.data.0.id', $future->id)->where('videos.data.0.status', 'scheduled')
        ->where('videos.data.0.on_tiktok_schedule', true));
});

test('video info endpoint returns the viewer payload and is owner only', function (): void {
    $v = mvideo($this, 'posted', ['posted_at' => now()->subHour(), 'caption' => 'xin chào', 'stats' => ['latest' => ['views' => 10, 'likes' => 2, 'comments' => 1, 'shares' => 0]]]);

    $this->actingAs($this->owner)->getJson("/auto/kho/video/{$v->id}/info")->assertOk()
        ->assertJsonPath('id', $v->id)->assertJsonPath('stats.views', 10)->assertJsonPath('caption', 'xin chào');

    $this->actingAs(User::factory()->create(['account_id' => $this->account->id]))->getJson("/auto/kho/video/{$v->id}/info")->assertForbidden();
});

test('product image is downloaded once, served locally, and shown on the page', function (): void {
    File::deleteDirectory(storage_path('app/product-covers'));
    Http::fake(['https://p16-oec-sg.ibyteimg.com/*' => Http::response(base64_decode(PNG_1PX), 200, ['Content-Type' => 'image/png']), '*' => Http::response('', 404)]);
    Http::fake(['*' => Http::response('', 404)]);

    $shop = ShopProduct::query()->create(['social_account_id' => $this->sa->id, 'product_id' => '7600000000000000001', 'title' => 'SP', 'cover_url' => 'https://p16-oec-sg.ibyteimg.com/x.png', 'synced_at' => now()]);
    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => '7600000000000000001', 'display_name' => 'SP']);
    AutoAccount::query()->create(['social_account_id' => $this->sa->id, 'enabled' => true]);

    $this->actingAs($this->owner)->get('/auto')->assertInertia(fn (AssertableInertia $p) => $p
        ->where('products.0.image', fn ($url) => str_starts_with((string) $url, "/auto/anh-san-pham/{$shop->id}")));

    $this->actingAs($this->owner)->get("/auto/anh-san-pham/{$shop->id}")->assertOk()->assertHeader('Content-Type', 'image/png');
    $this->actingAs($this->owner)->get("/auto/anh-san-pham/{$shop->id}")->assertOk();
    Http::assertSentCount(1);

    $this->actingAs(User::factory()->create(['account_id' => $this->account->id]))->get("/auto/anh-san-pham/{$shop->id}")->assertForbidden();
    File::deleteDirectory(storage_path('app/product-covers'));
});

test('remote images only come from TikTok hosts over https', function (): void {
    expect(RemoteImage::allowed('https://p16-sign.tiktokcdn.com/a.jpeg'))->toBeTrue()
        ->and(RemoteImage::allowed('http://p16-sign.tiktokcdn.com/a.jpeg'))->toBeFalse()
        ->and(RemoteImage::allowed('https://evil.example.com/a.jpeg'))->toBeFalse()
        ->and(RemoteImage::allowed('https://tiktokcdn.com.evil.com/a.jpeg'))->toBeFalse();
});

test('channel avatar is stored locally and exposed on the social account', function (): void {
    Http::fake(['https://p16-sign.tiktokcdn.com/*' => Http::response(base64_decode(PNG_1PX), 200)]);

    expect(app(ChannelAvatars::class)->store($this->sa, 'https://p16-sign.tiktokcdn.com/a.png'))->toBeTrue();

    $raw = $this->sa->fresh()->getRawOriginal('avatar_url');
    expect($raw)->toStartWith('avatars/tiktok-');
    Storage::disk('public')->assertExists($raw);
    expect($this->sa->fresh()->avatar_url)->not->toBeNull()
        ->and(ChannelAvatars::needsRefresh($this->sa->fresh()))->toBeFalse();

    expect(app(ChannelAvatars::class)->store($this->sa->fresh(), 'https://evil.example.com/a.png'))->toBeFalse();
});

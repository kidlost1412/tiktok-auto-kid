<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Onboarding;
use App\Fork\Chrome\Models\ChromeClient;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.auto.hub_api.key', null);
    config()->set('fork.xuong.url', 'http://xuong.test');
    config()->set('fork.xuong.health_url', 'http://xuong.test/health');
    Cache::forget(Onboarding::HUB_CACHE_KEY);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id, 'timezone' => 'Asia/Ho_Chi_Minh']);
    AutoProduct::query()->create(['code' => 'nano-dong', 'name' => 'Nano Đồng', 'short_name' => 'NanoĐồng', 'facts' => [], 'enabled' => true]);
});

function onbHubUp(bool $claude = true, bool $voice = true): void
{
    Http::fake([
        'xuong.test/health' => Http::response(['ok' => true, 'dang_chay_lo' => false]),
        'xuong.test/api/khoa-giong' => Http::response(['ok' => true, 'co' => $voice, 'cuoi' => $voice ? 'abcd' : '']),
        'xuong.test/api/tai-khoan-ds' => Http::response([['ma' => 'tk1', 'ten' => 'Tài khoản 1', 'dang_nhap' => $claude]]),
    ]);
}

function onbReady(object $t): void
{
    ChromeClient::query()->create([
        'account_id' => $t->account->id, 'label' => 'Chrome', 'token_hash' => str_repeat('a', 64), 'ext_version' => '1.0.0',
        'protocol' => 1, 'last_seen_at' => now(),
    ]);
    AutoVideo::query()->create([
        'hash' => hash('sha256', 'onb'), 'path' => '/x/onb.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'onb.mp4',
        'product_code' => 'nano-dong', 'source' => 'kho', 'status' => AutoVideo::NEW, 'caption' => 'xin chào',
    ]);
    ProductLink::query()->create(['social_account_id' => $t->sa->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => '7600000000000000001', 'display_name' => 'SP']);
    AutoAccount::query()->create(['social_account_id' => $t->sa->id, 'enabled' => true]);
}

function onbSteps(object $t): ?array
{
    return app(Onboarding::class)->forAccounts([(string) $t->sa->id]);
}

test('fresh install shows 4 open steps; hub offline is a soft state, not an error', function (): void {
    Http::fake(['*' => Http::failedConnection()]);

    $o = onbSteps($this);

    expect($o)->not->toBeNull()
        ->and($o['done'])->toBe(0)->and($o['total'])->toBe(4)
        ->and(collect($o['steps'])->pluck('key')->all())->toBe(['xuong', 'chrome', 'stock', 'auto'])
        ->and($o['steps'][0]['state'])->toBe('offline')
        ->and($o['steps'][0]['detail'])->toContain('Xưởng chưa chạy')
        ->and($o['steps'][1]['action']['href'])->toBe('/settings/chrome')
        ->and($o['steps'][2]['action']['href'])->toBe('/xuong')
        ->and($o['steps'][3]['action']['href'])->toBe('#kenh');
});

test('hub step reports what is missing and never exposes the key tail', function (): void {
    onbHubUp(claude: false, voice: true);

    $step = onbSteps($this)['steps'][0];

    expect($step['done'])->toBeFalse()->and($step['state'])->toBe('todo')
        ->and($step['detail'])->toContain('đăng nhập Claude')->not->toContain('khoá giọng')
        ->and(json_encode($step))->not->toContain('abcd')
        ->and($step['action']['href'])->toBe('/xuong?tab=cai-dat');
});

test('hub answer is cached for a short while', function (): void {
    onbHubUp();

    onbSteps($this);
    onbSteps($this);

    Http::assertSentCount(3); // health + khoa-giong + tai-khoan-ds, chỉ một lần
});

test('stock step asks for a cart when videos exist but no product is linked', function (): void {
    onbHubUp();
    AutoVideo::query()->create([
        'hash' => hash('sha256', 'onb2'), 'path' => '/x/onb2.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'onb2.mp4',
        'product_code' => 'nano-dong', 'source' => 'kho', 'status' => AutoVideo::NEW, 'caption' => 'xin chào',
    ]);

    $step = onbSteps($this)['steps'][2];

    expect($step['done'])->toBeFalse()->and($step['action']['href'])->toBe('/auto/gio-hang');
});

test('stock step counts already-scheduled hub videos as stock', function (): void {
    onbHubUp();
    $v = AutoVideo::query()->create([
        'hash' => hash('sha256', 'onb3'), 'path' => '/x/onb3.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'onb3.mp4',
        'product_code' => 'nano-dong', 'source' => 'hub', 'hub_id' => 'h1', 'status' => AutoVideo::SCHEDULED, 'caption' => 'xin chào',
    ]);

    // Có video đã xếp lịch nhưng chưa gắn giỏ: vẫn đòi chọn giỏ, không báo "chưa có video".
    expect(onbSteps($this)['steps'][2]['action']['href'])->toBe('/auto/gio-hang');

    ProductLink::query()->create(['social_account_id' => $this->sa->id, 'auto_product_id' => 'nano-dong', 'shop_product_id' => '7600000000000000002', 'display_name' => 'SP']);
    expect(onbSteps($this)['steps'][2]['done'])->toBeTrue();

    $v->update(['status' => AutoVideo::POSTED]);
    expect(onbSteps($this)['steps'][2]['done'])->toBeFalse()->and(onbSteps($this)['steps'][2]['action']['href'])->toBe('/xuong');
});

test('auto page stock separates unscheduled from scheduled videos', function (): void {
    Http::fake(['*' => Http::failedConnection()]);
    AutoVideo::query()->create([
        'hash' => hash('sha256', 'onb4'), 'path' => '/x/onb4.mp4', 'batch_date' => '2026-01-05', 'file_name' => 'onb4.mp4',
        'product_code' => 'nano-dong', 'source' => 'hub', 'hub_id' => 'h2', 'status' => AutoVideo::SCHEDULED, 'caption' => 'xin chào',
    ]);

    $this->actingAs($this->owner)->get('/auto')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->where('stock.new_total', 0)
        ->where('stock.scheduled_total', 1));
});

test('card disappears when all four steps are done', function (): void {
    onbHubUp();
    onbReady($this);

    expect(onbSteps($this))->toBeNull();
});

test('card is not shown once hidden, and only the owner can hide it', function (): void {
    Http::fake(['*' => Http::response('', 500)]);

    $this->actingAs(User::factory()->create(['account_id' => $this->account->id]))->post('/auto/huong-dan/an')->assertForbidden();
    expect(AutoSetting::read(Onboarding::HIDDEN_KEY))->toBeNull();

    $this->actingAs($this->owner)->post('/auto/huong-dan/an')->assertRedirect()->assertSessionHas('flash.success');

    expect(AutoSetting::read(Onboarding::HIDDEN_KEY))->toBe('1')->and(onbSteps($this))->toBeNull();
});

test('the auto page loads the onboarding card as a deferred prop', function (): void {
    Http::fake(['*' => Http::failedConnection()]);

    $this->actingAs($this->owner)->get('/auto')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->missing('onboarding')
        ->loadDeferredProps(fn (AssertableInertia $d) => $d
            ->where('onboarding.total', 4)
            ->where('onboarding.steps.0.state', 'offline')));
});

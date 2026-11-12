<?php

declare(strict_types=1);

use App\Enums\SocialAccount\Platform;
use App\Enums\SocialAccount\Status;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Models\Account;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;
use Inertia\Testing\AssertableInertia;

function chromeClient(string $accountId, array $overrides = []): ChromeClient
{
    return ChromeClient::query()->create(array_merge([
        'account_id' => $accountId,
        'label' => 'Chrome test',
        'token_hash' => hash('sha256', uniqid('', true)),
        'ext_version' => '1.0.0',
        'protocol' => 1,
        'last_seen_at' => now(),
    ], $overrides));
}

beforeEach(function () {
    config()->set('trypost.self_hosted', true);
    Cache::forget('fork:chrome:pair');
    Cache::forget('fork:chrome:profiles');

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create([
        'account_id' => $this->account->id,
        'user_id' => $this->owner->id,
    ]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
});

test('the account owner sees the chrome page', function () {
    $this->actingAs($this->owner)
        ->get('/settings/chrome')
        ->assertOk()
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->component('settings/fork/Chrome')
            ->where('pair', null)
            ->has('clients', 0)
            ->has('accounts', 0)
            ->has('jobs', 0)
            ->has('profiles', 0));
});

test('members who are not the owner cannot use the chrome page', function () {
    $member = User::factory()->create(['account_id' => $this->account->id]);
    $client = chromeClient($this->account->id);

    $this->actingAs($member)->get('/settings/chrome')->assertForbidden();
    $this->actingAs($member)->post('/settings/chrome/pair-code')->assertForbidden();
    $this->actingAs($member)->delete("/settings/chrome/clients/{$client->id}")->assertForbidden();
});

test('guests are sent to login', function () {
    $this->get('/settings/chrome')->assertRedirect();
});

test('creating a pair code stores a 6 digit code for the account and shows it', function () {
    $this->actingAs($this->owner)->post('/settings/chrome/pair-code')->assertRedirect();

    $pair = Cache::get('fork:chrome:pair');
    expect($pair['account_id'])->toBe($this->account->id)
        ->and($pair['code'])->toMatch('/^\d{6}$/');

    $this->actingAs($this->owner)
        ->get('/settings/chrome')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('pair.code', $pair['code'])
            ->where('pair.valid_s', fn ($s) => $s > 0 && $s <= 300));
});

test('profile dir is validated and saved', function () {
    $client = chromeClient($this->account->id);

    $this->actingAs($this->owner)
        ->patch("/settings/chrome/clients/{$client->id}", ['chrome_profile_dir' => 'Profile 2'])
        ->assertSessionHas('flash.success');
    expect($client->fresh()->chrome_profile_dir)->toBe('Profile 2');

    $this->actingAs($this->owner)
        ->patch("/settings/chrome/clients/{$client->id}", ['chrome_profile_dir' => '../evil'])
        ->assertSessionHas('flash.error');
    expect($client->fresh()->chrome_profile_dir)->toBe('Profile 2');
});

test('a client of another account cannot be edited or revoked', function () {
    $other = Account::factory()->create();
    $client = chromeClient($other->id);

    $this->actingAs($this->owner)
        ->patch("/settings/chrome/clients/{$client->id}", ['chrome_profile_dir' => 'Default'])
        ->assertNotFound();
    $this->actingAs($this->owner)->delete("/settings/chrome/clients/{$client->id}")->assertNotFound();
});

test('revoking a client marks it revoked', function () {
    $client = chromeClient($this->account->id);

    $this->actingAs($this->owner)
        ->delete("/settings/chrome/clients/{$client->id}")
        ->assertSessionHas('flash.success');

    expect($client->fresh()->revoked_at)->not->toBeNull();
});

test('toggling on binds the tiktok user id from a matching chrome', function () {
    $social = SocialAccount::factory()->create([
        'workspace_id' => $this->workspace->id,
        'platform' => Platform::TikTok,
        'username' => 'shop.vui',
    ]);
    chromeClient($this->account->id, ['tiktok_username' => 'Shop.Vui', 'tiktok_user_id' => '7001']);

    $this->actingAs($this->owner)
        ->post("/settings/chrome/accounts/{$social->id}/toggle")
        ->assertSessionHas('flash.success');

    $row = ChromeAccount::query()->find($social->id);
    expect($row->enabled)->toBeTrue()
        ->and($row->tiktok_user_id)->toBe('7001')
        ->and($row->chrome_only)->toBeFalse();

    $this->actingAs($this->owner)->post("/settings/chrome/accounts/{$social->id}/toggle");
    expect(ChromeAccount::query()->find($social->id)->enabled)->toBeFalse();
});

test('toggling on without a matching chrome shows an error', function () {
    $social = SocialAccount::factory()->create([
        'workspace_id' => $this->workspace->id,
        'platform' => Platform::TikTok,
        'username' => 'shop.vui',
    ]);
    chromeClient($this->account->id, ['tiktok_username' => 'someone.else', 'tiktok_user_id' => '7002']);

    $this->actingAs($this->owner)
        ->post("/settings/chrome/accounts/{$social->id}/toggle")
        ->assertSessionHas('flash.error', 'Mở Chrome đăng nhập đúng tài khoản rồi thử lại.');

    expect(ChromeAccount::query()->find($social->id))->toBeNull();
});

test('a tiktok account of another account cannot be toggled', function () {
    $otherAccount = Account::factory()->create();
    $otherOwner = User::factory()->create(['account_id' => $otherAccount->id]);
    $otherWorkspace = Workspace::factory()->create([
        'account_id' => $otherAccount->id,
        'user_id' => $otherOwner->id,
    ]);
    $social = SocialAccount::factory()->create([
        'workspace_id' => $otherWorkspace->id,
        'platform' => Platform::TikTok,
    ]);

    $this->actingAs($this->owner)->post("/settings/chrome/accounts/{$social->id}/toggle")->assertNotFound();
});

test('creating a chrome only account from a client', function () {
    $client = chromeClient($this->account->id, ['tiktok_username' => 'chi.chrome', 'tiktok_user_id' => '7003']);

    $this->actingAs($this->owner)
        ->post("/settings/chrome/accounts/from-client/{$client->id}")
        ->assertSessionHas('flash.success');

    $social = SocialAccount::query()
        ->where('workspace_id', $this->workspace->id)
        ->where('platform', Platform::TikTok->value)
        ->firstOrFail();

    expect($social->username)->toBe('chi.chrome')
        ->and($social->access_token)->toBe('')
        ->and($social->status)->toBe(Status::Connected);

    $row = ChromeAccount::query()->findOrFail($social->id);
    expect($row->enabled)->toBeTrue()
        ->and($row->chrome_only)->toBeTrue()
        ->and($row->tiktok_user_id)->toBe('7003');

    $this->actingAs($this->owner)
        ->post("/settings/chrome/accounts/from-client/{$client->id}")
        ->assertSessionHas('flash.success');
    expect(SocialAccount::query()->where('platform', Platform::TikTok->value)->count())->toBe(1);
});

test('a client without a tiktok identity cannot create an account', function () {
    $client = chromeClient($this->account->id);

    $this->actingAs($this->owner)
        ->post("/settings/chrome/accounts/from-client/{$client->id}")
        ->assertSessionHas('flash.error');

    expect(SocialAccount::query()->where('platform', Platform::TikTok->value)->count())->toBe(0);
});

test('the jobs endpoint returns json for the owner only', function () {
    $this->actingAs($this->owner)->getJson('/settings/chrome/jobs')->assertOk()->assertJsonStructure(['jobs']);

    $member = User::factory()->create(['account_id' => $this->account->id]);
    $this->actingAs($member)->getJson('/settings/chrome/jobs')->assertForbidden();
});

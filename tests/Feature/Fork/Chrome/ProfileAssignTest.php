<?php

declare(strict_types=1);

use App\Fork\Chrome\Models\ChromeClient;
use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;
use Inertia\Testing\AssertableInertia;

function profClient(string $accountId, array $overrides = []): ChromeClient
{
    return ChromeClient::query()->create(array_merge([
        'account_id' => $accountId,
        'label' => 'Chrome '.uniqid(),
        'token_hash' => hash('sha256', uniqid('', true)),
        'ext_version' => '1.0.0',
        'protocol' => 1,
        'last_seen_at' => now(),
    ], $overrides));
}

function reportProfiles(array $profiles): void
{
    Cache::put('fork:chrome:profiles', $profiles, now()->addDay());
}

beforeEach(function () {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.slim.enabled', false);
    Cache::forget('fork:chrome:profiles');

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $workspace->id]);
});

test('one client and one profile with the extension are linked automatically', function () {
    $client = profClient($this->account->id);
    reportProfiles([
        ['dir' => 'Default', 'name' => 'Cá nhân', 'has_extension' => false],
        ['dir' => 'Profile 2', 'name' => 'Kênh 1', 'has_extension' => true],
    ]);

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.clients.0.chrome_profile_dir', 'Profile 2')
            ->where('chrome.clients.0.profile_needs_choice', false));

    expect($client->refresh()->chrome_profile_dir)->toBe('Profile 2');
});

test('the launcher profile report also auto-assigns', function () {
    config()->set('fork.chrome.launcher_secret', 'secret-x');
    $client = profClient($this->account->id);

    $this->postJson('/api/fork/chrome/profiles', ['profiles' => [['dir' => 'Default', 'name' => 'A', 'has_extension' => true]]], ['X-Fork-Launcher-Secret' => 'secret-x'])
        ->assertOk();

    expect($client->refresh()->chrome_profile_dir)->toBe('Default');
});

test('several candidates are not guessed and raise a warning', function () {
    $client = profClient($this->account->id);
    reportProfiles([
        ['dir' => 'Profile 1', 'name' => 'A', 'has_extension' => true],
        ['dir' => 'Profile 2', 'name' => 'B', 'has_extension' => true],
    ]);

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.clients.0.chrome_profile_dir', null)
            ->where('chrome.clients.0.profile_needs_choice', true));

    expect($client->refresh()->chrome_profile_dir)->toBeNull();
});

test('two unassigned clients with one profile are not guessed and show no warning', function () {
    profClient($this->account->id);
    profClient($this->account->id);
    reportProfiles([['dir' => 'Default', 'name' => 'A', 'has_extension' => true]]);

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.clients.0.chrome_profile_dir', null)
            ->where('chrome.clients.0.profile_needs_choice', false));
});

test('a profile already used by another client is not a candidate', function () {
    profClient($this->account->id, ['chrome_profile_dir' => 'Profile 1']);
    $second = profClient($this->account->id);
    reportProfiles([
        ['dir' => 'Profile 1', 'name' => 'A', 'has_extension' => true],
        ['dir' => 'Profile 2', 'name' => 'B', 'has_extension' => true],
    ]);

    $this->actingAs($this->owner)->get('/settings');

    expect($second->refresh()->chrome_profile_dir)->toBe('Profile 2');
});

test('saving the same profile for two clients warns but keeps the value', function () {
    $a = profClient($this->account->id, ['label' => 'Kênh A', 'chrome_profile_dir' => 'Default']);
    $b = profClient($this->account->id, ['label' => 'Kênh B']);

    $this->actingAs($this->owner)
        ->patch("/settings/chrome/clients/{$b->id}", ['chrome_profile_dir' => 'Default'])
        ->assertSessionHas('flash.error', fn ($m) => str_contains($m, 'Kênh A'));

    expect($b->refresh()->chrome_profile_dir)->toBe('Default');

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.clients', fn ($clients) => collect($clients)->every(fn ($c) => ! empty($c['profile_conflict_with']))));
    expect($a->refresh()->chrome_profile_dir)->toBe('Default');
});

test('edge profiles are reported with their browser and can be assigned', function () {
    config()->set('fork.chrome.launcher_secret', 'secret-x');
    $client = profClient($this->account->id);

    $this->postJson('/api/fork/chrome/profiles', ['profiles' => [
        ['browser' => 'chrome', 'dir' => 'Default', 'name' => 'A', 'has_extension' => false],
        ['browser' => 'edge', 'dir' => 'Profile 2', 'name' => 'Công việc', 'has_extension' => true, 'bundle_extension' => true],
    ]], ['X-Fork-Launcher-Secret' => 'secret-x'])->assertOk();

    $client->refresh();
    expect($client->chrome_profile_dir)->toBe('Profile 2')
        ->and($client->chrome_browser)->toBe('edge');

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.clients.0.chrome_browser', 'edge')
            ->where('chrome.profiles.1.browser', 'edge')
            ->where('chrome.profiles.0.browser', 'chrome'));
});

test('a profile that uses this bundle extension folder wins over an older install elsewhere', function () {
    $client = profClient($this->account->id);
    reportProfiles([
        ['browser' => 'chrome', 'dir' => 'Profile 1', 'name' => 'Mới', 'has_extension' => true, 'bundle_extension' => true],
        ['browser' => 'chrome', 'dir' => 'Profile 2', 'name' => 'Cũ', 'has_extension' => true, 'bundle_extension' => false],
    ]);

    $this->actingAs($this->owner)->get('/settings');

    expect($client->refresh()->chrome_profile_dir)->toBe('Profile 1');
});

test('the profile reporting the same TikTok username is chosen even with several candidates', function () {
    $a = profClient($this->account->id, ['tiktok_username' => 'kenh_a']);
    $b = profClient($this->account->id, ['tiktok_username' => 'kenh_b']);
    reportProfiles([
        ['browser' => 'chrome', 'dir' => 'Profile 1', 'name' => 'x', 'has_extension' => true, 'tiktok_username' => 'kenh_b'],
        ['browser' => 'edge', 'dir' => 'Default', 'name' => 'y', 'has_extension' => true, 'tiktok_username' => '@KENH_A'],
    ]);

    $this->actingAs($this->owner)->get('/settings');

    expect($a->refresh()->chrome_profile_dir)->toBe('Default')
        ->and($a->chrome_browser)->toBe('edge')
        ->and($b->refresh()->chrome_profile_dir)->toBe('Profile 1')
        ->and($b->chrome_browser)->toBe('chrome');
});

test('the same profile directory in another browser is a different profile', function () {
    profClient($this->account->id, ['chrome_profile_dir' => 'Default', 'chrome_browser' => 'chrome']);
    $second = profClient($this->account->id);
    reportProfiles([
        ['browser' => 'chrome', 'dir' => 'Default', 'name' => 'A', 'has_extension' => true],
        ['browser' => 'edge', 'dir' => 'Default', 'name' => 'B', 'has_extension' => true],
    ]);

    $this->actingAs($this->owner)->get('/settings');

    expect($second->refresh()->chrome_browser)->toBe('edge');

    $this->actingAs($this->owner)
        ->patch("/settings/chrome/clients/{$second->id}", ['chrome_profile_dir' => 'Default', 'chrome_browser' => 'edge'])
        ->assertSessionHas('flash.success');
});

test('saving a profile stores the browser', function () {
    $client = profClient($this->account->id);

    $this->actingAs($this->owner)
        ->patch("/settings/chrome/clients/{$client->id}", ['chrome_profile_dir' => 'Profile 3', 'chrome_browser' => 'edge'])
        ->assertSessionHas('flash.success');

    expect($client->refresh()->chrome_browser)->toBe('edge');

    $this->actingAs($this->owner)
        ->patch("/settings/chrome/clients/{$client->id}", ['chrome_profile_dir' => ''])
        ->assertSessionHas('flash.success');

    expect($client->refresh()->chrome_browser)->toBeNull();
});

test('in single-user mode the TikTok channel is created from the paired Chrome without extra clicks', function () {
    config()->set('fork.single_user', true);
    profClient($this->account->id, ['tiktok_username' => 'nongduoctoancauofficial', 'tiktok_user_id' => '7311506061541475329']);

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.accounts.0.username', 'nongduoctoancauofficial')
            ->where('chrome.accounts.0.enabled', true)
            ->where('chrome.accounts.0.chrome_only', true));

    // Gọi lại không tạo thêm và không bật lại tài khoản đã tắt.
    $social = \App\Models\SocialAccount::query()->where('platform_user_id', '7311506061541475329')->firstOrFail();
    \App\Fork\Chrome\Models\ChromeAccount::query()->where('social_account_id', $social->id)->update(['enabled' => false]);

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->has('chrome.accounts', 1)
            ->where('chrome.accounts.0.enabled', false));
});

test('outside single-user and slim mode nothing is created automatically', function () {
    config()->set('fork.single_user', false);
    config()->set('fork.slim.enabled', false);
    profClient($this->account->id, ['tiktok_username' => 'abc', 'tiktok_user_id' => '123']);

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page->has('chrome.accounts', 0));
});

test('the extension path points at this bundle', function () {
    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.extensionPath', fn ($p) => str_ends_with(str_replace(chr(92), '/', (string) $p), 'extension/autotok')));
});

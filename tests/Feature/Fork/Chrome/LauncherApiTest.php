<?php

declare(strict_types=1);

use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;

beforeEach(function () {
    config()->set('fork.chrome.launcher_secret', 'bi-mat-thu-nghiem');
    Cache::forget('fork:chrome:profiles');
});

function launcherHeaders(string $secret = 'bi-mat-thu-nghiem'): array
{
    return ['X-Fork-Launcher-Secret' => $secret];
}

/** @return array{0: ChromeClient, 1: ChromeJob} */
function launcherFixture(): array
{
    $account = Account::factory()->create();
    $owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $owner->id]);
    $workspace = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $owner->id]);
    $social = SocialAccount::factory()->tiktok()->create(['workspace_id' => $workspace->id]);
    $post = Post::factory()->create(['workspace_id' => $workspace->id]);

    $client = ChromeClient::query()->create([
        'account_id' => $account->id,
        'label' => 'Chrome thử',
        'token_hash' => hash('sha256', Str::random(20)),
        'ext_version' => '1.0.0',
        'protocol' => 1,
        'tiktok_user_id' => '7012345678901234567',
        'chrome_profile_dir' => 'Profile 2',
        'last_seen_at' => now()->subHour(),
    ]);

    $job = ChromeJob::query()->create([
        'id' => 'ej_'.bin2hex(random_bytes(12)),
        'post_id' => $post->id,
        'social_account_id' => $social->id,
        'attempt' => 1,
        'mode' => 'now',
        'expect_user_id' => '7012345678901234567',
        'media_path' => 'x.mp4',
        'video_name' => 'x.mp4',
        'video_size' => 10,
        'video_mime' => 'video/mp4',
        'caption' => 'xin chào',
        'options' => [],
        'state' => 'queued',
        'nonce' => bin2hex(random_bytes(16)),
        'deliver_by' => now()->addHour(),
    ]);

    return [$client, $job];
}

test('missing or wrong secret is forbidden', function () {
    $this->getJson('/api/fork/chrome/launch-requests')->assertForbidden();
    $this->getJson('/api/fork/chrome/launch-requests', launcherHeaders('sai'))->assertForbidden();
    $this->postJson('/api/fork/chrome/profiles', ['profiles' => []], launcherHeaders('sai'))->assertForbidden();
    $this->postJson('/api/fork/chrome/launched', ['client_id' => 1, 'job_id' => 'ej_x'], launcherHeaders('sai'))->assertForbidden();
});

test('empty configured secret forbids everything', function () {
    config()->set('fork.chrome.launcher_secret', '');

    $this->getJson('/api/fork/chrome/launch-requests', ['X-Fork-Launcher-Secret' => ''])->assertForbidden();
    $this->getJson('/api/fork/chrome/launch-requests')->assertForbidden();
});

test('launch requests list a queued job whose chrome is offline', function () {
    [$client, $job] = launcherFixture();

    $this->getJson('/api/fork/chrome/launch-requests', launcherHeaders())
        ->assertOk()
        ->assertJson(['ok' => true, 'requests' => [
            ['client_id' => $client->id, 'profile_dir' => 'Profile 2', 'job_id' => $job->id],
        ]]);
});

test('launched is recorded and stops the same request for a while', function () {
    [$client, $job] = launcherFixture();

    $this->postJson('/api/fork/chrome/launched', ['client_id' => $client->id, 'job_id' => $job->id], launcherHeaders())
        ->assertOk()
        ->assertJson(['ok' => true]);

    expect($job->fresh()->launched_at)->not->toBeNull()
        ->and($client->fresh()->last_launch_at)->not->toBeNull();

    $this->getJson('/api/fork/chrome/launch-requests', launcherHeaders())
        ->assertOk()
        ->assertJson(['requests' => []]);
});

test('launched rejects unknown client and bad body', function () {
    $this->postJson('/api/fork/chrome/launched', ['client_id' => 999999, 'job_id' => 'ej_x'], launcherHeaders())
        ->assertNotFound();
    $this->postJson('/api/fork/chrome/launched', ['job_id' => 'ej_x'], launcherHeaders())
        ->assertUnprocessable();
});

test('profiles are stored in cache and bad dirs are rejected', function () {
    $this->postJson('/api/fork/chrome/profiles', [
        'profiles' => [
            ['dir' => 'Default', 'name' => 'Người 1', 'has_extension' => true],
            ['dir' => 'Profile 3', 'name' => 'Người 2', 'has_extension' => false],
        ],
    ], launcherHeaders())->assertOk()->assertJson(['ok' => true, 'count' => 2]);

    expect(Cache::get('fork:chrome:profiles', []))->toBe([
        ['dir' => 'Default', 'name' => 'Người 1', 'browser' => 'chrome', 'has_extension' => true, 'bundle_extension' => false, 'extension_id' => null, 'tiktok_username' => null],
        ['dir' => 'Profile 3', 'name' => 'Người 2', 'browser' => 'chrome', 'has_extension' => false, 'bundle_extension' => false, 'extension_id' => null, 'tiktok_username' => null],
    ]);

    $this->postJson('/api/fork/chrome/profiles', [
        'profiles' => [['dir' => '..\\evil', 'name' => 'x', 'has_extension' => false]],
    ], launcherHeaders())->assertUnprocessable();
});

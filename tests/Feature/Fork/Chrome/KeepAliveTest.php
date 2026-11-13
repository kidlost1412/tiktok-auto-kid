<?php

declare(strict_types=1);

use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Support\ChromeKeepAlive;
use App\Models\Account;
use App\Models\User;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia;

function keepAliveHeaders(): array
{
    return ['X-Fork-Launcher-Secret' => 'bi-mat-thu-nghiem'];
}

function keepAliveClient(array $overrides = []): ChromeClient
{
    return ChromeClient::query()->create(array_merge([
        'account_id' => test()->account->id,
        'label' => 'Chrome thử',
        'token_hash' => hash('sha256', Str::random(20)),
        'ext_version' => '1.4.1',
        'protocol' => 1,
        'tiktok_user_id' => '7012345678901234567',
        'chrome_profile_dir' => 'Profile 2',
        'last_seen_at' => now()->subHour(),
    ], $overrides));
}

beforeEach(function () {
    config()->set('fork.chrome.launcher_secret', 'bi-mat-thu-nghiem');
    config()->set('trypost.self_hosted', true);
    Cache::forget('fork:chrome:profiles');
    Cache::forget(ChromeKeepAlive::BROWSER_SETTINGS_KEY);
    Cache::forget(ChromeKeepAlive::LAUNCHER_SEEN_KEY);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
});

test('launcher poll lists a silent client with a chosen profile as should-be-running', function () {
    $client = keepAliveClient();

    $this->getJson('/api/fork/chrome/launch-requests', keepAliveHeaders())
        ->assertOk()
        ->assertJson(['ok' => true, 'requests' => [], 'keepalive' => [
            ['client_id' => $client->id, 'profile_dir' => 'Profile 2', 'browser' => 'chrome', 'reason' => 'keepalive'],
        ]]);

    // Đã giao việc: thời gian chờ 5 phút có tác dụng ngay.
    $this->getJson('/api/fork/chrome/launch-requests', keepAliveHeaders())
        ->assertOk()
        ->assertJson(['keepalive' => []]);
});

test('online, switched off, unchosen profile and revoked clients are not listed', function () {
    keepAliveClient(['last_seen_at' => now()->subSeconds(30), 'chrome_profile_dir' => 'Default']);
    keepAliveClient(['keep_alive' => false, 'chrome_profile_dir' => 'Profile 1']);
    keepAliveClient(['chrome_profile_dir' => null]);
    keepAliveClient(['revoked_at' => now(), 'chrome_profile_dir' => 'Profile 5']);
    keepAliveClient(['last_seen_at' => now()->subSeconds(120), 'chrome_profile_dir' => 'Profile 6']);

    $this->getJson('/api/fork/chrome/launch-requests', keepAliveHeaders())
        ->assertOk()
        ->assertJson(['keepalive' => []]);
});

test('backoff: not relaunched within 5 minutes and stops after the failure limit', function () {
    $client = keepAliveClient();
    $keep = new ChromeKeepAlive;
    $t = Carbon\CarbonImmutable::now();

    expect($keep->requests($t))->toHaveCount(1);

    for ($i = 1; $i <= ChromeKeepAlive::MAX_FAILURES; $i++) {
        $t = $t->addSeconds(ChromeKeepAlive::BACKOFF + 1);
        expect($keep->requests($t->subSeconds(10)))->toHaveCount(0);
        $got = $keep->requests($t);

        if ($i < ChromeKeepAlive::MAX_FAILURES) {
            expect($got)->toHaveCount(1);
        }
    }

    // Đã quá số lần thử: dừng và báo lỗi.
    $later = $t->addSeconds(ChromeKeepAlive::BACKOFF * 3);
    expect($keep->requests($later))->toBe([]);
    expect($keep->state($client->refresh(), $later)['state'])->toBe('failed');
});

test('manual open now bypasses backoff once and clears failures', function () {
    $client = keepAliveClient(['keepalive_failures' => 5, 'keepalive_last_start_at' => now()->subSeconds(10), 'keepalive_error' => 'x']);

    $this->actingAs($this->owner)->post("/settings/chrome/clients/{$client->id}/open-now")->assertRedirect();

    $this->getJson('/api/fork/chrome/launch-requests', keepAliveHeaders())
        ->assertJson(['keepalive' => [['client_id' => $client->id, 'reason' => 'manual']]]);

    expect($client->fresh()->keepalive_failures)->toBe(0)
        ->and($client->fresh()->keepalive_requested_at)->toBeNull();
});

test('keepalive result is stored and an error is surfaced on the settings page', function () {
    $client = keepAliveClient();

    $this->postJson('/api/fork/chrome/keepalive-result', ['client_id' => $client->id, 'ok' => false, 'error' => 'Không tìm thấy trình duyệt chrome trên máy.'], keepAliveHeaders())
        ->assertOk();
    $this->postJson('/api/fork/chrome/keepalive-result', ['client_id' => 999999, 'ok' => true], keepAliveHeaders())->assertNotFound();
    $this->postJson('/api/fork/chrome/keepalive-result', ['client_id' => $client->id, 'ok' => true], \array_merge(['X-Fork-Launcher-Secret' => 'sai']))->assertForbidden();

    $this->actingAs($this->owner)->get('/settings')
        ->assertOk()
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.clients.0.keep_alive', true)
            ->where('chrome.clients.0.keepalive.state', 'failed')
            ->where('chrome.clients.0.keepalive.message', 'Không tìm thấy trình duyệt chrome trên máy.'));
});

test('a check-in after a launch clears the error and shows running', function () {
    $client = keepAliveClient(['keepalive_error' => 'cũ', 'keepalive_failures' => 2, 'keepalive_last_start_at' => now()->subMinutes(2)]);
    $client->update(['last_seen_at' => now()]);

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.clients.0.keepalive.state', 'running')
            ->where('chrome.clients.0.keepalive.message', null));

    expect($client->fresh()->keepalive_failures)->toBe(0);
});

test('the toggle is saved per client and defaults to on', function () {
    $client = keepAliveClient();
    expect($client->fresh()->keep_alive)->toBeTrue();

    $this->actingAs($this->owner)->post("/settings/chrome/clients/{$client->id}/keep-alive", ['keep_alive' => false])->assertRedirect();
    expect($client->fresh()->keep_alive)->toBeFalse();

    $this->actingAs($this->owner)->post("/settings/chrome/clients/{$client->id}/keep-alive", ['keep_alive' => true])->assertRedirect();
    expect($client->fresh()->keep_alive)->toBeTrue();

    $member = User::factory()->create(['account_id' => $this->account->id]);
    $this->actingAs($member)->post("/settings/chrome/clients/{$client->id}/keep-alive", ['keep_alive' => false])->assertForbidden();
});

test('open now needs a chosen profile', function () {
    $client = keepAliveClient(['chrome_profile_dir' => null]);

    $this->actingAs($this->owner)->post("/settings/chrome/clients/{$client->id}/open-now")
        ->assertRedirect()
        ->assertSessionHas('flash.error');
    expect($client->fresh()->keepalive_requested_at)->toBeNull();
});

test('background mode read by the launcher is exposed to the page', function () {
    keepAliveClient();

    $this->postJson('/api/fork/chrome/profiles', [
        'profiles' => [],
        'browser_settings' => ['chrome' => ['background_mode' => false], 'edge' => ['background_mode' => null]],
    ], keepAliveHeaders())->assertOk();

    $this->actingAs($this->owner)->get('/settings')
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->where('chrome.backgroundMode.chrome', false)
            ->where('chrome.backgroundMode.edge', null));
});

test('chrome-launcher.ps1 dry-run prints the background launch without starting anything', function () {
    if (PHP_OS_FAMILY !== 'Windows') {
        $this->markTestSkipped('Windows PowerShell only.');
    }

    $fake = tempnam(sys_get_temp_dir(), 'kl').'.json';
    file_put_contents($fake, json_encode([
        'ok' => true,
        'requests' => [],
        'keepalive' => [
            ['client_id' => 7, 'profile_dir' => 'Profile 2', 'browser' => 'chrome', 'reason' => 'keepalive'],
            ['client_id' => 8, 'profile_dir' => '..\\evil', 'browser' => 'chrome', 'reason' => 'keepalive'],
        ],
    ]));

    $script = base_path('tools/fork/chrome-launcher/chrome-launcher.ps1');
    $out = shell_exec('powershell -NoProfile -ExecutionPolicy Bypass -File '.escapeshellarg($script).' -DryRun -FakeResponse '.escapeshellarg($fake).' 2>&1');
    @unlink($fake);

    expect((string) $out)
        ->toContain('--profile-directory="Profile 2" --no-startup-window')
        ->toContain('client 7')
        ->not->toContain('evil" --no-startup-window');
});

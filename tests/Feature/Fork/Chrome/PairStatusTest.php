<?php

declare(strict_types=1);

use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeClient;
use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;

beforeEach(function () {
    config()->set('trypost.self_hosted', true);
    Cache::forget('fork:chrome:pair');
    Cache::forget('fork:chrome:profiles');

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $workspace = Workspace::factory()->create([
        'account_id' => $this->account->id,
        'user_id' => $this->owner->id,
    ]);
    $this->owner->update(['current_workspace_id' => $workspace->id]);
});

function pairStatusClient(string $accountId, array $overrides = []): ChromeClient
{
    return ChromeClient::query()->create(array_merge([
        'account_id' => $accountId,
        'label' => 'Chrome',
        'token_hash' => hash('sha256', uniqid('', true)),
        'ext_version' => '1.0.0',
        'protocol' => 1,
        'last_seen_at' => now(),
    ], $overrides));
}

test('pair status waits for the extension and returns the server time as since', function () {
    app(ChromeJobs::class)->newPairCode($this->account->id);

    $this->actingAs($this->owner)
        ->getJson('/settings/chrome/pair-status')
        ->assertOk()
        ->assertJsonPath('stage', 'waiting_extension')
        ->assertJsonPath('pair_active', true)
        ->assertJsonPath('client', null)
        ->assertJsonPath('since', fn ($s) => is_int($s) && abs($s - time()) <= 10);
});

test('older clients do not count as a new pairing', function () {
    $old = pairStatusClient($this->account->id);
    $old->forceFill(['created_at' => now()->subHour()])->save();

    $this->actingAs($this->owner)
        ->getJson('/settings/chrome/pair-status?since='.time())
        ->assertJsonPath('stage', 'waiting_extension');
});

test('a client paired after since moves to paired, then to account once tiktok reports a handle', function () {
    $since = time() - 2;
    $client = pairStatusClient($this->account->id);

    $this->actingAs($this->owner)
        ->getJson("/settings/chrome/pair-status?since={$since}")
        ->assertJsonPath('stage', 'paired')
        ->assertJsonPath('client.id', $client->id)
        ->assertJsonPath('client.tiktok_username', null);

    $client->update(['tiktok_username' => '@kenh_thu', 'tiktok_user_id' => '123']);

    $this->actingAs($this->owner)
        ->getJson("/settings/chrome/pair-status?since={$since}")
        ->assertJsonPath('stage', 'account')
        ->assertJsonPath('client.tiktok_username', 'kenh_thu');
});

test('a requested profile not yet reported by the launcher is still opening', function () {
    $this->actingAs($this->owner)
        ->getJson('/settings/chrome/pair-status?since='.time().'&profile='.rawurlencode('Profile 7'))
        ->assertJsonPath('stage', 'opening')
        ->assertJsonPath('profile_seen', false);

    Cache::put('fork:chrome:profiles', [['dir' => 'Profile 7', 'browser' => 'chrome', 'name' => 'Profile 7']], now()->addHour());

    $this->actingAs($this->owner)
        ->getJson('/settings/chrome/pair-status?since='.time().'&profile='.rawurlencode('Profile 7'))
        ->assertJsonPath('stage', 'waiting_extension')
        ->assertJsonPath('profile_seen', true);
});

test('pair status ignores other accounts and revoked clients, and is owner only', function () {
    $since = time() - 2;
    $other = Account::factory()->create();
    pairStatusClient($other->id);
    pairStatusClient($this->account->id, ['revoked_at' => now()]);

    $this->actingAs($this->owner)
        ->getJson("/settings/chrome/pair-status?since={$since}")
        ->assertJsonPath('stage', 'waiting_extension');

    $member = User::factory()->create(['account_id' => $this->account->id]);
    $this->actingAs($member)->getJson('/settings/chrome/pair-status')->assertForbidden();
});

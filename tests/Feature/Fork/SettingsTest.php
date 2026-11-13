<?php

declare(strict_types=1);

use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Cache;
use Inertia\Testing\AssertableInertia;

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

test('the merged settings page renders all three sections for the owner', function () {
    $this->actingAs($this->owner)
        ->get('/settings')
        ->assertOk()
        ->assertInertia(fn (AssertableInertia $page) => $page
            ->component('fork/Settings')
            ->where('tab', 'chrome')
            ->has('chrome')
            ->has('telegram')
            ->has('update')
            ->where('chrome.pair', null)
            ->where('telegram.configured', false)
            ->where('update.launcher_port', fn ($p) => is_int($p)));
});

test('a tab query selects which section is active, anything else falls back to chrome', function () {
    $this->actingAs($this->owner)
        ->get('/settings?tab=telegram')
        ->assertInertia(fn (AssertableInertia $page) => $page->where('tab', 'telegram'));

    $this->actingAs($this->owner)
        ->get('/settings?tab=nope')
        ->assertInertia(fn (AssertableInertia $page) => $page->where('tab', 'chrome'));
});

test('members who are not the owner cannot see the settings page', function () {
    $member = User::factory()->create(['account_id' => $this->account->id]);

    $this->actingAs($member)->get('/settings')->assertForbidden();
});

test('guests are sent to login', function () {
    $this->get('/settings')->assertRedirect();
});

test('the old settings urls redirect to the merged page with the right anchor', function () {
    $this->actingAs($this->owner)->get('/settings/chrome')->assertRedirect('/settings#chrome');
    $this->actingAs($this->owner)->get('/settings/telegram')->assertRedirect('/settings#telegram');
    $this->actingAs($this->owner)->get('/settings/cap-nhat')->assertRedirect('/settings#cap-nhat');
});

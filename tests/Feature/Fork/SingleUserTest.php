<?php

declare(strict_types=1);

use App\Fork\SingleUser\SingleUser;
use App\Models\User;
use App\Models\Workspace;

test('flag off does not create or log in an owner', function () {
    config()->set('fork.single_user', false);

    $this->get('/auto')->assertRedirect('/login');
    expect(User::query()->count())->toBe(0);
});

test('flag on auto-logs the owner in on loopback', function () {
    config()->set('fork.single_user', true);

    $this->withServerVariables(['REMOTE_ADDR' => '127.0.0.1'])->get('/')->assertRedirect('/nha');
    $this->withServerVariables(['REMOTE_ADDR' => '127.0.0.1'])->get('/auto')->assertOk();

    $this->assertAuthenticated();
    expect(User::query()->count())->toBe(1)
        ->and(Workspace::query()->count())->toBe(1)
        ->and(auth()->user()->email_verified_at)->not->toBeNull()
        ->and(auth()->user()->currentWorkspace)->not->toBeNull();
});

test('flag on opens /auto directly', function () {
    config()->set('fork.single_user', true);

    $this->withServerVariables(['REMOTE_ADDR' => '::1'])->get('/auto')->assertOk();
    $this->assertAuthenticated();
});

test('flag on answers 403 to non-loopback addresses', function (string $ip) {
    config()->set('fork.single_user', true);

    $this->withServerVariables(['REMOTE_ADDR' => $ip])
        ->withHeader('X-Forwarded-For', '127.0.0.1')
        ->get('/auto')
        ->assertForbidden();

    $this->assertGuest();
    expect(User::query()->count())->toBe(0);
})->with(['203.0.113.7', '192.168.1.20', '2001:db8::1']);

test('fork:single-user is idempotent and does nothing when the flag is off', function () {
    config()->set('fork.single_user', false);
    $this->artisan('fork:single-user')->assertSuccessful();
    expect(User::query()->count())->toBe(0);

    config()->set('fork.single_user', true);
    $this->artisan('fork:single-user')->assertSuccessful();
    $this->artisan('fork:single-user')->assertSuccessful();

    $owner = SingleUser::owner();

    expect(User::query()->count())->toBe(1)
        ->and(Workspace::query()->count())->toBe(1)
        ->and($owner->email)->toBe(SingleUser::OWNER_EMAIL)
        ->and($owner->email_verified_at)->not->toBeNull()
        ->and($owner->isAccountOwner())->toBeTrue()
        ->and($owner->current_workspace_id)->not->toBeNull();
});

test('an existing owner is reused rather than duplicated', function () {
    config()->set('fork.single_user', true);
    $existing = User::factory()->create(['email_verified_at' => null]);

    $this->artisan('fork:single-user')->assertSuccessful();

    expect(User::query()->count())->toBe(1)
        ->and($existing->fresh()->email_verified_at)->not->toBeNull()
        ->and($existing->fresh()->current_workspace_id)->not->toBeNull();
});

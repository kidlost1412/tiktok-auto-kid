<?php

declare(strict_types=1);

use App\Fork\Update\LauncherClient;
use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Http\Client\Factory;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

function launcherStatus(array $over = []): array
{
    return array_merge([
        'ok' => true, 'state' => 'idle', 'message' => '', 'percent' => 0, 'error' => '', 'busy' => false,
        'current' => '1.0.0', 'configured' => true, 'repo' => 'owner/tiktok-auto-kid', 'auto_check' => true,
        'checked_at' => now()->toIso8601String(), 'check_error' => '', 'update_available' => true,
        'latest' => [
            'version' => '1.1.0', 'notes' => "## Mới\n- Sửa lỗi <script>alert(1)</script>", 'page_url' => 'https://github.com/owner/tiktok-auto-kid/releases/tag/v1.1.0',
            'published_at' => '2026-11-01T00:00:00Z', 'zip_size' => 52428800,
        ],
        'can_rollback' => true, 'rollback_version' => '0.9.0', 'launcher_pending' => false,
    ], $over);
}

beforeEach(function () {
    Cache::flush();
    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $workspace->id]);

    $this->tokenFile = tempnam(sys_get_temp_dir(), 'tta');
    file_put_contents($this->tokenFile, "secret-token\n");
    $this->versionFile = tempnam(sys_get_temp_dir(), 'ver');
    file_put_contents($this->versionFile, "1.0.0\n");
    config()->set('fork-update.token_file', $this->tokenFile);
    config()->set('fork-update.version_file', $this->versionFile);
    config()->set('fork-update.repo', 'owner/tiktok-auto-kid');
    config()->set('fork-update.launcher_port', 8009);
});

afterEach(function () {
    @unlink($this->tokenFile);
    @unlink($this->versionFile);
});

test('page shows current and latest version, notes and rollback from the launcher', function () {
    Http::swap(new Factory);
    Http::fake(['127.0.0.1:8009/api/update/status' => Http::response(launcherStatus())]);

    $this->actingAs($this->owner)->get('/settings/cap-nhat')->assertOk()->assertInertia(fn ($p) => $p
        ->component('settings/fork/CapNhat')
        ->where('configured', true)
        ->where('launcher_ok', true)
        ->where('current', '1.0.0')
        ->where('latest.version', '1.1.0')
        ->where('update_available', true)
        ->where('can_rollback', true)
        ->where('rollback_version', '0.9.0')
        ->where('latest.page_url', 'https://github.com/owner/tiktok-auto-kid/releases/tag/v1.1.0')
        ->where('job.busy', false));
});

test('page refreshes a stale check through the launcher with the control token', function () {
    Http::swap(new Factory);
    Http::fake([
        '127.0.0.1:8009/api/update/status' => Http::response(launcherStatus(['checked_at' => now()->subHours(3)->toIso8601String(), 'latest' => null, 'update_available' => false])),
        '127.0.0.1:8009/api/update/check' => Http::response(launcherStatus()),
    ]);

    $this->actingAs($this->owner)->get('/settings/cap-nhat')->assertInertia(fn ($p) => $p->where('latest.version', '1.1.0'));
    Http::assertSent(fn (Request $r) => str_ends_with($r->url(), '/api/update/check') && $r->header('X-TTA-Token') === ['secret-token']);
});

test('placeholder repo means not configured and never calls the launcher to install', function () {
    config()->set('fork-update.repo', 'CHUA_CAU_HINH/tiktok-auto-kid');
    expect(LauncherClient::repoConfigured())->toBeFalse();
    Http::swap(new Factory);
    Http::fake(['127.0.0.1:8009/*' => Http::response(launcherStatus(['configured' => false, 'latest' => null, 'update_available' => false]))]);

    $this->actingAs($this->owner)->get('/settings/cap-nhat')->assertInertia(fn ($p) => $p->where('configured', false)->where('repo', null));
    $this->actingAs($this->owner)->post('/settings/cap-nhat/install')->assertSessionHas('flash.error');
    Http::assertNotSent(fn (Request $r) => str_ends_with($r->url(), '/api/update'));
});

test('page copes with the launcher being down', function () {
    Http::swap(new Factory);
    Http::fake(['127.0.0.1:8009/*' => fn () => throw new Illuminate\Http\Client\ConnectionException('down')]);

    $this->actingAs($this->owner)->get('/settings/cap-nhat')->assertOk()->assertInertia(fn ($p) => $p->where('launcher_ok', false)->where('job', null));
    $this->actingAs($this->owner)->post('/settings/cap-nhat/install')->assertSessionHas('flash.error');
});

test('install, rollback and prefs are forwarded to the launcher with the token', function () {
    Http::swap(new Factory);
    Http::fake([
        '127.0.0.1:8009/api/update/prefs' => Http::response(launcherStatus(['auto_check' => false])),
        '127.0.0.1:8009/api/update/rollback' => Http::response(['ok' => true], 202),
        '127.0.0.1:8009/api/update' => Http::response(['ok' => true], 202),
    ]);

    $this->actingAs($this->owner)->post('/settings/cap-nhat/install')->assertSessionHas('flash.success');
    $this->actingAs($this->owner)->post('/settings/cap-nhat/rollback')->assertSessionHas('flash.success');
    $this->actingAs($this->owner)->patch('/settings/cap-nhat/prefs', ['auto_check' => false])->assertSessionMissing('flash.error');

    Http::assertSent(fn (Request $r) => str_ends_with($r->url(), '/api/update') && $r->header('X-TTA-Token') === ['secret-token']);
    Http::assertSent(fn (Request $r) => str_ends_with($r->url(), '/api/update/prefs') && $r['auto_check'] === false);
    Http::assertSent(fn (Request $r) => str_ends_with($r->url(), '/api/update/rollback'));
});

test('launcher errors are shown as a flash error', function () {
    Http::swap(new Factory);
    Http::fake(['127.0.0.1:8009/api/update' => Http::response(['ok' => false, 'error' => 'đang dùng bản mới nhất'], 400)]);

    $this->actingAs($this->owner)->post('/settings/cap-nhat/install')->assertSessionHas('flash.error', 'đang dùng bản mới nhất');
});

test('only the account owner and signed-in users can use the page', function () {
    Http::swap(new Factory);
    Http::fake(['127.0.0.1:8009/*' => Http::response(launcherStatus())]);

    $this->get('/settings/cap-nhat')->assertRedirect();

    $member = User::factory()->create(['account_id' => $this->account->id]);
    $this->actingAs($member)->get('/settings/cap-nhat')->assertForbidden();
    $this->actingAs($member)->post('/settings/cap-nhat/install')->assertForbidden();
    $this->actingAs($member)->post('/settings/cap-nhat/rollback')->assertForbidden();
    $this->actingAs($member)->patch('/settings/cap-nhat/prefs', ['auto_check' => true])->assertForbidden();
    Http::assertNothingSent();
});

test('non-github release links are dropped from the page props', function () {
    Http::swap(new Factory);
    $s = launcherStatus();
    $s['latest']['page_url'] = 'https://evil.example.com/x';
    Http::fake(['127.0.0.1:8009/api/update/status' => Http::response($s)]);

    $this->actingAs($this->owner)->get('/settings/cap-nhat')->assertInertia(fn ($p) => $p->where('latest.page_url', null));
});

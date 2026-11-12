<?php

declare(strict_types=1);

use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.xuong.url', 'http://127.0.0.1:8765/');
    config()->set('fork.xuong.health_url', 'http://127.0.0.1:8765/health');
    config()->set('fork.xuong.control_token_file', sys_get_temp_dir().'/xuong-test-token-'.getmypid());

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $ws->id]);
});

afterEach(function (): void {
    @unlink((string) config('fork.xuong.control_token_file'));
});

test('xuong page renders with the hub url and a validated tab', function (): void {
    $this->get('/xuong')->assertRedirect();

    $this->actingAs($this->owner)->get('/xuong?tab=kho')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->component('fork/Xuong')->where('url', 'http://127.0.0.1:8765')->where('tab', 'kho'));

    $this->actingAs($this->owner)->get('/xuong?tab=../../x')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->where('tab', null));
    expect(route('fork.xuong', absolute: false))->toBe('/xuong');
});

test('health proxy reports up, busy and offline', function (array $body, int $status, array $expect): void {
    Http::fake(['127.0.0.1:8765/health' => Http::response($body, $status)]);
    $this->actingAs($this->owner)->getJson('/xuong/health')->assertOk()->assertJson($expect);
})->with([
    'busy' => [['ok' => true, 'app' => 'xuong-video', 'dang_chay_lo' => 1], 200, ['up' => true, 'busy' => true]],
    'idle' => [['ok' => true, 'dang_chay_lo' => 0], 200, ['up' => true, 'busy' => false]],
    'error' => [['x' => 1], 500, ['up' => false, 'busy' => false]],
    'not ok' => [['ok' => false], 200, ['up' => false]],
]);

test('health proxy treats a refused connection as offline', function (): void {
    Http::fake(['127.0.0.1:8765/health' => fn () => throw new RuntimeException('refused')]);
    $this->actingAs($this->owner)->getJson('/xuong/health')->assertOk()->assertJson(['up' => false, 'busy' => false]);
});

test('restart without a launcher token answers 503', function (): void {
    $this->actingAs($this->owner)->postJson('/xuong/restart')->assertStatus(503)->assertJson(['ok' => false]);
});

test('restart asks the launcher with the token', function (): void {
    file_put_contents((string) config('fork.xuong.control_token_file'), "tok123\n");
    Http::fake(['127.0.0.1:8009/*' => Http::response(['ok' => true], 202)]);
    $this->actingAs($this->owner)->postJson('/xuong/restart')->assertOk()->assertJson(['ok' => true]);
    Http::assertSent(fn ($r) => $r->method() === 'POST'
        && str_contains($r->url(), '/api/restart?service=xuong-video')
        && $r->header('X-TTA-Token') === ['tok123']);
});

test('restart surfaces launcher refusal and outage', function (): void {
    file_put_contents((string) config('fork.xuong.control_token_file'), 'tok123');
    Http::fake(['127.0.0.1:8009/*' => Http::response(['ok' => false, 'error' => 'chưa cài'], 400)]);
    $this->actingAs($this->owner)->postJson('/xuong/restart')->assertStatus(502)->assertJson(['message' => 'chưa cài']);
});

test('restart reports 503 when the launcher is unreachable', function (): void {
    file_put_contents((string) config('fork.xuong.control_token_file'), 'tok123');
    Http::fake(['127.0.0.1:8009/*' => fn () => throw new RuntimeException('down')]);
    $this->actingAs($this->owner)->postJson('/xuong/restart')->assertStatus(503);
});

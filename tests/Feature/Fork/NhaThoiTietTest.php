<?php

declare(strict_types=1);

use App\Fork\Nha\ThoiTiet;
use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    Cache::flush();

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $ws->id]);
});

function geoFake(): array
{
    return ['geocoding-api.open-meteo.com/*' => Http::response([
        'results' => [['name' => 'Buon Ma Thuot', 'admin1' => 'Dak Lak', 'latitude' => 12.66667, 'longitude' => 108.05, 'country_code' => 'VN']],
    ])];
}

function forecastFake(int $code): array
{
    return ['api.open-meteo.com/*' => Http::response(['current' => ['weather_code' => $code, 'is_day' => 1, 'precipitation' => 0, 'cloud_cover' => 50]])];
}

test('saving a place geocodes once and stores name + coordinates', function (): void {
    Http::fake(geoFake() + forecastFake(0));

    $this->actingAs($this->owner)->putJson('/nha/thoi-tiet', ['noi' => 'Buôn Ma Thuột'])
        ->assertOk()
        ->assertJsonPath('noi', 'Buon Ma Thuot, Dak Lak')
        ->assertJsonPath('sky', 'sunny');

    expect(ThoiTiet::place())->toBe(['name' => 'Buon Ma Thuot, Dak Lak', 'lat' => 12.6667, 'lon' => 108.05]);
    Http::assertSent(fn (Request $r) => str_contains($r->url(), 'geocoding-api.open-meteo.com')
        && $r['name'] === 'Buôn Ma Thuột' && $r['countryCode'] === 'VN' && $r['language'] === 'vi');
});

test('unknown place is rejected and nothing is stored', function (): void {
    Http::fake(['geocoding-api.open-meteo.com/*' => Http::response(['generationtime_ms' => 0.3])]);

    $this->actingAs($this->owner)->putJson('/nha/thoi-tiet', ['noi' => 'zzzzqqq'])->assertStatus(422);

    expect(ThoiTiet::place())->toBeNull();
});

test('empty place clears the setting', function (): void {
    Http::fake(geoFake() + forecastFake(3));
    $this->actingAs($this->owner)->putJson('/nha/thoi-tiet', ['noi' => 'Đà Lạt'])->assertOk();

    $this->actingAs($this->owner)->putJson('/nha/thoi-tiet', ['noi' => ''])
        ->assertOk()->assertJsonPath('noi', null)->assertJsonPath('sky', null);

    expect(ThoiTiet::place())->toBeNull();
});

test('only the account owner can set the place', function (): void {
    Http::fake();
    $other = User::factory()->create(['account_id' => $this->owner->account_id]);

    $this->actingAs($other)->putJson('/nha/thoi-tiet', ['noi' => 'Đà Lạt'])->assertForbidden();
});

test('weather codes map to sunny, cloudy, rain', function (int $code, string $sky): void {
    expect(ThoiTiet::skyFromCode($code))->toBe($sky);
})->with([
    [0, 'sunny'], [1, 'sunny'],
    [2, 'cloudy'], [3, 'cloudy'], [45, 'cloudy'], [48, 'cloudy'],
    [51, 'rain'], [55, 'rain'], [61, 'rain'], [65, 'rain'], [67, 'rain'], [80, 'rain'], [82, 'rain'], [95, 'rain'], [99, 'rain'],
    [71, 'cloudy'], [77, 'cloudy'], [85, 'cloudy'], [86, 'cloudy'],
]);

test('endpoint returns the real sky for the stored place', function (): void {
    Http::fake(geoFake() + forecastFake(63));
    $this->actingAs($this->owner)->putJson('/nha/thoi-tiet', ['noi' => 'Buôn Ma Thuột'])->assertOk();

    $this->actingAs($this->owner)->getJson('/nha/thoi-tiet')
        ->assertOk()->assertJsonPath('sky', 'rain')->assertJsonPath('noi', 'Buon Ma Thuot, Dak Lak');

    Http::assertSent(fn (Request $r) => str_contains($r->url(), 'api.open-meteo.com/v1/forecast')
        && $r['latitude'] == 12.6667 && $r['current'] === 'weather_code,is_day,precipitation,cloud_cover');
});

test('no place means null sky and no outgoing request', function (): void {
    Http::fake();

    $this->actingAs($this->owner)->getJson('/nha/thoi-tiet')->assertOk()->assertJsonPath('sky', null)->assertJsonPath('noi', null);

    Http::assertNothingSent();
});

test('sky is cached for 15 minutes', function (): void {
    Http::fake(geoFake() + forecastFake(0));
    $this->actingAs($this->owner)->putJson('/nha/thoi-tiet', ['noi' => 'Buôn Ma Thuột'])->assertOk(); // đã gọi forecast 1 lần

    $this->actingAs($this->owner)->getJson('/nha/thoi-tiet')->assertJsonPath('sky', 'sunny');
    $this->actingAs($this->owner)->getJson('/nha/thoi-tiet')->assertJsonPath('sky', 'sunny');

    Http::assertSentCount(2); // 1 geocode + 1 forecast, các lần sau lấy từ đệm
});

test('forecast failure returns null instead of breaking', function (): void {
    // lần gọi forecast thứ 1 (khi lưu): lỗi 500; thứ 2: mất kết nối; thứ 3: thiếu dữ liệu
    Http::fake(geoFake() + ['api.open-meteo.com/*' => Http::sequence()
        ->push('boom', 500)
        ->pushFailedConnection()
        ->push(['current' => []])]);

    $this->actingAs($this->owner)->putJson('/nha/thoi-tiet', ['noi' => 'Buôn Ma Thuột'])->assertOk()->assertJsonPath('sky', null);

    foreach ([1, 2] as $_) {
        Cache::flush();
        $this->actingAs($this->owner)->getJson('/nha/thoi-tiet')->assertOk()->assertJsonPath('sky', null);
    }
});

test('a failed lookup is remembered briefly so the provider is not hammered', function (): void {
    Http::fake(geoFake() + ['api.open-meteo.com/*' => Http::response('boom', 500)]);
    $this->actingAs($this->owner)->putJson('/nha/thoi-tiet', ['noi' => 'Buôn Ma Thuột'])->assertOk();

    $this->actingAs($this->owner)->getJson('/nha/thoi-tiet')->assertJsonPath('sky', null);

    Http::assertSentCount(2); // geocode + 1 forecast lỗi; lần GET sau lấy từ đệm lỗi
});

<?php

declare(strict_types=1);

use App\Fork\Nha\NhaState;
use App\Models\Account;
use App\Models\User;
use App\Models\Workspace;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);
    config()->set('fork.xuong.url', 'http://127.0.0.1:8765');

    $account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $account->id]);
    $account->update(['owner_id' => $this->owner->id]);
    $ws = Workspace::factory()->create(['account_id' => $account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $ws->id]);
});

/** Sự kiện giả: cách bay_gio `$ago` giây. */
function nhaEvent(int $ago, string $vai, string $loai, array $extra = []): array
{
    return array_merge(['n' => (int) ((1_800_000_000 - $ago) * 1_000_000), 'vai' => $vai, 'loai' => $loai], $extra);
}

function nhaHub(array $events, bool $running = true, array $tienDo = ['xong' => 6, 'tong' => 10, 'het_han_muc' => null]): array
{
    return ['ok' => true, 'dang_chay' => $running, 'tien_do' => $tienDo, 'san_pham' => ['ma' => 'dam-ca', 'ten' => 'Đạm cá'], 'su_kien' => $events, 'bay_gio' => 1_800_000_000.0];
}

test('/ redirects to the house and the page renders', function (): void {
    $this->get('/')->assertRedirect('/nha');
    $this->get('/login')->assertRedirect('/nha');

    $this->actingAs($this->owner)->get('/nha')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p->component('fork/Nha'));
});

test('xuong page passes a validated muc', function (): void {
    $this->actingAs($this->owner)->get('/xuong?tab=prompt-ai&muc=bien-kich')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->where('tab', 'prompt-ai')->where('muc', 'bien-kich'));
    $this->actingAs($this->owner)->get('/xuong?tab=cai-dat&muc=../x')->assertOk()->assertInertia(fn (AssertableInertia $p) => $p
        ->where('tab', 'cai-dat')->where('muc', null));
});

test('state maps hub events to working roles with real data', function (): void {
    Http::fake(['127.0.0.1:8765/api/su-kien*' => Http::response(nhaHub([
        nhaEvent(300, 'he-thong', 'bat-dau-lo', ['ten' => 'Đạm cá', 'so_video' => 10]),
        nhaEvent(200, 'bien-kich', 'bat-dau', ['so' => 5]),
        nhaEvent(190, 'bien-kich', 'xong', ['so' => 5]),
        nhaEvent(100, 'giam-khao', 'bat-dau', ['video' => 'a']),
        nhaEvent(90, 'giam-khao', 'diem', ['video' => 'a', 'diem' => 8]),
        nhaEvent(80, 'giam-khao', 'bat-dau', ['video' => 'b']),
        nhaEvent(70, 'dung', 'bat-dau', ['video' => 'c']),
    ]))]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();

    expect($j['mode'])->toBe('working')
        ->and($j['line'])->toBe('Xưởng đang làm 10 video Đạm cá · 6/10')
        ->and($j['vai']['bienkich']['state'])->toBe('idle')
        ->and($j['vai']['giamkhao'])->toBe(['state' => 'working', 'bubble' => 'Đang chấm 1/10 · 8 điểm'])
        ->and($j['vai']['thodung']['bubble'])->toBe('Đang dựng 1 video…')
        ->and($j['bang']['san_pham'])->toBe('Đạm cá')
        ->and($j['bang']['tien_do'])->toBe(['xong' => 6, 'tong' => 10]);
});

test('state shows writer bubble and ignores stale starts', function (): void {
    Http::fake(['127.0.0.1:8765/api/su-kien*' => Http::response(nhaHub([
        nhaEvent(5000, 'he-thong', 'bat-dau-lo', ['ten' => 'Đạm cá', 'so_video' => 10]),
        nhaEvent(4000, 'dao-dien', 'bat-dau', ['video' => 'x']),
        nhaEvent(30, 'bien-kich', 'bat-dau', ['so' => 5]),
    ]))]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->json();
    expect($j['vai']['bienkich'])->toBe(['state' => 'working', 'bubble' => 'Đang viết 5 lời…'])
        ->and($j['vai']['daodien']['state'])->toBe('idle');
});

test('state reports the quota limit with everyone sleepy', function (): void {
    Http::fake(['127.0.0.1:8765/api/su-kien*' => Http::response(nhaHub([
        nhaEvent(400, 'he-thong', 'bat-dau-lo', ['ten' => 'Đạm cá', 'so_video' => 10]),
        nhaEvent(60, 'he-thong', 'het-han-muc', ['msg' => 'Hết hạn mức Claude']),
    ], false))]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->json();
    expect($j['mode'])->toBe('limit')
        ->and($j['vai']['bienkich']['state'])->toBe('sleep')
        ->and($j['bang']['dong'])->toContain('hạn mức');
});

test('state falls back to the status endpoint for an older hub', function (): void {
    Http::fake([
        '127.0.0.1:8765/api/su-kien*' => Http::response('nope', 404),
        '127.0.0.1:8765/api/trang-thai' => Http::response(['dang_chay' => false, 'tien_do' => ['xong' => 8, 'tong' => 8]]),
    ]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();
    expect($j['mode'])->toBe('idle')->and($j['hub']['up'])->toBeTrue()->and($j['line'])->toStartWith('Xưởng đang nghỉ');
});

test('state shows a sleeping house when the hub is down', function (): void {
    Http::fake(['127.0.0.1:8765/*' => fn () => throw new RuntimeException('refused')]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();
    expect($j['mode'])->toBe('down')
        ->and($j['hub']['up'])->toBeFalse()
        ->and($j['line'])->toStartWith('Xưởng đang tắt')
        ->and(collect($j['vai'])->pluck('state')->unique()->all())->toContain('sleep');
});

test('postman works when a post is due within 30 minutes', function (): void {
    $now = CarbonImmutable::parse('2026-11-13 04:00:00', 'UTC');
    $hub = ['up' => true, 'dang_chay' => false, 'tien_do' => [], 'su_kien' => []];

    $soon = NhaState::build($hub, ['posts_today' => 3, 'next' => ['at' => $now->addMinutes(20)->toIso8601String(), 'minutes' => 20, 'channel' => '@kenh']], $now);
    expect($soon['vai']['buuta']['state'])->toBe('working')->and($soon['vai']['buuta']['bubble'])->toContain('@kenh');

    $later = NhaState::build($hub, ['posts_today' => 3, 'next' => ['at' => $now->addHours(3)->toIso8601String(), 'minutes' => 180, 'channel' => '@kenh']], $now);
    expect($later['vai']['buuta']['state'])->toBe('idle')->and($later['line'])->toContain('3 bài hẹn hôm nay');

    $none = NhaState::build($hub, ['posts_today' => 0, 'next' => null], $now);
    expect($none['line'])->toContain('hôm nay chưa có bài hẹn');
});

test('state exposes the event feed, batch reels and finished message', function (): void {
    Http::fake(['127.0.0.1:8765/api/su-kien*' => Http::response(nhaHub([
        nhaEvent(900, 'he-thong', 'bat-dau-lo', ['ten' => 'Đạm cá', 'so_video' => 2]),
        nhaEvent(500, 'kho', 'luu', ['video' => 'a-0', 'so' => 1, 'tong' => 2, 'diem' => 8, 'file' => 'a.mp4', 'ngay' => '2026-11-13']),
        nhaEvent(400, 'giam-khao', 'diem', ['video' => 'a-1', 'diem' => 5, 'dat' => false, 'loi' => 'Chữ lệch', 'file' => 'b.mp4', 'secret' => 'x']),
        nhaEvent(300, 'kho', 'luu', ['video' => 'a-1', 'so' => 2, 'tong' => 2, 'diem' => 5, 'file' => 'b.mp4', 'ngay' => '2026-11-13']),
        nhaEvent(100, 'he-thong', 'ket-thuc-lo', ['so' => 2, 'tong' => 2, 'phut' => 34.5]),
    ], false, ['xong' => 2, 'tong' => 2, 'het_han_muc' => null]))]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();

    expect($j['lo'])->toBeInt()
        ->and($j['reels'])->toHaveCount(2)
        ->and($j['reels'][1])->toMatchArray(['so' => 2, 'file' => 'b.mp4', 'ngay' => '2026-11-13', 'diem' => 5])
        ->and($j['events'])->toHaveCount(5)
        ->and($j['events'][2]['loi'])->toBe('Chữ lệch')
        ->and($j['events'][2])->not->toHaveKey('secret')
        ->and($j['bang']['dong'])->toBe('Xong 2/2 · 34,5 phút')
        ->and($j['hub']['url'])->toBe('http://127.0.0.1:8765')
        ->and($j['app']['post_counts'])->toHaveKeys(['scheduled', 'posted']);
});

test('viec lists only the roles that have something waiting', function (): void {
    expect(NhaState::viec(['chrome_online' => true], []))->toBe([]);

    $v = NhaState::viec(['chrome_online' => false], ['loi' => 2, 'gio_tam_dung' => 3, 'kho' => 4, 'kho_thap' => true]);
    expect($v['buuta']['so'])->toBe(3)
        ->and($v['buuta']['tom_tat'])->toContain('2 bài đăng lỗi')->toContain('Chrome')
        ->and($v['chuquay'])->toBe(['so' => 3, 'tom_tat' => '3 giỏ hàng đang tạm dừng'])
        ->and($v['thukho'])->toBe(['so' => 1, 'tom_tat' => 'Kho còn 4 video'])
        ->and($v)->not->toHaveKey('giamkhao');

    expect(NhaState::viec(['chrome_online' => null], ['kho' => 40, 'kho_thap' => false]))->toBe([]);
});

test('state endpoint always carries a viec map', function (): void {
    Http::fake(['127.0.0.1:8765/*' => Http::response([], 500)]);

    $j = $this->actingAs($this->owner)->getJson('/nha/trang-thai')->assertOk()->json();

    expect($j)->toHaveKey('viec')->and($j['viec'])->toBeArray();
});

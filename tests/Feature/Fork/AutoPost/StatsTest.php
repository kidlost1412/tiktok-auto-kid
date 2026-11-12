<?php

declare(strict_types=1);

use App\Enums\Analytics\PublicationAvailability;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Stats\Insights;
use App\Fork\AutoPost\Stats\StatsCollector;
use App\Models\AnalyticsPublication;
use App\Models\AnalyticsPublicationDailySnapshot;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\File;

beforeEach(function (): void {
    $this->hub = str_replace('\\', '/', sys_get_temp_dir()).'/hub-stats-'.bin2hex(random_bytes(4));
    File::ensureDirectoryExists($this->hub.'/ra/2026-01-05');
    config(['fork.auto.hub_path' => $this->hub]);
    $this->sa = SocialAccount::factory()->tiktok()->create(['timezone' => 'Asia/Ho_Chi_Minh']);
});

afterEach(function (): void {
    File::deleteDirectory($this->hub);
});

function statsVideo(array $o = []): AutoVideo
{
    static $n = 0;
    $n++;

    return AutoVideo::query()->create(array_merge([
        'hash' => hash('sha256', 'v'.$n.random_bytes(4)),
        'path' => '/x/'.$n.'.mp4',
        'batch_date' => '2026-01-05',
        'file_name' => "NanoDong_a_b_MIXKIT_{$n}.mp4",
        'status' => 'posted',
    ], $o));
}

/** @param  list<array{0: CarbonImmutable, 1: int, 2: int}>  $snaps */
function statsPublication(SocialAccount $sa, AutoVideo $v, array $snaps): void
{
    $pub = AnalyticsPublication::factory()->create([
        'workspace_id' => $sa->workspace_id,
        'social_account_id' => $sa->id,
        'post_id' => null,
        'remote_id' => 'tt-'.$v->id,
        'permalink' => 'https://www.tiktok.com/@x/video/'.$v->id,
        'availability' => PublicationAvailability::Available,
    ]);
    $v->update(['tiktok_video_id' => 'tt-'.$v->id]);

    foreach ($snaps as [$at, $views, $likes]) {
        AnalyticsPublicationDailySnapshot::factory()->create([
            'publication_id' => $pub->id,
            'date' => $at->toDateString(),
            'provider_observed_at' => $at,
            'collected_at' => $at,
            'views_count' => $views,
            'reactions_count' => $likes,
        ]);
    }
}

test('collector records 24h and 72h milestones and latest', function (): void {
    $now = CarbonImmutable::parse('2026-01-10 12:00:00');
    $posted = $now->subHours(100);
    $v = statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $posted]);
    statsPublication($this->sa, $v, [
        [$posted->addHours(25), 100, 5],
        [$posted->addHours(73), 300, 15],
        [$now->subHour(), 500, 20],
    ]);

    $r = app(StatsCollector::class)->collect($now);

    expect($r['updated'])->toBe(1);
    $s = $v->fresh()->stats;
    expect($s['h24']['views'])->toBe(100)
        ->and($s['h72']['views'])->toBe(300)
        ->and($s['latest']['views'])->toBe(500)
        ->and($s['link'])->toContain('tiktok.com');
});

test('collector skips videos younger than 24 hours or without publication', function (): void {
    $now = CarbonImmutable::parse('2026-01-10 12:00:00');
    statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $now->subHours(5)]);
    statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $now->subHours(30)]);

    expect(app(StatsCollector::class)->collect($now)['updated'])->toBe(0);
});

test('collector writes so-lieu.csv with BOM atomically', function (): void {
    $now = CarbonImmutable::parse('2026-01-10 12:00:00');
    $posted = $now->subHours(30);
    $v = statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $posted]);
    statsPublication($this->sa, $v, [[$posted->addHours(25), 120, 7]]);

    $r = app(StatsCollector::class)->collect($now);
    $path = $this->hub.'/ra/2026-01-05/so-lieu.csv';

    expect($r['hub']['sheets'])->toBe(1)->and(is_file($path))->toBeTrue();
    $raw = file_get_contents($path);
    expect(str_starts_with($raw, "\xEF\xBB\xBF"))->toBeTrue()
        ->and($raw)->toContain('"file","tai_khoan","dang_luc"')
        ->and($raw)->toContain('"120"')
        ->and(glob($this->hub.'/ra/2026-01-05/*.tmp*'))->toBe([]);
});

test('bang-ghi luot_xem is filled only for old days and quiet files', function (): void {
    $now = CarbonImmutable::parse('2026-01-10 12:00:00');
    $posted = $now->subHours(30);
    $v = statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $posted, 'file_name' => 'A_x_MIXKIT_1.mp4']);
    statsPublication($this->sa, $v, [[$posted->addHours(25), 321, 7]]);

    $csv = $this->hub.'/ra/2026-01-05/bang-ghi.csv';
    $orig = "\xEF\xBB\xBF"
        .'"file","goc","luot_xem","ghi_chu"'."\r\n"
        .'"A_x_MIXKIT_1.mp4","chu-hang","","có ""ngoặc"""'."\r\n"
        .'"B.mp4","g2","","k"'."\r\n";

    // File vừa sửa: không đụng.
    file_put_contents($csv, $orig);
    touch($csv, $now->getTimestamp() - 60);
    app(StatsCollector::class)->collect($now);
    expect(file_get_contents($csv))->toBe($orig);

    // File cũ hơn 1 giờ: điền, giữ nguyên các cột khác.
    touch($csv, $now->getTimestamp() - 7200);
    $r = app(StatsCollector::class)->collect($now);
    $out = file_get_contents($csv);

    expect($r['hub']['filled'])->toBe(1)
        ->and(str_starts_with($out, "\xEF\xBB\xBF"))->toBeTrue()
        ->and($out)->toContain('"A_x_MIXKIT_1.mp4","chu-hang","321","có ""ngoặc"""')
        ->and($out)->toContain('"B.mp4","g2","","k"');
});

test('bang-ghi of today is never touched', function (): void {
    $now = CarbonImmutable::parse('2026-01-05 20:00:00');
    $posted = $now->subHours(30);
    $v = statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $posted, 'file_name' => 'A.mp4']);
    statsPublication($this->sa, $v, [[$posted->addHours(25), 9, 1]]);

    $csv = $this->hub.'/ra/2026-01-05/bang-ghi.csv';
    $orig = "\xEF\xBB\xBF".'"file","luot_xem"'."\r\n".'"A.mp4",""'."\r\n";
    file_put_contents($csv, $orig);
    touch($csv, $now->getTimestamp() - 9999);

    app(StatsCollector::class)->collect($now);

    expect(file_get_contents($csv))->toBe($orig);
});

test('insights groups average views by hour in local time and by product', function (): void {
    $base = CarbonImmutable::parse('2026-01-01 00:00:00', 'UTC');
    // 02:00 UTC = 09:00 giờ VN
    statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $base->setTime(2, 0), 'product_code' => 'p1', 'goc' => 'g1', 'stats' => ['h24' => ['views' => 100]]]);
    statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $base->setTime(2, 30), 'product_code' => 'p1', 'goc' => 'g2', 'stats' => ['h24' => ['views' => 300]]]);
    statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $base->setTime(12, 0), 'product_code' => 'p2', 'goc' => 'g1', 'stats' => ['h24' => ['views' => 50]]]);

    $b = app(Insights::class)->breakdowns();
    $hour9 = collect($b['hour'])->firstWhere('key', '09');

    expect($hour9['avg_views'])->toBe(200.0)->and($hour9['samples'])->toBe(2)
        ->and(collect($b['product_code'])->firstWhere('key', 'p1')['avg_views'])->toBe(200.0)
        ->and(collect($b['goc'])->firstWhere('key', 'g1')['samples'])->toBe(2);
});

test('recommendHours returns null with a reason when data is insufficient', function (): void {
    $auto = AutoAccount::query()->create(['social_account_id' => $this->sa->id]);
    statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => now()->subDays(2), 'stats' => ['h24' => ['views' => 10]]]);

    $r = app(Insights::class)->recommendHours($auto);

    expect($r['hours'])->toBeNull()->and($r['reason'])->toContain('Chưa đủ dữ liệu');
});

test('recommendHours ranks the best hours with delta vs average', function (): void {
    $auto = AutoAccount::query()->create(['social_account_id' => $this->sa->id, 'daily_cap' => 6]);
    $base = CarbonImmutable::parse('2026-01-01 00:00:00', 'Asia/Ho_Chi_Minh');

    // 8 ngày x 6 bài = 48 bài; giờ 19 và 20 cao, các giờ khác thấp.
    foreach (range(0, 7) as $d) {
        foreach ([8 => 100, 10 => 100, 12 => 100, 15 => 100, 19 => 900, 20 => 700] as $h => $views) {
            statsVideo(['social_account_id' => $this->sa->id, 'posted_at' => $base->addDays($d)->setTime($h, 0)->utc(), 'stats' => ['h24' => ['views' => $views]]]);
        }
    }

    $r = app(Insights::class)->recommendHours($auto);

    expect($r['reason'])->toBeNull()
        ->and($r['hours'][0]['hour'])->toBe(19)
        ->and($r['hours'][1]['hour'])->toBe(20)
        ->and($r['hours'][0]['delta_pct'])->toBeGreaterThan(0)
        ->and($r['videos'])->toBe(48)
        ->and($r['days'])->toBe(8);
});

test('fork:auto-stats command runs', function (): void {
    $this->artisan('fork:auto-stats')->assertSuccessful();
});

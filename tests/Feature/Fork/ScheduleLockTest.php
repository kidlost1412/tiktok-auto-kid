<?php

declare(strict_types=1);

use Illuminate\Console\Scheduling\Schedule;

// Mutex withoutOverlapping mặc định sống 24 giờ: tiến trình bị giết giữa chừng (máy ngủ, khởi động lại launcher)
// để lại khoá mồ côi và lệnh đó (kể cả đăng bài hẹn giờ) không chạy suốt một ngày.
test('no scheduled task keeps its overlap lock longer than an hour', function () {
    $events = collect(app(Schedule::class)->events())->filter(fn ($e) => $e->withoutOverlapping);

    expect($events)->not->toBeEmpty();

    foreach ($events as $event) {
        expect((int) $event->expiresAt)->toBeLessThanOrEqual(60, $event->command ?? $event->description);
    }
});

test('posting due scheduled posts recovers within minutes after a killed run', function () {
    $event = collect(app(Schedule::class)->events())->first(fn ($e) => str_contains((string) $e->command, 'posts:process-scheduled'));

    expect($event)->not->toBeNull()->and((int) $event->expiresAt)->toBeLessThanOrEqual(10);
});

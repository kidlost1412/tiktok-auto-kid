<?php

declare(strict_types=1);

use App\Fork\AutoPost\Rieng\RiengClean;
use App\Fork\AutoPost\Rieng\RiengThumbs;
use Symfony\Component\Process\Process;

test('a private video is cleaned of origin metadata with ffmpeg, keeping a real export date and leaving the source untouched', function () {
    $ffmpeg = app(RiengThumbs::class)->ffmpegPath();

    if ($ffmpeg === null) {
        $this->markTestSkipped('ffmpeg không có trên máy.');
    }

    $dir = sys_get_temp_dir().DIRECTORY_SEPARATOR.'rieng-clean-'.bin2hex(random_bytes(4));
    @mkdir($dir);
    $src = $dir.DIRECTORY_SEPARATOR.'goc.mp4';
    // Video giả mang dấu vết giống file tải từ TikTok: comment (mã video gốc), vid_md5, ngày cũ.
    (new Process([$ffmpeg, '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=160x120:rate=10:duration=1',
        '-f', 'lavfi', '-i', 'sine=duration=1', '-c:v', 'libx264', '-c:a', 'aac', '-shortest',
        '-metadata', 'comment=vid:v1c044gABC', '-metadata', 'vid_md5=deadbeef', '-metadata', 'creation_time=2020-01-01T00:00:00Z', $src]))->mustRun();
    $before = hash_file('sha256', $src);

    $out = (new RiengClean)->file(7, $src);
    $tags = (new Process([dirname($ffmpeg).DIRECTORY_SEPARATOR.(PHP_OS_FAMILY === 'Windows' ? 'ffprobe.exe' : 'ffprobe'),
        '-v', 'error', '-show_entries', 'format_tags:stream_tags', '-of', 'compact', $out]))->mustRun()->getOutput();
    $raw = (string) file_get_contents($out);

    expect($tags)->not->toContain('vid:v1c044g')->not->toContain('vid_md5')->not->toContain('encoder')->not->toContain('2020-01-01')
        ->toContain('creation_time='.now()->utc()->format('Y-m-d'))->toContain('handler_name=VideoHandle')
        ->and($raw)->not->toContain('x264')->not->toContain('Lavf')
        ->and(hash_file('sha256', $src))->toBe($before);

    @unlink($out);
    @unlink($src);
    @rmdir($dir);
});

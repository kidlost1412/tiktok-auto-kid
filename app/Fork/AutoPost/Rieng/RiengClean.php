<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use Closure;
use RuntimeException;
use Symfony\Component\Process\Process;

/**
 * Xoá metadata video Kho riêng trước khi đăng (giống bước làm sạch của Xưởng, xuong-video/engine/lam_sach.py):
 * bỏ mã video TikTok gốc, phần mềm dựng, chữ ký bộ mã hoá, ngày cũ, dấu app điện thoại. Chỉ ghi ngày tạo = lúc xuất file
 * (ngày thật) và nhãn luồng chung; không ghi tên máy nào. Hình chép nguyên (không nén lại), file gốc không đụng tới.
 * Hàm chạy ffmpeg tiêm được để test (file test chỉ là chữ) không cần video thật.
 */
class RiengClean
{
    /** @param  (Closure(string, string): void)|null  $run  chép $source sang $out đã làm sạch */
    public function __construct(private readonly ?Closure $run = null) {}

    /**
     * File tạm MỚI đã làm sạch, cùng định dạng (mp4/m4v ra mp4, mov ra mov, webm ra webm).
     * Ném RuntimeException khi không làm sạch được: video không bị đăng kèm dấu vết.
     */
    public function file(int $videoId, string $source): string
    {
        $ext = match (strtolower(pathinfo($source, PATHINFO_EXTENSION))) {
            'mov' => 'mov', 'webm' => 'webm', default => 'mp4',
        };
        $dir = storage_path('app/rieng-music');
        @mkdir($dir, 0775, true);
        $out = $dir.DIRECTORY_SEPARATOR.$videoId.'-sach-'.bin2hex(random_bytes(4)).'.'.$ext;

        try {
            ($this->run ?? $this->ffmpeg(...))($source, $out);
        } catch (\Throwable $e) {
            @unlink($out);

            throw $e instanceof RuntimeException ? $e : new RuntimeException('Làm sạch video lỗi: '.$e->getMessage());
        }

        if (! is_file($out) || filesize($out) < 1) {
            @unlink($out);

            throw new RuntimeException('Làm sạch video lỗi: không ra file.');
        }

        return $out;
    }

    private function ffmpeg(string $source, string $out): void
    {
        $ffmpeg = app(RiengThumbs::class)->ffmpegPath() ?? throw new RuntimeException('Không tìm thấy ffmpeg để làm sạch video.');
        $webm = str_ends_with($out, '.webm');
        $p = new Process([$ffmpeg, '-y', '-v', 'error', '-i', $source, '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'copy',
            ...($webm ? ['-c:a', 'copy'] : ['-c:a', 'aac', '-b:a', '192k']),
            ...self::args(self::isH264($ffmpeg, $source), ! $webm), $out]);
        $p->setTimeout(600);
        $p->run();

        if (! $p->isSuccessful() || ! is_file($out) || filesize($out) < 1024) {
            throw new RuntimeException('Làm sạch video lỗi: '.mb_substr(trim($p->getErrorOutput()), -200));
        }
    }

    /**
     * Cờ ffmpeg xoá metadata, dùng chung cho bản làm sạch và bản ghép nhạc.
     *
     * @return list<string>
     */
    public static function args(bool $h264, bool $mp4 = true): array
    {
        return [
            '-map_metadata', '-1', '-map_metadata:s:v', '-1', '-map_metadata:s:a', '-1', '-map_chapters', '-1',
            '-fflags', '+bitexact', '-flags:v', '+bitexact', '-flags:a', '+bitexact',
            // SEI của x264 ghi tên + cấu hình bộ mã hoá; chỉ bỏ với h264 (mã 6 ở HEVC là loại khác).
            ...($h264 ? ['-bsf:v', 'filter_units=remove_types=6'] : []),
            '-metadata', 'creation_time='.now()->utc()->format('Y-m-d\TH:i:s.u\Z'),
            ...($mp4 ? [
                '-metadata:s:v', 'handler_name=VideoHandle', '-metadata:s:a', 'handler_name=SoundHandle',
                '-metadata:s:v', 'language=und', '-metadata:s:a', 'language=und',
                '-movflags', '+faststart',
            ] : []),
        ];
    }

    public static function isH264(string $ffmpeg, string $file): bool
    {
        $p = new Process([$ffmpeg, '-hide_banner', '-i', $file]);
        $p->setTimeout(30);
        $p->run();

        return preg_match('/Stream #\d+:\d+.*Video:\s*h264/', $p->getErrorOutput()) === 1;
    }
}

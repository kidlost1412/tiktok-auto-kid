<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Support\VideoDurationProbe;
use Closure;
use Symfony\Component\Process\ExecutableFinder;
use Symfony\Component\Process\Process;
use Throwable;

/**
 * Một file video riêng đã "ghi xong" chưa? Kiểm ngay, không chờ vài chục giây:
 * kích thước > 0 và không đổi giữa hai lần đo cách nhau ~1,5 giây, và đọc được thời lượng dương
 * (mp4/mov đang chép dở chưa có atom `moov` nên không đọc được thời lượng).
 * Hai hàm (đọc thời lượng, chờ) tiêm được để test không phải chờ thật.
 */
class RiengReady
{
    /** Đuôi video app nhận (TikTok nhận các định dạng này). Không phân biệt hoa thường. */
    public const array EXTENSIONS = ['mp4', 'mov', 'm4v', 'webm'];

    /** @var array<string, string> */
    public const array MIME = ['mp4' => 'video/mp4', 'mov' => 'video/quicktime', 'm4v' => 'video/mp4', 'webm' => 'video/webm'];

    /** @param  (Closure(string): ?float)|null  $probe  */
    public function __construct(private readonly ?Closure $probe = null, private readonly ?Closure $sleep = null) {}

    public static function isVideoName(string $name): bool
    {
        return in_array(strtolower(pathinfo($name, PATHINFO_EXTENSION)), self::EXTENSIONS, true);
    }

    public static function mimeFor(string $nameOrPath): string
    {
        return self::MIME[strtolower(pathinfo($nameOrPath, PATHINFO_EXTENSION))] ?? 'video/mp4';
    }

    /** Tên file tạm của trình tải / ứng dụng đang ghi: không bao giờ nhận. */
    public static function isTempName(string $name): bool
    {
        $n = strtolower($name);

        return str_starts_with($n, '~$') || str_starts_with($n, '.')
            || preg_match('/\.(crdownload|part|partial|tmp|temp|download|opdownload|filepart)(\.|$)/', $n) === 1;
    }

    /** Chờ giữa hai lần đo kích thước (một lần cho cả loạt file mới). */
    public function pause(): void
    {
        $ms = max(0, (int) config('fork.auto.rieng_gap_ms', 1500));

        if ($this->sleep !== null) {
            ($this->sleep)($ms);
        } elseif ($ms > 0) {
            usleep($ms * 1000);
        }
    }

    /**
     * Thời lượng (giây) nếu đọc được và dương; null nếu file chưa dùng được (đang chép dở, hỏng, không phải video).
     */
    public function duration(string $path): ?float
    {
        $d = $this->probe !== null ? ($this->probe)($path) : $this->probeFile($path);

        return $d !== null && is_finite($d) && $d > 0 ? $d : null;
    }

    private function probeFile(string $path): ?float
    {
        $ext = strtolower(pathinfo($path, PATHINFO_EXTENSION));

        if (in_array($ext, ['mp4', 'mov', 'm4v'], true)) {
            return VideoDurationProbe::fromFile($path);
        }

        return $this->probeWithFfmpeg($path);
    }

    /** webm (và mọi định dạng không có atom mvhd): hỏi ffprobe, không có thì đọc dòng "Duration:" của ffmpeg. */
    private function probeWithFfmpeg(string $path): ?float
    {
        try {
            $ffmpeg = app(RiengThumbs::class)->ffmpegPath();
            $finder = new ExecutableFinder;
            $probe = null;

            if ($ffmpeg !== null) {
                foreach (['ffprobe.exe', 'ffprobe'] as $n) {
                    if (is_file(dirname($ffmpeg).DIRECTORY_SEPARATOR.$n)) {
                        $probe = dirname($ffmpeg).DIRECTORY_SEPARATOR.$n;
                        break;
                    }
                }
            }

            $probe ??= $finder->find('ffprobe');

            if ($probe !== null) {
                $p = new Process([$probe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', $path]);
                $p->setTimeout(20);
                $p->run();
                $v = trim($p->getOutput());

                return $p->isSuccessful() && is_numeric($v) ? (float) $v : null;
            }

            if ($ffmpeg !== null) {
                $p = new Process([$ffmpeg, '-hide_banner', '-i', $path]);
                $p->setTimeout(20);
                $p->run();

                if (preg_match('/Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)/', $p->getErrorOutput(), $m) === 1) {
                    return ((int) $m[1]) * 3600 + ((int) $m[2]) * 60 + (float) $m[3];
                }
            }
        } catch (Throwable) {
        }

        return null;
    }
}

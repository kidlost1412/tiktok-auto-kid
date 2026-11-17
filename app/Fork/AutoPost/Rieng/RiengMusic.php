<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\Models\AutoVideo;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;
use RuntimeException;
use Symfony\Component\Process\Process;
use Throwable;

/**
 * Ghép nhạc hàng loạt cho video Kho riêng, cài theo từng thư mục (cột fork_rieng_folders.music):
 *   enabled, dir (thư mục nhạc), mode: replace (tắt hẳn tiếng video, chỉ còn nhạc) | mix (giữ tiếng gốc, nhạc nhỏ đi gain_db).
 * Lúc tạo bài, mỗi video bốc ngẫu nhiên một bài nhạc (tránh lặp các bài vừa dùng), cắt vừa độ dài video, nhỏ dần ở cuối,
 * ra một file mp4 MỚI để đăng. File gốc trong thư mục không bao giờ bị đụng tới.
 */
final class RiengMusic
{
    public const array EXT = ['mp3', 'm4a', 'aac', 'wav', 'ogg', 'flac', 'opus'];

    public const string MODE_REPLACE = 'replace';

    public const string MODE_MIX = 'mix';

    public const int DEFAULT_GAIN_DB = -12;

    /** Bao nhiêu bài vừa dùng thì tránh lặp lại (theo thư mục). */
    private const int RECENT = 5;

    private const int MAX_TRACKS = 2000;

    /**
     * Cài đặt ghép nhạc của thư mục (đã chuẩn hoá).
     *
     * @return array{enabled: bool, dir: ?string, mode: string, gain_db: int}
     */
    public static function settings(?RiengFolder $folder): array
    {
        $m = $folder !== null ? (array) ($folder->music ?? []) : [];
        $dir = is_string($m['dir'] ?? null) && trim($m['dir']) !== '' ? trim($m['dir']) : null;

        return [
            'enabled' => (bool) ($m['enabled'] ?? false) && $dir !== null,
            'dir' => $dir,
            'mode' => ($m['mode'] ?? null) === self::MODE_REPLACE ? self::MODE_REPLACE : self::MODE_MIX,
            'gain_db' => max(-40, min(0, (int) ($m['gain_db'] ?? self::DEFAULT_GAIN_DB))),
        ];
    }

    /**
     * File nhạc trong thư mục (cả thư mục con), sắp theo tên.
     *
     * @return list<string>
     */
    public function tracks(?string $dir): array
    {
        if ($dir === null || ! is_dir($dir)) {
            return [];
        }

        $out = [];

        try {
            $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS));

            foreach ($it as $f) {
                if ($f->isFile() && in_array(strtolower($f->getExtension()), self::EXT, true)) {
                    $out[] = $f->getPathname();

                    if (count($out) >= self::MAX_TRACKS) {
                        break;
                    }
                }
            }
        } catch (Throwable) {
            // ổ rời rút ra giữa chừng: dùng những gì đã thấy
        }

        sort($out);

        return $out;
    }

    /** Bốc ngẫu nhiên một bài, tránh các bài vừa dùng của thư mục này. */
    public function pick(int $folderId, array $tracks): ?string
    {
        if ($tracks === []) {
            return null;
        }

        $key = 'fork-rieng:music-recent:'.$folderId;
        $recent = array_values(array_filter((array) Cache::get($key, []), 'is_string'));
        $avoid = array_slice($recent, -min(self::RECENT, count($tracks) - 1));
        $pool = array_values(array_diff($tracks, $avoid));
        $track = ($pool === [] ? $tracks : $pool)[random_int(0, count($pool === [] ? $tracks : $pool) - 1)];
        Cache::forever($key, array_slice([...$recent, $track], -self::RECENT * 2));

        return $track;
    }

    /**
     * Ghép nhạc cho video nếu thư mục của nó đang bật. null = không ghép (đăng file gốc).
     * Ném RuntimeException khi bật mà không ghép được: video không bị đăng thiếu nhạc.
     *
     * @return array{path: string, track: string, mode: string}|null
     */
    public function apply(AutoVideo $video, string $source): ?array
    {
        if (! $video->isRieng()) {
            return null;
        }

        $folder = RiengFolder::query()->find((int) data_get($video->meta, 'folder_id'));
        $s = self::settings($folder);

        if (! $s['enabled']) {
            return null;
        }

        $tracks = $this->tracks($s['dir']);

        if ($tracks === []) {
            throw new RuntimeException('Thư mục nhạc "'.$s['dir'].'" không có bài nhạc nào (hoặc ổ đĩa đang tắt).');
        }

        $track = (string) $this->pick((int) $folder->id, $tracks);
        $dir = storage_path('app/rieng-music');
        @mkdir($dir, 0775, true);
        $out = $dir.DIRECTORY_SEPARATOR.$video->id.'-'.Str::lower(Str::random(8)).'.mp4';
        $this->mix($source, $track, $out, $s['mode'], $s['gain_db']);

        return ['path' => $out, 'track' => basename($track), 'mode' => $s['mode']];
    }

    /** Ghép bằng ffmpeg (hình chép nguyên, không nén lại). */
    public function mix(string $video, string $track, string $out, string $mode, int $gainDb): void
    {
        $ffmpeg = app(RiengThumbs::class)->ffmpegPath() ?? throw new RuntimeException('Không tìm thấy ffmpeg để ghép nhạc.');
        [$videoDur, $videoAudio] = $this->probe($ffmpeg, $video);
        [$trackDur] = $this->probe($ffmpeg, $track);

        if ($videoDur === null || $videoDur <= 0) {
            throw new RuntimeException('Không đọc được độ dài video để ghép nhạc.');
        }

        // Nhạc dài hơn video: bắt đầu ở một chỗ ngẫu nhiên cho đỡ giống nhau; ngắn hơn thì lặp lại.
        $offset = $trackDur !== null && $trackDur > $videoDur + 5 ? random_int(0, (int) floor(min($trackDur - $videoDur - 2, $trackDur * 0.5))) : 0;
        $fade = min(2.0, $videoDur / 4);
        $fadeAt = max(0, $videoDur - $fade);
        $music = sprintf('[1:a]volume=%ddB,atrim=0:%.3f,afade=t=out:st=%.3f:d=%.3f[m]', $mode === self::MODE_MIX ? $gainDb : 0, $videoDur, $fadeAt, $fade);
        $filter = $mode === self::MODE_MIX && $videoAudio
            ? $music.';[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]'
            : str_replace('[m]', '[a]', $music);

        $cmd = [$ffmpeg, '-y', '-v', 'error', '-i', $video, '-stream_loop', '-1', '-ss', (string) $offset, '-i', $track,
            '-filter_complex', $filter, '-map', '0:v:0', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            '-t', sprintf('%.3f', $videoDur), '-movflags', '+faststart', $out];
        $p = new Process($cmd);
        $p->setTimeout(600);
        $p->run();

        if (! $p->isSuccessful() || ! is_file($out) || filesize($out) < 1024) {
            @unlink($out);

            throw new RuntimeException('Ghép nhạc lỗi: '.mb_substr(trim($p->getErrorOutput()), -200));
        }
    }

    /** @return array{0: ?float, 1: bool} [độ dài giây, có tiếng] */
    private function probe(string $ffmpeg, string $file): array
    {
        $p = new Process([$ffmpeg, '-hide_banner', '-i', $file]);
        $p->setTimeout(30);
        $p->run();
        $log = $p->getErrorOutput();
        $dur = preg_match('/Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)/', $log, $m) === 1 ? ((int) $m[1]) * 3600 + ((int) $m[2]) * 60 + (float) $m[3] : null;

        return [$dur, preg_match('/Stream #\d+:\d+.*Audio:/', $log) === 1];
    }
}

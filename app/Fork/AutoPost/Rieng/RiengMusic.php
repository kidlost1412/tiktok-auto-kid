<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Dto\MediaItem;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Models\Media;
use App\Models\Post;
use App\Support\VideoDurationProbe;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use RuntimeException;
use Symfony\Component\Process\Process;
use Throwable;

/**
 * Ghép nhạc hàng loạt cho video Kho riêng, cài theo từng thư mục (cột fork_rieng_folders.music):
 *   enabled, dir (thư mục nhạc), mode: replace (tắt hẳn tiếng video, chỉ còn nhạc) | mix (giữ tiếng gốc, nhạc nhỏ đi gain_db).
 * Lúc tạo bài, mỗi video bốc ngẫu nhiên một bài nhạc (tránh lặp các bài vừa dùng), cắt vừa độ dài video, nhỏ dần ở cuối,
 * ra một file mp4 MỚI để đăng (đã xoá metadata, RiengClean::args). File gốc trong thư mục không bao giờ bị đụng tới.
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
    public function apply(AutoVideo $video, string $source, array|false|null $choice = null): ?array
    {
        // $choice (Đăng hàng loạt): null = theo cài đặt của thư mục; false = không ghép nhạc; mảng = đúng bài đã chọn trong hộp.
        if (! $video->isRieng() || $choice === false) {
            return null;
        }

        if ($choice === null) {
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
        } else {
            $s = $choice;
            $track = $this->resolveIn($s['dir'], $s['rel']) ?? throw new RuntimeException('Bài nhạc đã chọn không còn trong thư mục nhạc "'.$s['dir'].'".');
        }

        $dir = storage_path('app/rieng-music');
        @mkdir($dir, 0775, true);
        $out = $dir.DIRECTORY_SEPARATOR.$video->id.'-'.Str::lower(Str::random(8)).'.mp4';
        $this->mix($source, $track, $out, $s['mode'], $s['gain_db']);

        return ['path' => $out, 'track' => basename($track), 'mode' => $s['mode']];
    }

    /**
     * Nhạc chọn được cho video này (thư mục nhạc của thư mục video), kèm bài đang dùng. null = video không ghép nhạc được.
     *
     * @return array{dir: string, mode: string, gain_db: int, current: ?string, tracks: list<array{name: string, rel: string}>}|null
     */
    public function choicesFor(AutoVideo $video, ?Post $post = null): ?array
    {
        if (! $video->isRieng()) {
            return null;
        }

        $folder = RiengFolder::query()->find((int) data_get($video->meta, 'folder_id'));
        $s = self::settings($folder);

        if ($s['dir'] === null) {
            return null;
        }

        return [
            'dir' => $s['dir'], 'mode' => $s['mode'], 'gain_db' => $s['gain_db'],
            'current' => $post !== null ? (data_get($post->meta, 'fork_music') ?: null) : null,
            'tracks' => $this->list($s['dir']),
        ];
    }

    /**
     * Bài nhạc của một thư mục: tên + đường dẫn tương đối.
     *
     * @return list<array{name: string, rel: string}>
     */
    public function list(string $dir): array
    {
        $base = rtrim(str_replace('\\', '/', $dir), '/').'/';

        return array_map(fn (string $t): array => [
            'name' => pathinfo($t, PATHINFO_FILENAME),
            'rel' => ltrim(substr(str_replace('\\', '/', $t), strlen($base)), '/'),
        ], $this->tracks($dir));
    }

    /**
     * Thứ tự bốc nhạc của một lượt đăng: xáo trộn theo $seed nhưng cố định (cùng seed = cùng thứ tự), nên giao diện và máy chủ
     * chia y hệt nhau; video thứ k nhận bài thứ k (hết bài mới quay vòng, không lặp trong lượt khi đủ bài).
     *
     * @param  list<string>  $rels
     * @return list<string>
     */
    public static function plan(array $rels, int $seed): array
    {
        usort($rels, fn (string $a, string $b): int => crc32($seed.'|'.$a) <=> crc32($seed.'|'.$b) ?: strcmp($a, $b));

        return $rels;
    }

    /** Đường dẫn thật của bài nhạc trong thư mục nhạc $dir. null = không có / không phải file nhạc / ra ngoài thư mục. */
    public function resolveIn(string $dir, string $rel): ?string
    {
        $rel = str_replace('\\', '/', $rel);
        $root = realpath($dir);
        $file = $root === false || $rel === '' || str_contains($rel, '..') ? false : realpath($root.DIRECTORY_SEPARATOR.$rel);

        if ($file === false || ! is_file($file) || ! in_array(strtolower(pathinfo($file, PATHINFO_EXTENSION)), self::EXT, true)) {
            return null;
        }

        return str_starts_with($file, rtrim($root, '/\\').DIRECTORY_SEPARATOR) ? $file : null;
    }

    /** Đường dẫn thật của một bài nhạc (theo đường tương đối trong thư mục nhạc của video). null = không có / ra ngoài thư mục. */
    public function resolve(AutoVideo $video, string $rel): ?string
    {
        $c = $this->choicesFor($video);

        if ($c === null || $rel === '' || str_contains($rel, '..')) {
            return null;
        }

        foreach ($c['tracks'] as $t) {
            if ($t['rel'] === str_replace('\\', '/', $rel)) {
                return rtrim($c['dir'], '/\\').DIRECTORY_SEPARATOR.str_replace('/', DIRECTORY_SEPARATOR, $t['rel']);
            }
        }

        return null;
    }

    /**
     * Đổi nhạc của bài đã xếp lịch (chưa lên TikTok, hoặc vừa xoá bài hẹn xong): ghép lại từ FILE GỐC với bài mới,
     * thay file đăng của bài. null = xong; ngược lại là câu báo lỗi (không đổi gì).
     */
    public function remix(AutoVideo $video, Post $post, string $track): ?string
    {
        $c = $this->choicesFor($video, $post);

        if ($c === null || ! is_file($track)) {
            return 'Không tìm thấy bài nhạc đã chọn (thư mục nhạc đổi hoặc ổ đĩa đang tắt) — chưa đổi nhạc.';
        }

        if (! is_file((string) $video->path)) {
            return 'Không còn thấy file video gốc trong thư mục — chưa đổi nhạc.';
        }

        $media = Media::query()->where('post_id', $post->id)->where('collection', Media::COLLECTION_MEDIA)->orderBy('order')->first();

        if ($media === null) {
            return 'Bài này không có file video — chưa đổi nhạc.';
        }

        $dir = storage_path('app/rieng-music');
        @mkdir($dir, 0775, true);
        $out = $dir.DIRECTORY_SEPARATOR.$video->id.'-'.Str::lower(Str::random(8)).'.mp4';

        try {
            $this->mix((string) $video->path, $track, $out, $c['mode'], $c['gain_db']);
        } catch (Throwable $e) {
            return mb_substr($e->getMessage(), 0, 300);
        }

        $old = (string) $media->path;
        $new = 'medias/'.Str::uuid().'.mp4';

        try {
            $stream = fopen($out, 'rb');

            if ($stream === false) {
                return 'Không đọc được file vừa ghép nhạc — chưa đổi nhạc.';
            }

            try {
                Storage::writeStream($new, $stream);
            } finally {
                if (is_resource($stream)) {
                    fclose($stream);
                }
            }

            $media->forceFill([
                'path' => $new,
                'mime_type' => 'video/mp4',
                'size' => (int) filesize($out),
                'original_filename' => pathinfo((string) $media->original_filename, PATHINFO_FILENAME).'.mp4',
                'meta' => VideoDurationProbe::mergeInto((array) ($media->meta ?? []), VideoDurationProbe::fromFile($out)),
            ])->save();

            $meta = (array) $post->meta;
            $meta['fork_music'] = basename($track);
            $meta['fork_music_mode'] = $c['mode'];
            $post->forceFill(['media' => [MediaItem::fromMedia($media)->toArray()], 'meta' => $meta])->save();
        } finally {
            @unlink($out);
        }

        try {
            if ($old !== '' && $old !== $new) {
                Storage::delete($old);
            }
        } catch (Throwable) {
        }

        return null;
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
            '-t', sprintf('%.3f', $videoDur), ...RiengClean::args(RiengClean::isH264($ffmpeg, $video)), $out];
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

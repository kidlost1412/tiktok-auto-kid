<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\KhoStore;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Paths;
use Carbon\CarbonImmutable;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use RecursiveCallbackFilterIterator;
use RecursiveDirectoryIterator;
use RecursiveIteratorIterator;
use SplFileInfo;
use Throwable;

/**
 * Quét các thư mục "Kho riêng": mỗi video (mp4, mov, m4v, webm; đệ quy, bỏ thư mục bắt đầu bằng `_`) thành một AutoVideo nguồn `rieng`,
 * trạng thái `new`, chưa có sản phẩm/caption. File mới được nhận NGAY khi ghi xong (RiengReady: kích thước đứng yên giữa hai lần đo
 * trong cùng lượt quét và đọc được thời lượng). Video trùng nội dung với video đã có vẫn được nhận, kèm cờ `meta.duplicate_of`.
 * App chỉ ĐỌC: không dời, không xoá, không sửa file.
 */
final class RiengScanner
{
    public const TZ = 'Asia/Ho_Chi_Minh';

    public const REASON_GONE = 'file đã bị xoá hoặc dời khỏi thư mục';

    public function __construct(private readonly KhoStore $kho = new KhoStore, private readonly ?RiengReady $ready = null) {}

    private function ready(): RiengReady
    {
        return $this->ready ?? app(RiengReady::class);
    }

    /**
     * @return array{new: int, known: int, duplicate: int, waiting: int, gone: int, folders_missing: int, skipped: int, busy: int}
     */
    public function scan(): array
    {
        $out = ['new' => 0, 'known' => 0, 'duplicate' => 0, 'waiting' => 0, 'gone' => 0, 'folders_missing' => 0, 'skipped' => 0, 'busy' => 0];

        // Một lượt quét tại một thời điểm (lịch 5 phút, nút Quét lại và quét nhanh của trang không giẫm lên nhau).
        $lock = Cache::lock('fork-rieng:scan', 600);

        if (! $lock->get()) {
            $out['busy'] = 1;

            return $out;
        }

        try {
            foreach (RiengFolder::query()->orderBy('id')->get() as $folder) {
                $root = rtrim(Paths::slash((string) $folder->path), '/');

                if (! is_dir($root)) {
                    $out['folders_missing']++;

                    continue;
                }

                $this->scanFolder($folder, $root, $out);
            }

            $out['gone'] = $this->markGone();
        } finally {
            $lock->release();
        }

        return $out;
    }

    /** @param  array<string, int>  $out */
    private function scanFolder(RiengFolder $folder, string $root, array &$out): void
    {
        $files = $this->videoFiles($root, $out['skipped']);
        $fresh = [];

        foreach (array_chunk($files, 400) as $chunk) {
            $known = AutoVideo::query()->whereIn('path', $chunk)->get(['id', 'path', 'source', 'status', 'files_deleted_at'])->keyBy('path');

            foreach ($chunk as $path) {
                $existing = $known[$path] ?? null;

                if ($existing === null) {
                    $fresh[] = $path;

                    continue;
                }

                // File từng "biến mất" nay đã có lại (video còn `new`): mở lại.
                if ($existing->isRieng() && $existing->status === AutoVideo::NEW && $existing->files_deleted_at !== null) {
                    $existing->forceFill(['files_deleted_at' => null, 'skip_reason' => null])->save();
                }

                $out['known']++;
            }
        }

        if ($fresh === []) {
            return;
        }

        // Đo kích thước hai lần cách nhau ~1,5 giây cho cả loạt file mới (một lần chờ, không phải mỗi file một lần).
        $first = [];

        foreach ($fresh as $path) {
            $first[$path] = $this->stat($path);
        }

        // File cũ hơn nhận trước: khi hai file trùng nội dung, file cũ là "bản gốc", file mới là bản trùng.
        usort($fresh, fn (string $a, string $b): int => [$first[$a]['mtime'] ?? 0, $a] <=> [$first[$b]['mtime'] ?? 0, $b]);

        $this->ready()->pause();

        foreach ($fresh as $path) {
            try {
                $again = $this->stat($path);
                $a = $first[$path];

                if ($a === null || $again === null || $a['size'] <= 0 || $a !== $again) {
                    $out['waiting']++;

                    continue;
                }

                $r = $this->ingestFile($folder, $root, $path, $again['size'], $again['mtime']);

                if ($r === 'waiting') {
                    $out['waiting']++;
                } elseif ($r === 'known') {
                    $out['known']++;
                } else {
                    $out['new']++;

                    if ($r === 'duplicate') {
                        $out['duplicate']++;
                    }
                }
            } catch (Throwable $e) {
                report($e);
            }
        }
    }

    /** @return array{size: int, mtime: int}|null */
    private function stat(string $path): ?array
    {
        clearstatcache(true, $path);
        $size = @filesize($path);
        $mtime = @filemtime($path);

        return $size === false || $mtime === false ? null : ['size' => (int) $size, 'mtime' => (int) $mtime];
    }

    /** @return 'new'|'duplicate'|'known'|'waiting' */
    private function ingestFile(RiengFolder $folder, string $root, string $path, int $size, int $mtime): string
    {
        // Đọc được thời lượng dương = file đã ghi xong (mp4/mov đang chép dở chưa có moov).
        $duration = $this->ready()->duration($path);

        if ($duration === null) {
            return 'waiting';
        }

        // Băm tốn thời gian: nhớ theo (đường dẫn, kích thước, mtime) để file không đổi không bị băm lại.
        $hashKey = 'fork-rieng:hash:'.sha1($path.'|'.$size.'|'.$mtime);
        $hash = Cache::get($hashKey);

        if (! is_string($hash) || strlen($hash) !== 64) {
            $hash = hash_file('sha256', $path);

            if ($hash === false) {
                return 'waiting';
            }

            Cache::put($hashKey, $hash, 86400);
        }

        // Trùng nội dung với video đã có (video hub, video riêng khác): vẫn nhận, ghi lại nó trùng với video nào.
        $original = AutoVideo::query()
            ->where(fn ($q) => $q->where('hash', $hash)->orWhere('content_hash', $hash))
            ->orderBy('id')->first(['id']);

        $rel = ltrim(substr($path, strlen($root)), '/');
        $when = CarbonImmutable::createFromTimestamp($mtime, self::TZ);

        try {
            AutoVideo::query()->create([
                // `hash` là UNIQUE: bản đầu tiên giữ sha256 thật; bản trùng dùng mã dẫn xuất (nội dung + đường dẫn).
                'hash' => $original === null ? $hash : hash('sha256', $hash.'|rieng|'.$path),
                'content_hash' => $hash,
                'path' => $path,
                'source' => AutoVideo::SOURCE_RIENG,
                'batch_date' => $when->format('Y-m-d'),
                'file_name' => basename($path),
                'duration' => $duration,
                'status' => AutoVideo::NEW,
                'meta' => [
                    'folder_id' => $folder->id,
                    'rel_path' => $rel,
                    'file_mtime' => $when->toIso8601String(),
                    'kich_thuoc' => $size,
                    ...($original !== null ? ['duplicate_of' => (int) $original->id] : []),
                ],
            ]);
        } catch (UniqueConstraintViolationException) {
            return 'known';
        }

        return $original === null ? 'new' : 'duplicate';
    }

    /** Video riêng còn `new` mà file không còn trên đĩa: đánh dấu để không đăng (cột files_deleted_at như video hub). */
    private function markGone(): int
    {
        $n = 0;

        AutoVideo::query()->where('source', AutoVideo::SOURCE_RIENG)->where('status', AutoVideo::NEW)->whereNull('files_deleted_at')
            ->orderBy('id')->each(function (AutoVideo $v) use (&$n): void {
                if (! is_file((string) $v->path)) {
                    $v->forceFill(['files_deleted_at' => now(), 'skip_reason' => self::REASON_GONE])->save();
                    Log::info('Kho riêng: file không còn, không đăng.', ['video_id' => $v->id]);
                    $n++;
                }
            });

        return $n;
    }

    /**
     * Video (mp4, mov, m4v, webm) dưới $root (đệ quy), bỏ thư mục bắt đầu bằng `_` và file tạm của trình tải; đường dẫn dùng '/'.
     *
     * @return list<string>
     */
    public function videoFiles(string $root, int &$skipped = 0): array
    {
        $files = [];

        try {
            $dirs = new RecursiveDirectoryIterator($root, RecursiveDirectoryIterator::SKIP_DOTS);
            $it = new RecursiveIteratorIterator(
                new RecursiveCallbackFilterIterator($dirs, function (SplFileInfo $f): bool {
                    return ! ($f->isDir() && str_starts_with($f->getFilename(), '_'));
                }),
                RecursiveIteratorIterator::LEAVES_ONLY,
                RecursiveIteratorIterator::CATCH_GET_CHILD,
            );

            foreach ($it as $f) {
                if (! $f->isFile()) {
                    continue;
                }

                $name = $f->getFilename();

                if (RiengReady::isTempName($name)) {
                    $skipped++;
                } elseif (RiengReady::isVideoName($name)) {
                    $files[] = Paths::slash($f->getPathname());
                }
            }
        } catch (Throwable $e) {
            Log::warning('Kho riêng: không đọc được thư mục.', ['dir' => $root, 'error' => $e->getMessage()]);
        }

        sort($files);

        return $files;
    }
}

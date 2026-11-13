<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\KhoStore;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Paths;
use App\Support\VideoDurationProbe;
use Carbon\CarbonImmutable;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use RecursiveDirectoryIterator;
use RecursiveIteratorIterator;
use Throwable;

/**
 * Quét các thư mục "Kho riêng": mỗi mp4 (đệ quy, bỏ thư mục bắt đầu bằng `_`) thành một AutoVideo nguồn `rieng`, trạng thái `new`,
 * chưa có sản phẩm/caption. Chỉ nhặt khi kích thước ổn định đủ `settle_seconds`. App chỉ ĐỌC: không dời, không xoá, không sửa file.
 */
final class RiengScanner
{
    public const TZ = 'Asia/Ho_Chi_Minh';

    public const REASON_GONE = 'file đã bị xoá hoặc dời khỏi thư mục';

    public function __construct(private readonly KhoStore $kho = new KhoStore) {}

    /**
     * @return array{new: int, known: int, duplicate: int, waiting: int, gone: int, folders_missing: int}
     */
    public function scan(): array
    {
        $out = ['new' => 0, 'known' => 0, 'duplicate' => 0, 'waiting' => 0, 'gone' => 0, 'folders_missing' => 0];

        foreach (RiengFolder::query()->orderBy('id')->get() as $folder) {
            $root = rtrim(Paths::slash((string) $folder->path), '/');

            if (! is_dir($root)) {
                $out['folders_missing']++;

                continue;
            }

            foreach ($this->mp4Files($root) as $file) {
                try {
                    $out[$this->ingestFile($folder, $root, $file)]++;
                } catch (Throwable $e) {
                    report($e);
                }
            }
        }

        $out['gone'] = $this->markGone();

        return $out;
    }

    /** @return 'new'|'known'|'duplicate'|'waiting' */
    private function ingestFile(RiengFolder $folder, string $root, string $path): string
    {
        $existing = AutoVideo::query()->where('path', $path)->first();

        if ($existing !== null) {
            // File từng "biến mất" nay đã có lại (video còn `new`): mở lại.
            if ($existing->isRieng() && $existing->status === AutoVideo::NEW && $existing->files_deleted_at !== null) {
                $existing->forceFill(['files_deleted_at' => null, 'skip_reason' => null])->save();
            }

            return 'known';
        }

        // Cache theo (đường dẫn, kích thước, mtime): file trùng không bị băm lại mỗi 5 phút.
        clearstatcache(true, $path);
        $size = (int) filesize($path);
        $mtime = (int) filemtime($path);
        $dupKey = 'fork-rieng:dup:'.sha1($path.'|'.$size.'|'.$mtime);

        if (Cache::has($dupKey)) {
            return 'duplicate';
        }

        if ($size <= 0 || ! $this->kho->isStable($path)) {
            return 'waiting';
        }

        $hash = hash_file('sha256', $path);

        if ($hash === false) {
            return 'waiting';
        }

        // Trùng nội dung với video bất kỳ đã có (kể cả video hub): giữ một bản.
        if (AutoVideo::query()->where('hash', $hash)->exists()) {
            Cache::put($dupKey, true, 86400);

            return 'duplicate';
        }

        $rel = ltrim(substr($path, strlen($root)), '/');
        $when = CarbonImmutable::createFromTimestamp($mtime, self::TZ);

        try {
            AutoVideo::query()->create([
                'hash' => $hash,
                'path' => $path,
                'source' => AutoVideo::SOURCE_RIENG,
                'batch_date' => $when->format('Y-m-d'),
                'file_name' => basename($path),
                'duration' => VideoDurationProbe::fromFile($path),
                'status' => AutoVideo::NEW,
                'meta' => [
                    'folder_id' => $folder->id,
                    'rel_path' => $rel,
                    'file_mtime' => $when->toIso8601String(),
                    'kich_thuoc' => $size,
                ],
            ]);
        } catch (UniqueConstraintViolationException) {
            return 'known';
        }

        return 'new';
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

    /** @return list<string> mp4 dưới $root (đệ quy), bỏ thư mục bắt đầu bằng `_`; đường dẫn dùng '/'. */
    public function mp4Files(string $root): array
    {
        $files = [];

        try {
            $dirs = new RecursiveDirectoryIterator($root, RecursiveDirectoryIterator::SKIP_DOTS);
            $it = new RecursiveIteratorIterator(
                new \RecursiveCallbackFilterIterator($dirs, function (\SplFileInfo $f): bool {
                    return ! ($f->isDir() && str_starts_with($f->getFilename(), '_'));
                }),
                RecursiveIteratorIterator::LEAVES_ONLY,
                RecursiveIteratorIterator::CATCH_GET_CHILD,
            );

            foreach ($it as $f) {
                if ($f->isFile() && strtolower($f->getExtension()) === 'mp4') {
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

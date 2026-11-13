<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Persona\CoverStore;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Str;
use InvalidArgumentException;
use Symfony\Component\Process\Process;
use Throwable;

/**
 * Ảnh bìa riêng của video trong Kho riêng (tải lên hoặc chọn một khung hình trong video).
 *
 * Chuẩn hoá đúng như ảnh bìa sản phẩm (CoverStore::prepare: jpg, cắt giữa 3:4, tối đa 1080x1440, <= 5 MB) nên đi cùng đường
 * với bìa sản phẩm tới tiện ích Chrome (meta.fork_cover + fork_cover_src=rieng, tải qua /api/ext/cover).
 *
 * Chỗ lưu: storage/app/rieng-covers/<mã video>/<uuid>.jpg (mỗi video giữ bản riêng của mình) và storage/app/rieng-covers/_tmp/<uuid>.jpg
 * (ảnh chọn trong hộp thoại, chưa gắn video nào; tự dọn sau 1 ngày).
 */
final class RiengCovers
{
    public const string SOURCE = 'rieng';

    private const int TMP_TTL = 86400;

    public function root(): string
    {
        // fork.auto.rieng_covers_dir chỉ để test trỏ sang thư mục tạm (không đụng ảnh bìa thật).
        $dir = config('fork.auto.rieng_covers_dir');

        return is_string($dir) && $dir !== '' ? rtrim($dir, '/\\') : storage_path('app/rieng-covers');
    }

    public function dir(int $videoId): string
    {
        return $this->root().'/'.$videoId;
    }

    public function tmpDir(): string
    {
        return $this->root().'/_tmp';
    }

    public static function validName(string $name): bool
    {
        return preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jpg$/', $name) === 1;
    }

    /** Đường dẫn file bìa của một video; null nếu tên lạ hoặc file mất. */
    public function path(int $videoId, string $file): ?string
    {
        if ($videoId <= 0 || ! self::validName($file)) {
            return null;
        }

        $path = $this->dir($videoId).'/'.$file;

        return is_file($path) ? $path : null;
    }

    public function tmpPath(string $token): ?string
    {
        if (! self::validName($token)) {
            return null;
        }

        $path = $this->tmpDir().'/'.$token;

        return is_file($path) ? $path : null;
    }

    /**
     * Thông tin ảnh cho job Chrome (cùng khuôn với CoverStore::forPost).
     *
     * @return array<string, mixed>|null
     */
    public function describeFile(int $videoId, string $file): ?array
    {
        $path = $this->path($videoId, $file);

        if ($path === null || ($size = (int) filesize($path)) <= 0 || $size > CoverStore::MAX_BYTES) {
            return null;
        }

        $dim = @getimagesize($path) ?: [0, 0];

        return [
            'src' => self::SOURCE,
            'video' => $videoId,
            'code' => '',
            'file' => $file,
            'name' => 'cover.jpg',
            'mime' => 'image/jpeg',
            'size' => $size,
            'sha256' => (string) hash_file('sha256', $path),
            'width' => (int) $dim[0],
            'height' => (int) $dim[1],
        ];
    }

    // ------------------------------------------------------------------ Chọn ảnh trong hộp thoại (chưa gắn video)

    /** Lưu ảnh tải lên vào chỗ tạm. Ném InvalidArgumentException (tiếng Việt) khi ảnh không hợp lệ. Trả về token (tên file). */
    public function stageUpload(UploadedFile $upload): string
    {
        if (! $upload->isValid() || ($upload->getSize() ?: 0) <= 0) {
            throw new InvalidArgumentException('Không đọc được file ảnh.');
        }

        return $this->stageBytes((string) file_get_contents($upload->getRealPath()), true);
    }

    /** Lấy khung hình tại giây $at của video, lưu vào chỗ tạm; trả về token. */
    public function stageFrame(AutoVideo $video, float $at): string
    {
        $bytes = $this->frameBytes($video, $at);

        if ($bytes === null) {
            throw new InvalidArgumentException('Không lấy được khung hình này (máy chưa có ffmpeg hoặc video không đọc được).');
        }

        return $this->stageBytes($bytes, false);
    }

    private function stageBytes(string $bytes, bool $checkInputSize): string
    {
        $prepared = app(CoverStore::class)->prepare($bytes, $checkInputSize);

        $this->ensureDir($this->tmpDir());
        $this->gcTmp();

        $token = Str::uuid()->toString().'.jpg';

        if (file_put_contents($this->tmpDir().'/'.$token, $prepared['bytes']) === false) {
            throw new InvalidArgumentException('Không ghi được file ảnh bìa.');
        }

        return $token;
    }

    private function gcTmp(): void
    {
        foreach (glob($this->tmpDir().'/*.jpg') ?: [] as $f) {
            if (time() - (int) @filemtime($f) > self::TMP_TTL) {
                @unlink($f);
            }
        }
    }

    // ------------------------------------------------------------------ Khung hình

    /** Thời điểm (giây) của ảnh nhỏ mặc định, trùng RiengThumbs. */
    public function defaultFrameTime(AutoVideo $v): float
    {
        return $v->duration !== null && $v->duration > 2 ? 1.0 : 0.0;
    }

    public function canExtract(): bool
    {
        return app(RiengThumbs::class)->ffmpegPath() !== null;
    }

    /** jpg nguyên độ phân giải của một khung; null nếu không có ffmpeg hoặc lỗi. */
    public function frameBytes(AutoVideo $v, float $at): ?string
    {
        $ffmpeg = app(RiengThumbs::class)->ffmpegPath();
        $src = (string) $v->path;

        if ($ffmpeg === null || $src === '' || ! is_file($src)) {
            return null;
        }

        $at = max(0.0, $v->duration !== null && $v->duration > 0 ? min($at, max(0.0, $v->duration - 0.1)) : $at);

        $this->ensureDir($this->tmpDir());
        $tmp = $this->tmpDir().'/frame-'.bin2hex(random_bytes(4)).'.tmp.jpg';

        try {
            $p = new Process([$ffmpeg, '-y', '-v', 'error', '-ss', number_format($at, 2, '.', ''), '-i', $src, '-frames:v', '1', '-q:v', '2', $tmp]);
            $p->setTimeout(60);
            $p->run();

            $bytes = is_file($tmp) && filesize($tmp) > 0 ? (string) file_get_contents($tmp) : null;
        } catch (Throwable) {
            $bytes = null;
        }

        @unlink($tmp);

        return $bytes;
    }

    // ------------------------------------------------------------------ Gắn vào video

    /**
     * Ghi ảnh bìa cho một video (xoá bìa cũ của video này trước). Nguồn là token đã chọn trong hộp thoại; không có token
     * thì lấy khung hình ở thời điểm ảnh nhỏ mặc định. Ném InvalidArgumentException khi không dựng được.
     *
     * @return array{file: string, w: int, h: int}
     */
    public function attach(AutoVideo $video, ?string $token): array
    {
        $this->forget((int) $video->id);

        if ($token !== null && $token !== '') {
            $src = $this->tmpPath($token) ?? throw new InvalidArgumentException('Ảnh bìa đã chọn không còn nữa, hãy chọn lại.');
            $bytes = (string) file_get_contents($src);
        } else {
            $bytes = $this->frameBytes($video, $this->defaultFrameTime($video))
                ?? throw new InvalidArgumentException('Không lấy được khung hình làm ảnh bìa (máy chưa có ffmpeg hoặc video không đọc được).');
        }

        // Ảnh tạm đã chuẩn hoá rồi; qua prepare lần nữa vô hại (đã đúng 3:4) và kiểm lại giới hạn.
        $prepared = app(CoverStore::class)->prepare($bytes, false);
        $dir = $this->dir((int) $video->id);
        $this->ensureDir($dir);
        $file = Str::uuid()->toString().'.jpg';

        if (file_put_contents($dir.'/'.$file, $prepared['bytes']) === false) {
            throw new InvalidArgumentException('Không ghi được file ảnh bìa.');
        }

        return ['file' => $file, 'w' => $prepared['w'], 'h' => $prepared['h']];
    }

    /** Xoá mọi ảnh bìa của một video (khi video bị bỏ/xoá, hoặc sau khi đã giữ đủ lâu). */
    public function forget(int $videoId): void
    {
        if ($videoId <= 0) {
            return;
        }

        $dir = $this->dir($videoId);

        if (! is_dir($dir)) {
            return;
        }

        foreach (glob($dir.'/*') ?: [] as $f) {
            if (is_file($f)) {
                @unlink($f);
            }
        }

        @rmdir($dir);
    }

    private function ensureDir(string $dir): void
    {
        if (! is_dir($dir) && ! @mkdir($dir, 0775, true) && ! is_dir($dir)) {
            throw new InvalidArgumentException('Không tạo được thư mục lưu ảnh bìa.');
        }
    }
}

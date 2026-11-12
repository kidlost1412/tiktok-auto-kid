<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Persona;

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Models\Post;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use Throwable;

/**
 * Ảnh bìa riêng của sản phẩm hub: lưu ở storage/app/covers/<mã sản phẩm>/<uuid>.jpg, luôn là JPEG (png/webp được đổi sang jpg).
 * Chọn ảnh cho từng bài ở PostBuilder; đưa cho tiện ích qua /api/ext/cover (xem ChromeJobs, ExtensionController).
 */
final class CoverStore
{
    public const string DEFAULT = 'default';

    public const string FIXED = 'fixed';

    public const string RANDOM = 'random';

    public const int MAX_BYTES = 5 * 1024 * 1024;

    public const int MAX_IMAGES = 20;

    public const int MAX_SIDE = 8000;

    public const int MIN_SIDE = 200;

    public static function normalizeMode(mixed $mode): string
    {
        return in_array($mode, [self::FIXED, self::RANDOM], true) ? $mode : self::DEFAULT;
    }

    public static function dir(string $code): string
    {
        $safe = preg_match('/^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/', $code) === 1 ? $code : 'p-'.md5($code);

        return storage_path('app/covers/'.$safe);
    }

    /** Đường dẫn file của ảnh có trong danh sách của sản phẩm, null nếu tên lạ hoặc file mất. */
    public static function pathFor(AutoProduct $p, string $file): ?string
    {
        if (! collect($p->cover_images ?? [])->contains(fn ($i): bool => ($i['file'] ?? null) === $file)) {
            return null;
        }

        $path = self::dir((string) $p->code).DIRECTORY_SEPARATOR.basename($file);

        return is_file($path) ? $path : null;
    }

    /**
     * Kiểm tra và lưu một ảnh. Ném InvalidArgumentException (tiếng Việt) khi ảnh không hợp lệ.
     *
     * @return array{entry: array<string, mixed>, warning: ?string}
     */
    public function add(AutoProduct $p, UploadedFile $upload): array
    {
        if (count($p->cover_images ?? []) >= self::MAX_IMAGES) {
            throw new InvalidArgumentException('Mỗi sản phẩm tối đa '.self::MAX_IMAGES.' ảnh bìa.');
        }

        if (! $upload->isValid() || ($upload->getSize() ?: 0) <= 0) {
            throw new InvalidArgumentException('Không đọc được file ảnh.');
        }

        if (($upload->getSize() ?: 0) > self::MAX_BYTES) {
            throw new InvalidArgumentException('Ảnh lớn hơn 5 MB.');
        }

        $bytes = (string) file_get_contents($upload->getRealPath());
        $info = @getimagesizefromstring($bytes);

        if ($info === false || ! in_array($info[2], [IMAGETYPE_JPEG, IMAGETYPE_PNG, IMAGETYPE_WEBP], true)) {
            throw new InvalidArgumentException('Chỉ nhận ảnh jpg, png hoặc webp.');
        }

        [$w, $h] = [(int) $info[0], (int) $info[1]];

        if (min($w, $h) < self::MIN_SIDE) {
            throw new InvalidArgumentException('Ảnh quá nhỏ (cạnh ngắn dưới '.self::MIN_SIDE.' px).');
        }

        if (max($w, $h) > self::MAX_SIDE) {
            throw new InvalidArgumentException('Ảnh quá lớn (cạnh dài trên '.self::MAX_SIDE.' px).');
        }

        if ($info[2] !== IMAGETYPE_JPEG) {
            $bytes = $this->toJpeg($bytes);
        }

        if (strlen($bytes) > self::MAX_BYTES) {
            throw new InvalidArgumentException('Ảnh sau khi đổi sang jpg vẫn lớn hơn 5 MB.');
        }

        $dir = self::dir((string) $p->code);

        if (! is_dir($dir) && ! @mkdir($dir, 0775, true) && ! is_dir($dir)) {
            throw new InvalidArgumentException('Không tạo được thư mục lưu ảnh bìa.');
        }

        $file = Str::uuid()->toString().'.jpg';

        if (file_put_contents($dir.DIRECTORY_SEPARATOR.$file, $bytes) === false) {
            throw new InvalidArgumentException('Không ghi được file ảnh bìa.');
        }

        $entry = [
            'file' => $file,
            'name' => mb_substr(mb_scrub(pathinfo((string) $upload->getClientOriginalName(), PATHINFO_FILENAME), 'UTF-8'), 0, 80),
            'w' => $w,
            'h' => $h,
            'size' => strlen($bytes),
            'sha256' => hash('sha256', $bytes),
        ];

        $ratio = $h > 0 ? $w / $h : 0;
        $warning = abs($ratio - 9 / 16) > 0.03 || $w < 540
            ? 'Ảnh '.$w.'x'.$h.' chưa đúng khuyến nghị 1080x1920 (tỉ lệ 9:16); TikTok có thể cắt ảnh.'
            : null;

        return ['entry' => $entry, 'warning' => $warning];
    }

    public function remove(AutoProduct $p, string $file): bool
    {
        $images = collect($p->cover_images ?? []);

        if (! $images->contains(fn ($i): bool => ($i['file'] ?? null) === $file)) {
            return false;
        }

        $path = self::dir((string) $p->code).DIRECTORY_SEPARATOR.basename($file);

        if (is_file($path)) {
            @unlink($path);
        }

        $p->forceFill([
            'cover_images' => $images->reject(fn ($i): bool => ($i['file'] ?? null) === $file)->values()->all(),
            'cover_fixed' => $p->cover_fixed === $file ? null : $p->cover_fixed,
            'cover_last' => $p->cover_last === $file ? null : $p->cover_last,
        ])->save();

        return true;
    }

    /**
     * Chọn ảnh bìa cho một bài mới theo chế độ của sản phẩm; null = dùng bìa mặc định của TikTok.
     * Ngẫu nhiên thì không chọn lại ảnh vừa dùng cho bài trước (khi có từ 2 ảnh trở lên).
     */
    public function pick(AutoProduct $p): ?string
    {
        if (self::normalizeMode($p->cover_mode) === self::DEFAULT) {
            return null;
        }

        return DB::transaction(function () use ($p): ?string {
            $fresh = AutoProduct::query()->whereKey($p->code)->lockForUpdate()->first() ?? $p;
            $files = collect($fresh->cover_images ?? [])
                ->pluck('file')
                ->filter(fn ($f): bool => is_string($f) && self::pathFor($fresh, $f) !== null)
                ->values();

            if ($files->isEmpty()) {
                return null;
            }

            if (self::normalizeMode($fresh->cover_mode) === self::FIXED) {
                return $files->contains($fresh->cover_fixed) ? $fresh->cover_fixed : $files->first();
            }

            $pool = $files->count() > 1 ? $files->reject(fn ($f): bool => $f === $fresh->cover_last)->values() : $files;
            $chosen = $pool[random_int(0, $pool->count() - 1)];

            $fresh->forceFill(['cover_last' => $chosen])->save();
            $p->cover_last = $chosen;

            return $chosen;
        });
    }

    /**
     * Ảnh bìa của một bài cho job Chrome: ảnh đã chọn lúc dựng bài (meta.fork_cover), còn thuộc bộ ảnh hiện tại của sản phẩm.
     *
     * @return array{code: string, file: string, name: string, mime: string, size: int, sha256: string}|null
     */
    public function forPost(Post $post): ?array
    {
        $file = data_get($post->meta, 'fork_cover');
        $videoId = data_get($post->meta, 'fork_auto_video_id');

        if (! is_string($file) || $file === '' || ! $videoId) {
            return null;
        }

        try {
            $code = AutoVideo::query()->whereKey($videoId)->value('product_code');
            $product = $code ? AutoProduct::query()->find($code) : null;

            if ($product === null || self::normalizeMode($product->cover_mode) === self::DEFAULT) {
                return null;
            }

            $path = self::pathFor($product, $file);

            if ($path === null || ($size = (int) filesize($path)) <= 0 || $size > self::MAX_BYTES) {
                return null;
            }

            return [
                'code' => (string) $product->code,
                'file' => $file,
                'name' => 'cover.jpg',
                'mime' => 'image/jpeg',
                'size' => $size,
                'sha256' => (string) hash_file('sha256', $path),
            ];
        } catch (Throwable) {
            return null;
        }
    }

    /** @return list<array{file: string, name: string, w: int, h: int, size: int, url: string}> */
    public function describe(AutoProduct $p): array
    {
        return collect($p->cover_images ?? [])
            ->filter(fn ($i): bool => is_array($i) && is_string($i['file'] ?? null))
            ->map(fn (array $i): array => [
                'file' => $i['file'],
                'name' => (string) ($i['name'] ?? ''),
                'w' => (int) ($i['w'] ?? 0),
                'h' => (int) ($i['h'] ?? 0),
                'size' => (int) ($i['size'] ?? 0),
                'url' => '/auto/anh-bia/'.rawurlencode((string) $p->code).'/'.$i['file'],
            ])->values()->all();
    }

    private function toJpeg(string $bytes): string
    {
        if (! function_exists('imagecreatefromstring')) {
            throw new InvalidArgumentException('Máy chưa có thư viện xử lý ảnh (GD) để đổi png/webp sang jpg; hãy tải ảnh jpg.');
        }

        $src = @imagecreatefromstring($bytes);

        if ($src === false) {
            throw new InvalidArgumentException('Không đọc được ảnh (file hỏng?).');
        }

        $w = imagesx($src);
        $h = imagesy($src);
        $dst = imagecreatetruecolor($w, $h);
        imagefill($dst, 0, 0, (int) imagecolorallocate($dst, 255, 255, 255));   // nền trắng cho ảnh trong suốt
        imagecopy($dst, $src, 0, 0, 0, 0, $w, $h);

        ob_start();
        imagejpeg($dst, null, 92);
        $out = (string) ob_get_clean();

        return $out;
    }
}

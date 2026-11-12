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

    /** Studio từ chối ảnh bìa nhỏ hơn 324x432. Ảnh luôn được cắt giữa theo 3:4 rồi thu về tối đa 1080x1440. */
    public const int MIN_WIDTH = 324;

    public const int MIN_HEIGHT = 432;

    public const int TARGET_WIDTH = 1080;

    public const int TARGET_HEIGHT = 1440;

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

        [$cw, $ch] = self::cropSize($w, $h);

        if ($cw < self::MIN_WIDTH || $ch < self::MIN_HEIGHT) {
            throw new InvalidArgumentException('Ảnh quá nhỏ: sau khi cắt 3:4 phải tối thiểu '.self::MIN_WIDTH.'×'.self::MIN_HEIGHT.' px (ảnh này chỉ còn '.$cw.'×'.$ch.').');
        }

        if (max($w, $h) > self::MAX_SIDE) {
            throw new InvalidArgumentException('Ảnh quá lớn (cạnh dài trên '.self::MAX_SIDE.' px).');
        }

        // Luôn cắt giữa theo 3:4 (đúng cách Studio gửi bìa tự tải lên) và đổi sang jpg.
        [$bytes, $cw, $ch] = $this->cropToJpeg($bytes);

        if (strlen($bytes) > self::MAX_BYTES) {
            throw new InvalidArgumentException('Ảnh sau khi cắt và đổi sang jpg vẫn lớn hơn 5 MB.');
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
            'w' => $cw,
            'h' => $ch,
            'orig_w' => $w,
            'orig_h' => $h,
            'size' => strlen($bytes),
            'sha256' => hash('sha256', $bytes),
        ];

        $ratio = $h > 0 ? $w / $h : 0;
        $notes = [];

        if (abs($ratio - 3 / 4) > 0.01) {
            $notes[] = 'ảnh '.$w.'×'.$h.' không phải 3:4 nên đã được cắt giữa còn '.$cw.'×'.$ch;
        }

        if ($cw < self::TARGET_WIDTH) {
            $notes[] = 'khuyên dùng '.self::TARGET_WIDTH.'×'.self::TARGET_HEIGHT.' (3:4) để bìa nét';
        }

        $warning = $notes === [] ? null : ucfirst(implode('; ', $notes)).'.';

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
     * Ngẫu nhiên = xoay vòng đều: ưu tiên ảnh đã dùng ít nhất, không lặp ảnh vừa dùng (khi có từ 2 ảnh trở lên).
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

            // Xoay vòng đều: chọn ảnh đã dùng ít nhất (đếm ở cover_images[].used), hoà thì bốc ngẫu nhiên,
            // không lặp lại ảnh vừa dùng ngay trước đó khi bộ có từ 2 ảnh. Ít ảnh vẫn được dùng lặp lại.
            $images = collect($fresh->cover_images ?? []);
            $used = fn (string $f): int => (int) ($images->first(fn ($i): bool => ($i['file'] ?? null) === $f)['used'] ?? 0);
            $pool = $files->count() > 1 ? $files->reject(fn ($f): bool => $f === $fresh->cover_last)->values() : $files;
            $min = $pool->map(fn ($f): int => $used($f))->min();
            $ties = $pool->filter(fn ($f): bool => $used($f) === $min)->values();
            $chosen = $ties[random_int(0, $ties->count() - 1)];

            $fresh->forceFill([
                'cover_last' => $chosen,
                'cover_images' => $images->map(fn ($i) => is_array($i) && ($i['file'] ?? null) === $chosen
                    ? array_merge($i, ['used' => $used($chosen) + 1])
                    : $i)->values()->all(),
            ])->save();
            $p->cover_images = $fresh->cover_images;
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
            $entry = collect($product->cover_images ?? [])->first(fn ($i): bool => ($i['file'] ?? null) === $file) ?? [];

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
                'width' => (int) ($entry['w'] ?? 0),
                'height' => (int) ($entry['h'] ?? 0),
            ];
        } catch (Throwable) {
            return null;
        }
    }

    /**
     * orig_w/orig_h: kích thước ảnh gốc trước khi cắt 3:4 (null với ảnh tải lên từ bản cũ), để giao diện
     * cho thấy phần đã bị cắt.
     *
     * @return list<array{file: string, name: string, w: int, h: int, orig_w: int|null, orig_h: int|null, size: int, url: string}>
     */
    public function describe(AutoProduct $p): array
    {
        return collect($p->cover_images ?? [])
            ->filter(fn ($i): bool => is_array($i) && is_string($i['file'] ?? null))
            ->map(fn (array $i): array => [
                'file' => $i['file'],
                'name' => (string) ($i['name'] ?? ''),
                'w' => (int) ($i['w'] ?? 0),
                'h' => (int) ($i['h'] ?? 0),
                'orig_w' => isset($i['orig_w']) ? (int) $i['orig_w'] : null,
                'orig_h' => isset($i['orig_h']) ? (int) $i['orig_h'] : null,
                'size' => (int) ($i['size'] ?? 0),
                'url' => '/auto/anh-bia/'.rawurlencode((string) $p->code).'/'.$i['file'],
            ])->values()->all();
    }

    /** Kích thước sau khi cắt giữa theo 3:4 (chưa thu nhỏ). @return array{0: int, 1: int} */
    public static function cropSize(int $w, int $h): array
    {
        if ($w * 4 > $h * 3) {
            return [(int) round($h * 3 / 4), $h];   // rộng hơn 3:4: cắt hai bên
        }

        return [$w, (int) round($w * 4 / 3)];       // cao hơn 3:4: cắt trên dưới
    }

    /** @return array{0: string, 1: int, 2: int} jpg, rộng, cao */
    private function cropToJpeg(string $bytes): array
    {
        if (! function_exists('imagecreatefromstring')) {
            throw new InvalidArgumentException('Máy chưa có thư viện xử lý ảnh (GD) để cắt ảnh; hãy liên hệ người cài đặt.');
        }

        $src = @imagecreatefromstring($bytes);

        if ($src === false) {
            throw new InvalidArgumentException('Không đọc được ảnh (file hỏng?).');
        }

        $w = imagesx($src);
        $h = imagesy($src);
        [$cw, $ch] = self::cropSize($w, $h);
        $sx = intdiv($w - $cw, 2);
        $sy = intdiv($h - $ch, 2);
        [$ow, $oh] = $cw > self::TARGET_WIDTH ? [self::TARGET_WIDTH, self::TARGET_HEIGHT] : [$cw, $ch];

        $dst = imagecreatetruecolor($ow, $oh);
        imagefill($dst, 0, 0, (int) imagecolorallocate($dst, 255, 255, 255));   // nền trắng cho ảnh trong suốt
        imagecopyresampled($dst, $src, 0, 0, $sx, $sy, $ow, $oh, $cw, $ch);

        ob_start();
        imagejpeg($dst, null, 92);
        $out = (string) ob_get_clean();

        return [$out, $ow, $oh];
    }
}

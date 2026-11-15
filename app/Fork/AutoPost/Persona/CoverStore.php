<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Persona;

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Rieng\RiengCovers;
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

    /**
     * Studio từ chối ảnh bìa nhỏ hơn 324x432. Hai tỉ lệ được giữ: 3:4 (tối đa 1080x1440, tối thiểu 324x432)
     * và 9:16 (tối đa 1080x1920, tối thiểu 324x576). Ảnh lệch tỉ lệ quá 3% được cắt giữa về tỉ lệ gần nhất.
     */
    public const int MIN_WIDTH = 324;

    public const int MIN_HEIGHT = 432;

    public const int MIN_HEIGHT_TALL = 576;

    public const int TARGET_WIDTH = 1080;

    public const int TARGET_HEIGHT = 1440;

    public const int TARGET_HEIGHT_TALL = 1920;

    /** Sai số tỉ lệ (tương đối) mà ảnh vẫn được coi là đúng 3:4 hoặc 9:16 và giữ nguyên, không cắt. */
    public const float RATIO_TOLERANCE = 0.03;

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

        ['bytes' => $bytes, 'w' => $cw, 'h' => $ch, 'orig_w' => $w, 'orig_h' => $h] = $this->prepare((string) file_get_contents($upload->getRealPath()));

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

        $tall = self::isTall($cw, $ch);
        $label = $tall ? '9:16' : '3:4';
        $notes = [];

        if (self::planCrop($w, $h)[0] !== $w || self::planCrop($w, $h)[1] !== $h) {
            $notes[] = 'ảnh '.$w.'×'.$h.' không đúng 3:4 hay 9:16 nên đã được cắt giữa theo '.$label.' còn '.$cw.'×'.$ch;
        }

        if ($cw < self::TARGET_WIDTH) {
            $notes[] = 'khuyên dùng '.self::TARGET_WIDTH.'×'.($tall ? self::TARGET_HEIGHT_TALL : self::TARGET_HEIGHT).' ('.$label.') để bìa nét';
        }

        $warning = $notes === [] ? null : ucfirst(implode('; ', $notes)).'.';

        return ['entry' => $entry, 'warning' => $warning];
    }

    /**
     * Kiểm tra ảnh (jpg/png/webp, đủ lớn, không quá 5 MB) và chuẩn hoá về đúng thứ pipeline cần: jpg giữ tỉ lệ 3:4 hoặc 9:16
     * (lệch quá 3% thì cắt giữa về tỉ lệ gần nhất), tối đa 1080x1440 (3:4) hoặc 1080x1920 (9:16).
     * Dùng chung cho ảnh bìa sản phẩm và ảnh bìa của video riêng. Ném InvalidArgumentException (tiếng Việt) khi không hợp lệ.
     *
     * @return array{bytes: string, w: int, h: int, orig_w: int, orig_h: int}
     */
    public function prepare(string $bytes, bool $checkInputSize = true): array
    {
        if ($checkInputSize && strlen($bytes) > self::MAX_BYTES) {
            throw new InvalidArgumentException('Ảnh lớn hơn 5 MB.');
        }

        $info = @getimagesizefromstring($bytes);

        if ($info === false || ! in_array($info[2], [IMAGETYPE_JPEG, IMAGETYPE_PNG, IMAGETYPE_WEBP], true)) {
            throw new InvalidArgumentException('Chỉ nhận ảnh jpg, png hoặc webp.');
        }

        [$w, $h] = [(int) $info[0], (int) $info[1]];

        [$cw, $ch] = self::planCrop($w, $h);
        $tall = self::isTall($cw, $ch);
        $minH = $tall ? self::MIN_HEIGHT_TALL : self::MIN_HEIGHT;

        if ($cw < self::MIN_WIDTH || $ch < $minH) {
            throw new InvalidArgumentException('Ảnh quá nhỏ: sau khi cắt '.($tall ? '9:16' : '3:4').' phải tối thiểu '.self::MIN_WIDTH.'×'.$minH.' px (ảnh này chỉ còn '.$cw.'×'.$ch.').');
        }

        if (max($w, $h) > self::MAX_SIDE) {
            throw new InvalidArgumentException('Ảnh quá lớn (cạnh dài trên '.self::MAX_SIDE.' px).');
        }

        // Giữ 3:4 / 9:16, ngoài ra cắt giữa về tỉ lệ gần nhất, rồi đổi sang jpg.
        [$out, $cw, $ch] = $this->cropToJpeg($bytes);

        if (strlen($out) > self::MAX_BYTES) {
            throw new InvalidArgumentException('Ảnh sau khi cắt và đổi sang jpg vẫn lớn hơn 5 MB.');
        }

        return ['bytes' => $out, 'w' => $cw, 'h' => $ch, 'orig_w' => $w, 'orig_h' => $h];
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

        // Ảnh bìa riêng của video trong Kho riêng (tải lên / chọn khung): file nằm ở rieng-covers/<mã video>/, không qua bộ ảnh sản phẩm.
        if (data_get($post->meta, 'fork_cover_src') === RiengCovers::SOURCE) {
            return app(RiengCovers::class)->describeFile((int) $videoId, $file);
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

    /** Cắt giữa theo 9:16 (chưa thu nhỏ). @return array{0: int, 1: int} */
    public static function cropSizeTall(int $w, int $h): array
    {
        if ($w * 16 > $h * 9) {
            return [(int) round($h * 9 / 16), $h];
        }

        return [$w, (int) round($w * 16 / 9)];
    }

    /**
     * Kích thước ảnh bìa sau xử lý (chưa thu nhỏ): giữ nguyên nếu tỉ lệ w/h cách 3:4 hoặc 9:16 không quá 3%,
     * còn lại cắt giữa theo tỉ lệ gần hơn (so theo tỉ lệ logarit).
     *
     * @return array{0: int, 1: int}
     */
    public static function planCrop(int $w, int $h): array
    {
        if ($w <= 0 || $h <= 0) {
            return [$w, $h];
        }

        $r = $w / $h;

        foreach ([3 / 4, 9 / 16] as $target) {
            if (abs($r - $target) / $target <= self::RATIO_TOLERANCE) {
                return [$w, $h];
            }
        }

        return abs(log($r / (3 / 4))) <= abs(log($r / (9 / 16))) ? self::cropSize($w, $h) : self::cropSizeTall($w, $h);
    }

    /** Ảnh đã chuẩn hoá có phải loại 9:16 không (gần 9:16 hơn 3:4). */
    public static function isTall(int $w, int $h): bool
    {
        return $w > 0 && $h > 0 && abs(log(($w / $h) / (9 / 16))) < abs(log(($w / $h) / (3 / 4)));
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
        [$cw, $ch] = self::planCrop($w, $h);
        $sx = intdiv($w - $cw, 2);
        $sy = intdiv($h - $ch, 2);
        $maxH = self::isTall($cw, $ch) ? self::TARGET_HEIGHT_TALL : self::TARGET_HEIGHT;
        $scale = min(1.0, self::TARGET_WIDTH / $cw, $maxH / $ch);
        [$ow, $oh] = $scale < 1.0 ? [max(1, (int) round($cw * $scale)), max(1, (int) round($ch * $scale))] : [$cw, $ch];

        $dst = imagecreatetruecolor($ow, $oh);
        imagefill($dst, 0, 0, (int) imagecolorallocate($dst, 255, 255, 255));   // nền trắng cho ảnh trong suốt
        imagecopyresampled($dst, $src, 0, 0, $sx, $sy, $ow, $oh, $cw, $ch);

        ob_start();
        imagejpeg($dst, null, 92);
        $out = (string) ob_get_clean();

        return [$out, $ow, $oh];
    }
}

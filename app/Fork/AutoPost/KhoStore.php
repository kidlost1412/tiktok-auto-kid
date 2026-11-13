<?php

declare(strict_types=1);

namespace App\Fork\AutoPost;

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoSetting;
use App\Fork\AutoPost\Models\AutoVideo;
use Carbon\CarbonImmutable;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;

/**
 * Kho chuẩn mới: <hub>/kho-dang/ (video sẵn sàng đăng, mỗi X.mp4 có X.json) và <hub>/da-dang/<ngày>/.
 * Chuẩn đầy đủ: app/Fork/AutoPost/KHO-CHUAN.md.
 */
final class KhoStore
{
    public const RETENTION_KEY = 'retention';

    public const RETENTIONS = ['xoa_ngay', '7', '30', 'vinh_vien'];

    /** Cột của AutoVideo lấy thẳng từ khoá cùng tên trong file .json. */
    private const JSON_COLUMNS = ['goc', 'giong', 'nhac', 'font', 'phu_de', 'chuyen_canh', 'chuyen_dong', 'mau'];

    /** Khoá đã có cột riêng, không bỏ vào meta. */
    private const JSON_KNOWN = ['ma', 'quy_cach', 'goc', 'giong', 'loi_thoai', 'ngay_lam', 'phien_ban', 'nhac', 'font', 'phu_de', 'chuyen_canh', 'chuyen_dong', 'mau', 'thoi_luong', 'caption', 'hashtag', 'ten_gio'];

    public function hub(): string
    {
        return Paths::root((string) config('fork.auto.hub_path'));
    }

    public function khoPath(): string
    {
        return $this->hub().'/'.trim((string) config('fork.auto.kho_dir', 'kho-dang'), '/\\');
    }

    public function donePath(): string
    {
        return $this->hub().'/'.trim((string) config('fork.auto.done_dir', 'da-dang'), '/\\');
    }

    public function retention(): string
    {
        $value = AutoSetting::read(self::RETENTION_KEY);

        if ($value !== null && in_array($value, self::RETENTIONS, true)) {
            return $value;
        }

        $default = (string) config('fork.auto.retention_default', '30');

        return in_array($default, self::RETENTIONS, true) ? $default : '30';
    }

    /**
     * @return array{new: int, skipped: int, known: int, error: int, waiting: int}
     */
    public function ingest(): array
    {
        $result = ['new' => 0, 'skipped' => 0, 'known' => 0, 'error' => 0, 'waiting' => 0];

        foreach ($this->khoFiles() as $path) {
            $json = substr($path, 0, -4).'.json';

            if (AutoVideo::query()->where('path', $path)->exists()) {
                $result['known']++;

                continue;
            }

            if (! is_file($json)) {
                $age = time() - (int) filemtime($path);

                if ($age > (int) config('fork.auto.json_wait_minutes', 120) * 60) {
                    $this->reject($path, $json, 'thiếu file .json đi kèm');
                    $result['error']++;
                } else {
                    $result['waiting']++;
                }

                continue;
            }

            if (! $this->isStable($path) || ! $this->isStable($json)) {
                $result['waiting']++;

                continue;
            }

            $data = json_decode((string) file_get_contents($json), true);

            if (! is_array($data) || array_is_list($data)) {
                $this->reject($path, $json, 'file .json không hợp lệ');
                $result['error']++;

                continue;
            }

            $problem = $this->validate($data);

            if ($problem !== null) {
                $this->reject($path, $json, $problem);
                $result['error']++;

                continue;
            }

            $hash = hash_file('sha256', $path);

            if ($hash === false) {
                $result['waiting']++;

                continue;
            }

            if ($existing = AutoVideo::query()->where('hash', $hash)->first(['id'])) {
                $this->reject($path, $json, "trùng video đã có trong kho (id {$existing->id})");
                $result['error']++;

                continue;
            }

            try {
                AutoVideo::query()->create($this->attributes($path, $json, $hash, $data));
            } catch (UniqueConstraintViolationException) {
                $result['known']++;

                continue;
            }

            $result['new']++;
        }

        return $result;
    }

    /** Dời video đã đăng vào da-dang/<ngày đăng>/, ghi .ket-qua.json, rồi xoá mp4/json nếu cài đặt là xoa_ngay. */
    public function archive(AutoVideo $v): void
    {
        // Video riêng của chủ app: không bao giờ dời/xoá file.
        if ($v->isRieng()) {
            return;
        }

        $postedAt = CarbonImmutable::instance($v->posted_at ?? now())->setTimezone('Asia/Ho_Chi_Minh');
        $dir = $this->donePath().'/'.$postedAt->format('Y-m-d');

        if (! is_dir($dir) && ! @mkdir($dir, 0775, true) && ! is_dir($dir)) {
            Log::warning('AutoPost: không tạo được thư mục da-dang', ['dir' => $dir]);

            return;
        }

        $name = basename($v->path);

        if (dirname($v->path) !== $dir) {
            if (! is_file($v->path)) {
                Log::warning('AutoPost: không thấy file để chuyển sang da-dang', ['path' => $v->path]);
            } else {
                $target = $dir.'/'.$name;

                if (file_exists($target)) {
                    $target = $dir.'/'.pathinfo($name, PATHINFO_FILENAME).'-'.$v->id.'.mp4';
                }

                if (! @rename($v->path, $target)) {
                    Log::warning('AutoPost: không chuyển được file sang da-dang', ['from' => $v->path, 'to' => $target]);

                    return;
                }

                if ($v->json_path && is_file($v->json_path)) {
                    @rename($v->json_path, substr($target, 0, -4).'.json');
                }

                $v->path = $target;
                $v->json_path = substr($target, 0, -4).'.json';
            }
        }

        $v->loadMissing('socialAccount');
        $stats = (array) ($v->stats ?? []);
        $result = [
            'file' => basename($v->path),
            'hash' => $v->hash,
            'ma' => $v->product_code,
            'quy_cach' => $v->quy_cach,
            'kenh' => $v->socialAccount?->username,
            'tiktok_video_id' => $v->tiktok_video_id,
            'tiktok_link' => $stats['link'] ?? null,
            'dang_luc' => $postedAt->toIso8601String(),
            'goc' => $v->goc,
            'ngay_lam' => $v->batch_date?->format('Y-m-d'),
        ];
        @file_put_contents(
            substr($v->path, 0, -4).'.ket-qua.json',
            json_encode($result, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT),
        );

        if ($this->retention() === 'xoa_ngay') {
            $this->deleteFiles($v);
        }
    }

    /**
     * Xoá mp4/json trong da-dang của thư mục ngày quá hạn (không bao giờ xoá .ket-qua.json).
     *
     * @return array{deleted: int, retention: string}
     */
    public function cleanup(?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now('Asia/Ho_Chi_Minh');
        $retention = $this->retention();
        $deleted = 0;

        if ($retention === 'vinh_vien' || ! is_dir($this->donePath())) {
            return ['deleted' => 0, 'retention' => $retention];
        }

        $limit = $retention === 'xoa_ngay' ? null : $now->startOfDay()->subDays((int) $retention);

        foreach (scandir($this->donePath()) ?: [] as $entry) {
            if (! preg_match('/^\d{4}-\d{2}-\d{2}$/', $entry)) {
                continue;
            }

            $dir = $this->donePath().'/'.$entry;

            if (! is_dir($dir)) {
                continue;
            }

            // Thư mục ngày phải CŨ HƠN hạn (ngày đăng < hôm nay - N ngày).
            if ($limit !== null && CarbonImmutable::parse($entry, 'Asia/Ho_Chi_Minh')->greaterThanOrEqualTo($limit)) {
                continue;
            }

            foreach (scandir($dir) ?: [] as $file) {
                if (str_ends_with($file, '.ket-qua.json') || ! preg_match('/\.(mp4|json)$/', $file)) {
                    continue;
                }

                if (@unlink($dir.'/'.$file)) {
                    $deleted++;
                }
            }

            AutoVideo::query()
                ->where('source', 'kho')
                ->whereNull('files_deleted_at')
                ->where('path', 'like', str_replace(['\\', '%', '_'], ['\\\\', '\%', '\_'], $dir).'/%')
                ->update(['files_deleted_at' => now()]);
        }

        return ['deleted' => $deleted, 'retention' => $retention];
    }

    /** Đếm file chờ nhặt và file lỗi trong kho (để hiện trên trang Kho). */
    public function folderCounts(): array
    {
        $errors = is_dir($this->khoPath().'/_loi') ? count(glob($this->khoPath().'/_loi/*.mp4') ?: []) : 0;
        $known = AutoVideo::query()->where('source', 'kho')->pluck('path')->flip();
        $waiting = 0;

        foreach ($this->khoFiles() as $path) {
            if (! isset($known[$path])) {
                $waiting++;
            }
        }

        return ['waiting' => $waiting, 'error' => $errors];
    }

    private function deleteFiles(AutoVideo $v): void
    {
        if ($v->isRieng()) {
            return;
        }

        foreach ([$v->path, $v->json_path] as $file) {
            if ($file && is_file($file)) {
                @unlink($file);
            }
        }

        $v->files_deleted_at = now();
    }

    /** @return list<string> mp4 trong kho-dang/ và kho-dang/<ma>/ (bỏ thư mục bắt đầu bằng _) */
    private function khoFiles(): array
    {
        $root = $this->khoPath();

        if (! is_dir($root)) {
            return [];
        }

        $files = Paths::glob($root.'/*.mp4');

        foreach (scandir($root) ?: [] as $entry) {
            if ($entry === '.' || $entry === '..' || str_starts_with($entry, '_') || ! is_dir($root.'/'.$entry)) {
                continue;
            }

            $files = array_merge($files, Paths::glob($root.'/'.$entry.'/*.mp4'));
        }

        sort($files);

        return $files;
    }

    /** Ổn định = kích thước không đổi suốt `settle_seconds` (theo dõi qua cache giữa các lần quét). */
    public function isStable(string $path): bool
    {
        $settle = (int) config('fork.auto.settle_seconds', 20);
        clearstatcache(true, $path);
        $size = (int) filesize($path);
        $key = 'fork-auto:size:'.sha1($path);
        $seen = Cache::get($key);

        if (! is_array($seen) || ($seen['size'] ?? null) !== $size) {
            Cache::put($key, ['size' => $size, 'since' => time()], 3600);

            return $settle <= 0 && $size > 0;
        }

        return $size > 0 && time() - (int) $seen['since'] >= $settle;
    }

    /** @param  array<string, mixed>  $data */
    public function validate(array $data): ?string
    {
        $ma = $data['ma'] ?? null;

        if (! is_string($ma) || $ma === '') {
            return 'json thiếu "ma"';
        }

        $product = AutoProduct::query()->find($ma);

        if ($product === null) {
            return "mã sản phẩm \"{$ma}\" chưa có trong san-pham/";
        }

        $quyCach = $data['quy_cach'] ?? null;

        if ($quyCach !== null && ! is_string($quyCach)) {
            return '"quy_cach" phải là chuỗi hoặc null';
        }

        $codes = collect((array) $product->quy_cach)->pluck('ma')->map(fn ($c): string => (string) $c)->all();

        if ($codes === [] && $quyCach !== null) {
            return "sản phẩm \"{$ma}\" không có quy cách nhưng json ghi \"{$quyCach}\"";
        }

        if ($codes !== [] && ($quyCach === null || ! in_array($quyCach, $codes, true))) {
            return 'quy cách "'.($quyCach ?? 'null').'" không nằm trong '.implode('/', $codes);
        }

        if (isset($data['ngay_lam']) && (! is_string($data['ngay_lam']) || ! preg_match('/^\d{4}-\d{2}-\d{2}$/', $data['ngay_lam']))) {
            return '"ngay_lam" phải dạng YYYY-MM-DD';
        }

        return null;
    }

    /** @param  array<string, mixed>  $data */
    private function attributes(string $path, string $json, string $hash, array $data): array
    {
        $text = HubText::resolve($path, $data);

        $attributes = [
            'hash' => $hash,
            'path' => $path,
            'json_path' => $json,
            'source' => 'kho',
            'batch_date' => $data['ngay_lam'] ?? now('Asia/Ho_Chi_Minh')->format('Y-m-d'),
            'file_name' => basename($path),
            'product_code' => (string) $data['ma'],
            'quy_cach' => $data['quy_cach'] ?? null,
            'phien_ban' => isset($data['phien_ban']) && is_numeric($data['phien_ban']) ? (int) $data['phien_ban'] : null,
            'duration' => isset($data['thoi_luong']) && is_numeric($data['thoi_luong']) ? (float) $data['thoi_luong'] : null,
            'script' => isset($data['loi_thoai']) && is_scalar($data['loi_thoai']) && $data['loi_thoai'] !== '' ? (string) $data['loi_thoai'] : null,
            'status' => AutoVideo::NEW,
            'caption' => $text['caption'],
            'hashtags' => $text['hashtags'],
            'caption_source' => $text['caption'] === null ? null : HubText::SOURCE,
            'product_name' => $text['ten_gio'],
            // Chưa có caption từ hub thì video chờ ở trạng thái mới nhưng không được giữ chỗ.
            'skip_reason' => $text['reason'],
            'meta' => array_diff_key($data, array_flip(self::JSON_KNOWN)) ?: null,
        ];

        foreach (self::JSON_COLUMNS as $column) {
            $attributes[$column] = isset($data[$column]) && is_scalar($data[$column]) && $data[$column] !== '' ? (string) $data[$column] : null;
        }

        return $attributes;
    }

    /** Chuyển mp4 + json vào kho-dang/_loi/ kèm <tên>.loi.txt ghi lý do. */
    private function reject(string $path, string $json, string $reason): void
    {
        $dir = $this->khoPath().'/_loi';

        if (! is_dir($dir) && ! @mkdir($dir, 0775, true) && ! is_dir($dir)) {
            Log::warning('AutoPost: không tạo được kho-dang/_loi', ['dir' => $dir]);

            return;
        }

        $name = basename($path);
        $stem = pathinfo($name, PATHINFO_FILENAME);

        if (file_exists($dir.'/'.$name)) {
            $stem .= '-'.date('His');
            $name = $stem.'.mp4';
        }

        @rename($path, $dir.'/'.$name);

        if (is_file($json)) {
            @rename($json, $dir.'/'.$stem.'.json');
        }

        @file_put_contents($dir.'/'.$stem.'.loi.txt', $reason."\n");
        Cache::forget('fork-auto:size:'.sha1($path));
        Log::warning('AutoPost: video vào kho-dang/_loi', ['file' => $name, 'reason' => $reason]);
    }
}

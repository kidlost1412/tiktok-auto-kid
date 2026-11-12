<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Hub;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Scheduling\MissingVideoFile;
use App\Models\Media;
use App\Models\Post;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Log;
use RuntimeException;

/**
 * Lấy file mp4/ảnh bìa của video hub. Ưu tiên đường dẫn trên đĩa (thư mục hub gắn vào máy);
 * không có thì tải qua HTTP (url_file/url_anh_bia hub trả) vào storage/app/hub-cache/<hub_id>.(mp4|jpg),
 * kiểm tra kích thước + sha256, đổi tên nguyên tử, lần sau dùng lại.
 */
class HubFiles
{
    public function __construct(private readonly HubApi $api = new HubApi) {}

    public function cacheDir(): string
    {
        return storage_path('app/hub-cache');
    }

    /** Video có lấy được không: file trên đĩa, bản cache, hoặc có url_file để tải. */
    public function available(AutoVideo $v): bool
    {
        return $this->localVideo($v) !== null || $this->videoUrl($v) !== null;
    }

    /** File mp4 đã có sẵn trên máy (đĩa hoặc cache), không tải. */
    public function localVideo(AutoVideo $v): ?string
    {
        $path = (string) $v->path;

        if ($path !== '' && is_file($path) && (int) filesize($path) > 0) {
            return $path;
        }

        return $this->readyCache($v);
    }

    /**
     * Đường dẫn file mp4 dùng được, tải về nếu cần.
     *
     * @throws MissingVideoFile file không còn/không khớp (không thử lại)
     * @throws RuntimeException hub tắt hoặc lỗi tạm (thử lại sau)
     */
    public function video(AutoVideo $v): string
    {
        $path = (string) $v->path;

        if ($path !== '' && is_file($path) && (int) filesize($path) > 0) {
            return $path;
        }

        return $this->cachedVideo($v);
    }

    /**
     * Chỉ bản trong hub-cache (tải nếu chưa có), không bao giờ trả đường dẫn $v->path: dùng cho route phục vụ file,
     * nơi đường dẫn trên đĩa phải qua kiểm tra riêng.
     *
     * @throws MissingVideoFile
     * @throws RuntimeException
     */
    public function cachedVideo(AutoVideo $v): string
    {
        $ready = $this->readyCache($v);

        if ($ready !== null) {
            return $ready;
        }

        $url = $this->videoUrl($v);
        $cache = $this->cachePath($v, 'mp4');

        if ($url === null || $cache === null) {
            throw new MissingVideoFile('Không tìm thấy file video trong hub hoặc file rỗng: '.$v->file_name);
        }

        $this->fetch($url, $cache, (string) $v->hash, data_get($v->meta, 'kich_thuoc'), (string) $v->file_name);

        return $cache;
    }

    private function readyCache(AutoVideo $v): ?string
    {
        $cache = $this->cachePath($v, 'mp4');

        return $cache !== null && is_file($cache) && $this->sizeMatches($cache, data_get($v->meta, 'kich_thuoc')) ? $cache : null;
    }

    /** Ảnh bìa: đường dẫn dùng được hoặc null (không có/không tải được; ảnh bìa không bắt buộc). */
    public function cover(AutoVideo $v): ?string
    {
        $url = data_get($v->meta, 'url_anh_bia');
        $cache = $this->cachePath($v, 'jpg');

        if (! is_string($url) || $url === '' || $cache === null) {
            return null;
        }

        if (is_file($cache) && (int) filesize($cache) > 0) {
            return $cache;
        }

        try {
            $this->fetch($url, $cache, null, null, 'ảnh bìa '.$v->file_name);
        } catch (RuntimeException) {
            return null;
        }

        return $cache;
    }

    public function hasCoverUrl(AutoVideo $v): bool
    {
        $url = data_get($v->meta, 'url_anh_bia');

        return is_string($url) && $url !== '';
    }

    /**
     * Xoá bản cache của video đã xong (đã đăng/lỗi/bỏ qua) quá hạn lưu giữ, và file tạm bỏ dở.
     * `$retention`: `vinh_vien` | `xoa_ngay` | số ngày.
     *
     * @return int số file đã xoá
     */
    public function cleanup(string $retention, ?CarbonImmutable $now = null): int
    {
        $dir = $this->cacheDir();

        if (! is_dir($dir)) {
            return 0;
        }

        $now ??= CarbonImmutable::now();
        $deleted = 0;
        $limit = in_array($retention, ['vinh_vien', 'xoa_ngay'], true) ? null : $now->subDays((int) $retention);

        foreach (scandir($dir) ?: [] as $name) {
            $file = $dir.'/'.$name;

            if (! is_file($file)) {
                continue;
            }

            if (str_ends_with($name, '.part')) {
                if ($now->getTimestamp() - (int) filemtime($file) > 86400 && @unlink($file)) {
                    $deleted++;
                }

                continue;
            }

            if ($retention === 'vinh_vien' || ! preg_match('/^(.+)\.(mp4|jpg)$/', $name, $m)) {
                continue;
            }

            $video = AutoVideo::query()->where('hub_id', $m[1])->first(['id', 'status', 'posted_at', 'updated_at']);

            if ($video === null) {
                if (@unlink($file)) {
                    $deleted++;
                }

                continue;
            }

            if (! in_array($video->status, [AutoVideo::POSTED, AutoVideo::FAILED, AutoVideo::SKIPPED], true)) {
                continue;
            }

            $since = $video->posted_at ?? $video->updated_at;

            if ($limit === null || ($since !== null && CarbonImmutable::instance($since)->lessThan($limit))) {
                if (@unlink($file)) {
                    $deleted++;
                }
            }
        }

        return $deleted;
    }

    /**
     * Xoá file video trong thư viện media của bài tự động ĐÃ ĐĂNG xong quá hạn lưu giữ. Mỗi bài tự động chép một file mp4
     * vào storage (khoảng 15 MB), còn lịch sử bài giữ tới 730 ngày nên ổ đĩa sẽ đầy dần. Bài chưa Published thì không đụng.
     * `$retention`: `vinh_vien` | `xoa_ngay` (chừa 1 ngày) | số ngày.
     *
     * @return int số dòng media đã xoá
     */
    public function cleanupPostedMedia(string $retention, ?CarbonImmutable $now = null): int
    {
        if ($retention === 'vinh_vien') {
            return 0;
        }

        $now ??= CarbonImmutable::now();
        $limit = $now->subDays($retention === 'xoa_ngay' ? 1 : max(1, (int) $retention));
        $deleted = 0;

        AutoVideo::query()
            ->where('status', AutoVideo::POSTED)
            ->whereNotNull('post_id')
            ->where('posted_at', '<', $limit)
            ->select(['id', 'post_id'])
            ->chunkById(200, function ($videos) use ($limit, &$deleted): void {
                $postIds = Post::query()
                    ->whereIn('id', $videos->pluck('post_id')->all())
                    ->where('status', PostStatus::Published)
                    ->where('published_at', '<', $limit)
                    ->whereIn('id', Media::query()->whereNotNull('post_id')->select('post_id'))
                    ->pluck('id')
                    ->all();

                if ($postIds === []) {
                    return;
                }

                $deleted += Media::query()->whereIn('post_id', $postIds)->count();
                Media::query()->whereIn('post_id', $postIds)->each(fn (Media $m) => $m->delete());
            }, 'id');

        return $deleted;
    }

    private function videoUrl(AutoVideo $v): ?string
    {
        $url = data_get($v->meta, 'url_file');

        return is_string($url) && $url !== '' ? $url : null;
    }

    /** Tên cache chỉ gồm [\w.-], không bao giờ thoát khỏi thư mục cache. */
    private function cachePath(AutoVideo $v, string $ext): ?string
    {
        $id = (string) $v->hub_id;

        if ($id === '' || preg_match('/^[\w.-]+$/', $id) !== 1 || str_contains($id, '..')) {
            return null;
        }

        return $this->cacheDir().'/'.$id.'.'.$ext;
    }

    private function sizeMatches(string $file, mixed $expected): bool
    {
        $size = (int) filesize($file);

        return $size > 0 && (! is_numeric($expected) || (int) $expected <= 0 || (int) $expected === $size);
    }

    /**
     * @throws MissingVideoFile
     * @throws RuntimeException
     */
    private function fetch(string $url, string $destination, ?string $sha256, mixed $size, string $label): void
    {
        File::ensureDirectoryExists(dirname($destination));
        $tmp = $destination.'.'.bin2hex(random_bytes(4)).'.part';

        try {
            $result = $this->api->download($url, $tmp);

            if ($result === HubApi::NOT_FOUND) {
                throw new MissingVideoFile('Hub không còn file: '.$label);
            }

            if ($result !== 'ok') {
                throw new RuntimeException('Không tải được file từ hub ('.$result.'): '.$label);
            }

            clearstatcache(true, $tmp);

            if (! is_file($tmp) || (int) filesize($tmp) <= 0) {
                throw new RuntimeException('File tải từ hub rỗng: '.$label);
            }

            if (is_numeric($size) && (int) $size > 0 && (int) filesize($tmp) !== (int) $size) {
                Log::warning('Hub API: file tải về sai kích thước.', ['file' => $label, 'got' => filesize($tmp), 'expected' => (int) $size]);

                throw new MissingVideoFile('File tải từ hub sai kích thước, bị từ chối: '.$label);
            }

            if ($sha256 !== null && preg_match('/^[0-9a-f]{64}$/i', $sha256) === 1
                && ! hash_equals(strtolower($sha256), (string) hash_file('sha256', $tmp))) {
                Log::warning('Hub API: file tải về sai sha256.', ['file' => $label]);

                throw new MissingVideoFile('File tải từ hub sai sha256, bị từ chối: '.$label);
            }

            if (! @rename($tmp, $destination)) {
                throw new RuntimeException('Không ghi được file cache: '.$label);
            }
        } finally {
            if (is_file($tmp)) {
                @unlink($tmp);
            }
        }
    }
}

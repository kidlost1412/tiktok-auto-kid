<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Media;

use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use Illuminate\Http\Client\Pool;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Throwable;

/**
 * Ảnh bìa sản phẩm TikTok Shop: tải một lần về storage/app/product-covers và phục vụ qua route nội bộ
 * (link CDN gốc hết hạn). Tên file chứa mã băm của cover_url nên đổi ảnh trên shop là tự tải lại.
 */
final class ProductImages
{
    public static function dir(): string
    {
        return storage_path('app/product-covers');
    }

    public static function version(ShopProduct $p): string
    {
        return substr(md5((string) $p->cover_url), 0, 8);
    }

    /** Đường dẫn tương đối trả cho giao diện, hoặc null nếu sản phẩm chưa có ảnh. */
    public static function url(?ShopProduct $p): ?string
    {
        return $p && filled($p->cover_url) ? route('fork.auto.product-image', ['shopProduct' => $p->id, 'v' => self::version($p)], false) : null;
    }

    /** Cạnh dài nhất (px) của ảnh lưu về máy: đủ nét cho khung 96px trên màn hình 2x, nhẹ để hiện tức thì. */
    public const int MAX_SIDE = 360;

    /** Đường dẫn file ảnh đã có trên máy, không tải; null nếu chưa có. */
    public function cached(ShopProduct $p): ?string
    {
        if (blank($p->cover_url)) {
            return null;
        }

        $base = self::dir().DIRECTORY_SEPARATOR.$p->id.'-'.self::version($p);

        foreach (['jpg', 'png', 'webp', 'gif'] as $ext) {
            if (is_file($base.'.'.$ext)) {
                return $base.'.'.$ext;
            }
        }

        return null;
    }

    /** Đường dẫn file ảnh trên máy (tải nếu chưa có); null khi chưa lấy được. */
    public function file(ShopProduct $p): ?string
    {
        if (blank($p->cover_url)) {
            return null;
        }

        if (($have = $this->cached($p)) !== null) {
            return $have;
        }

        $failKey = self::failKey($p);

        if (Cache::has($failKey)) {
            return null;
        }

        $img = RemoteImage::fetch(self::largeUrl($p));
        $img ??= self::largeUrl($p) !== (string) $p->cover_url ? RemoteImage::fetch((string) $p->cover_url) : null;

        return $this->store($p, $img);
    }

    /**
     * Tải sẵn ảnh của các sản phẩm chưa có ảnh trên máy, nhiều ảnh cùng lúc (chạy nền sau mỗi lần lấy sản phẩm
     * để lúc mở hộp chọn ảnh đã sẵn). Ảnh nào lỗi thì để route nội bộ thử lại khi cần.
     *
     * @param  iterable<ShopProduct>  $products
     * @return int số ảnh vừa lưu
     */
    public function prefetch(iterable $products, int $concurrency = 6): int
    {
        $todo = [];

        foreach ($products as $p) {
            if (filled($p->cover_url) && RemoteImage::allowed((string) $p->cover_url) && $this->cached($p) === null && ! Cache::has(self::failKey($p))) {
                $todo[] = $p;
            }
        }

        $saved = 0;

        foreach (array_chunk($todo, max(1, $concurrency)) as $batch) {
            try {
                $responses = Http::pool(fn (Pool $pool): array => array_map(
                    fn (ShopProduct $p) => $pool->as((string) $p->id)->timeout(15)->connectTimeout(5)->withoutRedirecting()
                        ->withHeaders(['User-Agent' => RemoteImage::USER_AGENT, 'Referer' => 'https://www.tiktok.com/'])
                        ->get(self::largeUrl($p)),
                    $batch,
                ));
            } catch (Throwable) {
                $responses = [];
            }

            foreach ($batch as $p) {
                $img = RemoteImage::fromResponse($responses[(string) $p->id] ?? null);

                // Bản lớn không được thì thử đúng link gốc (từng cái một, hiếm khi xảy ra).
                if ($img === null && self::largeUrl($p) !== (string) $p->cover_url) {
                    $img = RemoteImage::fetch((string) $p->cover_url);
                }

                if ($this->store($p, $img) !== null) {
                    $saved++;
                }
            }
        }

        return $saved;
    }

    /** Shop thường gửi bản thu nhỏ 48x48: xin bản lớn của cùng ảnh trước. */
    private static function largeUrl(ShopProduct $p): string
    {
        $url = (string) $p->cover_url;
        $big = preg_replace('/(resize-image:)\d+:\d+(\.image)/', '${1}400:400${2}', $url);

        return is_string($big) ? $big : $url;
    }

    private static function failKey(ShopProduct $p): string
    {
        return 'fork-product-image-fail:'.$p->id.':'.self::version($p);
    }

    /**
     * Ghi ảnh (đã thu nhỏ) vào thư mục ảnh; ảnh cũ của sản phẩm bị xoá. Không có ảnh thì nhớ lỗi 10 phút.
     *
     * @param  array{body: string, ext: string}|null  $img
     */
    private function store(ShopProduct $p, ?array $img): ?string
    {
        if ($img === null) {
            Cache::put(self::failKey($p), 1, 600);

            return null;
        }

        $img = self::shrink($img);

        if (! is_dir(self::dir())) {
            @mkdir(self::dir(), 0775, true);
        }

        foreach (glob(self::dir().DIRECTORY_SEPARATOR.$p->id.'-*') ?: [] as $stale) {
            @unlink($stale);
        }

        $path = self::dir().DIRECTORY_SEPARATOR.$p->id.'-'.self::version($p).'.'.$img['ext'];
        file_put_contents($path, $img['body']);

        return $path;
    }

    /**
     * Ảnh gốc của shop hay nặng cả MB; thu về tối đa MAX_SIDE px dạng JPEG (nền trắng) để hiện tức thì.
     * Không có GD hoặc ảnh động (gif) thì giữ nguyên.
     *
     * @param  array{body: string, ext: string}  $img
     * @return array{body: string, ext: string}
     */
    public static function shrink(array $img): array
    {
        if ($img['ext'] === 'gif' || ! function_exists('imagecreatefromstring') || ! function_exists('imagejpeg')) {
            return $img;
        }

        $src = @imagecreatefromstring($img['body']);

        if ($src === false) {
            return $img;
        }

        $w = imagesx($src);
        $h = imagesy($src);
        $scale = min(1, self::MAX_SIDE / max(1, $w, $h));
        $nw = max(1, (int) round($w * $scale));
        $nh = max(1, (int) round($h * $scale));

        $dst = imagecreatetruecolor($nw, $nh);
        imagefill($dst, 0, 0, (int) imagecolorallocate($dst, 255, 255, 255));
        imagecopyresampled($dst, $src, 0, 0, 0, 0, $nw, $nh, $w, $h);

        ob_start();
        imagejpeg($dst, null, 82);
        $jpg = (string) ob_get_clean();

        return $jpg !== '' && strlen($jpg) < strlen($img['body']) ? ['body' => $jpg, 'ext' => 'jpg'] : $img;
    }

    /**
     * Tra ảnh theo (kênh, mã hub, quy cách) và theo mã hub, nạp một lần cho cả trang.
     *
     * @param  list<string>|null  $accountIds  null = mọi kênh
     */
    public static function lookup(?array $accountIds = null): ProductImageLookup
    {
        $links = ProductLink::query()
            ->when($accountIds !== null, fn ($q) => $q->whereIn('social_account_id', $accountIds))
            ->get(['social_account_id', 'auto_product_id', 'quy_cach', 'shop_product_id']);

        $shop = ShopProduct::query()
            ->whereIn('product_id', $links->pluck('shop_product_id')->filter()->unique()->all())
            ->whereNotNull('cover_url')
            ->get()
            ->keyBy(fn (ShopProduct $p): string => $p->social_account_id.'|'.$p->product_id);

        return new ProductImageLookup($links, $shop);
    }
}

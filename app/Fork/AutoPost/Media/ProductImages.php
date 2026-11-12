<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Media;

use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use Illuminate\Support\Facades\Cache;

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

    /** Đường dẫn file ảnh trên máy (tải nếu chưa có); null khi chưa lấy được. */
    public function file(ShopProduct $p): ?string
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

        $failKey = 'fork-product-image-fail:'.$p->id.':'.self::version($p);

        if (Cache::has($failKey)) {
            return null;
        }

        // Shop thường gửi bản thu nhỏ 48x48: thử xin bản lớn của cùng ảnh trước, không được thì dùng link gốc.
        $img = null;
        $big = preg_replace('/(resize-image:)\d+:\d+(\.image)/', '${1}400:400${2}', (string) $p->cover_url);

        if (is_string($big) && $big !== $p->cover_url) {
            $img = RemoteImage::fetch($big);
        }

        $img ??= RemoteImage::fetch((string) $p->cover_url);

        if ($img === null) {
            Cache::put($failKey, 1, 600);

            return null;
        }

        if (! is_dir(self::dir())) {
            @mkdir(self::dir(), 0775, true);
        }

        foreach (glob(self::dir().DIRECTORY_SEPARATOR.$p->id.'-*') ?: [] as $stale) {
            @unlink($stale);
        }

        file_put_contents($base.'.'.$img['ext'], $img['body']);

        return $base.'.'.$img['ext'];
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

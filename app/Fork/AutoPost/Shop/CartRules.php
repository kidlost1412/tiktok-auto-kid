<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Shop;

use App\Fork\AutoPost\Models\AnchorTemplate;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;

/**
 * Luật giỏ hàng: nguyên tắc "gắn sai sản phẩm tệ hơn không gắn". Cặp (mã hub, quy cách) chỉ được đăng trên một kênh khi
 * chủ app đã chọn sản phẩm, liên kết không bị tạm dừng,
 * và sản phẩm còn trong shop với tồn kho > 0. Còn lại thì giữ video trong kho và báo cảnh báo.
 */
final class CartRules
{
    public const int NAME_MAX = 30;

    /** Lý do tiện ích báo khi job có sản phẩm thất bại (chắc chắn chưa đăng). */
    public const array FAIL_REASONS = ['product-unavailable', 'anchor-build-failed'];

    /** Tiện ích không đọc được API shop (mạng/HTTP/code khác 0), chưa gửi gì: thử lại sau, KHÔNG tạm dừng liên kết. */
    public const string RETRY_REASON = 'product-check-failed';

    public function hasTemplate(string $socialAccountId): bool
    {
        return AnchorTemplate::query()->where('social_account_id', $socialAccountId)->exists();
    }

    /**
     * Các cặp (mã hub, quy cách) được phép đăng trên kênh. Quy cách null nghĩa là sản phẩm chỉ có một quy cách.
     *
     * @return array<string, list<?string>>
     */
    public function eligible(string $socialAccountId): array
    {
        return $this->evaluate($socialAccountId)['allowed'];
    }

    /**
     * @return array{allowed: array<string, list<?string>>, warnings: list<string>}
     */
    public function evaluate(string $socialAccountId): array
    {
        $links = ProductLink::query()->where('social_account_id', $socialAccountId)->orderBy('auto_product_id')->orderBy('quy_cach')->get();
        $hub = AutoProduct::query()->get()->keyBy('code');

        $products = $links->isEmpty() ? collect() : ShopProduct::query()
            ->where('social_account_id', $socialAccountId)
            ->whereIn('product_id', $links->pluck('shop_product_id'))
            ->get()
            ->keyBy('product_id');

        $allowed = [];
        $warnings = [];
        $linked = [];

        foreach ($links as $link) {
            $code = (string) $link->auto_product_id;
            $qc = filled($link->quy_cach) ? (string) $link->quy_cach : null;
            $label = self::label($hub[$code] ?? null, $code, $qc);
            $linked[$code.'|'.($qc ?? '')] = true;

            $hubProduct = $hub[$code] ?? null;

            if ($hubProduct === null) {
                $warnings[] = "{$label}: sản phẩm này không còn trong hub";

                continue;
            }

            if (! in_array($qc, self::quyCachCodes($hubProduct), true)) {
                $warnings[] = "{$label}: quy cách này không còn trong hub, hãy chọn lại";

                continue;
            }

            if (filled($link->paused_reason)) {
                $warnings[] = "{$label} đang tạm dừng: {$link->paused_reason}";

                continue;
            }

            $shop = $products[$link->shop_product_id] ?? null;
            $problem = $this->problem($shop) ?? ($shop->hidden ? 'sản phẩm đang bị ẩn, hãy hiện lại hoặc chọn sản phẩm khác' : null);

            if ($problem !== null) {
                $warnings[] = "{$label}: {$problem}";

                continue;
            }

            $allowed[$code][] = $qc;
        }

        // Quy cách còn video trong kho mà chưa chọn sản phẩm: video giữ lại trong kho.
        $waiting = AutoVideo::query()
            ->notRieng()->where('status', AutoVideo::NEW)
            ->whereNotNull('product_code')
            ->select('product_code', 'quy_cach')
            ->distinct()
            ->get();

        foreach ($waiting as $row) {
            $code = (string) $row->product_code;
            $qc = filled($row->quy_cach) ? (string) $row->quy_cach : null;
            $hubProduct = $hub[$code] ?? null;

            if ($hubProduct === null || ! $hubProduct->enabled || isset($linked[$code.'|'.($qc ?? '')])) {
                continue;
            }

            $warnings[] = self::label($hubProduct, $code, $qc).' chưa chọn sản phẩm: video giữ trong kho';
        }

        return ['allowed' => $allowed, 'warnings' => $warnings];
    }

    /**
     * Danh sách quy cách của sản phẩm hub: [{ma, ten}]. Rỗng = chỉ một quy cách.
     *
     * @return list<array{ma: string, ten: string}>
     */
    public static function quyCachList(AutoProduct $product): array
    {
        $raw = $product->getAttribute('quy_cach');
        $raw = is_string($raw) ? json_decode($raw, true) : $raw;
        $out = [];

        foreach (is_array($raw) ? $raw : [] as $item) {
            $ma = is_array($item) ? ($item['ma'] ?? null) : null;

            if (is_string($ma) && $ma !== '') {
                $out[$ma] = ['ma' => $ma, 'ten' => is_string($item['ten'] ?? null) && $item['ten'] !== '' ? $item['ten'] : $ma];
            }
        }

        return array_values($out);
    }

    /**
     * Các quy cách hợp lệ của sản phẩm: [null] nếu sản phẩm không khai báo quy cách.
     *
     * @return list<?string>
     */
    public static function quyCachCodes(AutoProduct $product): array
    {
        $list = self::quyCachList($product);

        return $list === [] ? [null] : array_column($list, 'ma');
    }

    /** "Đạm cá – Chai 1L" (hoặc chỉ tên sản phẩm khi không có quy cách). */
    public static function label(?AutoProduct $product, string $code, ?string $quyCach): string
    {
        $name = (string) ($product?->short_name ?: $code);

        if ($quyCach === null) {
            return $name;
        }

        $ten = collect($product ? self::quyCachList($product) : [])->firstWhere('ma', $quyCach)['ten'] ?? $quyCach;

        return $name.' – '.$ten;
    }

    /** Tên hiện trên video gợi ý từ tên sản phẩm shop: bỏ các cụm [..], in hoa, tối đa 30 ký tự. */
    public static function suggestName(string $title): string
    {
        $clean = trim((string) preg_replace('/\s+/u', ' ', (string) preg_replace('/\[[^\]]*\]/u', '', $title)));

        return self::limitName(mb_strtoupper($clean !== '' ? $clean : $title));
    }

    /** Vì sao sản phẩm shop không dùng được (null = dùng được). */
    public function problem(?ShopProduct $product): ?string
    {
        return match (true) {
            $product === null => 'không tìm thấy sản phẩm đã chọn trong danh sách shop, hãy lấy lại sản phẩm từ shop',
            $product->missing => 'sản phẩm đã không còn trong shop',
            $product->stock_num <= 0 => 'sản phẩm đã hết hàng',
            default => null,
        };
    }

    /** Tên hiện trên video: tối đa 30 ký tự. */
    public static function limitName(string $name): string
    {
        return mb_substr(trim($name), 0, self::NAME_MAX);
    }
}

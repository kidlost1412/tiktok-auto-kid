<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Media;

use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use Illuminate\Support\Collection;

/** Kết quả nạp sẵn của ProductImages::lookup(): trả URL ảnh cho video / mã sản phẩm mà không truy vấn thêm. */
final class ProductImageLookup
{
    /**
     * @param  Collection<int, ProductLink>  $links
     * @param  Collection<string, ShopProduct>  $shop
     */
    public function __construct(private readonly Collection $links, private readonly Collection $shop) {}

    /** Ảnh theo đúng khe (kênh, mã, quy cách); không có thì lấy khe cùng mã (cùng kênh rồi tới kênh khác). */
    public function forSlot(?string $accountId, ?string $code, ?string $quyCach): ?string
    {
        if (blank($code)) {
            return null;
        }

        $ofCode = $this->links->where('auto_product_id', $code);
        $candidates = collect();

        if ($accountId !== null) {
            $mine = $ofCode->where('social_account_id', $accountId);
            $candidates = $candidates
                ->concat($mine->filter(fn (ProductLink $l): bool => ($l->quy_cach ?: null) === ($quyCach ?: null)))
                ->concat($mine);
        }

        foreach ($candidates->concat($ofCode) as $l) {
            $p = $this->shop[$l->social_account_id.'|'.$l->shop_product_id] ?? null;

            if ($p !== null) {
                return ProductImages::url($p);
            }
        }

        return null;
    }

    public function forCode(?string $code): ?string
    {
        return $this->forSlot(null, $code, null);
    }

    /** @return array<string, string> mã hub => URL ảnh, chỉ các mã có ảnh */
    public function byCode(): array
    {
        $out = [];

        foreach ($this->links->pluck('auto_product_id')->unique() as $code) {
            $url = $this->forCode((string) $code);

            if ($url !== null) {
                $out[(string) $code] = $url;
            }
        }

        return $out;
    }
}

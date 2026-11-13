<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Jobs;

use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Models\ShopProduct;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;

/**
 * Tải sẵn ảnh bìa các sản phẩm TikTok Shop của một kênh ngay sau khi tiện ích lấy sản phẩm về,
 * để hộp "Chọn giỏ hàng" mở ra là có ảnh (không phải đợi từng ảnh tải lúc mở).
 */
final class PrefetchProductCovers implements ShouldQueue
{
    use Queueable;

    public int $tries = 1;

    public int $timeout = 240;

    public function __construct(public readonly string $socialAccountId) {}

    public function handle(ProductImages $images): void
    {
        $images->prefetch(
            ShopProduct::query()->where('social_account_id', $this->socialAccountId)->where('missing', false)->whereNotNull('cover_url')->get(),
        );
    }
}

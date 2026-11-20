<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Ảnh bìa riêng của một sản phẩm hub trên MỘT kênh (giỏ của kênh đó). Kênh khác cùng sản phẩm có bộ ảnh riêng.
 *
 * @property string $social_account_id
 * @property string $auto_product_id
 */
class ProductCover extends Model
{
    protected $table = 'fork_product_covers';

    protected $guarded = [];

    protected function casts(): array
    {
        return ['cover_images' => 'array'];
    }

    /** Bộ ảnh của (kênh, mã hub); chưa có thì trả bản mới chưa lưu (chế độ mặc định, không ảnh). */
    public static function for(string $socialAccountId, string $code): self
    {
        return static::query()->firstOrNew(
            ['social_account_id' => $socialAccountId, 'auto_product_id' => $code],
            ['cover_mode' => 'default'],
        );
    }

    /** Mã sản phẩm hub (thư mục ảnh covers/<mã>). */
    public function getCodeAttribute(): string
    {
        return (string) $this->auto_product_id;
    }
}

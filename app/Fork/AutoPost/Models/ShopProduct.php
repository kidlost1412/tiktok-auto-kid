<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use App\Models\SocialAccount;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/** Sản phẩm trong TikTok Shop của một kênh, do tiện ích đồng bộ về. product_id luôn là chuỗi. */
class ShopProduct extends Model
{
    protected $table = 'fork_shop_products';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'product_id' => 'string',
            'stock_num' => 'integer',
            'hidden' => 'boolean',
            'missing' => 'boolean',
            'synced_at' => 'datetime',
        ];
    }

    public function socialAccount(): BelongsTo
    {
        return $this->belongsTo(SocialAccount::class, 'social_account_id');
    }
}

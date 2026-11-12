<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use App\Models\SocialAccount;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/** Chủ app chọn: mã hub nào gắn sản phẩm TikTok Shop nào trên kênh nào. */
class ProductLink extends Model
{
    protected $table = 'fork_product_links';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'auto_product_id' => 'string',
            'shop_product_id' => 'string',
        ];
    }

    /** Liên kết của đúng (kênh, mã hub, quy cách); quy cách null chỉ khớp liên kết không quy cách. */
    public static function slot(string $socialAccountId, string $code, ?string $quyCach): Builder
    {
        return static::query()
            ->where('social_account_id', $socialAccountId)
            ->where('auto_product_id', $code)
            ->when($quyCach === null || $quyCach === '', fn (Builder $q) => $q->whereNull('quy_cach'), fn (Builder $q) => $q->where('quy_cach', $quyCach));
    }

    public function socialAccount(): BelongsTo
    {
        return $this->belongsTo(SocialAccount::class, 'social_account_id');
    }
}

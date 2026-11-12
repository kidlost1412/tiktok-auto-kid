<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use App\Models\SocialAccount;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/** Mẫu anchors (giỏ hàng) tiện ích bắt được khi chủ app tự đăng tay một bài có gắn sản phẩm. Mỗi kênh một mẫu. */
class AnchorTemplate extends Model
{
    protected $table = 'fork_anchor_templates';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'product_id' => 'string',
            'captured_at' => 'datetime',
        ];
    }

    public function socialAccount(): BelongsTo
    {
        return $this->belongsTo(SocialAccount::class, 'social_account_id');
    }
}

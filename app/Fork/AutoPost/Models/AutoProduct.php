<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class AutoProduct extends Model
{
    protected $table = 'fork_auto_products';

    protected $primaryKey = 'code';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'facts' => 'array',
            'quy_cach' => 'array',
            'enabled' => 'boolean',
            'cover_images' => 'array',
            'hashtags' => 'array',
            'hashtag_pick' => 'integer',
        ];
    }

    public function videos(): HasMany
    {
        return $this->hasMany(AutoVideo::class, 'product_code', 'code');
    }
}

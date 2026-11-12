<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use App\Models\SocialAccount;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class AutoAccount extends Model
{
    public const EXPLORE = 'explore';

    public const OPTIMIZED = 'optimized';

    protected $table = 'fork_auto_accounts';

    protected $primaryKey = 'social_account_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'enabled' => 'boolean',
            'daily_cap' => 'integer',
            'schedule_ahead_days' => 'integer',
            'window_start' => 'integer',
            'window_end' => 'integer',
            'preferred_hours' => 'array',
            'explore_ratio' => 'float',
            'products_synced_at' => 'datetime',
            'products_sync_requested_at' => 'datetime',
        ];
    }

    public function socialAccount(): BelongsTo
    {
        return $this->belongsTo(SocialAccount::class, 'social_account_id');
    }

    public function timezone(): string
    {
        return $this->socialAccount?->timezone ?: 'Asia/Ho_Chi_Minh';
    }
}

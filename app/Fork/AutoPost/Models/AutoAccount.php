<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use App\Fork\AutoPost\Scheduling\Planner;
use App\Models\SocialAccount;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class AutoAccount extends Model
{
    public const EXPLORE = 'explore';

    public const OPTIMIZED = 'optimized';

    /** Nguồn video của kênh (cột video_source). */
    public const SOURCE_BOTH = 'both';

    public const SOURCE_RIENG = 'rieng';

    public const SOURCE_HUB = 'hub';

    public const SOURCES = [self::SOURCE_BOTH, self::SOURCE_RIENG, self::SOURCE_HUB];

    public function videoSource(): string
    {
        return in_array($this->video_source, self::SOURCES, true) ? (string) $this->video_source : self::SOURCE_BOTH;
    }

    /** Kênh nhận video Xưởng (tự tạo). */
    public function usesHub(): bool
    {
        return $this->videoSource() !== self::SOURCE_RIENG;
    }

    /** Kênh nhận video Kho riêng tự đăng theo khung. */
    public function usesRieng(): bool
    {
        return $this->videoSource() !== self::SOURCE_HUB;
    }

    protected $table = 'fork_auto_accounts';

    protected $primaryKey = 'social_account_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'enabled' => 'boolean',
            'mix_products' => 'boolean',
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
        return Planner::zone()->getName();
    }
}

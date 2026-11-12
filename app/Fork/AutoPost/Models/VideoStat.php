<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/** Số liệu mới nhất của một video trên TikTok (theo item_id), do tiện ích TikTok Auto Kid đọc từ TikTok Studio. */
class VideoStat extends Model
{
    protected $table = 'fork_video_stats';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'traffic' => 'array',
            'posted_at' => 'datetime',
            'insight_at' => 'datetime',
            'collected_at' => 'datetime',
            'avg_watch_s' => 'float',
            'finish_rate' => 'float',
            'total_watch_s' => 'float',
        ];
    }

    public function autoVideo(): BelongsTo
    {
        return $this->belongsTo(AutoVideo::class);
    }
}

<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/** Bình luận trên video của kênh (bảng fork_comments). `commented_at` là giờ bình luận trên TikTok, created_at là lúc app nhận. */
class VideoComment extends Model
{
    protected $table = 'fork_comments';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'is_buy_intent' => 'boolean',
            'commented_at' => 'datetime',
            'notified_at' => 'datetime',
        ];
    }

    public function autoVideo(): BelongsTo
    {
        return $this->belongsTo(AutoVideo::class);
    }
}

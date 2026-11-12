<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use Illuminate\Database\Eloquent\Model;

/** Một lần chụp số liệu của video (để tính mốc 24h / 72h). */
class VideoSnapshot extends Model
{
    protected $table = 'fork_video_snapshots';

    public $timestamps = false;

    protected $guarded = [];

    protected function casts(): array
    {
        return ['taken_at' => 'datetime'];
    }
}

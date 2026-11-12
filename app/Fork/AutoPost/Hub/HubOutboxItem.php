<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Hub;

use Illuminate\Database\Eloquent\Model;

/** Một lời báo ngược về hub đang chờ gửi (da-dang, loi, so-lieu). */
class HubOutboxItem extends Model
{
    protected $table = 'fork_hub_outbox';

    protected $guarded = [];

    protected function casts(): array
    {
        return ['payload' => 'array', 'next_attempt_at' => 'datetime'];
    }
}

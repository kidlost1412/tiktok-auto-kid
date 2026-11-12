<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use Illuminate\Database\Eloquent\Model;

/** Số người theo dõi của kênh trong một ngày. */
class AccountStat extends Model
{
    protected $table = 'fork_account_stats';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'date' => 'date',
            'history' => 'array',
            'collected_at' => 'datetime',
        ];
    }
}

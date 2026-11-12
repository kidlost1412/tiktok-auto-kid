<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Models;

use App\Models\Account;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ChromeClient extends Model
{
    protected $table = 'fork_chrome_clients';

    protected $guarded = [];

    protected $hidden = ['token_hash'];

    protected function casts(): array
    {
        return [
            'protocol' => 'integer',
            'last_seen_at' => 'datetime',
            'last_launch_at' => 'datetime',
            'revoked_at' => 'datetime',
        ];
    }

    public function account(): BelongsTo
    {
        return $this->belongsTo(Account::class);
    }
}

<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Models;

use App\Models\SocialAccount;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ChromeAccount extends Model
{
    protected $table = 'fork_chrome_accounts';

    protected $primaryKey = 'social_account_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'enabled' => 'boolean',
            'chrome_only' => 'boolean',
        ];
    }

    public function socialAccount(): BelongsTo
    {
        return $this->belongsTo(SocialAccount::class, 'social_account_id');
    }
}

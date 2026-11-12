<?php

declare(strict_types=1);

namespace App\Models;

use Database\Factories\UserFactory;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Foundation\Auth\User as Authenticatable;

class User extends Authenticatable
{
    /** @use HasFactory<UserFactory> */
    use HasFactory, HasUuids;

    /**
     * @var list<string>
     */
    protected $fillable = [
        'name',
        'email',
        'password',
        'account_id',
        'current_workspace_id',
        'email_verified_at',
        'locale',
        'timezone',
    ];

    /**
     * @var list<string>
     */
    protected $hidden = [
        'password',
        'remember_token',
    ];

    protected function casts(): array
    {
        return [
            'email_verified_at' => 'datetime',
            'password' => 'hashed',
        ];
    }

    public function account(): BelongsTo
    {
        return $this->belongsTo(Account::class);
    }

    public function isAccountOwner(): bool
    {
        if (! $this->account_id) {
            return false;
        }

        if ($this->relationLoaded('account')) {
            return $this->id === $this->account?->owner_id;
        }

        return Account::query()
            ->whereKey($this->account_id)
            ->where('owner_id', $this->id)
            ->exists();
    }

    public function workspaces(): BelongsToMany
    {
        return $this->belongsToMany(Workspace::class, 'user_workspace')->withTimestamps();
    }

    public function currentWorkspace(): BelongsTo
    {
        return $this->belongsTo(Workspace::class, 'current_workspace_id');
    }

    /** Workspace của tài khoản hiện tại mà user thuộc về. */
    public function accountWorkspaces(): BelongsToMany
    {
        return $this->workspaces()->where('workspaces.account_id', $this->account_id);
    }
}

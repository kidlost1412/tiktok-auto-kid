<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Models;

use App\Models\Post;
use App\Models\SocialAccount;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ChromeJob extends Model
{
    /** Các trạng thái còn mở: Chrome có thể đang nhận hoặc đang đăng. */
    public const array OPEN = ['queued', 'claimed', 'uploading', 'ready', 'authorized'];

    /** Còn trước bước cấp quyền: vẫn thu hồi được và chắc chắn chưa đăng. */
    public const array PRE_AUTH = ['queued', 'claimed', 'uploading', 'ready'];

    /** Đang chạy trên Chrome nhưng chưa được cấp quyền. */
    public const array RUNNING = ['claimed', 'uploading', 'ready'];

    public const array TERMINAL = ['posted', 'rejected', 'uncertain', 'revoked', 'failed'];

    protected $table = 'fork_chrome_jobs';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $guarded = [];

    protected $hidden = ['nonce', 'claim_token'];

    protected function casts(): array
    {
        return [
            'attempt' => 'integer',
            'video_size' => 'integer',
            'options' => 'array',
            'result' => 'array',
            'cancel_requested' => 'boolean',
            'duplicate_results' => 'integer',
            'claimed_at' => 'datetime',
            'heartbeat_at' => 'datetime',
            'authorized_at' => 'datetime',
            'result_at' => 'datetime',
            'launched_at' => 'datetime',
            'deliver_by' => 'datetime',
        ];
    }

    public function post(): BelongsTo
    {
        return $this->belongsTo(Post::class);
    }

    public function socialAccount(): BelongsTo
    {
        return $this->belongsTo(SocialAccount::class);
    }

    public function isOpen(): bool
    {
        return in_array($this->state, self::OPEN, true);
    }
}

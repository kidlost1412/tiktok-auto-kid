<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use App\Models\Post;
use App\Models\SocialAccount;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class AutoVideo extends Model
{
    public const NEW = 'new';

    public const SKIPPED = 'skipped';

    public const RESERVED = 'reserved';

    public const SCHEDULED = 'scheduled';

    public const POSTED = 'posted';

    public const FAILED = 'failed';

    protected $table = 'fork_auto_videos';

    protected $guarded = [];

    protected function casts(): array
    {
        return [
            'batch_date' => 'date',
            'duration' => 'float',
            'hashtags' => 'array',
            'stats' => 'array',
            'meta' => 'array',
            'files_deleted_at' => 'datetime',
            'scheduled_for' => 'datetime',
            'posted_at' => 'datetime',
            'stats_written_at' => 'datetime',
        ];
    }

    /**
     * Bài đã thật sự lên TikTok: trạng thái posted và giờ đăng không ở tương lai.
     * (Video đã hẹn giờ sẵn có status posted nhưng posted_at là giờ hẹn, chưa tới.)
     *
     * @param  Builder<static>  $q
     */
    public function scopeLivePosted(Builder $q): Builder
    {
        return $q->where('status', self::POSTED)->where(fn ($w) => $w->whereNull('posted_at')->orWhere('posted_at', '<=', now()));
    }

    /**
     * Bài posted nhưng giờ đăng còn ở tương lai: thực chất là "đã hẹn trên TikTok".
     *
     * @param  Builder<static>  $q
     */
    public function scopeHeldOnTikTok(Builder $q): Builder
    {
        return $q->where('status', self::POSTED)->where('posted_at', '>', now());
    }

    /** Biểu thức SQL cho trạng thái hiển thị (posted có giờ đăng ở tương lai => scheduled), để gom nhóm. */
    public static function effectiveStatusSql(): string
    {
        return "CASE WHEN status = 'posted' AND posted_at > '".now()->format('Y-m-d H:i:s')."' THEN 'scheduled' ELSE status END";
    }

    /** Trạng thái hiển thị: posted có giờ đăng ở tương lai được coi là scheduled. */
    public function effectiveStatus(): string
    {
        return $this->status === self::POSTED && $this->posted_at?->isFuture() ? self::SCHEDULED : (string) $this->status;
    }

    public function product(): BelongsTo
    {
        return $this->belongsTo(AutoProduct::class, 'product_code', 'code');
    }

    public function socialAccount(): BelongsTo
    {
        return $this->belongsTo(SocialAccount::class, 'social_account_id');
    }

    public function post(): BelongsTo
    {
        return $this->belongsTo(Post::class, 'post_id');
    }
}

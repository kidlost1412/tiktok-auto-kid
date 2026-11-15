<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Một yêu cầu "Đổi giờ" cho bài đã hẹn sẵn trên TikTok (xem App\Fork\AutoPost\Scheduling\Reschedules).
 *
 * pending  -> chờ Chrome nhận việc xoá bài hẹn cũ
 * claimed  -> Chrome đang xoá + kiểm lại
 * done     -> đã xác minh xoá, giờ mới đã đặt (bài sẽ được tải lên lại)
 * failed   -> không xoá được / không xác minh được; KHÔNG đổi gì, lịch cũ trên TikTok vẫn giữ
 * expired  -> Chrome không nhận việc kịp; không đổi gì
 * unknown  -> Chrome nhận việc nhưng không báo kết quả; chủ app cần kiểm TikTok Studio (kết quả muộn vẫn được nhận)
 */
class Reschedule extends Model
{
    public const array OPEN = ['pending', 'claimed'];

    protected $table = 'fork_reschedules';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $guarded = [];

    protected $hidden = ['nonce'];

    protected function casts(): array
    {
        return [
            'auto_video_id' => 'integer',
            'schedule_unix' => 'integer',
            'claim_client_id' => 'integer',
            'old_at' => 'datetime',
            'new_at' => 'datetime',
            'claimed_at' => 'datetime',
            'finished_at' => 'datetime',
            'result' => 'array',
        ];
    }

    public function isOpen(): bool
    {
        return in_array($this->state, self::OPEN, true);
    }
}

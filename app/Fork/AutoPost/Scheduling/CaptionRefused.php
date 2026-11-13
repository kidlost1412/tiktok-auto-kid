<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use RuntimeException;

/**
 * Caption của chính video này không đăng được (rỗng / quá 2200 ký tự TikTok). Lỗi cố định của video, thử lại cũng vậy:
 * bộ xếp lịch đánh dấu video lỗi và xếp tiếp video khác, không dừng cả kênh.
 */
final class CaptionRefused extends RuntimeException {}

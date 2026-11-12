<?php

declare(strict_types=1);

namespace App\Fork\AutoPost;

use App\Fork\AutoPost\Models\AutoVideo;
use RuntimeException;

/**
 * Caption và hashtag của một video: lấy nguyên văn chữ hub đã viết (đã lưu vào AutoVideo lúc ingest).
 * Không gọi AI, không gọi mạng, không sửa chữ ngoài việc cắt khoảng trắng đầu cuối.
 */
final class CaptionService
{
    /** @return array{caption: string, hashtags: list<string>, product_name: ?string, source: 'hub'} */
    public function captionFor(AutoVideo $v): array
    {
        $caption = trim((string) $v->caption);

        if ($caption === '') {
            throw new RuntimeException(HubText::REASON_MISSING);
        }

        $hashtags = HubText::tags((array) $v->hashtags);

        if (mb_strlen(HubText::compose($caption, $hashtags)) > HubText::MAX_CHARS) {
            throw new RuntimeException('Caption từ hub dài quá '.HubText::MAX_CHARS.' ký tự.');
        }

        return [
            'caption' => $caption,
            'hashtags' => $hashtags,
            'product_name' => HubText::cartName($v->product_name),
            'source' => HubText::SOURCE,
        ];
    }
}

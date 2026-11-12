<?php

declare(strict_types=1);

namespace App\Services\Social;

use App\Models\Post;

/** Đưa nội dung bài về văn bản thuần như TikTok nhận. */
class ContentSanitizer
{
    private const TAG_BODY = '/?[a-z][^<>]*>';

    private const TYPED_BRACKET_PATTERN = '~<(?!'.self::TAG_BODY.')~i';

    /**
     * Nội dung của bài khi gửi đi, hoặc null nếu bài không có chữ.
     */
    public function forPost(Post $post): ?string
    {
        return filled($post->content) ? $this->plainText($post->content) : null;
    }

    public function plainText(string $content): string
    {
        return $this->stripHtml($this->escapeTypedBrackets($content));
    }

    /** Dấu `<` không mở thẻ HTML là chữ thường, giữ lại. */
    private function escapeTypedBrackets(string $content): string
    {
        return preg_replace(self::TYPED_BRACKET_PATTERN, '&lt;', $content) ?? $content;
    }

    private function stripHtml(string $content): string
    {
        $content = $this->blocksToLines($content);
        $content = strip_tags($content);
        $content = html_entity_decode($content, ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $content = preg_replace("/\n{3,}/", "\n\n", $content);

        return trim($content);
    }

    /** Thẻ khối của bài soạn cũ thành xuống dòng: đoạn, tiêu đề, trích dẫn kết thúc một dòng, mục danh sách bắt đầu bằng dấu gạch. */
    private function blocksToLines(string $content): string
    {
        return (string) preg_replace(
            ['~<p\b[^>]*>~i', '~<li\b[^>]*>~i', '~<br\s*/?>|</(?:p|li|div|h[1-6]|blockquote)>~i'],
            ['', '- ', "\n"],
            $content,
        );
    }
}

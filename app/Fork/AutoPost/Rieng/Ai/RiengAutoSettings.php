<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use App\Fork\AutoPost\Models\AutoSetting;

/**
 * Cài đặt "Kho riêng tự đăng theo khung" (một JSON trong fork_auto_settings).
 *
 * - enabled: bật thì video riêng đủ điều kiện được Planner xếp vào giờ trống (trước video Xưởng).
 * - caption_mode: ai = ChatGPT viết caption từ nội dung video; kid = chủ app tự viết.
 * - empty_caption_ok: video chưa có caption vẫn đăng (TikTok cho bài không chữ).
 * - approve_first: caption AI phải được chủ app bấm "Duyệt" mới đăng.
 * - duplicates: ask = video trùng phải bấm "Vẫn đăng"; allow = cứ đăng (thẻ vẫn cảnh báo).
 * - model / effort: model ChatGPT (Codex CLI) và mức nghĩ.
 * - folder_channels: kênh được đăng cho từng thư mục (id thư mục => list social_account_id); trống = mọi kênh có giỏ.
 */
final class RiengAutoSettings
{
    public const string KEY = 'rieng.auto';

    public const array MODELS = [
        'gpt-6.1-terra' => 'GPT-6.1 Terra',
        'gpt-6.1-sol' => 'GPT-6.1 Sol',
    ];

    public const array EFFORTS = [
        'low' => 'Nghĩ nhanh',
        'medium' => 'Vừa',
        'high' => 'Nghĩ kỹ',
    ];

    public const array DEFAULTS = [
        'enabled' => false,
        'caption_mode' => 'ai',
        'empty_caption_ok' => true,
        'approve_first' => false,
        'duplicates' => 'ask',
        'model' => 'gpt-6.1-terra',
        'effort' => 'low',
        'folder_channels' => [],
    ];

    /** @return array{enabled: bool, caption_mode: string, empty_caption_ok: bool, approve_first: bool, duplicates: string, model: string, effort: string, folder_channels: array<string, list<string>>} */
    public static function get(): array
    {
        $raw = json_decode((string) AutoSetting::read(self::KEY, '{}'), true);

        return self::clean(is_array($raw) ? $raw : []);
    }

    /**
     * Gộp thay đổi vào cài đặt hiện có rồi lưu.
     *
     * @param  array<string, mixed>  $changes
     * @return array<string, mixed>
     */
    public static function update(array $changes): array
    {
        $next = self::clean(array_merge(self::get(), array_intersect_key($changes, self::DEFAULTS)));
        AutoSetting::write(self::KEY, (string) json_encode($next, JSON_UNESCAPED_UNICODE));

        return $next;
    }

    /** Kênh chủ app chọn cho một thư mục; [] = không giới hạn. @return list<string> */
    public static function folderChannels(?int $folderId): array
    {
        return $folderId === null ? [] : (self::get()['folder_channels'][(string) $folderId] ?? []);
    }

    /** @param  array<string, mixed>  $in */
    private static function clean(array $in): array
    {
        $s = array_merge(self::DEFAULTS, $in);
        $folders = [];

        foreach ((array) $s['folder_channels'] as $id => $list) {
            $ids = self::ids($list);

            if (is_numeric($id) && $ids !== []) {
                $folders[(string) (int) $id] = $ids;
            }
        }

        return [
            'enabled' => (bool) $s['enabled'],
            'caption_mode' => in_array($s['caption_mode'], ['ai', 'kid'], true) ? $s['caption_mode'] : 'ai',
            'empty_caption_ok' => (bool) $s['empty_caption_ok'],
            'approve_first' => (bool) $s['approve_first'],
            'duplicates' => in_array($s['duplicates'], ['ask', 'allow'], true) ? $s['duplicates'] : 'ask',
            'model' => array_key_exists((string) $s['model'], self::MODELS) ? (string) $s['model'] : self::DEFAULTS['model'],
            'effort' => array_key_exists((string) $s['effort'], self::EFFORTS) ? (string) $s['effort'] : self::DEFAULTS['effort'],
            'folder_channels' => $folders,
        ];
    }

    /** @return list<string> */
    public static function ids(mixed $list): array
    {
        return array_values(array_unique(array_filter(array_map(
            fn ($v): string => is_scalar($v) ? trim((string) $v) : '',
            is_array($list) ? $list : [],
        ), fn (string $v): bool => $v !== '' && preg_match('/^[A-Za-z0-9-]{1,64}$/', $v) === 1)));
    }
}

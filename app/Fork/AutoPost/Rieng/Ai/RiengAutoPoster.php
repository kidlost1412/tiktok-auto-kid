<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Rieng\RiengBatch;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Log;

/**
 * Kho riêng tự đăng theo khung: Planner gọi `postNext` cho mỗi giờ trống, TRƯỚC video Xưởng.
 * Video được đăng khi: bật tự đăng, còn file, đã có sản phẩm hợp lệ với giỏ của kênh, kênh nằm trong kênh được phép
 * (video > thư mục > mọi kênh), caption sẵn sàng theo cài đặt, và video trùng thì chủ app đã bấm "Vẫn đăng" (khi cài "hỏi trước").
 * Mỗi video chỉ đăng một lần trên một kênh (giữ chỗ new → reserved như Đăng hàng loạt).
 */
class RiengAutoPoster
{
    /** Video vừa tạo bài lỗi thì không thử lại tự động trong ngần này giờ. */
    public const int ERROR_PAUSE_HOURS = 6;

    public function __construct(private readonly RiengBatch $batch) {}

    /**
     * Thử đăng một video riêng vào giờ `$slot` của kênh. true = đã tạo bài.
     *
     * @param  array<string, list<string|null>>  $allowed  mã sản phẩm => quy cách có giỏ hợp lệ trên kênh (CartRules)
     */
    public function postNext(SocialAccount $social, array $allowed, CarbonImmutable $slot, ?CarbonImmutable $now = null): bool
    {
        $settings = RiengAutoSettings::get();

        if (! $settings['enabled'] || $allowed === []) {
            return false;
        }

        foreach ($this->candidates($social, $allowed, $settings, $now ?? CarbonImmutable::now()) as [$video, $qc, $caption, $tags]) {
            $error = $this->batch->postOne($social, (int) $video->id, (string) $video->product_code, $qc, $caption, $tags, $slot);

            if ($error === null) {
                Log::info('Kho riêng tự đăng: đã xếp video.', ['video_id' => $video->id, 'social_account_id' => $social->id]);

                return true;
            }

            $fresh = AutoVideo::query()->find($video->id);

            if ($fresh !== null) {
                $meta = (array) $fresh->meta;
                $meta['auto_error'] = mb_substr($error, 0, 300);
                $meta['auto_error_at'] = CarbonImmutable::now()->toIso8601String();
                $fresh->forceFill(['meta' => $meta])->save();
            }

            Log::warning('Kho riêng tự đăng: tạo bài lỗi, thử video khác.', ['video_id' => $video->id, 'error' => $error]);
        }

        return false;
    }

    /**
     * Video đăng được lên kênh này, theo thứ tự cũ trước. Mỗi phần tử: [video, quy cách, caption, hashtag AI].
     *
     * @param  array<string, list<string|null>>  $allowed
     * @return list<array{0: AutoVideo, 1: ?string, 2: string, 3: list<string>}>
     */
    public function candidates(SocialAccount $social, array $allowed, ?array $settings = null, ?CarbonImmutable $now = null): array
    {
        $settings ??= RiengAutoSettings::get();
        $now ??= CarbonImmutable::now();
        $out = [];

        $videos = AutoVideo::query()
            ->where('source', AutoVideo::SOURCE_RIENG)
            ->where('status', AutoVideo::NEW)
            ->whereNull('files_deleted_at')
            ->notHeld()
            ->whereIn('product_code', array_keys($allowed))
            ->orderBy('id')
            ->limit(300)
            ->get();

        foreach ($videos as $v) {
            if ($this->blocker($v, (string) $social->id, $allowed, $settings, $now) !== null) {
                continue;
            }

            $caption = (string) $this->captionFor($v, $settings);
            $out[] = [$v, $this->quyCachFor($v, $allowed), $caption, $this->hashtagsFor($v, $caption)];
        }

        return $out;
    }

    /**
     * Lý do (tiếng Việt, ngắn) khiến video chưa tự đăng lên kênh này; null = đăng được.
     * `$channelId` null = xét chung (không theo kênh nào), dùng cho thẻ video.
     *
     * @param  array<string, list<string|null>>|null  $allowed
     */
    public function blocker(AutoVideo $v, ?string $channelId, ?array $allowed, array $settings, ?CarbonImmutable $now = null): ?string
    {
        $now ??= CarbonImmutable::now();
        $meta = (array) $v->meta;
        $ai = (array) ($meta['ai'] ?? []);

        // AI đang xem (kết quả có thể đổi sản phẩm / caption): chờ AI xong rồi mới đăng.
        if (is_array($dang = $ai['dang'] ?? null) && CarbonImmutable::parse((string) ($dang['luc'] ?? 'now'))->diffInMinutes($now, true) < 40) {
            return empty($dang['tong']) ? 'AI sắp xem video' : "AI đang xem (bước {$dang['buoc']}/{$dang['tong']})";
        }

        if (! filled($v->product_code)) {
            return match ($ai['state'] ?? null) {
                null, 'error' => 'Chờ AI xem video',
                'gave_up' => 'AI không xem được, anh chọn sản phẩm',
                default => 'Anh chọn sản phẩm',
            };
        }

        if (filled($meta['auto_error_at'] ?? null) && CarbonImmutable::parse($meta['auto_error_at'])->addHours(self::ERROR_PAUSE_HOURS)->greaterThan($now)) {
            return 'Lần đăng trước lỗi: '.($meta['auto_error'] ?? '');
        }

        if (is_numeric($meta['duplicate_of'] ?? null) && $settings['duplicates'] === 'ask' && ! ($meta['dup_ok'] ?? false)) {
            return 'Trùng video, chờ anh bấm "Vẫn đăng"';
        }

        if ($this->captionFor($v, $settings) === null) {
            return $settings['caption_mode'] === 'ai'
                ? (in_array($ai['state'] ?? null, ['ok', 'unsure'], true) && filled($ai['caption'] ?? null) && $settings['approve_first'] ? 'Chờ anh duyệt caption' : 'Chờ AI viết caption')
                : 'Chờ anh viết caption';
        }

        $channels = $this->channelsFor($v, $settings);

        if ($channelId !== null && $channels !== [] && ! in_array($channelId, $channels, true)) {
            return 'Không thuộc kênh này';
        }

        if ($allowed !== null && $this->quyCachFor($v, $allowed) === false) {
            return 'Anh chọn quy cách sản phẩm';
        }

        return null;
    }

    /** Kênh được đăng: chọn riêng cho video > chọn cho thư mục > [] (mọi kênh có giỏ). @return list<string> */
    public function channelsFor(AutoVideo $v, ?array $settings = null): array
    {
        $own = RiengAutoSettings::ids(data_get($v->meta, 'channels'));

        if ($own !== []) {
            return $own;
        }

        $folder = data_get($v->meta, 'folder_id');

        return is_numeric($folder) ? (($settings ?? RiengAutoSettings::get())['folder_channels'][(string) (int) $folder] ?? []) : [];
    }

    /**
     * Caption sẽ đăng; null = chưa sẵn sàng (chờ AI / chờ duyệt / chờ chủ app viết).
     * Chủ app tự viết (caption_source = kid) luôn được dùng. '' = đăng không caption.
     */
    public function captionFor(AutoVideo $v, array $settings): ?string
    {
        if ($v->caption_source === 'kid' && filled($v->caption)) {
            return trim((string) $v->caption);
        }

        $ai = (array) data_get($v->meta, 'ai', []);

        if ($settings['caption_mode'] === 'ai') {
            $ready = in_array($ai['state'] ?? null, ['ok', 'unsure'], true) && filled($ai['caption'] ?? null);

            if ($ready && (! $settings['approve_first'] || ($ai['approved'] ?? false))) {
                return (string) $ai['caption'];
            }

            // AI đã xem (hoặc bỏ cuộc) mà không có caption dùng được: tuỳ cài đặt cho đăng không chữ.
            $settled = in_array($ai['state'] ?? null, ['ok', 'unsure', 'gave_up'], true);

            return $settled && ! ($ready && $settings['approve_first']) && $settings['empty_caption_ok'] ? '' : null;
        }

        return $settings['empty_caption_ok'] ? '' : null;
    }

    /**
     * Hashtag AI viết (3 cái, như video Xưởng) đi kèm caption; app còn thêm hashtag của sản phẩm theo cài đặt sản phẩm.
     * Đăng không chữ thì không kèm hashtag.
     *
     * @return list<string>
     */
    public function hashtagsFor(AutoVideo $v, string $caption): array
    {
        if ($caption === '') {
            return [];
        }

        // Chủ app đã sửa hashtag thì dùng đúng hashtag đó (kể cả để trống), không thì hashtag AI đề xuất.
        $kid = data_get($v->meta, 'kid_hashtags');

        return array_values(array_filter(is_array($kid) ? $kid : (array) data_get($v->meta, 'ai.hashtags', []), 'is_string'));
    }

    /**
     * Quy cách gắn giỏ trên kênh: video đã chọn thì phải nằm trong danh sách; chưa chọn mà kênh chỉ có một lựa chọn thì dùng nó.
     * false = không xác định được (kênh có nhiều quy cách mà video chưa chọn, hoặc quy cách đã chọn không có giỏ).
     *
     * @param  array<string, list<string|null>>  $allowed
     */
    public function quyCachFor(AutoVideo $v, array $allowed): string|false|null
    {
        $options = $allowed[(string) $v->product_code] ?? [];

        if ($options === []) {
            return false;
        }

        if (in_array('*', $options, true)) {
            return filled($v->quy_cach) ? (string) $v->quy_cach : null;
        }

        if (filled($v->quy_cach)) {
            return in_array((string) $v->quy_cach, $options, true) ? (string) $v->quy_cach : false;
        }

        if (in_array(null, $options, true)) {
            return null;
        }

        return count($options) === 1 ? $options[0] : false;
    }
}

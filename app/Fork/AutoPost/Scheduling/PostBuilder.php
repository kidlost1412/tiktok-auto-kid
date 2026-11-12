<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Dto\MediaItem;
use App\Enums\Media\Type as MediaType;
use App\Enums\Post\CreatedVia;
use App\Enums\Post\PublishStatus;
use App\Enums\Post\ScheduleMode;
use App\Enums\Post\Status as PostStatus;
use App\Enums\PostPlatform\ContentType;
use App\Fork\AutoPost\Hub\HubFiles;
use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Persona\CoverStore;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\Shop\ShopSync;
use App\Models\Media;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Support\VideoDurationProbe;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use RuntimeException;
use Throwable;

/**
 * Đưa một video của hub vào hàng đợi thành bài TikTok hẹn giờ: tạo bài, chép file vào kho media,
 * rồi ghi AutoVideo. Tất cả trong một transaction; lỗi thì không để lại bài hay file thừa.
 */
final class PostBuilder
{
    public const string PRIVACY = 'PUBLIC_TO_EVERYONE';

    /**
     * @param  array{caption: string, hashtags: list<string>, source: string, product_name?: ?string}  $caption
     */
    public function build(SocialAccount $social, AutoVideo $video, array $caption, CarbonImmutable $slot): Post
    {
        // Ưu tiên file trên đĩa; không có thì tải từ hub qua HTTP vào cache (MissingVideoFile nếu file mất/sai sha256,
        // lỗi thường nếu hub tắt: video về kho, thử lại sau).
        $path = app(HubFiles::class)->video($video);

        $workspace = $social->workspace ?? throw new RuntimeException('Tài khoản không có workspace.');
        $owner = $workspace->owner ?? throw new RuntimeException('Workspace không có chủ.');
        $hashtags = array_values($caption['hashtags'] ?? []);

        // Cá nhân hoá theo sản phẩm: hashtag riêng (hoặc mặc định chung) và ảnh bìa riêng. Caption/hashtag hub gốc vẫn được
        // lưu vào AutoVideo bên dưới; chữ cuối cùng chỉ nằm ở nội dung bài.
        $product = filled($video->product_code) ? AutoProduct::query()->find($video->product_code) : null;
        $final = app(Hashtags::class)->apply($caption['caption'], $hashtags, $product);
        $coverFile = $product !== null ? app(CoverStore::class)->pick($product) : null;
        $content = HubText::compose($final['caption'], $final['hashtags']);

        if ($content === '') {
            throw new RuntimeException('Caption rỗng.');
        }

        if (mb_strlen($content) > HubText::MAX_CHARS) {
            throw new RuntimeException('Caption dài quá '.HubText::MAX_CHARS.' ký tự (giới hạn TikTok).');
        }

        // K4: sản phẩm giỏ hàng lấy từ liên kết chủ app đã chọn cho (kênh, mã hub). Không có liên kết thì không tạo bài.
        // Theo đúng (kênh, mã hub, quy cách) của video, không bao giờ dùng sản phẩm của quy cách khác.
        $link = filled($video->product_code)
            ? ProductLink::slot((string) $social->id, (string) $video->product_code, $video->quy_cach)->first()
            : null;

        if ($link === null || ! preg_match(ShopSync::ID_PATTERN, (string) $link->shop_product_id) || CartRules::limitName((string) $link->display_name) === '') {
            throw new RuntimeException('Sản phẩm '.($video->product_code ?? '?').(filled($video->quy_cach) ? ' ('.$video->quy_cach.')' : '').' chưa được chọn sản phẩm giỏ hàng trên kênh này.');
        }

        // Tên giỏ hàng riêng của video (ten_gio của hub) nếu hợp lệ 1..30 ký tự, không thì dùng tên hiển thị của liên kết.
        $videoName = HubText::cartName($caption['product_name'] ?? null);
        $cartName = $videoName ?? CartRules::limitName((string) $link->display_name);

        $storedPath = null;

        try {
            return DB::transaction(function () use ($social, $video, $caption, $slot, $workspace, $owner, $content, $path, $link, $hashtags, $cartName, $videoName, $coverFile, &$storedPath): Post {
                $post = $workspace->posts()->forceCreate([
                    'post_group_id' => (string) Str::uuid7(),
                    'user_id' => $owner->id,
                    'content' => $content,
                    'media' => [],
                    'status' => PostStatus::Scheduled,
                    'schedule_mode' => ScheduleMode::Custom,
                    'created_via' => CreatedVia::Api,
                    'scheduled_at' => $slot->utc(),
                    'social_account_id' => $social->id,
                    'platform' => $social->platform,
                    ...$social->channelSnapshot(),
                    'content_type' => ContentType::TikTokVideo,
                    'publish_status' => PublishStatus::Pending,
                    'meta' => [
                        'privacy_level' => self::PRIVACY,
                        'allow_comments' => true,
                        'allow_duet' => false,
                        'allow_stitch' => false,
                        // Khoá riêng của app: video nguồn và sản phẩm giỏ hàng.
                        'fork_auto_video_id' => $video->id,
                        'fork_shop_product_id' => (string) $link->shop_product_id,
                        'fork_shop_product_name' => $cartName,
                        ...($coverFile !== null ? ['fork_cover' => $coverFile] : []),
                    ],
                ]);

                // Chép file vào kho media, hàng media thuộc về bài.
                $storedPath = 'medias/'.Str::uuid().'.mp4';
                $stream = fopen($path, 'rb');

                if ($stream === false) {
                    throw new RuntimeException('Không mở được file video: '.$path);
                }

                try {
                    Storage::writeStream($storedPath, $stream);
                } finally {
                    if (is_resource($stream)) {
                        fclose($stream);
                    }
                }

                $media = Media::query()->create([
                    'workspace_id' => $workspace->id,
                    'post_id' => $post->id,
                    'group_id' => (string) Str::uuid(),
                    'collection' => Media::COLLECTION_MEDIA,
                    'type' => MediaType::Video,
                    'path' => $storedPath,
                    'original_filename' => mb_scrub((string) $video->file_name, 'UTF-8'),
                    'mime_type' => 'video/mp4',
                    'size' => (int) filesize($path),
                    'order' => 0,
                    'meta' => VideoDurationProbe::mergeInto([], VideoDurationProbe::fromFile($path)),
                ]);

                $post->forceFill(['media' => [MediaItem::fromMedia($media)->toArray()]])->save();

                $video->forceFill([
                    'status' => 'scheduled',
                    'social_account_id' => $social->id,
                    'post_id' => $post->id,
                    'scheduled_for' => $slot->utc(),
                    'caption' => $caption['caption'],
                    'hashtags' => $hashtags,
                    'caption_source' => $caption['source'] ?? HubText::SOURCE,
                    'product_name' => $videoName,
                ])->save();

                return $post;
            });
        } catch (Throwable $e) {
            // Transaction đã rollback hàng media; file đã chép vào kho thì xoá để khỏi mồ côi.
            if ($storedPath !== null) {
                try {
                    Storage::delete($storedPath);
                } catch (Throwable) {
                }
            }

            throw $e;
        }
    }
}

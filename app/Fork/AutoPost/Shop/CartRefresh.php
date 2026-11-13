<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Shop;

use App\Enums\Post\Status as PostStatus;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use Illuminate\Support\Facades\DB;

/**
 * Chủ app đổi giỏ hàng (chọn sản phẩm shop khác / đổi tên giỏ) cho (kênh, mã hub, quy cách): các bài ĐÃ XẾP LỊCH
 * mà tiện ích chưa nhận đăng cũng phải đổi theo — trước đây bài dựng sẵn giữ nguyên giỏ cũ tới lúc đăng.
 *
 * Chỉ đụng bài còn "đang hẹn" (Scheduled) và chưa có lượt Chrome nào đang chạy / đã được duyệt đăng;
 * bài đang đăng dở thì để yên (đổi giữa chừng có thể gắn nhầm giỏ). Tên giỏ riêng của video (do hub đặt)
 * được giữ nguyên, chỉ tên lấy từ liên kết mới đổi theo.
 */
final class CartRefresh
{
    /**
     * @param  string|null  $oldName  tên hiển thị của liên kết TRƯỚC khi đổi (để nhận ra bài cũ dùng tên của liên kết)
     * @return int số bài đã đổi giỏ
     */
    public static function apply(string $socialId, ProductLink $link, ?string $oldName): int
    {
        $postIds = AutoVideo::query()
            ->where('product_code', $link->auto_product_id)
            ->when(
                $link->quy_cach === null,
                fn ($q) => $q->whereNull('quy_cach'),
                fn ($q) => $q->where('quy_cach', $link->quy_cach),
            )
            ->where('status', AutoVideo::SCHEDULED)
            ->whereNotNull('post_id')
            ->pluck('post_id');

        if ($postIds->isEmpty()) {
            return 0;
        }

        $busy = ChromeJob::query()
            ->whereIn('post_id', $postIds)
            // đang đăng dở, đã được duyệt đăng, đã lên TikTok (kể cả hẹn giờ trên TikTok) hoặc chưa rõ: không đổi nữa
            ->whereIn('state', [...ChromeJob::RUNNING, 'authorized', 'posted', 'uncertain'])
            ->pluck('post_id')
            ->all();

        $newName = CartRules::limitName((string) $link->display_name);
        $oldLimited = $oldName !== null ? CartRules::limitName($oldName) : null;
        $changed = 0;

        $posts = Post::query()
            ->whereIn('id', $postIds)
            ->whereNotIn('id', $busy)
            ->where('social_account_id', $socialId)
            ->where('status', PostStatus::Scheduled)
            ->get();

        foreach ($posts as $post) {
            DB::transaction(function () use ($post, $link, $newName, $oldLimited, &$changed): void {
                /** @var Post $fresh */
                $fresh = Post::query()->lockForUpdate()->find($post->id);

                if ($fresh === null || $fresh->status !== PostStatus::Scheduled) {
                    return;
                }

                $meta = is_array($fresh->meta) ? $fresh->meta : [];
                $name = (string) ($meta['fork_shop_product_name'] ?? '');
                $src = $meta['fork_shop_name_src'] ?? null;
                // Tên của bài lấy từ liên kết (không phải tên riêng hub đặt cho video) thì đổi theo tên mới.
                $fromLink = $src === 'link' || ($src === null && ($name === '' || $name === $oldLimited));

                $next = [
                    ...$meta,
                    'fork_shop_product_id' => (string) $link->shop_product_id,
                    'fork_shop_product_name' => $fromLink ? $newName : $name,
                ];

                if ($next !== $meta) {
                    $fresh->forceFill(['meta' => $next])->save();
                    $changed++;
                }
            });
        }

        return $changed;
    }

    /** Số bài đã xếp lịch vẫn đang dùng sản phẩm shop này (để báo chủ app khi bỏ chọn / ẩn). */
    public static function scheduledUsing(string $socialId, string $shopProductId): int
    {
        return Post::query()
            ->where('social_account_id', $socialId)
            ->where('status', PostStatus::Scheduled)
            ->where('meta->fork_shop_product_id', $shopProductId)
            ->count();
    }
}

<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\Media\ProductImageLookup;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use Illuminate\Support\Collection;

/** Thông tin hiển thị riêng của video riêng: cờ trùng video và sản phẩm đã gắn. Dùng chung cho trang Kho riêng và khung xem video. */
final class RiengInfo
{
    /**
     * Cờ "trùng video" cho nhiều video một lượt (một truy vấn lấy video gốc).
     *
     * @param  iterable<AutoVideo>  $videos
     * @return array<int, array{id: int, where: string, state: string, text: string, link: ?string}> theo id video, chỉ video bị trùng
     */
    public function duplicates(iterable $videos): array
    {
        $map = [];

        foreach ($videos as $v) {
            $of = data_get($v->meta, 'duplicate_of');

            if ($v->isRieng() && is_numeric($of)) {
                $map[(int) $v->id] = (int) $of;
            }
        }

        if ($map === []) {
            return [];
        }

        $originals = AutoVideo::query()->whereIn('id', array_unique(array_values($map)))->get()->keyBy('id');
        $out = [];

        foreach ($map as $id => $of) {
            $out[$id] = $this->describe($of, $originals[$of] ?? null);
        }

        return $out;
    }

    /** @return array{id: int, where: string, state: string, text: string, link: ?string} */
    public function describe(int $originalId, ?AutoVideo $original): array
    {
        if ($original === null) {
            return ['id' => $originalId, 'where' => 'gone', 'state' => 'gone', 'text' => 'Trùng một video đã có (video gốc không còn trong app)', 'link' => null];
        }

        $tz = RiengScanner::TZ;
        $held = $original->status === AutoVideo::POSTED && $original->posted_at?->isFuture();
        $state = $original->effectiveStatus();
        $link = data_get($original->stats, 'link');
        $link = is_string($link) && preg_match('#^https://#i', $link) === 1 ? $link : null;
        $where = $original->isRieng() ? 'rieng' : 'hub';

        $statePart = match ($state) {
            AutoVideo::SCHEDULED, AutoVideo::RESERVED => 'đã hẹn '.(($held ? $original->posted_at : $original->scheduled_for)?->copy()->timezone($tz)->format('H:i d/m') ?? 'giờ đăng'),
            AutoVideo::POSTED => 'đã đăng',
            AutoVideo::FAILED => 'đăng lỗi',
            AutoVideo::SKIPPED => 'đã bỏ qua',
            default => $where === 'rieng' ? null : 'chưa đăng',
        };

        $text = 'Trùng video #'.$original->id.' · '.($where === 'rieng' ? 'trùng video riêng khác' : 'Kho Xưởng Video').($statePart !== null ? ' · '.$statePart : '');

        return ['id' => (int) $original->id, 'where' => $where, 'state' => $state, 'text' => $text, 'link' => $state === AutoVideo::POSTED ? $link : null];
    }

    /**
     * Sản phẩm đã gắn cho video riêng (có sau khi hẹn giờ): tên + ảnh nhỏ. null nếu chưa gắn.
     *
     * @param  Collection<string, AutoProduct>  $products
     * @return array{code: string, name: string, image: ?string}|null
     */
    public function product(AutoVideo $v, Collection $products, ProductImageLookup $images): ?array
    {
        if (! filled($v->product_code)) {
            return null;
        }

        $p = $products[$v->product_code] ?? null;

        return [
            'code' => (string) $v->product_code,
            'name' => (string) ($p?->short_name ?: $v->product_code),
            'image' => $images->forSlot($v->social_account_id ? (string) $v->social_account_id : null, (string) $v->product_code, $v->quy_cach),
        ];
    }
}

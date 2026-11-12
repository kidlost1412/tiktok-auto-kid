<?php

declare(strict_types=1);

namespace App\Fork\Xuong;

use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Media\RemoteImage;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\SingleUser\SingleUser;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

/**
 * Nguồn dữ liệu chỉ đọc cho hub "Xưởng Video": sản phẩm TikTok Shop kèm ảnh thật.
 * Máy gọi máy: xác thực bằng X-Key == FORK_HUB_KEY (so sánh hằng thời gian), chỉ nhận từ loopback.
 */
final class ShopFeedController extends Controller
{
    private function guard(Request $request): void
    {
        $key = (string) config('fork.auto.hub_api.key');
        $sent = (string) $request->headers->get('X-Key', '');

        abort_unless(SingleUser::isLoopback($request), 403);
        abort_if($key === '' || $sent === '' || ! hash_equals($key, $sent), 401);
    }

    public function index(Request $request): JsonResponse
    {
        $this->guard($request);

        $links = ProductLink::query()->get(['auto_product_id', 'shop_product_id'])
            ->groupBy('shop_product_id')
            ->map(fn ($g): array => $g->pluck('auto_product_id')->unique()->values()->all());

        $seen = [];
        $items = [];

        foreach (ShopProduct::query()->where('missing', false)->where('hidden', false)->orderBy('title')->get() as $p) {
            if (isset($seen[$p->product_id])) {
                continue;
            }

            $seen[$p->product_id] = true;
            $items[] = [
                'shop_product_id' => (string) $p->product_id,
                'title' => (string) $p->title,
                'short_name' => CartRules::suggestName((string) $p->title),
                'image_url' => filled($p->cover_url) ? '/api/xuong/shop-products/'.$p->product_id.'/image?v='.ProductImages::version($p) : null,
                'price' => $p->price,
                'stock_num' => (int) $p->stock_num,
                'linked_codes' => $links[$p->product_id] ?? [],
            ];
        }

        return response()->json(['ok' => true, 'items' => $items]);
    }

    public function image(Request $request, string $id): BinaryFileResponse
    {
        $this->guard($request);

        $product = ShopProduct::query()->where('product_id', $id)->where('missing', false)->orderByDesc('synced_at')->first();
        abort_if($product === null, 404);

        $file = app(ProductImages::class)->file($product);
        abort_if($file === null, 404);

        return response()->file($file, [
            'Content-Type' => RemoteImage::mime(strtolower(pathinfo($file, PATHINFO_EXTENSION))),
            'Cache-Control' => 'private, max-age=86400',
        ]);
    }
}

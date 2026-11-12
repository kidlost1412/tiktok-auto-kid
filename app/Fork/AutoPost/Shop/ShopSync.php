<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Shop;

use App\Fork\AutoPost\Models\AnchorTemplate;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\Chrome\Models\ChromeJob;
use App\Models\Post;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use Throwable;

/**
 * Phần dữ liệu giỏ hàng mà tiện ích Chrome đọc và ghi: yêu cầu đồng bộ sản phẩm, danh sách sản phẩm shop,
 * mẫu anchor, và trường `product` của payload job. Giao thức: app/Fork/AutoPost/KE-HOACH.md (K4 CHỐT).
 */
final class ShopSync
{
    public const string ID_PATTERN = '/^[0-9]{6,25}$/';

    public const array SOURCES = ['my_shop', 'showcase'];

    public const int MAX_PRODUCTS = 5000;

    // ---------------------------------------------------------------- Yêu cầu đồng bộ

    /** Yêu cầu lấy sản phẩm chỉ có hiệu lực ngần này giây, sau đó hết hạn và chủ app phải bấm lại. */
    public const int REQUEST_TTL = 600;

    /** Chủ app bấm "Lấy sản phẩm từ shop": luôn cấp request_id MỚI (bấm lại thì thay yêu cầu cũ), tiện ích thấy ở lần hỏi /api/ext/tasks kế tiếp. */
    public function requestSync(string $socialAccountId): string
    {
        $id = (string) Str::uuid();

        AutoAccount::query()->updateOrCreate(['social_account_id' => $socialAccountId], [
            'products_sync_request' => $id,
            'products_sync_requested_at' => CarbonImmutable::now(),
            'products_sync_error' => null,
        ]);

        return $id;
    }

    /** request_id đang chờ tiện ích xử lý; null nếu không có hoặc đã hết hạn (10 phút). */
    public function pendingRequest(string $socialAccountId): ?string
    {
        $auto = AutoAccount::query()->find($socialAccountId);

        if ($auto === null || blank($auto->products_sync_request) || $this->expired($auto)) {
            return null;
        }

        return (string) $auto->products_sync_request;
    }

    private function expired(AutoAccount $auto): bool
    {
        $at = $auto->products_sync_requested_at;

        return $at === null || $at->lt(CarbonImmutable::now()->subSeconds(self::REQUEST_TTL));
    }

    /**
     * Tiện ích báo không lấy được sản phẩm. Chỉ ghi nếu request_id còn là yêu cầu đang chờ.
     */
    public function reportFailure(string $socialAccountId, string $requestId, string $reason): bool
    {
        $auto = AutoAccount::query()->find($socialAccountId);

        if ($auto === null || $requestId === '' || $auto->products_sync_request !== $requestId) {
            return false;
        }

        $auto->forceFill(['products_sync_error' => mb_substr(trim($reason) !== '' ? trim($reason) : 'không rõ lý do', 0, 500)])->save();

        return true;
    }

    /**
     * Trạng thái hiển thị cho chủ app: idle | waiting | error | expired | done.
     *
     * @return array{state: string, reason: ?string, requested_at: ?string, synced_at: ?string}
     */
    public function status(?AutoAccount $auto): array
    {
        $state = 'idle';
        $reason = null;

        if ($auto !== null && filled($auto->products_sync_request)) {
            if ($this->expired($auto)) {
                $state = 'expired';
            } elseif (filled($auto->products_sync_error)) {
                $state = 'error';
                $reason = (string) $auto->products_sync_error;
            } else {
                $state = 'waiting';
            }
        } elseif ($auto?->products_synced_at !== null) {
            $state = 'done';
        }

        return [
            'state' => $state,
            'reason' => $reason,
            'requested_at' => $auto?->products_sync_requested_at?->toIso8601String(),
            'synced_at' => $auto?->products_synced_at?->toIso8601String(),
        ];
    }

    // ---------------------------------------------------------------- Sản phẩm shop

    /**
     * Kiểm tra và chuẩn hoá danh sách sản phẩm tiện ích gửi lên. product_id BẮT BUỘC là chuỗi 6-25 chữ số
     * (số JSON sẽ mất chính xác nên bị từ chối).
     *
     * @return list<array{product_id: string, title: string, price: ?string, cover_url: ?string, stock_num: int, stock_status: ?string}>
     *
     * @throws InvalidArgumentException
     */
    public function normalizeProducts(mixed $raw): array
    {
        if (! is_array($raw) || ! array_is_list($raw)) {
            throw new InvalidArgumentException('products phải là một danh sách');
        }

        if (count($raw) > self::MAX_PRODUCTS) {
            throw new InvalidArgumentException('quá nhiều sản phẩm trong một lần gửi');
        }

        $out = [];

        foreach ($raw as $i => $item) {
            if (! is_array($item)) {
                throw new InvalidArgumentException("products[{$i}] phải là một object");
            }

            $id = $item['product_id'] ?? null;

            if (! is_string($id) || preg_match(self::ID_PATTERN, $id) !== 1) {
                throw new InvalidArgumentException("products[{$i}].product_id phải là chuỗi 6-25 chữ số");
            }

            $title = is_scalar($item['title'] ?? null) ? trim((string) $item['title']) : '';
            $price = $item['price'] ?? null;
            $cover = $item['cover_url'] ?? null;
            $stock = $item['stock_num'] ?? 0;
            $status = $item['stock_status'] ?? null;

            $out[$id] = [
                'product_id' => $id,
                'title' => mb_substr($title, 0, 500),
                'price' => is_scalar($price) && ! is_bool($price) ? mb_substr(trim((string) $price), 0, 100) : null,
                // Ảnh hiện thẳng trên trang: chỉ nhận https.
                'cover_url' => is_string($cover) && preg_match('#^https://#i', $cover) === 1 ? mb_substr($cover, 0, 1000) : null,
                'stock_num' => is_numeric($stock) ? max(0, (int) $stock) : 0,
                'stock_status' => is_scalar($status) && ! is_bool($status) ? mb_substr((string) $status, 0, 32) : null,
            ];
        }

        return array_values($out);
    }

    /**
     * Ghi sản phẩm của một nguồn. Khi `complete`, sản phẩm cùng nguồn không còn trong danh sách thì đánh
     * missing và, nếu requestId khớp cờ đang chờ, xoá cờ yêu cầu.
     *
     * @param  list<array<string, mixed>>  $products  đã qua normalizeProducts
     * @return array{received: int, missing: int}
     */
    public function ingestProducts(string $socialAccountId, string $requestId, string $source, array $products, bool $complete): array
    {
        $now = CarbonImmutable::now();
        $missing = 0;

        DB::transaction(function () use ($socialAccountId, $requestId, $source, $products, $complete, $now, &$missing): void {
            foreach ($products as $p) {
                ShopProduct::query()->updateOrCreate(
                    ['social_account_id' => $socialAccountId, 'product_id' => $p['product_id']],
                    [...$p, 'source' => $source, 'missing' => false, 'synced_at' => $now],
                );
            }

            if (! $complete) {
                return;
            }

            $missing = ShopProduct::query()
                ->where('social_account_id', $socialAccountId)
                ->where('source', $source)
                ->where('missing', false)
                ->whereNotIn('product_id', array_column($products, 'product_id'))
                ->update(['missing' => true, 'updated_at' => $now]);

            $auto = AutoAccount::query()->firstOrCreate(['social_account_id' => $socialAccountId]);
            $changes = ['products_synced_at' => $now];

            if ($requestId !== '' && $auto->products_sync_request === $requestId) {
                $changes['products_sync_request'] = null;
                $changes['products_sync_error'] = null;
            }

            $auto->forceFill($changes)->save();
        });

        try {
            app(HubCartAttach::class)->run();   // Shop vừa đồng bộ → gắn ngay giỏ đã chọn ở Xưởng (ô còn trống)
        } catch (Throwable) {
        }

        return ['received' => count($products), 'missing' => $missing];
    }

    // ---------------------------------------------------------------- Mẫu anchor

    /**
     * Lưu mẫu mới nhất của kênh. `$anchors` là kết quả json_decode KHÔNG assoc (giữ nguyên object rỗng).
     *
     * @throws InvalidArgumentException
     */
    public function saveTemplate(string $socialAccountId, string $productId, mixed $anchors, mixed $capturedAt): AnchorTemplate
    {
        if (preg_match(self::ID_PATTERN, $productId) !== 1) {
            throw new InvalidArgumentException('product_id phải là chuỗi 6-25 chữ số');
        }

        if (! is_array($anchors) || $anchors === [] || ! array_is_list($anchors)) {
            throw new InvalidArgumentException('anchors phải là danh sách không rỗng');
        }

        $json = json_encode($anchors, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION);

        if ($json === false || strlen($json) > 200_000) {
            throw new InvalidArgumentException('anchors không hợp lệ hoặc quá lớn');
        }

        try {
            $at = is_string($capturedAt) && $capturedAt !== '' ? CarbonImmutable::parse($capturedAt) : CarbonImmutable::now();
        } catch (Throwable) {
            $at = CarbonImmutable::now();
        }

        return AnchorTemplate::query()->updateOrCreate(
            ['social_account_id' => $socialAccountId],
            ['product_id' => $productId, 'anchors' => $json, 'captured_at' => $at],
        );
    }

    /** anchors của mẫu dưới dạng cây object/array (giữ nguyên object rỗng), sẵn sàng đưa vào JSON. */
    public function anchorsOf(AnchorTemplate $template): mixed
    {
        return json_decode((string) $template->getRawOriginal('anchors'), false, 512, JSON_BIGINT_AS_STRING);
    }

    // ---------------------------------------------------------------- Payload job

    /**
     * Trường `product` của payload /next: null khi bài không có sản phẩm giỏ hàng.
     *
     * @return array{product_id: string, product_name: string, anchor_template: mixed, template_product_id: ?string}|null
     */
    public function payloadFor(ChromeJob $job): ?array
    {
        $post = Post::query()->find($job->post_id);
        $meta = is_array($post?->meta) ? $post->meta : [];
        $id = $meta['fork_shop_product_id'] ?? null;

        if (! is_string($id) || preg_match(self::ID_PATTERN, $id) !== 1) {
            return null;
        }

        $name = $meta['fork_shop_product_name'] ?? null;
        $template = AnchorTemplate::query()->where('social_account_id', $job->social_account_id)->first();

        return [
            'product_id' => $id,
            'product_name' => CartRules::limitName(is_string($name) ? $name : ''),
            'anchor_template' => $template ? $this->anchorsOf($template) : null,
            'template_product_id' => $template ? (string) $template->product_id : null,
        ];
    }
}

<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Shop;

use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\Chrome\Models\ChromeAccount;
use Illuminate\Database\UniqueConstraintViolationException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * Tự gắn giỏ hàng theo sản phẩm TikTok Shop chủ app đã chọn trong hub (san-pham.json -> shop_product_id,
 * đã có sẵn trong AutoProduct.facts sau syncProducts), để không phải chọn lại ở trang Giỏ hàng.
 *
 * Thận trọng ("gắn sai tệ hơn không gắn"):
 * - Chỉ gắn trên kênh (Chrome đang bật) mà shop của kênh CÓ sản phẩm đó (fork_shop_products), còn trong shop, không bị ẩn.
 * - Chỉ gắn vào ô CHƯA có liên kết; không bao giờ sửa/ghi đè liên kết đã có.
 * - Sản phẩm hub có từ 2 quy cách trở lên: hub chỉ chọn một sản phẩm Shop cho cả mã nên không đoán quy cách nào, bỏ qua.
 * - Mỗi lựa chọn (kênh, mã, quy cách, sản phẩm Shop) chỉ được xét một lần (bảng fork_cart_auto_attach): chủ app bỏ chọn
 *   thì không gắn lại; hub đổi sang sản phẩm Shop khác và ô đang trống thì gắn sản phẩm mới.
 */
final class HubCartAttach
{
    public const string TABLE = 'fork_cart_auto_attach';

    /** @return int số liên kết vừa tạo */
    public function run(): int
    {
        $channels = ChromeAccount::query()->where('enabled', true)->pluck('social_account_id')->all();

        if ($channels === []) {
            return 0;
        }

        $created = 0;

        foreach (AutoProduct::query()->where('enabled', true)->orderBy('code')->get() as $product) {
            $shopId = self::hubShopId($product);

            if ($shopId === null) {
                continue;
            }

            $codes = CartRules::quyCachCodes($product);

            if (count($codes) !== 1) {
                continue;
            }

            $shops = ShopProduct::query()
                ->whereIn('social_account_id', $channels)
                ->where('product_id', $shopId)
                ->get();

            foreach ($shops as $shop) {
                if ($this->attach($product, $codes[0], $shop)) {
                    $created++;
                }
            }
        }

        return $created;
    }

    /** Sản phẩm Shop chủ app chọn trong hub cho mã này (null = chưa chọn / không hợp lệ / kho cảnh chung). */
    public static function hubShopId(AutoProduct $product): ?string
    {
        $facts = is_array($product->facts) ? $product->facts : [];

        if (($facts['loai'] ?? null) === 'kho-chung') {
            return null;
        }

        $id = $facts['shop_product_id'] ?? null;
        $id = is_int($id) ? (string) $id : $id;

        return is_string($id) && preg_match(ShopSync::ID_PATTERN, $id) === 1 ? $id : null;
    }

    private function attach(AutoProduct $product, ?string $quyCach, ShopProduct $shop): bool
    {
        if ($shop->missing || $shop->hidden) {
            return false;   // chưa xét: hiện lại / có lại trong shop thì lượt sau gắn
        }

        $key = [
            'social_account_id' => (string) $shop->social_account_id,
            'auto_product_id' => (string) $product->code,
            'quy_cach' => $quyCach ?? '',
            'shop_product_id' => (string) $shop->product_id,
        ];

        if (DB::table(self::TABLE)->where($key)->exists()) {
            return false;
        }

        $name = self::cartName($product, $quyCach) ?? CartRules::suggestName((string) $shop->title);

        if ($name === '') {
            return false;
        }

        try {
            return DB::transaction(function () use ($key, $product, $quyCach, $shop, $name): bool {
                $taken = ProductLink::slot($key['social_account_id'], $key['auto_product_id'], $quyCach)->exists();
                $now = now();
                $recorded = DB::table(self::TABLE)->insertOrIgnore([...$key, 'attached' => ! $taken, 'created_at' => $now, 'updated_at' => $now]);

                if ($taken || $recorded === 0) {
                    return false;
                }

                ProductLink::query()->create([
                    'social_account_id' => $key['social_account_id'],
                    'auto_product_id' => $key['auto_product_id'],
                    'quy_cach' => $quyCach,
                    'shop_product_id' => $key['shop_product_id'],
                    'display_name' => $name,
                ]);

                Log::info('Giỏ hàng: tự gắn theo lựa chọn trong hub.', [...$key, 'product' => $product->short_name]);

                return true;
            });
        } catch (UniqueConstraintViolationException) {
            return false;   // chủ app vừa chọn tay cùng lúc: giữ lựa chọn của chủ app
        }
    }

    /** ten_gio của hub (chuỗi, hoặc {quy_cach: tên, "": tên chung}) nếu dài 1..30 ký tự. */
    private static function cartName(AutoProduct $product, ?string $quyCach): ?string
    {
        $raw = (is_array($product->facts) ? $product->facts : [])['ten_gio'] ?? null;

        if (is_array($raw)) {
            $raw = HubText::cartName($raw[$quyCach ?? ''] ?? null) ?? ($raw[''] ?? null);
        }

        return HubText::cartName($raw);
    }
}

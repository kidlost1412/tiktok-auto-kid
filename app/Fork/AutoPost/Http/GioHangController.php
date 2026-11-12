<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

/**
 * Trang "Giỏ hàng" (/auto/gio-hang): chủ app chọn, cho từng kênh, sản phẩm TikTok Shop đúng với từng
 * sản phẩm của hub và từng quy cách (vd "Đạm cá – Chai 1L"). Không bao giờ tự chọn, không bao giờ ghép theo tên.
 */
final class GioHangController extends Controller
{
    use ScopesToOwner;

    public function index(Request $request): Response
    {
        $accountId = $this->authorizeOwner($request);
        $enabled = ChromeAccount::query()->where('enabled', true)->pluck('social_account_id')->all();
        $channels = $this->tiktokAccounts($accountId)->filter(fn (SocialAccount $a): bool => in_array($a->id, $enabled, true))->values();

        $selected = $channels->first(fn (SocialAccount $a): bool => $a->id === (string) $request->query('kenh')) ?? $channels->first();

        $props = [
            'channels' => $channels->map(fn (SocialAccount $a): array => [
                'id' => $a->id,
                'username' => $a->username,
                'display_name' => $a->display_name,
                'avatar_url' => $a->avatar_url,
            ])->all(),
            'selected' => $selected?->id,
            'sync' => null,
            'products' => [],
            'rows' => [],
            'name_max' => CartRules::NAME_MAX,
            // Cá nhân hoá (ảnh bìa, hashtag) theo mã sản phẩm hub, và hashtag mặc định chung.
            'personalise' => AutoProduct::query()->get()->mapWithKeys(fn (AutoProduct $p): array => [$p->code => PersonaliseController::stateFor($p)])->all(),
            'personalise_default' => Hashtags::defaults(),
            'sync_ttl_minutes' => intdiv(ShopSync::REQUEST_TTL, 60),
        ];

        if ($selected !== null) {
            $props = [...$props, ...$this->channelData($selected)];
        }

        return Inertia::render('fork/GioHang', $props);
    }

    /** Bấm "Lấy sản phẩm từ shop": mỗi lần bấm cấp một yêu cầu MỚI; tiện ích Chrome của kênh sẽ thấy ở lần hỏi kế tiếp. */
    public function requestSync(Request $request, string $socialAccount): RedirectResponse
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);

        if (! ChromeAccount::query()->where('social_account_id', $account->id)->where('enabled', true)->exists()) {
            return back()->with('flash.error', 'Kênh chưa bật đăng qua Chrome nên không lấy được sản phẩm từ shop.');
        }

        app(ShopSync::class)->requestSync($account->id);

        return back()->with('flash.success', 'Đã gửi yêu cầu. Tiện ích Chrome sẽ lấy sản phẩm từ shop @'.$account->username.' trong ít phút.');
    }

    /** Chủ app chọn sản phẩm shop cho (sản phẩm hub, quy cách) trên một kênh. Lưu lại thì liên kết hết bị tạm dừng. */
    public function saveLink(Request $request, string $socialAccount, string $code): RedirectResponse
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);
        $product = AutoProduct::query()->findOrFail($code);

        $data = $request->validate([
            'shop_product_id' => ['required', 'string', 'regex:'.ShopSync::ID_PATTERN],
            'display_name' => ['required', 'string', 'min:1', 'max:'.CartRules::NAME_MAX],
            'quy_cach' => ['nullable', 'string', 'max:100'],
        ]);

        $quyCach = filled($data['quy_cach'] ?? null) ? (string) $data['quy_cach'] : null;

        if (! in_array($quyCach, CartRules::quyCachCodes($product), true)) {
            return back()->with('flash.error', 'Quy cách này không có trong sản phẩm '.$product->short_name.'.');
        }

        $shop = ShopProduct::query()
            ->where('social_account_id', $account->id)
            ->where('product_id', $data['shop_product_id'])
            ->first();

        if ($shop === null) {
            return back()->with('flash.error', 'Sản phẩm này không thuộc shop của kênh @'.$account->username.'.');
        }

        if ($shop->missing) {
            return back()->with('flash.error', 'Sản phẩm này đã không còn trong shop, hãy lấy lại sản phẩm từ shop.');
        }

        if ($shop->hidden) {
            return back()->with('flash.error', 'Sản phẩm này đang bị ẩn, hãy hiện lại trước khi chọn.');
        }

        $values = ['shop_product_id' => $shop->product_id, 'display_name' => $data['display_name'], 'paused_reason' => null];
        $existing = ProductLink::slot($account->id, $product->code, $quyCach)->first();

        if ($existing !== null) {
            $existing->update($values);
        } else {
            ProductLink::query()->create([...$values, 'social_account_id' => $account->id, 'auto_product_id' => $product->code, 'quy_cach' => $quyCach]);
        }

        return back()->with('flash.success', 'Đã chọn sản phẩm giỏ hàng cho '.CartRules::label($product, $product->code, $quyCach).' trên @'.$account->username.'.');
    }

    public function clearLink(Request $request, string $socialAccount, string $code): RedirectResponse
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);
        $data = $request->validate(['quy_cach' => ['nullable', 'string', 'max:100']]);

        ProductLink::slot($account->id, $code, $data['quy_cach'] ?? null)->delete();

        return back()->with('flash.success', 'Đã bỏ chọn. Video của sản phẩm này sẽ được giữ lại trong kho, không đăng.');
    }

    /** Ẩn/hiện một sản phẩm trong danh sách chọn. Chỉ có tác dụng trong app, không đụng TikTok Shop. */
    public function setHidden(Request $request, string $socialAccount, string $productId): RedirectResponse
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);
        $data = $request->validate(['hidden' => ['required', 'boolean']]);

        $updated = ShopProduct::query()
            ->where('social_account_id', $account->id)
            ->where('product_id', $productId)
            ->update(['hidden' => (bool) $data['hidden']]);

        abort_if($updated === 0, SymfonyResponse::HTTP_NOT_FOUND);

        $inUse = $data['hidden'] && ProductLink::query()->where('social_account_id', $account->id)->where('shop_product_id', $productId)->exists();

        if ($inUse) {
            return back()->with('flash.error', 'Đã ẩn. Lưu ý sản phẩm này đang được chọn cho video: video đó sẽ được giữ trong kho cho tới khi anh chọn sản phẩm khác.');
        }

        return back()->with('flash.success', $data['hidden'] ? 'Đã ẩn sản phẩm khỏi danh sách chọn.' : 'Đã hiện lại sản phẩm.');
    }

    /**
     * @return array<string, mixed>
     */
    private function channelData(SocialAccount $account): array
    {
        $auto = AutoAccount::query()->find($account->id);
        $sync = app(ShopSync::class)->status($auto);
        $rules = app(CartRules::class);

        $shop = ShopProduct::query()->where('social_account_id', $account->id)->orderBy('title')->get();
        $byId = $shop->keyBy('product_id');
        $links = ProductLink::query()->where('social_account_id', $account->id)->get()
            ->keyBy(fn (ProductLink $l): string => $l->auto_product_id.'|'.($l->quy_cach ?? ''));

        $waiting = AutoVideo::query()
            ->where('status', AutoVideo::NEW)
            ->selectRaw('product_code, quy_cach, count(*) as total')
            ->groupBy('product_code', 'quy_cach')
            ->get()
            ->mapWithKeys(fn ($r): array => [$r->product_code.'|'.($r->quy_cach ?? '') => (int) $r->total]);

        $rows = [];
        $usedBy = [];

        foreach (AutoProduct::query()->orderBy('short_name')->get() as $hub) {
            $list = CartRules::quyCachList($hub);

            foreach ($list === [] ? [['ma' => null, 'ten' => null]] : $list as $qc) {
                $key = $hub->code.'|'.($qc['ma'] ?? '');
                $link = $links[$key] ?? null;

                if (! $hub->enabled && $link === null) {
                    continue;
                }

                $card = $link ? $byId->get($link->shop_product_id) : null;
                $label = CartRules::label($hub, $hub->code, $qc['ma']);

                if ($link) {
                    $usedBy[$link->shop_product_id][] = $label;
                }

                $rows[] = [
                    'key' => $key,
                    'code' => $hub->code,
                    'quy_cach' => $qc['ma'],
                    'label' => $label,
                    'hub_name' => $hub->short_name,
                    'quy_cach_name' => $qc['ten'],
                    'enabled' => (bool) $hub->enabled,
                    'new_videos' => (int) ($waiting[$key] ?? 0),
                    'link' => $link ? [
                        'shop_product_id' => (string) $link->shop_product_id,
                        'display_name' => (string) $link->display_name,
                        'paused_reason' => $link->paused_reason,
                        'problem' => $rules->problem($card) ?? ($card?->hidden ? 'sản phẩm đang bị ẩn' : null),
                        'product' => $card ? $this->shopRow($card) : null,
                    ] : null,
                ];
            }
        }

        return [
            'sync' => $sync,
            'products' => $shop->map(fn (ShopProduct $p): array => [
                ...$this->shopRow($p),
                'suggested_name' => CartRules::suggestName((string) $p->title),
                'used_by' => $usedBy[$p->product_id] ?? [],
            ])->values()->all(),
            'rows' => $rows,
        ];
    }

    /**
     * @return array<string, mixed>
     */
    private function shopRow(ShopProduct $p): array
    {
        $cover = $p->cover_url;

        return [
            'product_id' => (string) $p->product_id,
            'title' => (string) $p->title,
            'price' => $p->price,
            'cover_url' => is_string($cover) && preg_match('#^https://#i', $cover) === 1 ? $cover : null,
            // Ảnh đã tải về máy, phục vụ qua route nội bộ (link CDN gốc hết hạn).
            'image' => ProductImages::url($p),
            'stock_num' => (int) $p->stock_num,
            'source' => $p->source,
            'hidden' => (bool) $p->hidden,
            'missing' => (bool) $p->missing,
        ];
    }
}

<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Hub\HubProducts;
use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Shop\CartRefresh;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\AutoPost\Shop\ProductNaming;
use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\AutoPost\VideoLibrary;
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

        // Dữ liệu của kênh đang chọn (sync, products, rows, sample_hidden) tính chung một lần, và chỉ khi có prop nào cần
        // (partial reload của bàn Chủ quầy / các prop không được xin thì không chạy).
        $channelData = null;
        $channel = function () use (&$channelData, $selected): array {
            return $channelData ??= $selected !== null ? $this->channelData($selected) : [];
        };

        return Inertia::render('fork/GioHang', [
            'channels' => $channels->map(fn (SocialAccount $a): array => [
                'id' => $a->id,
                'username' => $a->username,
                'display_name' => $a->display_name,
                'avatar_url' => $a->avatar_url,
            ])->all(),
            'selected' => $selected?->id,
            'sync' => fn (): mixed => $channel()['sync'] ?? null,
            'products' => fn (): array => $channel()['products'] ?? [],
            'rows' => fn (): array => $channel()['rows'] ?? [],
            'sample_hidden' => fn (): bool => $channel()['sample_hidden'] ?? false,
            'name_short_max' => ProductNaming::SHORT_MAX,
            'name_max' => CartRules::NAME_MAX,
            // Cá nhân hoá (ảnh bìa, hashtag) theo mã sản phẩm hub, và hashtag mặc định chung.
            'personalise' => fn (): array => AutoProduct::query()->get()->mapWithKeys(fn (AutoProduct $p): array => [$p->code => PersonaliseController::stateFor($p)])->all(),
            'personalise_default' => fn (): array => Hashtags::defaults(),
            'sync_ttl_minutes' => intdiv(ShopSync::REQUEST_TTL, 60),
        ]);
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
        $oldName = $existing?->display_name;

        if ($existing !== null) {
            $existing->update($values);
            $link = $existing;
        } else {
            $link = ProductLink::query()->create([...$values, 'social_account_id' => $account->id, 'auto_product_id' => $product->code, 'quy_cach' => $quyCach]);
        }

        // Bài đã xếp lịch (chưa đăng) của sản phẩm này đổi sang giỏ mới luôn.
        $moved = CartRefresh::apply($account->id, $link, $oldName);
        $note = $moved > 0 ? ' '.$moved.' bài đã xếp lịch cũng được đổi sang giỏ mới.' : '';

        return back()->with('flash.success', 'Đã chọn sản phẩm giỏ hàng cho '.CartRules::label($product, $product->code, $quyCach).' trên @'.$account->username.'.'.$note);
    }

    public function clearLink(Request $request, string $socialAccount, string $code): RedirectResponse
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);
        $data = $request->validate(['quy_cach' => ['nullable', 'string', 'max:100']]);

        $link = ProductLink::slot($account->id, $code, $data['quy_cach'] ?? null)->first();
        $link?->delete();
        $still = $link !== null ? CartRefresh::scheduledUsing($account->id, (string) $link->shop_product_id) : 0;

        // Bài đã xếp lịch thì không tự huỷ (chủ app quyết): chỉ báo để chủ app biết còn bài đăng kèm giỏ cũ.
        return $still > 0
            ? back()->with('flash.warning', 'Đã bỏ chọn. Video mới của sản phẩm này sẽ được giữ trong kho. Lưu ý: '.$still.' bài đã xếp lịch vẫn đăng kèm giỏ cũ — muốn đổi thì chọn giỏ mới cho sản phẩm này.')
            : back()->with('flash.success', 'Đã bỏ chọn. Video của sản phẩm này sẽ được giữ lại trong kho, không đăng.');
    }

    /**
     * "+ Thêm sản phẩm": chọn một sản phẩm TikTok Shop của kênh -> tạo luôn sản phẩm hub tương ứng (qua API của Xưởng Video,
     * tên và mã suy ra từ sản phẩm shop, chủ app đổi tên được) và gắn giỏ hàng cho kênh này trong một lần.
     */
    public function addProduct(Request $request, string $socialAccount): RedirectResponse
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);

        $data = $request->validate([
            'shop_product_id' => ['required', 'string', 'regex:'.ShopSync::ID_PATTERN],
            'name' => ['nullable', 'string', 'max:'.ProductNaming::SHORT_MAX],
            'display_name' => ['nullable', 'string', 'max:'.CartRules::NAME_MAX],
        ]);

        $shop = ShopProduct::query()->where('social_account_id', $account->id)->where('product_id', $data['shop_product_id'])->first();

        if ($shop === null) {
            return back()->with('flash.error', 'Sản phẩm này không thuộc shop của kênh @'.$account->username.'.');
        }

        if ($shop->missing || $shop->hidden) {
            return back()->with('flash.error', $shop->missing
                ? 'Sản phẩm này đã không còn trong shop, hãy lấy lại sản phẩm từ shop.'
                : 'Sản phẩm này đang bị ẩn, hãy hiện lại trước khi chọn.');
        }

        $title = (string) $shop->title;
        $short = filled($data['name'] ?? null) ? trim((string) preg_replace('/\s+/u', ' ', (string) $data['name'])) : ProductNaming::shortName($title);
        $cartName = filled($data['display_name'] ?? null) ? CartRules::limitName((string) $data['display_name']) : CartRules::suggestName($title);
        $hubPath = app(VideoLibrary::class)->hubPath();
        $code = ProductNaming::code($short, fn (string $c): bool => AutoProduct::query()->whereKey($c)->exists() || is_dir($hubPath.'/san-pham/'.$c));

        $made = app(HubProducts::class)->create($code, ProductNaming::fullName($title), $short, (string) $shop->product_id);

        if (! $made['ok']) {
            return back()->with('flash.error', 'Chưa tạo được sản phẩm: '.$made['error']);
        }

        app(VideoLibrary::class)->syncProducts();
        $product = AutoProduct::query()->find($code);

        if ($product === null) {
            return back()->with('flash.error', 'Hub đã tạo sản phẩm nhưng app chưa thấy nó. Chờ vài phút hoặc mở trang Kho video rồi quay lại.');
        }

        $product->update(['enabled' => true]);
        ProductLink::query()->create([
            'social_account_id' => $account->id, 'auto_product_id' => $product->code, 'quy_cach' => null,
            'shop_product_id' => $shop->product_id, 'display_name' => $cartName,
        ]);

        $msg = 'Đã thêm sản phẩm "'.$product->short_name.'" và gắn giỏ hàng cho @'.$account->username.'. Anh có thể đổi tên ngay trên thẻ.';

        return back()->with(filled($made['warning']) ? 'flash.error' : 'flash.success', filled($made['warning']) ? $msg.' Lưu ý: '.$made['warning'] : $msg);
    }

    /** Đổi tên gọi ngắn của sản phẩm hub (tên hiện trên thẻ và đọc trong video). */
    public function renameProduct(Request $request, string $code): RedirectResponse
    {
        $this->authorizeOwner($request);
        $product = AutoProduct::query()->findOrFail($code);
        $data = $request->validate(['name' => ['required', 'string', 'min:1', 'max:'.ProductNaming::SHORT_MAX]]);
        $name = trim((string) preg_replace('/\s+/u', ' ', $data['name']));

        if ($name === '') {
            return back()->with('flash.error', 'Tên sản phẩm không được để trống.');
        }

        $done = app(HubProducts::class)->rename($product->code, $name);

        if (! $done['ok']) {
            return back()->with('flash.error', 'Chưa đổi được tên: '.$done['error']);
        }

        app(VideoLibrary::class)->syncProducts();

        return back()->with('flash.success', 'Đã đổi tên sản phẩm thành "'.$name.'".');
    }

    /**
     * Xoá sản phẩm hub (hồ sơ vào Thùng rác của Windows; video gốc và video đã làm không bị đụng).
     * Không cho xoá khi còn video đang chờ hoặc đã xếp lịch để khỏi mất video giữa chừng.
     */
    public function deleteProduct(Request $request, string $code): RedirectResponse
    {
        $this->authorizeOwner($request);
        $product = AutoProduct::query()->findOrFail($code);

        $busy = AutoVideo::query()->where('product_code', $product->code)
            ->whereIn('status', [AutoVideo::NEW, AutoVideo::RESERVED, AutoVideo::SCHEDULED])->count();

        if ($busy > 0) {
            return back()->with('flash.error', 'Sản phẩm "'.$product->short_name.'" còn '.$busy.' video đang chờ hoặc đã xếp lịch đăng nên chưa xoá được.');
        }

        $done = app(HubProducts::class)->delete($product->code);

        if (! $done['ok']) {
            return back()->with('flash.error', 'Chưa xoá được: '.$done['error']);
        }

        ProductLink::query()->where('auto_product_id', $product->code)->delete();
        $product->update(['enabled' => false]);
        app(VideoLibrary::class)->syncProducts();

        return back()->with('flash.success', 'Đã xoá sản phẩm "'.$product->short_name.'" (hồ sơ nằm trong Thùng rác của Windows nếu anh cần lấy lại).');
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
            ->notRieng()->where('status', AutoVideo::NEW)
            ->selectRaw('product_code, quy_cach, count(*) as total')
            ->groupBy('product_code', 'quy_cach')
            ->get()
            ->mapWithKeys(fn ($r): array => [$r->product_code.'|'.($r->quy_cach ?? '') => (int) $r->total]);

        $rows = [];
        $usedBy = [];
        $hubProducts = AutoProduct::query()->orderBy('short_name')->get();
        // Sản phẩm ví dụ chỉ để người mới thấy cách dùng: có sản phẩm thật rồi thì ẩn thẻ ví dụ chưa dùng (chưa có giỏ, chưa có video).
        $hasReal = $hubProducts->contains(fn (AutoProduct $p): bool => $p->enabled && $p->code !== HubProducts::SAMPLE_CODE
            && (is_array($p->facts) ? ($p->facts['loai'] ?? null) : null) !== 'kho-chung');
        $sampleHidden = false;

        foreach ($hubProducts as $hub) {
            $list = CartRules::quyCachList($hub);

            foreach ($list === [] ? [['ma' => null, 'ten' => null]] : $list as $qc) {
                $key = $hub->code.'|'.($qc['ma'] ?? '');
                $link = $links[$key] ?? null;

                if (! $hub->enabled && $link === null) {
                    continue;
                }

                if ($hub->code === HubProducts::SAMPLE_CODE && $hasReal && $link === null && (int) ($waiting[$key] ?? 0) === 0) {
                    $sampleHidden = true;

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
                    'is_sample' => $hub->code === HubProducts::SAMPLE_CODE,
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
            'sample_hidden' => $sampleHidden,
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

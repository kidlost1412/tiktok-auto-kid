<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Scheduling;

use App\Enums\SocialAccount\Platform;
use App\Enums\SocialAccount\Status as AccountStatus;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\AutoPost\Shop\CartRules;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Support\Collection;

/**
 * Chỉ đọc: giải thích vì sao từng video `new` chưa được xếp lịch (hoặc khi nào tới lượt).
 * Không thay đổi hành vi xếp lịch, chỉ phản chiếu cùng điều kiện mà Planner/VideoLibrary dùng.
 */
final class Readiness
{
    public const string READY = 'ready';

    public const string NO_CART = 'no_cart';

    public const string CART_BROKEN = 'cart_broken';

    public const string NO_CHANNEL = 'no_channel';

    public const string CHANNEL_OFF = 'channel_off';

    public const string NO_CAPTION = 'no_caption';

    public const string NO_FILE = 'no_file';

    public const string PRODUCT_OFF = 'product_off';

    public const string NO_SLOT = 'no_slot';

    public const string LEGACY = 'legacy';

    /** @var array<string, array{auto: AutoAccount, name: string}>|null */
    private ?array $eligible = null;

    /** @var array<string, string> lý do kênh không dùng được, khoá là social_account_id */
    private array $ineligible = [];

    /** @var array<string, array{allowed: array<string, list<?string>>, warnings: list<string>}> */
    private array $carts = [];

    /** @var array<string, ?CarbonImmutable> */
    private array $nextSlot = [];

    /** @var Collection<string, AutoProduct>|null */
    private ?Collection $products = null;

    private CarbonImmutable $now;

    public function __construct(private readonly Planner $planner, private readonly CartRules $cart)
    {
        $this->now = CarbonImmutable::now();
    }

    /**
     * Đánh giá mọi video `new` (đã lọc theo $videos nếu truyền vào).
     *
     * @param  Collection<int, AutoVideo>|null  $videos
     * @return array<int, array{code: string, severity: string, reason: string, next_slot: ?string}> khoá là id video
     */
    public function assess(?Collection $videos = null): array
    {
        $videos ??= AutoVideo::query()->notRieng()->where('status', AutoVideo::NEW)->get();
        $out = [];

        foreach ($videos as $v) {
            if ($v->status === AutoVideo::NEW) {
                $out[$v->id] = $this->one($v);
            }
        }

        return $out;
    }

    /**
     * Tóm tắt các vấn đề chặn video để hiện ở đầu trang.
     *
     * @param  array<int, array{code: string, severity: string, reason: string, next_slot: ?string}>  $assessments
     * @param  Collection<int, AutoVideo>  $videos
     * @return list<array{code: string, severity: string, count: int, message: string, action: string, href: ?string}>
     */
    public function summarize(array $assessments, Collection $videos): array
    {
        $groups = [];

        foreach ($videos as $v) {
            $a = $assessments[$v->id] ?? null;

            if ($a === null || ! in_array($a['code'], [self::NO_CART, self::CART_BROKEN, self::NO_CHANNEL, self::CHANNEL_OFF, self::NO_CAPTION, self::NO_FILE, self::PRODUCT_OFF], true)) {
                continue;
            }

            $key = $a['code'].'|'.($a['code'] === self::NO_CAPTION || $a['code'] === self::NO_FILE || $a['code'] === self::CHANNEL_OFF || $a['code'] === self::NO_CHANNEL ? '' : (string) $v->product_code);
            $groups[$key] ??= ['code' => $a['code'], 'severity' => $a['severity'], 'count' => 0, 'product' => $this->productName($v->product_code), 'reasons' => []];
            $groups[$key]['count']++;
        }

        $out = [];

        foreach ($groups as $g) {
            [$message, $action, $href] = match ($g['code']) {
                self::NO_CART => ["{$g['count']} video {$g['product']} đang chờ vì chưa chọn giỏ hàng", 'Chọn giỏ', route('fork.auto.gio-hang')],
                self::CART_BROKEN => ["{$g['count']} video {$g['product']} đang chờ vì giỏ hàng đã chọn không dùng được (hết hàng, bị ẩn hoặc tạm dừng)", 'Xem giỏ hàng', route('fork.auto.gio-hang')],
                self::NO_CHANNEL => ["{$g['count']} video đang chờ vì chưa có kênh nào bật tự động đăng", 'Bật kênh', route('fork.auto.index')],
                self::CHANNEL_OFF => ["{$g['count']} video đang chờ vì kênh đang tắt tự động đăng hoặc chưa bật Chrome", 'Xem kênh', route('fork.auto.index')],
                self::NO_CAPTION => ["{$g['count']} video thiếu caption từ hub nên chưa đăng được", 'Chờ hub bổ sung', null],
                self::NO_FILE => ["{$g['count']} video chưa thấy file mp4 trong hub", 'Quét kho', null],
                default => ["{$g['count']} video {$g['product']} đang chờ vì sản phẩm đang tắt", 'Xem sản phẩm', route('fork.auto.index')],
            };

            $out[] = ['code' => $g['code'], 'severity' => $g['severity'], 'count' => $g['count'], 'message' => $message, 'action' => $action, 'href' => $href];
        }

        usort($out, fn (array $a, array $b): int => $b['count'] <=> $a['count']);

        return $out;
    }

    /** @return array{code: string, severity: string, reason: string, next_slot: ?string} */
    private function one(AutoVideo $v): array
    {
        if ($v->source === 'ra') {
            return $this->result(self::LEGACY, 'muted', 'Bản ghi cũ, app không đăng video này');
        }

        $product = $this->products()[$v->product_code] ?? null;

        if ($product === null || ! $product->enabled) {
            return $this->result(self::PRODUCT_OFF, 'error', 'Sản phẩm '.$this->productName($v->product_code).' đang tắt hoặc không còn trong hub');
        }

        if (! filled($v->caption)) {
            return $this->result(self::NO_CAPTION, 'error', 'Thiếu caption từ hub'.(filled($v->skip_reason) ? ' ('.$v->skip_reason.')' : ''));
        }

        if ($v->files_deleted_at !== null) {
            return $this->result(self::NO_FILE, 'error', 'Chưa thấy file mp4 trong hub');
        }

        $eligible = $this->eligibleChannels();
        $label = CartRules::label($product, (string) $v->product_code, filled($v->quy_cach) ? (string) $v->quy_cach : null);

        if ($eligible === []) {
            $all = AutoAccount::query()->count();

            return $all === 0
                ? $this->result(self::NO_CHANNEL, 'error', 'Chưa có kênh nào bật tự động đăng')
                : $this->result(self::CHANNEL_OFF, 'error', 'Kênh đang tắt tự động đăng'.($this->ineligible === [] ? '' : ' ('.implode('; ', array_unique($this->ineligible)).')'));
        }

        $qc = filled($v->quy_cach) ? (string) $v->quy_cach : null;
        $matching = [];

        foreach ($eligible as $id => $_) {
            $allowed = $this->cartFor((string) $id)['allowed'][$v->product_code] ?? [];

            if (in_array($qc, $allowed, true) || in_array('*', $allowed, true)) {
                $matching[] = (string) $id;
            }
        }

        if ($matching === []) {
            $linked = ProductLink::query()
                ->whereIn('social_account_id', array_keys($eligible))
                ->where('auto_product_id', $v->product_code)
                ->when($qc === null, fn ($q) => $q->whereNull('quy_cach'), fn ($q) => $q->where('quy_cach', $qc))
                ->exists();

            if (! $linked) {
                return $this->result(self::NO_CART, 'error', "Chưa chọn giỏ cho {$label} trên kênh nào → vào Giỏ hàng");
            }

            $warning = null;

            foreach (array_keys($eligible) as $id) {
                foreach ($this->cartFor((string) $id)['warnings'] as $w) {
                    if (str_starts_with($w, $label)) {
                        $warning = $w;
                        break 2;
                    }
                }
            }

            return $this->result(self::CART_BROKEN, 'error', 'Giỏ đã chọn nhưng chưa dùng được'.($warning ? ': '.$warning : '').' → vào Giỏ hàng');
        }

        $next = null;

        foreach ($matching as $id) {
            $slot = $this->nextSlotFor($id);

            if ($slot !== null && ($next === null || $slot->lessThan($next))) {
                $next = $slot;
            }
        }

        if ($next === null) {
            return $this->result(self::NO_SLOT, 'warn', 'Sẵn sàng nhưng chưa còn giờ trống trong các ngày xếp trước (hết hạn mức ngày, ngoài khung giờ hoặc đã đủ bài chờ đăng)');
        }

        $local = $next->setTimezone('Asia/Ho_Chi_Minh');
        $when = $local->isSameDay($this->now->setTimezone('Asia/Ho_Chi_Minh')) ? $local->format('H:i') : $local->format('H:i d/m');

        return $this->result(self::READY, 'ok', "Sẵn sàng — chờ tới lượt (lượt kế tiếp ~{$when})", $next);
    }

    /** @return array{code: string, severity: string, reason: string, next_slot: ?string} */
    private function result(string $code, string $severity, string $reason, ?CarbonImmutable $slot = null): array
    {
        return ['code' => $code, 'severity' => $severity, 'reason' => $reason, 'next_slot' => $slot?->toIso8601String()];
    }

    /** @return array<string, array{auto: AutoAccount, name: string}> */
    private function eligibleChannels(): array
    {
        if ($this->eligible !== null) {
            return $this->eligible;
        }

        $this->eligible = [];

        foreach (AutoAccount::query()->get() as $auto) {
            $id = (string) $auto->social_account_id;
            $social = SocialAccount::query()->find($id);
            $name = $social ? '@'.($social->username ?: $social->display_name) : $id;

            $why = match (true) {
                ! $auto->enabled => "{$name} đang tắt tự động đăng",
                filled($auto->paused_reason) => "{$name} tạm dừng: {$auto->paused_reason}",
                $social === null || $social->platform !== Platform::TikTok => "{$name} không phải kênh TikTok",
                $social->status !== AccountStatus::Connected => "{$name} chưa kết nối",
                ! ChromeAccount::query()->where('social_account_id', $id)->where('enabled', true)->exists() => "{$name} chưa bật đăng qua Chrome",
                default => null,
            };

            if ($why === null) {
                $this->eligible[$id] = ['auto' => $auto, 'name' => $name];
            } else {
                $this->ineligible[$id] = $why;
            }
        }

        return $this->eligible;
    }

    /** @return array{allowed: array<string, list<?string>>, warnings: list<string>} */
    private function cartFor(string $id): array
    {
        return $this->carts[$id] ??= $this->cart->evaluate($id);
    }

    private function nextSlotFor(string $id): ?CarbonImmutable
    {
        if (array_key_exists($id, $this->nextSlot)) {
            return $this->nextSlot[$id];
        }

        $auto = $this->eligibleChannels()[$id]['auto'];
        $from = $this->now->addSeconds(Planner::MIN_LEAD)->startOfMinute()->addMinute();
        $slots = $this->planner->futureRoom($auto, $this->now) <= 0 ? [] : $this->planner->slotsFor($auto, $from, $this->planner->horizonFor($auto, $this->now));

        return $this->nextSlot[$id] = $slots[0] ?? null;
    }

    /** @return Collection<string, AutoProduct> */
    private function products(): Collection
    {
        return $this->products ??= AutoProduct::query()->get()->keyBy('code');
    }

    private function productName(?string $code): string
    {
        return (string) ($this->products()[$code]?->short_name ?? $code ?? '(chưa rõ sản phẩm)');
    }
}

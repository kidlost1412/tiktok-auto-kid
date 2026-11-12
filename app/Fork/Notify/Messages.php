<?php

declare(strict_types=1);

namespace App\Fork\Notify;

use Carbon\CarbonInterface;

/**
 * Dựng nội dung từng loại tin Telegram (HTML). Mỗi tin: dòng đầu mạnh (biểu tượng + chuyện gì xảy ra),
 * 2 đến 4 dòng dữ kiện, và một đường dẫn hành động khi cần. Chỉ dùng thẻ b, i, code, a mà Telegram cho phép.
 * Mọi hàm thuần (không đọc DB) để dễ kiểm thử và dùng cho tin mẫu.
 */
final class Messages
{
    /** Biểu tượng và tên nhóm cho từng loại (dùng khi gộp nhiều tin cùng loại). */
    public const array META = [
        'posted' => ['✅', 'bài đã lên'],
        'failed' => ['❌', 'bài lỗi'],
        'chrome_offline' => ['🔌', 'cảnh báo kết nối Chrome'],
        'hub_offline' => ['🔌', 'cảnh báo kết nối hub'],
        'cart' => ['🛒', 'giỏ hàng cần xử lý'],
        'stock' => ['📦', 'cảnh báo kho'],
        'buy_comment' => ['💬', 'khách hỏi mua'],
        'daily' => ['📊', 'tổng kết'],
        'highlight' => ['📈', 'video nổi bật'],
    ];

    public static function e(?string $s): string
    {
        return htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    /** Số kiểu Việt Nam: 12.340 hoặc 3,1. */
    public static function num(int|float $n, int $decimals = 0): string
    {
        return number_format($n, $decimals, ',', '.');
    }

    public static function appUrl(string $path = ''): string
    {
        return rtrim((string) config('app.url', 'http://localhost:8010'), '/').$path;
    }

    public static function tiktokUrl(?string $user, ?string $itemId): ?string
    {
        $user = ltrim((string) $user, '@');

        return $user !== '' && filled($itemId) ? "https://www.tiktok.com/@{$user}/video/{$itemId}" : null;
    }

    public static function snippet(?string $text, int $max = 70): string
    {
        $text = trim((string) preg_replace('/\s+/u', ' ', (string) $text));

        return $text === '' ? '(không có chú thích)' : mb_strimwidth($text, 0, $max, '…');
    }

    private static function link(string $label, ?string $url): string
    {
        return $url ? '<a href="'.self::e($url).'">'.self::e($label).'</a>' : '';
    }

    /** @param  list<string>  $links */
    private static function links(array $links): string
    {
        $links = array_values(array_filter($links));

        return $links === [] ? '' : "\n".implode(' · ', $links);
    }

    private static function who(?string $user): string
    {
        $user = ltrim((string) $user, '@');

        return $user === '' ? '' : ' · <b>@'.self::e($user).'</b>';
    }

    /** @param  array{user?: ?string, at: CarbonInterface, product?: ?string, cart?: ?string, item_id?: ?string, video_id?: ?int, caption?: ?string}  $d */
    public static function posted(array $d, string $key): Message
    {
        $user = $d['user'] ?? null;
        $tiktok = self::tiktokUrl($user, $d['item_id'] ?? null);
        $at = $d['at']->format('H:i d/m');

        $text = '✅ <b>Đã lên TikTok</b>'.self::who($user)
            ."\n🕘 <b>Giờ đăng:</b> <code>{$at}</code>"
            .(filled($d['product'] ?? null) ? "\n📦 <b>Sản phẩm:</b> ".self::e($d['product']) : '')
            ."\n🛒 <b>Giỏ hàng:</b> ".(filled($d['cart'] ?? null) ? 'đã gắn “'.self::e(self::snippet($d['cart'], 40)).'”' : 'không gắn')
            ."\n🎬 ".self::e(self::snippet($d['caption'] ?? null))
            .self::links([self::link('Xem trên TikTok', $tiktok), isset($d['video_id']) ? self::link('Mở trong app', self::appUrl('/auto/kho?tab=dang&video='.$d['video_id'])) : '']);

        return new Message('posted', $key, '@'.self::e(ltrim((string) $user, '@'))." · {$at} · ".self::e(self::snippet($d['product'] ?? $d['caption'] ?? null, 30)), $text);
    }

    /**
     * Lý do lỗi dễ hiểu + bước xử lý.
     *
     * @return array{0: string, 1: string}
     */
    public static function friendlyReason(string $raw, string $state = 'failed'): array
    {
        $raw = trim($raw);
        $low = mb_strtolower($raw);

        $map = [
            ['/hết hàng|out of stock|sold out/u', 'Sản phẩm trong giỏ đã hết hàng', 'Vào Giỏ hàng, chọn sản phẩm khác hoặc lưu lại liên kết.'],
            ['/đăng nhập|login|sai tài khoản|wrong account|khác tài khoản/u', 'Chrome đang đăng nhập sai tài khoản TikTok', 'Mở đúng profile Chrome của kênh và đăng nhập lại.'],
            ['/trùng|duplicate/u', 'TikTok báo video trùng nội dung', 'Không đăng lại video này, dùng video khác.'],
            ['/hết hạn|expired|token/u', 'Phiên đăng nhập TikTok đã hết hạn', 'Mở Chrome của kênh, đăng nhập lại TikTok.'],
            ['/quá lâu|timeout|timed out|treo|stalled|không phản hồi/u', 'Đăng quá lâu không xong', 'Kiểm tra Chrome còn mở, có mạng; app sẽ tự xếp lại nếu an toàn.'],
            ['/dung lượng|quá dài|too long|too large|định dạng|format/u', 'Video không đúng yêu cầu của TikTok (độ dài hoặc dung lượng)', 'Xuất lại video khác trong Xưởng Video.'],
        ];

        foreach ($map as [$re, $short, $step]) {
            if (preg_match($re, $low)) {
                return [$short, $step];
            }
        }

        return match ($state) {
            'uncertain' => ['Chưa rõ bài đã lên hay chưa (app không tự đăng lại)', 'Mở TikTok kiểm tra kênh; nếu đã lên thì bỏ qua.'],
            'rejected' => [$raw !== '' ? self::snippet($raw, 120) : 'TikTok từ chối bài này', 'Mở TikTok Studio xem chi tiết, sửa chú thích hoặc dùng video khác.'],
            default => [$raw !== '' ? self::snippet($raw, 120) : 'Chưa rõ nguyên nhân', 'Xem chi tiết ở trang Kết nối Chrome (mục bài gần đây); bấm đăng lại nếu cần.'],
        };
    }

    /** @param  array{user?: ?string, reason?: ?string, caption?: ?string, state?: string, file?: ?string, link?: ?string}  $d */
    public static function failed(array $d, string $key): Message
    {
        [$why, $fix] = self::friendlyReason((string) ($d['reason'] ?? ''), (string) ($d['state'] ?? 'failed'));
        $uncertain = ($d['state'] ?? '') === 'uncertain';
        $title = $uncertain ? '⚠️ <b>Chưa rõ kết quả đăng</b>' : '❌ <b>Đăng lỗi</b>';

        $text = $title.self::who($d['user'] ?? null)
            ."\n<b>Lý do:</b> ".self::e($why)
            ."\n🎬 ".self::e(self::snippet($d['caption'] ?? $d['file'] ?? null))
            ."\n👉 <b>Cách xử lý:</b> ".self::e($fix)
            .self::links([self::link('Mở Kết nối Chrome', $d['link'] ?? self::appUrl('/settings/chrome'))]);

        return new Message('failed', $key, '@'.self::e(ltrim((string) ($d['user'] ?? '?'), '@')).' · '.self::e(mb_strimwidth($why, 0, 50, '…')), $text);
    }

    public static function chromeOffline(string $who, ?CarbonInterface $since, string $key): Message
    {
        $text = '🔌 <b>Chrome mất kết nối</b> · <b>'.self::e($who).'</b>'
            .($since ? "\n🕘 <b>Từ:</b> <code>".$since->format('H:i d/m').'</code> ('.self::ago($since).')' : "\n🕘 Chưa từng thấy tiện ích kết nối")
            ."\n⏳ Còn bài chờ đăng, sẽ không đăng được cho tới khi kết nối lại"
            ."\n👉 <b>Cách xử lý:</b> mở Chrome (đúng profile của kênh)."
            .self::links([self::link('Mở Kết nối Chrome', self::appUrl('/settings/chrome'))]);

        return new Message('chrome_offline', $key, self::e($who).' mất kết nối', $text, 3600);
    }

    public static function chromeBack(string $who, int $minutes, string $key): Message
    {
        $text = '✅ <b>Chrome đã kết nối lại</b> · <b>'.self::e($who).'</b>'
            ."\n⏱ Mất kết nối khoảng <code>".self::duration($minutes).'</code>'
            ."\n▶️ Việc đăng bài đã tiếp tục bình thường.";

        return new Message('chrome_offline', $key, self::e($who).' đã kết nối lại sau '.self::duration($minutes), $text, 3600);
    }

    public static function hubOffline(string $label, string $key): Message
    {
        $text = '🔌 <b>Hub Xưởng Video mất kết nối</b>'
            ."\n<b>Tình trạng:</b> ".self::e($label)
            ."\n⏳ Video mới chưa về kho; bài đã xếp lịch vẫn đăng bình thường"
            ."\n👉 <b>Cách xử lý:</b> mở Xưởng Video (hub) trên máy."
            .self::links([self::link('Mở Kho video', self::appUrl('/auto/kho'))]);

        return new Message('hub_offline', $key, 'Hub mất kết nối', $text, 3600);
    }

    public static function hubBack(int $minutes, string $key): Message
    {
        $text = '✅ <b>Hub Xưởng Video đã kết nối lại</b>'
            ."\n⏱ Mất kết nối khoảng <code>".self::duration($minutes).'</code>'
            ."\n▶️ Video mới sẽ về kho trong lượt quét tới.";

        return new Message('hub_offline', $key, 'Hub đã kết nối lại sau '.self::duration($minutes), $text, 3600);
    }

    /** @param  array{user?: ?string, product?: ?string, code?: ?string, reason?: ?string}  $d */
    public static function cartPaused(array $d, string $key): Message
    {
        $reason = (string) ($d['reason'] ?? '');
        $out = (bool) preg_match('/hết hàng|out of stock|sold out/ui', $reason);
        $name = (string) (($d['product'] ?? null) ?: ($d['code'] ?? '?'));

        $text = '🛒 <b>'.($out ? 'Giỏ hàng hết hàng' : 'Giỏ hàng tạm dừng').'</b>'.self::who($d['user'] ?? null)
            ."\n📦 <b>Sản phẩm:</b> ".self::e($name).(filled($d['code'] ?? null) ? ' (<code>'.self::e($d['code']).'</code>)' : '')
            ."\n<b>Lý do:</b> ".self::e($out ? 'Sản phẩm hết hàng' : self::snippet($reason, 100))
            ."\n👉 <b>Cách xử lý:</b> chọn sản phẩm khác hoặc lưu lại liên kết; video của mã này tạm không đăng."
            .self::links([self::link('Mở Giỏ hàng', self::appUrl('/auto/gio-hang'))]);

        return new Message('cart', $key, '@'.self::e(ltrim((string) ($d['user'] ?? '?'), '@')).' · '.self::e($name), $text, 6 * 3600);
    }

    public static function stockLow(int $available, int $perDay, ?float $days, string $key): Message
    {
        $left = $days === null ? '' : ' đủ cho khoảng <code>'.self::num($days, 1).'</code> ngày';

        $text = '📦 <b>Kho sắp hết video</b>'
            ."\nCòn <code>{$available}</code> video mới{$left}"
            ."\n🎯 Mức đăng: <code>{$perDay}</code> bài/ngày (cộng các kênh đang bật)"
            ."\n👉 <b>Cách xử lý:</b> sản xuất thêm video trong Xưởng Video."
            .self::links([self::link('Mở Kho video', self::appUrl('/auto/kho'))]);

        return new Message('stock', $key, "Còn {$available} video, {$perDay} bài/ngày", $text, 6 * 3600);
    }

    /** @param  array{user?: ?string, author?: ?string, text: string, caption?: ?string, item_id?: ?string, video_id?: ?int}  $d */
    public static function buyComment(array $d, string $key): Message
    {
        $author = (string) ($d['author'] ?? '') ?: 'Khách';
        $tiktok = self::tiktokUrl($d['user'] ?? null, $d['item_id'] ?? null);

        $text = '💬 <b>Khách hỏi mua</b>'.self::who($d['user'] ?? null)
            ."\n<b>".self::e($author).':</b> “'.self::e(self::snippet($d['text'], 140)).'”'
            .(filled($d['caption'] ?? null) ? "\n🎬 ".self::e(self::snippet($d['caption'], 60)) : '')
            .self::links([self::link('Trả lời trên TikTok', $tiktok), isset($d['video_id']) ? self::link('Xem trong app', self::appUrl('/auto/kho?tab=dang&video='.$d['video_id'])) : self::link('Xem ở Số liệu', self::appUrl('/auto/so-lieu'))]);

        return new Message('buy_comment', $key, self::e($author).': '.self::e(self::snippet($d['text'], 50)), $text);
    }

    /** @param  array{user?: ?string, views: int, average: int, caption?: ?string, item_id?: ?string, video_id?: ?int}  $d */
    public static function highlight(array $d, string $key): Message
    {
        $times = $d['average'] > 0 ? $d['views'] / $d['average'] : 0;
        $tiktok = self::tiktokUrl($d['user'] ?? null, $d['item_id'] ?? null);

        $text = '📈 <b>Video nổi bật sau 24 giờ</b>'.self::who($d['user'] ?? null)
            ."\n👁 <code>".self::num($d['views']).'</code> lượt xem'.($times > 0 ? ', gấp <code>'.self::num($times, 1).'×</code> mức trung bình (<code>'.self::num($d['average']).'</code>)' : '')
            ."\n🎬 ".self::e(self::snippet($d['caption'] ?? null))
            .self::links([self::link('Xem video', $tiktok), isset($d['video_id']) ? self::link('Mở trong app', self::appUrl('/auto/kho?tab=dang&video='.$d['video_id'])) : '']);

        return new Message('highlight', $key, self::num($d['views']).' lượt · '.self::e(self::snippet($d['caption'] ?? null, 40)), $text);
    }

    /**
     * @param  array{
     *   date: CarbonInterface, posted: int, target: int, failed: int, views: int,
     *   top: list<array{views: int, user: ?string, caption: ?string, url: ?string}>,
     *   product: ?array{name: string, views: int}, buy_comments: int,
     *   tomorrow: ?array{count: int, first: string, last: string}, channels?: list<array{user: string, posted: int}>
     * }  $d
     */
    public static function daily(array $d, string $key): Message
    {
        $lines = ['📊 <b>Tổng kết ngày '.$d['date']->format('d/m').'</b>'];
        $lines[] = "✅ Đã đăng <code>{$d['posted']}/{$d['target']}</code> bài".($d['failed'] > 0 ? " · ❌ lỗi <code>{$d['failed']}</code>" : '');

        if (count($d['channels'] ?? []) > 1) {
            $lines[] = '📺 '.implode(' · ', array_map(fn (array $c): string => '@'.self::e(ltrim($c['user'], '@')).' <code>'.$c['posted'].'</code>', $d['channels']));
        }

        $lines[] = '👁 <code>'.self::num($d['views']).'</code> lượt xem (bài đăng trong 24 giờ qua)';

        if ($d['top'] !== []) {
            $lines[] = '🏆 <b>Top video</b>';

            foreach (array_slice($d['top'], 0, 3) as $i => $t) {
                $lines[] = ($i + 1).'. <code>'.self::num($t['views']).'</code> · '.self::e(self::snippet($t['caption'], 38))
                    .($t['url'] ? ' · '.self::link('xem', $t['url']) : '');
            }
        }

        if ($d['product']) {
            $lines[] = '🛒 <b>Sản phẩm chạy nhất:</b> '.self::e(self::snippet($d['product']['name'], 40)).' (<code>'.self::num($d['product']['views']).'</code> lượt)';
        }

        if ($d['buy_comments'] > 0) {
            $lines[] = "💬 Khách hỏi mua hôm nay: <code>{$d['buy_comments']}</code>";
        }

        $lines[] = $d['tomorrow']
            ? "🗓 <b>Ngày mai:</b> <code>{$d['tomorrow']['count']}</code> bài, từ <code>{$d['tomorrow']['first']}</code> đến <code>{$d['tomorrow']['last']}</code>"
            : '🗓 <b>Ngày mai:</b> chưa có bài nào được xếp lịch';

        $lines[] = self::link('Mở Tổng quan & Lịch', self::appUrl('/auto'));

        return new Message('daily', $key, 'Tổng kết '.$d['date']->format('d/m'), implode("\n", $lines), 2 * 86400);
    }

    /**
     * Nhiều tin cùng loại trong một lượt: gộp thành một tin gọn.
     *
     * @param  list<Message>  $items
     */
    public static function grouped(string $type, array $items, string $key): Message
    {
        [$icon, $name] = self::META[$type] ?? ['🔔', 'thông báo'];
        $shown = array_slice($items, 0, 10);
        $lines = ["{$icon} <b>".count($items)." {$name}</b> cùng lúc"];

        foreach ($shown as $m) {
            $lines[] = '• '.$m->headline;
        }

        if (count($items) > count($shown)) {
            $lines[] = '… và '.(count($items) - count($shown)).' mục nữa';
        }

        $lines[] = self::link('Mở app', self::appUrl('/auto'));

        return new Message($type, $key, count($items).' '.$name, implode("\n", $lines));
    }

    public static function duration(int $minutes): string
    {
        if ($minutes < 60) {
            return max(1, $minutes).' phút';
        }

        $h = intdiv($minutes, 60);
        $m = $minutes % 60;

        return $h.' giờ'.($m > 0 ? " {$m} phút" : '');
    }

    private static function ago(CarbonInterface $at): string
    {
        return self::duration((int) abs($at->diffInMinutes(now()))).' trước';
    }

    /**
     * Tin mẫu cho trang cài đặt (dữ liệu giả, không đụng DB).
     *
     * @return array<string, array{label: string, message: Message}>
     */
    public static function samples(): array
    {
        $now = now()->timezone((string) config('fork.telegram.timezone', 'Asia/Ho_Chi_Minh'));
        $url = 'https://www.tiktok.com/@kenh_mau/video/7000000000000000000';

        return [
            'posted' => ['label' => 'Bài đã lên', 'message' => self::posted(['user' => 'kenh_mau', 'at' => $now, 'product' => 'Phân bón hữu cơ 1kg', 'cart' => 'Phân bón hữu cơ 1kg', 'item_id' => '7000000000000000000', 'video_id' => 1, 'caption' => 'Cách bón phân cho cây ra hoa đều #nongnghiep'], 'sample')],
            'failed' => ['label' => 'Bài lỗi', 'message' => self::failed(['user' => 'kenh_mau', 'reason' => 'Sản phẩm hết hàng', 'caption' => 'Cách bón phân cho cây ra hoa đều #nongnghiep'], 'sample')],
            'chrome_offline' => ['label' => 'Chrome mất kết nối', 'message' => self::chromeOffline('@kenh_mau', $now->copy()->subMinutes(25), 'sample')],
            'chrome_back' => ['label' => 'Chrome kết nối lại', 'message' => self::chromeBack('@kenh_mau', 38, 'sample')],
            'hub_offline' => ['label' => 'Hub mất kết nối', 'message' => self::hubOffline('Hub đang tắt (mở Xưởng Video để lấy video mới)', 'sample')],
            'cart' => ['label' => 'Giỏ hàng hết hàng', 'message' => self::cartPaused(['user' => 'kenh_mau', 'product' => 'Phân bón hữu cơ 1kg', 'code' => 'SP01', 'reason' => 'Sản phẩm hết hàng'], 'sample')],
            'stock' => ['label' => 'Kho sắp hết video', 'message' => self::stockLow(6, 8, 0.8, 'sample')],
            'buy_comment' => ['label' => 'Khách hỏi mua', 'message' => self::buyComment(['user' => 'kenh_mau', 'author' => 'Chị Lan', 'text' => 'Giá bao nhiêu vậy shop, ship về Đà Nẵng được không?', 'caption' => 'Cách bón phân cho cây ra hoa đều', 'item_id' => '7000000000000000000', 'video_id' => 1], 'sample')],
            'highlight' => ['label' => 'Video nổi bật 24h', 'message' => self::highlight(['user' => 'kenh_mau', 'views' => 12400, 'average' => 4000, 'caption' => 'Cách bón phân cho cây ra hoa đều', 'item_id' => '7000000000000000000', 'video_id' => 1], 'sample')],
            'daily' => ['label' => 'Tổng kết ngày', 'message' => self::daily([
                'date' => $now, 'posted' => 6, 'target' => 8, 'failed' => 1, 'views' => 21840,
                'top' => [
                    ['views' => 12400, 'user' => 'kenh_mau', 'caption' => 'Cách bón phân cho cây ra hoa đều', 'url' => $url],
                    ['views' => 5200, 'user' => 'kenh_mau', 'caption' => 'Mẹo tưới cây mùa nắng', 'url' => $url],
                    ['views' => 2100, 'user' => 'kenh_mau', 'caption' => 'Chọn đất trồng chậu', 'url' => $url],
                ],
                'product' => ['name' => 'Phân bón hữu cơ 1kg', 'views' => 12400], 'buy_comments' => 3,
                'tomorrow' => ['count' => 7, 'first' => '08:15', 'last' => '21:40'],
            ], 'sample')],
        ];
    }
}

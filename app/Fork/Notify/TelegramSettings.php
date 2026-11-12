<?php

declare(strict_types=1);

namespace App\Fork\Notify;

use App\Fork\AutoPost\Models\AutoSetting;
use Illuminate\Support\Facades\Crypt;
use Throwable;

/**
 * Cấu hình Telegram lưu trong DB (bảng fork_auto_settings): token bot được mã hoá (Crypt),
 * phần còn lại là tuỳ chọn thường. Biến môi trường FORK_TELEGRAM_* chỉ là dự phòng khi DB chưa có.
 */
final class TelegramSettings
{
    private const string TOKEN = 'telegram.bot_token';

    private const string PREFS = 'telegram.prefs';

    /** Các loại tin: khoá => [nhãn, khẩn cấp (không bị giữ trong giờ yên tĩnh)]. */
    public const array TYPES = [
        'posted' => ['Đăng thành công', false],
        'failed' => ['Đăng lỗi', true],
        'chrome_offline' => ['Chrome mất kết nối', true],
        'hub_offline' => ['Hub mất kết nối', true],
        'cart' => ['Giỏ hàng tạm dừng / hết hàng', false],
        'stock' => ['Kho sắp hết video', false],
        'buy_comment' => ['Bình luận hỏi mua', false],
        'daily' => ['Tổng kết ngày', false],
        'highlight' => ['Số liệu 24h nổi bật', false],
    ];

    /** @return array<string, mixed> */
    private static function prefs(): array
    {
        $raw = AutoSetting::read(self::PREFS);
        $data = $raw ? json_decode($raw, true) : null;

        return is_array($data) ? $data : [];
    }

    /** @param  array<string, mixed>  $patch */
    private static function savePrefs(array $patch): void
    {
        AutoSetting::write(self::PREFS, json_encode(array_replace(self::prefs(), $patch), JSON_UNESCAPED_UNICODE));
    }

    public static function token(): string
    {
        $raw = AutoSetting::read(self::TOKEN);

        if ($raw) {
            try {
                return trim(Crypt::decryptString($raw));
            } catch (Throwable) {
                // Khoá app đổi: coi như chưa có, rơi về .env.
            }
        }

        return trim((string) config('fork.telegram.bot_token', ''));
    }

    public static function chatId(): string
    {
        $id = (string) (self::prefs()['chat_id'] ?? '');

        return $id !== '' ? $id : trim((string) config('fork.telegram.chat_id', ''));
    }

    public static function configured(): bool
    {
        return self::token() !== '' && self::chatId() !== '';
    }

    public static function hasToken(): bool
    {
        return self::token() !== '';
    }

    /** Token che gần hết, không bao giờ trả đầy đủ ra giao diện. */
    public static function maskedToken(): ?string
    {
        $token = self::token();

        if ($token === '') {
            return null;
        }

        [$id] = explode(':', $token, 2) + [''];

        return $id.':••••••••'.substr($token, -4);
    }

    public static function saveToken(string $token, ?string $botUsername): void
    {
        AutoSetting::write(self::TOKEN, Crypt::encryptString(trim($token)));
        self::savePrefs(['bot_username' => $botUsername]);
    }

    public static function saveChat(string $chatId, ?string $name): void
    {
        self::savePrefs(['chat_id' => trim($chatId), 'chat_name' => $name]);
    }

    public static function clear(): void
    {
        AutoSetting::query()->whereIn('key', [self::TOKEN, self::PREFS])->delete();
    }

    public static function botUsername(): ?string
    {
        $u = self::prefs()['bot_username'] ?? null;

        return is_string($u) && $u !== '' ? ltrim($u, '@') : null;
    }

    public static function chatName(): ?string
    {
        $n = self::prefs()['chat_name'] ?? null;

        return is_string($n) && $n !== '' ? $n : null;
    }

    public static function enabled(string $type): bool
    {
        $toggles = self::prefs()['toggles'] ?? [];

        return ! is_array($toggles) || ! array_key_exists($type, $toggles) || (bool) $toggles[$type];
    }

    /** @return array<string, bool> */
    public static function toggles(): array
    {
        return collect(array_keys(self::TYPES))->mapWithKeys(fn (string $t): array => [$t => self::enabled($t)])->all();
    }

    public static function urgent(string $type): bool
    {
        return (bool) (self::TYPES[$type][1] ?? false);
    }

    public static function summaryTime(): string
    {
        $t = (string) (self::prefs()['summary_time'] ?? '');

        return self::validTime($t) ? $t : sprintf('%02d:00', (int) config('fork.telegram.summary_hour', 21));
    }

    /** @return array{enabled: bool, start: string, end: string} */
    public static function quiet(): array
    {
        $q = self::prefs()['quiet'] ?? [];
        $q = is_array($q) ? $q : [];

        return [
            'enabled' => (bool) ($q['enabled'] ?? false),
            'start' => self::validTime((string) ($q['start'] ?? '')) ? $q['start'] : '23:00',
            'end' => self::validTime((string) ($q['end'] ?? '')) ? $q['end'] : '06:00',
        ];
    }

    /** @param  array<string, bool>  $toggles */
    public static function savePrefsFromForm(array $toggles, string $summaryTime, bool $quietEnabled, string $quietStart, string $quietEnd): void
    {
        $clean = [];

        foreach (array_keys(self::TYPES) as $t) {
            $clean[$t] = (bool) ($toggles[$t] ?? true);
        }

        self::savePrefs([
            'toggles' => $clean,
            'summary_time' => self::validTime($summaryTime) ? $summaryTime : '21:00',
            'quiet' => ['enabled' => $quietEnabled, 'start' => $quietStart, 'end' => $quietEnd],
        ]);
    }

    /** Đang trong giờ yên tĩnh (giờ địa phương của app)? */
    public static function inQuietHours(?\DateTimeInterface $at = null): bool
    {
        $q = self::quiet();

        if (! $q['enabled']) {
            return false;
        }

        $tz = (string) config('fork.telegram.timezone', 'Asia/Ho_Chi_Minh');
        $now = ($at ? \Carbon\CarbonImmutable::instance($at) : \Carbon\CarbonImmutable::now())->timezone($tz);
        $min = $now->hour * 60 + $now->minute;
        $start = self::minutes($q['start']);
        $end = self::minutes($q['end']);

        if ($start === $end) {
            return false;
        }

        return $start < $end ? ($min >= $start && $min < $end) : ($min >= $start || $min < $end);
    }

    /** Mốc bắt đầu theo dõi: chỉ báo các sự kiện sau mốc này (tránh dồn một loạt tin cũ khi mới bật). */
    public static function since(): \Carbon\CarbonImmutable
    {
        $ts = (int) (self::prefs()['since'] ?? 0);

        if ($ts <= 0) {
            $ts = now()->subHour()->getTimestamp();
            self::savePrefs(['since' => $ts]);
        }

        return \Carbon\CarbonImmutable::createFromTimestamp($ts);
    }

    public static function validTime(string $t): bool
    {
        return preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $t) === 1;
    }

    private static function minutes(string $t): int
    {
        [$h, $m] = array_map('intval', explode(':', $t));

        return $h * 60 + $m;
    }
}

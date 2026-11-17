<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use App\Fork\AutoPost\Models\AutoVideo;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;

/**
 * Tình hình "AI xem video Kho riêng" cho dòng trạng thái trên trang: đang xem video nào, còn bao nhiêu video chờ,
 * video nào lỗi và khi nào thử lại, lượt chạy gần nhất ra sao. Chủ app nhìn là biết AI đang làm hay đang kẹt ở đâu.
 */
final class RiengAiStatus
{
    /** Nhịp của lệnh fork:rieng-ai (ghi lúc bắt đầu / mỗi video / lúc xong). */
    public const string KEY = 'fork-rieng:ai-run';

    /** Lịch chạy mỗi 2 phút: quá ngần này phút không thấy nhịp mà vẫn còn video chờ thì coi như AI không chạy. */
    public const int STALE_MINUTES = 6;

    private const string TZ = 'Asia/Ho_Chi_Minh';

    /** @param array<string, mixed> $data */
    public static function beat(array $data): void
    {
        Cache::put(self::KEY, $data + ['luc' => now()->toIso8601String()], now()->addDays(3));
    }

    /** Giờ ngắn kiểu "14:05" (hoặc "14:05 18/11" nếu khác ngày) theo giờ Việt Nam. */
    public static function clock(string $iso, ?CarbonImmutable $now = null): string
    {
        $t = CarbonImmutable::parse($iso)->setTimezone(self::TZ);
        $n = ($now ?? CarbonImmutable::now())->setTimezone(self::TZ);

        return $t->format($t->isSameDay($n) ? 'H:i' : 'H:i d/m');
    }

    /** @return array<string, mixed> */
    public static function get(ChatGptAccounts $accounts, ?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $nowIso = $now->utc()->toIso8601String();
        $videos = AutoVideo::query()->where('source', AutoVideo::SOURCE_RIENG)->where('status', AutoVideo::NEW)
            ->whereNull('files_deleted_at')
            ->get(['id', 'file_name', 'meta', 'product_code']);

        $running = null;
        $queued = 0;
        $waiting = 0;
        $nextTry = null;
        $lastError = null;
        $gaveUp = 0;
        $unsure = 0;

        foreach ($videos as $v) {
            $ai = (array) data_get($v->meta, 'ai', []);
            $dang = $ai['dang'] ?? null;

            if (is_array($dang) && CarbonImmutable::parse((string) ($dang['luc'] ?? 'now'))->diffInMinutes($now, true) < 40) {
                // Đã có bước (tong > 0) là đang xem thật; chỉ "đang chờ AI" thì tính vào hàng chờ.
                if (! empty($dang['tong']) && $running === null) {
                    $running = ['id' => $v->id, 'file_name' => $v->file_name, 'buoc' => (int) $dang['buoc'], 'tong' => (int) $dang['tong'], 'viec' => (string) ($dang['viec'] ?? '')];
                } elseif (empty($dang['tong'])) {
                    $queued++;
                }

                continue;
            }

            $state = $ai['state'] ?? null;

            if ($state === null || ($state === 'error' && (string) ($ai['next_try_at'] ?? '') <= $nowIso)) {
                $queued++;
            } elseif ($state === 'error') {
                $waiting++;
                $nextTry = $nextTry === null || $ai['next_try_at'] < $nextTry ? $ai['next_try_at'] : $nextTry;
                $lastError ??= $ai['error'] ?? null;
            } elseif (filled($v->product_code)) {
                continue;
            } elseif ($state === 'gave_up') {
                $gaveUp++;
            } elseif ($state === 'unsure') {
                $unsure++;
            }
        }

        $beat = Cache::get(self::KEY);
        $beat = is_array($beat) ? $beat : null;
        $beatAge = $beat !== null ? CarbonImmutable::parse((string) $beat['luc'])->diffInMinutes($now, true) : null;
        $list = $accounts->all($now);
        $ready = array_values(array_filter($list, fn (array $a): bool => $a['ready']));
        $free = array_values(array_filter($ready, fn (array $a): bool => $a['cooldown_until'] === null));
        $cli = $accounts->cliStatus()['installed'];

        $out = [
            'running' => $running,
            'queued' => $queued,
            'waiting' => $waiting,
            'next_try_at' => $nextTry,
            'last_error' => $lastError,
            'gave_up' => $gaveUp,
            'unsure' => $unsure,
            'last_run' => $beat,
            'can_run' => false,
        ];

        // Thứ tự ưu tiên: đang xem > thiếu thứ cần có > còn video chờ > video lỗi chờ thử lại > xong hết.
        if ($running !== null) {
            $more = $queued > 0 ? " · còn {$queued} video chờ" : '';

            return $out + ['tone' => 'info', 'title' => "AI đang xem {$running['file_name']} (bước {$running['buoc']}/{$running['tong']}){$more}", 'detail' => $running['viec']];
        }

        $todo = $queued + $waiting;

        if ($todo === 0) {
            $parts = array_filter([$unsure ? "{$unsure} video AI chưa chắc, anh chọn giúp sản phẩm" : null, $gaveUp ? "{$gaveUp} video AI không xem được" : null]);

            return $out + ['tone' => $parts === [] ? 'success' : 'warn', 'title' => 'AI đã xem hết video mới', 'detail' => $parts === [] ? null : implode(' · ', $parts)];
        }

        if (! $cli) {
            return $out + ['tone' => 'warn', 'title' => "{$todo} video chờ AI xem, nhưng máy chưa cài ChatGPT", 'detail' => 'Mở "Tự đăng theo khung" để cài ChatGPT CLI và đăng nhập tài khoản.', 'fix' => 'settings'];
        }

        if ($ready === []) {
            return $out + ['tone' => 'warn', 'title' => "{$todo} video chờ AI xem, nhưng chưa có tài khoản ChatGPT nào đăng nhập", 'detail' => 'Mở "Tự đăng theo khung" để thêm tài khoản ChatGPT.', 'fix' => 'settings'];
        }

        if ($free === []) {
            $until = min(array_column($ready, 'cooldown_until'));

            return $out + ['tone' => 'warn', 'title' => "{$todo} video chờ AI xem: tài khoản ChatGPT đang hết lượt", 'detail' => 'AI xem tiếp lúc '.self::clock($until, $now).'. Thêm tài khoản khác thì xem được ngay.', 'fix' => 'settings'];
        }

        $out['can_run'] = true;

        if ($queued > 0) {
            $stale = $beatAge === null || $beatAge >= self::STALE_MINUTES;
            $detail = $stale
                ? ($beat === null ? 'AI chưa chạy lượt nào. Bấm "Cho AI xem ngay".' : 'Lượt gần nhất lúc '.self::clock((string) $beat['luc'], $now).', lâu rồi chưa thấy chạy lại. Bấm "Cho AI xem ngay".')
                : ($beat['note'] ?? null ? 'Lượt gần nhất: '.$beat['note'].'. ' : '').'Lượt tới trong khoảng 2 phút.';

            return $out + ['tone' => $stale ? 'warn' : 'info', 'title' => "{$queued} video đang chờ AI xem".($waiting ? " · {$waiting} video chờ thử lại" : ''), 'detail' => $detail];
        }

        return $out + [
            'tone' => 'warn',
            'title' => "{$waiting} video AI chưa xem được, sẽ thử lại lúc ".self::clock((string) $nextTry, $now),
            'detail' => $lastError !== null ? 'Lỗi: '.$lastError : null,
        ];
    }
}

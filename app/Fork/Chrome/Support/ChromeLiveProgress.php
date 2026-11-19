<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Support;

use Illuminate\Support\Facades\Cache;
use Throwable;

/**
 * Tiến độ tải/đăng mới nhất mà tiện ích Chrome báo qua /api/ext/progress (pct, msg, phase), giữ trong bộ đệm 30 phút,
 * KHÔNG ghi DB. Chỉ để Khu Tự Trị hiện tiến độ thật; lỗi ở đây không bao giờ làm hỏng nhịp tim của job.
 */
final class ChromeLiveProgress
{
    private const int TTL_SECONDS = 1800;

    private const int RING = 6;

    public static function key(string $jobId): string
    {
        return 'fork:chrome:progress:'.$jobId;
    }

    /** @param array<string, mixed> $body thân yêu cầu progress của tiện ích (đã giải JSON) */
    public static function record(string $jobId, array $body): void
    {
        try {
            $pct = $body['pct'] ?? null;
            $pct = (is_int($pct) || is_float($pct)) && is_finite((float) $pct) && $pct >= 0 && $pct <= 100 ? (float) $pct : null;
            $msg = is_string($body['msg'] ?? null) ? trim($body['msg']) : '';
            $msg = $msg !== '' && mb_strlen($msg) <= 160 ? $msg : null;
            $phase = is_string($body['phase'] ?? null) && preg_match('/^[a-z][a-z-]{0,23}$/', $body['phase']) === 1 ? $body['phase'] : null;
            $msg = $msg === null ? null : self::human($phase, $msg);
            if ($pct === null && $msg === null) {
                return;
            }

            $prev = self::get($jobId) ?? ['pct' => null, 'msg' => null, 'phase' => null, 'hist' => []];
            $hist = $prev['hist'];
            if ($msg !== null && ($hist === [] || end($hist) !== $msg)) {
                $hist[] = $msg;
            }
            Cache::put(self::key($jobId), [
                'pct' => $pct ?? $prev['pct'],
                'msg' => $msg ?? $prev['msg'],
                'phase' => $msg !== null ? $phase : $prev['phase'],
                'at' => microtime(true),
                'hist' => array_slice($hist, -self::RING),
            ], self::TTL_SECONDS);
        } catch (Throwable) {
            // tiến độ chỉ để xem, bỏ qua mọi lỗi
        }
    }

    /**
     * Câu người đọc được cho các bước đáng kể; bước kỹ thuật (sts, HTTP, SDK...) trả null (vẫn nhận pct nhưng không hiện lời).
     */
    private static function human(?string $phase, string $msg): ?string
    {
        if ($phase === 'transfer' && preg_match('/^part (\d{1,4})\/(\d{1,4})$/', $msg, $m) === 1) {
            return "Đang tải phần {$m[1]}/{$m[2]} của video lên TikTok";
        }
        if ($phase === 'start') {
            return 'Bắt đầu tải video lên TikTok';
        }
        if (in_array($phase, ['cover', 'product', 'post', 'ready'], true)) {
            $t = trim((string) preg_replace(['/^WARN\s+/', '/\s\d{6,}$/'], '', $msg));

            return $t === '' ? null : mb_strtoupper(mb_substr($t, 0, 1)).mb_substr($t, 1);
        }

        return null;
    }

    /** @return array{pct: float|null, msg: string|null, phase: string|null, at: float, hist: list<string>}|null */
    public static function get(string $jobId): ?array
    {
        try {
            $v = Cache::get(self::key($jobId));
        } catch (Throwable) {
            return null;
        }

        return is_array($v) && isset($v['hist']) ? $v : null;
    }
}

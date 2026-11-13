<?php

declare(strict_types=1);

namespace App\Fork\Update;

use Illuminate\Support\Facades\Http;
use Throwable;

/** Gọi API điều khiển của launcher (127.0.0.1, header X-TTA-Token lấy từ runtime/control.token). */
final class LauncherClient
{
    private const string NO_LAUNCHER = 'Không liên lạc được launcher. Hãy mở TikTok Auto Kid bằng TikTokAuto.exe rồi thử lại.';

    public static function port(): int
    {
        return (int) config('fork-update.launcher_port');
    }

    public static function currentVersion(): string
    {
        $file = (string) config('fork-update.version_file');
        $v = is_file($file) ? trim((string) file_get_contents($file)) : '';

        return preg_match('/^v?\d+(\.\d+){0,2}([-+][0-9A-Za-z.]+)?$/', $v) === 1 ? ltrim($v, 'vV') : '0.0.0';
    }

    public static function repoConfigured(): bool
    {
        $repo = trim((string) config('fork-update.repo'));

        return preg_match('#^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$#', $repo) === 1
            && ! str_starts_with(strtoupper($repo), 'CHUA_CAU_HINH/')
            && ! str_starts_with($repo, '.') && ! str_contains($repo, '/.');
    }

    /** Trạng thái cập nhật của launcher (không cần token) hoặc null nếu không liên lạc được. */
    public static function status(): ?array
    {
        try {
            $r = Http::timeout(3)->connectTimeout(1)->acceptJson()->get(self::url('/api/update/status'));
        } catch (Throwable) {
            return null;
        }

        return $r->successful() && is_array($r->json()) ? $r->json() : null;
    }

    /** @return array{ok: bool, error: ?string, data: ?array, status?: int} */
    public static function post(string $path, array $body = [], int $timeout = 30): array
    {
        $file = (string) config('fork-update.token_file');
        $token = is_file($file) ? trim((string) file_get_contents($file)) : '';

        if ($token === '') {
            return ['ok' => false, 'error' => self::NO_LAUNCHER, 'data' => null];
        }

        try {
            $req = Http::timeout($timeout)->connectTimeout(2)->acceptJson()->withHeaders(['X-TTA-Token' => $token]);
            $r = $body === [] ? $req->post(self::url($path)) : $req->asJson()->post(self::url($path), $body);
        } catch (Throwable) {
            return ['ok' => false, 'error' => self::NO_LAUNCHER, 'data' => null];
        }

        if (! $r->successful()) {
            return ['ok' => false, 'error' => (string) ($r->json('error') ?: 'Launcher từ chối yêu cầu.'), 'data' => null, 'status' => $r->status()];
        }

        return ['ok' => true, 'error' => null, 'data' => $r->json(), 'status' => $r->status()];
    }

    private static function url(string $path): string
    {
        return sprintf('http://127.0.0.1:%d%s', self::port(), $path);
    }
}

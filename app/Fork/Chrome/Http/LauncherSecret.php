<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Http;

use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Xác thực trợ lý Windows bằng header X-Fork-Launcher-Secret.
 * Secret trong cấu hình rỗng thì từ chối tất cả.
 */
final class LauncherSecret
{
    public function handle(Request $request, Closure $next): Response
    {
        $secret = (string) config('fork.chrome.launcher_secret', '');
        $given = (string) $request->header('X-Fork-Launcher-Secret', '');

        if ($secret === '' || $given === '' || ! hash_equals($secret, $given)) {
            return new JsonResponse(
                ['ok' => false, 'error' => 'forbidden', 'message' => 'Sai hoặc thiếu mã bí mật của trợ lý mở Chrome.'],
                403,
            );
        }

        return $next($request);
    }
}

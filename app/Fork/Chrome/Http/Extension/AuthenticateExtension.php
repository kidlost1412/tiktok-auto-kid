<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Http\Extension;

use App\Fork\Chrome\ChromeJobs;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * Xác thực Bearer của tiện ích, đánh dấu "vừa thấy" Chrome này ở mỗi request.
 */
final class AuthenticateExtension
{
    public const CLIENT_ATTRIBUTE = 'chrome_client';

    public function handle(Request $request, Closure $next): Response
    {
        $header = (string) $request->headers->get('Authorization', '');
        $token = str_starts_with($header, 'Bearer ') ? substr($header, 7) : '';

        $chrome = app(ChromeJobs::class);
        $client = $token === '' ? null : $chrome->clientForToken($token);

        if ($client === null) {
            throw new ExtError(401, 'unauthorized', 'Cần ghép nối lại tiện ích với ứng dụng');
        }

        $chrome->touch($client, self::protocolOf($request));
        $request->attributes->set(self::CLIENT_ATTRIBUTE, $client);

        return $next($request);
    }

    public static function protocolOf(Request $request): int
    {
        $value = (string) $request->headers->get('X-Autotok-Protocol', '0');

        return preg_match('/^\s*-?\d+\s*$/', $value) === 1 ? (int) $value : 0;
    }
}

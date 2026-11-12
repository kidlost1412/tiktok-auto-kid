<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Http\Extension;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * CORS cho /api/ext/*: chỉ origin của tiện ích mới được thêm header.
 * Header CORS do lớp CORS chung của Laravel (cho phép mọi origin) thêm vào bị gỡ để
 * origin lạ không nhận được gì.
 */
final class ExtensionCors
{
    public const ALLOW_HEADERS = 'Authorization, Content-Type, X-Requested-With, X-Autotok-Protocol, Range';

    public const EXPOSE_HEADERS = 'Content-Range, Content-Length, Accept-Ranges';

    public function handle(Request $request, Closure $next): Response
    {
        if (! $request->is('api/ext/*')) {
            return $next($request);
        }

        $allowed = $this->allowedOrigin();
        $origin = $request->headers->get('Origin');
        $matches = $allowed !== '' && $origin === $allowed;

        if ($matches && $request->isMethod('OPTIONS') && $request->headers->has('Access-Control-Request-Method')) {
            $response = new Response('', 204);
            $response->headers->set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
            $response->headers->set('Access-Control-Allow-Headers', self::ALLOW_HEADERS);
            $response->headers->set('Access-Control-Max-Age', '600');

            return $this->decorate($response, $allowed);
        }

        $response = $next($request);

        foreach (array_keys($response->headers->all()) as $name) {
            if (str_starts_with(strtolower((string) $name), 'access-control-')) {
                $response->headers->remove((string) $name);
            }
        }

        return $matches ? $this->decorate($response, $allowed) : $response;
    }

    private function decorate(Response $response, string $origin): Response
    {
        $response->headers->set('Access-Control-Allow-Origin', $origin);
        $response->headers->set('Vary', 'Origin', false);
        $response->headers->set('Access-Control-Expose-Headers', self::EXPOSE_HEADERS);

        return $response;
    }

    private function allowedOrigin(): string
    {
        return (string) config('fork.chrome.extension_origin', '');
    }
}

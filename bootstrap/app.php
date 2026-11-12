<?php

declare(strict_types=1);

use App\Fork\SingleUser\AutoLoginOwner;
use App\Http\Middleware\App\HandleInertiaRequests;
use App\Http\Middleware\App\SetLocale;
use Illuminate\Contracts\Auth\Middleware\AuthenticatesRequests;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Middleware\AddLinkHeadersForPreloadedAssets;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->web(append: [
            AutoLoginOwner::class,
            SetLocale::class,
            HandleInertiaRequests::class,
            AddLinkHeadersForPreloadedAssets::class,
        ]);

        // Phải đăng nhập chủ app trước khi middleware `auth` của route chạy.
        $middleware->prependToPriorityList(before: AuthenticatesRequests::class, prepend: AutoLoginOwner::class);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(fn (Request $request, Throwable $e): bool => $request->is('api/*') || $request->expectsJson());
    })->create();

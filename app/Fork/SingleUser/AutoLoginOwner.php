<?php

declare(strict_types=1);

namespace App\Fork\SingleUser;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Symfony\Component\HttpFoundation\Response;

/**
 * Chế độ một người dùng: chỉ nhận request từ loopback (nếu không thì 403) và tự đăng nhập chủ app.
 */
final class AutoLoginOwner
{
    public function handle(Request $request, Closure $next): Response
    {
        if (! SingleUser::enabled()) {
            return $next($request);
        }

        abort_unless(SingleUser::isLoopback($request), Response::HTTP_FORBIDDEN);

        if (! Auth::check()) {
            Auth::login(SingleUser::ensureOwner());
        }

        return $next($request);
    }
}

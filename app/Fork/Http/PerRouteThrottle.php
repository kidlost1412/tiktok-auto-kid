<?php

declare(strict_types=1);

namespace App\Fork\Http;

use Illuminate\Routing\Middleware\ThrottleRequests;

/**
 * `throttle:N,M` mặc định của Laravel đếm chung MỘT bộ đếm cho mọi đường dẫn của cùng người dùng: trang Kho riêng
 * tự hỏi máy chủ vài giây một lần (quét nhanh, chờ hộp chọn thư mục...) làm bộ đếm chung đầy, rồi nút khác có giới hạn
 * thấp hơn (vd. "Chọn thư mục" 20/phút) bị chặn 429 dù chủ app mới bấm một lần. Ở đây mỗi đường dẫn có bộ đếm riêng.
 */
class PerRouteThrottle extends ThrottleRequests
{
    protected function resolveRequestSignature($request)
    {
        $route = $request->route();
        $name = $route === null ? '' : ($route->getName() ?? $request->method().' '.$route->uri());

        return sha1(parent::resolveRequestSignature($request).'|'.$name);
    }
}

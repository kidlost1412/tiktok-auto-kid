<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Media\RemoteImage;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Models\SocialAccount;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

/** Phục vụ ảnh sản phẩm đã tải về máy cho giao diện /auto (chỉ ảnh của kênh thuộc chủ tài khoản). */
final class MediaController
{
    use ScopesToOwner;

    public function productImage(Request $request, ShopProduct $shopProduct): BinaryFileResponse
    {
        $accountId = $this->authorizeOwner($request);

        abort_unless(
            $this->tiktokAccounts($accountId)->contains(fn (SocialAccount $a): bool => (string) $a->id === (string) $shopProduct->social_account_id),
            SymfonyResponse::HTTP_NOT_FOUND,
        );

        $file = app(ProductImages::class)->file($shopProduct);

        abort_if($file === null, SymfonyResponse::HTTP_NOT_FOUND);

        return response()->file($file, [
            'Content-Type' => RemoteImage::mime(strtolower(pathinfo($file, PATHINFO_EXTENSION))),
            // Tên file đã gắn mã băm của link ảnh nên URL có ?v=... đổi khi ảnh đổi.
            'Cache-Control' => 'private, max-age=86400',
        ]);
    }
}

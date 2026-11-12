<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Http\Extension\AuthenticateExtension;
use App\Fork\Chrome\Models\ChromeClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/**
 * POST /api/ext/sync_status: tiện ích báo lần lấy sản phẩm shop bị lỗi (kèm lý do) để trang Giỏ hàng hiện rõ.
 * Body: {request_id, ok: false, reason}. Chỉ ghi khi request_id vẫn là yêu cầu đang chờ của kênh gắn với Chrome này.
 */
final class SyncStatusController
{
    public function __invoke(Request $request, ChromeJobs $chrome, ShopSync $shop): JsonResponse
    {
        /** @var ChromeClient $client */
        $client = $request->attributes->get(AuthenticateExtension::CLIENT_ATTRIBUTE);
        $account = filled($client->tiktok_user_id) ? $chrome->boundAccount((string) $client->tiktok_user_id) : null;
        $body = json_decode($request->getContent(), true);
        $body = is_array($body) ? $body : [];

        $requestId = is_string($body['request_id'] ?? null) ? mb_substr($body['request_id'], 0, 64) : '';
        $reason = is_string($body['reason'] ?? null) ? $body['reason'] : '';
        $recorded = false;

        if ($account !== null && ($body['ok'] ?? null) === false) {
            $recorded = $shop->reportFailure((string) $account->social_account_id, $requestId, self::describe($reason));
        }

        return response()->json(['ok' => true, 'recorded' => $recorded]);
    }

    /** Lý do kỹ thuật của tiện ích thành câu tiếng Việt dễ hiểu. */
    public static function describe(string $reason): string
    {
        $known = [
            'sync-timeout' => 'tiện ích mở TikTok Studio nhưng quá 4 phút không lấy được sản phẩm',
            'tab-closed' => 'cửa sổ TikTok Studio bị đóng giữa chừng',
            'open-window-failed' => 'tiện ích không mở được cửa sổ TikTok Studio',
            'identity-unknown' => 'Chrome chưa đăng nhập TikTok Studio',
            'gave-up' => 'tiện ích đã thử 3 lần mà vẫn không lấy được',
        ];

        $reason = trim($reason);

        return $known[$reason] ?? ($reason === '' ? 'không rõ lý do' : mb_substr($reason, 0, 200));
    }
}

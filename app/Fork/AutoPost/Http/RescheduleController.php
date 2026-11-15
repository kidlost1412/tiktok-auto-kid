<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Scheduling\Reschedules;
use App\Http\Controllers\Controller;
use Carbon\CarbonImmutable;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use RuntimeException;
use Throwable;

/**
 * "Đổi giờ" một bài đã xếp lịch mà chưa đăng (Lịch đăng, trang Tổng quan). JSON cho hộp thoại; logic ở Reschedules.
 */
final class RescheduleController extends Controller
{
    use ScopesToOwner;

    public function show(Request $request, AutoVideo $video, Reschedules $reschedules): JsonResponse
    {
        $this->own($request, $video);

        return response()->json($reschedules->describe($video));
    }

    public function store(Request $request, AutoVideo $video, Reschedules $reschedules): JsonResponse
    {
        $this->own($request, $video);
        $data = $request->validate(['at' => ['required', 'string', 'max:40']]);

        try {
            $at = CarbonImmutable::parse($data['at'])->utc();
        } catch (Throwable) {
            return response()->json(['ok' => false, 'message' => 'Giờ mới không hợp lệ.'], 422);
        }

        try {
            $result = $reschedules->request($video, $at);
        } catch (RuntimeException $e) {
            return response()->json(['ok' => false, 'message' => $e->getMessage(), ...$reschedules->describe($video->refresh())], 422);
        }

        return response()->json(['ok' => true, ...$result, ...$reschedules->describe($video->refresh())]);
    }

    private function own(Request $request, AutoVideo $video): void
    {
        $accounts = $this->tiktokAccounts($this->authorizeOwner($request));

        abort_if($video->social_account_id === null || ! $accounts->contains('id', $video->social_account_id), 404);
    }
}

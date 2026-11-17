<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Scheduling\Trash;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use RuntimeException;

/** Thùng rác video (JSON): xem, khôi phục, xoá hẳn từng video hoặc dọn sạch. Chỉ chủ app. */
final class TrashController extends Controller
{
    use ScopesToOwner;

    public function index(Request $request, Trash $trash): JsonResponse
    {
        $this->authorizeOwner($request);

        return response()->json(['days' => Trash::DAYS, 'items' => $trash->list()]);
    }

    public function restore(Request $request, AutoVideo $video, Trash $trash): JsonResponse
    {
        $this->authorizeOwner($request);

        return $this->run(fn (): string => $trash->restore($video));
    }

    public function purge(Request $request, AutoVideo $video, Trash $trash): JsonResponse
    {
        $this->authorizeOwner($request);

        return $this->run(function () use ($trash, $video): string {
            $trash->purge($video);

            return 'Đã xoá hẳn video khỏi app.';
        });
    }

    public function purgeAll(Request $request, Trash $trash): JsonResponse
    {
        $this->authorizeOwner($request);
        $n = $trash->purgeAll();

        return response()->json(['ok' => true, 'message' => $n > 0 ? "Đã xoá hẳn {$n} video trong thùng rác." : 'Thùng rác đã trống.']);
    }

    /** @param  callable(): string  $fn */
    private function run(callable $fn): JsonResponse
    {
        try {
            return response()->json(['ok' => true, 'message' => $fn()]);
        } catch (RuntimeException $e) {
            return response()->json(['ok' => false, 'message' => $e->getMessage()], 422);
        }
    }
}

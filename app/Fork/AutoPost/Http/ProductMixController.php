<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Scheduling\ProductMix;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use RuntimeException;

/** Nút "Trộn xen kẽ sản phẩm" (Lịch đăng, Kho riêng, Chỉnh kênh): xem trước, áp dụng, hoàn tác. */
final class ProductMixController extends Controller
{
    use ScopesToOwner;

    public function show(Request $request, string $socialAccount): JsonResponse
    {
        $auto = $this->auto($request, $socialAccount);
        $plan = app(ProductMix::class)->plan($auto, $request->boolean('include_pinned'));
        unset($plan['changes']);

        return response()->json(['ok' => true] + $plan);
    }

    public function store(Request $request, string $socialAccount): JsonResponse
    {
        $auto = $this->auto($request, $socialAccount);

        try {
            return response()->json(['ok' => true] + app(ProductMix::class)->apply($auto, $request->boolean('include_pinned')));
        } catch (RuntimeException $e) {
            return response()->json(['ok' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function undo(Request $request, string $socialAccount): JsonResponse
    {
        $auto = $this->auto($request, $socialAccount);
        $data = $request->validate([
            'undo' => ['required', 'array', 'min:1', 'max:200'],
            'undo.*.id' => ['required', 'integer'],
            'undo.*.at' => ['required', 'string', 'max:40'],
        ]);

        try {
            return response()->json(['ok' => true] + app(ProductMix::class)->restore($auto, $data['undo']));
        } catch (RuntimeException $e) {
            return response()->json(['ok' => false, 'error' => $e->getMessage()], 422);
        }
    }

    private function auto(Request $request, string $socialAccount): AutoAccount
    {
        $account = $this->findAccount($this->authorizeOwner($request), $socialAccount);

        return AutoAccount::query()->find($account->id)
            ?? abort(404, 'Kênh chưa bật tự động đăng.');
    }
}

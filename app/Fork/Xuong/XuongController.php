<?php

declare(strict_types=1);

namespace App\Fork\Xuong;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Inertia\Inertia;
use Inertia\Response;
use Throwable;

/** Trang "Xưởng Video": nhúng giao diện hub (iframe) kèm kiểm tra sống/chết và nút "Bật lại". */
final class XuongController extends Controller
{
    public const array TABS = ['san-xuat', 'kho', 'san-pham', 'gu', 'prompt-ai', 'cai-dat'];

    public function index(Request $request): Response
    {
        $tab = (string) $request->query('tab', '');
        $muc = (string) $request->query('muc', '');

        return Inertia::render('fork/Xuong', [
            'url' => rtrim((string) config('fork.xuong.url'), '/'),
            'tab' => in_array($tab, self::TABS, true) ? $tab : null,
            // Mục trong tab (vd. prompt-ai > bien-kich, cai-dat > giong); chỉ nhận chữ thường/số/gạch ngang.
            'muc' => preg_match('/^[a-z0-9-]{1,40}$/', $muc) === 1 ? $muc : null,
        ]);
    }

    /** Hỏi sức khoẻ hub từ phía máy chủ (trình duyệt không gọi thẳng được vì CORS). */
    public function health(): JsonResponse
    {
        return response()->json(self::probe())->header('Cache-Control', 'no-store');
    }

    /** @return array{up: bool, busy: bool} */
    public static function probe(): array
    {
        try {
            $r = Http::timeout(2)->connectTimeout(1)->get((string) config('fork.xuong.health_url'));
            $up = $r->successful() && $r->json('ok') === true;

            return ['up' => $up, 'busy' => $up && (int) $r->json('dang_chay_lo', 0) > 0];
        } catch (Throwable) {
            return ['up' => false, 'busy' => false];
        }
    }

    /** Nhờ launcher khởi động lại đúng dịch vụ hub (endpoint chỉ nghe loopback, có token trong runtime/control.token). */
    public function restart(): JsonResponse
    {
        $file = (string) config('fork.xuong.control_token_file');
        $token = is_file($file) ? trim((string) file_get_contents($file)) : '';
        if ($token === '') {
            return response()->json(['ok' => false, 'message' => 'Không liên lạc được launcher. Dùng khay hệ thống: TikTok Auto Kid > Khởi động lại.'], 503);
        }

        try {
            $r = Http::timeout(5)->withHeaders(['X-TTA-Token' => $token])
                ->post(sprintf('http://127.0.0.1:%d/api/restart?service=%s', (int) config('fork.xuong.control_port'), (string) config('fork.xuong.service')));
        } catch (Throwable) {
            return response()->json(['ok' => false, 'message' => 'Không liên lạc được launcher. Dùng khay hệ thống: TikTok Auto Kid > Khởi động lại.'], 503);
        }

        if (! $r->successful()) {
            return response()->json(['ok' => false, 'message' => (string) ($r->json('error') ?: 'Launcher từ chối yêu cầu.')], 502);
        }

        return response()->json(['ok' => true]);
    }
}

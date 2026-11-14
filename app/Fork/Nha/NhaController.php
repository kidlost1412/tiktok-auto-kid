<?php

declare(strict_types=1);

namespace App\Fork\Nha;

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeClient;
use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Inertia\Inertia;
use Inertia\Response;
use Throwable;

/** Trang chủ "Khu Tự Trị" và nguồn trạng thái cho nó (chỉ đọc: không đổi gì trong hub hay lịch đăng). */
final class NhaController extends Controller
{
    public function index(): Response
    {
        return Inertia::render('fork/Nha', ['avatar' => Avatar::read()]);
    }

    /** Ngoại hình nhân vật do chủ app tự đặt (hiện chỉ nhân vật chính). */
    public function avatar(string $who): JsonResponse
    {
        abort_unless(in_array($who, Avatar::WHO, true), 404);

        return response()->json(['ok' => true, 'avatar' => Avatar::read($who)])->header('Cache-Control', 'no-store');
    }

    public function saveAvatar(Request $request, string $who): JsonResponse
    {
        abort_unless(in_array($who, Avatar::WHO, true), 404);
        abort_unless($request->user()?->isAccountOwner(), 403);
        $data = $request->validate(Avatar::rules());

        return response()->json(['ok' => true, 'avatar' => Avatar::write($who, $data)]);
    }

    public function state(): JsonResponse
    {
        $now = CarbonImmutable::now();

        $app = $this->appFacts($now);
        $state = NhaState::build($this->hub(), $app, $now);
        $state['viec'] = NhaState::viec($app, $this->dem($now));
        // Địa chỉ hub để bấm cuộn phim mở video (trình duyệt gọi thẳng hub như khung Xưởng Video).
        $state['hub']['url'] = rtrim((string) config('fork.xuong.url'), '/');

        return response()->json($state)->header('Cache-Control', 'no-store');
    }

    /**
     * Hỏi sổ sự kiện của hub. Hub cũ chưa có /api/su-kien thì rơi về /api/trang-thai (không có sự kiện); hub tắt thì up=false.
     *
     * @return array<string, mixed>
     */
    private function hub(): array
    {
        $base = rtrim((string) config('fork.xuong.url'), '/');
        try {
            $r = Http::timeout(3)->connectTimeout(1)->acceptJson()->get($base.'/api/su-kien', ['max' => 600]);
            if ($r->successful() && $r->json('ok') === true) {
                return [
                    'up' => true,
                    'dang_chay' => (bool) $r->json('dang_chay'),
                    'tien_do' => (array) $r->json('tien_do', []),
                    'san_pham' => (array) $r->json('san_pham', []),
                    'su_kien' => (array) $r->json('su_kien', []),
                    'bay_gio' => (float) $r->json('bay_gio', 0),
                ];
            }
            $r = Http::timeout(3)->connectTimeout(1)->acceptJson()->get($base.'/api/trang-thai');
            if ($r->successful()) {
                return ['up' => true, 'dang_chay' => (bool) $r->json('dang_chay'), 'tien_do' => (array) $r->json('tien_do', []), 'su_kien' => []];
            }
        } catch (Throwable) {
            // rơi xuống "hub tắt"
        }

        return ['up' => false];
    }

    /**
     * Số đếm rẻ cho "việc chờ" của từng vai (chỉ đọc, có index theo status).
     *
     * @return array{loi: int, gio_tam_dung: int, kho: int|null, kho_thap: bool}
     */
    private function dem(CarbonImmutable $now): array
    {
        $dem = ['loi' => 0, 'gio_tam_dung' => 0, 'kho' => null, 'kho_thap' => false];
        try {
            $dem['loi'] = AutoVideo::query()->where('status', AutoVideo::FAILED)->where('updated_at', '>=', $now->subDay())->count();
            $dem['gio_tam_dung'] = ProductLink::query()->whereNotNull('paused_reason')->where('paused_reason', '!=', '')->count();

            $perDay = (int) AutoAccount::query()->where('enabled', true)->sum('daily_cap');
            if ($perDay > 0) {
                // Cùng cách tính "Kho đủ … ngày" ở Tổng quan: video mới + video hub đã xếp/giữ chỗ chưa đăng.
                $con = AutoVideo::query()->eligibleNew()
                    ->whereIn('product_code', AutoProduct::query()->where('enabled', true)->select('code'))
                    ->count()
                    + AutoVideo::query()
                        ->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED])
                        ->whereNotNull('hub_id')
                        ->whereIn('product_code', AutoProduct::query()->where('enabled', true)->select('code'))
                        ->count();
                $dem['kho'] = $con;
                $dem['kho_thap'] = $con < $perDay;
            }
        } catch (Throwable) {
            // thiếu bảng/dữ liệu thì không báo việc
        }

        return $dem;
    }

    /**
     * Số bài còn hẹn trong hôm nay, bài kế tiếp và tiện ích Chrome có đang kết nối không.
     *
     * @return array{posts_today: int, next: array{at: string, minutes: int, channel: string}|null, chrome_online: bool|null, post_counts: array{scheduled: int, posted: int}}
     */
    private function appFacts(CarbonImmutable $now): array
    {
        $postsToday = 0;
        $next = null;
        $chrome = null;
        try {
            $from = $now->setTimezone(NhaState::TZ)->startOfDay();
            $postsToday = AutoVideo::query()->where('status', AutoVideo::SCHEDULED)
                ->whereBetween('scheduled_for', [$from, $from->addDay()])->count();

            $v = AutoVideo::query()->where('status', AutoVideo::SCHEDULED)->whereNotNull('scheduled_for')
                ->where('scheduled_for', '>=', $now->subMinutes(10))->orderBy('scheduled_for')->first();
            if ($v !== null) {
                $acc = SocialAccount::query()->find($v->social_account_id);
                $at = CarbonImmutable::instance($v->scheduled_for);
                $next = [
                    'at' => $at->toIso8601String(),
                    'minutes' => (int) floor(($at->getTimestamp() - $now->getTimestamp()) / 60),
                    'channel' => $acc !== null ? (string) ($acc->username ? '@'.ltrim((string) $acc->username, '@') : $acc->display_name) : 'kênh TikTok',
                ];
            }

            $jobs = app(ChromeJobs::class);
            $chrome = ChromeClient::query()->whereNull('revoked_at')->get()->contains(fn (ChromeClient $c): bool => $jobs->isOnline($c));
        } catch (Throwable) {
            // thiếu bảng/dữ liệu thì để trống, nhà vẫn hiện
        }

        // Bộ đếm để trình duyệt so giữa hai lần hỏi: tăng = vừa có bài được hẹn / vừa đăng (Bưu tá ra hòm thư).
        $held = 0;
        $posted = 0;
        try {
            $held = AutoVideo::query()->where(fn ($q) => $q->where('status', AutoVideo::SCHEDULED)->orWhere(fn ($w) => $w->heldOnTikTok()))->count();
            $posted = AutoVideo::query()->livePosted()->count();
        } catch (Throwable) {
            // bỏ qua
        }

        return ['posts_today' => $postsToday, 'next' => $next, 'chrome_online' => $chrome, 'post_counts' => ['scheduled' => $held, 'posted' => $posted]];
    }
}

<?php

declare(strict_types=1);

namespace App\Fork\Nha;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeClient;
use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Http;
use Inertia\Inertia;
use Inertia\Response;
use Throwable;

/** Trang chủ "Xưởng nhỏ" và nguồn trạng thái cho nó (chỉ đọc: không đổi gì trong hub hay lịch đăng). */
final class NhaController extends Controller
{
    public function index(): Response
    {
        return Inertia::render('fork/Nha');
    }

    public function state(): JsonResponse
    {
        $now = CarbonImmutable::now();

        return response()->json(NhaState::build($this->hub(), $this->appFacts($now), $now))->header('Cache-Control', 'no-store');
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
     * Số bài còn hẹn trong hôm nay, bài kế tiếp và tiện ích Chrome có đang kết nối không.
     *
     * @return array{posts_today: int, next: array{at: string, minutes: int, channel: string}|null, chrome_online: bool|null}
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

        return ['posts_today' => $postsToday, 'next' => $next, 'chrome_online' => $chrome];
    }
}

<?php

declare(strict_types=1);

namespace App\Fork\Nha;

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ProductLink;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Update\LauncherClient;
use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
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
        $hub = $this->hub();
        $state = NhaState::build($hub, $app, $now);
        $dem = $this->dem($now);
        $dem['cho_duyet'] = isset($hub['cho_duyet']) ? (int) $hub['cho_duyet'] : null;
        $state['viec'] = NhaState::viec($app, $dem);
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
                    // Số video chờ anh duyệt (hub mới mới có; hub cũ không có thì bỏ qua).
                    'cho_duyet' => is_numeric($r->json('cho_duyet')) ? (int) $r->json('cho_duyet') : null,
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
     * @return array{loi: int, gio_tam_dung: int, chua_gio: int, kho: int|null, kho_thap: bool, cap_nhat: string|null}
     */
    private function dem(CarbonImmutable $now): array
    {
        $dem = ['loi' => 0, 'gio_tam_dung' => 0, 'chua_gio' => 0, 'kho' => null, 'kho_thap' => false, 'cap_nhat' => null];
        try {
            $dem['loi'] = AutoVideo::query()->where('status', AutoVideo::FAILED)->where('updated_at', '>=', $now->subDay())->count();
            $dem['gio_tam_dung'] = ProductLink::query()->whereNotNull('paused_reason')->where('paused_reason', '!=', '')->count();

            // Sản phẩm (mã x quy cách) đang có video chờ mà chưa chọn giỏ trên kênh nào (cùng ý với CartRules::forAccount).
            $linked = ProductLink::query()->get(['auto_product_id', 'quy_cach'])
                ->mapWithKeys(fn (ProductLink $l): array => [$l->auto_product_id.'|'.($l->quy_cach ?? '') => true])->all();
            $dem['chua_gio'] = AutoVideo::query()->notRieng()->where('status', AutoVideo::NEW)->whereNotNull('product_code')
                ->whereIn('product_code', AutoProduct::query()->where('enabled', true)->select('code'))
                ->select('product_code', 'quy_cach')->distinct()->get()
                ->filter(fn (AutoVideo $v): bool => ! isset($linked[$v->product_code.'|'.(filled($v->quy_cach) ? $v->quy_cach : '')]))
                ->count();

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
        $dem['cap_nhat'] = $this->capNhat();

        return $dem;
    }

    /**
     * Phiên bản mới (nếu có) theo kết quả kiểm tra launcher đã giữ sẵn; không hỏi GitHub. Đệm 5 phút để không gọi launcher mỗi lần poll.
     */
    private function capNhat(): ?string
    {
        try {
            $v = Cache::remember('nha.cap-nhat', 300, function (): string {
                if (! LauncherClient::repoConfigured()) {
                    return '';
                }
                $st = LauncherClient::status();

                return ($st['update_available'] ?? false) === true ? (string) ($st['latest']['version'] ?? '') : '';
            });
        } catch (Throwable) {
            return null;
        }

        // Đệm còn ghi bản mới nhưng app vừa cập nhật lên bản đó rồi: thôi báo.
        $cur = trim((string) @file_get_contents((string) config('fork-update.version_file')));
        if ($v !== '' && $cur !== '' && version_compare(ltrim($v, 'v'), ltrim($cur, 'v'), '<=')) {
            return null;
        }

        return $v !== '' ? $v : null;
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

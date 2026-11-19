<?php

declare(strict_types=1);

namespace App\Fork\Nha;

use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Models\ShopProduct;
use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeLiveProgress;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Throwable;

/**
 * "Đang làm ngay lúc này" của các vai lo việc app + phần hub chuyển tiếp, cho Khu Tự Trị.
 * Mỗi mục theo hợp đồng LiveItem (khoá snake_case, nguon app|hub). CHỈ ĐỌC, rẻ (truy vấn có chỉ mục, không gọi mạng
 * trừ phần hub, có hạn giờ ngắn); thiếu bảng/cột thì vai đó không có mục nào.
 *
 * Dữ liệu thật có sẵn:
 *  - buuta: job Chrome (trạng thái, giờ nhận, nhịp tim cuối, tên video, dung lượng). Tiện ích KHÔNG lưu % tải hay lời nhắn
 *    nên không có tien_do thật cho việc đăng.
 *  - chuquay: yêu cầu lấy sản phẩm shop (+ số sản phẩm đã lấy / tổng nếu tiện ích đã báo).
 *  - thukho: AI Kho riêng (bước n/tổng và việc đang làm của từng video).
 *  - cu, meo: không có dấu hiệu "đang làm" nào được lưu nên không có mục.
 */
final class NhaTrucTiep
{
    /** Mục đã xong còn giữ ngần này giây để trang kịp diễn đoạn kết. */
    private const int GIU_XONG = 60;

    /** Job mở mà hơn ngần này phút không động đậy thì coi là treo, không báo "đang làm". */
    private const int JOB_TREO_PHUT = 20;

    private const int SAP_DANG_PHUT = 10;

    private const string HUB_CACHE = 'nha.truc-tiep.hub';

    /** @return list<array<string, mixed>> */
    public static function app(CarbonImmutable $now): array
    {
        $out = [];
        foreach (['buuTa', 'sapDang', 'chuQuay', 'thuKho'] as $fn) {
            try {
                array_push($out, ...self::$fn($now));
            } catch (Throwable) {
                // thiếu bảng/cột thì vai đó im
            }
        }

        return $out;
    }

    /**
     * Mục "đang làm" của hub (GET /api/truc-tiep). Hub tắt / hub cũ chưa có đường này / quá giờ thì trả mảng rỗng.
     * Kết quả giữ 2 giây để nhiều lần hỏi liền nhau chỉ gọi hub một lần.
     *
     * @return list<array<string, mixed>>
     */
    public static function hub(): array
    {
        try {
            $cached = Cache::get(self::HUB_CACHE);
            if (is_array($cached)) {
                return $cached;
            }
        } catch (Throwable) {
            // không có kho đệm thì cứ hỏi
        }

        $items = [];
        $base = rtrim((string) config('fork.xuong.url'), '/');
        try {
            $r = Http::timeout(1.5)->connectTimeout(1)->acceptJson()->get($base.'/api/truc-tiep');
            if ($r->successful() && is_array($r->json('ds'))) {
                foreach ($r->json('ds') as $it) {
                    if (is_array($it) && is_string($it['id'] ?? null) && $it['id'] !== '') {
                        $it['nguon'] = 'hub';
                        $items[] = $it;
                    }
                    if (count($items) >= 40) {
                        break;
                    }
                }
            }
        } catch (Throwable) {
            // hub tắt / chậm: chỉ còn mục của app
        }

        try {
            Cache::put(self::HUB_CACHE, $items, 2);
        } catch (Throwable) {
            // bỏ qua
        }

        return $items;
    }

    private static function kenh(?SocialAccount $a): ?string
    {
        if ($a === null) {
            return null;
        }

        return filled($a->username) ? '@'.ltrim((string) $a->username, '@') : ((string) $a->display_name ?: null);
    }

    private static function ngan(?string $s, int $max): ?string
    {
        $s = trim(preg_replace('/\s+/u', ' ', (string) $s) ?? '');

        return $s === '' ? null : mb_substr($s, 0, $max);
    }

    private static function ts(mixed $t, CarbonImmutable $now): float
    {
        return $t === null ? (float) $now->getTimestamp() : (float) CarbonImmutable::parse($t)->format('U.u');
    }

    private static function gio(mixed $t): string
    {
        return CarbonImmutable::parse($t)->setTimezone(NhaState::TZ)->format('H:i');
    }

    /**
     * @param  array<string, mixed>  $extra
     * @return array<string, mixed>
     */
    private static function item(string $id, string $vai, string $viec, float $batDau, float $capNhat, array $extra = []): array
    {
        return $extra + [
            'id' => $id, 'nguon' => 'app', 'vai' => $vai, 'viec' => $viec, 'sp' => null, 'video' => null, 'kenh' => null,
            'bat_dau' => $batDau, 'cap_nhat' => $capNhat, 'xong' => false, 'ket_qua' => null, 'ky_tu' => null, 'dong' => [],
            'dang_go' => null, 'suy_nghi' => null, 'tien_do' => null, 'buoc' => null, 'chi_tiet' => null,
        ];
    }

    /** Bưu tá: job đăng bài của Chrome đang mở, và vừa xong trong 60 giây qua. */
    private static function buuTa(CarbonImmutable $now): array
    {
        $out = [];
        $jobs = ChromeJob::query()->with('socialAccount')
            ->where(fn ($q) => $q->whereIn('state', ChromeJob::OPEN)->where('updated_at', '>=', $now->subMinutes(self::JOB_TREO_PHUT))
                ->orWhere(fn ($w) => $w->whereIn('state', ['posted', 'rejected', 'uncertain', 'failed'])->where('updated_at', '>=', $now->subSeconds(self::GIU_XONG))))
            ->orderByDesc('updated_at')->limit(6)->get();

        $viec = [
            'queued' => ['Đang chờ Chrome nhận bài', 'Chờ Chrome nhận'],
            'claimed' => ['Chrome vừa nhận bài, chuẩn bị tải video', 'Nhận việc'],
            'uploading' => ['Đang tải video lên TikTok', 'Tải video lên'],
            'ready' => ['Đã tải xong, sắp bấm đăng', 'Sẵn sàng đăng'],
            'authorized' => ['Đang bấm đăng lên TikTok', 'Đang đăng'],
        ];

        foreach ($jobs as $j) {
            $st = (string) $j->state;
            $mb = $j->video_size !== null ? round($j->video_size / 1048576, 1) : null;
            $chiTiet = array_filter(['mb' => $mb > 0 ? $mb : null, 'lan' => (int) $j->attempt > 1 ? (int) $j->attempt : null, 'hen_gio' => $j->mode === 'scheduled' ? true : null]);
            $dong = [];
            if ($j->claimed_at !== null) {
                $dong[] = 'Chrome nhận bài lúc '.self::gio($j->claimed_at);
            }
            if ($j->authorized_at !== null) {
                $dong[] = 'Được phép đăng lúc '.self::gio($j->authorized_at);
            }
            if ($j->heartbeat_at !== null && $st !== 'authorized') {
                $dong[] = 'Chrome báo còn làm lúc '.self::gio($j->heartbeat_at);
            }
            $base = [
                'video' => self::ngan($j->video_name, 80), 'kenh' => self::kenh($j->socialAccount), 'dong' => $dong,
                'chi_tiet' => $chiTiet === [] ? null : $chiTiet,
            ];
            $batDau = self::ts($j->claimed_at ?? $j->created_at, $now);
            $capNhat = self::ts($j->heartbeat_at ?? $j->updated_at, $now);

            if (isset($viec[$st])) {
                $live = in_array($st, ['claimed', 'uploading', 'ready', 'authorized'], true) ? ChromeLiveProgress::get((string) $j->id) : null;
                if ($live !== null) {
                    $base['dong'] = array_slice([...$base['dong'], ...$live['hist']], -8);
                    $base['dang_go'] = $live['msg'];
                    $base['tien_do'] = $live['pct'] !== null ? $live['pct'] / 100 : null;
                    $capNhat = max($capNhat, (float) $live['at']);
                }
                $out[] = self::item("buuta-{$j->id}", 'buuta', $viec[$st][0], $batDau, $capNhat, $base + ['buoc' => $viec[$st][1]]);
            } else {
                $ok = $st === 'posted';
                $out[] = self::item("buuta-{$j->id}", 'buuta', $ok ? 'Đã đăng xong' : 'Đăng không thành', $batDau, self::ts($j->result_at ?? $j->updated_at, $now),
                    $base + ['xong' => true, 'ket_qua' => $ok ? 'ok' : 'loi', 'buoc' => $ok ? 'Xong' : 'Lỗi']);
            }
        }

        return $out;
    }

    /** Bưu tá: bài hẹn sắp tới giờ đăng (mục chờ, viec bắt đầu bằng "Sắp"). */
    private static function sapDang(CarbonImmutable $now): array
    {
        $v = AutoVideo::query()->where('status', AutoVideo::SCHEDULED)->whereNotNull('scheduled_for')
            ->whereBetween('scheduled_for', [$now, $now->addMinutes(self::SAP_DANG_PHUT)])
            ->orderBy('scheduled_for')->first(['id', 'file_name', 'product_name', 'social_account_id', 'scheduled_for']);
        if ($v === null) {
            return [];
        }
        $acc = SocialAccount::query()->find($v->social_account_id);
        $kenh = self::kenh($acc);
        $luc = CarbonImmutable::instance($v->scheduled_for);
        $t = (float) $now->getTimestamp();

        return [self::item('buuta-sap-'.$v->id, 'buuta', 'Sắp đăng '.self::gio($luc).($kenh !== null ? ' · '.$kenh : ''), $t, $t, [
            'video' => self::ngan((string) $v->file_name, 80), 'sp' => self::ngan((string) $v->product_name, 40), 'kenh' => $kenh,
            'buoc' => 'Còn '.max(0, (int) ceil(($luc->getTimestamp() - $now->getTimestamp()) / 60)).' phút',
        ])];
    }

    /** Chủ quầy: đang lấy sản phẩm từ shop TikTok (có số đã lấy / tổng nếu tiện ích báo), vừa xong, hoặc vừa lỗi. */
    private static function chuQuay(CarbonImmutable $now): array
    {
        $out = [];
        $accs = AutoAccount::query()->with('socialAccount')
            ->where(fn ($q) => $q->where('products_sync_requested_at', '>=', $now->subSeconds(ShopSync::REQUEST_TTL))
                ->orWhere('products_synced_at', '>=', $now->subSeconds(self::GIU_XONG)))
            ->limit(6)->get();
        $sync = app(ShopSync::class);

        foreach ($accs as $a) {
            $kenh = self::kenh($a->socialAccount);
            $req = $a->products_sync_requested_at;
            $done = $a->products_synced_at;
            $moi = $req !== null && ($done === null || $done < $req);
            $id = 'chuquay-'.$a->social_account_id;
            $batDau = self::ts($req, $now);

            if ($moi && filled($a->products_sync_request) && blank($a->products_sync_error) && $req >= $now->subSeconds(ShopSync::REQUEST_TTL)) {
                $st = $sync->status($a);
                $p = $st['progress'] ?? null;
                $buoc = $p !== null ? 'Đã lấy '.$p['got'].($p['total'] !== null ? '/'.$p['total'] : '').' sản phẩm' : 'Chờ Chrome mở giỏ shop';
                $out[] = self::item($id, 'chuquay', 'Đang lấy sản phẩm trong giỏ TikTok Shop', $batDau, $batDau, [
                    'kenh' => $kenh, 'buoc' => $buoc,
                    'tien_do' => $p !== null && $p['total'] ? min(1.0, $p['got'] / $p['total']) : null,
                    'chi_tiet' => $p !== null ? array_filter(['da_lay' => $p['got'], 'tong' => $p['total']], static fn ($x) => $x !== null) : null,
                ]);
            } elseif ($moi && filled($a->products_sync_error) && $a->updated_at !== null && $a->updated_at >= $now->subSeconds(self::GIU_XONG)) {
                $out[] = self::item($id, 'chuquay', 'Lấy giỏ shop không được', $batDau, self::ts($a->updated_at, $now), [
                    'kenh' => $kenh, 'xong' => true, 'ket_qua' => 'loi', 'dong' => [ShopSync::humanReason((string) $a->products_sync_error)],
                ]);
            } elseif ($done !== null && $done >= $now->subSeconds(self::GIU_XONG)) {
                $so = ShopProduct::query()->where('social_account_id', $a->social_account_id)
                    ->where('synced_at', '>=', CarbonImmutable::parse($done)->subMinutes(5))->count();
                $out[] = self::item($id, 'chuquay', 'Đã lấy xong sản phẩm trong giỏ', $req !== null && $req <= $done ? $batDau : self::ts($done, $now), self::ts($done, $now), [
                    'kenh' => $kenh, 'xong' => true, 'ket_qua' => 'ok', 'chi_tiet' => ['san_pham' => $so],
                ]);
            }
        }

        return $out;
    }

    /** Thủ kho: AI Kho riêng đang xem video nào (bước n/tổng, việc đang làm) và video vừa xem xong. */
    private static function thuKho(CarbonImmutable $now): array
    {
        $out = [];
        $vids = AutoVideo::query()->where('source', AutoVideo::SOURCE_RIENG)
            ->where('updated_at', '>=', $now->subMinutes(40))->orderByDesc('updated_at')->limit(20)
            ->get(['id', 'file_name', 'product_name', 'meta', 'updated_at']);

        foreach ($vids as $v) {
            $ai = is_array($v->meta['ai'] ?? null) ? $v->meta['ai'] : [];
            $dang = is_array($ai['dang'] ?? null) ? $ai['dang'] : null;
            $ten = self::ngan((string) $v->file_name, 80);

            if ($dang !== null && ! empty($dang['tong']) && filled($dang['luc'] ?? null)
                && CarbonImmutable::parse((string) $dang['luc']) >= $now->subMinutes(40)) {
                $buoc = (int) ($dang['buoc'] ?? 0);
                $tong = (int) $dang['tong'];
                $out[] = self::item('thukho-'.$v->id, 'thukho', 'Đang xem video để nhận ra sản phẩm', self::ts($dang['tu'] ?? $dang['luc'], $now), self::ts($dang['luc'], $now), [
                    'video' => $ten, 'buoc' => "Bước {$buoc}/{$tong}", 'tien_do' => $tong > 0 ? max(0.0, min(1.0, ($buoc - 1) / $tong)) : null,
                    'dong' => array_values(array_filter([self::ngan((string) ($dang['viec'] ?? ''), 200)])),
                ]);
            } elseif (filled($ai['at'] ?? null) && CarbonImmutable::parse((string) $ai['at']) >= $now->subSeconds(self::GIU_XONG)) {
                $state = (string) ($ai['state'] ?? '');
                $loi = in_array($state, ['error', 'gave_up'], true);
                $dong = array_values(array_filter([self::ngan((string) ($loi ? ($ai['error'] ?? '') : ($ai['ly_do'] ?? $ai['tom_tat'] ?? '')), 200)]));
                $out[] = self::item('thukho-'.$v->id, 'thukho', $loi ? 'AI xem video không được' : 'AI đã xem xong video', self::ts($ai['at'], $now), self::ts($ai['at'], $now), [
                    'video' => $ten, 'sp' => $loi ? null : self::ngan((string) $v->product_name, 40), 'xong' => true, 'ket_qua' => $loi ? 'loi' : 'ok',
                    'dong' => $dong, 'chi_tiet' => filled($ai['chac'] ?? null) ? ['chac' => (string) $ai['chac']] : null,
                ]);
            }
        }

        return $out;
    }
}

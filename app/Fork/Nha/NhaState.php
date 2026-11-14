<?php

declare(strict_types=1);

namespace App\Fork\Nha;

use Carbon\CarbonImmutable;

/**
 * Biến dữ liệu thật (sổ sự kiện của hub + lịch đăng của app) thành trạng thái từng nhân vật trong "Khu Tự Trị".
 * Hàm thuần: không gọi mạng/DB, nên test được bằng dữ liệu giả.
 *
 * Khoá nhân vật: bienkich, thuam, daodien, thodung, giamkhao, thukho, chuquay, cu, buuta (mèo không có trạng thái thật).
 */
final class NhaState
{
    public const string TZ = 'Asia/Ho_Chi_Minh';

    /** Sự kiện "bắt đầu" quá cũ thì coi là đã treo/chết, không để nhân vật làm việc mãi. */
    private const int STALE_SECONDS = 1200;

    /** Hết hạn mức cũ hơn mức này thì thôi báo (đã qua giờ reset). */
    private const int LIMIT_SECONDS = 21600;

    private const array VAI_KHOA = [
        'bien-kich' => 'bienkich',
        'giong' => 'thuam',
        'dao-dien' => 'daodien',
        'dung' => 'thodung',
        'giam-khao' => 'giamkhao',
    ];

    /**
     * @param  array{up: bool, dang_chay?: bool, tien_do?: array<string, mixed>, san_pham?: array<string, mixed>, su_kien?: list<array<string, mixed>>, bay_gio?: float|int}  $hub
     * @param  array{posts_today?: int, next?: array{at: string, minutes: int, channel: string}|null, chrome_online?: bool|null}  $app
     * @return array<string, mixed>
     */
    public static function build(array $hub, array $app, CarbonImmutable $now): array
    {
        $vai = [];
        foreach (['bienkich', 'thuam', 'daodien', 'thodung', 'giamkhao', 'thukho', 'chuquay', 'cu', 'buuta'] as $k) {
            $vai[$k] = ['state' => 'idle', 'bubble' => null];
        }

        $postsToday = (int) ($app['posts_today'] ?? 0);
        $next = $app['next'] ?? null;

        if (! ($hub['up'] ?? false)) {
            foreach ($vai as $k => $_) {
                $vai[$k] = ['state' => 'sleep', 'bubble' => null];
            }
            $vai['buuta'] = self::postman($next);

            return [
                'mode' => 'down',
                'line' => 'Xưởng đang tắt'.($postsToday > 0 ? ' · '.$postsToday.' bài hẹn hôm nay' : ''),
                'vai' => $vai,
                'bang' => ['san_pham' => null, 'tien_do' => null, 'dong' => 'Xưởng Video đang tắt. Mở lại ở trang Xưởng Video.'],
                'hub' => ['up' => false, 'dang_chay' => false],
                'app' => $app,
                'lo' => null,
                'reels' => [],
                'events' => [],
                'bay_gio' => (float) $now->getTimestamp(),
            ];
        }

        $running = (bool) ($hub['dang_chay'] ?? false);
        $events = array_values(array_filter((array) ($hub['su_kien'] ?? []), 'is_array'));
        $hubNow = (float) ($hub['bay_gio'] ?? $now->getTimestamp());
        $age = static fn (array $e): float => $hubNow - ((float) ($e['n'] ?? 0)) / 1_000_000;

        // Chỉ xét từ lần "bắt đầu lô" gần nhất.
        $start = null;
        foreach ($events as $i => $e) {
            if (($e['loai'] ?? '') === 'bat-dau-lo') {
                $start = $i;
            }
        }
        $cur = $start === null ? $events : array_slice($events, $start);
        $batchStart = $start === null ? null : $events[$start];
        $lastEvent = $cur === [] ? null : $cur[array_key_last($cur)];
        $finished = $lastEvent !== null && ($lastEvent['loai'] ?? '') === 'ket-thuc-lo';

        $tong = (int) ($hub['tien_do']['tong'] ?? 0);
        $xong = (int) ($hub['tien_do']['xong'] ?? 0);
        $name = (string) ($hub['san_pham']['ten'] ?? ($batchStart['ten'] ?? ''));
        $soVideo = (int) ($batchStart['so_video'] ?? $tong);
        if ($name === '' && $tong > 0) {
            $name = 'Lô gần nhất';
        }

        // Hết hạn mức: sự kiện xảy ra sau lần bắt đầu lô gần nhất và còn mới.
        $limit = false;
        foreach ($cur as $e) {
            if (($e['loai'] ?? '') === 'het-han-muc' && $age($e) < self::LIMIT_SECONDS) {
                $limit = true;
            }
        }

        // Vai nào đang làm: khoá (vai|video) mà sự kiện cuối cùng là "bắt đầu" và chưa quá cũ.
        $last = [];
        $scored = 0;
        $lastScore = null;
        foreach ($cur as $e) {
            $last[($e['vai'] ?? '').'|'.($e['video'] ?? '')] = $e;
            if (($e['loai'] ?? '') === 'diem') {
                $scored++;
                $lastScore = $e['diem'] ?? null;
            }
        }
        $work = [];
        if ($running && ! $finished && ! $limit) {
            foreach ($last as $e) {
                $loai = $e['loai'] ?? '';
                if (($loai === 'bat-dau' || $loai === 'hoc') && $age($e) <= self::STALE_SECONDS) {
                    $work[(string) $e['vai']][] = $e;
                }
            }
            // Không suy được ai đang làm (sự kiện thiếu): lấy vai của sự kiện cuối cùng.
            if ($work === [] && $lastEvent !== null && isset(self::VAI_KHOA[$lastEvent['vai'] ?? ''])) {
                $work[(string) $lastEvent['vai']][] = $lastEvent;
            }
        }

        foreach ($work as $v => $list) {
            $key = self::VAI_KHOA[$v] ?? null;
            if ($key === null) {
                continue;
            }
            $vai[$key] = ['state' => 'working', 'bubble' => self::bubble($v, $list, $tong, $scored, $lastScore)];
        }

        // Thủ kho: vừa nhập kho một video (vài giây).
        if ($running && $lastEvent !== null && ($lastEvent['loai'] ?? '') === 'luu' && $age($lastEvent) <= 25) {
            $vai['thukho'] = ['state' => 'working', 'bubble' => 'Nhập kho video '.(int) ($lastEvent['so'] ?? $xong).'/'.(int) ($lastEvent['tong'] ?? $tong)];
        }

        $vai['buuta'] = self::postman($next);

        if ($limit) {
            foreach (['bienkich', 'thuam', 'daodien', 'thodung', 'giamkhao', 'thukho', 'chuquay', 'cu'] as $k) {
                $vai[$k] = ['state' => 'sleep', 'bubble' => null];
            }
        }

        $mode = $limit ? 'limit' : ($running && ! $finished ? 'working' : 'idle');
        $hhmm = $next === null ? null : CarbonImmutable::parse($next['at'])->setTimezone(self::TZ)->format('H:i');

        $line = match ($mode) {
            'working' => 'Xưởng đang làm '.($soVideo > 0 ? $soVideo.' video ' : '').$name.($tong > 0 ? ' · '.$xong.'/'.$tong : ''),
            'limit' => 'Xưởng tạm nghỉ vì hết hạn mức Claude'.($tong > 0 ? ' · đã xong '.$xong.'/'.$tong : ''),
            default => 'Xưởng đang nghỉ · '.($postsToday > 0
                ? $postsToday.' bài hẹn hôm nay'.($hhmm !== null ? ', bài kế tiếp lúc '.$hhmm : '')
                : 'hôm nay chưa có bài hẹn'),
        };

        $phut = $finished && isset($lastEvent['phut']) ? ' · '.str_replace('.', ',', (string) $lastEvent['phut']).' phút' : '';
        $dong = match ($mode) {
            'limit' => 'Hết hạn mức Claude. Vào Xưởng Video > Cài đặt để đổi tài khoản rồi chạy tiếp.',
            'working' => (string) ($lastEvent['msg'] ?? 'Đang làm việc'),
            default => $finished ? (isset($lastEvent['so'], $lastEvent['tong']) ? 'Xong '.(int) $lastEvent['so'].'/'.(int) $lastEvent['tong'].$phut : (string) ($lastEvent['msg'] ?? 'Đã xong lô')) : ($tong > 0 && $xong >= $tong ? 'Lô gần nhất đã xong, xưởng đang nghỉ' : 'Chưa có lô nào đang chạy'),
        };

        return [
            'mode' => $mode,
            'line' => trim($line),
            'vai' => $vai,
            'bang' => [
                'san_pham' => $name !== '' ? $name : null,
                'tien_do' => $tong > 0 ? ['xong' => $xong, 'tong' => $tong] : null,
                'dong' => $dong,
            ],
            'hub' => ['up' => true, 'dang_chay' => $running],
            'app' => $app,
            'lo' => $batchStart['n'] ?? null,
            'reels' => self::reels($cur),
            'events' => self::compact($events),
            'bay_gio' => $hubNow,
        ];
    }

    /**
     * Số việc đang chờ chủ app theo vai (chỉ vai có việc). Hàm thuần: số đếm do nơi gọi truy vấn rồi đưa vào.
     *
     * @param  array{chrome_online?: bool|null}  $app
     * @param  array{loi?: int, gio_tam_dung?: int, chua_gio?: int, kho?: int|null, kho_thap?: bool, cho_duyet?: int|null, cap_nhat?: string|null}  $dem  loi = bài lỗi 24h qua; gio_tam_dung = giỏ bị tạm dừng; chua_gio = sản phẩm có video chờ mà chưa chọn giỏ; kho = số video còn chờ đăng (null = không có kênh bật); cho_duyet = video hub chưa Ưng/Bỏ (null = hub cũ/không biết); cap_nhat = số phiên bản mới (đã có sẵn, không gọi mạng)
     * @return array<string, array{so: int, tom_tat: string}>
     */
    public static function viec(array $app, array $dem): array
    {
        $viec = [];

        $loi = (int) ($dem['loi'] ?? 0);
        if ($loi > 0) {
            $viec['buuta'] = ['so' => $loi, 'tom_tat' => $loi.' bài đăng lỗi, cần xem lại'];
        }

        $chua = (int) ($dem['chua_gio'] ?? 0);
        $gio = (int) ($dem['gio_tam_dung'] ?? 0);
        if ($chua + $gio > 0) {
            $viec['chuquay'] = ['so' => $chua + $gio, 'tom_tat' => implode(' · ', array_filter([
                $chua > 0 ? $chua.' sản phẩm chưa chọn giỏ' : null,
                $gio > 0 ? $gio.' giỏ tạm dừng' : null,
            ]))];
        }

        $kho = $dem['kho'] ?? null;
        if ($kho !== null && ($dem['kho_thap'] ?? false)) {
            $viec['thukho'] = ['so' => 1, 'tom_tat' => 'Kho còn '.(int) $kho.' video'];
        }

        $duyet = (int) ($dem['cho_duyet'] ?? 0);
        if ($duyet > 0) {
            $viec['giamkhao'] = ['so' => $duyet, 'tom_tat' => $duyet.' video chờ anh duyệt'];
        }

        // Mèo = quản gia cài đặt: Chrome mất kết nối, có bản cập nhật mới.
        $meo = [];
        if (($app['chrome_online'] ?? null) === false) {
            $meo[] = 'Chrome chưa kết nối';
        }
        $cn = (string) ($dem['cap_nhat'] ?? '');
        if ($cn !== '') {
            $meo[] = 'Có bản cập nhật '.$cn;
        }
        if ($meo !== []) {
            $viec['meo'] = ['so' => count($meo), 'tom_tat' => implode(' · ', $meo)];
        }

        return $viec;
    }

    /** Trường sự kiện gửi cho trình duyệt (đủ để diễn hoạt cảnh và dòng "hoạt động gần đây"; không gửi gì khác). */
    private const array EVENT_KEYS = ['n', 't', 'vai', 'loai', 'video', 'msg', 'so', 'tong', 'diem', 'dat', 'file', 'ngay', 'loi', 'phut', 'ten', 'so_video', 'lan', 'buoc'];

    /**
     * @param  list<array<string, mixed>>  $events
     * @return list<array<string, mixed>>
     */
    private static function compact(array $events): array
    {
        $out = [];
        foreach (array_slice($events, -60) as $e) {
            $out[] = array_intersect_key($e, array_flip(self::EVENT_KEYS));
        }

        return $out;
    }

    /**
     * Video đã lưu trong lô hiện tại (kệ cuộn phim ở Kho hàng).
     *
     * @param  list<array<string, mixed>>  $cur
     * @return list<array{n: mixed, so: int, file: string, ngay: string, diem: mixed}>
     */
    private static function reels(array $cur): array
    {
        $out = [];
        foreach ($cur as $e) {
            if (($e['loai'] ?? '') === 'luu') {
                $out[] = ['n' => $e['n'] ?? 0, 'so' => (int) ($e['so'] ?? count($out) + 1), 'file' => (string) ($e['file'] ?? ''), 'ngay' => (string) ($e['ngay'] ?? ''), 'diem' => $e['diem'] ?? null];
            }
        }

        return array_slice($out, -40);
    }

    /**
     * @param  array{at: string, minutes: int, channel: string}|null  $next
     * @return array{state: string, bubble: ?string}
     */
    private static function postman(?array $next): array
    {
        if ($next === null || $next['minutes'] > 30) {
            return ['state' => 'idle', 'bubble' => null];
        }
        $hhmm = CarbonImmutable::parse($next['at'])->setTimezone(self::TZ)->format('H:i');

        return ['state' => 'working', 'bubble' => $next['minutes'] <= 0
            ? 'Tới giờ đăng · '.$next['channel']
            : 'Bài hẹn '.$hhmm.' · '.$next['channel']];
    }

    /** @param list<array<string, mixed>> $list */
    private static function bubble(string $vai, array $list, int $tong, int $scored, mixed $lastScore): string
    {
        $n = count($list);
        $e = $list[0];

        return match ($vai) {
            'bien-kich' => 'Đang viết '.(int) ($e['so'] ?? 0).' lời…',
            'giong' => 'Đang thu '.(int) ($e['so'] ?? 0).' giọng…',
            'dao-dien' => $n > 1 ? $n.' đạo diễn đang lên bảng dựng…' : 'Đang lên bảng dựng…',
            'dung' => ($e['buoc'] ?? '') === 'chu' && $n === 1 ? 'Đang chạy lớp chữ…' : 'Đang dựng '.$n.' video…',
            'giam-khao' => ($e['loai'] ?? '') === 'hoc' ? 'Đang gom bài học…' : ($scored > 0
                ? 'Đang chấm '.$scored.'/'.$tong.($lastScore !== null ? ' · '.$lastScore.' điểm' : '')
                : 'Đang chấm bản đầu…'),
            default => 'Đang làm…',
        };
    }
}

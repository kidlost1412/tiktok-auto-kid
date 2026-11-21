<?php

declare(strict_types=1);

namespace App\Fork\Nha;

use App\Fork\AutoPost\Models\AutoSetting;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Throwable;

/**
 * Thời tiết thật cho "Khu Tự Trị": chủ app gõ tên nơi ở, máy chủ tra toạ độ MỘT lần (Open-Meteo geocoding) rồi lưu;
 * sau đó hỏi Open-Meteo thời tiết hiện tại (đệm 15 phút) và quy về nắng / nhiều mây / mưa.
 * Chỉ tên nơi và toạ độ do chủ gõ được gửi đi, không gửi gì khác. Lỗi gì cũng trả null để trang tự dùng thời tiết ngẫu nhiên.
 */
final class ThoiTiet
{
    private const KEY = 'nha.thoi-tiet';

    private const GEOCODE = 'https://geocoding-api.open-meteo.com/v1/search';

    private const FORECAST = 'https://api.open-meteo.com/v1/forecast';

    public const CACHE_SECONDS = 900;

    /** Tên hiện khi nơi ở do trình duyệt tự lấy (không tra ngược ra tên tỉnh). */
    public const HERE = 'Vị trí hiện tại của máy';

    /** Nơi đã lưu: name + lat + lon, hoặc null nếu chưa đặt. */
    public static function place(): ?array
    {
        $raw = json_decode((string) AutoSetting::read(self::KEY, ''), true);
        if (! is_array($raw) || ! is_string($raw['name'] ?? null) || ! is_numeric($raw['lat'] ?? null) || ! is_numeric($raw['lon'] ?? null)) {
            return null;
        }

        return ['name' => $raw['name'], 'lat' => (float) $raw['lat'], 'lon' => (float) $raw['lon']];
    }

    /** Tra toạ độ theo tên (kết quả đầu tiên ở Việt Nam). Không tìm thấy hoặc lỗi mạng: null. */
    public static function geocode(string $name): ?array
    {
        try {
            $r = Http::timeout(3)->connectTimeout(2)->acceptJson()->get(self::GEOCODE, [
                'name' => $name, 'count' => 5, 'language' => 'vi', 'countryCode' => 'VN',
            ]);
            $hit = $r->successful() ? ($r->json('results.0') ?? null) : null;
            if (! is_array($hit) || ! is_numeric($hit['latitude'] ?? null) || ! is_numeric($hit['longitude'] ?? null)) {
                return null;
            }
            $label = trim((string) ($hit['name'] ?? ''));
            $admin = trim((string) ($hit['admin1'] ?? ''));
            if ($label === '') {
                $label = $name;
            }
            if ($admin !== '' && $admin !== $label) {
                $label .= ', '.$admin;
            }

            return ['name' => $label, 'lat' => round((float) $hit['latitude'], 4), 'lon' => round((float) $hit['longitude'], 4)];
        } catch (Throwable) {
            return null;
        }
    }

    /** Lưu nơi (null = xoá, quay về thời tiết ngẫu nhiên). */
    public static function save(?array $place): void
    {
        AutoSetting::write(self::KEY, $place === null ? '' : json_encode($place, JSON_UNESCAPED_UNICODE));
    }

    /** Mã thời tiết WMO → 'sunny' | 'cloudy' | 'rain'. */
    public static function skyFromCode(int $code): string
    {
        return match (true) {
            $code <= 1 => 'sunny',
            ($code >= 51 && $code <= 67), ($code >= 80 && $code <= 82), $code >= 95 => 'rain',
            default => 'cloudy', // 2-3, sương mù 45/48, tuyết 71-77/85-86 và mã lạ
        };
    }

    /** Trời hiện tại ở nơi đã lưu; chưa đặt nơi hoặc lỗi thì null. */
    public static function sky(): ?string
    {
        $p = self::place();
        if ($p === null) {
            return null;
        }
        $key = 'nha.thoi-tiet.'.md5($p['lat'].','.$p['lon']);
        $hit = Cache::get($key);
        if (is_string($hit)) {
            return $hit === '' ? null : $hit;
        }

        $sky = self::fetch($p['lat'], $p['lon']);
        // Lỗi thì nhớ 1 phút (đỡ gọi dồn khi Open-Meteo chập chờn), thành công nhớ 15 phút.
        Cache::put($key, $sky ?? '', $sky === null ? 60 : self::CACHE_SECONDS);

        return $sky;
    }

    private static function fetch(float $lat, float $lon): ?string
    {
        try {
            $r = Http::timeout(3)->connectTimeout(2)->acceptJson()->get(self::FORECAST, [
                'latitude' => $lat, 'longitude' => $lon,
                'current' => 'weather_code,is_day,precipitation,cloud_cover',
            ]);
            $code = $r->successful() ? $r->json('current.weather_code') : null;

            return is_numeric($code) ? self::skyFromCode((int) $code) : null;
        } catch (Throwable) {
            return null;
        }
    }
}

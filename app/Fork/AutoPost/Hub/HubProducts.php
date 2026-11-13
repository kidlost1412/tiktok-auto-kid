<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Hub;

use Illuminate\Http\Client\PendingRequest;
use Illuminate\Support\Facades\Http;
use Throwable;

/**
 * Tạo / đổi tên / xoá sản phẩm hub bằng đúng API mà giao diện Xưởng Video (cổng 8765) dùng
 * (/api/san-pham-moi, /api/san-pham/<mã>, /api/xoa-san-pham/<mã>), để app không tự ghi file san-pham/ của hub.
 * Hub chỉ nhận lệnh gửi từ chính cổng của nó (đúng Host, JSON), nên máy chủ gọi thẳng ở loopback là được.
 */
final class HubProducts
{
    /** Sản phẩm ví dụ hub tạo sẵn cho người mới. */
    public const string SAMPLE_CODE = 'vi-du';

    public function baseUrl(): string
    {
        return rtrim((string) config('fork.xuong.url'), '/');
    }

    /**
     * Tạo sản phẩm hub gắn sẵn sản phẩm Shop (hub tự lấy ảnh thật của sản phẩm làm ảnh sản phẩm).
     *
     * @return array{ok: bool, error: ?string, warning: ?string}
     */
    public function create(string $code, string $fullName, string $shortName, string $shopProductId): array
    {
        return $this->call('/api/san-pham-moi', [
            'ma' => $code, 'ten' => $fullName, 'ten_ngan' => $shortName, 'shop_id' => $shopProductId,
        ], 90);
    }

    /** @return array{ok: bool, error: ?string, warning: ?string} */
    public function rename(string $code, string $shortName): array
    {
        return $this->call('/api/san-pham/'.$code, ['ten_ngan' => $shortName], 15);
    }

    /** Hub đưa hồ sơ sản phẩm vào Thùng rác (không đụng video gốc, không xoá video đã làm). */
    public function delete(string $code): array
    {
        return $this->call('/api/xoa-san-pham/'.$code, [], 60);
    }

    /**
     * @param  array<string, mixed>  $body
     * @return array{ok: bool, error: ?string, warning: ?string}
     */
    private function call(string $path, array $body, int $timeout): array
    {
        try {
            $res = $this->client($timeout)->post($this->baseUrl().$path, $body === [] ? (object) [] : $body);
        } catch (Throwable) {
            return ['ok' => false, 'error' => 'Xưởng Video đang tắt hoặc không trả lời. Hãy mở lại Xưởng Video rồi thử lại.', 'warning' => null];
        }

        $json = $res->json();

        if (! $res->successful() || ! is_array($json) || ($json['ok'] ?? false) !== true) {
            $why = is_array($json) && filled($json['loi'] ?? null) ? (string) $json['loi'] : 'Xưởng Video từ chối yêu cầu (mã '.$res->status().').';

            return ['ok' => false, 'error' => $why, 'warning' => null];
        }

        return ['ok' => true, 'error' => null, 'warning' => filled($json['canh_bao'] ?? null) ? (string) $json['canh_bao'] : null];
    }

    private function client(int $timeout): PendingRequest
    {
        return Http::timeout($timeout)->connectTimeout(3)->acceptJson()->asJson();
    }
}

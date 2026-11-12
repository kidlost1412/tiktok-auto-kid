<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Hub;

use Carbon\CarbonInterface;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\PendingRequest;
use Illuminate\Http\Client\Response;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * Máy khách HTTP của hub "Xưởng Video". Hub chỉ chạy khi app của nó đang mở, nên lỗi kết nối
 * chỉ được ghi log rồi trả kết quả "offline", không bao giờ ném ngoại lệ.
 */
final class HubApi
{
    public const OK = 'ok';

    public const OFFLINE = 'offline';

    public const BAD_KEY = 'bad_key';

    public const NOT_FOUND = 'not_found';

    /** Hub từ chối nội dung (4xx khác): thử lại cũng vô ích. */
    public const REJECTED = 'rejected';

    /** Hub lỗi tạm (5xx hoặc trả lời lạ): thử lại sau. */
    public const RETRY = 'retry';

    /** Kết quả giữ chỗ (claim): máy này giữ được. */
    public const CLAIM_OK = 'ok';

    /** Máy khác đang giữ video. */
    public const CLAIM_HELD = 'held';

    /** Hub báo video đã đăng. */
    public const CLAIM_POSTED = 'posted';

    /** Hub không có video này. */
    public const CLAIM_NOT_FOUND = 'not_found';

    /** Hub bản cũ chưa có route /giu: chạy kiểu một máy như trước. */
    public const CLAIM_NO_ROUTE = 'no_route';

    /** Không xác nhận được (hub tắt, sai khoá, lỗi): KHÔNG được đăng video này lúc này. */
    public const CLAIM_UNKNOWN = 'unknown';

    public static function enabled(): bool
    {
        return filled(config('fork.auto.hub_api.key'));
    }

    public function url(): string
    {
        return rtrim((string) config('fork.auto.hub_api.url', 'http://127.0.0.1:8766'), '/');
    }

    /** @return 'ok'|'offline'|'bad_key'|'error' */
    public function ping(): string
    {
        try {
            $response = $this->client()->get('/trypost/ping');
        } catch (ConnectionException $e) {
            Log::info('Hub API: hub đang tắt.', ['error' => $e->getMessage()]);

            return self::OFFLINE;
        } catch (Throwable $e) {
            Log::warning('Hub API: ping lỗi.', ['error' => $e->getMessage()]);

            return 'error';
        }

        if ($response->status() === 401) {
            return self::BAD_KEY;
        }

        return $response->successful() && $response->json('ok') === true ? self::OK : 'error';
    }

    /**
     * Video theo trạng thái (ung = chủ đã duyệt, chưa đăng). Trả null khi hub tắt, sai khoá hoặc lỗi:
     * khi đó giữ nguyên dữ liệu cũ, lượt sau thử lại.
     *
     * @return list<array<string, mixed>>|null
     */
    public function videos(string $status = 'ung'): ?array
    {
        try {
            $response = $this->client()->get('/trypost/videos', ['status' => $status, 'may' => $this->may()]);
        } catch (Throwable $e) {
            Log::info('Hub API: không lấy được danh sách video.', ['error' => $e->getMessage()]);

            return null;
        }

        if (! $response->successful() || ! is_array($response->json('videos'))) {
            Log::warning('Hub API: danh sách video không dùng được.', ['status' => $response->status()]);

            return null;
        }

        return array_values(array_filter((array) $response->json('videos'), 'is_array'));
    }

    /** Mã của máy này khi dùng chung hub. */
    public function may(): string
    {
        return (string) config('fork.auto.hub_api.may', 'ban-chinh');
    }

    /**
     * Giữ chỗ video cho máy này (idempotent, gọi lại chỉ cập nhật kênh/hạn).
     *
     * @return array{state: string, by: ?string, status: ?int}
     */
    public function claim(string $id, string $channel, ?CarbonInterface $until): array
    {
        $body = ['may' => $this->may(), 'kenh' => $channel];

        if ($until !== null) {
            $body['han'] = $until->toIso8601String();
        }

        try {
            $response = $this->client()->asJson()->post('/trypost/videos/'.rawurlencode($id).'/giu', $body);
        } catch (ConnectionException $e) {
            Log::info('Hub API: hub đang tắt, chưa giữ chỗ được video.', ['hub_id' => $id, 'error' => $e->getMessage()]);

            return ['state' => self::CLAIM_UNKNOWN, 'by' => null, 'status' => null];
        } catch (Throwable $e) {
            Log::warning('Hub API: giữ chỗ video lỗi.', ['hub_id' => $id, 'error' => $e->getMessage()]);

            return ['state' => self::CLAIM_UNKNOWN, 'by' => null, 'status' => null];
        }

        $status = $response->status();
        $by = is_string($response->json('giu_boi')) && $response->json('giu_boi') !== '' ? (string) $response->json('giu_boi') : null;

        if ($response->successful()) {
            return ['state' => self::CLAIM_OK, 'by' => $by, 'status' => $status];
        }

        if ($status === 409) {
            // Đã đăng: giu_boi null. Máy khác giữ: giu_boi là mã máy đó.
            return ['state' => $by === null ? self::CLAIM_POSTED : self::CLAIM_HELD, 'by' => $by, 'status' => $status];
        }

        if ($status === 404) {
            // Hub mới trả JSON {"ok":false,...} khi không có video; hub cũ không có route nên 404 không kèm "ok".
            return ['state' => $response->json('ok') === false ? self::CLAIM_NOT_FOUND : self::CLAIM_NO_ROUTE, 'by' => null, 'status' => $status];
        }

        Log::warning('Hub API: hub từ chối giữ chỗ video.', ['hub_id' => $id, 'status' => $status]);

        return ['state' => self::CLAIM_UNKNOWN, 'by' => null, 'status' => $status];
    }

    /** Nhả chỗ video đã giữ (gửi qua outbox để thử lại). */
    public function release(string $id): string
    {
        return $this->post('/trypost/videos/'.rawurlencode($id).'/nha', ['may' => $this->may()]);
    }

    /**
     * Tải file từ hub (stream thẳng xuống đĩa). `$url` là url_file/url_anh_bia hub trả, tương đối hoặc tuyệt đối
     * nhưng phải cùng máy chủ với hub (không gửi X-Key đi nơi khác).
     *
     * @return 'ok'|'offline'|'not_found'|'error'
     */
    public function download(string $url, string $destination): string
    {
        $path = $this->localPath($url);

        if ($path === null) {
            Log::warning('Hub API: từ chối tải file ngoài hub.', ['url' => $url]);

            return 'error';
        }

        try {
            $response = $this->client()->timeout(600)->withOptions(['sink' => $destination])->get($path);
        } catch (ConnectionException $e) {
            Log::info('Hub API: hub tắt khi tải file.', ['url' => $path, 'error' => $e->getMessage()]);

            return self::OFFLINE;
        } catch (Throwable $e) {
            Log::warning('Hub API: tải file lỗi.', ['url' => $path, 'error' => $e->getMessage()]);

            return 'error';
        }

        if ($response->status() === 404) {
            return self::NOT_FOUND;
        }

        return $response->successful() ? 'ok' : 'error';
    }

    /** Đường dẫn (kèm query) trên hub, hoặc null nếu url trỏ ra máy chủ khác. */
    private function localPath(string $url): ?string
    {
        if (! preg_match('#^[a-z][a-z0-9+.-]*://#i', $url)) {
            return '/'.ltrim($url, '/');
        }

        $target = parse_url($url);
        $hub = parse_url($this->url());

        if (! is_array($target) || ! is_array($hub) || strtolower((string) ($target['host'] ?? '')) !== strtolower((string) ($hub['host'] ?? '-'))
            || ($target['port'] ?? null) !== ($hub['port'] ?? null)) {
            return null;
        }

        return ($target['path'] ?? '/').(isset($target['query']) ? '?'.$target['query'] : '');
    }

    /** @param  array<string, mixed>  $body  kenh, tiktok_id, link, luc */
    public function markPosted(string $id, array $body): string
    {
        return $this->post('/trypost/videos/'.rawurlencode($id).'/da-dang', $body);
    }

    public function markFailed(string $id, string $reason): string
    {
        return $this->post('/trypost/videos/'.rawurlencode($id).'/loi', ['ly_do' => $reason]);
    }

    /** @param  array<string, mixed>  $body  id, kenh, luot_xem_24h, luot_xem_72h, thich, binh_luan, chia_se, don, luc */
    public function sendStats(array $body): string
    {
        return $this->post('/trypost/so-lieu', $body);
    }

    /** @param  array<string, mixed>  $body */
    private function post(string $path, array $body): string
    {
        try {
            $response = $this->client()->asJson()->post($path, $body);
        } catch (ConnectionException $e) {
            Log::info('Hub API: hub đang tắt, sẽ gửi lại sau.', ['path' => $path, 'error' => $e->getMessage()]);

            return self::OFFLINE;
        } catch (Throwable $e) {
            Log::warning('Hub API: gửi lỗi.', ['path' => $path, 'error' => $e->getMessage()]);

            return self::RETRY;
        }

        return $this->classify($response);
    }

    private function classify(Response $response): string
    {
        return match (true) {
            $response->successful() => self::OK,
            $response->status() === 401 => self::BAD_KEY,
            $response->status() === 404 => self::NOT_FOUND,
            $response->clientError() => self::REJECTED,
            default => self::RETRY,
        };
    }

    private function client(): PendingRequest
    {
        return Http::baseUrl($this->url())
            ->withHeaders(['X-Key' => (string) config('fork.auto.hub_api.key')])
            ->acceptJson()
            ->connectTimeout(3)
            ->timeout(5);
    }
}

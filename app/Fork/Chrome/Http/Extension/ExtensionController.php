<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Http\Extension;

use App\Fork\AutoPost\Shop\ShopSync;
use App\Fork\AutoPost\Stats\CommentIngest;
use App\Fork\AutoPost\Stats\StatsIngest;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeAccount;
use App\Fork\Chrome\Models\ChromeClient;
use App\Fork\Chrome\Models\ChromeJob;
use App\Fork\Chrome\Support\ChromeAccountLinker;
use App\Fork\AutoPost\Media\ChannelAvatars;
use App\Models\SocialAccount;
use App\Models\Workspace;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use InvalidArgumentException;
use stdClass;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpFoundation\StreamedResponse;

/**
 * /api/ext/*: giao thức v1 giữa tiện ích TikTok Auto Kid và TikTok Auto Kid.
 * Giao thức: extension/autotok/PROTOCOL.md (nguồn cũ: router Python ext.py).
 */
final class ExtensionController
{
    private const RELOAD_TEXT = 'Cần tải lại tiện ích (chrome://extensions → ⟳)';

    private const RUNNING = ['claimed', 'uploading', 'ready'];

    public function __construct(private readonly ChromeJobs $chrome, private readonly ShopSync $shop) {}

    public function pair(Request $request): JsonResponse
    {
        $body = $this->body($request);

        if (! $this->chrome->protocolOk($this->intOf($body['protocol'] ?? 0))) {
            throw new ExtError(409, 'need_reload', self::RELOAD_TEXT, ['need_reload' => true]);
        }

        $result = $this->chrome->usePairCode((string) ($body['code'] ?? ''));

        if (! $result['ok']) {
            if ($result['error'] === 'bad_code') {
                throw new ExtError(403, 'bad_code', 'Mã ghép nối sai', ['tries_left' => $result['tries_left']]);
            }

            throw new ExtError(410, 'no_code', 'Không có mã ghép nối đang hiệu lực — bấm tạo mã mới trong ứng dụng');
        }

        $created = $this->chrome->createClient(
            (string) $result['account_id'],
            mb_substr($this->text($body['label'] ?? null) ?: 'Chrome', 0, 128),
            mb_substr($this->text($body['ext_version'] ?? null), 0, 32),
            $this->intOf($body['protocol'] ?? 0),
        );

        return response()->json(['ok' => true, 'client_id' => $created['client']->id, 'token' => $created['token']]);
    }

    public function hello(Request $request): JsonResponse
    {
        $body = $this->body($request);
        $client = $this->client($request);

        $username = $userId = null;
        $identity = $body['identity'] ?? null;

        if (is_array($identity)) {
            $rawName = $this->text($identity['username'] ?? null);
            $rawId = $this->text($identity['user_id'] ?? null);

            if ($rawName !== '' && $rawId !== '') {
                $username = mb_substr($rawName, 0, 128);
                $userId = mb_substr($rawId, 0, 32);

                if (! preg_match('/^[0-9]{1,32}$/', $userId) || ! preg_match('/^[A-Za-z0-9_.\-]{1,128}$/', $username)) {
                    throw new ExtError(400, 'bad_request', 'identity must be {username: TikTok handle, user_id: digits}');
                }
            }
        }

        $protocol = array_key_exists('protocol', $body)
            ? $this->intOf($body['protocol'])
            : AuthenticateExtension::protocolOf($request);

        $this->chrome->touch($client, $protocol, [
            'tiktok_username' => $username,
            'tiktok_user_id' => $userId,
            'ext_version' => mb_substr($this->text($body['ext_version'] ?? null) ?: (string) $client->ext_version, 0, 32),
        ]);

        $client->refresh();

        // Chế độ một người dùng: tạo kênh TikTok ngay từ danh tính Chrome báo về, khỏi bấm "Kết nối kênh".
        if ($userId !== null && ChromeAccountLinker::automatic()) {
            $workspace = Workspace::query()->where('account_id', $client->account_id)->oldest()->first();

            if ($workspace) {
                ChromeAccountLinker::link($workspace, $client);
            }
        }

        $bound = $this->chrome->boundAccount($userId);
        $social = $bound ? SocialAccount::find($bound->social_account_id) : null;

        // Ảnh đại diện TikTok (tiện ích v1.3+): tải về máy, tối đa mỗi ngày một lần. Lỗi ảnh không làm hỏng hello.
        $avatar = is_array($identity) ? $this->text($identity['avatar_url'] ?? null) : '';

        if ($social && $avatar !== '' && ChannelAvatars::needsRefresh($social)) {
            try {
                app(ChannelAvatars::class)->store($social, $avatar);
            } catch (\Throwable $e) {
                report($e);
            }
        }

        $need = ! $this->chrome->protocolOk($protocol);

        return response()->json([
            'ok' => true,
            'client_id' => $client->id,
            'protocol_min' => ChromeJobs::PROTOCOL_MIN,
            'protocol_max' => ChromeJobs::PROTOCOL_MAX,
            'need_reload' => $need,
            'message' => $need ? self::RELOAD_TEXT : '',
            'server_time' => now()->utc()->format('Y-m-d\TH:i:s\Z'),
            'account' => $social ? ['id' => $social->id, 'username' => $social->username, 'publisher' => 'chrome'] : null,
            'avatar_ok' => $social ? filled($social->getRawOriginal('avatar_url')) : null,
            'conflict' => $userId !== null && $this->chrome->inConflict($client),
        ]);
    }

    public function next(Request $request): Response
    {
        $client = $this->client($request);
        $this->assertProtocol($request);

        if (! $client->tiktok_user_id) {
            throw new ExtError(409, 'no_identity', 'Chrome chưa đăng nhập TikTok (gửi hello sau khi đăng nhập)');
        }

        if ($this->chrome->inConflict($client)) {
            throw new ExtError(409, 'identity_conflict', 'Có hai hồ sơ Chrome cùng một tài khoản TikTok — gỡ bớt một trong ứng dụng');
        }

        $max = (float) config('fork.chrome.next_max_wait', 20);
        $wait = min(max((float) $request->query('wait', 0), 0.0), $max);
        $end = microtime(true) + $wait;

        while (true) {
            $this->chrome->reconcile();
            $job = $this->chrome->claimNext($client);

            if ($job !== null) {
                return response()->json($this->chrome->jobPayload($job, $client));
            }

            if (microtime(true) >= $end || connection_aborted()) {
                return response()->noContent();
            }

            sleep(1);
        }
    }

    /** K4: việc đang chờ tiện ích làm. Hiện chỉ có `sync_products` (request_id khi chủ app bấm "Lấy sản phẩm từ shop"). */
    public function tasks(Request $request): JsonResponse
    {
        $client = $this->client($request);
        $bound = filled($client->tiktok_user_id) ? $this->chrome->boundAccount((string) $client->tiktok_user_id) : null;

        return response()->json([
            'sync_products' => $bound ? $this->shop->pendingRequest((string) $bound->social_account_id) : null,
        ]);
    }

    /** K4: tiện ích gửi danh sách sản phẩm TikTok Shop của kênh. */
    public function products(Request $request): JsonResponse
    {
        $body = $this->body($request);
        $account = $this->shopAccount($request, $body);

        $source = $body['source'] ?? null;

        if (! is_string($source) || ! in_array($source, ShopSync::SOURCES, true)) {
            throw new ExtError(400, 'bad_request', 'source phải là my_shop hoặc showcase');
        }

        try {
            $products = $this->shop->normalizeProducts($body['products'] ?? null);
        } catch (InvalidArgumentException $e) {
            throw new ExtError(400, 'bad_request', $e->getMessage());
        }

        $result = $this->shop->ingestProducts(
            (string) $account->social_account_id,
            mb_substr($this->text($body['request_id'] ?? null), 0, 64),
            $source,
            $products,
            ($body['complete'] ?? null) === true,
        );

        return response()->json(['ok' => true, ...$result]);
    }

    /** K4: tiện ích gửi mẫu anchors bắt được khi chủ app tự đăng tay một bài có sản phẩm. */
    public function anchorTemplate(Request $request): JsonResponse
    {
        // Giải mã KHÔNG assoc để giữ nguyên object rỗng và số nguyên lớn trong anchors (verbatim).
        $raw = json_decode($request->getContent(), false, 512, JSON_BIGINT_AS_STRING);

        if (! $raw instanceof stdClass) {
            throw new ExtError(400, 'bad_request', 'body must be a JSON object');
        }

        $account = $this->shopAccount($request, (array) $raw);
        $productId = $raw->product_id ?? null;

        try {
            $this->shop->saveTemplate(
                (string) $account->social_account_id,
                is_string($productId) ? $productId : '',
                $raw->anchors ?? null,
                $raw->captured_at ?? null,
            );
        } catch (InvalidArgumentException $e) {
            throw new ExtError(400, 'bad_request', $e->getMessage());
        }

        return response()->json(['ok' => true]);
    }

    /** v1.4: số liệu video + số người theo dõi do tiện ích đọc từ TikTok Studio (chỉ ghi vào bảng số liệu, không đụng lịch đăng). */
    public function stats(Request $request): JsonResponse
    {
        $body = $this->body($request);
        $account = $this->shopAccount($request, $body);
        $social = SocialAccount::query()->find($account->social_account_id)
            ?? throw new ExtError(409, 'no_account', 'Tài khoản TikTok này chưa được bật đăng qua Chrome trong ứng dụng');

        if (! is_array($body['videos'] ?? []) && ! is_array($body['account'] ?? [])) {
            throw new ExtError(400, 'bad_request', 'videos phải là mảng');
        }

        return response()->json(['ok' => true, ...app(StatsIngest::class)->ingest($social, $body)]);
    }

    /** v1.4: bình luận mới trên video của kênh (đã lọc phía tiện ích tới bình luận đã thấy lần trước). */
    public function comments(Request $request): JsonResponse
    {
        $body = $this->body($request);
        $account = $this->shopAccount($request, $body);
        $social = SocialAccount::query()->find($account->social_account_id)
            ?? throw new ExtError(409, 'no_account', 'Tài khoản TikTok này chưa được bật đăng qua Chrome trong ứng dụng');

        if (! is_array($body['comments'] ?? null)) {
            throw new ExtError(400, 'bad_request', 'comments phải là mảng');
        }

        return response()->json(['ok' => true, ...app(CommentIngest::class)->ingest($social, $body['comments'])]);
    }

    public function videoMeta(Request $request): JsonResponse
    {
        $job = $this->videoJob($request);
        $path = $this->videoPath($job);

        return response()->json([
            'name' => $job->video_name,
            'size' => filesize($path),
            'type' => $this->libraryType((string) $job->video_name),
        ]);
    }

    public function video(Request $request): Response
    {
        $job = $this->videoJob($request);
        $path = $this->videoPath($job);
        $size = (int) filesize($path);
        $type = $this->libraryType((string) $job->video_name);
        $contentRange = 'Content-'.'Range';

        $start = 0;
        $end = $size - 1;
        $status = 200;
        $range = $request->headers->get('Range');

        if ($range !== null && $range !== '') {
            if (! preg_match('/^bytes=(\d*)-(\d*)$/', trim($range), $m) || ($m[1] === '' && $m[2] === '')) {
                return response('', 416, [$contentRange => "bytes */{$size}"]);
            }

            if ($m[1] !== '') {
                $start = (int) $m[1];
                $end = $m[2] !== '' ? min((int) $m[2], $size - 1) : $size - 1;
            } else {
                $start = max($size - (int) $m[2], 0);
            }

            if ($start >= $size || $start > $end) {
                return response('', 416, [$contentRange => "bytes */{$size}"]);
            }

            $status = 206;
        }

        $length = $end - $start + 1;
        $headers = [
            'Content-Type' => $type,
            'Accept-Ranges' => 'bytes',
            'Content-Length' => (string) $length,
        ];

        if ($status === 206) {
            $headers[$contentRange] = "bytes {$start}-{$end}/{$size}";
        }

        return new StreamedResponse(function () use ($path, $start, $length): void {
            $handle = fopen($path, 'rb');

            if ($handle === false) {
                return;
            }

            fseek($handle, $start);
            $left = $length;

            while ($left > 0 && ! feof($handle)) {
                $buffer = fread($handle, min(1 << 20, $left));

                if ($buffer === false || $buffer === '') {
                    break;
                }

                $left -= strlen($buffer);
                echo $buffer;
                flush();
            }

            fclose($handle);
        }, $status, $headers);
    }

    /** Ảnh bìa riêng của job (jpg <= 5 MB). Cùng điều kiện truy cập với /api/ext/video. */
    public function cover(Request $request): Response
    {
        $job = $this->videoJob($request);
        $cv = is_array($job->options['cover'] ?? null) ? $job->options['cover'] : null;
        $product = $cv === null ? null : \App\Fork\AutoPost\Models\AutoProduct::query()->find((string) ($cv['code'] ?? ''));
        $path = $product === null ? null : \App\Fork\AutoPost\Persona\CoverStore::pathFor($product, (string) ($cv['file'] ?? ''));

        if ($path === null) {
            throw new ExtError(404, 'unknown_job', 'việc này không có ảnh bìa (hoặc file đã mất)');
        }

        return response()->file($path, ['Content-Type' => 'image/jpeg', 'Cache-Control' => 'no-store']);
    }

    public function progress(Request $request): JsonResponse
    {
        $body = $this->body($request);
        $job = $this->owned($body);
        $state = $this->chrome->heartbeat($job, ($body['phase'] ?? null) === 'ready');

        if ($state === 'revoked') {
            return response()->json(['ok' => false, 'state' => $state, 'cancelled' => true]);
        }

        return response()->json(['ok' => in_array($state, [...self::RUNNING, 'authorized'], true), 'state' => $state]);
    }

    public function authorize(Request $request): JsonResponse
    {
        $body = $this->body($request);
        $client = $this->client($request);
        $job = $this->owned($body);

        $reason = $this->chrome->authorizeRefusal($job, $client, $body, AuthenticateExtension::protocolOf($request));

        if ($reason === null) {
            try {
                $granted = $this->chrome->authorize(
                    $job,
                    is_string($body['body_sha256'] ?? null) ? $body['body_sha256'] : '',
                    is_string($body['creation_id'] ?? null) ? $body['creation_id'] : '',
                );
            } catch (\Throwable $e) {
                report($e);

                throw new ExtError(500, 'persist_failed', 'không ghi được quyền đăng — không đăng');
            }

            if ($granted) {
                return response()->json(['ok' => true]);
            }

            $job->refresh();
            $reason = $this->chrome->stateRefusal($job) ?? 'not-ready';
        }

        return response()->json(['ok' => false, 'reason' => $reason]);
    }

    public function result(Request $request): JsonResponse
    {
        $body = $this->body($request);
        $job = $this->owned($body);

        $outcome = $this->chrome->ingestResult($job->id, $body);
        $this->chrome->reconcile();

        return response()->json(['ok' => true, 'duplicate' => $outcome['duplicate'], 'state' => $outcome['state']]);
    }

    public function cancel(Request $request): JsonResponse
    {
        $body = $this->body($request);
        $job = $this->owned($body);

        // requestCancel tự nối CANCEL_TEXT, chỉ truyền lý do thô.
        $outcome = $this->chrome->requestCancel($job, $this->text($body['reason'] ?? null));
        $this->chrome->reconcile();

        return response()->json(['ok' => true, 'state' => $outcome['state'], 'cancel_recorded' => $outcome['cancel_recorded']]);
    }

    public function jobState(Request $request): JsonResponse
    {
        $job = $this->job($request->query('id'));

        return response()->json(['ok' => true, 'state' => $job->state, 'authorized' => $job->authorized_at !== null]);
    }

    public function preflight(): Response
    {
        return response()->noContent();
    }

    // ---------- helpers ----------

    /**
     * Tài khoản TikTok Auto Kid mà request giỏ hàng nói tới. user_id/username trong body phải khớp danh tính
     * Chrome này đã khai báo (hello), nếu không thì 409: không bao giờ ghi dữ liệu của kênh khác vào kênh này.
     *
     * @param  array<string, mixed>  $body
     */
    private function shopAccount(Request $request, array $body): ChromeAccount
    {
        $client = $this->client($request);

        if (blank($client->tiktok_user_id) || blank($client->tiktok_username)) {
            throw new ExtError(409, 'no_identity', 'Chrome chưa đăng nhập TikTok (gửi hello sau khi đăng nhập)');
        }

        $userId = $this->text($body['user_id'] ?? null);
        $username = $this->text($body['username'] ?? null);

        if ($userId !== (string) $client->tiktok_user_id || strcasecmp($username, (string) $client->tiktok_username) !== 0) {
            throw new ExtError(409, 'identity_mismatch', 'Tài khoản TikTok trong yêu cầu không khớp Chrome này');
        }

        return $this->chrome->boundAccount($userId)
            ?? throw new ExtError(409, 'no_account', 'Tài khoản TikTok này chưa được bật đăng qua Chrome trong ứng dụng');
    }

    private function client(Request $request): ChromeClient
    {
        return $request->attributes->get(AuthenticateExtension::CLIENT_ATTRIBUTE);
    }

    private function assertProtocol(Request $request): void
    {
        if (! $this->chrome->protocolOk(AuthenticateExtension::protocolOf($request))) {
            throw new ExtError(409, 'need_reload', self::RELOAD_TEXT, ['need_reload' => true]);
        }
    }

    /** @return array<string, mixed> */
    private function body(Request $request): array
    {
        $decoded = json_decode($request->getContent(), true);

        if (! is_array($decoded) || ($decoded !== [] && array_is_list($decoded))) {
            throw new ExtError(400, 'bad_request', $decoded === null ? 'invalid JSON' : 'body must be a JSON object');
        }

        return $decoded;
    }

    private function job(mixed $id): ChromeJob
    {
        $job = is_string($id) && $id !== '' ? ChromeJob::query()->find($id) : null;

        if ($job === null) {
            throw new ExtError(404, 'unknown_job', 'máy chủ không còn việc này');
        }

        return $job;
    }

    /** @param array<string, mixed> $body */
    private function owned(array $body): ChromeJob
    {
        $job = $this->job($body['id'] ?? null);

        $nonce = $body['nonce'] ?? null;
        $claim = $body['claim_token'] ?? null;

        if (! is_string($nonce) || ! is_string($claim) || ! $job->claim_token || ! $job->nonce
            || ! hash_equals((string) $job->nonce, $nonce) || ! hash_equals((string) $job->claim_token, $claim)) {
            throw new ExtError(403, 'bad_nonce', 'nonce/claim_token không khớp');
        }

        return $job;
    }

    private function videoJob(Request $request): ChromeJob
    {
        $job = $this->job($request->query('id'));

        if ((int) $job->claim_client_id !== (int) $this->client($request)->id || ! in_array($job->state, self::RUNNING, true)) {
            throw new ExtError(403, 'bad_nonce', 'việc này không thuộc Chrome này hoặc đã xong');
        }

        return $job;
    }

    private function videoPath(ChromeJob $job): string
    {
        $relative = (string) $job->media_path;
        $disk = Storage::disk();

        if ($relative === '' || ! $disk->exists($relative)) {
            throw new ExtError(404, 'unknown_job', 'không thấy file video của việc này');
        }

        try {
            $path = $disk->path($relative);
        } catch (\Throwable) {
            throw new ExtError(404, 'unknown_job', 'không đọc được file video từ ổ lưu trữ này');
        }

        if (! is_file($path)) {
            throw new ExtError(404, 'unknown_job', 'không thấy file video của việc này');
        }

        return $path;
    }

    private function libraryType(string $name): string
    {
        return match (strtolower(strrchr($name, '.') ?: '')) {
            '.webm' => 'video/webm',
            '.mov' => 'video/quicktime',
            default => 'video/mp4',
        };
    }

    private function text(mixed $value): string
    {
        return is_scalar($value) && ! is_bool($value) ? trim((string) $value) : '';
    }

    private function intOf(mixed $value): int
    {
        $int = filter_var($value, FILTER_VALIDATE_INT);

        return $int === false ? 0 : $int;
    }
}

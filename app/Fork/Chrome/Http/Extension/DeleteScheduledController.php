<?php

declare(strict_types=1);

namespace App\Fork\Chrome\Http\Extension;

use App\Fork\AutoPost\Scheduling\Reschedules;
use App\Fork\Chrome\ChromeJobs;
use App\Fork\Chrome\Models\ChromeClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use InvalidArgumentException;

/**
 * PROTOCOL.md mục 12: tiện ích xoá một bài đã hẹn trên TikTok (để "Đổi giờ") rồi kiểm lại bằng danh sách bài.
 * Việc được giao qua GET /api/ext/tasks (`delete_scheduled`); ở đây chỉ có nhận việc và báo kết quả.
 */
final class DeleteScheduledController
{
    public function __construct(private readonly Reschedules $reschedules, private readonly ChromeJobs $chrome) {}

    public function claim(Request $request): JsonResponse
    {
        if (! $this->chrome->protocolOk(AuthenticateExtension::protocolOf($request))) {
            throw new ExtError(409, 'need_reload', 'Cần tải lại tiện ích (chrome://extensions → ⟳)', ['need_reload' => true]);
        }

        $body = $this->body($request);
        $client = $this->client($request);

        if ($this->chrome->inConflict($client)) {
            return response()->json(['ok' => false, 'reason' => 'identity-conflict']);
        }

        return response()->json($this->guard(fn (): array => $this->reschedules->claim($this->str($body['id'] ?? null), $this->str($body['nonce'] ?? null), $client)));
    }

    public function result(Request $request): JsonResponse
    {
        $body = $this->body($request);
        $out = $this->guard(fn (): array => $this->reschedules->ingestResult($this->str($body['id'] ?? null), $this->str($body['nonce'] ?? null), $body));

        return response()->json(['ok' => true, ...$out]);
    }

    /** @return array<string, mixed> */
    private function guard(callable $fn): array
    {
        try {
            return $fn();
        } catch (InvalidArgumentException $e) {
            throw $e->getMessage() === 'bad_nonce'
                ? new ExtError(403, 'bad_nonce', 'nonce không khớp')
                : new ExtError(404, 'unknown_job', 'máy chủ không còn việc này');
        }
    }

    private function client(Request $request): ChromeClient
    {
        return $request->attributes->get(AuthenticateExtension::CLIENT_ATTRIBUTE);
    }

    /** @return array<string, mixed> */
    private function body(Request $request): array
    {
        $decoded = json_decode($request->getContent(), true);

        if (! is_array($decoded) || ($decoded !== [] && array_is_list($decoded))) {
            throw new ExtError(400, 'bad_request', 'body must be a JSON object');
        }

        return $decoded;
    }

    private function str(mixed $v): string
    {
        return is_string($v) ? trim($v) : '';
    }
}

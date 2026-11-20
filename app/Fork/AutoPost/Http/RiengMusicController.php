<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Rieng\RiengFolder;
use App\Fork\AutoPost\Rieng\RiengMusic;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

/** Nhạc trong hộp Đăng hàng loạt của Kho riêng: nhạc mặc định của thư mục video, danh sách bài, nghe thử. */
final class RiengMusicController extends Controller
{
    use ScopesToOwner;

    private const array MIME = [
        'mp3' => 'audio/mpeg', 'm4a' => 'audio/mp4', 'aac' => 'audio/aac', 'wav' => 'audio/wav',
        'ogg' => 'audio/ogg', 'flac' => 'audio/flac', 'opus' => 'audio/ogg',
    ];

    /** Cài đặt nhạc của thư mục đầu tiên (trong các video chọn) đang bật ghép nhạc; null = không có. */
    public function defaults(Request $request): JsonResponse
    {
        $this->authorizeOwner($request);
        $ids = $request->validate(['ids' => ['required', 'array', 'max:200'], 'ids.*' => ['integer']])['ids'];
        $folderIds = AutoVideo::query()->whereIn('id', $ids)->where('source', AutoVideo::SOURCE_RIENG)->orderBy('id')->get()
            ->map(fn (AutoVideo $v): int => (int) data_get($v->meta, 'folder_id'))->unique();
        $music = $folderIds->map(fn (int $id): array => RiengMusic::settings(RiengFolder::query()->find($id)))->first(fn (array $s): bool => $s['enabled']);

        return response()->json(['ok' => true, 'music' => $music]);
    }

    /** Bài nhạc của một thư mục + thứ tự bốc cố định theo seed (giao diện và máy chủ chia nhạc y hệt nhau). */
    public function tracks(Request $request, RiengMusic $music): JsonResponse
    {
        $this->authorizeOwner($request);
        $data = $request->validate(['dir' => ['required', 'string', 'max:500'], 'seed' => ['nullable', 'integer']]);
        $tracks = $music->list(trim($data['dir']));

        return response()->json(['ok' => true, 'tracks' => $tracks, 'plan' => RiengMusic::plan(array_column($tracks, 'rel'), (int) ($data['seed'] ?? 0))]);
    }

    /** Nghe thử một bài: chỉ file nhạc nằm trong thư mục nhạc đã chọn (Range do BinaryFileResponse lo). */
    public function listen(Request $request, RiengMusic $music): BinaryFileResponse
    {
        $this->authorizeOwner($request);
        $file = $music->resolveIn(trim((string) $request->query('dir', '')), (string) $request->query('rel', ''));
        abort_if($file === null, 404);

        return response()->file($file, ['Content-Type' => self::MIME[strtolower(pathinfo($file, PATHINFO_EXTENSION))] ?? 'audio/mpeg', 'Cache-Control' => 'private, max-age=600']);
    }
}

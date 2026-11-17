<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Rieng\RiengMusic;
use App\Fork\AutoPost\Scheduling\PostEdits;
use App\Http\Controllers\Controller;
use App\Models\Media;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

/**
 * Sửa bài đã xếp lịch mà chưa đăng (giờ, kênh, caption, hashtag, ảnh bìa), "Bỏ xếp lịch" và "Cho xếp lịch lại".
 * JSON cho khung xem video và Lịch đăng; logic ở PostEdits.
 */
final class PostEditController extends Controller
{
    use ScopesToOwner;

    public function show(Request $request, AutoVideo $video, PostEdits $edits): JsonResponse
    {
        $this->own($request, $video, true);

        return response()->json($edits->describe($video));
    }

    public function update(Request $request, AutoVideo $video, PostEdits $edits): JsonResponse
    {
        $this->own($request, $video);
        $data = $request->validate([
            'at' => ['nullable', 'string', 'max:40'],
            'social_account_id' => ['nullable', 'string', 'max:64'],
            'caption' => ['nullable', 'string', 'max:5000'],
            'hashtags' => ['nullable', 'array', 'max:60'],
            'hashtags.*' => ['string', 'max:120'],
            'cover_token' => ['nullable', 'string', 'max:120'],
            'cover_reset' => ['nullable', 'boolean'],
            'music' => ['nullable', 'string', 'max:500'],
        ]);

        return $this->run($video, $edits, fn () => $edits->edit($video, $data));
    }

    public function unschedule(Request $request, AutoVideo $video, PostEdits $edits): JsonResponse
    {
        $this->own($request, $video);

        return $this->run($video, $edits, fn () => $edits->unschedule($video));
    }

    /** Nghe / xem bản sẽ đăng (đã ghép nhạc) của bài đã xếp lịch. */
    public function postedFile(Request $request, AutoVideo $video): BinaryFileResponse
    {
        $this->own($request, $video);
        $path = $video->post_id ? Media::query()->where('post_id', $video->post_id)->where('collection', Media::COLLECTION_MEDIA)->orderBy('order')->value('path') : null;
        abort_if($path === null || ! Storage::exists((string) $path), 404);

        return response()->file(Storage::path((string) $path), ['Content-Type' => 'video/mp4', 'Cache-Control' => 'no-store']);
    }

    /** Nghe thử một bài trong thư mục nhạc của video (chỉ bài nằm trong thư mục nhạc). */
    public function musicTrack(Request $request, AutoVideo $video, RiengMusic $music): BinaryFileResponse
    {
        $this->own($request, $video, true);
        $file = $music->resolve($video, (string) $request->query('rel', ''));
        abort_if($file === null || ! is_file($file), 404);

        return response()->file($file, ['Cache-Control' => 'no-store']);
    }

    public function remove(Request $request, AutoVideo $video, PostEdits $edits): JsonResponse
    {
        $this->own($request, $video, true);

        return $this->run($video, $edits, fn () => $edits->remove($video));
    }

    public function release(Request $request, AutoVideo $video, PostEdits $edits): JsonResponse
    {
        $this->own($request, $video, true);
        $edits->release($video);

        return response()->json(['ok' => true, 'message' => 'Video đã được cho xếp lịch lại.']);
    }

    /** @param  callable(): array<string, mixed>  $fn */
    private function run(AutoVideo $video, PostEdits $edits, callable $fn): JsonResponse
    {
        try {
            $result = $fn();
        } catch (RuntimeException $e) {
            return response()->json(['ok' => false, 'message' => $e->getMessage(), ...$edits->describe($video->refresh())], 422);
        }

        return response()->json(['ok' => true, ...$result, ...$edits->describe($video->refresh())]);
    }

    /** Video đã về kho (không còn kênh) vẫn của chủ app; còn kênh thì kênh phải thuộc chủ app. */
    private function own(Request $request, AutoVideo $video, bool $allowUnassigned = false): void
    {
        $accounts = $this->tiktokAccounts($this->authorizeOwner($request));

        if ($video->social_account_id === null) {
            abort_unless($allowUnassigned, 404);

            return;
        }

        abort_unless($accounts->contains('id', $video->social_account_id), 404);
    }
}

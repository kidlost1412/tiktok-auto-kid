<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\KhoStore;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Paths;
use App\Fork\AutoPost\Persona\CoverStore;
use App\Fork\AutoPost\Rieng\RiengBatch;
use App\Fork\AutoPost\Rieng\RiengCovers;
use App\Fork\AutoPost\Rieng\RiengFolder;
use App\Fork\AutoPost\Rieng\RiengScanner;
use App\Fork\AutoPost\Rieng\RiengThumbs;
use App\Fork\AutoPost\Scheduling\Planner;
use App\Fork\AutoPost\Scheduling\RetryFailed;
use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use InvalidArgumentException;
use Inertia\Inertia;
use Inertia\Response;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

/**
 * "Kho riêng": video chủ app tự làm. Quản lý thư mục, quét, danh sách và đăng hàng loạt (chọn nhiều video, gắn giỏ, hẹn giờ).
 * App chỉ đọc các thư mục này; bỏ thư mục khỏi danh sách không bao giờ xoá file.
 */
final class RiengController extends Controller
{
    use ScopesToOwner;

    private const int PER_PAGE = 24;

    /** Bộ lọc trạng thái trong danh sách. */
    private const array STATUS = ['chua', 'hen', 'dang', 'loi'];

    public function index(Request $request): Response
    {
        $accountId = $this->authorizeOwner($request);

        $folderId = $request->query('folder');
        $folderId = is_string($folderId) && ctype_digit($folderId) ? (int) $folderId : 0;
        $status = $request->query('status');
        $status = is_string($status) && in_array($status, self::STATUS, true) ? $status : '';
        $day = $request->query('day');
        $day = is_string($day) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $day) === 1 ? $day : '';

        $folders = RiengFolder::query()->orderBy('id')->get();
        $base = fn (): Builder => AutoVideo::query()->where('source', AutoVideo::SOURCE_RIENG);
        $filtered = fn (): Builder => $base()
            ->when($folderId > 0, fn ($q) => $q->where('meta->folder_id', (string) $folderId))
            ->when($day !== '', fn ($q) => $q->whereDate('batch_date', $day))
            ->tap(fn ($q) => $this->applyStatus($q, $status));

        $statusCounts = [];

        foreach (['chua', 'hen', 'dang', 'loi'] as $key) {
            $statusCounts[$key] = $base()->tap(fn ($q) => $this->applyStatus($q, $key))->count();
        }

        $videos = $filtered()
            ->with('socialAccount:id,username,display_name,avatar_url')
            ->orderByDesc('batch_date')
            ->orderByDesc('id')
            ->paginate(self::PER_PAGE)
            ->withQueryString();

        $names = $folders->mapWithKeys(fn (RiengFolder $f): array => [$f->id => $f->displayName()]);
        $selectable = $filtered()
            ->where(fn ($q) => $q->where(fn ($n) => $n->where('status', AutoVideo::NEW)->whereNull('files_deleted_at'))->orWhere('status', AutoVideo::FAILED))
            ->orderByDesc('batch_date')->orderByDesc('id')->limit(1000)->get(['id', 'file_name', 'duration'])
            ->map(fn (AutoVideo $v): array => ['id' => $v->id, 'file_name' => $v->file_name, 'duration' => $v->duration])->all();

        $folderCounts = $base()->selectRaw("meta->>'folder_id' as fid, count(*) as total")->groupByRaw("meta->>'folder_id'")->pluck('total', 'fid');

        return Inertia::render('fork/KhoRieng', [
            'folders' => $folders->map(fn (RiengFolder $f): array => [
                'id' => $f->id,
                'name' => $f->displayName(),
                'path' => str_replace('/', '\\', (string) $f->path),
                'exists' => is_dir((string) $f->path),
                'count' => (int) ($folderCounts[(string) $f->id] ?? 0),
            ])->values()->all(),
            'filters' => ['folder' => $folderId, 'status' => $status, 'day' => $day],
            'counts' => $statusCounts + ['all' => $base()->count()],
            'days' => $base()->select('batch_date')->distinct()->orderByDesc('batch_date')->limit(120)->pluck('batch_date')
                ->map(fn ($d): string => $d->format('Y-m-d'))->values()->all(),
            'videos' => [
                'data' => $videos->getCollection()->map(fn (AutoVideo $v): array => $this->row($v, $names))->values()->all(),
                'current_page' => $videos->currentPage(),
                'last_page' => $videos->lastPage(),
                'total' => $videos->total(),
            ],
            'selectable' => $selectable,
            'accounts' => $this->accounts($accountId),
            'limits' => ['min_lead_minutes' => intdiv(Planner::MIN_LEAD, 60), 'gap_minutes' => intdiv(app(Planner::class)->gapSeconds(), 60), 'caption_max' => 2200],
            'last_scan_at' => Cache::get('fork-rieng:last-scan'),
        ]);
    }

    /** @param  Builder<AutoVideo>  $q */
    private function applyStatus($q, string $status): void
    {
        match ($status) {
            'chua' => $q->where('status', AutoVideo::NEW),
            'hen' => $q->where(fn ($w) => $w->whereIn('status', [AutoVideo::RESERVED, AutoVideo::SCHEDULED])->orWhere(fn ($h) => $h->heldOnTikTok())),
            'dang' => $q->livePosted(),
            'loi' => $q->whereIn('status', [AutoVideo::FAILED, AutoVideo::SKIPPED]),
            default => null,
        };
    }

    /**
     * @param  \Illuminate\Support\Collection<int, string>  $names
     * @return array<string, mixed>
     */
    private function row(AutoVideo $v, $names): array
    {
        $held = $v->status === AutoVideo::POSTED && $v->posted_at?->isFuture();
        $tz = RiengScanner::TZ;
        $link = data_get($v->stats, 'link');
        $gone = $v->files_deleted_at !== null;

        return [
            'id' => $v->id,
            'file_name' => $v->file_name,
            'folder' => (string) ($names[(int) data_get($v->meta, 'folder_id')] ?? 'Thư mục đã bỏ'),
            'rel_path' => data_get($v->meta, 'rel_path'),
            'file_date' => $v->batch_date?->format('Y-m-d'),
            'file_time' => data_get($v->meta, 'file_mtime'),
            'duration' => $v->duration,
            'status' => $v->effectiveStatus(),
            'gone' => $gone,
            'channel' => $v->socialAccount ? '@'.($v->socialAccount->username ?: $v->socialAccount->display_name) : null,
            'scheduled_for' => ($held ? $v->posted_at : $v->scheduled_for)?->copy()->timezone($tz)->toIso8601String(),
            'posted_at' => $held ? null : $v->posted_at?->copy()->timezone($tz)->toIso8601String(),
            'tiktok_link' => is_string($link) && preg_match('#^https://#i', $link) === 1 ? $link : null,
            'reason' => $v->skip_reason,
            'caption' => $v->caption,
            'can_retry' => $v->status === AutoVideo::FAILED && app(RetryFailed::class)->refusal($v) === null,
            'selectable' => ($v->status === AutoVideo::NEW && ! $gone) || $v->status === AutoVideo::FAILED,
            'can_preview' => ! $gone && is_file((string) $v->path),
        ];
    }

    /**
     * Kênh dùng được để đăng hàng loạt + sản phẩm có giỏ hàng hợp lệ trên từng kênh.
     *
     * @return list<array<string, mixed>>
     */
    private function accounts(string $accountId): array
    {
        $planner = app(Planner::class);
        $batch = app(RiengBatch::class);
        $autos = AutoAccount::query()->get()->keyBy('social_account_id');

        return $this->tiktokAccounts($accountId)
            ->filter(fn (SocialAccount $a): bool => $autos->has($a->id))
            ->map(function (SocialAccount $a) use ($autos, $planner, $batch): array {
                $auto = $autos[$a->id];
                $why = $planner->ineligible($auto);
                $options = $why === null ? $batch->productOptions((string) $a->id) : [];

                return [
                    'id' => $a->id,
                    'name' => '@'.($a->username ?: $a->display_name),
                    'avatar_url' => $a->avatar_url,
                    'auto_enabled' => (bool) $auto->enabled,
                    'usable' => $why === null && $options !== [],
                    'unusable_reason' => $why !== null ? $why : ($options === [] ? 'chưa có sản phẩm nào gắn giỏ hàng hợp lệ trên kênh này (vào mục Giỏ hàng để chọn)' : null),
                    'ahead_days' => $planner->aheadDays($auto),
                    'products' => $options,
                ];
            })->values()->all();
    }

    // ------------------------------------------------------------------ Thư mục

    public function addFolder(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);
        $data = $request->validate(['path' => ['required', 'string', 'max:500'], 'name' => ['nullable', 'string', 'max:80']]);

        $raw = trim((string) $data['path'], " \t\n\r\0\x0B\"'");
        $real = $raw !== '' && ! str_contains($raw, "\0") ? realpath($raw) : false;

        if ($real === false || ! is_dir($real)) {
            return back()->with('flash.error', 'Không tìm thấy thư mục này trên máy. Hãy dán đúng đường dẫn đầy đủ, ví dụ D:\Video\Video-cua-toi.');
        }

        $path = rtrim(Paths::slash($real), '/');
        $hub = realpath(app(KhoStore::class)->hub());

        if ($hub !== false && (Paths::isUnder($real, $hub) || Paths::isUnder($hub, $real) || strcasecmp(Paths::slash($real), Paths::slash($hub)) === 0)) {
            return back()->with('flash.error', 'Đây là thư mục của Xưởng Video (hoặc chứa nó). Hãy chọn một thư mục riêng cho video bạn tự làm.');
        }

        foreach (RiengFolder::query()->get() as $f) {
            if (strcasecmp((string) $f->path, $path) === 0) {
                return back()->with('flash.error', 'Thư mục này đã có trong danh sách rồi.');
            }

            if (Paths::isUnder($path, (string) $f->path) || Paths::isUnder((string) $f->path, $path)) {
                return back()->with('flash.error', 'Thư mục này nằm trong (hoặc chứa) một thư mục đã thêm, nên video sẽ bị đếm hai lần. Hãy chọn thư mục khác.');
            }
        }

        RiengFolder::query()->create(['path' => $path, 'name' => filled($data['name'] ?? null) ? trim((string) $data['name']) : null]);
        $r = app(RiengScanner::class)->scan();

        return back()->with('flash.success', "Đã thêm thư mục. Tìm thấy {$r['new']} video mới".($r['waiting'] > 0 ? ", {$r['waiting']} video đang chờ ghi xong" : '').'.');
    }

    /** Bỏ thư mục khỏi Kho riêng: chỉ xoá dòng trong app (video chưa đăng của thư mục này cũng bị bỏ khỏi danh sách); KHÔNG xoá file nào. */
    public function removeFolder(Request $request, RiengFolder $folder): RedirectResponse
    {
        $this->authorizeOwner($request);
        $thumbs = app(RiengThumbs::class);

        $folder->videosQuery()->where('status', AutoVideo::NEW)->each(function (AutoVideo $v) use ($thumbs): void {
            $thumbs->forget($v);
            app(RiengCovers::class)->forget((int) $v->id);
            $v->delete();
        });
        $folder->delete();

        return back()->with('flash.success', 'Đã bỏ thư mục khỏi Kho riêng. File video trong thư mục vẫn còn nguyên.');
    }

    public function scan(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);
        set_time_limit(300);
        $r = app(RiengScanner::class)->scan();
        Cache::forever('fork-rieng:last-scan', now()->toIso8601String());

        $parts = ["{$r['new']} video mới"];
        $r['waiting'] > 0 && $parts[] = "{$r['waiting']} đang chờ ghi xong";
        $r['duplicate'] > 0 && $parts[] = "{$r['duplicate']} trùng video đã có";
        $r['gone'] > 0 && $parts[] = "{$r['gone']} không còn file";
        $r['folders_missing'] > 0 && $parts[] = "{$r['folders_missing']} thư mục không mở được";

        return back()->with('flash.success', 'Đã quét Kho riêng: '.implode(', ', $parts).'.');
    }

    // ------------------------------------------------------------------ File

    public function thumb(Request $request, AutoVideo $video): BinaryFileResponse|SymfonyResponse
    {
        $this->authorizeOwner($request);
        abort_unless($video->isRieng(), SymfonyResponse::HTTP_NOT_FOUND);

        $file = app(RiengThumbs::class)->get($video);
        abort_if($file === null, SymfonyResponse::HTTP_NOT_FOUND);

        return response()->file($file, ['Content-Type' => 'image/jpeg', 'Cache-Control' => 'private, max-age=86400']);
    }

    /** Đường dẫn thật của mp4 riêng nếu nó nằm dưới một thư mục Kho riêng đã đăng ký; không thì null. */
    public static function safeVideoPath(AutoVideo $video): ?string
    {
        $file = $video->files_deleted_at === null ? realpath((string) $video->path) : false;

        if ($file === false || strtolower(pathinfo($file, PATHINFO_EXTENSION)) !== 'mp4' || ! is_file($file)) {
            return null;
        }

        foreach (RiengFolder::query()->get() as $f) {
            $root = realpath((string) $f->path);

            if ($root !== false && Paths::isUnder($file, $root)) {
                return $file;
            }
        }

        return null;
    }

    // ------------------------------------------------------------------ Ảnh bìa (chọn trong hộp thoại đăng hàng loạt)

    /** Tải một ảnh bìa lên chỗ tạm. Cùng giới hạn với ảnh bìa sản phẩm (jpg/png/webp, tối đa 5 MB). */
    public function coverUpload(Request $request): JsonResponse
    {
        $this->authorizeOwner($request);
        $request->validate(['image' => ['required', 'file', 'max:'.(CoverStore::MAX_BYTES / 1024), 'mimes:jpg,jpeg,png,webp']], [
            'image.required' => 'Hãy chọn một ảnh.',
            'image.max' => 'Ảnh lớn hơn 5 MB.',
            'image.mimes' => 'Chỉ nhận ảnh jpg, png hoặc webp.',
            'image.file' => 'Không đọc được file ảnh.',
        ]);

        try {
            $token = app(RiengCovers::class)->stageUpload($request->file('image'));
        } catch (InvalidArgumentException $e) {
            return response()->json(['ok' => false, 'error' => $e->getMessage()], 422);
        }

        return response()->json(['ok' => true, 'token' => $token, 'url' => '/auto/kho/rieng/anh-bia/tam/'.$token]);
    }

    /** Lấy một khung hình của video (giây `t`) làm ảnh bìa, nguyên độ phân giải. */
    public function coverFrame(Request $request, AutoVideo $video): JsonResponse
    {
        $this->authorizeOwner($request);
        abort_unless($video->isRieng(), SymfonyResponse::HTTP_NOT_FOUND);
        $data = $request->validate(['t' => ['required', 'numeric', 'min:0', 'max:86400']]);

        try {
            $token = app(RiengCovers::class)->stageFrame($video, (float) $data['t']);
        } catch (InvalidArgumentException $e) {
            return response()->json(['ok' => false, 'error' => $e->getMessage()], 422);
        }

        return response()->json(['ok' => true, 'token' => $token, 'url' => '/auto/kho/rieng/anh-bia/tam/'.$token]);
    }

    public function coverTemp(Request $request, string $token): BinaryFileResponse|SymfonyResponse
    {
        $this->authorizeOwner($request);
        $path = app(RiengCovers::class)->tmpPath($token);
        abort_if($path === null, SymfonyResponse::HTTP_NOT_FOUND);

        return response()->file($path, ['Content-Type' => 'image/jpeg', 'Cache-Control' => 'private, max-age=3600']);
    }

    // ------------------------------------------------------------------ Đăng hàng loạt

    public function batchPreview(Request $request): JsonResponse
    {
        return $this->batch($request, false);
    }

    public function batchCommit(Request $request): JsonResponse
    {
        return $this->batch($request, true);
    }

    private function batch(Request $request, bool $commit): JsonResponse
    {
        $accountId = $this->authorizeOwner($request);
        set_time_limit(300);

        $in = $request->validate([
            'social_account_id' => ['required', 'string'],
            'product_code' => ['required', 'string', 'max:100'],
            'quy_cach' => ['nullable', 'string', 'max:100'],
            'caption' => ['nullable', 'string', 'max:5000'],
            'hashtags' => ['nullable'],
            'mode' => ['required', 'in:auto,manual'],
            'accept_warnings' => ['sometimes', 'boolean'],
            'items' => ['required', 'array', 'min:1', 'max:200'],
            'items.*.id' => ['required', 'integer'],
            'items.*.at' => ['nullable', 'string', 'max:40'],
            'items.*.caption' => ['nullable', 'string', 'max:5000'],
            'items.*.hashtags' => ['nullable'],
            'cover_mode' => ['sometimes', 'in:product,upload,frame'],
            'cover_token' => ['nullable', 'string', 'max:60'],
            'items.*.cover_token' => ['nullable', 'string', 'max:60'],
        ]);

        $this->findAccount($accountId, (string) $in['social_account_id']);
        $batch = app(RiengBatch::class);

        $result = $commit
            ? $batch->commit($in, (bool) ($in['accept_warnings'] ?? false))
            : $batch->preview($in);

        return response()->json($result);
    }
}

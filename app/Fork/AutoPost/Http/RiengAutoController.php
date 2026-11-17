<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\Console\RiengAiCommand;
use App\Fork\AutoPost\Models\AutoAccount;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Fork\AutoPost\Rieng\Ai\ChatGptAccounts;
use App\Fork\AutoPost\Rieng\Ai\RiengAiStatus;
use App\Fork\AutoPost\Rieng\Ai\RiengAnalyzer;
use App\Fork\AutoPost\Rieng\Ai\RiengAutoPoster;
use App\Fork\AutoPost\Rieng\Ai\RiengAutoSettings;
use App\Fork\AutoPost\Rieng\Ai\RiengSpeech;
use App\Fork\AutoPost\Rieng\RiengFolder;
use App\Fork\AutoPost\Shop\CartRules;
use App\Http\Controllers\Controller;
use App\Models\SocialAccount;
use Carbon\CarbonImmutable;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;

/** "Kho riêng tự đăng theo khung": cài đặt, tài khoản ChatGPT, và chỉnh sản phẩm/caption/kênh của từng video. */
final class RiengAutoController extends Controller
{
    use ScopesToOwner;

    public function show(Request $request, ChatGptAccounts $accounts): JsonResponse
    {
        $accountId = $this->authorizeOwner($request);

        return response()->json($this->payload($accountId, $accounts));
    }

    public function update(Request $request, ChatGptAccounts $accounts): JsonResponse
    {
        $accountId = $this->authorizeOwner($request);
        $in = $request->validate([
            'enabled' => ['sometimes', 'boolean'],
            'caption_mode' => ['sometimes', 'in:ai,kid'],
            'empty_caption_ok' => ['sometimes', 'boolean'],
            'approve_first' => ['sometimes', 'boolean'],
            'duplicates' => ['sometimes', 'in:ask,allow'],
            'model' => ['sometimes', 'string', 'in:'.implode(',', array_keys(RiengAutoSettings::MODELS + self::accountModels($accounts)))],
            'effort' => ['sometimes', 'string', 'in:'.implode(',', array_keys(RiengAutoSettings::EFFORTS))],
            'fast' => ['sometimes', 'boolean'],
            'folder_channels' => ['sometimes', 'array'],
        ]);

        if (isset($in['folder_channels'])) {
            $mine = $this->tiktokAccounts($accountId)->pluck('id')->map(fn ($id): string => (string) $id)->all();
            $folders = RiengFolder::query()->pluck('id')->map(fn ($id): string => (string) $id)->all();
            $in['folder_channels'] = collect($in['folder_channels'])
                ->filter(fn ($list, $id): bool => in_array((string) $id, $folders, true))
                ->map(fn ($list): array => array_values(array_intersect(RiengAutoSettings::ids($list), $mine)))
                ->all();
        }

        $before = RiengAutoSettings::get();
        RiengAutoSettings::update($in);
        $after = RiengAutoSettings::get();

        // Đổi model / mức nghĩ / Fast, hoặc vừa bật: video lỗi trước đó được thử lại ngay với cài đặt mới.
        foreach (['model', 'effort', 'fast', 'enabled'] as $k) {
            if (($before[$k] ?? null) !== ($after[$k] ?? null)) {
                app(RiengAnalyzer::class)->retryNow();
                RiengAiCommand::launch();
                break;
            }
        }

        return response()->json($this->payload($accountId, $accounts));
    }

    /** Nút "Thử lại ngay": video AI chưa xem được sẽ được xem ở lượt tới (trong khoảng 2 phút). */
    public function retryAi(Request $request, ChatGptAccounts $accounts, RiengAnalyzer $analyzer): JsonResponse
    {
        $accountId = $this->authorizeOwner($request);
        $n = $analyzer->retryNow();

        return response()->json(['retried' => $n] + $this->payload($accountId, $accounts));
    }

    /** Dòng trạng thái "AI xem video" trên trang Kho riêng (trang hỏi lại vài giây một lần). */
    public function aiStatus(Request $request, ChatGptAccounts $accounts): JsonResponse
    {
        $this->authorizeOwner($request);

        // Nhiều tab / nhiều bàn cùng hỏi: dùng chung kết quả 3 giây (hàm này đọc mọi video chưa đăng).
        return response()->json(Cache::remember('fork-rieng:ai-status', 3, fn (): array => RiengAiStatus::get($accounts)));
    }

    /** Nút "Cho AI xem ngay": video lỗi được thử lại từ đầu và AI chạy ở nền liền, không đợi lịch 2 phút. */
    public function aiRunNow(Request $request, ChatGptAccounts $accounts, RiengAnalyzer $analyzer): JsonResponse
    {
        $this->authorizeOwner($request);
        $analyzer->retryNow();
        RiengAiStatus::beat(['dang' => true, 'note' => 'anh vừa bấm cho AI xem ngay']);
        RiengAiCommand::launch();
        Cache::forget('fork-rieng:ai-status');

        return response()->json(RiengAiStatus::get($accounts));
    }

    /** Tự cài ChatGPT CLI (Codex) vào thư mục của app. POST bắt đầu cài (chạy nền); trả trạng thái để trang hỏi lại. */
    public function installCli(Request $request, ChatGptAccounts $accounts): JsonResponse
    {
        $this->authorizeOwner($request);

        if ($request->boolean('check')) {
            return response()->json(['cli' => $accounts->cliStatus()]);
        }

        $error = $accounts->installCli();

        return response()->json(['cli' => $accounts->cliStatus(), 'error' => $error], $error === null ? 200 : 422);
    }

    /** Tiến độ cài ChatGPT CLI (trang hỏi vài giây một lần trong lúc cài). */
    public function cliStatus(Request $request, ChatGptAccounts $accounts): JsonResponse
    {
        $this->authorizeOwner($request);

        return response()->json(['cli' => $accounts->cliStatus()]);
    }

    public function addChatGpt(Request $request, ChatGptAccounts $accounts): JsonResponse
    {
        $this->authorizeOwner($request);
        $r = $accounts->startLogin();

        return response()->json($r, $r['ok'] ? 200 : 422);
    }

    public function chatGptStatus(Request $request, ChatGptAccounts $accounts, string $id): JsonResponse
    {
        $this->authorizeOwner($request);
        $row = collect($accounts->all())->firstWhere('id', $id);

        return response()->json(['account' => $row, 'url' => $row === null || $row['ready'] ? null : $accounts->loginUrl($id)]);
    }

    /** Hạn mức còn lại của một tài khoản ChatGPT (hỏi Codex, khoảng 1–3 giây, không tốn lượt). */
    public function chatGptLimits(Request $request, ChatGptAccounts $accounts, string $id): JsonResponse
    {
        $this->authorizeOwner($request);
        $limits = $accounts->limits($id);
        $known = self::accountModels($accounts);

        return response()->json(['ok' => $limits !== null, 'limits' => $limits, 'models' => $known === [] ? RiengAutoSettings::MODELS : $known, 'models_from_accounts' => $known !== [], 'model_effective' => $this->effectiveModel($accounts, $known)]);
    }

    public function removeChatGpt(Request $request, ChatGptAccounts $accounts, string $id): JsonResponse
    {
        $this->authorizeOwner($request);

        return response()->json(['ok' => $accounts->remove($id)]);
    }

    /** Chủ app chỉnh một video: sản phẩm (+ quy cách), caption tự viết, kênh, duyệt caption AI, cho đăng video trùng. */
    public function updateVideo(Request $request, AutoVideo $video): JsonResponse
    {
        $accountId = $this->authorizeOwner($request);
        abort_unless($video->isRieng(), 404);
        $in = $request->validate([
            'product_code' => ['sometimes', 'nullable', 'string', 'max:100'],
            'quy_cach' => ['sometimes', 'nullable', 'string', 'max:100'],
            'caption' => ['sometimes', 'nullable', 'string', 'max:2200'],
            'channels' => ['sometimes', 'array'],
            'approved' => ['sometimes', 'boolean'],
            'dup_ok' => ['sometimes', 'boolean'],
            'hashtags' => ['sometimes', 'nullable', 'array', 'max:10'],
            'hashtags.*' => ['nullable', 'string', 'max:60'],
        ]);

        if ($video->status !== AutoVideo::NEW) {
            return response()->json(['ok' => false, 'error' => 'Video này đã hẹn giờ hoặc đã đăng, không sửa được ở đây.'], 422);
        }

        $meta = (array) $video->meta;
        $changes = [];

        if (array_key_exists('product_code', $in)) {
            $code = filled($in['product_code']) ? (string) $in['product_code'] : null;

            if ($code !== null && ! AutoProduct::query()->whereKey($code)->exists()) {
                return response()->json(['ok' => false, 'error' => 'Không có sản phẩm này.'], 422);
            }

            $changes['product_code'] = $code;
            $changes['quy_cach'] = filled($in['quy_cach'] ?? null) ? (string) $in['quy_cach'] : null;
            // Chọn lại "theo AI" (null) thì AI được gắn lại lần xem sau; chọn một sản phẩm thì giữ, AI không đè.
            if ($code === null) {
                unset($meta['product_by']);
                $changes['product_code'] = data_get($meta, 'ai.state') === 'ok' ? data_get($meta, 'ai.product_code') : null;
            } else {
                $meta['product_by'] = 'kid';
            }
        }

        if (array_key_exists('caption', $in)) {
            $caption = trim((string) ($in['caption'] ?? ''));
            $changes['caption'] = $caption === '' ? null : $caption;
            $changes['caption_source'] = $caption === '' ? null : 'kid';
        }

        if (array_key_exists('channels', $in)) {
            $mine = $this->tiktokAccounts($accountId)->pluck('id')->map(fn ($id): string => (string) $id)->all();
            $meta['channels'] = array_values(array_intersect(RiengAutoSettings::ids($in['channels']), $mine));
        }

        if (array_key_exists('approved', $in)) {
            $meta['ai']['approved'] = (bool) $in['approved'];
        }

        if (array_key_exists('dup_ok', $in)) {
            $meta['dup_ok'] = (bool) $in['dup_ok'];
        }

        // Hashtag chủ app tự sửa (thay hashtag AI đề xuất); null = quay lại dùng hashtag AI.
        if (array_key_exists('hashtags', $in)) {
            if ($in['hashtags'] === null) {
                unset($meta['kid_hashtags']);
            } else {
                $meta['kid_hashtags'] = Hashtags::normalize(array_map(
                    fn (string $t): string => '#'.(preg_replace('/[^A-Za-z0-9]/', '', Str::ascii($t)) ?? ''),
                    array_filter($in['hashtags'], fn ($t): bool => is_string($t) && preg_match('/[\p{L}\p{N}]/u', $t) === 1),
                ));
            }
        }

        // Chủ app vừa sửa: bỏ khoá "lần đăng trước lỗi" để app thử lại ngay lượt tới.
        unset($meta['auto_error'], $meta['auto_error_at']);
        $video->forceFill($changes + ['meta' => $meta])->save();

        return response()->json(['ok' => true, 'auto' => self::videoAuto($video->refresh(), RiengAutoSettings::get())]);
    }

    /**
     * Cho AI xem lại video ngay: chạy ở nền liền (không đợi lịch 2 phút), trang hỏi tiến độ qua videoState().
     * Giữ lời nói đã nghe lần trước (đỡ nghe lại).
     */
    public function reanalyze(Request $request, AutoVideo $video): JsonResponse
    {
        $this->authorizeOwner($request);
        abort_unless($video->isRieng(), 404);

        if ($video->status !== AutoVideo::NEW) {
            return response()->json(['ok' => false, 'error' => 'Video này đã hẹn giờ hoặc đã đăng.'], 422);
        }

        $meta = (array) $video->meta;
        $prev = (array) ($meta['ai'] ?? []);
        $meta['ai'] = ['tries' => 0, 'dang' => ['buoc' => 0, 'tong' => 0, 'viec' => 'Đang chờ AI', 'tu' => now()->toIso8601String(), 'luc' => now()->toIso8601String()]]
            + (is_string($prev['loi'] ?? null) ? ['loi' => $prev['loi']] : []);
        $video->forceFill(['meta' => $meta])->save();
        RiengAiCommand::launch($video->id);

        return response()->json(['ok' => true, 'auto' => self::videoAuto($video->refresh(), RiengAutoSettings::get())]);
    }

    /** Trạng thái "tự đăng" của một video (trang hỏi lại trong lúc AI đang xem). */
    public function videoState(Request $request, AutoVideo $video): JsonResponse
    {
        $this->authorizeOwner($request);
        abort_unless($video->isRieng(), 404);

        return response()->json(['auto' => self::videoAuto($video, RiengAutoSettings::get())]);
    }

    /**
     * Phần "tự đăng" của một video cho thẻ ở trang Kho riêng.
     *
     * @return array<string, mixed>|null
     */
    public static function videoAuto(AutoVideo $v, array $settings): ?array
    {
        if (! $v->isRieng()) {
            return null;
        }

        $ai = (array) data_get($v->meta, 'ai', []);
        $poster = app(RiengAutoPoster::class);
        $isNew = $v->status === AutoVideo::NEW && $v->files_deleted_at === null;
        $blocker = $isNew ? $poster->blocker($v, null, null, $settings) : null;

        return [
            'ai_state' => $ai['state'] ?? null,
            'ai_product' => $ai['product_code'] ?? null,
            'ai_sure' => $ai['chac'] ?? null,
            'ai_reason' => $ai['ly_do'] ?? null,
            'ai_summary' => $ai['tom_tat'] ?? null,
            'ai_caption' => $ai['caption'] ?? null,
            'ai_hashtags' => array_values(array_filter((array) ($ai['hashtags'] ?? []), 'is_string')),
            'kid_hashtags' => is_array($kh = data_get($v->meta, 'kid_hashtags')) ? array_values(array_filter($kh, 'is_string')) : null,
            // AI đang xem (bậc mấy / tổng, việc gì); null khi không xem. Quá 40 phút không cập nhật coi như đã dừng.
            'ai_progress' => is_array($dang = $ai['dang'] ?? null) && now()->diffInMinutes(CarbonImmutable::parse((string) ($dang['luc'] ?? 'now')), true) < 40 ? $dang : null,
            'ai_steps' => array_values(array_filter((array) ($ai['buoc'] ?? []), 'is_array')),
            'ai_heard' => is_string($ai['loi'] ?? null) ? ($ai['loi'] === '' ? 'Video không có lời nói.' : $ai['loi']) : null,
            'ai_error' => $ai['error'] ?? null,
            'ai_tries' => (int) ($ai['tries'] ?? 0),
            'ai_next_try_at' => $ai['next_try_at'] ?? null,
            'ai_at' => $ai['at'] ?? null,
            'approved' => (bool) ($ai['approved'] ?? false),
            'product_by' => data_get($v->meta, 'product_by') === 'kid' ? 'kid' : (filled($v->product_code) ? 'ai' : null),
            'product_code' => $v->product_code,
            'quy_cach' => $v->quy_cach,
            'kid_caption' => $v->caption_source === 'kid' ? $v->caption : null,
            'final_caption' => $isNew ? $poster->captionFor($v, $settings) : null,
            'channels' => RiengAutoSettings::ids(data_get($v->meta, 'channels')),
            'effective_channels' => $poster->channelsFor($v, $settings),
            'dup_ok' => (bool) data_get($v->meta, 'dup_ok', false),
            'auto_error' => data_get($v->meta, 'auto_error'),
            'ready' => $isNew && $blocker === null,
            'blocker' => $blocker,
        ];
    }

    /**
     * Model mà ít nhất một tài khoản đã đăng nhập dùng được (theo danh sách Codex trả về, đã nhớ). Rỗng nếu chưa biết.
     *
     * @return array<string, array{name: string, note: string, efforts: list<string>, fast: bool, default?: bool}>
     */
    private static function accountModels(ChatGptAccounts $accounts): array
    {
        $out = [];

        foreach ($accounts->all() as $a) {
            if ($a['ready']) {
                foreach ($accounts->knownModels($a['id']) ?? [] as $mid => $m) {
                    $out[$mid] ??= $m;
                    $out[$mid]['fast'] = $out[$mid]['fast'] || $m['fast'];
                }
            }
        }

        return $out;
    }

    /** Model app thật sự dùng khi model đã chọn không có ở tài khoản nào (null = dùng đúng model đã chọn). */
    private function effectiveModel(ChatGptAccounts $accounts, array $known): ?string
    {
        $want = RiengAutoSettings::get()['model'];

        if ($known === [] || isset($known[$want])) {
            return null;
        }

        foreach ($accounts->all() as $a) {
            if ($a['ready'] && $accounts->knownModels($a['id']) !== null) {
                return $accounts->modelFor($a['id'], $want)[0];
            }
        }

        return null;
    }

    /** @return array<string, mixed> */
    private function payload(string $accountId, ChatGptAccounts $accounts): array
    {
        $autos = AutoAccount::query()->get()->keyBy('social_account_id');
        $products = AutoProduct::query()->where('enabled', true)->orderBy('code')->get();
        $counts = AutoVideo::query()->where('source', AutoVideo::SOURCE_RIENG)->where('status', AutoVideo::NEW)->whereNull('files_deleted_at')
            // Video lỗi vừa được cho thử lại (tries = 0) tính là "chờ AI xem".
            ->selectRaw("case when meta->'ai'->>'state' = 'error' and coalesce(meta->'ai'->>'tries', '0') = '0' then 'cho' else coalesce(meta->'ai'->>'state', 'cho') end as s, count(*) as n")->groupBy('s')->pluck('n', 's');

        return [
            'settings' => RiengAutoSettings::get(),
            'models' => ($known = self::accountModels($accounts)) === [] ? RiengAutoSettings::MODELS : $known,
            // Model tài khoản dùng được đã biết: model đã chọn không có thì app dùng model mặc định của tài khoản.
            'models_from_accounts' => $known !== [],
            'model_effective' => $this->effectiveModel($accounts, $known),
            'efforts' => RiengAutoSettings::EFFORTS,
            'codex_installed' => ($cli = $accounts->cliStatus())['installed'],
            'speech' => app(RiengSpeech::class)->status(),
            'cli' => $cli,
            'chatgpt' => $accounts->all(),
            'channels' => $this->tiktokAccounts($accountId)
                ->filter(fn (SocialAccount $a): bool => $autos->has($a->id))
                ->map(fn (SocialAccount $a): array => ['id' => (string) $a->id, 'name' => '@'.($a->username ?: $a->display_name), 'avatar_url' => $a->avatar_url, 'auto_enabled' => (bool) $autos[$a->id]->enabled])
                ->values()->all(),
            'folders' => RiengFolder::query()->orderBy('id')->get()->map(fn (RiengFolder $f): array => ['id' => $f->id, 'name' => $f->displayName()])->all(),
            'products' => $products->map(fn (AutoProduct $p): array => [
                'code' => (string) $p->code,
                'name' => (string) ($p->short_name ?: $p->code),
                'quy_cach' => CartRules::quyCachList($p),
            ])->all(),
            'counts' => $counts->map(fn ($n): int => (int) $n)->all(),
        ];
    }
}

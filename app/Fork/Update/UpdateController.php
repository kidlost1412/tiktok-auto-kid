<?php

declare(strict_types=1);

namespace App\Fork\Update;

use App\Http\Controllers\Controller;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

/** Cài đặt → Cập nhật. Mọi việc nặng do launcher làm; trang này chỉ hiển thị và gửi lệnh (kèm token của launcher). */
final class UpdateController extends Controller
{
    /**
     * Trang riêng cũ (`/settings/cap-nhat`) giờ chỉ chuyển hướng sang trang Cài đặt hợp nhất.
     */
    public function index(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        return redirect()->to('/settings#cap-nhat');
    }

    /**
     * Dữ liệu cho mục "Cập nhật" trong trang Cài đặt hợp nhất.
     *
     * @return array<string, mixed>
     */
    public function props(Request $request): array
    {
        $this->authorizeOwner($request);

        $configured = LauncherClient::repoConfigured();
        $status = LauncherClient::status();

        // Chưa có kết quả kiểm tra, hoặc đã quá 1 giờ: nhờ launcher hỏi GitHub (launcher tự giữ cache 1 giờ).
        if ($configured && $status !== null && ! ($status['busy'] ?? false)) {
            $checked = (string) ($status['checked_at'] ?? '');

            if ($checked === '' || (strtotime($checked) ?: 0) < time() - 3600) {
                $r = LauncherClient::post('/api/update/check');
                $status = $r['ok'] && is_array($r['data']) ? $r['data'] : $status;
            }
        }

        $latest = is_array($status['latest'] ?? null) ? $status['latest'] : null;

        return [
            'configured' => $configured,
            'repo' => $configured ? (string) config('fork-update.repo') : null,
            'launcher_ok' => $status !== null,
            'launcher_port' => LauncherClient::port(),
            'current' => LauncherClient::currentVersion(),
            'latest' => $latest === null ? null : [
                'version' => (string) ($latest['version'] ?? ''),
                'notes' => mb_substr((string) ($latest['notes'] ?? ''), 0, 20000),
                'page_url' => $this->githubUrl((string) ($latest['page_url'] ?? '')),
                'published_at' => (string) ($latest['published_at'] ?? ''),
                'size' => (int) ($latest['zip_size'] ?? 0),
            ],
            'update_available' => (bool) ($status['update_available'] ?? false),
            'check_error' => (string) ($status['check_error'] ?? ''),
            'checked_at' => (string) ($status['checked_at'] ?? ''),
            'auto_check' => (bool) ($status['auto_check'] ?? true),
            'can_rollback' => (bool) ($status['can_rollback'] ?? false),
            'rollback_version' => (string) ($status['rollback_version'] ?? ''),
            'launcher_pending' => (bool) ($status['launcher_pending'] ?? false),
            'job' => $status === null ? null : [
                'state' => (string) ($status['state'] ?? 'idle'),
                'busy' => (bool) ($status['busy'] ?? false),
                'message' => (string) ($status['message'] ?? ''),
                'percent' => (int) ($status['percent'] ?? 0),
                'error' => (string) ($status['error'] ?? ''),
            ],
        ];
    }

    public function check(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        if (! LauncherClient::repoConfigured()) {
            return back()->with('flash.error', 'Chưa có kho cập nhật. Đặt UPDATE_REPO trong file .env.');
        }

        $r = LauncherClient::post('/api/update/check?force=1');

        if (! $r['ok']) {
            return back()->with('flash.error', $r['error']);
        }

        $err = (string) ($r['data']['check_error'] ?? '');

        if ($err !== '' && empty($r['data']['latest'])) {
            return back()->with('flash.error', $err);
        }

        return back()->with('flash.success', ($r['data']['update_available'] ?? false) ? 'Có bản mới.' : 'Bạn đang dùng bản mới nhất.');
    }

    public function install(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        if (! LauncherClient::repoConfigured()) {
            return back()->with('flash.error', 'Chưa có kho cập nhật. Đặt UPDATE_REPO trong file .env.');
        }

        $r = LauncherClient::post('/api/update');

        return $r['ok']
            ? back()->with('flash.success', 'Đang cập nhật. Ứng dụng sẽ tạm dừng ít phút, đừng đóng trang này.')
            : back()->with('flash.error', $r['error']);
    }

    public function rollback(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        $r = LauncherClient::post('/api/update/rollback');

        return $r['ok']
            ? back()->with('flash.success', 'Đang quay lại bản trước. Ứng dụng sẽ tạm dừng ít phút.')
            : back()->with('flash.error', $r['error']);
    }

    public function prefs(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        $r = LauncherClient::post('/api/update/prefs', ['auto_check' => $request->boolean('auto_check')]);

        return $r['ok'] ? back() : back()->with('flash.error', $r['error']);
    }

    private function authorizeOwner(Request $request): void
    {
        abort_unless($request->user()?->isAccountOwner(), SymfonyResponse::HTTP_FORBIDDEN);
    }

    /** Chỉ cho liên kết https tới github.com để mở ra ngoài. */
    private function githubUrl(string $url): ?string
    {
        $host = parse_url($url, PHP_URL_HOST);

        return str_starts_with($url, 'https://') && is_string($host) && ($host === 'github.com' || str_ends_with($host, '.github.com')) ? $url : null;
    }
}

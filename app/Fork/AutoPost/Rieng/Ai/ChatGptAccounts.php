<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use App\Fork\AutoPost\Models\AutoSetting;
use Carbon\CarbonImmutable;
use Illuminate\Support\Str;
use Symfony\Component\Process\ExecutableFinder;
use Symfony\Component\Process\Process;
use Throwable;

/**
 * Các tài khoản ChatGPT dùng cho Codex CLI, dùng luân phiên.
 *
 * Mỗi tài khoản là một thư mục CODEX_HOME riêng của app: storage/app/chatgpt/<id>/ (chứa auth.json do `codex login` ghi).
 * App không bao giờ đụng ~/.codex của máy (đó là đăng nhập của app Codex của chủ máy).
 * Trạng thái (lần dùng, nghỉ vì hết lượt, lỗi) nằm trong fork_auto_settings `rieng.chatgpt`.
 */
final class ChatGptAccounts
{
    public const string KEY = 'rieng.chatgpt';

    /** Hết lượt mà không đọc được giờ mở lại thì nghỉ ngần này phút. */
    public const int LIMIT_COOLDOWN_MINUTES = 60;

    public function dir(): string
    {
        return rtrim((string) (config('fork.auto.chatgpt_dir') ?: storage_path('app/chatgpt')), '/\\');
    }

    public function home(string $id): string
    {
        return $this->dir().DIRECTORY_SEPARATOR.$id;
    }

    /** Đường dẫn lệnh codex (Codex CLI); null nếu máy chưa cài. */
    public function codexPath(): ?string
    {
        $configured = (string) config('fork.auto.codex_path', '');

        if ($configured !== '' && is_file($configured)) {
            return $configured;
        }

        $candidates = [];

        foreach (['APPDATA' => '', 'USERPROFILE' => DIRECTORY_SEPARATOR.'AppData'.DIRECTORY_SEPARATOR.'Roaming'] as $env => $suffix) {
            $base = (string) (getenv($env) ?: '');

            if ($base !== '') {
                $candidates[] = $base.$suffix.DIRECTORY_SEPARATOR.'npm'.DIRECTORY_SEPARATOR.'codex.cmd';
            }
        }

        foreach ($candidates as $c) {
            if (is_file($c)) {
                return $c;
            }
        }

        return (new ExecutableFinder)->find('codex');
    }

    /**
     * Danh sách tài khoản để hiển thị.
     *
     * @return list<array{id: string, email: ?string, plan: ?string, ready: bool, logging_in: bool, cooldown_until: ?string, last_error: ?string, last_used_at: ?string, uses: int}>
     */
    public function all(?CarbonImmutable $now = null): array
    {
        $now ??= CarbonImmutable::now();
        $state = $this->state();
        $out = [];

        foreach ($this->ids() as $id) {
            $s = $state['accounts'][$id] ?? [];
            $who = $this->identity($id);
            $cool = isset($s['cooldown_until']) && is_string($s['cooldown_until']) && CarbonImmutable::parse($s['cooldown_until'])->greaterThan($now) ? $s['cooldown_until'] : null;
            $out[] = [
                'id' => $id,
                'email' => $who['email'],
                'plan' => $who['plan'],
                'ready' => $who['ready'],
                'logging_in' => ! $who['ready'] && $this->loginRunning($id),
                'cooldown_until' => $cool,
                'last_error' => $who['ready'] ? ($s['last_error'] ?? null) : null,
                'last_used_at' => $s['last_used_at'] ?? null,
                'uses' => (int) ($s['uses'] ?? 0),
            ];
        }

        return $out;
    }

    /** Tài khoản dùng lượt tới: luân phiên, bỏ qua tài khoản chưa đăng nhập hoặc đang nghỉ vì hết lượt. */
    public function pick(?CarbonImmutable $now = null, array $skip = []): ?string
    {
        $ready = array_values(array_filter($this->all($now), fn (array $a): bool => $a['ready'] && $a['cooldown_until'] === null && ! in_array($a['id'], $skip, true)));

        if ($ready === []) {
            return null;
        }

        $last = $this->state()['last'] ?? null;
        $ids = array_column($ready, 'id');
        $at = array_search($last, $ids, true);

        return $ids[$at === false ? 0 : ($at + 1) % count($ids)];
    }

    public function markUsed(string $id): void
    {
        $this->mutate(function (array &$s) use ($id): void {
            $s['last'] = $id;
            $s['accounts'][$id]['uses'] = (int) ($s['accounts'][$id]['uses'] ?? 0) + 1;
            $s['accounts'][$id]['last_used_at'] = now()->toIso8601String();
            $s['accounts'][$id]['last_error'] = null;
            $s['accounts'][$id]['cooldown_until'] = null;
        });
    }

    public function markLimited(string $id, ?CarbonImmutable $until = null): void
    {
        $until ??= CarbonImmutable::now()->addMinutes(self::LIMIT_COOLDOWN_MINUTES);

        $this->mutate(function (array &$s) use ($id, $until): void {
            $s['last'] = $id;
            $s['accounts'][$id]['cooldown_until'] = $until->toIso8601String();
            $s['accounts'][$id]['last_error'] = 'Hết lượt, nghỉ tới '.$until->setTimezone('Asia/Ho_Chi_Minh')->format('H:i d/m');
        });
    }

    public function markError(string $id, string $error): void
    {
        $this->mutate(function (array &$s) use ($id, $error): void {
            $s['last'] = $id;
            $s['accounts'][$id]['last_error'] = mb_substr($error, 0, 300);
        });
    }

    /**
     * Mở đăng nhập ChatGPT cho một tài khoản mới: chạy `codex login` (tự mở trình duyệt) ở nền với CODEX_HOME riêng.
     *
     * @return array{ok: bool, id: ?string, error: ?string}
     */
    public function startLogin(): array
    {
        $codex = $this->codexPath();

        if ($codex === null) {
            return ['ok' => false, 'id' => null, 'error' => 'Máy chưa cài ChatGPT CLI (Codex).'];
        }

        foreach ($this->ids() as $other) {
            if ($this->loginRunning($other)) {
                return ['ok' => false, 'id' => $other, 'error' => 'Đang có một lượt đăng nhập mở, hãy làm xong ở trình duyệt hoặc huỷ lượt đó.'];
            }
        }

        $id = 'tk-'.Str::lower(Str::random(8));
        $home = $this->home($id);
        @mkdir($home, 0775, true);
        $this->spawn($home, ['set "CODEX_HOME='.$home.'"', 'call "'.$codex.'" login'], $home.DIRECTORY_SEPARATOR.'login.log');

        return ['ok' => true, 'id' => $id, 'error' => null];
    }

    /** Link đăng nhập (codex in ra) để chủ app tự mở nếu trình duyệt không tự bật. */
    public function loginUrl(string $id): ?string
    {
        $log = @file_get_contents($this->home($id).DIRECTORY_SEPARATOR.'login.log');

        return is_string($log) && preg_match('#https://auth\.openai\.com/\S+#', $log, $m) === 1 ? rtrim($m[0], '.,') : null;
    }

    /** Bỏ tài khoản: xoá thư mục CODEX_HOME của app (không đụng gì ngoài storage/app/chatgpt). */
    public function remove(string $id): bool
    {
        if (! in_array($id, $this->ids(), true)) {
            return false;
        }

        $this->stopLogin($id);
        $this->deleteDir($this->home($id));
        $this->mutate(function (array &$s) use ($id): void {
            unset($s['accounts'][$id]);
        });

        return true;
    }

    /** @return list<string> */
    private function ids(): array
    {
        $out = [];

        foreach (glob($this->dir().DIRECTORY_SEPARATOR.'tk-*', GLOB_ONLYDIR) ?: [] as $d) {
            $id = basename($d);

            if (preg_match('/^tk-[a-z0-9]{8}$/', $id) === 1) {
                $out[$id] = @filectime($d) ?: 0;
            }
        }

        asort($out);

        return array_keys($out);
    }

    /** @return array{ready: bool, email: ?string, plan: ?string} */
    private function identity(string $id): array
    {
        $auth = json_decode((string) @file_get_contents($this->home($id).DIRECTORY_SEPARATOR.'auth.json'), true);
        $tokens = is_array($auth) ? ($auth['tokens'] ?? null) : null;

        if (! is_array($tokens) || ! filled($tokens['refresh_token'] ?? null)) {
            return ['ready' => false, 'email' => null, 'plan' => null];
        }

        $email = null;
        $plan = null;
        $parts = explode('.', (string) ($tokens['id_token'] ?? ''));

        if (count($parts) === 3) {
            $claims = json_decode((string) base64_decode(strtr($parts[1], '-_', '+/'), false), true);

            if (is_array($claims)) {
                $email = is_string($claims['email'] ?? null) ? $claims['email'] : null;
                $plan = $claims['https://api.openai.com/auth']['chatgpt_plan_type'] ?? null;
                $plan = is_string($plan) ? $plan : null;
            }
        }

        return ['ready' => true, 'email' => $email, 'plan' => $plan];
    }

    private function loginRunning(string $id): bool
    {
        $pidFile = $this->home($id).DIRECTORY_SEPARATOR.'login.running';

        if (! is_file($pidFile)) {
            return false;
        }

        // Lượt đăng nhập bỏ dở: quá 15 phút coi như đã thôi.
        if (time() - (int) @filemtime($pidFile) > 15 * 60) {
            @unlink($pidFile);

            return false;
        }

        return true;
    }

    private function stopLogin(string $id): void
    {
        @unlink($this->home($id).DIRECTORY_SEPARATOR.'login.running');

        if (PHP_OS_FAMILY === 'Windows') {
            // Tắt tiến trình codex đang chờ đăng nhập của đúng thư mục này (lọc theo dòng lệnh).
            $needle = str_replace("'", "''", $this->home($id));

            try {
                (new Process(['powershell.exe', '-NoProfile', '-Command',
                    "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*codex*login*' -and \$_.CommandLine -like '*{$needle}*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }"]))->setTimeout(20)->run();
            } catch (Throwable) {
            }
        }
    }

    /**
     * Chạy lệnh ở nền và trả về ngay (tiến trình con sống tiếp sau khi request xong).
     *
     * @param  list<string>  $lines  các dòng lệnh cmd
     */
    private function spawn(string $home, array $lines, string $log): void
    {
        $marker = $home.DIRECTORY_SEPARATOR.'login.running';
        @file_put_contents($marker, (string) time());

        if (PHP_OS_FAMILY !== 'Windows') {
            return;
        }

        $script = $home.DIRECTORY_SEPARATOR.'login.cmd';
        // Dòng cuối của $lines là lệnh codex: phần ghi log gắn vào đúng dòng đó.
        $body = "@echo off\r\nchcp 65001 >nul\r\n".implode("\r\n", $lines).' > "'.$log.'" 2>&1'."\r\n".'del "'.$marker.'" >nul 2>&1'."\r\n";
        file_put_contents($script, $body);
        (new Process(['cmd.exe', '/c', 'start', '""', '/b', 'cmd.exe', '/c', $script]))->setTimeout(15)->run();
    }

    private function deleteDir(string $dir): void
    {
        if (! is_dir($dir) || ! str_starts_with(realpath($dir) ?: '', realpath($this->dir()) ?: "\0")) {
            return;
        }

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);

        foreach ($it as $f) {
            $f->isDir() ? @rmdir($f->getPathname()) : @unlink($f->getPathname());
        }

        @rmdir($dir);
    }

    /** @return array{last: ?string, accounts: array<string, array<string, mixed>>} */
    private function state(): array
    {
        $raw = json_decode((string) AutoSetting::read(self::KEY, '{}'), true);
        $raw = is_array($raw) ? $raw : [];

        return ['last' => is_string($raw['last'] ?? null) ? $raw['last'] : null, 'accounts' => is_array($raw['accounts'] ?? null) ? $raw['accounts'] : []];
    }

    private function mutate(callable $fn): void
    {
        $s = $this->state();
        $fn($s);
        AutoSetting::write(self::KEY, (string) json_encode($s, JSON_UNESCAPED_UNICODE));
    }
}

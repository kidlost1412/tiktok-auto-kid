<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use App\Fork\AutoPost\Models\AutoSetting;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;
use Symfony\Component\Process\ExecutableFinder;
use Symfony\Component\Process\InputStream;
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

    private const string MODELS_CACHE = 'fork-rieng:chatgpt-models:';

    public function dir(): string
    {
        return rtrim((string) (config('fork.auto.chatgpt_dir') ?: storage_path('app/chatgpt')), '/\\');
    }

    public function home(string $id): string
    {
        return $this->dir().DIRECTORY_SEPARATOR.$id;
    }

    /** codex.exe trong gói bản chạy Windows (npm đặt gói này lồng trong @openai/codex khi cài toàn máy, hoặc ngang hàng khi cài vào một thư mục). */
    private const string NATIVE_EXE = '@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe';

    /** Thư mục app tự cài Codex CLI vào (nằm trong storage nên giữ qua các bản cập nhật). */
    public function cliDir(): string
    {
        return rtrim((string) (config('fork.auto.codex_dir') ?: storage_path('app/codex-cli')), '/\\');
    }

    /**
     * Đường dẫn lệnh codex (Codex CLI); null nếu máy chưa cài.
     * Ưu tiên codex.exe chạy thẳng (không cần node, không phụ thuộc PATH): bản app tự cài, rồi bản cài toàn máy bằng npm.
     */
    public function codexPath(): ?string
    {
        $configured = (string) config('fork.auto.codex_path', '');

        if ($configured !== '' && is_file($configured)) {
            return $configured;
        }

        $sep = DIRECTORY_SEPARATOR;
        $native = str_replace('/', $sep, self::NATIVE_EXE);
        $candidates = [];

        foreach ([$this->cliDir(), ...$this->npmGlobalDirs()] as $root) {
            $modules = $root.$sep.'node_modules';
            $candidates[] = $modules.$sep.$native;
            $candidates[] = $modules.$sep.'@openai'.$sep.'codex'.$sep.'node_modules'.$sep.$native;
        }

        foreach ($this->npmGlobalDirs() as $npm) {
            $candidates[] = $npm.$sep.'codex.cmd';
        }

        foreach ($candidates as $c) {
            if (is_file($c)) {
                return $c;
            }
        }

        return (new ExecutableFinder)->find('codex');
    }

    /** Thư mục npm toàn máy của người dùng (nơi `npm i -g` đặt lệnh). @return list<string> */
    private function npmGlobalDirs(): array
    {
        $dirs = [];

        foreach (['APPDATA' => '', 'USERPROFILE' => '\\AppData\\Roaming'] as $env => $suffix) {
            $base = (string) (getenv($env, true) ?: getenv($env) ?: ($_SERVER[$env] ?? ''));

            if ($base !== '') {
                $dirs[] = rtrim($base, '/\\').str_replace('\\', DIRECTORY_SEPARATOR, $suffix).DIRECTORY_SEPARATOR.'npm';
            }
        }

        return array_values(array_unique($dirs));
    }

    /**
     * Biến môi trường cho tiến trình con (codex, npm): php-cgi dưới launcher có thể thiếu PATH tới node.
     *
     * @return array<string, string>
     */
    public function childEnv(): array
    {
        if (PHP_OS_FAMILY !== 'Windows') {
            return [];
        }

        $path = (string) (getenv('PATH', true) ?: getenv('PATH') ?: '');
        $extra = array_filter([
            ...$this->npmGlobalDirs(),
            ($pf = getenv('ProgramFiles', true) ?: 'C:\\Program Files') ? $pf.'\\nodejs' : null,
        ], fn ($d): bool => is_string($d) && is_dir($d) && stripos($path, $d) === false);

        return $extra === [] ? [] : ['PATH' => implode(';', [...$extra, $path])];
    }

    /** Lệnh npm của máy (cần Node.js) để tự cài Codex CLI; null nếu máy không có Node.js. */
    public function npmPath(): ?string
    {
        if (PHP_OS_FAMILY !== 'Windows') {
            return (new ExecutableFinder)->find('npm');
        }

        foreach (['ProgramFiles', 'ProgramW6432', 'ProgramFiles(x86)'] as $env) {
            $base = (string) (getenv($env, true) ?: '');

            if ($base !== '' && is_file($base.'\\nodejs\\npm.cmd')) {
                return $base.'\\nodejs\\npm.cmd';
            }
        }

        $found = (new ExecutableFinder)->find('npm');

        return $found !== null && is_file($found) ? $found : null;
    }

    /**
     * Trạng thái cài Codex CLI cho app.
     *
     * @return array{installed: bool, installing: bool, node: bool, error: ?string}
     */
    public function cliStatus(): array
    {
        $installed = $this->codexPath() !== null;
        $marker = $this->cliDir().DIRECTORY_SEPARATOR.'install.running';
        $installing = ! $installed && is_file($marker) && time() - (int) @filemtime($marker) < 20 * 60;
        $error = null;

        if (! $installed && ! $installing) {
            @unlink($marker);
            $log = (string) @file_get_contents($this->cliDir().DIRECTORY_SEPARATOR.'install.log');

            if (trim($log) !== '') {
                $lines = array_values(array_filter(array_map('trim', preg_split('/\R/', $log) ?: []), fn (string $l): bool => $l !== '' && stripos($l, 'npm warn') !== 0));
                $error = 'Cài chưa xong: '.mb_substr((string) end($lines), 0, 200);
            }
        }

        return ['installed' => $installed, 'installing' => $installing, 'node' => $this->npmPath() !== null, 'error' => $error];
    }

    /**
     * Cài Codex CLI vào thư mục của app (npm, chạy nền ~1-3 phút). Trả về lỗi tiếng Việt, null = đã bắt đầu.
     */
    public function installCli(): ?string
    {
        if ($this->codexPath() !== null) {
            return null;
        }

        $npm = $this->npmPath();

        if ($npm === null) {
            return 'Máy chưa có Node.js nên chưa cài được. Anh cài Node.js (nodejs.org, bản LTS) rồi bấm lại.';
        }

        if ($this->cliStatus()['installing']) {
            return null;
        }

        $dir = $this->cliDir();
        @mkdir($dir, 0775, true);
        $marker = $dir.DIRECTORY_SEPARATOR.'install.running';
        $env = $this->childEnv();
        $lines = $env !== [] ? ['set "PATH='.$env['PATH'].'"'] : [];
        $lines[] = 'call "'.$npm.'" install --prefix "'.$dir.'" @openai/codex@latest --no-audit --no-fund --loglevel=error';
        $this->spawn($dir, $marker, $lines, $dir.DIRECTORY_SEPARATOR.'install.log');

        return null;
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

    /** Xoá lỗi cũ của mọi tài khoản (sau khi đã sửa nguyên nhân); lỗi thật sẽ hiện lại ở lượt sau. */
    public function clearErrors(): void
    {
        $this->mutate(function (array &$s): void {
            foreach (array_keys((array) ($s['accounts'] ?? [])) as $id) {
                $s['accounts'][$id]['last_error'] = null;
            }
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
        $env = $this->childEnv();
        $lines = $env !== [] ? ['set "PATH='.$env['PATH'].'"'] : [];
        $lines[] = 'set "CODEX_HOME='.$home.'"';
        $lines[] = 'call "'.$codex.'" login';
        $this->spawn($home, $home.DIRECTORY_SEPARATOR.'login.running', $lines, $home.DIRECTORY_SEPARATOR.'login.log');

        return ['ok' => true, 'id' => $id, 'error' => null];
    }

    /** Link đăng nhập (codex in ra) để chủ app tự mở nếu trình duyệt không tự bật. */
    public function loginUrl(string $id): ?string
    {
        $log = @file_get_contents($this->home($id).DIRECTORY_SEPARATOR.'login.log');

        return is_string($log) && preg_match('#https://auth\.openai\.com/\S+#', $log, $m) === 1 ? rtrim($m[0], '.,') : null;
    }

    /**
     * Hạn mức ChatGPT (Codex) của một tài khoản: hỏi `codex app-server` (account/rateLimits/read), không tốn lượt.
     * Cùng lượt hỏi luôn danh sách model tài khoản dùng được (model/list) và nhớ lại (gói free ít model hơn, không có Fast).
     * Mỗi khung: phần trăm đã dùng, độ dài khung (phút), lúc đặt lại. null nếu không hỏi được.
     *
     * @return array{plan: ?string, windows: list<array{used: int, minutes: ?int, resets_at: ?string}>, reached: bool}|null
     */
    public function limits(string $id): ?array
    {
        $r = $this->rpc($id, [2 => ['account/rateLimits/read', null], 3 => ['model/list', []]]);

        if (isset($r[3]) && ($models = self::parseModels($r[3])) !== null) {
            Cache::put(self::MODELS_CACHE.$id, $models, now()->addHours(12));
        }

        return isset($r[2]) ? self::parseLimits($r[2]) : null;
    }

    /**
     * Model tài khoản này dùng được (đã nhớ; hỏi lại Codex nếu chưa có hoặc $refresh). null nếu không biết.
     *
     * @return array<string, array{name: string, note: string, efforts: list<string>, fast: bool, default: bool}>|null
     */
    public function models(string $id, bool $refresh = false): ?array
    {
        $cached = Cache::get(self::MODELS_CACHE.$id);

        if (is_array($cached) && ! $refresh) {
            return $cached;
        }

        $r = $this->rpc($id, [2 => ['model/list', []]]);
        $models = isset($r[2]) ? self::parseModels($r[2]) : null;

        if ($models !== null) {
            Cache::put(self::MODELS_CACHE.$id, $models, now()->addHours(12));
        }

        return $models ?? (is_array($cached) ? $cached : null);
    }

    /** Model đã nhớ của tài khoản (không hỏi Codex); null nếu chưa biết. */
    public function knownModels(string $id): ?array
    {
        $cached = Cache::get(self::MODELS_CACHE.$id);

        return is_array($cached) ? $cached : null;
    }

    /**
     * Model thật sẽ dùng với tài khoản: model chủ app chọn nếu tài khoản có; không thì model mặc định của tài khoản.
     *
     * @return array{0: string, 1: bool} [model, có Fast không]
     */
    public function modelFor(string $id, string $wanted, bool $refresh = false): array
    {
        $list = $refresh ? $this->models($id, true) : $this->knownModels($id);

        if ($list === null || $list === []) {
            return [$wanted, true];
        }

        if (isset($list[$wanted])) {
            return [$wanted, $list[$wanted]['fast']];
        }

        foreach ($list as $mid => $m) {
            if ($m['default']) {
                return [$mid, $m['fast']];
            }
        }

        $mid = (string) array_key_first($list);

        return [$mid, $list[$mid]['fast']];
    }

    /**
     * Model thay thế khi tài khoản báo không dùng được $bad: hỏi lại danh sách, bỏ $bad, lấy model mặc định còn lại.
     *
     * @return array{0: string, 1: bool}|null
     */
    public function fallbackModel(string $id, string $bad): ?array
    {
        $list = $this->models($id, true) ?? [];
        unset($list[$bad]);

        if ($list === []) {
            return null;
        }

        Cache::put(self::MODELS_CACHE.$id, $list, now()->addHours(12));

        foreach ($list as $mid => $m) {
            if ($m['default']) {
                return [$mid, $m['fast']];
            }
        }

        $mid = (string) array_key_first($list);

        return [$mid, $list[$mid]['fast']];
    }

    /**
     * @param  array<string, mixed>  $msg  câu trả lời JSON-RPC của model/list
     * @return array<string, array{name: string, note: string, efforts: list<string>, fast: bool, default: bool}>|null
     */
    public static function parseModels(array $msg): ?array
    {
        $data = data_get($msg, 'result.data');

        if (! is_array($data)) {
            return null;
        }

        $out = [];

        foreach ($data as $m) {
            $mid = is_array($m) ? (string) ($m['id'] ?? $m['model'] ?? '') : '';

            // Bỏ model ẩn và model không xem được ảnh (AI phải xem khung hình video).
            if ($mid === '' || ($m['hidden'] ?? false) || ! in_array('image', (array) ($m['inputModalities'] ?? ['image']), true)) {
                continue;
            }

            $desc = (string) ($m['description'] ?? '');
            $kind = match (true) {
                str_contains($mid, 'luna') => 'Nhanh, tiết kiệm lượt',
                str_contains($mid, 'terra') => 'Cân bằng nhanh và giỏi',
                str_contains($mid, 'sol') => 'Giỏi nhất, tốn lượt hơn',
                default => 'Model của Codex',
            };
            $out[$mid] = [
                'name' => (string) ($m['displayName'] ?? $mid),
                'note' => $kind.(str_starts_with(strtolower($desc), 'older') ? ' · đời cũ' : ''),
                'efforts' => array_values(array_filter(array_map(fn ($e): string => (string) (is_array($e) ? ($e['reasoningEffort'] ?? '') : $e), (array) ($m['supportedReasoningEfforts'] ?? [])))),
                'fast' => (array) ($m['serviceTiers'] ?? []) !== [] || (array) ($m['additionalSpeedTiers'] ?? []) !== [],
                'default' => (bool) ($m['isDefault'] ?? false),
            ];
        }

        return $out === [] ? null : $out;
    }

    /**
     * Hỏi `codex app-server` (JSON-RPC qua stdin/stdout) một lượt. $calls: [id => [method, params]]. Trả [id => câu trả lời].
     *
     * @param  array<int, array{0: string, 1: mixed}>  $calls
     * @return array<int, array<string, mixed>>
     */
    private function rpc(string $id, array $calls): array
    {
        $codex = $this->codexPath();

        if ($codex === null || ! in_array($id, $this->ids(), true)) {
            return [];
        }

        $lines = [
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"tiktok-auto-kid","version":"1"}}}',
            '{"jsonrpc":"2.0","method":"initialized"}',
        ];

        foreach ($calls as $cid => [$method, $params]) {
            $lines[] = (string) json_encode(['jsonrpc' => '2.0', 'id' => $cid, 'method' => $method] + ($params === null ? [] : ['params' => (object) $params]));
        }

        $p = new Process([$codex, 'app-server'], $this->home($id), ['CODEX_HOME' => $this->home($id)] + $this->childEnv(), null, 30);
        $in = new InputStream;
        $p->setInput($in);
        $buf = '';
        $got = [];

        try {
            $p->start();
            $in->write(implode("\n", $lines)."\n");

            while ($p->isRunning() && count($got) < count($calls)) {
                usleep(50_000);
                $p->checkTimeout();
                $buf .= $p->getIncrementalOutput();

                foreach (explode("\n", $buf) as $line) {
                    $msg = json_decode(trim($line), true);

                    if (is_array($msg) && isset($msg['id']) && array_key_exists((int) $msg['id'], $calls)) {
                        $got[(int) $msg['id']] = $msg;
                    }
                }
            }
        } catch (Throwable) {
            // hết giờ hoặc không chạy được: trả những gì đã nhận
        } finally {
            $in->close();
            $p->stop(1);
        }

        return $got;
    }

    /**
     * @param  array<string, mixed>  $msg  câu trả lời JSON-RPC của account/rateLimits/read
     * @return array{plan: ?string, windows: list<array{used: int, minutes: ?int, resets_at: ?string}>, reached: bool}|null
     */
    public static function parseLimits(array $msg): ?array
    {
        $rl = data_get($msg, 'result.rateLimits');

        if (! is_array($rl)) {
            return null;
        }

        $windows = [];

        foreach (['primary', 'secondary'] as $k) {
            $w = $rl[$k] ?? null;

            if (is_array($w) && isset($w['usedPercent'])) {
                $windows[] = [
                    'used' => (int) round((float) $w['usedPercent']),
                    'minutes' => isset($w['windowDurationMins']) ? (int) $w['windowDurationMins'] : null,
                    'resets_at' => isset($w['resetsAt']) ? CarbonImmutable::createFromTimestamp((int) $w['resetsAt'])->toIso8601String() : null,
                ];
            }
        }

        return [
            'plan' => is_string($rl['planType'] ?? null) ? $rl['planType'] : null,
            'windows' => $windows,
            'reached' => filled($rl['rateLimitReachedType'] ?? null) || data_get($msg, 'result.ordinaryUsageAllowed') === false,
        ];
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
    private function spawn(string $dir, string $marker, array $lines, string $log): void
    {
        @file_put_contents($marker, (string) time());

        if (PHP_OS_FAMILY !== 'Windows') {
            return;
        }

        $script = $dir.DIRECTORY_SEPARATOR.basename($marker, '.running').'.cmd';
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

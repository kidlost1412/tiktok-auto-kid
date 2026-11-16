<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use RuntimeException;
use Symfony\Component\Process\Process;

/** Hỏi ChatGPT một lần qua Codex CLI (`codex exec`, phiên mới, chỉ đọc) kèm ảnh; trả về câu trả lời cuối. */
class CodexRunner
{
    public const int TIMEOUT = 240;

    public function __construct(private readonly ChatGptAccounts $accounts) {}

    /**
     * @param  list<string>  $images
     *
     * @throws CodexLimited khi tài khoản hết lượt
     * @throws RuntimeException lỗi khác
     */
    public function ask(string $accountId, string $model, string $effort, string $prompt, array $images, string $workDir, bool $fast = false): string
    {
        $codex = $this->accounts->codexPath();

        if ($codex === null) {
            throw new RuntimeException('Máy chưa cài ChatGPT CLI (Codex).');
        }

        $out = $workDir.DIRECTORY_SEPARATOR.'tra-loi.txt';
        @unlink($out);
        $cmd = [$codex, 'exec', '-m', $model, '-c', 'model_reasoning_effort='.$effort, '--skip-git-repo-check', '--ephemeral', '-s', 'read-only', '-o', $out];

        if ($fast) {
            // Chế độ Fast của Codex: nhanh gấp đôi, tốn lượt hơn.
            array_splice($cmd, 4, 0, ['-c', 'service_tier="fast"']);
        }

        foreach ($images as $img) {
            $cmd[] = '-i';
            $cmd[] = $img;
        }

        $cmd[] = '-';
        $p = new Process($cmd, $workDir, ['CODEX_HOME' => $this->accounts->home($accountId)] + $this->accounts->childEnv(), $prompt, self::TIMEOUT);
        $p->run();
        $answer = is_file($out) ? trim((string) file_get_contents($out)) : '';
        $log = $p->getOutput()."\n".$p->getErrorOutput();

        if ($p->isSuccessful() && $answer !== '') {
            return $answer;
        }

        if (preg_match('/usage limit|rate limit|too many requests|\b429\b|quota|out of credits|add credits/i', $log) === 1) {
            throw new CodexLimited(self::retryAt($log));
        }

        if (preg_match('/\b401\b|unauthori[sz]ed|not logged in|login again|refresh token|sign in again/i', $log) === 1) {
            throw new RuntimeException('Tài khoản ChatGPT cần đăng nhập lại.');
        }

        throw new RuntimeException('ChatGPT không trả lời'.($p->getExitCode() !== null ? ' (mã '.$p->getExitCode().')' : '').': '.mb_substr(trim(preg_replace('/\s+/', ' ', $log) ?? ''), -240));
    }

    /** "try again in 2 hours 5 minutes" / "in 37 minutes" → số phút; null nếu không đọc được. */
    public static function retryAt(string $log): ?int
    {
        if (preg_match('/try again in\s+(?:(\d+)\s*(?:hours?|h)\b)?\s*,?\s*(?:(\d+)\s*(?:minutes?|mins?|m)\b)?/i', $log, $m) !== 1) {
            return null;
        }

        $minutes = (int) ($m[1] ?? 0) * 60 + (int) ($m[2] ?? 0);

        return $minutes > 0 ? $minutes : null;
    }
}

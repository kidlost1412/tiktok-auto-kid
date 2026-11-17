<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use Symfony\Component\Process\Process;
use Throwable;

/**
 * Nghe lời nói trong video Kho riêng bằng Whisper chạy ngay trên máy (miễn phí, không gửi tiếng ra ngoài).
 *
 * Dùng Python của Xưởng (runtime/xuong-venv). Lần đầu cần thì app tự cài faster-whisper vào đó (chạy nền),
 * model tải về storage/app/whisper (~1.6 GB, một lần). Có card đồ hoạ NVIDIA thì chạy bằng card, không thì CPU.
 * Chỉ dùng khi AI xem hình chưa nhận ra sản phẩm (bậc "nghe thêm lời nói" của RiengAnalyzer).
 */
class RiengSpeech
{
    public const string MODEL = 'large-v3-turbo';

    public const int TIMEOUT = 900;

    public function dir(): string
    {
        return rtrim((string) (config('fork.auto.whisper_dir') ?: storage_path('app/whisper')), '/\\');
    }

    public function python(): ?string
    {
        $env = (string) (getenv('XUONG_PYTHON') ?: '');
        $candidates = array_filter([
            (string) config('fork.auto.speech_python', ''),
            $env === '' ? null : (preg_match('#^([A-Za-z]:|[\\\\/])#', $env) === 1 ? $env : base_path($env)),
            base_path('runtime/xuong-venv/Scripts/python.exe'),
        ]);

        foreach ($candidates as $c) {
            if (is_file($c)) {
                return $c;
            }
        }

        return null;
    }

    /** @return array{python: bool, installed: bool, installing: bool, error: ?string} */
    public function status(): array
    {
        $dir = $this->dir();
        $installed = is_file($dir.DIRECTORY_SEPARATOR.'cai-xong.txt');
        $marker = $dir.DIRECTORY_SEPARATOR.'cai.running';
        $installing = ! $installed && is_file($marker) && time() - (int) @filemtime($marker) < 30 * 60;
        $error = null;

        if (! $installed && ! $installing) {
            @unlink($marker);
            $log = trim((string) @file_get_contents($dir.DIRECTORY_SEPARATOR.'cai.log'));

            if ($log !== '') {
                $lines = array_values(array_filter(array_map('trim', preg_split('/\R/', $log) ?: []), fn (string $l): bool => $l !== '' && ! str_starts_with($l, '[notice]')));
                $error = 'Cài bộ nghe chưa xong: '.mb_substr((string) end($lines), 0, 200);
            }
        }

        return ['python' => $this->python() !== null, 'installed' => $installed, 'installing' => $installing, 'error' => $error];
    }

    /** Cài faster-whisper vào Python của Xưởng (chạy nền, vài phút). Trả lỗi nếu không cài được. */
    public function install(): ?string
    {
        $st = $this->status();

        if ($st['installed'] || $st['installing']) {
            return null;
        }

        $python = $this->python();

        if ($python === null) {
            return 'Máy chưa có Python của Xưởng Video nên chưa nghe được lời nói.';
        }

        $dir = $this->dir();
        @mkdir($dir, 0775, true);
        $marker = $dir.DIRECTORY_SEPARATOR.'cai.running';
        $log = $dir.DIRECTORY_SEPARATOR.'cai.log';
        $done = $dir.DIRECTORY_SEPARATOR.'cai-xong.txt';
        @file_put_contents($marker, (string) time());

        if (PHP_OS_FAMILY === 'Windows') {
            $script = $dir.DIRECTORY_SEPARATOR.'cai.cmd';
            file_put_contents($script, "@echo off\r\nchcp 65001 >nul\r\n"
                .'"'.$python.'" -m pip install --disable-pip-version-check faster-whisper > "'.$log.'" 2>&1'."\r\n"
                .'if not errorlevel 1 "'.$python.'" -c "import faster_whisper" >> "'.$log.'" 2>&1 && echo ok> "'.$done.'"'."\r\n"
                .'del "'.$marker.'" >nul 2>&1'."\r\n");
            (new Process(['cmd.exe', '/c', 'start', '""', '/b', 'cmd.exe', '/c', $script]))->setTimeout(15)->run();
        }

        return null;
    }

    /** Bộ nghe đã cài xong, dùng được ngay. */
    public function ready(): bool
    {
        return $this->status()['installed'] && $this->python() !== null;
    }

    /**
     * Lời nói trong video (tiếng Việt). null khi bộ nghe chưa sẵn sàng hoặc nghe lỗi; '' khi video không có tiếng nói.
     * Bộ nghe chưa cài thì bắt đầu cài ở nền để lần sau dùng được.
     */
    public function transcribe(string $video): ?string
    {
        if (! $this->status()['installed']) {
            $this->install();

            return null;
        }

        $python = $this->python();

        if ($python === null || ! is_file($video)) {
            return null;
        }

        try {
            $p = new Process([$python, resource_path('python/nghe_loi.py'), $video, $this->dir().DIRECTORY_SEPARATOR.'model', self::MODEL], null, ['PYTHONIOENCODING' => 'utf-8', 'PYTHONUTF8' => '1'], null, self::TIMEOUT);
            $p->run();
            $lines = array_values(array_filter(array_map('trim', preg_split('/\R/', $p->getOutput()) ?: [])));
            $json = json_decode((string) end($lines), true);

            return is_array($json) && ($json['ok'] ?? false) ? mb_substr(trim((string) ($json['text'] ?? '')), 0, 4000) : null;
        } catch (Throwable) {
            return null;
        }
    }
}

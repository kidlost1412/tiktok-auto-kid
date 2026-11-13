<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\Models\AutoVideo;
use Symfony\Component\Process\ExecutableFinder;
use Symfony\Component\Process\Process;
use Throwable;

/** Ảnh nhỏ (một khung hình) của video riêng, dựng bằng ffmpeg và nhớ ở storage/app/rieng-thumbs/<id>.jpg. */
final class RiengThumbs
{
    public function dir(): string
    {
        return storage_path('app/rieng-thumbs');
    }

    public function cachePath(AutoVideo $v): string
    {
        return $this->dir().'/'.(int) $v->id.'-'.substr((string) $v->hash, 0, 8).'.jpg';
    }

    /** Đường dẫn ảnh (dựng nếu chưa có); null nếu không có ffmpeg hoặc dựng lỗi. */
    public function get(AutoVideo $v): ?string
    {
        $out = $this->cachePath($v);

        if (is_file($out) && filesize($out) > 0) {
            return $out;
        }

        $src = (string) $v->path;
        $ffmpeg = $this->ffmpeg();

        if ($ffmpeg === null || $src === '' || ! is_file($src)) {
            return null;
        }

        if (! is_dir($this->dir()) && ! @mkdir($this->dir(), 0775, true) && ! is_dir($this->dir())) {
            return null;
        }

        $tmp = $out.'.'.bin2hex(random_bytes(3)).'.tmp.jpg';
        $at = $v->duration !== null && $v->duration > 2 ? '1' : '0';

        try {
            $p = new Process([$ffmpeg, '-y', '-v', 'error', '-ss', $at, '-i', $src, '-frames:v', '1', '-vf', 'scale=360:-2', '-q:v', '5', $tmp]);
            $p->setTimeout(30);
            $p->run();
        } catch (Throwable) {
            @unlink($tmp);

            return null;
        }

        if (is_file($tmp) && filesize($tmp) > 0 && @rename($tmp, $out)) {
            return $out;
        }

        @unlink($tmp);

        return null;
    }

    /** Xoá ảnh nhớ của một video (khi bỏ thư mục khỏi Kho riêng). Không đụng file video. */
    public function forget(AutoVideo $v): void
    {
        $out = $this->cachePath($v);

        if (is_file($out)) {
            @unlink($out);
        }
    }

    /** ffmpeg của app (runtime/ffmpeg) hoặc trong PATH; null nếu không có. */
    public function ffmpegPath(): ?string
    {
        return $this->ffmpeg();
    }

    private function ffmpeg(): ?string
    {
        foreach ([base_path('runtime/ffmpeg/bin/ffmpeg.exe'), base_path('runtime/ffmpeg/bin/ffmpeg')] as $local) {
            if (is_file($local)) {
                return $local;
            }
        }

        return (new ExecutableFinder)->find('ffmpeg');
    }
}

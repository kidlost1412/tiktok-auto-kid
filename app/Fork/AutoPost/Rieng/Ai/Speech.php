<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng\Ai;

use App\Fork\AutoPost\Paths;
use Dotenv\Dotenv;
use Illuminate\Support\Facades\Http;
use RuntimeException;
use Throwable;

/** Chép lời nói trong video bằng ElevenLabs Speech-to-Text (dùng khoá ElevenLabs của Xưởng Video). */
final class Speech
{
    public const string URL = 'https://api.elevenlabs.io/v1/speech-to-text';

    /** Khoá ElevenLabs: biến môi trường của app → file .env trong thư mục dữ liệu Xưởng. null nếu chưa có. */
    public function key(): ?string
    {
        $env = trim((string) (getenv('ELEVENLABS_API_KEY') ?: ''));

        if ($env !== '') {
            return $env;
        }

        $file = Paths::root((string) config('fork.auto.hub_path')).'/.env';

        try {
            $vars = is_file($file) ? Dotenv::parse((string) file_get_contents($file)) : [];
        } catch (Throwable) {
            $vars = [];
        }

        $key = trim((string) ($vars['ELEVENLABS_API_KEY'] ?? ''));

        return $key === '' ? null : $key;
    }

    /** Lời nói (tiếng Việt) trong file âm thanh; '' nếu không có lời. Lỗi mạng/khoá thì ném RuntimeException. */
    public function transcribe(string $audioFile): string
    {
        $key = $this->key();

        if ($key === null) {
            throw new RuntimeException('Chưa có khoá ElevenLabs để chép lời.');
        }

        $res = Http::timeout(120)
            ->withHeaders(['xi-api-key' => $key])
            ->attach('file', (string) file_get_contents($audioFile), basename($audioFile))
            ->post(self::URL, ['model_id' => 'scribe_v1', 'language_code' => 'vie', 'tag_audio_events' => 'false']);

        if (! $res->successful()) {
            throw new RuntimeException('ElevenLabs chép lời lỗi (mã '.$res->status().').');
        }

        return trim((string) ($res->json('text') ?? ''));
    }
}

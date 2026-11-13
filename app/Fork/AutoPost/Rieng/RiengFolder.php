<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Rieng;

use App\Fork\AutoPost\Models\AutoVideo;
use Illuminate\Database\Eloquent\Model;

/** Một thư mục video riêng của chủ app (đường dẫn Windows, lưu dạng dùng '/'). */
class RiengFolder extends Model
{
    protected $table = 'fork_rieng_folders';

    protected $guarded = [];

    public function displayName(): string
    {
        if (filled($this->name)) {
            return (string) $this->name;
        }

        $base = basename(rtrim((string) $this->path, '/'));

        return $base !== '' ? $base : (string) $this->path;
    }

    /** Video (mọi trạng thái) đã nhặt từ thư mục này. */
    public function videosQuery()
    {
        return AutoVideo::query()->where('source', AutoVideo::SOURCE_RIENG)->where('meta->folder_id', (string) $this->id);
    }
}

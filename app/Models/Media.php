<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\Media\Type as MediaType;
use App\Jobs\Media\DeleteMediaFiles;
use Database\Factories\MediaFactory;
use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\MorphTo;
use Illuminate\Support\Facades\Storage;

/** File video của một bài (bảng `medias`), thuộc về bài qua post_id. */
class Media extends Model
{
    /** @use HasFactory<MediaFactory> */
    use HasFactory, HasUuids;

    public const string COLLECTION_MEDIA = 'media';

    protected $table = 'medias';

    protected $appends = ['url'];

    protected $fillable = [
        'workspace_id',
        'post_id',
        'group_id',
        'collection',
        'type',
        'path',
        'original_filename',
        'mime_type',
        'size',
        'order',
        'meta',
        'upload_token',
    ];

    protected function casts(): array
    {
        return [
            'type' => MediaType::class,
            'size' => 'integer',
            'order' => 'integer',
            'meta' => 'array',
        ];
    }

    public function workspace(): BelongsTo
    {
        return $this->belongsTo(Workspace::class);
    }

    public function post(): BelongsTo
    {
        return $this->belongsTo(Post::class);
    }

    protected function url(): Attribute
    {
        return Attribute::make(
            get: fn () => Storage::url($this->path),
        );
    }

    public function isVideo(): bool
    {
        return MediaType::classify($this->mime_type, $this->path) === MediaType::Video;
    }

    public function isImage(): bool
    {
        return MediaType::classify($this->mime_type, $this->path) === MediaType::Image;
    }

    /**
     * File chỉ bị xoá sau khi commit và chỉ khi không dòng nào khác dùng cùng đường dẫn,
     * để xoá bị rollback không để lại dòng trỏ tới file đã mất.
     */
    public function delete(): bool
    {
        $deleted = (bool) parent::delete();

        if ($deleted && filled($this->path)) {
            DeleteMediaFiles::dispatch([$this->path])->afterCommit();
        }

        return $deleted;
    }
}

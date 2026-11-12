<?php

declare(strict_types=1);

namespace App\Dto;

use App\Enums\Media\Type;
use App\Models\Media;

/** Một mục trong `posts.media` (JSON). */
class MediaItem
{
    /**
     * @param  array<string, mixed>|null  $meta
     */
    public function __construct(
        public readonly string $id,
        public readonly string $path,
        public readonly string $url,
        public readonly ?string $mime_type = null,
        public readonly ?string $original_filename = null,
        public readonly ?array $meta = null,
        public readonly ?Type $type = null,
        public readonly ?int $size = null,
    ) {}

    public static function fromMedia(Media $media): self
    {
        return new self(
            id: $media->id,
            path: $media->path,
            url: $media->url,
            mime_type: $media->mime_type,
            original_filename: $media->original_filename,
            meta: ($media->meta ?? []) ?: null,
            type: $media->type,
            size: $media->size,
        );
    }

    /**
     * @return array<string, mixed>
     */
    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'path' => $this->path,
            'url' => $this->url,
            'type' => $this->type?->value,
            'mime_type' => $this->mime_type,
            'original_filename' => $this->original_filename,
            'size' => $this->size,
            ...array_filter(['meta' => $this->meta]),
        ];
    }

    public function isVideo(): bool
    {
        return $this->kind() === Type::Video;
    }

    public function isImage(): bool
    {
        return $this->kind() === Type::Image;
    }

    /** `type` đã lưu được ưu tiên; mục cũ chưa có thì phân loại theo MIME rồi theo đuôi file. */
    private function kind(): ?Type
    {
        return $this->type ?? Type::classify($this->mime_type, $this->path);
    }

    /**
     * @param  array<string, mixed>  $data
     */
    public static function fromArray(array $data): self
    {
        $meta = data_get($data, 'meta');
        $type = data_get($data, 'type');
        $size = data_get($data, 'size');

        return new self(
            id: (string) data_get($data, 'id', ''),
            path: (string) data_get($data, 'path', ''),
            url: (string) data_get($data, 'url', ''),
            mime_type: data_get($data, 'mime_type'),
            original_filename: data_get($data, 'original_filename'),
            meta: is_array($meta) ? $meta : null,
            type: is_string($type) ? Type::tryFrom($type) : null,
            size: is_numeric($size) ? (int) $size : null,
        );
    }
}

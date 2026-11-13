<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Fork\AutoPost\HubText;
use App\Fork\AutoPost\Media\ProductImages;
use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Models\AutoVideo;
use App\Fork\AutoPost\Persona\CoverStore;
use App\Fork\AutoPost\Persona\Hashtags;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;
use InvalidArgumentException;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

/** "Cá nhân hoá" theo sản phẩm hub: ảnh bìa riêng và hashtag riêng (cùng mặc định chung cho sản phẩm không có hashtag riêng). */
final class PersonaliseController
{
    use ScopesToOwner;

    /** @return array<string, mixed> dữ liệu cho giao diện */
    public static function stateFor(AutoProduct $p): array
    {
        return [
            'cover_mode' => CoverStore::normalizeMode($p->cover_mode),
            'cover_fixed' => $p->cover_fixed,
            'covers' => app(CoverStore::class)->describe($p),
            'hashtags' => Hashtags::normalize($p->hashtags),
            'hashtag_mode' => Hashtags::normalizeMode($p->hashtag_mode),
            'hashtag_pick' => max(0, (int) $p->hashtag_pick),
        ];
    }

    /**
     * Trang "Ảnh bìa & hashtag" (/auto/anh-bia-hashtag): mọi sản phẩm hub đang bật, mỗi sản phẩm một thẻ
     * tóm tắt ảnh bìa, hashtag và một dòng caption mẫu; sửa bằng cùng hộp thoại "Cá nhân hoá" của trang Giỏ hàng.
     */
    public function index(Request $request): Response
    {
        $accountId = $this->authorizeOwner($request);
        $products = AutoProduct::query()->where('enabled', true)->orderBy('short_name')->get();
        $images = ProductImages::lookup($this->tiktokAccounts($accountId)->pluck('id')->map(fn ($id): string => (string) $id)->all());

        return Inertia::render('fork/AnhBiaHashtag', [
            'products' => $products->map(fn (AutoProduct $p): array => [
                'code' => $p->code,
                'name' => (string) $p->short_name,
                'full_name' => (string) $p->name,
                'image' => $images->forCode($p->code),
                'quy_cach' => array_values(array_filter(array_map(
                    fn ($q): ?string => is_array($q) && filled($q['ten'] ?? null) ? (string) $q['ten'] : null,
                    (array) ($p->quy_cach ?? []),
                ))),
                'videos_waiting' => AutoVideo::query()->notRieng()->where('product_code', $p->code)->where('status', AutoVideo::NEW)->count(),
                'caption' => $this->captionPreview($p),
            ])->values()->all(),
            // Cùng tên prop với trang Giỏ hàng: hộp thoại tải lại 'personalise' sau khi thêm/xoá ảnh.
            'personalise' => $products->mapWithKeys(fn (AutoProduct $p): array => [$p->code => self::stateFor($p)])->all(),
            'personalise_default' => Hashtags::defaults(),
        ]);
    }

    /**
     * Caption cuối cùng của một bài ví dụ: lấy caption video gần nhất của sản phẩm (nếu có), áp hashtag như lúc đăng.
     *
     * @return array{text: string, source: string, source_hashtags: string}
     */
    private function captionPreview(AutoProduct $p): array
    {
        $video = AutoVideo::query()
            ->where('product_code', $p->code)
            ->whereNotNull('caption')->where('caption', '!=', '')
            ->latest('id')
            ->first(['id', 'caption', 'hashtags']);

        $caption = $video !== null ? (string) $video->caption : 'Caption hub viết cho video '.$p->short_name.'…';
        $hubTags = $video !== null ? Hashtags::normalize($video->hashtags ?? []) : [];
        $final = app(Hashtags::class)->apply($caption, $hubTags, $p);

        return [
            'text' => HubText::compose($final['caption'], $final['hashtags']),
            'source' => $video !== null ? 'video' : 'sample',
            // product | default | none: hashtag thêm vào đến từ đâu.
            'source_hashtags' => app(Hashtags::class)->configFor($p)['source'],
        ];
    }

    public function update(Request $request, string $code): RedirectResponse
    {
        $this->authorizeOwner($request);
        $product = AutoProduct::query()->findOrFail($code);

        $data = $request->validate([
            'cover_mode' => ['sometimes', 'in:default,fixed,random'],
            'cover_fixed' => ['sometimes', 'nullable', 'string', 'max:100'],
            'hashtags' => ['sometimes', 'nullable', 'string', 'max:5000'],
            'hashtag_mode' => ['sometimes', 'in:append,replace'],
            'hashtag_pick' => ['sometimes', 'integer', 'min:0', 'max:'.Hashtags::MAX_TAGS],
        ]);

        $fill = [];

        if (array_key_exists('cover_mode', $data)) {
            $fill['cover_mode'] = $data['cover_mode'];
        }

        if (array_key_exists('cover_fixed', $data)) {
            $fixed = $data['cover_fixed'];
            $fill['cover_fixed'] = $fixed !== null && CoverStore::pathFor($product, $fixed) !== null ? $fixed : null;
        }

        if (array_key_exists('hashtags', $data)) {
            $fill['hashtags'] = Hashtags::normalize($data['hashtags'] ?? '');
        }

        foreach (['hashtag_mode', 'hashtag_pick'] as $k) {
            if (array_key_exists($k, $data)) {
                $fill[$k] = $data[$k];
            }
        }

        $product->forceFill($fill)->save();

        return back()->with('flash.success', 'Đã lưu cá nhân hoá cho '.$product->short_name.'.');
    }

    public function upload(Request $request, string $code): RedirectResponse
    {
        $this->authorizeOwner($request);
        $product = AutoProduct::query()->findOrFail($code);

        $request->validate([
            'images' => ['required', 'array', 'min:1', 'max:'.CoverStore::MAX_IMAGES],
            'images.*' => ['file', 'max:'.(CoverStore::MAX_BYTES / 1024), 'mimes:jpg,jpeg,png,webp'],
        ], [
            'images.*.max' => 'Ảnh lớn hơn 5 MB.',
            'images.*.mimes' => 'Chỉ nhận ảnh jpg, png hoặc webp.',
            'images.*.file' => 'Không đọc được file ảnh.',
            'images.required' => 'Chưa chọn ảnh.',
        ]);

        $store = app(CoverStore::class);
        $ok = 0;
        $notes = [];

        foreach ($request->file('images', []) as $file) {
            try {
                $product->refresh();
                $res = $store->add($product, $file);
                $product->forceFill(['cover_images' => [...($product->cover_images ?? []), $res['entry']]])->save();
                $ok++;

                if ($res['warning'] !== null) {
                    $notes[] = $res['warning'];
                }
            } catch (InvalidArgumentException $e) {
                $notes[] = ($file->getClientOriginalName() ?: 'ảnh').': '.$e->getMessage();
            }
        }

        if ($ok === 0) {
            return back()->with('flash.error', implode(' ', array_slice($notes, 0, 3)) ?: 'Không thêm được ảnh nào.');
        }

        return back()->with('flash.success', 'Đã thêm '.$ok.' ảnh bìa.'.($notes === [] ? '' : ' Lưu ý: '.implode(' ', array_slice($notes, 0, 3))));
    }

    public function destroy(Request $request, string $code, string $file): RedirectResponse
    {
        $this->authorizeOwner($request);
        $product = AutoProduct::query()->findOrFail($code);

        abort_unless(app(CoverStore::class)->remove($product, $file), SymfonyResponse::HTTP_NOT_FOUND);

        return back()->with('flash.success', 'Đã xoá ảnh bìa.');
    }

    public function image(Request $request, string $code, string $file): BinaryFileResponse
    {
        $this->authorizeOwner($request);
        $product = AutoProduct::query()->findOrFail($code);
        $path = CoverStore::pathFor($product, $file);

        abort_if($path === null, SymfonyResponse::HTTP_NOT_FOUND);

        return response()->file($path, ['Content-Type' => 'image/jpeg', 'Cache-Control' => 'private, max-age=86400']);
    }

    /** Xem trước caption cuối cùng với một caption mẫu, theo cấu hình đang nhập (chưa cần lưu). */
    public function preview(Request $request, string $code): JsonResponse
    {
        $this->authorizeOwner($request);
        $product = AutoProduct::query()->findOrFail($code);

        $data = $request->validate([
            'sample' => ['nullable', 'string', 'max:2200'],
            'hashtags' => ['nullable', 'string', 'max:5000'],
            'hashtag_mode' => ['nullable', 'in:append,replace'],
            'hashtag_pick' => ['nullable', 'integer', 'min:0', 'max:'.Hashtags::MAX_TAGS],
        ]);

        $draft = clone $product;
        $draft->hashtags = Hashtags::normalize($data['hashtags'] ?? '');
        $draft->hashtag_mode = Hashtags::normalizeMode($data['hashtag_mode'] ?? null);
        $draft->hashtag_pick = (int) ($data['hashtag_pick'] ?? 0);

        return response()->json($this->render((string) ($data['sample'] ?? ''), $draft));
    }

    public function updateDefault(Request $request): RedirectResponse
    {
        $this->authorizeOwner($request);

        $data = $request->validate([
            'hashtags' => ['nullable', 'string', 'max:5000'],
            'hashtag_mode' => ['required', 'in:append,replace'],
            'hashtag_pick' => ['required', 'integer', 'min:0', 'max:'.Hashtags::MAX_TAGS],
        ]);

        Hashtags::saveDefaults((string) ($data['hashtags'] ?? ''), $data['hashtag_mode'], (int) $data['hashtag_pick']);

        return back()->with('flash.success', 'Đã lưu hashtag mặc định chung.');
    }

    public function previewDefault(Request $request): JsonResponse
    {
        $this->authorizeOwner($request);

        $data = $request->validate([
            'sample' => ['nullable', 'string', 'max:2200'],
            'hashtags' => ['nullable', 'string', 'max:5000'],
            'hashtag_mode' => ['nullable', 'in:append,replace'],
            'hashtag_pick' => ['nullable', 'integer', 'min:0', 'max:'.Hashtags::MAX_TAGS],
        ]);

        $draft = new AutoProduct([
            'hashtags' => Hashtags::normalize($data['hashtags'] ?? ''),
            'hashtag_mode' => Hashtags::normalizeMode($data['hashtag_mode'] ?? null),
            'hashtag_pick' => (int) ($data['hashtag_pick'] ?? 0),
        ]);

        return response()->json($this->render((string) ($data['sample'] ?? ''), $draft));
    }

    /** @return array{text: string, length: int, max: int} */
    private function render(string $sample, AutoProduct $draft): array
    {
        $sample = trim($sample) !== '' ? $sample : 'Đạm cá nguyên chất cho cây khoẻ, ra hoa đẹp #damca #phanbon';
        $sampleTags = Hashtags::tagsIn($sample);
        $final = app(Hashtags::class)->apply($sample, [], $draft);
        $text = HubText::compose($final['caption'], $final['hashtags']);

        return ['text' => $text, 'length' => mb_strlen($text), 'max' => HubText::MAX_CHARS, 'sample_tags' => $sampleTags];
    }
}

<?php

declare(strict_types=1);

namespace App\Http\Middleware\App;

use App\Fork\AutoPost\Models\VideoComment;
use Illuminate\Http\Request;
use Inertia\Middleware;

class HandleInertiaRequests extends Middleware
{
    protected $rootView = 'app';

    /**
     * @return array<string, mixed>
     */
    public function share(Request $request): array
    {
        return [
            ...parent::share($request),
            'name' => config('app.name'),
            'flash' => $request->session()->get('flash', []),
            // Số bình luận "hỏi mua" trong 24 giờ qua, hiện thành chấm số cạnh mục Số liệu.
            'fork_badges' => fn (): ?array => $request->user()?->isAccountOwner()
                ? ['buy_comments' => VideoComment::query()->where('is_buy_intent', true)->where('commented_at', '>=', now()->subDay())->count()]
                : null,
        ];
    }
}

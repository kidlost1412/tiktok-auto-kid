<?php

declare(strict_types=1);

namespace App\Fork\AutoPost\Http;

use App\Enums\SocialAccount\Platform;
use App\Models\SocialAccount;
use App\Models\Workspace;
use Illuminate\Http\Request;
use Illuminate\Support\Collection;
use Symfony\Component\HttpFoundation\Response as SymfonyResponse;

/** Các trang /auto chỉ dành cho chủ tài khoản (bản tự host) và chỉ thấy tài khoản TikTok của mình. */
trait ScopesToOwner
{
    private function authorizeOwner(Request $request): string
    {
        abort_unless(
            $request->user()?->isAccountOwner(),
            SymfonyResponse::HTTP_FORBIDDEN,
        );

        return (string) $request->user()->account_id;
    }

    /**
     * @return Collection<int, SocialAccount>
     */
    private function tiktokAccounts(string $accountId)
    {
        return SocialAccount::query()
            ->whereIn('workspace_id', Workspace::query()->where('account_id', $accountId)->pluck('id'))
            ->where('platform', Platform::TikTok->value)
            ->orderBy('username')
            ->get();
    }

    private function findAccount(string $accountId, string $id): SocialAccount
    {
        return $this->tiktokAccounts($accountId)->first(fn (SocialAccount $a): bool => $a->id === $id)
            ?? abort(SymfonyResponse::HTTP_NOT_FOUND);
    }
}

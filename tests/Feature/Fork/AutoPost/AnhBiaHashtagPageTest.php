<?php

declare(strict_types=1);

use App\Fork\AutoPost\Models\AutoProduct;
use App\Fork\AutoPost\Persona\HashtagSuggestions;
use App\Fork\AutoPost\Persona\Hashtags;
use App\Models\Account;
use App\Models\Post;
use App\Models\SocialAccount;
use App\Models\User;
use App\Models\Workspace;

beforeEach(function (): void {
    config()->set('trypost.self_hosted', true);

    $this->account = Account::factory()->create();
    $this->owner = User::factory()->create(['account_id' => $this->account->id]);
    $this->account->update(['owner_id' => $this->owner->id]);
    $this->workspace = Workspace::factory()->create(['account_id' => $this->account->id, 'user_id' => $this->owner->id]);
    $this->owner->update(['current_workspace_id' => $this->workspace->id]);
});

test('the old Ảnh bìa & hashtag page now redirects to Giỏ hàng', function (): void {
    $this->actingAs($this->owner)->get('/auto/anh-bia-hashtag')->assertRedirect('/auto/gio-hang');
});

test('the old Ảnh bìa & hashtag route is still owner-only', function (): void {
    $member = User::factory()->create(['account_id' => $this->account->id]);

    $this->actingAs($member)->get('/auto/anh-bia-hashtag')->assertForbidden();
});

test('hashtag suggestions rank past caption hashtags by frequency and add product and default hashtags', function (): void {
    $social = SocialAccount::factory()->tiktok()->create(['workspace_id' => $this->workspace->id]);

    foreach (['Cây khoẻ #damca #phanbon', 'Bón lá #DamCa', 'Mẹo hay #damca #nongnghiep'] as $content) {
        Post::factory()->forAccount($social)->create(['workspace_id' => $this->workspace->id, 'content' => $content]);
    }

    Post::factory()->forAccount($social)->create(['workspace_id' => $this->workspace->id, 'content' => 'Không có hashtag']);
    AutoProduct::query()->create(['code' => 'bon-la', 'name' => 'Bón lá', 'short_name' => 'Bón lá', 'facts' => [], 'enabled' => true, 'hashtags' => ['#rieng', '#phanbon']]);
    Hashtags::saveDefaults('#chung', 'append', 0);

    $top = HashtagSuggestions::top();
    $tags = array_column($top, 'tag');

    expect($tags[0])->toBe('#damca')
        ->and($top[0]['uses'])->toBe(3)
        ->and($tags)->toContain('#phanbon', '#nongnghiep', '#rieng', '#chung')
        // Không phân biệt hoa thường: chỉ một mục #damca.
        ->and(array_count_values(array_map('mb_strtolower', $tags))['#damca'])->toBe(1)
        // #phanbon vừa ở caption vừa ở sản phẩm nên đứng trên #nongnghiep (chỉ một lần trong caption).
        ->and(array_search('#phanbon', $tags, true))->toBeLessThan(array_search('#nongnghiep', $tags, true));
});

test('hashtag suggestions are empty when nothing was ever used', function (): void {
    expect(HashtagSuggestions::top())->toBe([]);
});

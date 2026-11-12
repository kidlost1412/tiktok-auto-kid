<?php

declare(strict_types=1);

namespace App\Fork\SingleUser;

use Illuminate\Console\Command;

final class SingleUserCommand extends Command
{
    protected $signature = 'fork:single-user';

    protected $description = 'Tạo chủ app + workspace nội bộ cho chế độ một người dùng (chạy lại nhiều lần vẫn an toàn)';

    public function handle(): int
    {
        if (! SingleUser::enabled()) {
            $this->line('APP_SINGLE_USER đang tắt: bỏ qua.');

            return self::SUCCESS;
        }

        $user = SingleUser::ensureOwner();

        $this->info("Chủ app: {$user->email} (workspace: {$user->currentWorkspace?->name})");

        return self::SUCCESS;
    }
}

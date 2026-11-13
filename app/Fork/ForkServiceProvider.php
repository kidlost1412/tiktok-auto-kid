<?php

declare(strict_types=1);

namespace App\Fork;

use App\Fork\SingleUser\SingleUserCommand;
use Illuminate\Support\ServiceProvider;

/** Nối các phần của app (Chrome, AutoPost, Notify, SingleUser) vào Laravel. */
final class ForkServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->register(Chrome\ChromeServiceProvider::class);
        $this->app->register(AutoPost\AutoPostServiceProvider::class);
        $this->app->register(Notify\NotifyServiceProvider::class);
        $this->app->register(Update\UpdateServiceProvider::class);
        $this->app->register(Nha\NhaServiceProvider::class);
        $this->app->register(Settings\SettingsServiceProvider::class);
    }

    public function boot(): void
    {
        if ($this->app->runningInConsole()) {
            $this->commands([SingleUserCommand::class]);
        }
    }
}

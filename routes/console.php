<?php

declare(strict_types=1);

use App\Console\Commands\ProcessScheduledPosts;
use App\Console\Commands\RecoverStuckPosts;
use Illuminate\Support\Facades\Schedule;

Schedule::command(ProcessScheduledPosts::class)->everyMinute()->withoutOverlapping(10)->onOneServer();
Schedule::command(RecoverStuckPosts::class)->everyThirtyMinutes()->withoutOverlapping(30)->onOneServer();

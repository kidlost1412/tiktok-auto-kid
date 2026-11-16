<?php

declare(strict_types=1);

namespace App\Fork\Notify;

/** Gửi một loạt tin cùng loại: bỏ tin đã gửi, quá 5 tin trong một lượt thì gộp thành một tin. */
final class Notifier
{
    public const int GROUP_OVER = 5;

    /**
     * @param  iterable<Message>  $messages
     * @param  (callable(list<Message>, string): Message)|null  $grouper  dựng tin gộp riêng (mặc định Messages::grouped)
     * @param  int  $groupOver  nhiều hơn chừng này tin trong một lượt thì gộp thành một tin
     * @return int số tin Telegram đã gửi
     */
    public static function dispatch(string $type, iterable $messages, ?callable $grouper = null, int $groupOver = self::GROUP_OVER): int
    {
        if (! Telegram::configured() || ! Telegram::allowed($type)) {
            return 0;
        }

        $fresh = [];

        foreach ($messages as $m) {
            if (! Telegram::wasSent($m->key)) {
                $fresh[] = $m;
            }
        }

        if ($fresh === []) {
            return 0;
        }

        if (count($fresh) > $groupOver) {
            $key = 'group:'.md5(implode('|', array_map(fn (Message $m): string => $m->key, $fresh)));
            $group = $grouper !== null ? $grouper($fresh, $key) : Messages::grouped($type, $fresh, $key);

            if (! Telegram::sendMessage($group)) {
                return 0;
            }

            foreach ($fresh as $m) {
                Telegram::markSent($m->key, $m->ttl);
            }

            return 1;
        }

        $sent = 0;

        foreach ($fresh as $m) {
            $sent += (int) Telegram::sendMessage($m);
        }

        return $sent;
    }
}

// Nhạc trong hộp Đăng hàng loạt: link nghe thử, máy phát dùng chung (một lúc chỉ một bài), hộp chọn thư mục nhạc.
import { ref } from 'vue';

import { callJson } from '@/components/fork/kho/rieng';

export interface MusicTrack {
    name: string;
    rel: string;
}

/** Cách ghép nhạc của lượt đăng: none = không ghép; random = bốc từ thư mục nhạc (seed cố định thứ tự bốc). */
export interface BatchMusicCfg {
    kind: 'none' | 'random';
    dir: string;
    mode: 'replace' | 'mix';
    gain_db: number;
    seed: number;
}

export const listenUrl = (dir: string, rel: string): string =>
    `/auto/kho/rieng/nhac/nghe?${new URLSearchParams({ dir, rel }).toString()}`;

/** Link đang phát (null = không phát gì). */
export const playingUrl = ref<string | null>(null);
let audio: HTMLAudioElement | null = null;

export function stopTrack(): void {
    audio?.pause();
    playingUrl.value = null;
}

export function toggleTrack(url: string): void {
    if (playingUrl.value === url) {
        stopTrack();

        return;
    }

    audio ??= new Audio();
    audio.onended = () => (playingUrl.value = null);
    audio.onerror = () => (playingUrl.value = null);
    audio.src = url;
    playingUrl.value = url;
    void audio.play().catch(() => (playingUrl.value = null));
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Mở hộp chọn thư mục của máy (chờ tới khi anh chọn xong). path = thư mục đã chọn; error = lý do không chọn được. */
export async function pickMusicDir(
    alive: () => boolean = () => true,
): Promise<{ path?: string; error?: string }> {
    type R = {
        ok?: boolean;
        pending?: boolean;
        id?: string;
        path?: string;
        cancelled?: boolean;
        error?: string;
    };
    let r = await callJson<R>('POST', '/auto/kho/rieng/chon-thu-muc', {
        muc_dich: 'nhac',
    });
    const started = Date.now();

    while (alive() && r.data?.pending && Date.now() - started < 11 * 60_000) {
        const id = r.data.id;
        await sleep(1000);

        if (id) {
            const next = await callJson<R>(
                'POST',
                '/auto/kho/rieng/chon-thu-muc/ket-qua',
                { id },
            );

            if (next.data === null) {
                break;
            }

            r = { ok: next.ok, data: { ...next.data, id } };
        }
    }

    if (r.data?.ok && r.data.path) {
        return { path: r.data.path };
    }

    return r.data?.cancelled
        ? {}
        : {
              error:
                  r.data?.error ??
                  'Chưa mở được hộp chọn thư mục, anh thử lại.',
          };
}

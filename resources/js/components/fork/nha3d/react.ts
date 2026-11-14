// Phản ứng của nhân vật khi chủ app thao tác trong popup "Bàn làm việc" (kênh bus.ts → world.react).
// Dùng lại hàng đợi bước của Actor: vẫy tay, gật đầu, chạy đi đưa thư, đi quanh kho… rồi về chỗ làm.
import type * as THREE from 'three';

import type { Actor, Step } from '@/components/fork/nha3d/actor';
import type { Owl } from '@/components/fork/nha3d/cast';
import type { Director } from '@/components/fork/nha3d/director';

export interface ReactDeps {
    A: Record<string, Actor>;
    owl: Owl;
    director: Director;
    camera: THREE.Camera;
    raiseFlag: () => void;
}

/** Vai của popup → khoá nhân vật trong cảnh (sảnh/bảng không có nhân vật riêng). */
const ACTOR_KEY: Record<string, string> = {
    daodien: 'daodienA',
    bang: 'thodung',
};

const LINE: Record<string, string> = {
    'buuta.xep-lich': 'Đi đưa thư đây!',
    'buuta.thu-lai': 'Để em gửi lại nha!',
    'chuquay.luu-gio': 'Giỏ hàng xong rồi!',
    'chuquay.lay-lai': 'Để em kiểm lại kệ.',
    'thukho.quet': 'Em đi kiểm kho liền!',
    'giamkhao.ung': 'Ưng! Bản này đạt.',
    'giamkhao.bo': 'Bản này bỏ nha.',
    'thodung.bat-dau': 'Vô việc thôi!',
};

const steps = (
    d: ReactDeps,
    a: Actor,
    vai: string,
    viec: string,
): Step[] | null => {
    const toCam = (): THREE.Vector3 => d.camera.position;
    const say = (text: string): Step => ({ k: 'say', text, prio: 'reply' });
    const text = LINE[`${vai}.${viec}`] ?? '';
    const back: Step[] = [
        { k: 'face', rot: a.home.rot },
        { k: 'home', gait: 'walk' },
    ];
    const nod: Step[] = [
        { k: 'anim', a: 'chat', d: 1.3, expr: 'happy' },
        ...(text ? [say(text)] : []),
    ];

    if (viec === 'mo') {
        const chao = d.director.line(a, 'chao_sep');

        return [
            { k: 'face', at: toCam },
            { k: 'anim', a: 'wave', d: 1.7, expr: 'happy' },
            ...(chao ? [say(chao)] : []),
            { k: 'wait', d: 0.4 },
            ...back,
        ];
    }
    if (viec === 'dong') {
        return null;
    }
    if (vai === 'buuta' && viec === 'xep-lich') {
        return [
            { k: 'item', item: 'letter' },
            say(text),
            { k: 'go', to: 'mail', gait: 'run' },
            { k: 'face', rot: 0 },
            { k: 'anim', a: 'give', d: 0.9 },
            { k: 'do', fn: d.raiseFlag },
            { k: 'item', item: null },
            { k: 'anim', a: 'wave', d: 1.2, expr: 'happy' },
            ...back,
        ];
    }
    if (vai === 'chuquay' && viec === 'lay-lai') {
        return [
            { k: 'go', to: 'chuquay.cart', gait: 'walk' },
            say(text),
            { k: 'anim', a: 'look', d: 2.4, expr: 'focus' },
            ...back,
        ];
    }
    if (vai === 'chuquay' && viec === 'luu-gio') {
        return [
            { k: 'anim', a: 'cheer', d: 1.5, expr: 'joy' },
            say(text),
            ...back,
        ];
    }
    if (vai === 'thukho' && viec === 'quet') {
        return [
            say(text),
            { k: 'go', to: 'thukho.mid', gait: 'walk' },
            { k: 'go', to: 'thukho.shelf', gait: 'walk' },
            { k: 'anim', a: 'look', d: 1.6, expr: 'focus' },
            ...back,
        ];
    }
    if (vai === 'giamkhao' && viec === 'ung') {
        return [
            { k: 'item', item: 'board' },
            { k: 'anim', a: 'cheer', d: 1.6, expr: 'joy' },
            say(text),
            { k: 'item', item: null },
            ...back,
        ];
    }
    if (vai === 'giamkhao' && viec === 'bo') {
        return [
            { k: 'anim', a: 'look', d: 1.6, expr: 'annoyed' },
            say(text),
            ...back,
        ];
    }
    if (vai === 'thodung' && viec === 'bat-dau') {
        return [
            say(text),
            { k: 'home', gait: 'run' },
            { k: 'anim', a: 'type', d: 6, expr: 'focus' },
        ];
    }

    return [...nod, ...back];
};

/** Cho nhân vật của `vai` phản ứng với `viec`. Đang bận việc thật thì chỉ nói một câu. */
export const reactTo = (d: ReactDeps, vai: string, viec: string): void => {
    if (viec === 'dong') {
        return;
    }
    if (vai === 'cu') {
        d.owl.hop();
        if (viec !== 'mo') {
            d.owl.say('Hú! Số liệu đây.');
        } else {
            d.owl.say('Hú hú, chào sếp!');
        }

        return;
    }
    const a = d.A[ACTOR_KEY[vai] ?? vai];
    if (!a) {
        return;
    }
    const plan = steps(d, a, vai, viec);
    if (!plan) {
        return;
    }
    if (!d.director.grab(a)) {
        // đang diễn việc thật: không chen ngang
        return;
    }
    a.push(...plan, d.director.release(a));
};

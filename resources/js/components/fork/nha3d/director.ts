// Đạo diễn hoạt cảnh: đọc dữ liệu thật từ /nha/trang-thai, biến từng sự kiện MỚI của hub thành màn diễn có thật
// (chạy đưa giấy, "hack" tín hiệu, giơ bảng điểm, cất cuộn phim…), xếp hàng để không loạn, và cho cả nhà sống động khi rảnh.
import * as THREE from 'three';

import { lineFor, noi } from '../nha/loi-thoai';
import type { NhaData, NhaEvent } from '../nha/types';
import type { Actor, Step, Talker } from './actor';
import type { Owl } from './cast';
import type { Cat } from './cat';
import type { AnimName, Expr } from './chibi';
import type { Effects } from './effects';
import type { House, Reel } from './house';
import { F1, F2, GATHER, MEET, room, SEATS, Z_FRONT, Z_ROOM } from './layout';
import type { NavGraph } from './nav';
import type { Pond } from './pond';
import { pick, rand } from './util';
import type { Weather } from './weather';
import type { Wings } from './wings';
import type { World } from './world';

interface Scene {
    need: Actor[];
    start: () => void;
    skip?: () => void;
    label: string;
    /** Màn chơi/nghỉ: ai đang có việc thì bỏ màn này. */
    leisure?: boolean;
}

const WORKERS = [
    'bienkich',
    'thuam',
    'daodienA',
    'daodienB',
    'thodung',
    'giamkhao',
    'thukho',
    'chuquay',
];
const ROLE: Record<string, string> = {
    daodienA: 'daodien',
    daodienB: 'daodien',
};
const VAI_ACTOR: Record<string, string> = {
    'bien-kich': 'bienkich',
    giong: 'thuam',
    'dao-dien': 'daodienA',
    dung: 'thodung',
    'giam-khao': 'giamkhao',
    kho: 'thukho',
};
const BEHIND: Record<string, string> = {
    bienkich: 'bienkich.behind',
    thuam: 'thuam.behind',
    giamkhao: 'giamkhao.behind',
    thodung: 'thodung.behind',
    daodienA: 'daodien.hfA',
    daodienB: 'daodien.hfB',
};

export class Director {
    private started = false;
    private cursor = 0;
    private lo: number | null | undefined = undefined;
    private postSum = -1;
    private queue: Scene[] = [];
    private pending = new Set<number>();
    private reels: Reel[] = [];
    private boardKey = '';
    private dirFlip = false;
    private owlChat = 25;
    private lastStates = new Map<string, string>();
    private cleanups = new Map<Actor, () => void>();
    private coffeeLine: Actor[] = [];
    private timers: { at: number; fn: () => void }[] = [];
    private planT = 12;
    private mealKey = '';
    private catCool = 20;
    /** Ngữ cảnh cho lời thoại: thời gian làm việc liên tục (mệt), lần gần nhất đạt/hỏng, tên sản phẩm. */
    private workT = new Map<Actor, number>();
    private goodAt = -999;
    private badAt = -999;
    private sanpham = '';
    private pairCool = new Map<string, number>();
    private greetCool = new Map<Actor, number>();
    private kidCatAt = 6;
    /** Nhân vật của chủ xưởng (khi đi dạo). */
    kid: Actor | null = null;
    /** Tên + cách xưng hô với chủ xưởng (từ "Nhân vật của tôi"). */
    player = { ten: 'Kid', anh: 'anh' };
    /** Ao (nhảy/rơi xuống) và thời tiết — gắn từ ngoài vào. */
    pond: Pond | null = null;
    weather: Weather | null = null;
    nav: NavGraph | null = null;
    /** Tình cảm với sếp (−5 giận … +5 quý), nhạt dần theo thời gian. */
    private rel = new Map<string, number>();
    private avoidCool = new Map<Actor, number>();
    readonly board: Talker;
    data: NhaData | null = null;
    log: string[] = [];

    constructor(
        private A: Record<string, Actor>,
        private owl: Owl,
        private cat: Cat,
        private house: House,
        private world: World,
        private fx: Effects,
        private now: () => number,
        private motion: boolean,
        private wings: Wings,
        private hour: () => number,
    ) {
        const c = room('sanh').cx;
        const boardPos = new THREE.Vector3(c, F1 + 2.95, -4.3);
        this.board = {
            key: 'bang',
            root: house.boardMesh,
            alertUntil: 0,
            anchor: (o) => o.copy(boardPos),
            bubble: () => null,
        };
        for (const a of Object.values(A)) {
            a.onIdle = (x) => this.idleFor(x);
        }
    }

    // ------------------------------------------------------------------ dữ liệu
    update(data: NhaData) {
        this.data = data;
        const events = data.events ?? [];
        const sum =
            (data.app.post_counts?.scheduled ?? 0) +
            (data.app.post_counts?.posted ?? 0);
        if (!this.started) {
            // lần đầu: chỉ lấy hiện trạng, KHÔNG diễn lại lịch sử
            this.started = true;
            this.cursor = events.reduce((m, e) => Math.max(m, e.n), 0);
            this.postSum = sum;
            this.lo = data.lo;
            this.reels = data.reels ?? [];
            this.syncShelf();
        } else {
            if (data.lo !== this.lo) {
                this.lo = data.lo;
                this.pending.clear();
            }
            this.reels = data.reels ?? [];
            const fresh = events
                .filter((e) => e.n > this.cursor)
                .sort((a, b) => a.n - b.n);
            for (const e of fresh) {
                this.cursor = Math.max(this.cursor, e.n);
                this.onEvent(e);
            }
            this.syncShelf();
            if (sum > this.postSum && this.postSum >= 0) {
                this.enqueue(this.postScene());
            }
            this.postSum = sum;
        }
        this.applyStates(data);
        const bk = JSON.stringify([data.bang, data.mode]);
        if (bk !== this.boardKey) {
            this.boardKey = bk;
            this.house.drawBoard(data.bang, data.mode);
        }
    }

    private syncShelf() {
        this.house.setReels(this.reels.filter((r) => !this.pending.has(r.n)));
    }

    private applyStates(d: NhaData) {
        const down = d.mode === 'down';
        const working = new Set<string>();
        for (const [k, a] of Object.entries(this.A)) {
            const role = ROLE[k] ?? k;
            const v = d.vai[role];
            const st = down ? 'sleep' : (v?.state ?? 'idle');
            if (st === 'working') {
                working.add(role);
            }
            const prev = this.lastStates.get(k);
            a.base = st;
            a.bubbleText = v?.bubble ?? null;
            if (
                prev !== undefined &&
                prev !== st &&
                st === 'working' &&
                (!a.inScene || a.leisure)
            ) {
                // có việc giữa lúc đang chơi: bỏ hết, lật đật chạy về bàn (không dịch chuyển tức thời)
                this.cleanups.get(a)?.();
                this.cleanups.delete(a);
                this.leaveLine(a);
                a.interrupt();
                a.inScene = false;
                a.leisure = false;
                if (!a.atHome && this.motion) {
                    a.push(
                        {
                            k: 'say',
                            text: this.line(a, 'co_viec'),
                            prio: 'work',
                        },
                        { k: 'expr', e: 'surprise', d: 1.5 },
                        { k: 'stand' },
                        { k: 'home', gait: 'sprint' },
                    );
                }
            } else if (
                prev !== undefined &&
                prev !== st &&
                st !== 'idle' &&
                !a.inScene
            ) {
                a.interrupt(); // bỏ việc vặt, về chỗ làm/ngủ
            }
            this.lastStates.set(k, st);
        }
        this.owl.sleeping =
            down || d.mode === 'limit' || d.vai.cu?.state === 'sleep';
        this.house.setWorking(working);
    }

    // ------------------------------------------------------------------ hàng đợi màn diễn
    private enqueue(s: Scene | null) {
        if (!s) {
            return;
        }
        this.queue.push(s);
        // dồn quá nhiều (vd. quay lại tab sau lâu): bỏ bớt màn cũ, chỉ giữ hệ quả (cuộn phim lên kệ)
        while (this.queue.length > 8) {
            const old = this.queue.shift()!;
            old.skip?.();
        }
    }

    tick(dt: number) {
        void dt;
        // bắt đầu các màn mà diễn viên đã rảnh, giữ đúng thứ tự cho từng người
        const blocked = new Set<Actor>();
        for (let i = 0; i < this.queue.length; i++) {
            const s = this.queue[i];
            if (
                s.leisure &&
                s.need.some((a) => a.base !== 'idle' || a.leisure)
            ) {
                // có việc rồi, khỏi chơi
                this.queue.splice(i, 1);
                i--;
                continue;
            }
            const free = s.need.every(
                (a) =>
                    (!a.inScene || (a.leisure && !s.leisure)) &&
                    !blocked.has(a),
            );
            if (free) {
                for (const a of s.need) {
                    if (a.leisure) {
                        this.cleanups.get(a)?.();
                        this.cleanups.delete(a);
                        this.leaveLine(a);
                    }
                    const wasFun = a.leisure;
                    a.interrupt();
                    a.inScene = true;
                    a.leisure = !!s.leisure;
                    if (wasFun && !s.leisure && !a.atHome) {
                        a.push(
                            {
                                k: 'say',
                                text: this.line(a, 'co_viec'),
                                prio: 'work',
                            },
                            { k: 'stand' },
                        );
                    }
                }
                this.log.push(s.label);
                if (this.log.length > 30) {
                    this.log.shift();
                }
                s.start();
                this.queue.splice(i, 1);
                i--;
            } else {
                s.need.forEach((a) => blocked.add(a));
            }
        }
        // hẹn giờ nhỏ (câu đáp khi va nhau…)
        const now = this.now();
        for (let i = this.timers.length - 1; i >= 0; i--) {
            if (now >= this.timers[i].at) {
                const fn = this.timers[i].fn;
                this.timers.splice(i, 1);
                fn();
            }
        }
        this.planLeisure(dt);
        for (const a of Object.values(this.A)) {
            const w = this.workT.get(a) ?? 0;
            this.workT.set(
                a,
                Math.max(
                    0,
                    Math.min(1200, w + (a.base === 'working' ? dt : -dt * 0.6)),
                ),
            );
        }
        for (const [k, v] of this.rel) {
            const nv =
                v > 0 ? Math.max(0, v - dt / 50) : Math.min(0, v + dt / 50);
            if (nv === 0) {
                this.rel.delete(k);
            } else {
                this.rel.set(k, nv);
            }
        }
        this.noticeKid(dt);
        this.catBump();
        // Cú thỉnh thoảng nói
        this.owlChat -= dt;
        if (this.owlChat <= 0 && this.motion) {
            this.owlChat = rand(35, 70);
            if (!this.owl.sleeping) {
                this.owl.say(noi('cu_idle'), 4.5);
            }
        }
    }

    get queued() {
        return this.queue.length;
    }

    release = (a: Actor): Step => ({
        k: 'do',
        fn: () => {
            a.inScene = false;
            a.leisure = false;
            this.cleanups.get(a)?.();
            this.cleanups.delete(a);
        },
    });

    // ------------------------------------------------------------------ sự kiện → màn diễn
    onEvent(e: NhaEvent) {
        const key = `${e.vai}|${e.loai}`;
        if (e.loai === 'loi') {
            const who = VAI_ACTOR[e.vai];
            const t: Talker = who ? this.A[who] : this.board;
            t.alertUntil = this.now() + 8;
            if (who) {
                this.A[who].say(noi('loi'), 4);
                this.A[who].setExpr('sad', 6);
            }

            return;
        }
        switch (key) {
            case 'he-thong|bat-dau-lo':
                this.sanpham = e.ten ?? this.sanpham;
                this.enqueue(this.wakeScene());
                break;
            case 'bien-kich|xong':
                this.enqueue(
                    this.handoff(
                        'bienkich',
                        'thuam',
                        'paper',
                        'bienkich_giao',
                        'thuam_nhan',
                        'walk',
                    ),
                );
                break;
            case 'giong|xong':
                this.enqueue(this.hackScene());
                break;
            case 'dao-dien|xong': {
                this.dirFlip = !this.dirFlip;
                this.enqueue(
                    this.handoff(
                        this.dirFlip ? 'daodienA' : 'daodienB',
                        'thodung',
                        'board',
                        'daodien_giao',
                        'thodung_nhan',
                        'walk',
                        true,
                    ),
                );
                break;
            }
            case 'dung|xong':
                if (e.buoc !== 'chu') {
                    this.enqueue(this.renderScene());
                }
                break;
            case 'giam-khao|diem':
                if (e.dat) {
                    this.goodAt = this.now();
                } else if (e.dat === false) {
                    this.badAt = this.now();
                }
                if (e.diem != null) {
                    this.enqueue(
                        e.dat ? this.paddleScene(e) : this.redoScene(e),
                    );
                }
                break;
            case 'kho|luu':
                this.enqueue(this.reelScene(e));
                break;
            case 'he-thong|het-han-muc':
                this.enqueue(this.sleepScene());
                break;
            case 'he-thong|ket-thuc-lo':
                this.enqueue(this.partyScene());
                break;
            default:
                break;
        }
    }

    /** Người `from` mang `item` chạy tới chỗ người `to`, trao tận tay rồi về. */
    private handoff(
        from: string,
        to: string,
        item: 'paper' | 'board',
        giveLine: string,
        takeLine: string,
        gait: 'run' | 'walk' | 'stomp',
        drink = false,
    ): Scene {
        const F = this.A[from];
        const T = this.A[to];
        const flag = { arrived: false, done: false };

        return {
            label: `${from}→${to}`,
            need: [F, T],
            start: () => {
                F.push(
                    { k: 'say', text: noi(giveLine) },
                    { k: 'item', item },
                    { k: 'go', to: MEET[to], gait },
                    { k: 'face', at: () => T.pos },
                    { k: 'do', fn: () => (flag.arrived = true) },
                    { k: 'anim', a: 'give', d: 1.6 },
                    { k: 'item', item: null },
                    { k: 'do', fn: () => (flag.done = true) },
                    { k: 'wait', d: 0.4 },
                    { k: 'home', gait: 'walk' },
                    this.release(F),
                );
                T.push(
                    { k: 'home' },
                    { k: 'until', fn: () => flag.arrived, max: 40 },
                    { k: 'face', at: () => F.pos },
                    { k: 'say', text: noi(takeLine) },
                    { k: 'anim', a: 'receive', d: 1.6 },
                    { k: 'until', fn: () => flag.done, max: 3 },
                    { k: 'face', rot: T.home.rot },
                    ...(drink
                        ? ([
                              { k: 'item', item: 'can' },
                              { k: 'anim', a: 'drink', d: 1.4 },
                              { k: 'item', item: null },
                          ] as Step[])
                        : []),
                    this.release(T),
                );
            },
        };
    }

    private hackScene(): Scene {
        const T = this.A.thuam;
        const DA = this.A.daodienA;
        const DB = this.A.daodienB;
        const st = { sigAt: Infinity, a: false, b: false };
        const target = new THREE.Vector3(room('daodien').cx, F2 + 1.4, -2.2);

        return {
            label: 'hack',
            need: [T, DA, DB],
            start: () => {
                T.push(
                    { k: 'home' },
                    { k: 'say', text: noi('thuam_hack') },
                    { k: 'anim', a: 'smash', d: 0.7, expr: 'cocky' },
                    {
                        k: 'do',
                        fn: () => {
                            this.fx.signal(
                                T.anchor(new THREE.Vector3()).add(
                                    new THREE.Vector3(0, -0.5, 0.3),
                                ),
                                target,
                                1.9,
                            );
                            st.sigAt = this.now() + 1.9;
                        },
                    },
                    { k: 'anim', a: 'smash', d: 2.2, expr: 'cocky' },
                    this.release(T),
                );
                DA.push(
                    { k: 'home' },
                    { k: 'until', fn: () => this.now() > st.sigAt, max: 8 },
                    { k: 'expr', e: 'surprise', d: 0.8 },
                    { k: 'say', text: noi('daodien_cai_a') },
                    { k: 'anim', a: 'argue', d: 1.8, expr: 'annoyed' },
                    { k: 'wait', d: 1.2 },
                    { k: 'go', to: 'daodien.hfA' },
                    { k: 'face', at: () => DB.pos },
                    { k: 'do', fn: () => (st.a = true) },
                    { k: 'until', fn: () => st.b, max: 8 },
                    {
                        k: 'do',
                        fn: () =>
                            this.fx.sparkle(
                                DA.pos
                                    .clone()
                                    .add(DB.pos)
                                    .multiplyScalar(0.5)
                                    .add(new THREE.Vector3(0, 1.6, 0)),
                                8,
                            ),
                    },
                    { k: 'say', text: noi('daodien_hoa'), prio: 'reply' },
                    { k: 'anim', a: 'highfive', d: 1.0 },
                    { k: 'home' },
                    this.release(DA),
                );
                DB.push(
                    { k: 'home' },
                    { k: 'until', fn: () => this.now() > st.sigAt, max: 8 },
                    { k: 'wait', d: 1.1 },
                    { k: 'say', text: noi('daodien_cai_b') },
                    { k: 'anim', a: 'argue', d: 1.8, expr: 'annoyed' },
                    { k: 'go', to: 'daodien.hfB' },
                    { k: 'face', at: () => DA.pos },
                    { k: 'do', fn: () => (st.b = true) },
                    { k: 'until', fn: () => st.a, max: 8 },
                    { k: 'anim', a: 'highfive', d: 1.0 },
                    { k: 'home' },
                    this.release(DB),
                );
            },
        };
    }

    private renderScene(): Scene {
        const T = this.A.thodung;

        return {
            label: 'render',
            need: [T],
            start: () => {
                T.push(
                    { k: 'home' },
                    { k: 'say', text: noi('thodung_render') },
                    {
                        k: 'do',
                        fn: () =>
                            this.fx.sparkle(
                                T.anchor(new THREE.Vector3()).add(
                                    new THREE.Vector3(0, -0.6, 0.6),
                                ),
                                6,
                            ),
                    },
                    { k: 'anim', a: 'cheer', d: 1.3 },
                    this.release(T),
                );
            },
        };
    }

    private paddleScene(e: NhaEvent): Scene {
        const G = this.A.giamkhao;

        return {
            label: 'paddle',
            need: [G],
            start: () => {
                G.push(
                    { k: 'stand' },
                    { k: 'go', to: BEHIND.giamkhao },
                    { k: 'face', rot: 0 },
                    { k: 'item', item: 'paddle', arg: e.diem ?? '?' },
                    { k: 'say', text: noi('giamkhao_dat', { diem: e.diem }) },
                    {
                        k: 'do',
                        fn: () =>
                            this.fx.confetti(
                                G.anchor(new THREE.Vector3()).add(
                                    new THREE.Vector3(0, 0.3, 0.2),
                                ),
                                70,
                            ),
                    },
                    { k: 'anim', a: 'paddle', d: 3.0 },
                    { k: 'item', item: null },
                    { k: 'home' },
                    this.release(G),
                );
            },
        };
    }

    private redoScene(e: NhaEvent): Scene {
        const G = this.A.giamkhao;
        this.dirFlip = !this.dirFlip;
        const D = this.dirFlip ? this.A.daodienA : this.A.daodienB;
        const flag = { arrived: false };
        const loi = (e.loi ?? '').trim();
        const short = loi.length > 42 ? loi.slice(0, 40) + '…' : loi;

        return {
            label: 'redo',
            need: [G, D],
            start: () => {
                G.push(
                    { k: 'item', item: 'paper' },
                    { k: 'expr', e: 'annoyed', d: 60 },
                    { k: 'say', text: `Hừm… ${e.diem} điểm.` },
                    { k: 'go', to: 'daodien.meet', gait: 'stomp' },
                    { k: 'face', at: () => D.pos },
                    { k: 'do', fn: () => (flag.arrived = true) },
                    {
                        k: 'say',
                        text: short
                            ? `Làm lại! ${short}`
                            : noi('giamkhao_hong'),
                        d: 5,
                    },
                    { k: 'anim', a: 'give', d: 1.8 },
                    { k: 'item', item: null },
                    { k: 'anim', a: 'adjust', d: 1.0 },
                    { k: 'expr', e: 'focus', d: 1 },
                    { k: 'home', gait: 'walk' },
                    this.release(G),
                );
                D.push(
                    { k: 'home' },
                    { k: 'until', fn: () => flag.arrived, max: 60 },
                    { k: 'face', at: () => G.pos },
                    { k: 'wait', d: 1.6 },
                    { k: 'say', text: noi('daodien_nhan_lai') },
                    { k: 'anim', a: 'receive', d: 1.6, expr: 'sad' },
                    { k: 'face', rot: D.home.rot },
                    this.release(D),
                );
            },
        };
    }

    private reelScene(e: NhaEvent): Scene {
        const T = this.A.thodung;
        const K = this.A.thukho;
        const flag = { arrived: false };
        this.pending.add(e.n);
        const place = () => {
            if (this.pending.delete(e.n)) {
                this.syncShelf();
                this.house.popReel(e.n);
            }
        };

        return {
            label: 'reel',
            need: [T, K],
            skip: place,
            start: () => {
                T.push(
                    { k: 'say', text: noi('thodung_giao') },
                    { k: 'item', item: 'reel' },
                    { k: 'go', to: 'thukho.shelf', gait: 'walk' },
                    { k: 'face', rot: Math.PI },
                    { k: 'do', fn: () => (flag.arrived = true) },
                    { k: 'anim', a: 'give', d: 1.0 },
                    {
                        k: 'do',
                        fn: () => {
                            place();
                            const m = this.house.reelMeshes.get(e.n);
                            if (m) {
                                this.fx.sparkle(
                                    m.position
                                        .clone()
                                        .add(new THREE.Vector3(0, 0.1, 0.2)),
                                    8,
                                );
                            }
                        },
                    },
                    { k: 'item', item: null },
                    { k: 'wait', d: 0.4 },
                    { k: 'home', gait: 'walk' },
                    this.release(T),
                );
                K.push(
                    { k: 'home' },
                    { k: 'until', fn: () => flag.arrived, max: 50 },
                    { k: 'face', at: () => T.pos },
                    { k: 'say', text: noi('thukho_nhan') },
                    { k: 'anim', a: 'polish', d: 2.4 },
                    { k: 'face', rot: K.home.rot },
                    this.release(K),
                );
            },
        };
    }

    private sleepScene(): Scene {
        const list = WORKERS.map((k) => this.A[k]);
        const talkers = new Set([pick(list), pick(list)]);

        return {
            label: 'sleep',
            need: list,
            start: () => {
                for (const a of list) {
                    a.push(
                        { k: 'home' },
                        { k: 'wait', d: rand(0, 1.4) },
                        ...(talkers.has(a)
                            ? ([
                                  { k: 'say', text: noi('het_han_muc') },
                              ] as Step[])
                            : []),
                        { k: 'anim', a: 'yawn', d: 2.0, expr: 'sleepy' },
                        this.release(a),
                    );
                }
            },
        };
    }

    private wakeScene(): Scene {
        const list = WORKERS.map((k) => this.A[k]);
        const talkers = new Set([pick(list), pick(list), pick(list)]);

        return {
            label: 'wake',
            need: list,
            start: () => {
                this.owl.hop();
                for (const a of list) {
                    a.push(
                        { k: 'home' },
                        { k: 'wait', d: rand(0, 1.0) },
                        ...(talkers.has(a)
                            ? ([{ k: 'say', text: noi('thuc_day') }] as Step[])
                            : []),
                        { k: 'anim', a: 'stretch', d: 1.8, expr: 'joy' },
                        this.release(a),
                    );
                }
            },
        };
    }

    private partyScene(): Scene {
        const list = [...WORKERS, 'buuta'].map((k) => this.A[k]);
        const arrived = new Set<Actor>();
        const talkers = new Set([
            pick(list),
            pick(list),
            pick(list),
            pick(list),
        ]);
        let boomed = false;
        const c = room('sanh').cx;
        const boom = () => {
            if (boomed) {
                return;
            }
            boomed = true;
            this.fx.confetti(new THREE.Vector3(c - 1, F1 + 2.4, -1.2), 80, 1.4);
            this.fx.confetti(new THREE.Vector3(c + 1, F1 + 2.4, -1.2), 80, 1.4);
            this.owl.say(noi('xong_lo'), 4);
            this.owl.hop();
        };

        return {
            label: 'party',
            need: list,
            start: () => {
                this.cat.visit('g.4', 14);
                list.forEach((a, i) => {
                    a.push(
                        { k: 'wait', d: i * 0.25 },
                        { k: 'go', to: `g.${i % GATHER.length}`, gait: 'run' },
                        { k: 'face', rot: 0 },
                        { k: 'do', fn: () => arrived.add(a) },
                        {
                            k: 'until',
                            fn: () => arrived.size >= list.length,
                            max: 40,
                        },
                        { k: 'do', fn: boom },
                        ...(talkers.has(a)
                            ? ([
                                  { k: 'wait', d: rand(0, 0.8) },
                                  { k: 'say', text: noi('xong_lo') },
                              ] as Step[])
                            : []),
                        { k: 'anim', a: 'cheer', d: 3.2 },
                        { k: 'wait', d: rand(0.5, 2) },
                        { k: 'home', gait: 'walk' },
                        this.release(a),
                    );
                });
            },
        };
    }

    private postScene(): Scene {
        const P = this.A.buuta;

        return {
            label: 'post',
            need: [P],
            start: () => {
                P.push(
                    { k: 'item', item: 'letter' },
                    { k: 'say', text: noi('buuta_den') },
                    { k: 'go', to: 'mail', gait: 'walk' },
                    { k: 'face', rot: 0 },
                    { k: 'anim', a: 'give', d: 0.9 },
                    {
                        k: 'do',
                        fn: () => {
                            this.world.raiseFlag();
                            this.fx.sparkle(
                                new THREE.Vector3(-8.5, 1.6, 13.0),
                                6,
                            );
                        },
                    },
                    { k: 'item', item: null },
                    { k: 'anim', a: 'wave', d: 1.4 },
                    { k: 'home' },
                    this.release(P),
                );
            },
        };
    }

    // ------------------------------------------------------------------ đời sống lúc rảnh
    private stroll(a: Actor): Step[] {
        const spot = pick([
            'c1.0',
            'c1.2',
            'c2.1',
            'c2.3',
            'porch',
            'gp1',
            'flower',
            'lawnR1',
            'pondW',
            'lawnL1',
            'bench',
        ]);

        return [
            { k: 'say', text: this.line(a, 'dao_choi') },
            { k: 'go', to: spot },
            { k: 'face', rot: rand(-0.6, 0.6) },
            { k: 'anim', a: 'look', d: rand(3, 5) },
            { k: 'home' },
        ];
    }

    private coffee(a: Actor): Step[] {
        return [
            ...(a.home.seated
                ? ([
                      { k: 'stand' },
                      { k: 'go', to: BEHIND[a.key] ?? a.home.node },
                      { k: 'face', rot: 0 },
                  ] as Step[])
                : []),
            { k: 'item', item: 'mug' },
            { k: 'anim', a: 'drink', d: 1.8 },
            { k: 'say', text: this.line(a, 'ca_phe') },
            { k: 'anim', a: 'idle', d: 1.2 },
            { k: 'item', item: null },
            { k: 'home' },
        ];
    }

    private idleFor(a: Actor): Step[] | null {
        const fun = this.leisureFor(a);
        if (fun) {
            return fun;
        }
        const r = Math.random();
        if (r < 0.14 && a.key !== 'buuta') {
            return this.stroll(a);
        }
        if (r < 0.24 && a.key !== 'buuta' && a.key !== 'chuquay') {
            return Math.random() < 0.65 ? this.coffeeRun(a) : this.coffee(a);
        }
        if (r < 0.32) {
            return [{ k: 'anim', a: 'stretch', d: 1.6 }];
        }
        switch (a.key) {
            case 'bienkich':
                return pick([
                    [
                        { k: 'go', to: 'bienkich.win' },
                        { k: 'face', rot: Math.PI },
                        { k: 'anim', a: 'look', d: 4 },
                        { k: 'face', rot: 0 },
                        { k: 'say', text: this.line(a, 'idle') },
                        { k: 'wait', d: 1.5 },
                        { k: 'home' },
                    ],
                    [
                        { k: 'item', item: 'water' },
                        { k: 'go', to: 'bienkich.plant' },
                        { k: 'face', rot: -Math.PI / 2 - 0.4 },
                        { k: 'anim', a: 'water', d: 3 },
                        { k: 'item', item: null },
                        { k: 'say', text: 'Cây ơi, uống nước nè 🌱' },
                        { k: 'home' },
                    ],
                    [
                        { k: 'say', text: this.line(a, 'idle') },
                        { k: 'anim', a: 'write', d: 4 },
                    ],
                ] as Step[][]);
            case 'thuam':
                return pick([
                    [
                        { k: 'say', text: this.line(a, 'idle') },
                        { k: 'do', fn: () => this.notes(a, 4) },
                        { k: 'anim', a: 'smash', d: 2.6, expr: 'cocky' },
                    ],
                    [
                        { k: 'do', fn: () => this.notes(a, 5) },
                        { k: 'anim', a: 'cheer', d: 2.0 },
                    ],
                ] as Step[][]);
            case 'daodienA':
            case 'daodienB': {
                const other =
                    this.A[a.key === 'daodienA' ? 'daodienB' : 'daodienA'];
                if (
                    !other.inScene &&
                    !other.busy &&
                    other.base === 'idle' &&
                    Math.random() < 0.6
                ) {
                    this.enqueue(this.chatScene());

                    return null;
                }

                return [{ k: 'anim', a: 'type', d: 3 }];
            }
            case 'thodung':
                return pick([
                    [
                        { k: 'do', fn: () => a.spin(2.2) },
                        { k: 'wait', d: 2.3 },
                        { k: 'face', rot: 0 },
                        { k: 'say', text: this.line(a, 'idle') },
                    ],
                    [
                        { k: 'item', item: 'can' },
                        { k: 'anim', a: 'drink', d: 1.8 },
                        { k: 'item', item: null },
                        { k: 'say', text: this.line(a, 'idle') },
                    ],
                ] as Step[][]);
            case 'giamkhao':
                return pick([
                    [
                        { k: 'anim', a: 'adjust', d: 1.6 },
                        { k: 'say', text: this.line(a, 'idle') },
                    ],
                    [
                        { k: 'go', to: 'giamkhao.shelf' },
                        { k: 'face', rot: -Math.PI / 2 },
                        { k: 'anim', a: 'look', d: 3 },
                        { k: 'say', text: this.line(a, 'idle') },
                        { k: 'home' },
                    ],
                ] as Step[][]);
            case 'thukho':
                return pick([
                    [
                        { k: 'anim', a: 'polish', d: 3 },
                        { k: 'say', text: this.line(a, 'idle') },
                    ],
                    [
                        { k: 'go', to: 'thukho.shelf' },
                        { k: 'face', rot: Math.PI },
                        { k: 'anim', a: 'polish', d: 3.5 },
                        { k: 'say', text: this.line(a, 'idle') },
                        { k: 'home' },
                    ],
                ] as Step[][]);
            case 'chuquay':
                return pick([
                    [
                        { k: 'anim', a: 'wave', d: 1.8 },
                        { k: 'say', text: this.line(a, 'idle') },
                    ],
                    [
                        { k: 'go', to: 'chuquay.cart' },
                        { k: 'face', rot: Math.PI / 2 },
                        { k: 'anim', a: 'polish', d: 2.4 },
                        { k: 'say', text: this.line(a, 'idle') },
                        { k: 'home' },
                    ],
                ] as Step[][]);
            case 'buuta':
                return pick([
                    [
                        { k: 'go', to: 'bench' },
                        { k: 'face', rot: Math.PI / 2 + 0.5 },
                        { k: 'anim', a: 'look', d: 5 },
                        { k: 'say', text: this.line(a, 'idle') },
                        { k: 'home' },
                    ],
                    [
                        { k: 'go', to: 'mail' },
                        { k: 'face', rot: 0 },
                        { k: 'anim', a: 'polish', d: 2 },
                        { k: 'say', text: this.line(a, 'idle') },
                        { k: 'home' },
                    ],
                    [{ k: 'anim', a: 'wave', d: 1.6 }],
                ] as Step[][]);
            default:
                return null;
        }
    }

    // ------------------------------------------------------------------ giờ nghỉ: ăn, cà phê, chơi, ngủ trưa
    /** Đánh dấu một chuỗi việc là "đi chơi": có việc thật là bỏ ngay (và dọn đồ chơi đang bật). */
    fun(a: Actor, steps: Step[], cleanup?: () => void): Step[] {
        return [
            {
                k: 'do',
                fn: () => {
                    a.leisure = true;
                    if (cleanup) {
                        this.cleanups.set(a, cleanup);
                    }
                },
            },
            ...steps,
            {
                k: 'do',
                fn: () => {
                    a.leisure = false;
                    this.cleanups.get(a)?.();
                    this.cleanups.delete(a);
                },
            },
        ];
    }

    /** Đi tới một chỗ ngồi/nằm (sofa, ghế ăn, giường, võng). */
    seat(node: string, anim?: AnimName, d = 8): Step[] {
        const s = SEATS[node];
        const out: Step[] = [{ k: 'go', to: node }];
        if (s?.lie) {
            out.push({ k: 'lie', at: s.lie });
        } else {
            out.push(
                { k: 'face', rot: s?.rot ?? 0 },
                { k: 'sit', rot: s?.rot ?? 0, h: s?.h ?? 0.5 },
            );
        }
        if (anim) {
            out.push({ k: 'anim', a: anim, d });
        }

        return out;
    }

    relOf(a: Actor) {
        return this.rel.get(a.key) ?? 0;
    }

    relAdd(a: Actor, d: number) {
        this.rel.set(a.key, Math.max(-5, Math.min(5, this.relOf(a) + d)));
    }

    /** Đang diễn việc thật (giao giấy, chấm điểm…)? Khi đó sếp không chen ngang được. */
    onDuty(a: Actor) {
        return a.inScene && !a.leisure;
    }

    /** Kéo một người ra khỏi trò chơi đang dở để tương tác với sếp (việc thật thì không). */
    grab(a: Actor): boolean {
        if (this.onDuty(a)) {
            return false;
        }
        this.cleanups.get(a)?.();
        this.cleanups.delete(a);
        this.leaveLine(a);
        a.interrupt();
        a.inScene = true;
        a.leisure = true;

        return true;
    }

    /** Việc dọn dẹp khi `a` bị gọi đi làm giữa chừng (tắt TV, cất bóng…). */
    setCleanup(a: Actor, fn: () => void) {
        this.cleanups.set(a, fn);
    }

    /** Gọi cả nhà ăn cơm (sếp hô). */
    callMeal() {
        const cook = [this.A.chuquay, this.A.thukho, this.A.bienkich].find(
            (a) => this.freeIdle(a),
        );
        if (!cook) {
            return false;
        }
        this.enqueue(this.mealScene(cook));

        return true;
    }

    /** Ai rảnh (không có việc thật)? */
    get freeActors() {
        return Object.values(this.A).filter(
            (a) => a.base !== 'working' && !this.onDuty(a),
        );
    }

    /** Lưu trạng thái điều phối (khi rời trang). */
    snapshot() {
        const byKey = <T>(m: Map<Actor, T>) =>
            [...m.entries()].map(([a, v]) => [a.key, v] as [string, T]);

        return {
            rel: [...this.rel.entries()],
            workT: byKey(this.workT),
            greetCool: byKey(this.greetCool),
            pairCool: [...this.pairCool.entries()],
            goodAt: this.goodAt,
            badAt: this.badAt,
            sanpham: this.sanpham,
            mealKey: this.mealKey,
            kidCatAt: this.kidCatAt,
            catCool: this.catCool,
            planT: this.planT,
            owlChat: this.owlChat,
            tv: this.wings.state.tv,
        };
    }

    restore(s: Partial<ReturnType<Director['snapshot']>>) {
        const A = this.A;
        const toActor = <T>(arr: [string, T][] | undefined, m: Map<Actor, T>) =>
            (arr ?? []).forEach(([k, v]) => A[k] && m.set(A[k], v));
        this.rel = new Map(s.rel ?? []);
        toActor(s.workT, this.workT);
        toActor(s.greetCool, this.greetCool);
        this.pairCool = new Map(s.pairCool ?? []);
        this.goodAt = s.goodAt ?? this.goodAt;
        this.badAt = s.badAt ?? this.badAt;
        this.sanpham = s.sanpham ?? '';
        this.mealKey = s.mealKey ?? '';
        this.kidCatAt = s.kidCatAt ?? this.kidCatAt;
        this.catCool = s.catCool ?? this.catCool;
        this.planT = s.planT ?? this.planT;
        this.owlChat = s.owlChat ?? this.owlChat;
    }

    /** Quay lại trang sau ít phút: ai đang chơi/nghỉ dở thì làm nốt rồi mới về chỗ. */
    resume(a: Actor, snap: ReturnType<Actor['snapshot']>, tv: boolean) {
        if (snap.atHome || !this.motion) {
            return;
        }
        a.inScene = true;
        a.leisure = true;
        const steps: Step[] = [];
        if (snap.anim === 'game' && tv) {
            this.wings.state.tv = true;
            this.cleanups.set(a, () => (this.wings.state.tv = false));
        }
        if (snap.anim && snap.animLeft > 1.5) {
            steps.push({
                k: 'anim',
                a: snap.anim,
                d: Math.min(snap.animLeft, 25),
            });
        } else if (snap.seated || snap.lying) {
            steps.push({
                k: 'anim',
                a: snap.lying ? 'lie' : 'sitIdle',
                d: rand(3, 8),
            });
        } else {
            steps.push({ k: 'wait', d: rand(0.5, 2) });
        }
        steps.push({ k: 'stand' }, this.release(a));
        a.push(...steps);
    }

    /** Đang mệt? (làm liên tục khá lâu) */
    tired(a: Actor) {
        return (this.workT.get(a) ?? 0) > 360;
    }

    /** Một câu hợp ngữ cảnh cho `a` trong tình huống `situation`. */
    line(
        a: Actor,
        situation: string,
        extra: {
            with?: string | null;
            vars?: Record<string, string | number | null | undefined>;
        } = {},
    ) {
        const now = this.now();
        const mood =
            now - this.badAt < 150
                ? 'buon'
                : now - this.goodAt < 150
                  ? 'vui'
                  : null;

        const r = this.relOf(a);

        return lineFor(a.key, {
            situation,
            hour: this.hourNow,
            mood,
            rel: r >= 3 ? 'than' : r <= -3 ? 'gian' : null,
            tired: this.tired(a),
            with: extra.with ?? null,
            vars: {
                sanpham: this.sanpham || 'hàng mới',
                sep: this.player.ten,
                anh: this.player.anh,
                Anh: this.player.anh === 'chị' ? 'Chị' : 'Anh',
                ...extra.vars,
            },
        });
    }

    private get hourNow() {
        return this.hour();
    }

    private freeIdle(a: Actor) {
        return a.base === 'idle' && !a.inScene && !a.busy;
    }

    /** Các trò chơi/nghỉ ngơi một mình theo tính cách và giờ giấc. */
    /** Ngoài trời (vườn) — trời mưa thì không ra. */
    private outdoorNode(id: string) {
        const p = this.nav?.has(id) ? this.nav.pos(id) : null;

        return !!p && p.y < 0.2 && p.z > Z_FRONT + 0.2;
    }

    get raining() {
        return !!this.weather?.raining;
    }

    private leisureFor(a: Actor): Step[] | null {
        const steps = this.leisurePick(a);
        if (
            steps &&
            this.raining &&
            steps.some(
                (s) =>
                    (s.k === 'go' && this.outdoorNode(s.to)) ||
                    (s.k === 'goto' && s.p.z > Z_FRONT),
            )
        ) {
            return this.fun(a, [
                { k: 'face', rot: 0 },
                { k: 'say', text: noi('mua_ngam') },
                { k: 'anim', a: 'stretch', d: 2 },
                { k: 'anim', a: 'yawn', d: 1.6, expr: 'sleepy' },
            ]);
        }

        return steps;
    }

    /** Vài trò "như người thật" ai cũng có thể làm khi rảnh. */
    private everyday(a: Actor): Step[] | null {
        const r = Math.random();
        const garden = pick([
            'lawnL1',
            'lawnL2',
            'lawnL3',
            'lawnR1',
            'lawnR2',
            'lawnR3',
            'gp1',
            'gp2',
        ]);
        if (r < 0.22 && this.nav?.has(garden)) {
            // ra bãi cỏ lăn vài vòng rồi cười khoái chí
            return this.fun(a, [
                { k: 'go', to: garden },
                { k: 'say', text: noi('lan_co_mot_minh') },
                { k: 'anim', a: 'roll', d: 3.2, expr: 'joy' },
                { k: 'anim', a: 'getup', d: 0.9 },
                { k: 'anim', a: 'laugh', d: 1.8, expr: 'joy' },
                { k: 'anim', a: 'stretch', d: 1.4 },
            ]);
        }
        const pond = this.pond;
        const h = this.hourNow;
        if (r < 0.32 && pond && h >= 9 && h < 18 && pond.busy.size === 0) {
            // nóng quá nhảy ao cho mát
            const edge = pond.edgeFor(a.pos);
            return this.fun(a, [
                { k: 'goto', p: edge },
                { k: 'face', at: new THREE.Vector3(9.2, 0, 9.0) },
                { k: 'say', text: noi('nhay_ao') },
                { k: 'anim', a: 'jump', d: 0.9, expr: 'joy' },
                { k: 'do', fn: () => pond.plunge(a, { how: 'jump' }) },
                {
                    k: 'until',
                    fn: () => !a.driver && !pond.busy.has(a),
                    max: 16,
                },
                { k: 'anim', a: 'laugh', d: 1.6, expr: 'joy' },
            ]);
        }
        if (r < 0.5) {
            return this.fun(a, [
                { k: 'anim', a: 'stretch', d: 2.2 },
                { k: 'anim', a: 'yawn', d: 1.6, expr: 'sleepy' },
                { k: 'anim', a: 'jump', d: 1.8, expr: 'joy' },
            ]);
        }

        return null;
    }

    private leisurePick(a: Actor): Step[] | null {
        if (Math.random() < 0.3) {
            const e = this.everyday(a);
            if (e) {
                return e;
            }
        }
        const h = this.hourNow;
        const W = this.wings;
        const napTime = h >= 13 && h < 14.5;
        const sleepy =
            a.key === 'thodung' || a.key === 'thuam' || a.key === 'bienkich';
        if (napTime && sleepy && Math.random() < 0.6) {
            const spot =
                a.key === 'thodung'
                    ? 'nghi.bed'
                    : a.key === 'thuam'
                      ? 'nghi.bean0'
                      : 'nghi.bean1';
            const lie = !!SEATS[spot]?.lie;

            return this.fun(a, [
                { k: 'say', text: noi('ngu_trua') },
                ...this.seat(spot),
                { k: 'anim', a: lie ? 'lie' : 'sleep', d: 22, expr: 'sleepy' },
                { k: 'stand' },
                { k: 'anim', a: 'stretch', d: 1.4 },
            ]);
        }
        const r = Math.random();
        switch (a.key) {
            case 'thodung':
                if (r < 0.45) {
                    return this.fun(
                        a,
                        [
                            { k: 'say', text: noi('choi_game') },
                            ...this.seat('gt.so1'),
                            { k: 'do', fn: () => (W.state.tv = true) },
                            { k: 'anim', a: 'game', d: 14 },
                            { k: 'say', text: noi('choi_game') },
                            { k: 'anim', a: 'game', d: 8 },
                            { k: 'do', fn: () => (W.state.tv = false) },
                            { k: 'stand' },
                        ],
                        () => (W.state.tv = false),
                    );
                }
                break;
            case 'bienkich':
                if (r < 0.3) {
                    return this.fun(a, [
                        ...this.seat('gt.read'),
                        { k: 'say', text: noi('doc_sach') },
                        { k: 'anim', a: 'read', d: 16 },
                        { k: 'stand' },
                    ]);
                }
                if (r < 0.45) {
                    return this.fun(a, [
                        { k: 'item', item: 'water' },
                        { k: 'go', to: 'veg' },
                        { k: 'face', rot: Math.PI },
                        { k: 'anim', a: 'water', d: 4 },
                        { k: 'say', text: noi('tuoi_rau') },
                        { k: 'item', item: null },
                    ]);
                }
                break;
            case 'thukho':
                if (r < 0.4) {
                    return this.fun(a, [
                        { k: 'go', to: 'bep.sink' },
                        { k: 'face', rot: Math.PI },
                        { k: 'say', text: noi('don_bep') },
                        { k: 'anim', a: 'polish', d: 4 },
                        { k: 'go', to: 'bep.stove' },
                        { k: 'face', rot: Math.PI },
                        { k: 'anim', a: 'polish', d: 3 },
                    ]);
                }
                break;
            case 'buuta':
                if (r < 0.35) {
                    return this.fun(
                        a,
                        [
                            { k: 'go', to: 'hammock' },
                            {
                                k: 'do',
                                fn: () => (this.world.play.hammock = true),
                            },
                            ...this.seat('hammock'),
                            { k: 'say', text: noi('nam_vong') },
                            { k: 'anim', a: 'lie', d: 16, expr: 'sleepy' },
                            { k: 'stand' },
                            {
                                k: 'do',
                                fn: () => (this.world.play.hammock = false),
                            },
                        ],
                        () => (this.world.play.hammock = false),
                    );
                }
                break;
            case 'chuquay':
                if (r < 0.25) {
                    return this.fun(a, [
                        { k: 'item', item: 'water' },
                        { k: 'go', to: 'veg' },
                        { k: 'face', rot: Math.PI },
                        { k: 'anim', a: 'water', d: 4 },
                        { k: 'say', text: noi('tuoi_rau') },
                        { k: 'item', item: null },
                    ]);
                }
                break;
            case 'thuam':
                if (r < 0.25 && !this.world.play.hammock) {
                    return this.fun(
                        a,
                        [
                            { k: 'go', to: 'hammock' },
                            {
                                k: 'do',
                                fn: () => (this.world.play.hammock = true),
                            },
                            ...this.seat('hammock'),
                            { k: 'say', text: noi('nam_vong') },
                            { k: 'anim', a: 'lie', d: 14, expr: 'sleepy' },
                            { k: 'stand' },
                            {
                                k: 'do',
                                fn: () => (this.world.play.hammock = false),
                            },
                        ],
                        () => (this.world.play.hammock = false),
                    );
                }
                break;
        }

        return null;
    }

    /** Ra quầy pha chế xếp hàng lấy cà phê, rồi bưng ly về chỗ uống. */
    private coffeeRun(a: Actor): Step[] {
        if (this.coffeeLine.includes(a) || this.coffeeLine.length >= 4) {
            return [
                { k: 'item', item: 'mug' },
                { k: 'anim', a: 'drink', d: 1.6 },
                { k: 'item', item: null },
            ];
        }
        const idx = this.coffeeLine.length;
        this.coffeeLine.push(a);
        const steps: Step[] = [
            { k: 'go', to: `phache.q${idx}` },
            { k: 'face', rot: Math.PI },
        ];
        if (idx > 0) {
            steps.push({ k: 'say', text: noi('xep_hang_ca_phe') });
        }
        for (let i = idx; i > 0; i--) {
            steps.push(
                {
                    k: 'until',
                    fn: () => this.coffeeLine.indexOf(a) < i,
                    max: 25,
                },
                { k: 'go', to: `phache.q${i - 1}` },
                { k: 'face', rot: Math.PI },
            );
        }
        steps.push(
            { k: 'do', fn: () => (this.wings.state.coffee = this.now()) },
            { k: 'anim', a: 'idle', d: 2.4 },
            { k: 'item', item: 'mug' },
            { k: 'do', fn: () => this.leaveLine(a) },
            { k: 'say', text: this.line(a, 'ca_phe') },
            { k: 'home', gait: 'walk' },
            { k: 'anim', a: 'drink', d: 1.8 },
            { k: 'item', item: null },
        );

        return this.fun(a, steps, () => this.leaveLine(a));
    }

    private leaveLine(a: Actor) {
        const i = this.coffeeLine.indexOf(a);
        if (i >= 0) {
            this.coffeeLine.splice(i, 1);
        }
    }

    /** Hai đạo diễn ra quầy, ngồi ghế cao cãi nhau chuyện cà phê. */
    private coffeeArgue(): Scene {
        const DA = this.A.daodienA;
        const DB = this.A.daodienB;
        const st = { a: false, b: false };
        const lines = (
            who: Actor,
            other: Actor,
            mine: 'a' | 'b',
            node: string,
            first: boolean,
        ): Step[] => [
            ...this.seat(node),
            { k: 'item', item: 'mug' },
            { k: 'do', fn: () => (st[mine] = true) },
            { k: 'until', fn: () => st.a && st.b, max: 15 },
            { k: 'do', fn: () => (this.wings.state.coffee = this.now()) },
            ...(first ? [] : ([{ k: 'wait', d: 1.6 }] as Step[])),
            { k: 'face', at: () => other.pos },
            {
                k: 'say',
                text: noi(first ? 'ca_phe_cai_a' : 'ca_phe_cai_b'),
                prio: first ? 'chat' : 'reply',
            },
            { k: 'anim', a: 'drink', d: 1.6 },
            { k: 'wait', d: first ? 1.8 : 0.4 },
            {
                k: 'say',
                text: noi(first ? 'ca_phe_cai_a' : 'ca_phe_hoa'),
                prio: 'reply',
            },
            { k: 'anim', a: 'drink', d: 1.8 },
            { k: 'item', item: null },
            { k: 'stand' },
            { k: 'home' },
            this.release(who),
        ];

        return {
            label: 'coffee-argue',
            leisure: true,
            need: [DA, DB],
            start: () => {
                DA.push(...lines(DA, DB, 'a', 'phache.st0', true));
                DB.push(...lines(DB, DA, 'b', 'phache.st1', false));
            },
        };
    }

    /** Hai người chơi bi lắc (trong nhà) hoặc bóng bàn (ngoài vườn). */
    private gameScene(
        x: Actor,
        y: Actor,
        kind: 'foosball' | 'pingpong',
    ): Scene {
        const st = { a: false, b: false };
        const [n0, n1] =
            kind === 'foosball' ? ['gt.fb0', 'gt.fb1'] : ['pp0', 'pp1'];
        const setOn = (on: boolean) => {
            if (kind === 'foosball') {
                this.wings.state.foosball = on;
            } else {
                this.world.play.pingpong = on;
            }
        };
        const side = (
            who: Actor,
            other: Actor,
            mine: 'a' | 'b',
            node: string,
            rot: number,
        ): Step[] => [
            { k: 'do', fn: () => this.cleanups.set(who, () => setOn(false)) },
            { k: 'go', to: node },
            { k: 'face', rot },
            { k: 'do', fn: () => (st[mine] = true) },
            { k: 'until', fn: () => st.a && st.b, max: 20 },
            { k: 'do', fn: () => setOn(true) },
            {
                k: 'say',
                text: noi(kind === 'foosball' ? 'bi_lac' : 'bong_ban'),
            },
            { k: 'anim', a: 'swing', d: 7 },
            {
                k: 'say',
                text: noi(kind === 'foosball' ? 'bi_lac' : 'bong_ban'),
            },
            { k: 'anim', a: 'swing', d: 6 },
            { k: 'do', fn: () => setOn(false) },
            { k: 'face', at: () => other.pos },
            { k: 'anim', a: mine === 'a' ? 'cheer' : 'idle', d: 1.4 },
            { k: 'home' },
            this.release(who),
        ];

        return {
            label: kind,
            leisure: true,
            need: [x, y],
            start: () => {
                x.push(...side(x, y, 'a', n0, Math.PI / 2));
                y.push(...side(y, x, 'b', n1, -Math.PI / 2));
            },
        };
    }

    /** Giờ cơm (trưa 11:30–13:00, tối 18:00–19:30 theo đồng hồ thật): một người nấu, cả nhà ngồi ăn chung. */
    private mealScene(cook: Actor): Scene {
        const W = this.wings.state;
        const flag = { ready: false };

        return {
            label: 'meal',
            leisure: true,
            need: [cook],
            start: () => {
                const eaters = WORKERS.map((k) => this.A[k]).filter(
                    (a) => a !== cook && a.base === 'idle' && !a.inScene,
                );
                eaters.push(this.A.chuquay);
                const uniq = [...new Set(eaters)]
                    .filter(
                        (a) => a !== cook && a.base === 'idle' && !a.inScene,
                    )
                    .slice(0, 5);
                cook.push(
                    { k: 'say', text: noi('nau_an') },
                    { k: 'go', to: 'bep.stove' },
                    { k: 'face', rot: Math.PI },
                    { k: 'do', fn: () => (W.cooking = true) },
                    { k: 'anim', a: 'cook', d: 6 },
                    { k: 'say', text: noi('nau_an') },
                    { k: 'anim', a: 'cook', d: 6 },
                    {
                        k: 'do',
                        fn: () => (
                            (W.cooking = false),
                            (W.eating = true),
                            (flag.ready = true)
                        ),
                    },
                    { k: 'say', text: noi('goi_an') },
                    ...this.seat('bep.s5', 'eat', 12),
                    { k: 'say', text: noi('an') },
                    { k: 'anim', a: 'eat', d: 6 },
                    { k: 'do', fn: () => (W.eating = false) },
                    { k: 'stand' },
                    { k: 'home' },
                    this.release(cook),
                );
                this.cleanups.set(
                    cook,
                    () => ((W.cooking = false), (W.eating = false)),
                );
                uniq.forEach((a, i) => {
                    a.interrupt();
                    a.inScene = true;
                    a.leisure = true;
                    a.push(
                        // tới bàn trước, đứng chờ cơm chín rồi mới ngồi ăn
                        { k: 'wait', d: i * 0.6 },
                        { k: 'go', to: `bep.s${i}` },
                        { k: 'face', at: () => this.wings.panPos },
                        { k: 'until', fn: () => flag.ready, max: 30 },
                        ...this.seat(`bep.s${i}`, 'eat', 9 + i),
                        { k: 'say', text: noi('an') },
                        { k: 'anim', a: 'eat', d: 6 },
                        { k: 'stand' },
                        { k: 'home' },
                        this.release(a),
                    );
                });
                if (this.motion) {
                    window.setTimeout(() => {
                        this.cat.visit('bep.meo', 22);
                        this.later(5, () =>
                            this.cat.say('Meo? (xin cá) 🐟', 3),
                        );
                    }, 9000);
                }
            },
        };
    }

    /** Bắt đầu mưa: ai đang ở ngoài vườn (đang chơi/rảnh) thì che đầu chạy vào nhà; mèo cũng chạy. */
    onRain(start: boolean) {
        if (!start) {
            const a = pick(Object.values(this.A));
            if (a && !this.onDuty(a)) {
                a.say(noi('het_mua'), 2.6, 'chat');
            }

            return;
        }
        let spoke = 0;
        for (const a of Object.values(this.A)) {
            const out = a.pos.y < 0.2 && a.pos.z > Z_ROOM + 0.3;
            if (!out || a.driver) {
                continue;
            }
            if (this.onDuty(a)) {
                continue; // đang giao hàng/việc thật: cầm ô đi tiếp
            }
            this.cleanups.get(a)?.();
            this.cleanups.delete(a);
            this.leaveLine(a);
            a.interrupt();
            a.inScene = false;
            a.leisure = false;
            a.push(
                ...(spoke++ < 2
                    ? ([
                          { k: 'say', text: noi('mua_chay'), prio: 'reply' },
                      ] as Step[])
                    : []),
                { k: 'stand' },
                { k: 'home', gait: 'cover' },
            );
        }
        if (this.cat.pos.z > Z_ROOM + 0.3) {
            this.cat.visit('sanh.mid', 30);
            this.cat.say(
                lineFor('meo', { situation: 'meo_mua', hour: this.hourNow }),
                2.6,
                'reply',
            );
        }
    }

    later(d: number, fn: () => void) {
        this.timers.push({ at: this.now() + d, fn });
    }

    /** Thỉnh thoảng (khi rảnh) nghĩ ra trò chơi cho cả nhóm, và lo bữa cơm đúng giờ. */
    private planLeisure(dt: number) {
        this.planT -= dt;
        if (
            this.planT > 0 ||
            !this.motion ||
            !this.data ||
            this.data.mode === 'down'
        ) {
            return;
        }
        this.planT = 9;
        const h = this.hourNow;
        const meal =
            h >= 11.5 && h < 13 ? 'trua' : h >= 18 && h < 19.5 ? 'toi' : null;
        const day = new Date().toDateString();
        if (meal && this.mealKey !== `${day}|${meal}`) {
            const cook = [this.A.chuquay, this.A.thukho, this.A.bienkich].find(
                (a) => this.freeIdle(a),
            );
            if (cook) {
                this.mealKey = `${day}|${meal}`;
                this.enqueue(this.mealScene(cook));

                return;
            }
        }
        if (this.queue.length) {
            return;
        }
        const r = Math.random();
        if (r < 0.12) {
            const pool = ['thodung', 'thuam', 'chuquay', 'buuta', 'bienkich']
                .map((k) => this.A[k])
                .filter((a) => this.freeIdle(a));
            if (pool.length >= 2) {
                const [x, y] = pool.sort(() => Math.random() - 0.5);
                this.enqueue(
                    this.gameScene(
                        x,
                        y,
                        Math.random() < 0.5 ? 'foosball' : 'pingpong',
                    ),
                );
            }
        } else if (
            r < 0.2 &&
            this.freeIdle(this.A.daodienA) &&
            this.freeIdle(this.A.daodienB)
        ) {
            this.enqueue(this.coffeeArgue());
        }
    }

    /** (Gỡ lỗi / xem thử) bày ngay một trò: meal, foosball, pingpong, argue, queue, game, read, nap, hammock, bump. */
    debugPlay(kind: string, whoKey?: string) {
        const A = this.A;
        if (kind === 'tv' && whoKey && A[whoKey]) {
            const who = A[whoKey];
            who.interrupt();
            who.push(
                ...this.fun(
                    who,
                    [
                        ...this.seat('gt.so1'),
                        { k: 'do', fn: () => (this.wings.state.tv = true) },
                        { k: 'anim', a: 'game', d: 60 },
                    ],
                    () => (this.wings.state.tv = false),
                ),
            );

            return;
        }
        switch (kind) {
            case 'meal':
                this.enqueue(this.mealScene(A.chuquay));
                break;
            case 'foosball':
            case 'pingpong':
                this.enqueue(this.gameScene(A.thuam, A.chuquay, kind));
                break;
            case 'argue':
                this.enqueue(this.coffeeArgue());
                break;
            case 'queue':
                for (const k of ['bienkich', 'thodung', 'giamkhao']) {
                    A[k].interrupt();
                    A[k].push(...this.coffeeRun(A[k]));
                }
                break;
            case 'bump':
                A.thuam.interrupt();
                A.thukho.interrupt();
                A.thuam.push(
                    { k: 'go', to: 'c1.0', gait: 'run' },
                    { k: 'go', to: 'c1.3', gait: 'run' },
                );
                A.thukho.push({ k: 'go', to: 'c1.3' }, { k: 'go', to: 'c1.0' });
                break;
            default: {
                const who =
                    kind === 'game'
                        ? A.thodung
                        : kind === 'read'
                          ? A.bienkich
                          : kind === 'hammock'
                            ? A.buuta
                            : A.thodung;
                for (let i = 0; i < 20; i++) {
                    const steps = kind === 'nap' ? null : this.leisureFor(who);
                    if (steps) {
                        who.interrupt();
                        who.push(...steps);
                        break;
                    }
                }
                if (kind === 'nap') {
                    who.interrupt();
                    who.push(
                        ...this.fun(who, [
                            { k: 'say', text: noi('ngu_trua') },
                            ...this.seat('nghi.bed'),
                            { k: 'anim', a: 'lie', d: 22, expr: 'sleepy' },
                            { k: 'stand' },
                        ]),
                    );
                }
            }
        }
    }

    // ------------------------------------------------------------------ va nhau trên đường
    bump(a: Actor, b: Actor) {
        if (!this.motion) {
            return;
        }
        // mỗi cặp chỉ cãi nhau một lần mỗi phút
        const pair = [a.key, b.key].sort().join('|');
        const now = this.now();
        if ((this.pairCool.get(pair) ?? -99) > now) {
            return;
        }
        this.pairCool.set(pair, now + rand(55, 75));
        if (a === this.kid || b === this.kid) {
            const o = a === this.kid ? b : a;
            o.react(null, this.kid!.pos, 1.6, 'surprise');
            this.later(rand(0.3, 0.8), () =>
                o.say(this.line(o, 'bi_sep_dung'), undefined, 'greet'),
            );

            return;
        }
        const ka = ROLE[a.key] ?? a.key;
        const kb = ROLE[b.key] ?? b.key;
        const ea: Expr =
            ka === 'giamkhao'
                ? 'annoyed'
                : ka === 'bienkich'
                  ? 'sad'
                  : ka === 'thuam'
                    ? 'cocky'
                    : 'surprise';
        const eb: Expr =
            kb === 'giamkhao'
                ? 'annoyed'
                : kb === 'bienkich'
                  ? 'sad'
                  : kb === 'thuam'
                    ? 'cocky'
                    : kb === 'thodung'
                      ? 'focus'
                      : 'annoyed';
        // người đụng mở lời; nếu lúc này không nói được (vừa nói xong) thì chỉ khựng lại nhìn nhau
        const opened = a.say(
            this.line(a, 'dung', { with: kb }),
            undefined,
            'greet',
        );
        a.react(null, b.pos, 1.5, ea);
        // Thợ dựng mải chơi: không thèm ngẩng lên
        b.react(null, kb === 'thodung' ? null : a.pos, 2.2, eb);
        if (!opened) {
            return;
        }
        this.later(rand(0.9, 1.8), () => {
            if (
                b.say(
                    this.line(b, 'bi_dung', { with: ka }),
                    undefined,
                    'reply',
                ) &&
                Math.random() < 0.4
            ) {
                // thỉnh thoảng người kia vặn lại một câu rồi thôi
                this.later(rand(1.4, 2.4), () =>
                    a.say(noi('bump_xong'), undefined, 'reply'),
                );
            }
        });
    }

    /** Ai đi ngang qua sếp thì chào theo tính cách; mèo chạy lại làm nũng. */
    private noticeKid(dt: number) {
        const k = this.kid;
        if (!k || !this.motion) {
            return;
        }
        const now = this.now();
        for (const a of Object.values(this.A)) {
            if (a.lying || a.base === 'sleep') {
                continue;
            }
            const d = Math.hypot(a.pos.x - k.pos.x, a.pos.z - k.pos.z);
            if (d > 2.3 || Math.abs(a.pos.y - k.pos.y) > 1) {
                continue;
            }
            if ((this.greetCool.get(a) ?? -99) > now) {
                continue;
            }
            const busy = a.base === 'working' && a.atHome;
            const r = this.relOf(a);
            if (r <= -3) {
                // còn giận sếp: lảng đi, lẩm bẩm
                if (
                    (this.avoidCool.get(a) ?? -99) < now &&
                    a.say(this.line(a, 'ne_sep'), undefined, 'greet')
                ) {
                    this.avoidCool.set(a, now + rand(25, 40));
                    this.greetCool.set(a, now + rand(30, 50));
                    a.setExpr('annoyed', 2.5);
                    if (!busy && !a.seated && !a.lying && !this.onDuty(a)) {
                        a.shove(
                            new THREE.Vector3(
                                a.pos.x - k.pos.x,
                                0,
                                a.pos.z - k.pos.z,
                            ),
                            1.1,
                            0.9,
                            'walk',
                        );
                    }
                }
                continue;
            }
            if (a.say(this.line(a, 'chao_sep'), undefined, 'greet')) {
                if (r >= 3) {
                    this.fx.hearts(
                        a
                            .anchor(new THREE.Vector3())
                            .add(new THREE.Vector3(0, -0.3, 0)),
                        2,
                    );
                }
                this.greetCool.set(a, now + rand(70, 120));
                if (!busy && a.key !== 'thodung') {
                    a.react(null, k.pos, 1.4, 'joy');
                    if (!a.busy && !a.seated) {
                        a.push({ k: 'anim', a: 'wave', d: 1.4 });
                    }
                }
            }
        }
        // mèo thấy sếp là chạy lại
        this.kidCatAt -= dt;
        if (this.kidCatAt <= 0) {
            this.kidCatAt = rand(70, 120);
            if (
                Math.hypot(this.cat.pos.x - k.pos.x, this.cat.pos.z - k.pos.z) >
                1.5
            ) {
                this.cat.seekNow(k);
                this.later(1.5, () =>
                    this.cat.say(
                        lineFor('meo', {
                            situation: 'chao_sep',
                            hour: this.hourNow,
                        }),
                        3,
                    ),
                );
            }
        }
    }

    private catBump() {
        const now = this.now();
        if (now < this.catCool || !this.motion) {
            return;
        }
        for (const a of Object.values(this.A)) {
            if (!a.moving || a.lying) {
                continue;
            }
            const d = Math.hypot(
                a.pos.x - this.cat.pos.x,
                a.pos.z - this.cat.pos.z,
            );
            if (d < 0.5 && Math.abs(a.pos.y - this.cat.pos.y) < 0.6) {
                this.catCool = now + 30;
                this.cat.say(noi('meo_xi'), 2);
                a.react('Ối, xin lỗi mèo!', this.cat.pos, 1.3, 'surprise');
                this.later(2.4, () => {
                    this.cat.say(noi('meo_tha'), 2.4);
                    this.fx.hearts(this.cat.anchor(new THREE.Vector3()), 3);
                });

                return;
            }
        }
    }

    private notes(a: Actor, n: number) {
        for (let i = 0; i < n; i++) {
            window.setTimeout(
                () =>
                    this.fx.notes(
                        a
                            .anchor(new THREE.Vector3())
                            .add(new THREE.Vector3(rand(-0.3, 0.3), -0.5, 0.2)),
                    ),
                i * 380,
            );
        }
    }

    private chatScene(): Scene {
        const DA = this.A.daodienA;
        const DB = this.A.daodienB;
        const st = { a: false, b: false };

        return {
            label: 'chat',
            need: [DA, DB],
            start: () => {
                DA.push(
                    { k: 'go', to: 'daodien.hfA' },
                    { k: 'face', at: () => DB.pos },
                    { k: 'do', fn: () => (st.a = true) },
                    { k: 'until', fn: () => st.b, max: 10 },
                    { k: 'say', text: noi('daodien_chat') },
                    { k: 'anim', a: 'chat', d: 2.6 },
                    { k: 'wait', d: 2.2 },
                    { k: 'say', text: noi('daodien_hoa') },
                    { k: 'anim', a: 'highfive', d: 1.0 },
                    { k: 'home' },
                    this.release(DA),
                );
                DB.push(
                    { k: 'go', to: 'daodien.hfB' },
                    { k: 'face', at: () => DA.pos },
                    { k: 'do', fn: () => (st.b = true) },
                    { k: 'until', fn: () => st.a, max: 10 },
                    { k: 'wait', d: rand(1.2, 2.2) },
                    { k: 'say', text: noi('daodien_chat'), prio: 'reply' },
                    { k: 'anim', a: 'argue', d: 2.2 },
                    { k: 'anim', a: 'highfive', d: 1.0 },
                    { k: 'home' },
                    this.release(DB),
                );
            },
        };
    }
}

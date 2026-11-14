// Một nhân vật sống trong nhà: hàng đợi hành động (đi, ngồi, nói, cầm đồ, diễn), tự tìm đường, né nhau, chớp mắt.
import * as THREE from 'three';

import {
    type AnimName,
    applyPose,
    Chibi,
    type ChibiSpec,
    type Expr,
    type Pose,
    poseFor,
    restPose,
} from './chibi';
import type { Effects } from './effects';
import { F1, type Home, stairY } from './layout';
import type { NavGraph } from './nav';
import { AGENT_R, groundY, levelOf, type NavGrid, PAIR_D } from './navgrid';
import { type Prio, Speech } from './speech';
import {
    C,
    CanvasTex,
    clamp,
    damp,
    dampAngle,
    FONT,
    Kit,
    pick,
    rand,
    roundRect,
    Shapes,
} from './util';

export type Gait = 'walk' | 'run' | 'stomp' | 'sprint' | 'cover';
export type ItemKind =
    | 'paper'
    | 'reel'
    | 'board'
    | 'letter'
    | 'paddle'
    | 'can'
    | 'mug'
    | 'water'
    | 'umbrella';

export type Step =
    | { k: 'go'; to: string; gait?: Gait }
    /** Đi tới một điểm bất kỳ (theo lưới va chạm). */
    | { k: 'goto'; p: THREE.Vector3; gait?: Gait }
    | { k: 'home'; gait?: Gait }
    | { k: 'sit'; rot?: number; h?: number }
    | { k: 'lie'; at: { x: number; y: number; z: number; rot: number } }
    | { k: 'stand' }
    | { k: 'anim'; a: AnimName; d: number; expr?: Expr }
    | { k: 'say'; text: string; d?: number; prio?: Prio }
    | { k: 'item'; item: ItemKind | null; arg?: number | string }
    | { k: 'face'; rot?: number; at?: THREE.Vector3 | (() => THREE.Vector3) }
    | { k: 'wait'; d: number }
    | { k: 'do'; fn: () => void }
    | { k: 'expr'; e: Expr; d: number }
    | { k: 'until'; fn: () => boolean; max: number };

export type VaiState = 'working' | 'idle' | 'sleep';

/** Thứ có bong bóng/nhãn trên đầu (nhân vật, cú, mèo). */
export interface Talker {
    key: string;
    anchor(out: THREE.Vector3): THREE.Vector3;
    bubble(): string | null;
    /** Số giây bong bóng còn hiện (để mờ dần). */
    bubbleLeft?(): number;
    alertUntil: number;
    /** Đang được "Gọi về gấp": dấu "!" hiện màu vàng. */
    callAlert?: boolean;
    root: THREE.Object3D;
}

export interface ActorCtx {
    nav: NavGraph;
    fx: Effects;
    kit: Kit;
    shapes: Shapes;
    actors: Actor[];
    now: () => number;
    motion: boolean;
    /** Hai người va nhau trên đường (để đạo diễn cho họ cãi nhau vui vẻ). */
    onBump?: (a: Actor, b: Actor) => void;
    /** Giữ một điểm trong vùng đi được (không lọt vào tường) — dùng khi bị đá văng/đẩy. */
    clampPos?: (p: THREE.Vector3) => void;
    /** Điều phối lời nói (chống nói dồn dập). */
    speech?: Speech;
    /** Lưới va chạm (có sau vài khung hình đầu). */
    grid?: NavGrid;
    /** Đang mưa: ai đi ngoài trời thì chạy che đầu. */
    raining?: () => boolean;
}

/** Nhân vật to hơn so với phòng (so với khung xương gốc). */
export const ACTOR_SCALE = 1.32;

const SPEED: Record<Gait, number> = {
    walk: 1.6,
    run: 3.4,
    stomp: 1.9,
    sprint: 5.3,
    cover: 3.6,
};
const _umb = new WeakMap<Kit, THREE.BufferGeometry>();
/** Tán ô (dùng chung). */
const umbrellaGeo = (kit: Kit) => {
    let g = _umb.get(kit);
    if (!g) {
        g = kit.geo(
            new THREE.SphereGeometry(
                0.62,
                16,
                6,
                0,
                Math.PI * 2,
                0,
                Math.PI / 2.4,
            ),
        );
        _umb.set(kit, g);
    }

    return g;
};
const _v = new THREE.Vector3();
const _w = new THREE.Vector3();

export class Actor implements Talker {
    root: THREE.Group;
    ch: Chibi;
    readonly pos = new THREE.Vector3();
    rot = 0;
    targetRot = 0;
    nodeId: string;
    seated = false;
    base: VaiState = 'idle';
    bubbleText: string | null = null;
    inScene = false;
    /** Đang chơi/nghỉ (có việc thì bỏ ngay). */
    leisure = false;
    /** Đang nằm (giường, võng). */
    lying: { x: number; y: number; z: number; rot: number } | null = null;
    /** Độ cao hông khi ngồi (m, theo thế giới). */
    seatH = 0.5;
    private pauseUntil = 0;
    private lookAt: THREE.Vector3 | null = null;
    private bumpCool = 0;
    alertUntil = 0;
    idleTimer = rand(6, 16);
    onIdle: ((a: Actor) => Step[] | null) | null = null;
    private queue: Step[] = [];
    private step: Step | null = null;
    private stepT = 0;
    private path: THREE.Vector3[] = [];
    private pathIds: (string | null)[] = [];
    /** Đoạn đi "xuyên" (cầu thang, bước vào ghế/giường, thoát kẹt) — không xét va chạm. */
    private pathGhost: boolean[] = [];
    /** Đang ở đoạn đi xuyên / được điều khiển riêng — bỏ qua khi soát va chạm. */
    ghost = false;
    /** Đứng đúng chỗ đã định (bàn làm việc, cạnh kệ…) dù sát đồ đạc. */
    parked = false;
    /** Vận tốc thực (m/s) — để người khác né. */
    readonly vel = new THREE.Vector3();
    private lastPos = new THREE.Vector3();
    private animStart = 0;
    private animChain: [AnimName, number][] = [];
    private repathAt = 0;
    private escapeUntil = 0;
    /** Số lần phải "xuyên" để thoát kẹt (báo cáo). */
    escapes = 0;
    private dustAt = 0;
    private tripCool = 0;
    /** Điều khiển riêng từng khung hình (rơi xuống ao, bơi…); trả false khi xong. */
    driver: ((dt: number) => boolean) | null = null;
    private pathI = 0;
    private segFrom = new THREE.Vector3();
    private gait: Gait = 'walk';
    private anim: AnimName = 'idle';
    private animUntil = 0;
    private sayText: string | null = null;
    private sayUntil = 0;
    private sayStart = 0;
    private exprOverride: Expr | null = null;
    private exprUntil = 0;
    private blinkAt = rand(1, 4);
    private blinkEnd = 0;
    private zzzAt = 0;
    private blocked = 0;
    private t = rand(0, 10);
    private cur: Pose = restPose();
    private tgt: Pose = restPose();
    private item: THREE.Object3D | null = null;
    private itemTex: CanvasTex | null = null;
    private visualY = 0;
    private shadow: THREE.Mesh;

    constructor(
        readonly key: string,
        spec: ChibiSpec,
        readonly home: Home,
        private ctx: ActorCtx,
        shadowMat: THREE.Material,
        public baseExpr: { work: Expr; idle: Expr } = {
            work: 'focus',
            idle: 'happy',
        },
    ) {
        this.ch = new Chibi(ctx.kit, ctx.shapes, spec, ACTOR_SCALE);
        this.root = this.ch.root;
        this.root.rotation.order = 'YXZ';
        this.root.userData.pick = {
            kind: 'role',
            key: key.startsWith('daodien') ? 'daodien' : key,
        };
        this.ch.meshes.forEach(
            (m) => (m.userData.pick = this.root.userData.pick),
        );
        this.nodeId = home.node;
        this.pos.copy(ctx.nav.pos(home.node));
        this.visualY = this.pos.y;
        this.rot = this.targetRot = home.rot;
        this.seated = home.seated;
        this.shadow = new THREE.Mesh(
            ctx.shapes.plane(0.85 * ACTOR_SCALE, 0.85 * ACTOR_SCALE),
            shadowMat,
        );
        this.shadow.rotation.x = -Math.PI / 2;
        this.shadow.renderOrder = 1;
        this.shadow.raycast = () => undefined;
    }

    get shadowMesh() {
        return this.shadow;
    }

    get busy() {
        return this.step !== null || this.queue.length > 0;
    }

    get atHome() {
        return (
            this.nodeId === this.home.node &&
            this.path.length === 0 &&
            this.seated === this.home.seated
        );
    }

    get moving() {
        return (
            this.step?.k === 'go' ||
            this.step?.k === 'home' ||
            this.step?.k === 'goto'
        );
    }

    /** Không xét va chạm lúc này (ngồi/nằm/đi xuyên/điều khiển riêng/đứng đúng chỗ đã định). */
    get passThrough() {
        return (
            this.ghost ||
            this.seated ||
            !!this.lying ||
            !!this.driver ||
            this.shoving ||
            this.parked
        );
    }

    /** Chuỗi động tác nối nhau (vấp → nằm sấp → đứng dậy…). */
    chain(list: [AnimName, number][], expr?: Expr) {
        this.animChain = list.slice(1);
        this.act(list[0][0], list[0][1], expr);
    }

    /** Thêm hành động vào cuối hàng. */
    push(...steps: Step[]) {
        this.queue.push(...steps);
    }

    /** Bỏ hết việc đang làm (dừng tại chỗ). */
    interrupt() {
        const next = this.moving
            ? this.pathIds.slice(this.pathI).find((x) => x)
            : null;
        if (next) {
            this.queue = [{ k: 'go', to: next }];
        } else {
            this.queue = [];
        }
        this.step = null;
        this.path = [];
        this.pathIds = [];
        this.pathGhost = [];
        this.animChain = [];
        this.animUntil = 0;
        this.pauseUntil = 0;
        this.setItem(null);
    }

    /** Khựng lại vài giây (va phải ai đó), quay nhìn và nói. */
    react(
        text: string | null,
        look: THREE.Vector3 | null,
        d = 1.6,
        expr?: Expr,
    ) {
        const now = this.ctx.now();
        this.pauseUntil = now + d;
        this.lookAt = look ? look.clone() : null;
        if (text) {
            this.say(text, Math.max(d + 0.8, 2.6));
        }
        if (expr) {
            this.setExpr(expr, d + 0.6);
        }
    }

    /** Nói một câu (qua người điều phối: có thể bị bỏ nếu vừa nói hoặc cả xưởng đang ồn). */
    /** Đang được gọi: chỉ nói đúng câu báo cáo này (không để câu chào ngẫu nhiên đè lên). */
    callText: string | null = null;
    callAlert = false;

    say(text: string, d?: number, prio?: Prio): boolean {
        if (!text) {
            return false;
        }
        if (this.callText !== null) {
            if (text !== this.callText) {
                return false;
            }
            this.sayText = text;
            this.sayStart = this.ctx.now();
            this.sayUntil = this.sayStart + clamp(d ?? 5, 3, 6);

            return true;
        }
        const p = prio ?? (this.inScene && !this.leisure ? 'work' : 'chat');
        if (this.ctx.speech && !this.ctx.speech.allow(this.key, text, p)) {
            return false;
        }
        this.sayText = text;
        this.sayStart = this.ctx.now();
        this.sayUntil = this.sayStart + clamp(d ?? Speech.dur(text), 3, 5);

        return true;
    }

    /** Còn bao lâu bong bóng tắt (để lớp chữ mờ dần). */
    bubbleLeft(): number {
        return this.sayText ? this.sayUntil - this.ctx.now() : 99;
    }

    /** Điều khiển tay (nhân vật của chủ xưởng): tốc độ hiện tại + hướng nhìn. */
    manual: { speed: number; heading: number } | null = null;

    /** Dựng lại hình nhân vật theo ngoại hình mới (không tải lại trang); giải phóng hình cũ. */
    rebuild(spec: ChibiSpec, expr?: { work: Expr; idle: Expr }) {
        const old = this.ch;
        const parent = old.root.parent;
        this.setItem(null);
        const extras = old.root.children.filter((c) => c !== old.body);
        const ch = new Chibi(this.ctx.kit, this.ctx.shapes, spec, ACTOR_SCALE);
        ch.root.rotation.order = 'YXZ';
        ch.root.position.copy(old.root.position);
        ch.root.rotation.copy(old.root.rotation);
        extras.forEach((e) => ch.root.add(e));
        const pick = old.root.userData.pick;
        ch.root.userData.pick = pick;
        if (pick) {
            ch.meshes.forEach((m) => (m.userData.pick = pick));
        }
        old.dispose();
        parent?.add(ch.root);
        this.ch = ch;
        this.root = ch.root;
        if (expr) {
            this.baseExpr = expr;
        }
    }

    /** Diễn ngay một động tác (không qua hàng đợi) — dùng cho Kid và phản ứng nhanh. */
    act(a: AnimName, d: number, expr?: Expr) {
        this.anim = a;
        this.animStart = this.ctx.now();
        this.animUntil = this.ctx.now() + d;
        if (expr) {
            this.setExpr(expr, d + 0.3);
        }
    }

    /** Quay mặt về phía một điểm. */
    faceTo(p: THREE.Vector3) {
        const r = Math.atan2(p.x - this.pos.x, p.z - this.pos.z);
        this.targetRot = r;
        if (this.manual) {
            this.manual.heading = r;
        }
    }

    /** Cầm/bỏ một món đồ. */
    hold(kind: ItemKind | null) {
        this.setItem(kind);
    }

    private shoveFrom = new THREE.Vector3();
    private shoveTo = new THREE.Vector3();
    private shoveT = 0;
    private shoveD = 0;
    private shoveAnim: AnimName = 'hop';

    /** Bị đẩy/nhảy dịch đi một đoạn (đá đít nhẹ, chạy lại ôm…), có kiểm tra tường. */
    shove(
        dir: THREE.Vector3,
        dist: number,
        dur: number,
        anim: AnimName = 'hop',
    ) {
        this.shoveFrom.copy(this.pos);
        this.shoveTo
            .copy(this.pos)
            .addScaledVector(_w.set(dir.x, 0, dir.z).normalize(), dist);
        const grid = this.ctx.grid;
        if (grid) {
            // trượt tới chỗ còn trống cuối cùng trên đường bị đẩy (không lọt tường)
            const l = levelOf(this.pos.y);
            const n = Math.ceil(dist / 0.05);
            let ok = 0;
            for (let i = 1; i <= n; i++) {
                const t = i / n;
                const x =
                    this.shoveFrom.x + (this.shoveTo.x - this.shoveFrom.x) * t;
                const z =
                    this.shoveFrom.z + (this.shoveTo.z - this.shoveFrom.z) * t;
                if (grid.clearance(l, x, z) < AGENT_R) {
                    break;
                }
                ok = t;
            }
            this.shoveTo.lerpVectors(this.shoveFrom, this.shoveTo, ok);
        } else {
            this.ctx.clampPos?.(this.shoveTo);
        }
        this.shoveTo.y = this.pos.y;
        this.shoveT = 0;
        this.shoveD = Math.max(0.05, dur);
        this.shoveAnim = anim;
        this.seated = false;
        this.lying = null;
        this.path = [];
        this.pathIds = [];
        this.pathGhost = [];
        if (
            this.step &&
            (this.step.k === 'go' ||
                this.step.k === 'home' ||
                this.step.k === 'goto')
        ) {
            this.queue.unshift(this.step);
            this.step = null;
        }
    }

    /** Bị đẩy xong thì đi tiếp từ điểm dẫn đường gần nhất. */
    private get shoving() {
        return this.shoveT < this.shoveD;
    }

    /** Ảnh chụp trạng thái (lưu khi rời trang). */
    snapshot() {
        const now = this.ctx.now();

        return {
            x: +this.pos.x.toFixed(3),
            y: +this.pos.y.toFixed(3),
            z: +this.pos.z.toFixed(3),
            rot: +this.rot.toFixed(3),
            node: this.nodeId,
            seated: this.seated,
            seatH: this.seatH,
            lying: this.lying,
            anim: now < this.animUntil ? this.anim : null,
            animLeft: Math.max(0, this.animUntil - now),
            atHome: this.atHome,
        };
    }

    /** Đặt lại vị trí/tư thế đã lưu (không phát lại cảnh — người điều phối tự lo tiếp). */
    restore(s: ReturnType<Actor['snapshot']>, nearest: string) {
        this.pos.set(s.x, s.y, s.z);
        this.visualY = s.y;
        this.rot = this.targetRot = s.rot;
        this.nodeId = nearest;
        this.seated = s.seated;
        this.seatH = s.seatH;
        this.lying = s.lying;
        this.root.position.copy(this.pos);
    }

    setExpr(e: Expr, d: number) {
        this.exprOverride = e;
        this.exprUntil = this.ctx.now() + d;
    }

    /** Xoay ghế vòng vòng (game thủ rảnh tay). */
    spin(d: number) {
        this.spinUntil = this.ctx.now() + d;
    }

    private spinUntil = 0;

    alert(sec = 8) {
        this.alertUntil = this.ctx.now() + sec;
    }

    bubble(): string | null {
        const now = this.ctx.now();
        if (this.sayText && now < this.sayUntil) {
            return this.sayText;
        }
        if (
            this.base === 'working' &&
            this.bubbleText &&
            this.atHome &&
            !this.busy
        ) {
            return this.bubbleText;
        }

        return null;
    }

    anchor(out: THREE.Vector3) {
        this.ch.head.getWorldPosition(out);
        out.y += 0.82 * ACTOR_SCALE;

        return out;
    }

    // ------------------------------------------------------------------ đồ cầm tay
    private setItem(kind: ItemKind | null, arg?: number | string) {
        if (this.item) {
            this.item.parent?.remove(this.item);
            this.item = null;
        }
        if (this.itemTex) {
            this.itemTex.texture.dispose();
            this.ctx.kit.texs.delete(this.itemTex.texture);
            this.itemTex = null;
        }
        if (!kind) {
            return;
        }
        const { shapes: S, kit } = this.ctx;
        const g = new THREE.Group();
        const add = (
            geo: THREE.BufferGeometry,
            col: number,
            p: {
                x?: number;
                y?: number;
                z?: number;
                rx?: number;
                ry?: number;
                rz?: number;
                sx?: number;
                sy?: number;
                sz?: number;
            } = {},
        ) => {
            const m = new THREE.Mesh(geo, kit.toon(col));
            m.position.set(p.x ?? 0, p.y ?? 0, p.z ?? 0);
            m.rotation.set(p.rx ?? 0, p.ry ?? 0, p.rz ?? 0);
            m.scale.set(p.sx ?? 1, p.sy ?? 1, p.sz ?? 1);
            g.add(m);

            return m;
        };
        let parent: THREE.Object3D = this.ch.hold;
        switch (kind) {
            case 'umbrella': {
                // ô che mưa: cán cầm tay phải, tán trên đầu
                parent = this.ch.body;
                const col = [C.pink, C.mint, C.yellow, C.blue][
                    this.key.length % 4
                ];
                add(S.cyl(0.012, 0.012, 1.05, 6), 0x5a4a78, {
                    x: 0.2,
                    y: 1.05,
                    z: 0.14,
                });
                const can = add(umbrellaGeo(kit), col, {
                    x: 0.2,
                    y: 1.5,
                    z: 0.14,
                    sy: 0.55,
                });
                can.material = kit.toon(col, { side: THREE.DoubleSide });
                add(S.sphere(0.03, 8, 6), 0xffffff, {
                    x: 0.2,
                    y: 1.86,
                    z: 0.14,
                });
                break;
            }
            case 'paper':
                add(S.box(0.3, 0.4, 0.015), 0xffffff, { rx: -0.3 });
                for (let k = 0; k < 4; k++) {
                    add(S.box(0.2, 0.018, 0.02), 0x9a8fb8, {
                        y: 0.12 - k * 0.07,
                        z: 0.01 + k * 0.02,
                        rx: -0.3,
                    });
                }
                break;
            case 'letter':
                add(S.box(0.3, 0.2, 0.02), 0xfff3d6, { rx: -0.2 });
                add(S.cyl(0.04, 0.04, 0.025, 10), C.red, {
                    z: 0.02,
                    rx: Math.PI / 2 - 0.2,
                });
                break;
            case 'board':
                add(S.rbox(0.42, 0.32, 0.03, 0.01), 0xfffaf2, {
                    rx: -0.25,
                    y: 0.02,
                });
                for (let k = 0; k < 4; k++) {
                    add(
                        S.box(0.16, 0.11, 0.01),
                        [C.pink, C.mint, C.yellow, C.blue][k],
                        {
                            x: -0.09 + (k % 2) * 0.18,
                            y: 0.09 - Math.floor(k / 2) * 0.13,
                            z: 0.02 + Math.floor(k / 2) * 0.03,
                            rx: -0.25,
                        },
                    );
                }
                break;
            case 'reel':
                add(S.cyl(0.2, 0.2, 0.06, 24), 0x5c4a86, {
                    rx: Math.PI / 2 - 0.2,
                });
                add(S.cyl(0.06, 0.06, 0.07, 12), 0xfff3c9, {
                    rx: Math.PI / 2 - 0.2,
                });
                for (let k = 0; k < 5; k++) {
                    const a = (k / 5) * Math.PI * 2;
                    add(S.cyl(0.035, 0.035, 0.065, 8), 0xfff3c9, {
                        x: Math.cos(a) * 0.11,
                        y: Math.sin(a) * 0.11,
                        z: Math.sin(a) * 0.02,
                        rx: Math.PI / 2 - 0.2,
                    });
                }
                break;
            case 'paddle': {
                parent = this.ch.handR;
                add(S.cyl(0.02, 0.02, 0.4, 6), C.woodDark, { y: -0.15 });
                const tex = kit.canvas(128, 128, (cg, w) => {
                    cg.fillStyle = '#fffaf2';
                    cg.beginPath();
                    cg.arc(w / 2, w / 2, w / 2 - 4, 0, Math.PI * 2);
                    cg.fill();
                    cg.lineWidth = 8;
                    cg.strokeStyle = '#4a3868';
                    cg.stroke();
                    cg.fillStyle = '#6a52b8';
                    cg.font = `900 ${String(arg).length > 1 ? 62 : 80}px ${FONT}`;
                    cg.textAlign = 'center';
                    cg.textBaseline = 'middle';
                    cg.fillText(String(arg ?? '?'), w / 2, w / 2 + 4);
                });
                this.itemTex = tex;
                const face = new THREE.Mesh(
                    S.cyl(0.24, 0.24, 0.03, 26),
                    kit.toon(C.yellow),
                );
                face.rotation.x = Math.PI / 2;
                face.position.y = -0.55;
                g.add(face);
                const front = new THREE.Mesh(
                    S.plane(0.44, 0.44),
                    kit.mat(
                        new THREE.MeshBasicMaterial({
                            map: tex.texture,
                            transparent: true,
                        }),
                    ),
                );
                front.position.set(0, -0.55, 0.02);
                g.add(front);
                g.rotation.y = Math.PI;
                break;
            }
            case 'can':
            case 'mug':
                parent = this.ch.handR;
                if (kind === 'can') {
                    add(S.cyl(0.05, 0.05, 0.16, 10), 0x6fe07a, {
                        y: -0.02,
                        z: 0.04,
                    });
                    add(S.cyl(0.051, 0.051, 0.03, 10), C.yellow, {
                        y: 0.02,
                        z: 0.04,
                    });
                } else {
                    add(S.cyl(0.07, 0.06, 0.13, 12), 0xffffff, {
                        y: -0.02,
                        z: 0.05,
                    });
                    add(S.torus(0.04, 0.012, 6, 12), 0xffffff, {
                        x: 0.08,
                        y: -0.02,
                        z: 0.05,
                        ry: Math.PI / 2,
                    });
                    add(S.cyl(0.06, 0.06, 0.01, 12), 0x8a5a3a, {
                        y: 0.045,
                        z: 0.05,
                    });
                }
                break;
            case 'water':
                parent = this.ch.handR;
                add(S.cyl(0.09, 0.1, 0.16, 12), C.mint, { y: -0.05, z: 0.08 });
                add(S.cyl(0.015, 0.02, 0.22, 6), C.mint, {
                    y: 0.0,
                    z: 0.22,
                    rx: 1.1,
                });
                break;
            default:
                break;
        }
        g.traverse((o) => (o.raycast = () => undefined));
        g.userData.kind = kind;
        parent.add(g);
        this.item = g;
    }

    private get carrying() {
        return this.item !== null && this.item.parent === this.ch.hold;
    }

    // ------------------------------------------------------------------ vòng lặp
    update(dt: number) {
        const now = this.ctx.now();
        this.t += dt;
        this.lastPos.copy(this.pos);
        if (this.driver) {
            this.ghost = true;
            if (!this.driver(dt)) {
                this.driver = null;
                this.ghost = false;
                this.nodeId = this.ctx.nav.nearest(
                    this.pos,
                    (id) => !id.endsWith('.seat'),
                );
            }
        } else if (this.shoving) {
            this.shoveT += dt;
            const k = clamp(this.shoveT / this.shoveD, 0, 1);
            const e = 1 - (1 - k) * (1 - k);
            this.pos.x =
                this.shoveFrom.x + (this.shoveTo.x - this.shoveFrom.x) * e;
            this.pos.z =
                this.shoveFrom.z + (this.shoveTo.z - this.shoveFrom.z) * e;
            this.anim = this.shoveAnim;
            this.animUntil = now + 0.1;
            if (k >= 1 && !this.manual) {
                this.nodeId = this.ctx.nav.nearest(
                    this.pos,
                    (id) => !id.endsWith('.seat'),
                );
            }
        } else if (this.manual) {
            if (this.manual.speed > 0.05) {
                this.targetRot = this.manual.heading;
            }
        } else {
            // lấy bước kế tiếp
            if (!this.step) {
                this.nextStep();
            }
            this.runStep(dt, now);
            if (!this.moving) {
                this.ghost = false;
            }
        }

        // quay mặt mượt
        if (now < this.spinUntil && this.ctx.motion) {
            this.rot += dt * 9;
            this.targetRot = this.rot;
        }
        if (this.lookAt && now < this.pauseUntil) {
            this.targetRot = Math.atan2(
                this.lookAt.x - this.pos.x,
                this.lookAt.z - this.pos.z,
            );
        }
        this.rot = dampAngle(
            this.rot,
            this.targetRot,
            this.moving ? 10 : 7,
            dt,
        );
        this.root.rotation.y = this.lying ? this.lying.rot : this.rot;
        this.root.rotation.x = damp(
            this.root.rotation.x,
            this.lying ? -Math.PI / 2 : 0,
            8,
            dt,
        );

        // vận tốc thực (để người khác đoán hướng mà né)
        if (dt > 0) {
            this.vel
                .set(
                    this.pos.x - this.lastPos.x,
                    0,
                    this.pos.z - this.lastPos.z,
                )
                .divideScalar(dt);
            if (this.vel.lengthSq() > 64) {
                this.vel.setLength(8);
            }
        }
        // chuỗi động tác
        if (now >= this.animUntil && this.animChain.length) {
            const [na, nd] = this.animChain.shift()!;
            this.act(na, nd);
        }

        // dáng điệu
        let a: AnimName;
        const wet = this.ctx.raining?.() && this.pos.y < 0.2;
        if (this.driver && now < this.animUntil) {
            a = this.anim;
        } else if (this.manual && this.manual.speed > 0.1) {
            a =
                this.manual.speed > 4.0
                    ? 'sprint'
                    : this.manual.speed > 2.4
                      ? wet
                          ? 'coverRun'
                          : 'run'
                      : 'walk';
        } else if (this.moving && this.path.length && now >= this.pauseUntil) {
            const g = this.gait;
            a = this.carrying
                ? g === 'run' || g === 'sprint'
                    ? 'carryRun'
                    : 'carry'
                : g === 'cover' || (wet && g !== 'sprint')
                  ? 'coverRun'
                  : g;
        } else if (now < this.animUntil) {
            a = this.anim;
        } else {
            a = this.restAnim();
        }
        poseFor(
            a,
            this.ctx.motion ? this.t : 0.5,
            this.seated,
            this.tgt,
            now - this.animStart,
        );
        // trời mưa mà phải ra ngoài làm việc: cầm ô
        const outside = this.pos.y < 0.2 && !this.driver;
        const umb = this.item?.userData.kind === 'umbrella';
        if (
            wet &&
            outside &&
            !this.item &&
            !this.manual &&
            this.inScene &&
            !this.leisure
        ) {
            this.setItem('umbrella');
        } else if (umb && (!wet || !outside)) {
            this.setItem(null);
        }
        if (this.item?.userData.kind === 'umbrella') {
            this.tgt.armRx = -1.05;
            this.tgt.armRz = 0.3;
        }
        // bụi bay khi chạy nước rút
        if (
            a === 'sprint' &&
            this.ctx.motion &&
            now > this.dustAt &&
            this.pos.y < F1 + 0.2
        ) {
            this.dustAt = now + 0.14;
            this.ctx.fx.dust(
                _w.set(
                    this.pos.x - Math.sin(this.rot) * 0.25,
                    this.pos.y + 0.05,
                    this.pos.z - Math.cos(this.rot) * 0.25,
                ),
            );
        }
        if (this.seated) {
            this.tgt.hipsY = this.seatH / ACTOR_SCALE;
        }
        if (
            this.base === 'sleep' &&
            !this.seated &&
            !this.moving &&
            now >= this.animUntil
        ) {
            this.tgt.headX = 0.35;
            this.tgt.headZ = 0.15;
        }
        applyPose(this.ch, this.cur, this.tgt, dt);

        // vị trí (y mượt khi lên bậc thang)
        this.visualY = damp(this.visualY, this.pos.y, 16, dt);
        if (this.lying) {
            this.root.position.set(this.lying.x, this.lying.y, this.lying.z);
        } else {
            this.root.position.set(this.pos.x, this.visualY, this.pos.z);
        }
        this.shadow.visible = !this.lying;
        this.shadow.position.set(this.pos.x, this.visualY + 0.02, this.pos.z);
        this.shadow.scale.setScalar(
            this.seated ? 1.05 : 1 - this.cur.bodyY * 1.2,
        );

        // mặt
        const e = this.currentExpr(now, a);
        if (now > this.blinkAt) {
            this.blinkEnd = now + 0.13;
            this.blinkAt = now + rand(2.2, 5.5);
        }
        const talking =
            this.sayText && now < this.sayUntil && now - this.sayStart < 1.6;
        this.ch.face.set(
            e,
            now < this.blinkEnd,
            talking ? (Math.sin(this.t * 16) > 0 ? 1 : 0.5) : 0,
        );

        // zzz khi ngủ
        if (
            (this.base === 'sleep' ||
                (this.lying !== null &&
                    this.exprOverride === 'sleepy' &&
                    now < this.exprUntil)) &&
            !this.moving &&
            now > this.zzzAt &&
            this.ctx.motion
        ) {
            this.zzzAt = now + 1.7;
            this.ctx.fx.zzz(this.anchor(_v).add(_w.set(0.25, -0.3, 0)));
        }
        // việc vặt khi rảnh
        if (
            !this.busy &&
            !this.inScene &&
            this.base === 'idle' &&
            this.ctx.motion &&
            this.onIdle
        ) {
            this.idleTimer -= dt;
            if (this.idleTimer <= 0) {
                this.idleTimer = rand(14, 32);
                const steps = this.onIdle(this);
                if (steps) {
                    this.push(...steps);
                }
            }
        }
    }

    private restAnim(): AnimName {
        if (this.lying) {
            return this.base === 'sleep' ? 'curl' : 'lie';
        }
        if (this.base === 'sleep') {
            return this.seated ? 'sleep' : 'idle';
        }
        if (this.base === 'working' && this.atHome) {
            return this.home.work === 'idle' ? 'idle' : this.home.work;
        }

        return this.seated ? 'sitIdle' : 'idle';
    }

    private currentExpr(now: number, a: AnimName): Expr {
        if (this.exprOverride && now < this.exprUntil) {
            return this.exprOverride;
        }
        if (a === 'cheer' || a === 'highfive' || a === 'paddle') {
            return 'joy';
        }
        if (a === 'yawn' || this.base === 'sleep') {
            return 'sleepy';
        }
        if (a === 'stomp') {
            return 'annoyed';
        }
        if (this.base === 'working' && this.atHome) {
            return this.baseExpr.work;
        }

        return this.baseExpr.idle;
    }

    /** Khi hết việc: tự về chỗ của mình. */
    private nextStep() {
        let s = this.queue.shift() ?? null;
        if (!s && !this.inScene && !this.atHome) {
            s = { k: 'home' };
        }
        this.step = s;
        this.stepT = 0;
        if (!s) {
            return;
        }
        const now = this.ctx.now();
        switch (s.k) {
            case 'go':
            case 'goto':
            case 'home': {
                this.parked = false;
                const to =
                    s.k === 'home'
                        ? this.home.node
                        : s.k === 'goto'
                          ? this.ctx.nav.nearest(
                                s.p,
                                (id) =>
                                    !id.endsWith('.seat') &&
                                    levelOf(this.ctx.nav.pos(id).y) ===
                                        levelOf(s.p.y),
                            )
                          : s.to;
                this.gait =
                    // việc thường ngày (kể cả về chỗ làm) thì đi bộ; chạy chỉ khi kịch bản ghi rõ
                    s.gait ?? 'walk';
                this.seated = false;
                this.lying = null;
                if (!this.ctx.motion) {
                    // giảm chuyển động: không đi lại, đứng yên tại chỗ
                    if (s.k === 'home') {
                        this.nodeId = this.home.node;
                        this.pos.copy(this.ctx.nav.pos(this.home.node));
                        this.seated = this.home.seated;
                        this.seatH = 0.5;
                        this.targetRot = this.rot = this.home.rot;
                    }
                    this.step = null;

                    return;
                }
                const ids = this.ctx.nav.path(this.nodeId, to);
                if (ids.length === 0) {
                    this.nodeId = to;
                    this.pos.copy(s.k === 'goto' ? s.p : this.ctx.nav.pos(to));
                    this.pathIds = [];
                    this.path = [];
                    this.pathGhost = [];
                } else {
                    // bỏ điểm đầu nếu đang đứng đúng ở đó
                    if (this.ctx.nav.pos(ids[0]).distanceTo(this.pos) < 0.05) {
                        ids.shift();
                    }
                    if (s.k === 'goto') {
                        // điểm dẫn đường cuối thường thừa: đi thẳng tới điểm đích
                        ids.pop();
                    }
                    this.refine(ids, s.k === 'goto' ? s.p : undefined);
                    this.pathI = 0;
                    this.segFrom.copy(this.pos);
                }
                break;
            }
            case 'sit':
                this.seated = true;
                this.lying = null;
                this.seatH = s.h ?? 0.5;
                this.targetRot = s.rot ?? this.home.rot;
                this.step = null;
                break;
            case 'lie':
                this.seated = false;
                this.lying = { ...s.at };
                this.step = null;
                break;
            case 'stand':
                this.seated = false;
                this.lying = null;
                this.step = null;
                break;
            case 'anim':
                this.anim = s.a;
                this.animUntil =
                    now + (this.ctx.motion ? s.d : Math.min(s.d, 1.5));
                if (s.expr) {
                    this.setExpr(s.expr, s.d);
                }
                break;
            case 'say':
                this.say(s.text, s.d, s.prio);
                this.step = null;
                break;
            case 'item':
                this.setItem(s.item, s.arg);
                this.step = null;
                break;
            case 'face': {
                const at = typeof s.at === 'function' ? s.at() : s.at;
                if (at) {
                    this.targetRot = Math.atan2(
                        at.x - this.pos.x,
                        at.z - this.pos.z,
                    );
                } else if (s.rot !== undefined) {
                    this.targetRot = s.rot;
                }
                break;
            }
            case 'do':
                s.fn();
                this.step = null;
                break;
            case 'expr':
                this.setExpr(s.e, s.d);
                this.step = null;
                break;
            default:
                break;
        }
        if (this.step === null && this.queue.length) {
            this.nextStep();
        }
    }

    private runStep(dt: number, now: number) {
        const s = this.step;
        if (!s) {
            return;
        }
        this.stepT += dt;
        switch (s.k) {
            case 'go':
            case 'goto':
            case 'home':
                if (now < this.pauseUntil) {
                    break;
                }
                if (this.move(dt)) {
                    if (s.k === 'home' && this.home.seated) {
                        this.seated = true;
                        this.seatH = 0.5;
                    }
                    if (s.k === 'home') {
                        this.targetRot = this.home.rot;
                    }
                    this.step = null;
                }
                break;
            case 'anim':
                if (now >= this.animUntil) {
                    this.step = null;
                }
                break;
            case 'face':
                if (this.stepT > 0.3) {
                    this.step = null;
                }
                break;
            case 'wait':
                if (
                    this.stepT >= (this.ctx.motion ? s.d : Math.min(s.d, 0.5))
                ) {
                    this.step = null;
                }
                break;
            case 'until':
                if (s.fn() || this.stepT >= s.max) {
                    this.step = null;
                }
                break;
            default:
                this.step = null;
        }
    }

    /**
     * Biến chuỗi điểm của đồ thị thành đường đi thật: trong cùng một tầng thì tìm đường trên lưới va chạm
     * (vòng qua tường, đồ đạc, người khác), giữa các tầng thì theo cầu thang.
     */
    private refine(
        ids: string[],
        dest?: THREE.Vector3,
        avoid: { x: number; z: number; r: number }[] = [],
    ) {
        const nav = this.ctx.nav;
        const pts = ids.map((id) => nav.pos(id));
        const pid: (string | null)[] = [...ids];
        if (dest) {
            pts.push(dest.clone());
            pid.push(null);
        }
        const P: THREE.Vector3[] = [];
        const I: (string | null)[] = [];
        const G: boolean[] = [];
        const grid = this.ctx.grid;
        const stair = (a: string | null, b: string | null) =>
            !!a?.startsWith('st.') && !!b?.startsWith('st.');
        let cur = this.pos.clone();
        let curId: string | null = this.nodeId;
        let i = 0;
        while (i < pts.length) {
            const l = levelOf(cur.y);
            if (!grid || levelOf(pts[i].y) !== l || stair(curId, pid[i])) {
                P.push(pts[i]);
                I.push(pid[i]);
                G.push(!!grid);
                cur = pts[i];
                curId = pid[i];
                i++;
                continue;
            }
            let j = i;
            while (
                j + 1 < pts.length &&
                levelOf(pts[j + 1].y) === l &&
                !stair(pid[j], pid[j + 1])
            ) {
                j++;
            }
            const seg = this.gridSeg(grid, l, cur, pts[j], avoid);
            seg.forEach((q, k) => {
                P.push(q.p);
                I.push(k === seg.length - 1 ? pid[j] : null);
                G.push(q.ghost);
            });
            cur = pts[j];
            curId = pid[j];
            i = j + 1;
        }
        this.path = P;
        this.pathIds = I;
        this.pathGhost = G;
    }

    private gridSeg(
        grid: NavGrid,
        l: number,
        from: THREE.Vector3,
        to: THREE.Vector3,
        avoid: { x: number; z: number; r: number }[],
    ): { p: THREE.Vector3; ghost: boolean }[] {
        const yAt = (x: number, z: number) => (l === 0 ? groundY(x, z) : to.y);
        const s = grid.nearestFree(l, from.x, from.z);
        const g = grid.nearestFree(l, to.x, to.z);
        if (!s || !g) {
            return [{ p: to.clone(), ghost: true }];
        }
        const out: { p: THREE.Vector3; ghost: boolean }[] = [];
        if (Math.hypot(s.x - from.x, s.z - from.z) > 0.03) {
            // đứng dậy khỏi ghế / bước ra khỏi chỗ chật
            out.push({
                p: new THREE.Vector3(s.x, yAt(s.x, s.z), s.z),
                ghost: true,
            });
        }
        const path =
            grid.findPath(l, s.x, s.z, g.x, g.z, AGENT_R, avoid) ??
            (avoid.length ? grid.findPath(l, s.x, s.z, g.x, g.z) : null);
        if (!path) {
            out.push({ p: to.clone(), ghost: true });

            return out;
        }
        for (const q of path) {
            out.push({
                p: new THREE.Vector3(q.x, yAt(q.x, q.z), q.z),
                ghost: false,
            });
        }
        if (Math.hypot(g.x - to.x, g.z - to.z) > 0.03) {
            // bước nốt vào ghế / sát bàn
            out.push({ p: to.clone(), ghost: true });
        } else {
            out[out.length - 1].p.copy(to);
        }

        return out;
    }

    /** Bị chặn lâu: tìm đường khác, coi những người đang đứng yên gần đó là vật cản. */
    private repath() {
        const grid = this.ctx.grid;
        if (!grid) {
            return;
        }
        let k = this.pathI;
        while (
            k < this.path.length - 1 &&
            !this.pathIds[k] &&
            !this.pathGhost[k + 1]
        ) {
            k++;
        }
        const goal = this.path[k];
        const l = levelOf(this.pos.y);
        if (levelOf(goal.y) !== l) {
            return;
        }
        const avoid = this.ctx.actors
            .filter(
                (o) =>
                    o !== this &&
                    !o.lying &&
                    Math.abs(o.pos.y - this.pos.y) < 0.6 &&
                    o.vel.lengthSq() < 0.09 &&
                    o.pos.distanceTo(this.pos) < 5 &&
                    o.pos.distanceTo(goal) > 0.5,
            )
            .map((o) => ({ x: o.pos.x, z: o.pos.z, r: PAIR_D + 0.06 }));
        const seg = this.gridSeg(grid, l, this.pos, goal, avoid);
        const id = this.pathIds[k];
        this.path.splice(
            this.pathI,
            k - this.pathI + 1,
            ...seg.map((q) => q.p),
        );
        this.pathIds.splice(
            this.pathI,
            k - this.pathI + 1,
            ...seg.map((_, n) => (n === seg.length - 1 ? id : null)),
        );
        this.pathGhost.splice(
            this.pathI,
            k - this.pathI + 1,
            ...seg.map((q) => q.ghost),
        );
        this.segFrom.copy(this.pos);
    }

    /** Vấp ngã (khi chạy nước rút hoặc bị va mạnh), nằm sấp chút rồi lồm cồm bò dậy. */
    stumble() {
        const now = this.ctx.now();
        if (now < this.tripCool || this.seated || this.lying || this.driver) {
            return false;
        }
        this.tripCool = now + 25;
        this.pauseUntil = now + 2.7;
        this.lookAt = null;
        this.chain(
            [
                ['trip', 0.7],
                ['fallen', 1.1],
                ['getup', 0.9],
            ],
            'surprise',
        );
        this.setExpr('surprise', 1.2);
        this.say(
            pick(['Ui da!', 'Oái!', 'Á á á!', 'Ối giời ơi!']),
            2.2,
            'reply',
        );
        if (this.ctx.motion) {
            const p = this.pos.clone();
            p.x += Math.sin(this.rot) * 0.6;
            p.z += Math.cos(this.rot) * 0.6;
            setTimeout(() => this.ctx.fx.dust(p, 6), 600);
        }

        return true;
    }

    /** Đi dọc đường; trả true khi tới nơi. */
    private move(dt: number): boolean {
        if (this.pathI >= this.path.length) {
            const lastGhost = this.pathGhost[this.pathGhost.length - 1];
            this.parked = !!lastGhost;
            this.path = [];
            this.pathIds = [];
            this.pathGhost = [];
            this.ghost = false;

            return true;
        }
        const now = this.ctx.now();
        const target = this.path[this.pathI];
        const ghostPath = this.pathGhost[this.pathI];
        const escaping = now < this.escapeUntil;
        const ghost = ghostPath || escaping;
        this.ghost = ghost;
        _v.set(target.x - this.pos.x, 0, target.z - this.pos.z);
        const dist = _v.length();
        if (dist < 0.04) {
            this.pos.x = target.x;
            this.pos.z = target.z;
            this.pos.y = target.y;
            const id = this.pathIds[this.pathI];
            if (id) {
                this.nodeId = id;
            }
            this.segFrom.copy(target);
            this.pathI++;

            return this.move(0);
        }
        _v.divideScalar(dist);
        this.targetRot = Math.atan2(_v.x, _v.z);
        const speed = SPEED[this.gait];
        const grid = this.ctx.grid;
        const lvl = levelOf(this.pos.y);
        // né người: đoán điểm gần nhất sắp tới (theo vận tốc hai bên) rồi bước tránh sang bên + chậm lại
        let ax = 0;
        let az = 0;
        let slow = 1;
        let blocker: Actor | null = null;
        if (!ghost) {
            for (const o of this.ctx.actors) {
                if (
                    o === this ||
                    o.lying ||
                    Math.abs(o.pos.y - this.pos.y) > 0.6
                ) {
                    continue;
                }
                const rx = o.pos.x - this.pos.x;
                const rz = o.pos.z - this.pos.z;
                const d = Math.hypot(rx, rz);
                if (d > 1.9 || d < 1e-4) {
                    continue;
                }
                const ahead = (rx * _v.x + rz * _v.z) / d;
                const dvx = o.vel.x - _v.x * speed;
                const dvz = o.vel.z - _v.z * speed;
                const dv2 = dvx * dvx + dvz * dvz;
                const tc =
                    dv2 > 1e-4
                        ? clamp(-(rx * dvx + rz * dvz) / dv2, 0, 1.4)
                        : 0;
                const dmin = Math.hypot(rx + dvx * tc, rz + dvz * tc);
                if (dmin < PAIR_D + 0.14 && ahead > -0.1) {
                    const cr = _v.x * rz - _v.z * rx;
                    const side = Math.abs(cr) < 0.12 * d ? 1 : -Math.sign(cr);
                    const w = (1 - tc / 1.4) * clamp((1.9 - d) / 1.1, 0, 1);
                    ax += -_v.z * side * w * 1.4;
                    az += _v.x * side * w * 1.4;
                }
                if (ahead > 0.5 && d < 1.05) {
                    slow = Math.min(
                        slow,
                        clamp((d - PAIR_D + 0.04) / 0.4, 0.06, 1),
                    );
                    if (o.vel.lengthSq() < 0.09) {
                        blocker = o;
                    }
                    // chạy nước rút mà đâm sầm vào người → vấp
                    if (
                        this.gait === 'sprint' &&
                        d < PAIR_D + 0.06 &&
                        Math.random() < 0.35
                    ) {
                        this.stumble();
                    }
                }
            }
        }
        let mx = _v.x + ax;
        let mz = _v.z + az;
        const ml = Math.hypot(mx, mz) || 1;
        mx /= ml;
        mz /= ml;
        const step = Math.min(dist, speed * slow * dt);
        let nx = this.pos.x + mx * step;
        let nz = this.pos.z + mz * step;
        if (!ghostPath && grid) {
            let q = grid.slide(lvl, this.pos.x, this.pos.z, nx, nz);
            if (q.x === this.pos.x && q.z === this.pos.z) {
                q = grid.slide(
                    lvl,
                    this.pos.x,
                    this.pos.z,
                    this.pos.x + _v.x * step,
                    this.pos.z + _v.z * step,
                );
            }
            nx = q.x;
            nz = q.z;
        }
        const moved = Math.hypot(nx - this.pos.x, nz - this.pos.z);
        this.pos.x = nx;
        this.pos.z = nz;
        if (dt > 0 && moved < speed * dt * 0.3) {
            this.blocked += dt;
        } else {
            this.blocked = Math.max(0, this.blocked - dt * 2);
        }
        if (this.blocked > 0.5 && blocker && now > this.bumpCool) {
            this.bumpCool = now + 14;
            this.ctx.onBump?.(this, blocker);
        }
        if (this.blocked > 1.4 && now > this.repathAt && !ghost) {
            this.repathAt = now + 1.6;
            this.repath();
        }
        // đích đã có người đứng (cả nhóm cùng tới một chỗ): dừng gần đó là được
        const fin = this.path[this.path.length - 1];
        const left = Math.hypot(fin.x - this.pos.x, fin.z - this.pos.z);
        if (
            this.blocked > 0.8 &&
            left < 1.6 &&
            (blocker || this.blocked > 3) &&
            this.step?.k !== 'home' &&
            !this.pathGhost[this.path.length - 1]
        ) {
            const id = this.pathIds[this.path.length - 1];
            if (id) {
                this.nodeId = id;
            }
            this.pathI = this.path.length;
            this.blocked = 0;
            this.ghost = false;

            return this.move(0);
        }
        if (this.blocked > 10) {
            // kẹt rất lâu (hai người cùng chặn nhau ở chỗ hẹp): lách qua nhau một chút (vẫn không xuyên tường)
            this.escapeUntil = now + 1.0;
            this.blocked = 0;
            this.escapes++;
        }
        // chạy nước rút thì thỉnh thoảng vấp
        if (
            this.gait === 'sprint' &&
            !ghost &&
            this.ctx.motion &&
            Math.random() < dt / 22
        ) {
            this.stumble();
        }
        // độ cao: tầng 1 + vườn theo mặt sàn; nơi khác nội suy theo đoạn, cầu thang theo bậc
        if (!ghost && lvl === 0) {
            this.pos.y = groundY(this.pos.x, this.pos.z);
        } else {
            const segLen =
                Math.hypot(
                    target.x - this.segFrom.x,
                    target.z - this.segFrom.z,
                ) || 1;
            const left = Math.hypot(
                target.x - this.pos.x,
                target.z - this.pos.z,
            );
            const tt = clamp(1 - left / segLen, 0, 1);
            this.pos.y = this.segFrom.y + (target.y - this.segFrom.y) * tt;
            const sy = stairY(this.pos.x, this.pos.z);
            if (sy !== null && Math.abs(target.y - this.segFrom.y) > 0.5) {
                this.pos.y = sy;
            }
        }

        return false;
    }

    setHighlight(on: boolean) {
        this.ch.setHighlight(on);
    }
}

/** Ảnh bóng tròn mềm dưới chân. */
export const blobShadow = (kit: Kit) => {
    const tex = kit.canvas(64, 64, (g, w) => {
        const gr = g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
        gr.addColorStop(0, 'rgba(58,40,90,0.42)');
        gr.addColorStop(0.6, 'rgba(58,40,90,0.2)');
        gr.addColorStop(1, 'rgba(58,40,90,0)');
        g.fillStyle = gr;
        g.fillRect(0, 0, w, w);
    });

    return kit.mat(
        new THREE.MeshBasicMaterial({
            map: tex.texture,
            transparent: true,
            depthWrite: false,
            polygonOffset: true,
            polygonOffsetFactor: -2,
        }),
    );
};

export { roundRect };

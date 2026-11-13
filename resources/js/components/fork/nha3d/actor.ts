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
import { type Home, stairY } from './layout';
import type { NavGraph } from './nav';
import { type Prio, Speech } from './speech';
import {
    C,
    CanvasTex,
    clamp,
    damp,
    dampAngle,
    FONT,
    Kit,
    rand,
    roundRect,
    Shapes,
} from './util';

export type Gait = 'walk' | 'run' | 'stomp';
export type ItemKind =
    | 'paper'
    | 'reel'
    | 'board'
    | 'letter'
    | 'paddle'
    | 'can'
    | 'mug'
    | 'water';

export type Step =
    | { k: 'go'; to: string; gait?: Gait }
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
    /** Điều phối lời nói (chống nói dồn dập). */
    speech?: Speech;
}

/** Nhân vật to hơn so với phòng (so với khung xương gốc). */
export const ACTOR_SCALE = 1.32;

const SPEED: Record<Gait, number> = { walk: 1.6, run: 3.4, stomp: 1.9 };
const _v = new THREE.Vector3();
const _w = new THREE.Vector3();

export class Actor implements Talker {
    readonly root: THREE.Group;
    readonly ch: Chibi;
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
    private pathIds: string[] = [];
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
    private side = 0;
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
        readonly baseExpr: { work: Expr; idle: Expr } = {
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
        return this.step?.k === 'go' || this.step?.k === 'home';
    }

    /** Thêm hành động vào cuối hàng. */
    push(...steps: Step[]) {
        this.queue.push(...steps);
    }

    /** Bỏ hết việc đang làm (dừng tại chỗ). */
    interrupt() {
        if (this.moving && this.pathIds[this.pathI]) {
            this.nodeId = this.pathIds[this.pathI];
            this.queue = [{ k: 'go', to: this.nodeId }];
        } else {
            this.queue = [];
        }
        this.step = null;
        this.path = [];
        this.pathIds = [];
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
    say(text: string, d?: number, prio?: Prio): boolean {
        if (!text) {
            return false;
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
        if (this.manual) {
            if (this.manual.speed > 0.05) {
                this.targetRot = this.manual.heading;
            }
        } else {
            // lấy bước kế tiếp
            if (!this.step) {
                this.nextStep();
            }
            this.runStep(dt, now);
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

        // dáng điệu
        let a: AnimName;
        if (this.manual && this.manual.speed > 0.1) {
            a = this.manual.speed > 2.4 ? 'run' : 'walk';
        } else if (this.moving && this.path.length && now >= this.pauseUntil) {
            const g = this.gait;
            a = this.carrying ? (g === 'run' ? 'carryRun' : 'carry') : g;
        } else if (now < this.animUntil) {
            a = this.anim;
        } else {
            a = this.restAnim();
        }
        poseFor(a, this.ctx.motion ? this.t : 0.5, this.seated, this.tgt);
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
            return 'lie';
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
            case 'home': {
                const to = s.k === 'home' ? this.home.node : s.to;
                this.gait =
                    s.gait ??
                    (s.k === 'home' && this.base === 'working'
                        ? 'run'
                        : 'walk');
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
                this.pathIds = this.ctx.nav.path(this.nodeId, to);
                if (this.pathIds.length === 0) {
                    this.nodeId = to;
                    this.pos.copy(this.ctx.nav.pos(to));
                    this.pathIds = [];
                    this.path = [];
                } else {
                    // bỏ điểm đầu nếu đang đứng đúng ở đó
                    if (
                        this.ctx.nav.pos(this.pathIds[0]).distanceTo(this.pos) <
                        0.05
                    ) {
                        this.pathIds.shift();
                    }
                    this.path = this.pathIds.map((id) => this.ctx.nav.pos(id));
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

    /** Đi dọc đường; trả true khi tới nơi. */
    private move(dt: number): boolean {
        if (this.pathI >= this.path.length) {
            this.path = [];
            this.pathIds = [];

            return true;
        }
        const target = this.path[this.pathI];
        _v.set(target.x - this.pos.x, 0, target.z - this.pos.z);
        const dist = _v.length();
        if (dist < 0.04) {
            this.pos.x = target.x;
            this.pos.z = target.z;
            this.pos.y = target.y;
            this.nodeId = this.pathIds[this.pathI];
            this.segFrom.copy(target);
            this.pathI++;

            return this.move(0);
        }
        _v.divideScalar(dist);
        this.targetRot = Math.atan2(_v.x, _v.z);
        // né người khác
        let block = false;
        for (const o of this.ctx.actors) {
            if (
                o === this ||
                o.seated ||
                o.lying ||
                Math.abs(o.pos.y - this.pos.y) > 0.6
            ) {
                continue;
            }
            _w.set(o.pos.x - this.pos.x, 0, o.pos.z - this.pos.z);
            const d = _w.length();
            if (d < 0.78 && d > 0.001 && _w.dot(_v) / d > 0.35) {
                // người kia cũng đang đi về phía mình hoặc đứng chắn đường
                block = true;
                if (
                    this.blocked > 0.25 &&
                    this.ctx.now() > this.bumpCool &&
                    !o.lying
                ) {
                    this.bumpCool = this.ctx.now() + 14;
                    this.ctx.onBump?.(this, o);
                }
                break;
            }
        }
        let speed = SPEED[this.gait];
        if (block) {
            this.blocked += dt;
            speed *= 0.15;
            if (this.blocked > 0.6) {
                this.side = 1.2;
            }
        } else {
            this.blocked = Math.max(0, this.blocked - dt);
        }
        const step = Math.min(dist, speed * dt);
        this.pos.x += _v.x * step;
        this.pos.z += _v.z * step;
        if (this.side > 0) {
            // bước tránh sang phải một chút
            this.side -= dt;
            const k = Math.sin((this.side / 1.2) * Math.PI) * 0.9 * dt;
            this.pos.x += -_v.z * k;
            this.pos.z += _v.x * k;
            if (this.side <= 0) {
                this.blocked = 0;
            }
        }
        // độ cao: nội suy theo đoạn, cầu thang theo bậc
        const segLen =
            Math.hypot(target.x - this.segFrom.x, target.z - this.segFrom.z) ||
            1;
        const left = Math.hypot(target.x - this.pos.x, target.z - this.pos.z);
        const tt = clamp(1 - left / segLen, 0, 1);
        this.pos.y = this.segFrom.y + (target.y - this.segFrom.y) * tt;
        const sy = stairY(this.pos.x, this.pos.z);
        if (sy !== null && Math.abs(target.y - this.segFrom.y) > 0.5) {
            this.pos.y = sy;
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

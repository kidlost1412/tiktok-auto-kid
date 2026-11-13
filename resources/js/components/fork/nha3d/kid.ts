// "Kid" — nhân vật của chủ xưởng: đi dạo trong xưởng bằng WASD/mũi tên hoặc bấm xuống sàn để đi tới.
// Va chạm đơn giản bằng các hình chữ nhật trên mặt đất (tường, vách, cầu thang, bàn, hồ…); chỉ đi ở tầng 1 và ngoài vườn.
import * as THREE from 'three';

import type { Actor } from './actor';
import type { AnimName } from './chibi';
import {
    BAY_CX,
    F1,
    FENCE_Z,
    PINGPONG,
    PLOT,
    POND,
    RW,
    STAIR_Z0,
    STAIR_Z1,
    VEG,
    wingOf,
    X0,
    X1,
    XL0,
    XR1,
    Z_BACK,
    Z_FRONT,
    Z_ROOM,
} from './layout';
import type { NavGraph } from './nav';
import { AGENT_R, inPond, type NavGrid, PAIR_D } from './navgrid';

interface Rect {
    x0: number;
    x1: number;
    z0: number;
    z1: number;
}

const R = 0.3; // bán kính thân
const WALK = 2.3;
const RUN = 4.2;

/** Độ cao sàn tại (x, z): trong nhà + hiên là tầng 1, ngoài là vườn. */
export const groundY = (x: number, z: number) =>
    z <= Z_FRONT && x >= XL0 - 0.3 && x <= XR1 + 0.3 ? F1 : 0;

const rect = (x0: number, x1: number, z0: number, z1: number): Rect => ({
    x0: Math.min(x0, x1),
    x1: Math.max(x0, x1),
    z0: Math.min(z0, z1),
    z1: Math.max(z0, z1),
});

const buildRects = (desks: Record<string, THREE.Vector3>): Rect[] => {
    const out: Rect[] = [];
    // tường sau (cả nhà chính lẫn hai dãy phụ)
    out.push(rect(XL0 - 0.3, XR1 + 0.3, Z_BACK - 0.4, Z_BACK + 0.05));
    // tường đầu hồi nhà chính và hai đầu dãy phụ
    for (const x of [X0 - 0.15, X1 + 0.15]) {
        out.push(rect(x - 0.2, x + 0.2, Z_BACK, Z_ROOM + 0.15));
    }
    out.push(rect(XL0 - 0.35, XL0 + 0.05, Z_BACK, Z_ROOM + 0.15));
    out.push(rect(XR1 - 0.05, XR1 + 0.35, Z_BACK, Z_ROOM + 0.15));
    // vách giữa các phòng tầng 1 (kín từ tường sau tới mép phòng)
    for (let k = 1; k <= 4; k++) {
        const x = X0 + k * RW;
        out.push(rect(x - 0.1, x + 0.1, Z_BACK, Z_ROOM));
    }
    // vách giữa hai phòng mỗi dãy phụ: kín phía sau, vòm thông phía trước
    for (const k of ['bep', 'giaitri'] as const) {
        const x = wingOf(k).x1;
        out.push(rect(x - 0.1, x + 0.1, Z_BACK, -1.3));
    }
    // cầu thang
    out.push(rect(BAY_CX - 1.3, BAY_CX + 1.3, STAIR_Z1, STAIR_Z0 + 0.25));
    // bàn làm việc tầng 1
    for (const p of Object.values(desks)) {
        if (p.y < F1 + 1.5) {
            out.push(rect(p.x - 0.85, p.x + 0.85, p.z - 0.45, p.z + 0.45));
        }
    }
    // hồ, vườn rau, bàn bóng bàn
    out.push(
        rect(
            POND.x - POND.rx * 0.85,
            POND.x + POND.rx * 0.85,
            POND.z - POND.rz * 0.8,
            POND.z + POND.rz * 0.8,
        ),
    );
    out.push(rect(VEG.x0 - 0.15, VEG.x1 + 0.15, VEG.z0 - 0.15, VEG.z1 + 0.15));
    out.push(
        rect(
            PINGPONG.x - 1.3,
            PINGPONG.x + 1.3,
            PINGPONG.z - 0.75,
            PINGPONG.z + 0.75,
        ),
    );

    return out;
};

/** Một bước trong "kịch bản" tự động của Kid (vd. đi cùng ra quầy cà phê). Bấm phím di chuyển là huỷ. */
export type KidStep =
    | { k: 'go'; p: THREE.Vector3 }
    | { k: 'face'; p: THREE.Vector3 | (() => THREE.Vector3) }
    | { k: 'anim'; a: AnimName; d: number }
    | { k: 'wait'; d: number }
    | { k: 'do'; fn: () => void };

export class KidControl {
    /** Kịch bản tự động đang chạy. */
    script: KidStep[] = [];
    private scriptT = 0;
    private scriptStarted = false;
    private nav: NavGraph | null = null;
    readonly keys = new Set<string>();
    /** Điểm đến khi bấm xuống sàn. */
    target: THREE.Vector3 | null = null;
    /** Các điểm trung gian (theo lối đi của nhà) trước khi tới đích. */
    private way: THREE.Vector3[] = [];
    private rects: Rect[];
    private stuck = 0;
    private last = new THREE.Vector3();
    /** Lưới va chạm chung với mọi người (có sau vài khung hình đầu). */
    grid: NavGrid | null = null;
    /** Những người khác (Kid không đi xuyên qua họ). */
    others: Actor[] = [];
    /** Cứ cố đi vào hồ thì… rơi tõm. */
    onPond: (() => void) | null = null;
    private pondPush = 0;

    constructor(
        readonly actor: Actor,
        desks: Record<string, THREE.Vector3>,
    ) {
        this.rects = buildRects(desks);
        actor.manual = { speed: 0, heading: Math.PI };
    }

    /** Bấm xuống sàn: tìm đường theo lối đi (qua cửa, vòng hiên) rồi tới đúng chỗ bấm. */
    goTo(p: THREE.Vector3, nav: NavGraph) {
        this.nav = nav;
        const g = this.grid;
        if (g) {
            const a = this.actor.pos;
            const s = g.nearestFree(0, a.x, a.z) ?? { x: a.x, z: a.z };
            const e = g.nearestFree(0, p.x, p.z);
            const path = e ? g.findPath(0, s.x, s.z, e.x, e.z) : null;
            if (path) {
                this.way = path
                    .slice(0, -1)
                    .map((q) => new THREE.Vector3(q.x, groundY(q.x, q.z), q.z));
                this.target = new THREE.Vector3(
                    e!.x,
                    groundY(e!.x, e!.z),
                    e!.z,
                );

                return;
            }
        }
        const ok = (id: string) =>
            !id.endsWith('.seat') && nav.pos(id).y < 2 && !id.startsWith('st.');
        const ids = nav.path(
            nav.nearest(this.actor.pos, ok),
            nav.nearest(p, ok),
        );
        this.way = ids.every(ok) ? ids.map((id) => nav.pos(id).clone()) : [];
        // bỏ các điểm đầu nằm "sau lưng"
        while (
            this.way.length > 1 &&
            this.way[0].distanceTo(this.actor.pos) < 1.2
        ) {
            this.way.shift();
        }
        this.target = p.clone();
    }

    /** Chạy một chuỗi bước tự động (huỷ chuỗi cũ). */
    run(steps: KidStep[], nav: NavGraph) {
        this.nav = nav;
        this.script = steps;
        this.scriptStarted = false;
        this.scriptT = 0;
    }

    private runScript(dt: number) {
        const s = this.script[0];
        if (!s) {
            return;
        }
        const first = !this.scriptStarted;
        this.scriptStarted = true;
        this.scriptT += dt;
        let done = false;
        switch (s.k) {
            case 'go':
                if (first && this.nav) {
                    this.goTo(s.p, this.nav);
                }
                done = !this.target;
                break;
            case 'face': {
                const p = typeof s.p === 'function' ? s.p() : s.p;
                this.actor.faceTo(p);
                done = this.scriptT > 0.3;
                break;
            }
            case 'anim':
                if (first) {
                    this.actor.act(s.a, s.d);
                }
                done = this.scriptT >= s.d;
                break;
            case 'wait':
                done = this.scriptT >= s.d;
                break;
            case 'do':
                s.fn();
                done = true;
                break;
        }
        if (done) {
            this.script.shift();
            this.scriptStarted = false;
            this.scriptT = 0;
        }
    }

    /** Giữ một điểm trong vùng đi được (dùng cho người bị đá văng). */
    clampPos(p: THREE.Vector3) {
        if (this.grid && this.grid.clearance(0, p.x, p.z) < AGENT_R) {
            const q = this.grid.nearestFree(0, p.x, p.z);
            if (q) {
                p.x = q.x;
                p.z = q.z;
            }

            return;
        }
        this.collide(p);
    }

    /** Không đi xuyên người: chạm ai thì bị đẩy ra theo mép (vẫn giữ trong vùng đi được). */
    private avoidPeople(p: THREE.Vector3) {
        for (const o of this.others) {
            if (
                o === this.actor ||
                o.lying ||
                o.driver ||
                Math.abs(o.pos.y - p.y) > 0.6
            ) {
                continue;
            }
            const dx = p.x - o.pos.x;
            const dz = p.z - o.pos.z;
            const d = Math.hypot(dx, dz);
            const min = o.seated ? PAIR_D * 0.75 : PAIR_D;
            if (d < min && d > 1e-4) {
                const k = (min - d) / d;
                const q = this.grid!.slide(
                    0,
                    p.x,
                    p.z,
                    p.x + dx * k,
                    p.z + dz * k,
                );
                p.x = q.x;
                p.z = q.z;
            }
        }
    }

    get moving() {
        return (this.actor.manual?.speed ?? 0) > 0.1;
    }

    /** Di chuyển theo phím (so với hướng camera `yaw`) hoặc tới điểm đã bấm. */
    update(dt: number, yaw: number) {
        const a = this.actor;
        const m = a.manual!;
        if (a.driver) {
            // đang bị điều khiển riêng (rơi xuống ao…): bỏ phím
            m.speed = 0;
            this.target = null;
            this.way = [];

            return;
        }
        let ix = 0;
        let iz = 0;
        const k = this.keys;
        if (k.has('KeyW') || k.has('ArrowUp')) {
            iz -= 1;
        }
        if (k.has('KeyS') || k.has('ArrowDown')) {
            iz += 1;
        }
        if (k.has('KeyA') || k.has('ArrowLeft')) {
            ix -= 1;
        }
        if (k.has('KeyD') || k.has('ArrowRight')) {
            ix += 1;
        }
        let vx = 0;
        let vz = 0;
        let speed = 0;
        if (ix || iz) {
            this.target = null;
            this.way = [];
            this.script = [];
            // tiến = hướng camera nhìn; phải = vuông góc
            const fx = -Math.sin(yaw);
            const fz = -Math.cos(yaw);
            const rx = Math.cos(yaw);
            const rz = -Math.sin(yaw);
            vx = fx * -iz + rx * ix;
            vz = fz * -iz + rz * ix;
            const l = Math.hypot(vx, vz) || 1;
            vx /= l;
            vz /= l;
            speed = k.has('ShiftLeft') || k.has('ShiftRight') ? RUN : WALK;
        } else if (this.script.length && !this.target) {
            this.runScript(dt);
        }
        if (!(ix || iz) && this.target) {
            const goal = this.way[0] ?? this.target;
            const dx = goal.x - a.pos.x;
            const dz = goal.z - a.pos.z;
            const d = Math.hypot(dx, dz);
            if (this.way.length && d < 0.22) {
                this.way.shift();
            } else if (d < 0.15) {
                this.target = null;
            } else {
                vx = dx / d;
                vz = dz / d;
                speed = d > 6 ? RUN : WALK;
                speed = Math.min(speed, d / Math.max(dt, 1e-3));
            }
        }
        // tăng/giảm tốc mềm
        m.speed += (speed - m.speed) * Math.min(1, dt * 10);
        if (speed > 0) {
            m.heading = Math.atan2(vx, vz);
        }
        if (m.speed > 0.02) {
            this.last.copy(a.pos);
            const s = speed > 0 ? m.speed : 0;
            const tx = a.pos.x + vx * s * dt;
            const tz = a.pos.z + vz * s * dt;
            if (this.grid) {
                const q = this.grid.slide(0, a.pos.x, a.pos.z, tx, tz);
                // cố đi vào hồ (bị bờ chặn) một lúc → rơi tõm
                if (
                    s > 0.5 &&
                    (q.x !== tx || q.z !== tz) &&
                    inPond(tx, tz, 1.12)
                ) {
                    this.pondPush += dt;
                    if (this.pondPush > 0.35 && this.onPond) {
                        this.pondPush = 0;
                        this.onPond();
                    }
                } else {
                    this.pondPush = Math.max(0, this.pondPush - dt);
                }
                a.pos.x = q.x;
                a.pos.z = q.z;
                this.avoidPeople(a.pos);
            } else {
                a.pos.x = tx;
                a.pos.z = tz;
                this.collide(a.pos);
            }
            a.pos.y = groundY(a.pos.x, a.pos.z);
            // kẹt (đi vào tường): bỏ điểm đến
            if (this.target && this.last.distanceTo(a.pos) < s * dt * 0.2) {
                this.stuck += dt;
                if (this.stuck > 0.6) {
                    if (this.way.length) {
                        this.way.shift();
                    } else {
                        this.target = null;
                    }
                    this.stuck = 0;
                }
            } else {
                this.stuck = 0;
            }
        }
    }

    private collide(p: THREE.Vector3) {
        p.x = Math.min(PLOT.x1 - 0.8, Math.max(PLOT.x0 + 0.8, p.x));
        p.z = Math.min(FENCE_Z - 0.4, Math.max(PLOT.z0 + 0.8, p.z));
        for (let it = 0; it < 2; it++) {
            for (const r of this.rects) {
                const cx = Math.min(r.x1, Math.max(r.x0, p.x));
                const cz = Math.min(r.z1, Math.max(r.z0, p.z));
                const dx = p.x - cx;
                const dz = p.z - cz;
                const d2 = dx * dx + dz * dz;
                if (d2 >= R * R) {
                    continue;
                }
                if (d2 > 1e-8) {
                    const d = Math.sqrt(d2);
                    p.x = cx + (dx / d) * R;
                    p.z = cz + (dz / d) * R;
                } else {
                    // tâm nằm trong hình: đẩy ra cạnh gần nhất
                    const opts = [
                        [r.x0 - R - p.x, 0],
                        [r.x1 + R - p.x, 0],
                        [0, r.z0 - R - p.z],
                        [0, r.z1 + R - p.z],
                    ];
                    opts.sort(
                        (u, v) => Math.abs(u[0] + u[1]) - Math.abs(v[0] + v[1]),
                    );
                    p.x += opts[0][0];
                    p.z += opts[0][1];
                }
            }
        }
    }
}

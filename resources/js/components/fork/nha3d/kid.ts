// "Kid" — nhân vật của chủ xưởng: đi dạo trong xưởng bằng WASD/mũi tên hoặc bấm xuống sàn để đi tới.
// Va chạm đơn giản bằng các hình chữ nhật trên mặt đất (tường, vách, cầu thang, bàn, hồ…); chỉ đi ở tầng 1 và ngoài vườn.
import * as THREE from 'three';

import type { Actor } from './actor';
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

export class KidControl {
    readonly keys = new Set<string>();
    /** Điểm đến khi bấm xuống sàn. */
    target: THREE.Vector3 | null = null;
    /** Các điểm trung gian (theo lối đi của nhà) trước khi tới đích. */
    private way: THREE.Vector3[] = [];
    private rects: Rect[];
    private stuck = 0;
    private last = new THREE.Vector3();

    constructor(
        readonly actor: Actor,
        desks: Record<string, THREE.Vector3>,
    ) {
        this.rects = buildRects(desks);
        actor.manual = { speed: 0, heading: Math.PI };
    }

    /** Bấm xuống sàn: tìm đường theo lối đi (qua cửa, vòng hiên) rồi tới đúng chỗ bấm. */
    goTo(p: THREE.Vector3, nav: NavGraph) {
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

    get moving() {
        return (this.actor.manual?.speed ?? 0) > 0.1;
    }

    /** Di chuyển theo phím (so với hướng camera `yaw`) hoặc tới điểm đã bấm. */
    update(dt: number, yaw: number) {
        const a = this.actor;
        const m = a.manual!;
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
        } else if (this.target) {
            const goal = this.way[0] ?? this.target;
            const dx = goal.x - a.pos.x;
            const dz = goal.z - a.pos.z;
            const d = Math.hypot(dx, dz);
            if (this.way.length && d < 0.4) {
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
            a.pos.x += vx * s * dt;
            a.pos.z += vz * s * dt;
            this.collide(a.pos);
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

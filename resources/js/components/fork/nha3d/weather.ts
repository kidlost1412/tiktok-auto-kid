// Thời tiết: nắng / nhiều mây / mưa rào, đổi theo giờ thật (mỗi 15 phút một "ô" thời tiết, cùng một giờ thì
// mọi lần mở trang đều giống nhau). Mưa: hạt mưa rơi quanh camera (không rơi vào trong nhà có mái), trời tối hơn,
// vũng nước loang trên cỏ. Không có tiếng (mặc định tắt âm).
import * as THREE from 'three';

import { POND, XL0, XR1, Z_BACK, Z_ROOM } from './layout';
import { clamp, type Kit } from './util';

export type Sky = 'sunny' | 'cloudy' | 'rain';

const N = 1500;
const BOX = { w: 46, h: 16, d: 34 };
const BLOCK = 15 * 60 * 1000;

/** Số giả ngẫu nhiên ổn định theo ô thời gian. */
const hash = (n: number) => {
    let x = (n ^ 0x9e3779b9) >>> 0;
    x = Math.imul(x ^ (x >>> 16), 0x85ebca6b) >>> 0;
    x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35) >>> 0;

    return ((x ^ (x >>> 16)) >>> 0) / 4294967296;
};

export const skyAt = (ms: number): Sky => {
    const r = hash(Math.floor(ms / BLOCK));
    // mưa rào ~15%, nhiều mây ~30%; mưa thường đi sau một ô nhiều mây
    if (r < 0.15) {
        return 'rain';
    }

    return r < 0.45 ? 'cloudy' : 'sunny';
};

export class Weather {
    readonly group = new THREE.Group();
    sky: Sky;
    /** 0..1 mức mưa hiện tại (chuyển mượt). */
    rain = 0;
    /** 0..1 độ u ám (mây + mưa). */
    overcast = 0;
    /** 0..1 độ ướt mặt đất (khô dần sau mưa). */
    wet = 0;
    private forced: Sky | null = null;
    private pos: Float32Array;
    private lines: THREE.LineSegments;
    private mat: THREE.LineBasicMaterial;
    private puddles: THREE.Mesh[] = [];
    private puddleMat: THREE.MeshBasicMaterial;
    private center = new THREE.Vector3();
    /** Đổi trạng thái (để người điều phối cho mọi người chạy vào nhà…). */
    onChange: ((s: Sky, prev: Sky) => void) | null = null;

    constructor(
        kit: Kit,
        private motion: boolean,
        private clockMs: () => number = () => Date.now(),
    ) {
        this.sky = skyAt(clockMs());
        this.rain = this.sky === 'rain' ? 1 : 0;
        this.overcast = this.target().ov;
        this.wet = this.rain;
        this.pos = new Float32Array(N * 6);
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
        kit.geo(g);
        this.mat = kit.mat(
            new THREE.LineBasicMaterial({
                color: 0xc4d4f0,
                transparent: true,
                opacity: 0,
                depthWrite: false,
            }),
        ) as THREE.LineBasicMaterial;
        this.lines = new THREE.LineSegments(g, this.mat);
        this.lines.frustumCulled = false;
        this.lines.raycast = () => undefined;
        this.lines.userData.noCollide = true;
        this.group.add(this.lines);
        for (let i = 0; i < N; i++) {
            this.respawn(i, Math.random() * BOX.h);
        }
        // vũng nước trên cỏ và lối đi (hiện dần khi mưa)
        this.puddleMat = kit.mat(
            new THREE.MeshBasicMaterial({
                color: 0xd6ecff,
                transparent: true,
                opacity: 0,
                depthWrite: false,
                polygonOffset: true,
                polygonOffsetFactor: -3,
            }),
        ) as THREE.MeshBasicMaterial;
        const disc = kit.geo(new THREE.CircleGeometry(1, 24));
        const spots = [
            [-3.5, 5.2, 1.1, 0.6],
            [2.4, 7.4, 0.8, 0.5],
            [-9.2, 9.8, 1.3, 0.7],
            [6.2, 4.6, 0.7, 0.45],
            [14.5, 8.8, 1.0, 0.6],
            [-17.5, 11.5, 0.9, 0.55],
            [19.8, 6.2, 0.8, 0.5],
            [-1.2, 11.6, 1.2, 0.6],
            [POND.x - 3.6, POND.z + 2.2, 0.7, 0.4],
        ];
        for (const [x, z, rx, rz] of spots) {
            const m = new THREE.Mesh(disc, this.puddleMat);
            m.rotation.x = -Math.PI / 2;
            m.position.set(x, 0.012, z);
            m.scale.set(rx, rz, 1);
            m.renderOrder = 1;
            m.raycast = () => undefined;
            m.userData.noCollide = true;
            this.puddles.push(m);
            this.group.add(m);
        }
    }

    private target() {
        const s = this.forced ?? this.sky;

        return {
            rain: s === 'rain' ? 1 : 0,
            ov: s === 'rain' ? 1 : s === 'cloudy' ? 0.45 : 0,
        };
    }

    get raining() {
        return this.rain > 0.35;
    }

    /** Ép thời tiết (gỡ lỗi / thử). null = theo giờ thật. */
    force(s: Sky | null) {
        this.forced = s;
        this.check(true);
    }

    private check(force = false) {
        const s = this.forced ?? skyAt(this.clockMs());
        if (s !== this.sky || force) {
            const prev = this.sky;
            this.sky = s;
            if (s !== prev) {
                this.onChange?.(s, prev);
            }
        }
    }

    private respawn(i: number, y: number) {
        let x = 0;
        let z = 0;
        for (let k = 0; k < 6; k++) {
            x = this.center.x + (Math.random() - 0.5) * BOX.w;
            z = this.center.z + (Math.random() - 0.5) * BOX.d;
            // dưới mái nhà thì không mưa
            if (
                !(
                    x > XL0 - 0.4 &&
                    x < XR1 + 0.4 &&
                    z > Z_BACK - 1.2 &&
                    z < Z_ROOM + 0.3
                )
            ) {
                break;
            }
            z = Z_ROOM + 0.4 + Math.random() * 12;
        }
        const o = i * 6;
        this.pos[o] = x;
        this.pos[o + 1] = y;
        this.pos[o + 2] = z;
        this.pos[o + 3] = x + 0.04;
        this.pos[o + 4] = y + 0.42;
        this.pos[o + 5] = z + 0.02;
    }

    private checkAt = 0;

    update(dt: number, focus: THREE.Vector3, now: number) {
        if (now > this.checkAt) {
            this.checkAt = now + 5;
            this.check();
        }
        const tg = this.target();
        this.rain = clamp(
            this.rain + (Math.sign(tg.rain - this.rain) * dt) / 6,
            0,
            1,
        );
        if (Math.abs(tg.rain - this.rain) < dt / 6) {
            this.rain = tg.rain;
        }
        const dov = tg.ov - this.overcast;
        this.overcast += clamp(dov, -dt / 8, dt / 8);
        this.wet = clamp(
            this.wet + (this.rain > 0.3 ? dt / 20 : -dt / 90),
            0,
            1,
        );
        this.puddleMat.opacity = this.wet * 0.42;
        this.mat.opacity = this.rain * 0.55;
        this.lines.visible = this.rain > 0.01 && this.motion;
        if (!this.lines.visible) {
            return;
        }
        this.center.copy(focus);
        const fall = 15 * dt;
        const n = Math.floor(N * this.rain);
        for (let i = 0; i < N; i++) {
            const o = i * 6;
            if (i >= n) {
                this.pos[o + 1] = -50;
                this.pos[o + 4] = -50;
                continue;
            }
            this.pos[o + 1] -= fall;
            this.pos[o + 4] -= fall;
            this.pos[o] += 0.6 * dt;
            this.pos[o + 3] += 0.6 * dt;
            if (
                this.pos[o + 1] < 0 ||
                Math.abs(this.pos[o] - this.center.x) > BOX.w / 2 + 2 ||
                Math.abs(this.pos[o + 2] - this.center.z) > BOX.d / 2 + 2
            ) {
                this.respawn(i, BOX.h * (0.6 + Math.random() * 0.4));
            }
        }
        (
            this.lines.geometry.attributes.position as THREE.BufferAttribute
        ).needsUpdate = true;
    }

    snapshot() {
        return {
            forced: this.forced,
            rain: this.rain,
            ov: this.overcast,
            wet: this.wet,
        };
    }

    restore(s: ReturnType<Weather['snapshot']>) {
        this.forced = s.forced;
        this.rain = s.rain;
        this.overcast = s.ov;
        this.wet = s.wet;
        this.check(true);
    }
}

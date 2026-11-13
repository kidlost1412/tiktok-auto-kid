// Rơi/nhảy xuống ao: bay vòng cung → tõm (té nước) → quẫy → bơi chó vào bờ → bám bờ trèo lên → giũ nước → nhỏ nước một lúc.
// Dùng chung cho Kid (cố đi vào hồ, bị đẩy) và mọi người (nhảy xuống chơi, bị sếp "đẩy xuống ao").
import * as THREE from 'three';

import type { Actor } from './actor';
import type { AnimName, Expr } from './chibi';
import type { Effects } from './effects';
import { POND } from './layout';
import type { NavGrid } from './navgrid';
import { rand } from './util';

const WATER_Y = 0.065;

export interface PlungeOpts {
    /** 'push' = bị đẩy/trượt chân (hoảng), 'jump' = tự nhảy cho vui. */
    how: 'push' | 'jump' | 'slip';
    /** Gọi khi đã lên bờ, giũ nước xong. */
    onDone?: () => void;
    /** Gọi ngay lúc chạm nước. */
    onSplash?: () => void;
}

export class Pond {
    private wet = new Map<Actor, number>();
    private dripAt = 0;
    grid: NavGrid | null = null;

    constructor(
        private fx: Effects,
        private now: () => number,
        private motion: boolean,
    ) {}

    /** Có ai đang dưới ao không. */
    busy = new Set<Actor>();

    /** Điểm trên bờ (ngoài hồ, đi được) gần hướng `toward`. */
    private shore(toward: THREE.Vector3): THREE.Vector3 {
        const a = Math.atan2(
            (toward.z - POND.z) / POND.rz,
            (toward.x - POND.x) / POND.rx,
        );
        for (let k = 0; k < 24; k++) {
            const aa = a + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 0.22;
            for (let s = 1.08; s < 1.9; s += 0.08) {
                const x = POND.x + Math.cos(aa) * POND.rx * s;
                const z = POND.z + Math.sin(aa) * POND.rz * s;
                if (!this.grid || this.grid.free(0, x, z)) {
                    return new THREE.Vector3(x, 0, z);
                }
            }
        }

        return new THREE.Vector3(POND.x, 0, POND.z + POND.rz * 1.4);
    }

    /** Điểm dưới nước cách bờ một chút theo hướng từ `p` vào tâm hồ. */
    private inside(p: THREE.Vector3, depth = 0.55): THREE.Vector3 {
        const a = Math.atan2(
            (p.z - POND.z) / POND.rz,
            (p.x - POND.x) / POND.rx,
        );
        const k = Math.max(0.25, 1 - depth / Math.min(POND.rx, POND.rz));

        return new THREE.Vector3(
            POND.x + Math.cos(a) * POND.rx * k,
            WATER_Y,
            POND.z + Math.sin(a) * POND.rz * k,
        );
    }

    /** Điểm đứng bờ gần nhất để nhảy xuống (cho người đi tới trước). */
    edgeFor(p: THREE.Vector3) {
        return this.shore(p);
    }

    plunge(a: Actor, o: PlungeOpts) {
        if (this.busy.has(a) || a.driver) {
            return false;
        }
        this.busy.add(a);
        a.seated = false;
        a.lying = null;
        const from = a.pos.clone();
        const entry = this.inside(from, o.how === 'jump' ? 0.9 : 0.6);
        const exitLand = this.shore(
            from.clone().add(new THREE.Vector3(rand(-2, 2), 0, rand(-2, 2))),
        );
        const exitWater = this.inside(exitLand, 0.25);
        const scared = o.how !== 'jump';
        const fly = o.how === 'jump' ? 0.75 : 0.55;
        const arc = o.how === 'jump' ? 0.9 : 0.35;
        let t = 0;
        let phase = 0;
        let swimT = 0;
        const swimD = Math.max(1.2, entry.distanceTo(exitWater) / 0.9);
        const setAnim = (an: AnimName, d: number, e?: Expr) => a.act(an, d, e);
        setAnim(
            scared ? 'flail' : 'jump',
            fly + 0.1,
            scared ? 'surprise' : 'joy',
        );
        a.faceTo(entry);
        a.driver = (dt: number) => {
            t += dt;
            switch (phase) {
                case 0: {
                    // bay vòng cung xuống nước
                    const k = Math.min(1, t / fly);
                    a.pos.lerpVectors(from, entry, k);
                    a.pos.y =
                        from.y +
                        (WATER_Y - from.y) * k +
                        Math.sin(k * Math.PI) * arc;
                    if (k >= 1) {
                        phase = 1;
                        t = 0;
                        this.fx.splash(entry.clone().setY(WATER_Y));
                        o.onSplash?.();
                        setAnim('flail', 1.4, 'surprise');
                    }
                    break;
                }
                case 1:
                    // quẫy tại chỗ
                    a.pos.y = WATER_Y - 0.02 + Math.sin(t * 9) * 0.03;
                    if (this.motion && Math.random() < dt * 6) {
                        this.fx.drop(
                            a.pos
                                .clone()
                                .add(
                                    new THREE.Vector3(
                                        rand(-0.3, 0.3),
                                        0.5,
                                        rand(-0.3, 0.3),
                                    ),
                                ),
                            rand(-1, 1),
                            rand(-1, 1),
                        );
                    }
                    if (t > 1.3) {
                        phase = 2;
                        t = 0;
                        a.faceTo(exitWater);
                        setAnim('swim', swimD + 0.2, scared ? 'sad' : 'joy');
                    }
                    break;
                case 2: {
                    // bơi chó vào bờ
                    swimT += dt;
                    const k = Math.min(1, swimT / swimD);
                    a.pos.lerpVectors(entry, exitWater, k);
                    a.pos.y = WATER_Y - 0.02 + Math.sin(t * 6) * 0.025;
                    a.faceTo(exitWater);
                    if (k >= 1) {
                        phase = 3;
                        t = 0;
                        a.faceTo(exitLand);
                        setAnim('climb', 1.15);
                    }
                    break;
                }
                case 3: {
                    // bám bờ trèo lên
                    const k = Math.min(1, t / 1.1);
                    a.pos.lerpVectors(exitWater, exitLand, k * k);
                    a.pos.y = WATER_Y + (0 - WATER_Y) * k;
                    if (k >= 1) {
                        phase = 4;
                        t = 0;
                        a.pos.copy(exitLand);
                        setAnim('shake', 1.3, scared ? 'sad' : 'joy');
                        for (let i = 0; i < 14; i++) {
                            const an = rand(0, Math.PI * 2);
                            this.fx.drop(
                                a.pos
                                    .clone()
                                    .add(
                                        new THREE.Vector3(0, rand(0.6, 1.3), 0),
                                    ),
                                Math.cos(an) * 2.2,
                                Math.sin(an) * 2.2,
                            );
                        }
                    }
                    break;
                }
                default:
                    // giũ nước xong
                    if (t > 1.3) {
                        this.busy.delete(a);
                        this.wet.set(a, this.now() + 9);
                        o.onDone?.();

                        return false;
                    }
            }

            return true;
        };

        return true;
    }

    /** Có đang ướt sũng không (để nói câu hợp cảnh). */
    isWet(a: Actor) {
        return (this.wet.get(a) ?? 0) > this.now() || this.busy.has(a);
    }

    update() {
        const now = this.now();
        if (!this.motion || now < this.dripAt) {
            return;
        }
        this.dripAt = now + 0.09;
        for (const [a, until] of this.wet) {
            if (now > until) {
                this.wet.delete(a);
                continue;
            }
            this.fx.drop(
                a.pos
                    .clone()
                    .add(
                        new THREE.Vector3(
                            rand(-0.25, 0.25),
                            rand(0.3, 1.2),
                            rand(-0.25, 0.25),
                        ),
                    ),
            );
        }
    }

    /** Ảnh chụp (rời trang khi đang dưới ao thì lúc quay lại đã lên bờ). */
    reset() {
        for (const a of this.busy) {
            a.driver = null;
            a.pos.copy(this.shore(a.pos));
        }
        this.busy.clear();
    }
}

// Hiệu ứng hạt: tim, zzz, mã nhị phân xanh, sóng radio, giấy màu, lấp lánh, khói ống khói.
import * as THREE from 'three';

import { C, FONT, Kit, rand, Shapes } from './util';

type Kind =
    | 'heart'
    | 'z'
    | 'zero'
    | 'one'
    | 'star'
    | 'note'
    | 'smoke'
    | 'puff'
    | 'anger'
    | 'drop'
    | 'cloud'
    | 'ball'
    | 'sweat';

interface P {
    obj: THREE.Object3D;
    mat: THREE.SpriteMaterial | THREE.MeshBasicMaterial;
    vel: THREE.Vector3;
    life: number;
    max: number;
    grow: number;
    spin: THREE.Vector3;
    size: number;
    gravity: number;
    fade: number;
    path?: {
        a: THREE.Vector3;
        b: THREE.Vector3;
        c: THREE.Vector3;
        t: number;
        speed: number;
    };
    kind: string;
    /** Bám theo một điểm (vd. sao quay quanh đầu). */
    follow?: {
        get: () => THREE.Vector3;
        r: number;
        w: number;
        ph: number;
        y: number;
    };
    /** Mây mưa: thời điểm rơi giọt kế tiếp. */
    rainAt?: number;
    onDone?: () => void;
}

export class Effects {
    readonly group = new THREE.Group();
    private tex = new Map<Kind, THREE.Texture>();
    private live: P[] = [];
    private confettiMats: THREE.MeshBasicMaterial[] = [];
    private ringGeo: THREE.BufferGeometry;
    private confGeo: THREE.BufferGeometry;
    enabled = true;

    constructor(
        private kit: Kit,
        shapes: Shapes,
    ) {
        const draw = (
            k: Kind,
            fn: (g: CanvasRenderingContext2D, s: number) => void,
        ) => {
            this.tex.set(k, kit.canvas(64, 64, (g, s) => fn(g, s)).texture);
        };
        draw('heart', (g, s) => {
            g.fillStyle = '#ff5b84';
            g.strokeStyle = '#ffffff';
            g.lineWidth = 5;
            g.beginPath();
            g.moveTo(s / 2, s * 0.84);
            g.bezierCurveTo(
                s * 0.04,
                s * 0.5,
                s * 0.18,
                s * 0.08,
                s / 2,
                s * 0.3,
            );
            g.bezierCurveTo(
                s * 0.82,
                s * 0.08,
                s * 0.96,
                s * 0.5,
                s / 2,
                s * 0.84,
            );
            g.stroke();
            g.fill();
        });
        const glyph = (k: Kind, ch: string, col: string, stroke = '#ffffff') =>
            draw(k, (g, s) => {
                g.font = `900 ${s * 0.78}px ${FONT}`;
                g.textAlign = 'center';
                g.textBaseline = 'middle';
                g.lineWidth = 7;
                g.strokeStyle = stroke;
                g.strokeText(ch, s / 2, s / 2 + 3);
                g.fillStyle = col;
                g.fillText(ch, s / 2, s / 2 + 3);
            });
        glyph('z', 'z', '#7a68c8');
        glyph('zero', '0', '#2bff88', '#0b3a22');
        glyph('one', '1', '#2bff88', '#0b3a22');
        glyph('note', '♪', '#ff7fd8');
        draw('star', (g, s) => {
            g.fillStyle = '#ffe066';
            g.beginPath();
            for (let i = 0; i < 10; i++) {
                const r = i % 2 ? s * 0.18 : s * 0.46;
                const a = (i / 10) * Math.PI * 2 - Math.PI / 2;
                g.lineTo(s / 2 + Math.cos(a) * r, s / 2 + Math.sin(a) * r);
            }
            g.fill();
        });
        draw('smoke', (g, s) => {
            const gr = g.createRadialGradient(
                s / 2,
                s / 2,
                0,
                s / 2,
                s / 2,
                s / 2,
            );
            gr.addColorStop(0, 'rgba(255,255,255,0.95)');
            gr.addColorStop(0.6, 'rgba(255,255,255,0.7)');
            gr.addColorStop(1, 'rgba(255,255,255,0)');
            g.fillStyle = gr;
            g.fillRect(0, 0, s, s);
        });
        this.tex.set('puff', this.tex.get('smoke')!);
        // 💢 dấu giận (bốn góc cong đỏ)
        draw('anger', (g, s) => {
            g.strokeStyle = '#ff3b5c';
            g.lineWidth = s * 0.11;
            g.lineCap = 'round';
            const c = s / 2;
            const o = s * 0.1;
            const r = s * 0.24;
            for (const [sx, sy] of [
                [-1, -1],
                [1, -1],
                [1, 1],
                [-1, 1],
            ]) {
                g.beginPath();
                g.moveTo(c + sx * o, c + sy * (o + r));
                g.quadraticCurveTo(
                    c + sx * o,
                    c + sy * o,
                    c + sx * (o + r),
                    c + sy * o,
                );
                g.stroke();
            }
        });
        draw('drop', (g, s) => {
            g.fillStyle = '#6fb8ff';
            g.beginPath();
            g.moveTo(s / 2, s * 0.12);
            g.quadraticCurveTo(s * 0.8, s * 0.55, s / 2, s * 0.86);
            g.quadraticCurveTo(s * 0.2, s * 0.55, s / 2, s * 0.12);
            g.fill();
        });
        draw('sweat', (g, s) => {
            g.fillStyle = '#9fd8ff';
            g.strokeStyle = '#ffffff';
            g.lineWidth = 4;
            g.beginPath();
            g.moveTo(s / 2, s * 0.1);
            g.quadraticCurveTo(s * 0.85, s * 0.6, s / 2, s * 0.9);
            g.quadraticCurveTo(s * 0.15, s * 0.6, s / 2, s * 0.1);
            g.stroke();
            g.fill();
        });
        draw('cloud', (g, s) => {
            g.fillStyle = '#8f97b8';
            for (const [x, y, r] of [
                [0.3, 0.58, 0.2],
                [0.5, 0.45, 0.26],
                [0.7, 0.58, 0.2],
                [0.5, 0.64, 0.2],
            ]) {
                g.beginPath();
                g.arc(x * s, y * s, r * s, 0, Math.PI * 2);
                g.fill();
            }
        });
        draw('ball', (g, s) => {
            g.fillStyle = '#ffffff';
            g.strokeStyle = '#b9b3cc';
            g.lineWidth = 4;
            g.beginPath();
            for (let i = 0; i < 9; i++) {
                const a = (i / 9) * Math.PI * 2;
                const r = s * (0.36 + (i % 2) * 0.06);
                g.lineTo(s / 2 + Math.cos(a) * r, s / 2 + Math.sin(a) * r);
            }
            g.closePath();
            g.fill();
            g.stroke();
            g.beginPath();
            g.moveTo(s * 0.35, s * 0.4);
            g.lineTo(s * 0.6, s * 0.55);
            g.lineTo(s * 0.45, s * 0.68);
            g.stroke();
        });
        for (const c of [
            C.pink,
            C.yellow,
            C.mint,
            C.blue,
            C.purple,
            C.orange,
            0xffffff,
        ]) {
            this.confettiMats.push(kit.basic(c, { side: THREE.DoubleSide }));
        }
        this.ringGeo = kit.geo(new THREE.TorusGeometry(0.35, 0.035, 6, 32));
        this.confGeo = shapes.plane(0.09, 0.14);
    }

    private sprite(
        kind: Kind,
        pos: THREE.Vector3,
        size: number,
        extra: Partial<P> = {},
    ): P {
        const mat = this.kit.mat(
            new THREE.SpriteMaterial({
                map: this.tex.get(kind),
                transparent: true,
                depthWrite: false,
                depthTest: kind !== 'zero' && kind !== 'one',
            }),
        );
        const s = new THREE.Sprite(mat);
        s.position.copy(pos);
        s.scale.setScalar(size);
        s.renderOrder = 5;
        s.raycast = () => undefined;
        this.group.add(s);
        const p: P = {
            obj: s,
            mat,
            vel: new THREE.Vector3(),
            life: 0,
            max: 2,
            grow: 0,
            spin: new THREE.Vector3(),
            size,
            gravity: 0,
            fade: 0.3,
            kind,
            ...extra,
        };
        this.live.push(p);

        return p;
    }

    hearts(pos: THREE.Vector3, n = 3) {
        if (!this.enabled) {
            return;
        }
        for (let i = 0; i < n; i++) {
            this.sprite(
                'heart',
                pos
                    .clone()
                    .add(
                        new THREE.Vector3(
                            rand(-0.25, 0.25),
                            rand(0, 0.2),
                            rand(-0.1, 0.1),
                        ),
                    ),
                0.28,
                {
                    vel: new THREE.Vector3(
                        rand(-0.15, 0.15),
                        rand(0.5, 0.8),
                        0,
                    ),
                    max: rand(1.4, 2.0),
                    grow: 0.15,
                    life: -i * 0.25,
                },
            );
        }
    }

    zzz(pos: THREE.Vector3) {
        if (!this.enabled) {
            return;
        }
        this.sprite('z', pos.clone(), 0.22, {
            vel: new THREE.Vector3(0.18, 0.35, 0),
            max: 2.4,
            grow: 0.25,
        });
    }

    notes(pos: THREE.Vector3) {
        if (!this.enabled) {
            return;
        }
        this.sprite('note', pos.clone(), 0.26, {
            vel: new THREE.Vector3(rand(-0.3, 0.3), 0.5, 0),
            max: 1.6,
            grow: 0.1,
        });
    }

    sparkle(pos: THREE.Vector3, n = 6) {
        if (!this.enabled) {
            return;
        }
        for (let i = 0; i < n; i++) {
            const a = (i / n) * Math.PI * 2;
            this.sprite('star', pos.clone(), 0.22, {
                vel: new THREE.Vector3(
                    Math.cos(a) * 0.9,
                    Math.sin(a) * 0.9 + 0.3,
                    0.2,
                ),
                max: 0.9,
                grow: -0.15,
                gravity: -0.6,
            });
        }
    }

    /** Sao quay vòng quanh đầu (bị cốc đầu). */
    dizzy(get: () => THREE.Vector3, d = 2.6) {
        if (!this.enabled) {
            return;
        }
        for (let i = 0; i < 4; i++) {
            this.sprite('star', get(), 0.16, {
                max: d,
                fade: 0.25,
                follow: {
                    get,
                    r: 0.32,
                    w: 6,
                    ph: (i / 4) * Math.PI * 2,
                    y: 0.05,
                },
            });
        }
    }

    /** Đám mây mưa nhỏ lơ lửng trên đầu (bị mắng, dỗi). */
    rainCloud(get: () => THREE.Vector3, d = 4.5) {
        if (!this.enabled) {
            return;
        }
        this.sprite('cloud', get(), 0.62, {
            max: d,
            fade: 0.2,
            follow: { get, r: 0, w: 0, ph: 0, y: 0.25 },
            rainAt: 0,
        });
    }

    /** Dấu giận 💢 bật lên cạnh đầu. */
    anger(pos: THREE.Vector3) {
        if (!this.enabled) {
            return;
        }
        this.sprite(
            'anger',
            pos.clone().add(new THREE.Vector3(0.25, 0.1, 0)),
            0.1,
            {
                max: 1.4,
                grow: 0.5,
                fade: 0.4,
            },
        );
    }

    /** Giọt mồ hôi (ngại, toát mồ hôi). */
    sweat(pos: THREE.Vector3) {
        if (!this.enabled) {
            return;
        }
        this.sprite(
            'sweat',
            pos.clone().add(new THREE.Vector3(-0.3, 0, 0)),
            0.2,
            {
                vel: new THREE.Vector3(0, -0.25, 0),
                max: 1.3,
            },
        );
    }

    /** Ném bóng giấy theo đường cong; trúng thì gọi `onHit`. */
    ball(a: THREE.Vector3, b: THREE.Vector3, dur: number, onHit?: () => void) {
        const c = a.clone().lerp(b, 0.5);
        c.y += 0.9;
        const p = this.sprite('ball', a.clone(), 0.2, {
            path: { a: a.clone(), b: b.clone(), c, t: 0, speed: 1 / dur },
            kind: 'ball',
            onDone: onHit,
        });
        if (!this.enabled) {
            p.path!.speed = 1 / 0.01;
        }
    }

    smoke(pos: THREE.Vector3) {
        if (!this.enabled) {
            return;
        }
        const p = this.sprite('smoke', pos.clone(), 0.6, {
            vel: new THREE.Vector3(0.35, 0.7, 0),
            max: 4.5,
            grow: 0.5,
            fade: 0.6,
        });
        (p.mat as THREE.SpriteMaterial).opacity = 0.85;
    }

    /** Hơi nước nhỏ (nồi, tách cà phê). */
    steam(pos: THREE.Vector3, size = 0.22) {
        if (!this.enabled) {
            return;
        }
        const p = this.sprite(
            'smoke',
            pos
                .clone()
                .add(
                    new THREE.Vector3(rand(-0.05, 0.05), 0, rand(-0.05, 0.05)),
                ),
            size,
            {
                vel: new THREE.Vector3(rand(-0.06, 0.06), 0.45, 0),
                max: 1.5,
                grow: 0.35,
                fade: 0.8,
            },
        );
        (p.mat as THREE.SpriteMaterial).opacity = 0.7;
    }

    puff(pos: THREE.Vector3) {
        if (!this.enabled) {
            return;
        }
        for (let i = 0; i < 5; i++) {
            this.sprite(
                'puff',
                pos
                    .clone()
                    .add(
                        new THREE.Vector3(
                            rand(-0.2, 0.2),
                            0.05,
                            rand(-0.2, 0.2),
                        ),
                    ),
                0.35,
                {
                    vel: new THREE.Vector3(
                        rand(-0.5, 0.5),
                        rand(0.2, 0.5),
                        rand(-0.3, 0.3),
                    ),
                    max: 0.8,
                    grow: 0.6,
                },
            );
        }
    }

    /** Bụi dưới chân khi chạy nước rút / ngã. */
    dust(pos: THREE.Vector3, n = 2) {
        if (!this.enabled || this.live.length > 260) {
            return;
        }
        for (let i = 0; i < n; i++) {
            const sp = this.sprite(
                'puff',
                pos
                    .clone()
                    .add(
                        new THREE.Vector3(
                            rand(-0.12, 0.12),
                            0.04,
                            rand(-0.12, 0.12),
                        ),
                    ),
                0.16,
                {
                    vel: new THREE.Vector3(
                        rand(-0.35, 0.35),
                        rand(0.15, 0.4),
                        rand(-0.35, 0.35),
                    ),
                    max: 0.55,
                    grow: 0.9,
                    fade: 0.6,
                },
            );
            sp.mat.color.setHex(0xe8d6b8);
        }
    }

    /** Một giọt nước rơi (người ướt sũng nhỏ nước). */
    drop(pos: THREE.Vector3, vx = 0, vz = 0) {
        if (!this.enabled || this.live.length > 300) {
            return;
        }
        this.sprite('drop', pos.clone(), 0.08, {
            vel: new THREE.Vector3(vx, rand(-0.3, 0.1), vz),
            gravity: 6,
            max: 0.5,
            fade: 0.3,
        });
    }

    /** Nước mắt văng hai bên (khóc nức nở). */
    tears(pos: THREE.Vector3, rot: number) {
        if (!this.enabled) {
            return;
        }
        const rx = Math.cos(rot);
        const rz = -Math.sin(rot);
        for (const sd of [-1, 1]) {
            this.sprite(
                'drop',
                pos
                    .clone()
                    .add(new THREE.Vector3(rx * sd * 0.16, 0, rz * sd * 0.16)),
                0.075,
                {
                    vel: new THREE.Vector3(rx * sd * 0.9, 1.1, rz * sd * 0.9),
                    gravity: 6,
                    max: 0.55,
                    fade: 0.3,
                },
            );
        }
    }

    /** Té nước tung toé (rơi xuống ao). */
    splash(pos: THREE.Vector3, n = 22) {
        if (!this.enabled) {
            return;
        }
        for (let i = 0; i < n; i++) {
            const a = (i / n) * Math.PI * 2 + rand(-0.2, 0.2);
            const sp = rand(1.0, 2.2);
            this.sprite(
                'drop',
                pos.clone().add(new THREE.Vector3(0, 0.05, 0)),
                rand(0.09, 0.15),
                {
                    vel: new THREE.Vector3(
                        Math.cos(a) * sp,
                        rand(2.2, 4.2),
                        Math.sin(a) * sp,
                    ),
                    gravity: 9,
                    max: 0.9,
                    fade: 0.3,
                },
            );
        }
        for (let i = 0; i < 4; i++) {
            const pf = this.sprite(
                'puff',
                pos
                    .clone()
                    .add(
                        new THREE.Vector3(
                            rand(-0.3, 0.3),
                            0.1,
                            rand(-0.3, 0.3),
                        ),
                    ),
                0.4,
                {
                    vel: new THREE.Vector3(0, rand(0.3, 0.6), 0),
                    max: 0.7,
                    grow: 1.2,
                    fade: 0.6,
                },
            );
            pf.mat.color.setHex(0xdff3ff);
        }
    }

    confetti(pos: THREE.Vector3, n = 60, spread = 1) {
        if (!this.enabled) {
            return;
        }
        for (let i = 0; i < n; i++) {
            const mat = this.confettiMats[i % this.confettiMats.length];
            const m = new THREE.Mesh(this.confGeo, mat);
            m.position
                .copy(pos)
                .add(
                    new THREE.Vector3(
                        rand(-0.3, 0.3) * spread,
                        0,
                        rand(-0.3, 0.3) * spread,
                    ),
                );
            m.rotation.set(rand(0, 6), rand(0, 6), rand(0, 6));
            m.raycast = () => undefined;
            this.group.add(m);
            const a = rand(0, Math.PI * 2);
            const v = rand(1.2, 2.6) * spread;
            this.live.push({
                obj: m,
                mat,
                vel: new THREE.Vector3(
                    Math.cos(a) * v * 0.6,
                    rand(2.8, 4.6),
                    Math.sin(a) * v * 0.6,
                ),
                life: -rand(0, 0.15),
                max: rand(2.2, 3.2),
                grow: 0,
                spin: new THREE.Vector3(rand(-9, 9), rand(-9, 9), rand(-9, 9)),
                size: 1,
                gravity: 5.5,
                fade: 0,
                kind: 'confetti',
            });
        }
    }

    /** Tín hiệu "hack": chuỗi số 0/1 xanh + vòng sóng bay theo vòng cung từ a tới b trong `dur` giây. */
    signal(a: THREE.Vector3, b: THREE.Vector3, dur = 1.8) {
        if (!this.enabled) {
            return;
        }
        const c = a.clone().add(b).multiplyScalar(0.5);
        c.y += 1.4;
        c.z += 0.6;
        for (let i = 0; i < 26; i++) {
            const p = this.sprite(
                i % 2 ? 'one' : 'zero',
                a.clone(),
                rand(0.16, 0.26),
                { max: 99 },
            );
            p.path = {
                a: a
                    .clone()
                    .add(
                        new THREE.Vector3(
                            rand(-0.15, 0.15),
                            rand(-0.1, 0.2),
                            0,
                        ),
                    ),
                b: b
                    .clone()
                    .add(
                        new THREE.Vector3(rand(-0.2, 0.2), rand(-0.2, 0.2), 0),
                    ),
                c: c
                    .clone()
                    .add(
                        new THREE.Vector3(0, rand(-0.4, 0.4), rand(-0.3, 0.3)),
                    ),
                t: -i * 0.07,
                speed: 1 / dur,
            };
        }
        for (let i = 0; i < 5; i++) {
            const mat = this.kit.basic(0x2bff88, {
                transparent: true,
                opacity: 0.9,
                depthWrite: false,
                blending: THREE.AdditiveBlending,
            });
            const m = new THREE.Mesh(this.ringGeo, mat);
            m.position.copy(a);
            m.raycast = () => undefined;
            this.group.add(m);
            this.live.push({
                obj: m,
                mat,
                vel: new THREE.Vector3(),
                life: 0,
                max: 99,
                grow: 0,
                spin: new THREE.Vector3(),
                size: 1,
                gravity: 0,
                fade: 0,
                kind: 'ring',
                path: {
                    a: a.clone(),
                    b: b.clone(),
                    c: c.clone(),
                    t: -i * 0.28,
                    speed: 1 / dur,
                },
            });
        }
    }

    update(dt: number) {
        const keep: P[] = [];
        const tmp = new THREE.Vector3();
        for (const p of this.live) {
            p.life += dt;
            if (p.life < 0) {
                p.obj.visible = false;
                keep.push(p);
                continue;
            }
            p.obj.visible = true;
            let done = false;
            if (p.path) {
                const q = p.path;
                q.t += dt * q.speed;
                if (q.t < 0) {
                    p.obj.visible = false;
                    keep.push(p);
                    continue;
                }
                const t = Math.min(1, q.t);
                const u = 1 - t;
                tmp.set(0, 0, 0)
                    .addScaledVector(q.a, u * u)
                    .addScaledVector(q.c, 2 * u * t)
                    .addScaledVector(q.b, t * t);
                p.obj.position.copy(tmp);
                if (p.kind === 'ring') {
                    // vòng sóng quay mặt theo hướng bay, to dần
                    const d = q.b
                        .clone()
                        .sub(q.a)
                        .multiplyScalar(2 * t)
                        .add(
                            q.c
                                .clone()
                                .sub(q.a)
                                .multiplyScalar(2 * u),
                        )
                        .normalize();
                    p.obj.quaternion.setFromUnitVectors(
                        new THREE.Vector3(0, 0, 1),
                        d,
                    );
                    p.obj.scale.setScalar(0.6 + t * 1.6);
                    p.mat.opacity = 0.9 * (1 - t * 0.7);
                }
                if (q.t >= 1) {
                    done = true;
                }
            } else if (p.follow) {
                const f = p.follow;
                const c = f.get();
                const a = f.ph + p.life * f.w;
                p.obj.position.set(
                    c.x + Math.cos(a) * f.r,
                    c.y + f.y + Math.sin(a * 2) * 0.03,
                    c.z + Math.sin(a) * f.r,
                );
                if (
                    p.rainAt !== undefined &&
                    p.life >= p.rainAt &&
                    p.life < p.max - 0.6
                ) {
                    p.rainAt = p.life + 0.18;
                    this.sprite(
                        'drop',
                        p.obj.position
                            .clone()
                            .add(
                                new THREE.Vector3(
                                    rand(-0.2, 0.2),
                                    -0.12,
                                    rand(-0.08, 0.08),
                                ),
                            ),
                        0.1,
                        {
                            vel: new THREE.Vector3(0, -1.6, 0),
                            max: 0.45,
                            fade: 0.3,
                        },
                    );
                }
                const fadeStart = p.max * (1 - Math.max(0.25, p.fade));
                p.mat.opacity =
                    p.life > fadeStart
                        ? 1 - (p.life - fadeStart) / (p.max - fadeStart)
                        : 1;
                done = p.life >= p.max;
            } else {
                p.vel.y -= p.gravity * dt;
                if (p.kind === 'confetti') {
                    p.vel.multiplyScalar(1 - dt * 1.4);
                    p.vel.y = Math.max(p.vel.y, -0.9);
                    p.obj.rotation.x += p.spin.x * dt;
                    p.obj.rotation.y += p.spin.y * dt;
                    p.obj.rotation.z += p.spin.z * dt;
                }
                p.obj.position.addScaledVector(p.vel, dt);
                if (p.grow) {
                    const s = Math.max(0.01, p.size + p.grow * p.life);
                    p.obj.scale.setScalar(s);
                }
                const fadeStart = p.max * (1 - Math.max(0.25, p.fade));
                if (p.mat.transparent || p.obj instanceof THREE.Sprite) {
                    p.mat.transparent = true;
                    const base = p.kind === 'smoke' ? 0.85 : 1;
                    p.mat.opacity =
                        p.life > fadeStart
                            ? base *
                              (1 - (p.life - fadeStart) / (p.max - fadeStart))
                            : base;
                }
                done = p.life >= p.max;
            }
            if (done) {
                p.onDone?.();
                this.group.remove(p.obj);
                if (p.kind !== 'confetti') {
                    p.mat.dispose();
                    this.kit.mats.delete(p.mat);
                }
            } else {
                keep.push(p);
            }
        }
        this.live = keep;
    }

    get count() {
        return this.live.length;
    }
}

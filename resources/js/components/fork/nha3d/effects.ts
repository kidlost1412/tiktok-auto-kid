// Hiệu ứng hạt: tim, zzz, mã nhị phân xanh, sóng radio, giấy màu, lấp lánh, khói ống khói.
import * as THREE from 'three';

import { C, FONT, Kit, rand, Shapes } from './util';

type Kind = 'heart' | 'z' | 'zero' | 'one' | 'star' | 'note' | 'smoke' | 'puff';

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

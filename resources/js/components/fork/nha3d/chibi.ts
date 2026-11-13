// Nhân vật chibi dựng hoàn toàn bằng hình khối: đầu to tròn, thân nhỏ, mặt vẽ bằng canvas (chớp mắt, đổi biểu cảm),
// dáng điệu tính bằng code (thở, gõ phím, đi, chạy, cổ vũ, ngáp, ngủ…).
import * as THREE from 'three';

import {
    C,
    type CanvasTex,
    clamp,
    damp,
    Kit,
    outlineMaterial,
    Shapes,
} from './util';

export type Expr =
    | 'happy'
    | 'joy'
    | 'focus'
    | 'sleepy'
    | 'annoyed'
    | 'surprise'
    | 'cocky'
    | 'love'
    | 'sad';

export type HairStyle =
    | 'bob'
    | 'long'
    | 'spiky'
    | 'short'
    | 'bun'
    | 'pony'
    | 'messy';

export interface ChibiSpec {
    skin?: number;
    shirt: number;
    sleeve?: number;
    pants: number;
    shoes: number;
    hair: number;
    hairStyle: HairStyle;
    hat?: {
        kind: 'beret' | 'cap' | 'postcap' | 'headband' | 'hood';
        color: number;
        color2?: number;
    };
    glasses?: number;
    headphones?: number;
    mustache?: boolean;
    brows?: 'strict' | 'soft' | 'none';
    bowtie?: number;
    apron?: number;
    satchel?: number;
    scarf?: number;
    lashes?: boolean;
    eye?: string;
    collar?: number;
    /** Kiểu áo (mặc định áo thun). */
    top?: 'tee' | 'hoodie' | 'shirt' | 'sweater';
    /** Kiểu quần/váy (mặc định quần dài). */
    bottom?: 'pants' | 'shorts' | 'skirt' | 'dress';
    /** Ba lô sau lưng. */
    backpack?: number;
    /** Dáng nữ: vai hẹp hơn, hông tròn hơn, mi cong. */
    girl?: boolean;
}

export const HEAD_R = 0.36;
export const HEAD_Y = 1.02; // tâm đầu khi đứng
export const SEAT_HIPS = 0.5;

/** Mặt vẽ trên canvas, dán lên chỏm cầu phía trước đầu. */
export class Face {
    expr: Expr = 'happy';
    blink = false;
    talk = 0; // 0..1 miệng mở khi nói

    constructor(
        private tex: CanvasTex,
        private spec: ChibiSpec,
    ) {
        this.draw();
    }

    set(expr: Expr, blink = this.blink, talk = this.talk) {
        const t = Math.round(talk * 2) / 2;
        if (expr === this.expr && blink === this.blink && t === this.talk) {
            return;
        }
        this.expr = expr;
        this.blink = blink;
        this.talk = t;
        this.draw();
    }

    private draw() {
        const s = this.spec;
        this.tex.redraw((g, w, h) => {
            const ink = s.eye ?? '#3a2c55';
            const ey = h * 0.53;
            const ex = 30;
            const cx = w / 2;
            const e = this.expr;
            g.lineCap = 'round';
            g.lineJoin = 'round';
            // má hồng
            g.fillStyle = 'rgba(255,128,150,0.42)';
            for (const sx of [-1, 1]) {
                g.beginPath();
                g.ellipse(cx + sx * 46, ey + 20, 13, 7, 0, 0, Math.PI * 2);
                g.fill();
            }
            if (e === 'love') {
                g.fillStyle = 'rgba(255,90,130,0.55)';
                for (const sx of [-1, 1]) {
                    g.beginPath();
                    g.ellipse(cx + sx * 46, ey + 20, 15, 8, 0, 0, Math.PI * 2);
                    g.fill();
                }
            }
            // mắt
            const closed = this.blink || e === 'sleepy';
            g.strokeStyle = ink;
            g.fillStyle = ink;
            for (const sx of [-1, 1]) {
                const x = cx + sx * ex;
                if (closed) {
                    g.lineWidth = 4.5;
                    g.beginPath();
                    if (e === 'sleepy') {
                        g.arc(x, ey - 2, 9, 0.15 * Math.PI, 0.85 * Math.PI);
                    } else {
                        g.moveTo(x - 9, ey + 1);
                        g.quadraticCurveTo(x, ey + 6, x + 9, ey + 1);
                    }
                    g.stroke();
                } else if (e === 'joy') {
                    g.lineWidth = 5;
                    g.beginPath();
                    g.moveTo(x - 9, ey + 3);
                    g.quadraticCurveTo(x, ey - 10, x + 9, ey + 3);
                    g.stroke();
                } else if (e === 'love') {
                    g.fillStyle = '#ff5b84';
                    g.beginPath();
                    g.moveTo(x, ey + 9);
                    g.bezierCurveTo(x - 14, ey - 1, x - 8, ey - 13, x, ey - 5);
                    g.bezierCurveTo(x + 8, ey - 13, x + 14, ey - 1, x, ey + 9);
                    g.fill();
                    g.fillStyle = ink;
                } else {
                    const ry =
                        e === 'surprise'
                            ? 13
                            : e === 'focus' || e === 'cocky'
                              ? 9
                              : 12;
                    g.beginPath();
                    g.ellipse(x, ey, 8.5, ry, 0, 0, Math.PI * 2);
                    g.fill();
                    g.fillStyle = '#ffffff';
                    g.beginPath();
                    g.arc(x + 3, ey - 4.5, 3.4, 0, Math.PI * 2);
                    g.fill();
                    g.beginPath();
                    g.arc(x - 2.6, ey + 4, 1.7, 0, Math.PI * 2);
                    g.fill();
                    g.fillStyle = ink;
                    if (e === 'focus' || e === 'cocky' || e === 'annoyed') {
                        // mí mắt hạ xuống
                        g.fillStyle =
                            '#' +
                            (s.skin ?? C.skin).toString(16).padStart(6, '0');
                        const lid = e === 'cocky' ? 7 : 5;
                        g.fillRect(x - 11, ey - 16, 22, lid + 4);
                        g.strokeStyle = ink;
                        g.lineWidth = 3;
                        g.beginPath();
                        g.moveTo(x - 10, ey - 12 + lid + 2);
                        g.lineTo(x + 10, ey - 12 + lid + 2);
                        g.stroke();
                        g.fillStyle = ink;
                    }
                    if (s.lashes) {
                        g.lineWidth = 2.5;
                        g.beginPath();
                        g.moveTo(x + sx * 7, ey - 8);
                        g.lineTo(x + sx * 12, ey - 12);
                        g.stroke();
                    }
                }
            }
            // lông mày
            const brows = e === 'annoyed' ? 'strict' : (s.brows ?? 'none');
            if (brows !== 'none' || e === 'sad' || e === 'surprise') {
                g.lineWidth = 4;
                g.strokeStyle = ink;
                for (const sx of [-1, 1]) {
                    const x = cx + sx * ex;
                    g.beginPath();
                    if (e === 'sad') {
                        g.moveTo(x - sx * 10, ey - 18);
                        g.lineTo(x + sx * 8, ey - 23);
                    } else if (e === 'surprise') {
                        g.arc(x, ey - 14, 9, 1.15 * Math.PI, 1.85 * Math.PI);
                    } else if (brows === 'strict') {
                        g.moveTo(x + sx * 11, ey - 23);
                        g.lineTo(x - sx * 8, ey - 16);
                    } else {
                        g.arc(x, ey - 12, 10, 1.2 * Math.PI, 1.8 * Math.PI);
                    }
                    g.stroke();
                }
            }
            // ria mép
            if (s.mustache) {
                g.fillStyle = '#7a4a2c';
                for (const sx of [-1, 1]) {
                    g.beginPath();
                    g.ellipse(
                        cx + sx * 9,
                        ey + 22,
                        11,
                        5,
                        sx * 0.25,
                        0,
                        Math.PI * 2,
                    );
                    g.fill();
                }
            }
            // miệng
            const my = ey + (s.mustache ? 32 : 26);
            g.strokeStyle = ink;
            g.lineWidth = 3.5;
            const open = this.talk > 0 || e === 'joy' || e === 'surprise';
            if (e === 'sleepy') {
                g.beginPath();
                g.ellipse(cx, my, 4, 3, 0, 0, Math.PI * 2);
                g.stroke();
            } else if (e === 'annoyed' || e === 'sad') {
                g.beginPath();
                g.moveTo(cx - 8, my + 3);
                g.quadraticCurveTo(cx, my - 4, cx + 8, my + 3);
                g.stroke();
            } else if (open) {
                const oh = e === 'surprise' ? 9 : 5 + this.talk * 5;
                g.fillStyle = '#c4466a';
                g.beginPath();
                if (e === 'surprise') {
                    g.ellipse(cx, my + 2, 6, oh, 0, 0, Math.PI * 2);
                } else {
                    g.moveTo(cx - 10, my - 1);
                    g.quadraticCurveTo(cx, my + oh * 2.2, cx + 10, my - 1);
                    g.closePath();
                }
                g.fill();
                g.stroke();
            } else if (e === 'focus') {
                g.beginPath();
                g.moveTo(cx - 6, my + 1);
                g.lineTo(cx + 6, my + 1);
                g.stroke();
            } else if (e === 'cocky') {
                g.beginPath();
                g.moveTo(cx - 8, my + 1);
                g.quadraticCurveTo(cx + 2, my + 6, cx + 10, my - 3);
                g.stroke();
            } else {
                g.beginPath();
                g.moveTo(cx - 8, my - 1);
                g.quadraticCurveTo(cx, my + 7, cx + 8, my - 1);
                g.stroke();
            }
        });
    }
}

/** Khung xương đơn giản của một chibi + vật liệu riêng để làm sáng viền khi rê chuột. */
export class Chibi {
    readonly root = new THREE.Group();
    readonly body = new THREE.Group(); // nhún/nhảy
    readonly hips = new THREE.Group();
    readonly torso = new THREE.Group();
    readonly head = new THREE.Group();
    readonly armL = new THREE.Group();
    readonly armR = new THREE.Group();
    readonly legL = new THREE.Group();
    readonly legR = new THREE.Group();
    /** Ống chân (xoay ở đầu gối). */
    readonly shinL = new THREE.Group();
    readonly shinR = new THREE.Group();
    readonly hold = new THREE.Group(); // vật cầm trước ngực
    readonly handR = new THREE.Group(); // vật cầm tay phải
    readonly face: Face;
    readonly outline: THREE.MeshBasicMaterial;
    readonly meshes: THREE.Mesh[] = [];
    private matCache = new Map<number, THREE.MeshToonMaterial>();

    constructor(
        private kit: Kit,
        private shapes: Shapes,
        readonly spec: ChibiSpec,
        readonly scale = 1,
    ) {
        this.outline = outlineMaterial(kit, C.ink, 0.016);
        const skin = spec.skin ?? C.skin;
        const S = shapes;
        this.root.add(this.body);
        this.body.add(this.hips);
        this.hips.position.y = 0.3;
        this.hips.add(this.torso);

        // chân
        for (const [leg, shin, sx] of [
            [this.legL, this.shinL, 1],
            [this.legR, this.shinR, -1],
        ] as const) {
            leg.position.set(sx * 0.085, 0.02, 0);
            this.hips.add(leg);
            shin.position.y = -0.12;
            leg.add(shin);
            const bare =
                spec.bottom === 'shorts' ||
                spec.bottom === 'skirt' ||
                spec.bottom === 'dress';
            // đùi + ống chân (gối ở y −0.12) — gập được khi ngồi
            this.part(
                S.capsule(0.068, 0.06, 4, 10),
                bare ? skin : spec.pants,
                leg,
                { y: -0.06 },
            );
            this.part(
                S.capsule(0.066, 0.07, 4, 10),
                bare ? skin : spec.pants,
                shin,
                { y: -0.04 },
            );
            if (spec.bottom === 'shorts') {
                this.part(S.cyl(0.085, 0.08, 0.1, 14), spec.pants, leg, {
                    y: -0.03,
                });
            }
            this.part(S.sphere(0.1, 14, 10), spec.shoes, shin, {
                y: -0.125,
                z: 0.035,
                sx: 0.85,
                sy: 0.6,
                sz: 1.2,
            });
            this.part(
                S.cyl(0.082, 0.085, 0.025, 14),
                0xfffaf2,
                shin,
                { y: -0.175, z: 0.04, sz: 1.35 },
                false,
            );
            this.part(
                S.torus(0.066, 0.016, 6, 14),
                0xffffff,
                shin,
                { y: -0.08, rx: Math.PI / 2 },
                false,
            );
        }
        // quần/hông
        this.part(S.sphere(0.18, 18, 12), spec.pants, this.hips, {
            y: 0.03,
            sx: spec.girl ? 1.1 : 1.05,
            sy: 0.6,
            sz: 0.92,
        });
        if (spec.bottom === 'skirt' || spec.bottom === 'dress') {
            // váy xoè
            this.part(S.cyl(0.19, 0.27, 0.22, 22), spec.pants, this.hips, {
                y: -0.04,
                sz: 0.9,
            });
            this.part(
                S.torus(0.27, 0.018, 6, 26),
                new THREE.Color(spec.pants).multiplyScalar(0.84).getHex(),
                this.hips,
                { y: -0.15, rx: Math.PI / 2, sy: 0.9 },
                false,
            );
        }
        // thân
        this.part(S.capsule(0.17, 0.14, 6, 16), spec.shirt, this.torso, {
            y: 0.19,
            sx: spec.girl ? 0.98 : 1.06,
            sz: 0.9,
        });
        const shade = new THREE.Color(spec.shirt).multiplyScalar(0.86).getHex();
        this.part(
            S.torus(0.172, 0.028, 8, 22),
            shade,
            this.torso,
            { y: 0.06, rx: Math.PI / 2, sx: 1.06, sy: 0.9 },
            false,
        );
        this.part(
            S.torus(0.1, 0.03, 8, 18),
            spec.collar ?? 0xffffff,
            this.torso,
            { y: 0.37, z: 0.01, rx: Math.PI / 2 - 0.25 },
            false,
        );
        for (let k = 0; k < 2; k++) {
            this.part(
                S.sphere(0.018, 6, 5),
                shade,
                this.torso,
                { y: 0.27 - k * 0.09, z: 0.16 - k * 0.004 },
                false,
            );
        }
        if (spec.bottom !== 'dress') {
            this.part(
                S.torus(0.17, 0.022, 6, 22),
                0x5a4a78,
                this.hips,
                { y: 0.09, rx: Math.PI / 2, sx: 1.05, sy: 0.92 },
                false,
            );
        }
        if (spec.top === 'hoodie') {
            // mũ trùm sau gáy + túi trước bụng + dây rút
            this.part(S.sphere(0.15, 16, 10), shade, this.torso, {
                y: 0.4,
                z: -0.12,
                sx: 1.25,
                sy: 0.7,
                sz: 0.8,
            });
            this.part(
                S.rbox(0.2, 0.09, 0.04, 0.02),
                shade,
                this.torso,
                { y: 0.1, z: 0.155 },
                false,
            );
            for (const sx of [-1, 1]) {
                this.part(
                    S.cyl(0.008, 0.008, 0.1, 5),
                    0xffffff,
                    this.torso,
                    { x: sx * 0.04, y: 0.3, z: 0.165 },
                    false,
                );
            }
        } else if (spec.top === 'shirt') {
            // cổ áo sơ mi hai vạt
            for (const sx of [-1, 1]) {
                this.part(
                    S.box(0.09, 0.05, 0.02),
                    spec.collar ?? 0xffffff,
                    this.torso,
                    { x: sx * 0.05, y: 0.36, z: 0.12, rz: sx * 0.5, rx: -0.3 },
                    false,
                );
            }
        } else if (spec.top === 'sweater') {
            const band = new THREE.Color(spec.shirt)
                .lerp(new THREE.Color(0xffffff), 0.45)
                .getHex();
            for (const y of [0.13, 0.24]) {
                this.part(
                    S.torus(0.168, 0.02, 6, 22),
                    band,
                    this.torso,
                    {
                        y,
                        rx: Math.PI / 2,
                        sx: spec.girl ? 0.98 : 1.06,
                        sy: 0.9,
                    },
                    false,
                );
            }
        }
        if (spec.backpack) {
            this.part(
                S.rbox(0.26, 0.28, 0.12, 0.05),
                spec.backpack,
                this.torso,
                {
                    y: 0.2,
                    z: -0.2,
                },
            );
            this.part(
                S.rbox(0.18, 0.1, 0.05, 0.02),
                new THREE.Color(spec.backpack).multiplyScalar(0.85).getHex(),
                this.torso,
                { y: 0.12, z: -0.27 },
                false,
            );
            for (const sx of [-1, 1]) {
                this.part(
                    S.box(0.035, 0.24, 0.02),
                    new THREE.Color(spec.backpack).multiplyScalar(0.8).getHex(),
                    this.torso,
                    { x: sx * 0.09, y: 0.24, z: 0.155, rx: -0.15 },
                    false,
                );
            }
        }
        if (spec.apron) {
            this.part(
                S.rbox(0.26, 0.26, 0.04, 0.02),
                spec.apron,
                this.torso,
                { y: 0.14, z: 0.15 },
                false,
            );
            this.part(
                S.box(0.2, 0.05, 0.02),
                spec.apron,
                this.torso,
                { y: 0.3, z: 0.155 },
                false,
            );
        }
        if (spec.bowtie) {
            this.part(
                S.cone(0.045, 0.08, 8),
                spec.bowtie,
                this.torso,
                { x: 0.035, y: 0.38, z: 0.13, rz: Math.PI / 2 },
                false,
            );
            this.part(
                S.cone(0.045, 0.08, 8),
                spec.bowtie,
                this.torso,
                { x: -0.035, y: 0.38, z: 0.13, rz: -Math.PI / 2 },
                false,
            );
        }
        if (spec.scarf) {
            this.part(
                S.torus(0.12, 0.045, 8, 18),
                spec.scarf,
                this.torso,
                { y: 0.4, rx: Math.PI / 2, sy: 0.9 },
                false,
            );
        }
        if (spec.satchel) {
            this.part(
                S.torus(0.2, 0.02, 6, 24),
                0x8a5a3a,
                this.torso,
                { y: 0.2, rx: -Math.PI / 2, ry: 0.6 },
                false,
            );
            this.part(S.rbox(0.1, 0.17, 0.17, 0.03), spec.satchel, this.torso, {
                x: 0.21,
                y: 0.04,
                z: 0.02,
            });
        }
        // tay
        for (const [arm, sx] of [
            [this.armL, 1],
            [this.armR, -1],
        ] as const) {
            arm.position.set(sx * 0.2, 0.33, 0);
            this.torso.add(arm);
            this.part(
                S.capsule(0.056, 0.12, 4, 10),
                spec.sleeve ?? spec.shirt,
                arm,
                { y: -0.1 },
            );
            this.part(
                S.torus(0.052, 0.014, 6, 12),
                new THREE.Color(spec.sleeve ?? spec.shirt)
                    .multiplyScalar(0.86)
                    .getHex(),
                arm,
                { y: -0.17, rx: Math.PI / 2 },
                false,
            );
            this.part(S.sphere(0.062, 12, 10), skin, arm, { y: -0.22 });
            this.part(
                S.sphere(0.026, 6, 5),
                skin,
                arm,
                { x: sx * -0.035, y: -0.2, z: 0.04 },
                false,
            );
        }
        this.armR.add(this.handR);
        this.handR.position.set(0, -0.26, 0.02);
        this.torso.add(this.hold);
        this.hold.position.set(0, 0.16, 0.26);

        // đầu
        this.torso.add(this.head);
        this.head.position.y = 0.42;
        const R = HEAD_R;
        this.part(S.sphere(R, 28, 20), skin, this.head, { y: 0.3 });
        for (const sx of [-1, 1]) {
            this.part(S.sphere(0.07, 10, 8), skin, this.head, {
                x: sx * R * 0.98,
                y: 0.28,
                sx: 0.6,
            });
        }
        // mặt
        const faceTex = kit.canvas(256, 144, () => undefined);
        this.faceTex = faceTex.texture;
        this.face = new Face(faceTex, spec);
        const faceGeo = kit.geo(
            new THREE.SphereGeometry(
                R * 1.004,
                28,
                16,
                Math.PI / 2 - Math.PI * 0.45,
                Math.PI * 0.9,
                Math.PI * 0.3,
                Math.PI * 0.5,
            ),
        );
        const faceMesh = new THREE.Mesh(
            faceGeo,
            kit.mat(
                new THREE.MeshToonMaterial({
                    map: faceTex.texture,
                    transparent: true,
                    gradientMap: kit.gradient,
                    depthWrite: false,
                }),
            ),
        );
        faceMesh.position.y = 0.3;
        this.faceMesh = faceMesh;
        faceMesh.renderOrder = 2;
        this.head.add(faceMesh);
        this.hair(spec, R);
        if (spec.glasses !== undefined) {
            this.glasses(spec.glasses, R);
        }
        if (spec.headphones !== undefined) {
            this.part(
                S.torus(R * 1.12, 0.03, 8, 24, Math.PI),
                spec.headphones,
                this.head,
                { y: 0.3 + 0.02 },
            );
            for (const sx of [-1, 1]) {
                this.part(
                    S.cyl(0.1, 0.1, 0.08, 16),
                    spec.headphones,
                    this.head,
                    { x: sx * R * 1.08, y: 0.29, rz: Math.PI / 2 },
                );
                this.part(
                    S.cyl(0.07, 0.07, 0.085, 14),
                    0xff8fd8,
                    this.head,
                    { x: sx * R * 1.1, y: 0.29, rz: Math.PI / 2 },
                    false,
                );
            }
        }
        this.root.scale.setScalar(scale);
        this.meshes.forEach((m) => (m.userData.actorPart = true));
    }

    private faceTex: THREE.Texture | null = null;
    private faceMesh: THREE.Mesh | null = null;

    /** Gỡ khỏi cảnh và giải phóng vật liệu/ảnh riêng của nhân vật này (hình khối dùng chung thì giữ). */
    dispose() {
        this.root.parent?.remove(this.root);
        for (const m of this.matCache.values()) {
            m.dispose();
            this.kit.mats.delete(m);
        }
        this.matCache.clear();
        this.outline.dispose();
        this.kit.mats.delete(this.outline);
        if (this.faceMesh) {
            const fm = this.faceMesh.material as THREE.Material;
            fm.dispose();
            this.kit.mats.delete(fm);
            this.faceMesh.geometry.dispose();
            this.kit.geos.delete(this.faceMesh.geometry);
        }
        if (this.faceTex) {
            this.faceTex.dispose();
            this.kit.texs.delete(this.faceTex);
        }
    }

    material(color: number): THREE.MeshToonMaterial {
        let m = this.matCache.get(color);
        if (!m) {
            m = this.kit.toonOwn(color);
            this.matCache.set(color, m);
        }

        return m;
    }

    /** Thêm một khối; `outline` = có viền mực. */
    part(
        geo: THREE.BufferGeometry,
        color: number,
        parent: THREE.Object3D,
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
        outline = true,
    ): THREE.Mesh {
        const m = new THREE.Mesh(geo, this.material(color));
        m.position.set(p.x ?? 0, p.y ?? 0, p.z ?? 0);
        m.rotation.set(p.rx ?? 0, p.ry ?? 0, p.rz ?? 0);
        m.scale.set(p.sx ?? 1, p.sy ?? 1, p.sz ?? 1);
        parent.add(m);
        this.meshes.push(m);
        if (outline) {
            const o = new THREE.Mesh(geo, this.outline);
            o.raycast = () => undefined;
            m.add(o);
        }

        return m;
    }

    private hair(s: ChibiSpec, R: number) {
        const S = this.shapes;
        const hc = s.hair;
        const top = this.kit.geo(
            new THREE.SphereGeometry(
                R * 1.07,
                26,
                14,
                0,
                Math.PI * 2,
                0,
                Math.PI * 0.42,
            ),
        );
        const hy = 0.3;
        const hood = s.hat?.kind === 'hood';
        // phần tóc sau gáy + đỉnh
        this.part(S.sphere(R * 1.045, 24, 18), hc, this.head, {
            y: hy + 0.01,
            z: -0.07,
        });
        this.part(top, hc, this.head, { y: hy + 0.01, rx: -0.42 });
        // mái
        const bangs =
            s.hairStyle === 'spiky' ? 0 : s.hairStyle === 'short' ? 2 : 3;
        for (let i = 0; i < bangs; i++) {
            const a = (i - (bangs - 1) / 2) * 0.42;
            this.part(
                S.sphere(0.13, 12, 10),
                hc,
                this.head,
                {
                    x: Math.sin(a) * R * 0.8,
                    y: hy + R * 0.62,
                    z: Math.cos(a) * R * 0.66,
                    sx: 1.25,
                    sy: 0.6,
                    sz: 0.7,
                    rz: -a * 0.6,
                    rx: 0.35,
                },
                false,
            );
        }
        if (s.hairStyle !== 'spiky' && !s.hat) {
            const ah = this.part(
                S.cone(0.035, 0.2, 6),
                hc,
                this.head,
                { x: 0.04, y: hy + R * 1.08, z: 0.02, rz: -0.5, rx: -0.3 },
                false,
            );
            void ah;
        }
        if (
            s.hairStyle === 'short' ||
            s.hairStyle === 'messy' ||
            s.hairStyle === 'spiky'
        ) {
            for (const sx of [-1, 1]) {
                this.part(
                    S.cone(0.06, 0.16, 6),
                    hc,
                    this.head,
                    {
                        x: sx * R * 0.92,
                        y: hy - 0.05,
                        z: 0.08,
                        rz: sx * 0.25,
                        rx: Math.PI,
                    },
                    false,
                );
            }
        }
        switch (s.hairStyle) {
            case 'bob':
                for (const sx of [-1, 1]) {
                    this.part(S.sphere(0.17, 14, 12), hc, this.head, {
                        x: sx * R * 0.9,
                        y: hy - 0.1,
                        z: -0.02,
                        sx: 0.7,
                        sy: 1.25,
                    });
                }
                break;
            case 'long':
                for (const sx of [-1, 1]) {
                    this.part(S.capsule(0.12, 0.26, 4, 12), hc, this.head, {
                        x: sx * R * 0.86,
                        y: hy - 0.2,
                        z: -0.08,
                    });
                }
                this.part(S.capsule(0.3, 0.2, 6, 14), hc, this.head, {
                    y: hy - 0.22,
                    z: -0.17,
                    sz: 0.55,
                });
                break;
            case 'spiky':
                for (let i = 0; i < 7; i++) {
                    const a = (i / 7) * Math.PI * 2;
                    const tilt = 0.75;
                    const m = this.part(
                        S.cone(0.1, 0.24, 8),
                        hc,
                        this.head,
                        {},
                        true,
                    );
                    const dir = new THREE.Vector3(
                        Math.cos(a) * Math.sin(tilt),
                        Math.cos(tilt),
                        Math.sin(a) * Math.sin(tilt) - 0.25,
                    ).normalize();
                    m.position.set(0, hy, 0).addScaledVector(dir, R * 1.0);
                    m.quaternion.setFromUnitVectors(
                        new THREE.Vector3(0, 1, 0),
                        dir,
                    );
                }
                this.part(S.cone(0.11, 0.26, 8), hc, this.head, {
                    y: hy + R * 1.05,
                    z: 0.05,
                    rx: 0.3,
                });
                break;
            case 'bun':
                this.part(S.sphere(0.15, 14, 12), hc, this.head, {
                    y: hy + R * 0.95,
                    z: -0.12,
                });
                this.part(
                    S.torus(0.1, 0.03, 6, 16),
                    0xff8fa3,
                    this.head,
                    { y: hy + R * 0.82, z: -0.1, rx: 1.2 },
                    false,
                );
                break;
            case 'pony':
                this.part(S.capsule(0.11, 0.28, 4, 12), hc, this.head, {
                    x: -0.06,
                    y: hy - 0.05,
                    z: -R * 1.05,
                    rx: 0.4,
                });
                this.part(S.sphere(0.09, 12, 10), 0xff7fa8, this.head, {
                    x: -0.04,
                    y: hy + 0.2,
                    z: -R * 0.98,
                });
                for (const sx of [-1, 1]) {
                    this.part(
                        S.cone(0.07, 0.14, 8),
                        0xff7fa8,
                        this.head,
                        {
                            x: -0.04 + sx * 0.1,
                            y: hy + 0.2,
                            z: -R * 0.98,
                            rz: (sx * Math.PI) / 2,
                        },
                        false,
                    );
                }
                break;
            case 'messy':
                for (let i = 0; i < 6; i++) {
                    const a = (i / 6) * Math.PI * 2;
                    this.part(
                        S.sphere(0.12, 10, 8),
                        hc,
                        this.head,
                        {
                            x: Math.cos(a) * 0.18,
                            y: hy + R * 0.88,
                            z: Math.sin(a) * 0.16 - 0.04,
                        },
                        false,
                    );
                }
                break;
            default:
                break;
        }
        const hat = s.hat;
        if (!hat) {
            return;
        }
        switch (hat.kind) {
            case 'beret':
                this.part(S.sphere(R * 1.0, 22, 14), hat.color, this.head, {
                    x: 0.05,
                    y: hy + R * 0.82,
                    z: -0.03,
                    sy: 0.38,
                    sx: 1.12,
                    sz: 1.06,
                    rz: -0.18,
                });
                this.part(S.cyl(0.025, 0.03, 0.07, 8), hat.color, this.head, {
                    x: 0.02,
                    y: hy + R * 1.2,
                    rz: -0.18,
                });
                break;
            case 'cap':
                this.part(
                    this.kit.geo(
                        new THREE.SphereGeometry(
                            R * 1.1,
                            22,
                            12,
                            0,
                            Math.PI * 2,
                            0,
                            Math.PI * 0.5,
                        ),
                    ),
                    hat.color,
                    this.head,
                    { y: hy + 0.06, rx: -0.12 },
                );
                this.part(
                    S.cyl(0.26, 0.26, 0.03, 20),
                    hat.color2 ?? hat.color,
                    this.head,
                    { y: hy + 0.16, z: R * 0.78, sz: 0.7, rx: 0.15 },
                );
                this.part(
                    S.cyl(0.06, 0.06, 0.02, 12),
                    C.white,
                    this.head,
                    { y: hy + R * 0.75, z: R * 0.72, rx: 1.05 },
                    false,
                );
                break;
            case 'postcap':
                this.part(
                    S.cyl(R * 0.95, R * 0.92, 0.2, 22),
                    hat.color,
                    this.head,
                    { y: hy + R * 0.82, rx: -0.12 },
                );
                this.part(
                    S.cyl(R * 1.0, R * 1.0, 0.04, 22),
                    hat.color,
                    this.head,
                    { y: hy + R * 0.95, z: -0.01, rx: -0.12 },
                );
                this.part(S.cyl(0.22, 0.22, 0.025, 18), C.dark, this.head, {
                    y: hy + R * 0.62,
                    z: R * 0.78,
                    sz: 0.65,
                    rx: 0.2,
                });
                this.part(
                    S.cyl(0.06, 0.06, 0.02, 12),
                    C.yellow,
                    this.head,
                    { y: hy + R * 0.86, z: R * 0.86, rx: 1.35 },
                    false,
                );
                break;
            case 'headband':
                this.part(
                    S.torus(R * 1.02, 0.045, 8, 28),
                    hat.color,
                    this.head,
                    { y: hy + R * 0.42, rx: Math.PI / 2 - 0.25 },
                );
                break;
            case 'hood':
                this.part(S.sphere(R * 1.0, 20, 14), hat.color, this.head, {
                    y: hy - 0.12,
                    z: -0.28,
                    sx: 1.05,
                    sy: 0.75,
                    sz: 0.55,
                });
                break;
            default:
                break;
        }
        void hood;
    }

    private glasses(color: number, R: number) {
        const S = this.shapes;
        const rr = 0.082;
        const pts: THREE.Vector3[] = [];
        for (const sx of [-1, 1]) {
            const yaw = sx * 0.33;
            const pitch = -0.08;
            const dir = new THREE.Vector3(
                Math.sin(yaw) * Math.cos(pitch),
                Math.sin(pitch),
                Math.cos(yaw) * Math.cos(pitch),
            );
            const m = this.part(
                S.torus(rr, 0.016, 6, 20),
                color,
                this.head,
                {},
                false,
            );
            m.position.set(0, 0.3, 0).addScaledVector(dir, R * 1.04);
            m.lookAt(m.position.clone().add(dir));
            pts.push(m.position.clone());
            const lens = new THREE.Mesh(
                S.cyl(rr, rr, 0.005, 18),
                this.kit.basic(0xffffff, { transparent: true, opacity: 0.25 }),
            );
            lens.position.copy(m.position);
            lens.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
            this.head.add(lens);
        }
        const bridge = this.part(
            S.cyl(0.012, 0.012, 0.07, 6),
            color,
            this.head,
            {},
            false,
        );
        bridge.position.copy(pts[0]).add(pts[1]).multiplyScalar(0.5);
        bridge.position.z += 0.02;
        bridge.rotation.z = Math.PI / 2;
    }

    /** Làm sáng viền khi rê chuột. */
    setHighlight(on: boolean) {
        this.outline.color.setHex(on ? 0xffc93c : C.ink);
        this.outline.userData.width.value = on ? 0.034 : 0.016;
    }
}

/** Đích dáng điệu (được nội suy mượt từ khung trước). */
export interface Pose {
    bodyY: number;
    hipsY: number;
    lean: number; // nghiêng người trước/sau
    twist: number;
    legL: number;
    legR: number;
    armLx: number;
    armLz: number;
    armRx: number;
    armRz: number;
    headX: number;
    headY: number;
    headZ: number;
    breath: number;
    /** Cả người chúi tới (+) / ngả ra sau (−), xoay quanh bàn chân. */
    pitch: number;
    /** Nghiêng cả người sang bên. */
    roll: number;
    /** Xoay cả người quanh trục dọc thân (lăn tròn). */
    spin: number;
    /** Nhấc (+) / hạ (−) cả người (nằm sấp, lội nước). */
    lift: number;
    kneeL: number;
    kneeR: number;
}

export const restPose = (): Pose => ({
    bodyY: 0,
    hipsY: 0.3,
    lean: 0,
    twist: 0,
    legL: 0,
    legR: 0,
    armLx: 0,
    armLz: 0.14,
    armRx: 0,
    armRz: -0.14,
    headX: 0,
    headY: 0,
    headZ: 0,
    breath: 0,
    pitch: 0,
    roll: 0,
    spin: 0,
    lift: 0,
    kneeL: 0,
    kneeR: 0,
});

export type AnimName =
    | 'idle'
    | 'walk'
    | 'run'
    | 'stomp'
    | 'carry'
    | 'carryRun'
    | 'type'
    | 'smash'
    | 'sitIdle'
    | 'sleep'
    | 'yawn'
    | 'stretch'
    | 'cheer'
    | 'give'
    | 'receive'
    | 'wave'
    | 'drink'
    | 'spin'
    | 'polish'
    | 'water'
    | 'look'
    | 'paddle'
    | 'highfive'
    | 'chat'
    | 'adjust'
    | 'argue'
    | 'write'
    | 'lie'
    | 'cook'
    | 'eat'
    | 'game'
    | 'read'
    | 'swing'
    | 'bonk'
    | 'kick'
    | 'hug'
    | 'rub'
    | 'hop'
    | 'dance'
    | 'pose'
    | 'throw'
    | 'sulk'
    | 'dizzy'
    | 'blush'
    | 'pet'
    | 'point'
    | 'sprint'
    | 'coverRun'
    | 'trip'
    | 'fallen'
    | 'getup'
    | 'cry'
    | 'laugh'
    | 'roll'
    | 'jump'
    | 'curl'
    | 'swim'
    | 'flail'
    | 'climb'
    | 'shake';

/** Tính dáng điệu cho một kiểu chuyển động tại thời điểm t (giây). `seated` = đang ngồi ghế. */
export const poseFor = (
    a: AnimName,
    t: number,
    seated: boolean,
    out: Pose,
    /** Số giây kể từ lúc bắt đầu động tác (cho động tác có diễn biến: vấp, ngã, đứng dậy…). */
    u = t,
): Pose => {
    const p = out;
    Object.assign(p, restPose());
    const sin = Math.sin;
    p.breath = sin(t * 2.2) * 0.022;
    if (seated) {
        p.hipsY = SEAT_HIPS;
        p.legL = -1.45;
        p.legR = -1.45;
        p.kneeL = 1.45;
        p.kneeR = 1.45;
        p.armLx = -0.5;
        p.armRx = -0.5;
        p.armLz = 0.2;
        p.armRz = -0.2;
    }
    switch (a) {
        case 'idle':
            p.armLz = 0.14 + sin(t * 1.3) * 0.03;
            p.armRz = -0.14 - sin(t * 1.3) * 0.03;
            p.headZ = sin(t * 0.7) * 0.05;
            break;
        case 'walk':
        case 'run':
        case 'sprint':
        case 'coverRun':
        case 'stomp':
        case 'carry':
        case 'carryRun': {
            const sprint = a === 'sprint';
            const run =
                a === 'run' || a === 'carryRun' || a === 'coverRun' || sprint;
            const f = sprint ? 15 : run ? 12.5 : a === 'stomp' ? 7.5 : 9;
            const amp = sprint ? 1.15 : run ? 0.95 : a === 'stomp' ? 0.75 : 0.6;
            const s = sin(t * f);
            p.legL = s * amp;
            p.legR = -s * amp;
            // gối gập khi chân đưa ra sau rồi vung lên
            p.kneeL = Math.max(0, sin(t * f + 0.9)) * amp * (run ? 1.3 : 0.8);
            p.kneeR = Math.max(0, -sin(t * f + 0.9)) * amp * (run ? 1.3 : 0.8);
            p.bodyY =
                Math.abs(Math.cos(t * f)) *
                (run ? 0.07 : a === 'stomp' ? 0.07 : 0.035);
            p.lean = sprint ? 0.42 : run ? 0.18 : a === 'stomp' ? 0.1 : 0.05;
            if (a === 'coverRun') {
                // chạy mưa: hai tay che đầu
                p.armLx = -2.75;
                p.armRx = -2.75;
                p.armLz = -0.25;
                p.armRz = 0.25;
                p.lean = 0.3;
            } else if (a === 'carry' || a === 'carryRun') {
                p.armLx = -1.25 + s * 0.05;
                p.armRx = -1.25 - s * 0.05;
                p.armLz = -0.15;
                p.armRz = 0.15;
            } else if (a === 'stomp') {
                p.armLx = -s * 0.3;
                p.armRx = s * 0.3;
                p.armLz = 0.35;
                p.armRz = -0.35;
                p.headX = 0.12;
            } else {
                p.armLx = -s * amp * (sprint ? 1.25 : 0.9) - (sprint ? 0.3 : 0);
                p.armRx = s * amp * (sprint ? 1.25 : 0.9) - (sprint ? 0.3 : 0);
                p.armLz = run ? 0.25 : 0.14;
                p.armRz = run ? -0.25 : -0.14;
            }
            if (sprint) {
                p.headX -= 0.18; // ngẩng nhìn tới khi chúi người
            }
            p.headZ = sin(t * f * 0.5) * 0.04;
            p.twist = -s * (run ? 0.2 : 0.12);
            p.headY = s * (run ? 0.12 : 0.07);
            p.headX =
                (p.headX || 0) +
                (run ? -0.06 : 0) +
                Math.abs(Math.cos(t * f)) * 0.03;
            break;
        }
        case 'lie':
            p.legL = 0;
            p.legR = 0.05;
            p.armLx = 0.05;
            p.armRx = 0.05;
            p.armLz = 0.2;
            p.armRz = -0.2;
            p.headY = sin(t * 0.3) * 0.25;
            p.breath = sin(t * 1.3) * 0.04;
            break;
        case 'cook':
            p.armRx = -1.15 + Math.max(0, sin(t * 8.2)) * 0.5;
            p.armRz = 0.1;
            p.armLx = -0.9 + sin(t * 3) * 0.2;
            p.headX = 0.2;
            p.bodyY = Math.abs(sin(t * 4.1)) * 0.02;
            break;
        case 'eat':
            p.armRx = -1.1 - Math.max(0, sin(t * 3.2)) * 0.9;
            p.armRz = 0.35;
            p.armLx = -0.9;
            p.headX = 0.12 - Math.max(0, sin(t * 3.2)) * 0.15;
            break;
        case 'game':
            p.armLx = -1.0 + sin(t * 11) * 0.06;
            p.armRx = -1.0 + sin(t * 13 + 1) * 0.06;
            p.armLz = -0.35;
            p.armRz = 0.35;
            p.lean = 0.12 + sin(t * 1.7) * 0.05;
            p.twist = sin(t * 1.1) * 0.15;
            p.headZ = sin(t * 1.1) * 0.1;
            break;
        case 'read':
            p.armLx = -1.05;
            p.armRx = -1.05;
            p.armLz = -0.3;
            p.armRz = 0.3;
            p.headX = 0.3;
            p.headZ = sin(t * 0.4) * 0.06;
            break;
        case 'swing':
            p.armRx = -1.3 + sin(t * 6.3) * 0.7;
            p.armRz = -0.5 + sin(t * 6.3) * 0.4;
            p.twist = sin(t * 6.3) * 0.3;
            p.lean = 0.12;
            p.bodyY = Math.abs(sin(t * 6.3)) * 0.04;
            p.legL = sin(t * 3.1) * 0.15;
            p.legR = -sin(t * 3.1) * 0.15;
            break;
        case 'type':
        case 'write':
            p.armLx = -1.15 + sin(t * 17) * 0.09;
            p.armRx = -1.15 + sin(t * 17 + 1.7) * 0.09;
            p.armLz = -0.05;
            p.armRz = 0.05;
            p.headX = 0.16 + sin(t * 1.4) * 0.03;
            p.headZ = sin(t * 0.9) * 0.05;
            p.lean = 0.08;
            if (a === 'write') {
                p.armLx = -1.0;
                p.armRx = -1.2 + sin(t * 6) * 0.06;
                p.armRz = 0.1 + sin(t * 9) * 0.05;
            }
            break;
        case 'smash':
            p.armLx = -1.25 + Math.max(0, sin(t * 14)) * 0.45;
            p.armRx = -1.25 + Math.max(0, sin(t * 14 + Math.PI)) * 0.45;
            p.armLz = -0.05;
            p.armRz = 0.05;
            p.headX = 0.05 + Math.abs(sin(t * 7)) * 0.16;
            p.bodyY = Math.abs(sin(t * 7)) * 0.03;
            p.lean = 0.1;
            break;
        case 'sitIdle':
            p.armLx = -0.85;
            p.armRx = -0.85;
            p.armLz = -0.05;
            p.armRz = 0.05;
            p.headZ = sin(t * 0.6) * 0.07;
            p.headY = sin(t * 0.35) * 0.18;
            break;
        case 'sleep':
            p.lean = 0.45;
            p.armLx = -1.55;
            p.armRx = -1.55;
            p.armLz = -0.35;
            p.armRz = 0.35;
            p.headX = 0.35;
            p.headZ = 0.25;
            p.breath = sin(t * 1.2) * 0.04;
            break;
        case 'yawn':
            p.armLx = -2.7;
            p.armRx = -2.7;
            p.armLz = 0.35;
            p.armRz = -0.35;
            p.headX = -0.25;
            p.lean = -0.08;
            break;
        case 'stretch':
            p.armLx = -2.9 + sin(t * 3) * 0.1;
            p.armRx = -2.9 - sin(t * 3) * 0.1;
            p.armLz = 0.25;
            p.armRz = -0.25;
            p.lean = -0.12 + sin(t * 1.5) * 0.05;
            p.headX = -0.2;
            p.headZ = sin(t * 3) * 0.12;
            p.bodyY = seated ? 0 : 0.03;
            break;
        case 'cheer':
            p.bodyY = seated ? 0 : Math.abs(sin(t * 7)) * 0.3;
            p.legL = seated ? p.legL : -Math.abs(sin(t * 7)) * 0.4;
            p.legR = seated ? p.legR : -Math.abs(sin(t * 7)) * 0.4;
            p.armLx = -2.8 + sin(t * 14) * 0.25;
            p.armRx = -2.8 - sin(t * 14) * 0.25;
            p.armLz = 0.45;
            p.armRz = -0.45;
            p.headX = -0.15;
            break;
        case 'give':
        case 'receive':
            p.armLx = -1.35;
            p.armRx = -1.35;
            p.armLz = -0.1;
            p.armRz = 0.1;
            p.headX = 0.1;
            p.lean = 0.06;
            break;
        case 'wave':
            p.armRx = -2.6;
            p.armRz = -0.4 + sin(t * 10) * 0.4;
            p.headZ = 0.12;
            p.bodyY = seated ? 0 : Math.abs(sin(t * 5)) * 0.04;
            break;
        case 'drink':
            p.armRx = -2.2;
            p.armRz = 0.55;
            p.headX = -0.3;
            break;
        case 'spin':
            p.armLz = 0.9;
            p.armRz = -0.9;
            p.armLx = -0.3;
            p.armRx = -0.3;
            p.headX = -0.15;
            break;
        case 'polish':
            p.armLx = -1.2 + sin(t * 8) * 0.15;
            p.armRx = -1.2 + Math.cos(t * 8) * 0.15;
            p.armLz = -0.15 + Math.cos(t * 8) * 0.15;
            p.armRz = 0.15 + sin(t * 8) * 0.15;
            p.headX = 0.2;
            p.headZ = sin(t * 4) * 0.08;
            break;
        case 'water':
            p.armRx = -1.2;
            p.armRz = 0.1;
            p.lean = 0.12;
            p.headX = 0.25;
            break;
        case 'look':
            p.headY = sin(t * 0.8) * 0.5;
            p.headX = -0.1;
            p.armLx = 0.2;
            p.armRx = 0.2;
            p.armLz = 0.3;
            p.armRz = -0.3;
            break;
        case 'paddle':
            p.armRx = -2.85 + sin(t * 6) * 0.08;
            p.armRz = -0.1;
            p.armLz = 0.5;
            p.headX = -0.12;
            p.bodyY = seated ? 0 : Math.abs(sin(t * 4)) * 0.05;
            break;
        case 'highfive':
            p.armRx = -2.4;
            p.armRz = 0.25;
            p.lean = 0.12;
            p.bodyY = seated ? 0 : Math.max(0, sin(t * 6)) * 0.12;
            break;
        case 'chat':
        case 'argue': {
            const k = a === 'argue' ? 1.6 : 1;
            p.armRx = -1.0 + sin(t * 4 * k) * 0.5;
            p.armRz = -0.3;
            p.armLx = -0.6 + Math.cos(t * 3 * k) * 0.35 * k;
            p.headZ = sin(t * 2.5 * k) * 0.1;
            p.headX = sin(t * 5 * k) * 0.06;
            p.bodyY = seated ? 0 : Math.abs(sin(t * 3 * k)) * 0.02 * k;
            break;
        }
        case 'adjust':
            p.armRx = -2.35;
            p.armRz = 0.75;
            p.headX = -0.05;
            break;
        // ---- tương tác với sếp (hoạt hình kiểu slapstick, không ai đau thật)
        case 'bonk': {
            // giơ tay lên rồi cốc xuống một cái
            const k = (t * 2.2) % 1;
            p.armRx = k < 0.55 ? -2.9 : -1.2;
            p.armRz = -0.15;
            p.lean = k < 0.55 ? -0.05 : 0.12;
            p.headX = 0.05;
            break;
        }
        case 'kick': {
            const k = (t * 1.8) % 1;
            p.legR = k < 0.4 ? 0.6 : -1.35;
            p.legL = 0.1;
            p.lean = k < 0.4 ? 0.1 : -0.15;
            p.armLz = 0.6;
            p.armRz = -0.6;
            p.bodyY = 0.02;
            break;
        }
        case 'hug':
            p.armLx = -1.35;
            p.armRx = -1.35;
            p.armLz = -0.55 + sin(t * 3) * 0.05;
            p.armRz = 0.55 - sin(t * 3) * 0.05;
            p.lean = 0.12;
            p.headZ = 0.2;
            p.bodyY = seated ? 0 : Math.abs(sin(t * 3)) * 0.03;
            break;
        case 'rub':
            p.armRx = -2.9;
            p.armRz = 0.95 + sin(t * 12) * 0.12;
            p.headX = 0.15;
            p.headZ = 0.15 + sin(t * 6) * 0.06;
            break;
        case 'hop': {
            const k = Math.abs(sin(t * 6));
            p.bodyY = seated ? 0 : k * 0.35;
            p.legL = -k * 0.6;
            p.legR = -k * 0.3;
            p.lean = 0.25;
            p.armLx = 0.6;
            p.armRx = 0.6;
            p.armLz = 0.6;
            p.armRz = -0.6;
            p.headX = -0.2;
            break;
        }
        case 'dance': {
            const b = sin(t * 8);
            p.bodyY = seated ? 0 : Math.abs(b) * 0.12;
            p.twist = sin(t * 4) * 0.35;
            p.armLx = -1.6 + b * 0.9;
            p.armRx = -1.6 - b * 0.9;
            p.armLz = 0.5;
            p.armRz = -0.5;
            p.headZ = sin(t * 4) * 0.2;
            p.legL = seated ? p.legL : Math.max(0, b) * -0.5;
            p.legR = seated ? p.legR : Math.max(0, -b) * -0.5;
            break;
        }
        case 'pose':
            p.armRx = -2.6;
            p.armRz = -0.55;
            p.armLz = 0.7;
            p.armLx = -0.4;
            p.headZ = 0.22;
            p.bodyY = seated ? 0 : 0.02;
            break;
        case 'throw': {
            const k = (t * 1.6) % 1;
            p.armRx = k < 0.45 ? -2.9 : -0.9;
            p.armRz = -0.2;
            p.twist = k < 0.45 ? -0.35 : 0.3;
            p.lean = k < 0.45 ? -0.08 : 0.15;
            break;
        }
        case 'sulk':
            p.armLx = -1.2;
            p.armRx = -1.2;
            p.armLz = -0.75;
            p.armRz = 0.75;
            p.headX = 0.32;
            p.headY = 0.35;
            p.lean = 0.08;
            p.breath = sin(t * 1.0) * 0.03;
            break;
        case 'dizzy':
            p.headZ = sin(t * 5) * 0.3;
            p.headX = Math.cos(t * 5) * 0.15;
            p.twist = sin(t * 2.5) * 0.25;
            p.armLz = 0.5 + sin(t * 5) * 0.2;
            p.armRz = -0.5 + sin(t * 5) * 0.2;
            p.lean = sin(t * 2.5) * 0.08;
            break;
        case 'blush':
            p.armLx = -2.3;
            p.armRx = -2.3;
            p.armLz = -0.55;
            p.armRz = 0.55;
            p.headX = 0.15;
            p.headZ = sin(t * 3) * 0.18;
            p.twist = sin(t * 3) * 0.15;
            break;
        case 'pet':
            p.armRx = -1.1 + sin(t * 7) * 0.12;
            p.armRz = 0.2;
            p.lean = 0.35;
            p.headX = 0.3;
            p.bodyY = seated ? 0 : -0.05;
            break;
        case 'point':
            p.armRx = -1.55;
            p.armRz = -0.1;
            p.armLz = 0.5;
            p.armLx = -0.2 + sin(t * 9) * 0.1;
            p.headX = -0.05;
            p.lean = 0.05;
            break;
        case 'trip': {
            // vấp: loạng choạng 0.3 s rồi đổ sấp về trước
            const k = clamp((u - 0.25) / 0.4, 0, 1);
            const e = k * k;
            p.pitch = e * 1.42;
            p.lift = e * 0.2;
            p.lean = 0.35 - e * 0.2;
            p.armLx = -1.2 - sin(u * 30) * 0.8 * (1 - k) - e * 1.4;
            p.armRx = -1.4 + sin(u * 30) * 0.8 * (1 - k) - e * 1.2;
            p.armLz = 0.6;
            p.armRz = -0.6;
            p.legL = -0.5 * (1 - k) + 0.3 * k;
            p.legR = 0.6 * (1 - k) + 0.15 * k;
            p.kneeR = 0.8 * (1 - k);
            p.headX = -0.3 * k;
            break;
        }
        case 'fallen':
            // nằm sấp sau cú ngã, chân đạp nhẹ
            p.pitch = 1.42;
            p.lift = 0.2;
            p.armLx = -2.6;
            p.armRx = -2.6;
            p.armLz = 0.5;
            p.armRz = -0.5;
            p.kneeL = 0.6 + sin(t * 6) * 0.5;
            p.kneeR = 0.6 - sin(t * 6) * 0.5;
            p.headX = -0.45;
            p.headZ = sin(t * 2) * 0.15;
            break;
        case 'getup': {
            // chống tay, quỳ gối rồi đứng lên
            const k = clamp(u / 0.9, 0, 1);
            const e = 1 - (1 - k) * (1 - k);
            p.pitch = 1.42 * (1 - e);
            p.lift = 0.2 * (1 - e);
            p.legL = -1.2 * sin(k * Math.PI);
            p.kneeL = 1.6 * sin(k * Math.PI);
            p.kneeR = 1.2 * sin(k * Math.PI);
            p.armLx = -1.5 * (1 - e);
            p.armRx = -1.5 * (1 - e);
            p.headX = -0.3 * (1 - e);
            break;
        }
        case 'cry':
            // khóc nức nở: tay dụi mắt, vai giật
            p.armLx = -2.25;
            p.armRx = -2.25;
            p.armLz = -0.55;
            p.armRz = 0.55;
            p.headX = 0.28;
            p.bodyY = seated ? 0 : Math.abs(sin(t * 7)) * 0.025;
            p.breath = sin(t * 14) * 0.04;
            p.headZ = sin(t * 7) * 0.06;
            p.lean = 0.1;
            break;
        case 'laugh':
            // cười ngặt nghẽo: ôm bụng, ngửa ra sau, rung cả người
            p.lean = -0.18 + sin(t * 18) * 0.04;
            p.bodyY = seated ? 0 : Math.abs(sin(t * 18)) * 0.03;
            p.armLx = -0.85;
            p.armLz = -0.55;
            p.armRx = -0.4 + sin(t * 9) * 0.6;
            p.armRz = -0.6;
            p.headX = -0.32;
            p.headZ = sin(t * 9) * 0.08;
            p.breath = sin(t * 18) * 0.035;
            break;
        case 'roll':
            // lăn tròn trên cỏ / ghế lười
            p.pitch = -1.5;
            p.lift = 0.22;
            p.spin = t * 4.5;
            p.armLx = -2.9;
            p.armRx = -2.9;
            p.armLz = 0.1;
            p.armRz = -0.1;
            p.headX = 0.1;
            break;
        case 'jump': {
            const k = (u % 0.9) / 0.9;
            const air = Math.max(0, sin(k * Math.PI * 1.25 - 0.4));
            p.bodyY = seated ? 0 : air * 0.62;
            p.kneeL = (1 - air) * 0.9;
            p.kneeR = (1 - air) * 0.9;
            p.legL = -(1 - air) * 0.45;
            p.legR = -(1 - air) * 0.45;
            p.armLx = -2.8 * air;
            p.armRx = -2.8 * air;
            p.armLz = 0.4;
            p.armRz = -0.4;
            p.headX = -0.2 * air;
            break;
        }
        case 'curl':
            // ngủ cuộn tròn (dùng khi nằm)
            p.legL = -1.2;
            p.legR = -1.1;
            p.kneeL = 1.5;
            p.kneeR = 1.4;
            p.armLx = -1.3;
            p.armRx = -1.1;
            p.armLz = -0.3;
            p.armRz = 0.3;
            p.headX = 0.4;
            p.lean = 0.35;
            p.breath = sin(t * 1.2) * 0.045;
            p.spin = 1.45; // nằm nghiêng
            break;
        case 'swim':
            // bơi chó dưới ao: chìm nửa người, tay khua vòng
            p.lift = -0.62;
            p.pitch = 0.75;
            p.armLx = -1.6 + sin(t * 6) * 1.3;
            p.armRx = -1.6 - sin(t * 6) * 1.3;
            p.armLz = 0.35;
            p.armRz = -0.35;
            p.legL = sin(t * 11) * 0.45;
            p.legR = -sin(t * 11) * 0.45;
            p.headX = -0.55;
            break;
        case 'flail':
            // vừa rơi xuống nước: quẫy loạn xạ
            p.lift = -0.5 + Math.abs(sin(t * 7)) * 0.08;
            p.armLx = -2.5 + sin(t * 17) * 0.7;
            p.armRx = -2.5 - sin(t * 17) * 0.7;
            p.armLz = 0.7;
            p.armRz = -0.7;
            p.headX = -0.35;
            p.headZ = sin(t * 9) * 0.2;
            break;
        case 'climb': {
            // bám bờ trèo lên
            const k = clamp(u / 1.1, 0, 1);
            p.lift = -0.55 * (1 - k);
            p.pitch = 0.55 * sin(k * Math.PI);
            p.armLx = -2.2 + k * 1.8;
            p.armRx = -2.2 + k * 1.8;
            p.legL = -1.1 * sin(k * Math.PI);
            p.kneeL = 1.4 * sin(k * Math.PI);
            p.headX = -0.2;
            break;
        }
        case 'shake':
            // giũ nước như cún
            p.twist = sin(t * 32) * 0.45;
            p.headY = sin(t * 32 + 0.6) * 0.45;
            p.armLz = 0.9 + sin(t * 32) * 0.2;
            p.armRz = -0.9 + sin(t * 32) * 0.2;
            p.bodyY = seated ? 0 : Math.abs(sin(t * 16)) * 0.03;
            break;
        default:
            break;
    }

    return p;
};

/** Áp dáng điệu lên khung xương, nội suy mượt. */
export const applyPose = (
    c: Chibi,
    cur: Pose,
    target: Pose,
    dt: number,
    k = 14,
) => {
    // lăn tròn: quấn góc về gần đích để không "tua ngược" nhiều vòng
    const ds = cur.spin - target.spin;
    if (Math.abs(ds) > Math.PI) {
        cur.spin =
            target.spin +
            (((ds % (Math.PI * 2)) + Math.PI * 3) % (Math.PI * 2)) -
            Math.PI;
    }
    for (const key of Object.keys(target) as (keyof Pose)[]) {
        cur[key] = damp(
            cur[key],
            target[key],
            key === 'bodyY' ||
                key === 'legL' ||
                key === 'legR' ||
                key === 'spin' ||
                key.startsWith('knee') ||
                key.startsWith('arm')
                ? k * 1.6
                : k,
            dt,
        );
    }
    c.body.position.y = cur.bodyY + cur.lift;
    c.body.rotation.set(cur.pitch, cur.spin, cur.roll);
    c.shinL.rotation.x = cur.kneeL;
    c.shinR.rotation.x = cur.kneeR;
    c.hips.position.y = cur.hipsY;
    c.torso.rotation.x = cur.lean;
    c.torso.rotation.y = cur.twist;
    c.torso.scale.set(
        1 - cur.breath * 0.5,
        1 + cur.breath,
        1 - cur.breath * 0.5,
    );
    c.legL.rotation.x = cur.legL;
    c.legR.rotation.x = cur.legR;
    c.armL.rotation.x = cur.armLx;
    c.armL.rotation.z = cur.armLz;
    c.armR.rotation.x = cur.armRx;
    c.armR.rotation.z = cur.armRz;
    c.head.rotation.set(clamp(cur.headX, -0.6, 0.6), cur.headY, cur.headZ);
};

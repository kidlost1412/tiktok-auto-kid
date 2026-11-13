// Sân vườn quanh nhà (bãi cỏ dạng mô hình nổi, lối đá, hàng rào, cây đung đưa, hồ có vịt, ghế, hòm thư, đèn đường)
// + bầu trời, mặt trời/mặt trăng, sao, mây và ánh sáng theo giờ thật.
import * as THREE from 'three';

import { RIDGE_Y, RIDGE_Z } from './house';
import {
    BENCH,
    F2,
    FENCE_Z,
    GATE,
    HAMMOCK,
    MAILBOX,
    PINGPONG,
    PLOT,
    POND,
    VEG,
    XL0,
    XR1,
    Z_FRONT,
} from './layout';
import {
    Batch,
    C,
    clamp,
    Kit,
    lerp,
    radialTexture,
    rand,
    Shapes,
} from './util';

interface Tree {
    g: THREE.Object3D;
    phase: number;
    amp: number;
}

export interface Butterfly {
    g: THREE.Group;
    wl: THREE.Object3D;
    wr: THREE.Object3D;
    pos: THREE.Vector3;
    target: THREE.Vector3;
    t: number;
}

const PATH: [number, number][] = [
    [0.8, 2.3],
    [0.3, 4.6],
    [-0.6, 6.2],
    [-1.9, 7.4],
    [-3.3, 8.5],
    [-4.3, 9.7],
    [-5.4, 11.0],
    [-6.2, 12.4],
    [-6.2, 14.4],
];

export class World {
    readonly group = new THREE.Group();
    readonly sun: THREE.DirectionalLight;
    readonly hemi: THREE.HemisphereLight;
    readonly amb: THREE.AmbientLight;
    readonly butterflies: Butterfly[] = [];
    readonly mailboxPick: THREE.Mesh;
    readonly skyTex: { canvas: HTMLCanvasElement; tex: THREE.CanvasTexture };
    readonly skyColor = new THREE.Color();
    readonly groundMeshes: THREE.Mesh[] = [];
    night = 0;
    private trees: Tree[] = [];
    private flag: THREE.Group;
    private flagUp = 0;
    private flagTimer = 0;
    private duck: THREE.Group;
    private clouds: THREE.Group[] = [];
    private stars: THREE.Points;
    private starMat: THREE.PointsMaterial;
    private sunDisc: THREE.Mesh;
    private moonDisc: THREE.Mesh;
    private halo: THREE.Sprite;
    private haloMat: THREE.SpriteMaterial;
    private lampGlows: THREE.SpriteMaterial[] = [];
    private lampBulbs: THREE.MeshBasicMaterial[] = [];
    private fireflies: {
        s: THREE.Sprite;
        m: THREE.SpriteMaterial;
        base: THREE.Vector3;
        ph: number;
    }[] = [];
    private ripples: {
        m: THREE.Mesh;
        mat: THREE.MeshBasicMaterial;
        t: number;
    }[] = [];
    private S: Shapes;

    constructor(
        private kit: Kit,
        shapes: Shapes,
    ) {
        this.S = shapes;
        const S = shapes;
        const ground = new Batch();
        const deco = new Batch();
        // ---- bệ đảo cỏ
        const W = PLOT.x1 - PLOT.x0;
        const D = PLOT.z1 - PLOT.z0;
        const zc = (PLOT.z0 + PLOT.z1) / 2;
        ground.add(S.rbox(W, 0.7, D, 0.32), C.grass, { y: -0.35, z: zc });
        ground.add(S.box(W - 0.3, 0.9, D - 0.3), C.soil, { y: -1.1, z: zc });
        ground.add(S.rbox(W - 0.5, 0.55, D - 0.5, 0.2), C.soilDark, {
            y: -1.75,
            z: zc,
        });
        // mảng cỏ đậm nhạt
        for (let i = 0; i < 26; i++) {
            const x = rand(PLOT.x0 + 2, PLOT.x1 - 2);
            const z = rand(3.5, PLOT.z1 - 1.5);
            if (
                Math.hypot((x - POND.x) / POND.rx, (z - POND.z) / POND.rz) < 1.4
            ) {
                continue;
            }
            ground.add(S.cyl(1, 1, 0.02, 18), i % 2 ? C.grassDark : 0xb8e49c, {
                x,
                // mỗi mảng cao khác nhau vài mm: chồng lên nhau không bị nhấp nháy
                y: 0.004 + i * 0.0016,
                z,
                sx: rand(0.6, 1.6),
                sz: rand(0.4, 1.0),
            });
        }
        // ---- lối đá
        for (let k = 0; k + 1 < PATH.length; k++) {
            const [ax, az] = PATH[k];
            const [bx, bz] = PATH[k + 1];
            const len = Math.hypot(bx - ax, bz - az);
            const n = Math.max(1, Math.round(len / 0.72));
            for (let j = 0; j < n; j++) {
                const t = (j + 0.5) / n;
                const x = lerp(ax, bx, t) + rand(-0.12, 0.12);
                const z = lerp(az, bz, t) + rand(-0.08, 0.08);
                ground.add(
                    S.cyl(1, 1, 0.08, 14),
                    j % 3 ? C.stone : C.stoneDark,
                    {
                        x,
                        y: 0.03 + ((k * 7 + j) % 5) * 0.004,
                        z,
                        sx: rand(0.3, 0.4),
                        sz: rand(0.26, 0.34),
                        ry: rand(0, 3),
                    },
                );
            }
        }
        // ---- hàng rào
        const picket = (x: number, z: number, ry = 0) => {
            deco.add(S.rbox(0.16, 0.8, 0.07, 0.035), 0xfffaf2, {
                x,
                y: 0.4,
                z,
                ry,
            });
        };
        for (let x = PLOT.x0 + 0.5; x <= PLOT.x1 - 0.5; x += 0.42) {
            if (x > GATE.x0 && x < GATE.x1) {
                continue;
            }
            picket(x, FENCE_Z);
        }
        for (const [x0, x1] of [
            [PLOT.x0 + 0.4, GATE.x0],
            [GATE.x1, PLOT.x1 - 0.4],
        ]) {
            for (const y of [0.3, 0.6]) {
                deco.add(S.box(x1 - x0, 0.07, 0.04), 0xf1e2cc, {
                    x: (x0 + x1) / 2,
                    y,
                    z: FENCE_Z - 0.05,
                });
            }
        }
        for (const side of [-1, 1]) {
            const x = side < 0 ? PLOT.x0 + 0.45 : PLOT.x1 - 0.45;
            for (let z = -2.5; z < FENCE_Z; z += 0.42) {
                picket(x, z, Math.PI / 2);
            }
            for (const y of [0.3, 0.6]) {
                deco.add(S.box(0.04, 0.07, FENCE_Z + 2.5), 0xf1e2cc, {
                    x: x - side * 0.05,
                    y,
                    z: (FENCE_Z - 2.5) / 2,
                });
            }
        }
        for (const x of [GATE.x0, GATE.x1]) {
            deco.add(S.rbox(0.24, 1.05, 0.24, 0.05), C.lavMid, {
                x,
                y: 0.52,
                z: FENCE_Z,
            });
            deco.add(S.sphere(0.16, 12, 10), C.purple, {
                x,
                y: 1.1,
                z: FENCE_Z,
            });
        }
        // cánh cổng mở
        for (let k = 0; k < 4; k++) {
            deco.add(S.rbox(0.14, 0.7, 0.06, 0.03), 0xfffaf2, {
                x: GATE.x1 + 0.2 + Math.cos(0.9) * 0.0,
                y: 0.38,
                z: FENCE_Z + 0.25 + k * 0.32,
            });
        }
        // ---- bồn hoa trước nhà
        const bed = (x0: number, x1: number, z: number, d: number) => {
            deco.add(S.rbox(x1 - x0, 0.2, d, 0.06), 0xc98f5a, {
                x: (x0 + x1) / 2,
                y: 0.1,
                z,
            });
            deco.add(S.box(x1 - x0 - 0.16, 0.05, d - 0.16), 0x9a6a45, {
                x: (x0 + x1) / 2,
                y: 0.19,
                z,
            });
            const cols = [
                C.pink,
                C.yellow,
                0xffffff,
                0xc9b6ff,
                C.red,
                0xffb36b,
            ];
            for (let x = x0 + 0.25; x < x1 - 0.2; x += rand(0.25, 0.4)) {
                const fz = z + rand(-d / 2 + 0.15, d / 2 - 0.15);
                const h = rand(0.25, 0.45);
                deco.add(S.cyl(0.015, 0.015, h, 5), C.leaf2, {
                    x,
                    y: 0.2 + h / 2,
                    z: fz,
                });
                deco.add(S.sphere(0.07, 8, 6), C.leaf, {
                    x: x + 0.05,
                    y: 0.2 + h * 0.4,
                    z: fz,
                    sy: 0.5,
                });
                deco.add(
                    S.sphere(0.085, 10, 8),
                    cols[Math.floor(rand(0, cols.length))],
                    { x, y: 0.2 + h, z: fz, sy: 0.75 },
                );
                deco.add(S.sphere(0.035, 6, 5), 0xffe066, {
                    x,
                    y: 0.24 + h,
                    z: fz + 0.02,
                });
            }
        };
        bed(-11.6, -0.8, Z_FRONT + 0.85, 0.7);
        bed(2.4, 8.2, Z_FRONT + 0.85, 0.7);
        bed(-17.4, -13.0, Z_FRONT + 0.85, 0.7);
        bed(12.6, 18.4, Z_FRONT + 0.85, 0.7);
        bed(XL0 - 0.2, -21.0, Z_FRONT + 0.85, 0.7);
        bed(22.0, XR1 + 0.2, Z_FRONT + 0.85, 0.7);
        // bồn tròn
        {
            const x = -8.6;
            const z = 9.4;
            deco.add(S.torus(1.0, 0.13, 8, 26), 0xc98f5a, {
                x,
                y: 0.1,
                z,
                rx: Math.PI / 2,
            });
            deco.add(S.cyl(0.98, 0.98, 0.16, 26), 0x9a6a45, { x, y: 0.06, z });
            const cols = [C.pink, C.yellow, 0xffffff, 0xc9b6ff];
            for (let i = 0; i < 18; i++) {
                const a = rand(0, Math.PI * 2);
                const r = rand(0, 0.8);
                const h = rand(0.2, 0.42);
                const fx = x + Math.cos(a) * r;
                const fz = z + Math.sin(a) * r;
                deco.add(S.cyl(0.015, 0.015, h, 5), C.leaf2, {
                    x: fx,
                    y: 0.14 + h / 2,
                    z: fz,
                });
                deco.add(S.sphere(0.09, 10, 8), cols[i % 4], {
                    x: fx,
                    y: 0.14 + h,
                    z: fz,
                    sy: 0.75,
                });
            }
        }
        // ---- hồ nước
        {
            ground.add(S.cyl(1, 1, 0.1, 40), 0x7ec8e8, {
                x: POND.x,
                y: 0.0,
                z: POND.z,
                sx: POND.rx,
                sz: POND.rz,
            });
            for (let i = 0; i < 26; i++) {
                const a = (i / 26) * Math.PI * 2;
                deco.add(S.sphere(0.3, 10, 8), i % 3 ? 0xd6cab6 : 0xe9e0cf, {
                    x: POND.x + Math.cos(a) * (POND.rx + 0.1),
                    y: 0.04,
                    z: POND.z + Math.sin(a) * (POND.rz + 0.1),
                    sy: 0.45,
                    sx: rand(0.9, 1.3),
                });
            }
            for (const [dx, dz, r] of [
                [-1.2, 0.4, 0.32],
                [0.9, -0.6, 0.26],
                [1.5, 0.7, 0.22],
            ]) {
                deco.add(S.cyl(r, r, 0.02, 16), 0x6fbd78, {
                    x: POND.x + dx,
                    y: 0.075,
                    z: POND.z + dz,
                });
            }
            deco.add(S.sphere(0.08, 8, 6), C.pink, {
                x: POND.x - 1.15,
                y: 0.12,
                z: POND.z + 0.35,
            });
            // lau sậy
            for (let i = 0; i < 6; i++) {
                const x = POND.x + POND.rx * 0.8 + rand(-0.3, 0.3);
                const z = POND.z - POND.rz * 0.6 + rand(-0.3, 0.3);
                const h = rand(0.6, 1.0);
                deco.add(S.cyl(0.02, 0.02, h, 5), C.leaf2, { x, y: h / 2, z });
                deco.add(S.capsule(0.04, 0.12, 3, 6), 0x9a6a45, { x, y: h, z });
            }
            const wmat = this.kit.basic(0xa8e4fa, {
                transparent: true,
                opacity: 0.85,
            });
            const water = new THREE.Mesh(S.cyl(1, 1, 0.02, 40), wmat);
            water.position.set(POND.x, 0.065, POND.z);
            water.scale.set(POND.rx * 0.97, 1, POND.rz * 0.97);
            water.receiveShadow = true;
            this.group.add(water);
            this.waterMat = wmat;
            for (let i = 0; i < 3; i++) {
                const mat = this.kit.basic(0xffffff, {
                    transparent: true,
                    opacity: 0,
                });
                const m = new THREE.Mesh(S.torus(0.3, 0.02, 4, 24), mat);
                m.rotation.x = Math.PI / 2;
                m.position.set(
                    POND.x + rand(-1.4, 1.4),
                    0.08,
                    POND.z + rand(-0.8, 0.8),
                );
                this.group.add(m);
                this.ripples.push({ m, mat, t: i * 1.3 });
            }
        }
        // vịt
        {
            const d = new THREE.Group();
            const mat = this.kit.toon(0xffe066);
            const body = new THREE.Mesh(S.sphere(0.2, 14, 10), mat);
            body.scale.set(1, 0.75, 1.3);
            const head = new THREE.Mesh(S.sphere(0.13, 12, 10), mat);
            head.position.set(0, 0.2, 0.18);
            const beak = new THREE.Mesh(
                S.cone(0.05, 0.12, 8),
                this.kit.toon(0xff9f3a),
            );
            beak.rotation.x = Math.PI / 2;
            beak.position.set(0, 0.18, 0.33);
            const eye = new THREE.Mesh(
                S.sphere(0.022, 6, 5),
                this.kit.toon(0x2b2440),
            );
            eye.position.set(0.08, 0.24, 0.26);
            const eye2 = eye.clone();
            eye2.position.x = -0.08;
            d.add(body, head, beak, eye, eye2);
            d.position.set(POND.x, 0.12, POND.z);
            this.group.add(d);
            this.duck = d;
        }
        // ---- ghế đá
        {
            const g = new THREE.Group();
            const bb = new Batch();
            for (let k = 0; k < 3; k++) {
                bb.add(S.rbox(1.6, 0.06, 0.16, 0.03), C.wood, {
                    y: 0.45,
                    z: -0.2 + k * 0.19,
                });
            }
            for (let k = 0; k < 2; k++) {
                bb.add(S.rbox(1.6, 0.14, 0.05, 0.03), C.wood, {
                    y: 0.66 + k * 0.2,
                    z: -0.32,
                    rx: -0.15,
                });
            }
            for (const sx of [-1, 1]) {
                bb.add(S.box(0.07, 0.45, 0.5), 0x6d6480, {
                    x: sx * 0.68,
                    y: 0.22,
                });
                bb.add(S.box(0.07, 0.5, 0.07), 0x6d6480, {
                    x: sx * 0.68,
                    y: 0.7,
                    z: -0.32,
                });
            }
            const m = bb.build(this.kit, { cast: true });
            g.add(m);
            g.position.set(BENCH.x, 0, BENCH.z);
            g.rotation.y = BENCH.ry;
            this.group.add(g);
        }
        // ---- hòm thư
        {
            const x = MAILBOX.x;
            const z = MAILBOX.z;
            deco.add(S.box(0.12, 1.0, 0.12), C.woodDark, { x, y: 0.5, z });
            deco.add(S.rbox(0.45, 0.4, 0.62, 0.12), C.red, { x, y: 1.15, z });
            deco.add(S.cyl(0.22, 0.22, 0.62, 16), C.red, {
                x,
                y: 1.32,
                z,
                rx: Math.PI / 2,
                sx: 1,
            });
            deco.add(S.cyl(0.19, 0.19, 0.03, 16), 0xffffff, {
                x,
                y: 1.25,
                z: z + 0.32,
                rx: Math.PI / 2,
            });
            deco.add(S.box(0.2, 0.04, 0.03), 0x4a3868, {
                x,
                y: 1.2,
                z: z + 0.34,
            });
            const flag = new THREE.Group();
            flag.position.set(x + 0.25, 1.15, z - 0.05);
            const pole = new THREE.Mesh(
                S.box(0.04, 0.5, 0.04),
                this.kit.toon(0x6d6480),
            );
            pole.position.y = 0.22;
            const cloth = new THREE.Mesh(
                S.box(0.03, 0.18, 0.24),
                this.kit.toon(C.yellow),
            );
            cloth.position.set(0, 0.38, 0.12);
            flag.add(pole, cloth);
            flag.rotation.x = Math.PI / 2;
            this.group.add(flag);
            this.flag = flag;
            const hit = new THREE.Mesh(
                S.box(0.9, 1.7, 1.0),
                this.kit.basic(0xffffff),
            );
            hit.position.set(x, 0.85, z);
            hit.visible = false;
            hit.userData.pick = { kind: 'role', key: 'buuta' };
            this.group.add(hit);
            this.mailboxPick = hit;
        }
        // ---- đèn đường
        const glowTex = radialTexture(
            kit,
            'rgba(255,230,160,0.95)',
            'rgba(255,200,120,0)',
        );
        for (const [x, z] of [
            [1.75, 4.9],
            [-3.0, 7.7],
            [-4.75, 12.9],
            [7.4, 5.2],
        ]) {
            deco.add(S.cyl(0.07, 0.09, 1.3, 8), 0x4a3868, { x, y: 0.65, z });
            deco.add(S.cyl(0.18, 0.22, 0.1, 10), 0x4a3868, { x, y: 0.05, z });
            deco.add(S.cone(0.26, 0.2, 6), C.purple, { x, y: 1.72, z });
            const bm = this.kit.basic(0xf5ecd8);
            this.lampBulbs.push(bm);
            const bulb = new THREE.Mesh(S.cyl(0.14, 0.11, 0.3, 6), bm);
            bulb.position.set(x, 1.47, z);
            this.group.add(bulb);
            const gm = this.kit.mat(
                new THREE.SpriteMaterial({
                    map: glowTex,
                    transparent: true,
                    opacity: 0,
                    depthWrite: false,
                    blending: THREE.AdditiveBlending,
                }),
            );
            const sp = new THREE.Sprite(gm);
            sp.scale.setScalar(2.4);
            sp.position.set(x, 1.47, z);
            sp.raycast = () => undefined;
            this.group.add(sp);
            this.lampGlows.push(gm);
        }
        // ---- bụi cây + đá
        const bush = (x: number, z: number, s = 1) => {
            for (let k = 0; k < 4; k++) {
                deco.add(S.sphere(0.45 * s, 12, 10), k % 2 ? C.leaf : C.leaf2, {
                    x: x + (k - 1.5) * 0.35 * s,
                    y: 0.32 * s,
                    z: z + (k % 2) * 0.2 * s,
                    sy: 0.8,
                });
            }
            deco.add(S.sphere(0.07, 6, 5), C.red, {
                x: x + 0.2 * s,
                y: 0.62 * s,
                z: z + 0.3 * s,
            });
            deco.add(S.sphere(0.07, 6, 5), C.red, {
                x: x - 0.35 * s,
                y: 0.55 * s,
                z: z + 0.32 * s,
            });
        };
        bush(-15.6, 12.4, 1.1);
        bush(-25.6, 1.0, 1.0);
        bush(25.6, -1.0, 1.1);
        bush(-26.0, 12.0, 1.0);
        bush(26.0, 13.0, 0.9);
        bush(14.0, 13.0, 0.8);
        bush(-2.6, 13.0, 0.8);
        bush(4.2, 13.1, 0.9);
        for (const [x, z, s] of [
            [-12.3, 4.4, 0.35],
            [6.8, 6.9, 0.3],
            [-3.3, 5.2, 0.25],
            [11.2, 12.6, 0.4],
        ]) {
            deco.add(S.sphere(1, 10, 8), C.stoneDark, {
                x,
                y: s * 0.3,
                z,
                sx: s * 1.3,
                sy: s * 0.8,
                sz: s,
            });
        }
        // ---- cây (mỗi cây một nhóm để đung đưa)
        this.tree(-15.6, -5.8, 'pine', 1.2);
        this.tree(-13.6, -7.4, 'round', 1.0);
        this.tree(15.6, -6.0, 'pine', 1.3);
        this.tree(13.4, -7.6, 'round', 0.95, 0xffb3c6);
        this.tree(-24.2, 11.4, 'round', 1.05, 0xffb3c6);
        this.tree(HAMMOCK.x - 2.1, HAMMOCK.z, 'round', 0.85);
        this.tree(HAMMOCK.x + 2.1, HAMMOCK.z, 'round', 0.9, 0xffb3c6);
        this.tree(-25.8, -5.4, 'pine', 1.15);
        this.tree(25.8, -5.0, 'round', 1.05);
        this.tree(-20.0, -6.8, 'round', 0.95);
        this.tree(20.5, -7.0, 'pine', 1.1);
        this.tree(-12.3, 12.0, 'round', 0.9);
        this.tree(15.0, 12.7, 'round', 0.9);
        this.tree(-4.5, -7.6, 'pine', 1.0);
        this.tree(5.0, -7.8, 'round', 1.05);
        this.tree(10.9, 13.2, 'pine', 0.75);

        this.garden(deco);

        const gm = ground.build(kit, { receive: true });
        const dm = deco.build(kit, { receive: true, cast: true });
        this.group.add(gm, dm);
        this.groundMeshes.push(gm);

        // ---- bướm
        for (let i = 0; i < 5; i++) {
            const g = new THREE.Group();
            const wingMat = this.kit.basic(
                [0xffe27a, 0xffb3e6, 0xb3e0ff, 0xffffff, 0xffc58a][i],
                { side: THREE.DoubleSide },
            );
            const shape = new THREE.Shape();
            shape.moveTo(0, 0);
            shape.bezierCurveTo(0.12, 0.14, 0.26, 0.12, 0.22, -0.02);
            shape.bezierCurveTo(0.24, -0.14, 0.1, -0.16, 0, 0);
            const wg = this.kit.geo(new THREE.ShapeGeometry(shape));
            wg.rotateX(-Math.PI / 2);
            const wl = new THREE.Group();
            const wr = new THREE.Group();
            const ml = new THREE.Mesh(wg, wingMat);
            const mr = new THREE.Mesh(wg, wingMat);
            mr.scale.x = -1;
            wl.add(ml);
            wr.add(mr);
            const bodyM = new THREE.Mesh(
                S.capsule(0.02, 0.1, 3, 6),
                this.kit.toon(0x4a3868),
            );
            bodyM.rotation.x = Math.PI / 2;
            g.add(wl, wr, bodyM);
            const pos = new THREE.Vector3(rand(-20, 20), 1.2, rand(4, 12));
            g.position.copy(pos);
            this.group.add(g);
            this.butterflies.push({
                g,
                wl,
                wr,
                pos,
                target: pos.clone(),
                t: rand(0, 10),
            });
        }
        // ---- mây
        for (let i = 0; i < 6; i++) {
            const cb = new Batch();
            const n = 4 + (i % 3);
            for (let k = 0; k < n; k++) {
                cb.add(S.sphere(1, 14, 10), 0xffffff, {
                    x: k * 1.1 - n * 0.55,
                    y: Math.sin(k * 1.7) * 0.3 + (k % 2) * 0.4,
                    z: (k % 3) * 0.3,
                    sx: 1.1 + (k % 2) * 0.5,
                    sy: 0.85,
                    sz: 0.9,
                });
            }
            const m = cb.build(kit);
            m.material = this.kit.mat(
                new THREE.MeshToonMaterial({
                    vertexColors: true,
                    gradientMap: kit.gradient,
                    transparent: true,
                    opacity: 0.95,
                }),
            );
            const g = new THREE.Group();
            g.add(m);
            g.position.set(rand(-40, 40), rand(13, 19), rand(-30, -18));
            g.scale.setScalar(rand(0.8, 1.4));
            this.group.add(g);
            this.clouds.push(g);
        }
        // ---- sao
        {
            const N = 260;
            const pos = new Float32Array(N * 3);
            for (let i = 0; i < N; i++) {
                pos[i * 3] = rand(-80, 80);
                pos[i * 3 + 1] = rand(6, 45);
                pos[i * 3 + 2] = rand(-45, -30);
            }
            const geo = this.kit.geo(new THREE.BufferGeometry());
            geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
            this.starMat = this.kit.mat(
                new THREE.PointsMaterial({
                    color: 0xffffff,
                    size: 2.4,
                    sizeAttenuation: false,
                    transparent: true,
                    opacity: 0,
                    depthWrite: false,
                }),
            );
            this.stars = new THREE.Points(geo, this.starMat);
            this.group.add(this.stars);
        }
        // ---- mặt trời / trăng
        this.sunDisc = new THREE.Mesh(
            S.sphere(2.2, 24, 16),
            this.kit.basic(0xffd36a),
        );
        this.moonDisc = new THREE.Mesh(
            S.sphere(1.8, 24, 16),
            this.kit.basic(0xfff6cf),
        );
        this.haloMat = this.kit.mat(
            new THREE.SpriteMaterial({
                map: radialTexture(
                    kit,
                    'rgba(255,240,190,0.8)',
                    'rgba(255,240,190,0)',
                ),
                transparent: true,
                depthWrite: false,
            }),
        );
        this.halo = new THREE.Sprite(this.haloMat);
        this.halo.scale.setScalar(12);
        this.group.add(this.sunDisc, this.moonDisc, this.halo);
        // ---- đom đóm
        const ff = radialTexture(
            kit,
            'rgba(230,255,150,1)',
            'rgba(200,255,120,0)',
            64,
        );
        for (let i = 0; i < 22; i++) {
            const m = this.kit.mat(
                new THREE.SpriteMaterial({
                    map: ff,
                    transparent: true,
                    opacity: 0,
                    depthWrite: false,
                    blending: THREE.AdditiveBlending,
                }),
            );
            const s = new THREE.Sprite(m);
            s.scale.setScalar(0.35);
            const base = new THREE.Vector3(
                rand(-25, 25),
                rand(0.5, 1.8),
                rand(3.5, 13),
            );
            s.position.copy(base);
            s.raycast = () => undefined;
            this.group.add(s);
            this.fireflies.push({ s, m, base, ph: rand(0, 10) });
        }

        // ---- ánh sáng
        this.hemi = new THREE.HemisphereLight(0xdff0ff, 0xb9d99a, 1.2);
        this.amb = new THREE.AmbientLight(0xffffff, 0.25);
        this.sun = new THREE.DirectionalLight(0xfff1dc, 2.2);
        this.sun.castShadow = true;
        this.sun.shadow.mapSize.set(2048, 2048);
        const sc = this.sun.shadow.camera;
        sc.left = -36;
        sc.right = 36;
        sc.top = 26;
        sc.bottom = -26;
        sc.near = 1;
        sc.far = 120;
        this.sun.shadow.bias = -0.0008;
        this.sun.shadow.normalBias = 0.03;
        this.sun.shadow.radius = 4;
        this.sun.target.position.set(0, 0, 2);
        this.group.add(this.hemi, this.amb, this.sun, this.sun.target);

        const sky = document.createElement('canvas');
        sky.width = 4;
        sky.height = 256;
        const tex = new THREE.CanvasTexture(sky);
        tex.colorSpace = THREE.SRGBColorSpace;
        this.kit.tex(tex);
        this.skyTex = { canvas: sky, tex };
    }

    waterMat!: THREE.MeshBasicMaterial;
    /** Cờ cho đồ chơi ngoài vườn (bóng bàn đang đánh, võng có người nằm). */
    readonly play = { pingpong: false, hammock: false };
    private ppBall!: THREE.Mesh;
    private hammockG!: THREE.Group;
    private fish: THREE.Object3D[] = [];
    private birds: {
        g: THREE.Group;
        home: THREE.Vector3;
        ph: number;
        fly: number;
        hop: number;
    }[] = [];
    private grassTime = { value: 0 };

    /** Vườn rau, võng, bàn bóng bàn, cá dưới hồ, chim trên mái, cỏ đung đưa. */
    private garden(deco: Batch) {
        const S = this.S;
        // ---- vườn rau
        {
            const { x0, x1, z0, z1 } = VEG;
            deco.add(
                S.rbox(x1 - x0 + 0.3, 0.22, z1 - z0 + 0.3, 0.06),
                0xc98f5a,
                { x: (x0 + x1) / 2, y: 0.11, z: (z0 + z1) / 2 },
            );
            deco.add(S.box(x1 - x0, 0.06, z1 - z0), 0x8a5a3a, {
                x: (x0 + x1) / 2,
                y: 0.2,
                z: (z0 + z1) / 2,
            });
            const rows = 4;
            for (let r = 0; r < rows; r++) {
                const z = z0 + 0.35 + r * ((z1 - z0 - 0.7) / (rows - 1));
                deco.add(S.box(x1 - x0 - 0.3, 0.07, 0.3), 0x9a6a45, {
                    x: (x0 + x1) / 2,
                    y: 0.24,
                    z,
                });
                for (let x = x0 + 0.4; x < x1 - 0.3; x += 0.55) {
                    if (r % 2 === 0) {
                        // bắp cải
                        deco.add(
                            S.sphere(0.2, 10, 8),
                            r === 0 ? 0x8fd68a : 0x7bc67e,
                            { x, y: 0.36, z, sy: 0.8 },
                        );
                        deco.add(S.sphere(0.12, 8, 6), 0xb8eaa0, {
                            x,
                            y: 0.45,
                            z: z + 0.02,
                        });
                    } else {
                        // cà rốt: lá xanh, đầu cam ló lên
                        deco.add(S.cone(0.07, 0.14, 8), C.orange, {
                            x,
                            y: 0.3,
                            z,
                            rx: Math.PI,
                        });
                        for (let k = 0; k < 3; k++) {
                            deco.add(S.cone(0.03, 0.22, 5), C.leaf2, {
                                x: x + (k - 1) * 0.04,
                                y: 0.45,
                                z,
                                rz: (k - 1) * 0.3,
                            });
                        }
                    }
                }
            }
            // cọc cà chua
            for (let k = 0; k < 3; k++) {
                const x = x1 + 0.6;
                const z = z0 + 0.4 + k * 0.9;
                deco.add(S.cyl(0.025, 0.025, 1.2, 5), C.woodDark, {
                    x,
                    y: 0.6,
                    z,
                });
                deco.add(S.sphere(0.22, 10, 8), C.leaf, {
                    x,
                    y: 0.8,
                    z,
                    sy: 1.4,
                });
                for (let j = 0; j < 3; j++) {
                    deco.add(S.sphere(0.07, 8, 6), C.red, {
                        x: x + (j - 1) * 0.12,
                        y: 0.65 + j * 0.15,
                        z: z + 0.15,
                    });
                }
            }
            // biển nhỏ + bình tưới
            deco.add(S.box(0.06, 0.6, 0.06), C.woodDark, {
                x: x0 - 0.3,
                y: 0.3,
                z: z0 - 0.1,
            });
            deco.add(S.rbox(0.7, 0.32, 0.05, 0.03), 0xfffaf2, {
                x: x0 - 0.3,
                y: 0.7,
                z: z0 - 0.08,
            });
            deco.add(S.cyl(0.14, 0.16, 0.24, 12), C.mint, {
                x: x1 + 0.2,
                y: 0.12,
                z: z0 - 0.35,
            });
            deco.add(S.cyl(0.02, 0.03, 0.3, 6), C.mint, {
                x: x1 + 0.36,
                y: 0.22,
                z: z0 - 0.35,
                rz: -1.0,
            });
        }
        // ---- võng
        {
            const g = new THREE.Group();
            g.position.set(HAMMOCK.x, 1.15, HAMMOCK.z);
            const cloth = new THREE.Mesh(
                S.sphere(1, 18, 10),
                this.kit.toon(0xffb36b),
            );
            cloth.scale.set(1.25, 0.22, 0.42);
            cloth.position.y = -0.38;
            const stripe = new THREE.Mesh(
                S.sphere(1, 18, 10),
                this.kit.toon(0xffffff),
            );
            stripe.scale.set(1.0, 0.2, 0.43);
            stripe.position.y = -0.36;
            g.add(cloth, stripe);
            for (const sx of [-1, 1]) {
                const rope = new THREE.Mesh(
                    S.cyl(0.015, 0.015, 0.8, 4),
                    this.kit.toon(0xd6c3a0),
                );
                rope.position.set(sx * 1.55, -0.15, 0);
                rope.rotation.z = sx * 1.0;
                g.add(rope);
            }
            this.group.add(g);
            this.hammockG = g;
        }
        // ---- bàn bóng bàn
        {
            const { x, z } = PINGPONG;
            deco.add(S.rbox(2.6, 0.08, 1.45, 0.03), 0x3f9a6a, {
                x,
                y: 0.76,
                z,
            });
            deco.add(S.box(2.6, 0.005, 0.03), 0xffffff, { x, y: 0.805, z });
            deco.add(S.box(0.04, 0.16, 1.5), 0xffffff, { x, y: 0.88, z });
            for (const dx of [-1.1, 1.1]) {
                for (const dz of [-0.6, 0.6]) {
                    deco.add(S.box(0.07, 0.72, 0.07), 0x3a3150, {
                        x: x + dx,
                        y: 0.36,
                        z: z + dz,
                    });
                }
            }
            this.ppBall = new THREE.Mesh(
                S.sphere(0.05, 8, 6),
                this.kit.toon(0xffa64f),
            );
            this.ppBall.position.set(x, 0.86, z);
            this.ppBall.castShadow = true;
            this.group.add(this.ppBall);
        }
        // ---- cá dưới hồ
        for (let k = 0; k < 4; k++) {
            const f = new THREE.Group();
            const col = [0xff8f4f, 0xffffff, 0xff6f4f, 0xffd36a][k];
            const body = new THREE.Mesh(
                S.sphere(0.12, 8, 6),
                this.kit.toon(col),
            );
            body.scale.set(0.6, 0.45, 1.4);
            const tail = new THREE.Mesh(
                S.cone(0.09, 0.14, 4),
                this.kit.toon(col),
            );
            tail.rotation.x = -Math.PI / 2;
            tail.position.z = -0.2;
            f.add(body, tail);
            f.userData.ph = k * 1.6;
            this.group.add(f);
            this.fish.push(f);
        }
        // ---- chim nhỏ trên nóc nhà và lan can sân thượng
        const homes = [
            new THREE.Vector3(-6.4, RIDGE_Y + 0.2, RIDGE_Z),
            new THREE.Vector3(-5.6, RIDGE_Y + 0.2, RIDGE_Z),
            new THREE.Vector3(6.9, RIDGE_Y + 0.2, RIDGE_Z),
            new THREE.Vector3(XR1 - 1.5, F2 + 0.5, 0.22),
            new THREE.Vector3(XL0 + 2.2, F2 + 0.5, 0.22),
        ];
        homes.forEach((home, i) => {
            const g = new THREE.Group();
            const col = [0x8fd3ff, 0xffd36a, 0xff9fb7, 0x8fd3ff, 0xffffff][i];
            const body = new THREE.Mesh(
                S.sphere(0.13, 10, 8),
                this.kit.toon(col),
            );
            body.scale.set(0.9, 0.85, 1.15);
            const head = new THREE.Mesh(
                S.sphere(0.09, 10, 8),
                this.kit.toon(col),
            );
            head.position.set(0, 0.12, 0.08);
            const beak = new THREE.Mesh(
                S.cone(0.03, 0.07, 6),
                this.kit.toon(0xff9f3a),
            );
            beak.rotation.x = Math.PI / 2;
            beak.position.set(0, 0.11, 0.18);
            const eye = new THREE.Mesh(
                S.sphere(0.015, 6, 5),
                this.kit.toon(0x2b2440),
            );
            eye.position.set(0.05, 0.15, 0.14);
            const eye2 = eye.clone();
            eye2.position.x = -0.05;
            const wing = new THREE.Mesh(
                S.sphere(0.08, 8, 6),
                this.kit.toon(
                    new THREE.Color(col).multiplyScalar(0.85).getHex(),
                ),
            );
            wing.scale.set(0.4, 0.7, 1.2);
            wing.position.set(0.1, 0.02, -0.02);
            const wing2 = wing.clone();
            wing2.position.x = -0.1;
            g.add(body, head, beak, eye, eye2, wing, wing2);
            g.position.copy(home);
            g.rotation.y = rand(-0.6, 0.6);
            this.group.add(g);
            this.birds.push({
                g,
                home: home.clone(),
                ph: rand(0, 6),
                fly: -rand(5, 25),
                hop: 0,
            });
        });
        // ---- cỏ đung đưa (instanced, lắc bằng shader)
        {
            const geo = this.kit.geo(new THREE.ConeGeometry(0.06, 0.32, 4, 1));
            geo.translate(0, 0.16, 0);
            const mat = this.kit.mat(
                new THREE.MeshToonMaterial({
                    color: 0x8fcf6f,
                    gradientMap: this.kit.gradient,
                }),
            );
            const time = this.grassTime;
            mat.onBeforeCompile = (sh) => {
                sh.uniforms.uTime = time;
                sh.vertexShader =
                    'uniform float uTime;\n' +
                    sh.vertexShader.replace(
                        '#include <begin_vertex>',
                        '#include <begin_vertex>\nvec4 ip = instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);\nfloat sw = sin(uTime * 1.8 + ip.x * 0.7 + ip.z * 0.5) * 0.09 * position.y / 0.32;\ntransformed.x += sw;\ntransformed.z += sw * 0.4;',
                    );
            };
            const N = 520;
            const im = new THREE.InstancedMesh(geo, mat, N);
            const m4 = new THREE.Matrix4();
            const q = new THREE.Quaternion();
            const sc = new THREE.Vector3();
            const p = new THREE.Vector3();
            const up = new THREE.Vector3(0, 1, 0);
            let n = 0;
            for (let tries = 0; tries < N * 6 && n < N; tries++) {
                const x = rand(PLOT.x0 + 0.8, PLOT.x1 - 0.8);
                const z = rand(Z_FRONT + 1.2, FENCE_Z - 0.4);
                if (
                    Math.hypot(
                        (x - POND.x) / (POND.rx + 0.5),
                        (z - POND.z) / (POND.rz + 0.5),
                    ) < 1
                ) {
                    continue;
                }
                if (
                    x > VEG.x0 - 0.5 &&
                    x < VEG.x1 + 1 &&
                    z > VEG.z0 - 0.6 &&
                    z < VEG.z1 + 0.4
                ) {
                    continue;
                }
                if (
                    Math.abs(x - PINGPONG.x) < 2.2 &&
                    Math.abs(z - PINGPONG.z) < 1.4
                ) {
                    continue;
                }
                p.set(x, 0, z);
                q.setFromAxisAngle(up, rand(0, 6));
                sc.setScalar(rand(0.7, 1.4));
                m4.compose(p, q, sc);
                im.setMatrixAt(n++, m4);
            }
            im.count = n;
            im.instanceMatrix.needsUpdate = true;
            im.raycast = () => undefined;
            this.group.add(im);
        }
    }

    private tree(
        x: number,
        z: number,
        kind: 'round' | 'pine',
        s: number,
        blossom?: number,
    ) {
        const S = this.S;
        const b = new Batch();
        if (kind === 'pine') {
            b.add(S.cyl(0.18, 0.26, 1.2, 8), 0xa8764d, { y: 0.6 });
            for (let k = 0; k < 3; k++) {
                b.add(
                    S.cone(1.5 - k * 0.38, 1.5, 10),
                    k % 2 ? 0x5fae78 : 0x6fbf86,
                    { y: 1.5 + k * 0.85 },
                );
            }
            b.add(S.sphere(0.12, 8, 6), C.yellow, { y: 4.0 });
        } else {
            b.add(S.cyl(0.2, 0.32, 1.8, 9), 0xb98557, { y: 0.9 });
            b.add(S.cyl(0.08, 0.1, 0.8, 6), 0xb98557, {
                x: 0.35,
                y: 1.7,
                rz: -0.7,
            });
            const leaf = blossom ?? C.leaf;
            const leaf2 = blossom ? 0xff9fb7 : C.leaf2;
            const pts: [number, number, number, number][] = [
                [0, 2.8, 0, 1.25],
                [-0.85, 2.3, 0.2, 0.95],
                [0.85, 2.35, -0.1, 1.0],
                [0.2, 2.25, 0.8, 0.85],
                [-0.2, 3.5, -0.2, 0.85],
            ];
            pts.forEach(([px, py, pz, r], i) =>
                b.add(S.sphere(r, 16, 12), i % 2 ? leaf2 : leaf, {
                    x: px,
                    y: py,
                    z: pz,
                }),
            );
            for (let i = 0; i < 6; i++) {
                const a = i * 1.1;
                b.add(S.sphere(0.1, 8, 6), blossom ? 0xffffff : C.red, {
                    x: Math.cos(a) * 1.05,
                    y: 2.4 + (i % 3) * 0.4,
                    z: Math.sin(a) * 1.05 + 0.3,
                });
            }
        }
        const m = b.build(this.kit, { cast: true, receive: false });
        const g = new THREE.Group();
        g.add(m);
        g.position.set(x, 0, z);
        g.scale.setScalar(s);
        this.group.add(g);
        this.trees.push({
            g,
            phase: rand(0, 6),
            amp: kind === 'pine' ? 0.015 : 0.025,
        });
    }

    /** Bưu tá thả thư: cờ bật lên rồi tự hạ sau ~40 giây. */
    raiseFlag() {
        this.flagUp = 1;
        this.flagTimer = 40;
    }

    /** Ánh sáng/bầu trời theo giờ (0..24, lẻ). */
    /** `ov`: độ u ám 0..1 (nhiều mây / mưa) — trời xám, nắng yếu. */
    setHour(h: number, ov = 0) {
        // 0 = ngày, 1 = đêm; chạng vạng 17.5-19.5, rạng đông 5-6.5
        const night =
            h >= 19.5 || h < 5
                ? 1
                : h >= 17.5
                  ? (h - 17.5) / 2
                  : h < 6.5
                    ? 1 - (h - 5) / 1.5
                    : 0;
        const dusk =
            h >= 15.5 && h < 19.5
                ? 1 - Math.abs(h - 18) / 2.5
                : h >= 5 && h < 7.5
                  ? 1 - Math.abs(h - 6) / 1.5
                  : 0;
        this.night = clamp(night, 0, 1);
        const n = this.night;
        const d = clamp(dusk, 0, 1) * (1 - n * 0.6);
        const top = new THREE.Color(0x8fcbff)
            .lerp(new THREE.Color(0x9b8cf0), d * 0.8)
            .lerp(new THREE.Color(0x15123a), n);
        const mid = new THREE.Color(0xcfe8ff)
            .lerp(new THREE.Color(0xffb7b0), d)
            .lerp(new THREE.Color(0x2c2468), n);
        const bot = new THREE.Color(0xfff3e0)
            .lerp(new THREE.Color(0xffd29a), d)
            .lerp(new THREE.Color(0x4a3a86), n);
        if (ov > 0) {
            const k = ov * (1 - n * 0.5);
            top.lerp(new THREE.Color(0x8a93a8), k * 0.75);
            mid.lerp(new THREE.Color(0xadb3c2), k * 0.7);
            bot.lerp(new THREE.Color(0xc8cad3), k * 0.6);
        }
        const g = this.skyTex.canvas.getContext('2d')!;
        const gr = g.createLinearGradient(0, 0, 0, 256);
        gr.addColorStop(0, `#${top.getHexString()}`);
        gr.addColorStop(0.55, `#${mid.getHexString()}`);
        gr.addColorStop(1, `#${bot.getHexString()}`);
        g.fillStyle = gr;
        g.fillRect(0, 0, 4, 256);
        this.skyTex.tex.needsUpdate = true;
        this.skyColor.copy(mid).lerp(bot, 0.5);

        // mặt trời đi từ trái sang phải phía trước nhà
        const dayT = clamp((h - 6) / 13, 0, 1);
        const elev = Math.sin(dayT * Math.PI);
        const sx = lerp(-28, 28, dayT);
        this.sun.position.set(
            n > 0.5 ? 14 : sx,
            n > 0.5 ? 30 : 12 + elev * 22,
            26,
        );
        this.sun.color
            .set(0xfff1dc)
            .lerp(new THREE.Color(0xffb37a), d)
            .lerp(new THREE.Color(0x9fb0ff), n);
        this.sun.intensity =
            lerp(2.3, 0.55, n) * (1 - d * 0.15) * (1 - ov * 0.62);
        this.hemi.color
            .set(0xe3f1ff)
            .lerp(new THREE.Color(0xffd8c0), d)
            .lerp(new THREE.Color(0x7d78c8), n);
        this.hemi.groundColor.set(0xbfdc9f).lerp(new THREE.Color(0x3c3f6a), n);
        this.hemi.intensity = lerp(1.25, 0.75, n) * (1 - ov * 0.12);
        this.hemi.color.lerp(new THREE.Color(0xc9d0dc), ov * 0.5);
        this.amb.intensity = lerp(0.3, 0.35, n);
        this.starMat.opacity = n;
        this.sunDisc.visible = n < 0.6 && ov < 0.6;
        this.moonDisc.visible = n >= 0.6;
        const bx = n >= 0.6 ? 26 : lerp(-34, 34, dayT);
        const by = n >= 0.6 ? 26 : 10 + elev * 16;
        this.sunDisc.position.set(bx, by, -34);
        this.moonDisc.position.set(bx, by, -34);
        this.halo.position.set(bx, by, -35);
        this.haloMat.color.set(n >= 0.6 ? 0xc8d0ff : 0xfff0c0);
        this.haloMat.opacity = (n >= 0.6 ? 0.55 : 0.9) * (1 - ov * 0.85);
        (this.sunDisc.material as THREE.MeshBasicMaterial).color
            .set(0xffd36a)
            .lerp(new THREE.Color(0xff9a6a), d);
        this.lampGlows.forEach((m) => (m.opacity = n * 0.85));
        this.lampBulbs.forEach((m) =>
            m.color.set(0xf5ecd8).lerp(new THREE.Color(0xffe08a), n),
        );
        this.clouds.forEach((c) =>
            (
                (c.children[0] as THREE.Mesh).material as THREE.MeshToonMaterial
            ).color
                .set(0xffffff)
                .lerp(new THREE.Color(0x9a9fb0), ov * 0.75)
                .lerp(new THREE.Color(0x6a62a8), n * 0.8),
        );
        this.waterMat.color
            .set(0xa8e4fa)
            .lerp(new THREE.Color(0x4a5aa8), n * 0.8);
    }

    update(t: number, dt: number, motion: boolean) {
        if (motion) {
            for (const tr of this.trees) {
                tr.g.rotation.z = Math.sin(t * 0.9 + tr.phase) * tr.amp;
                tr.g.rotation.x = Math.cos(t * 0.7 + tr.phase) * tr.amp * 0.6;
            }
            for (const c of this.clouds) {
                c.position.x += dt * 0.35;
                if (c.position.x > 48) {
                    c.position.x = -48;
                }
            }
            const a = t * 0.18;
            this.duck.position.set(
                POND.x + Math.cos(a) * POND.rx * 0.55,
                0.12 + Math.sin(t * 2) * 0.015,
                POND.z + Math.sin(a) * POND.rz * 0.5,
            );
            this.duck.rotation.y = -a;
            for (const r of this.ripples) {
                r.t += dt;
                const k = (r.t % 4) / 4;
                r.m.scale.setScalar(0.5 + k * 2.2);
                r.mat.opacity = (1 - k) * 0.5;
                if (r.t % 4 < dt) {
                    r.m.position.set(
                        POND.x + rand(-1.6, 1.6),
                        0.08,
                        POND.z + rand(-0.9, 0.9),
                    );
                }
            }
            for (const bf of this.butterflies) {
                bf.t += dt;
                if (bf.pos.distanceTo(bf.target) < 0.3) {
                    bf.target.set(
                        rand(-24, 24),
                        rand(0.6, 1.8),
                        rand(3.5, 12.5),
                    );
                }
                const dir = bf.target.clone().sub(bf.pos).normalize();
                bf.pos.addScaledVector(dir, dt * 1.1);
                bf.g.position.set(
                    bf.pos.x,
                    bf.pos.y + Math.sin(bf.t * 3) * 0.25,
                    bf.pos.z,
                );
                bf.g.rotation.y = Math.atan2(dir.x, dir.z);
                const f = Math.sin(bf.t * 22) * 1.1;
                bf.wl.rotation.z = f;
                bf.wr.rotation.z = -f;
            }
            for (const f of this.fireflies) {
                f.s.position.set(
                    f.base.x + Math.sin(t * 0.5 + f.ph) * 0.8,
                    f.base.y + Math.sin(t * 0.9 + f.ph * 2) * 0.3,
                    f.base.z + Math.cos(t * 0.4 + f.ph) * 0.6,
                );
                f.m.opacity =
                    this.night * Math.max(0, Math.sin(t * 2 + f.ph * 3));
            }
        }
        // vườn: võng, bóng bàn, cá, chim, cỏ
        this.grassTime.value = motion ? t : 0;
        this.hammockG.rotation.x = motion
            ? Math.sin(t * 1.1) * (this.play.hammock ? 0.12 : 0.05)
            : 0;
        {
            const { x, z } = PINGPONG;
            if (this.play.pingpong && motion) {
                const k = (t * 0.9) % 2;
                const u = k < 1 ? k : 2 - k;
                this.ppBall.position.set(
                    x - 1.2 + u * 2.4,
                    0.86 + Math.abs(Math.sin(u * Math.PI * 2)) * 0.45,
                    z + Math.sin(t * 1.7) * 0.3,
                );
            } else {
                this.ppBall.position.set(x + 0.6, 0.85, z + 0.2);
            }
        }
        for (const f of this.fish) {
            const a = (motion ? t : 0) * 0.35 + (f.userData.ph as number);
            f.position.set(
                POND.x + Math.cos(a) * POND.rx * 0.45,
                0.02,
                POND.z + Math.sin(a * 1.3) * POND.rz * 0.4,
            );
            f.rotation.y = -a + Math.PI;
        }
        if (motion) {
            for (const b of this.birds) {
                b.fly += dt;
                const wl = b.g.children[5];
                const wr = b.g.children[6];
                if (b.fly > 0 && b.fly < 6) {
                    // bay một vòng rồi về chỗ cũ
                    const k = b.fly / 6;
                    const a = k * Math.PI * 2;
                    b.g.position.set(
                        b.home.x + Math.sin(a) * 4,
                        b.home.y + Math.sin(k * Math.PI) * 3,
                        b.home.z + (1 - Math.cos(a)) * 3,
                    );
                    b.g.rotation.y = a + Math.PI / 2;
                    const flap = Math.sin(t * 30) * 0.9;
                    wl.rotation.z = flap;
                    wr.rotation.z = -flap;
                } else {
                    if (b.fly >= 6) {
                        b.fly = -rand(18, 45);
                        b.g.position.copy(b.home);
                    }
                    wl.rotation.z = wr.rotation.z = 0;
                    b.hop -= dt;
                    if (b.hop <= 0) {
                        b.hop = rand(1.2, 4);
                        b.g.rotation.y = rand(-0.9, 0.9);
                    }
                    b.g.position.y =
                        b.home.y + Math.max(0, Math.sin(t * 9 + b.ph)) * 0.04;
                    b.g.children[1].rotation.x =
                        Math.max(0, Math.sin(t * 2.3 + b.ph)) * 0.5;
                }
            }
        }
        // cờ hòm thư
        if (this.flagTimer > 0) {
            this.flagTimer -= dt;
            if (this.flagTimer <= 0) {
                this.flagUp = 0;
            }
        }
        const target = this.flagUp ? 0 : Math.PI / 2;
        this.flag.rotation.x +=
            (target - this.flag.rotation.x) *
            Math.min(1, dt * (this.flagUp ? 9 : 3));
        if (this.flagUp && motion) {
            this.flag.rotation.x +=
                Math.sin(t * 18) * 0.02 * Math.max(0, this.flagTimer - 37);
        }
    }
}

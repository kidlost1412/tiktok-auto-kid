// Hai dãy nhà phụ một tầng (Bếp + Quầy cà phê bên trái, Góc giải trí + Phòng nghỉ bên phải), sân thượng trên mái,
// cùng đồ đạc "sống" được: chảo lật, máy pha cà phê bốc hơi, TV chơi game, bi lắc, bể cá ở Sảnh, dây đèn ban đêm.
import * as THREE from 'three';

import type { Effects } from './effects';
import type { House } from './house';
import {
    AW,
    F1,
    F2,
    H,
    room,
    SLAB,
    wingOf,
    WINGS,
    XL0,
    XL1,
    XR0,
    XR1,
    Z_BACK,
    Z_ROOM,
} from './layout';
import { Batch, C, CanvasTex, FONT, rand, roundRect } from './util';

export interface WingState {
    cooking: boolean;
    eating: boolean;
    coffee: number; // thời điểm (giây) lần pha gần nhất
    tv: boolean;
    foosball: boolean;
}

export class Wings {
    readonly state: WingState = {
        cooking: false,
        eating: false,
        coffee: -99,
        tv: false,
        foosball: false,
    };
    readonly pan = new THREE.Group();
    readonly panPos = new THREE.Vector3();
    readonly machinePos = new THREE.Vector3();
    private tv!: CanvasTex;
    private tvT = 0;
    private ball!: THREE.Mesh;
    private fish: THREE.Object3D[] = [];
    private bubbles: THREE.Mesh[] = [];
    private fairy: THREE.MeshBasicMaterial;
    private warm: THREE.MeshBasicMaterial;
    private moon: THREE.MeshBasicMaterial;
    private steamT = 0;
    private night = 0;
    private lamps: THREE.PointLight[] = [];
    private tankCenter = new THREE.Vector3();

    constructor(
        private h: House,
        private fx: Effects,
    ) {
        this.fairy = h.kit.basic(0xf2e6c8);
        this.warm = h.kit.basic(0xf3e6cf);
        this.moon = h.kit.basic(0xf6efd0);
        const shell = new Batch();
        const floors = new Batch();
        const furn = new Batch();
        this.shell(shell, floors);
        this.kitchen(furn);
        this.cafe(furn);
        this.rec(furn);
        this.nap(furn);
        this.terrace(furn);
        this.fishTank(furn);
        this.extraDecor(furn);
        const sm = shell.build(h.kit, { cast: true, receive: false });
        const fm = floors.build(h.kit, { receive: false });
        const um = furn.build(h.kit, { cast: false });
        sm.name = 'wing-shell';
        fm.name = 'wing-floors';
        um.name = 'wing-furn';
        h.group.add(sm, fm, um);
        h.occluders.push(sm);
        // đèn ấm ban đêm cho hai dãy phụ
        for (const x of [XL1 - AW / 2, XR0 + AW / 2]) {
            const l = new THREE.PointLight(0xffc98a, 0, 9.5, 1.2);
            l.position.set(x, F1 + 2.4, -1.3);
            h.group.add(l);
            this.lamps.push(l);
        }
        this.signsAndHits();
    }

    // ---------------------------------------------------------------- vỏ
    private shell(b: Batch, floors: Batch) {
        const S = this.h.S;
        const y = F1;
        for (const w of WINGS) {
            const n = 9;
            const dz = (Z_ROOM - Z_BACK) / n;
            for (let k = 0; k < n; k++) {
                floors.add(
                    S.box(w.x1 - w.x0, 0.06, dz - 0.015),
                    k % 2 ? w.floorA : w.floorB,
                    { x: w.cx, y: y - 0.03, z: Z_BACK + dz * (k + 0.5) },
                );
            }
            b.add(
                S.box(w.x1 - w.x0, H, 0.3),
                w.wall,
                { x: w.cx, y: y + H / 2, z: Z_BACK - 0.15 },
                { ao: y, aoH: 0.9 },
            );
            b.add(
                S.box(w.x1 - w.x0, 0.85, 0.05),
                w.wain,
                { x: w.cx, y: y + 0.425, z: Z_BACK + 0.025 },
                { ao: y, aoH: 0.5 },
            );
            b.add(S.box(w.x1 - w.x0, 0.06, 0.08), 0xfffaf2, {
                x: w.cx,
                y: y + 0.86,
                z: Z_BACK + 0.04,
            });
            b.add(S.box(w.x1 - w.x0, 0.12, 0.06), 0xfffaf2, {
                x: w.cx,
                y: y + H - 0.06,
                z: Z_BACK + 0.03,
            });
        }
        // vách giữa hai phòng mỗi dãy: kín phía sau, phía trước là vòm thông
        for (const [x, l, r] of [
            [wingOf('bep').x1, wingOf('bep').wall, wingOf('phache').wall],
            [wingOf('giaitri').x1, wingOf('giaitri').wall, wingOf('nghi').wall],
        ] as const) {
            for (const [dx, col] of [
                [-0.05, l],
                [0.05, r],
            ] as const) {
                b.add(
                    S.box(0.1, H, -1.3 - Z_BACK),
                    col,
                    { x: x + dx, y: y + H / 2, z: (Z_BACK - 1.3) / 2 },
                    { ao: y, aoH: 0.9 },
                );
                b.add(S.box(0.1, H - 2.4, Z_ROOM + 1.3), col, {
                    x: x + dx,
                    y: y + 2.4 + (H - 2.4) / 2,
                    z: (Z_ROOM - 1.3) / 2,
                });
            }
            b.add(S.rbox(0.3, 0.12, Z_ROOM + 1.36, 0.04), C.woodLight, {
                x,
                y: y + 2.4,
                z: (Z_ROOM - 1.3) / 2,
            });
            b.add(S.rbox(0.3, 2.4, 0.1, 0.04), C.woodLight, {
                x,
                y: y + 1.2,
                z: -1.3,
            });
            b.add(S.rbox(0.3, H, 0.16, 0.05), 0xfffaf2, {
                x,
                y: y + H / 2,
                z: Z_ROOM + 0.02,
            });
        }
        // mái bằng (sân thượng) + nẹp tím, cột hiên
        for (const [x0, x1] of [
            [XL0 - 0.3, XL1],
            [XR0, XR1 + 0.3],
        ]) {
            b.add(S.box(x1 - x0, SLAB - 0.06, Z_ROOM - Z_BACK + 0.3), C.lav, {
                x: (x0 + x1) / 2,
                y: F2 - SLAB / 2 - 0.03,
                z: (Z_ROOM + Z_BACK - 0.3) / 2,
            });
            b.add(S.rbox(x1 - x0 + 0.1, SLAB + 0.04, 0.14, 0.05), C.trim, {
                x: (x0 + x1) / 2,
                y: F2 - SLAB / 2,
                z: Z_ROOM + 0.05,
            });
            b.add(S.box(x1 - x0, 0.03, 0.02), 0xb7a2f0, {
                x: (x0 + x1) / 2,
                y: F2 - 0.04,
                z: Z_ROOM + 0.125,
            });
            // sàn sân thượng (gạch)
            for (let k = 0; k < 4; k++) {
                const dz = (Z_ROOM - Z_BACK + 0.3) / 4;
                floors.add(
                    S.box(x1 - x0 - 0.1, 0.04, dz - 0.03),
                    k % 2 ? 0xf3d9c4 : 0xe9c9b0,
                    {
                        x: (x0 + x1) / 2,
                        y: F2 + 0.0,
                        z: Z_BACK - 0.3 + dz * (k + 0.5),
                    },
                );
            }
        }
        for (const x of [XL0 + 0.15 - 0.3, XR1 + 0.15]) {
            b.add(S.rbox(0.26, H, 0.26, 0.06), 0xfffaf2, {
                x,
                y: y + H / 2,
                z: Z_ROOM + 0.1,
            });
        }
        // hai tường đầu hồi ngoài cùng (mờ đi khi xoay camera về phía đó)
        for (const side of [-1, 1] as const) {
            const wb = new Batch();
            const x = side < 0 ? XL0 - 0.15 - 0.3 + 0.15 : XR1 + 0.15;
            const xi = side < 0 ? XL0 : XR1;
            const z0 = Z_BACK - 0.3;
            const zf = Z_ROOM + 0.15;
            wb.add(S.box(0.3, F2 - 0.0, zf - z0), C.wallOut, {
                x: side < 0 ? XL0 - 0.15 : XR1 + 0.15,
                y: F2 / 2,
                z: (zf + z0) / 2,
            });
            void x;
            const w = side < 0 ? wingOf('bep') : wingOf('nghi');
            wb.add(
                S.box(0.02, H, Z_ROOM - Z_BACK),
                w.wall,
                {
                    x: xi - side * 0.01,
                    y: F1 + H / 2,
                    z: (Z_ROOM + Z_BACK) / 2,
                },
                { ao: F1, aoH: 0.9 },
            );
            wb.add(S.rbox(0.36, F2 + 0.05, 0.22, 0.06), 0xfffaf2, {
                x: side < 0 ? XL0 - 0.15 : XR1 + 0.15,
                y: F2 / 2,
                z: zf - 0.05,
            });
            // cửa sổ tròn
            wb.add(S.torus(0.42, 0.08, 8, 24), C.trim, {
                x: side < 0 ? XL0 - 0.31 : XR1 + 0.31,
                y: F1 + 1.6,
                z: -1.6,
                ry: Math.PI / 2,
            });
            wb.add(S.cyl(0.4, 0.4, 0.04, 24), 0xcfeaff, {
                x: side < 0 ? XL0 - 0.3 : XR1 + 0.3,
                y: F1 + 1.6,
                z: -1.6,
                rz: Math.PI / 2,
            });
            const mat = this.h.kit.toonOwn(0xffffff, {
                vertexColors: true,
                transparent: true,
                opacity: 1,
            });
            const mesh = wb.build(this.h.kit, { cast: true, material: mat });
            this.h.group.add(mesh);
            this.h.fadeWalls.push({
                mesh,
                normal: new THREE.Vector3(side, 0, 0),
                mat,
                op: 1,
            });
        }
    }

    /** Dây đèn nhỏ treo võng giữa hai điểm (bóng gộp, sáng lên lúc tối). */
    private fairyString(
        b: Batch,
        x0: number,
        x1: number,
        y: number,
        z: number,
        n: number,
        sag = 0.18,
    ) {
        const S = this.h.S;
        for (let k = 0; k <= n; k++) {
            const t = k / n;
            const x = x0 + (x1 - x0) * t;
            const yy = y - Math.sin(t * Math.PI) * sag;
            b.add(S.box((x1 - x0) / n + 0.01, 0.012, 0.012), 0x6d6480, {
                x: x - (x1 - x0) / n / 2,
                y: yy + 0.04,
                z,
            });
        }
        const geoms: THREE.BufferGeometry[] = [];
        void geoms;
        const bulbs = new Batch();
        const cols = [C.yellow, C.pink, C.mint, C.blue, 0xffffff];
        for (let k = 0; k <= n; k++) {
            const t = k / n;
            bulbs.add(S.sphere(0.05, 8, 6), cols[k % cols.length], {
                x: x0 + (x1 - x0) * t,
                y: y - Math.sin(t * Math.PI) * sag,
                z,
                sy: 1.25,
            });
        }
        const m = bulbs.build(this.h.kit, { material: this.fairyMat() });
        this.h.group.add(m);
    }

    private fairyMatCache: THREE.MeshBasicMaterial | null = null;
    private fairyMat() {
        if (!this.fairyMatCache) {
            this.fairyMatCache = this.h.kit.mat(
                new THREE.MeshBasicMaterial({
                    vertexColors: true,
                    color: 0xb8b0a0,
                }),
            );
        }

        return this.fairyMatCache;
    }

    // ---------------------------------------------------------------- Bếp
    private kitchen(b: Batch) {
        const S = this.h.S;
        const c = wingOf('bep').cx;
        const y = F1;
        const zb = Z_BACK + 0.32;
        // tủ bếp + bếp nấu
        b.add(
            S.rbox(1.55, 0.86, 0.6, 0.04),
            0x9ad9c8,
            { x: c - 1.65, y: y + 0.43, z: zb },
            { ao: y, aoH: 0.3 },
        );
        b.add(S.rbox(1.6, 0.06, 0.64, 0.02), 0xfffaf2, {
            x: c - 1.65,
            y: y + 0.89,
            z: zb,
        });
        for (const dx of [-0.38, 0.38]) {
            b.add(S.box(0.66, 0.6, 0.02), 0xb5e8da, {
                x: c - 1.65 + dx,
                y: y + 0.45,
                z: zb + 0.31,
            });
            b.add(S.sphere(0.03, 6, 5), C.woodDark, {
                x: c - 1.65 + dx * 0.4,
                y: y + 0.6,
                z: zb + 0.33,
            });
        }
        for (const dx of [-0.35, 0.3]) {
            b.add(S.cyl(0.17, 0.17, 0.03, 18), 0x3a3150, {
                x: c - 1.65 + dx,
                y: y + 0.935,
                z: zb,
            });
            b.add(S.torus(0.11, 0.012, 6, 16), 0xff6f4f, {
                x: c - 1.65 + dx,
                y: y + 0.955,
                z: zb,
                rx: Math.PI / 2,
            });
        }
        // nồi trên bếp trái
        b.add(S.cyl(0.17, 0.15, 0.22, 16), 0xff8f6f, {
            x: c - 2.0,
            y: y + 1.06,
            z: zb,
        });
        b.add(S.cyl(0.18, 0.18, 0.03, 16), 0xff8f6f, {
            x: c - 2.0,
            y: y + 1.18,
            z: zb,
        });
        b.add(S.sphere(0.035, 6, 5), C.dark, {
            x: c - 2.0,
            y: y + 1.21,
            z: zb,
        });
        // máy hút mùi
        b.add(S.rbox(1.1, 0.28, 0.5, 0.06), 0xfffaf2, {
            x: c - 1.65,
            y: y + 1.78,
            z: zb - 0.02,
        });
        b.add(S.box(0.3, 0.6, 0.3), 0xfffaf2, {
            x: c - 1.65,
            y: y + 2.2,
            z: zb - 0.1,
        });
        // chảo (lật khi nấu)
        this.pan.position.set(c - 1.35, y + 0.97, zb + 0.02);
        const panMat = this.h.kit.toon(0x3a3150);
        const p1 = new THREE.Mesh(S.cyl(0.17, 0.14, 0.05, 18), panMat);
        const handle = new THREE.Mesh(
            S.box(0.3, 0.03, 0.05),
            this.h.kit.toon(C.woodDark),
        );
        handle.position.set(0.3, 0.02, 0.0);
        const egg = new THREE.Mesh(
            S.cyl(0.1, 0.1, 0.02, 14),
            this.h.kit.toon(0xffffff),
        );
        egg.position.y = 0.035;
        const yolk = new THREE.Mesh(
            S.sphere(0.045, 10, 8),
            this.h.kit.toon(C.yellow),
        );
        yolk.position.y = 0.05;
        yolk.scale.y = 0.6;
        this.pan.add(p1, handle, egg, yolk);
        this.h.group.add(this.pan);
        this.panPos.copy(this.pan.position);
        // tủ lạnh
        b.add(
            S.rbox(0.78, 1.66, 0.62, 0.08),
            0xc5e6ff,
            { x: c - 0.05, y: y + 0.83, z: zb + 0.02 },
            { ao: y, aoH: 0.3 },
        );
        b.add(S.box(0.74, 0.02, 0.01), 0x9fc5e8, {
            x: c - 0.05,
            y: y + 1.12,
            z: zb + 0.34,
        });
        b.add(S.rbox(0.04, 0.32, 0.05, 0.02), 0xffffff, {
            x: c + 0.25,
            y: y + 1.32,
            z: zb + 0.36,
        });
        b.add(S.rbox(0.04, 0.42, 0.05, 0.02), 0xffffff, {
            x: c + 0.25,
            y: y + 0.75,
            z: zb + 0.36,
        });
        for (let k = 0; k < 5; k++) {
            b.add(
                S.rbox(0.09, 0.09, 0.02, 0.02),
                [C.pink, C.yellow, C.mint, C.red, C.purple][k],
                {
                    x: c - 0.3 + (k % 3) * 0.14,
                    y: y + 1.35 + Math.floor(k / 3) * 0.14,
                    z: zb + 0.34,
                    rz: rand(-0.3, 0.3),
                },
            );
        }
        // bồn rửa + kệ bát
        b.add(
            S.rbox(1.6, 0.86, 0.6, 0.04),
            0x9ad9c8,
            { x: c + 1.5, y: y + 0.43, z: zb },
            { ao: y, aoH: 0.3 },
        );
        b.add(S.rbox(1.64, 0.06, 0.64, 0.02), 0xfffaf2, {
            x: c + 1.5,
            y: y + 0.89,
            z: zb,
        });
        b.add(S.box(0.6, 0.04, 0.4), 0x8aa0b8, {
            x: c + 1.3,
            y: y + 0.91,
            z: zb,
        });
        b.add(S.cyl(0.025, 0.025, 0.3, 8), 0xc8cfe0, {
            x: c + 1.3,
            y: y + 1.05,
            z: zb - 0.22,
        });
        b.add(S.cyl(0.02, 0.02, 0.2, 8), 0xc8cfe0, {
            x: c + 1.3,
            y: y + 1.2,
            z: zb - 0.12,
            rx: Math.PI / 2,
        });
        for (let k = 0; k < 4; k++) {
            b.add(
                S.cyl(0.12, 0.12, 0.02, 16),
                [0xffffff, C.pinkSoft, 0xffffff, 0xc9f2e6][k],
                {
                    x: c + 1.85 + k * 0.07,
                    y: y + 1.04,
                    z: zb - 0.05,
                    rz: Math.PI / 2 - 0.15,
                },
            );
        }
        // kệ gia vị
        b.add(S.box(1.4, 0.05, 0.22), C.woodLight, {
            x: c + 1.5,
            y: y + 1.48,
            z: Z_BACK + 0.12,
        });
        for (let k = 0; k < 6; k++) {
            b.add(
                S.cyl(0.06, 0.06, 0.16, 10),
                [C.red, C.yellow, C.mint, C.orange, C.pink, C.blue][k],
                { x: c + 0.95 + k * 0.22, y: y + 1.58, z: Z_BACK + 0.12 },
            );
            b.add(S.cyl(0.065, 0.065, 0.04, 10), 0xffffff, {
                x: c + 0.95 + k * 0.22,
                y: y + 1.68,
                z: Z_BACK + 0.12,
            });
        }
        this.h.frame(
            c - 1.65,
            y + 1.42,
            Z_BACK + 0.06,
            0.9,
            0.38,
            (g, W, H2) => {
                g.fillStyle = '#3a3150';
                g.fillRect(0, 0, W, H2);
                g.fillStyle = '#fff3c9';
                g.font = `800 ${H2 * 0.42}px ${FONT}`;
                g.textAlign = 'center';
                g.textBaseline = 'middle';
                g.fillText('Hôm nay ăn gì? 🍜', W / 2, H2 / 2 + 2);
            },
            384,
        );
        // bàn ăn + ghế đẩu
        const tz = -1.2;
        b.add(S.rbox(2.3, 0.08, 1.0, 0.04), C.woodLight, {
            x: c,
            y: y + 0.74,
            z: tz,
        });
        b.add(S.rbox(2.36, 0.02, 0.4, 0.01), 0xffb3c6, {
            x: c,
            y: y + 0.785,
            z: tz,
        });
        for (const [dx, dz] of [
            [-1.0, -0.38],
            [1.0, -0.38],
            [-1.0, 0.38],
            [1.0, 0.38],
        ]) {
            b.add(
                S.box(0.07, 0.72, 0.07),
                C.wood,
                { x: c + dx, y: y + 0.36, z: tz + dz },
                { ao: y, aoH: 0.3 },
            );
        }
        for (const [dx, dz] of [
            [-0.75, -0.75],
            [0.75, -0.75],
            [-0.75, 0.78],
            [0.75, 0.78],
            [-1.65, 0],
            [1.65, 0],
        ]) {
            b.add(S.cyl(0.21, 0.21, 0.07, 16), C.pink, {
                x: c + dx,
                y: y + 0.44,
                z: tz + dz,
            });
            b.add(S.cyl(0.04, 0.05, 0.4, 8), C.woodDark, {
                x: c + dx,
                y: y + 0.2,
                z: tz + dz,
            });
            b.add(S.cyl(0.15, 0.17, 0.03, 12), C.woodDark, {
                x: c + dx,
                y: y + 0.015,
                z: tz + dz,
            });
        }
        // đĩa, bát, giỏ trái cây
        for (const [dx, dz] of [
            [-0.75, -0.3],
            [0.75, -0.3],
            [-0.75, 0.3],
            [0.75, 0.3],
        ]) {
            b.add(S.cyl(0.14, 0.12, 0.02, 16), 0xffffff, {
                x: c + dx,
                y: y + 0.8,
                z: tz + dz,
            });
            b.add(S.cyl(0.02, 0.02, 0.2, 6), C.woodDark, {
                x: c + dx + 0.18,
                y: y + 0.8,
                z: tz + dz,
                rx: Math.PI / 2,
            });
        }
        b.add(S.cyl(0.2, 0.14, 0.1, 16), 0xd9a066, {
            x: c,
            y: y + 0.83,
            z: tz,
        });
        for (const [dx, col] of [
            [-0.08, C.red],
            [0.06, C.orange],
            [0.0, C.yellow],
        ] as const) {
            b.add(S.sphere(0.07, 10, 8), col, {
                x: c + dx,
                y: y + 0.92,
                z: tz + (dx > 0 ? 0.04 : -0.03),
            });
        }
        // đèn thả
        for (const dx of [-0.6, 0.6]) {
            b.add(S.cyl(0.008, 0.008, H - 2.3, 4), 0x6d6480, {
                x: c + dx,
                y: y + 2.3 + (H - 2.3) / 2,
                z: tz,
            });
            b.add(S.cone(0.2, 0.18, 14), C.yellow, {
                x: c + dx,
                y: y + 2.25,
                z: tz,
            });
            const bulb = new THREE.Mesh(S.sphere(0.07, 8, 6), this.warm);
            bulb.position.set(c + dx, y + 2.14, tz);
            this.h.group.add(bulb);
        }
        this.h.plant(b, c + 2.3, y, -0.25, 0.85);
    }

    // ---------------------------------------------------------------- Quầy cà phê
    private cafe(b: Batch) {
        const S = this.h.S;
        const c = wingOf('phache').cx;
        const y = F1;
        // tủ sau quầy + kệ cốc
        b.add(
            S.rbox(3.6, 0.9, 0.5, 0.04),
            0x8a5a3a,
            { x: c, y: y + 0.45, z: Z_BACK + 0.27 },
            { ao: y, aoH: 0.3 },
        );
        b.add(S.rbox(3.65, 0.05, 0.54, 0.02), 0xfffaf2, {
            x: c,
            y: y + 0.92,
            z: Z_BACK + 0.27,
        });
        b.add(S.box(3.4, 0.05, 0.22), C.woodLight, {
            x: c,
            y: y + 1.3,
            z: Z_BACK + 0.12,
        });
        for (let k = 0; k < 9; k++) {
            b.add(
                S.cyl(0.06, 0.05, 0.12, 10),
                [0xffffff, C.pink, C.mint, C.yellow][k % 4],
                { x: c - 1.5 + k * 0.37, y: y + 1.39, z: Z_BACK + 0.12 },
            );
        }
        for (let k = 0; k < 4; k++) {
            b.add(S.cyl(0.1, 0.1, 0.26, 12), 0xfff3d6, {
                x: c - 1.4 + k * 0.32,
                y: y + 1.07,
                z: Z_BACK + 0.3,
            });
            b.add(
                S.cyl(0.105, 0.105, 0.06, 12),
                [C.red, C.mint, C.yellow, C.purple][k],
                { x: c - 1.4 + k * 0.32, y: y + 1.22, z: Z_BACK + 0.3 },
            );
        }
        // bảng thực đơn
        this.h.frame(
            c + 0.9,
            y + 1.15,
            Z_BACK + 0.06,
            1.3,
            0.62,
            (g, W, H2) => {
                g.fillStyle = '#2f3a33';
                g.fillRect(0, 0, W, H2);
                g.strokeStyle = '#c98f5a';
                g.lineWidth = 10;
                g.strokeRect(5, 5, W - 10, H2 - 10);
                g.fillStyle = '#fff3c9';
                g.font = `800 ${H2 * 0.2}px ${FONT}`;
                g.textAlign = 'left';
                g.fillText('☕ Cà phê sữa', 22, H2 * 0.3);
                g.fillText('🧋 Trà sữa', 22, H2 * 0.55);
                g.fillText('🍩 Bánh ngọt', 22, H2 * 0.8);
                g.fillStyle = '#ffd36a';
                g.textAlign = 'right';
                g.fillText('0đ', W - 22, H2 * 0.3);
                g.fillText('0đ', W - 22, H2 * 0.55);
                g.fillText('free', W - 22, H2 * 0.8);
            },
            384,
        );
        // quầy trước
        const qz = -2.2;
        b.add(
            S.rbox(3.3, 1.0, 0.6, 0.05),
            0xc98f5a,
            { x: c - 0.05, y: y + 0.5, z: qz },
            { ao: y, aoH: 0.35 },
        );
        for (let k = 0; k < 7; k++) {
            b.add(S.box(0.4, 0.8, 0.02), k % 2 ? 0xe2b078 : 0xd9a066, {
                x: c - 1.25 + k * 0.42,
                y: y + 0.48,
                z: qz + 0.31,
            });
        }
        b.add(S.rbox(3.45, 0.07, 0.72, 0.03), 0xfffaf2, {
            x: c - 0.05,
            y: y + 1.03,
            z: qz,
        });
        // máy pha cà phê
        const mx = c + 0.55;
        b.add(S.rbox(0.58, 0.55, 0.42, 0.06), 0xff7f8f, {
            x: mx,
            y: y + 1.33,
            z: qz - 0.05,
        });
        b.add(S.rbox(0.5, 0.08, 0.36, 0.03), 0xc8cfe0, {
            x: mx,
            y: y + 1.64,
            z: qz - 0.05,
        });
        b.add(S.cyl(0.05, 0.05, 0.08, 10), 0x3a3150, {
            x: mx,
            y: y + 1.2,
            z: qz + 0.12,
        });
        b.add(S.box(0.2, 0.03, 0.04), 0x3a3150, {
            x: mx + 0.1,
            y: y + 1.2,
            z: qz + 0.2,
        });
        b.add(S.rbox(0.4, 0.03, 0.16, 0.01), 0xc8cfe0, {
            x: mx,
            y: y + 1.07,
            z: qz + 0.14,
        });
        b.add(S.cyl(0.05, 0.04, 0.08, 10), 0xffffff, {
            x: mx,
            y: y + 1.12,
            z: qz + 0.14,
        });
        for (let k = 0; k < 3; k++) {
            b.add(S.sphere(0.03, 6, 5), [C.mint, C.yellow, 0xffffff][k], {
                x: mx - 0.15 + k * 0.08,
                y: y + 1.45,
                z: qz + 0.17,
            });
        }
        this.machinePos.set(mx, y + 1.3, qz + 0.15);
        // bánh trên quầy
        b.add(S.cyl(0.2, 0.2, 0.02, 18), 0xffffff, {
            x: c - 0.7,
            y: y + 1.08,
            z: qz + 0.05,
        });
        for (let k = 0; k < 3; k++) {
            b.add(S.torus(0.06, 0.03, 8, 14), [C.pink, 0xa87452, C.yellow][k], {
                x: c - 0.8 + k * 0.1,
                y: y + 1.11 + (k === 1 ? 0.04 : 0),
                z: qz + 0.05 + (k === 1 ? 0 : 0.06),
                rx: Math.PI / 2,
            });
        }
        b.add(S.cyl(0.12, 0.12, 0.22, 14), 0xdff3ff, {
            x: c - 1.25,
            y: y + 1.18,
            z: qz,
        });
        for (let k = 0; k < 4; k++) {
            b.add(S.cyl(0.05, 0.05, 0.015, 10), 0xc98f5a, {
                x: c - 1.25,
                y: y + 1.12 + k * 0.035,
                z: qz,
                rz: 0.1 * k,
            });
        }
        // ghế quầy cao
        for (const dx of [-1.25, -0.55]) {
            b.add(S.cyl(0.2, 0.2, 0.07, 16), C.mint, {
                x: c + dx,
                y: y + 0.6,
                z: -1.6,
            });
            b.add(S.cyl(0.03, 0.03, 0.58, 8), 0x8a8299, {
                x: c + dx,
                y: y + 0.3,
                z: -1.6,
            });
            b.add(S.torus(0.13, 0.015, 6, 16), 0x8a8299, {
                x: c + dx,
                y: y + 0.25,
                z: -1.6,
                rx: Math.PI / 2,
            });
            b.add(S.cyl(0.16, 0.18, 0.03, 12), 0x8a8299, {
                x: c + dx,
                y: y + 0.015,
                z: -1.6,
            });
        }
        // ghế bành nhỏ
        const sx = c - 1.45;
        const sz = -0.35;
        const g = new THREE.Group();
        g.position.set(sx, y, sz);
        g.rotation.y = 0.5;
        g.updateMatrixWorld();
        const add = (
            geo: THREE.BufferGeometry,
            col: number,
            p: { x?: number; y?: number; z?: number },
        ) => {
            const m = new THREE.Matrix4().makeTranslation(
                p.x ?? 0,
                p.y ?? 0,
                p.z ?? 0,
            );
            b.add(geo, col, g.matrixWorld.clone().multiply(m));
        };
        add(S.rbox(0.75, 0.32, 0.6, 0.1), 0xffb3c6, { y: 0.2 });
        add(S.rbox(0.75, 0.5, 0.16, 0.08), 0xff9fb7, { y: 0.5, z: -0.24 });
        add(S.rbox(0.14, 0.38, 0.6, 0.06), 0xff9fb7, { x: -0.38, y: 0.3 });
        add(S.rbox(0.14, 0.38, 0.6, 0.06), 0xff9fb7, { x: 0.38, y: 0.3 });
        this.h.plant(b, c + 1.75, y, -0.55, 0.9);
        this.fairyString(b, c - 1.8, c + 1.8, y + 1.7, Z_BACK + 0.08, 12, 0.12);
    }

    // ---------------------------------------------------------------- Góc giải trí
    private rec(b: Batch) {
        const S = this.h.S;
        const c = wingOf('giaitri').cx;
        const y = F1;
        // kệ TV + TV
        b.add(
            S.rbox(1.9, 0.5, 0.45, 0.04),
            0xffffff,
            { x: c - 1.3, y: y + 0.25, z: Z_BACK + 0.26 },
            { ao: y, aoH: 0.3 },
        );
        for (const dx of [-0.6, 0, 0.6]) {
            b.add(S.box(0.56, 0.38, 0.02), 0xbfe0ff, {
                x: c - 1.3 + dx,
                y: y + 0.25,
                z: Z_BACK + 0.49,
            });
        }
        b.add(S.rbox(1.62, 0.95, 0.07, 0.05), 0x2b2440, {
            x: c - 1.3,
            y: y + 1.12,
            z: Z_BACK + 0.12,
        });
        this.tv = this.h.kit.canvas(320, 180, (g, W, H2) =>
            this.drawTv(g, W, H2, 0),
        );
        const scr = new THREE.Mesh(
            this.h.kit.geo(new THREE.PlaneGeometry(1.5, 0.84)),
            this.h.kit.basic(0xffffff, { map: this.tv.texture }),
        );
        scr.position.set(c - 1.3, y + 1.12, Z_BACK + 0.16);
        this.h.group.add(scr);
        // máy chơi game + tay cầm + loa
        b.add(S.rbox(0.42, 0.08, 0.3, 0.03), 0xffffff, {
            x: c - 1.75,
            y: y + 0.54,
            z: Z_BACK + 0.3,
        });
        b.add(S.box(0.3, 0.01, 0.02), C.blue, {
            x: c - 1.75,
            y: y + 0.585,
            z: Z_BACK + 0.45,
        });
        for (const dx of [-0.95, 0.95]) {
            b.add(S.rbox(0.2, 0.42, 0.2, 0.04), 0x3a3150, {
                x: c - 1.3 + dx,
                y: y + 0.71,
                z: Z_BACK + 0.25,
            });
        }
        // sofa quay về TV
        const sz = -1.05;
        b.add(
            S.rbox(2.4, 0.36, 0.75, 0.12),
            0xb79be8,
            { x: c - 1.3, y: y + 0.2, z: sz },
            { ao: y, aoH: 0.25 },
        );
        b.add(S.rbox(2.4, 0.5, 0.2, 0.1), 0xa58bea, {
            x: c - 1.3,
            y: y + 0.55,
            z: sz + 0.3,
        });
        for (const dx of [-1.25, 1.25]) {
            b.add(S.rbox(0.2, 0.5, 0.75, 0.1), 0xa58bea, {
                x: c - 1.3 + dx,
                y: y + 0.33,
                z: sz,
            });
        }
        b.add(S.rbox(0.4, 0.34, 0.12, 0.1), C.yellow, {
            x: c - 2.15,
            y: y + 0.55,
            z: sz + 0.12,
            rz: 0.2,
        });
        b.add(S.rbox(0.4, 0.34, 0.12, 0.1), C.mint, {
            x: c - 0.45,
            y: y + 0.55,
            z: sz + 0.12,
            rz: -0.2,
        });
        // thảm + bàn trà nhỏ
        b.add(S.cyl(1.1, 1.1, 0.02, 28), 0xffd1dc, {
            x: c - 1.3,
            y: y + 0.01,
            z: -2.0,
            sx: 1.2,
        });
        b.add(S.rbox(0.8, 0.06, 0.42, 0.03), C.woodLight, {
            x: c - 1.3,
            y: y + 0.36,
            z: -2.05,
        });
        for (const dx of [-0.32, 0.32]) {
            b.add(S.box(0.05, 0.34, 0.34), C.wood, {
                x: c - 1.3 + dx,
                y: y + 0.17,
                z: -2.05,
            });
        }
        b.add(S.cyl(0.12, 0.09, 0.07, 14), 0xffffff, {
            x: c - 1.45,
            y: y + 0.42,
            z: -2.05,
        });
        for (let k = 0; k < 5; k++) {
            b.add(S.sphere(0.035, 6, 5), C.yellow, {
                x: c - 1.5 + (k % 3) * 0.04,
                y: y + 0.47,
                z: -2.05 + (k % 2) * 0.04,
            });
        }
        b.add(S.cyl(0.05, 0.05, 0.15, 10), C.red, {
            x: c - 1.1,
            y: y + 0.46,
            z: -2.0,
        });
        // bi lắc
        const fx = c + 1.25;
        const fz = -0.95;
        b.add(S.rbox(1.0, 0.3, 0.62, 0.04), 0x8a5a3a, {
            x: fx,
            y: y + 0.78,
            z: fz,
        });
        b.add(S.box(0.92, 0.02, 0.54), 0x6fd08a, { x: fx, y: y + 0.88, z: fz });
        for (const dx of [-0.45, 0.45]) {
            for (const dz of [-0.26, 0.26]) {
                b.add(S.box(0.07, 0.65, 0.07), C.woodDark, {
                    x: fx + dx,
                    y: y + 0.33,
                    z: fz + dz,
                });
            }
        }
        for (let k = 0; k < 4; k++) {
            const rx = fx - 0.33 + k * 0.22;
            b.add(S.cyl(0.012, 0.012, 0.9, 6), 0xc8cfe0, {
                x: rx,
                y: y + 0.96,
                z: fz,
                rx: Math.PI / 2,
            });
            for (let j = 0; j < 2; j++) {
                b.add(S.rbox(0.05, 0.12, 0.05, 0.02), k % 2 ? C.red : C.blue, {
                    x: rx,
                    y: y + 0.92,
                    z: fz - 0.12 + j * 0.24,
                });
            }
            b.add(S.cyl(0.03, 0.03, 0.08, 8), 0x3a3150, {
                x: rx,
                y: y + 0.96,
                z: fz + (k % 2 ? 0.47 : -0.47),
                rx: Math.PI / 2,
            });
        }
        this.ball = new THREE.Mesh(
            S.sphere(0.035, 8, 6),
            this.h.kit.toon(0xffffff),
        );
        this.ball.position.set(fx, y + 0.91, fz);
        this.h.group.add(this.ball);
        // góc đọc sách: ghế bành + đèn cây + tủ sách
        const ax = c + 1.85;
        const az = -2.6;
        const g = new THREE.Group();
        g.position.set(ax, y, az);
        g.rotation.y = -0.6;
        g.updateMatrixWorld();
        const add = (
            geo: THREE.BufferGeometry,
            col: number,
            p: { x?: number; y?: number; z?: number },
        ) => {
            b.add(
                geo,
                col,
                g.matrixWorld
                    .clone()
                    .multiply(
                        new THREE.Matrix4().makeTranslation(
                            p.x ?? 0,
                            p.y ?? 0,
                            p.z ?? 0,
                        ),
                    ),
            );
        };
        add(S.rbox(0.8, 0.34, 0.7, 0.1), 0x7fd1c1, { y: 0.2 });
        add(S.rbox(0.8, 0.6, 0.18, 0.08), 0x6fc1b1, { y: 0.6, z: -0.28 });
        add(S.rbox(0.14, 0.42, 0.7, 0.06), 0x6fc1b1, { x: -0.4, y: 0.35 });
        add(S.rbox(0.14, 0.42, 0.7, 0.06), 0x6fc1b1, { x: 0.4, y: 0.35 });
        b.add(S.cyl(0.02, 0.02, 1.4, 6), 0x3a3150, {
            x: c + 2.45,
            y: y + 0.7,
            z: -1.9,
        });
        b.add(S.cone(0.2, 0.22, 12), C.yellow, {
            x: c + 2.45,
            y: y + 1.45,
            z: -1.9,
        });
        b.add(S.cyl(0.15, 0.17, 0.03, 12), 0x3a3150, {
            x: c + 2.45,
            y: y + 0.015,
            z: -1.9,
        });
        const lamp = new THREE.Mesh(S.sphere(0.07, 8, 6), this.warm);
        lamp.position.set(c + 2.45, y + 1.36, -1.9);
        this.h.group.add(lamp);
        this.h.shelfUnit(b, c + 0.85, y, Z_BACK + 0.22, 1.1, 1.6, 3, 0xffffff);
        for (let k = 0; k < 3; k++) {
            this.h.books(
                b,
                c + 0.85,
                y + 0.075 + k * 0.5,
                Z_BACK + 0.22,
                0.95,
                k * 5 + 2,
            );
        }
        // túi đậu
        b.add(S.sphere(0.48, 16, 12), C.orange, {
            x: c - 2.1,
            y: y + 0.24,
            z: -2.6,
            sy: 0.55,
        });
        this.fairyString(
            b,
            c - 2.5,
            c + 2.5,
            y + 1.72,
            Z_BACK + 0.08,
            16,
            0.14,
        );
        this.h.frame(
            c - 0.05,
            y + 1.3,
            Z_BACK + 0.06,
            0.5,
            0.66,
            (gg, W, H2) => {
                const gr = gg.createLinearGradient(0, 0, 0, H2);
                gr.addColorStop(0, '#7fd1c1');
                gr.addColorStop(1, '#6a52b8');
                gg.fillStyle = gr;
                gg.fillRect(0, 0, W, H2);
                gg.fillStyle = '#fff';
                gg.font = `900 ${W * 0.2}px ${FONT}`;
                gg.textAlign = 'center';
                gg.fillText('LEVEL', W / 2, H2 * 0.4);
                gg.fillText('UP!', W / 2, H2 * 0.62);
                gg.fillStyle = '#ffd36a';
                gg.beginPath();
                gg.arc(W / 2, H2 * 0.82, W * 0.1, 0, Math.PI * 2);
                gg.fill();
            },
        );
    }

    private drawTv(
        g: CanvasRenderingContext2D,
        W: number,
        H2: number,
        t: number,
    ) {
        if (!this.state.tv) {
            g.fillStyle = '#1d1830';
            g.fillRect(0, 0, W, H2);
            g.fillStyle = '#3a3150';
            g.font = `800 22px ${FONT}`;
            g.textAlign = 'center';
            g.textBaseline = 'middle';
            g.fillText('zzz', W / 2, H2 / 2);

            return;
        }
        const sky = g.createLinearGradient(0, 0, 0, H2);
        sky.addColorStop(0, '#8fd3ff');
        sky.addColorStop(1, '#d8f1ff');
        g.fillStyle = sky;
        g.fillRect(0, 0, W, H2);
        // mặt đất chạy
        const off = (t * 80) % 40;
        for (let x = -40; x < W + 40; x += 40) {
            g.fillStyle = '#6fd08a';
            g.fillRect(x - off, H2 - 34, 40, 34);
            g.fillStyle = '#4fae6a';
            g.fillRect(x - off, H2 - 34, 40, 6);
        }
        // khối ? và đồng xu
        for (let k = 0; k < 3; k++) {
            const bx = ((k * 130 - t * 80) % (W + 120)) + W;
            const xx = bx > W + 40 ? bx - (W + 120) : bx;
            g.fillStyle = '#ffd36a';
            g.fillRect(xx, 52, 28, 28);
            g.fillStyle = '#c98f2a';
            g.font = `900 20px ${FONT}`;
            g.textAlign = 'center';
            g.textBaseline = 'middle';
            g.fillText('?', xx + 14, 67);
        }
        // nhân vật nhảy
        const jy = Math.abs(Math.sin(t * 3)) * 40;
        g.fillStyle = '#ff6f7f';
        roundRect(g, 70, H2 - 34 - 34 - jy, 26, 34, 8);
        g.fill();
        g.fillStyle = '#fff';
        g.fillRect(84, H2 - 34 - 26 - jy, 6, 6);
        g.fillStyle = '#3a3150';
        g.font = `800 16px ${FONT}`;
        g.textAlign = 'left';
        g.fillText(`★ ${Math.floor(t * 7) % 999}`, 10, 18);
    }

    // ---------------------------------------------------------------- Phòng nghỉ
    private nap(b: Batch) {
        const S = this.h.S;
        const c = wingOf('nghi').cx;
        const y = F1;
        const bz = -2.95;
        const x0 = c - 1.0;
        const x1 = c + 0.95;
        const bx = (x0 + x1) / 2;
        const len = x1 - x0;
        // giường tầng
        for (const [dx, dz] of [
            [x0, bz - 0.42],
            [x1, bz - 0.42],
            [x0, bz + 0.42],
            [x1, bz + 0.42],
        ]) {
            b.add(
                S.rbox(0.09, 1.95, 0.09, 0.03),
                0xffffff,
                { x: dx, y: y + 0.975, z: dz },
                { ao: y, aoH: 0.3 },
            );
        }
        for (const ly of [0.3, 1.3]) {
            b.add(S.rbox(len + 0.1, 0.1, 0.9, 0.03), 0xd2c2f5, {
                x: bx,
                y: y + ly,
                z: bz,
            });
            b.add(S.rbox(len - 0.05, 0.14, 0.82, 0.06), 0xfffaf2, {
                x: bx,
                y: y + ly + 0.12,
                z: bz,
            });
            b.add(S.rbox(0.36, 0.1, 0.55, 0.05), 0xffffff, {
                x: x1 - 0.3,
                y: y + ly + 0.24,
                z: bz,
            });
            b.add(
                S.rbox(len * 0.6, 0.06, 0.84, 0.04),
                ly < 1 ? 0x9fd8ff : 0xffb3c6,
                { x: x0 + len * 0.32, y: y + ly + 0.2, z: bz },
            );
        }
        b.add(S.rbox(len + 0.1, 0.18, 0.06, 0.03), 0xffffff, {
            x: bx,
            y: y + 1.6,
            z: bz + 0.43,
        });
        // thang
        for (let k = 0; k < 4; k++) {
            b.add(S.cyl(0.02, 0.02, 0.4, 6), 0xffffff, {
                x: x1 + 0.12,
                y: y + 0.35 + k * 0.3,
                z: bz + 0.25,
                rx: Math.PI / 2,
            });
        }
        // túi đậu
        b.add(S.sphere(0.5, 16, 12), 0xc9b6ff, {
            x: c - 1.15,
            y: y + 0.22,
            z: -1.15,
            sy: 0.55,
        });
        b.add(S.sphere(0.5, 16, 12), 0x9ad9c8, {
            x: c + 1.1,
            y: y + 0.22,
            z: -1.1,
            sy: 0.55,
        });
        b.add(S.cyl(1.2, 1.2, 0.02, 28), 0xe8dcff, {
            x: c,
            y: y + 0.01,
            z: -1.1,
            sx: 1.3,
        });
        // đèn ngủ mặt trăng + sao treo
        b.add(S.rbox(0.4, 0.4, 0.4, 0.05), 0xffffff, {
            x: c + 1.6,
            y: y + 0.2,
            z: -3.2,
        });
        const moon = new THREE.Mesh(S.sphere(0.16, 12, 10), this.moon);
        moon.position.set(c + 1.6, y + 0.56, -3.2);
        this.h.group.add(moon);
        for (let k = 0; k < 5; k++) {
            const sx = c - 1.4 + k * 0.7;
            b.add(S.cyl(0.006, 0.006, 0.5 + (k % 2) * 0.25, 4), 0x9a8fb8, {
                x: sx,
                y: y + H - 0.25 - (k % 2) * 0.12,
                z: -0.7,
            });
            b.add(S.cone(0.09, 0.05, 5), C.yellow, {
                x: sx,
                y: y + H - 0.55 - (k % 2) * 0.25,
                z: -0.7,
                rx: Math.PI / 2,
            });
        }
        this.h.frame(c + 1.5, y + 1.3, Z_BACK + 0.06, 0.7, 0.45, (g, W, H2) => {
            g.fillStyle = '#4a3868';
            g.fillRect(0, 0, W, H2);
            g.fillStyle = '#ffe9a8';
            g.font = `800 ${H2 * 0.3}px ${FONT}`;
            g.textAlign = 'center';
            g.textBaseline = 'middle';
            g.fillText('Suỵt… 🌙', W / 2, H2 / 2);
        });
    }

    // ---------------------------------------------------------------- sân thượng
    private terrace(b: Batch) {
        const S = this.h.S;
        const y = F2;
        for (const [x0, x1, outer] of [
            [XL0 - 0.3, XL1, XL0 - 0.3],
            [XR0, XR1 + 0.3, XR1 + 0.3],
        ]) {
            // lan can trước + bên ngoài
            for (let x = x0 + 0.15; x < x1 - 0.05; x += 0.36) {
                b.add(S.cyl(0.03, 0.03, 0.42, 6), 0xffffff, {
                    x,
                    y: y + 0.21,
                    z: Z_ROOM + 0.02,
                });
            }
            b.add(S.rbox(x1 - x0, 0.06, 0.1, 0.03), 0xffffff, {
                x: (x0 + x1) / 2,
                y: y + 0.44,
                z: Z_ROOM + 0.02,
            });
            for (let z = Z_BACK - 0.2; z < Z_ROOM; z += 0.36) {
                b.add(S.cyl(0.03, 0.03, 0.42, 6), 0xffffff, {
                    x: outer + (outer < 0 ? 0.1 : -0.1),
                    y: y + 0.21,
                    z,
                });
            }
            b.add(S.rbox(0.1, 0.06, Z_ROOM - Z_BACK + 0.3, 0.03), 0xffffff, {
                x: outer + (outer < 0 ? 0.1 : -0.1),
                y: y + 0.44,
                z: (Z_ROOM + Z_BACK - 0.3) / 2,
            });
            // chậu hoa + ô che + ghế nằm
            for (let k = 0; k < 4; k++) {
                const px = x0 + 0.8 + k * ((x1 - x0 - 1.6) / 3);
                b.add(S.rbox(0.7, 0.32, 0.4, 0.05), 0xe8a98f, {
                    x: px,
                    y: y + 0.16,
                    z: Z_BACK + 0.1,
                });
                for (let j = 0; j < 5; j++) {
                    b.add(
                        S.sphere(0.09, 8, 6),
                        [C.pink, C.yellow, 0xffffff, C.red, 0xc9b6ff][
                            (j + k) % 5
                        ],
                        {
                            x: px - 0.24 + j * 0.12,
                            y: y + 0.4 + (j % 2) * 0.06,
                            z: Z_BACK + 0.1,
                        },
                    );
                    b.add(S.sphere(0.08, 8, 6), C.leaf, {
                        x: px - 0.22 + j * 0.12,
                        y: y + 0.33,
                        z: Z_BACK + 0.16,
                    });
                }
            }
            const ux = (x0 + x1) / 2 + (outer < 0 ? 1.4 : -1.4);
            b.add(S.cyl(0.03, 0.03, 1.9, 6), 0xffffff, {
                x: ux,
                y: y + 0.95,
                z: -1.7,
            });
            b.add(S.cone(1.1, 0.45, 12), outer < 0 ? 0xff9fb7 : 0x7fd1c1, {
                x: ux,
                y: y + 1.95,
                z: -1.7,
            });
            b.add(S.cyl(0.42, 0.42, 0.05, 16), 0xffffff, {
                x: ux,
                y: y + 0.7,
                z: -1.7,
            });
            b.add(S.cyl(0.04, 0.04, 0.7, 6), 0xffffff, {
                x: ux,
                y: y + 0.35,
                z: -1.7,
            });
            for (const dx of [-0.7, 0.7]) {
                b.add(S.cyl(0.2, 0.2, 0.05, 12), C.yellow, {
                    x: ux + dx,
                    y: y + 0.45,
                    z: -1.7,
                });
                b.add(S.cyl(0.03, 0.03, 0.45, 6), 0xffffff, {
                    x: ux + dx,
                    y: y + 0.22,
                    z: -1.7,
                });
            }
            this.fairyString(
                b,
                x0 + 0.2,
                x1 - 0.2,
                y + 1.5,
                Z_BACK + 0.0,
                18,
                0.25,
            );
            for (const px of [x0 + 0.2, x1 - 0.2]) {
                b.add(S.cyl(0.025, 0.025, 1.5, 6), 0x8a8299, {
                    x: px,
                    y: y + 0.75,
                    z: Z_BACK + 0.0,
                });
            }
        }
    }

    // ---------------------------------------------------------------- bể cá ở Sảnh
    private fishTank(b: Batch) {
        const S = this.h.S;
        const c = room('sanh').cx;
        const y = F1;
        const x = c - 2.15;
        const z = -2.35;
        b.add(
            S.rbox(0.5, 0.62, 1.0, 0.04),
            0xffffff,
            { x, y: y + 0.31, z },
            { ao: y, aoH: 0.3 },
        );
        b.add(S.box(0.46, 0.04, 0.96), 0x3a3150, { x, y: y + 0.64, z });
        b.add(S.box(0.46, 0.04, 0.96), 0x3a3150, { x, y: y + 1.16, z });
        b.add(S.box(0.4, 0.06, 0.9), 0xf3e0b0, { x, y: y + 0.69, z });
        for (let k = 0; k < 3; k++) {
            b.add(S.cone(0.04, 0.3, 6), C.leaf, {
                x: x + (k - 1) * 0.08,
                y: y + 0.85,
                z: z - 0.3 + k * 0.25,
                rz: (k - 1) * 0.2,
            });
        }
        b.add(S.sphere(0.07, 8, 6), 0xff9fb7, {
            x: x + 0.05,
            y: y + 0.74,
            z: z + 0.25,
        });
        const water = new THREE.Mesh(
            S.box(0.44, 0.48, 0.94),
            this.h.kit.mat(
                new THREE.MeshBasicMaterial({
                    color: 0x8fd3ff,
                    transparent: true,
                    opacity: 0.35,
                    depthWrite: false,
                }),
            ),
        );
        water.position.set(x, y + 0.9, z);
        water.renderOrder = 3;
        water.raycast = () => undefined;
        this.h.group.add(water);
        this.tankCenter.set(x, y + 0.92, z);
        const cols = [0xff8f4f, 0xffd36a, 0xff6f9f];
        for (let k = 0; k < 3; k++) {
            const f = new THREE.Group();
            const body = new THREE.Mesh(
                S.sphere(0.055, 8, 6),
                this.h.kit.toon(cols[k]),
            );
            body.scale.set(0.6, 0.8, 1.3);
            const tail = new THREE.Mesh(
                S.cone(0.04, 0.06, 4),
                this.h.kit.toon(cols[k]),
            );
            tail.rotation.x = -Math.PI / 2;
            tail.position.z = -0.08;
            f.add(body, tail);
            f.userData.phase = k * 2.1;
            this.h.group.add(f);
            this.fish.push(f);
        }
        const bm = this.h.kit.mat(
            new THREE.MeshBasicMaterial({
                color: 0xffffff,
                transparent: true,
                opacity: 0.7,
            }),
        );
        for (let k = 0; k < 4; k++) {
            const m = new THREE.Mesh(S.sphere(0.018, 6, 4), bm);
            m.userData.phase = k * 0.27;
            this.h.group.add(m);
            this.bubbles.push(m);
        }
    }

    // ---------------------------------------------------------------- trang trí thêm trong nhà chính
    private extraDecor(b: Batch) {
        const S = this.h.S;
        // dây đèn trong vài phòng
        for (const k of [
            'sanh',
            'bienkich',
            'thuam',
            'thodung',
            'giamkhao',
        ] as const) {
            const r = room(k);
            this.fairyString(
                b,
                r.cx - 2.4,
                r.cx + 2.4,
                r.fy + 1.72,
                Z_BACK + 0.07,
                14,
                0.12,
            );
        }
        // chậu cây nhỏ trên hiên
        for (const x of [-12.0, -6.5, 4.0, 8.4]) {
            this.h.plant(b, x, F1, 1.75, 0.7, x > 0 ? 0x7fd18a : C.leaf);
        }
        // ghế xích đu trên hiên Sảnh? -> băng ghế nhỏ trước Kho
        b.add(S.rbox(1.2, 0.08, 0.4, 0.03), C.woodLight, {
            x: room('thukho').cx - 1.2,
            y: F1 + 0.42,
            z: 1.55,
        });
        for (const dx of [-0.5, 0.5]) {
            b.add(S.box(0.06, 0.4, 0.34), C.wood, {
                x: room('thukho').cx - 1.2 + dx,
                y: F1 + 0.2,
                z: 1.55,
            });
        }
    }

    // ---------------------------------------------------------------- bảng tên + vùng bấm
    private signsAndHits() {
        for (const w of WINGS) {
            const tex = this.h.kit.canvas(512, 120, (g, W, H2) => {
                const text = `${w.emoji} ${w.name}`;
                g.font = `800 56px ${FONT}`;
                const tw = Math.min(W - 16, g.measureText(text).width + 64);
                const x0 = (W - tw) / 2;
                roundRect(g, x0 + 3, 9, tw - 6, H2 - 16, (H2 - 16) / 2);
                g.fillStyle = '#4a3868';
                g.fill();
                roundRect(g, x0 + 3, 5, tw - 6, H2 - 18, (H2 - 18) / 2);
                g.fillStyle = '#fffaf2';
                g.fill();
                g.lineWidth = 6;
                g.strokeStyle = '#4a3868';
                g.stroke();
                g.fillStyle = '#4a3868';
                g.textAlign = 'center';
                g.textBaseline = 'middle';
                g.fillText(text, W / 2, H2 / 2 - 4);
            });
            const ww = 3.3;
            const m = new THREE.Mesh(
                this.h.kit.geo(new THREE.PlaneGeometry(ww, (ww * 120) / 512)),
                this.h.kit.basic(0xffffff, {
                    map: tex.texture,
                    transparent: true,
                }),
            );
            m.position.set(w.cx, F2 - SLAB / 2 - 0.02, Z_ROOM + 0.16);
            m.renderOrder = 1;
            this.h.group.add(m);
            const hit = new THREE.Mesh(
                this.h.S.box(w.x1 - w.x0 - 0.25, H - 0.1, Z_ROOM - Z_BACK),
                this.h.kit.basic(0xffffff),
            );
            hit.position.set(w.cx, F1 + H / 2, (Z_BACK + Z_ROOM) / 2);
            hit.visible = false;
            hit.userData.pick = {
                kind: 'place',
                key: w.key,
                name: `${w.emoji} ${w.name}`,
            };
            hit.updateMatrixWorld();
            this.h.group.add(hit);
            this.h.pickRooms.push(hit);
        }
    }

    // ---------------------------------------------------------------- mỗi khung hình
    setNight(n: number) {
        this.night = n;
        this.lamps.forEach((l) => (l.intensity = n * 3.2));
        const on = n > 0.3;
        this.fairy.color.setHex(0xf2e6c8);
        this.fairyMat().color.setHex(on ? 0xffffff : 0xb8b0a0);
        this.warm.color.setHex(on ? 0xffe38a : 0xf3e6cf);
        this.moon.color.setHex(on ? 0xfff2a8 : 0xf6efd0);
    }

    update(t: number, dt: number, now: number) {
        const st = this.state;
        // chảo lật khi nấu
        if (st.cooking) {
            const k = (t * 1.3) % 1;
            const flip = k < 0.35 ? Math.sin((k / 0.35) * Math.PI) : 0;
            this.pan.position.y = this.panPos.y + flip * 0.04;
            this.pan.children[2].position.y = 0.035 + flip * 0.32;
            this.pan.children[3].position.y = 0.05 + flip * 0.32;
            this.pan.children[2].rotation.x = this.pan.children[3].rotation.x =
                (k < 0.35 ? k / 0.35 : 1) * Math.PI * 2;
            this.pan.rotation.z = Math.sin(t * 8) * 0.04;
        } else {
            this.pan.position.y = this.panPos.y;
            this.pan.rotation.z = 0;
        }
        this.steamT -= dt;
        if (this.steamT <= 0) {
            this.steamT = 0.28;
            if (st.cooking) {
                this.fx.steam(
                    this.panPos.clone().add(new THREE.Vector3(0, 0.1, 0)),
                    0.26,
                );
                this.fx.steam(
                    new THREE.Vector3(
                        this.panPos.x - 0.65,
                        this.panPos.y + 0.3,
                        this.panPos.z,
                    ),
                    0.3,
                );
            }
            if (now - st.coffee < 3.5) {
                this.fx.steam(
                    this.machinePos.clone().add(new THREE.Vector3(0, -0.1, 0)),
                    0.16,
                );
            }
        }
        // TV
        this.tvT += dt;
        if (this.tvT > (st.tv ? 0.12 : 2)) {
            this.tvT = 0;
            this.tv.redraw((g, W, H2) => this.drawTv(g, W, H2, t));
        }
        // bi lắc
        const fx = wingOf('giaitri').cx + 1.25;
        if (st.foosball) {
            this.ball.position.x = fx + Math.sin(t * 3.1) * 0.38;
            this.ball.position.z = -0.95 + Math.sin(t * 5.3) * 0.2;
        } else {
            this.ball.position.x = fx;
            this.ball.position.z = -0.95;
        }
        // cá bơi
        const tc = this.tankCenter;
        for (const f of this.fish) {
            const p = f.userData.phase as number;
            const a = t * 0.5 + p;
            f.position.set(
                tc.x + Math.sin(a * 1.3) * 0.1,
                tc.y + Math.sin(a * 0.9 + p) * 0.12,
                tc.z + Math.sin(a) * 0.36,
            );
            f.rotation.y = Math.cos(a) > 0 ? 0 : Math.PI;
        }
        for (const m of this.bubbles) {
            const k = (t * 0.35 + (m.userData.phase as number)) % 1;
            m.position.set(tc.x + 0.08, tc.y - 0.2 + k * 0.42, tc.z + 0.3);
            m.visible = k < 0.95;
        }
        void this.night;
    }
}

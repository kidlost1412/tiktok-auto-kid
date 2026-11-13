// Ngôi nhà 2 tầng kiểu nhà búp bê (bỏ tường trước để nhìn vào): vỏ nhà, cầu thang, gác mái, đồ đạc từng phòng,
// bảng việc ở Sảnh (vẽ canvas), kệ cuộn phim ở Kho hàng, bảng tên phòng.
import * as THREE from 'three';

import {
    BAY,
    BAY_CX,
    BAY_X,
    DESK_Z,
    DOOR2,
    F1,
    F2,
    FA,
    H,
    room,
    ROOMS,
    RW,
    SEAT_Z,
    SLAB,
    STAIR_D,
    STAIR_N,
    STAIR_R,
    STAIR_W,
    STAIR_Z0,
    STAIR_Z1,
    X0,
    X1,
    XL0,
    XR1,
    Z_BACK,
    Z_FRONT,
    Z_ROOM,
} from './layout';
import {
    Batch,
    C,
    CanvasTex,
    fitText,
    FONT,
    Kit,
    radialTexture,
    roundRect,
    Shapes,
} from './util';

export interface Reel {
    n: number;
    so: number;
    file: string;
    ngay: string;
    diem: number | null;
}

export interface FadeWall {
    mesh: THREE.Mesh;
    normal: THREE.Vector3;
    mat: THREE.MeshToonMaterial;
    op: number;
}

interface Glow {
    sprite: THREE.Sprite;
    mat: THREE.SpriteMaterial;
    on: boolean;
    base: number;
}

export const RIDGE_Z = (Z_BACK - 0.3 + Z_ROOM + 0.15) / 2;
export const RIDGE_Y = FA + 2.5;
export const BACK_EAVE_Z = Z_BACK - 0.9;
export const FRONT_EAVE_Z = Z_ROOM + 0.75;
/** Khoảng hở giữa mái trước để nhìn thấy gác mái (Cú). */
export const DORMER = 3.7;

export class House {
    readonly group = new THREE.Group();
    readonly occluders: THREE.Object3D[] = [];
    readonly pickRooms: THREE.Mesh[] = [];
    readonly fadeWalls: FadeWall[] = [];
    readonly board: CanvasTex;
    readonly reelGroup = new THREE.Group();
    readonly reelSlots: THREE.Vector3[] = [];
    readonly reelMeshes = new Map<number, THREE.Mesh>();
    readonly deskTops: Record<string, THREE.Vector3> = {};
    readonly lights: THREE.PointLight[] = [];
    private reelGeo!: THREE.BufferGeometry;
    private reelMat!: THREE.Material;
    private glows: Record<string, Glow[]> = {};
    private lampShades: { mat: THREE.MeshBasicMaterial; key: string | null }[] =
        [];
    private leds: THREE.MeshBasicMaterial[] = [];
    private onAir!: THREE.MeshBasicMaterial;
    private rgb: THREE.MeshBasicMaterial[] = [];
    private glass: THREE.MeshBasicMaterial;
    private stringLights: THREE.MeshBasicMaterial[] = [];
    private turntable!: THREE.Object3D;
    private glowTex: THREE.Texture;
    private working = new Set<string>();
    private night = 0;
    readonly S: Shapes;

    constructor(
        readonly kit: Kit,
        shapes: Shapes,
    ) {
        this.S = shapes;
        this.glowTex = radialTexture(
            kit,
            'rgba(255,255,255,0.9)',
            'rgba(255,255,255,0)',
        );
        this.glass = kit.basic(0xbfe6ff);
        const shell = new Batch();
        const floors = new Batch();
        const furn = new Batch();
        this.buildShell(shell, floors);
        this.buildStairs(shell, furn);
        this.buildRoof(shell);
        this.buildRooms(furn);
        this.buildAttic(furn);
        const shellMesh = shell.build(kit, { cast: true, receive: false });
        const floorMesh = floors.build(kit, { receive: false });
        const furnMesh = furn.build(kit, { cast: false });
        shellMesh.name = 'shell';
        floorMesh.name = 'floors';
        furnMesh.name = 'furn';
        this.group.add(shellMesh, floorMesh, furnMesh, this.reelGroup);
        this.occluders.push(shellMesh);
        this.board = this.buildBoard();
        this.buildSigns();
        this.buildHitBoxes();
        this.buildLights();
    }

    // ---------------------------------------------------------------- vỏ nhà
    private buildShell(b: Batch, floors: Batch) {
        const S = this.S;
        const D = Z_FRONT - (Z_BACK - 0.3);
        const zc = (Z_FRONT + Z_BACK - 0.3) / 2;
        // móng
        // mặt trên móng thấp hơn mặt sàn 3cm (nằm dưới ván sàn) để hai mặt không trùng nhau gây nhấp nháy
        b.add(S.box(XR1 - XL0 + 1.5, F1 - 0.03, D + 0.4), C.lavMid, {
            y: (F1 - 0.03) / 2,
            z: zc + 0.1,
        });
        b.add(S.box(XR1 - XL0 + 1.6, 0.08, 0.12), C.trim, {
            y: F1 - 0.02,
            z: Z_FRONT + 0.27,
        });
        // sàn gỗ từng phòng + hành lang
        for (const r of ROOMS) {
            const x0 = X0 + r.i * RW;
            const n = 10;
            const dz = (Z_ROOM - Z_BACK) / n;
            for (let k = 0; k < n; k++) {
                floors.add(
                    S.box(RW, 0.06, dz - 0.015),
                    k % 2 ? r.floorA : r.floorB,
                    {
                        x: x0 + RW / 2,
                        y: r.fy - 0.03,
                        z: Z_BACK + dz * (k + 0.5),
                    },
                );
            }
            // thảm tròn nhỏ có viền (màu đậm hơn sàn để không trông như cái lỗ)
            const rug: Partial<Record<string, [number, number]>> = {
                giamkhao: [0xb79be8, 0x8a6fd6],
                sanh: [0xffc6d6, 0xff8fa3],
                bienkich: [0xa8e0cf, 0x6fbfa8],
                thuam: [0xb79be8, 0x7a5fc6],
                daodien: [0xffd9a0, 0xe8a85a],
                thodung: [0x9fb0e8, 0x6a7fd0],
            };
            const rc = rug[r.key];
            if (rc) {
                const rx =
                    r.cx +
                    (r.key === 'sanh' ? 0 : r.key === 'daodien' ? 0 : -0.6);
                floors.add(S.cyl(0.95, 0.95, 0.02, 28), rc[1], {
                    x: rx,
                    y: r.fy + 0.008,
                    z: -0.75,
                    sx: 1.3,
                });
                floors.add(S.cyl(0.82, 0.82, 0.02, 28), rc[0], {
                    x: rx,
                    y: r.fy + 0.016,
                    z: -0.75,
                    sx: 1.3,
                });
            }
        }
        // hiên tầng 1 (ván gỗ, không mái)
        for (let k = 0; k < 5; k++) {
            const dz = (Z_FRONT - Z_ROOM) / 5;
            floors.add(
                S.box(XR1 - XL0 + 0.6, 0.06, dz - 0.015),
                k % 2 ? 0xf1e0c6 : 0xe9d5b7,
                {
                    x: (XL0 + XR1) / 2,
                    y: F1 - 0.03,
                    z: Z_ROOM + dz * (k + 0.5),
                },
            );
        }
        // khoang cầu thang tầng 1 (sàn sau gầm thang)
        floors.add(S.box(BAY, 0.06, Z_ROOM - Z_BACK), 0xe9d5b7, {
            x: BAY_CX,
            y: F1 - 0.03,
            z: (Z_ROOM + Z_BACK) / 2,
        });
        // sàn chiếu nghỉ tầng 2
        floors.add(S.box(BAY, 0.06, STAIR_Z1 - Z_BACK), 0xe9d5b7, {
            x: BAY_CX,
            y: F2 - 0.03,
            z: (STAIR_Z1 + Z_BACK) / 2,
        });

        // sàn giữa các tầng (tấm) + nẹp tím mặt trước
        const slab = (
            y: number,
            x0: number,
            x1: number,
            z0: number,
            z1: number,
            trim: boolean,
        ) => {
            b.add(S.box(x1 - x0, SLAB - 0.06, z1 - z0), C.lav, {
                x: (x0 + x1) / 2,
                y: y - SLAB / 2 - 0.03,
                z: (z0 + z1) / 2,
            });
            if (trim) {
                b.add(S.rbox(x1 - x0 + 0.1, SLAB + 0.04, 0.14, 0.05), C.trim, {
                    x: (x0 + x1) / 2,
                    y: y - SLAB / 2,
                    z: z1 + 0.05,
                });
                b.add(S.box(x1 - x0, 0.03, 0.02), 0xb7a2f0, {
                    x: (x0 + x1) / 2,
                    y: y - 0.04,
                    z: z1 + 0.125,
                });
            }
        };
        slab(F2, X0 - 0.3, BAY_X, Z_BACK - 0.3, Z_ROOM, true);
        slab(F2, BAY_X, X1 + 0.3, Z_BACK - 0.3, STAIR_Z1, false);
        slab(FA, X0 - 0.3, X1 + 0.3, Z_BACK - 0.3, Z_ROOM, true);
        // tường sau theo từng phòng (màu giấy dán tường) + ốp chân tường
        const back = (
            x0: number,
            x1: number,
            fy: number,
            wall: number,
            wain: number,
        ) => {
            b.add(
                S.box(x1 - x0, H, 0.3),
                wall,
                { x: (x0 + x1) / 2, y: fy + H / 2, z: Z_BACK - 0.15 },
                { ao: fy, aoH: 0.9 },
            );
            b.add(
                S.box(x1 - x0, 0.85, 0.05),
                wain,
                { x: (x0 + x1) / 2, y: fy + 0.425, z: Z_BACK + 0.025 },
                { ao: fy, aoH: 0.5 },
            );
            b.add(S.box(x1 - x0, 0.06, 0.08), 0xfffaf2, {
                x: (x0 + x1) / 2,
                y: fy + 0.86,
                z: Z_BACK + 0.04,
            });
            b.add(S.box(x1 - x0, 0.12, 0.06), 0xfffaf2, {
                x: (x0 + x1) / 2,
                y: fy + H - 0.06,
                z: Z_BACK + 0.03,
            });
        };
        for (const r of ROOMS) {
            back(X0 + r.i * RW, X0 + (r.i + 1) * RW, r.fy, r.wall, r.wain);
        }
        back(BAY_X, X1, F1, 0xf6efff, 0xe2d4fa);
        back(BAY_X, X1, F2, 0xf6efff, 0xe2d4fa);
        // vách ngăn: hai lớp mỏng mang màu hai phòng kề nhau + nẹp đầu vách
        const part = (
            x: number,
            fy: number,
            left: number,
            right: number,
            door: 'back' | 'front' | null = null,
        ) => {
            const seg = (z0: number, z1: number, y0: number, y1: number) => {
                for (const [dx, col] of [
                    [-0.05, left],
                    [0.05, right],
                ] as const) {
                    b.add(
                        S.box(0.1, y1 - y0, z1 - z0),
                        col,
                        { x: x + dx, y: (y0 + y1) / 2, z: (z0 + z1) / 2 },
                        { ao: fy, aoH: 0.9 },
                    );
                }
            };
            const doorway = (z0: number, z1: number) => {
                const top = fy + 2.3;
                seg(z0, z1, top, fy + H);
                b.add(S.box(0.3, 0.1, z1 - z0 + 0.08), C.woodLight, {
                    x,
                    y: top,
                    z: (z0 + z1) / 2,
                });
                for (const z of [z0, z1]) {
                    b.add(S.box(0.3, 2.3, 0.08), C.woodLight, {
                        x,
                        y: fy + 1.15,
                        z,
                    });
                }
            };
            if (door === 'back') {
                // cửa sau phòng dựng thông ra chiếu nghỉ
                seg(Z_BACK, -3.45, fy, fy + H);
                seg(-2.6, Z_ROOM, fy, fy + H);
                doorway(-3.45, -2.6);
            } else if (door === 'front') {
                // tầng 2: cửa thông giữa các phòng ở phía trước
                seg(Z_BACK, DOOR2, fy, fy + H);
                doorway(DOOR2, Z_ROOM - 0.06);
            } else {
                seg(Z_BACK, Z_ROOM, fy, fy + H);
                b.add(S.box(0.22, 0.2, 0.06), 0xfffaf2, {
                    x,
                    y: fy + 0.1,
                    z: Z_ROOM - 0.4,
                });
            }
            b.add(S.rbox(0.3, H, 0.16, 0.05), 0xfffaf2, {
                x,
                y: fy + H / 2,
                z: Z_ROOM + 0.02,
            });
        };
        const f1 = ROOMS.filter((r) => r.floor === 1);
        const f2 = ROOMS.filter((r) => r.floor === 2);
        for (let k = 1; k <= 4; k++) {
            const x = X0 + k * RW;
            part(x, F1, f1[k - 1].wall, k < 4 ? f1[k].wall : 0xf6efff);
            part(
                x,
                F2,
                f2[k - 1].wall,
                k < 4 ? f2[k].wall : 0xf6efff,
                k === 4 ? 'back' : 'front',
            );
        }
        // lan can thấp mép trước tầng 2 (con tiện nhỏ, thấp để không che người)
        for (let x = X0 + 0.25; x < BAY_X - 0.1; x += 0.36) {
            b.add(S.cyl(0.035, 0.035, 0.42, 8), C.woodLight, {
                x,
                y: F2 + 0.21,
                z: Z_ROOM + 0.04,
            });
        }
        b.add(S.rbox(BAY_X - X0, 0.07, 0.12, 0.03), C.wood, {
            x: (X0 + BAY_X) / 2,
            y: F2 + 0.44,
            z: Z_ROOM + 0.04,
        });
        // cột hiên + bậc lên hiên
        for (const x of [X0 + 0.15, X1 - 0.15]) {
            b.add(S.rbox(0.26, F2 - F1 - SLAB, 0.26, 0.06), 0xfffaf2, {
                x,
                y: F1 + (F2 - F1 - SLAB) / 2,
                z: Z_ROOM + 0.1,
            });
        }
        // lan can chiếu nghỉ
        for (let x = BAY_X + 0.25; x < X1; x += 0.42) {
            if (Math.abs(x - BAY_CX) > STAIR_W / 2 - 0.05) {
                b.add(S.cyl(0.04, 0.04, 0.85, 8), C.woodLight, {
                    x,
                    y: F2 + 0.42,
                    z: STAIR_Z1 + 0.06,
                });
            }
        }

        // hai tường đầu hồi (mờ đi khi xoay camera về phía đó)
        for (const side of [-1, 1] as const) {
            const wb = new Batch();
            const x = side < 0 ? X0 - 0.15 : X1 + 0.15;
            const z0 = Z_BACK - 0.3;
            const zf = Z_ROOM + 0.15;
            wb.add(S.box(0.3, FA, zf - z0), C.wallOut, {
                x,
                y: FA / 2,
                z: (zf + z0) / 2,
            });
            // lớp trong mang màu phòng
            const rl = side < 0 ? [room('giamkhao'), room('bienkich')] : null;
            if (rl) {
                for (const r of rl) {
                    wb.add(
                        S.box(0.02, H, Z_ROOM - Z_BACK),
                        r.wall,
                        {
                            x: x + 0.16,
                            y: r.fy + H / 2,
                            z: (Z_ROOM + Z_BACK) / 2,
                        },
                        { ao: r.fy, aoH: 0.9 },
                    );
                }
            }
            // đầu hồi tam giác
            const tri = new THREE.Shape();
            tri.moveTo(z0 - 0.0, 0);
            tri.lineTo(zf, 0);
            tri.lineTo(RIDGE_Z, RIDGE_Y - FA - 0.15);
            tri.closePath();
            const tg = new THREE.ExtrudeGeometry(tri, {
                depth: 0.3,
                bevelEnabled: false,
            });
            tg.rotateY(-Math.PI / 2);
            wb.add(
                tg,
                C.wallOut,
                { x: x - 0.15 * -1 + (side < 0 ? 0 : 0), y: FA, z: 0 },
                { dispose: true },
            );
            // viền góc + cửa sổ tròn
            wb.add(S.rbox(0.36, FA + 0.05, 0.22, 0.06), 0xfffaf2, {
                x,
                y: FA / 2,
                z: zf - 0.05,
            });
            wb.add(S.torus(0.5, 0.09, 8, 24), C.trim, {
                x: x + side * 0.16,
                y: FA + 1.3,
                z: RIDGE_Z + 0.6,
                ry: Math.PI / 2,
            });
            wb.add(S.cyl(0.47, 0.47, 0.04, 24), 0xcfeaff, {
                x: x + side * 0.15,
                y: FA + 1.3,
                z: RIDGE_Z + 0.6,
                rz: Math.PI / 2,
            });
            // cửa sổ hông mỗi tầng
            for (const fy of [F1, F2]) {
                wb.add(S.rbox(0.12, 1.3, 1.5, 0.05), 0xfffaf2, {
                    x: x + side * 0.16,
                    y: fy + 1.6,
                    z: -1.7,
                });
                wb.add(S.box(0.06, 1.1, 1.3), 0xcfeaff, {
                    x: x + side * 0.2,
                    y: fy + 1.6,
                    z: -1.7,
                });
                wb.add(S.box(0.08, 1.1, 0.06), 0xfffaf2, {
                    x: x + side * 0.23,
                    y: fy + 1.6,
                    z: -1.7,
                });
                wb.add(S.rbox(0.3, 0.1, 1.7, 0.04), C.trim, {
                    x: x + side * 0.22,
                    y: fy + 0.95,
                    z: -1.7,
                });
            }
            const mat = this.kit.toonOwn(0xffffff, {
                vertexColors: true,
                transparent: true,
                opacity: 1,
            });
            const mesh = wb.build(this.kit, { cast: true, material: mat });
            // tam giác đùn ra theo trục x: đặt lại cho đúng mép
            mesh.position.x += side * 0.006; // không trùng mặt tường vỏ nhà
            this.group.add(mesh);
            this.fadeWalls.push({
                mesh,
                normal: new THREE.Vector3(side, 0, 0),
                mat,
                op: 1,
            });
        }
    }

    // ---------------------------------------------------------------- cầu thang
    private buildStairs(b: Batch, furn: Batch) {
        const S = this.S;
        for (let i = 0; i < STAIR_N; i++) {
            const top = F1 + (i + 1) * STAIR_R;
            const zf = STAIR_Z0 - i * STAIR_D;
            const zb = zf - STAIR_D;
            b.add(
                S.box(STAIR_W, top - F1 + 0.02, STAIR_D),
                i % 2 ? 0xe9cfa8 : 0xe2c497,
                { x: BAY_CX, y: (top + F1) / 2 - 0.01, z: (zf + zb) / 2 },
            );
            b.add(S.box(STAIR_W + 0.02, 0.05, 0.06), 0xfffaf2, {
                x: BAY_CX,
                y: top - 0.02,
                z: zf - 0.02,
            });
        }
        // tay vịn bên trái
        const x = BAY_CX - STAIR_W / 2 - 0.06;
        for (let i = 0; i <= STAIR_N; i += 2) {
            const z = STAIR_Z0 - i * STAIR_D - STAIR_D / 2;
            const y = F1 + (i + 1) * STAIR_R;
            furn.add(S.cyl(0.04, 0.04, 0.9, 8), C.woodLight, {
                x,
                y: y + 0.45,
                z,
            });
        }
        const len = Math.hypot(STAIR_Z0 - STAIR_Z1, F2 - F1);
        const ang = Math.atan2(F2 - F1, STAIR_Z0 - STAIR_Z1);
        furn.add(S.rbox(0.1, 0.08, len, 0.03), C.wood, {
            x,
            y: (F1 + F2) / 2 + 0.95,
            z: (STAIR_Z0 + STAIR_Z1) / 2 - STAIR_D / 2,
            rx: ang,
        });
        // cây cảnh dưới chân thang
        this.plant(furn, BAY_CX + 1.45, F1, 0.75, 0.75);
    }

    // ---------------------------------------------------------------- mái
    private buildRoof(b: Batch) {
        const S = this.S;
        const W = X1 - X0 + 1.4;
        // mái sau: các hàng ngói xếp chồng
        const run = RIDGE_Z - BACK_EAVE_Z;
        const rise = RIDGE_Y - FA + 0.2;
        const len = Math.hypot(run, rise);
        const ang = Math.atan2(rise, run);
        const rows = 7;
        for (let k = 0; k < rows; k++) {
            const t0 = k / rows;
            const t1 = (k + 1) / rows;
            const zm = BACK_EAVE_Z + run * ((t0 + t1) / 2);
            const ym = FA - 0.2 + rise * ((t0 + t1) / 2);
            b.add(S.box(W, 0.2, len / rows + 0.12), k % 2 ? C.roofA : C.roofB, {
                y: ym + 0.08,
                z: zm,
                rx: -ang,
            });
        }
        // mặt trong mái (gỗ tím nhạt) + xà
        b.add(S.box(W - 0.6, 0.06, len), 0xe6d8f6, {
            y: FA - 0.2 + rise / 2 - 0.08,
            z: BACK_EAVE_Z + run / 2 + 0.04,
            rx: -ang,
        });
        for (let k = 0; k < 6; k++) {
            b.add(S.box(0.16, 0.16, len - 0.3), 0xcdb8f2, {
                x: X0 + 1.5 + k * ((X1 - X0 - 3) / 5),
                y: FA - 0.2 + rise / 2 - 0.16,
                z: BACK_EAVE_Z + run / 2 + 0.08,
                rx: -ang,
            });
        }
        // nóc
        b.add(S.cyl(0.18, 0.18, W + 0.1, 12), C.purpleDeep, {
            y: RIDGE_Y + 0.05,
            z: RIDGE_Z,
            rz: Math.PI / 2,
        });
        // mái trước: hai nửa hai bên, chừa khoảng giữa (DORMER) để nhìn vào gác mái
        const fr = FRONT_EAVE_Z - RIDGE_Z;
        const fang = Math.atan2(rise, fr);
        const fl = Math.hypot(fr, rise);
        for (const side of [-1, 1]) {
            const xa = side < 0 ? X0 - 0.7 : DORMER;
            const xb = side < 0 ? -DORMER : X1 + 0.7;
            for (let k = 0; k < rows; k++) {
                const t = (k + 0.5) / rows;
                b.add(
                    S.box(xb - xa, 0.2, fl / rows + 0.12),
                    k % 2 ? C.roofA : C.roofB,
                    {
                        x: (xa + xb) / 2,
                        y: FA - 0.2 + rise * t + 0.08,
                        z: FRONT_EAVE_Z - fr * t,
                        rx: fang,
                    },
                );
            }
            b.add(S.rbox(xb - xa + 0.2, 0.16, 0.18, 0.06), C.trim, {
                x: (xa + xb) / 2,
                y: FA - 0.18,
                z: FRONT_EAVE_Z + 0.05,
            });
            // má tường hai bên khoảng hở
            const xc = side * DORMER;
            const za = FRONT_EAVE_Z - (0.25 * fr) / rise;
            const tri = new THREE.Shape();
            tri.moveTo(za, 0);
            tri.lineTo(RIDGE_Z, 0);
            tri.lineTo(RIDGE_Z, rise - 0.3);
            tri.closePath();
            const tg = new THREE.ExtrudeGeometry(tri, {
                depth: 0.24,
                bevelEnabled: false,
            });
            tg.rotateY(-Math.PI / 2);
            b.add(
                tg,
                C.wallOut,
                { x: xc + 0.12, y: FA - 0.05, z: 0 },
                { dispose: true },
            );
            b.add(S.rbox(0.26, 0.2, fl + 0.1, 0.06), C.trim, {
                x: xc,
                y: FA - 0.1 + rise / 2 + 0.1,
                z: RIDGE_Z + fr / 2,
                rx: fang,
            });
            // diềm hai bên đầu hồi
            const x = side < 0 ? X0 - 0.75 : X1 + 0.75;
            b.add(S.rbox(0.2, 0.2, len + 0.2, 0.06), C.trim, {
                x,
                y: FA - 0.1 + rise / 2,
                z: BACK_EAVE_Z + run / 2,
                rx: -ang,
            });
            b.add(S.rbox(0.2, 0.2, fl + 0.1, 0.06), C.trim, {
                x,
                y: FA - 0.1 + rise / 2,
                z: RIDGE_Z + fr / 2,
                rx: fang,
            });
        }
        // ống khói
        const cz = BACK_EAVE_Z + run * 0.55;
        const cy = FA - 0.2 + rise * 0.55;
        b.add(S.box(0.9, 2.2, 0.9), 0xe8a98f, {
            x: X0 + 4.2,
            y: cy + 0.7,
            z: cz,
        });
        b.add(S.rbox(1.15, 0.25, 1.15, 0.07), 0xc98568, {
            x: X0 + 4.2,
            y: cy + 1.85,
            z: cz,
        });
        this.chimney = new THREE.Vector3(X0 + 4.2, cy + 2.0, cz);
    }

    chimney = new THREE.Vector3();

    // ---------------------------------------------------------------- đồ dùng chung
    desk(
        b: Batch,
        x: number,
        y: number,
        z: number,
        w: number,
        d: number,
        col: number,
        drawer = true,
    ) {
        const S = this.S;
        b.add(S.rbox(w, 0.08, d, 0.035), col, { x, y: y + 0.68, z });
        b.add(
            S.box(w - 0.12, 0.03, d - 0.06),
            0xffffff,
            { x, y: y + 0.722, z },
            { shade: 0.0 + 0.97 },
        );
        for (const sx of [-1, 1]) {
            b.add(
                S.box(0.07, 0.64, d - 0.12),
                col,
                { x: x + sx * (w / 2 - 0.08), y: y + 0.32, z },
                { ao: y, aoH: 0.4, shade: 0.9 },
            );
        }
        if (drawer) {
            b.add(
                S.rbox(0.5, 0.5, d - 0.14, 0.03),
                col,
                { x: x - w / 2 + 0.36, y: y + 0.36, z },
                { ao: y, aoH: 0.3 },
            );
            for (const k of [0, 1]) {
                b.add(S.box(0.12, 0.03, 0.03), 0xfff3c9, {
                    x: x - w / 2 + 0.36,
                    y: y + 0.26 + k * 0.2,
                    z: z + d / 2 - 0.05,
                });
            }
        }
        b.add(
            S.box(w - 0.2, 0.3, 0.03),
            col,
            { x, y: y + 0.48, z: z - d / 2 + 0.08 },
            { shade: 0.85 },
        );
    }

    chair(
        b: Batch,
        x: number,
        y: number,
        z: number,
        col: number,
        gaming = false,
    ) {
        const S = this.S;
        b.add(S.rbox(0.52, 0.09, 0.48, 0.04), col, { x, y: y + 0.44, z });
        b.add(S.rbox(0.5, gaming ? 0.85 : 0.5, 0.08, 0.04), col, {
            x,
            y: y + (gaming ? 0.92 : 0.74),
            z: z - 0.25,
            rx: -0.08,
        });
        if (gaming) {
            b.add(S.rbox(0.3, 0.12, 0.09, 0.04), 0x2b2440, {
                x,
                y: y + 1.22,
                z: z - 0.27,
            });
            b.add(S.box(0.06, 0.6, 0.085), 0x2b2440, {
                x: x - 0.12,
                y: y + 0.88,
                z: z - 0.245,
            });
            b.add(S.box(0.06, 0.6, 0.085), 0x2b2440, {
                x: x + 0.12,
                y: y + 0.88,
                z: z - 0.245,
            });
        }
        b.add(S.cyl(0.04, 0.04, 0.36, 8), 0x8a8299, { x, y: y + 0.22, z });
        for (let k = 0; k < 5; k++) {
            const a = (k / 5) * Math.PI * 2;
            b.add(S.box(0.06, 0.04, 0.3), 0x6d6480, {
                x: x + Math.sin(a) * 0.14,
                y: y + 0.05,
                z: z + Math.cos(a) * 0.14,
                ry: a,
            });
            b.add(S.sphere(0.035, 8, 6), 0x3a3150, {
                x: x + Math.sin(a) * 0.28,
                y: y + 0.035,
                z: z + Math.cos(a) * 0.28,
            });
        }
    }

    plant(
        b: Batch,
        x: number,
        y: number,
        z: number,
        s = 1,
        leaf: number = C.leaf,
    ) {
        const S = this.S;
        b.add(
            S.cyl(0.2 * s, 0.15 * s, 0.32 * s, 14),
            0xf0a585,
            { x, y: y + 0.16 * s, z },
            { ao: y, aoH: 0.2 },
        );
        b.add(S.cyl(0.21 * s, 0.21 * s, 0.05 * s, 14), 0xe08f6f, {
            x,
            y: y + 0.32 * s,
            z,
        });
        for (let k = 0; k < 5; k++) {
            const a = (k / 5) * Math.PI * 2;
            b.add(S.sphere(0.16 * s, 10, 8), k % 2 ? leaf : C.leaf3, {
                x: x + Math.sin(a) * 0.12 * s,
                y: y + (0.5 + (k % 3) * 0.1) * s,
                z: z + Math.cos(a) * 0.12 * s,
                sy: 1.4,
            });
        }
        b.add(S.sphere(0.17 * s, 10, 8), C.leaf2, {
            x,
            y: y + 0.72 * s,
            z,
            sy: 1.3,
        });
    }

    lamp(b: Batch, x: number, y: number, z: number, key: string | null) {
        const S = this.S;
        b.add(S.cyl(0.12, 0.14, 0.04, 14), C.purpleDeep, { x, y: y + 0.02, z });
        b.add(S.cyl(0.02, 0.02, 0.45, 6), C.purpleDeep, {
            x,
            y: y + 0.25,
            z,
            rz: 0.2,
        });
        const mat = this.kit.basic(0xf3e6cf);
        const shade = new THREE.Mesh(S.cone(0.15, 0.17, 16), mat);
        shade.position.set(x - 0.08, y + 0.5, z);
        shade.rotation.z = 0.35;
        this.group.add(shade);
        this.lampShades.push({ mat, key });
        if (key) {
            this.glow(key, x - 0.1, y + 0.35, z + 0.05, 0xffe08a, 1.3);
        }
    }

    /** Quầng sáng (màn hình/đèn bật) gắn với vai đang làm. */
    glow(
        key: string,
        x: number,
        y: number,
        z: number,
        color: number,
        size: number,
    ) {
        const mat = this.kit.mat(
            new THREE.SpriteMaterial({
                map: this.glowTex,
                color,
                transparent: true,
                opacity: 0,
                depthWrite: false,
                blending: THREE.AdditiveBlending,
            }),
        );
        const sp = new THREE.Sprite(mat);
        sp.position.set(x, y, z);
        sp.scale.setScalar(size);
        sp.raycast = () => undefined;
        this.group.add(sp);
        (this.glows[key] ??= []).push({
            sprite: sp,
            mat,
            on: false,
            base: 0.55,
        });
    }

    private monitor(
        b: Batch,
        x: number,
        y: number,
        z: number,
        ry: number,
        w: number,
        key: string,
        col: number,
    ) {
        const S = this.S;
        const g = new THREE.Group();
        g.position.set(x, y, z);
        g.rotation.y = ry;
        // chân + khung (khối gộp được đặt theo ma trận nhóm)
        g.updateMatrixWorld();
        const m = (p: THREE.Vector3) => p.applyMatrix4(g.matrixWorld);
        const base = m(new THREE.Vector3(0, 0.02, 0.05));
        b.add(S.cyl(0.1, 0.12, 0.03, 12), 0x3a3150, {
            x: base.x,
            y: base.y,
            z: base.z,
        });
        const neck = m(new THREE.Vector3(0, 0.18, 0.05));
        b.add(S.box(0.05, 0.3, 0.04), 0x3a3150, {
            x: neck.x,
            y: neck.y,
            z: neck.z,
            ry,
        });
        const fr = m(new THREE.Vector3(0, 0.42, 0));
        b.add(S.rbox(w, w * 0.62, 0.06, 0.025), 0x3a3150, {
            x: fr.x,
            y: fr.y,
            z: fr.z,
            ry,
        });
        // màn hình (quay về phía người ngồi, tức -z cục bộ)
        const scr = new THREE.Mesh(
            S.plane(w - 0.06, w * 0.62 - 0.06),
            this.screenMat(key, col),
        );
        scr.position.set(0, 0.42, -0.035);
        scr.rotation.y = Math.PI;
        g.add(scr);
        // đèn nhỏ sau lưng màn
        const led = new THREE.Mesh(
            S.sphere(0.018, 6, 5),
            this.screenMat(key, col),
        );
        led.position.set(w / 2 - 0.06, 0.42 - w * 0.25, 0.035);
        g.add(led);
        this.group.add(g);
        const gp = m(new THREE.Vector3(0, 0.42, -0.35));
        this.glow(key, gp.x, gp.y, gp.z, col, 1.1);
    }

    private screenMats = new Map<string, THREE.MeshBasicMaterial>();

    private screenMat(key: string, col: number) {
        const k = `${key}|${col}`;
        let m = this.screenMats.get(k);
        if (!m) {
            m = this.kit.basic(0x2c2a44);
            m.userData = { key, on: col, off: 0x2c2a44 };
            this.screenMats.set(k, m);
        }

        return m;
    }

    books(b: Batch, x: number, y: number, z: number, w: number, seed = 1) {
        const S = this.S;
        const cols = [
            C.pink,
            C.mint,
            C.yellow,
            C.blue,
            C.purple,
            C.orange,
            0x9ad0ec,
            0xf7b267,
        ];
        let cx = x - w / 2 + 0.05;
        let i = seed;
        while (cx < x + w / 2 - 0.08) {
            const bw = 0.07 + ((i * 37) % 5) * 0.012;
            const bh = 0.26 + ((i * 53) % 4) * 0.035;
            b.add(S.box(bw, bh, 0.26), cols[i % cols.length], {
                x: cx + bw / 2,
                y: y + bh / 2,
                z,
                rz: i % 7 === 0 ? 0.18 : 0,
            });
            cx += bw + 0.012;
            i++;
        }
    }

    shelfUnit(
        b: Batch,
        x: number,
        y: number,
        z: number,
        w: number,
        h: number,
        tiers: number,
        col: number,
    ) {
        const S = this.S;
        for (const sx of [-1, 1]) {
            b.add(
                S.box(0.06, h, 0.42),
                col,
                { x: x + sx * (w / 2 - 0.03), y: y + h / 2, z },
                { ao: y, aoH: 0.4 },
            );
        }
        b.add(
            S.box(w, h, 0.03),
            col,
            { x, y: y + h / 2, z: z - 0.2 },
            { shade: 0.85 },
        );
        for (let k = 0; k <= tiers; k++) {
            b.add(S.box(w, 0.05, 0.42), col, {
                x,
                y: y + 0.05 + (k * (h - 0.1)) / tiers,
                z,
            });
        }
    }

    frame(
        x: number,
        y: number,
        z: number,
        w: number,
        h: number,
        draw: (g: CanvasRenderingContext2D, W: number, H: number) => void,
        px = 256,
    ) {
        const tex = this.kit.canvas(px, Math.round((px * h) / w), draw);
        const m = new THREE.Mesh(
            this.kit.geo(new THREE.PlaneGeometry(w, h)),
            this.kit.basic(0xffffff, { map: tex.texture }),
        );
        m.position.set(x, y, z);
        this.group.add(m);

        return tex;
    }

    // ---------------------------------------------------------------- các phòng
    private buildRooms(b: Batch) {
        const S = this.S;
        const zb = Z_BACK + 0.22;
        // ===== Phòng chấm
        {
            const r = room('giamkhao');
            const c = r.cx;
            const y = r.fy;
            this.desk(b, c, y, DESK_Z, 2.0, 0.8, 0xb59be8);
            this.chair(b, c, y, SEAT_Z, 0x8a6fd6);
            this.lamp(b, c + 0.75, y + 0.72, DESK_Z - 0.1, 'giamkhao');
            this.deskTops.giamkhao = new THREE.Vector3(
                c - 0.55,
                y + 0.73,
                DESK_Z + 0.05,
            );
            // giấy + kính lúp
            b.add(S.box(0.45, 0.06, 0.32), 0xffffff, {
                x: c - 0.1,
                y: y + 0.75,
                z: DESK_Z + 0.05,
                ry: 0.1,
            });
            b.add(S.torus(0.09, 0.02, 6, 18), 0xd9a441, {
                x: c + 0.35,
                y: y + 0.74,
                z: DESK_Z + 0.15,
                rx: Math.PI / 2,
            });
            b.add(S.cyl(0.02, 0.02, 0.18, 6), 0x7a4a2c, {
                x: c + 0.47,
                y: y + 0.74,
                z: DESK_Z + 0.26,
                rz: Math.PI / 2,
                ry: -0.7,
            });
            // bảng điểm trên tường
            const nums = ['7', '8', '9'];
            nums.forEach((n, i) => {
                const fx = c - 1.15 + i * 1.15;
                b.add(S.rbox(0.84, 0.74, 0.06, 0.04), 0x4a3868, {
                    x: fx,
                    y: y + 1.32,
                    z: Z_BACK + 0.04,
                });
                this.frame(
                    fx,
                    y + 1.32,
                    Z_BACK + 0.08,
                    0.72,
                    0.62,
                    (g, W, H2) => {
                        g.fillStyle = i === 2 ? '#3a2c55' : '#fff8ec';
                        g.fillRect(0, 0, W, H2);
                        g.fillStyle = i === 2 ? '#ffd36a' : '#6a52b8';
                        g.font = `900 ${H2 * 0.7}px ${FONT}`;
                        g.textAlign = 'center';
                        g.textBaseline = 'middle';
                        g.fillText(n, W / 2, H2 * 0.55);
                        g.fillStyle = '#ffd36a';
                        g.font = `700 ${H2 * 0.16}px ${FONT}`;
                        g.fillText(
                            '★ ★ ★'.slice(0, 1 + i * 2),
                            W / 2,
                            H2 * 0.14,
                        );
                    },
                );
            });
            // tủ cúp bên trái
            this.shelfUnit(
                b,
                c - 1.95,
                y,
                Z_BACK + 0.22,
                1.0,
                1.5,
                3,
                0xcdb8f2,
            );
            for (let k = 0; k < 3; k++) {
                for (const dx of [-0.25, 0.25]) {
                    const tx = c - 1.95 + dx;
                    const ty = y + 0.1 + k * 0.47;
                    const tz = Z_BACK + 0.25;
                    b.add(S.cyl(0.05, 0.07, 0.06, 10), 0xd9a441, {
                        x: tx,
                        y: ty + 0.03,
                        z: tz,
                    });
                    b.add(S.cyl(0.03, 0.03, 0.08, 8), 0xffc93c, {
                        x: tx,
                        y: ty + 0.1,
                        z: tz,
                    });
                    b.add(S.cyl(0.09, 0.04, 0.12, 12), 0xffc93c, {
                        x: tx,
                        y: ty + 0.2,
                        z: tz,
                    });
                }
            }
            this.plant(b, c + 2.1, y, -3.2, 1.0);
        }
        // ===== Kho hàng
        {
            const r = room('thukho');
            const c = r.cx;
            const y = r.fy;
            // kệ thùng bên trái
            this.shelfUnit(b, c - 1.3, y, zb, 2.2, 1.7, 3, C.woodDark);
            const boxCols = [0xe2b078, 0xd9a066, 0xecc08c];
            for (let k = 0; k < 3; k++) {
                let bx = c - 2.3;
                let i = k;
                while (bx < c - 0.4) {
                    const w = 0.4 + ((i * 7) % 3) * 0.08;
                    const h = 0.3 + ((i * 5) % 3) * 0.06;
                    b.add(S.rbox(w, h, 0.34, 0.02), boxCols[i % 3], {
                        x: bx + w / 2,
                        y: y + 0.1 + k * 0.533 + h / 2,
                        z: zb,
                    });
                    b.add(S.box(0.1, h + 0.005, 0.345), 0xfff3c9, {
                        x: bx + w / 2,
                        y: y + 0.1 + k * 0.533 + h / 2,
                        z: zb,
                    });
                    bx += w + 0.06;
                    i++;
                }
            }
            // kệ cuộn phim bên phải
            this.shelfUnit(b, c + 1.3, y, zb, 2.2, 1.7, 3, 0x8a6fd6);
            for (let k = 0; k < 3; k++) {
                for (let j = 0; j < 5; j++) {
                    this.reelSlots.push(
                        new THREE.Vector3(
                            c + 1.3 + (j - 2) * 0.4,
                            y + 0.1 + k * 0.533 + 0.23,
                            zb + 0.06,
                        ),
                    );
                }
            }
            b.add(S.rbox(2.0, 0.42, 0.06, 0.05), 0x4a3868, {
                x: c + 1.3,
                y: y + 1.98,
                z: zb + 0.24,
            });
            this.frame(
                c + 1.3,
                y + 1.98,
                zb + 0.28,
                1.9,
                0.34,
                (g, W, H2) => {
                    g.fillStyle = '#4a3868';
                    g.fillRect(0, 0, W, H2);
                    g.fillStyle = '#ffe9a8';
                    g.font = `800 ${H2 * 0.55}px ${FONT}`;
                    g.textAlign = 'center';
                    g.textBaseline = 'middle';
                    g.fillText('🎞️ Cuộn phim lô này', W / 2, H2 * 0.54);
                },
                512,
            );
            // bàn gói hàng
            b.add(S.rbox(1.4, 0.08, 0.6, 0.03), C.woodLight, {
                x: c - 1.2,
                y: y + 0.8,
                z: -1.3,
            });
            for (const sx of [-1, 1]) {
                b.add(
                    S.box(0.07, 0.78, 0.5),
                    C.wood,
                    { x: c - 1.2 + sx * 0.62, y: y + 0.39, z: -1.3 },
                    { ao: y, aoH: 0.3 },
                );
            }
            b.add(S.rbox(0.45, 0.32, 0.36, 0.02), 0xe2b078, {
                x: c - 1.45,
                y: y + 1.0,
                z: -1.3,
            });
            b.add(S.box(0.46, 0.06, 0.1), 0xfff3c9, {
                x: c - 1.45,
                y: y + 1.14,
                z: -1.3,
            });
            b.add(S.torus(0.08, 0.035, 8, 16), 0xd6c3a0, {
                x: c - 0.85,
                y: y + 0.88,
                z: -1.25,
                rx: Math.PI / 2,
            });
            // thùng to dưới đất
            b.add(
                S.rbox(0.6, 0.5, 0.5, 0.03),
                0xd9a066,
                { x: c - 2.15, y: y + 0.25, z: -0.5 },
                { ao: y, aoH: 0.3 },
            );
            b.add(S.rbox(0.45, 0.38, 0.4, 0.03), 0xecc08c, {
                x: c - 2.1,
                y: y + 0.69,
                z: -0.52,
                ry: 0.2,
            });
            // cuộn phim mẫu (hình dùng chung cho kệ)
            const rb = new Batch();
            rb.add(S.cyl(0.19, 0.19, 0.06, 26), 0x5c4a86, { rx: Math.PI / 2 });
            rb.add(S.cyl(0.155, 0.155, 0.064, 26), 0x6f5aa0, {
                rx: Math.PI / 2,
            });
            rb.add(S.cyl(0.05, 0.05, 0.075, 12), 0xfff3c9, { rx: Math.PI / 2 });
            for (let k = 0; k < 5; k++) {
                const a = (k / 5) * Math.PI * 2;
                rb.add(S.cyl(0.035, 0.035, 0.07, 10), 0xfff3c9, {
                    x: Math.cos(a) * 0.1,
                    y: Math.sin(a) * 0.1,
                    rx: Math.PI / 2,
                });
            }
            const reel = rb.build(this.kit);
            this.reelGeo = reel.geometry;
            this.reelMat = reel.material as THREE.Material;
        }
        // ===== Sảnh
        {
            const r = room('sanh');
            const c = r.cx;
            const y = r.fy;
            this.plant(b, c - 2.15, y, -3.2, 1.15);
            // ổ mèo
            b.add(S.torus(0.32, 0.12, 10, 22), C.pink, {
                x: c + 2.05,
                y: y + 0.1,
                z: -3.05,
                rx: Math.PI / 2,
            });
            b.add(S.cyl(0.32, 0.32, 0.06, 20), C.pinkSoft, {
                x: c + 2.05,
                y: y + 0.05,
                z: -3.05,
            });
            // giá treo áo + đồng hồ
            b.add(S.cyl(0.04, 0.04, 1.7, 8), C.woodDark, {
                x: c - 2.2,
                y: y + 0.85,
                z: 0.0,
            });
            b.add(S.cyl(0.2, 0.24, 0.05, 12), C.woodDark, {
                x: c - 2.2,
                y: y + 0.03,
                z: 0.0,
            });
            b.add(S.sphere(0.16, 10, 8), C.yellow, {
                x: c - 2.1,
                y: y + 1.5,
                z: 0.08,
                sy: 0.6,
            });
            b.add(S.cyl(0.3, 0.3, 0.05, 24), 0xfffaf2, {
                x: c + 2.0,
                y: y + 1.35,
                z: Z_BACK + 0.04,
                rx: Math.PI / 2,
            });
            b.add(S.torus(0.3, 0.04, 6, 24), C.trim, {
                x: c + 2.0,
                y: y + 1.35,
                z: Z_BACK + 0.06,
            });
            this.clock = { x: c + 2.0, y: y + 1.35, z: Z_BACK + 0.09 };
            // cửa sổ nhỏ hai bên bảng
            this.window(b, c - 2.15, y + 1.3, 0.55, 0.7);
            // bậc thềm trước sảnh
            for (let k = 0; k < 2; k++) {
                b.add(
                    S.rbox(2.6 - k * 0.3, 0.15, 0.45, 0.04),
                    k ? 0xefe6f8 : 0xe2d4fa,
                    {
                        x: c,
                        y: 0.075 + k * 0.15 - 0.0,
                        z: Z_FRONT + 0.42 - k * 0.24,
                    },
                );
            }
        }
        // ===== Quầy giỏ hàng
        {
            const r = room('chuquay');
            const c = r.cx;
            const y = r.fy;
            b.add(
                S.rbox(2.6, 0.95, 0.7, 0.05),
                0xfffaf2,
                { x: c, y: y + 0.475, z: -1.3 },
                { ao: y, aoH: 0.4 },
            );
            for (let k = 0; k < 6; k++) {
                b.add(S.box(0.2, 0.7, 0.02), k % 2 ? C.mint : 0xbfeee0, {
                    x: c - 1.0 + k * 0.4,
                    y: y + 0.42,
                    z: -0.94,
                });
            }
            b.add(S.rbox(2.75, 0.07, 0.8, 0.03), C.woodLight, {
                x: c,
                y: y + 0.98,
                z: -1.3,
            });
            // máy tính tiền
            b.add(S.rbox(0.5, 0.22, 0.4, 0.04), 0x6eb5f2, {
                x: c + 0.65,
                y: y + 1.12,
                z: -1.35,
            });
            b.add(S.rbox(0.36, 0.22, 0.05, 0.02), 0x3a3150, {
                x: c + 0.65,
                y: y + 1.32,
                z: -1.5,
                rx: -0.3,
            });
            this.frame(
                c + 0.65,
                y + 1.33,
                -1.47,
                0.3,
                0.16,
                (g, W, H2) => {
                    g.fillStyle = '#183a3a';
                    g.fillRect(0, 0, W, H2);
                    g.fillStyle = '#7dffb2';
                    g.font = `800 ${H2 * 0.62}px ${FONT}`;
                    g.textAlign = 'center';
                    g.textBaseline = 'middle';
                    g.fillText('12k', W / 2, H2 / 2);
                },
                128,
            ).texture;
            // túi + hộp quà trên quầy
            b.add(S.rbox(0.3, 0.32, 0.18, 0.03), C.pink, {
                x: c - 0.7,
                y: y + 1.17,
                z: -1.25,
            });
            b.add(S.torus(0.08, 0.015, 6, 14, Math.PI), 0xffffff, {
                x: c - 0.7,
                y: y + 1.33,
                z: -1.25,
            });
            b.add(S.rbox(0.24, 0.22, 0.24, 0.02), C.yellow, {
                x: c - 0.25,
                y: y + 1.12,
                z: -1.2,
            });
            b.add(S.box(0.05, 0.225, 0.245), C.red, {
                x: c - 0.25,
                y: y + 1.12,
                z: -1.2,
            });
            // mái hiên sọc
            for (let k = 0; k < 8; k++) {
                b.add(S.box(0.38, 0.06, 1.6), k % 2 ? 0xffffff : C.pink, {
                    x: c - 1.33 + k * 0.38,
                    y: y + 2.3,
                    z: -1.75,
                    rx: 0.32,
                });
                b.add(S.cyl(0.19, 0.19, 0.06, 12), k % 2 ? 0xffffff : C.pink, {
                    x: c - 1.33 + k * 0.38,
                    y: y + 2.05,
                    z: -1.0,
                    rx: Math.PI / 2,
                    sz: 0.5,
                });
            }
            // kệ hàng tường sau
            for (let k = 0; k < 2; k++) {
                b.add(S.box(3.6, 0.06, 0.35), C.woodLight, {
                    x: c,
                    y: y + 0.9 + k * 0.45,
                    z: zb,
                });
                for (let j = 0; j < 9; j++) {
                    const col = [
                        C.pink,
                        C.mint,
                        C.yellow,
                        C.blue,
                        C.orange,
                        C.purple,
                    ][(j + k * 2) % 6];
                    if (j % 3 === 1) {
                        b.add(S.cyl(0.07, 0.08, 0.3, 10), col, {
                            x: c - 1.6 + j * 0.4,
                            y: y + 1.08 + k * 0.45,
                            z: zb,
                        });
                        b.add(S.cyl(0.04, 0.04, 0.06, 8), 0xffffff, {
                            x: c - 1.6 + j * 0.4,
                            y: y + 1.26 + k * 0.45,
                            z: zb,
                        });
                    } else {
                        b.add(S.rbox(0.28, 0.28, 0.22, 0.03), col, {
                            x: c - 1.6 + j * 0.4,
                            y: y + 1.07 + k * 0.45,
                            z: zb,
                        });
                    }
                }
            }
            // bảng SALE
            b.add(S.rbox(0.8, 0.45, 0.05, 0.04), 0xffffff, {
                x: c - 1.85,
                y: y + 0.95,
                z: -0.2,
                rx: -0.15,
            });
            this.frame(
                c - 1.85,
                y + 0.95,
                -0.17,
                0.72,
                0.37,
                (g, W, H2) => {
                    g.fillStyle = '#fff';
                    g.fillRect(0, 0, W, H2);
                    g.strokeStyle = '#ff6f7f';
                    g.lineWidth = 8;
                    g.strokeRect(6, 6, W - 12, H2 - 12);
                    g.fillStyle = '#ff4f6f';
                    g.font = `900 ${H2 * 0.55}px ${FONT}`;
                    g.textAlign = 'center';
                    g.textBaseline = 'middle';
                    g.fillText('SALE', W / 2, H2 / 2 + 2);
                },
                256,
            ).texture;
            b.add(S.box(0.05, 0.75, 0.05), C.woodDark, {
                x: c - 1.85,
                y: y + 0.37,
                z: -0.25,
            });
            // xe đẩy
            const kx = c + 1.95;
            const kz = -0.35;
            b.add(S.box(0.6, 0.04, 0.45), 0x9aa3b8, {
                x: kx,
                y: y + 0.45,
                z: kz,
            });
            for (const sx of [-1, 1]) {
                b.add(S.box(0.03, 0.4, 0.45), 0xbac2d4, {
                    x: kx + sx * 0.3,
                    y: y + 0.65,
                    z: kz,
                });
                b.add(S.box(0.6, 0.4, 0.03), 0xbac2d4, {
                    x: kx,
                    y: y + 0.65,
                    z: kz + sx * 0.225,
                });
            }
            b.add(S.cyl(0.02, 0.02, 0.5, 6), 0x6d6480, {
                x: kx + 0.36,
                y: y + 0.95,
                z: kz,
                rx: Math.PI / 2,
            });
            for (const [dx, dz] of [
                [-0.25, -0.18],
                [0.25, -0.18],
                [-0.25, 0.18],
                [0.25, 0.18],
            ]) {
                b.add(S.cyl(0.06, 0.06, 0.04, 10), 0x3a3150, {
                    x: kx + dx,
                    y: y + 0.06,
                    z: kz + dz,
                    rx: Math.PI / 2,
                });
            }
            b.add(S.rbox(0.22, 0.2, 0.2, 0.03), C.yellow, {
                x: kx - 0.1,
                y: y + 0.58,
                z: kz,
            });
            b.add(S.rbox(0.18, 0.26, 0.15, 0.03), C.mint, {
                x: kx + 0.12,
                y: y + 0.6,
                z: kz + 0.05,
            });
        }
        // ===== Phòng viết
        {
            const r = room('bienkich');
            const c = r.cx;
            const y = r.fy;
            this.desk(b, c, y, DESK_Z, 2.0, 0.8, C.wood);
            this.chair(b, c, y, SEAT_Z, 0x7fd1c1);
            this.lamp(b, c - 0.75, y + 0.72, DESK_Z - 0.1, 'bienkich');
            this.deskTops.bienkich = new THREE.Vector3(
                c + 0.6,
                y + 0.73,
                DESK_Z + 0.05,
            );
            // giấy, sách mở, lọ mực + bút lông
            for (let k = 0; k < 4; k++) {
                b.add(S.box(0.32, 0.012, 0.42), 0xffffff, {
                    x: c - 0.25 + k * 0.01,
                    y: y + 0.735 + k * 0.012,
                    z: DESK_Z + 0.05,
                    ry: k * 0.08,
                });
            }
            b.add(S.box(0.3, 0.02, 0.4), 0xfff3d6, {
                x: c + 0.15,
                y: y + 0.74,
                z: DESK_Z + 0.05,
                rz: 0.08,
            });
            b.add(S.box(0.3, 0.02, 0.4), 0xfff3d6, {
                x: c + 0.46,
                y: y + 0.74,
                z: DESK_Z + 0.05,
                rz: -0.08,
            });
            b.add(S.cyl(0.06, 0.07, 0.12, 12), 0x3a3150, {
                x: c + 0.75,
                y: y + 0.79,
                z: DESK_Z - 0.2,
            });
            b.add(S.cone(0.05, 0.42, 8), 0xc9b6ff, {
                x: c + 0.72,
                y: y + 1.02,
                z: DESK_Z - 0.18,
                rz: 0.35,
            });
            // tủ sách
            this.shelfUnit(b, c - 1.55, y, zb, 1.5, 1.7, 3, C.woodDark);
            for (let k = 0; k < 3; k++) {
                this.books(
                    b,
                    c - 1.55,
                    y + 0.075 + k * 0.533,
                    zb,
                    1.35,
                    k * 3 + 1,
                );
            }
            this.window(b, c + 1.25, y + 1.15, 1.2, 0.95);
            this.plant(b, c - 2.15, y, -0.4, 1.05);
            // rèm
            b.add(S.box(1.6, 0.06, 0.06), C.woodDark, {
                x: c + 1.25,
                y: y + 1.72,
                z: Z_BACK + 0.15,
            });
            for (const sx of [-1, 1]) {
                b.add(S.rbox(0.3, 1.1, 0.06, 0.03), C.pinkSoft, {
                    x: c + 1.25 + sx * 0.72,
                    y: y + 1.15,
                    z: Z_BACK + 0.14,
                });
            }
        }
        // ===== Phòng thu
        {
            const r = room('thuam');
            const c = r.cx;
            const y = r.fy;
            // mút tiêu âm
            for (let i = 0; i < 9; i++) {
                for (let j = 0; j < 3; j++) {
                    const fx = c - 1.6 + i * 0.4;
                    const fyy = y + 0.65 + j * 0.4;
                    b.add(
                        S.box(0.38, 0.38, 0.05),
                        (i + j) % 2 ? 0x8a6fd6 : 0x7a5fc6,
                        { x: fx, y: fyy, z: Z_BACK + 0.03 },
                    );
                    b.add(
                        S.cone(0.2, 0.12, 4),
                        (i + j) % 2 ? 0x9a82e0 : 0x8a6fd6,
                        {
                            x: fx,
                            y: fyy,
                            z: Z_BACK + 0.1,
                            rx: Math.PI / 2,
                            ry: Math.PI / 4,
                        },
                    );
                }
            }
            // biển ON AIR
            b.add(S.rbox(1.1, 0.42, 0.1, 0.05), 0x3a3150, {
                x: c - 0.9,
                y: y + 2.5,
                z: -0.62,
            });
            for (const sx of [-1, 1]) {
                b.add(S.cyl(0.012, 0.012, H - 2.7, 4), 0x6d6480, {
                    x: c - 0.9 + sx * 0.4,
                    y: y + 2.71 + (H - 2.7) / 2,
                    z: -0.62,
                });
            }
            this.onAir = this.kit.basic(0x7a3a4a);
            const onTex = this.kit.canvas(256, 96, (g, W, H2) => {
                g.fillStyle = '#ffffff';
                g.font = `900 ${H2 * 0.62}px ${FONT}`;
                g.textAlign = 'center';
                g.textBaseline = 'middle';
                g.fillText('ON AIR', W / 2, H2 / 2 + 2);
            });
            this.onAir.map = onTex.texture;
            const on = new THREE.Mesh(S.plane(0.98, 0.32), this.onAir);
            on.position.set(c - 0.9, y + 2.5, -0.565);
            this.group.add(on);
            this.glow('thuam-air', c - 0.9, y + 2.5, -0.4, 0xff4f6f, 1.6);
            // bàn + ghế gaming
            this.desk(b, c, y, DESK_Z, 2.0, 0.8, 0x4d3f73, false);
            this.chair(b, c, y, SEAT_Z, 0xff6f7f, true);
            this.deskTops.thuam = new THREE.Vector3(
                c - 0.6,
                y + 0.73,
                DESK_Z + 0.1,
            );
            this.monitor(
                b,
                c + 0.35,
                y + 0.72,
                DESK_Z - 0.05,
                0.25,
                0.75,
                'thuam',
                0x6effc4,
            );
            // bàn phím RGB
            b.add(S.rbox(0.7, 0.04, 0.22, 0.02), 0x2b2440, {
                x: c,
                y: y + 0.75,
                z: DESK_Z - 0.28,
            });
            const rgb = this.kit.basic(0xff7fd8);
            this.rgb.push(rgb);
            const strip = new THREE.Mesh(S.box(0.66, 0.012, 0.03), rgb);
            strip.position.set(c, y + 0.775, DESK_Z - 0.18);
            this.group.add(strip);
            // micro trên cần
            b.add(S.cyl(0.05, 0.06, 0.05, 10), 0x3a3150, {
                x: c - 0.85,
                y: y + 0.75,
                z: DESK_Z - 0.3,
            });
            b.add(S.cyl(0.018, 0.018, 0.65, 6), 0x6d6480, {
                x: c - 0.85,
                y: y + 1.07,
                z: DESK_Z - 0.3,
            });
            b.add(S.cyl(0.018, 0.018, 0.65, 6), 0x6d6480, {
                x: c - 0.6,
                y: y + 1.35,
                z: DESK_Z - 0.45,
                rz: -1.0,
                ry: 0.6,
            });
            b.add(S.capsule(0.07, 0.12, 4, 10), 0x3a3150, {
                x: c - 0.35,
                y: y + 1.2,
                z: DESK_Z - 0.6,
                rx: 0.4,
            });
            b.add(S.torus(0.09, 0.012, 6, 16), 0x9a8fb8, {
                x: c - 0.35,
                y: y + 1.2,
                z: DESK_Z - 0.6,
                rx: Math.PI / 2 + 0.4,
            });
            // loa
            for (const sx of [-1, 1]) {
                b.add(S.rbox(0.22, 0.34, 0.22, 0.03), 0x3a3150, {
                    x: c + sx * 0.92 + (sx > 0 ? 0 : 0.15),
                    y: y + 0.89,
                    z: DESK_Z + 0.1,
                });
                b.add(S.cyl(0.07, 0.07, 0.02, 12), 0x8a8299, {
                    x: c + sx * 0.92 + (sx > 0 ? 0 : 0.15),
                    y: y + 0.86,
                    z: DESK_Z + 0.21,
                    rx: Math.PI / 2,
                });
            }
            // bàn xoay đĩa
            b.add(
                S.rbox(0.8, 0.7, 0.6, 0.04),
                0x4d3f73,
                { x: c - 2.05, y: y + 0.35, z: -1.4 },
                { ao: y, aoH: 0.3 },
            );
            const tt = new THREE.Group();
            tt.position.set(c - 2.05, y + 0.72, -1.4);
            const disc = new THREE.Mesh(
                S.cyl(0.26, 0.26, 0.03, 26),
                this.kit.toon(0x2b2440),
            );
            const lab = new THREE.Mesh(
                S.cyl(0.08, 0.08, 0.034, 16),
                this.kit.toon(C.pink),
            );
            const dot = new THREE.Mesh(
                S.box(0.06, 0.036, 0.02),
                this.kit.toon(0xffffff),
            );
            dot.position.set(0.18, 0, 0);
            tt.add(disc, lab, dot);
            this.group.add(tt);
            this.turntable = tt;
        }
        // ===== Phòng đạo diễn
        {
            const r = room('daodien');
            const c = r.cx;
            const y = r.fy;
            this.desk(b, c, y, DESK_Z, 3.4, 0.8, C.woodLight);
            this.chair(b, c - 1.0, y, SEAT_Z, 0xd84a5a);
            this.chair(b, c + 1.0, y, SEAT_Z, 0x5a7ad8);
            this.deskTops.daodienA = new THREE.Vector3(
                c - 0.2,
                y + 0.73,
                DESK_Z + 0.1,
            );
            this.deskTops.daodienB = new THREE.Vector3(
                c + 0.2,
                y + 0.73,
                DESK_Z + 0.1,
            );
            this.monitor(
                b,
                c - 1.0,
                y + 0.72,
                DESK_Z - 0.1,
                0,
                0.6,
                'daodien',
                0xffc98a,
            );
            this.monitor(
                b,
                c + 1.0,
                y + 0.72,
                DESK_Z - 0.1,
                0,
                0.6,
                'daodien',
                0xffc98a,
            );
            // bảng phân cảnh
            b.add(S.rbox(3.3, 1.2, 0.06, 0.05), 0xc98f5a, {
                x: c,
                y: y + 1.12,
                z: Z_BACK + 0.04,
            });
            this.frame(
                c,
                y + 1.12,
                Z_BACK + 0.08,
                3.14,
                1.06,
                (g, W, H2) => {
                    g.fillStyle = '#e8c08a';
                    g.fillRect(0, 0, W, H2);
                    const cols = [
                        '#fff8ec',
                        '#ffeef3',
                        '#eef8ff',
                        '#fff8ec',
                        '#f2ffef',
                        '#fff3d6',
                    ];
                    for (let i = 0; i < 6; i++) {
                        const cx2 = 30 + (i % 3) * ((W - 60) / 3);
                        const cy2 = 22 + Math.floor(i / 3) * (H2 / 2 - 6);
                        const w = (W - 60) / 3 - 26;
                        const h = H2 / 2 - 36;
                        g.save();
                        g.translate(cx2 + w / 2, cy2 + h / 2);
                        g.rotate((i % 2 ? 1 : -1) * 0.03);
                        g.fillStyle = cols[i];
                        g.fillRect(-w / 2, -h / 2, w, h);
                        g.strokeStyle = '#6a52b8';
                        g.lineWidth = 3;
                        g.strokeRect(-w / 2 + 8, -h / 2 + 8, w - 16, h - 28);
                        g.beginPath();
                        // phác hoạ: núi, mặt trời, người que
                        g.moveTo(-w / 2 + 14, h / 2 - 26);
                        g.lineTo(-w / 6, -h / 8);
                        g.lineTo(0, h / 6);
                        g.lineTo(w / 5, -h / 5);
                        g.lineTo(w / 2 - 14, h / 2 - 26);
                        g.stroke();
                        g.beginPath();
                        g.arc(w / 4, -h / 4, 8, 0, Math.PI * 2);
                        g.stroke();
                        g.fillStyle = '#4a3868';
                        g.font = `700 14px ${FONT}`;
                        g.fillText(`Cảnh ${i + 1}`, -w / 2 + 10, h / 2 - 6);
                        g.restore();
                        g.fillStyle = '#ff6f7f';
                        g.beginPath();
                        g.arc(cx2 + w / 2, cy2 + 2, 6, 0, Math.PI * 2);
                        g.fill();
                    }
                },
                640,
            );
            // bảng clapper
            b.add(S.rbox(0.36, 0.26, 0.04, 0.01), 0x2b2440, {
                x: c,
                y: y + 0.86,
                z: DESK_Z + 0.1,
                rx: -0.2,
            });
            for (let k = 0; k < 4; k++) {
                b.add(S.box(0.08, 0.06, 0.042), k % 2 ? 0xffffff : 0x2b2440, {
                    x: c - 0.135 + k * 0.09,
                    y: y + 1.02,
                    z: DESK_Z + 0.07,
                    rx: -0.2,
                    rz: -0.25,
                });
            }
            // máy quay trên chân
            const tx = c - 2.1;
            const tz = -3.1;
            for (let k = 0; k < 3; k++) {
                const a = (k / 3) * Math.PI * 2;
                b.add(S.cyl(0.025, 0.025, 1.25, 6), 0x3a3150, {
                    x: tx + Math.sin(a) * 0.18,
                    y: y + 0.6,
                    z: tz + Math.cos(a) * 0.18,
                    rx: Math.cos(a) * 0.25,
                    rz: -Math.sin(a) * 0.25,
                });
            }
            b.add(S.rbox(0.3, 0.26, 0.48, 0.05), 0x3a3150, {
                x: tx,
                y: y + 1.32,
                z: tz,
                ry: 0.6,
            });
            b.add(S.cyl(0.1, 0.12, 0.2, 14), 0x6d6480, {
                x: tx + 0.2,
                y: y + 1.32,
                z: tz + 0.27,
                rx: Math.PI / 2,
                rz: -0.6,
                ry: 0.6,
            });
            b.add(S.cyl(0.13, 0.13, 0.08, 16), 0x3a3150, {
                x: tx - 0.05,
                y: y + 1.53,
                z: tz - 0.05,
                rx: Math.PI / 2,
                ry: 0.6,
            });
            b.add(S.cyl(0.13, 0.13, 0.08, 16), 0x3a3150, {
                x: tx + 0.12,
                y: y + 1.53,
                z: tz + 0.17,
                rx: Math.PI / 2,
                ry: 0.6,
            });
            // đèn hộp
            b.add(S.cyl(0.025, 0.025, 1.5, 6), 0x3a3150, {
                x: c + 2.15,
                y: y + 0.75,
                z: -3.15,
            });
            b.add(S.rbox(0.55, 0.45, 0.2, 0.05), 0xffffff, {
                x: c + 2.15,
                y: y + 1.6,
                z: -3.1,
                ry: -0.6,
                rx: 0.2,
            });
        }
        // ===== Phòng dựng
        {
            const r = room('thodung');
            const c = r.cx;
            const y = r.fy;
            this.desk(b, c, y, DESK_Z, 2.6, 0.8, 0x5a6aa8, false);
            this.chair(b, c, y, SEAT_Z, 0x46c08a, true);
            this.deskTops.thodung = new THREE.Vector3(
                c + 0.95,
                y + 0.73,
                DESK_Z + 0.15,
            );
            this.monitor(
                b,
                c - 0.8,
                y + 0.72,
                DESK_Z - 0.0,
                -0.45,
                0.62,
                'thodung',
                0x8ad8ff,
            );
            this.monitor(
                b,
                c,
                y + 0.72,
                DESK_Z - 0.12,
                0,
                0.75,
                'thodung',
                0xb3a2ff,
            );
            this.monitor(
                b,
                c + 0.8,
                y + 0.72,
                DESK_Z - 0.0,
                0.45,
                0.62,
                'thodung',
                0x8affc9,
            );
            b.add(S.rbox(0.7, 0.04, 0.22, 0.02), 0x2b2440, {
                x: c,
                y: y + 0.75,
                z: DESK_Z - 0.3,
            });
            const rgb = this.kit.basic(0x7fe0ff);
            this.rgb.push(rgb);
            const strip = new THREE.Mesh(S.box(0.66, 0.012, 0.03), rgb);
            strip.position.set(c, y + 0.775, DESK_Z - 0.2);
            this.group.add(strip);
            // lon nước tăng lực
            for (let k = 0; k < 3; k++) {
                b.add(
                    S.cyl(0.045, 0.045, 0.15, 10),
                    k === 1 ? C.yellow : 0x6fe07a,
                    {
                        x: c + 1.0 + k * 0.1,
                        y: y + 0.8,
                        z: DESK_Z + 0.22 - (k % 2) * 0.12,
                    },
                );
            }
            // tháp render + đèn LED
            const tx = c - 2.0;
            const tz = -3.15;
            b.add(
                S.rbox(0.65, 1.45, 0.7, 0.05),
                0x2b2440,
                { x: tx, y: y + 0.725, z: tz },
                { ao: y, aoH: 0.3 },
            );
            b.add(S.box(0.5, 1.2, 0.02), 0x3a3150, {
                x: tx,
                y: y + 0.75,
                z: tz + 0.36,
            });
            for (let k = 0; k < 8; k++) {
                const m = this.kit.basic(0x2c2a44);
                this.leds.push(m);
                const led = new THREE.Mesh(S.box(0.07, 0.05, 0.02), m);
                led.position.set(
                    tx - 0.15 + (k % 2) * 0.3,
                    y + 0.3 + Math.floor(k / 2) * 0.28,
                    tz + 0.37,
                );
                this.group.add(led);
            }
            b.add(S.torus(0.14, 0.02, 6, 18), 0x6eb5f2, {
                x: tx,
                y: y + 1.25,
                z: tz + 0.37,
            });
            this.glow('thodung', tx, y + 0.9, tz + 0.6, 0x7fe0ff, 1.3);
            // áp phích + ghế lười
            b.add(S.rbox(0.8, 1.05, 0.04, 0.03), 0x3a3150, {
                x: c + 1.2,
                y: y + 1.2,
                z: Z_BACK + 0.04,
            });
            this.frame(
                c + 1.2,
                y + 1.2,
                Z_BACK + 0.07,
                0.72,
                0.95,
                (g, W, H2) => {
                    const gr = g.createLinearGradient(0, 0, 0, H2);
                    gr.addColorStop(0, '#6a52b8');
                    gr.addColorStop(1, '#ff8fa3');
                    g.fillStyle = gr;
                    g.fillRect(0, 0, W, H2);
                    g.fillStyle = '#ffd36a';
                    g.beginPath();
                    g.arc(W / 2, H2 * 0.4, W * 0.22, 0, Math.PI * 2);
                    g.fill();
                    g.fillStyle = '#fff';
                    g.font = `900 ${W * 0.16}px ${FONT}`;
                    g.textAlign = 'center';
                    g.fillText('GG!', W / 2, H2 * 0.82);
                },
            );
            b.add(S.sphere(0.5, 16, 12), C.orange, {
                x: c - 2.0,
                y: y + 0.3,
                z: -1.75,
                sy: 0.6,
            });
        }
        // khoang cầu thang: cửa sổ chiếu nghỉ + đèn
        this.window(b, BAY_CX, F2 + 1.2, 1.2, 0.95);
        this.window(b, BAY_CX + 0.9, F1 + 1.2, 0.8, 0.9);
    }

    clock = { x: 0, y: 0, z: 0 };

    window(b: Batch, x: number, y: number, w: number, h: number) {
        const S = this.S;
        b.add(S.rbox(w + 0.16, h + 0.16, 0.08, 0.04), 0xfffaf2, {
            x,
            y,
            z: Z_BACK + 0.04,
        });
        const glass = new THREE.Mesh(S.plane(w, h), this.glass);
        glass.position.set(x, y, Z_BACK + 0.09);
        this.group.add(glass);
        b.add(S.box(0.05, h, 0.04), 0xfffaf2, { x, y, z: Z_BACK + 0.11 });
        b.add(S.box(w, 0.05, 0.04), 0xfffaf2, { x, y, z: Z_BACK + 0.11 });
        b.add(S.rbox(w + 0.3, 0.07, 0.2, 0.03), 0xfffaf2, {
            x,
            y: y - h / 2 - 0.08,
            z: Z_BACK + 0.1,
        });
    }

    // ---------------------------------------------------------------- gác mái
    private buildAttic(b: Batch) {
        const S = this.S;
        const y = FA;
        // giá đậu của Cú
        b.add(S.cyl(0.05, 0.06, 1.0, 8), C.woodDark, {
            x: 0,
            y: y + 0.5,
            z: -1.3,
        });
        b.add(S.cyl(0.3, 0.36, 0.06, 14), C.woodDark, {
            x: 0,
            y: y + 0.03,
            z: -1.3,
        });
        b.add(S.cyl(0.05, 0.05, 0.9, 8), C.wood, {
            x: 0,
            y: y + 1.0,
            z: -1.3,
            rz: Math.PI / 2,
        });
        // bảng biểu đồ
        b.add(S.cyl(0.03, 0.03, 1.5, 6), C.woodDark, {
            x: -2.6 - 0.45,
            y: y + 0.7,
            z: -1.9,
            rx: 0.15,
        });
        b.add(S.cyl(0.03, 0.03, 1.5, 6), C.woodDark, {
            x: -2.6 + 0.45,
            y: y + 0.7,
            z: -1.9,
            rx: 0.15,
        });
        b.add(S.rbox(1.25, 0.95, 0.05, 0.03), 0xfffaf2, {
            x: -2.6,
            y: y + 1.05,
            z: -1.82,
            rx: -0.15,
        });
        const chart = this.frame(
            -2.6,
            y + 1.05,
            -1.79,
            1.12,
            0.84,
            (g, W, H2) => {
                g.fillStyle = '#fffaf2';
                g.fillRect(0, 0, W, H2);
                const bars = [0.3, 0.45, 0.4, 0.62, 0.78];
                const cols = [
                    '#a58bea',
                    '#7fd1c1',
                    '#ffd36a',
                    '#ff8fa3',
                    '#6eb5f2',
                ];
                bars.forEach((v, i) => {
                    g.fillStyle = cols[i];
                    g.fillRect(
                        24 + i * 44,
                        H2 - 20 - v * (H2 - 50),
                        30,
                        v * (H2 - 50),
                    );
                });
                g.strokeStyle = '#6a52b8';
                g.lineWidth = 5;
                g.beginPath();
                bars.forEach((v, i) =>
                    g.lineTo(39 + i * 44, H2 - 30 - v * (H2 - 50)),
                );
                g.stroke();
                g.fillStyle = '#4a3868';
                g.font = `800 20px ${FONT}`;
                g.fillText('Lượt xem ↑', 14, 26);
            },
        );
        chart.texture.anisotropy = 4;
        const cm = this.group.children[this.group.children.length - 1];
        cm.rotation.x = -0.15;
        // kính viễn vọng
        const tx = 3.0;
        const tz = -0.6;
        for (let k = 0; k < 3; k++) {
            const a = (k / 3) * Math.PI * 2;
            b.add(S.cyl(0.025, 0.025, 1.0, 6), C.woodDark, {
                x: tx + Math.sin(a) * 0.15,
                y: y + 0.48,
                z: tz + Math.cos(a) * 0.15,
                rx: Math.cos(a) * 0.3,
                rz: -Math.sin(a) * 0.3,
            });
        }
        b.add(S.cyl(0.09, 0.13, 1.1, 14), 0x6eb5f2, {
            x: tx + 0.25,
            y: y + 1.15,
            z: tz + 0.2,
            rz: -1.0,
            rx: 0.35,
        });
        b.add(S.cyl(0.14, 0.14, 0.06, 14), 0xffd36a, {
            x: tx + 0.72,
            y: y + 1.45,
            z: tz + 0.37,
            rz: -1.0,
            rx: 0.35,
        });
        // rương, thùng, sách
        b.add(S.rbox(1.0, 0.55, 0.6, 0.06), 0xb98557, {
            x: 6.2,
            y: y + 0.28,
            z: -2.6,
        });
        b.add(S.cyl(0.3, 0.3, 1.0, 14), 0xa8764d, {
            x: 6.2,
            y: y + 0.55,
            z: -2.6,
            rz: Math.PI / 2,
            sx: 1,
            sz: 1,
        });
        b.add(S.box(1.02, 0.08, 0.1), C.yellow, {
            x: 6.2,
            y: y + 0.5,
            z: -2.29,
        });
        b.add(S.rbox(0.7, 0.5, 0.6, 0.03), 0xe2b078, {
            x: -6.5,
            y: y + 0.25,
            z: -2.8,
        });
        b.add(S.rbox(0.55, 0.4, 0.5, 0.03), 0xecc08c, {
            x: -6.3,
            y: y + 0.7,
            z: -2.75,
            ry: 0.3,
        });
        this.books(b, -8.6, y, -2.6, 0.9, 5);
        b.add(S.cyl(0.9, 0.9, 0.02, 24), 0xc9b6ff, {
            x: 0,
            y: y + 0.01,
            z: -0.9,
            sx: 1.5,
        });
        // dây đèn nhấp nháy dọc nóc
        for (let k = 0; k < 22; k++) {
            const x = X0 + 0.8 + k * ((X1 - X0 - 1.6) / 21);
            const sag = Math.sin(((k % 7) / 6) * Math.PI) * 0.3;
            const m = this.kit.basic([C.yellow, C.pink, C.mint, C.blue][k % 4]);
            this.stringLights.push(m);
            const bulb = new THREE.Mesh(S.sphere(0.06, 8, 6), m);
            bulb.position.set(x, RIDGE_Y - 0.4 - sag, RIDGE_Z + 0.25);
            this.group.add(bulb);
        }
    }

    // ---------------------------------------------------------------- bảng việc
    private buildBoard(): CanvasTex {
        const S = this.S;
        const c = room('sanh').cx;
        const y = F1;
        const b = new Batch();
        // bảng đứng trên hai chân (đặt hơi xa tường để camera thấy trọn)
        const bz = -2.95;
        const by = y + 1.28;
        b.add(S.rbox(2.72, 1.66, 0.1, 0.06), 0xb9a2ea, { x: c, y: by, z: bz });
        b.add(S.rbox(2.5, 0.07, 0.18, 0.03), 0xb9a2ea, {
            x: c,
            y: by - 0.86,
            z: bz + 0.06,
        });
        b.add(S.rbox(0.28, 0.05, 0.05, 0.02), C.red, {
            x: c - 0.9,
            y: by - 0.8,
            z: bz + 0.1,
        });
        b.add(S.rbox(0.28, 0.05, 0.05, 0.02), C.blue, {
            x: c - 0.5,
            y: by - 0.8,
            z: bz + 0.1,
        });
        for (const sx of [-1, 1]) {
            b.add(S.rbox(0.08, by - y + 0.2, 0.08, 0.03), 0x8a6fd6, {
                x: c + sx * 1.2,
                y: y + (by - y + 0.2) / 2,
                z: bz - 0.06,
            });
            b.add(S.rbox(0.1, 0.06, 0.55, 0.03), 0x8a6fd6, {
                x: c + sx * 1.2,
                y: y + 0.03,
                z: bz,
            });
        }
        const fm = b.build(this.kit);
        this.group.add(fm);
        const tex = this.kit.canvas(1024, 600, () => undefined);
        const m = new THREE.Mesh(
            this.kit.geo(new THREE.PlaneGeometry(2.56, 1.5)),
            this.kit.basic(0xffffff, { map: tex.texture }),
        );
        m.position.set(c, by, bz + 0.06);
        m.userData.pick = { kind: 'role', key: 'bang' };
        this.group.add(m);
        this.boardMesh = m;

        return tex;
    }

    boardMesh!: THREE.Mesh;

    drawBoard(
        bang:
            | {
                  san_pham: string | null;
                  tien_do: { xong: number; tong: number } | null;
                  dong: string;
              }
            | undefined,
        mode: string | undefined,
    ) {
        this.board.redraw((g, W, H2) => {
            g.fillStyle = '#fffdf8';
            g.fillRect(0, 0, W, H2);
            g.fillStyle = '#8a6fd6';
            g.font = `800 34px ${FONT}`;
            g.fillText('BẢNG VIỆC', 56, 76);
            const tag =
                mode === 'working'
                    ? ['ĐANG LÀM', '#2fbf71']
                    : mode === 'limit'
                      ? ['TẠM NGHỈ', '#ff8a3d']
                      : mode === 'down'
                        ? ['ĐANG TẮT', '#9a8fb8']
                        : ['ĐANG NGHỈ', '#d9a441'];
            g.font = `800 28px ${FONT}`;
            const tw = g.measureText(tag[0]).width + 40;
            roundRect(g, W - 56 - tw, 44, tw, 46, 23);
            g.fillStyle = tag[1];
            g.fill();
            g.fillStyle = '#fff';
            g.fillText(tag[0], W - 56 - tw + 20, 78);
            g.fillStyle = '#3a2c55';
            g.font = `900 64px ${FONT}`;
            g.fillText(
                fitText(g, bang?.san_pham ?? 'Chưa có lô nào', W - 112),
                56,
                170,
            );
            const td = bang?.tien_do;
            const bx = 56;
            const by = 220;
            const bw = W - 112;
            roundRect(g, bx, by, bw, 54, 27);
            g.fillStyle = '#efe7fb';
            g.fill();
            g.lineWidth = 5;
            g.strokeStyle = '#4a3868';
            g.stroke();
            if (td && td.tong > 0) {
                const f = Math.max(0, Math.min(1, td.xong / td.tong));
                if (f > 0) {
                    roundRect(
                        g,
                        bx + 6,
                        by + 6,
                        Math.max(42, (bw - 12) * f),
                        42,
                        21,
                    );
                    const gr = g.createLinearGradient(bx, 0, bx + bw, 0);
                    gr.addColorStop(0, '#7fd1c1');
                    gr.addColorStop(1, '#a58bea');
                    g.fillStyle = gr;
                    g.fill();
                }
                g.fillStyle = '#6a52b8';
                g.font = `900 56px ${FONT}`;
                g.fillText(`${td.xong}/${td.tong} video`, 56, 360);
            } else {
                g.fillStyle = '#9a8fb8';
                g.font = `800 44px ${FONT}`;
                g.fillText('—', 56, 360);
            }
            g.fillStyle = '#4a3868';
            g.font = `600 38px ${FONT}`;
            const words = (bang?.dong ?? '').split(/\s+/);
            let line = '';
            let ly = 440;
            for (const w of words) {
                if (g.measureText(line + ' ' + w).width > W - 112 && line) {
                    g.fillText(line, 56, ly);
                    ly += 50;
                    line = w;
                    if (ly > 540) {
                        break;
                    }
                } else {
                    line = (line + ' ' + w).trim();
                }
            }
            if (ly <= 540) {
                g.fillText(fitText(g, line, W - 112), 56, ly);
            }
            // hình vẽ tay ở góc
            g.strokeStyle = '#ff8fa3';
            g.lineWidth = 6;
            g.beginPath();
            g.arc(W - 90, H2 - 70, 26, 0, Math.PI * 2);
            g.stroke();
            g.fillStyle = '#ffd36a';
            g.beginPath();
            g.arc(W - 160, H2 - 60, 12, 0, Math.PI * 2);
            g.fill();
        });
    }

    // ---------------------------------------------------------------- bảng tên phòng
    private buildSigns() {
        const mk = (text: string, x: number, y: number, z: number, w = 2.1) => {
            const tex = this.kit.canvas(512, 120, (g, W, H2) => {
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
            const m = new THREE.Mesh(
                this.kit.geo(new THREE.PlaneGeometry(w, (w * 120) / 512)),
                this.kit.basic(0xffffff, {
                    map: tex.texture,
                    transparent: true,
                }),
            );
            m.position.set(x, y, z);
            m.renderOrder = 1;
            this.group.add(m);
        };
        for (const r of ROOMS) {
            mk(
                `${r.emoji} ${r.name}`,
                r.cx,
                r.floor === 2 ? r.fy + H - 0.42 : r.fy + H + SLAB / 2 - 0.02,
                Z_ROOM + 0.16,
                3.3,
            );
        }
        mk('🦉 Gác mái', -2.2, FA + 0.62, -0.35, 2.4);
    }

    // ---------------------------------------------------------------- vùng bấm
    private buildHitBoxes() {
        const mk = (
            key: string,
            x: number,
            y: number,
            z: number,
            w: number,
            h: number,
            d: number,
        ) => {
            const m = new THREE.Mesh(
                this.S.box(w, h, d),
                this.kit.basic(0xffffff),
            );
            m.position.set(x, y, z);
            m.visible = false;
            m.userData.pick = { kind: 'role', key };
            m.updateMatrixWorld();
            this.group.add(m);
            this.pickRooms.push(m);
        };
        for (const r of ROOMS) {
            mk(
                r.pick,
                r.cx,
                r.fy + H / 2,
                (Z_BACK + Z_ROOM) / 2,
                RW - 0.25,
                H - 0.1,
                Z_ROOM - Z_BACK,
            );
        }
        mk('cu', 0, FA + 1.2, RIDGE_Z + 0.8, 8, 2.4, 4);
    }

    // ---------------------------------------------------------------- đèn trong nhà (ban đêm)
    private buildLights() {
        const spots: [number, number, number][] = [
            [room('giamkhao').cx + 1, F1 + 2.4, -1.2],
            [room('sanh').cx - 1.5, F1 + 2.4, -1.2],
            [room('chuquay').cx + 1.2, F1 + 2.4, -1.0],
            [room('bienkich').cx + 1.3, F2 + 2.4, -1.2],
            [room('daodien').cx - 1.3, F2 + 2.4, -1.2],
            [0, FA + 1.6, -0.5],
        ];
        for (const [x, y, z] of spots) {
            const l = new THREE.PointLight(0xffc98a, 0, 9, 1.2);
            l.position.set(x, y, z);
            this.group.add(l);
            this.lights.push(l);
        }
    }

    // ---------------------------------------------------------------- kệ cuộn phim
    /** Đặt đúng danh sách cuộn phim lên kệ (lấy 15 cuộn mới nhất). */
    setReels(reels: Reel[]) {
        const show = reels.slice(-this.reelSlots.length);
        const keep = new Set(show.map((r) => r.n));
        for (const [n, m] of this.reelMeshes) {
            if (!keep.has(n)) {
                this.reelGroup.remove(m);
                this.reelMeshes.delete(n);
            }
        }
        show.forEach((r, i) => {
            let m = this.reelMeshes.get(r.n);
            if (!m) {
                m = new THREE.Mesh(this.reelGeo, this.reelMat);
                m.userData.pick = { kind: 'reel', reel: r };
                m.userData.pop = 0;
                this.reelMeshes.set(r.n, m);
                this.reelGroup.add(m);
            }
            m.userData.pick.reel = r;
            m.position.copy(this.reelSlots[i]);
        });
    }

    /** Ô kệ sẽ dùng cho cuộn thứ `count` (để thợ dựng đi tới đúng chỗ). */
    slotFor(index: number) {
        return this.reelSlots[Math.min(index, this.reelSlots.length - 1)];
    }

    popReel(n: number) {
        const m = this.reelMeshes.get(n);
        if (m) {
            m.userData.pop = 1;
        }
    }

    // ---------------------------------------------------------------- trạng thái + hoạt ảnh
    setWorking(keys: Set<string>) {
        this.working = keys;
        for (const [, m] of this.screenMats) {
            const on = keys.has(m.userData.key as string);
            m.color.setHex(
                on ? (m.userData.on as number) : (m.userData.off as number),
            );
        }
        for (const [k, list] of Object.entries(this.glows)) {
            const base = k.split('-')[0];
            for (const gl of list) {
                gl.on = k === 'thuam-air' ? keys.has('thuam') : keys.has(base);
            }
        }
        this.onAir.color.setHex(keys.has('thuam') ? 0xff3f5f : 0x7a3a4a);
    }

    setNight(n: number, sky: THREE.Color) {
        this.night = n;
        this.glass.color.copy(sky);
        this.lights.forEach(
            (l, i) =>
                (l.intensity = n * (i === this.lights.length - 1 ? 2.2 : 3.2)),
        );
    }

    update(t: number, dt: number) {
        for (const list of Object.values(this.glows)) {
            for (const gl of list) {
                const target = gl.on
                    ? gl.base + Math.sin(t * 3 + gl.sprite.position.x) * 0.08
                    : 0;
                gl.mat.opacity +=
                    (target - gl.mat.opacity) * Math.min(1, dt * 4);
                gl.sprite.visible = gl.mat.opacity > 0.01;
            }
        }
        for (const l of this.lampShades) {
            const on =
                this.night > 0.35 ||
                (l.key !== null && this.working.has(l.key));
            l.mat.color.setHex(on ? 0xffe38a : 0xf3e6cf);
        }
        const busy = this.working.has('thodung');
        this.leds.forEach((m, i) => {
            const v = busy
                ? Math.sin(t * (5 + i) + i * 1.7) > 0.2
                    ? 1
                    : 0
                : i % 3 === 0
                  ? 0.5
                  : 0;
            m.color.setHex(
                v > 0.9
                    ? i % 2
                        ? 0x6effc4
                        : 0x7fe0ff
                    : v > 0
                      ? 0x3f8a6a
                      : 0x2c2a44,
            );
        });
        const hue = (t * 0.15) % 1;
        this.rgb.forEach((m, i) =>
            m.color.setHSL((hue + i * 0.3) % 1, 0.9, 0.65),
        );
        if (this.turntable) {
            this.turntable.rotation.y +=
                dt * (this.working.has('thuam') ? 6 : 0.6);
        }
        this.stringLights.forEach((m, i) => {
            const on = 0.55 + 0.45 * Math.sin(t * 2 + i * 1.3);
            const base = [C.yellow, C.pink, C.mint, C.blue][i % 4];
            m.color
                .setHex(base)
                .multiplyScalar(0.5 + on * 0.5 * (0.6 + this.night * 0.4));
        });
        for (const m of this.reelMeshes.values()) {
            const p = m.userData.pop as number;
            if (p > 0) {
                m.userData.pop = Math.max(0, p - dt * 1.2);
                const s = 1 + Math.sin((1 - m.userData.pop) * Math.PI) * 0.45;
                m.scale.setScalar(s);
                m.rotation.z += dt * 8 * m.userData.pop;
            }
        }
    }
}

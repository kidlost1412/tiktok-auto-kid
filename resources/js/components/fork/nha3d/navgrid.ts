// Lưới va chạm cho người đi lại: quét MỌI hình tĩnh trong nhà/vườn (tường, khung cửa, bàn ghế, cầu thang, cây, hàng rào…)
// thành ô 10 cm theo từng tầng, tính khoảng cách tới vật cản gần nhất, rồi tìm đường A* + làm mượt (không cắt góc).
// Giữa các tầng vẫn đi theo đồ thị điểm (cầu thang); trong cùng một tầng thì đi theo lưới này.
import * as THREE from 'three';

import {
    F1,
    F2,
    FA,
    FENCE_Z,
    PLOT,
    POND,
    VEG,
    XL0,
    XR1,
    Z_FRONT,
} from './layout';

/** Kích thước một ô (m). */
export const CELL = 0.1;
/** Bán kính thân người khi va tường/đồ đạc (đầu chibi to nên hơi rộng). */
export const AGENT_R = 0.3;
/** Khoảng cách tối thiểu giữa tâm hai người. */
export const PAIR_D = 0.62;

const FLOORS = [F1, F2, FA];

/** Tầng của một độ cao: 0 = tầng 1 + vườn, 1 = tầng 2, 2 = gác mái. */
export const levelOf = (y: number) => (y < F1 + 1.6 ? 0 : y < F2 + 1.6 ? 1 : 2);

/** Mặt sàn tầng 1 + vườn tại (x, z). */
export const groundY = (x: number, z: number) =>
    z <= Z_FRONT && x >= XL0 - 0.3 && x <= XR1 + 0.3 ? F1 : 0;

const inPond = (x: number, z: number, k = 1) =>
    ((x - POND.x) / (POND.rx * k)) ** 2 + ((z - POND.z) / (POND.rz * k)) ** 2 <
    1;
export { inPond };

interface Circle {
    x: number;
    z: number;
    r: number;
}

class Heap {
    private ids: number[] = [];
    private keys: number[] = [];
    get size() {
        return this.ids.length;
    }
    push(id: number, k: number) {
        const ids = this.ids;
        const ks = this.keys;
        let i = ids.length;
        ids.push(id);
        ks.push(k);
        while (i > 0) {
            const p = (i - 1) >> 1;
            if (ks[p] <= k) {
                break;
            }
            ids[i] = ids[p];
            ks[i] = ks[p];
            i = p;
        }
        ids[i] = id;
        ks[i] = k;
    }
    pop(): number {
        const ids = this.ids;
        const ks = this.keys;
        const top = ids[0];
        const id = ids.pop()!;
        const k = ks.pop()!;
        const n = ids.length;
        if (n) {
            let i = 0;
            for (;;) {
                let c = i * 2 + 1;
                if (c >= n) {
                    break;
                }
                if (c + 1 < n && ks[c + 1] < ks[c]) {
                    c++;
                }
                if (ks[c] >= k) {
                    break;
                }
                ids[i] = ids[c];
                ks[i] = ks[c];
                i = c;
            }
            ids[i] = id;
            ks[i] = k;
        }

        return top;
    }
}

const _a = new THREE.Vector3();
const _b = new THREE.Vector3();
const _c = new THREE.Vector3();
const _m = new THREE.Matrix4();
const _mi = new THREE.Matrix4();

export class NavGrid {
    readonly x0 = PLOT.x0;
    readonly z0 = PLOT.z0;
    readonly nx = Math.ceil((PLOT.x1 - PLOT.x0) / CELL);
    readonly nz = Math.ceil((PLOT.z1 - PLOT.z0) / CELL);
    /** 1 = có vật cản (từng tầng). */
    readonly occ: Uint8Array[] = [];
    /** Khoảng cách (m) từ tâm ô tới vật cản gần nhất. */
    readonly dist: Float32Array[] = [];
    private floor: Uint8Array[] = [];
    /** Thời gian dựng (ms) — để báo cáo hiệu năng. */
    buildMs = 0;

    constructor() {
        for (let l = 0; l < FLOORS.length; l++) {
            this.occ.push(new Uint8Array(this.nx * this.nz));
            this.floor.push(new Uint8Array(this.nx * this.nz));
            this.dist.push(new Float32Array(this.nx * this.nz));
        }
    }

    ix(x: number) {
        return Math.floor((x - this.x0) / CELL);
    }
    iz(z: number) {
        return Math.floor((z - this.z0) / CELL);
    }
    cx(i: number) {
        return this.x0 + (i + 0.5) * CELL;
    }
    cz(j: number) {
        return this.z0 + (j + 0.5) * CELL;
    }

    /**
     * Quét các nhóm hình tĩnh. `seeds`: các điểm chắc chắn đi được (điểm đồ thị) để loại phần "lòng" kín của đồ vật.
     * `skip`: vùng không quét (lòng cầu thang — đi theo đồ thị).
     */
    build(
        roots: THREE.Object3D[],
        seeds: THREE.Vector3[],
        skip: { x0: number; x1: number; z0: number; z1: number }[],
    ) {
        const t0 = performance.now();
        for (const r of roots) {
            r.updateWorldMatrix(true, true);
            r.traverseVisible((o) => {
                const m = o as THREE.Mesh;
                if (!m.isMesh || o.userData.noCollide) {
                    return;
                }
                const mat = m.material as THREE.Material;
                if (
                    !mat ||
                    Array.isArray(mat) ||
                    mat.visible === false ||
                    (mat.transparent && !mat.depthWrite) ||
                    mat.blending === THREE.AdditiveBlending
                ) {
                    return; // quầng sáng, bóng mờ, hiệu ứng: không phải vật cản
                }
                const geo = m.geometry;
                if (!geo?.attributes.position) {
                    return;
                }
                const im = m as THREE.InstancedMesh;
                if (im.isInstancedMesh) {
                    geo.computeBoundingBox();
                    const bb = geo.boundingBox!;
                    if (bb.max.y - bb.min.y < 0.5) {
                        return; // cỏ, hoa nhỏ: đi xuyên được
                    }
                    for (let i = 0; i < im.count; i++) {
                        im.getMatrixAt(i, _mi);
                        _m.multiplyMatrices(m.matrixWorld, _mi);
                        this.rasterMesh(geo, _m, skip);
                    }
                } else {
                    this.rasterMesh(geo, m.matrixWorld, skip);
                }
            });
        }
        // các vùng vẽ bằng công thức: hồ, luống rau, ngoài hàng rào
        const o0 = this.occ[0];
        for (let j = 0; j < this.nz; j++) {
            const z = this.cz(j);
            for (let i = 0; i < this.nx; i++) {
                const x = this.cx(i);
                if (
                    inPond(x, z, 1.04) ||
                    (x > VEG.x0 - 0.1 &&
                        x < VEG.x1 + 0.1 &&
                        z > VEG.z0 - 0.1 &&
                        z < VEG.z1 + 0.1) ||
                    z > FENCE_Z - 0.05 ||
                    x < PLOT.x0 + 0.4 ||
                    x > PLOT.x1 - 0.4 ||
                    z < PLOT.z0 + 0.4
                ) {
                    o0[j * this.nx + i] = 1;
                }
            }
        }
        // tầng trên: chỗ nào không có sàn là vực
        for (let l = 1; l < FLOORS.length; l++) {
            const o = this.occ[l];
            const f = this.floor[l];
            for (let k = 0; k < o.length; k++) {
                if (!f[k]) {
                    o[k] = 1;
                }
            }
        }
        // lòng kín của đồ vật (chỉ quét được vỏ): ô trống không nối với điểm đi được nào → coi là vật cản
        for (let l = 0; l < FLOORS.length; l++) {
            const o = this.occ[l];
            const seen = new Uint8Array(o.length);
            const stack: number[] = [];
            for (const s of seeds) {
                if (levelOf(s.y) !== l) {
                    continue;
                }
                const i = this.ix(s.x);
                const j = this.iz(s.z);
                if (i < 0 || j < 0 || i >= this.nx || j >= this.nz) {
                    continue;
                }
                const k = j * this.nx + i;
                if (!o[k] && !seen[k]) {
                    seen[k] = 1;
                    stack.push(k);
                }
            }
            while (stack.length) {
                const k = stack.pop()!;
                const i = k % this.nx;
                const j = (k - i) / this.nx;
                const nb = [
                    i > 0 ? k - 1 : -1,
                    i < this.nx - 1 ? k + 1 : -1,
                    j > 0 ? k - this.nx : -1,
                    j < this.nz - 1 ? k + this.nx : -1,
                ];
                for (const n of nb) {
                    if (n >= 0 && !o[n] && !seen[n]) {
                        seen[n] = 1;
                        stack.push(n);
                    }
                }
            }
            for (let k = 0; k < o.length; k++) {
                if (!o[k] && !seen[k]) {
                    o[k] = 2;
                }
            }
            this.distance(l);
        }
        this.buildMs = performance.now() - t0;
    }

    private rasterMesh(
        geo: THREE.BufferGeometry,
        mw: THREE.Matrix4,
        skip: { x0: number; x1: number; z0: number; z1: number }[],
    ) {
        const pos = geo.attributes.position as THREE.BufferAttribute;
        const idx = geo.index;
        const n = idx ? idx.count : pos.count;
        for (let t = 0; t + 2 < n; t += 3) {
            const a = idx ? idx.getX(t) : t;
            const b = idx ? idx.getX(t + 1) : t + 1;
            const c = idx ? idx.getX(t + 2) : t + 2;
            _a.fromBufferAttribute(pos, a).applyMatrix4(mw);
            _b.fromBufferAttribute(pos, b).applyMatrix4(mw);
            _c.fromBufferAttribute(pos, c).applyMatrix4(mw);
            this.rasterTri(_a, _b, _c, skip);
        }
    }

    private rasterTri(
        a: THREE.Vector3,
        b: THREE.Vector3,
        c: THREE.Vector3,
        skip: { x0: number; x1: number; z0: number; z1: number }[],
    ) {
        const ymin = Math.min(a.y, b.y, c.y);
        const ymax = Math.max(a.y, b.y, c.y);
        const mx = (a.x + b.x + c.x) / 3;
        const mz = (a.z + b.z + c.z) / 3;
        for (const s of skip) {
            if (mx > s.x0 && mx < s.x1 && mz > s.z0 && mz < s.z1) {
                return;
            }
        }
        // mặt sàn tầng trên (mặt ngửa lên, ngang mặt sàn)
        if (ymax - ymin < 0.02) {
            for (let l = 1; l < FLOORS.length; l++) {
                if (Math.abs(ymin - FLOORS[l]) < 0.08) {
                    const ny =
                        (b.z - a.z) * (c.x - a.x) - (b.x - a.x) * (c.z - a.z);
                    if (ny > 0 || ny < 0) {
                        this.fillPoly([a, b, c], this.floor[l], false);
                    }
                }
            }
        }
        for (let l = 0; l < FLOORS.length; l++) {
            const g = l === 0 ? groundY(mx, mz) : FLOORS[l];
            // ngoài vườn: bậc thềm, đá, hoa thấp bước qua được
            const lo = l === 0 && g === 0 ? 0.36 : g + 0.14;
            const hi = g + 1.55;
            if (ymax < lo || ymin > hi) {
                continue;
            }
            const poly = clipY([a, b, c], lo, hi);
            if (poly.length >= 2) {
                this.fillPoly(poly, this.occ[l], true);
            }
        }
    }

    /** Tô hình chiếu xuống mặt phẳng ngang của đa giác (kể cả khi nó dựng đứng thành một đường). */
    private fillPoly(poly: THREE.Vector3[], into: Uint8Array, edges: boolean) {
        const nx = this.nx;
        const nz = this.nz;
        const set = (x: number, z: number) => {
            const i = this.ix(x);
            const j = this.iz(z);
            if (i >= 0 && j >= 0 && i < nx && j < nz) {
                into[j * nx + i] = 1;
            }
        };
        if (edges) {
            for (let k = 0; k < poly.length; k++) {
                const p = poly[k];
                const q = poly[(k + 1) % poly.length];
                const len = Math.hypot(q.x - p.x, q.z - p.z);
                const st = Math.max(1, Math.ceil(len / (CELL * 0.5)));
                for (let s = 0; s <= st; s++) {
                    const t = s / st;
                    set(p.x + (q.x - p.x) * t, p.z + (q.z - p.z) * t);
                }
            }
        }
        // lòng đa giác: tâm ô nằm trong (đa giác lồi sau khi cắt)
        let x0 = Infinity;
        let x1 = -Infinity;
        let z0 = Infinity;
        let z1 = -Infinity;
        for (const p of poly) {
            x0 = Math.min(x0, p.x);
            x1 = Math.max(x1, p.x);
            z0 = Math.min(z0, p.z);
            z1 = Math.max(z1, p.z);
        }
        const i0 = Math.max(0, this.ix(x0));
        const i1 = Math.min(nx - 1, this.ix(x1));
        const j0 = Math.max(0, this.iz(z0));
        const j1 = Math.min(nz - 1, this.iz(z1));
        if (i1 < i0 || j1 < j0) {
            return;
        }
        for (let j = j0; j <= j1; j++) {
            const z = this.cz(j);
            for (let i = i0; i <= i1; i++) {
                const x = this.cx(i);
                let pos = false;
                let neg = false;
                for (let k = 0; k < poly.length; k++) {
                    const p = poly[k];
                    const q = poly[(k + 1) % poly.length];
                    const cr =
                        (q.x - p.x) * (z - p.z) - (q.z - p.z) * (x - p.x);
                    if (cr > 1e-9) {
                        pos = true;
                    } else if (cr < -1e-9) {
                        neg = true;
                    }
                }
                if (!(pos && neg)) {
                    into[j * nx + i] = 1;
                }
            }
        }
    }

    /** Biến đổi khoảng cách (chamfer 2 lượt), đơn vị mét. */
    private distance(l: number) {
        const o = this.occ[l];
        const d = this.dist[l];
        const nx = this.nx;
        const nz = this.nz;
        const BIG = 1e6;
        const D1 = CELL;
        const D2 = CELL * Math.SQRT2;
        for (let k = 0; k < o.length; k++) {
            d[k] = o[k] ? 0 : BIG;
        }
        for (let j = 0; j < nz; j++) {
            for (let i = 0; i < nx; i++) {
                const k = j * nx + i;
                let v = d[k];
                if (v === 0) {
                    continue;
                }
                if (i > 0) {
                    v = Math.min(v, d[k - 1] + D1);
                }
                if (j > 0) {
                    v = Math.min(v, d[k - nx] + D1);
                    if (i > 0) {
                        v = Math.min(v, d[k - nx - 1] + D2);
                    }
                    if (i < nx - 1) {
                        v = Math.min(v, d[k - nx + 1] + D2);
                    }
                }
                d[k] = v;
            }
        }
        for (let j = nz - 1; j >= 0; j--) {
            for (let i = nx - 1; i >= 0; i--) {
                const k = j * nx + i;
                let v = d[k];
                if (v === 0) {
                    continue;
                }
                if (i < nx - 1) {
                    v = Math.min(v, d[k + 1] + D1);
                }
                if (j < nz - 1) {
                    v = Math.min(v, d[k + nx] + D1);
                    if (i < nx - 1) {
                        v = Math.min(v, d[k + nx + 1] + D2);
                    }
                    if (i > 0) {
                        v = Math.min(v, d[k + nx - 1] + D2);
                    }
                }
                d[k] = v;
            }
        }
        // khoảng cách tính từ tâm ô vật cản → trừ nửa ô để ra tới mép vật
        for (let k = 0; k < d.length; k++) {
            if (d[k] > 0) {
                d[k] = Math.max(0.001, d[k] - CELL * 0.5);
            }
        }
    }

    /** Khoảng trống quanh điểm (m); ngoài lưới = 0. */
    clearance(l: number, x: number, z: number) {
        const i = this.ix(x);
        const j = this.iz(z);
        if (i < 0 || j < 0 || i >= this.nx || j >= this.nz) {
            return 0;
        }

        return this.dist[l][j * this.nx + i];
    }

    free(l: number, x: number, z: number, r = AGENT_R) {
        return this.clearance(l, x, z) >= r;
    }

    /**
     * Bước từ (fx, fz) tới (tx, tz) mà không lấn vào vật cản: bị chặn thì trượt dọc mép (bỏ phần lao vào tường).
     * Đang lỡ đứng trong vùng chật thì vẫn cho bước nếu ra xa vật cản hơn.
     */
    slide(
        l: number,
        fx: number,
        fz: number,
        tx: number,
        tz: number,
        r = AGENT_R,
    ) {
        const need = r - 0.015;
        const c0 = this.clearance(l, fx, fz);
        const ok = (x: number, z: number) => {
            const c = this.clearance(l, x, z);

            return c >= need || (c0 < need && c > c0 + 1e-4);
        };
        if (ok(tx, tz)) {
            return { x: tx, z: tz };
        }
        // pháp tuyến mép vật cản = hướng khoảng cách tăng
        const e = CELL;
        const gx =
            this.clearance(l, tx + e, tz) - this.clearance(l, tx - e, tz);
        const gz =
            this.clearance(l, tx, tz + e) - this.clearance(l, tx, tz - e);
        const gl = Math.hypot(gx, gz);
        let mx = tx - fx;
        let mz = tz - fz;
        if (gl > 1e-6) {
            const nx = gx / gl;
            const nz = gz / gl;
            const into = mx * nx + mz * nz;
            if (into < 0) {
                mx -= into * nx;
                mz -= into * nz;
                if (ok(fx + mx, fz + mz)) {
                    return { x: fx + mx, z: fz + mz };
                }
            }
        }
        if (ok(tx, fz)) {
            return { x: tx, z: fz };
        }
        if (ok(fx, tz)) {
            return { x: fx, z: tz };
        }

        return { x: fx, z: fz };
    }

    /** Đoạn thẳng a→b có đủ rộng cho người bán kính r không. */
    los(
        l: number,
        ax: number,
        az: number,
        bx: number,
        bz: number,
        r = AGENT_R,
    ) {
        const len = Math.hypot(bx - ax, bz - az);
        const st = Math.max(1, Math.ceil(len / (CELL * 0.5)));
        for (let s = 0; s <= st; s++) {
            const t = s / st;
            if (this.clearance(l, ax + (bx - ax) * t, az + (bz - az) * t) < r) {
                return false;
            }
        }

        return true;
    }

    /** Ô trống gần nhất (theo vòng xoắn) — dùng khi đích/xuất phát nằm trong ghế, giường… */
    nearestFree(l: number, x: number, z: number, r = AGENT_R, maxR = 2.5) {
        if (this.free(l, x, z, r)) {
            return { x, z };
        }
        let best: { x: number; z: number } | null = null;
        let bd = Infinity;
        const n = Math.ceil(maxR / CELL);
        const i0 = this.ix(x);
        const j0 = this.iz(z);
        for (let dj = -n; dj <= n; dj++) {
            for (let di = -n; di <= n; di++) {
                const d = di * di + dj * dj;
                if (d >= bd || d > n * n) {
                    continue;
                }
                const i = i0 + di;
                const j = j0 + dj;
                if (i < 0 || j < 0 || i >= this.nx || j >= this.nz) {
                    continue;
                }
                if (this.dist[l][j * this.nx + i] >= r + 0.02) {
                    bd = d;
                    best = { x: this.cx(i), z: this.cz(j) };
                }
            }
        }

        return best;
    }

    /**
     * A* trên lưới (8 hướng, không lách qua góc) rồi kéo thẳng các đoạn nhìn thấy nhau.
     * `avoid`: người đứng chắn (tạm coi là vật cản). Trả về các điểm (không gồm điểm đầu), null nếu không tới được.
     */
    findPath(
        l: number,
        ax: number,
        az: number,
        bx: number,
        bz: number,
        r = AGENT_R,
        avoid: Circle[] = [],
    ): { x: number; z: number }[] | null {
        const nx = this.nx;
        const nz = this.nz;
        const d = this.dist[l];
        const si = this.ix(ax);
        const sj = this.iz(az);
        const gi = this.ix(bx);
        const gj = this.iz(bz);
        if (
            si < 0 ||
            sj < 0 ||
            gi < 0 ||
            gj < 0 ||
            si >= nx ||
            gi >= nx ||
            sj >= nz ||
            gj >= nz
        ) {
            return null;
        }
        const ok = (i: number, j: number) => {
            if (d[j * nx + i] < r) {
                return false;
            }
            if (avoid.length) {
                const x = this.cx(i);
                const z = this.cz(j);
                for (const c of avoid) {
                    if ((x - c.x) ** 2 + (z - c.z) ** 2 < c.r * c.r) {
                        return false;
                    }
                }
            }

            return true;
        };
        if (si === gi && sj === gj) {
            return [{ x: bx, z: bz }];
        }
        const start = sj * nx + si;
        const goal = gj * nx + gi;
        const g = new Float32Array(nx * nz).fill(Infinity);
        const came = new Int32Array(nx * nz).fill(-1);
        const closed = new Uint8Array(nx * nz);
        const h = (i: number, j: number) => {
            const dx = Math.abs(i - gi);
            const dz = Math.abs(j - gj);

            return (dx + dz + (Math.SQRT2 - 2) * Math.min(dx, dz)) * 1.02;
        };
        const heap = new Heap();
        g[start] = 0;
        heap.push(start, h(si, sj));
        let found = false;
        let iter = 0;
        while (heap.size && iter++ < 400000) {
            const k = heap.pop();
            if (closed[k]) {
                continue;
            }
            closed[k] = 1;
            if (k === goal) {
                found = true;
                break;
            }
            const i = k % nx;
            const j = (k - i) / nx;
            for (let dj = -1; dj <= 1; dj++) {
                for (let di = -1; di <= 1; di++) {
                    if (!di && !dj) {
                        continue;
                    }
                    const ni = i + di;
                    const nj = j + dj;
                    if (ni < 0 || nj < 0 || ni >= nx || nj >= nz) {
                        continue;
                    }
                    const nk = nj * nx + ni;
                    if (closed[nk]) {
                        continue;
                    }
                    if (nk !== goal && !ok(ni, nj)) {
                        continue;
                    }
                    if (di && dj && (!ok(i + di, j) || !ok(i, j + dj))) {
                        continue; // không cắt góc
                    }
                    const ng = g[k] + (di && dj ? Math.SQRT2 : 1);
                    if (ng < g[nk]) {
                        g[nk] = ng;
                        came[nk] = k;
                        heap.push(nk, ng + h(ni, nj));
                    }
                }
            }
        }
        if (!found) {
            return null;
        }
        const cells: { x: number; z: number }[] = [];
        for (let k = came[goal]; k !== -1 && k !== start; k = came[k]) {
            const i = k % nx;
            cells.unshift({ x: this.cx(i), z: this.cz((k - i) / nx) });
        }
        cells.push({ x: bx, z: bz });
        // kéo thẳng: từ điểm hiện tại nhảy tới điểm xa nhất còn nhìn thấy
        const out: { x: number; z: number }[] = [];
        let cx = ax;
        let cz = az;
        let i = 0;
        while (i < cells.length) {
            let far = i;
            for (let k = cells.length - 1; k > i; k--) {
                if (this.los(l, cx, cz, cells[k].x, cells[k].z, r * 0.98)) {
                    far = k;
                    break;
                }
            }
            out.push(cells[far]);
            cx = cells[far].x;
            cz = cells[far].z;
            i = far + 1;
        }

        return out;
    }

    /** Ảnh PNG (data URL) của một tầng để soát bằng mắt. */
    debugImage(l: number, marks: { x: number; z: number; c?: string }[] = []) {
        const cv = document.createElement('canvas');
        cv.width = this.nx;
        cv.height = this.nz;
        const g = cv.getContext('2d')!;
        const img = g.createImageData(this.nx, this.nz);
        const o = this.occ[l];
        const d = this.dist[l];
        for (let k = 0; k < o.length; k++) {
            const v =
                o[k] === 1
                    ? [40, 30, 60]
                    : o[k] === 2
                      ? [120, 90, 140]
                      : d[k] < AGENT_R
                        ? [230, 170, 170]
                        : [235, 245, 225];
            img.data[k * 4] = v[0];
            img.data[k * 4 + 1] = v[1];
            img.data[k * 4 + 2] = v[2];
            img.data[k * 4 + 3] = 255;
        }
        g.putImageData(img, 0, 0);
        for (const m of marks) {
            g.fillStyle = m.c ?? '#2266ff';
            g.fillRect(this.ix(m.x) - 2, this.iz(m.z) - 2, 5, 5);
        }

        return cv.toDataURL('image/png');
    }
}

/** Cắt đa giác theo dải độ cao [lo, hi]. */
const clipY = (poly: THREE.Vector3[], lo: number, hi: number) => {
    const cut = (pts: THREE.Vector3[], y: number, keepAbove: boolean) => {
        const out: THREE.Vector3[] = [];
        for (let k = 0; k < pts.length; k++) {
            const p = pts[k];
            const q = pts[(k + 1) % pts.length];
            const pin = keepAbove ? p.y >= y : p.y <= y;
            const qin = keepAbove ? q.y >= y : q.y <= y;
            if (pin) {
                out.push(p);
            }
            if (pin !== qin) {
                const t = (y - p.y) / (q.y - p.y);
                out.push(
                    new THREE.Vector3(
                        p.x + (q.x - p.x) * t,
                        y,
                        p.z + (q.z - p.z) * t,
                    ),
                );
            }
        }

        return out;
    };
    let p = poly;
    if (Math.min(...p.map((v) => v.y)) < lo) {
        p = cut(p, lo, true);
    }
    if (p.length && Math.max(...p.map((v) => v.y)) > hi) {
        p = cut(p, hi, false);
    }

    return p;
};

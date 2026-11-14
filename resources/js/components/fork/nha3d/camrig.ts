// Camera phối cảnh với hai chế độ:
//  - "walk": ngang tầm mắt, đi theo sau lưng Kid (kéo chuột để xoay, cuộn để gần/xa), không xuyên tường.
//  - "overview": toàn cảnh góc thấp, nhìn chính diện ngôi nhà (xoay/phóng giới hạn), tự căn cho vừa khung.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

import { RIDGE_Y, RIDGE_Z } from './house';
import {
    F2,
    FA,
    PLOT,
    X0,
    X1,
    XL0,
    XR1,
    Z_BACK,
    Z_FRONT,
    Z_ROOM,
} from './layout';
import { clamp } from './util';

export type CamMode = 'walk' | 'overview';

const OV_AZ = 0.12;
const OV_AZ_RANGE = 0.55;
const OV_POLAR = 1.3;
const OV_FOV = 30;
const WALK_FOV = 50;

export class CamRig {
    readonly camera = new THREE.PerspectiveCamera(WALK_FOV, 1, 0.1, 400);
    readonly controls: OrbitControls;
    mode: CamMode = 'walk';
    /** Góc xoay quanh Kid (0 = camera ở phía trước nhà nhìn vào). */
    yaw = 0;
    pitch = 0.26;
    dist = 8.4;
    private aspect = 1;
    private fitTarget = new THREE.Vector3(0, 3, 0);
    private fitDist = 60;
    private touched = false;
    private reset = -1;
    private from = { pos: new THREE.Vector3(), target: new THREE.Vector3() };
    private look = new THREE.Vector3();
    private ray = new THREE.Raycaster();
    private seeded = false;

    constructor(
        dom: HTMLElement,
        private motion: boolean,
        public occluders: THREE.Object3D[],
    ) {
        const c = new OrbitControls(this.camera, dom);
        c.enableDamping = motion;
        c.dampingFactor = 0.08;
        c.rotateSpeed = 0.5;
        c.minAzimuthAngle = OV_AZ - OV_AZ_RANGE;
        c.maxAzimuthAngle = OV_AZ + OV_AZ_RANGE;
        c.minPolarAngle = 1.1;
        c.maxPolarAngle = 1.45;
        c.zoomToCursor = true;
        c.screenSpacePanning = true;
        c.addEventListener('start', () => {
            this.touched = true;
            this.glideFocus = null;
        });
        c.addEventListener('change', () => {
            const t = c.target;
            const cx = clamp(t.x, PLOT.x0 + 4, PLOT.x1 - 4);
            const cy = clamp(t.y, 0, 10);
            const cz = clamp(t.z, -8, 12);
            if (cx !== t.x || cy !== t.y || cz !== t.z) {
                const d = new THREE.Vector3(cx - t.x, cy - t.y, cz - t.z);
                t.add(d);
                this.camera.position.add(d);
            }
        });
        this.controls = c;
    }

    /** Hướng nhìn ngang của camera (để phím WASD đi theo hướng màn hình ở cả hai chế độ). */
    get viewYaw() {
        return this.mode === 'overview'
            ? this.controls.getAzimuthalAngle()
            : this.yaw;
    }

    snapshot() {
        const r = (v: THREE.Vector3) => v.toArray().map((x) => +x.toFixed(3));

        return {
            yaw: this.yaw,
            pitch: this.pitch,
            dist: this.dist,
            ov: this.touched
                ? { p: r(this.camera.position), t: r(this.controls.target) }
                : null,
        };
    }

    /** Khôi phục góc nhìn (gọi sau setMode). */
    restore(s: ReturnType<CamRig['snapshot']>) {
        this.yaw = s.yaw;
        this.pitch = s.pitch;
        this.dist = s.dist;
        this.seeded = false;
        if (s.ov && this.mode === 'overview') {
            this.camera.position.fromArray(s.ov.p);
            this.controls.target.fromArray(s.ov.t);
            this.touched = true;
            this.controls.update();
        }
    }

    /** Tâm đang nhìn (để làm mờ tường đầu hồi…). */
    get target() {
        return this.mode === 'overview' ? this.controls.target : this.look;
    }

    setMode(m: CamMode, focus: THREE.Vector3) {
        this.mode = m;
        this.controls.enabled = m === 'overview';
        this.camera.fov = m === 'overview' ? OV_FOV : WALK_FOV;
        // near/far vừa đủ để độ sâu chính xác (tránh nhấp nháy mặt phẳng sát nhau)
        this.camera.near = m === 'overview' ? 2 : 0.25;
        this.camera.far = m === 'overview' ? 260 : 160;
        this.camera.updateProjectionMatrix();
        if (m === 'overview') {
            this.touched = false;
            this.placeOverview();
        } else {
            this.seeded = false;
            this.update(0, focus);
        }
    }

    resize(aspect: number) {
        this.aspect = aspect;
        this.camera.aspect = aspect;
        this.camera.updateProjectionMatrix();
        this.fitOverview();
        if (this.mode === 'overview' && !this.touched) {
            this.placeOverview();
        }
    }

    /** Toàn cảnh: tính tâm + khoảng cách sao cho cả nhà và hai dãy phụ vừa khung. */
    private fitOverview() {
        const narrow = this.aspect < 1.1;
        const dir = new THREE.Vector3(
            Math.sin(OV_POLAR) * Math.sin(OV_AZ),
            Math.cos(OV_POLAR),
            Math.sin(OV_POLAR) * Math.cos(OV_AZ),
        );
        const tmp = new THREE.PerspectiveCamera(OV_FOV, this.aspect, 0.1, 400);
        const base = new THREE.Vector3(0.6, 3.6, -0.6);
        tmp.position.copy(base).addScaledVector(dir, 80);
        tmp.lookAt(base);
        tmp.updateMatrixWorld(true);
        const x0 = narrow ? -10 : XL0 - 0.4;
        const x1 = narrow ? 10 : XR1 + 0.4;
        const pts: [number, number, number][] = [];
        for (const x of [x0, x1]) {
            pts.push(
                [x, 0, Z_FRONT + 2.6],
                [x, F2 + 1.4, Z_BACK - 0.4],
                [x, 0, Z_BACK],
            );
        }
        for (const x of narrow ? [x0, x1] : [X0 - 0.8, X1 + 0.8]) {
            pts.push([x, RIDGE_Y + 0.5, RIDGE_Z], [x, FA + 0.3, Z_ROOM]);
        }
        // tâm = trung bình các điểm (theo mặt phẳng camera), rồi lùi ra tới khi mọi điểm lọt khung
        const inv = tmp.matrixWorldInverse;
        const v = new THREE.Vector3();
        let mx = Infinity;
        let Mx = -Infinity;
        let my = Infinity;
        let My = -Infinity;
        for (const [x, y, z] of pts) {
            v.set(x, y, z).applyMatrix4(inv);
            mx = Math.min(mx, v.x);
            Mx = Math.max(Mx, v.x);
            my = Math.min(my, v.y);
            My = Math.max(My, v.y);
        }
        My += (My - my) * 0.06; // chừa chỗ khung lời chào
        const right = new THREE.Vector3().setFromMatrixColumn(
            tmp.matrixWorld,
            0,
        );
        const up = new THREE.Vector3().setFromMatrixColumn(tmp.matrixWorld, 1);
        this.fitTarget
            .copy(base)
            .addScaledVector(right, (mx + Mx) / 2)
            .addScaledVector(up, (my + My) / 2);
        const tv = Math.tan(THREE.MathUtils.degToRad(OV_FOV / 2));
        const th = tv * this.aspect;
        let need = 10;
        const fwd = dir.clone();
        for (const [x, y, z] of pts) {
            v.set(x, y, z).sub(this.fitTarget);
            const px = v.dot(right);
            const py = v.dot(up);
            const pz = v.dot(fwd); // về phía camera
            need = Math.max(
                need,
                pz + Math.abs(px) / th,
                pz + Math.abs(py) / tv,
            );
        }
        this.fitDist = need * 1.02;
        // tinh chỉnh theo phối cảnh thật: chiếu các điểm mốc, dời tâm cho cân và thu khoảng cách cho vừa khít
        const cam = new THREE.PerspectiveCamera(OV_FOV, this.aspect, 0.1, 400);
        for (let it = 0; it < 3; it++) {
            this.overviewPose(cam.position);
            cam.lookAt(this.fitTarget);
            cam.updateMatrixWorld(true);
            let x0 = Infinity;
            let x1 = -Infinity;
            let y0 = Infinity;
            let y1 = -Infinity;
            for (const [x, y, z] of pts) {
                v.set(x, y, z).project(cam);
                x0 = Math.min(x0, v.x);
                x1 = Math.max(x1, v.x);
                y0 = Math.min(y0, v.y);
                y1 = Math.max(y1, v.y);
            }
            y1 += (y1 - y0) * 0.08; // chừa chỗ khung lời chào
            const cr = new THREE.Vector3().setFromMatrixColumn(
                cam.matrixWorld,
                0,
            );
            const cu = new THREE.Vector3().setFromMatrixColumn(
                cam.matrixWorld,
                1,
            );
            this.fitTarget
                .addScaledVector(cr, ((x0 + x1) / 2) * th * this.fitDist)
                .addScaledVector(cu, ((y0 + y1) / 2) * tv * this.fitDist);
            const k = Math.max((x1 - x0) / 2, (y1 - y0) / 2) / 0.97;
            this.fitDist *= 0.5 + 0.5 * k;
        }
    }

    private overviewPose(pos: THREE.Vector3) {
        return pos.set(
            this.fitTarget.x +
                this.fitDist * Math.sin(OV_POLAR) * Math.sin(OV_AZ),
            this.fitTarget.y + this.fitDist * Math.cos(OV_POLAR),
            this.fitTarget.z +
                this.fitDist * Math.sin(OV_POLAR) * Math.cos(OV_AZ),
        );
    }

    private placeOverview() {
        this.controls.target.copy(this.fitTarget);
        this.overviewPose(this.camera.position);
        this.controls.minDistance = this.fitDist * 0.3;
        this.controls.maxDistance = this.fitDist * 1.25;
        this.camera.lookAt(this.fitTarget);
        this.controls.update();
    }

    /** Bấm đúp: về góc nhìn ban đầu. */
    home() {
        if (this.mode === 'walk') {
            this.yaw = 0;
            this.pitch = 0.26;
            this.dist = 8.4;

            return;
        }
        this.reset = 0;
        this.from.pos.copy(this.camera.position);
        this.from.target.copy(this.controls.target);
    }

    /** Khi sếp đang nói chuyện với ai: xoay camera chéo sang để thấy cả hai (người dùng kéo chuột là thôi). */
    yawTo: number | null = null;

    /** "Gọi về gấp" (Toàn cảnh): điểm camera lướt theo; người dùng kéo/xoay/cuộn là huỷ ngay. */
    glideFocus: THREE.Vector3 | null = null;

    drag(dx: number, dy: number) {
        this.yawTo = null;
        this.yaw -= dx * 0.006;
        this.pitch = clamp(this.pitch + dy * 0.004, 0.05, 0.85);
    }

    wheel(dy: number) {
        this.dist = clamp(this.dist * Math.exp(dy * 0.0012), 2.6, 13);
    }

    update(dt: number, focus: THREE.Vector3) {
        if (this.mode === 'overview') {
            if (this.reset >= 0) {
                this.reset = Math.min(1, this.reset + dt / 0.7);
                const k = 1 - Math.pow(1 - this.reset, 3);
                const home = this.overviewPose(new THREE.Vector3());
                this.camera.position.lerpVectors(this.from.pos, home, k);
                this.controls.target.lerpVectors(
                    this.from.target,
                    this.fitTarget,
                    k,
                );
                if (this.reset >= 1) {
                    this.reset = -1;
                    this.touched = false;
                }
            }
            const g = this.glideFocus;
            if (g) {
                // lướt mượt: dời cả camera lẫn tâm nhìn cùng một đoạn (giữ nguyên góc nhìn)
                const k = this.motion ? 1 - Math.exp(-dt * 2.6) : 1;
                const t = this.controls.target;
                const dx = (g.x - t.x) * k;
                const dy = (g.y + 1 - t.y) * k;
                const dz = (g.z - t.z) * k;
                t.x += dx;
                t.y += dy;
                t.z += dz;
                this.camera.position.x += dx;
                this.camera.position.y += dy;
                this.camera.position.z += dz;
                this.touched = true;
            }
            this.controls.update();

            return;
        }
        // đi theo sau lưng Kid, ngang tầm mắt
        if (this.yawTo !== null) {
            let d = this.yawTo - this.yaw;
            d = Math.atan2(Math.sin(d), Math.cos(d));
            this.yaw += d * (this.motion ? Math.min(1, dt * 3) : 1);
            if (Math.abs(d) < 0.01) {
                this.yawTo = null;
            }
        }
        const tgt = new THREE.Vector3(focus.x, focus.y + 1.55, focus.z);
        const dir = new THREE.Vector3(
            Math.sin(this.yaw) * Math.cos(this.pitch),
            Math.sin(this.pitch),
            Math.cos(this.yaw) * Math.cos(this.pitch),
        );
        // không xuyên tường: kéo camera lại gần nếu có vật chắn
        let d = this.dist;
        this.ray.set(tgt, dir);
        this.ray.far = d;
        const hit = this.ray.intersectObjects(this.occluders, false)[0];
        if (hit) {
            d = Math.max(0.8, hit.distance - 0.3);
        }
        const want = tgt.clone().addScaledVector(dir, d);
        if (!this.seeded || !this.motion) {
            this.seeded = true;
            this.camera.position.copy(want);
            this.look.copy(tgt);
        } else {
            const k = 1 - Math.exp(-dt * 7);
            this.camera.position.lerp(want, k);
            this.look.lerp(tgt, 1 - Math.exp(-dt * 10));
        }
        this.camera.lookAt(this.look);
    }
}

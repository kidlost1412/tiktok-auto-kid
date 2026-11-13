// Mèo cam: đi lang thang trong nhà và vườn, chọn một người "yêu thích" (đổi vài phút một lần) tới cọ chân
// hoặc nhảy lên bàn cuộn tròn ngủ cạnh họ, đuổi bướm, phơi nắng. Bấm vào thì "Meo~" + tim.
import * as THREE from 'three';

import type { Prio, Speech } from './speech';

import type { Actor, Talker } from './actor';
import type { Effects } from './effects';
import { GARDEN_NODES, SUNNY } from './layout';
import type { NavGraph } from './nav';
import {
    C,
    CanvasTex,
    clamp,
    damp,
    dampAngle,
    Kit,
    outlineMaterial,
    pick,
    rand,
    Shapes,
} from './util';
import type { Butterfly } from './world';

type Mode = 'idle' | 'walk' | 'curl' | 'rub' | 'jump' | 'chase' | 'sit';

interface Task {
    kind: 'path' | 'curl' | 'rub' | 'jump' | 'chase' | 'sit' | 'do';
    to?: string;
    run?: boolean;
    d?: number;
    from?: THREE.Vector3;
    dest?: THREE.Vector3;
    actor?: Actor;
    bf?: Butterfly;
    fn?: () => void;
}

export class Cat implements Talker {
    readonly key = 'meo';
    readonly root = new THREE.Group();
    readonly pos = new THREE.Vector3();
    alertUntil = 0;
    favourite: Actor | null = null;
    private favUntil = 0;
    private rot = 0;
    private targetRot = 0;
    private nodeId: string;
    private tasks: Task[] = [];
    private task: Task | null = null;
    private taskT = 0;
    private path: THREE.Vector3[] = [];
    private pathIds: string[] = [];
    private pathI = 0;
    private mode: Mode = 'curl';
    private body = new THREE.Group();
    private head = new THREE.Group();
    private legs: THREE.Object3D[] = [];
    private tail: THREE.Object3D[] = [];
    private face: CanvasTex;
    private faceState = '';
    private sayText: string | null = null;
    /** Điều phối lời nói chung của cả xưởng. */
    speech: Speech | null = null;
    private sayUntil = 0;
    private t = 0;
    private heartAt = 0;
    private onDesk: Actor | null = null;
    private outline: THREE.MeshBasicMaterial;
    private shadow: THREE.Mesh;
    private hopT = 0;
    private visualY = 0;

    constructor(
        kit: Kit,
        S: Shapes,
        private nav: NavGraph,
        private fx: Effects,
        private actors: Actor[],
        private deskTops: Record<string, THREE.Vector3>,
        private butterflies: Butterfly[],
        private now: () => number,
        private motion: boolean,
        shadowMat: THREE.Material,
    ) {
        this.outline = outlineMaterial(kit, C.ink, 0.012);
        const pickInfo = { kind: 'cat' };
        const orange = 0xffa64d;
        const part = (
            geo: THREE.BufferGeometry,
            col: number,
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
        ) => {
            const m = new THREE.Mesh(geo, kit.toon(col));
            m.position.set(p.x ?? 0, p.y ?? 0, p.z ?? 0);
            m.rotation.set(p.rx ?? 0, p.ry ?? 0, p.rz ?? 0);
            m.scale.set(p.sx ?? 1, p.sy ?? 1, p.sz ?? 1);
            m.userData.pick = pickInfo;
            parent.add(m);
            if (outline) {
                const o = new THREE.Mesh(geo, this.outline);
                o.raycast = () => undefined;
                m.add(o);
            }

            return m;
        };
        this.root.add(this.body);
        part(S.capsule(0.15, 0.26, 6, 14), orange, this.body, {
            y: 0.25,
            rx: Math.PI / 2,
        });
        part(
            S.sphere(0.13, 12, 10),
            0xfff3e2,
            this.body,
            { y: 0.2, z: 0.12, sx: 0.9, sy: 0.8 },
            false,
        );
        for (let k = 0; k < 3; k++) {
            part(
                S.torus(0.152, 0.018, 5, 16, Math.PI),
                0xe07f2a,
                this.body,
                { y: 0.25, z: -0.12 + k * 0.1, ry: Math.PI / 2, rz: 0 },
                false,
            );
        }
        // chân
        for (const [x, z] of [
            [0.08, 0.17],
            [-0.08, 0.17],
            [0.08, -0.17],
            [-0.08, -0.17],
        ]) {
            const leg = new THREE.Group();
            leg.position.set(x, 0.2, z);
            part(S.capsule(0.045, 0.1, 3, 8), orange, leg, { y: -0.09 });
            part(
                S.sphere(0.05, 8, 6),
                0xfff3e2,
                leg,
                { y: -0.16, z: 0.01, sy: 0.7 },
                false,
            );
            this.body.add(leg);
            this.legs.push(leg);
        }
        // đuôi
        let parent: THREE.Object3D = this.body;
        const base = new THREE.Group();
        base.position.set(0, 0.3, -0.27);
        this.body.add(base);
        parent = base;
        for (let k = 0; k < 4; k++) {
            const seg = new THREE.Group();
            if (k > 0) {
                seg.position.set(0, 0.11, 0);
            }
            part(
                S.capsule(0.04 - k * 0.004, 0.08, 3, 8),
                k === 3 ? 0xfff3e2 : orange,
                seg,
                { y: 0.05 },
            );
            parent.add(seg);
            this.tail.push(seg);
            parent = seg;
        }
        // đầu
        this.head.position.set(0, 0.42, 0.27);
        this.body.add(this.head);
        part(S.sphere(0.17, 18, 14), orange, this.head, { sx: 1.1, sy: 0.95 });
        for (const sx of [-1, 1]) {
            part(S.cone(0.07, 0.13, 6), orange, this.head, {
                x: sx * 0.1,
                y: 0.15,
                z: -0.02,
                rz: -sx * 0.35,
            });
            part(
                S.cone(0.04, 0.08, 6),
                C.pinkSoft,
                this.head,
                { x: sx * 0.1, y: 0.145, z: 0.012, rz: -sx * 0.35 },
                false,
            );
        }
        part(
            S.sphere(0.08, 10, 8),
            0xfff3e2,
            this.head,
            { y: -0.05, z: 0.1, sx: 1.2, sy: 0.75, sz: 0.8 },
            false,
        );
        this.face = kit.canvas(128, 72, () => undefined);
        const fg = kit.geo(
            new THREE.SphereGeometry(
                0.172 * 1.0,
                20,
                12,
                Math.PI / 2 - Math.PI * 0.4,
                Math.PI * 0.8,
                Math.PI * 0.3,
                Math.PI * 0.45,
            ),
        );
        const fm = new THREE.Mesh(
            fg,
            kit.mat(
                new THREE.MeshToonMaterial({
                    map: this.face.texture,
                    transparent: true,
                    gradientMap: kit.gradient,
                    depthWrite: false,
                }),
            ),
        );
        fm.scale.set(1.1, 0.95, 1.0);
        fm.position.z = 0.005;
        fm.userData.pick = pickInfo;
        this.head.add(fm);
        this.drawFace('open');
        this.root.scale.setScalar(1.1);
        this.root.userData.pick = pickInfo;

        this.nodeId = 'sanh.sofa';
        this.pos.copy(nav.pos(this.nodeId));
        this.pos.y += 0.1;
        this.visualY = this.pos.y;
        this.shadow = new THREE.Mesh(S.plane(0.7, 0.7), shadowMat);
        this.shadow.rotation.x = -Math.PI / 2;
        this.shadow.raycast = () => undefined;
    }

    get shadowMesh() {
        return this.shadow;
    }

    private drawFace(state: 'open' | 'closed' | 'happy') {
        if (state === this.faceState) {
            return;
        }
        this.faceState = state;
        this.face.redraw((g, w, h) => {
            const ey = h * 0.5;
            g.strokeStyle = '#3a2c55';
            g.fillStyle = '#3a2c55';
            g.lineCap = 'round';
            g.lineWidth = 3.5;
            for (const sx of [-1, 1]) {
                const x = w / 2 + sx * 20;
                g.beginPath();
                if (state === 'closed') {
                    g.arc(x, ey - 3, 7, 0.15 * Math.PI, 0.85 * Math.PI);
                    g.stroke();
                } else if (state === 'happy') {
                    g.moveTo(x - 7, ey + 2);
                    g.quadraticCurveTo(x, ey - 8, x + 7, ey + 2);
                    g.stroke();
                } else {
                    g.ellipse(x, ey, 5.5, 8, 0, 0, Math.PI * 2);
                    g.fill();
                    g.fillStyle = '#fff';
                    g.beginPath();
                    g.arc(x + 2, ey - 3, 2.2, 0, Math.PI * 2);
                    g.fill();
                    g.fillStyle = '#3a2c55';
                }
            }
            g.fillStyle = '#ff7f9f';
            g.beginPath();
            g.moveTo(w / 2 - 4, ey + 9);
            g.lineTo(w / 2 + 4, ey + 9);
            g.lineTo(w / 2, ey + 13);
            g.closePath();
            g.fill();
            g.lineWidth = 2.5;
            g.beginPath();
            g.moveTo(w / 2, ey + 13);
            g.quadraticCurveTo(w / 2 - 4, ey + 19, w / 2 - 8, ey + 15);
            g.moveTo(w / 2, ey + 13);
            g.quadraticCurveTo(w / 2 + 4, ey + 19, w / 2 + 8, ey + 15);
            g.stroke();
            g.strokeStyle = 'rgba(58,44,85,0.55)';
            g.lineWidth = 1.6;
            for (const sx of [-1, 1]) {
                for (const dy of [-2, 3]) {
                    g.beginPath();
                    g.moveTo(w / 2 + sx * 12, ey + 12 + dy * 0.6);
                    g.lineTo(w / 2 + sx * 34, ey + 9 + dy * 1.6);
                    g.stroke();
                }
            }
            g.fillStyle = 'rgba(255,128,150,0.4)';
            for (const sx of [-1, 1]) {
                g.beginPath();
                g.ellipse(w / 2 + sx * 30, ey + 8, 6, 3.5, 0, 0, Math.PI * 2);
                g.fill();
            }
        });
    }

    say(text: string, d = 2.2, prio: Prio = 'chat') {
        if (this.speech && !this.speech.allow('meo', text, prio)) {
            return;
        }
        this.sayText = text;
        this.sayUntil = this.now() + Math.min(5, Math.max(3, d));
    }

    bubble() {
        return this.sayText && this.now() < this.sayUntil ? this.sayText : null;
    }

    bubbleLeft() {
        return this.sayText ? this.sayUntil - this.now() : 99;
    }

    anchor(out: THREE.Vector3) {
        return this.head
            .getWorldPosition(out)
            .add(new THREE.Vector3(0, 0.45, 0));
    }

    setHighlight(on: boolean) {
        this.outline.color.setHex(on ? 0xffc93c : C.ink);
        this.outline.userData.width.value = on ? 0.03 : 0.012;
    }

    /** Bấm vào mèo. */
    poke(line: string) {
        this.say(line);
        this.fx.hearts(
            this.anchor(new THREE.Vector3()).add(new THREE.Vector3(0, -0.2, 0)),
            4,
        );
        this.hopT = 0.5;
    }

    /** Đang được ai bế (ngồi trên vai). */
    rider: Actor | null = null;
    private happyUntil = 0;
    private eatUntil = 0;
    private swatT = 0;

    /** Kid bế mèo lên vai. */
    ride(a: Actor) {
        this.rider = a;
        this.task = null;
        this.tasks = [];
        this.onDesk = null;
        this.happyUntil = this.now() + 3;
    }

    /** Thả mèo xuống trước mặt người bế. */
    drop() {
        const a = this.rider;
        if (!a) {
            return;
        }
        this.rider = null;
        this.pos.set(
            a.pos.x + Math.sin(a.rot) * 0.55,
            a.pos.y,
            a.pos.z + Math.cos(a.rot) * 0.55,
        );
        this.visualY = this.pos.y;
        this.nodeId = this.nav.nearest(this.pos);
        this.tasks = [{ kind: 'sit', d: 2.5 }];
        this.hopT = 0.5;
        this.fx.puff(this.pos);
    }

    /** Được vuốt ve: ngồi yên, nheo mắt, gừ gừ, tim bay. */
    petted(by: THREE.Vector3, d = 4) {
        if (this.rider) {
            this.happyUntil = this.now() + d;
            this.fx.hearts(this.anchor(new THREE.Vector3()), 3);

            return;
        }
        this.task = null;
        this.onDesk = null;
        this.tasks = [{ kind: 'sit', d }];
        this.targetRot = Math.atan2(by.x - this.pos.x, by.z - this.pos.z);
        this.happyUntil = this.now() + d;
        this.heartAt = 0;
    }

    /** Ăn bát cá trước mặt. */
    eat(d = 5) {
        this.task = null;
        this.onDesk = null;
        this.tasks = [{ kind: 'sit', d }];
        this.eatUntil = this.now() + d;
    }

    /** Bị trêu: tát một phát rồi lùi lại. */
    swat(at: THREE.Vector3) {
        if (this.rider) {
            this.drop();
        }
        this.task = null;
        this.tasks = [{ kind: 'sit', d: 1.6 }];
        this.targetRot = Math.atan2(at.x - this.pos.x, at.z - this.pos.z);
        this.swatT = 0.6;
        this.hopT = 0.5;
    }

    snapshot() {
        return {
            x: +this.pos.x.toFixed(3),
            y: +this.pos.y.toFixed(3),
            z: +this.pos.z.toFixed(3),
            rot: +this.rot.toFixed(3),
            riding: !!this.rider,
        };
    }

    restore(s: ReturnType<Cat['snapshot']>) {
        this.pos.set(s.x, s.y, s.z);
        this.visualY = s.y;
        this.rot = this.targetRot = s.rot;
        this.nodeId = this.nav.nearest(this.pos);
        this.task = null;
        this.tasks = [{ kind: 'sit', d: 3 }];
        this.onDesk = null;
    }

    /** Gọi mèo tới một chỗ (vd. tụ họp ở Sảnh) rồi ngồi đó một lúc. */
    visit(node: string, d: number) {
        if (!this.motion) {
            return;
        }
        this.onDesk = null;
        this.task = null;
        this.nodeId = this.nav.nearest(this.pos);
        this.tasks = [
            { kind: 'path', to: node, run: true },
            { kind: 'sit', d },
        ];
    }

    /** (Gỡ lỗi) đi tìm ngay người được chọn để làm nũng. */
    seekNow(a: Actor) {
        if (!this.motion) {
            return;
        }
        this.favourite = a;
        this.favUntil = this.now() + 240;
        this.onDesk = null;
        this.task = null;
        this.nodeId = this.nav.nearest(this.pos);
        this.tasks = [];
        this.seek(a);
    }

    // ----------------------------------------------------------------- suy nghĩ
    private think() {
        const now = this.now();
        if (!this.favourite || now > this.favUntil) {
            const pool = this.actors.filter((a) => a.key !== 'buuta');
            this.favourite = pick(pool);
            this.favUntil = now + rand(120, 240);
        }
        const r = Math.random();
        if (r < 0.42 && this.favourite) {
            this.seek(this.favourite);
        } else if (r < 0.62) {
            const spot = pick(SUNNY);
            this.tasks.push(
                { kind: 'path', to: spot },
                { kind: 'curl', d: rand(18, 32) },
            );
        } else if (r < 0.78) {
            const bf = pick(this.butterflies);
            const near = this.nav.nearest(bf.pos, (id) =>
                GARDEN_NODES.includes(id),
            );
            this.tasks.push(
                { kind: 'path', to: near, run: true },
                { kind: 'chase', d: rand(7, 11), bf },
                { kind: 'sit', d: 2.5 },
            );
        } else if (r < 0.92) {
            const ids = [...this.nav.nodes.keys()].filter(
                (id) => !id.endsWith('.seat') && !id.startsWith('st.'),
            );
            this.tasks.push(
                { kind: 'path', to: pick(ids) },
                { kind: 'sit', d: rand(3, 6) },
            );
        } else {
            this.tasks.push({ kind: 'sit', d: rand(4, 7) });
        }
    }

    private seek(a: Actor) {
        const desk = this.deskTops[a.key];
        if (desk && a.seated && a.atHome) {
            const floorY = desk.y - 0.73;
            const near = this.nav.nearest(
                new THREE.Vector3(desk.x, floorY, desk.z + 0.6),
                (id) =>
                    !id.endsWith('.seat') &&
                    Math.abs(this.nav.pos(id).y - floorY) < 0.2 &&
                    !id.startsWith('g.'),
            );
            this.tasks.push(
                { kind: 'path', to: near },
                {
                    kind: 'jump',
                    dest: desk.clone().add(new THREE.Vector3(0, 0.0, 0)),
                },
                { kind: 'do', fn: () => (this.onDesk = a) },
                { kind: 'curl', d: rand(22, 38), actor: a },
                { kind: 'do', fn: () => (this.onDesk = null) },
                { kind: 'jump', dest: this.nav.pos(near).clone() },
            );
        } else {
            this.tasks.push(
                { kind: 'path', to: a.nodeId },
                { kind: 'rub', d: 4.5, actor: a },
            );
        }
    }

    private startTask(t: Task) {
        this.task = t;
        this.taskT = 0;
        if (t.kind === 'path' && t.to) {
            this.pathIds = this.nav.path(this.nodeId, t.to);
            if (
                this.pathIds.length &&
                this.nav.pos(this.pathIds[0]).distanceTo(this.pos) < 0.05
            ) {
                this.pathIds.shift();
            }
            this.path = this.pathIds.map((id) => this.nav.pos(id));
            this.pathI = 0;
            if (!this.path.length) {
                this.nodeId = t.to;
            }
        }
        if (t.kind === 'jump') {
            t.from = this.pos.clone();
        }
        if (t.kind === 'do') {
            t.fn?.();
            this.task = null;
        }
    }

    update(dt: number) {
        const now = this.now();
        this.t += dt;
        if (this.rider) {
            this.mode = 'sit';
        } else if (!this.motion) {
            this.mode = 'curl';
        } else {
            if (!this.task) {
                if (!this.tasks.length) {
                    this.think();
                }
                const next = this.tasks.shift();
                if (next) {
                    this.startTask(next);
                }
            }
            this.runTask(dt, now);
        }
        this.rot = dampAngle(this.rot, this.targetRot, 8, dt);
        this.root.rotation.y = this.rot;
        this.visualY =
            this.mode === 'jump'
                ? this.pos.y
                : damp(this.visualY, this.pos.y, 14, dt);
        let hop = 0;
        if (this.hopT > 0) {
            this.hopT -= dt;
            hop = Math.sin((this.hopT / 0.5) * Math.PI) * 0.25;
        }
        if (this.rider) {
            // ngồi trên vai người bế
            const r = this.rider;
            this.rider.ch.head.getWorldPosition(this.pos);
            // vai phải của người bế (nhìn từ sau lưng), hơi lùi ra sau
            const side = 0.5;
            this.pos.y -= 0.18;
            this.pos.x += -Math.cos(r.rot) * side - Math.sin(r.rot) * 0.08;
            this.pos.z += Math.sin(r.rot) * side - Math.cos(r.rot) * 0.08;
            this.visualY = this.pos.y;
            this.rot = this.targetRot = r.rot;
            this.root.rotation.y = this.rot;
        }
        this.shadow.visible = !this.rider;
        if (now < this.happyUntil && now > this.heartAt) {
            this.heartAt = now + 1.4;
            this.fx.hearts(this.anchor(new THREE.Vector3()), 1);
        }
        if (this.swatT > 0) {
            this.swatT -= dt;
        }
        this.root.position.set(this.pos.x, this.visualY + hop, this.pos.z);
        this.shadow.position.set(
            this.pos.x,
            (this.mode === 'jump' ? this.shadowY : this.visualY) + 0.02,
            this.pos.z,
        );
        this.pose(dt);
    }

    private shadowY = 0;

    private runTask(dt: number, now: number) {
        const t = this.task;
        if (!t) {
            this.mode = 'idle';

            return;
        }
        this.taskT += dt;
        switch (t.kind) {
            case 'path': {
                this.mode = 'walk';
                if (this.follow(dt, t.run ? 2.4 : 1.4)) {
                    this.task = null;
                }
                break;
            }
            case 'curl':
                this.mode = 'curl';
                if (t.actor && now > this.heartAt) {
                    this.heartAt = now + rand(3, 5);
                    this.fx.hearts(this.anchor(new THREE.Vector3()), 2);
                }
                if (t.actor && this.onDesk && !t.actor.seated) {
                    this.task = null; // người kia đứng dậy → mèo cũng dậy
                }
                if (this.taskT > (t.d ?? 20)) {
                    this.task = null;
                }
                break;
            case 'sit':
                this.mode = 'sit';
                if (this.taskT > (t.d ?? 3)) {
                    this.task = null;
                }
                break;
            case 'rub': {
                const a = t.actor!;
                const dx = this.pos.x - a.pos.x;
                const dz = this.pos.z - a.pos.z;
                const d = Math.hypot(dx, dz) || 1;
                if (d > 0.5 && this.taskT < 3) {
                    this.mode = 'walk';
                    const k = Math.min(d - 0.42, dt * 1.2);
                    this.pos.x -= (dx / d) * k;
                    this.pos.z -= (dz / d) * k;
                    this.targetRot = Math.atan2(-dx, -dz);
                } else {
                    this.mode = 'rub';
                    this.targetRot = Math.atan2(-dz, dx); // đứng ngang, cọ sườn vào chân
                    if (now > this.heartAt) {
                        this.heartAt = now + 1.3;
                        this.fx.hearts(this.anchor(new THREE.Vector3()), 2);
                        a.setExpr('love', 2);
                    }
                }
                if (this.taskT > (t.d ?? 4) + 1.5) {
                    this.task = null;
                    this.nodeId = this.nav.nearest(this.pos);
                    this.path = [];
                    // trở về điểm gần nhất cho lần đi sau
                    this.tasks.unshift({ kind: 'path', to: this.nodeId });
                }
                break;
            }
            case 'jump': {
                this.mode = 'jump';
                const k = clamp(this.taskT / 0.55, 0, 1);
                const from = t.from!;
                const to = t.dest!;
                this.pos.lerpVectors(from, to, k);
                this.pos.y += Math.sin(k * Math.PI) * 0.6;
                this.shadowY = from.y + (to.y - from.y) * k;
                this.targetRot = Math.atan2(to.x - from.x, to.z - from.z);
                if (k >= 1) {
                    this.pos.copy(to);
                    this.task = null;
                    this.fx.puff(to);
                }
                break;
            }
            case 'chase': {
                const bf = t.bf!;
                this.mode = 'chase';
                const tx = clamp(bf.pos.x, -15, 15);
                const tz = clamp(bf.pos.z, 4, 12.5);
                const dx = tx - this.pos.x;
                const dz = tz - this.pos.z;
                const d = Math.hypot(dx, dz);
                if (d > 0.5) {
                    const k = Math.min(d, dt * 2.3);
                    this.pos.x += (dx / d) * k;
                    this.pos.z += (dz / d) * k;
                    this.targetRot = Math.atan2(dx, dz);
                }
                this.pos.y = Math.abs(Math.sin(this.t * 6)) * 0.12;
                if (this.taskT > (t.d ?? 8)) {
                    this.pos.y = 0;
                    this.task = null;
                    this.nodeId = this.nav.nearest(this.pos, (id) =>
                        GARDEN_NODES.includes(id),
                    );
                    this.tasks.unshift({ kind: 'path', to: this.nodeId });
                    this.say('Meo! (hụt rồi…)', 2);
                }
                break;
            }
            default:
                this.task = null;
        }
    }

    private follow(dt: number, speed: number): boolean {
        if (this.pathI >= this.path.length) {
            return true;
        }
        const target = this.path[this.pathI];
        const dx = target.x - this.pos.x;
        const dz = target.z - this.pos.z;
        const d = Math.hypot(dx, dz);
        if (d < 0.04) {
            this.pos.copy(target);
            this.nodeId = this.pathIds[this.pathI];
            this.pathI++;

            return this.pathI >= this.path.length;
        }
        const k = Math.min(d, speed * dt);
        const fromY = this.pos.y;
        this.pos.x += (dx / d) * k;
        this.pos.z += (dz / d) * k;
        this.pos.y = fromY + (target.y - fromY) * (k / d);
        this.targetRot = Math.atan2(dx, dz);

        return false;
    }

    private pose(dt: number) {
        const m = this.mode;
        const t = this.t;
        const walking = m === 'walk' || m === 'chase';
        const f = m === 'chase' ? 14 : 10;
        this.legs.forEach((l, i) => {
            const ph = i === 0 || i === 3 ? 0 : Math.PI;
            const target = walking
                ? Math.sin(t * f + ph) * 0.7
                : m === 'curl'
                  ? i < 2
                      ? -1.3
                      : 1.3
                  : m === 'sit' && i >= 2
                    ? -1.2
                    : 0;
            l.rotation.x = damp(l.rotation.x, target, 14, dt);
            l.visible = m !== 'curl' || i < 2;
        });
        const bodyY =
            m === 'curl'
                ? -0.12
                : m === 'sit'
                  ? -0.02
                  : walking
                    ? Math.abs(Math.sin(t * f)) * 0.03
                    : 0;
        this.body.position.y = damp(this.body.position.y, bodyY, 10, dt);
        const pitch = m === 'sit' ? -0.45 : m === 'jump' ? -0.3 : 0;
        this.body.rotation.x = damp(this.body.rotation.x, pitch, 10, dt);
        this.body.rotation.z =
            m === 'rub'
                ? Math.sin(t * 5) * 0.12
                : damp(this.body.rotation.z, 0, 8, dt);
        this.body.scale.set(
            m === 'curl' ? 1.1 : 1,
            m === 'curl' ? 0.85 : 1 + Math.sin(t * 2) * 0.01,
            m === 'curl' ? 0.8 : 1,
        );
        // đầu
        const hx = m === 'curl' ? 0.5 : m === 'sit' ? 0.35 : 0;
        this.head.rotation.x = damp(this.head.rotation.x, hx, 8, dt);
        this.head.rotation.y =
            m === 'curl'
                ? 0.9
                : m === 'idle' || m === 'sit'
                  ? Math.sin(t * 0.7) * 0.4
                  : 0;
        this.head.position.y = damp(
            this.head.position.y,
            m === 'curl' ? 0.27 : 0.42,
            8,
            dt,
        );
        // đuôi
        this.tail.forEach((s, i) => {
            if (m === 'curl') {
                s.rotation.x = damp(s.rotation.x, i === 0 ? -1.4 : -0.3, 8, dt);
                s.rotation.z = damp(
                    s.rotation.z,
                    0.5 + Math.sin(t * 1.5) * 0.1,
                    8,
                    dt,
                );
            } else {
                const up = m === 'rub' || m === 'walk' ? -0.2 : 0.4;
                s.rotation.x = damp(
                    s.rotation.x,
                    i === 0 ? up - 0.4 : 0.15,
                    8,
                    dt,
                );
                s.rotation.z =
                    Math.sin(t * (m === 'rub' ? 6 : 2.5) - i * 0.7) *
                    (0.25 + i * 0.08);
            }
        });
        const now = this.now();
        if (this.swatT > 0 && this.legs[0]) {
            this.legs[0].rotation.x = -1.6 + Math.sin(this.swatT * 30) * 0.6;
        }
        if (now < this.eatUntil) {
            this.head.rotation.x = 0.75 + Math.abs(Math.sin(t * 7)) * 0.15;
        }
        this.drawFace(
            m === 'curl'
                ? 'closed'
                : m === 'rub' ||
                    this.hopT > 0 ||
                    now < this.happyUntil ||
                    now < this.eatUntil
                  ? 'happy'
                  : 'open',
        );
    }
}

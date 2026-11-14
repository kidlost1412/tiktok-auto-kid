// "Gọi về gấp": gọi một nhân viên chạy thục mạng tới chỗ Kid đứng, dừng trước mặt, vẫy tay và báo cáo.
// Nút "📣 Gọi" + danh sách chữ (phím G) trong cảnh; tự báo cáo khi số việc chờ của một vai tăng.
import * as THREE from 'three';

import { DICH, type NhaData } from '@/components/fork/nha/types';
import type { Actor, Step } from '@/components/fork/nha3d/actor';
import type { CamRig } from '@/components/fork/nha3d/camrig';
import type { Owl } from '@/components/fork/nha3d/cast';
import type { Cat } from '@/components/fork/nha3d/cat';
import type { Director } from '@/components/fork/nha3d/director';
import type { NavGraph } from '@/components/fork/nha3d/nav';
import {
    AGENT_R,
    levelOf,
    type NavGrid,
} from '@/components/fork/nha3d/navgrid';

/** Các vai có nhân vật, theo thứ tự gốc của danh sách. */
const ROSTER = [
    'buuta',
    'chuquay',
    'cu',
    'thukho',
    'thodung',
    'giamkhao',
    'daodien',
    'bienkich',
    'thuam',
    'meo',
];
const ACTOR_KEY: Record<string, string> = { daodien: 'daodienA' };
const HELLO = 'Dạ, anh gọi em ạ?';
/** Khoảng đứng trước mặt Kid (m). */
const STOP_D = 1.3;
const WAIT_S = 25;
/** Góc thử quanh hướng camera (rad): trước mặt, hai bên, rồi sau lưng. */
const ANGLES = [0, 0.6, -0.6, 1.2, -1.2, 1.9, -1.9, 2.5, -2.5, Math.PI];
const DISTS = [1.3, 1.0, 1.6, 1.8];
const OPEN_S = 90;
const AUTO_GAP_S = 60;
const STATE_CLS: Record<string, string> = {
    working: 'n3-st-working',
    idle: 'n3-st-idle',
    sleep: 'n3-st-sleep',
};

interface Row {
    el: HTMLButtonElement;
    dot: HTMLSpanElement;
    badge: HTMLSpanElement;
}

interface Cur {
    vai: string;
    phase: 'run' | 'wait' | 'open';
    t0: number;
    report: string;
    sayAt: number;
    chkAt: number;
    retry: number;
    kx: number;
    kz: number;
}

export interface CallDeps {
    host: HTMLElement;
    scene: THREE.Scene;
    A: Record<string, Actor>;
    owl: Owl;
    cat: Cat;
    nav: NavGraph;
    rig: CamRig;
    kidActor: Actor;
    director: Director;
    camera: THREE.Camera;
    getGrid: () => NavGrid | undefined;
    now: () => number;
    motion: boolean;
}

const normVai = (v: string) => (v === 'bang' ? 'thodung' : v);

export class Caller {
    private btn: HTMLButtonElement;
    private panel: HTMLDivElement;
    private rows = new Map<string, Row>();
    private isOpen = false;
    private data: NhaData | null = null;
    private prev = new Map<string, number>();
    private seen = false;
    private lastAuto = new Map<string, number>();
    private queue: string[] = [];
    private cur: Cur | null = null;
    private owlBack = false;
    private ring: THREE.Mesh;
    private disc: THREE.Mesh;
    private dest = new THREE.Vector3();
    private owlHomeX: number;
    private owlHomeZ: number;
    private owlHomeY: number;
    private flapAt = 0;
    /** Camera Toàn cảnh lướt theo: 0 không, 1 đang lướt, 2 người dùng đã giành lại. */
    private glide = 0;
    private readonly mid = new THREE.Vector3();
    private readonly kidPosFn = () => this.d.kidActor.pos;
    private readonly onArrive = () => this.arrive();

    constructor(private d: CallDeps) {
        this.btn = document.createElement('button');
        this.btn.type = 'button';
        this.btn.className = 'n3-all n3-call';
        this.btn.innerHTML = '📣 Gọi <kbd>G</kbd>';
        this.btn.title = 'Gọi một nhân viên chạy về chỗ anh';
        this.btn.addEventListener('click', () => this.toggle());
        this.panel = document.createElement('div');
        this.panel.className = 'n3-calls';
        this.panel.style.display = 'none';
        const h = document.createElement('div');
        h.className = 'n3-calls-h';
        h.textContent = 'Gọi về gấp';
        this.panel.appendChild(h);
        for (const vai of ROSTER) {
            const el = document.createElement('button');
            el.type = 'button';
            el.className = 'n3-calls-r';
            const dot = document.createElement('span');
            dot.className = 'n3-calls-dot';
            const name = document.createElement('span');
            name.className = 'n3-calls-n';
            name.textContent = DICH[vai]?.ten ?? vai;
            const badge = document.createElement('span');
            badge.className = 'n3-calls-b';
            badge.style.display = 'none';
            el.append(dot, name, badge);
            el.addEventListener('click', () => {
                this.close();
                this.call(vai);
            });
            this.panel.appendChild(el);
            this.rows.set(vai, { el, dot, badge });
        }
        d.host.append(this.btn, this.panel);

        const mat = (o: number) =>
            new THREE.MeshBasicMaterial({
                color: 0xffc93c,
                transparent: true,
                opacity: o,
                depthWrite: false,
                depthTest: false,
                side: THREE.DoubleSide,
            });
        this.ring = new THREE.Mesh(
            new THREE.RingGeometry(0.7, 0.98, 40),
            mat(0.9),
        );
        this.disc = new THREE.Mesh(
            new THREE.CircleGeometry(0.7, 40),
            mat(0.28),
        );
        for (const m of [this.ring, this.disc]) {
            m.rotation.x = -Math.PI / 2;
            m.renderOrder = 999;
            m.visible = false;
            m.frustumCulled = false;
            m.raycast = () => undefined;
            d.scene.add(m);
        }

        this.owlHomeX = d.owl.root.position.x;
        this.owlHomeZ = d.owl.root.position.z;
        this.owlHomeY = d.owl.yBase;
        this.refresh();
    }

    /** `vai` đang được gọi / đang chờ? */
    calling(vai: string) {
        return this.cur?.vai === normVai(vai);
    }

    get opened() {
        return this.isOpen;
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.isOpen = true;
            this.panel.style.display = 'flex';
            this.btn.classList.add('on');
            this.refresh();
        }
    }

    close() {
        this.isOpen = false;
        this.panel.style.display = 'none';
        this.btn.classList.remove('on');
    }

    /** Nhận dữ liệu mới: cập nhật danh sách và tự gọi vai có thêm việc. */
    setData(data: NhaData) {
        this.data = data;
        const viec = data.viec ?? {};
        const now = this.d.now();
        for (const vai of ROSTER) {
            const n = viec[vai]?.so ?? 0;
            if (
                this.seen &&
                n > (this.prev.get(vai) ?? 0) &&
                now - (this.lastAuto.get(vai) ?? -999) >= AUTO_GAP_S &&
                this.cur?.vai !== vai &&
                !this.queue.includes(vai)
            ) {
                this.lastAuto.set(vai, now);
                this.queue.push(vai);
            }
            this.prev.set(vai, n);
        }
        this.seen = true;
        this.refresh();
    }

    /** Danh sách: ai có việc lên đầu, mỗi dòng có chấm trạng thái và số việc. */
    private refresh() {
        const viec = this.data?.viec ?? {};
        const order = ROSTER.map((v, i) => ({
            v,
            i,
            n: viec[v]?.so ?? 0,
        })).sort((a, b) => b.n - a.n || a.i - b.i);
        let prev: Element | null = this.panel.firstElementChild;
        for (const o of order) {
            const r = this.rows.get(o.v)!;
            const st = this.data?.vai?.[o.v]?.state ?? 'idle';
            r.dot.className = `n3-calls-dot ${STATE_CLS[st] ?? ''}`;
            if (o.n > 0) {
                r.badge.textContent = o.n > 99 ? '99+' : String(o.n);
                r.badge.style.display = 'inline-block';
            } else {
                r.badge.style.display = 'none';
            }
            if (r.el.previousElementSibling !== prev) {
                prev!.after(r.el);
            }
            prev = r.el;
        }
    }

    // ---------------------------------------------------------------- gọi
    private reportOf(vai: string): string {
        return (
            this.data?.viec?.[vai]?.tom_tat ||
            this.data?.vai?.[vai]?.bubble ||
            HELLO
        );
    }

    /** Gọi `vai` chạy về chỗ Kid (chen ngang việc đang làm). */
    call(vai: string) {
        vai = normVai(vai);
        if (!ROSTER.includes(vai)) {
            return;
        }
        this.queue = this.queue.filter((v) => v !== vai);
        if (this.cur) {
            this.end();
        }
        this.start(vai);
    }

    private actorOf(vai: string): Actor | null {
        return this.d.A[ACTOR_KEY[vai] ?? vai] ?? null;
    }

    private take(a: Actor): boolean {
        const dir = this.d.director;
        if (dir.onDuty(a)) {
            const st = dir.release(a);
            if (st.k === 'do') {
                st.fn();
            }
        }
        if (!dir.grab(a)) {
            return false;
        }
        a.leisure = false;

        return true;
    }

    private start(vai: string) {
        const now = this.d.now();
        const kid = this.d.kidActor.pos;
        const c: Cur = {
            vai,
            phase: 'run',
            t0: now,
            report: this.reportOf(vai),
            sayAt: 0,
            chkAt: now + 0.7,
            retry: 0,
            kx: kid.x,
            kz: kid.z,
        };
        if (vai === 'cu') {
            this.cur = c;
            this.owlBack = false;
            this.pickSpot(
                null,
                this.d.owl.root.position.x,
                this.d.owl.root.position.z,
            );
            this.ring.visible = this.disc.visible = false;
            this.glideStart();

            return;
        }
        if (vai === 'meo') {
            this.cur = c;
            this.ring.visible = this.disc.visible = false;
            this.catGo();
            this.glideStart();

            return;
        }
        const a = this.actorOf(vai);
        if (!a || !this.take(a)) {
            return;
        }
        this.cur = c;
        this.go(a);
        this.glideStart();
    }

    /** Kid thấy được điểm (x, z) (không tường chắn) và điểm đứng được? */
    private seesKid(l: number, x: number, z: number, r: number): boolean {
        const g = this.d.getGrid();
        if (!g) {
            return true;
        }
        const k = this.d.kidActor.pos;

        return g.free(l, x, z, r) && g.los(l, k.x, k.z, x, z, 0.1);
    }

    /**
     * Chọn chỗ đứng trước mặt Kid: đi được, cùng phòng và nhìn thấy Kid, không ai khác đứng đó.
     * Ưu tiên phía camera (sân/hành lang trước mặt), rồi hai bên, rồi sau lưng. Ghi vào `this.dest`.
     */
    private pickSpot(self: Actor | null, fromX: number, fromZ: number) {
        const kid = this.d.kidActor.pos;
        const l = levelOf(kid.y);
        const g = this.d.getGrid();
        const cam = this.d.camera.position;
        let bx = cam.x - kid.x;
        let bz = cam.z - kid.z;
        if (Math.hypot(bx, bz) < 0.01) {
            bx = fromX - kid.x;
            bz = fromZ - kid.z;
        }
        const base = Math.atan2(bz, bx);
        this.dest.set(kid.x, kid.y, kid.z);
        if (!g) {
            this.dest.set(
                kid.x + Math.cos(base) * STOP_D,
                kid.y,
                kid.z + Math.sin(base) * STOP_D,
            );

            return;
        }
        const others = Object.values(this.d.A);
        for (const da of ANGLES) {
            for (const r of DISTS) {
                const x = kid.x + Math.cos(base + da) * r;
                const z = kid.z + Math.sin(base + da) * r;
                if (!this.seesKid(l, x, z, AGENT_R + 0.05)) {
                    continue;
                }
                let taken = false;
                for (const o of others) {
                    if (
                        o !== self &&
                        Math.abs(o.pos.y - kid.y) < 0.8 &&
                        Math.hypot(o.pos.x - x, o.pos.z - z) < 0.75
                    ) {
                        taken = true;
                        break;
                    }
                }
                if (!taken) {
                    this.dest.set(x, kid.y, z);

                    return;
                }
            }
        }
        const f = g.nearestFree(l, kid.x, kid.z + 1, AGENT_R, 2.5);
        this.dest.set(f?.x ?? kid.x, kid.y, f?.z ?? kid.z + 1);
    }

    /** Chạy tới chỗ đứng trước mặt Kid. */
    private go(a: Actor) {
        const kid = this.d.kidActor.pos;
        if (this.cur) {
            this.cur.kx = kid.x;
            this.cur.kz = kid.z;
        }
        a.interrupt();
        const l = levelOf(kid.y);
        if (
            Math.hypot(a.pos.x - kid.x, a.pos.z - kid.z) < 1.8 &&
            Math.abs(a.pos.y - kid.y) < 0.8 &&
            this.seesKid(l, a.pos.x, a.pos.z, 0.2)
        ) {
            this.arrive();

            return;
        }
        this.pickSpot(a, a.pos.x, a.pos.z);
        const steps: Step[] = [
            { k: 'goto', p: this.dest, gait: 'sprint' },
            { k: 'do', fn: this.onArrive },
        ];
        a.push(...steps);
    }

    /** Nút nav gần chỗ đã chọn mà Kid nhìn thấy (mèo đi theo đồ thị nav, không xuyên tường). */
    private catGo() {
        const kid = this.d.kidActor.pos;
        const cat = this.d.cat;
        this.pickSpot(null, cat.pos.x, cat.pos.z);
        const l = levelOf(kid.y);
        let best = '';
        let bd = Infinity;
        for (const n of this.d.nav.nodes.values()) {
            if (
                n.id.endsWith('.seat') ||
                n.id.startsWith('st.') ||
                levelOf(n.p.y) !== l ||
                Math.abs(n.p.y - kid.y) > 0.6
            ) {
                continue;
            }
            const dd = Math.hypot(n.p.x - this.dest.x, n.p.z - this.dest.z);
            if (dd < bd && this.seesKid(l, n.p.x, n.p.z, 0.1)) {
                bd = dd;
                best = n.id;
            }
        }
        if (!best) {
            best = this.d.nav.nearest(this.dest);
        }
        if (this.cur) {
            this.cur.kx = kid.x;
            this.cur.kz = kid.z;
        }
        cat.callTo(best, kid);
    }

    /** Chủ thể đang được gọi (để camera bám theo, vòng sáng đặt dưới chân). */
    private subject(vai: string): THREE.Vector3 | null {
        if (vai === 'cu') {
            return this.d.owl.root.position;
        }
        if (vai === 'meo') {
            return this.d.cat.root.position;
        }

        return this.actorOf(vai)?.root.position ?? null;
    }

    /** Toàn cảnh: camera lướt theo nhân vật được gọi (chế độ Nhân vật giữ nguyên). */
    private glideStart() {
        const rig = this.d.rig;
        const p = this.cur ? this.subject(this.cur.vai) : null;
        if (rig.mode === 'overview' && p) {
            this.glide = 1;
            rig.glideFocus = p;
        } else {
            this.glide = 0;
        }
    }

    private glideTick(now: number) {
        const rig = this.d.rig;
        const c = this.cur;
        if (this.glide === 0) {
            return;
        }
        if (rig.mode !== 'overview' || !c) {
            this.glideStop();

            return;
        }
        if (rig.glideFocus === null) {
            this.glide = 2; // người dùng kéo/xoay/cuộn: thôi bám theo ngay

            return;
        }
        if (this.glide !== 1) {
            return;
        }
        const p = this.subject(c.vai);
        if (!p) {
            return;
        }
        if (c.phase === 'run') {
            rig.glideFocus = p;
        } else if (now - c.t0 < 3.5) {
            // tới nơi: khung cả hai (Kid + nhân vật)
            this.mid.lerpVectors(this.d.kidActor.pos, p, 0.5);
            rig.glideFocus = this.mid;
        } else {
            this.glideStop(); // trả quyền điều khiển
        }
    }

    private glideStop() {
        if (this.glide === 1) {
            this.d.rig.glideFocus = null;
        }
        this.glide = 0;
    }

    private arrive() {
        const c = this.cur;
        if (!c || c.phase !== 'run') {
            return;
        }
        const now = this.d.now();
        const kid = this.d.kidActor.pos;
        if (c.vai !== 'cu' && c.vai !== 'meo') {
            const a = this.actorOf(c.vai)!;
            const far =
                Math.hypot(a.pos.x - kid.x, a.pos.z - kid.z) > 2 ||
                Math.abs(a.pos.y - kid.y) > 0.8 ||
                !this.seesKid(levelOf(kid.y), a.pos.x, a.pos.z, 0.2);
            if (far && c.retry < 2) {
                c.retry++;
                c.t0 = now;
                this.go(a);

                return;
            }
        }
        c.phase = 'wait';
        c.t0 = now;
        c.sayAt = now + 9;
        this.ring.visible = this.disc.visible = true;
        if (c.vai === 'cu') {
            const o = this.d.owl;
            o.callText = c.report;
            o.callAlert = true;
            o.alertUntil = now + WAIT_S + 1;
            o.say(c.report, 5);
            o.hop();

            return;
        }
        if (c.vai === 'meo') {
            const m = this.d.cat;
            m.callText = c.report;
            m.callAlert = true;
            m.alertUntil = now + WAIT_S + 1;
            m.say(c.report, 5);

            return;
        }
        const a = this.actorOf(c.vai)!;
        a.callText = c.report;
        a.callAlert = true;
        a.interrupt();
        a.push(
            { k: 'face', at: this.kidPosFn },
            { k: 'anim', a: 'wave', d: 1.6, expr: 'happy' },
            { k: 'say', text: c.report, d: 5, prio: 'reply' },
        );
        a.alert(WAIT_S + 1);
    }

    /** Popup của `vai` vừa mở: nhân vật ở lại tới khi bàn đóng. */
    onOpened(vai: string) {
        vai = normVai(vai);
        const c = this.cur;
        if (!c) {
            return;
        }
        if (c.vai === vai && c.phase !== 'open') {
            c.phase = 'open';
            c.t0 = this.d.now();
            if (c.vai === 'cu') {
                this.d.owl.alertUntil = 0;
                this.d.owl.callAlert = false;
            } else if (c.vai === 'meo') {
                this.d.cat.alertUntil = 0;
                this.d.cat.callAlert = false;
            } else {
                const a = this.actorOf(c.vai);
                a?.alert(0);
                if (a) {
                    a.callAlert = false;
                }
            }
        } else if (c.vai !== vai && c.phase === 'open') {
            this.end();
        }
    }

    onClosed(vai: string) {
        if (this.cur?.vai === normVai(vai) && this.cur.phase === 'open') {
            this.end();
        }
    }

    /** Cho về làm việc tiếp và giải phóng nhân vật. */
    private end() {
        const c = this.cur;
        if (!c) {
            return;
        }
        this.cur = null;
        this.glideStop();
        this.ring.visible = this.disc.visible = false;
        if (c.vai === 'meo') {
            this.d.cat.callEnd();

            return;
        }
        if (c.vai === 'cu') {
            this.d.owl.alertUntil = 0;
            this.d.owl.callText = null;
            this.d.owl.callAlert = false;
            this.owlBack = true;

            return;
        }
        const a = this.actorOf(c.vai);
        if (!a) {
            return;
        }
        a.alert(0);
        a.callText = null;
        a.callAlert = false;
        a.interrupt();
        const st = this.d.director.release(a);
        if (st.k === 'do') {
            st.fn();
        }
        a.push({ k: 'stand' }, { k: 'home', gait: 'run' });
    }

    // ---------------------------------------------------------------- mỗi khung hình
    update(dt: number) {
        const now = this.d.now();
        const c = this.cur;
        if (c) {
            this.tick(c, dt, now);
        } else if (this.queue.length) {
            this.start(this.queue.shift()!);
        }
        if (this.owlBack && this.cur?.vai !== 'cu') {
            this.owlFly(dt, this.owlHomeX, this.owlHomeZ, this.owlHomeY, true);
        }
        this.glideTick(now);
        if (this.ring.visible && this.cur) {
            const p = this.subject(this.cur.vai)!;
            const y = this.cur.vai === 'cu' ? this.d.kidActor.pos.y : p.y;
            this.ring.position.set(p.x, y + 0.03, p.z);
            this.disc.position.set(p.x, y + 0.025, p.z);
            const k = Math.sin(now * 6);
            this.ring.scale.setScalar(1 + 0.1 * k);
            this.disc.scale.setScalar(1 + 0.1 * k);
            (this.ring.material as THREE.MeshBasicMaterial).opacity =
                0.7 + 0.2 * k;
        }
    }

    private tick(c: Cur, dt: number, now: number) {
        const kid = this.d.kidActor.pos;
        if (c.vai === 'cu') {
            this.tickOwl(c, dt, now);

            return;
        }
        if (c.vai === 'meo') {
            this.tickCat(c, now);

            return;
        }
        const a = this.actorOf(c.vai)!;
        if (c.phase === 'run') {
            if (now - c.t0 > 22) {
                // kẹt đường: coi như tới nơi
                a.interrupt();
                this.arrive();
            } else if (now > c.chkAt) {
                c.chkAt = now + 0.7;
                if (Math.hypot(kid.x - c.kx, kid.z - c.kz) > 1.8) {
                    this.go(a);
                }
            }

            return;
        }
        a.faceTo(kid);
        if (c.phase === 'wait') {
            if (now - c.t0 > WAIT_S) {
                this.end();

                return;
            }
            if (now > c.sayAt) {
                c.sayAt = now + 9;
                c.report = this.reportOf(c.vai);
                a.callText = c.report;
                a.say(c.report, 5, 'reply');
                a.act('wave', 1.2, 'happy');
            }
        } else if (now - c.t0 > OPEN_S) {
            this.end();
        }
    }

    private tickCat(c: Cur, now: number) {
        const kid = this.d.kidActor.pos;
        const cat = this.d.cat;
        if (c.phase === 'run') {
            if (cat.callWaiting || now - c.t0 > 22) {
                this.arrive();
            } else if (
                now > c.chkAt &&
                Math.hypot(kid.x - c.kx, kid.z - c.kz) > 1.8
            ) {
                c.chkAt = now + 0.7;
                this.catGo();
            }

            return;
        }
        if (c.phase === 'wait') {
            if (now - c.t0 > WAIT_S) {
                this.end();
            } else if (now > c.sayAt) {
                c.sayAt = now + 9;
                c.report = this.reportOf(c.vai);
                cat.callText = c.report;
                cat.say(c.report, 5);
            }
        } else if (now - c.t0 > OPEN_S) {
            this.end();
        }
    }

    private tickOwl(c: Cur, dt: number, now: number) {
        const o = this.d.owl.root.position;
        const kid = this.d.kidActor.pos;
        if (c.phase === 'run') {
            if (now > c.chkAt && Math.hypot(kid.x - c.kx, kid.z - c.kz) > 1.8) {
                c.chkAt = now + 0.7;
                c.kx = kid.x;
                c.kz = kid.z;
                this.pickSpot(null, o.x, o.z);
            }
            const reached = this.owlFly(
                dt,
                this.dest.x,
                this.dest.z,
                kid.y + 1.1,
                false,
            );
            if (reached || now - c.t0 > 12) {
                this.arrive();
            }

            return;
        }
        this.d.owl.root.rotation.y = Math.atan2(kid.x - o.x, kid.z - o.z);
        if (c.phase === 'wait') {
            if (now - c.t0 > WAIT_S) {
                this.end();
            } else if (now > c.sayAt) {
                c.sayAt = now + 9;
                c.report = this.reportOf(c.vai);
                this.d.owl.callText = c.report;
                this.d.owl.say(c.report, 5);
                this.d.owl.hop();
            }
        } else if (now - c.t0 > OPEN_S) {
            this.end();
        }
    }

    /** Cú bay về phía (x, z) ở độ cao y; trả về true khi tới nơi. */
    private owlFly(dt: number, x: number, z: number, y: number, home: boolean) {
        const owl = this.d.owl;
        const o = owl.root.position;
        if (!this.d.motion) {
            o.x = x;
            o.z = z;
            owl.yBase = y;
            if (home) {
                this.owlBack = false;
            }

            return true;
        }
        const dx = x - o.x;
        const dz = z - o.z;
        const d = Math.hypot(dx, dz);
        owl.yBase += (y - owl.yBase) * Math.min(1, dt * 4);
        if (d < 0.12) {
            if (home && Math.abs(owl.yBase - y) < 0.05) {
                owl.yBase = y;
                this.owlBack = false;
            }

            return !home || !this.owlBack;
        }
        const step = Math.min(d, 9 * dt);
        o.x += (dx / d) * step;
        o.z += (dz / d) * step;
        owl.root.rotation.y = Math.atan2(dx, dz);
        const now = this.d.now();
        if (now > this.flapAt) {
            this.flapAt = now + 0.9;
            owl.hop();
        }

        return !home && d - step < 0.12;
    }

    dispose() {
        this.btn.remove();
        this.panel.remove();
        this.rows.clear();
        this.queue.length = 0;
        this.cur = null;
        this.d.scene.remove(this.ring);
        this.d.scene.remove(this.disc);
        for (const m of [this.ring, this.disc]) {
            m.geometry.dispose();
            (m.material as THREE.Material).dispose();
        }
    }
}

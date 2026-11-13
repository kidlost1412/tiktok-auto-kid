// "Khu Tự Trị" thu nhỏ cho trang Xưởng Video: hai Đạo diễn ở một góc làm việc nhỏ — KHÔNG dựng lại cả ngôi nhà
// (không House/World/NavGrid/Director). Tái dùng khối hình-người của thế giới 3D (Kit/Shapes, Chibi, poseFor/applyPose,
// SPECS) để cùng một bộ nhân vật với trang Khu Tự Trị đầy đủ.
//
// Sống theo dữ liệu thật (`setState` nhận trạng thái Đạo diễn từ /nha/trang-thai):
//   working → ngồi vào ghế, gõ phím / ghi chép;  idle → đứng dậy, đi bộ thong thả quanh khu, thỉnh thoảng ngồi nghỉ;
//   sleep / down → gục xuống bàn ngủ.
// Tương tác thật: rê chuột sáng viền, bấm vào một người thì người đó quay ra vẫy tay và nói một câu (câu soạn sẵn,
// không gọi AI). Vẽ tối đa ~30 khung/giây, dừng hẳn khi tab ẩn hoặc khung khuất màn hình.
import * as THREE from 'three';

import { lineFor, noi } from '../nha/loi-thoai';
import type { VaiState } from '../nha/types';

import { SPECS } from './cast';
import {
    applyPose,
    Chibi,
    poseFor,
    restPose,
    type AnimName,
    type Expr,
    type Pose,
} from './chibi';
import { Kit, Shapes } from './util';

export interface MiniSceneOptions {
    host: HTMLElement;
    reduced: boolean;
    /** Tên chủ xưởng để nhân vật gọi khi chào. */
    sep?: string;
}

export type MiniMode = VaiState | 'down';

export interface MiniScene {
    /** Trạng thái thật của Đạo diễn; `bubble` = câu hub đang báo (nếu có) để một người nói ra. */
    setState(mode: MiniMode, bubble?: string | null): void;
    /** Tên chủ xưởng (đọc từ nhân vật của tôi) để chào cho đúng. */
    setSep(name: string): void;
    dispose(): void;
}

const SCALE = 1.15;
const WALK = 0.62; // m/giây — đi bộ, không chạy
const FRAME_MS = 1000 / 30;

type Doing = 'seat' | 'toSeat' | 'stand' | 'walk' | 'react';

interface Worker {
    who: 'daodienA' | 'daodienB';
    ch: Chibi;
    cur: Pose;
    tgt: Pose;
    seatX: number;
    /** Nửa khu được đi (để hai người không đâm vào nhau). */
    side: -1 | 1;
    doing: Doing;
    anim: AnimName;
    seated: boolean;
    t: number;
    animT: number;
    /** Hết giờ của việc hiện tại (giây, theo đồng hồ cảnh). */
    until: number;
    path: THREE.Vector3[];
    face: number; // hướng muốn quay tới (rad)
    expr: Expr;
    blinkAt: number;
    blinkEnd: number;
    talkUntil: number;
    after: Doing | null;
}

const SEAT_Z = 0.95;
const AISLE_Z = 1.35;

export const createMiniXuongScene = (o: MiniSceneOptions): MiniScene => {
    const host = o.host;
    const motion = !o.reduced;
    const kit = new Kit();
    const shapes = new Shapes(kit);

    const renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: 'low-power',
    });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.setAttribute('aria-hidden', 'true');
    Object.assign(renderer.domElement.style, {
        display: 'block',
        width: '100%',
        height: '100%',
        touchAction: 'manipulation',
    });
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    // Camera trước bàn, hơi cao: thấy mặt hai người khi ngồi và cả khoảng sàn phía sau khi họ đứng dậy đi lại.
    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 40);
    camera.position.set(0, 2.2, -4.2);
    camera.lookAt(0, 0.62, 1.0);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x6a52b8, 1.05));
    const sun = new THREE.DirectionalLight(0xffffff, 0.9);
    sun.position.set(2, 3.2, -1.5);
    scene.add(sun);

    // ---------------------------------------------------------------- sàn + bàn + màn hình + ghế + chậu cây
    // Một "hòn đảo" sàn bầu dục kiểu diorama: mặt sàn sáng + đế dày đậm hơn, nằm trọn trong khung hình.
    // Mặt lớn dùng hình có pháp tuyến phẳng (trụ, hộp thường): hộp bo góc kéo giãn sẽ đổ vệt bóng chéo trên mặt rộng.
    const floor = new THREE.Mesh(
        new THREE.CylinderGeometry(2.05, 2.05, 0.08, 56),
        kit.toon(0xefe9fd),
    );
    floor.position.set(0, -0.04, 1.0);
    floor.scale.z = 0.72;
    scene.add(floor);
    const base = new THREE.Mesh(
        new THREE.CylinderGeometry(2.05, 1.95, 0.26, 56),
        kit.toon(0xb7a6ee),
    );
    base.position.set(0, -0.21, 1.0);
    base.scale.z = 0.72;
    scene.add(base);

    const woodMat = kit.toon(0xd39c68);
    const deskTop = new THREE.Mesh(shapes.box(2.3, 0.1, 0.9), woodMat);
    deskTop.position.y = 0.42;
    scene.add(deskTop);
    const legMat = kit.toon(0xa8764d);
    for (const sx of [-1, 1]) {
        const leg = new THREE.Mesh(shapes.box(0.08, 0.42, 0.08), legMat);
        leg.position.set(sx * 1.0, 0.21, 0.35);
        scene.add(leg);
    }
    const screenMat = kit.toonOwn(0x2b2440, {
        emissive: 0x5a4fb8,
        emissiveIntensity: 0.6,
    });
    const standMat = kit.toon(0x4a3868);
    for (const sx of [-0.52, 0.52]) {
        const stand = new THREE.Mesh(shapes.box(0.04, 0.16, 0.04), standMat);
        stand.position.set(sx, 0.55, 0.1);
        scene.add(stand);
        const screen = new THREE.Mesh(
            shapes.rbox(0.42, 0.28, 0.02, 0.015),
            screenMat,
        );
        screen.position.set(sx, 0.72, 0.08);
        scene.add(screen);
    }
    const stoolMat = kit.toon(0x7a5fd0);
    for (const sx of [-0.55, 0.55]) {
        const stool = new THREE.Mesh(
            shapes.cyl(0.26, 0.24, 0.42, 16),
            stoolMat,
        );
        stool.position.set(sx, 0.21, SEAT_Z);
        scene.add(stool);
    }
    const potMat = kit.toon(0xc8805a);
    const leafMat = kit.toon(0x5bb37a);
    for (const [px, pz] of [
        [-1.62, 2.08],
        [1.62, 2.08],
    ]) {
        const pot = new THREE.Mesh(shapes.cyl(0.16, 0.13, 0.28, 12), potMat);
        pot.position.set(px, 0.14, pz);
        scene.add(pot);
        const leaf = new THREE.Mesh(
            new THREE.SphereGeometry(0.26, 12, 10),
            leafMat,
        );
        leaf.position.set(px, 0.48, pz);
        leaf.scale.set(1, 1.15, 1);
        scene.add(leaf);
    }

    // ---------------------------------------------------------------- hai Đạo diễn
    let clock = 0;
    const rnd = (a: number, b: number) => a + Math.random() * (b - a);

    const workers: Worker[] = (['daodienA', 'daodienB'] as const).map(
        (who, i) => {
            const seatX = i === 0 ? -0.55 : 0.55;
            const ch = new Chibi(kit, shapes, SPECS[who], SCALE);
            ch.root.position.set(seatX, 0, SEAT_Z);
            ch.root.rotation.y = Math.PI;
            ch.root.userData.worker = i;
            scene.add(ch.root);

            return {
                who,
                ch,
                cur: restPose(),
                tgt: restPose(),
                seatX,
                side: i === 0 ? -1 : 1,
                doing: 'seat',
                anim: i === 0 ? 'write' : 'type',
                seated: true,
                t: Math.random() * 5,
                animT: 0,
                until: rnd(6, 12),
                path: [],
                face: Math.PI,
                expr: 'focus',
                blinkAt: 2 + Math.random() * 3,
                blinkEnd: 0,
                talkUntil: 0,
                after: null,
            } satisfies Worker;
        },
    );

    let mode: MiniMode = 'working';
    const vars = { sep: o.sep ?? 'Kid', anh: 'anh', Anh: 'Anh' };

    // ---------------------------------------------------------------- bong bóng lời thoại (HTML, đặt theo đầu nhân vật)
    const bubbles = workers.map(() => {
        const el = document.createElement('div');
        el.className = 'mini-bubble';
        el.setAttribute('role', 'status');
        Object.assign(el.style, {
            position: 'absolute',
            left: '0',
            top: '0',
            maxWidth: '68%',
            padding: '5px 9px',
            borderRadius: '10px',
            background: 'var(--card, #fff)',
            color: 'var(--card-foreground, #1c1917)',
            border: '1px solid var(--border, rgba(0,0,0,.12))',
            boxShadow: '0 4px 14px rgba(0,0,0,.14)',
            fontSize: '11.5px',
            fontWeight: '500',
            lineHeight: '1.35',
            pointerEvents: 'none',
            opacity: '0',
            transform: 'translate(-50%, -100%) scale(.92)',
            transition: 'opacity .18s ease, transform .18s ease',
            whiteSpace: 'normal',
            zIndex: '2',
        });
        host.appendChild(el);

        return { el, until: 0 };
    });

    const say = (i: number, text: string, secs = 4.2) => {
        if (!text) {
            return;
        }
        const b = bubbles[i];
        b.el.textContent = text;
        b.until = clock + secs;
        workers[i].talkUntil = clock + Math.min(secs, 2.4);
        // người kia đang nói thì tắt bớt để không chồng hai bong bóng
        const other = bubbles[1 - i];
        if (other.until > clock) {
            other.until = clock + 0.4;
        }
    };

    const head = new THREE.Vector3();
    const placeBubbles = () => {
        bubbles.forEach((b, i) => {
            const on = b.until > clock;
            b.el.style.opacity = on ? '1' : '0';
            if (!on) {
                b.el.style.transform = 'translate(-50%, -100%) scale(.92)';

                return;
            }
            const w = workers[i];
            head.copy(w.ch.root.position);
            head.y += (w.seated ? 1.25 : 1.6) * SCALE;
            head.project(camera);
            const x = Math.min(0.86, Math.max(0.14, (head.x + 1) / 2)) * W;
            const y = Math.max(28, ((1 - head.y) / 2) * H);
            b.el.style.transform = `translate(${x}px, ${y}px) translate(-50%, -100%) scale(1)`;
        });
    };

    // ---------------------------------------------------------------- việc của từng người
    const sitDown = (w: Worker) => {
        // đi về lối sau ghế rồi vào ghế
        w.path = [
            new THREE.Vector3(w.seatX, 0, AISLE_Z),
            new THREE.Vector3(w.seatX, 0, SEAT_Z),
        ];
        w.doing = 'toSeat';
        w.seated = false;
        w.anim = 'walk';
    };

    const seatAnim = (): { anim: AnimName; expr: Expr } =>
        mode === 'working'
            ? { anim: Math.random() < 0.5 ? 'type' : 'write', expr: 'focus' }
            : mode === 'idle'
              ? { anim: 'sitIdle', expr: 'happy' }
              : { anim: 'sleep', expr: 'sleepy' };

    const settle = (w: Worker) => {
        const s = seatAnim();
        w.doing = 'seat';
        w.seated = true;
        w.anim = s.anim;
        w.expr = s.expr;
        w.face = Math.PI;
        w.ch.root.position.set(w.seatX, 0, SEAT_Z);
        w.until = clock + (mode === 'idle' ? rnd(5, 10) : rnd(8, 16));
    };

    const wander = (w: Worker) => {
        const from = w.ch.root.position.clone();
        const to = new THREE.Vector3(
            w.side * rnd(0.25, 1.35),
            0,
            rnd(1.45, 2.05),
        );
        w.path = [];
        if (w.seated || from.z < AISLE_Z - 0.05) {
            w.path.push(new THREE.Vector3(from.x, 0, AISLE_Z)); // lùi ra khỏi ghế trước
        }
        w.path.push(to);
        w.doing = 'walk';
        w.seated = false;
        w.anim = 'walk';
        w.expr = 'happy';
    };

    const idleStand = (w: Worker) => {
        w.doing = 'stand';
        w.seated = false;
        const r = Math.random();
        w.anim = r < 0.2 ? 'stretch' : r < 0.32 ? 'yawn' : 'idle';
        w.expr = w.anim === 'yawn' ? 'sleepy' : 'happy';
        w.face = Math.PI + rnd(-0.9, 0.9); // nhìn quanh
        w.until = clock + rnd(2.5, 5.5);
        if (Math.random() < 0.18) {
            say(
                workers.indexOf(w),
                lineFor(w.who, { situation: 'idle', vars }),
                3.6,
            );
        }
    };

    // Đổi trạng thái thật: người đang đi thì về ghế khi có việc / buồn ngủ; đang ngồi mà rảnh thì lần lượt đứng dậy.
    const apply = () => {
        workers.forEach((w, i) => {
            if (mode === 'idle') {
                if (w.doing === 'seat') {
                    w.until = clock + (i === 0 ? rnd(0.6, 2) : rnd(3, 6));
                    const s = seatAnim();
                    w.anim = s.anim;
                    w.expr = s.expr;
                }

                return;
            }
            if (w.doing === 'seat') {
                const s = seatAnim();
                w.anim = s.anim;
                w.expr = s.expr;
                w.until = clock + rnd(8, 16);
            } else if (w.doing !== 'toSeat') {
                sitDown(w);
            }
        });
    };

    const tick = (w: Worker, i: number, dt: number) => {
        const pos = w.ch.root.position;

        if (w.doing === 'walk' || w.doing === 'toSeat') {
            const next = w.path[0];
            if (!next) {
                if (w.doing === 'toSeat') {
                    settle(w);
                } else {
                    idleStand(w);
                }
            } else {
                const dx = next.x - pos.x;
                const dz = next.z - pos.z;
                const d = Math.hypot(dx, dz);
                const step = WALK * dt;
                if (d <= step) {
                    pos.set(next.x, 0, next.z);
                    w.path.shift();
                } else {
                    pos.x += (dx / d) * step;
                    pos.z += (dz / d) * step;
                    w.face = Math.atan2(dx, dz);
                }
            }
        } else if (w.doing === 'react') {
            if (clock > w.until) {
                const back = w.after ?? 'stand';
                w.after = null;
                if (back === 'seat') {
                    settle(w);
                } else {
                    idleStand(w);
                }
            }
        } else if (w.doing === 'stand') {
            if (clock > w.until) {
                if (mode === 'idle') {
                    if (Math.random() < 0.22) {
                        sitDown(w);
                    } else {
                        wander(w);
                    }
                } else {
                    sitDown(w);
                }
            }
        } else if (w.doing === 'seat' && mode === 'idle' && clock > w.until) {
            wander(w);
        } else if (
            w.doing === 'seat' &&
            mode === 'working' &&
            clock > w.until
        ) {
            // đổi qua lại gõ phím / ghi chép cho đỡ đơ
            w.anim = w.anim === 'type' ? 'write' : 'type';
            w.until = clock + rnd(8, 16);
        }

        // quay người mượt về hướng muốn nhìn
        let diff = w.face - w.ch.root.rotation.y;
        diff = Math.atan2(Math.sin(diff), Math.cos(diff));
        w.ch.root.rotation.y += diff * Math.min(1, dt * 7);

        w.t += dt;
        w.animT += dt;
        poseFor(w.anim, w.t, w.seated, w.tgt, w.animT);
        applyPose(w.ch, w.cur, w.tgt, dt);
        if (w.t > w.blinkAt) {
            w.blinkEnd = w.t + 0.13;
            w.blinkAt = w.t + 2.2 + Math.random() * 3.3;
        }
        const talking =
            w.talkUntil > clock ? (Math.sin(clock * 18) > 0 ? 1 : 0.5) : 0;
        w.ch.face.set(w.expr, w.t < w.blinkEnd && w.expr !== 'sleepy', talking);
        void i;
    };

    // ---------------------------------------------------------------- khung hình
    let W = 1;
    let H = 1;
    const resize = () => {
        W = Math.max(1, host.clientWidth);
        H = Math.max(1, host.clientHeight);
        renderer.setSize(W, H, false);
        camera.aspect = W / Math.max(1, H);
        camera.updateProjectionMatrix();
        if (!motion) {
            draw();
        }
    };

    let visible = true;
    const io = new IntersectionObserver(
        (en) => (visible = en[0]?.isIntersecting ?? true),
    );
    io.observe(host);

    const draw = () => {
        placeBubbles();
        renderer.render(scene, camera);
    };

    // ---------------------------------------------------------------- chuột: rê sáng viền, bấm để trò chuyện
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    let hover = -1;

    const pick = (ev: PointerEvent): number => {
        const r = renderer.domElement.getBoundingClientRect();
        ndc.set(
            ((ev.clientX - r.left) / r.width) * 2 - 1,
            -((ev.clientY - r.top) / r.height) * 2 + 1,
        );
        ray.setFromCamera(ndc, camera);
        const hits = ray.intersectObjects(
            workers.map((w) => w.ch.root),
            true,
        );
        for (const h of hits) {
            let ob: THREE.Object3D | null = h.object;
            while (ob && ob.userData.worker === undefined) {
                ob = ob.parent;
            }
            if (ob) {
                return ob.userData.worker as number;
            }
        }

        return -1;
    };

    const onMove = (ev: PointerEvent) => {
        const i = pick(ev);
        if (i === hover) {
            return;
        }
        if (hover >= 0) {
            workers[hover].ch.setHighlight(false);
        }
        hover = i;
        if (i >= 0) {
            workers[i].ch.setHighlight(true);
        }
        renderer.domElement.style.cursor = i >= 0 ? 'pointer' : '';
        if (!motion) {
            draw();
        }
    };

    const onLeave = () => {
        if (hover >= 0) {
            workers[hover].ch.setHighlight(false);
        }
        hover = -1;
        renderer.domElement.style.cursor = '';
        if (!motion) {
            draw();
        }
    };

    const onClick = (ev: PointerEvent) => {
        const i = pick(ev);
        if (i < 0) {
            return;
        }
        const w = workers[i];
        const wasSeated = w.doing === 'seat' && w.seated;
        let text: string;
        if (mode === 'sleep' || mode === 'down') {
            text =
                Math.random() < 0.5
                    ? 'Ơ… sếp gọi em à? 😪'
                    : 'Cho em ngủ năm phút nữa thôi…';
            w.anim = 'yawn';
            w.expr = 'sleepy';
        } else if (mode === 'working') {
            text =
                Math.random() < 0.55
                    ? noi('bi_dung_daodien')
                    : lineFor(w.who, { situation: 'chao_sep', vars });
            w.anim = 'wave';
            w.expr = 'surprise';
        } else {
            text =
                lineFor(w.who, {
                    situation: Math.random() < 0.5 ? 'chao_sep' : 'treu',
                    vars,
                }) || noi('daodien_chat');
            w.anim = Math.random() < 0.3 ? 'cheer' : 'wave';
            w.expr = 'joy';
        }
        w.path = [];
        w.after = wasSeated || w.doing === 'toSeat' ? 'seat' : 'stand';
        if (w.doing === 'toSeat') {
            w.ch.root.position.set(w.seatX, 0, SEAT_Z);
            w.seated = true;
        }
        w.doing = 'react';
        w.animT = 0;
        w.face = Math.PI; // quay ra phía người xem
        w.until = clock + 2.6;
        say(i, text);
        if (!motion) {
            poseFor(w.anim, 0.4, w.seated, w.tgt, 0.4);
            applyPose(w.ch, w.cur, w.tgt, 1);
            w.ch.root.rotation.y = Math.PI;
            draw();
            window.setTimeout(() => {
                bubbles[i].until = 0;
                draw();
            }, 4200);
        }
    };

    const el = renderer.domElement;
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    el.addEventListener('click', onClick as EventListener);

    // ---------------------------------------------------------------- vòng vẽ (~30 khung/giây)
    let raf = 0;
    let last = performance.now();
    let acc = 0;
    const frame = (ts: number) => {
        raf = requestAnimationFrame(frame);
        if (document.hidden || !visible) {
            last = ts;

            return;
        }
        acc += ts - last;
        last = ts;
        if (acc < FRAME_MS) {
            return;
        }
        const dt = Math.min(0.1, acc / 1000);
        acc = 0;
        clock += dt;
        workers.forEach((w, i) => tick(w, i, dt));
        draw();
    };

    const ro = new ResizeObserver(resize);
    ro.observe(host);
    resize();

    if (motion) {
        raf = requestAnimationFrame(frame);
    } else {
        for (const w of workers) {
            poseFor(w.anim, 0.5, true, w.tgt, 0.5);
            applyPose(w.ch, w.cur, w.tgt, 1);
            w.ch.face.set(w.expr, false, 0);
        }
        draw();
    }

    let lastBubble: string | null = null;

    return {
        setState(next, bubble) {
            const changed = next !== mode;
            mode = next;
            if (changed) {
                if (motion) {
                    apply();
                } else {
                    for (const w of workers) {
                        const s = seatAnim();
                        w.anim = s.anim;
                        w.expr = s.expr;
                        poseFor(w.anim, 0.5, true, w.tgt, 0.5);
                        applyPose(w.ch, w.cur, w.tgt, 1);
                        w.ch.face.set(w.expr, false, 0);
                    }
                    draw();
                }
            }
            if (bubble && bubble !== lastBubble) {
                say(0, bubble, 5);
                if (!motion) {
                    draw();
                }
            }
            lastBubble = bubble ?? null;
        },
        setSep(name) {
            vars.sep = name || 'Kid';
        },
        dispose() {
            cancelAnimationFrame(raf);
            ro.disconnect();
            io.disconnect();
            el.removeEventListener('pointermove', onMove);
            el.removeEventListener('pointerleave', onLeave);
            el.removeEventListener('click', onClick as EventListener);
            bubbles.forEach((b) => b.el.remove());
            scene.traverse((ob) => {
                const m = ob as THREE.Mesh;
                if (m.geometry) {
                    m.geometry.dispose();
                }
                const mat = m.material as
                    | THREE.Material
                    | THREE.Material[]
                    | undefined;
                (Array.isArray(mat) ? mat : mat ? [mat] : []).forEach((x) =>
                    x.dispose(),
                );
            });
            kit.dispose();
            scene.clear();
            renderer.dispose();
            renderer.forceContextLoss();
            el.remove();
        },
    };
};

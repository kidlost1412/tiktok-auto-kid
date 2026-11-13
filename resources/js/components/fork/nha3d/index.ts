// Điểm vào của thế giới 3D "Xưởng nhỏ" (tải lười: chỉ trang /nha mới kéo three.js về).
// Dựng renderer + camera phối cảnh (đi dạo cùng Kid hoặc toàn cảnh), ghép nhà/vườn/nhân vật/mèo, vòng lặp vẽ, chọn bằng chuột, dọn sạch khi rời trang.
import * as THREE from 'three';

import { noi } from '../nha/loi-thoai';
import { DICH, type NhaData } from '../nha/types';
import { Actor, blobShadow, type ActorCtx, type Talker } from './actor';
import { CamRig, type CamMode } from './camrig';
import { NAMES, Owl, SPECS } from './cast';
import { Cat } from './cat';
import { Director } from './director';
import { Effects } from './effects';
import { House, type Reel } from './house';
import { KidControl } from './kid';
import { buildNav, F1, HOMES, room, XL0, XR1, Z_FRONT } from './layout';
import { Overlay } from './overlay';
import { Speech } from './speech';
import { Kit, Shapes } from './util';
import { Wings } from './wings';
import { World } from './world';

export interface NhaWorldOptions {
    host: HTMLElement;
    reduced: boolean;
    hour?: number | null;
    debug?: boolean;
    onGo: (key: string) => void;
    onOpen: (url: string | null) => void;
    onFail: (err: unknown) => void;
}

export interface NhaWorld {
    update(data: NhaData): void;
    dispose(): void;
}

export const webglOk = (): boolean => {
    try {
        const c = document.createElement('canvas');
        const gl = c.getContext('webgl2') ?? c.getContext('webgl');
        const ok = !!gl;
        (gl as WebGLRenderingContext | null)
            ?.getExtension('WEBGL_lose_context')
            ?.loseContext();

        return ok;
    } catch {
        return false;
    }
};

type Hover =
    | { kind: 'role'; key: string; room?: boolean }
    | { kind: 'place'; key: string; name: string }
    | { kind: 'reel'; reel: Reel; obj: THREE.Object3D }
    | { kind: 'cat' }
    | null;

export const createNhaWorld = (o: NhaWorldOptions): NhaWorld => {
    const host = o.host;
    const motion = !o.reduced;
    const kit = new Kit();
    const shapes = new Shapes(kit);
    const clock = { t: 0 };
    const now = () => clock.t;

    // ---------------------------------------------------------------- renderer + camera
    const renderer = new THREE.WebGLRenderer({
        antialias: true,
        powerPreference: 'high-performance',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.setAttribute('aria-hidden', 'true');
    host.appendChild(renderer.domElement);

    const hint = document.createElement('div');
    hint.className = 'n3-hint';
    hint.textContent = window.matchMedia?.('(pointer: coarse)').matches
        ? 'Vuốt ngang để xoay · hai ngón để phóng to'
        : 'Kéo để xoay · cuộn để phóng to · bấm đúp để về';
    host.appendChild(hint);
    hint.style.transition = 'opacity .6s';

    const scene = new THREE.Scene();
    const rig = new CamRig(renderer.domElement, motion, []);
    const camera = rig.camera;
    const controls = rig.controls;
    controls.addEventListener('start', () => (hint.style.opacity = '0'));
    const coarse = window.matchMedia?.('(pointer: coarse)').matches ?? false;
    let W = 1;
    let H = 1;
    const resize = () => {
        W = Math.max(1, host.clientWidth);
        H = Math.max(1, host.clientHeight);
        renderer.setSize(W, H, false);
        rig.resize(W / H);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(host);
    // sương mỏng khi đi dạo cho có chiều sâu (màu theo bầu trời)
    const walkFog = new THREE.Fog(0xffffff, 26, 80);

    // ---------------------------------------------------------------- thế giới
    const world = new World(kit, shapes);
    scene.add(world.group);
    scene.background = world.skyTex.tex;
    const house = new House(kit, shapes);
    scene.add(house.group);
    rig.occluders = house.occluders;
    const fx = new Effects(kit, shapes);
    fx.enabled = motion;
    scene.add(fx.group);
    const wings = new Wings(house, fx);
    const nav = buildNav();
    const shadowMat = blobShadow(kit);
    const actorList: Actor[] = [];
    const ctx: ActorCtx = {
        nav,
        fx,
        kit,
        shapes,
        actors: actorList,
        now,
        motion,
    };
    const A: Record<string, Actor> = {};
    for (const key of Object.keys(HOMES)) {
        const a = new Actor(
            key,
            SPECS[key],
            HOMES[key],
            ctx,
            shadowMat,
            key === 'thuam'
                ? { work: 'cocky', idle: 'cocky' }
                : key === 'giamkhao'
                  ? { work: 'focus', idle: 'focus' }
                  : { work: 'focus', idle: 'happy' },
        );
        A[key] = a;
        actorList.push(a);
        scene.add(a.root, a.shadowMesh);
    }
    const owl = new Owl(kit, shapes, now);
    scene.add(owl.root);
    const cat = new Cat(
        kit,
        shapes,
        nav,
        fx,
        actorList,
        house.deskTops,
        world.butterflies,
        now,
        motion,
        shadowMat,
    );
    scene.add(cat.root, cat.shadowMesh);
    const director = new Director(
        A,
        owl,
        cat,
        house,
        world,
        fx,
        now,
        motion,
        wings,
        () => hourNow(),
    );
    ctx.onBump = (x, y) => director.bump(x, y);
    // người điều phối lời nói chung (chống nói dồn dập)
    const speech = new Speech(now);
    ctx.speech = speech;
    cat.speech = speech;
    owl.speech = speech;
    speech.tired = (k) => (A[k] ? director.tired(A[k]) : false);
    const talkers: Talker[] = [...actorList, owl, cat, director.board];
    const overlay = new Overlay(host, camera, house.occluders);

    // giờ trong ngày
    const hourNow = () => {
        if (o.hour != null) {
            return o.hour;
        }
        const d = new Date();

        return d.getHours() + d.getMinutes() / 60;
    };
    let hourAt = -1;
    const applyHour = () => {
        world.setHour(hourNow());
        house.setNight(world.night, world.skyColor);
        wings.setNight(world.night);
        walkFog.color.copy(world.skyColor);
        hourAt = clock.t;
    };
    applyHour();

    // ---------------------------------------------------------------- chọn bằng chuột
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    let pointer: { x: number; y: number } | null = null;
    let hover: Hover = null;
    const pickables: THREE.Object3D[] = [
        ...actorList.map((a) => a.root),
        owl.root,
        cat.root,
        house.reelGroup,
        house.boardMesh,
        world.mailboxPick,
    ];
    const findPick = (x: number, y: number): Hover => {
        ndc.set((x / W) * 2 - 1, -(y / H) * 2 + 1);
        ray.setFromCamera(ndc, camera);
        const hits = ray.intersectObjects(pickables, true);
        for (const h of hits) {
            let ob: THREE.Object3D | null = h.object;
            while (ob && !ob.userData.pick) {
                ob = ob.parent;
            }
            if (ob) {
                const p = ob.userData.pick as {
                    kind: string;
                    key?: string;
                    reel?: Reel;
                };
                if (p.kind === 'reel' && p.reel) {
                    return { kind: 'reel', reel: p.reel, obj: ob };
                }
                if (p.kind === 'cat') {
                    return { kind: 'cat' };
                }

                return { kind: 'role', key: p.key! };
            }
        }
        if (rig.mode === 'walk') {
            return null; // đi dạo: bấm vào phòng là đi tới đó, không chuyển trang
        }
        const rh = ray.intersectObjects(house.pickRooms, false);
        if (rh.length) {
            const p = rh[0].object.userData.pick as {
                kind?: string;
                key: string;
                name?: string;
            };
            if (p.kind === 'place') {
                return { kind: 'place', key: p.key, name: p.name ?? '' };
            }

            return { kind: 'role', key: p.key };
        }

        return null;
    };
    const sameHover = (a: Hover, b: Hover) =>
        JSON.stringify(a && { ...a, obj: undefined }) ===
        JSON.stringify(b && { ...b, obj: undefined });
    const setHover = (h: Hover) => {
        if (sameHover(h, hover)) {
            return;
        }
        // tắt sáng cũ
        actorList.forEach((a) => a.setHighlight(false));
        owl.setHighlight(false);
        cat.setHighlight(false);
        if (hover?.kind === 'reel') {
            hover.obj.scale.setScalar(1);
        }
        hover = h;
        host.classList.toggle('n3-hover', !!h);
        if (!h) {
            overlay.hideTip();

            return;
        }
        if (h.kind === 'role') {
            if (h.key === 'cu') {
                owl.setHighlight(true);
            } else if (h.key === 'daodien') {
                A.daodienA.setHighlight(true);
                A.daodienB.setHighlight(true);
            } else if (A[h.key]) {
                A[h.key].setHighlight(true);
            }
        } else if (h.kind === 'cat') {
            cat.setHighlight(true);
        } else if (h.kind === 'reel') {
            h.obj.scale.setScalar(1.25);
        }
    };
    const tipFor = (h: Hover): [string, string] | null => {
        if (!h) {
            return null;
        }
        if (h.kind === 'cat') {
            return ['Mèo', 'Bấm để nghe meo~'];
        }
        if (h.kind === 'place') {
            return [h.name, 'Chỗ nghỉ ngơi của cả nhà'];
        }
        if (h.kind === 'reel') {
            return [
                `Video ${h.reel.so}${h.reel.diem != null ? ` · ${h.reel.diem} điểm` : ''}`,
                'Bấm để xem video',
            ];
        }
        const d = DICH[h.key];
        if (!d) {
            return null;
        }
        const name =
            h.key === 'daodien'
                ? 'Đạo diễn'
                : h.key === 'cu'
                  ? NAMES.cu
                  : d.ten;

        return [name, d.href ? `Bấm để tới ${d.dich}` : ''];
    };
    const activate = (h: Hover) => {
        if (!h) {
            return;
        }
        if (h.kind === 'cat') {
            cat.poke(noi('meo'));

            return;
        }
        if (h.kind === 'place') {
            return;
        }
        if (h.kind === 'reel') {
            const hub = director.data?.hub.url;
            const r = h.reel;
            o.onOpen(
                hub && r.file && r.ngay
                    ? `${hub}/file?p=${encodeURIComponent(`${r.ngay}/${r.file}`)}`
                    : null,
            );

            return;
        }
        o.onGo(h.key);
    };
    // ---------------------------------------------------------------- Kid (chủ xưởng) + hai chế độ camera
    const kidActor = new Actor(
        'kid',
        SPECS.kid,
        { node: 'porch', rot: Math.PI, seated: false, work: 'idle' },
        ctx,
        shadowMat,
        { work: 'happy', idle: 'happy' },
    );
    kidActor.root.userData.pick = undefined;
    kidActor.ch.meshes.forEach((m) => delete m.userData.pick);
    kidActor.pos.set(room('sanh').cx, F1, 1.25);
    kidActor.root.position.copy(kidActor.pos);
    const star = new THREE.Mesh(
        kit.geo(new THREE.OctahedronGeometry(0.11, 0)),
        kit.basic(0xffd23f),
    );
    star.position.y = 1.78;
    kidActor.root.add(star);
    scene.add(kidActor.root, kidActor.shadowMesh);
    actorList.push(kidActor);
    const kid = new KidControl(kidActor, house.deskTops);
    director.kid = kidActor;

    const modeBtn = document.createElement('button');
    modeBtn.type = 'button';
    modeBtn.className = 'n3-mode';
    const promptBtn = document.createElement('button');
    promptBtn.type = 'button';
    promptBtn.className = 'n3-prompt';
    promptBtn.style.display = 'none';
    host.append(modeBtn, promptBtn);
    const readMode = (): CamMode => {
        try {
            const v = localStorage.getItem('nha3d.cam');
            if (v === 'walk' || v === 'overview') {
                return v;
            }
        } catch {
            // không có bộ nhớ trình duyệt: dùng mặc định
        }

        return coarse ? 'overview' : 'walk';
    };
    const setMode = (m: CamMode, save = true) => {
        rig.setMode(m, kidActor.root.position);
        host.classList.toggle('n3-walk', m === 'walk');
        modeBtn.textContent =
            m === 'walk' ? '🏡 Toàn cảnh' : '🚶 Đi dạo cùng Kid';
        hint.textContent =
            m === 'walk'
                ? 'WASD / mũi tên để đi · Shift để chạy · bấm xuống sàn để tới đó · kéo để nhìn quanh'
                : coarse
                  ? 'Vuốt ngang để xoay · hai ngón để phóng to'
                  : 'Kéo để xoay · cuộn để phóng to · bấm đúp để về';
        hint.style.opacity = '1';
        scene.fog = m === 'walk' ? walkFog : null;
        renderer.domElement.style.touchAction =
            m === 'walk' ? 'none' : coarse ? 'pan-y' : '';
        kid.keys.clear();
        kid.target = null;
        if (save) {
            try {
                localStorage.setItem('nha3d.cam', m);
            } catch {
                // bỏ qua
            }
        }
    };
    modeBtn.addEventListener('click', () =>
        setMode(rig.mode === 'walk' ? 'overview' : 'walk'),
    );
    // đứng gần ai thì hiện nút "E · Tới khu làm việc"
    let near: string | null = null;
    const ROLE_OF: Record<string, string> = {
        daodienA: 'daodien',
        daodienB: 'daodien',
    };
    const updateNear = () => {
        let best: string | null = null;
        let bd = 1.9;
        if (rig.mode === 'walk') {
            for (const a of Object.values(A)) {
                const d = Math.hypot(
                    a.pos.x - kidActor.pos.x,
                    a.pos.z - kidActor.pos.z,
                );
                const role = ROLE_OF[a.key] ?? a.key;
                if (
                    d < bd &&
                    Math.abs(a.pos.y - kidActor.pos.y) < 1 &&
                    DICH[role]?.href
                ) {
                    bd = d;
                    best = role;
                }
            }
        }
        if (best !== near) {
            near = best;
            if (best) {
                promptBtn.textContent = `${coarse ? '' : 'E · '}Tới khu làm việc: ${DICH[best].ten}`;
                promptBtn.style.display = 'block';
            } else {
                promptBtn.style.display = 'none';
            }
        }
    };
    promptBtn.addEventListener('click', () => near && o.onGo(near));
    const typing = (t: EventTarget | null) =>
        t instanceof HTMLElement &&
        (t.isContentEditable ||
            /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(t.tagName));
    const MOVERS = [
        'KeyW',
        'KeyA',
        'KeyS',
        'KeyD',
        'ArrowUp',
        'ArrowDown',
        'ArrowLeft',
        'ArrowRight',
        'ShiftLeft',
        'ShiftRight',
    ];
    const onKey = (e: KeyboardEvent) => {
        if (
            rig.mode !== 'walk' ||
            !visible ||
            typing(e.target) ||
            e.ctrlKey ||
            e.metaKey ||
            e.altKey
        ) {
            return;
        }
        if (e.type === 'keydown' && e.code === 'KeyE' && near) {
            e.preventDefault();
            o.onGo(near);

            return;
        }
        if (!MOVERS.includes(e.code)) {
            return;
        }
        if (e.type === 'keydown') {
            kid.keys.add(e.code);
            hint.style.opacity = '0';
        } else {
            kid.keys.delete(e.code);
        }
        if (e.code.startsWith('Arrow')) {
            e.preventDefault();
        }
    };
    const onBlur = () => kid.keys.clear();
    window.addEventListener('keydown', onKey);
    window.addEventListener('keyup', onKey);
    window.addEventListener('blur', onBlur);
    // điểm trên sàn dưới con trỏ (trong nhà: sàn tầng 1; ngoài vườn: mặt đất)
    const floorAt = (x: number, y: number): THREE.Vector3 | null => {
        ndc.set((x / W) * 2 - 1, -(y / H) * 2 + 1);
        ray.setFromCamera(ndc, camera);
        const p = new THREE.Vector3();
        if (
            ray.ray.intersectPlane(
                new THREE.Plane(new THREE.Vector3(0, 1, 0), -F1),
                p,
            ) &&
            p.z <= Z_FRONT &&
            p.x >= XL0 - 0.3 &&
            p.x <= XR1 + 0.3
        ) {
            return p;
        }
        if (
            ray.ray.intersectPlane(
                new THREE.Plane(new THREE.Vector3(0, 1, 0), 0),
                p,
            )
        ) {
            return p;
        }

        return null;
    };

    let down: {
        x: number;
        y: number;
        t: number;
        lx: number;
        ly: number;
        drag: boolean;
    } | null = null;
    const local = (e: PointerEvent) => {
        const r = renderer.domElement.getBoundingClientRect();

        return { x: e.clientX - r.left, y: e.clientY - r.top };
    };
    const onMove = (e: PointerEvent) => {
        const p = local(e);
        if (e.pointerType === 'mouse') {
            pointer = p;
        }
        if (down && rig.mode === 'walk' && e.buttons) {
            if (!down.drag && Math.hypot(p.x - down.x, p.y - down.y) > 6) {
                down.drag = true;
                hint.style.opacity = '0';
            }
            if (down.drag) {
                rig.drag(p.x - down.lx, p.y - down.ly);
            }
            down.lx = p.x;
            down.ly = p.y;
        }
    };
    const onLeave = () => {
        pointer = null;
        setHover(null);
    };
    const onDown = (e: PointerEvent) => {
        const p = local(e);
        down = { ...p, lx: p.x, ly: p.y, t: performance.now(), drag: false };
    };
    const onUp = (e: PointerEvent) => {
        if (!down) {
            return;
        }
        const p = local(e);
        const click =
            !down.drag &&
            Math.hypot(p.x - down.x, p.y - down.y) < 7 &&
            performance.now() - down.t < 600;
        down = null;
        if (!click) {
            return;
        }
        const h = findPick(p.x, p.y);
        if (h || rig.mode === 'overview') {
            activate(h);

            return;
        }
        // đi dạo: bấm xuống sàn để Kid đi tới đó
        const f = floorAt(p.x, p.y);
        if (f) {
            kid.goTo(f, nav);
            hint.style.opacity = '0';
        }
    };
    const onWheel = (e: WheelEvent) => {
        if (rig.mode === 'walk') {
            e.preventDefault();
            rig.wheel(e.deltaY);
        }
    };
    const onDbl = () => rig.home();
    const el = renderer.domElement;
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    el.addEventListener('pointerdown', onDown);
    el.addEventListener('pointerup', onUp);
    el.addEventListener('dblclick', onDbl);
    el.addEventListener('wheel', onWheel, { passive: false });
    setMode(readMode(), false);

    // ---------------------------------------------------------------- vòng lặp
    let raf = 0;
    let last = performance.now();
    let visible = true;
    let failed = false;
    let smokeAt = 0;
    const fps = { frames: 0, at: performance.now(), value: 0 };
    const io = new IntersectionObserver(
        (en) => (visible = en[0]?.isIntersecting ?? true),
    );
    io.observe(host);
    const camDir = new THREE.Vector3();
    const frame = (ts: number) => {
        raf = requestAnimationFrame(frame);
        if (document.hidden || !visible) {
            last = ts;

            return;
        }
        const dt = Math.min(0.05, (ts - last) / 1000);
        last = ts;
        try {
            clock.t += dt;
            if (clock.t - hourAt > 60) {
                applyHour();
            }
            director.tick(dt);
            if (rig.mode === 'walk') {
                kid.update(dt, rig.yaw);
            }
            for (const a of actorList) {
                a.update(dt);
            }
            owl.update(clock.t, dt, motion);
            cat.update(dt);
            house.update(clock.t, dt);
            wings.update(motion ? clock.t : 0, dt, clock.t);
            world.update(clock.t, dt, motion);
            fx.update(dt);
            if (
                motion &&
                clock.t > smokeAt &&
                director.data &&
                director.data.mode !== 'down'
            ) {
                smokeAt = clock.t + 1.3;
                fx.smoke(house.chimney);
            }
            star.rotation.y += dt * 2;
            star.position.y =
                1.78 + (motion ? Math.sin(clock.t * 2.4) * 0.05 : 0);
            rig.update(dt, kidActor.root.position);
            updateNear();
            // tường đầu hồi mờ đi khi camera xoay về phía nó
            camDir.copy(camera.position).sub(rig.target).setY(0).normalize();
            for (const w of house.fadeWalls) {
                const target = w.normal.dot(camDir) > 0.45 ? 0.12 : 1;
                w.op += (target - w.op) * Math.min(1, dt * 6);
                w.mat.opacity = w.op;
                const solid = w.op > 0.98;
                if (w.mat.transparent === solid) {
                    w.mat.transparent = !solid;
                    w.mat.depthWrite = solid;
                    w.mat.needsUpdate = true;
                }
            }
            if (pointer) {
                const h = findPick(pointer.x, pointer.y);
                setHover(h);
                const tip = tipFor(h);
                if (tip) {
                    overlay.showTip(pointer.x, pointer.y, tip[0], tip[1]);
                } else {
                    overlay.hideTip();
                }
                pointer = null;
            }
            renderer.render(scene, camera);
            overlay.update(talkers, clock.t, W, H);
            fps.frames++;
            if (ts - fps.at > 1000) {
                fps.value = Math.round((fps.frames * 1000) / (ts - fps.at));
                fps.frames = 0;
                fps.at = ts;
            }
        } catch (err) {
            if (!failed) {
                failed = true;
                cancelAnimationFrame(raf);
                o.onFail(err);
            }
        }
    };
    raf = requestAnimationFrame(frame);

    // ---------------------------------------------------------------- gỡ lỗi (chỉ khi ?demo / ?debug)
    if (o.debug) {
        (window as unknown as Record<string, unknown>).__nha3d = {
            fps: () => fps.value,
            info: () => ({
                calls: renderer.info.render.calls,
                tris: renderer.info.render.triangles,
                geos: renderer.info.memory.geometries,
                texs: renderer.info.memory.textures,
                fx: fx.count,
                queue: director.queued,
                log: director.log.slice(-8),
            }),
            screen: (key: string) => {
                const t = talkers.find((x) => x.key === key);
                if (!t) {
                    return null;
                }
                const p = t
                    .anchor(new THREE.Vector3())
                    .add(new THREE.Vector3(0, -0.7, 0))
                    .project(camera);
                const r = renderer.domElement.getBoundingClientRect();

                return {
                    x: r.left + (p.x * 0.5 + 0.5) * W,
                    y: r.top + (-p.y * 0.5 + 0.5) * H,
                };
            },
            setHour: (h: number) => {
                o.hour = h;
                applyHour();
            },
            cam: (m: CamMode) => setMode(m, false),
            walkTo: (x: number, z: number) =>
                kid.goTo(new THREE.Vector3(x, 0, z), nav),
            kid: kidActor,
            rig,
            catTo: (key: string) => {
                if (A[key]) {
                    cat.seekNow(A[key]);
                }
            },
            play: (k: string, who?: string) => director.debugPlay(k, who),
            actors: A,
            cat,
            camera,
            controls,
            scene,
            hit: (key: string) => {
                const t = talkers.find((x) => x.key === key)!;
                const p = t
                    .anchor(new THREE.Vector3())
                    .add(new THREE.Vector3(0, -0.6, 0));
                const q = p.clone().project(camera);
                ray.setFromCamera(new THREE.Vector2(q.x, q.y), camera);
                return ray
                    .intersectObjects(scene.children, true)
                    .slice(0, 6)
                    .map((h) => [
                        h.object.name || h.object.type,
                        (h.object as THREE.Mesh).material &&
                            (
                                (h.object as THREE.Mesh)
                                    .material as THREE.Material
                            ).type,
                        h.point
                            .toArray()
                            .map((v) => v.toFixed(2))
                            .join(','),
                        h.object.parent?.type,
                    ]);
            },
        };
    }

    return {
        update(data: NhaData) {
            if (!failed) {
                director.update(data);
            }
        },
        dispose() {
            cancelAnimationFrame(raf);
            ro.disconnect();
            io.disconnect();
            el.removeEventListener('pointermove', onMove);
            el.removeEventListener('pointerleave', onLeave);
            el.removeEventListener('pointerdown', onDown);
            el.removeEventListener('pointerup', onUp);
            el.removeEventListener('dblclick', onDbl);
            el.removeEventListener('wheel', onWheel);
            window.removeEventListener('keydown', onKey);
            window.removeEventListener('keyup', onKey);
            window.removeEventListener('blur', onBlur);
            modeBtn.remove();
            promptBtn.remove();
            controls.dispose();
            overlay.dispose();
            hint.remove();
            world.sun.shadow.dispose();
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
            renderer.domElement.remove();
            if (o.debug) {
                delete (window as unknown as Record<string, unknown>).__nha3d;
            }
        },
    };
};

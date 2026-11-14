// Điểm vào của thế giới 3D "Khu Tự Trị" (tải lười: chỉ trang /nha mới kéo three.js về).
// Dựng renderer + camera phối cảnh (đi dạo cùng Kid hoặc toàn cảnh), ghép nhà/vườn/nhân vật/mèo, vòng lặp vẽ, chọn bằng chuột, dọn sạch khi rời trang.
import * as THREE from 'three';

import { Caller } from '@/components/fork/nha3d/call';
import { reactTo } from '@/components/fork/nha3d/react';

import { noi } from '../nha/loi-thoai';
import { DICH, type NhaData } from '../nha/types';
import {
    Actor,
    blobShadow,
    type ActorCtx,
    type Gait,
    type Talker,
} from './actor';
import {
    normalizeAvatar,
    specFromAvatar,
    xungHo,
    type AvatarCfg,
} from './avatar';
import { openAvatarPanel } from './avatar-ui';
import { CamRig, type CamMode } from './camrig';
import { NAMES, Owl, SPECS } from './cast';
import { Cat } from './cat';
import type { AnimName } from './chibi';
import { Director } from './director';
import { Effects } from './effects';
import { House, type Reel } from './house';
import { Interact } from './interact';
import { KidControl } from './kid';
import { buildNav, F1, HOMES, room, XL0, XR1, Z_FRONT } from './layout';
import { AGENT_R, inPond, levelOf, NavGrid, PAIR_D } from './navgrid';
import { Overlay } from './overlay';
import { Pond } from './pond';
import { Speech } from './speech';
import { Kit, pick, Shapes } from './util';
import { Weather, type Sky } from './weather';
import { Wings } from './wings';
import { World } from './world';

export interface NhaWorldOptions {
    host: HTMLElement;
    reduced: boolean;
    hour?: number | null;
    debug?: boolean;
    /** Ngoại hình nhân vật chính đã lưu trên máy chủ (thiếu thì dùng Kid mặc định). */
    avatar?: unknown;
    onGo: (key: string) => void;
    onOpen: (url: string | null) => void;
    onFail: (err: unknown) => void;
}

export interface NhaWorld {
    update(data: NhaData): void;
    /** "Gọi về gấp": nhân vật của `vai` chạy tới chỗ Kid đứng và báo cáo. */
    call(vai: string): void;
    /** Nhân vật của `vai` phản ứng với một việc vừa làm trong popup (xem ban/bus.ts). */
    react(vai: string, viec: string): void;
    dispose(): void;
}

export { webglOk } from './util';

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
    const weather = new Weather(kit, motion);
    scene.add(weather.group);
    const pond = new Pond(fx, now, motion);
    const nav = buildNav();
    // lưới va chạm từ mọi hình tĩnh (tường, cửa, đồ đạc, cây, hàng rào…)
    // (dựng sau vài khung hình đầu, khi mọi đồ vật đã về đúng chỗ)
    const grid = new NavGrid();
    const buildGrid = () => {
        scene.updateMatrixWorld(true);
        grid.build(
            [house.group, world.group],
            [...nav.nodes.values()]
                .filter(
                    (n) => !n.id.endsWith('.seat') && !n.id.startsWith('st.'),
                )
                .map((n) => n.p),
            [],
        );
        ctx.grid = grid;
        kid.grid = grid;
        pond.grid = grid;
    };
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
        raining: () => weather.raining,
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
    director.pond = pond;
    director.weather = weather;
    director.nav = nav;
    weather.onChange = (sk: Sky, prev: Sky) => {
        if (sk === 'rain') {
            director.onRain(true);
        } else if (prev === 'rain') {
            director.onRain(false);
        }
    };
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
    let ovApplied = 0;
    const applyHour = () => {
        ovApplied = weather.overcast;
        world.setHour(hourNow(), weather.overcast);
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
    const findPick = (x: number, y: number, rooms = false): Hover => {
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
        if (rig.mode === 'walk' || !rooms) {
            return null; // bấm vào phòng/sân là Kid đi tới đó (không chuyển trang)
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

            return { kind: 'role', key: p.key, room: true };
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
            return ['Mèo quản gia', 'Bấm để mở bàn làm việc'];
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

        if (h.room) {
            return [name, 'Bấm để Kid đi tới đây'];
        }

        return [name, d.href ? 'Bấm để mở bàn làm việc' : ''];
    };
    const activate = (h: Hover) => {
        if (!h) {
            return;
        }
        if (h.kind === 'cat') {
            cat.poke(noi('meo'));
            caller.onOpened('meo');
            o.onGo('meo');

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
        caller.onOpened(h.key);
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
    // biểu tượng lơ lửng trên đầu (sao / tim / vương miện / không)
    const star = new THREE.Group();
    star.position.y = 1.78;
    kidActor.root.add(star);
    const icons: Record<string, THREE.Object3D> = {};
    icons.star = new THREE.Mesh(
        kit.geo(new THREE.OctahedronGeometry(0.11, 0)),
        kit.basic(0xffd23f),
    );
    {
        const h = new THREE.Shape();
        h.moveTo(0, -0.1);
        h.bezierCurveTo(-0.02, -0.06, -0.12, -0.02, -0.12, 0.04);
        h.bezierCurveTo(-0.12, 0.1, -0.04, 0.12, 0, 0.06);
        h.bezierCurveTo(0.04, 0.12, 0.12, 0.1, 0.12, 0.04);
        h.bezierCurveTo(0.12, -0.02, 0.02, -0.06, 0, -0.1);
        const g = new THREE.ExtrudeGeometry(h, {
            depth: 0.04,
            bevelEnabled: true,
            bevelThickness: 0.015,
            bevelSize: 0.012,
            bevelSegments: 2,
        });
        g.translate(0, 0, -0.02);
        icons.heart = new THREE.Mesh(kit.geo(g), kit.basic(0xff6f9f));
        const crown = new THREE.Group();
        const gold = kit.basic(0xffc93c);
        const band = new THREE.Mesh(
            kit.geo(new THREE.CylinderGeometry(0.1, 0.09, 0.07, 16, 1, true)),
            gold,
        );
        (band.material as THREE.MeshBasicMaterial).side = THREE.DoubleSide;
        crown.add(band);
        for (let i = 0; i < 5; i++) {
            const a = (i / 5) * Math.PI * 2;
            const tip = new THREE.Mesh(
                kit.geo(new THREE.ConeGeometry(0.025, 0.07, 6)),
                gold,
            );
            tip.position.set(Math.sin(a) * 0.092, 0.065, Math.cos(a) * 0.092);
            crown.add(tip);
            const gem = new THREE.Mesh(
                kit.geo(new THREE.SphereGeometry(0.014, 8, 6)),
                kit.basic(i % 2 ? 0xff5f6d : 0x5aa9ff),
            );
            gem.position.set(Math.sin(a) * 0.1, 0, Math.cos(a) * 0.1);
            crown.add(gem);
        }
        icons.crown = crown;
        Object.values(icons).forEach((m) => star.add(m));
    }
    let avatar: AvatarCfg = normalizeAvatar(o.avatar);
    const applyAvatar = (c: AvatarCfg, rebuild: boolean) => {
        avatar = c;
        if (rebuild) {
            kidActor.rebuild(specFromAvatar(c), { work: c.mat, idle: c.mat });
            kidActor.root.userData.pick = undefined;
            kidActor.ch.meshes.forEach((m) => delete m.userData.pick);
        }
        for (const [k, m] of Object.entries(icons)) {
            m.visible = k === c.bieu_tuong;
        }
        director.player = { ten: c.ten, anh: xungHo(c) };
    };
    scene.add(kidActor.root, kidActor.shadowMesh);
    actorList.push(kidActor);
    const kid = new KidControl(kidActor, house.deskTops);
    director.kid = kidActor;
    ctx.clampPos = (p) => kid.clampPos(p);
    kid.others = actorList;
    kid.onPond = () => {
        // cứ cố đi vào hồ → trượt chân rơi tõm, bơi vào bờ, giũ nước
        if (pond.plunge(kidActor, { how: 'slip' })) {
            kidActor.say(
                pick([
                    'Á á á! Trượt chân!',
                    'Ối! Tõm mất rồi!',
                    'Ướt hết rồi nè!',
                ]),
                2.4,
                'reply',
            );
            for (const a of actorList) {
                if (a !== kidActor && a.pos.distanceTo(kidActor.pos) < 7) {
                    a.say(director.line(a, 'bi_thoc_let'), 2.2, 'chat');
                    break;
                }
            }
        }
    };
    talkers.push(kidActor);
    applyAvatar(
        avatar,
        JSON.stringify(specFromAvatar(avatar)) !==
            JSON.stringify(specFromAvatar(normalizeAvatar(null))),
    );
    const interact = new Interact({
        host,
        kid,
        kidActor,
        A,
        cat,
        director,
        fx,
        nav,
        now,
        hour: () => hourNow(),
        motion,
        wings,
        world,
        kit,
        shapes,
        scene,
        pond,
    });

    const caller = new Caller({
        host,
        scene,
        A,
        owl,
        cat,
        nav,
        rig,
        kidActor,
        director,
        camera,
        getGrid: () => ctx.grid,
        now,
        motion,
    });
    const modeBtn = document.createElement('button');
    modeBtn.type = 'button';
    modeBtn.className = 'n3-mode';
    const promptBtn = document.createElement('button');
    promptBtn.type = 'button';
    promptBtn.className = 'n3-prompt';
    promptBtn.style.display = 'none';
    const avBtn = document.createElement('button');
    avBtn.type = 'button';
    avBtn.className = 'n3-avbtn';
    avBtn.textContent = '🧑 Nhân vật';
    avBtn.title = 'Nhân vật của tôi: đặt tên và chọn ngoại hình';
    let avPanel: { close: () => void } | null = null;
    avBtn.addEventListener('click', () => {
        if (avPanel) {
            return;
        }
        kid.keys.clear();
        avPanel = openAvatarPanel({
            host,
            current: avatar,
            onSave: (c) => {
                applyAvatar(c, true);
                kidActor.say(
                    `Từ giờ gọi ${xungHo(c)} là ${c.ten} nha!`,
                    2.6,
                    'reply',
                );
                fx.sparkle(
                    kidActor.root.position.clone().setY(kidActor.pos.y + 1.2),
                    10,
                );
            },
            onClose: () => {
                avPanel = null;
            },
        });
    });
    host.append(modeBtn, avBtn, promptBtn);
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
                ? 'WASD / mũi tên để đi · Shift chạy · bấm xuống sàn để tới đó · kéo để nhìn quanh · đứng gần ai để tương tác · Q: cả nhà'
                : coarse
                  ? 'Vuốt ngang để xoay · hai ngón để phóng to'
                  : 'WASD / bấm xuống sàn để Kid đi · kéo để xoay · cuộn để phóng to · Q: cả nhà';
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
        {
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
                promptBtn.textContent = `${coarse ? '' : 'E · '}Mở bàn làm việc: ${DICH[best].ten}`;
                promptBtn.style.display = 'block';
            } else {
                promptBtn.style.display = 'none';
            }
        }
    };
    promptBtn.addEventListener('click', () => near && o.onGo(near));
    // huy hiệu số việc chờ trên đầu nhân vật: bấm = bấm nhân vật
    overlay.onBadge = (k) => o.onGo(ROLE_OF[k] ?? k);
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
            !visible ||
            avPanel ||
            typing(e.target) ||
            e.ctrlKey ||
            e.metaKey ||
            e.altKey
        ) {
            return;
        }
        if (e.type === 'keydown' && e.code === 'KeyG') {
            e.preventDefault();
            caller.toggle();

            return;
        }
        if (e.type === 'keydown' && e.code === 'Escape' && caller.opened) {
            e.preventDefault();
            caller.close();

            return;
        }
        if (interact.key(e)) {
            e.preventDefault();

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
        if (h) {
            activate(h);

            return;
        }
        // bấm xuống sàn để Kid đi tới đó (cả khi xem toàn cảnh)
        const f = floorAt(p.x, p.y);
        if (f) {
            kid.script = [];
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
    let saveAt = 5;
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
    const camFocus = new THREE.Vector3();
    interact.onFocus = (a) => {
        if (rig.mode !== 'walk') {
            return;
        }
        // camera chéo ~40° sau lưng Kid để thấy cả mặt người kia
        const base = Math.atan2(
            kidActor.pos.x - a.pos.x,
            kidActor.pos.z - a.pos.z,
        );
        const opts = [base + 0.75, base - 0.75];
        const diff = (x: number) =>
            Math.abs(Math.atan2(Math.sin(x - rig.yaw), Math.cos(x - rig.yaw)));
        rig.yawTo = diff(opts[0]) < diff(opts[1]) ? opts[0] : opts[1];
    };
    // ---------------------------------------------------------------- không ai đứng chồng lên ai
    const solid = (a: Actor) =>
        !a.ghost && !a.seated && !a.lying && !a.driver && !a.passThrough;
    const separate = () => {
        const g = ctx.grid;
        if (!g) {
            return;
        }
        for (let i = 0; i < actorList.length; i++) {
            const a = actorList[i];
            if (!solid(a) && !a.parked) {
                continue;
            }
            for (let j = i + 1; j < actorList.length; j++) {
                const b = actorList[j];
                if (
                    (!solid(b) && !b.parked) ||
                    Math.abs(a.pos.y - b.pos.y) > 0.6
                ) {
                    continue;
                }
                let dx = a.pos.x - b.pos.x;
                let dz = a.pos.z - b.pos.z;
                let d = Math.hypot(dx, dz);
                if (d >= PAIR_D) {
                    continue;
                }
                if (d < 1e-4) {
                    dx = 1;
                    dz = 0;
                    d = 1e-4;
                }
                const ma = a !== kidActor && !a.parked;
                const mb = b !== kidActor && !b.parked;
                if (!ma && !mb) {
                    continue;
                }
                const push = PAIR_D - d;
                const ka = ma && mb ? 0.5 : ma ? 1 : 0;
                const kb = ma && mb ? 0.5 : mb ? 1 : 0;
                const l = levelOf(a.pos.y);
                if (ka) {
                    const q = g.slide(
                        l,
                        a.pos.x,
                        a.pos.z,
                        a.pos.x + (dx / d) * push * ka,
                        a.pos.z + (dz / d) * push * ka,
                    );
                    a.pos.x = q.x;
                    a.pos.z = q.z;
                }
                if (kb) {
                    const q = g.slide(
                        l,
                        b.pos.x,
                        b.pos.z,
                        b.pos.x - (dx / d) * push * kb,
                        b.pos.z - (dz / d) * push * kb,
                    );
                    b.pos.x = q.x;
                    b.pos.z = q.z;
                }
            }
        }
    };
    // soát va chạm mỗi khung hình (chỉ khi gỡ lỗi): không ai lọt vào vật cản, không ai chồng lên ai
    const coll = {
        frames: 0,
        samples: 0,
        exempt: 0,
        wall: 0,
        pair: 0,
        worstWall: 0,
        worstPair: 0,
        log: [] as string[],
    };
    const checkCollisions = () => {
        const g = ctx.grid;
        if (!g) {
            return;
        }
        coll.frames++;
        for (const a of actorList) {
            coll.samples++;
            if (!solid(a)) {
                coll.exempt++;
                continue;
            }
            const c = g.clearance(levelOf(a.pos.y), a.pos.x, a.pos.z);
            if (c < AGENT_R - 0.06) {
                coll.wall++;
                coll.worstWall = Math.max(coll.worstWall, AGENT_R - c);
                if (coll.log.length < 60) {
                    coll.log.push(
                        `wall ${a.key} t=${clock.t.toFixed(1)} (${a.pos.x.toFixed(2)},${a.pos.y.toFixed(2)},${a.pos.z.toFixed(2)}) clear=${c.toFixed(3)}`,
                    );
                }
            }
        }
        for (let i = 0; i < actorList.length; i++) {
            const a = actorList[i];
            if (!solid(a) && !a.parked) {
                continue;
            }
            for (let j = i + 1; j < actorList.length; j++) {
                const b = actorList[j];
                if (
                    (!solid(b) && !b.parked) ||
                    Math.abs(a.pos.y - b.pos.y) > 0.6
                ) {
                    continue;
                }
                const d = Math.hypot(a.pos.x - b.pos.x, a.pos.z - b.pos.z);
                if (d < PAIR_D - 0.08) {
                    coll.pair++;
                    coll.worstPair = Math.max(coll.worstPair, PAIR_D - d);
                    if (coll.log.length < 60) {
                        coll.log.push(
                            `pair ${a.key}/${b.key} t=${clock.t.toFixed(1)} d=${d.toFixed(3)}`,
                        );
                    }
                }
            }
        }
    };

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
            if (!ctx.grid && clock.t > 0.2) {
                buildGrid();
            }
            if (clock.t - hourAt > 60) {
                applyHour();
            }
            director.tick(dt);
            kid.update(dt, rig.viewYaw);
            for (const a of actorList) {
                a.update(dt);
            }
            separate();
            if (o.debug) {
                checkCollisions();
            }
            pond.update();
            weather.update(
                dt,
                rig.mode === 'walk'
                    ? kidActor.root.position
                    : rig.controls.target,
                clock.t,
            );
            if (Math.abs(weather.overcast - ovApplied) > 0.02) {
                applyHour();
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
            const fa = rig.mode === 'walk' ? interact.focus : null;
            if (fa) {
                camFocus.copy(kidActor.root.position).lerp(fa.pos, 0.45);
                camFocus.y = kidActor.root.position.y;
            }
            rig.update(dt, fa ? camFocus : kidActor.root.position);
            updateNear();
            interact.update(dt);
            caller.update(dt);
            saveAt -= dt;
            if (saveAt <= 0) {
                saveAt = 5;
                save();
            }
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
                const h = findPick(pointer.x, pointer.y, true);
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

    // ---------------------------------------------------------------- nhớ thế giới khi rời trang rồi quay lại
    const SAVE_KEY = `nha3d.world${o.debug ? '.demo' : ''}`;
    const snapshot = () => ({
        v: 1,
        at: Date.now(),
        t: clock.t,
        kid: {
            x: kidActor.pos.x,
            y: kidActor.pos.y,
            z: kidActor.pos.z,
            rot: kidActor.rot,
        },
        cam: rig.snapshot(),
        actors: Object.fromEntries(
            Object.entries(A).map(([k, a]) => [k, a.snapshot()]),
        ),
        cat: cat.snapshot(),
        dir: director.snapshot(),
        speech: speech.snapshot(),
        ia: interact.snapshot(),
        wx: weather.snapshot(),
    });
    type Snap = ReturnType<typeof snapshot>;
    function save() {
        if (failed) {
            return;
        }
        try {
            sessionStorage.setItem(SAVE_KEY, JSON.stringify(snapshot()));
        } catch {
            // không lưu được (chế độ riêng tư…): bỏ qua
        }
    }
    const restore = () => {
        let s: Snap | null = null;
        try {
            const raw = sessionStorage.getItem(SAVE_KEY);
            s = raw ? (JSON.parse(raw) as Snap) : null;
        } catch {
            s = null;
        }
        if (!s || s.v !== 1) {
            return;
        }
        try {
            const away = Math.max(0, (Date.now() - s.at) / 1000);
            clock.t = s.t + Math.min(away, 3600);
            speech.restore(s.speech);
            director.restore(s.dir);
            if (s.wx) {
                weather.restore(s.wx);
            }
            // Kid luôn đứng đúng chỗ cũ
            kidActor.pos.set(s.kid.x, s.kid.y, s.kid.z);
            if (inPond(s.kid.x, s.kid.z, 1.05)) {
                kidActor.pos.copy(pond.edgeFor(kidActor.pos));
            }
            kidActor.rot = s.kid.rot;
            kidActor.faceTo(
                new THREE.Vector3(
                    s.kid.x + Math.sin(s.kid.rot),
                    0,
                    s.kid.z + Math.cos(s.kid.rot),
                ),
            );
            kidActor.root.position.copy(kidActor.pos);
            // vắng ngắn: mọi người vẫn ở chỗ cũ, làm nốt việc đang dở; vắng lâu: ai về chỗ nấy theo lịch
            if (away < 150) {
                for (const [k, snap] of Object.entries(s.actors)) {
                    const a = A[k];
                    if (!a || snap.atHome) {
                        continue;
                    }
                    if (inPond(snap.x, snap.z, 1.05)) {
                        const e = pond.edgeFor(
                            new THREE.Vector3(snap.x, 0, snap.z),
                        );
                        snap.x = e.x;
                        snap.y = 0;
                        snap.z = e.z;
                    }
                    a.restore(
                        snap,
                        nav.nearest(
                            new THREE.Vector3(snap.x, snap.y, snap.z),
                            (id) => !id.endsWith('.seat'),
                        ),
                    );
                    director.resume(a, snap, s.dir.tv);
                }
                cat.restore(s.cat);
                interact.restore(s.ia);
            }
            rig.restore(s.cam);
        } catch {
            // dữ liệu cũ hỏng: bắt đầu lại từ đầu
        }
    };
    restore();
    const onHide = () => {
        if (document.visibilityState === 'hidden') {
            save();
        }
    };
    document.addEventListener('visibilitychange', onHide);
    window.addEventListener('pagehide', save);

    // ---------------------------------------------------------------- gỡ lỗi (chỉ khi ?demo / ?debug)
    if (o.debug) {
        (window as unknown as Record<string, unknown>).__nha3d = {
            fps: () => fps.value,
            grid,
            coll: () => ({
                ...coll,
                buildMs: +grid.buildMs.toFixed(1),
                escapes: actorList.reduce((n, a) => n + a.escapes, 0),
            }),
            collReset: () => {
                coll.frames =
                    coll.samples =
                    coll.exempt =
                    coll.wall =
                    coll.pair =
                        0;
                coll.worstWall = coll.worstPair = 0;
                coll.log.length = 0;
            },
            weather: (sk: Sky | null) => weather.force(sk),
            wx: () => ({
                sky: weather.sky,
                rain: weather.rain,
                ov: weather.overcast,
                wet: weather.wet,
            }),
            pond: (k?: string) =>
                k && A[k] ? pond.plunge(A[k], { how: 'jump' }) : kid.onPond?.(),
            stumble: (k: string) => A[k]?.stumble(),
            anim: (k: string, an: AnimName, d = 3) => A[k]?.act(an, d),
            go: (k: string, node: string, gait: Gait = 'walk') => {
                const a = A[k];
                if (a) {
                    a.interrupt();
                    a.inScene = true;
                    a.leisure = true;
                    a.push(
                        { k: 'stand' },
                        { k: 'go', to: node, gait },
                        { k: 'wait', d: 6 },
                        director.release(a),
                    );
                }
            },
            seat: (k: string, node: string, an: AnimName = 'sitIdle') => {
                const a = A[k];
                if (a) {
                    a.interrupt();
                    a.inScene = true;
                    a.leisure = true;
                    a.push(
                        { k: 'stand' },
                        ...director.seat(node, an, 12),
                        director.release(a),
                    );
                }
            },
            goHome: (k: string, gait: Gait = 'sprint') => {
                const a = A[k];
                if (a) {
                    a.interrupt();
                    a.push({ k: 'home', gait });
                }
            },
            pos: () =>
                Object.fromEntries(
                    actorList.map((a) => [
                        a.key,
                        [
                            +a.pos.x.toFixed(2),
                            +a.pos.y.toFixed(2),
                            +a.pos.z.toFixed(2),
                            a.ghost
                                ? 'g'
                                : a.seated
                                  ? 's'
                                  : a.lying
                                    ? 'l'
                                    : a.parked
                                      ? 'p'
                                      : '',
                        ],
                    ]),
                ),
            gridImg: (l = 0) =>
                grid.debugImage(
                    l,
                    [...nav.nodes.values()]
                        .filter((n) =>
                            l === 0
                                ? n.p.y < 2
                                : l === 1
                                  ? n.p.y > 2 && n.p.y < 6
                                  : n.p.y > 6,
                        )
                        .map((n) => ({
                            x: n.p.x,
                            z: n.p.z,
                            c: n.id.endsWith('.seat') ? '#ff8800' : '#2266ff',
                        })),
                ),
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
            act: (k: string, who?: string) => interact.debug(k, who),
            near: () => interact.nearest()?.key ?? null,
            rel: (k: string) => director.relOf(A[k]),
            save,
            snap: () => snapshot(),
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
                caller.setData(data);
                const counts: Record<string, number> = {};
                for (const [vai, v] of Object.entries(data.viec ?? {})) {
                    counts[vai === 'daodien' ? 'daodienA' : vai] = v.so;
                }
                overlay.setCounts(counts);
            }
        },
        call(vai: string) {
            if (!failed) {
                caller.call(vai);
            }
        },
        react(vai: string, viec: string) {
            if (!failed) {
                if (viec === 'mo') {
                    caller.onOpened(vai);
                    if (vai === 'meo' && !caller.calling('meo')) {
                        cat.poke(noi('meo'));
                    }
                } else if (viec === 'dong') {
                    caller.onClosed(vai);
                }
                reactTo(
                    {
                        A,
                        owl,
                        director,
                        camera,
                        raiseFlag: () => world.raiseFlag(),
                    },
                    vai,
                    viec,
                );
            }
        },
        dispose() {
            save();
            avPanel?.close(); // bảng chỉnh nhân vật đang mở thì đóng theo, không để sót trên trang khác
            avPanel = null;
            document.removeEventListener('visibilitychange', onHide);
            window.removeEventListener('pagehide', save);
            interact.dispose();
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
            caller.dispose();
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

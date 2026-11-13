// Cảnh 3D thu nhỏ, độc lập, cho trang Xưởng Video: chỉ hai "Đạo diễn" đang ngồi làm việc ở một
// góc bàn nhỏ — KHÔNG dựng lại cả ngôi nhà (không House/World/Kid/NavGrid/bàn phím toàn cục).
// Tái dùng đúng các khối hình-người cấp thấp của thế giới 3D "Xưởng nhỏ" (Kit/Shapes cho vật liệu
// toon dùng chung, Chibi cho khối người, poseFor/applyPose cho dáng điệu, SPECS cho ngoại hình) để
// không "vẽ lại" một bộ nhân vật khác — nhưng không kéo theo NavGrid/Director/Interact (nặng và
// không cần để chỉ đứng yên một chỗ làm việc).
import * as THREE from 'three';

import { SPECS } from './cast';
import {
    applyPose,
    Chibi,
    restPose,
    poseFor,
    type AnimName,
    type Pose,
} from './chibi';
import { Kit, Shapes } from './util';

export interface MiniSceneOptions {
    host: HTMLElement;
    reduced: boolean;
}

export interface MiniScene {
    dispose(): void;
}

const SCALE = 1.15;

interface Worker {
    ch: Chibi;
    cur: Pose;
    tgt: Pose;
    anim: AnimName;
    t: number;
    blinkAt: number;
    blinkEnd: number;
}

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
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.25));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.setAttribute('aria-hidden', 'true');
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    // Camera đứng phía trước bàn (đối diện hai Đạo diễn), nhìn thấy mặt đang chăm chú làm việc —
    // không đứng cùng phía sau lưng họ (sẽ chỉ thấy gáy và tóc).
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 30);
    camera.position.set(0, 1.62, -2.75);
    camera.lookAt(0, 0.78, 0.85);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x6a52b8, 1.05));
    const sun = new THREE.DirectionalLight(0xffffff, 0.9);
    sun.position.set(2, 3.2, 2.4);
    scene.add(sun);

    // ---------------------------------------------------------------- bàn + hai màn hình nhỏ
    const woodMat = kit.toon(0xd39c68);
    const deskTop = new THREE.Mesh(shapes.rbox(2.3, 0.1, 0.9, 0.04), woodMat);
    deskTop.position.y = 0.42;
    scene.add(deskTop);
    const legMat = kit.toon(0xa8764d);
    for (const sx of [-1, 1]) {
        const leg = new THREE.Mesh(shapes.box(0.08, 0.42, 0.08), legMat);
        leg.position.set(sx * 1.0, 0.21, 0.35);
        scene.add(leg);
    }
    const screenMat = kit.toonOwn(0x2b2440, { emissive: 0x5a4fb8, emissiveIntensity: 0.6 });
    const standMat = kit.toon(0x4a3868);
    for (const sx of [-0.52, 0.52]) {
        const stand = new THREE.Mesh(shapes.box(0.04, 0.16, 0.04), standMat);
        stand.position.set(sx, 0.55, 0.1);
        scene.add(stand);
        const screen = new THREE.Mesh(shapes.rbox(0.42, 0.28, 0.02, 0.015), screenMat);
        screen.position.set(sx, 0.72, 0.08);
        scene.add(screen);
    }
    const stoolMat = kit.toon(0x7a5fd0);
    for (const sx of [-0.55, 0.55]) {
        const stool = new THREE.Mesh(shapes.cyl(0.26, 0.24, 0.42, 16), stoolMat);
        stool.position.set(sx, 0.21, 0.95);
        scene.add(stool);
    }

    // ---------------------------------------------------------------- hai "Đạo diễn" ngồi làm việc
    const workers: Worker[] = [];
    const ANIMS: AnimName[] = ['write', 'type'];
    [-0.55, 0.55].forEach((sx, i) => {
        const ch = new Chibi(kit, shapes, SPECS[i === 0 ? 'daodienA' : 'daodienB'], SCALE);
        ch.root.position.set(sx, 0, 0.95);
        ch.root.rotation.y = Math.PI;
        scene.add(ch.root);
        workers.push({
            ch,
            cur: restPose(),
            tgt: restPose(),
            anim: ANIMS[i],
            t: Math.random() * 5,
            blinkAt: 2 + Math.random() * 3,
            blinkEnd: 0,
        });
    });

    // ---------------------------------------------------------------- khung hình
    let W = 1;
    let H = 1;
    const resize = () => {
        W = Math.max(1, host.clientWidth);
        H = Math.max(1, host.clientHeight);
        renderer.setSize(W, H, false);
        camera.aspect = W / Math.max(1, H);
        camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(host);

    let visible = true;
    const io = new IntersectionObserver(
        (en) => (visible = en[0]?.isIntersecting ?? true),
    );
    io.observe(host);

    let raf = 0;
    let last = performance.now();
    const render = () => renderer.render(scene, camera);
    const frame = (ts: number) => {
        raf = requestAnimationFrame(frame);
        if (document.hidden || !visible) {
            last = ts;

            return;
        }
        const dt = Math.min(0.05, (ts - last) / 1000);
        last = ts;
        for (const w of workers) {
            w.t += dt;
            poseFor(w.anim, motion ? w.t : 0.5, true, w.tgt, w.t);
            applyPose(w.ch, w.cur, w.tgt, motion ? dt : 1);
            if (motion && w.t > w.blinkAt) {
                w.blinkEnd = w.t + 0.13;
                w.blinkAt = w.t + 2.2 + Math.random() * 3.3;
            }
            w.ch.face.set('focus', motion && w.t < w.blinkEnd, 0);
        }
        render();
    };
    if (motion) {
        raf = requestAnimationFrame(frame);
    } else {
        // không hoạt hình: vẫn đặt đúng dáng (ngồi làm việc) rồi vẽ một khung tĩnh.
        for (const w of workers) {
            poseFor(w.anim, 0.5, true, w.tgt, 0.5);
            applyPose(w.ch, w.cur, w.tgt, 1);
            w.ch.face.set('focus', false, 0);
        }
        render();
    }

    return {
        dispose() {
            cancelAnimationFrame(raf);
            ro.disconnect();
            io.disconnect();
            scene.traverse((ob) => {
                const m = ob as THREE.Mesh;
                if (m.geometry) {
                    m.geometry.dispose();
                }
                const mat = m.material as THREE.Material | THREE.Material[] | undefined;
                (Array.isArray(mat) ? mat : mat ? [mat] : []).forEach((x) => x.dispose());
            });
            kit.dispose();
            scene.clear();
            renderer.dispose();
            renderer.forceContextLoss();
            renderer.domElement.remove();
        },
    };
};

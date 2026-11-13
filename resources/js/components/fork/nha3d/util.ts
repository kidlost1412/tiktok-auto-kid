// Tiện ích dùng chung cho thế giới 3D "Khu Tự Trị": bảng màu, vật liệu toon, gộp hình tĩnh, texture vẽ bằng canvas.
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

export const C = {
    ink: 0x4a3868,
    cream: 0xfff6ea,
    creamDark: 0xf1e2cc,
    wallOut: 0xf6efff,
    lav: 0xe9dcff,
    lavMid: 0xcdb8f2,
    lavDeep: 0xb9a2ea,
    purple: 0x8a6fd6,
    purpleDeep: 0x6a52b8,
    trim: 0x7a5fd0,
    roofA: 0xa58bea,
    roofB: 0x8f74dc,
    wood: 0xd39c68,
    woodLight: 0xe8bd8c,
    woodDark: 0xa8764d,
    grass: 0xa9dc8a,
    grassDark: 0x92cd75,
    soil: 0xc09068,
    soilDark: 0x95694a,
    stone: 0xefe6d6,
    stoneDark: 0xd6cab6,
    water: 0x8fd6f2,
    leaf: 0x7bc67e,
    leaf2: 0x68b873,
    leaf3: 0x98d88a,
    pink: 0xff8fa3,
    pinkSoft: 0xffc2cf,
    yellow: 0xffd36a,
    mint: 0x7fd1c1,
    blue: 0x6eb5f2,
    orange: 0xff9f5a,
    red: 0xff6f7f,
    white: 0xffffff,
    dark: 0x3a3150,
    skin: 0xffdcc2,
};

export const FONT = '"Inter", "Segoe UI", system-ui, -apple-system, sans-serif';

export const clamp = (v: number, a: number, b: number) =>
    Math.min(b, Math.max(a, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
/** Giảm dần mượt về đích, độc lập khung hình. */
export const damp = (a: number, b: number, k: number, dt: number) =>
    lerp(a, b, 1 - Math.exp(-k * dt));
export const rand = (a: number, b: number) => a + Math.random() * (b - a);
export const pick = <T>(arr: readonly T[]): T =>
    arr[Math.floor(Math.random() * arr.length)];
/** Góc ngắn nhất từ a tới b. */
export const angleDelta = (a: number, b: number) => {
    let d = (b - a) % (Math.PI * 2);
    if (d > Math.PI) {
        d -= Math.PI * 2;
    }
    if (d < -Math.PI) {
        d += Math.PI * 2;
    }

    return d;
};
export const dampAngle = (a: number, b: number, k: number, dt: number) =>
    a + angleDelta(a, b) * (1 - Math.exp(-k * dt));

/** Kho tài nguyên GPU của một thế giới: giữ mọi geometry/material/texture tạo ra để giải phóng một lần khi rời trang. */
export class Kit {
    readonly geos = new Set<THREE.BufferGeometry>();
    readonly mats = new Set<THREE.Material>();
    readonly texs = new Set<THREE.Texture>();
    private toonCache = new Map<string, THREE.MeshToonMaterial>();
    readonly gradient: THREE.DataTexture;

    constructor() {
        // 4 bậc sáng mềm cho cảm giác hoạt hình nhưng không gắt.
        const steps = [118, 172, 222, 255];
        const data = new Uint8Array(steps.length * 4);
        steps.forEach((v, i) => data.set([v, v, v, 255], i * 4));
        this.gradient = new THREE.DataTexture(
            data,
            steps.length,
            1,
            THREE.RGBAFormat,
        );
        this.gradient.minFilter = THREE.NearestFilter;
        this.gradient.magFilter = THREE.NearestFilter;
        this.gradient.generateMipmaps = false;
        this.gradient.needsUpdate = true;
        this.texs.add(this.gradient);
    }

    geo<T extends THREE.BufferGeometry>(g: T): T {
        this.geos.add(g);

        return g;
    }

    mat<T extends THREE.Material>(m: T): T {
        this.mats.add(m);

        return m;
    }

    tex<T extends THREE.Texture>(t: T): T {
        this.texs.add(t);

        return t;
    }

    /** Vật liệu toon dùng chung theo màu (không đổi sau khi tạo). */
    toon(
        color: number,
        opts: { vertexColors?: boolean; side?: THREE.Side } = {},
    ): THREE.MeshToonMaterial {
        const k = `${color}|${opts.vertexColors ? 1 : 0}|${opts.side ?? 0}`;
        let m = this.toonCache.get(k);
        if (!m) {
            m = this.mat(
                new THREE.MeshToonMaterial({
                    color,
                    gradientMap: this.gradient,
                    vertexColors: !!opts.vertexColors,
                    side: opts.side ?? THREE.FrontSide,
                }),
            );
            this.toonCache.set(k, m);
        }

        return m;
    }

    /** Vật liệu toon riêng (để đổi màu/phát sáng từng cái). */
    toonOwn(
        color: number,
        extra: THREE.MeshToonMaterialParameters = {},
    ): THREE.MeshToonMaterial {
        return this.mat(
            new THREE.MeshToonMaterial({
                color,
                gradientMap: this.gradient,
                ...extra,
            }),
        );
    }

    basic(
        color: number,
        extra: THREE.MeshBasicMaterialParameters = {},
    ): THREE.MeshBasicMaterial {
        return this.mat(new THREE.MeshBasicMaterial({ color, ...extra }));
    }

    canvas(
        w: number,
        h: number,
        draw: (g: CanvasRenderingContext2D, w: number, h: number) => void,
    ): CanvasTex {
        const c = new CanvasTex(w, h, draw);
        this.tex(c.texture);

        return c;
    }

    dispose() {
        this.geos.forEach((g) => g.dispose());
        this.mats.forEach((m) => m.dispose());
        this.texs.forEach((t) => t.dispose());
        this.geos.clear();
        this.mats.clear();
        this.texs.clear();
        this.toonCache.clear();
    }
}

/** Texture vẽ bằng canvas 2D, vẽ lại được (bảng việc, mặt nhân vật, màn hình…). */
export class CanvasTex {
    readonly canvas: HTMLCanvasElement;
    readonly g: CanvasRenderingContext2D;
    readonly texture: THREE.CanvasTexture;

    constructor(
        readonly w: number,
        readonly h: number,
        private drawFn: (
            g: CanvasRenderingContext2D,
            w: number,
            h: number,
        ) => void,
    ) {
        this.canvas = document.createElement('canvas');
        this.canvas.width = w;
        this.canvas.height = h;
        this.g = this.canvas.getContext('2d')!;
        this.texture = new THREE.CanvasTexture(this.canvas);
        this.texture.colorSpace = THREE.SRGBColorSpace;
        this.texture.anisotropy = 4;
        this.redraw();
    }

    redraw(fn?: (g: CanvasRenderingContext2D, w: number, h: number) => void) {
        if (fn) {
            this.drawFn = fn;
        }
        this.g.clearRect(0, 0, this.w, this.h);
        this.drawFn(this.g, this.w, this.h);
        this.texture.needsUpdate = true;
    }
}

export const roundRect = (
    g: CanvasRenderingContext2D,
    x: number,
    y: number,
    w: number,
    h: number,
    r: number,
) => {
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
};

/** Cắt chữ cho vừa bề ngang canvas. */
export const fitText = (
    g: CanvasRenderingContext2D,
    text: string,
    maxW: number,
) => {
    if (g.measureText(text).width <= maxW) {
        return text;
    }
    let t = text;
    while (t.length > 1 && g.measureText(t + '…').width > maxW) {
        t = t.slice(0, -1);
    }

    return t + '…';
};

const _m = new THREE.Matrix4();
const _q = new THREE.Quaternion();
const _e = new THREE.Euler();
const _s = new THREE.Vector3();
const _p = new THREE.Vector3();
const _c = new THREE.Color();

export interface Place {
    x?: number;
    y?: number;
    z?: number;
    rx?: number;
    ry?: number;
    rz?: number;
    sx?: number;
    sy?: number;
    sz?: number;
}

export const placeMatrix = (p: Place) => {
    _p.set(p.x ?? 0, p.y ?? 0, p.z ?? 0);
    _q.setFromEuler(_e.set(p.rx ?? 0, p.ry ?? 0, p.rz ?? 0));
    _s.set(p.sx ?? 1, p.sy ?? 1, p.sz ?? 1);

    return _m.compose(_p, _q, _s);
};

/**
 * Gom nhiều hình tĩnh (mỗi hình một màu) thành MỘT mesh tô màu theo đỉnh → ít lệnh vẽ.
 * `ao`: làm tối nhẹ phần sát sàn (cảm giác đổ bóng góc) tính theo toạ độ y thế giới.
 */
export class Batch {
    private parts: THREE.BufferGeometry[] = [];

    add(
        geo: THREE.BufferGeometry,
        color: number,
        place: Place | THREE.Matrix4 = {},
        opts: {
            ao?: number;
            aoH?: number;
            shade?: number;
            dispose?: boolean;
        } = {},
    ) {
        let g = geo.index ? geo.toNonIndexed() : geo.clone();
        if (opts.dispose) {
            geo.dispose();
        }
        g.applyMatrix4(
            place instanceof THREE.Matrix4 ? place : placeMatrix(place),
        );
        for (const name of Object.keys(g.attributes)) {
            if (name !== 'position' && name !== 'normal') {
                g.deleteAttribute(name);
            }
        }
        if (!g.attributes.normal) {
            g.computeVertexNormals();
        }
        const pos = g.attributes.position;
        const col = new Float32Array(pos.count * 3);
        _c.setHex(color);
        const shade = opts.shade ?? 1;
        for (let i = 0; i < pos.count; i++) {
            let f = shade;
            if (opts.ao !== undefined) {
                const h = opts.aoH ?? 0.7;
                f *= 0.8 + 0.2 * clamp((pos.getY(i) - opts.ao) / h, 0, 1);
            }
            col[i * 3] = _c.r * f;
            col[i * 3 + 1] = _c.g * f;
            col[i * 3 + 2] = _c.b * f;
        }
        g.setAttribute('color', new THREE.BufferAttribute(col, 3));
        this.parts.push(g);
        if (g !== geo) {
            // geometry gốc do người gọi giữ; bản sao này sẽ bị gộp rồi bỏ
        }

        return this;
    }

    get empty() {
        return this.parts.length === 0;
    }

    build(
        kit: Kit,
        opts: {
            cast?: boolean;
            receive?: boolean;
            material?: THREE.Material;
        } = {},
    ): THREE.Mesh {
        const merged = this.parts.length
            ? mergeGeometries(this.parts, false)!
            : new THREE.BufferGeometry();
        this.parts.forEach((p) => p.dispose());
        this.parts = [];
        kit.geo(merged);
        merged.computeBoundingSphere();
        const mesh = new THREE.Mesh(
            merged,
            opts.material ?? kit.toon(0xffffff, { vertexColors: true }),
        );
        mesh.castShadow = !!opts.cast;
        mesh.receiveShadow = !!opts.receive;
        mesh.matrixAutoUpdate = false;
        mesh.updateMatrix();

        return mesh;
    }
}

/** Hình dùng lại nhiều lần (giữ trong kit). */
export class Shapes {
    private cache = new Map<string, THREE.BufferGeometry>();

    constructor(private kit: Kit) {}

    private get<T extends THREE.BufferGeometry>(k: string, make: () => T): T {
        let g = this.cache.get(k) as T | undefined;
        if (!g) {
            g = this.kit.geo(make());
            this.cache.set(k, g);
        }

        return g;
    }

    box(w = 1, h = 1, d = 1) {
        return this.get(
            `b${w},${h},${d}`,
            () => new THREE.BoxGeometry(w, h, d),
        );
    }

    sphere(r = 1, ws = 18, hs = 14) {
        return this.get(
            `s${r},${ws},${hs}`,
            () => new THREE.SphereGeometry(r, ws, hs),
        );
    }

    cyl(rt = 1, rb = 1, h = 1, seg = 16) {
        return this.get(
            `c${rt},${rb},${h},${seg}`,
            () => new THREE.CylinderGeometry(rt, rb, h, seg),
        );
    }

    capsule(r = 1, len = 1, cap = 6, seg = 12) {
        return this.get(
            `k${r},${len},${cap},${seg}`,
            () => new THREE.CapsuleGeometry(r, len, cap, seg),
        );
    }

    cone(r = 1, h = 1, seg = 14) {
        return this.get(
            `o${r},${h},${seg}`,
            () => new THREE.ConeGeometry(r, h, seg),
        );
    }

    torus(r = 1, t = 0.1, rs = 8, ts = 20, arc = Math.PI * 2) {
        return this.get(
            `t${r},${t},${rs},${ts},${arc}`,
            () => new THREE.TorusGeometry(r, t, rs, ts, arc),
        );
    }

    plane(w = 1, h = 1) {
        return this.get(`p${w},${h}`, () => new THREE.PlaneGeometry(w, h));
    }

    /** Hộp bo góc (dựng tay để khỏi kéo thêm module). */
    rbox(w: number, h: number, d: number, r = 0.06) {
        return this.get(`r${w},${h},${d},${r}`, () => roundedBox(w, h, d, r));
    }
}

/** Hộp bo góc: hình cầu nhỏ "kéo giãn" ra 8 góc — pháp tuyến mượt, đẹp với toon. */
export const roundedBox = (
    w: number,
    h: number,
    d: number,
    r: number,
    seg = 3,
) => {
    r = Math.min(r, w / 2 - 1e-3, h / 2 - 1e-3, d / 2 - 1e-3);
    const g = new THREE.SphereGeometry(r, seg * 4, seg * 2 + 2);
    const pos = g.attributes.position;
    const hx = w / 2 - r;
    const hy = h / 2 - r;
    const hz = d / 2 - r;
    for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i);
        const y = pos.getY(i);
        const z = pos.getZ(i);
        pos.setXYZ(
            i,
            x + Math.sign(x) * hx,
            y + (Math.abs(y) < 1e-6 ? 0 : Math.sign(y) * hy),
            z + Math.sign(z) * hz,
        );
    }
    g.computeVertexNormals();

    return g;
};

/** Thêm "viền mực" kiểu hoạt hình: mesh mặt sau phình theo pháp tuyến. */
export const outlineMaterial = (
    kit: Kit,
    color = C.ink,
    width = 0.018,
): THREE.MeshBasicMaterial => {
    const m = kit.basic(color, { side: THREE.BackSide });
    m.userData.width = { value: width };
    m.onBeforeCompile = (shader) => {
        shader.uniforms.outlineW = m.userData.width;
        shader.vertexShader = shader.vertexShader
            .replace(
                '#include <common>',
                '#include <common>\nuniform float outlineW;',
            )
            .replace(
                '#include <begin_vertex>',
                'vec3 transformed = position + normalize(normal) * outlineW;',
            );
    };

    return m;
};

/** Texture chấm tròn mềm (bóng dưới chân, quầng sáng). */
export const radialTexture = (
    kit: Kit,
    inner: string,
    outer: string,
    size = 128,
) =>
    kit.canvas(size, size, (g, w) => {
        const gr = g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
        gr.addColorStop(0, inner);
        gr.addColorStop(1, outer);
        g.fillStyle = gr;
        g.fillRect(0, 0, w, w);
    }).texture;

/** Trình duyệt có WebGL không (thử tạo ngữ cảnh rồi trả lại ngay). */
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

// Dàn nhân vật: ngoại hình từng người + Cú thông thái trên gác mái.
import * as THREE from 'three';

import type { Speech } from './speech';

import type { Talker } from './actor';
import type { ChibiSpec } from './chibi';
import { FA } from './layout';
import { C, Kit, outlineMaterial, rand, Shapes } from './util';

export const SPECS: Record<string, ChibiSpec> = {
    bienkich: {
        shirt: 0x7fc8a9,
        pants: 0x6a5a8a,
        shoes: 0x8a5a3a,
        hair: 0x8a5a3c,
        hairStyle: 'long',
        glasses: 0x8a6fd6,
        brows: 'soft',
        lashes: true,
        scarf: 0xffc2cf,
    },
    thuam: {
        shirt: 0xff6f8f,
        pants: 0x3a3150,
        shoes: 0xf4f0ff,
        hair: 0x2b2440,
        hairStyle: 'messy',
        hat: { kind: 'hood', color: 0xff6f8f },
        headphones: 0x9a7bff,
    },
    daodienA: {
        shirt: 0xf2b84b,
        pants: 0x4a3868,
        shoes: 0x3a3150,
        hair: 0x3b2a20,
        hairStyle: 'short',
        hat: { kind: 'beret', color: 0xd84a5a },
        brows: 'soft',
        scarf: 0xd84a5a,
    },
    daodienB: {
        shirt: 0xb7a2f0,
        pants: 0x3a5a9a,
        shoes: 0x3a3150,
        hair: 0xd98a4a,
        hairStyle: 'bob',
        hat: { kind: 'beret', color: 0x4a6ad8 },
        lashes: true,
    },
    thodung: {
        shirt: 0xff9f5a,
        pants: 0x3a5a9a,
        shoes: 0x46c08a,
        hair: 0x5ad1a4,
        hairStyle: 'spiky',
        hat: { kind: 'headband', color: 0xff5f6f },
    },
    giamkhao: {
        shirt: 0x7a5fd0,
        pants: 0x4a3868,
        shoes: 0x2b2440,
        hair: 0xdcd6ec,
        hairStyle: 'bun',
        glasses: 0x4a3868,
        bowtie: 0xff4f6f,
        brows: 'strict',
    },
    thukho: {
        shirt: 0xffd66b,
        pants: 0x8a5a3a,
        shoes: 0x5a3a2a,
        hair: 0x5a3a2a,
        hairStyle: 'short',
        hat: { kind: 'cap', color: 0xff8a3d },
        mustache: true,
        apron: 0xc8955b,
        skin: 0xf7d1b3,
    },
    chuquay: {
        shirt: 0x6eb5f2,
        pants: 0x3d6fb8,
        shoes: 0xff8fa3,
        hair: 0xffd36a,
        hairStyle: 'pony',
        lashes: true,
        apron: 0xffffff,
    },
    buuta: {
        shirt: 0x4a78d8,
        pants: 0x2f4fa0,
        shoes: 0x2b2440,
        hair: 0x3b2a20,
        hairStyle: 'short',
        hat: { kind: 'postcap', color: 0x3a5ac8 },
        satchel: 0xf2b84b,
    },
    // Kid — chủ xưởng: áo hoodie tím, mũ lưỡi trai vàng, khăn đỏ (có ngôi sao lơ lửng trên đầu)
    kid: {
        shirt: 0x8a6cff,
        sleeve: 0x7a5cf0,
        pants: 0x2f3b6b,
        shoes: 0xffffff,
        hair: 0x2b2440,
        hairStyle: 'short',
        hat: { kind: 'cap', color: 0xffc93c },
        scarf: 0xff5f7a,
        collar: 0xffe08a,
        brows: 'soft',
    },
};

export const NAMES: Record<string, string> = {
    bienkich: 'Biên kịch',
    thuam: 'Thu âm',
    daodienA: 'Đạo diễn A',
    daodienB: 'Đạo diễn B',
    thodung: 'Thợ dựng',
    giamkhao: 'Giám khảo',
    thukho: 'Thủ kho',
    chuquay: 'Chủ quầy',
    buuta: 'Bưu tá',
    cu: 'Cú thông thái',
    meo: 'Mèo',
};

/** Cú thông thái: tròn trịa, mũ tốt nghiệp, mắt to chớp chậm, thỉnh thoảng xoay đầu. */
export class Owl implements Talker {
    readonly key = 'cu';
    readonly root = new THREE.Group();
    alertUntil = 0;
    private head = new THREE.Group();
    private wingL: THREE.Mesh;
    private wingR: THREE.Mesh;
    private lids: THREE.Mesh[] = [];
    private sayText: string | null = null;
    /** Điều phối lời nói chung của cả xưởng. */
    speech: Speech | null = null;
    private sayUntil = 0;
    private headTarget = 0;
    private nextTurn = 3;
    private blinkAt = 2;
    private flap = 0;
    private outline: THREE.MeshBasicMaterial;
    sleeping = false;

    constructor(
        kit: Kit,
        S: Shapes,
        private now: () => number,
    ) {
        this.outline = outlineMaterial(kit, C.ink, 0.016);
        const pick = { kind: 'role', key: 'cu' };
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
            m.userData.pick = pick;
            parent.add(m);
            if (outline) {
                const o = new THREE.Mesh(geo, this.outline);
                o.raycast = () => undefined;
                m.add(o);
            }

            return m;
        };
        const body = 0x8f7ac8;
        part(S.sphere(0.42, 22, 16), body, this.root, { y: 0.42, sy: 1.1 });
        part(
            S.sphere(0.3, 18, 14),
            0xe9ddff,
            this.root,
            { y: 0.36, z: 0.18, sy: 1.1, sz: 0.7 },
            false,
        );
        this.wingL = part(S.sphere(0.2, 12, 10), 0x7a64b8, this.root, {
            x: 0.38,
            y: 0.42,
            sx: 0.45,
            sy: 1.1,
        });
        this.wingR = part(S.sphere(0.2, 12, 10), 0x7a64b8, this.root, {
            x: -0.38,
            y: 0.42,
            sx: 0.45,
            sy: 1.1,
        });
        for (const sx of [-1, 1]) {
            part(S.cone(0.06, 0.12, 6), C.orange, this.root, {
                x: sx * 0.12,
                y: 0.0,
                z: 0.15,
                rx: Math.PI,
            });
        }
        this.root.add(this.head);
        this.head.position.y = 0.9;
        part(S.sphere(0.34, 22, 16), body, this.head, { sy: 0.9 });
        for (const sx of [-1, 1]) {
            part(S.cone(0.09, 0.2, 8), body, this.head, {
                x: sx * 0.22,
                y: 0.3,
                rz: -sx * 0.4,
            });
            part(
                S.sphere(0.13, 16, 12),
                0xffffff,
                this.head,
                { x: sx * 0.13, y: 0.02, z: 0.26, sz: 0.5 },
                false,
            );
            part(
                S.torus(0.13, 0.02, 6, 20),
                0xffd36a,
                this.head,
                { x: sx * 0.13, y: 0.02, z: 0.3 },
                false,
            );
            part(
                S.sphere(0.07, 12, 10),
                0x2b2440,
                this.head,
                { x: sx * 0.13, y: 0.02, z: 0.31, sz: 0.5 },
                false,
            );
            part(
                S.sphere(0.022, 6, 5),
                0xffffff,
                this.head,
                { x: sx * 0.13 + 0.03, y: 0.06, z: 0.345 },
                false,
            );
            const lid = part(
                S.sphere(0.135, 14, 10),
                body,
                this.head,
                { x: sx * 0.13, y: 0.02, z: 0.27, sz: 0.55 },
                false,
            );
            lid.visible = false;
            this.lids.push(lid);
        }
        part(S.cone(0.05, 0.12, 6), C.orange, this.head, {
            y: -0.08,
            z: 0.33,
            rx: Math.PI / 2 + 0.3,
        });
        // mũ tốt nghiệp
        part(S.cyl(0.16, 0.18, 0.12, 14), 0x2b2440, this.head, { y: 0.3 });
        part(S.box(0.48, 0.03, 0.48), 0x2b2440, this.head, {
            y: 0.37,
            ry: 0.78,
        });
        part(
            S.cyl(0.012, 0.012, 0.2, 4),
            C.yellow,
            this.head,
            { x: 0.18, y: 0.28, z: 0.06 },
            false,
        );
        part(
            S.sphere(0.035, 6, 5),
            C.yellow,
            this.head,
            { x: 0.18, y: 0.17, z: 0.06 },
            false,
        );
        this.root.position.set(0, FA + 1.05, -1.3);
    }

    say(text: string, d = 4) {
        if (this.speech && !this.speech.allow('cu', text, 'chat')) {
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
            .add(new THREE.Vector3(0, 0.75, 0));
    }

    hop() {
        this.flap = 1.2;
    }

    setHighlight(on: boolean) {
        this.outline.color.setHex(on ? 0xffc93c : C.ink);
        this.outline.userData.width.value = on ? 0.034 : 0.016;
    }

    update(t: number, dt: number, motion: boolean) {
        const now = this.now();
        if (motion && now > this.nextTurn) {
            this.nextTurn = now + rand(3, 7);
            this.headTarget =
                this.headTarget !== 0
                    ? 0
                    : (Math.random() < 0.5 ? -1 : 1) * rand(0.6, 1.4);
        }
        this.head.rotation.y +=
            (this.headTarget - this.head.rotation.y) * Math.min(1, dt * 4);
        this.head.rotation.z = motion ? Math.sin(t * 0.8) * 0.08 : 0;
        if (now > this.blinkAt) {
            this.blinkAt = now + rand(2.5, 6);
        }
        const closed = this.sleeping || now > this.blinkAt - 0.18;
        this.lids.forEach((l) => (l.visible = closed));
        if (this.flap > 0 && motion) {
            this.flap -= dt;
            const f = Math.sin(t * 22) * 0.9;
            this.wingL.rotation.z = -0.3 - Math.abs(f);
            this.wingR.rotation.z = 0.3 + Math.abs(f);
            this.root.position.y =
                FA +
                1.05 +
                Math.sin((Math.max(0, this.flap) * Math.PI) / 1.2) * 0.25;
        } else {
            this.wingL.rotation.z = motion ? Math.sin(t * 1.5) * 0.05 : 0;
            this.wingR.rotation.z = -this.wingL.rotation.z;
            this.root.position.y = FA + 1.05;
        }
        this.root.scale.y = 1 + (motion ? Math.sin(t * 2) * 0.015 : 0);
    }
}

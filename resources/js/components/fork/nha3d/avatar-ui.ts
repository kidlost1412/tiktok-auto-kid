// Bảng "Nhân vật của tôi": đặt tên + chọn ngoại hình cho nhân vật chính, xem trước 3D xoay vòng, Ngẫu nhiên / Lưu / Huỷ.
// Lưu lên máy chủ (PUT /nha/nhan-vat/chinh) để đổi trình duyệt/máy vẫn giữ.
import * as THREE from 'three';

import {
    type AvatarCfg,
    DA,
    genderDefaults,
    MAU,
    normalizeAvatar,
    OPTS,
    randomAvatar,
    specFromAvatar,
} from './avatar';
import { applyPose, Chibi, poseFor, restPose } from './chibi';
import { Kit, Shapes } from './util';

const xsrf = () =>
    decodeURIComponent(document.cookie.match(/XSRF-TOKEN=([^;]+)/)?.[1] ?? '');

const esc = (s: string) =>
    s.replace(
        /[&<>"']/g,
        (c) =>
            ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;',
            })[c]!,
    );

export interface AvatarPanelOpts {
    host: HTMLElement;
    current: AvatarCfg;
    /** Đã lưu thành công trên máy chủ. */
    onSave: (cfg: AvatarCfg) => void;
    onClose: () => void;
}

export const openAvatarPanel = (o: AvatarPanelOpts) => {
    let cfg: AvatarCfg = { ...o.current };
    const el = document.createElement('div');
    el.className = 'n3-av';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', 'Nhân vật của tôi');
    o.host.append(el);

    // ---------------------------------------------------------------- xem trước 3D
    const kit = new Kit();
    const shapes = new Shapes(kit);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff, 0xd8c8ff, 1.6));
    const sun = new THREE.DirectionalLight(0xfff1dc, 1.8);
    sun.position.set(2, 4, 3);
    scene.add(sun);
    const cam = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
    cam.position.set(0, 1.0, 4.1);
    cam.lookAt(0, 0.78, 0);
    const disc = new THREE.Mesh(
        shapes.cyl(0.62, 0.66, 0.06, 32),
        kit.toon(0xe9ddff),
    );
    disc.position.y = -0.03;
    scene.add(disc);
    let chibi: Chibi | null = null;
    const cur = restPose();
    const tgt = restPose();
    const rebuild = () => {
        chibi?.dispose();
        chibi = new Chibi(kit, shapes, specFromAvatar(cfg), 1.32);
        chibi.face.set(cfg.mat);
        scene.add(chibi.root);
    };

    // ---------------------------------------------------------------- biểu mẫu
    const swatches = (
        field: keyof AvatarCfg,
        table: Record<string, { hex: number; ten: string }>,
    ) =>
        `<div class="n3-av-sw">${Object.entries(table)
            .map(
                ([k, v]) =>
                    `<button type="button" data-f="${field}" data-v="${k}" title="${esc(v.ten)}" aria-label="${esc(v.ten)}" style="--c:#${v.hex.toString(16).padStart(6, '0')}"></button>`,
            )
            .join('')}</div>`;
    const chips = (field: keyof typeof OPTS) =>
        `<div class="n3-av-ch">${OPTS[field]
            .map(
                ([k, t]) =>
                    `<button type="button" data-f="${field}" data-v="${k}">${esc(t)}</button>`,
            )
            .join('')}</div>`;
    const row = (label: string, body: string) =>
        `<div class="n3-av-row"><div class="n3-av-lb">${label}</div>${body}</div>`;
    el.innerHTML = `
        <div class="n3-av-card">
            <div class="n3-av-head">🧑 Nhân vật của tôi</div>
            <div class="n3-av-body">
                <div class="n3-av-prev"></div>
                <div class="n3-av-form">
                    ${row('Giới tính', chips('gioi'))}
                    ${row('Tên', '<input class="n3-av-name" maxlength="20" autocomplete="off" spellcheck="false">')}
                    ${row('Màu da', swatches('da', DA))}
                    ${row('Kiểu tóc', chips('toc'))}
                    ${row('Màu tóc', swatches('mau_toc', MAU))}
                    ${row('Mũ', chips('mu'))}
                    ${row('Màu mũ / phụ kiện', swatches('mau_mu', MAU))}
                    ${row('Áo', chips('ao'))}
                    ${row('Màu áo', swatches('mau_ao', MAU))}
                    ${row('Quần / váy', chips('quan'))}
                    ${row('Màu quần / váy', swatches('mau_quan', MAU))}
                    ${row('Màu giày', swatches('mau_giay', MAU))}
                    ${row('Phụ kiện', chips('phu_kien'))}
                    ${row('Nét mặt', chips('mat'))}
                    ${row('Biểu tượng trên đầu', chips('bieu_tuong'))}
                </div>
            </div>
            <div class="n3-av-msg" role="status"></div>
            <div class="n3-av-foot">
                <button type="button" class="n3-av-rand">🎲 Ngẫu nhiên</button>
                <span></span>
                <button type="button" class="n3-av-cancel">Huỷ</button>
                <button type="button" class="n3-av-save">💾 Lưu</button>
            </div>
        </div>`;
    const prev = el.querySelector('.n3-av-prev') as HTMLDivElement;
    prev.append(renderer.domElement);
    const name = el.querySelector('.n3-av-name') as HTMLInputElement;
    const msg = el.querySelector('.n3-av-msg') as HTMLDivElement;
    const saveBtn = el.querySelector('.n3-av-save') as HTMLButtonElement;

    const sync = () => {
        el.querySelectorAll<HTMLButtonElement>('button[data-f]').forEach(
            (b) => {
                const on =
                    (cfg as unknown as Record<string, string>)[b.dataset.f!] ===
                    b.dataset.v;
                b.classList.toggle('on', on);
                b.setAttribute('aria-pressed', String(on));
            },
        );
        if (name.value !== cfg.ten) {
            name.value = cfg.ten;
        }
    };
    const change = (p: Partial<AvatarCfg>) => {
        cfg = { ...cfg, ...p };
        sync();
        rebuild();
    };
    el.addEventListener('click', (e) => {
        const b = (e.target as HTMLElement).closest(
            'button[data-f]',
        ) as HTMLButtonElement | null;
        if (!b) {
            return;
        }
        const f = b.dataset.f as keyof AvatarCfg;
        if (f === 'gioi') {
            change(genderDefaults(b.dataset.v as AvatarCfg['gioi']));
        } else {
            change({ [f]: b.dataset.v } as Partial<AvatarCfg>);
        }
    });
    name.addEventListener('input', () => {
        cfg = { ...cfg, ten: name.value };
    });
    // gõ phím trong bảng không làm Kid đi/không bấm phím tắt
    el.addEventListener('keydown', (e) => {
        e.stopPropagation();
        if (e.key === 'Escape') {
            close();
        }
    });
    el.addEventListener('keyup', (e) => e.stopPropagation());
    (el.querySelector('.n3-av-rand') as HTMLButtonElement).addEventListener(
        'click',
        () => change(randomAvatar(cfg)),
    );
    (el.querySelector('.n3-av-cancel') as HTMLButtonElement).addEventListener(
        'click',
        () => close(),
    );
    saveBtn.addEventListener('click', async () => {
        const ten = cfg.ten.trim();
        if (!ten) {
            msg.textContent = 'Đặt tên cho nhân vật trước nha!';
            name.focus();

            return;
        }
        saveBtn.disabled = true;
        msg.textContent = 'Đang lưu…';
        try {
            const body = { ...cfg, ten };
            delete body.v;
            const r = await fetch('/nha/nhan-vat/chinh', {
                method: 'PUT',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-XSRF-TOKEN': xsrf(),
                },
                body: JSON.stringify(body),
            });
            const j = (await r.json().catch(() => null)) as {
                avatar?: unknown;
                errors?: Record<string, string[]>;
            } | null;
            if (!r.ok) {
                msg.textContent =
                    r.status === 422 && j?.errors?.ten
                        ? 'Tên chỉ gồm chữ, số, khoảng trắng (tối đa 20 ký tự).'
                        : 'Chưa lưu được, thử lại nha.';
                saveBtn.disabled = false;

                return;
            }
            o.onSave(normalizeAvatar(j?.avatar ?? body));
            close();
        } catch {
            msg.textContent = 'Mất kết nối, chưa lưu được.';
            saveBtn.disabled = false;
        }
    });

    // ---------------------------------------------------------------- vòng lặp xem trước
    let raf = 0;
    let t = 0;
    let last = performance.now();
    let open = true;
    const loop = (ts: number) => {
        raf = requestAnimationFrame(loop);
        const dt = Math.min(0.05, (ts - last) / 1000);
        last = ts;
        t += dt;
        const w = Math.max(1, prev.clientWidth);
        const h = Math.max(1, prev.clientHeight);
        const c = renderer.domElement;
        if (
            c.width !== Math.round(w * renderer.getPixelRatio()) ||
            c.height !== Math.round(h * renderer.getPixelRatio())
        ) {
            renderer.setSize(w, h, false);
            cam.aspect = w / h;
            cam.updateProjectionMatrix();
        }
        if (chibi) {
            chibi.root.rotation.y = Math.sin(t * 0.6) * 0.7;
            poseFor(
                Math.floor(t / 4) % 3 === 2 ? 'wave' : 'idle',
                t,
                false,
                tgt,
            );
            applyPose(chibi, cur, tgt, dt);
            chibi.face.set(cfg.mat, t % 3.2 < 0.12, 0);
        }
        renderer.render(scene, cam);
    };

    function close() {
        if (!open) {
            return;
        }
        open = false;
        cancelAnimationFrame(raf);
        chibi?.dispose();
        scene.traverse((ob) => {
            const m = ob as THREE.Mesh;
            m.geometry?.dispose();
        });
        kit.dispose();
        renderer.dispose();
        renderer.forceContextLoss();
        el.remove();
        o.onClose();
    }

    sync();
    rebuild();
    raf = requestAnimationFrame(loop);
    setTimeout(() => name.focus({ preventScroll: true }), 50);

    return { close };
};

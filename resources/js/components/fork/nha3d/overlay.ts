// Lớp HTML phủ lên khung 3D: bong bóng lời nói, dấu "!" khi lỗi, chú thích khi rê chuột.
// Vị trí tính lại mỗi khung hình từ toạ độ 3D; ẩn khi bị tường/sàn che hoặc ra ngoài khung.
import * as THREE from 'three';

import type { Talker } from './actor';

interface Slot {
    el: HTMLDivElement;
    text: HTMLSpanElement;
    alert: HTMLDivElement;
    badge: HTMLButtonElement;
    badgeN: number;
    cur: string | null;
    w: number;
    h: number;
    hidden: boolean;
    checkAt: number;
    occluded: boolean;
}

const _p = new THREE.Vector3();
const _ndc = new THREE.Vector2();

export class Overlay {
    readonly el: HTMLDivElement;
    private tip: HTMLDivElement;
    private slots = new Map<string, Slot>();
    private ray = new THREE.Raycaster();
    /** Số việc chờ theo khoá nhân vật (huy hiệu đỏ trên đầu). */
    private counts = new Map<string, number>();
    /** Bấm huy hiệu = bấm nhân vật. */
    onBadge: ((key: string) => void) | null = null;

    constructor(
        host: HTMLElement,
        private camera: THREE.Camera,
        private occluders: THREE.Object3D[],
    ) {
        this.el = document.createElement('div');
        this.el.className = 'n3-overlay';
        this.el.setAttribute('aria-hidden', 'true');
        host.appendChild(this.el);
        this.tip = document.createElement('div');
        this.tip.className = 'n3-tip';
        this.tip.setAttribute('role', 'tooltip');
        this.tip.style.display = 'none';
        host.appendChild(this.tip);
    }

    private slot(key: string): Slot {
        let s = this.slots.get(key);
        if (!s) {
            const el = document.createElement('div');
            el.className = 'n3-bubble';
            const text = document.createElement('span');
            el.appendChild(text);
            const alert = document.createElement('div');
            alert.className = 'n3-alert';
            alert.textContent = '!';
            const badge = document.createElement('button');
            badge.type = 'button';
            badge.className = 'n3-badge';
            badge.addEventListener('click', () => this.onBadge?.(key));
            this.el.appendChild(el);
            this.el.appendChild(alert);
            this.el.appendChild(badge);
            s = {
                el,
                text,
                alert,
                badge,
                badgeN: 0,
                cur: null,
                w: 0,
                h: 0,
                hidden: true,
                checkAt: 0,
                occluded: false,
            };
            el.style.display = 'none';
            alert.style.display = 'none';
            badge.style.display = 'none';
            this.slots.set(key, s);
        }

        return s;
    }

    /** Đặt số việc chờ (khoá nhân vật → số); bỏ qua số <= 0. */
    setCounts(counts: Record<string, number>) {
        this.counts.clear();
        for (const k of Object.keys(counts)) {
            if (counts[k] > 0) {
                this.counts.set(k, counts[k]);
            }
        }
    }

    update(talkers: Talker[], now: number, width: number, height: number) {
        const placed: {
            x: number;
            y: number;
            w: number;
            h: number;
            s: Slot;
        }[] = [];
        for (const t of talkers) {
            const s = this.slot(t.key);
            const text = t.bubble();
            const alert = now < t.alertUntil;
            const n = this.counts.get(t.key) ?? 0;
            if (!text && !alert && n === 0) {
                if (!s.hidden) {
                    s.el.style.display = 'none';
                    s.alert.style.display = 'none';
                    s.badge.style.display = 'none';
                    s.hidden = true;
                }
                continue;
            }
            t.anchor(_p);
            // che khuất (kiểm tra thưa cho nhẹ)
            if (now > s.checkAt) {
                s.checkAt = now + 0.25 + Math.random() * 0.1;
                s.occluded = this.isOccluded(_p);
            }
            _p.project(this.camera);
            const x = (_p.x * 0.5 + 0.5) * width;
            const y = (-_p.y * 0.5 + 0.5) * height;
            const off =
                _p.z > 1 ||
                x < -40 ||
                x > width + 40 ||
                y < -10 ||
                y > height + 60;
            if (off || s.occluded) {
                s.el.style.display = 'none';
                s.alert.style.display = 'none';
                s.badge.style.display = 'none';
                s.hidden = true;
                continue;
            }
            s.hidden = false;
            if (n > 0) {
                if (s.badgeN !== n) {
                    s.badgeN = n;
                    s.badge.textContent = n > 99 ? '99+' : String(n);
                }
                s.badge.style.display = 'grid';
                s.badge.style.transform = `translate(${Math.round(x + 17)}px, ${Math.round(y - 6)}px)`;
            } else {
                s.badge.style.display = 'none';
            }
            if (alert) {
                s.alert.style.display = 'grid';
                s.alert.style.transform = `translate(${Math.round(x - 15)}px, ${Math.round(y - (text ? 4 : 30))}px)`;
            } else {
                s.alert.style.display = 'none';
            }
            if (!text) {
                s.el.style.display = 'none';
                continue;
            }
            if (s.cur !== text) {
                s.cur = text;
                s.text.textContent = text;
                s.el.style.display = 'block';
                s.el.classList.remove('n3-pop');
                void s.el.offsetWidth;
                s.el.classList.add('n3-pop');
                s.w = s.el.offsetWidth;
                s.h = s.el.offsetHeight;
            }
            // mờ dần nửa giây cuối
            const left = t.bubbleLeft?.() ?? 99;
            s.el.style.opacity =
                left < 0.6 ? String(Math.max(0, left / 0.6)) : '';
            s.el.style.display = 'block';
            placed.push({ x, y, w: s.w, h: s.h, s });
        }
        // tránh chồng lên nhau: bong bóng thấp hơn đẩy cái kia lên
        placed.sort((a, b) => b.y - a.y);
        for (let i = 0; i < placed.length; i++) {
            const a = placed[i];
            for (let j = 0; j < i; j++) {
                const b = placed[j];
                const ax0 = a.x - a.w / 2;
                const bx0 = b.x - b.w / 2;
                const ayTop = a.y - a.h - 10;
                const byTop = b.y - b.h - 10;
                const overlapX = ax0 < bx0 + b.w + 4 && bx0 < ax0 + a.w + 4;
                const overlapY = ayTop < b.y - 6 && byTop < a.y - 6;
                if (overlapX && overlapY) {
                    a.y = Math.min(a.y, byTop - 2);
                }
            }
        }
        for (const p of placed) {
            const left = Math.min(Math.max(p.x - p.w / 2, 4), width - p.w - 4);
            const tail = Math.min(Math.max(p.x - left, 14), p.w - 14);
            p.s.el.style.setProperty('--tail', `${tail}px`);
            p.s.el.style.transform = `translate(${Math.round(left)}px, ${Math.round(p.y - p.h - 10)}px)`;
        }
    }

    private isOccluded(p: THREE.Vector3): boolean {
        const q = p.clone().project(this.camera);
        _ndc.set(q.x, q.y);
        this.ray.setFromCamera(_ndc, this.camera);
        const dist = p
            .clone()
            .sub(this.ray.ray.origin)
            .dot(this.ray.ray.direction);
        const hits = this.ray.intersectObjects(this.occluders, false);

        return hits.length > 0 && hits[0].distance < dist - 0.3;
    }

    showTip(x: number, y: number, title: string, text: string) {
        this.tip.innerHTML = '';
        const b = document.createElement('b');
        b.textContent = title;
        const s = document.createElement('span');
        s.textContent = text;
        this.tip.append(b, s);
        this.tip.style.display = 'block';
        const host = this.tip.parentElement!;
        const w = this.tip.offsetWidth;
        const left = Math.min(Math.max(x - w / 2, 6), host.clientWidth - w - 6);
        const top = Math.max(6, y - this.tip.offsetHeight - 18);
        this.tip.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;
    }

    hideTip() {
        this.tip.style.display = 'none';
    }

    dispose() {
        this.el.remove();
        this.tip.remove();
        this.counts.clear();
        this.onBadge = null;
        this.slots.clear();
    }
}

// Sếp (Kid) tương tác với cả nhà: đứng gần ai thì hiện bảng hành động (phím 1–9, Tab để xem thêm, bấm chuột cũng được).
// Mỗi hành động có động tác + phản ứng theo tính cách (hoạt hình vui nhộn, không ai đau thật), và mọi người nhớ
// sếp vừa làm gì với mình một lúc (hay bị cốc thì tránh mặt, hay được khen thì chào nồng nhiệt). Việc thật luôn ưu tiên.
import * as THREE from 'three';

import { lineFor } from '../nha/loi-thoai';
import type { Actor, Step } from './actor';
import { NAMES } from './cast';
import type { Cat } from './cat';
import type { Director } from './director';
import type { Effects } from './effects';
import type { KidControl } from './kid';
import { POND, room } from './layout';
import type { NavGraph } from './nav';
import type { Pond } from './pond';
import { type Kit, pick, rand, type Shapes } from './util';
import type { Wings } from './wings';
import type { World } from './world';

export interface InteractDeps {
    host: HTMLElement;
    kid: KidControl;
    kidActor: Actor;
    A: Record<string, Actor>;
    cat: Cat;
    director: Director;
    fx: Effects;
    nav: NavGraph;
    now: () => number;
    hour: () => number;
    motion: boolean;
    wings: Wings;
    world: World;
    kit: Kit;
    shapes: Shapes;
    scene: THREE.Scene;
    pond: Pond;
}

interface Act {
    icon: string;
    label: string;
    run: () => void;
}

type Target =
    | { kind: 'actor'; a: Actor }
    | { kind: 'cat' }
    | { kind: 'all' }
    | null;

const ROLE = (k: string) => (k.startsWith('daodien') ? 'daodien' : k);
/** Ai hay đuổi theo sếp khi bị chọc/đá. */
const CHASERS = new Set(['thuam', 'daodienA', 'daodienB', 'buuta']);
const BLUSHERS = new Set(['bienkich', 'chuquay']);
const SASSY = new Set(['thuam', 'giamkhao']);

const v3 = () => new THREE.Vector3();
/** Đứng gần bờ ao (để hiện "Đẩy xuống ao"). */
const nearPond = (p: THREE.Vector3) =>
    Math.hypot(
        (p.x - POND.x) / (POND.rx + 2.2),
        (p.z - POND.z) / (POND.rz + 2.2),
    ) < 1;

export class Interact {
    private el: HTMLDivElement;
    private head: HTMLDivElement;
    private list: HTMLDivElement;
    private allBtn: HTMLButtonElement;
    private flash: HTMLDivElement;
    private target: Target = null;
    private targetKey = '';
    private page = 0;
    private allOpen = false;
    private busyUntil = 0;
    private acts: Act[] = [];
    private relShown = 0;
    private photo: {
        phase: 'gather' | 'count' | 'shoot' | 'done';
        t: number;
        who: Actor[];
        ready: Set<Actor>;
        shoot: boolean;
        count: number;
    } | null = null;
    private party = 0;
    private partyNote = 0;
    private bowl: THREE.Object3D | null = null;

    constructor(private d: InteractDeps) {
        const el = document.createElement('div');
        el.className = 'n3-acts';
        el.style.display = 'none';
        this.head = document.createElement('div');
        this.head.className = 'n3-acts-h';
        this.list = document.createElement('div');
        this.list.className = 'n3-acts-l';
        el.append(this.head, this.list);
        this.el = el;
        this.allBtn = document.createElement('button');
        this.allBtn.type = 'button';
        this.allBtn.className = 'n3-all';
        this.allBtn.innerHTML = '🎉 Cả nhà <kbd>Q</kbd>';
        this.allBtn.addEventListener('click', () => this.toggleAll());
        this.flash = document.createElement('div');
        this.flash.className = 'n3-flash';
        d.host.append(el, this.allBtn, this.flash);
        this.list.addEventListener('click', (e) => {
            const b = (e.target as HTMLElement).closest(
                'button[data-i]',
            ) as HTMLButtonElement | null;
            if (b) {
                this.fire(Number(b.dataset.i));
            }
        });
    }

    dispose() {
        this.el.remove();
        this.allBtn.remove();
        this.flash.remove();
        if (this.bowl) {
            this.bowl.parent?.remove(this.bowl);
        }
    }

    // ---------------------------------------------------------------- tiện ích
    private get kidPos() {
        return this.d.kidActor.pos;
    }

    private headOf(a: Actor) {
        return () =>
            a.ch.head.getWorldPosition(v3()).add(new THREE.Vector3(0, 0.42, 0));
    }

    private kidSay(sit: string) {
        this.d.kidActor.say(
            lineFor('kid', { situation: `sep_${sit}`, hour: this.d.hour() }),
            undefined,
            'work',
        );
    }

    private catSay(sit: string, d = 3) {
        this.d.cat.say(
            lineFor('meo', { situation: sit, hour: this.d.hour() }),
            d,
            'reply',
        );
    }

    private line(a: Actor, sit: string) {
        return this.d.director.line(a, sit);
    }

    private sayStep(a: Actor, sit: string): Step {
        return { k: 'say', text: this.line(a, sit), prio: 'reply' };
    }

    /** Lấy người ra khỏi việc vặt; đang làm việc thật thì từ chối. */
    private take(a: Actor): boolean {
        if (!this.d.director.grab(a)) {
            a.say(this.line(a, 'ban_viec'), undefined, 'reply');

            return false;
        }

        return true;
    }

    private done(a: Actor): Step {
        return this.d.director.release(a);
    }

    private faceKid(): Step {
        return { k: 'face', at: () => this.kidPos };
    }

    /** Đuổi theo sếp vài bước (chạy rồi khựng lại giậm chân). */
    private chase(a: Actor): Step[] {
        const hop = (): Step => ({
            k: 'do',
            fn: () => {
                const dx = this.kidPos.x - a.pos.x;
                const dz = this.kidPos.z - a.pos.z;
                const dist = Math.hypot(dx, dz);
                if (dist > 0.7 && Math.abs(this.kidPos.y - a.pos.y) < 0.8) {
                    a.shove(
                        new THREE.Vector3(dx, 0, dz),
                        Math.min(1.4, dist - 0.6),
                        0.45,
                        'run',
                    );
                }
            },
        });

        return [
            hop(),
            { k: 'wait', d: 0.5 },
            hop(),
            { k: 'wait', d: 0.5 },
            hop(),
            { k: 'wait', d: 0.5 },
            { k: 'anim', a: 'stomp', d: 1.0, expr: 'annoyed' },
        ];
    }

    // ---------------------------------------------------------------- chọn đối tượng gần Kid
    /** Người gần nhất trong tầm với (cùng tầng). */
    nearest(): Actor | null {
        let best: Actor | null = null;
        let bd = 1.9;
        for (const a of Object.values(this.d.A)) {
            const dd = Math.hypot(
                a.pos.x - this.kidPos.x,
                a.pos.z - this.kidPos.z,
            );
            if (dd < bd && Math.abs(a.pos.y - this.kidPos.y) < 1) {
                bd = dd;
                best = a;
            }
        }

        return best;
    }

    private catNear() {
        const c = this.d.cat;
        if (c.rider === this.d.kidActor) {
            return true;
        }

        return (
            Math.hypot(c.pos.x - this.kidPos.x, c.pos.z - this.kidPos.z) <
                1.6 && Math.abs(c.pos.y - this.kidPos.y) < 1
        );
    }

    update(dt: number) {
        const a = this.nearest();
        let t: Target = null;
        if (this.allOpen) {
            t = { kind: 'all' };
        } else if (a) {
            t = { kind: 'actor', a };
        } else if (this.catNear()) {
            t = { kind: 'cat' };
        }
        const key =
            t?.kind === 'actor'
                ? `a:${t.a.key}`
                : t?.kind === 'cat'
                  ? `cat:${this.d.cat.rider ? 1 : 0}`
                  : (t?.kind ?? '');
        const rel =
            t?.kind === 'actor' ? Math.round(this.d.director.relOf(t.a)) : 0;
        if (key !== this.targetKey || rel !== this.relShown) {
            if (key !== this.targetKey) {
                this.page = 0;
            }
            this.targetKey = key;
            this.target = t;
            this.relShown = rel;
            this.render();
        }
        this.list.classList.toggle('n3-busy', this.d.now() < this.busyUntil);
        this.tickPhoto(dt);
        this.tickParty(dt);
    }

    private toggleAll() {
        this.allOpen = !this.allOpen;
        this.page = 0;
        this.allBtn.classList.toggle('on', this.allOpen);
        this.targetKey = '#';
    }

    /** Phím tắt; trả true nếu đã xử lý. */
    key(e: KeyboardEvent): boolean {
        if (e.type !== 'keydown') {
            return false;
        }
        if (e.code === 'KeyQ') {
            this.toggleAll();

            return true;
        }
        if (e.code === 'Escape' && this.allOpen) {
            this.toggleAll();

            return true;
        }
        if (!this.target) {
            return false;
        }
        if (e.code === 'Tab' || e.code === 'Digit0' || e.code === 'Numpad0') {
            this.page++;
            this.render();

            return true;
        }
        const m = /^(?:Digit|Numpad)([1-9])$/.exec(e.code);
        if (m) {
            const i = Number(m[1]) - 1;
            if (i < this.pageActs().length) {
                this.fire(i);

                return true;
            }
        }

        return false;
    }

    private pageActs() {
        const per = 9;
        const pages = Math.max(1, Math.ceil(this.acts.length / per));
        const p = this.page % pages;

        return this.acts.slice(p * per, p * per + per);
    }

    /** Người đang tương tác (để camera đóng khung cả hai). */
    focusA: Actor | null = null;
    focusUntil = 0;
    /** Gọi khi vừa làm một hành động với `a`: index.ts xoay camera cho thấy cả hai. */
    onFocus: ((a: Actor) => void) | null = null;

    get focus(): Actor | null {
        return this.focusA && this.d.now() < this.focusUntil
            ? this.focusA
            : null;
    }

    private fire(i: number) {
        const act = this.pageActs()[i];
        if (!act || this.d.now() < this.busyUntil) {
            return;
        }
        if (this.target?.kind === 'actor') {
            this.focusA = this.target.a;
            this.focusUntil = this.d.now() + 9;
            this.onFocus?.(this.target.a);
        }
        this.busyUntil = this.d.now() + 1.3;
        act.run();
        if (this.allOpen) {
            this.toggleAll();
        }
    }

    private render() {
        const t = this.target;
        if (!t) {
            this.el.style.display = 'none';
            this.acts = [];

            return;
        }
        this.acts = this.actsFor(t);
        if (t.kind === 'actor') {
            const r = this.d.director.relOf(t.a);
            const mood =
                r >= 3
                    ? ' 💖'
                    : r >= 1
                      ? ' ♥'
                      : r <= -3
                        ? ' 💢'
                        : r <= -1
                          ? ' 😒'
                          : '';
            this.head.textContent = `${NAMES[t.a.key] ?? t.a.key}${mood}`;
        } else if (t.kind === 'cat') {
            this.head.textContent = '🐱 Mèo';
        } else {
            this.head.textContent = '🎉 Cả nhà';
        }
        const per = 9;
        const pages = Math.max(1, Math.ceil(this.acts.length / per));
        const html = this.pageActs()
            .map(
                (a, i) =>
                    `<button type="button" class="n3-act" data-i="${i}"><kbd>${i + 1}</kbd>${a.icon} ${a.label}</button>`,
            )
            .join('');
        this.list.innerHTML =
            html +
            (pages > 1
                ? `<button type="button" class="n3-act n3-more" data-more="1"><kbd>Tab</kbd>Thêm ${(this.page % pages) + 1}/${pages}</button>`
                : '');
        const more = this.list.querySelector('[data-more]');
        more?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.page++;
            this.render();
        });
        this.el.style.display = 'flex';
    }

    private actsFor(t: NonNullable<Target>): Act[] {
        if (t.kind === 'cat') {
            const riding = this.d.cat.rider === this.d.kidActor;

            return [
                { icon: '🤚', label: 'Vuốt ve', run: () => this.catPet() },
                { icon: '🐟', label: 'Cho ăn', run: () => this.catFeed() },
                riding
                    ? {
                          icon: '⬇️',
                          label: 'Thả xuống',
                          run: () => this.catCarry(),
                      }
                    : {
                          icon: '🧺',
                          label: 'Bế lên vai',
                          run: () => this.catCarry(),
                      },
                { icon: '😼', label: 'Trêu mèo', run: () => this.catTease() },
            ];
        }
        if (t.kind === 'all') {
            return [
                {
                    icon: '📸',
                    label: 'Chụp ảnh tập thể',
                    run: () => this.photoStart(),
                },
                { icon: '🎵', label: 'Bật nhạc', run: () => this.partyStart() },
                {
                    icon: '🍚',
                    label: 'Gọi cả nhà ăn cơm',
                    run: () => this.meal(),
                },
                { icon: '🐱', label: 'Gọi mèo', run: () => this.callCat() },
            ];
        }
        const a = t.a;
        const extra: Act[] = [
            { icon: '🤣', label: 'Thọc lét', run: () => this.tickle(a) },
        ];
        if (a.pos.y < 0.2 && this.d.kidActor.pos.y < 0.2) {
            extra.push({
                icon: '🤸',
                label: 'Rủ lăn cỏ',
                run: () => this.rollTogether(a),
            });
        }
        if (nearPond(a.pos) && nearPond(this.d.kidActor.pos)) {
            extra.unshift({
                icon: '🌊',
                label: 'Đẩy xuống ao',
                run: () => this.pushPond(a),
            });
        }

        return [
            ...extra.filter((x) => x.icon === '🌊'),
            { icon: '👏', label: 'Khen', run: () => this.praise(a) },
            { icon: '😜', label: 'Trêu', run: () => this.tease(a) },
            { icon: '✊', label: 'Cốc đầu', run: () => this.bonk(a) },
            { icon: '🦶', label: 'Đá đít nhẹ', run: () => this.kick(a) },
            { icon: '😤', label: 'Mắng', run: () => this.scold(a) },
            { icon: '🙌', label: 'Đập tay', run: () => this.highfive(a) },
            { icon: '🤗', label: 'Ôm', run: () => this.hug(a) },
            { icon: '💼', label: 'Bắt đi làm', run: () => this.toWork(a) },
            { icon: '☕', label: 'Mời cà phê', run: () => this.coffee(a) },
            { icon: '😴', label: 'Cho nghỉ', run: () => this.rest(a) },
            { icon: '🎮', label: 'Rủ chơi', run: () => this.play(a) },
            { icon: '📄', label: 'Ném bóng giấy', run: () => this.paper(a) },
            ...extra.filter((x) => x.icon !== '🌊'),
        ];
    }

    /** Khóc nức nở: nước mắt văng hai bên trong `d` giây. */
    private cryFx(a: Actor, d: number) {
        const end = this.d.now() + d;
        const tick = () => {
            if (this.d.now() > end) {
                return;
            }
            this.d.fx.tears(
                this.headOf(a)().add(new THREE.Vector3(0, -0.45, 0)),
                a.rot,
            );
            this.d.director.later(0.28, tick);
        };
        tick();
    }

    private pushPond(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('kick', 0.55);
        this.kidSay('day_ao');
        this.d.director.relAdd(a, -1.2);
        if (!this.take(a)) {
            return;
        }
        let wet = false;
        this.d.director.later(0.3, () => {
            // đứng xa bờ quá thì bị đẩy lảo đảo tới mép rồi mới rơi
            wet = this.d.pond.plunge(a, {
                how: 'push',
                onSplash: () => a.say(this.line(a, 'roi_ao'), 2.4, 'reply'),
            });
        });
        a.push(
            { k: 'wait', d: 0.4 },
            {
                k: 'until',
                fn: () => !a.driver && !this.d.pond.busy.has(a),
                max: 14,
            },
            this.faceKid(),
            {
                k: 'do',
                fn: () => {
                    if (wet && this.d.director.relOf(a) > 1) {
                        a.say(this.line(a, 'len_bo_cuoi'), 3, 'reply');
                        a.act('laugh', 2.2, 'joy');
                    } else if (wet) {
                        a.say(this.line(a, 'len_bo_gian'), 3, 'reply');
                        this.d.fx.anger(this.headOf(a)());
                        a.act('stomp', 1.4, 'annoyed');
                    }
                },
            },
            { k: 'wait', d: 2.3 },
            ...(CHASERS.has(a.key) ? this.chase(a) : []),
            this.done(a),
        );
    }

    private tickle(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('rub', 1.4);
        this.kidSay('thoc_let');
        if (!this.take(a)) {
            return;
        }
        this.d.director.relAdd(a, 0.6);
        a.push(
            this.faceKid(),
            { k: 'stand' },
            { k: 'anim', a: 'laugh', d: 2.6, expr: 'joy' },
            this.sayStep(a, 'bi_thoc_let'),
            { k: 'anim', a: 'laugh', d: 1.4, expr: 'joy' },
            this.done(a),
        );
    }

    private rollTogether(a: Actor) {
        const K = this.d.kidActor;
        this.kidSay('lan_co');
        if (this.d.director.relOf(a) <= -3) {
            this.refuse(a, 'choi_tu_choi');

            return;
        }
        if (!this.take(a)) {
            return;
        }
        K.act('roll', 3.2);
        this.d.director.later(3.2, () =>
            K.chain([
                ['getup', 0.9],
                ['laugh', 1.6],
            ]),
        );
        a.push(
            { k: 'stand' },
            { k: 'anim', a: 'roll', d: 3.4, expr: 'joy' },
            { k: 'anim', a: 'getup', d: 0.9 },
            { k: 'anim', a: 'laugh', d: 1.8, expr: 'joy' },
            this.sayStep(a, 'lan_co'),
            this.done(a),
        );
    }

    // ---------------------------------------------------------------- hành động với người
    private praise(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('cheer', 1.2);
        this.kidSay('khen');
        this.d.director.relAdd(a, 1.5);
        if (!this.take(a)) {
            return;
        }
        const working = a.base === 'working';
        a.push(
            { k: 'wait', d: rand(0.7, 1.2) },
            this.faceKid(),
            {
                k: 'do',
                fn: () => {
                    this.d.fx.hearts(
                        this.headOf(a)().add(new THREE.Vector3(0, -0.2, 0)),
                        4,
                    );
                    this.d.fx.sparkle(this.headOf(a)(), 6);
                },
            },
            { k: 'anim', a: a.seated ? 'blush' : 'cheer', d: 1.6, expr: 'joy' },
            this.sayStep(a, 'khen'),
            { k: 'wait', d: 1.2 },
            ...(working
                ? ([
                      {
                          k: 'say',
                          text: this.line(a, 'hang_say'),
                          prio: 'work',
                      },
                  ] as Step[])
                : []),
            this.done(a),
        );
    }

    private tease(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('point', 1.2);
        this.kidSay('treu');
        this.d.director.relAdd(a, -0.5);
        if (!this.take(a)) {
            return;
        }
        const steps: Step[] = [{ k: 'wait', d: rand(0.6, 1.0) }];
        if (a.key === 'thodung') {
            steps.push(
                { k: 'expr', e: 'annoyed', d: 2 },
                this.sayStep(a, 'treu'),
            );
        } else if (BLUSHERS.has(a.key)) {
            steps.push(
                this.faceKid(),
                { k: 'do', fn: () => this.d.fx.sweat(this.headOf(a)()) },
                { k: 'anim', a: 'blush', d: 2.2, expr: 'love' },
                this.sayStep(a, 'treu'),
            );
        } else if (CHASERS.has(a.key) && !a.seated) {
            steps.push(
                this.faceKid(),
                { k: 'do', fn: () => this.d.fx.anger(this.headOf(a)()) },
                this.sayStep(a, 'treu'),
                ...this.chase(a),
            );
        } else {
            steps.push(
                this.faceKid(),
                { k: 'do', fn: () => this.d.fx.anger(this.headOf(a)()) },
                { k: 'anim', a: 'argue', d: 1.6, expr: 'annoyed' },
                this.sayStep(a, 'treu'),
            );
        }
        a.push(...steps, { k: 'wait', d: 0.8 }, this.done(a));
    }

    private bonk(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('bonk', 0.55);
        this.kidSay('coc');
        this.d.director.relAdd(a, -1.6);
        const grabbed = this.take(a);
        this.d.director.later(0.28, () => {
            this.d.fx.dizzy(this.headOf(a), 2.6);
            this.d.fx.puff(this.headOf(a)());
            a.setExpr('surprise', 1.2);
        });
        if (!grabbed) {
            return;
        }
        const steps: Step[] = [
            { k: 'wait', d: 0.3 },
            { k: 'anim', a: 'dizzy', d: 1.4, expr: 'surprise' },
            this.faceKid(),
            { k: 'anim', a: 'rub', d: 1.6, expr: 'sad' },
            this.sayStep(a, 'coc_dau'),
            { k: 'wait', d: 0.8 },
        ];
        if (this.d.director.relOf(a) <= -3 && !a.seated) {
            steps.push({
                k: 'do',
                fn: () =>
                    a.shove(
                        new THREE.Vector3(
                            a.pos.x - this.kidPos.x,
                            0,
                            a.pos.z - this.kidPos.z,
                        ),
                        1.3,
                        0.9,
                        'walk',
                    ),
            });
        }
        a.push(...steps, this.done(a));
    }

    private kick(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('kick', 0.55);
        this.kidSay('da');
        this.d.director.relAdd(a, -1.6);
        if (!this.take(a)) {
            return;
        }
        this.d.director.later(0.25, () => {
            a.shove(
                new THREE.Vector3(
                    a.pos.x - this.kidPos.x,
                    0,
                    a.pos.z - this.kidPos.z,
                ),
                1.0,
                0.45,
                'hop',
            );
            a.setExpr('surprise', 1.2);
            this.d.fx.puff(a.pos.clone().add(new THREE.Vector3(0, 0.6, 0)));
        });
        const steps: Step[] = [
            { k: 'wait', d: 0.75 },
            this.faceKid(),
            { k: 'do', fn: () => this.d.fx.anger(this.headOf(a)()) },
            { k: 'anim', a: 'stomp', d: 1.0, expr: 'annoyed' },
            this.sayStep(a, 'da_dit'),
        ];
        if (CHASERS.has(a.key) || Math.random() < 0.3) {
            steps.push(...this.chase(a));
        } else {
            steps.push({ k: 'anim', a: 'sulk', d: 1.6, expr: 'annoyed' });
        }
        a.push(...steps, this.done(a));
    }

    private scold(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('argue', 1.8);
        this.kidSay('mang');
        this.d.director.relAdd(a, -1);
        if (!this.take(a)) {
            return;
        }
        const steps: Step[] = [{ k: 'wait', d: rand(1.0, 1.5) }];
        if (SASSY.has(a.key)) {
            steps.push(
                this.faceKid(),
                {
                    k: 'anim',
                    a: 'argue',
                    d: 2,
                    expr: a.key === 'thuam' ? 'cocky' : 'annoyed',
                },
                this.sayStep(a, 'mang'),
            );
        } else if (a.key === 'thodung') {
            steps.push(this.sayStep(a, 'mang'), { k: 'anim', a: 'game', d: 2 });
        } else if (this.d.director.relOf(a) <= -2.5) {
            // bị mắng nặng nhiều lần: khóc nức nở
            steps.push(
                { k: 'do', fn: () => this.cryFx(a, 4.5) },
                { k: 'anim', a: 'cry', d: 2.2, expr: 'sad' },
                this.sayStep(a, 'khoc'),
                { k: 'anim', a: 'cry', d: 2.6, expr: 'sad' },
                { k: 'anim', a: 'sulk', d: 1.6, expr: 'sad' },
            );
        } else {
            steps.push(
                { k: 'do', fn: () => this.d.fx.rainCloud(this.headOf(a), 5) },
                this.sayStep(a, 'mang'),
                { k: 'anim', a: 'sulk', d: 4, expr: 'sad' },
            );
        }
        a.push(...steps, this.done(a));
    }

    private refuse(a: Actor, sit: string) {
        if (!this.take(a)) {
            return;
        }
        a.push(
            { k: 'wait', d: 0.6 },
            {
                k: 'face',
                rot: Math.atan2(
                    a.pos.x - this.kidPos.x,
                    a.pos.z - this.kidPos.z,
                ),
            },
            this.sayStep(a, sit),
            { k: 'anim', a: 'sulk', d: 1.8, expr: 'annoyed' },
            this.done(a),
        );
    }

    private highfive(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        this.kidSay('dap_tay');
        if (this.d.director.relOf(a) <= -3) {
            this.refuse(a, 'dap_tay_gian');

            return;
        }
        if (!this.take(a)) {
            return;
        }
        this.d.director.relAdd(a, 0.8);
        K.act('highfive', 1.3);
        a.push(
            this.faceKid(),
            { k: 'anim', a: 'highfive', d: 1.3, expr: 'joy' },
            {
                k: 'do',
                fn: () =>
                    this.d.fx.sparkle(
                        a.pos
                            .clone()
                            .lerp(this.kidPos, 0.5)
                            .add(new THREE.Vector3(0, 1.6, 0)),
                        8,
                    ),
            },
            this.sayStep(a, 'dap_tay'),
            { k: 'wait', d: 0.6 },
            this.done(a),
        );
    }

    private hug(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        this.kidSay('om');
        if (this.d.director.relOf(a) <= -3) {
            this.refuse(a, 'om_gian');

            return;
        }
        if (!this.take(a)) {
            return;
        }
        this.d.director.relAdd(a, 1);
        a.push(
            { k: 'stand' },
            {
                k: 'do',
                fn: () => {
                    const dx = this.kidPos.x - a.pos.x;
                    const dz = this.kidPos.z - a.pos.z;
                    const dist = Math.hypot(dx, dz);
                    if (dist > 0.7) {
                        a.shove(
                            new THREE.Vector3(dx, 0, dz),
                            dist - 0.62,
                            0.6,
                            'walk',
                        );
                    }
                },
            },
            { k: 'wait', d: 0.65 },
            this.faceKid(),
            {
                k: 'do',
                fn: () => {
                    K.faceTo(a.pos);
                    K.act('hug', 2.2);
                    this.d.fx.hearts(
                        a.pos
                            .clone()
                            .lerp(this.kidPos, 0.5)
                            .add(new THREE.Vector3(0, 1.5, 0)),
                        5,
                    );
                },
            },
            { k: 'anim', a: 'hug', d: 2.2, expr: 'love' },
            this.sayStep(a, 'om'),
            { k: 'wait', d: 0.6 },
            this.done(a),
        );
    }

    private toWork(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('point', 1.3);
        this.kidSay('di_lam');
        if (a.base === 'working' && a.atHome && !a.inScene) {
            this.d.director.relAdd(a, -0.2);
            this.d.director.later(rand(0.9, 1.4), () =>
                a.say(this.line(a, 'di_lam_dang_lam'), undefined, 'reply'),
            );

            return;
        }
        this.d.director.relAdd(a, -0.3);
        if (!this.take(a)) {
            return;
        }
        const work = a.home.work === 'idle' ? 'type' : a.home.work;
        a.push(
            { k: 'wait', d: rand(0.8, 1.2) },
            this.faceKid(),
            this.sayStep(a, 'di_lam'),
            {
                k: 'expr',
                e:
                    a.key === 'thodung'
                        ? 'sad'
                        : a.key === 'giamkhao'
                          ? 'annoyed'
                          : 'surprise',
                d: 1.5,
            },
            { k: 'stand' },
            { k: 'home', gait: 'walk' },
            { k: 'anim', a: work, d: rand(10, 14), expr: 'focus' },
            this.done(a),
        );
    }

    private coffee(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        this.kidSay('ca_phe');
        if (this.d.director.relOf(a) <= -3) {
            this.refuse(a, 'ca_phe_tu_choi');

            return;
        }
        if (!this.take(a)) {
            return;
        }
        this.d.director.relAdd(a, 1);
        const nav = this.d.nav;
        const q0 = nav.pos('phache.q0');
        const kidSpot = nav
            .pos('phache.q1')
            .clone()
            .add(new THREE.Vector3(-0.35, 0, 0.1));
        const near = () => this.kidPos.distanceTo(q0) < 2.4;
        a.push(
            { k: 'wait', d: rand(0.6, 1.0) },
            this.sayStep(a, 'ca_phe_nhan'),
            { k: 'stand' },
            { k: 'go', to: 'phache.q0' },
            { k: 'face', rot: Math.PI },
            { k: 'until', fn: near, max: 25 },
            { k: 'do', fn: () => (this.d.wings.state.coffee = this.d.now()) },
            { k: 'anim', a: 'idle', d: 2.4 },
            { k: 'item', item: 'mug' },
            this.faceKid(),
            { k: 'anim', a: 'drink', d: 2, expr: 'happy' },
            { k: 'say', text: this.line(a, 'ca_phe'), prio: 'reply' },
            { k: 'wait', d: 1.2 },
            { k: 'item', item: null },
            this.done(a),
        );
        this.d.kid.run(
            [
                { k: 'go', p: kidSpot },
                { k: 'face', p: q0 },
                { k: 'wait', d: 2.6 },
                { k: 'do', fn: () => K.hold('mug') },
                { k: 'face', p: () => a.pos },
                { k: 'anim', a: 'drink', d: 2 },
                { k: 'do', fn: () => K.hold(null) },
            ],
            nav,
        );
    }

    private rest(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('wave', 1.2);
        this.kidSay('nghi');
        if (!this.take(a)) {
            return;
        }
        this.d.director.relAdd(a, 1);
        const spot =
            a.key === 'thodung'
                ? 'nghi.bed'
                : pick([
                      'nghi.bean0',
                      'nghi.bean1',
                      'gt.so0',
                      'gt.so1',
                      'phache.sofa',
                  ]);
        const lie = spot === 'nghi.bed';
        a.push(
            { k: 'wait', d: rand(0.7, 1.1) },
            this.faceKid(),
            this.sayStep(a, 'nghi'),
            { k: 'stand' },
            ...this.d.director.seat(spot),
            {
                k: 'anim',
                a: lie ? 'lie' : 'sleep',
                d: rand(16, 22),
                expr: 'sleepy',
            },
            { k: 'stand' },
            { k: 'anim', a: 'stretch', d: 1.4 },
            this.done(a),
        );
    }

    private play(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        this.kidSay('choi');
        if (this.d.director.relOf(a) <= -3) {
            this.refuse(a, 'choi_tu_choi');

            return;
        }
        if (!this.take(a)) {
            return;
        }
        this.d.director.relAdd(a, 1);
        const nav = this.d.nav;
        const foos = a.pos.y > 0.15 || Math.random() < 0.5;
        const [mine, kids] = foos ? ['gt.fb1', 'gt.fb0'] : ['pp1', 'pp0'];
        const setOn = (on: boolean) => {
            if (foos) {
                this.d.wings.state.foosball = on;
            } else {
                this.d.world.play.pingpong = on;
            }
        };
        const kidAt = nav.pos(kids);
        const ready = () => this.kidPos.distanceTo(kidAt) < 0.9;
        const win = Math.random() < 0.5;
        this.d.director.setCleanup(a, () => setOn(false));
        a.push(
            { k: 'wait', d: rand(0.6, 1.0) },
            this.sayStep(a, 'choi_nhan'),
            { k: 'stand' },
            { k: 'go', to: mine, gait: 'run' },
            { k: 'face', rot: -Math.PI / 2 },
            { k: 'until', fn: ready, max: 30 },
            { k: 'do', fn: () => setOn(true) },
            { k: 'anim', a: foos ? 'swing' : 'paddle', d: 9 },
            { k: 'do', fn: () => setOn(false) },
            this.faceKid(),
            {
                k: 'anim',
                a: win ? 'cheer' : 'stomp',
                d: 1.5,
                expr: win ? 'joy' : 'annoyed',
            },
            {
                k: 'say',
                text: this.line(a, win ? 'choi_thang' : 'choi_thua'),
                prio: 'reply',
            },
            { k: 'wait', d: 1 },
            this.done(a),
        );
        this.d.kid.run(
            [
                { k: 'go', p: kidAt.clone() },
                { k: 'face', p: () => a.pos },
                { k: 'anim', a: foos ? 'swing' : 'paddle', d: 9.5 },
                { k: 'anim', a: win ? 'sulk' : 'cheer', d: 1.6 },
            ],
            nav,
        );
    }

    private paper(a: Actor) {
        const K = this.d.kidActor;
        K.faceTo(a.pos);
        K.act('throw', 0.6);
        this.kidSay('nem');
        this.d.director.relAdd(a, -0.3);
        const from = () =>
            this.d.kidActor.ch.head
                .getWorldPosition(v3())
                .add(new THREE.Vector3(0, 0.2, 0));
        this.d.director.later(0.32, () => {
            this.d.fx.ball(from(), this.headOf(a)(), 0.55, () => {
                this.d.fx.puff(this.headOf(a)());
                a.setExpr('surprise', 1.2);
                if (!this.take(a)) {
                    return;
                }
                const back =
                    CHASERS.has(a.key) || SASSY.has(a.key) ? 0.75 : 0.35;
                const steps: Step[] = [
                    this.faceKid(),
                    this.sayStep(a, 'nem_giay'),
                    { k: 'anim', a: 'argue', d: 1.0, expr: 'annoyed' },
                ];
                if (
                    Math.random() < back &&
                    a.key !== 'giamkhao' &&
                    a.key !== 'thukho'
                ) {
                    steps.push(
                        { k: 'anim', a: 'throw', d: 0.6 },
                        {
                            k: 'do',
                            fn: () =>
                                this.d.fx.ball(
                                    this.headOf(a)(),
                                    from(),
                                    0.55,
                                    () => {
                                        this.d.fx.puff(from());
                                        K.setExpr('surprise', 1.4);
                                        K.act('dizzy', 1.0);
                                    },
                                ),
                        },
                        {
                            k: 'say',
                            text: this.line(a, 'nem_lai'),
                            prio: 'reply',
                        },
                        { k: 'anim', a: 'cheer', d: 1.0, expr: 'cocky' },
                    );
                }
                a.push(...steps, this.done(a));
            });
        });
    }

    // ---------------------------------------------------------------- mèo
    private catPet() {
        const K = this.d.kidActor;
        K.faceTo(this.d.cat.pos);
        K.act('pet', 2.6);
        this.kidSay('vuot');
        this.d.cat.petted(this.kidPos, 4.5);
        this.d.director.later(0.8, () => this.catSay('meo_vuot'));
    }

    private catFeed() {
        const K = this.d.kidActor;
        const c = this.d.cat;
        if (c.rider) {
            c.drop();
        }
        K.faceTo(c.pos);
        K.act('give', 1.2);
        this.kidSay('cho_an');
        // bát cá nhỏ trước mặt mèo
        if (this.bowl) {
            this.bowl.parent?.remove(this.bowl);
        }
        const S = this.d.shapes;
        const g = new THREE.Group();
        const bowl = new THREE.Mesh(
            S.cyl(0.13, 0.1, 0.06, 18),
            this.d.kit.toon(0xff8fa3),
        );
        const fish = new THREE.Mesh(
            S.sphere(0.06, 10, 8),
            this.d.kit.toon(0x8fd3ff),
        );
        fish.scale.set(1.6, 0.6, 0.8);
        fish.position.y = 0.05;
        bowl.position.y = 0.03;
        g.add(bowl, fish);
        g.traverse((o) => (o.raycast = () => undefined));
        const dir = Math.atan2(
            this.kidPos.x - c.pos.x,
            this.kidPos.z - c.pos.z,
        );
        g.position.set(
            c.pos.x + Math.sin(dir) * 0.3,
            c.pos.y,
            c.pos.z + Math.cos(dir) * 0.3,
        );
        this.d.scene.add(g);
        this.bowl = g;
        c.eat(5);
        this.d.director.later(0.9, () => this.catSay('meo_an'));
        this.d.director.later(5.6, () => {
            if (this.bowl === g) {
                g.parent?.remove(g);
                this.bowl = null;
            }
        });
    }

    private catCarry() {
        const c = this.d.cat;
        const K = this.d.kidActor;
        if (c.rider === K) {
            c.drop();
            this.kidSay('tha');
            this.d.director.later(0.6, () => this.catSay('meo_tha'));
        } else {
            K.faceTo(c.pos);
            c.ride(K);
            K.act('cheer', 0.9);
            this.kidSay('be');
            this.d.fx.hearts(c.anchor(v3()), 3);
            this.d.director.later(0.8, () => this.catSay('meo_be'));
        }
        this.targetKey = '#';
    }

    private catTease() {
        const K = this.d.kidActor;
        const c = this.d.cat;
        K.faceTo(c.pos);
        K.act('pet', 0.8);
        this.kidSay('treu_meo');
        this.d.director.later(0.45, () => {
            c.swat(this.kidPos);
            this.d.fx.anger(c.anchor(v3()));
            K.setExpr('surprise', 1.5);
            K.act('rub', 1.2);
            this.catSay('meo_treu');
        });
    }

    // ---------------------------------------------------------------- cả nhà
    private callCat() {
        this.kidSay('meo');
        this.d.cat.seekNow(this.d.kidActor);
        this.d.director.later(1.2, () => this.catSay('meo_goi'));
    }

    private meal() {
        this.kidSay('an');
        this.d.director.callMeal();
        const free = this.d.director.freeActors.slice(0, 2);
        free.forEach((a, i) =>
            this.d.director.later(1.2 + i * 1.3, () =>
                a.say(this.line(a, 'an_com_goi'), undefined, 'reply'),
            ),
        );
    }

    /** Ảnh tập thể: ai rảnh ra bãi cỏ trước hiên xếp hai hàng, sếp đứng chụp, đếm 3-2-1, tạo dáng. */
    private photoStart() {
        if (this.photo && this.photo.phase !== 'done') {
            return;
        }
        this.kidSay('chup');
        const cx = room('sanh').cx;
        const who = this.d.director.freeActors.filter((a) =>
            this.d.director.grab(a),
        );
        const spots: THREE.Vector3[] = [];
        for (const x of [-2.4, -1.2, 0, 1.2, 2.4]) {
            spots.push(new THREE.Vector3(cx + x, 0, 4.5));
        }
        for (const x of [-1.8, -0.6, 0.6, 1.8]) {
            spots.push(new THREE.Vector3(cx + x, 0, 3.6));
        }
        const st = {
            phase: 'gather' as const,
            t: 0,
            who,
            ready: new Set<Actor>(),
            shoot: false,
            count: 3,
        };
        this.photo = st;
        who.forEach((a, i) => {
            const spot = spots[i % spots.length];
            const node = this.d.nav.nearest(
                spot,
                (id) => this.d.nav.pos(id).y < 0.1 && !id.endsWith('.seat'),
            );
            a.push(
                { k: 'wait', d: rand(0.2, 1.0) },
                { k: 'stand' },
                { k: 'go', to: node, gait: 'run' },
                {
                    k: 'do',
                    fn: () => {
                        const dx = spot.x - a.pos.x;
                        const dz = spot.z - a.pos.z;
                        a.shove(
                            new THREE.Vector3(dx, 0, dz),
                            Math.hypot(dx, dz),
                            Math.max(0.3, Math.hypot(dx, dz) / 2),
                            'walk',
                        );
                    },
                },
                { k: 'wait', d: 1.6 },
                { k: 'face', rot: 0 },
                { k: 'do', fn: () => st.ready.add(a) },
                { k: 'until', fn: () => st.shoot, max: 30 },
                { k: 'anim', a: 'pose', d: 3, expr: 'joy' },
                { k: 'wait', d: rand(0.2, 0.8) },
                this.done(a),
            );
        });
        this.d.cat.visit(this.d.nav.nearest(new THREE.Vector3(cx, 0, 5.2)), 12);
        this.d.kid.run(
            [
                { k: 'go', p: new THREE.Vector3(cx, 0, 8.4) },
                { k: 'face', p: new THREE.Vector3(cx, 0, 4) },
            ],
            this.d.nav,
        );
    }

    private tickPhoto(dt: number) {
        const p = this.photo;
        if (!p || p.phase === 'done') {
            return;
        }
        p.t += dt;
        const kidReady = !this.d.kid.script.length && !this.d.kid.target;
        if (p.phase === 'gather') {
            if ((p.ready.size >= p.who.length && kidReady) || p.t > 22) {
                p.phase = 'count';
                p.t = 0;
                p.count = 3;
                this.showCount('3');
                this.d.kidActor.act('point', 3.2);
            }
        } else if (p.phase === 'count') {
            const n = 3 - Math.floor(p.t);
            if (n !== p.count && n > 0) {
                p.count = n;
                this.showCount(String(n));
            }
            if (p.t >= 3) {
                p.phase = 'shoot';
                p.shoot = true;
                this.showCount('📸');
                this.flash.classList.remove('go');
                void this.flash.offsetWidth;
                this.flash.classList.add('go');
                this.d.kidActor.act('pose', 2.5);
                this.d.fx.confetti(
                    new THREE.Vector3(room('sanh').cx, 2.4, 4.1),
                    70,
                    1.6,
                );
                p.who
                    .slice(0, 3)
                    .forEach((a, i) =>
                        this.d.director.later(0.4 + i * 0.9, () =>
                            a.say(this.line(a, 'chup_anh'), undefined, 'reply'),
                        ),
                    );
                this.d.director.later(1.6, () => this.showCount(''));
                p.phase = 'done';
            }
        }
    }

    private countEl: HTMLDivElement | null = null;
    private showCount(t: string) {
        if (!this.countEl) {
            this.countEl = document.createElement('div');
            this.countEl.className = 'n3-count';
            this.d.host.append(this.countEl);
        }
        this.countEl.textContent = t;
        this.countEl.style.display = t ? 'block' : 'none';
    }

    /** Bật nhạc: ai rảnh quanh đó nhảy một lúc, nốt nhạc bay quanh sếp. */
    private partyStart() {
        this.kidSay('nhac');
        const K = this.d.kidActor;
        K.act('dance', 10);
        this.party = 10;
        const near = this.d.director.freeActors.filter(
            (a) =>
                Math.hypot(a.pos.x - this.kidPos.x, a.pos.z - this.kidPos.z) <
                    16 && this.d.director.grab(a),
        );
        near.forEach((a, i) => {
            a.push(
                { k: 'wait', d: rand(0.3, 1.4) },
                { k: 'stand' },
                this.faceKid(),
                { k: 'anim', a: 'dance', d: rand(8, 10), expr: 'joy' },
                this.done(a),
            );
            if (i < 3) {
                this.d.director.later(1.5 + i * 2.2, () =>
                    a.say(this.line(a, 'nhay'), undefined, 'reply'),
                );
            }
        });
    }

    private tickParty(dt: number) {
        if (this.party <= 0) {
            return;
        }
        this.party -= dt;
        this.partyNote -= dt;
        if (this.partyNote <= 0) {
            this.partyNote = 0.35;
            this.d.fx.notes(
                this.kidPos
                    .clone()
                    .add(
                        new THREE.Vector3(
                            rand(-0.8, 0.8),
                            rand(1.2, 1.9),
                            rand(-0.5, 0.5),
                        ),
                    ),
            );
        }
    }

    // ---------------------------------------------------------------- lưu / khôi phục
    snapshot() {
        return { riding: this.d.cat.rider === this.d.kidActor };
    }

    restore(s: { riding?: boolean }) {
        if (s.riding) {
            this.d.cat.ride(this.d.kidActor);
        }
    }

    /** (gỡ lỗi) chạy một hành động theo tên với người `key`. */
    debug(action: string, key?: string) {
        const a = key ? this.d.A[key] : null;
        if (a) {
            this.focusA = a;
            this.focusUntil = this.d.now() + 9;
            this.onFocus?.(a);
        }
        const map: Record<string, () => void> = {
            khen: () => a && this.praise(a),
            treu: () => a && this.tease(a),
            coc: () => a && this.bonk(a),
            da: () => a && this.kick(a),
            mang: () => a && this.scold(a),
            dap_tay: () => a && this.highfive(a),
            om: () => a && this.hug(a),
            di_lam: () => a && this.toWork(a),
            ca_phe: () => a && this.coffee(a),
            nghi: () => a && this.rest(a),
            choi: () => a && this.play(a),
            nem: () => a && this.paper(a),
            ao: () => a && this.pushPond(a),
            thoc: () => a && this.tickle(a),
            lan: () => a && this.rollTogether(a),
            vuot: () => this.catPet(),
            cho_an: () => this.catFeed(),
            be: () => this.catCarry(),
            treu_meo: () => this.catTease(),
            chup: () => this.photoStart(),
            nhac: () => this.partyStart(),
            an: () => this.meal(),
            goi_meo: () => this.callCat(),
            menu: () => this.toggleAll(),
        };
        map[action]?.();
    }
}

// Mặt bằng ngôi nhà + sân vườn (một chỗ duy nhất cho mọi toạ độ) và đồ thị đi lại dựng từ đó.
import { NavGraph } from './nav';

export const RW = 5.2; // bề ngang một phòng
export const BAY = 3.6; // khoang cầu thang
export const X0 = -(RW * 4 + BAY) / 2; // mép trái trong nhà
export const X1 = -X0;
export const Z_BACK = -3.6; // mặt trong tường sau
export const Z_ROOM = 0.2; // mép trước các phòng = mép sàn tầng trên (để camera nhìn thấu vào phòng)
export const Z_FRONT = 2.0; // mép hiên tầng 1 (hiên không có mái che)
export const LANE1 = 0.8; // lối đi dọc hiên trước các phòng tầng 1
export const LANE1B = 1.65; // lối đi vòng trước chân cầu thang
export const LANE2 = -0.45; // lối đi xuyên các phòng tầng 2
export const DOOR2 = -0.95; // vách ngăn tầng 2 dừng ở đây; phía trước là cửa thông phòng
export const F1 = 0.3;
export const H = 3.2;
export const SLAB = 0.3;
export const F2 = F1 + H + SLAB;
export const FA = F2 + H + SLAB; // sàn gác mái
export const BAY_X = X0 + RW * 4; // vách giữa phòng 4 và khoang cầu thang
export const BAY_CX = BAY_X + BAY / 2;

// Cầu thang: 14 bậc, từ chân (z = STAIR_Z0) lên mép chiếu nghỉ (z = STAIR_Z1).
export const STAIR_N = 14;
export const STAIR_Z0 = 1.15;
export const STAIR_Z1 = -2.45;
export const STAIR_D = (STAIR_Z0 - STAIR_Z1) / STAIR_N;
export const STAIR_R = (F2 - F1) / STAIR_N;
export const STAIR_W = 2.4;

export const cx = (i: number) => X0 + (i + 0.5) * RW;

export type RoomKey =
    | 'giamkhao'
    | 'thukho'
    | 'sanh'
    | 'chuquay'
    | 'bienkich'
    | 'thuam'
    | 'daodien'
    | 'thodung';

export interface RoomDef {
    key: RoomKey;
    floor: 1 | 2;
    i: number;
    cx: number;
    fy: number;
    name: string;
    emoji: string;
    wall: number;
    wain: number;
    floorA: number;
    floorB: number;
    pick: string; // khoá DICH khi bấm vào phòng
}

export const ROOMS: RoomDef[] = [
    {
        key: 'giamkhao',
        floor: 1,
        i: 0,
        cx: cx(0),
        fy: F1,
        name: 'Phòng chấm',
        emoji: '🧐',
        wall: 0xf1e8ff,
        wain: 0xd9c8f7,
        floorA: 0xd8c3ee,
        floorB: 0xcdb5e6,
        pick: 'giamkhao',
    },
    {
        key: 'thukho',
        floor: 1,
        i: 1,
        cx: cx(1),
        fy: F1,
        name: 'Kho hàng',
        emoji: '📦',
        wall: 0xfff1de,
        wain: 0xefd2a8,
        floorA: 0xe2c49c,
        floorB: 0xd7b78e,
        pick: 'thukho',
    },
    {
        key: 'sanh',
        floor: 1,
        i: 2,
        cx: cx(2),
        fy: F1,
        name: 'Sảnh',
        emoji: '📋',
        wall: 0xf6efff,
        wain: 0xe2d4fa,
        floorA: 0xeadff7,
        floorB: 0xe0d2f2,
        pick: 'bang',
    },
    {
        key: 'chuquay',
        floor: 1,
        i: 3,
        cx: cx(3),
        fy: F1,
        name: 'Quầy giỏ hàng',
        emoji: '🛒',
        wall: 0xe5f7ef,
        wain: 0xc5ead9,
        floorA: 0xf3e6d2,
        floorB: 0xe9d9c1,
        pick: 'chuquay',
    },
    {
        key: 'bienkich',
        floor: 2,
        i: 0,
        cx: cx(0),
        fy: F2,
        name: 'Phòng viết',
        emoji: '✍️',
        wall: 0xfff4d8,
        wain: 0xf3dca6,
        floorA: 0xe5c08e,
        floorB: 0xdab381,
        pick: 'bienkich',
    },
    {
        key: 'thuam',
        floor: 2,
        i: 1,
        cx: cx(1),
        fy: F2,
        name: 'Phòng thu',
        emoji: '🎙️',
        wall: 0xffe6f0,
        wain: 0xf7c4d8,
        floorA: 0xd9c0e8,
        floorB: 0xceb3df,
        pick: 'thuam',
    },
    {
        key: 'daodien',
        floor: 2,
        i: 2,
        cx: cx(2),
        fy: F2,
        name: 'Phòng đạo diễn',
        emoji: '🎬',
        wall: 0xfff0e2,
        wain: 0xf3d3b5,
        floorA: 0xe8c79f,
        floorB: 0xdcb98f,
        pick: 'daodien',
    },
    {
        key: 'thodung',
        floor: 2,
        i: 3,
        cx: cx(3),
        fy: F2,
        name: 'Phòng dựng',
        emoji: '🛠️',
        wall: 0xe4ecff,
        wain: 0xc6d5f7,
        floorA: 0xc9cdea,
        floorB: 0xbcc1e2,
        pick: 'thodung',
    },
];
export const room = (k: RoomKey) => ROOMS.find((r) => r.key === k)!;

// Hai dãy nhà phụ một tầng (mái bằng làm sân thượng): trái = Bếp + Quầy pha chế, phải = Góc giải trí + Phòng nghỉ.
export const AW = 9.6;
export const XL0 = X0 - 0.3 - AW;
export const XL1 = X0 - 0.3;
export const XR0 = X1 + 0.3;
export const XR1 = X1 + 0.3 + AW;
export type WingKey = 'bep' | 'phache' | 'giaitri' | 'nghi';
export interface WingDef {
    key: WingKey;
    x0: number;
    x1: number;
    cx: number;
    name: string;
    emoji: string;
    wall: number;
    wain: number;
    floorA: number;
    floorB: number;
}
const wing = (
    key: WingKey,
    x0: number,
    x1: number,
    name: string,
    emoji: string,
    wall: number,
    wain: number,
    floorA: number,
    floorB: number,
): WingDef => ({
    key,
    x0,
    x1,
    cx: (x0 + x1) / 2,
    name,
    emoji,
    wall,
    wain,
    floorA,
    floorB,
});
export const WINGS: WingDef[] = [
    wing(
        'bep',
        XL0,
        XL0 + 5.6,
        'Bếp',
        '🍳',
        0xfff6d8,
        0xffd9a0,
        0xf2e4c8,
        0xe8d6b4,
    ),
    wing(
        'phache',
        XL0 + 5.6,
        XL1,
        'Quầy cà phê',
        '☕',
        0xf3e6da,
        0xd9b99a,
        0xe6cfb4,
        0xdcc2a5,
    ),
    wing(
        'giaitri',
        XR0,
        XR0 + 5.6,
        'Góc giải trí',
        '🎮',
        0xe6f4ff,
        0xbfe0ff,
        0xd8d0f0,
        0xcdc4ea,
    ),
    wing(
        'nghi',
        XR0 + 5.6,
        XR1,
        'Phòng nghỉ',
        '😴',
        0xeee6ff,
        0xd2c2f5,
        0xc9bde6,
        0xbfb1de,
    ),
];
export const wingOf = (k: WingKey) => WINGS.find((w) => w.key === k)!;

export const SEAT_Z = -2.3;
export const DESK_Z = -1.65;

// Ngoài sân
export const POND = { x: 9.2, z: 9.0, rx: 2.7, rz: 1.8 };
export const MAILBOX = { x: -8.5, z: 13.0 };
export const FENCE_Z = 13.7;
export const GATE = { x0: -7.1, x1: -5.3 };
export const PLOT = { x0: -28, x1: 28, z0: -9, z1: 15.6 };
export const BENCH = { x: 13.0, z: 6.6, ry: -Math.PI / 2 - 0.5 };
export const HAMMOCK = { x: 23.2, z: 10.6 };
export const PINGPONG = { x: 18.0, z: 11.2 };
export const VEG = { x0: -20.0, x1: -14.2, z0: 5.4, z1: 8.2 };

/** Bậc thang dưới chân ở toạ độ (x, z), null nếu không ở cầu thang. */
export const stairY = (x: number, z: number): number | null => {
    if (
        Math.abs(x - BAY_CX) > STAIR_W / 2 + 0.2 ||
        z > STAIR_Z0 ||
        z < STAIR_Z1
    ) {
        return null;
    }
    const k = Math.min(STAIR_N, Math.ceil((STAIR_Z0 - z) / STAIR_D - 1e-4));

    return F1 + k * STAIR_R;
};

export const GATHER = (() => {
    const c = cx(2);
    const pts: [number, number, number][] = [];
    for (const x of [-1.7, -0.6, 0.6, 1.7]) {
        pts.push([c + x, F1, -1.75]);
    }
    for (const x of [-2.1, -1.05, 0, 1.05, 2.1]) {
        pts.push([c + x, F1, -0.6]);
    }
    for (const x of [-1.6, 1.6]) {
        pts.push([c + x, F1, 0.8]);
    }

    return pts;
})();

export const buildNav = () => {
    const g = new NavGraph();
    // hiên tầng 1 và lối đi xuyên các phòng tầng 2 (qua cửa thông ở đầu vách ngăn)
    for (let i = 0; i < 4; i++) {
        g.add(`c1.${i}`, cx(i), F1, LANE1);
        g.add(`c2.${i}`, cx(i), F2, LANE2);
        if (i > 0) {
            g.link(`c1.${i - 1}`, `c1.${i}`);
            g.link(`c2.${i - 1}`, `c2.${i}`);
        }
    }
    g.add('c1.4', BAY_CX, F1, LANE1B);
    g.link('c1.3', 'c1.4');
    g.add('st.top', BAY_CX, F2, STAIR_Z1 - 0.05);
    g.add('landing', BAY_CX, F2, -3.05);
    g.link('c1.4', 'st.top', 'landing');

    /** Phòng một bàn: (cửa) → chỗ giao việc → cạnh bàn → sau ghế → ghế. */
    const std = (k: RoomKey, corridor: string) => {
        const r = room(k);
        const c = r.cx;
        const y = r.fy;
        let entry = corridor;
        if (r.floor === 1) {
            g.add(`${k}.door`, c, y, -0.2);
            g.link(corridor, `${k}.door`);
            entry = `${k}.door`;
        }
        g.add(`${k}.meet`, c + 1.45, y, -0.8);
        g.add(`${k}.side`, c + 1.75, y, -2.15);
        g.add(`${k}.behind`, c + 0.8, y, -2.62);
        g.add(`${k}.seat`, c, y, SEAT_Z);
        g.link(entry, `${k}.meet`, `${k}.side`, `${k}.behind`, `${k}.seat`);
    };
    std('bienkich', 'c2.0');
    std('thuam', 'c2.1');
    std('giamkhao', 'c1.0');
    {
        const c = cx(0);
        g.add('bienkich.plant', c - 1.5, F2, -1.0);
        g.add('bienkich.win', c + 1.3, F2, -2.95);
        g.link('c2.0', 'bienkich.plant');
        g.link('bienkich.side', 'bienkich.win');
        g.add('giamkhao.shelf', c - 1.55, F1, -0.65);
        g.link('giamkhao.door', 'giamkhao.shelf');
    }
    // đạo diễn: hai ghế
    {
        const c = cx(2);
        const y = F2;
        g.add('daodien.meet', c, y, -0.95);
        g.add('daodien.hfA', c - 0.42, y, -0.95);
        g.add('daodien.hfB', c + 0.42, y, -0.95);
        g.add('daodien.cornerL', c - 2.15, y, -0.95);
        g.add('daodien.cornerR', c + 2.15, y, -0.95);
        g.add('daodien.sideL', c - 2.15, y, -2.3);
        g.add('daodien.sideR', c + 2.15, y, -2.3);
        g.add('daodien.behindA', c - 1.7, y, -2.62);
        g.add('daodien.behindB', c + 1.7, y, -2.62);
        g.add('daodien.seatA', c - 1.0, y, SEAT_Z);
        g.add('daodien.seatB', c + 1.0, y, SEAT_Z);
        g.link('c2.2', 'daodien.meet');
        g.link(
            'daodien.meet',
            'daodien.hfA',
            'daodien.cornerL',
            'daodien.sideL',
            'daodien.behindA',
            'daodien.seatA',
        );
        g.link(
            'daodien.meet',
            'daodien.hfB',
            'daodien.cornerR',
            'daodien.sideR',
            'daodien.behindB',
            'daodien.seatB',
        );
        g.link('c2.2', 'daodien.cornerL');
        g.link('c2.2', 'daodien.cornerR');
    }
    // phòng dựng: cửa sau thông ra chiếu nghỉ cầu thang
    {
        const c = cx(3);
        const y = F2;
        g.add('thodung.meet', c - 1.55, y, -0.85);
        g.add('thodung.corner', c + 1.9, y, -0.75);
        g.add('thodung.side', c + 1.9, y, -2.2);
        g.add('thodung.seat', c, y, SEAT_Z);
        g.add('thodung.behind', c + 0.9, y, -2.62);
        g.add('thodung.back', c + 2.15, y, -3.05);
        g.link('c2.3', 'thodung.meet');
        g.link(
            'c2.3',
            'thodung.corner',
            'thodung.side',
            'thodung.behind',
            'thodung.seat',
        );
        g.link('thodung.side', 'thodung.back', 'landing');
    }
    // kho hàng
    {
        const c = cx(1);
        const y = F1;
        g.add('thukho.door', c, y, -0.2);
        g.add('thukho.meet', c + 0.75, y, -0.75);
        g.add('thukho.mid', c + 0.15, y, -2.2);
        g.add('thukho.home', c - 1.2, y, -2.05);
        g.add('thukho.shelf', c + 1.3, y, -2.8);
        g.link(
            'c1.1',
            'thukho.door',
            'thukho.meet',
            'thukho.mid',
            'thukho.home',
        );
        g.link('thukho.mid', 'thukho.shelf');
    }
    // sảnh: chỗ tụ họp
    {
        const c = cx(2);
        g.add('sanh.door', c, F1, -0.2);
        g.add('sanh.mid', c, F1, -1.15);
        g.link('c1.2', 'sanh.door', 'sanh.mid');
        const ids = GATHER.map((p, i) => g.add(`g.${i}`, p[0], p[1], p[2]));
        for (const id of ids) {
            const p = g.pos(id);
            g.link(
                id,
                p.z > 0.5 ? 'c1.2' : p.z > -1 ? 'sanh.door' : 'sanh.mid',
            );
        }
        g.add('sanh.sofa', c + 2.0, F1, -2.85);
        g.link('sanh.mid', 'sanh.sofa');
    }
    // quầy
    {
        const c = cx(3);
        const y = F1;
        g.add('chuquay.door', c, y, -0.2);
        g.add('chuquay.meet', c - 1.6, y, -0.55);
        g.add('chuquay.side', c - 1.95, y, -2.1);
        g.add('chuquay.home', c, y, -2.1);
        g.add('chuquay.cart', c + 1.15, y, -0.45);
        g.link(
            'c1.3',
            'chuquay.door',
            'chuquay.meet',
            'chuquay.side',
            'chuquay.home',
        );
        g.link('chuquay.door', 'chuquay.cart');
    }
    // vườn
    const G = (id: string, x: number, z: number) => g.add(id, x, 0, z);
    // ---- nhà phụ
    {
        g.add('c1.L0', wingOf('phache').cx, F1, LANE1);
        g.add('c1.L1', wingOf('bep').cx, F1, LANE1);
        g.add('c1.R0', wingOf('giaitri').cx, F1, LANE1);
        g.add('c1.R1', wingOf('nghi').cx, F1, LANE1);
        g.link('c1.0', 'c1.L0', 'c1.L1');
        g.link('c1.4', 'c1.R0', 'c1.R1');
        const y = F1;
        // Bếp
        let c = wingOf('bep').cx;
        g.add('bep.door', c, y, -0.2);
        g.add('bep.aL', c - 2.3, y, -0.3);
        g.add('bep.aR', c + 2.3, y, -0.3);
        g.add('bep.aLb', c - 2.3, y, -2.6);
        g.add('bep.aRb', c + 2.3, y, -2.6);
        g.add('bep.stove', c - 1.6, y, -2.6);
        g.add('bep.b0', c - 0.75, y, -2.6);
        g.add('bep.fridge', c - 0.05, y, -2.6);
        g.add('bep.b1', c + 0.75, y, -2.6);
        g.add('bep.sink', c + 1.5, y, -2.6);
        g.add('bep.s0', c - 0.75, y, -1.95);
        g.add('bep.s1', c + 0.75, y, -1.95);
        g.add('bep.s2', c - 0.75, y, -0.42);
        g.add('bep.s3', c + 0.75, y, -0.42);
        g.add('bep.s4', c - 1.65, y, -1.2);
        g.add('bep.s5', c + 1.65, y, -1.2);
        g.add('bep.meo', c, y, -0.45);
        g.link('c1.L1', 'bep.door', 'bep.meo');
        g.link(
            'bep.door',
            'bep.aL',
            'bep.aLb',
            'bep.stove',
            'bep.b0',
            'bep.fridge',
            'bep.b1',
            'bep.sink',
            'bep.aRb',
            'bep.aR',
            'bep.door',
        );
        g.link('bep.b0', 'bep.s0');
        g.link('bep.b1', 'bep.s1');
        g.link('bep.door', 'bep.s2');
        g.link('bep.door', 'bep.s3');
        g.link('bep.aL', 'bep.s4');
        g.link('bep.aR', 'bep.s5');
        // Quầy cà phê: xếp hàng từ máy pha ra cửa
        c = wingOf('phache').cx;
        g.add('phache.door', c - 0.3, y, -0.2);
        g.add('phache.q0', c + 0.55, y, -1.5);
        g.add('phache.q1', c + 0.55, y, -0.85);
        g.add('phache.q2', c + 0.55, y, -0.2);
        g.add('phache.q3', c + 0.55, y, 0.45);
        g.add('phache.side', c - 1.2, y, -0.85);
        g.add('phache.st0', c - 1.25, y, -1.55);
        g.add('phache.st1', c - 0.55, y, -1.55);
        g.add('phache.sofa', c - 1.45, y, -0.35);
        g.link('c1.L0', 'phache.q3', 'phache.q2', 'phache.q1', 'phache.q0');
        g.link('c1.L0', 'phache.door', 'phache.side', 'phache.st0');
        g.link('phache.side', 'phache.st1');
        g.link('phache.door', 'phache.q1');
        g.link('phache.door', 'phache.sofa');
        // Góc giải trí
        c = wingOf('giaitri').cx;
        g.add('gt.door', c, y, -0.2);
        g.add('gt.so0', c - 1.85, y, -1.05);
        g.add('gt.so1', c - 0.75, y, -1.05);
        g.add('gt.front', c - 1.3, y, -0.35);
        g.add('gt.fb0', c + 0.55, y, -0.95);
        g.add('gt.fb1', c + 1.95, y, -0.95);
        g.add('gt.mid', c + 0.3, y, -2.0);
        g.add('gt.read', c + 1.85, y, -2.55);
        g.add('gt.bean', c - 2.1, y, -2.55);
        g.add('gt.back', c - 1.3, y, -2.72);
        g.link('c1.R0', 'gt.door', 'gt.front');
        g.link('gt.front', 'gt.so0');
        g.link('gt.front', 'gt.so1');
        g.link('gt.door', 'gt.fb0', 'gt.mid', 'gt.read');
        g.link('gt.mid', 'gt.back', 'gt.bean');
        g.link('gt.door', 'gt.fb1');
        // Phòng nghỉ
        c = wingOf('nghi').cx;
        g.add('nghi.door', c, y, -0.2);
        g.add('nghi.mid', c, y, -1.95);
        g.add('nghi.bed', c - 0.75, y, -2.25);
        g.add('nghi.bean0', c - 1.15, y, -1.05);
        g.add('nghi.bean1', c + 1.1, y, -1.0);
        g.link('c1.R1', 'nghi.door', 'nghi.mid', 'nghi.bed');
        g.link('nghi.door', 'nghi.bean0');
        g.link('nghi.door', 'nghi.bean1');
    }
    G('porch', cx(2), Z_FRONT + 0.95);
    g.link('c1.2', 'porch');
    G('gp1', 0.2, 4.6);
    G('gp2', -1.9, 7.2);
    G('gp3', -4.3, 9.6);
    G('gate', -6.2, 12.4);
    G('mail', MAILBOX.x + 0.15, MAILBOX.z - 0.85);
    G('post', -10.0, 10.9);
    g.link('porch', 'gp1', 'gp2', 'gp3', 'gate', 'mail', 'post');
    g.link('gate', 'post');
    G('lawnL1', -6.4, 5.0);
    G('lawnL2', -10.8, 6.0);
    G('lawnL3', -13.8, 9.6);
    G('sideL', -24.6, 3.4);
    G('gardenL', wingOf('bep').cx, Z_FRONT + 0.9);
    G('veg', -17.0, 4.7);
    g.link('c1.L1', 'gardenL', 'veg', 'lawnL2');
    g.link('gardenL', 'sideL');
    g.link('gp2', 'lawnL1', 'lawnL2', 'lawnL3', 'post');
    g.link('lawnL2', 'sideL');
    g.link('gp3', 'lawnL2');
    G('lawnR1', 4.2, 5.0);
    G('pondW', 5.6, 9.2);
    G('lawnR3', 8.8, 12.3);
    G('lawnR2', 13.6, 10.6);
    G('bench', BENCH.x - 0.75, BENCH.z + 0.45);
    G('sideR', 24.6, 3.4);
    G('gardenR', wingOf('nghi').cx, Z_FRONT + 0.9);
    G('hammock', HAMMOCK.x, HAMMOCK.z - 0.9);
    G('pp0', PINGPONG.x - 1.65, PINGPONG.z);
    G('pp1', PINGPONG.x + 1.65, PINGPONG.z);
    g.link('c1.R1', 'gardenR', 'hammock', 'pp1');
    g.link('gardenR', 'sideR');
    g.link('pp0', 'lawnR2');
    g.link('pp0', 'lawnR3');
    G('flower', 2.6, 8.2);
    g.link('gp1', 'lawnR1', 'pondW', 'lawnR3', 'lawnR2', 'bench', 'lawnR1');
    g.link('bench', 'sideR');
    g.link('gp1', 'flower', 'pondW');
    g.link('gp2', 'flower');

    return g;
};

/** Chỗ "nhà" của từng nhân vật: điểm đồ thị, hướng nhìn, ngồi hay đứng, dáng nghỉ. */
export interface Home {
    node: string;
    rot: number;
    seated: boolean;
    work: 'type' | 'smash' | 'write' | 'polish' | 'idle';
}
export const HOMES: Record<string, Home> = {
    bienkich: { node: 'bienkich.seat', rot: 0, seated: true, work: 'write' },
    thuam: { node: 'thuam.seat', rot: 0, seated: true, work: 'smash' },
    daodienA: { node: 'daodien.seatA', rot: 0, seated: true, work: 'type' },
    daodienB: { node: 'daodien.seatB', rot: 0, seated: true, work: 'type' },
    thodung: { node: 'thodung.seat', rot: 0, seated: true, work: 'type' },
    giamkhao: { node: 'giamkhao.seat', rot: 0, seated: true, work: 'write' },
    thukho: { node: 'thukho.home', rot: 0, seated: false, work: 'polish' },
    chuquay: { node: 'chuquay.home', rot: 0, seated: false, work: 'idle' },
    buuta: { node: 'post', rot: 0.3, seated: false, work: 'idle' },
};

/** Chỗ đứng khi tới giao việc cho vai `k`. */
export const MEET: Record<string, string> = {
    bienkich: 'bienkich.meet',
    thuam: 'thuam.meet',
    daodienA: 'daodien.meet',
    daodienB: 'daodien.meet',
    thodung: 'thodung.meet',
    giamkhao: 'giamkhao.meet',
    thukho: 'thukho.meet',
    chuquay: 'chuquay.meet',
};

export const GARDEN_NODES = [
    'gp1',
    'gp2',
    'gp3',
    'lawnL1',
    'lawnL2',
    'lawnL3',
    'lawnR1',
    'pondW',
    'lawnR3',
    'lawnR2',
    'bench',
    'flower',
    'sideL',
    'sideR',
    'porch',
    'veg',
    'gardenL',
    'gardenR',
    'hammock',
    'pp0',
];
export const SUNNY = [
    'flower',
    'lawnR1',
    'lawnL1',
    'sanh.sofa',
    'bienkich.win',
    'porch',
    'gt.bean',
    'nghi.bean1',
    'gt.so1',
    'phache.sofa',
];

/** Chỗ ngồi/nằm ngoài bàn làm việc: hướng nhìn, độ cao hông khi ngồi, chỗ nằm (nếu có). */
export interface Seat {
    rot: number;
    h?: number;
    lie?: { x: number; y: number; z: number; rot: number };
}
export const SEATS: Record<string, Seat> = {
    'bep.s0': { rot: 0 },
    'bep.s1': { rot: 0 },
    'bep.s2': { rot: Math.PI },
    'bep.s3': { rot: Math.PI },
    'bep.s4': { rot: Math.PI / 2 },
    'bep.s5': { rot: -Math.PI / 2 },
    'phache.st0': { rot: Math.PI, h: 0.62 },
    'phache.st1': { rot: Math.PI, h: 0.62 },
    'phache.sofa': { rot: 0.5, h: 0.42 },
    'gt.so0': { rot: Math.PI, h: 0.45 },
    'gt.so1': { rot: Math.PI, h: 0.45 },
    'gt.read': { rot: -0.6, h: 0.45 },
    'gt.bean': { rot: 0.5, h: 0.36 },
    'nghi.bean0': { rot: 0.35, h: 0.36 },
    'nghi.bean1': { rot: -0.35, h: 0.36 },
    'nghi.bed': {
        rot: 0,
        lie: {
            x: wingOf('nghi').cx - 0.92,
            y: F1 + 0.74,
            z: -2.95,
            rot: -Math.PI / 2,
        },
    },
    hammock: {
        rot: 0,
        lie: { x: HAMMOCK.x - 0.9, y: 0.98, z: HAMMOCK.z, rot: -Math.PI / 2 },
    },
};

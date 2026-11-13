// "Nhân vật của tôi": cấu hình ngoại hình (khớp đúng danh sách cho phép ở app/Fork/Nha/Avatar.php) và cách biến nó
// thành ChibiSpec. Hiện dùng cho nhân vật chính (Kid); các nhân vật khác sau này dùng lại được cùng cấu trúc.
import type { ChibiSpec, Expr, HairStyle } from './chibi';
import { pick } from './util';

export type Gioi = 'nam' | 'nu';
export type Mu = 'none' | 'cap' | 'beret' | 'headband' | 'hood' | 'postcap';
export type Ao = 'tee' | 'hoodie' | 'shirt' | 'sweater';
export type Quan = 'pants' | 'shorts' | 'skirt' | 'dress';
export type PhuKien = 'none' | 'glasses' | 'scarf' | 'backpack' | 'headphones';
export type BieuTuong = 'none' | 'star' | 'heart' | 'crown';

export interface AvatarCfg {
    v?: number;
    ten: string;
    gioi: Gioi;
    da: string;
    toc: HairStyle;
    mau_toc: string;
    mu: Mu;
    mau_mu: string;
    ao: Ao;
    mau_ao: string;
    quan: Quan;
    mau_quan: string;
    mau_giay: string;
    phu_kien: PhuKien;
    mat: Expr;
    bieu_tuong: BieuTuong;
}

/** Bảng màu cho phép (khoá giống máy chủ). */
export const MAU: Record<string, { hex: number; ten: string }> = {
    den: { hex: 0x2b2440, ten: 'Đen' },
    nau: { hex: 0x6b4430, ten: 'Nâu' },
    'nau-sang': { hex: 0xb07a4f, ten: 'Nâu sáng' },
    vang: { hex: 0xffc93c, ten: 'Vàng' },
    cam: { hex: 0xff9a4d, ten: 'Cam' },
    do: { hex: 0xff5f6d, ten: 'Đỏ' },
    hong: { hex: 0xff8fb8, ten: 'Hồng' },
    tim: { hex: 0x8a6cff, ten: 'Tím' },
    'tim-nhat': { hex: 0xc9b8ff, ten: 'Tím nhạt' },
    'xanh-duong': { hex: 0x5aa9ff, ten: 'Xanh dương' },
    'xanh-dam': { hex: 0x2f3b6b, ten: 'Xanh đậm' },
    'bac-ha': { hex: 0x7fdcc0, ten: 'Bạc hà' },
    'xanh-la': { hex: 0x6cc66b, ten: 'Xanh lá' },
    trang: { hex: 0xffffff, ten: 'Trắng' },
    xam: { hex: 0x9a98a8, ten: 'Xám' },
    kem: { hex: 0xfff1d6, ten: 'Kem' },
};

export const DA: Record<string, { hex: number; ten: string }> = {
    da1: { hex: 0xffe4d0, ten: 'Trắng hồng' },
    da2: { hex: 0xffd7bd, ten: 'Sáng' },
    da3: { hex: 0xf2c09a, ten: 'Bánh mật' },
    da4: { hex: 0xd99a6c, ten: 'Ngăm' },
    da5: { hex: 0x9a6648, ten: 'Nâu' },
};

export const OPTS = {
    gioi: [
        ['nam', '👦 Nam'],
        ['nu', '👧 Nữ'],
    ],
    toc: [
        ['short', 'Ngắn'],
        ['messy', 'Rối'],
        ['spiky', 'Dựng'],
        ['bob', 'Bob'],
        ['long', 'Dài'],
        ['pony', 'Đuôi ngựa'],
        ['bun', 'Búi'],
    ],
    mu: [
        ['none', 'Không'],
        ['cap', 'Lưỡi trai'],
        ['beret', 'Nồi'],
        ['headband', 'Băng đô'],
        ['hood', 'Mũ len'],
        ['postcap', 'Mũ bưu tá'],
    ],
    ao: [
        ['tee', 'Áo thun'],
        ['hoodie', 'Hoodie'],
        ['shirt', 'Sơ mi'],
        ['sweater', 'Áo len'],
    ],
    quan: [
        ['pants', 'Quần dài'],
        ['shorts', 'Quần đùi'],
        ['skirt', 'Chân váy'],
        ['dress', 'Váy liền'],
    ],
    phu_kien: [
        ['none', 'Không'],
        ['glasses', '👓 Kính'],
        ['scarf', '🧣 Khăn'],
        ['backpack', '🎒 Ba lô'],
        ['headphones', '🎧 Tai nghe'],
    ],
    mat: [
        ['happy', '🙂 Vui'],
        ['joy', '😆 Hớn hở'],
        ['cocky', '😏 Ngầu'],
        ['focus', '🧐 Nghiêm túc'],
        ['love', '🥰 Dễ thương'],
        ['sleepy', '😪 Buồn ngủ'],
    ],
    bieu_tuong: [
        ['none', 'Không'],
        ['star', '⭐ Sao'],
        ['heart', '💖 Tim'],
        ['crown', '👑 Vương miện'],
    ],
} as const;

/** Kid mặc định (giống Avatar::defaults()). */
export const DEFAULT_AVATAR: AvatarCfg = {
    v: 1,
    ten: 'Kid',
    gioi: 'nam',
    da: 'da2',
    toc: 'short',
    mau_toc: 'den',
    mu: 'cap',
    mau_mu: 'vang',
    ao: 'tee',
    mau_ao: 'tim',
    quan: 'pants',
    mau_quan: 'xanh-dam',
    mau_giay: 'trang',
    phu_kien: 'scarf',
    mat: 'happy',
    bieu_tuong: 'star',
};

/** Đổi giới tính trong bảng: đổi dáng người + gợi ý kiểu tóc/đồ mặc định (người dùng vẫn chọn lại được tất cả). */
export const genderDefaults = (g: Gioi): Partial<AvatarCfg> =>
    g === 'nu'
        ? {
              gioi: 'nu',
              toc: 'pony',
              quan: 'skirt',
              mau_quan: 'hong',
              mu: 'none',
          }
        : {
              gioi: 'nam',
              toc: 'short',
              quan: 'pants',
              mau_quan: 'xanh-dam',
              mu: 'cap',
          };

const col = (k: string, fb: number) => MAU[k]?.hex ?? fb;

/** Gộp cấu hình (có thể thiếu/hỏng) với mặc định, chỉ nhận giá trị hợp lệ. */
export const normalizeAvatar = (raw: unknown): AvatarCfg => {
    const out: AvatarCfg = { ...DEFAULT_AVATAR };
    if (!raw || typeof raw !== 'object') {
        return out;
    }
    const r = raw as Record<string, unknown>;
    const ok = (k: keyof typeof OPTS, v: unknown) =>
        typeof v === 'string' && OPTS[k].some(([x]) => x === v);
    for (const k of Object.keys(OPTS) as (keyof typeof OPTS)[]) {
        if (ok(k, r[k])) {
            (out as unknown as Record<string, unknown>)[k] = r[k];
        }
    }
    for (const k of [
        'mau_toc',
        'mau_mu',
        'mau_ao',
        'mau_quan',
        'mau_giay',
    ] as const) {
        if (typeof r[k] === 'string' && MAU[r[k] as string]) {
            out[k] = r[k] as string;
        }
    }
    if (typeof r.da === 'string' && DA[r.da]) {
        out.da = r.da;
    }
    if (typeof r.ten === 'string' && r.ten.trim()) {
        out.ten = r.ten.trim().slice(0, 20);
    }

    return out;
};

/** Cấu hình → hình dáng chibi. */
export const specFromAvatar = (c: AvatarCfg): ChibiSpec => {
    const shirt = col(c.mau_ao, 0x8a6cff);
    const bottom = col(c.mau_quan, 0x2f3b6b);
    const spec: ChibiSpec = {
        skin: DA[c.da]?.hex,
        shirt: c.quan === 'dress' ? bottom : shirt,
        sleeve: c.quan === 'dress' ? bottom : shirt,
        pants: bottom,
        shoes: col(c.mau_giay, 0xffffff),
        hair: col(c.mau_toc, 0x2b2440),
        hairStyle: c.toc,
        brows: 'soft',
        top: c.ao,
        bottom: c.quan,
        girl: c.gioi === 'nu',
        lashes: c.gioi === 'nu',
        collar: 0xffffff,
    };
    if (c.mu !== 'none') {
        spec.hat = { kind: c.mu, color: col(c.mau_mu, 0xffc93c) };
    }
    const accent = c.mau_mu !== c.mau_ao ? col(c.mau_mu, 0xff5f7a) : 0xff5f7a;
    switch (c.phu_kien) {
        case 'glasses':
            spec.glasses = 0x3d2f5c;
            break;
        case 'scarf':
            spec.scarf = accent;
            break;
        case 'backpack':
            spec.backpack = accent;
            break;
        case 'headphones':
            spec.headphones = 0x3d2f5c;
            break;
        default:
            break;
    }

    return spec;
};

/** Ngẫu nhiên một bộ đồ dễ thương (giữ tên và giới tính). */
export const randomAvatar = (c: AvatarCfg): AvatarCfg => {
    const colors = Object.keys(MAU);
    const hairCols = [
        'den',
        'nau',
        'nau-sang',
        'vang',
        'cam',
        'hong',
        'tim',
        'xanh-duong',
        'bac-ha',
    ];
    const of = <K extends keyof typeof OPTS>(k: K) =>
        pick(OPTS[k].map(([x]) => x)) as (typeof OPTS)[K][number][0];

    return {
        ...c,
        da: pick(Object.keys(DA)),
        toc: of('toc') as HairStyle,
        mau_toc: pick(hairCols),
        mu: Math.random() < 0.35 ? 'none' : (of('mu') as Mu),
        mau_mu: pick(colors),
        ao: of('ao') as Ao,
        mau_ao: pick(colors.filter((x) => x !== 'den')),
        quan:
            c.gioi === 'nu'
                ? (pick(['skirt', 'dress', 'shorts', 'pants']) as Quan)
                : (pick(['pants', 'pants', 'shorts']) as Quan),
        mau_quan: pick(colors),
        mau_giay: pick(['trang', 'den', 'do', 'vang', 'hong', 'xanh-duong']),
        phu_kien: of('phu_kien') as PhuKien,
        mat: of('mat') as Expr,
        bieu_tuong: of('bieu_tuong') as BieuTuong,
    };
};

/** Cách mọi người gọi chủ xưởng theo giới tính. */
export const xungHo = (c: AvatarCfg) => (c.gioi === 'nu' ? 'chị' : 'anh');

// "Trực tiếp" ở Khu Tự Trị: việc đang chạy thật (xem LiveItem trong types.ts) → bong bóng và màn hình của nhân vật.
// File này là phần LOGIC thuần (không Vue, không DOM) để kiểm được bằng tay:
//   - chuanHoa / conSong / nhanVatCua: làm sạch dữ liệu thô từ hub/app và gán việc cho nhân vật;
//   - GiamDocLoi ("đạo diễn lời thoại"): bình tĩnh đổi bong bóng mỗi ~5–7 giây cho từng nhân vật, lần lượt kể các mặt THẬT
//     của việc đang làm (câu vừa viết, câu đang gõ, đã làm bao lâu, bao nhiêu chữ, bước nào, đang nghĩ gì…).
// KHÔNG gọi AI, KHÔNG bịa: mặt nào thiếu dữ liệu thì bỏ qua, không bao giờ in "undefined" hay con số 0 không có thật.
import { tenVideo } from '@/components/fork/nha/tu-thoai';
import type { LiveItem } from '@/components/fork/nha/types';

/** Khoá vai của hợp đồng (hub + app) → khoá nhân vật của trang (data.vai). null = không gắn nhân vật nào (chỉ hiện ở Sảnh). */
const NHAN_VAT: Record<string, string | null> = {
    'bien-kich': 'bienkich',
    giong: 'thuam',
    'dao-dien': 'daodien',
    dung: 'thodung',
    'giam-khao': 'giamkhao',
    // Mọi việc AI nhìn kho/nhãn/cảnh của hub là việc của Thủ kho
    kho: 'thukho',
    'doc-nhan': 'thukho',
    'soat-kho': 'thukho',
    'hoc-canh': 'thukho',
    'he-thong': null,
    buuta: 'buuta',
    chuquay: 'chuquay',
    thukho: 'thukho',
    cu: 'cu',
    meo: 'meo',
    // đã là khoá của trang
    bienkich: 'bienkich',
    thuam: 'thuam',
    daodien: 'daodien',
    thodung: 'thodung',
    giamkhao: 'giamkhao',
};

/** Tên hiện cho từng khoá vai của hợp đồng (dòng "● Biên kịch đang…" ở Sảnh). */
export const TEN_VAI: Record<string, string> = {
    'bien-kich': 'Biên kịch',
    giong: 'Thu âm',
    'dao-dien': 'Đạo diễn',
    dung: 'Thợ dựng',
    'giam-khao': 'Giám khảo',
    kho: 'Thủ kho',
    'doc-nhan': 'Thủ kho',
    'soat-kho': 'Thủ kho',
    'hoc-canh': 'Thủ kho',
    'he-thong': 'Xưởng',
    buuta: 'Bưu tá',
    chuquay: 'Chủ quầy',
    thukho: 'Thủ kho',
    cu: 'Cú',
    meo: 'Mèo',
};

export const nhanVatCua = (it: Pick<LiveItem, 'vai'>): string | null =>
    NHAN_VAT[it.vai] ?? null;

export const tenVai = (it: Pick<LiveItem, 'vai'>): string =>
    TEN_VAI[it.vai] ?? 'Xưởng';

// ---------------------------------------------------------------- làm sạch dữ liệu thô
const MAU_RAC = /\b(undefined|null|NaN)\b|\[object/i;

const chuoi = (v: unknown, max = 300): string | null => {
    if (typeof v !== 'string') {
        return null;
    }
    const t = v.replace(/\s+/g, ' ').trim();

    return t && !MAU_RAC.test(t) ? t.slice(0, max) : null;
};

const so = (v: unknown): number | null =>
    typeof v === 'number' && Number.isFinite(v) ? v : null;

/** Một phần tử thô (JSON từ hub/Laravel) → LiveItem sạch; không dùng được thì null. */
export const chuanHoa = (raw: unknown): LiveItem | null => {
    if (typeof raw !== 'object' || raw === null) {
        return null;
    }
    const r = raw as Record<string, unknown>;
    const id = chuoi(r.id, 120);
    const vai = chuoi(r.vai, 40);

    if (!id || !vai) {
        return null;
    }
    const dong = Array.isArray(r.dong)
        ? r.dong
              .map((x) => chuoi(x, 200))
              .filter((x): x is string => x !== null)
              .slice(-8)
        : null;
    const td = so(r.tien_do);
    const ct =
        typeof r.chi_tiet === 'object' &&
        r.chi_tiet !== null &&
        !Array.isArray(r.chi_tiet)
            ? (r.chi_tiet as Record<string, unknown>)
            : null;

    return {
        id,
        nguon: r.nguon === 'app' ? 'app' : 'hub',
        vai,
        viec: chuoi(r.viec),
        sp: chuoi(r.sp, 120),
        video: chuoi(r.video, 120),
        kenh: chuoi(r.kenh, 120),
        bat_dau: so(r.bat_dau),
        cap_nhat: so(r.cap_nhat),
        xong: r.xong === true,
        ket_qua: r.ket_qua === 'ok' || r.ket_qua === 'loi' ? r.ket_qua : null,
        ky_tu: so(r.ky_tu),
        dong: dong && dong.length ? dong : null,
        dang_go: chuoi(r.dang_go),
        suy_nghi: chuoi(r.suy_nghi, 240),
        tien_do: td === null ? null : Math.min(1, Math.max(0, td)),
        buoc: chuoi(r.buoc, 80),
        chi_tiet: ct,
    };
};

export const chuanHoaDs = (raw: unknown): LiveItem[] =>
    Array.isArray(raw)
        ? raw.map(chuanHoa).filter((x): x is LiveItem => x !== null)
        : [];

/** Còn đáng hiện không: đang chạy thì im lặng tối đa 10 phút (trùng cửa sổ của máy chủ), vừa xong thì giữ ~75 giây. */
export const conSong = (it: LiveItem, nowSec: number): boolean => {
    const cap = it.cap_nhat ?? it.bat_dau ?? nowSec;

    return nowSec - cap < (it.xong ? 75 : 600);
};

/** Mới nhất lên đầu; id trùng thì lấy bản mới hơn. */
export const gop = (...ds: LiveItem[][]): LiveItem[] => {
    const m = new Map<string, LiveItem>();

    for (const d of ds) {
        for (const it of d) {
            const old = m.get(it.id);

            if (!old || (it.cap_nhat ?? 0) >= (old.cap_nhat ?? 0)) {
                m.set(it.id, it);
            }
        }
    }

    return [...m.values()].sort(
        (a, b) => (b.cap_nhat ?? 0) - (a.cap_nhat ?? 0),
    );
};

// ---------------------------------------------------------------- định dạng
/** "45 giây", "1 phút 20 giây", "12 phút", "1 giờ 5 phút". */
export const thoiGianDai = (sec: number): string => {
    const s = Math.max(0, Math.round(sec));

    if (s < 60) {
        return `${s} giây`;
    }
    const m = Math.floor(s / 60);

    if (m < 10) {
        return s % 60 ? `${m} phút ${s % 60} giây` : `${m} phút`;
    }

    if (m < 60) {
        return `${m} phút`;
    }

    return m % 60
        ? `${Math.floor(m / 60)} giờ ${m % 60} phút`
        : `${Math.floor(m / 60)} giờ`;
};

/** "1:20", "12:05", "1:02:03" (đồng hồ ở đầu màn hình). */
export const dongHo = (sec: number): string => {
    const s = Math.max(0, Math.floor(sec));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const ss = String(s % 60).padStart(2, '0');

    return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`;
};

export const soVi = (n: number): string =>
    Math.round(n).toLocaleString('vi-VN');

const so1 = (n: number): string =>
    String(Math.round(n * 10) / 10).replace('.', ',');

/** Số giây đã làm (null nếu không biết hoặc vô lý). */
export const daLam = (it: LiveItem, nowSec: number): number | null => {
    if (it.bat_dau == null) {
        return null;
    }
    const end = it.xong ? (it.cap_nhat ?? nowSec) : nowSec;
    const d = end - it.bat_dau;

    return d >= 0 && d < 86400 ? d : null;
};

/** Cắt gọn ở ranh giới chữ. `cuoi` = giữ phần CUỐI (đoạn đang gõ / đang nghĩ), đầu có "…". */
export const gon = (s: string, max: number, cuoi = false): string => {
    if (s.length <= max) {
        return s;
    }
    if (cuoi) {
        const t = s.slice(-max);
        const i = t.indexOf(' ');

        return `…${i > 0 && i < max * 0.4 ? t.slice(i + 1) : t}`;
    }
    const t = s.slice(0, max);
    const i = t.lastIndexOf(' ');

    return `${(i > max * 0.6 ? t.slice(0, i) : t).replace(/[\s,.;:!?-]+$/u, '')}…`;
};

const cat = (s: string) => s.replace(/[\s.…]+$/u, '');

const bam = (s: string): number => {
    let h = 2166136261;

    for (let i = 0; i < s.length; i++) {
        h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    }

    return h >>> 0;
};

// ---------------------------------------------------------------- mẫu câu
/** Vai nói "lời thật" (câu biên kịch viết, ý đạo diễn…) thì trích trong ngoặc kép; vai còn lại là dòng tiến độ, không ngoặc. */
const TRICH = new Set(['bienkich', 'daodien', 'giamkhao', 'thuam']);

type Vars = Record<string, string>;

const dien = (t: string, v: Vars) =>
    t.replace(/\{(\w+)\}/g, (_, k: string) => v[k] ?? '');

/** Câu mở đầu khi trích câu vừa xong. {x} = câu đó (đã có ngoặc kép nếu vai trích). */
const MO_DONG: Record<string, string[]> = {
    bienkich: [
        'Vừa viết: {x}',
        'Câu này được nè: {x}',
        'Chốt: {x}',
        'Mới nặn ra: {x}',
        'Nghe được không nè: {x}',
        'Dòng mới nè: {x}',
    ],
    daodien: [
        'Xếp cảnh: {x}',
        'Ghi vô bảng dựng: {x}',
        'Ý mới: {x}',
        'Cảnh này đó: {x}',
        'Chốt cảnh: {x}',
    ],
    giamkhao: [
        'Soi ra: {x}',
        'Ghi sổ: {x}',
        'Nhận xét: {x}',
        'Bắt được: {x}',
        'Chấm tới: {x}',
    ],
    thuam: [
        'Vừa thu: {x}',
        'Câu này đọc là: {x}',
        'Thu xong câu: {x}',
        'Đọc tới: {x}',
    ],
    thodung: [
        'Vừa xong: {x}',
        'Ráp xong: {x}',
        'Tới bước: {x}',
        'Ghi nhận: {x}',
    ],
    thukho: ['Vừa xong: {x}', 'AI báo: {x}', 'Ghi nhận: {x}', 'Kết quả: {x}'],
    buuta: ['Vừa xong: {x}', 'Tới đâu rồi: {x}', 'Báo cáo: {x}'],
    chuquay: ['Vừa xong: {x}', 'Giỏ báo: {x}', 'Ghi nhận: {x}'],
    cu: ['Vừa gom: {x}', 'Số liệu về: {x}', 'Ghi nhận: {x}'],
    meo: ['Vừa xong: {x}', 'Meo ghi: {x}'],
};
const MO_DONG_CHUNG = ['Vừa xong: {x}', 'Ghi nhận: {x}', 'Tới đây rồi: {x}'];

/** Câu mở khi đang gõ dở. {x} = đoạn đang gõ. */
const MO_GO: Record<string, string[]> = {
    bienkich: ['…đang gõ: {x}', 'Đang gõ dở: {x}', 'Tay đang chạy: {x}'],
    daodien: ['…đang xếp: {x}', 'Đang nháp: {x}'],
    giamkhao: ['…đang ghi: {x}', 'Đang viết nhận xét: {x}'],
    thuam: ['…đang đọc: {x}', 'Đọc dở: {x}'],
};
const MO_GO_CHUNG = ['Đang làm: {x}', '…đang chạy: {x}'];

const MO_CU = [
    'Hồi nãy: {x}',
    'Câu trước đó: {x}',
    'Mới đây thôi: {x}',
    'Nhắc lại nè: {x}',
];

const MO_NGHI = [
    'Đang nghĩ: {x}',
    'Trong đầu đang chạy: {x}',
    'Nghĩ thầm: {x}',
];

const MO_GIO: Record<string, string[]> = {
    bienkich: [
        'Ngồi nặn {t} rồi, đầu bốc khói.',
        'Viết {t} rồi mà chưa nghỉ phút nào.',
    ],
    daodien: ['Cân cảnh {t} rồi, kỹ lắm nha.', 'Ngồi dựng ý {t} rồi đó.'],
    giamkhao: ['Soi {t} rồi, kỹ lắm nha.', 'Chấm {t} rồi, đừng hối.'],
    thuam: ['Thu {t} rồi, chờ giọng về.', 'Mic bật {t} rồi đó.'],
    thodung: ['Dựng {t} rồi, máy nóng hầm hập.', 'Ráp {t} rồi, chưa xong đâu.'],
    buuta: ['Chạy {t} rồi, chưa tới nơi.', 'Đi {t} rồi đó, đừng lo.'],
};
const MO_GIO_CHUNG = [
    'Ngồi {t} rồi, chưa xong đâu.',
    'Làm được {t} rồi nha.',
    'Đã {t} trôi qua, vẫn đang cày.',
];

const MO_CHU = [
    'Gõ được {n} chữ rồi.',
    'Mới ra {n} chữ, còn tiếp.',
    '{n} chữ trên giấy rồi nè.',
];
const MO_BUOC = ['Đang ở {x}.', 'Tới {x} rồi.', 'Hiện tại: {x}.'];
const MO_TD = ['Được {x}% rồi.', 'Tiến độ {x}% rồi nha.', 'Chạy tới {x}% rồi.'];
const MO_KENH = ['Đang lo cho {x}.', 'Việc này của {x} nha.'];
const MO_SP = ['Đang làm cho {x}.', 'Hàng này là {x} nha.'];
const MO_VIDEO = ['Đang lo {x} đây.', 'Việc này là {x} nha.'];

const chon = (pool: string[], key: string): string =>
    pool[bam(key) % pool.length];

// ---------------------------------------------------------------- các mặt thật của một việc
const trich = (nv: string, x: string, max: number): string =>
    TRICH.has(nv) ? `“${gon(cat(x), max)}”` : gon(cat(x), max);

/** Câu hoàn chỉnh mới nhất của việc (null nếu chưa có). */
const dongMoi = (it: LiveItem): string | null => {
    const d = it.dong ?? [];

    return d.length ? d[d.length - 1] : null;
};

/** Câu kết khi việc xong, từ kết quả thật (thời gian làm, số chữ, điểm). null nếu việc không có gì để nói. */
export const cauKet = (it: LiveItem, nowSec: number): string | null => {
    const dur = daLam(it, nowSec);
    const diem = so(it.chi_tiet?.diem);

    if (it.ket_qua === 'loi') {
        return dur !== null && dur >= 5
            ? `Hỏng mất tiêu, ngồi ${thoiGianDai(dur)} mà không xong. Bực ghê.`
            : 'Hỏng mất tiêu, không xong được. Bực ghê.';
    }
    const parts: string[] = [];

    if (diem !== null) {
        parts.push(`${so1(diem)} điểm`);
    }

    if (it.ky_tu && it.ky_tu > 0) {
        parts.push(`${soVi(it.ky_tu)} chữ`);
    }

    if (dur !== null && dur >= 5) {
        parts.push(`mất ${thoiGianDai(dur)}`);
    }

    if (!parts.length) {
        return 'Xong rồi nha!';
    }

    const ghep = parts.join(', ');

    return `Xong rồi! ${ghep.charAt(0).toUpperCase()}${ghep.slice(1)}.`;
};

type Loai = 'go' | 'nghi' | 'su-that' | 'cu';

// ---------------------------------------------------------------- đạo diễn lời thoại
const MIN_MS = 5000;
const MAX_MS = 7000;
const GIU_KET_MS = 7000;
const GIU_LAI = 6; // nhớ bấy nhiêu câu gần nhất để không lặp

interface TrangThaiVai {
    text: string | null;
    nextAt: number;
    holdUntil: number;
    k: number; // vòng xoay các loại mặt
    rot: number; // vòng xoay giữa các việc của cùng nhân vật
    buoc: number; // bộ đếm đổi câu (băm chọn mẫu)
    recent: string[];
    itemId: string | null;
}

interface TrangThaiViec {
    daTrich: Set<string>;
    goCuoi: string;
    nghiCuoi: string;
    sv: number; // vòng xoay các sự thật
    gan: string[]; // loại sự thật vừa nói (tránh nói liền hai câu cùng loại)
    gioLuc: number; // lần cuối nói "đã làm bao lâu" (giây)
}

/** Số việc đồng thời tối đa có bong bóng riêng cho một nhân vật (Đạo diễn có 2 người). */
const SUC_CHUA: Record<string, number> = { daodien: 2 };

export class GiamDocLoi {
    private vai = new Map<string, TrangThaiVai>();
    private viec = new Map<string, TrangThaiViec>();
    private daThay = new Set<string>(); // đã từng thấy ĐANG CHẠY (để biết nên nói câu kết hay không)
    private daKet = new Set<string>(); // đã xử lý câu kết
    private out: Record<string, string | null> = {};

    /** Gọi mỗi ~1 giây. Trả bảng nhân vật → câu đang nói (null = không có việc trực tiếp, để lời thoại cũ lo). */
    tick(items: LiveItem[], nowMs: number): Record<string, string | null> {
        const nowSec = nowMs / 1000;
        const nhom = new Map<string, LiveItem[]>();

        for (const it of items) {
            const nv = nhanVatCua(it);

            if (!nv || !conSong(it, nowSec)) {
                continue;
            }
            const l = nhom.get(nv);

            if (l) {
                l.push(it);
            } else {
                nhom.set(nv, [it]);
            }
        }
        const ketQua: Record<string, string | null> = {};

        for (const nv of new Set([
            ...nhom.keys(),
            ...[...this.vai.keys()].filter((k) => !k.includes('#')),
        ])) {
            const ds = nhom.get(nv) ?? [];
            const chay = ds.filter((i) => !i.xong);
            const xong = ds.filter((i) => i.xong);

            for (const i of chay) {
                this.daThay.add(i.id);
            }
            let ket: string | null = null;

            for (const i of xong) {
                if (this.daKet.has(i.id)) {
                    continue;
                }
                this.daKet.add(i.id);

                if (this.daThay.has(i.id) || nowSec - (i.cap_nhat ?? 0) < 15) {
                    ket = cauKet(i, nowSec) ?? ket;
                }
            }
            const cap = SUC_CHUA[nv] ?? 1;
            const vai = this.trangThai(nv);

            if (ket) {
                // Việc vừa xong: giữ câu kết ~7 giây (đủ đọc) rồi mới trả lại cho lời thoại cũ / việc kế
                vai.text = ket;
                vai.itemId = null;
                vai.holdUntil = nowMs + GIU_KET_MS;
                vai.nextAt = vai.holdUntil;
                vai.recent.push(ket);
            }

            if (nowMs < vai.holdUntil) {
                this.dat(ketQua, nv, 0, vai.text);

                continue;
            }

            const slots = this.chiaSlot(nv, cap, chay, vai);

            if (!slots.some((x) => x !== null)) {
                this.nghi(vai);
                this.dat(ketQua, nv, 0, null);

                if (cap > 1) {
                    this.nghi(this.trangThai(`${nv}#2`));
                    this.dat(ketQua, nv, 1, null);
                }

                continue;
            }
            // Mỗi slot (Đạo diễn: 2 người) là một dòng chảy riêng; slot 0 dùng trạng thái của nhân vật, slot 1 dùng khoá "nv#2"
            slots.forEach((it, i) => {
                const kn = i === 0 ? nv : `${nv}#2`;
                const st = i === 0 ? vai : this.trangThai(kn);

                if (!it) {
                    this.nghi(st);
                    this.dat(ketQua, nv, i, null);

                    return;
                }
                this.dat(
                    ketQua,
                    nv,
                    i,
                    this.buoc(st, it, cap > 1 ? [it] : chay, nv, nowMs, kn),
                );
            });
        }
        // dọn trạng thái việc đã biến mất
        if (this.viec.size > 200) {
            const con = new Set(items.map((i) => i.id));

            for (const k of [...this.viec.keys()]) {
                if (!con.has(k)) {
                    this.viec.delete(k);
                }
            }
        }

        if (this.daThay.size > 400) {
            this.daThay = new Set([...this.daThay].slice(-200));
        }

        if (this.daKet.size > 400) {
            this.daKet = new Set([...this.daKet].slice(-200));
        }
        this.out = ketQua;

        return ketQua;
    }

    cur(): Record<string, string | null> {
        return this.out;
    }

    private dat(
        kq: Record<string, string | null>,
        nv: string,
        i: number,
        text: string | null,
    ) {
        kq[i === 0 ? nv : `${nv}${i + 1}`] = text;
    }

    /**
     * Chia các việc đang chạy cho các "ô" bong bóng của nhân vật. Nhân vật một ô (hầu hết) → [việc đầu]; Đạo diễn có hai ô: mỗi ô
     * giữ nguyên việc của mình (không đảo qua lại khi thứ tự cập nhật đổi), việc mới vào ô trống.
     */
    private chiaSlot(
        nv: string,
        cap: number,
        chay: LiveItem[],
        st0: TrangThaiVai,
    ): (LiveItem | null)[] {
        if (cap <= 1) {
            return [chay[0] ?? null];
        }
        const st1 = this.trangThai(`${nv}#2`);
        const a = chay.find((c) => c.id === st0.itemId) ?? null;
        const b = chay.find((c) => c.id === st1.itemId && c !== a) ?? null;
        const roi = chay.filter((c) => c !== a && c !== b);
        const x = a ?? roi.shift() ?? null;
        const y = b ?? roi.shift() ?? null;

        if (!x && y) {
            // ô đầu trống mà ô sau còn việc: dồn lên (bản 2D chỉ có một bong bóng cho Đạo diễn)
            this.nghi(st1);

            return [y, null];
        }

        return [x, y];
    }

    /** Hết việc: xoá câu đang nói; lần xuất hiện kế tiếp sẽ được xếp lệch lại. */
    private nghi(s: TrangThaiVai) {
        s.text = null;
        s.itemId = null;
        s.nextAt = 0;
    }

    private trangThai(nv: string): TrangThaiVai {
        let s = this.vai.get(nv);

        if (!s) {
            s = {
                text: null,
                nextAt: 0, // 0 = chưa xếp lịch; lần xuất hiện đầu xếp lệch 0–2 giây theo nhân vật
                holdUntil: 0,
                k: bam(nv) % 5,
                rot: 0,
                buoc: 0,
                recent: [],
                itemId: null,
            };
            this.vai.set(nv, s);
        }

        return s;
    }

    /** Một slot: đến lượt đổi câu thì chọn câu mới, chưa tới thì giữ nguyên. */
    private buoc(
        s: TrangThaiVai,
        it: LiveItem,
        chay: LiveItem[],
        nv: string,
        nowMs: number,
        kn: string,
    ): string | null {
        // việc đang nói đã xong/biến mất: đổi ngay sang việc còn chạy
        const doiViec =
            s.itemId !== null && !chay.some((c) => c.id === s.itemId);

        if (s.nextAt === 0) {
            s.nextAt = nowMs + (bam(kn) % 5) * 500;
        }

        if (s.text === null && nowMs < s.nextAt) {
            return null; // chưa tới lượt xuất hiện đầu tiên của nhân vật này
        }

        if (s.text !== null && nowMs < s.nextAt && !doiViec) {
            return s.text;
        }
        const nowSec = nowMs / 1000;
        // Nhân vật có nhiều việc cùng lúc (Thủ kho): ưu tiên việc có câu mới chưa kể, nếu không thì xoay vòng.
        const tuoi = chay.find((c) => this.coCauMoi(c));
        const dung = tuoi ?? chay[s.rot % chay.length] ?? it;
        const text = this.chonCau(dung, s, nv, nowSec);

        if (text === null) {
            s.nextAt = nowMs + 1500; // chưa có gì mới để nói: thử lại sớm

            return s.text;
        }
        s.rot += 1;
        s.buoc += 1;
        s.text = text;
        s.itemId = dung.id;
        s.recent.push(text);

        if (s.recent.length > GIU_LAI) {
            s.recent.shift();
        }
        s.nextAt =
            nowMs + MIN_MS + (bam(`${kn}|${s.buoc}`) % (MAX_MS - MIN_MS + 1));

        return text;
    }

    private tv(it: LiveItem): TrangThaiViec {
        let t = this.viec.get(it.id);

        if (!t) {
            t = {
                daTrich: new Set(),
                goCuoi: '',
                nghiCuoi: '',
                sv: 0,
                gan: [],
                gioLuc: 0,
            };
            this.viec.set(it.id, t);
        }

        return t;
    }

    private coCauMoi(it: LiveItem): boolean {
        const m = dongMoi(it);

        return m !== null && !this.tv(it).daTrich.has(m);
    }

    private chonCau(
        it: LiveItem,
        s: TrangThaiVai,
        nv: string,
        nowSec: number,
    ): string | null {
        const tv = this.tv(it);
        const khoa = `${it.id}|${s.buoc}`;
        const ok = (t: string | null): t is string =>
            t !== null && t !== s.text && !s.recent.includes(t);
        // 1) câu hoàn chỉnh mới → luôn ưu tiên (đây là nội dung thật), bỏ qua các câu cũ hơn đã trôi qua
        const moi = dongMoi(it);

        if (moi !== null && !tv.daTrich.has(moi)) {
            for (const d of it.dong ?? []) {
                tv.daTrich.add(d);
            }
            const t = dien(chon(MO_DONG[nv] ?? MO_DONG_CHUNG, khoa), {
                x: trich(nv, moi, 84),
            });

            if (ok(t)) {
                return t;
            }
        }
        // 2) xoay vòng các mặt khác
        const loai: Loai[] = ['go', 'su-that', 'nghi', 'cu', 'su-that'];

        for (let n = 0; n < loai.length; n++) {
            const l = loai[(s.k + n) % loai.length];
            const t = this.mat(l, it, tv, s, nv, nowSec, khoa);

            if (ok(t)) {
                s.k = (s.k + n + 1) % loai.length;

                return t;
            }
        }

        return null;
    }

    private mat(
        l: Loai,
        it: LiveItem,
        tv: TrangThaiViec,
        s: TrangThaiVai,
        nv: string,
        nowSec: number,
        khoa: string,
    ): string | null {
        if (l === 'go') {
            const g = it.dang_go;

            if (!g || g.length < 6 || g === tv.goCuoi) {
                return null;
            }
            tv.goCuoi = g;

            return dien(chon(MO_GO[nv] ?? MO_GO_CHUNG, khoa), {
                x: TRICH.has(nv)
                    ? `“${gon(g, 60, true)}…”`
                    : `${gon(g, 60, true)}…`,
            });
        }

        if (l === 'nghi') {
            const n = it.suy_nghi;

            if (!n || n.length < 12 || n === tv.nghiCuoi) {
                return null;
            }
            tv.nghiCuoi = n;

            return dien(chon(MO_NGHI, khoa), {
                x: `${gon(cat(n), 80, true)}…`,
            });
        }

        if (l === 'cu') {
            const d = it.dong ?? [];
            // câu cũ hơn câu mới nhất, chọn xoay vòng, chỉ khi còn ≥ 2 câu
            if (d.length < 2) {
                return null;
            }
            const x = d[(bam(khoa) % (d.length - 1)) | 0];

            return dien(chon(MO_CU, khoa), { x: trich(nv, x, 84) });
        }
        const sv = this.suThat(it, nv, nowSec, khoa, tv);

        if (!sv.length) {
            return null;
        }
        tv.sv += 1;
        // Thử lần lượt từ chỗ đang xoay: ưu tiên câu chưa nói gần đây VÀ khác loại với hai câu vừa rồi; không có thì thôi (giữ nguyên bong bóng).
        for (const chat of [true, false]) {
            for (let n = 0; n < sv.length; n++) {
                const c = sv[(tv.sv + n) % sv.length];

                if (
                    c.t !== s.text &&
                    !s.recent.includes(c.t) &&
                    !(chat && tv.gan.includes(c.k))
                ) {
                    tv.sv = (tv.sv + n) % sv.length;
                    tv.gan.push(c.k);

                    if (tv.gan.length > 2) {
                        tv.gan.shift();
                    }

                    if (c.k === 'gio') {
                        tv.gioLuc = nowSec;
                    }

                    return c.t;
                }
            }

            if (sv.length > 3) {
                break; // đủ loại để chọn: đừng nới lỏng mà lặp loại
            }
        }

        return null;
    }

    /** Các câu "sự thật" của việc (kèm loại): chỉ những mục có dữ liệu thật. */
    private suThat(
        it: LiveItem,
        nv: string,
        nowSec: number,
        khoa: string,
        tv: TrangThaiViec,
    ): { k: string; t: string }[] {
        const out: { k: string; t: string }[] = [];
        const dur = daLam(it, nowSec);

        // "Đã làm bao lâu" đổi từng giây nên dễ lặp: nói tối đa 25 giây một lần
        if (dur !== null && dur >= 20 && nowSec - tv.gioLuc >= 25) {
            out.push({
                k: 'gio',
                t: dien(chon(MO_GIO[nv] ?? MO_GIO_CHUNG, `${khoa}g`), {
                    t: thoiGianDai(dur),
                }),
            });
        }

        if (it.ky_tu && it.ky_tu > 0) {
            out.push({
                k: 'chu',
                t: dien(chon(MO_CHU, `${khoa}c`), { n: soVi(it.ky_tu) }),
            });
        }

        if (it.buoc) {
            out.push({
                k: 'buoc',
                t: dien(chon(MO_BUOC, `${khoa}b`), {
                    x: gon(cat(it.buoc), 40),
                }),
            });
        }

        if (it.tien_do != null && it.tien_do >= 0.05) {
            out.push({
                k: 'td',
                t: dien(chon(MO_TD, `${khoa}p`), {
                    x: String(Math.max(1, Math.round(it.tien_do * 100))),
                }),
            });
        }

        if (it.kenh) {
            out.push({
                k: 'kenh',
                t: dien(chon(MO_KENH, `${khoa}k`), { x: it.kenh }),
            });
        }

        if (it.sp) {
            out.push({
                k: 'sp',
                t: dien(chon(MO_SP, `${khoa}s`), { x: gon(it.sp, 40) }),
            });
        }
        const vd = tenVideo(it.video);

        if (vd) {
            out.push({
                k: 'video',
                t: dien(chon(MO_VIDEO, `${khoa}v`), { x: vd }),
            });
        }

        if (it.viec) {
            out.push({ k: 'viec', t: `${gon(cat(it.viec), 70)}…` });
        }

        return out;
    }
}

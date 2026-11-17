// "Tự thoại" của từng nhân vật ở Khu Tự Trị: nhân vật đang làm việc thật nào thì lẩm bẩm đúng việc đó, với số liệu thật
// (hook vừa chốt, lỗi giám khảo bắt, giọng dài bao nhiêu giây, kênh nào đang đăng, AI nhìn video ra sản phẩm gì…).
// KHÔNG gọi AI, KHÔNG bịa: chỉ ghép mẫu câu (giọng bỗ bã, chửi nhẹ được) với dữ liệu trong sự kiện.
// Chọn mẫu theo id sự kiện (cố định), nên bong bóng trên đầu và sổ tự thoại trong bàn làm việc nói cùng một câu.
import type { NhaData, NhaEvent } from './types';

/** Một câu tự thoại. `who` = khoá nhân vật trong data.vai (đạo diễn chung khoá "daodien"). */
export interface TuThoai {
    id: string;
    n: number;
    who: string;
    text: string;
}

/** Việc thật của các vai lo app (NhaHoatDong.php). */
export interface HoatDong {
    id: string;
    n: number;
    vai: string;
    loai: string;
    [k: string]: unknown;
}

type Vars = Record<string, string | number | null | undefined>;

const MAU: Record<string, string[]> = {
    // ---- Biên kịch
    'bienkich.goi': [
        'Nặn {so} bài cho {sp} đây, hook không ra tiền là xé.',
        'Lần {lan} rồi, thêm {so} bài nữa… đầu bốc khói luôn.',
        'Ngồi rặn {so} cái hook, cái nào nhạt là vô sọt rác.',
    ],
    'bienkich.loai': [
        'Moẹ, bài kiểu {kieu} dính lỗi "{loi}". Xé!',
        'Viết kiểu gì mà "{loi}"… bỏ, viết lại.',
        'Máy soát bắt "{loi}", thôi khỏi cãi, làm lại.',
    ],
    'bienkich.dat': [
        'Chốt bài {so}/{tong}: "{hook}" — tự chấm {diem}đ.',
        '"{hook}"… nghe là muốn bấm giỏ, chốt bài {so}!',
        'Hook bài {so} nè: "{hook}". {diem} điểm, không khiêm tốn.',
        'Chốt bài {so}/{tong}: "{hook}"',
    ],
    'bienkich.xong': [
        'Xong {so} lời rồi, đưa qua thu âm nè.',
        'Đủ {so} lời, thu âm nhận việc đi!',
    ],
    // ---- Thu âm
    'thuam.bat-dau': [
        'Vô thu {so} giọng, im lặng giùm cái.',
        'Mic lên, thu {so} giọng nè.',
    ],
    'thuam.xong1': [
        'Thu xong một giọng {dur} giây, ngọt như mía lùi.',
        'Giọng {dur} giây, vừa khít khung, ngon.',
        'Xong giọng góc {goc}, {dur} giây chẵn.',
    ],
    'thuam.dai': [
        'Moẹ, giọng dài {dur} giây, lố khung rồi, bỏ!',
        '{dur} giây? Dài như đọc sớ, vứt.',
    ],
    'thuam.hong': [
        'Giọng thu hỏng mất tiêu: {loi}. Bực ghê.',
        'Trời má, thu hỏng: {loi}.',
    ],
    'thuam.xong': ['Thu xong {so} giọng, đạo diễn vô việc!'],
    // ---- Đạo diễn
    'daodien.bat-dau': [
        'Lên bảng dựng {vid} theo gu {gu}.',
        'Gu {gu} nha, {vid} phải cuốn từ giây đầu.',
        'Để coi {vid} xếp cảnh sao cho đã mắt.',
    ],
    'daodien.xong': [
        'Xong bảng dựng {vid}: {so_canh} cảnh, công thức {cong_thuc}.',
        'Ý tưởng {vid}: {y}',
        '{so_canh} cảnh cho {vid}, giao thợ dựng nè.',
    ],
    'daodien.may': ['Đơ não rồi, cho máy tự dựng {vid} thay…'],
    'daodien.loi': ['Moẹ, hỏng: {msg}'],
    // ---- Thợ dựng
    'thodung.bat-dau': [
        'Ráp nền {vid}, FFmpeg chạy hừng hực.',
        'Dựng nền {vid} đây, đừng ai đụng máy.',
    ],
    'thodung.xong.nhac': [
        'Nền {vid} xong, có nhạc luôn, êm.',
        'Xong nền {vid}, nhạc vô rồi.',
    ],
    'thodung.xong.khong-nhac': [
        'Nền {vid} xong mà chưa có nhạc, lát anh chọn nhạc TikTok nha.',
    ],
    'thodung.xong': ['Nền {vid} xong, đưa đi đắp chữ.', 'Xong nền {vid}.'],
    'thodung.chu': [
        'Chạy lớp chữ {so} video, Remotion ơi nhanh lên.',
        'Đắp chữ cho {so} video, cực muốn xỉu.',
    ],
    'thodung.chu-xong': ['{msg}, đưa giám khảo soi đi.'],
    'thodung.dung-lai': ['Lại dựng lại {so} bản theo ý giám khảo… cực ghê.'],
    // ---- Giám khảo
    'giamkhao.bat-dau': [
        'Mở {vid} ra coi thử…',
        'Để coi {vid} làm ăn ra sao.',
        'Soi {vid} từng giây nè.',
    ],
    'giamkhao.dat': [
        '{vid}: {diem}đ, ngon, cho qua.',
        'Được đó, {vid} {diem}đ, cất kho!',
        '{diem}đ, ngon, cho qua.',
    ],
    'giamkhao.dat.loi': [
        '{vid} {diem}đ, qua nhưng còn chút: {loi}.',
        'Cho {vid} {diem}đ, mà {loi} nha, lần sau sửa.',
    ],
    'giamkhao.truot': [
        'Moẹ, làm kiểu gì mà {loi}… {vid} cho {diem}đ về chỗ!',
        '{vid}: {loi}. {diem} điểm, làm lại đi.',
        'Trời đất, {loi}. {vid} {diem} điểm thôi.',
        'Moẹ, làm kiểu gì mà {loi}… cho {diem}đ về chỗ!',
    ],
    'giamkhao.chua-cham': ['{vid} chưa chấm được: {loi}. Bó tay.'],
    'giamkhao.hoc': ['Gom bài học lô này, lần sau mà lặp lỗi là biết tay.'],
    // ---- Thủ kho
    'thukho.luu': [
        'Nhập kho video {so}/{tong}, {diem}đ.',
        'Cất thêm một cuộn lên kệ, {so}/{tong}.',
    ],
    'thukho.ai-dang': [
        'AI đang soi {video}…',
        'Cho AI coi {video}, chờ chút.',
        'AI đang làm: {y}',
    ],
    'thukho.ai-ok': [
        'AI nhìn {video} ra {san_pham}, chắc {chac}.',
        '{video} là {san_pham}, AI chốt rồi.',
    ],
    'thukho.ai-unsure': [
        '{video} AI phân vân, đoán {san_pham}, anh coi lại giùm.',
        'AI không chắc {video} là gì, anh chọn giùm cái.',
    ],
    'thukho.ai-loi': [
        'AI xem {video} lỗi: {loi}. Hên xui thử lại.',
        'Moẹ, AI kẹt ở {video}: {loi}.',
    ],
    // ---- Bưu tá
    'buuta.claimed': [
        'Nhận bài {video} cho {kenh}, xách lên Chrome.',
        'Có bài cho {kenh}, đi liền!',
    ],
    'buuta.uploading': [
        'Đang tải {video} lên {kenh}… đừng có rớt mạng nha.',
        'Tải {video} lên {kenh}, chờ xíu.',
    ],
    'buuta.ready': ['{video} lên tới {kenh} rồi, chờ TikTok gật đầu.'],
    'buuta.authorized': ['{kenh} cho đăng rồi, bấm nút nè.'],
    'buuta.da-dang': [
        'Đăng xong {video} lên {kenh}! Ting ting.',
        '{kenh} có bài mới rồi, nhẹ cả người.',
    ],
    'buuta.dang-loi': [
        'Moẹ, {kenh} đăng hỏng: {loi}.',
        'Đăng {video} không được: {loi}. Bực!',
    ],
    'buuta.xep-hang': [
        '{kenh} đang bận, xếp {video} vào hàng chờ.',
        'Xếp hàng {kenh}, tới lượt là đi.',
    ],
    // ---- Chủ quầy
    'chuquay.lay-gio': [
        'Đi lấy giỏ {kenh} đây…',
        'Hỏi TikTok Shop giỏ của {kenh} nè.',
    ],
    'chuquay.lay-gio-xong': [
        'Lấy giỏ {kenh} xong, {so} sản phẩm.',
        'Giỏ {kenh} về rồi: {so} món.',
    ],
    'chuquay.lay-gio-rong': [
        'Lấy giỏ {kenh} về tay trắng, 0 sản phẩm, kỳ ghê.',
    ],
    'chuquay.lay-gio-loi': [
        'Lấy giỏ {kenh} không được: {loi}.',
        'Moẹ, giỏ {kenh} kẹt: {loi}.',
    ],
    // ---- Cú
    'cu.hoi-mua': [
        'Có khách {ai} hỏi mua: "{y}" — chốt đơn đi sếp!',
        'Bình luận hỏi mua nè: "{y}"',
    ],
    // ---- Mèo
    'meo.chrome-tat': [
        'Chrome mất kết nối {so} phút rồi, meo!',
        'Meo… Chrome im re {so} phút rồi.',
    ],
};

const VAI_HUB: Record<string, string> = {
    'bien-kich': 'bienkich',
    giong: 'thuam',
    'dao-dien': 'daodien',
    dung: 'thodung',
    'giam-khao': 'giamkhao',
    kho: 'thukho',
};

/** Băm chuỗi ra số (chọn mẫu cố định theo id). */
const bam = (s: string): number => {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
        h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    }

    return h >>> 0;
};

const rong = (v: unknown) => v === null || v === undefined || v === '';

const fill = (t: string, v: Vars): string | null => {
    let ok = true;
    const out = t.replace(/\{(\w+)\}/g, (_, k: string) => {
        if (rong(v[k])) {
            ok = false;

            return '';
        }

        return String(v[k]);
    });

    return ok ? out : null;
};

/** Chọn một mẫu theo id; mẫu nào thiếu số liệu thì thử mẫu kế. */
export const chon = (key: string, id: string, v: Vars): string | null => {
    const pool = MAU[key] ?? [];
    const s = bam(id + key);
    for (let i = 0; i < pool.length; i++) {
        const t = fill(pool[(s + i) % pool.length], v);
        if (t) {
            return t.charAt(0).toUpperCase() + t.slice(1); // "video 2a: …" → "Video 2a: …"
        }
    }

    return null;
};

/** "…-03-1" (lời 03, đạo diễn thứ 2) → "video 4b". */
export const tenVideo = (video?: string | null): string | null => {
    if (!video) {
        return null;
    }
    const m = video.match(/-(\d{1,3})-(\d)$/);
    if (m) {
        return `video ${Number(m[1]) + 1}${m[2] === '0' ? 'a' : 'b'}`;
    }

    return null;
};

/** Tên file gọn để đọc: bỏ đuôi, cắt ngắn. */
const tenFile = (f?: unknown): string | null => {
    if (typeof f !== 'string' || !f.trim()) {
        return null;
    }
    const s = f.replace(/\.[a-z0-9]{2,4}$/i, '').trim();

    return s.length > 26 ? `${s.slice(0, 24)}…` : s;
};

/** Bỏ dấu câu cuối (mẫu câu tự thêm dấu, tránh `."` rồi lại `.`). */
const cut = (x?: string | null) =>
    x
        ? x
              .replace(/^\s*\[[^\]]*\]\s*/u, '') // bỏ nhãn "[máy]" đầu câu
              .trim()
              .replace(/[\s.!?…,;:]+$/u, '') || null
        : null;

const so1 = (x: unknown) =>
    typeof x === 'number'
        ? String(Math.round(x * 10) / 10).replace('.', ',')
        : null;

const CHAC: Record<string, string> = {
    cao: 'chắc nịch',
    vua: 'tương đối',
    thap: 'hơi hên xui',
};

/** Một sự kiện của hub sản xuất → câu tự thoại (null = sự kiện này không cần nói). */
export const tuThoaiHub = (e: NhaEvent, sp?: string | null): TuThoai | null => {
    const who = VAI_HUB[e.vai];
    if (!who) {
        return null;
    }
    const id = `hub:${e.n}`;
    const vid = tenVideo(e.video);
    const v: Vars = {
        so: e.so,
        tong: e.tong,
        lan: e.lan,
        sp: sp ?? null,
        kieu: e.kieu,
        loi: cut(e.loi),
        hook: cut(e.hook),
        diem: so1(e.diem),
        dur: so1(e.dur),
        goc: e.goc,
        vid,
        gu: e.gu,
        so_canh: e.so_canh || null,
        cong_thuc: e.cong_thuc,
        y: e.y,
        msg: e.msg,
    };
    let key: string | null = null;
    if (e.loai === 'nghi') {
        key = `${who}.${e.buoc}`;
    } else if (who === 'bienkich' && e.loai === 'xong') {
        key = 'bienkich.xong';
    } else if (who === 'thuam' && (e.loai === 'bat-dau' || e.loai === 'xong')) {
        key = `thuam.${e.loai}`;
    } else if (who === 'daodien') {
        key = e.loai === 'xong' && e.may ? 'daodien.may' : `daodien.${e.loai}`;
    } else if (who === 'thodung') {
        if (e.loai === 'dung-lai') {
            key = 'thodung.dung-lai';
        } else if (e.buoc === 'chu') {
            key = e.loai === 'bat-dau' ? 'thodung.chu' : 'thodung.chu-xong';
        } else if (e.loai === 'bat-dau') {
            key = 'thodung.bat-dau';
        } else if (e.loai === 'xong') {
            key =
                e.co_nhac === true
                    ? 'thodung.xong.nhac'
                    : e.co_nhac === false
                      ? 'thodung.xong.khong-nhac'
                      : 'thodung.xong';
        }
    } else if (who === 'giamkhao') {
        if (e.loai === 'diem') {
            key =
                e.diem == null
                    ? 'giamkhao.chua-cham'
                    : e.dat
                      ? e.loi
                          ? 'giamkhao.dat.loi'
                          : 'giamkhao.dat'
                      : 'giamkhao.truot';
        } else {
            key = `giamkhao.${e.loai}`;
        }
    } else if (who === 'thukho' && e.loai === 'luu') {
        key = 'thukho.luu';
    }
    const text = key ? chon(key, id, v) : null;

    return text ? { id, n: e.n, who, text } : null;
};

/** Một việc thật của app (đăng bài, giỏ, AI Kho riêng, bình luận, Chrome) → câu tự thoại. */
export const tuThoaiApp = (h: HoatDong): TuThoai | null => {
    const s = (k: string) =>
        typeof h[k] === 'string' ? (h[k] as string) : null;
    const v: Vars = {
        video: tenFile(h.video),
        kenh: s('kenh') ?? 'kênh',
        loi: cut(s('loi')),
        so: typeof h.so === 'number' ? h.so : null,
        san_pham: s('san_pham'),
        chac: CHAC[s('chac') ?? ''] ?? null,
        y: s('y'),
        ai: s('ai') ?? 'nào đó',
    };
    let key = `${h.vai}.${h.loai}`;
    if (h.vai === 'buuta' && h.loai === 'dang-dang') {
        key = `buuta.${s('buoc') ?? 'claimed'}`;
    } else if (h.vai === 'chuquay' && h.loai === 'lay-gio-xong' && h.so === 0) {
        key = 'chuquay.lay-gio-rong';
    } else if (h.vai === 'thukho' && h.loai === 'ai-xem') {
        key = s('state') === 'ok' ? 'thukho.ai-ok' : 'thukho.ai-unsure';
    }
    const text = chon(key, h.id, v);

    return text ? { id: `app:${h.id}`, n: h.n, who: h.vai, text } : null;
};

/** Toàn bộ tự thoại gần đây (hub + app), cũ → mới. */
export const tatCaTuThoai = (data: NhaData | null): TuThoai[] => {
    if (!data) {
        return [];
    }
    const out: TuThoai[] = [];
    for (const e of data.events ?? []) {
        const t = tuThoaiHub(e, data.bang?.san_pham);
        if (t) {
            out.push(t);
        }
    }
    for (const h of data.hoat_dong ?? []) {
        const t = tuThoaiApp(h);
        if (t) {
            out.push(t);
        }
    }

    return out.sort((a, b) => a.n - b.n);
};

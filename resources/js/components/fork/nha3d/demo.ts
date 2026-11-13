// /nha?demo=1: phát lại một lô sản xuất GIẢ hoàn toàn trong trình duyệt (không gọi máy chủ, không đụng dữ liệu thật).
// `?t=giây` để nhảy tới một thời điểm (các sự kiện trước đó coi như lịch sử, không diễn lại).
import type { NhaData, NhaEvent, VaiInfo } from '../nha/types';

type Ev = Omit<NhaEvent, 'n' | 't'>;

interface Beat {
    at: number;
    ev?: Ev;
    state?: Partial<Record<string, [VaiInfo['state'], string | null]>>;
    mode?: NhaData['mode'];
    tien?: number;
    dong?: string;
    post?: 'scheduled' | 'posted';
}

const SP = 'Bình giữ nhiệt mini';
const V = (j: number) => `binh-giu-nhiet-${j}`;

const BEATS: Beat[] = [
    {
        at: 4,
        ev: {
            vai: 'he-thong',
            loai: 'bat-dau-lo',
            ten: SP,
            so_video: 3,
            msg: 'Bắt đầu lô',
        },
        mode: 'working',
        tien: 0,
        dong: 'Biên kịch đang viết lời',
        state: { bienkich: ['working', 'Đang viết 3 lời…'] },
    },
    {
        at: 12,
        ev: { vai: 'bien-kich', loai: 'xong', so: 3 },
        dong: 'Thu âm đang thu giọng',
        state: {
            bienkich: ['idle', null],
            thuam: ['working', 'Đang thu 3 giọng…'],
        },
    },
    { at: 16, post: 'scheduled' },
    {
        at: 26,
        ev: { vai: 'giong', loai: 'xong', so: 3 },
        dong: 'Đạo diễn đang lên bảng dựng',
        state: {
            thuam: ['idle', null],
            daodien: ['working', '2 đạo diễn đang lên bảng dựng…'],
        },
    },
    { at: 40, ev: { vai: 'dao-dien', loai: 'xong', video: V(0) } },
    {
        at: 46,
        ev: { vai: 'dao-dien', loai: 'xong', video: V(1) },
        dong: 'Thợ dựng đang dựng',
        state: {
            daodien: ['idle', null],
            thodung: ['working', 'Đang dựng 3 video…'],
        },
    },
    {
        at: 58,
        ev: { vai: 'dung', loai: 'xong', video: V(0) },
        dong: 'Giám khảo đang chấm',
        state: { giamkhao: ['working', 'Đang chấm bản đầu…'] },
    },
    {
        at: 64,
        ev: { vai: 'giam-khao', loai: 'diem', video: V(0), diem: 9, dat: true },
        state: { giamkhao: ['working', 'Đang chấm 1/3 · 9 điểm'] },
    },
    {
        at: 72,
        ev: {
            vai: 'kho',
            loai: 'luu',
            video: V(0),
            so: 1,
            tong: 3,
            diem: 9,
            file: 'demo-binh-1.mp4',
        },
        tien: 1,
        dong: 'Đã lưu video 1/3',
        state: { thukho: ['working', 'Nhập kho video 1/3'] },
    },
    {
        at: 96,
        ev: {
            vai: 'giam-khao',
            loai: 'diem',
            video: V(1),
            diem: 6,
            dat: false,
            loi: 'chữ che mặt sản phẩm ở giây 3',
        },
        state: {
            thukho: ['idle', null],
            giamkhao: ['working', 'Đang chấm 2/3 · 6 điểm'],
        },
    },
    { at: 124, ev: { vai: 'dung', loai: 'xong', video: V(1) } },
    {
        at: 128,
        ev: { vai: 'giam-khao', loai: 'diem', video: V(1), diem: 8, dat: true },
        state: { giamkhao: ['working', 'Đang chấm 2/3 · 8 điểm'] },
    },
    {
        at: 134,
        ev: {
            vai: 'kho',
            loai: 'luu',
            video: V(1),
            so: 2,
            tong: 3,
            diem: 8,
            file: 'demo-binh-2.mp4',
        },
        tien: 2,
        dong: 'Đã lưu video 2/3',
        state: { thukho: ['working', 'Nhập kho video 2/3'] },
    },
    {
        at: 150,
        ev: { vai: 'giong', loai: 'loi', msg: 'mạng chập chờn' },
        state: { thukho: ['idle', null] },
    },
    {
        at: 156,
        ev: { vai: 'he-thong', loai: 'het-han-muc', msg: 'Hết hạn mức Claude' },
        mode: 'limit',
        dong: 'Hết hạn mức Claude. Vào Xưởng Video > Cài đặt để đổi tài khoản rồi chạy tiếp.',
    },
    {
        at: 180,
        ev: {
            vai: 'he-thong',
            loai: 'bat-dau-lo',
            ten: SP,
            so_video: 3,
            msg: 'Chạy tiếp',
        },
        mode: 'working',
        dong: 'Thợ dựng đang dựng video cuối',
        state: {
            thodung: ['working', 'Đang dựng 1 video…'],
            giamkhao: ['idle', null],
        },
    },
    {
        at: 190,
        ev: { vai: 'dung', loai: 'xong', video: V(2) },
        state: {
            thodung: ['idle', null],
            giamkhao: ['working', 'Đang chấm 3/3…'],
        },
    },
    {
        at: 196,
        ev: { vai: 'giam-khao', loai: 'diem', video: V(2), diem: 9, dat: true },
    },
    {
        at: 202,
        ev: {
            vai: 'kho',
            loai: 'luu',
            video: V(2),
            so: 3,
            tong: 3,
            diem: 9,
            file: 'demo-binh-3.mp4',
        },
        tien: 3,
        dong: 'Đã lưu video 3/3',
        state: {
            giamkhao: ['idle', null],
            thukho: ['working', 'Nhập kho video 3/3'],
        },
    },
    {
        at: 222,
        ev: { vai: 'he-thong', loai: 'ket-thuc-lo', so: 3, tong: 3, phut: 4.2 },
        mode: 'idle',
        dong: 'Xong 3/3 · 4,2 phút',
        state: { thukho: ['idle', null] },
    },
    { at: 236, post: 'posted' },
];
const LOOP = 270;
const KEYS = [
    'bienkich',
    'thuam',
    'daodien',
    'thodung',
    'giamkhao',
    'thukho',
    'chuquay',
    'cu',
    'buuta',
];

const pad = (n: number) => String(n).padStart(2, '0');
const localIso = (d: Date) =>
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

export const createDemo = (startAt = 0) => {
    const t0 = performance.now() - startAt * 1000;
    const wall0 = Date.now() - startAt * 1000;
    const base = Math.floor(wall0 * 1000);
    const today = localIso(new Date()).slice(0, 10);

    return {
        snapshot(): NhaData {
            const el = (performance.now() - t0) / 1000;
            const loop = Math.floor(el / LOOP);
            const inLoop = el - loop * LOOP;
            const vai: Record<string, VaiInfo> = {};
            KEYS.forEach((k) => (vai[k] = { state: 'idle', bubble: null }));
            let mode: NhaData['mode'] = 'idle';
            let tien = 0;
            let dong = 'Chưa có lô nào đang chạy (xem thử)';
            let started = false;
            let lo: number | null = null;
            const events: NhaEvent[] = [];
            const reels: NonNullable<NhaData['reels']> = [];
            let scheduled = 3 + loop * 1;
            let posted = 5 + loop * 1;
            // các vòng trước: chỉ còn là lịch sử sự kiện
            for (let L = 0; L <= loop; L++) {
                for (const [i, b] of BEATS.entries()) {
                    const at = L * LOOP + b.at;
                    if (at > el) {
                        break;
                    }
                    if (b.post && L === loop) {
                        if (b.post === 'scheduled') {
                            scheduled++;
                        } else {
                            posted++;
                        }
                    }
                    if (b.ev) {
                        const n = base + (L * 100 + i) * 1_000_000 + at * 1000;
                        const ev: NhaEvent = {
                            ...b.ev,
                            n,
                            t: localIso(new Date(wall0 + at * 1000)),
                        };
                        if (ev.loai === 'luu') {
                            ev.ngay = today;
                        }
                        events.push(ev);
                        if (L === loop) {
                            if (ev.loai === 'bat-dau-lo' && lo === null) {
                                lo = n;
                            }
                            if (ev.loai === 'luu') {
                                reels.push({
                                    n,
                                    so: ev.so ?? 0,
                                    file: ev.file ?? '',
                                    ngay: today,
                                    diem: ev.diem ?? null,
                                });
                            }
                        }
                    }
                    if (L === loop) {
                        started = true;
                        if (b.mode) {
                            mode = b.mode;
                        }
                        if (b.tien !== undefined) {
                            tien = b.tien;
                        }
                        if (b.dong) {
                            dong = b.dong;
                        }
                        for (const [k, v] of Object.entries(b.state ?? {})) {
                            vai[k] = { state: v![0], bubble: v![1] };
                        }
                    }
                }
            }
            if (mode === 'limit') {
                KEYS.filter((k) => k !== 'buuta').forEach(
                    (k) => (vai[k] = { state: 'sleep', bubble: null }),
                );
            }
            const working = mode === 'working';
            const line = working
                ? `Xưởng đang làm 3 video ${SP} · ${tien}/3 (xem thử)`
                : mode === 'limit'
                  ? `Xưởng tạm nghỉ vì hết hạn mức Claude · đã xong ${tien}/3 (xem thử)`
                  : 'Xưởng đang nghỉ · chế độ xem thử';

            return {
                mode,
                line,
                vai,
                bang: {
                    san_pham: started ? SP : null,
                    tien_do: started ? { xong: tien, tong: 3 } : null,
                    dong,
                },
                hub: { up: true, dang_chay: working, url: '' },
                lo,
                reels,
                events: events.slice(-60),
                bay_gio: Date.now() / 1000,
                app: {
                    posts_today: 2,
                    next: null,
                    chrome_online: true,
                    post_counts: { scheduled, posted },
                },
            };
        },
    };
};

// Hiệu ứng "chữ tự gõ ra" cho màn hình trực tiếp: chữ mới về thì hiện dần trong ~1 giây (requestAnimationFrame, chỉ chạy khi còn
// chữ chưa hiện), không giật cục. Lần đầu mở (đã có sẵn chữ) hiện luôn, không diễn lại. `prefers-reduced-motion` thì hiện luôn.
import { onBeforeUnmount, shallowRef, watch } from 'vue';

export interface HangChu {
    text: string;
    /** Số ký tự đã hiện. */
    hien: number;
    /** Đây là dòng đang gõ dở (có con trỏ nhấp nháy). */
    dang: boolean;
}

export interface NguonChu {
    dong: string[];
    dang: string | null;
}

const chung = (a: string, b: string): number => {
    const n = Math.min(a.length, b.length);
    let i = 0;

    while (i < n && a.charCodeAt(i) === b.charCodeAt(i)) {
        i++;
    }

    return i;
};

/** Thời gian để hiện hết phần chữ mới (giây). */
const THOI_GIAN = 1;
const TOC_DO_MIN = 40; // ký tự/giây

/** Ghép các dòng cũ và mới: dòng giống (hoặc đang dài thêm) giữ nguyên phần đã hiện, dòng mới bắt đầu từ 0. Xuất ra để kiểm. */
export const ghepHang = (
    cu: HangChu[],
    nguon: NguonChu,
    ngay: boolean,
): HangChu[] => {
    const rows: { text: string; dang: boolean }[] = nguon.dong.map((text) => ({
        text,
        dang: false,
    }));

    if (nguon.dang) {
        rows.push({ text: nguon.dang, dang: true });
    }
    const dung = new Set<number>();

    return rows.map(({ text, dang }) => {
        if (ngay) {
            return { text, hien: text.length, dang };
        }
        let tot = -1;
        let diem = 0;

        cu.forEach((o, j) => {
            if (dung.has(j)) {
                return;
            }
            const c = chung(o.text, text);
            const du =
                o.text === text ||
                c >= Math.max(6, Math.min(o.text.length, text.length) * 0.6);

            if (du && c + (o.text === text ? 1 : 0) > diem) {
                diem = c + (o.text === text ? 1 : 0);
                tot = j;
            }
        });

        if (tot < 0) {
            return { text, hien: 0, dang };
        }
        dung.add(tot);

        return {
            text,
            hien: Math.min(cu[tot].hien, chung(cu[tot].text, text)),
            dang,
        };
    });
};

export const useGoChu = (nguon: () => NguonChu) => {
    const hang = shallowRef<HangChu[]>([]);
    const giam =
        typeof window !== 'undefined' &&
        (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ??
            false);
    let lanDau = true;
    let raf = 0;
    let to = 0;
    let chay = false; // vòng gõ đang chạy
    let truoc = 0;
    let du = 0;

    // Hẹn nhịp kế: requestAnimationFrame (mượt), kèm đồng hồ dự phòng 100ms phòng trường hợp khung hình bị tạm dừng
    // (cửa sổ bị che, trình duyệt giảm tốc) — nhịp nào tới trước thì chạy, nhịp kia huỷ.
    const hen = () => {
        const chayMot = () => {
            cancelAnimationFrame(raf);
            window.clearTimeout(to);
            buoc(performance.now());
        };
        raf = requestAnimationFrame(chayMot);
        to = window.setTimeout(chayMot, 100);
    };

    const buoc = (t: number) => {
        if (!chay) {
            return;
        }
        const dt = truoc ? Math.min(0.5, (t - truoc) / 1000) : 0.016;
        truoc = t;
        const rows = hang.value;
        const con = rows.reduce((s, r) => s + (r.text.length - r.hien), 0);

        if (con <= 0) {
            chay = false;
            truoc = 0;
            du = 0;

            return;
        }
        du += Math.max(TOC_DO_MIN, con / THOI_GIAN) * dt;
        let n = Math.floor(du);
        du -= n;

        if (n > 0) {
            hang.value = rows.map((r) => {
                if (n <= 0 || r.hien >= r.text.length) {
                    return r;
                }
                const lay = Math.min(n, r.text.length - r.hien);
                n -= lay;

                return { ...r, hien: r.hien + lay };
            });
        }
        hen();
    };
    const batDau = () => {
        if (!chay && typeof requestAnimationFrame !== 'undefined') {
            chay = true;
            hen();
        }
    };

    watch(
        nguon,
        (n) => {
            const co = n.dong.length > 0 || !!n.dang;
            hang.value = ghepHang(hang.value, n, lanDau || giam);

            if (co) {
                lanDau = false;
            }

            if (!giam) {
                batDau();
            }
        },
        { immediate: true, deep: false },
    );
    onBeforeUnmount(() => {
        chay = false;
        cancelAnimationFrame(raf);
        window.clearTimeout(to);
    });

    return { hang };
};

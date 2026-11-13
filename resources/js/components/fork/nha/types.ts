// Kiểu dùng chung của "Xưởng nhỏ".
export type VaiState = 'working' | 'idle' | 'sleep';

/** Thông số đặt một căn phòng/nhân vật vào ngôi nhà (toạ độ viewBox của nhà). */
export interface RoomProps {
    x: number;
    y: number;
    state?: VaiState;
    dim?: boolean;
}

export interface VaiInfo {
    state: VaiState;
    bubble: string | null;
}

/** Một sự kiện của sổ sự kiện hub (xem xuong-video/engine/su_kien.py). */
export interface NhaEvent {
    n: number;
    t?: string;
    vai: string;
    loai: string;
    video?: string;
    msg?: string;
    so?: number;
    tong?: number;
    diem?: number | null;
    dat?: boolean | null;
    file?: string;
    ngay?: string;
    loi?: string;
    phut?: number;
    ten?: string;
    so_video?: number;
    lan?: number;
    buoc?: string;
}

export interface NhaData {
    mode: 'down' | 'working' | 'idle' | 'limit';
    line: string;
    vai: Record<string, VaiInfo>;
    bang: { san_pham: string | null; tien_do: { xong: number; tong: number } | null; dong: string };
    hub: { up: boolean; dang_chay: boolean; url?: string };
    lo?: number | null;
    reels?: { n: number; so: number; file: string; ngay: string; diem: number | null }[];
    events?: NhaEvent[];
    bay_gio?: number;
    app: { posts_today?: number; next?: { at: string; minutes: number; channel: string } | null; chrome_online?: boolean | null; post_counts?: { scheduled: number; posted: number } };
}

/** Nơi mỗi nhân vật dẫn tới khi bấm. */
export interface Dich {
    href: string | null;
    ten: string; // "Biên kịch"
    dich: string; // "Xưởng Video › Prompt AI"
}

export const DICH: Record<string, Dich> = {
    bienkich: { href: '/xuong?tab=prompt-ai&muc=bien-kich', ten: 'Biên kịch', dich: 'Xưởng Video › Prompt AI' },
    thuam: { href: '/xuong?tab=cai-dat&muc=giong', ten: 'Thu âm', dich: 'Xưởng Video › Cài đặt › Giọng đọc' },
    daodien: { href: '/xuong?tab=gu', ten: 'Đạo diễn', dich: 'Xưởng Video › Gu & bài học' },
    thodung: { href: '/xuong?tab=san-xuat', ten: 'Thợ dựng', dich: 'Xưởng Video › Sản xuất' },
    giamkhao: { href: '/xuong?tab=kho', ten: 'Giám khảo', dich: 'Xưởng Video › Kho video' },
    thukho: { href: '/xuong?tab=san-pham', ten: 'Thủ kho', dich: 'Xưởng Video › Sản phẩm & quà' },
    buuta: { href: '/auto', ten: 'Bưu tá', dich: 'Tự động đăng › Tổng quan & Lịch' },
    chuquay: { href: '/auto/gio-hang', ten: 'Chủ quầy', dich: 'Giỏ hàng' },
    cu: { href: '/auto/so-lieu', ten: 'Cú thông thái', dich: 'Số liệu' },
    bang: { href: '/xuong?tab=san-xuat', ten: 'Bảng việc', dich: 'Xưởng Video › Sản xuất' },
    meo: { href: null, ten: 'Mèo', dich: '' },
};

// "Bàn làm việc": bấm nhân vật / phòng trong Khu Tự Trị thì mở popup làm việc của vai đó ngay tại chỗ.
// Mỗi vai một component (tải lười). Thêm vai mới: tạo file *Ban.vue trong thư mục này rồi khai báo ở đây.
import { defineAsyncComponent, type Component } from 'vue';

import { DICH } from '@/components/fork/nha/types';

export interface BanDef {
    /** Tên hiện trên đầu popup. */
    ten: string;
    /** Một dòng mô tả việc của bàn này. */
    mo_ta: string;
    emoji: string;
    /** Màu nhấn của vai (gradient avatar ở đầu popup). */
    mau: string;
    /** Trang đầy đủ (nút "Mở trang đầy đủ ↗"); null = không có. */
    full: string | null;
    /** Vai trong `data.vai` để lấy trạng thái/lời thoại (mặc định = key). */
    vai?: string;
    component: Component;
}

const lazy = (loader: () => Promise<{ default: Component }>) =>
    defineAsyncComponent({ loader, delay: 0 });

export const BAN: Record<string, BanDef> = {
    // ---- Giai đoạn 1: dữ liệu trang Tự động đăng (đọc qua useInertiaProps)
    buuta: {
        ten: 'Bưu tá',
        mo_ta: 'Lịch đăng 3 ngày, bài kế tiếp, bài lỗi',
        emoji: '📮',
        mau: 'from-sky-400 to-indigo-500',
        full: '/auto',
        component: lazy(() => import('./BuuTaBan.vue')),
    },
    chuquay: {
        ten: 'Chủ quầy',
        mo_ta: 'Giỏ hàng TikTok Shop cho từng sản phẩm',
        emoji: '🛒',
        mau: 'from-rose-400 to-orange-400',
        full: '/auto/gio-hang',
        component: lazy(() => import('./ChuQuayBan.vue')),
    },
    cu: {
        ten: 'Cú thông thái',
        mo_ta: 'Số liệu 7 ngày, video nổi bật, bình luận hỏi mua',
        emoji: '📊',
        mau: 'from-amber-400 to-yellow-500',
        full: '/auto/so-lieu',
        component: lazy(() => import('./CuBan.vue')),
    },
    thukho: {
        ten: 'Thủ kho',
        mo_ta: 'Kho video chờ đăng và sản phẩm của xưởng',
        emoji: '📦',
        mau: 'from-emerald-400 to-teal-500',
        full: '/auto/kho',
        component: lazy(() => import('./ThuKhoBan.vue')),
    },
    sanh: {
        ten: 'Sảnh',
        mo_ta: 'Bảng tin: hôm nay thế nào, việc gì cần anh xử lý',
        emoji: '🏠',
        mau: 'from-violet-400 to-fuchsia-500',
        full: null,
        vai: 'buuta',
        component: lazy(() => import('./SanhBan.vue')),
    },
    // ---- Giai đoạn 2: phần của Xưởng Video (nhúng hub ở chế độ gọn qua HubEmbed)
    thodung: {
        ten: 'Thợ dựng',
        mo_ta: 'Làm video mới, tiến độ lô, nhật ký',
        emoji: '🛠️',
        mau: 'from-orange-400 to-red-500',
        full: DICH.thodung.href,
        component: lazy(() => import('./ThoDungBan.vue')),
    },
    bang: {
        ten: 'Bảng việc',
        mo_ta: 'Làm video mới, tiến độ lô, nhật ký',
        emoji: '📋',
        mau: 'from-orange-400 to-red-500',
        full: DICH.bang.href,
        vai: 'thodung',
        component: lazy(() => import('./ThoDungBan.vue')),
    },
    giamkhao: {
        ten: 'Giám khảo',
        mo_ta: 'Video vừa làm, điểm chấm, Ưng / Bỏ',
        emoji: '🧐',
        mau: 'from-lime-400 to-emerald-500',
        full: DICH.giamkhao.href,
        component: lazy(() => import('./GiamKhaoBan.vue')),
    },
    daodien: {
        ten: 'Đạo diễn',
        mo_ta: 'Gu của anh và bài học giám khảo',
        emoji: '🎬',
        mau: 'from-purple-400 to-violet-600',
        full: DICH.daodien.href,
        component: lazy(() => import('./DaoDienBan.vue')),
    },
    bienkich: {
        ten: 'Biên kịch',
        mo_ta: 'Prompt viết lời cho video',
        emoji: '✍️',
        mau: 'from-pink-400 to-rose-500',
        full: DICH.bienkich.href,
        component: lazy(() => import('./BienKichBan.vue')),
    },
    thuam: {
        ten: 'Thu âm',
        mo_ta: 'Giọng đọc ElevenLabs, nghe thử',
        emoji: '🎙️',
        mau: 'from-cyan-400 to-sky-500',
        full: DICH.thuam.href,
        component: lazy(() => import('./ThuAmBan.vue')),
    },
};

/** Thứ tự trên thanh avatar (giai đoạn 3). */
export const BAN_THU_TU = [
    'sanh',
    'buuta',
    'chuquay',
    'cu',
    'thukho',
    'thodung',
    'giamkhao',
    'daodien',
    'bienkich',
    'thuam',
];

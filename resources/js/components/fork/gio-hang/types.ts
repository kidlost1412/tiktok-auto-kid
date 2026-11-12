// Kiểu dữ liệu dùng chung của trang "Giỏ hàng" (/auto/gio-hang).

export interface ShopCard {
    product_id: string; // luôn là chuỗi (19 chữ số), không ép sang số
    title: string;
    price: string | null;
    cover_url: string | null;
    /** Ảnh đã tải về máy (ưu tiên, link CDN gốc hết hạn). */
    image?: string | null;
    stock_num: number;
    source: string | null;
    hidden: boolean;
    missing: boolean;
}

export interface ShopProduct extends ShopCard {
    suggested_name: string;
    used_by: string[];
}

export interface Row {
    key: string;
    code: string;
    quy_cach: string | null;
    label: string;
    hub_name: string;
    quy_cach_name: string | null;
    enabled: boolean;
    new_videos: number;
    link: {
        shop_product_id: string;
        display_name: string;
        paused_reason: string | null;
        problem: string | null;
        product: ShopCard | null;
    } | null;
}

export interface Sync {
    state: 'idle' | 'waiting' | 'error' | 'expired' | 'done';
    reason: string | null;
    requested_at: string | null;
    synced_at: string | null;
}

/** Cá nhân hoá theo sản phẩm hub (ảnh bìa, hashtag). */
export interface Persona {
    cover_mode: 'default' | 'fixed' | 'random';
    cover_fixed: string | null;
    covers: {
        file: string;
        name: string;
        w: number;
        h: number;
        size: number;
        url: string;
    }[];
    hashtags: string[];
    hashtag_mode: 'append' | 'replace';
    hashtag_pick: number;
}

export interface PersonaDefault {
    tags: string[];
    mode: 'append' | 'replace';
    pick: number;
}

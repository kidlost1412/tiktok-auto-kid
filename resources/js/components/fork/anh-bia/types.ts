// Kiểu dữ liệu của trang "Ảnh bìa & hashtag" (/auto/anh-bia-hashtag).

export interface PersonaProduct {
    code: string;
    name: string;
    full_name: string;
    image: string | null;
    /** Tên các quy cách (rỗng = sản phẩm một quy cách). */
    quy_cach: string[];
    videos_waiting: number;
    /** Caption cuối cùng của một bài ví dụ (caption video gần nhất, hoặc câu mẫu). */
    caption: {
        text: string;
        source: 'video' | 'sample';
        source_hashtags: 'product' | 'default' | 'none';
    };
}

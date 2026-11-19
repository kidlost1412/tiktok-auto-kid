// Lời chào theo giờ, dùng chung cho trang Khu Tự Trị (Nha.vue) và bàn Sảnh (SanhBan.vue).
// 0h–4h59 là khuya: không chào "buổi sáng" nữa mà nhắc anh nghỉ sớm.

const KHUYA = 'Khuya rồi, nghỉ sớm nha anh';

/** "Chào buổi sáng" / "Chào buổi trưa" / "Chào buổi chiều" / "Chào buổi tối", hoặc lời nhắc khuya. */
export const loiChao = (h: number): string =>
    h < 5
        ? KHUYA
        : h < 11
          ? 'Chào buổi sáng'
          : h < 14
            ? 'Chào buổi trưa'
            : h < 18
              ? 'Chào buổi chiều'
              : 'Chào buổi tối';

/** Lời chào gọi anh ở cuối: "Chào buổi sáng, anh." (khuya thì "Khuya rồi, nghỉ sớm nha anh."). */
export const loiChaoAnh = (h: number): string =>
    h < 5 ? `${KHUYA}.` : `${loiChao(h)}, anh.`;

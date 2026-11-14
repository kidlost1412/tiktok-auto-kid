// Kênh báo giữa popup "Bàn làm việc" và cảnh 3D: popup làm xong một việc thì báo, nhân vật trong cảnh phản ứng.
// Popup chỉ gọi banBao(...). Cảnh 3D (Nha3D.vue) nghe bằng onBanBao(...).
//
// Các việc đã quy ước (vai → viec):
//   buuta:    'xep-lich' (bấm Xếp lịch ngay), 'thu-lai' (Thử lại bài lỗi), 'xem' (mở xem video)
//   chuquay:  'luu-gio' (lưu giỏ / đổi sản phẩm shop), 'lay-lai' (Lấy lại từ shop)
//   cu:       'xem' (mở video / đổi khoảng ngày)
//   thukho:   'quet' (Quét kho ngay), 'xem'
//   giamkhao: 'ung' (duyệt), 'bo' (bỏ)
//   thodung:  'bat-dau' (Bắt đầu làm lô mới)
//   chung:    'mo' (popup vừa mở — nhân vật quay ra chào), 'dong'

export interface BanBao {
    vai: string;
    viec: string;
}

type Nghe = (b: BanBao) => void;
const nghe = new Set<Nghe>();

export const banBao = (vai: string, viec: string) => {
    nghe.forEach((f) => {
        try {
            f({ vai, viec });
        } catch {
            // một chỗ nghe lỗi không làm hỏng chỗ khác
        }
    });
};

/** Đăng ký nghe; trả hàm huỷ. */
export const onBanBao = (f: Nghe) => {
    nghe.add(f);

    return () => nghe.delete(f);
};

// ---- Mở một bàn khác từ trong popup (vd Sảnh bấm "2 giỏ thiếu" → mở bàn Chủ quầy). Nha.vue nghe.
type Mo = (vai: string) => void;
const moNghe = new Set<Mo>();

export const moBan = (vai: string) => moNghe.forEach((f) => f(vai));

export const onMoBan = (f: Mo) => {
    moNghe.add(f);

    return () => moNghe.delete(f);
};

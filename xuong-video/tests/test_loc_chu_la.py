"""Lọc chữ lạ (engine/loc_chu_la.py): khung giả bằng numpy/OpenCV, không cần video thật."""
import sys, unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import loc_chu_la as LC

W, H = 540, 960


def nen():
    """Nền êm (như tường/bầu trời), không có chữ."""
    return cv2.GaussianBlur(np.random.RandomState(1).randint(90, 140, (H // 16, W // 16, 3), dtype=np.uint8).repeat(16, 0).repeat(16, 1), (0, 0), 20)


def them_chu(img, y, chu="SALE HOI QUA HOI 99K", co=1.6):
    img = img.copy()
    cv2.putText(img, chu, (20, y), cv2.FONT_HERSHEY_DUPLEX, co, (0, 0, 0), 9, cv2.LINE_AA)       # viền đen
    cv2.putText(img, chu, (20, y), cv2.FONT_HERSHEY_DUPLEX, co, (255, 255, 255), 3, cv2.LINE_AA)  # ruột trắng
    return img


def doc_gia(*anh):
    return lambda path, ts, crop=None: [a.copy() for a in anh]


CANH = {"id": "0001", "file": "x.mp4", "tu": 0.0, "den": 9.0, "dai": 9.0}


class TestLocChuLa(unittest.TestCase):
    def test_khung_tron_sach(self):
        self.assertLess(LC.diem_khung([nen()] * 3), LC.NGUONG)

    def test_khung_co_chu_to_bi_bat(self):
        self.assertGreaterEqual(LC.diem_khung([them_chu(nen(), 800)] * 3), LC.NGUONG)

    def test_chu_tren_nhan_khong_tinh(self):
        a = them_chu(nen(), 480)                                   # chữ nằm giữa khung, đúng chỗ nhãn sản phẩm
        self.assertGreaterEqual(LC.diem_khung([a] * 3), LC.NGUONG)
        self.assertLess(LC.diem_khung([a] * 3, nhan=[0.0, 0.35, 1.0, 0.65]), LC.NGUONG)

    def test_phu_de_doi_chu_van_bat(self):
        self.assertGreaterEqual(LC.diem_khung([them_chu(nen(), 800, "ABC DEF GHI"), them_chu(nen(), 800, "XYZ KLM NOP"), them_chu(nen(), 800, "QRS TUV WXY")]), LC.NGUONG)

    def test_diem_chu_la_dung_doc_gia_va_khong_ghi_cache(self):
        self.assertGreaterEqual(LC.diem_chu_la(CANH, doc=doc_gia(*[them_chu(nen(), 800)] * 3)), LC.NGUONG)
        self.assertEqual(LC.diem_chu_la(CANH, doc=lambda *a: (_ for _ in ()).throw(OSError("hỏng"))), 0.0)    # video lỗi: không loại oan
        self.assertEqual(LC.diem_chu_la(CANH, doc=doc_gia()), 0.0)

    def test_tu_khoa_trong_ghi_soat(self):
        self.assertTrue(LC.la_chu_la({"soat": {"ghi": "Cảnh kết thúc hiện logo CapCut ở giữa"}}, 0.0))
        self.assertTrue(LC.la_chu_la({"soat": {"ghi": "Khung bình luận lớn che can"}}, 0.0))
        self.assertFalse(LC.la_chu_la({"soat": {"ghi": "Nam thanh niên nói về giá xả kho"}}, 0.0))      # nói giá bằng miệng ≠ chữ
        self.assertFalse(LC.la_chu_la({}, 0.0))

    def test_loc_bo_chu_la_va_giu_toi_thieu(self):
        sach, ban = [nen()] * 3, [them_chu(nen(), 800)] * 3
        ds = [dict(CANH, id=i, file=f"{i}.mp4") for i in "abcde"]
        anh = {"a": sach, "b": ban, "c": ban, "d": sach, "e": ban}
        orig = LC.doc_khung
        LC.doc_khung = lambda p, ts, crop=None: [x.copy() for x in anh[Path(str(p)).stem]]
        luu, LC._NHO = LC._NHO, {}
        LC.luu_cache = lambda: None
        try:
            self.assertEqual([s["id"] for s in LC.loc_chu_la(ds, toi_thieu=2)], ["a", "d"])
            LC._NHO = {}
            self.assertEqual(len(LC.loc_chu_la(ds, toi_thieu=3)), 3)         # thiếu → bù cảnh ít chữ nhất, giữ thứ tự gốc
            LC._NHO = {}
            self.assertEqual(len(LC.loc_chu_la(ds, toi_thieu=99)), 3)        # sàn tối đa 70% kho (5 → 3)
        finally:
            LC.doc_khung, LC._NHO = orig, luu


def mui_ten(img, mau=(0, 0, 230), x=300, y=500, k=1.0):
    """Mũi tên phẳng chéo (như sticker 'chỉ chỗ') màu mau."""
    img = img.copy()
    p = (np.array([(0, 45), (55, 0), (55, 25), (95, 25), (95, 65), (55, 65), (55, 90)]) * k).astype(np.int32) + (x, y)
    cv2.fillPoly(img, [p], mau)
    return img


def bong_bong(img, x=40, y=200, w=300, h=90, chu="Cà 3th phun được ko a"):
    """Bong bóng 'Trả lời bình luận': hộp trắng bo góc + chữ đen."""
    img = img.copy()
    cv2.rectangle(img, (x, y), (x + w, y + h), (255, 255, 255), -1)
    cv2.putText(img, chu, (x + 12, y + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20), 2, cv2.LINE_AA)
    return img


def la_xanh(seed=2):
    """Tán lá/cỏ giả: hue xanh, bão hoà cao, vân dày, thêm đốm cam/đỏ — không được báo là đồ hoạ lạ."""
    r = np.random.RandomState(seed)
    hsv = np.dstack([r.randint(35, 75, (H // 8, W // 8)), r.randint(150, 255, (H // 8, W // 8)), r.randint(70, 230, (H // 8, W // 8))]).astype(np.uint8)
    hsv[r.rand(*hsv.shape[:2]) < 0.03] = (12, 230, 220)
    return cv2.GaussianBlur(cv2.cvtColor(cv2.resize(hsv, (W, H), interpolation=cv2.INTER_CUBIC), cv2.COLOR_HSV2BGR), (0, 0), 1.5)


def cua_so(img, x=100, y=300, w=300, h=330):
    """Ảnh ghép: khung chữ nhật viền trắng, nội dung khác nền."""
    img = img.copy()
    img[y:y + h, x:x + w] = la_xanh(5)[y:y + h, x:x + w]
    cv2.rectangle(img, (x, y), (x + w, y + h), (255, 255, 255), 4)
    return img


def nen_dong(seed):
    """Cảnh đang chuyển động: mỗi khung một nền mịn khác hẳn."""
    return cv2.GaussianBlur(np.random.RandomState(seed).randint(40, 200, (H // 16, W // 16, 3), dtype=np.uint8).repeat(16, 0).repeat(16, 1), (0, 0), 6)


class TestDoHoaLa(unittest.TestCase):
    def test_mui_ten_do_va_vang_bi_bat(self):
        self.assertGreaterEqual(LC.diem_khung([mui_ten(nen())] * 3), LC.NGUONG)
        self.assertGreaterEqual(LC.diem_khung([mui_ten(nen(), mau=(0, 215, 255))] * 3), LC.NGUONG)       # vàng
        self.assertGreaterEqual(LC.diem_khung([nen(), mui_ten(nen()), mui_ten(nen())]), LC.NGUONG)       # mũi tên chỉ hiện ở vài khung

    def test_mui_ten_tren_nhan_khong_tinh(self):
        a = mui_ten(nen(), x=100, y=420)
        self.assertLess(LC.diem_khung([a] * 3, nhan=[0.0, 0.35, 1.0, 0.65]), LC.NGUONG)

    def test_mang_do_co_van_khong_phai_mui_ten(self):
        a = nen().copy()
        a[500:590, 300:395] = np.random.RandomState(4).randint(150, 255, (90, 95, 1)).astype(np.uint8) * np.array([0, 0, 1], np.uint8)   # đỏ nhưng nhiễu hạt (đất đỏ/lá)
        self.assertLess(LC.diem_khung([a] * 3), LC.NGUONG)

    def test_bong_bong_binh_luan_bi_bat(self):
        self.assertGreaterEqual(LC.diem_khung([bong_bong(nen())] * 3), LC.NGUONG)
        self.assertLess(LC.diem_khung([bong_bong(nen())] * 3, nhan=[0.0, 0.15, 1.0, 0.45]), LC.NGUONG)   # khung nằm trong vùng nhãn

    def test_hop_trang_tron_khong_chu_khong_phai_bong_bong(self):
        a = nen().copy()
        cv2.rectangle(a, (40, 200), (340, 290), (255, 255, 255), -1)                                      # mảng sáng không có nét chữ (mây/áo trắng)
        self.assertLess(LC.diem_khung([a] * 3), LC.NGUONG)

    def test_la_xanh_khong_bi_bat(self):
        self.assertLess(LC.diem_khung([la_xanh(1), la_xanh(2), la_xanh(3)]), LC.NGUONG)
        self.assertLess(LC.diem_khung([la_xanh(1)] * 3), LC.NGUONG)

    def test_anh_ghep_khung_thang_4_canh(self):
        g = lambda im: cv2.cvtColor(LC._nho(im), cv2.COLOR_BGR2GRAY)
        self.assertTrue(LC._inset(g(cua_so(nen()))))
        self.assertFalse(LC._inset(g(nen())))
        self.assertFalse(LC._inset(g(la_xanh(1))))
        self.assertTrue(LC._ben([LC._inset(g(cua_so(nen_dong(i)))) for i in (1, 2, 3)]))                  # đứng yên qua 3 khung
        self.assertFalse(LC._ben([LC._inset(g(cua_so(nen(), x=40 + 60 * i))) for i in range(3)]))         # trôi vị trí = vật thật

    def test_lop_phu_dung_yen_tren_canh_chuyen_dong(self):
        co = [them_chu(nen_dong(i), 800) for i in (1, 2, 3)]                                              # chữ y hệt, nền đổi
        sach = [nen_dong(i) for i in (1, 2, 3)]
        self.assertGreater(LC.tinh_dung_yen(co), LC.TINH_NG)
        self.assertLess(LC.tinh_dung_yen(sach), 0.002)
        self.assertEqual(LC.tinh_dung_yen([nen()] * 3), 0.0)                                              # cả khung đứng yên (tripod) → không tính
        self.assertEqual(LC.tinh_dung_yen(co[:2]), 0.0)

    def test_tin_hieu_yeu_chi_tinh_khi_co_lop_phu_dung_yen(self):
        def chu_nho(im):                                                                                  # chữ nhỏ (điểm chữ < ngưỡng) + logo ô vuông đứng yên
            im = them_chu(im, 800, "SALE 99K", co=0.7)
            for i in range(8):
                for j in range(8):
                    if (i + j) % 2:
                        im[30 + 14 * i:44 + 14 * i, 380 + 14 * j:394 + 14 * j] = 255
                    else:
                        im[30 + 14 * i:44 + 14 * i, 380 + 14 * j:394 + 14 * j] = 0
            return im
        co = [chu_nho(nen_dong(i)) for i in (1, 2, 3)]
        moi = [chu_nho(nen_dong(i)) if i == 1 else nen_dong(i) for i in (1, 2, 3)]
        self.assertLess(LC.diem_khung([chu_nho(nen())] * 3), LC.NGUONG)                                   # đứng yên cả khung: không đủ bằng chứng
        self.assertGreaterEqual(LC.diem_khung(co), LC.NGUONG)
        self.assertLess(LC.diem_khung(moi), LC.NGUONG)

    def test_cache_theo_phien_ban(self):
        luu, LC._NHO = LC._NHO, {"x.mp4|0.00|9.00|None|None": 5.0}                                       # khoá cũ (không có phiên bản) không được dùng lại
        try:
            self.assertEqual(LC.diem_chu_la(CANH), 0.0)                                                   # không đọc được video → 0, không phải 5.0
            LC._NHO[f"{LC.PHIEN_BAN}|x.mp4|0.00|9.00|None|None"] = 7.0
            self.assertEqual(LC.diem_chu_la(CANH), 7.0)                                                   # khoá đúng phiên bản thì dùng
        finally:
            LC._NHO = luu


if __name__ == "__main__":
    unittest.main()

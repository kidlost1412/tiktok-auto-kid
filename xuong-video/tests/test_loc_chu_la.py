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


if __name__ == "__main__":
    unittest.main()

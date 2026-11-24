"""Độ nét cảnh (engine/do_net.py): không cần video thật — khung giả sinh bằng numpy/OpenCV."""
import sys, unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import do_net as DN


def anh_net(w=1080, h=1920, seed=1):
    r = np.random.RandomState(seed)
    return cv2.resize(r.randint(0, 255, (h // 8, w // 8, 3), dtype=np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)


def anh_nhoe(w=1080, h=1920):
    return cv2.GaussianBlur(anh_net(w, h), (0, 0), 25)


def doc_gia(*anh):
    return lambda path, ts, crop=None: [a.copy() for a in anh]


CANH = {"id": "0001", "file": "x.mp4", "tu": 2.0, "den": 12.0, "dai": 10.0, "dep": [3.0, 9.0]}


class TestDoNet(unittest.TestCase):
    def test_khung_nhoe_diem_thap_hon_nhieu(self):
        self.assertGreater(DN.net_khung(anh_net()), 10 * DN.net_khung(anh_nhoe()))

    def test_nhoe_theo_nguong(self):
        self.assertTrue(DN.nhoe(CANH, doc=doc_gia(*[anh_nhoe()] * 4)))
        self.assertFalse(DN.nhoe(CANH, doc=doc_gia(*[anh_net()] * 4)))

    def test_trung_vi_bo_qua_1_khung_rung(self):
        self.assertFalse(DN.nhoe(CANH, doc=doc_gia(anh_net(), anh_net(seed=2), anh_nhoe(), anh_net(seed=3))))      # 1/4 khung nhoè: vẫn nét
        self.assertTrue(DN.nhoe(CANH, doc=doc_gia(anh_nhoe(), anh_nhoe(), anh_net(), anh_nhoe())))      # 3/4 nhoè: nhoè

    def test_vung_xam_can_ai_soat_ghi_nhoe(self):
        mo = dict(CANH, soat={"ghi": "Cây cà phê non mờ, rung"})
        self.assertTrue(DN.la_nhoe(mo, 80.0))                                  # 50–120 + AI ghi mờ → nhoè
        self.assertFalse(DN.la_nhoe(CANH, 80.0))                               # không ghi gì → nét
        self.assertFalse(DN.la_nhoe(dict(CANH, soat={"ghi": "Chai rõ nền mờ"}), 80.0))   # nền mờ cố ý không tính
        self.assertFalse(DN.la_nhoe(mo, 300.0))                                # đủ nét: bỏ qua lời AI
        self.assertTrue(DN.la_nhoe(CANH, 30.0))                                # dưới ngưỡng cứng: nhoè bất kể ghi chú

    def test_khong_doc_duoc_thi_khong_phan_nhoe(self):
        self.assertFalse(DN.nhoe(CANH, doc=doc_gia()))
        self.assertFalse(DN.nhoe(CANH, "khong-co-thu-muc"))                                    # file không tồn tại, không sập

    def test_doan_dung_duoc_va_mau_deu(self):
        self.assertEqual(DN._doan(CANH), (3.0, 9.0))
        self.assertEqual(DN._doan({"tu": 2.0, "dai": 4.0}), (2.0, 6.0))
        got = []
        DN.diem_net(CANH, doc=lambda p, ts, crop=None: (got.extend(ts), [anh_net()])[1])
        self.assertEqual(len(got), DN.SO_KHUNG)
        self.assertTrue(all(3.0 <= t <= 9.0 for t in got))

    def test_crop_duoc_chuyen_cho_bo_doc(self):
        seen = []
        DN.diem_net(dict(CANH, crop=[0.1, 0.2, 0.5, 0.5]), doc=lambda p, ts, crop=None: (seen.append(crop), [anh_net()])[1])
        self.assertEqual(seen, [[0.1, 0.2, 0.5, 0.5]])

    def test_loc_nhoe_bo_nhoe_va_giu_toi_thieu(self):
        diem = {"a": 500.0, "b": 10.0, "c": 20.0, "d": 700.0, "e": 5.0}
        goc = DN.diem_net
        DN.diem_net = lambda s, kho=None, doc=None: diem[s["id"]]
        DN.luu_cache = lambda: None
        try:
            ds = [{"id": i} for i in diem]
            self.assertEqual([s["id"] for s in DN.loc_nhoe(ds, toi_thieu=2)], ["a", "d"])
            self.assertEqual([s["id"] for s in DN.loc_nhoe(ds, toi_thieu=3)], ["a", "c", "d"])    # thiếu → bù cảnh ít nhoè nhất, giữ thứ tự gốc
            self.assertEqual(len(DN.loc_nhoe(ds, toi_thieu=99)), 3)           # sàn tối đa 70% kho: kho nhỏ vẫn loại được cảnh nhoè
            self.assertEqual([s["id"] for s in DN.loc_nhoe(ds, toi_thieu=0)], ["a", "d"])
        finally:
            DN.diem_net = goc


if __name__ == "__main__":
    unittest.main()

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

def lam_mo_nen(a, s=8, rong=0.28, cao=0.22):
    """Chủ thể (elip giữa) nét, nền mờ gaussian s."""
    b = cv2.GaussianBlur(a, (0, 0), s)
    h, w = a.shape[:2]
    m = np.zeros((h, w), np.float32)
    cv2.ellipse(m, (w // 2, h // 2), (int(w * rong), int(h * cao)), 0, 0, 360, 1, -1)
    m = cv2.GaussianBlur(m, (0, 0), 12)[..., None]
    return (a * m + b * (1 - m)).astype(np.uint8)


def nhoe_chuyen_dong(a, L=31, goc=0):
    k = np.zeros((L, L), np.float32)
    cv2.line(k, (0, L // 2), (L - 1, L // 2), 1, 1)
    k = cv2.warpAffine(k, cv2.getRotationMatrix2D(((L - 1) / 2, (L - 1) / 2), goc, 1), (L, L))
    return cv2.filter2D(a, -1, k / k.sum())


def anh_chi_tiet(w=1080, h=1920, seed=5):
    """Cảnh đời thực: vân đa tỉ lệ (không phải khối vuông) nên nhoè mới làm mất chi tiết thật."""
    r = np.random.RandomState(seed)
    x = sum(cv2.resize(r.randn(h // k, w // k).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC) * (k ** 0.3) for k in (2, 4, 8, 16, 32))
    x = (x - x.min()) / (x.max() - x.min()) * 255
    return cv2.cvtColor(x.astype(np.uint8), cv2.COLOR_GRAY2BGR)


class TestDoNetV2(unittest.TestCase):
    def test_chu_the_net_tren_nen_mo_van_net(self):
        self.assertFalse(DN.nhoe(CANH, doc=doc_gia(*[lam_mo_nen(anh_chi_tiet())] * 4)))

    def test_nhoe_gaussian_toan_khung_bi_gan_co(self):
        self.assertTrue(DN.nhoe(CANH, doc=doc_gia(*[cv2.GaussianBlur(anh_chi_tiet(), (0, 0), 8)] * 4)))

    def test_nhoe_chuyen_dong_bi_gan_co(self):
        for goc in (0, 90, 40):
            self.assertTrue(DN.nhoe(CANH, doc=doc_gia(*[nhoe_chuyen_dong(anh_chi_tiet(), 41, goc)] * 4)), goc)

    def test_van_net_thap_tuong_phan_van_net(self):
        x = anh_chi_tiet().astype(np.float32)
        thap = np.clip((x - x.mean()) * 0.3 + 128, 0, 255).astype(np.uint8)
        self.assertFalse(DN.nhoe(CANH, doc=doc_gia(*[thap] * 4)))

    def test_ve_tinh_mo_tuong_phan_thap_van_la_nhoe(self):
        x = cv2.GaussianBlur(anh_chi_tiet(), (0, 0), 8).astype(np.float32)
        thap = np.clip((x - x.mean()) * 0.3 + 128, 0, 255).astype(np.uint8)
        self.assertTrue(DN.nhoe(CANH, doc=doc_gia(*[thap] * 4)))

    def test_nhan_chai_net_cuu_ca_khung(self):
        a = anh_chi_tiet()
        h, w = a.shape[:2]
        mo = cv2.GaussianBlur(a, (0, 0), 8)
        mo[int(h * .4):int(h * .7), int(w * .3):int(w * .7)] = a[int(h * .4):int(h * .7), int(w * .3):int(w * .7)]   # chỉ vùng nhãn nét
        nhan = [0.3, 0.4, 0.7, 0.7]
        self.assertGreaterEqual(DN.net_khung(mo, nhan), DN.NGUONG)
        self.assertLess(DN.net_khung(cv2.GaussianBlur(a, (0, 0), 14), nhan), DN.NGUONG)       # nhãn cũng nhoè → vẫn nhoè
        self.assertGreaterEqual(DN.net_khung(mo, "hỏng"), 0)                                 # nhan lỗi không làm sập

    def test_phien_ban_cache_cu_bi_bo(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            goc = (DN.DATA, DN._NHO)
            try:
                DN.DATA = d
                (Path(d) / "cache-do-net.json").write_text(json.dumps({"x.mp4|1.00|2.00|None": 5.0, DN.PHIEN_BAN + "|y.mp4|1.00|2.00|None|None": 99.0}), encoding="utf-8")
                DN._NHO = None
                self.assertEqual(list(DN._cache()), [DN.PHIEN_BAN + "|y.mp4|1.00|2.00|None|None"])
            finally:
                DN.DATA, DN._NHO = goc


if __name__ == "__main__":
    unittest.main()

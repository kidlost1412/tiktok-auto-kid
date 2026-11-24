"""Chọn nhát cắt chuyển cảnh mạnh (khung chữ theo lời). Hàm thuần, không ffmpeg."""
import os, random, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from chon_chuyen_manh import chon, KIEU   # noqa: E402

CUTS = [0.3, 1.2, 2.5, 3.9, 5.1, 6.6, 8.0, 9.4, 10.8, 12.2, 13.5, 15.0, 16.4, 17.8, 19.2, 20.4, 21.0]


class ChonManh(unittest.TestCase):
    def test_gioi_han(self):
        for seed in range(20):
            r = chon(CUTS, 21.0, [5.1, 12.2], [8.0], random.Random(seed))
            self.assertLessEqual(len(r), 6)
            ts = [x[0] for x in r]
            self.assertTrue(all(b - a >= 2.0 for a, b in zip(ts, ts[1:])))
            self.assertTrue(all(0.5 <= t <= 19.5 for t in ts))
            self.assertTrue(all(a[1] != b[1] for a, b in zip(r, r[1:])))
            self.assertTrue(all(x[1] in KIEU and x[2] in (-1, 1) for x in r))

    def test_uu_tien_cho_doi_y(self):
        r = chon(CUTS, 21.0, [5.1], [], random.Random(1))
        self.assertIn(5.1, [x[0] for x in r])

    def test_video_ngan(self):
        self.assertEqual(len(chon(CUTS, 6.0, [], [], random.Random(1))), 1)
        self.assertEqual(chon([0.2, 3.9], 4.0, [], [], random.Random(1)), [])

    def test_co_dinh_theo_seed(self):
        self.assertEqual(chon(CUTS, 21.0, [5.1], [], random.Random("7-ccm")), chon(CUTS, 21.0, [5.1], [], random.Random("7-ccm")))


if __name__ == "__main__":
    unittest.main()

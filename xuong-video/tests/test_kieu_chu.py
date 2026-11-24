import random, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from dung_remotion import gan_kieu_chu, TRAN_KIEU


class TestKieuChu(unittest.TestCase):
    """23/11 Kid: chữ không cố định, không chỗ nào cũng vàng kim."""
    def test_tran_va_da_dang(self):
        loai = ["hook_dap", "chu_dap", "chu_so", "chu_dap", "chu_so", "chu_tang", "chu_dap", "canh_bao"]
        for s in range(200):
            bl = gan_kieu_chu([{"loai": l} for l in loai], random.Random(s))
            ks = [b.get("kieu") for b in bl]
            for k, n in TRAN_KIEU.items():
                self.assertLessEqual(ks.count(k), n, (s, ks))
            self.assertNotIn("kieu", bl[-1])                 # khối không thuộc chữ lớn thì không gắn
            self.assertGreaterEqual(len(set(k for k in ks if k)), 3, (s, ks))
            self.assertTrue(all(b["font"] in ("ph", "mi", "un", "pt") for b in bl[:-1]))


if __name__ == "__main__":
    unittest.main()

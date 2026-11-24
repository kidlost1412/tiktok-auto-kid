"""Hook chữ khổng lồ sau người (24/11): luật chọn dùng lớp tách người; chọn punch không rơi trong hook. Không gọi AI / ffmpeg."""
import os, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import hook_sau_nguoi as H   # noqa: E402
import dung_remotion as D    # noqa: E402


class HookSauNguoi(unittest.TestCase):
    def test_dung_cat(self):
        self.assertTrue(H.dung_cat(0.25, 0.30))
        self.assertFalse(H.dung_cat(0.05, 0.30))      # người quá nhỏ
        self.assertFalse(H.dung_cat(0.25, 0.60))      # che > 45 % nét chữ → chữ ở trước
        self.assertFalse(H.dung_cat(0.25, 0.0))       # người không chạm chữ

    def test_punch_khong_trong_hook(self):
        ev = [{"vai": "hit", "uu": 0, "t_neo": 1.0}, {"vai": "hit", "uu": 0, "t_neo": 4.0}]
        self.assertEqual(D.chon_punch(ev, 20), [1.0, 4.0])
        self.assertEqual(D.chon_punch(ev, 20, sau=2.0), [4.0])


if __name__ == "__main__":
    unittest.main()

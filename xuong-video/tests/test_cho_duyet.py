"""Số video chờ duyệt (/api/su-kien → cho_duyet): chưa có đánh giá thì tính, có ✅/❌ (kể cả tự duyệt) thì không; có đệm theo mtime."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]


class ChoDuyetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["XUONG_DATA"] = cls.tmp.name
        for p in (str(GOC / "app"), str(GOC / "engine")):
            if p not in sys.path:
                sys.path.insert(0, p)
        import server  # noqa: E402
        cls.s = server

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_dem_video_chua_danh_gia(self):
        s = self.s
        ngay = s.ra_dir() / "2026-11-14"
        ngay.mkdir(parents=True, exist_ok=True)
        for t in ("a.mp4", "b.mp4", "c.mp4", "d.part.mp4"):
            (ngay / t).write_bytes(b"x")
        self.assertEqual(s.so_cho_duyet(), 3)
        f = s.danh_gia_f()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"a.mp4": {"ket_qua": "dat"}, "b.mp4": {"ket_qua": "bo", "tu_dong": "điểm 9"}}), encoding="utf-8")
        self.assertEqual(s.so_cho_duyet(), 1)
        (ngay / "e.mp4").write_bytes(b"x")
        os.utime(ngay, None)
        self.assertEqual(s.so_cho_duyet(), 2)


if __name__ == "__main__":
    unittest.main()

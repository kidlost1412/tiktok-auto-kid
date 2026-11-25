"""Tờ ứng viên 3 khung/ô: cắt khung từ video gốc + cache, rơi về ảnh _khung khi thiếu nguồn, mặc định config.
Chạy: python -m unittest discover -s xuong-video/tests   (XUONG_DATA = thư mục tạm; cần ffmpeg)."""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-khung-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import dao_dien as DD  # noqa: E402
from PIL import Image  # noqa: E402


@unittest.skipUnless(shutil.which("ffmpeg"), "cần ffmpeg")
class KhungUngVien(unittest.TestCase):
    def setUp(self):
        self.hub = Path(tempfile.mkdtemp(prefix="xv-khung-hub-"))
        self.old = DD.HUB; DD.HUB = self.hub
        self.kho = self.hub / "kho"; self.kho.mkdir()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=270x480:rate=10:duration=4", "-pix_fmt", "yuv420p",
                        str(self.kho / "a.mp4")], check=True)
        d = self.hub / "san-pham" / "t1"; (d / "_khung").mkdir(parents=True)
        (d / "san-pham.json").write_text(json.dumps({"kho_video": str(self.kho)}), encoding="utf-8")
        Image.new("RGB", (270, 480), "red").save(d / "_khung" / "0001.jpg")
        Image.new("RGB", (270, 480), "red").save(d / "_khung" / "0002.jpg")
        DD.NGUON.clear()
        DD.NGUON["0001"] = {"id": "0001", "file": "a.mp4", "tu": 0.0, "den": 4.0, "dai": 4.0, "dep": [0.5, 3.5]}
        DD.NGUON["0002"] = {"id": "0002", "file": "thieu.mp4", "tu": 0.0, "den": 4.0, "dai": 4.0, "dep": [0.5, 3.5]}

    def tearDown(self):
        DD.HUB = self.old; DD.NGUON.clear()
        shutil.rmtree(self.hub, ignore_errors=True)

    def test_3_khung_va_cache(self):
        fs = DD.khung_canh("t1", "0001", DD.NGUON["0001"], 3)
        self.assertEqual(len(fs), 3)
        self.assertTrue(all(f.exists() and f.parent.name == "_khung3" for f in fs))
        mt = [f.stat().st_mtime_ns for f in fs]
        self.assertEqual(DD.khung_canh("t1", "0001", DD.NGUON["0001"], 3), fs)       # lần 2: dùng cache, không cắt lại
        self.assertEqual([f.stat().st_mtime_ns for f in fs], mt)
        outs = DD.to_ung_vien("t1", ["0001"], self.hub / "uv.jpg", k=3)
        with Image.open(outs[0]) as im:
            self.assertEqual(im.size, (3 * DD.FW + 2 * DD.GAP, DD.FH))
        self.assertLessEqual(max(im.size), 1568)

    def test_roi_ve_khung_cu_khi_thieu_nguon(self):
        self.assertIsNone(DD.khung_canh("t1", "0002", DD.NGUON["0002"], 3))
        self.assertIsNone(DD.khung_canh("t1", "0009", None, 3))
        outs = DD.to_ung_vien("t1", ["0002", "0001"], self.hub / "uv2.jpg", k=3)         # 1 ô khung cũ + 1 ô 3 khung, không sập
        self.assertEqual(len(outs), 1)

    def test_bo_cuc_to_gioi_han_va_mac_dinh(self):
        for k in range(1, 11):
            cw, ch, cot, hang = DD.bo_cuc_to(k)
            self.assertLessEqual(cot * cw, 1568); self.assertLessEqual(hang * ch, 1568)
        c = DD.cfg_hub
        try:
            DD.cfg_hub = lambda: {}
            self.assertEqual((DD.moi_cau(), DD.khung_moi_canh()), (6, 6))
            DD.cfg_hub = lambda: {"dao_dien": {"ung_vien_moi_cau": 99, "khung_moi_canh": 1}}
            self.assertEqual((DD.moi_cau(), DD.khung_moi_canh()), (DD.TRAN_MOI_CAU, 1))
            DD.cfg_hub = lambda: {"dao_dien": {"ung_vien_moi_cau": "x"}}
            self.assertEqual(DD.moi_cau(), 6)
        finally:
            DD.cfg_hub = c


if __name__ == "__main__":
    unittest.main()

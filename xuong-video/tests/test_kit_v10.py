"""23/11: hai món chép từ bộ kol-vip2 (v10) cho khung dựng "chữ theo lời": tách người (chữ sau người) + chuyển cảnh mạnh. Cần ffmpeg."""
import shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))


@unittest.skipUnless(shutil.which("ffmpeg"), "cần ffmpeg")
class KitV10Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="kitv10-"))
        cls.src = cls.tmp / "src.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=270x480:rate=30:duration=1.2",
                        "-pix_fmt", "yuv420p", str(cls.src)], check=True)

    def test_chuyen_canh_giu_so_khung(self):
        import chuyen_canh_manh as C
        out = self.tmp / "cut.mp4"
        C.ap(self.src, out, [(0.5, "whip", 1), (0.9, "glitch")])
        n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
        self.assertEqual(int(n), 36)

    def test_tach_nguoi_ra_png_rgba(self):
        import tach_nguoi as T
        self.assertTrue(T.MO_HINH.exists())
        n = T.tach(self.src, self.tmp / "m", 0.2, 0.4)
        self.assertEqual(n, 6)
        import cv2
        self.assertEqual(cv2.imread(str(self.tmp / "m" / "frame_000001.png"), cv2.IMREAD_UNCHANGED).shape[2], 4)


if __name__ == "__main__":
    unittest.main()

"""python -m unittest scripts.test_asset   (from tc01-remotion)

Real Remotion renders of the Asset composition (tick, ellipse) into a temp folder with spaces + Vietnamese, checked on the
pixels. Expected numbers come from the SVG geometry by hand (tick viewBox 52, circle r 26; ellipse extent formula)."""
import json, math, subprocess, sys, tempfile, unittest
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kit_layout  # noqa: E402

PTS = kit_layout.circle_unit_points("c_1086")


def render(jobs, d):
    p = Path(d) / "jobs.json"
    p.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "render_asset.mjs"), "--jobs", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr}


class AssetRenders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name) / "tài sản #1"
        cls.dir.mkdir()
        jobs = [{"kind": "tick", "params": {"d": 52, "fill": "#1F9E46", "mark": "#FFFFFF"}, "out": str(cls.dir / "dấu tick.png")},
                {"kind": "ellipse", "params": {"rx": 205, "ry": 78, "stroke": 11, "outline": 25, "color": "#E1262D", "outline_color": "#FFFFFF",
                                               "points": PTS}, "out": str(cls.dir / "vòng.png")}]
        cls.code, cls.res = render(jobs, cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_ok(self):
        self.assertEqual(self.code, 0, self.res)

    def test_tick(self):
        a = np.asarray(Image.open(self.dir / "dấu tick.png").convert("RGBA")).astype(int)
        self.assertEqual(a.shape, (52, 52, 4))
        self.assertEqual(a[1, 1, 3], 0)                                  # corner outside the r 26 disc
        px = a[26, 6]                                                   # inside the disc, far from the tick stroke
        self.assertEqual((px[3], abs(px[0] - 0x1F) <= 3, abs(px[1] - 0x9E) <= 3, abs(px[2] - 0x46) <= 3), (255, True, True, True))
        mk = a[36, 23]                                                  # the tick's corner point (23, 36)
        self.assertTrue((mk[:3] >= 245).all(), mk)

    def test_ellipse(self):
        a = np.asarray(Image.open(self.dir / "vòng.png").convert("RGBA")).astype(int)
        hw = max(abs(p[0]) for p in PTS) * 205 + 25 / 2 + 2
        hh = max(abs(p[1]) for p in PTS) * 78 + 25 / 2 + 2
        self.assertEqual(a.shape[:2], (2 * math.ceil(hh), 2 * math.ceil(hw)))
        h, w = a.shape[:2]
        self.assertEqual(a[h // 2, w // 2, 3], 0)                        # hollow centre
        self.assertEqual(a[0, 0, 3], 0)
        # along the horizontal axis through the centre: some pixel is the red stroke
        row = a[h // 2]
        red = [(x, p) for x, p in enumerate(row) if p[3] == 255 and p[0] > 200 and p[1] < 80 and p[2] < 80]
        self.assertTrue(red)
        white = [x for x, p in enumerate(row) if p[3] == 255 and (p[:3] > 240).all()]
        self.assertTrue(white)                                          # the outline around it
        # stroke ink stays inside the canvas: border columns transparent
        self.assertEqual(int(a[:, 0, 3].max()), 0); self.assertEqual(int(a[:, -1, 3].max()), 0)

    def test_bad_job_rejected_before_render(self):
        with tempfile.TemporaryDirectory() as d:
            code, res = render([{"kind": "tick", "params": {"d": 52, "fill": "red", "mark": "#FFFFFF"}, "out": str(Path(d) / "x.png")}], d)
            self.assertEqual(code, 1)
            self.assertIn("#RRGGBB", res["error"])
            self.assertFalse((Path(d) / "x.png").exists())


if __name__ == "__main__":
    unittest.main()

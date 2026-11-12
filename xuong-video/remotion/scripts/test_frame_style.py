"""python -m unittest test_frame_style -v   (from tc01-remotion/scripts)

Real Remotion renders of every catalog style (one bundle, temp folder with spaces + Vietnamese in the path) checked on
the pixels: transparent inside each box (no more than `cover` px of the video is ever covered), something drawn on the
edge, the inner contour following the mask corner radius, label text ink fully inside its badge, an animated .mov with
alpha. Plus the taste memory (pick never returns a rejected style; mark is atomic and keeps the rest of the profile).
Expected numbers are hand constants from the geometry, not taken from the renderer.
"""
import json, math, os, subprocess, sys, tempfile, unittest
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import frame_style as fsy  # noqa: E402

CAT = fsy.load_catalog()
IDS = [s["id"] for s in CAT["styles"]]
# radius 40 on a 2x2-like box, a square-corner box (radius 0) and a big radius 120 on the card
BOXES = [{"box": [60, 200, 500, 800], "radius": 40}, {"box": [580, 200, 1020, 800], "radius": 0},
         {"box": [140, 1000, 940, 1600], "radius": 120, "label": {"text": "ỔN ĐỊNH Ữ GIỎ", "corner": "tl"}}]


def render(jobs, d):
    p = Path(d) / "jobs.json"
    p.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "render_frame_style.mjs"), "--jobs", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr}


def inside_rounded(h, w, box, inset, radius):
    """bool mask of pixel centres strictly inside the box inset by `inset` px with corner radius max(0, radius - inset)."""
    x0, y0, x1, y1 = box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset
    r = max(0.0, radius - inset)
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    m = (xs > x0) & (xs < x1) & (ys > y0) & (ys < y1)
    cx = np.clip(xs, x0 + r, x1 - r)
    cy = np.clip(ys, y0 + r, y1 - r)
    return m & ((xs - cx) ** 2 + (ys - cy) ** 2 < r * r + 1e-9)


class Renders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name) / "khung kiểu #1"
        cls.dir.mkdir()
        jobs = [{"style": s, "boxes": BOXES, "out": str(cls.dir / f"{s}.png")} for s in IDS]
        jobs.append({"style": "clean", "boxes": BOXES[:1], "out": str(cls.dir / "clean anim.mov"), "animated": True, "frames": 16, "enter_f": 10})
        code, res = render(jobs, cls.tmp.name)
        assert code == 0, res
        cls.alpha = {s: np.asarray(Image.open(cls.dir / f"{s}.png").convert("RGBA"))[..., 3] for s in IDS}
        cls.rgba = {s: np.asarray(Image.open(cls.dir / f"{s}.png").convert("RGBA")) for s in IDS}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_size_and_transparent_background(self):
        for s, a in self.alpha.items():
            self.assertEqual(a.shape, (1920, 1080), s)
            self.assertEqual(int(a[5, 5]), 0, s)          # far corner of the canvas
            self.assertEqual(int(a[960, 1060]), 0, s)     # between the box rows (y 800..1000), right of every box and badge

    def test_inside_each_box_untouched(self):
        # cover = 2 px for edge styles, border_px (6 by default) for tape: everything deeper inside the box is alpha 0
        for s, a in self.alpha.items():
            cover = 6 if s == "tape" else 2
            for b in BOXES:
                m = inside_rounded(1920, 1080, b["box"], cover + 1, b["radius"])
                self.assertEqual(int(a[m].max()), 0, f"{s}: decoration inside {b['box']}")
                x0, y0, x1, y1 = b["box"]
                self.assertEqual(int(a[(y0 + y1) // 2, (x0 + x1) // 2]), 0, s)

    def test_decoration_on_the_edge(self):
        # something opaque within 24 px outside every box (ring, glow, card margin, corner, shadow)
        for s, a in self.alpha.items():
            for b in BOXES:
                x0, y0, x1, y1 = b["box"]
                band = inside_rounded(1920, 1080, [x0 - 24, y0 - 24, x1 + 24, y1 + 24], 0, b["radius"] + 24) & ~inside_rounded(1920, 1080, b["box"], 0, b["radius"])
                self.assertGreater(int(a[band].max()), 100, f"{s}: nothing drawn around {b['box']}")

    def test_inner_contour_follows_mask_radius(self):
        # on the diagonal of the top-left corner: the mask (radius r) hides the video beyond distance r from the corner
        # centre (x0+r, y0+r); the ring must be there at r+1 and absent at r-cover-2 (cover 2 px, tape 6 px, + anti-aliasing)
        for s, a in self.alpha.items():
            if s == "lift":
                continue   # shadow only, no edge line
            cover = 6 if s == "tape" else 2
            for b in BOXES:
                x0, y0 = b["box"][:2]
                r = b["radius"]
                for dist, want in ((r + 1.0, True), (r - cover - 2.0, False)):
                    if r == 0 and not want:
                        continue
                    k = dist / math.sqrt(2)
                    px, py = int(x0 + r - k), int(y0 + r - k)
                    got = int(a[py, px])
                    self.assertEqual(got > 100 if want else got == 0, True, f"{s} r={r}: alpha {got} at distance {dist} (pixel {px},{py})")

    def test_label_ink_inside_badge_with_diacritics(self):
        # badge sits above the card's top edge (y0 = 1000) at the left; dark text ink (label_text #1A1A1A) must lie strictly
        # inside the opaque white badge rows, so the stacked diacritics of "Ổ"/"Ữ" are not clipped
        for s in IDS:
            px = self.rgba[s][880:1010, 140:940].astype(int)
            opaque = px[..., 3] > 200
            white = opaque & (px[..., :3].min(axis=2) > 230)
            dark = opaque & (px[..., :3].max(axis=2) < 90)
            self.assertGreater(int(dark.sum()), 200, s)
            wy = np.where(white.any(axis=1))[0]
            dy = np.where(dark.any(axis=1))[0]
            self.assertGreater(dy.min(), wy.min(), f"{s}: label ink touches the badge top")
            if s == "lift":   # no ring under the badge: the white rows are the badge alone
                self.assertLess(dy.max(), wy.max(), f"{s}: label ink touches the badge bottom")
                self.assertLessEqual(wy.max() + 880, 1000 + 2, f"{s}: badge reaches into the card more than the cover")

    def test_animated_mov_has_alpha_and_draws_in(self):
        mov = self.dir / "clean anim.mov"
        pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                                        "stream=codec_name,pix_fmt,nb_read_frames,width,height", "-of", "json", str(mov)],
                                       capture_output=True, text=True, check=True).stdout)["streams"][0]
        self.assertEqual((pr["codec_name"], pr["width"], pr["height"], int(pr["nb_read_frames"])), ("prores", 1080, 1920, 16))
        self.assertTrue(pr["pix_fmt"].startswith("yuva"), pr["pix_fmt"])
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mov), "-vf", "alphaextract,scale=270:480", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True, check=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(16, 480, 270)
        self.assertLess(int(fr[0].sum()) * 2, int(fr[15].sum()))       # frame 0 is a short stroke stub
        self.assertEqual(int(fr[12].sum()), int(fr[15].sum()))          # drawn in by frame 9 (enter_f 10), then held

    def test_bad_jobs_rejected_before_render(self):
        with tempfile.TemporaryDirectory() as d:
            for job, msg in (({"style": "nope", "boxes": BOXES, "out": "x.png"}, "unknown frame style"),
                             ({"style": "clean", "params": {"colour": "#FFFFFF"}, "boxes": BOXES, "out": "x.png"}, "unknown param colour"),
                             ({"style": "clean", "params": {"color": "white"}, "boxes": BOXES, "out": "x.png"}, "color must be #RRGGBB"),
                             ({"style": "clean", "boxes": [{"box": [0, 0, 10, 10]}], "out": "x.png"}, "radius must be px"),
                             ({"style": "clean", "boxes": BOXES, "out": "x.mov"}, "needs a .png")):
                job["out"] = str(Path(d) / job["out"])
                code, res = render([job], d)
                self.assertEqual(code, 1, job)
                self.assertIn(msg, res["error"])
                self.assertFalse(Path(job["out"]).exists())


class Taste(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name) / "người nhờ edit.json"
        self.p.write_text(json.dumps({"schema_version": 1, "owner": "Anh", "gu": {"nhac": "giữ nguyên"}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *a):
        r = subprocess.run([sys.executable, str(HERE / "frame_style.py"), *a], capture_output=True, text=True, encoding="utf-8")
        return r.returncode, json.loads(r.stdout)

    def test_rejected_never_picked_liked_preferred(self):
        self.assertEqual(self.run_cli("pick", "--profile", str(self.p))[1]["id"], "clean")      # first in catalog
        self.run_cli("mark", "--profile", str(self.p), "--style", "clean", "--rejected")
        code, r = self.run_cli("pick", "--profile", str(self.p))
        self.assertEqual((code, r["id"]), (0, "glow"))
        self.assertEqual(r["excluded_rejected"], ["clean"])
        self.run_cli("mark", "--profile", str(self.p), "--style", "neon", "--liked")
        self.assertEqual(self.run_cli("pick", "--profile", str(self.p))[1]["id"], "neon")
        # tags: grid styles are clean, double, gradient, tape, corner, lift; clean rejected, neon not a grid style -> double
        self.assertEqual(self.run_cli("pick", "--profile", str(self.p), "--tags", "grid")[1]["id"], "double")
        # every style rejected -> exit 1, never a rejected id
        for s in IDS:
            self.run_cli("mark", "--profile", str(self.p), "--style", s, "--rejected")
        code, r = self.run_cli("pick", "--profile", str(self.p))
        self.assertEqual(code, 1)
        self.assertIn("no style left", r["error"])

    def test_pick_never_rejected_exhaustive(self):
        # every subset pattern of 9 styles: the pick is never rejected, and liked wins when any allowed liked exists
        for n in range(1 << len(IDS)):
            rej = [s for i, s in enumerate(IDS) if n >> i & 1]
            liked = [s for i, s in enumerate(IDS) if (n * 7 + 3) >> i & 1]
            prof = {"gu": {"frame_styles": {"liked": liked, "rejected": rej}}}
            try:
                r = fsy.pick(CAT, prof)
            except fsy.StyleError:
                self.assertEqual(len(rej), len(IDS))
                continue
            self.assertNotIn(r["id"], rej)
            if set(liked) - set(rej):
                self.assertIn(r["id"], liked)

    def test_mark_moves_between_lists_and_keeps_profile(self):
        self.run_cli("mark", "--profile", str(self.p), "--style", "tape", "--liked")
        code, r = self.run_cli("mark", "--profile", str(self.p), "--style", "tape", "--rejected")
        self.assertEqual((code, r["liked"], r["rejected"]), (0, [], ["tape"]))
        d = json.loads(self.p.read_text(encoding="utf-8"))
        self.assertEqual((d["owner"], d["gu"]["nhac"], d["schema_version"]), ("Anh", "giữ nguyên", 1))
        self.assertEqual(d["gu"]["frame_styles"], {"liked": [], "rejected": ["tape"]})
        self.assertTrue(Path(r["backup"]).is_file())        # previous bytes kept
        self.assertIn('"liked": [\n        "tape"', Path(r["backup"]).read_text(encoding="utf-8"))
        self.assertFalse(self.p.with_name(self.p.name + ".lock").exists())
        code, r = self.run_cli("mark", "--profile", str(self.p), "--style", "tape", "--clear")
        self.assertEqual(json.loads(self.p.read_text(encoding="utf-8"))["gu"]["frame_styles"], {"liked": [], "rejected": []})

    def test_mark_refuses_unknown_style_and_held_lock(self):
        before = self.p.read_bytes()
        code, r = self.run_cli("mark", "--profile", str(self.p), "--style", "sparkle", "--liked")
        self.assertEqual(code, 1)
        self.assertIn("unknown style", r["error"])
        lock = self.p.with_name(self.p.name + ".lock")
        lock.write_text("")
        code, r = self.run_cli("mark", "--profile", str(self.p), "--style", "clean", "--liked")
        self.assertEqual(code, 1)
        self.assertIn("another write in progress", r["error"])
        self.assertTrue(lock.exists())                       # someone else's lock is not removed
        self.assertEqual(self.p.read_bytes(), before)
        self.assertEqual(list(Path(self.tmp.name).glob("*.bak-frame-style-*")), [])

    def test_failed_write_keeps_profile(self):
        before = self.p.read_bytes()
        orig = os.replace

        def boom(a, b):
            raise OSError("disk full (simulated)")
        os.replace = boom
        try:
            with self.assertRaises(OSError):
                fsy.mark(CAT, self.p, "clean", "liked")
        finally:
            os.replace = orig
        self.assertEqual(self.p.read_bytes(), before)
        self.assertEqual([q.name for q in Path(self.tmp.name).iterdir() if ".tmp-" in q.name or q.suffix == ".lock"], [])


class Catalog(unittest.TestCase):
    def test_catalog_shape(self):
        self.assertGreaterEqual(len(IDS), 8)
        self.assertEqual(len(set(IDS)), len(IDS))
        for s in CAT["styles"]:
            for k in ("id", "name_vi", "description_vi", "tags", "params", "defaults"):
                self.assertIn(k, s, s["id"])
            self.assertTrue(set(s["defaults"]) <= set(CAT["params_schema"]), s["id"])
            self.assertTrue(set(s["params"]) <= set(CAT["params_schema"]), s["id"])


if __name__ == "__main__":
    unittest.main()

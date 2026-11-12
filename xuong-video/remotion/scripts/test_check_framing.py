"""python -X utf8 -m unittest test_check_framing -v   (from tc01-remotion/scripts)

Crop / face-intersection math of check_framing.py with hand-computed numbers; the ffmpeg reader and the face detector are
replaced by a synthetic frame and a known face box (the Haar detector itself is validated on the real TC01 V11 sources).
"""
import unittest

import numpy as np

import check_framing as cf

SW, SH = 576, 1024  # the TC01 library size


class CropWindow(unittest.TestCase):
    def test_wide_box_zoom1_centered(self):
        # box 844x576 on 576x1024: k = 844/576, half_w = 288 (full width), half_h = 288 * 576 / 844 = 196.5498
        x0, y0, x1, y1 = cf.crop_window(SW, SH, 844, 576, 1.0, [0.5, 0.5])
        self.assertAlmostEqual(x0, 0.0); self.assertAlmostEqual(x1, 576.0)
        self.assertAlmostEqual(y0, 512 - 196.5498, places=3); self.assertAlmostEqual(y1, 512 + 196.5498, places=3)

    def test_zoom_halves_the_window_and_center_moves_it(self):
        x0, y0, x1, y1 = cf.crop_window(SW, SH, 844, 576, 2.0, [0.25, 0.2])
        self.assertAlmostEqual(x1 - x0, 288.0); self.assertAlmostEqual((x0 + x1) / 2, 144.0)
        self.assertAlmostEqual(y1 - y0, 196.5498, places=3); self.assertAlmostEqual((y0 + y1) / 2, 204.8)

    def test_full_canvas_broll_is_cover_fit(self):
        # 1080x1920 canvas on 576x1024: k = 1080/576 = 1.875 both axes, so the whole source shows at zoom 1
        self.assertEqual([round(v, 6) for v in cf.crop_window(SW, SH, 1080, 1920, 1.0, [0.5, 0.5])], [0.0, 0.0, 576.0, 1024.0])

    def test_zoom_ramp(self):
        c = {"f0": 100, "f1": 111, "zoom": {"from": 1.0, "to": 1.5, "easing": "linear"}}
        self.assertAlmostEqual(cf.zoom_at(c, 100), 1.0)
        self.assertAlmostEqual(cf.zoom_at(c, 105), 1.25)  # p = 5/10
        self.assertAlmostEqual(cf.zoom_at(c, 110), 1.5)
        self.assertAlmostEqual(cf.zoom_at({"f0": 0, "f1": 11}, 5), 1.0)  # no zoom object
        self.assertAlmostEqual(cf.zoom_at({**c, "zoom": {"from": 1, "to": 2, "easing": "ease_in"}}, 105), 1.25)  # 0.5^2 = 0.25

    def test_sample_frames(self):
        self.assertEqual(cf.sample_frames(733, 776), [733, 754, 775])
        self.assertEqual(cf.sample_frames(5, 6), [5])
        self.assertEqual(cf.sample_frames(5, 7), [5, 6])


class Judge(unittest.TestCase):
    CROP = [0, 300, 576, 700]  # 400 px tall window
    def v(self, face):
        return cf.judge(face, self.CROP, SW, SH)

    def test_inside(self):
        self.assertEqual(self.v([200, 400, 340, 540]), ("OK", 0.0))

    def test_cut_by_half_is_flagged(self):
        verdict, out = self.v([200, 230, 340, 370])  # 70 of 140 rows above the top edge
        self.assertEqual(verdict, "FACE_CUT"); self.assertAlmostEqual(out, 0.5)

    def test_cut_by_20_percent_is_tolerated(self):
        verdict, out = self.v([200, 272, 340, 412])  # 28 of 140 rows outside = 20 %
        self.assertEqual(verdict, "OK"); self.assertAlmostEqual(out, 0.2)

    def test_cut_at_the_side(self):
        self.assertEqual(self.v([-70, 400, 70, 540])[0], "FACE_CUT")  # half outside on the left

    def test_head_above_crop_within_one_face_height(self):
        # face rows 120..260 (140 tall), crop top 300: gap 40 <= 140 -> head cut off, body shown
        self.assertEqual(self.v([200, 120, 340, 260])[0], "FACE_OUT")

    def test_head_far_above_is_not_out(self):
        self.assertEqual(self.v([200, 0, 340, 140])[0], "OK")  # gap 160 > 140: a deliberate other shot

    def test_face_below_or_beside_crop_is_not_out(self):
        self.assertEqual(self.v([200, 760, 340, 900])[0], "OK")

    def test_tiny_face_ignored(self):
        # 40x40 = 1600 px < 0.5 % of 576x1024 (2949 px)
        self.assertEqual(self.v([200, 230, 240, 270])[0], "OK")


class Suggest(unittest.TestCase):
    def test_real_case_numbers(self):
        # TC01 V11 fr_stages: crop h 374.4 (half 187.2), face rows 114..264 -> centre y in [76.8, 301.2]; nearest to 460.8 is 301.2
        crop = [13.7, 273.6, 562.3, 648.0]
        s = cf.suggest_center([249, 114, 399, 264], crop, SW, SH)
        self.assertAlmostEqual(s["center"][1], 301.2 / 1024, places=3)
        self.assertAlmostEqual(s["center"][0], 0.5, places=2)  # x already fine, unchanged (crop centre 288)
        self.assertIsNone(s["note"])

    def test_edge_clamp_is_reported(self):
        # face at the very top (rows 0..100), crop 500 tall: centre must be in [-150, 250]; moving up from 550 stops at 250 (crop top = 0)
        s = cf.suggest_center([100, 0, 200, 100], [0, 300, 576, 800], SW, SH)
        self.assertAlmostEqual(s["center"][1], 250 / 1024, places=3)
        self.assertIsNone(s["note"])

    def test_face_larger_than_crop(self):
        s = cf.suggest_center([0, 0, 500, 500], [0, 0, 576, 300], SW, SH)
        self.assertIsNone(s["center"][1]); self.assertIsNotNone(s["note"])


class Confirmed(unittest.TestCase):
    def test_single_detector_hits_dropped(self):
        a, b = [100, 100, 200, 200], [102, 98, 204, 198]
        hits = [(0, a), (1, b), (1, [400, 400, 460, 460])]
        self.assertEqual(cf.confirmed(hits), [a, b])  # the lone box has no second detector behind it


class CheckItem(unittest.TestCase):
    def test_pipeline_with_fake_reader_and_detector(self):
        img = np.zeros((SH, SW, 3), np.uint8)
        calls = []
        def reader(path, t):
            calls.append((path, round(t, 6)))
            return img
        detect = lambda im: [[249.0, 114.0, 399.0, 264.0]]
        clip = {"path": "x.mp4", "src_in_f": 900, "f0": 733, "f1": 776, "center": [0.5, 0.45], "zoom": {"from": 1.0, "to": 1.0}}
        r = cf.check_item({"id": "fr", "kind": "frame", "panel": 0, "clip": 0, "label": None}, 844, 576, clip, detect, 0.5, reader)
        # source time = (src_in_f + t - f0) / 30 + offset
        self.assertEqual(calls, [("x.mp4", 30.5), ("x.mp4", round((900 + 21) / 30 + 0.5, 6)), ("x.mp4", round((900 + 42) / 30 + 0.5, 6))])
        self.assertEqual(r["verdict"], "FACE_OUT")  # crop top = 460.8 - 196.55 = 264.25, just below the face bottom (264): head cut off
        self.assertEqual(len(r["samples"]), 3)

    def test_face_inside_is_ok(self):
        detect = lambda im: [[249.0, 114.0, 399.0, 264.0]]
        clip = {"path": "x.mp4", "src_in_f": 0, "f0": 0, "f1": 10, "center": [0.5, 0.2], "zoom": {"from": 1.0, "to": 1.0}}
        r = cf.check_item({"id": "fr"}, 844, 576, clip, detect, 0.0, lambda p, t: np.zeros((SH, SW, 3), np.uint8))
        self.assertEqual(r["verdict"], "OK")  # crop rows 8.2..401.8 contain 114..264


if __name__ == "__main__":
    unittest.main()

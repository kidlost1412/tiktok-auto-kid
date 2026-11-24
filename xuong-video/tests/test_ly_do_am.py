"""23/11 Kid: mỗi tiếng phải có lý do hình; không 2 tiếng chồng nhau; không bao giờ chữ "chết"."""
import os, random, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-lydoam-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import sfx as SFX  # noqa: E402
from viet_loi import bo_chet, CAM_CHU  # noqa: E402
from dung_remotion import gio_xeng  # noqa: E402


class LyDoAmTest(unittest.TestCase):
    def test_tu_nhan_chi_keu_khi_trung_moc_hinh(self):
        ctx = {"rng": random.Random(1), "ui": "tick"}
        nhan = [{"t": 2.0, "w": "30"}, {"t": 5.0, "w": "sạch"}, {"t": 8.0, "w": "nhanh"}]
        out = [x for x in SFX._lap_cho(nhan, [], [5.1], 20.0, ctx, [], moc=[5.1, 8.2]) if x["nguon"] == "nhan"]
        self.assertEqual([round(x["t"], 2) for x in out], [5.12, 8.22])     # 2.0 không có mốc hình → bỏ; còn lại canh đúng mốc
        self.assertFalse(any("chup" in x["nhom"] for x in SFX._lap_cho([{"t": 5.0, "w": "30"}], [], [5.0], 20.0, ctx, [])))

    def test_khong_chong_tieng(self):
        rng = random.Random(3)
        bl = [{"loai": "hook_dap", "f0": 0, "f1": 40}, {"loai": "vong_tron", "f0": 99, "f1": 140}, {"loai": "the_qua", "f0": 570, "f1": 630}]
        ev = SFX.len_lich("vua", bl, [3.3, 6.0, 9.0, 12.0, 15.0], 21.0, rng, cau=[3.3, 9.0, 15.0], dong=[1.0, 4.0, 7.0, 10.0])
        for a in ev:
            for b in ev:
                if a is b or (a.get("cum") and a.get("cum") == b.get("cum")):
                    continue
                if abs(a["t_neo"] - b["t_neo"]) < 0.05:
                    self.fail(f"chồng: {a['nhom']}@{a['t_neo']} + {b['nhom']}@{b['t_neo']}")


class XengTest(unittest.TestCase):
    def test_xeng_dung_tu_chot(self):
        words = [{"w": "bấm", "f0": 560}, {"w": "giỏ", "f0": 575}, {"w": "hàng", "f0": 580}]
        chot = {"loai": "the_qua", "f0": 570}
        ra = [gio_xeng(words, chot, random.Random(s)) for s in range(40)]
        self.assertTrue(all(r in (None, round(575 / 30, 3)) for r in ra))
        self.assertTrue(None in ra and any(ra))                              # có lúc có, có lúc không
        self.assertIsNone(gio_xeng(words, dict(chot, loai="nut_gio_hang"), random.Random(0)))


class KhongChetTest(unittest.TestCase):
    def test_thay_tu(self):
        self.assertIn("chết", CAM_CHU)
        self.assertEqual(bo_chet("Bọ trĩ chết nhanh"), "Bọ trĩ gục nhanh")
        self.assertEqual(bo_chet("BỌ TRĨ CHẾT SẠCH"), "BỌ TRĨ SẠCH BÓNG")
        self.assertEqual(bo_chet("cây chết khô"), "cây lụi khô")
        self.assertNotIn("chết", bo_chet("Chết rồi, chết thật").lower())


if __name__ == "__main__":
    unittest.main()

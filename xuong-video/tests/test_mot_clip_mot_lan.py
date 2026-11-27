"""Kid 27/11: cảnh cắt từ CÙNG một video gốc (cùng người, cùng áo) chỉ một lần trong video — cả cảnh chính, ô phụ đạo diễn chọn lẫn ô máy bù.
Không gọi AI/mạng/ffmpeg."""
import os, random, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-motclip-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import bo_cuc as BC  # noqa: E402
import dao_dien as DD  # noqa: E402


def canh(i, f, aff=True, chai=False):
    return {"id": f"{i:03d}", "file": f"{f}.mp4", "tu": float(i), "den": float(i) + 4, "dai": 4.0, "dep": [i + 0.5, i + 3.5],
            "vai_tro": ["chai_ro"] if chai else ["vuon"], "co_canh": "can",
            "soat": {"dep": 4, "mat": 2 if aff else 0, "chu_muc": 0}}


def doan(s, phu=()):
    return {"shot": s, "dur": 2.0, "src_start": s["tu"], "bo_cuc": "chia_ngang" if phu else "day", "phu_shots": list(phu)}


class NhomClipTest(unittest.TestCase):
    def test_chi_gan_nhan_clip_co_tu_hai_canh(self):
        ds = [canh(1, "A"), canh(2, "A"), canh(3, "B"), canh(4, "C"), canh(5, "C")]
        n = DD.nhom_clip(ds)
        self.assertEqual(n["001"], n["002"]); self.assertEqual(n["004"], n["005"])
        self.assertNotEqual(n["001"], n["004"]); self.assertNotIn("003", n)
        self.assertIn("[clip G1]", DD.dong_ds(0, {**ds[0], "mo_ta": "x"}, "G1"))


class MotClipMotLanTest(unittest.TestCase):
    def test_doi_canh_cung_clip_sang_clip_khac(self):
        a1, a2, a3, b, c, d = canh(1, "A"), canh(2, "A"), canh(3, "A"), canh(4, "B"), canh(5, "C"), canh(6, "D", aff=False, chai=True)
        segs = [doan(a1), doan(a2, [a3]), doan(d)]
        shots = [a1, a2, a3, b, c, d]
        used = {"001", "002", "003", "006"}
        ghi = DD.mot_clip_mot_lan(segs, shots, used)
        files = [segs[0]["shot"]["file"], segs[1]["shot"]["file"], segs[1]["phu_shots"][0]["file"], segs[2]["shot"]["file"]]
        self.assertEqual(len(files), len(set(files)), files)
        self.assertEqual(len(ghi), 2)

    def test_kho_het_clip_khac_thi_giu(self):
        a1, a2 = canh(1, "A"), canh(2, "A")
        segs = [doan(a1), doan(a2)]
        self.assertEqual(DD.mot_clip_mot_lan(segs, [a1, a2], {"001", "002"}), [])
        self.assertEqual(segs[1]["shot"]["id"], "002")


class ChonPhuTest(unittest.TestCase):
    def test_may_bu_khong_lay_clip_da_dung(self):
        main = canh(1, "M")
        pool = [main, canh(2, "A"), canh(3, "A"), canh(4, "B"), canh(5, "C")]
        for sd in range(20):
            used = {("A.mp4", 2)}
            ra = BC.chon_phu(doan(main), 2, pool, random.Random(sd), used)
            fs = [p["shot"]["file"] for p in ra]
            self.assertNotIn("A.mp4", fs); self.assertEqual(len(set(fs)), 2)

    def test_het_clip_moi_thi_van_lay_duoc(self):
        main = canh(1, "M")
        ra = BC.chon_phu(doan(main), 1, [main, canh(2, "A"), canh(3, "A")], random.Random(1), {("A.mp4", 2)})
        self.assertEqual(ra[0]["shot"]["id"], "003")


if __name__ == "__main__":
    unittest.main()

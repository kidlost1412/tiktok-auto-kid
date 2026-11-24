"""Kid 23/11 — mắt người khác con số: phụ đề ngắt theo nghĩa, bỏ dấu cuối dòng, lót nền tối khi nền sáng, danh sách bệnh không dùng tích xanh,
giám khảo chỉ hỏi AI 6 mục cần mắt. Không gọi AI / ffmpeg."""
import os, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import phu_de as PD      # noqa: E402
import do_nen            # noqa: E402
import kiem_may as km    # noqa: E402
import cong_thuc as ct   # noqa: E402
import tim_mat           # noqa: E402
import bo_cuc as BC      # noqa: E402


class PhuDeTheoNghia(unittest.TestCase):
    def test_khong_ngat_sau_chu_so(self):
        self.assertEqual(PD.cat_cum(PD._tu_dem("một nắp pha một bình hai chục lít."), 2, 5), ["một nắp pha", "một bình hai chục lít."])

    def test_bo_dau_cuoi_dong(self):
        words = [{"w": w, "s": i * 0.3, "e": i * 0.3 + 0.25} for i, w in enumerate("Luống cải vàng lá, còi cọc.".split())]
        lines, _ = PD.chia_dong("Luống cải vàng lá, còi cọc.", None, words)
        self.assertTrue(all(not l["text"].endswith((",", ".")) for l in lines))
        self.assertTrue(all(not l["words"][-1]["w"].endswith((",", ".")) for l in lines))
        self.assertEqual(PD._bo_dau_cuoi("vậy?"), "vậy?")


class LotNenToi(unittest.TestCase):
    def test_nen_sang_thi_lot(self):
        lines = [{"f0": 0, "f1": 30}, {"f0": 30, "f1": 60}]
        blocks = [{"loai": "chu_dap", "f0": 0, "f1": 40, "top": 300}, {"loai": "the_qua", "f0": 0, "f1": 40}]
        do = lambda v, t, r: (200, 20) if t < 1 else (60, 20)        # giây đầu nền trắng, sau tối
        n = do_nen.gan_nen("x.mp4", lines, {"center_y": 1490}, blocks, {}, do=do)
        self.assertEqual((lines[0].get("nen"), lines[1].get("nen")), (True, None))
        self.assertTrue(blocks[0].get("nen_toi")); self.assertNotIn("nen_toi", blocks[1])   # thẻ có nền riêng
        self.assertEqual(n, 2)

    def test_nen_roi_cung_lot_va_hop_mo_bo_qua(self):
        self.assertTrue(do_nen.can_lot((90, 80)))
        self.assertFalse(do_nen.can_lot(None))
        lines = [{"f0": 0, "f1": 30}]
        do_nen.gan_nen("x", lines, {"style": "hop_mo"}, [], {}, do=lambda *a: (250, 0))
        self.assertNotIn("nen", lines[0])


class DanhSachBenh(unittest.TestCase):
    def test_trieu_chung_khong_tich_xanh(self):
        x = ct.clean_data("checklist", {"tieu_de": "Dây tiêu đang bị", "items": ["Vàng lá", "Thối rễ"]})
        self.assertTrue(x["xau"])
        x = ct.clean_data("checklist", {"tieu_de": "Vì sao nên dùng", "items": ["Pha dễ", "Một can bốn chục bình"]})
        self.assertFalse(x["xau"])


class GiamKhaoSauMuc(unittest.TestCase):
    def test_chi_hoi_ai_sau_muc(self):
        q = km.danh_sach_cau_hoi()
        self.assertEqual(q.count("\n") + 1, 6)
        for k in ("nguoi_noi", "hinh_sach", "khoang_tho", "vung_an_toan", "nut_gio"):
            self.assertNotIn(f'"{k}"', q)

    def test_muc_may_khong_bat_la_dat(self):
        ai = {"muc": [{"id": k, "dat": True} for k in km.AI_HOI]}
        r = km.hop_nhat(ai, [])
        self.assertEqual(r["diem"], 10.0)
        self.assertEqual({m["id"] for m in r["muc"]}, set(km.AI_HOI) | km.CHI_MAY)


class CanhTheoMat(unittest.TestCase):
    def test_mat_lap_lai_thang_nhan_thoang_qua(self):
        khung = [[(0.4, 0.3, 0.2), (0.6, 0.7, 0.3)], [(0.42, 0.31, 0.2)], [(0.41, 0.29, 0.2)], []]
        self.assertEqual(tim_mat.chon_mat(khung), (0.41, 0.3))
        self.assertIsNone(tim_mat.chon_mat([[(0.6, 0.7, 0.3)], [], []]))     # 1 khung trong 3 → không tin

    def test_o_canh_theo_mat(self):
        f = BC._troi(340, 1200, 3.0, {"huong": 1}, 0, False, 0.2, "x", 0.63, 0.03, 0.3)
        self.assertIn("iw*0.630-340/2", f)
        self.assertIn("ih*0.300-1200*0.38", f)


if __name__ == "__main__":
    unittest.main()

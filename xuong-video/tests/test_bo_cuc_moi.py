"""Thử bố cục mới (gói L): chia_3, ba_doc, lat_trang; đạo diễn chọn thì giữ; ô vào cùng lúc; viền từ plan; chon_phu cho cảnh aff.
Không gọi AI/mạng/ffmpeg."""
import os, random, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-bocuc-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import bo_cuc as BC  # noqa: E402

LUOI = "eq=contrast=1.03:saturation=1.05"


def canh(i, **soat):
    return {"id": f"{i:03d}", "file": f"f{i}.mp4", "tu": 0.0, "den": 4.0, "dai": 4.0, "dep": [0.5, 3.5], "vai_tro": ["vuon"],
            "soat": {"dep": 4, "mat": 0, "chu_muc": 0, **soat}}


def doan(i, L, dur=2.4, phu=0, **kw):
    return {"shot": canh(i), "dur": dur, "src_start": 0.0, "bo_cuc": L, "phu_shots": [canh(100 + i * 10 + k) for k in range(phu)], **kw}


class HinhHocTest(unittest.TestCase):
    def test_kieu_moi_trong_vung_an_toan(self):
        for key in ("chia_3", "ba_doc"):
            ro = [(x - BC.B, y - BC.B, x + w + BC.B, y + h + BC.B) for (x, y, w, h) in BC.RECTS[key]]    # khung ngoài gồm viền
            for (x0, y0, x1, y1) in ro:
                self.assertGreaterEqual(y0, 220, key); self.assertLessEqual(y1, 1600, key)
                self.assertGreaterEqual(x0, 24, key); self.assertLessEqual(x1, BC.W - 24, key)
            for a in range(len(ro)):                                   # các ô không chạm/đè nhau (cách ≥ 8 px)
                for b in range(a + 1, len(ro)):
                    A, B_ = ro[a], ro[b]
                    ngang = A[2] + 8 <= B_[0] or B_[2] + 8 <= A[0]; doc = A[3] + 8 <= B_[1] or B_[3] + 8 <= A[1]
                    self.assertTrue(ngang or doc, (key, A, B_))
            self.assertEqual(len(BC.RECTS[key]), BC.SO_PHU[key] + 1)
            self.assertEqual(len(BC.APPEAR[key]), len(BC.RECTS[key]))

    def test_dang_ky_day_du(self):
        for k in ("chia_3", "ba_doc", "lat_trang"):
            self.assertIn(k, BC.SO_PHU)
        self.assertIn("chia_3", BC.HOP_MO); self.assertIn("ba_doc", BC.HOP_MO)
        self.assertEqual(len(BC.mask_sizes("chia_3", {"side": "trai"})), 3); self.assertEqual(BC.mask_sizes("lat_trang", {}), [])
        for k in ("chia_3", "ba_doc"):
            self.assertNotIn(k, BC.MAY_CHON)                           # máy không tự chọn kiểu mới

    def test_mo_ta_bo_cuc(self):
        m = BC.mo_ta_bo_cuc()
        self.assertEqual(set(m), set(BC.SO_PHU))
        for k, v in m.items():
            self.assertTrue(v["mo_ta"]); self.assertEqual(v["phu"], BC.SO_PHU[k]); self.assertGreaterEqual(v["phu_toi_da"], v["phu"])
        self.assertEqual(m["lat_trang"]["phu_toi_da"], 7)


class VaoCungLucTest(unittest.TestCase):
    def _loc(self, L, i=1, an_tu=0.33):
        opt = BC.tuy_chon(random.Random(1))
        n = BC.SO_PHU[L]
        mk = list(range(10, 10 + len(BC.mask_sizes(L, opt))))
        return BC.loc(i, L, 3.0, 0, list(range(1, 1 + n)), mk, LUOI, "null", opt, canh(1), [canh(2 + k) for k in range(n)], an_tu=an_tu)

    def test_moi_o_hien_tu_khung_dau(self):
        for L in ("chia_doi", "chia_ngang", "luoi_4", "chia_3", "ba_doc"):
            self.assertTrue(all(t == 0 for t in BC.APPEAR[L]), L)
            fc, times = self._loc(L)
            self.assertNotIn("enable=", ";".join(fc), L)                 # không ô nào bật muộn
            self.assertNotIn("eval=frame:enable", ";".join(fc))
            self.assertEqual(len(times), 1, L)                           # MỘT pop cho cả kiểu, không phải mỗi ô một pop
            self.assertAlmostEqual(times[0], 0.33)

    def test_doan_dau_khong_pop(self):
        self.assertEqual(self._loc("chia_3", i=0)[1], [])

    def test_pip_van_hien_sau(self):
        fc, times = self._loc("pip_troi")
        self.assertEqual(len(times), 1); self.assertGreater(times[0], 0.33)


class DaoDienChonTest(unittest.TestCase):
    def test_giu_nguyen_lua_chon_dao_dien(self):
        ban = ["khung_mo", "khung_mo", "khung_mo", "chia_doi", "khung_nho", "khung_nho", "chia_3", "khung_nho", "khung_nho", "khung_mo"]
        segs = [doan(i, k, phu=BC.SO_PHU[k]) for i, k in enumerate(ban)]
        L, ghi = BC.ep_bo_cuc(segs, ban, random.Random(1), lambda sg, n: [])
        self.assertEqual(L, ban); self.assertEqual(ghi, [])             # không ép trần 45% / sàn 35% / ≤ 2 liền

    def test_day_qua_2_8s_doi_khung_khong_doi_kieu(self):
        segs = [doan(0, "day", dur=3.4), doan(1, "day", dur=2.5)]
        L, ghi = BC.ep_bo_cuc(segs, ["day", "day"], random.Random(1), None)
        self.assertEqual(L, ["day", "day"])
        self.assertTrue(segs[0].get("doi_khung")); self.assertFalse(segs[1].get("doi_khung"))
        self.assertTrue(any("đoạn 0" in g and "đổi khung" in g for g in ghi))
        L2, ghi2 = BC.ep_bo_cuc(segs, L, random.Random(5), None)        # chạy lại: không ghi thêm
        self.assertEqual(L2, L); self.assertEqual(ghi2, [])

    def test_loc_day_doi_khung_hai_giai_doan(self):
        opt = BC.dat_doi_khung(BC.tuy_chon(random.Random(2)), [0.3, 0.3, 0.6, 0.7])
        fc, _ = BC.loc(0, "day", 3.4, 0, [], [], LUOI, "null", opt, canh(1), [])
        j = ";".join(fc)
        self.assertIn("split=2", j); self.assertIn("concat=n=2", j); self.assertIn("[v0]", j)
        nb = BC.nhan_hieu_dung("day", opt, [0.3, 0.3, 0.6, 0.7])
        self.assertTrue(all(0 <= v <= 1 for v in nb)); self.assertLessEqual(nb[0], 0.3 + 1e-6)

    def test_thieu_phu_lay_them_roi_ha_kieu(self):
        pool = [canh(50), canh(51)]
        segs = [doan(0, "chia_3", phu=0)]
        L, ghi = BC.ep_bo_cuc(segs, ["chia_3"], random.Random(1), lambda sg, n: pool[:n])
        self.assertEqual(L, ["chia_3"]); self.assertEqual(len(segs[0]["phu_shots"]), 2); self.assertEqual(ghi, [])   # lấy thêm được → giữ kiểu
        segs = [doan(0, "ba_doc", phu=0), doan(1, "luoi_4", phu=1), doan(2, "chia_3", phu=0)]
        L, ghi = BC.ep_bo_cuc(segs, ["ba_doc", "luoi_4", "chia_3"], random.Random(1), None)   # không có nguồn phụ → kiểu gần nhất vừa đủ
        self.assertEqual(L[0], "khung_mo")                              # ba_doc → chia_ngang (1 phụ) → khung_mo (0)
        self.assertIn(L[1], ("chia_doi", "khung_mo")); self.assertEqual(len(ghi), 3)
        for sg, k in zip(segs, L):
            self.assertGreaterEqual(len(sg["phu_shots"]), BC.SO_PHU[k])

    def test_lat_trang_qua_ngan_ha_kieu(self):
        segs = [doan(0, "lat_trang", dur=0.4, phu=3)]
        L, _ = BC.ep_bo_cuc(segs, ["lat_trang"], random.Random(1), None)
        self.assertEqual(L, ["day_zoom"])

    def test_doan_may_van_chiu_tran_san(self):
        segs = [{"shot": canh(i), "dur": 2.4, "src_start": 0.0, "phu_shots": []} for i in range(10)]    # không có bo_cuc → máy tự gán
        pool = [canh(200 + i) for i in range(10)]
        L, _ = BC.ep_bo_cuc(segs, ["khung_mo"] * 10, random.Random(1), lambda sg, n: pool[:n])
        self.assertLessEqual(sum(k in BC.HOP_MO for k in L), int(0.45 * 10 + 1e-9))
        self.assertTrue(all(k in BC.MAY_CHON for k in L))
        segs2 = [dict(sg, bo_cuc="khung_mo", bo_cuc_may=True) for sg in segs]        # đánh dấu máy gán → vẫn chịu trần/sàn
        L2, _ = BC.ep_bo_cuc(segs2, ["khung_mo"] * 10, random.Random(1), lambda sg, n: pool[:n])
        self.assertLessEqual(sum(k in BC.HOP_MO for k in L2), 4)


class LatTrangTest(unittest.TestCase):
    def test_chia_lat(self):
        n, sl, moc = BC.lat_trang_chia(4.0, 8)
        self.assertEqual(n, 8); self.assertAlmostEqual(sl, 0.5); self.assertEqual(len(moc), 7)
        n, sl, moc = BC.lat_trang_chia(1.0, 8)                            # ngắn → bớt lát, mỗi lát ≥ 0,28 s
        self.assertEqual(n, 3); self.assertGreaterEqual(sl, BC.LAT_MIN); self.assertEqual(len(moc), 2)
        n, sl, _ = BC.lat_trang_chia(3.0, 4)
        self.assertEqual(n, 4); self.assertAlmostEqual(sl, 0.75)
        self.assertEqual(BC.lat_trang_chia(0.2, 5)[0], 1)
        self.assertLessEqual(BC.lat_trang_chia(60, 20)[0], 8)

    def test_loc_lat_trang(self):
        phu = [canh(2 + k) for k in range(4)]
        fc, times = BC.loc(0, "lat_trang", 2.0, 0, [1, 2, 3, 4], [], LUOI, "null", {"cham": None}, canh(1), phu)
        j = ";".join(fc)
        self.assertIn("concat=n=5", j); self.assertEqual(times, [])
        self.assertEqual(len([x for x in fc if "trim=duration=0.400" in x]), 5)      # 2,0 s / 5 lát
        # mỗi lát một độ phóng/neo khác nhau
        cr = [x.split("crop=iw*")[2].split(",scale")[0] for x in fc if x.count("crop=iw*") >= 2]
        self.assertEqual(len(set(cr)), len(cr))

    def test_nhan_hieu_dung_lat_trang(self):
        self.assertIsNone(BC.nhan_hieu_dung("lat_trang", {}, [0.2, 0.2, 0.5, 0.5]))


class VienTest(unittest.TestCase):
    def test_vien_tu_plan_khong_ngau_nhien(self):
        for vien, mong in (("white", "white"), ("vang", "0xFFD400"), ("0x2E9E44", "0x2E9E44")):
            rng = random.Random(3)
            self.assertEqual({BC.tuy_chon(rng, None, vien)["vien"] for _ in range(60)}, {mong})
        self.assertEqual(BC.tuy_chon(random.Random(1))["vien"], "white")
        opt = BC.tuy_chon(random.Random(1), None, "0xFFD400")
        fc, _ = BC.loc(0, "chia_3", 3.0, 0, [1, 2], [10, 11, 12], LUOI, "null", opt, canh(1), [canh(2), canh(3)])
        self.assertIn("color=0xFFD400", ";".join(fc)); self.assertNotIn("color=white", ";".join(fc))


class ChonPhuTest(unittest.TestCase):
    def test_aff_duoc_chon_khong_bi_loai(self):
        aff = dict(canh(7, mat=2), vai_tro=["chai_ro"], loai="nguoi_noi", the=["nguoi_noi_vao_may"])
        chu_nang = canh(8, chu_muc=2); hang_khac = dict(canh(9, hang_khac=True), vai_tro=["chai_ro"]); xau = canh(10, dep=1)
        sg = {"shot": canh(1), "dur": 2.0, "src_start": 0.0}
        thay = set()
        for sd in range(40):
            for p in BC.chon_phu(sg, 2, [aff, chu_nang, hang_khac, xau, canh(1)], random.Random(sd), set()):
                thay.add(p["shot"]["id"])
        self.assertIn("007", thay)
        self.assertFalse(thay & {"008", "009", "010"}, thay)
        self.assertTrue(BC._aff(aff))

    def test_aff_nguoi_noi_khong_bi_tru_o_chuoi_chai(self):          # cảnh chính là chai: ô phụ aff cầm chai vẫn được dùng
        aff = dict(canh(7, mat=2), vai_tro=["chai_ro"], loai="nguoi_noi")
        sg = {"shot": dict(canh(1), vai_tro=["chai_ro"]), "dur": 2.0, "src_start": 0.0}
        ra = BC.chon_phu(sg, 1, [aff], random.Random(1), set())
        self.assertEqual(ra[0]["shot"]["id"], "007")


if __name__ == "__main__":
    unittest.main()

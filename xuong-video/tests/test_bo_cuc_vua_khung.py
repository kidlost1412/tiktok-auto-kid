"""Bố cục phải VỪA KHUNG cảnh: người toàn/trung không vào ô hẹp (mất đầu/mặt bé), kiểu nhiều ô tối đa 1 lần/video. Không AI/mạng/ffmpeg."""
import os, random, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-vuakhung-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import bo_cuc as BC  # noqa: E402


def canh(i, mat=0, co="toan", **kw):
    return {"id": f"{i:03d}", "file": f"f{i}.mp4", "tu": 0.0, "den": 4.0, "dai": 4.0, "dep": [0.5, 3.5], "vai_tro": ["vuon"], "co_canh": co,
            "soat": {"dep": 4, "mat": mat, "chu_muc": 0}, **kw}


NGUOI_TOAN, NGUOI_TRUNG, NGUOI_CAN, TAY_CAN, LA_TOAN = canh(1, 1, "toan"), canh(2, 1, "trung"), canh(3, 1, "can"), canh(4, 0, "can"), canh(5, 0, "toan")


def doan(i, L, shot=None, phu=(), **kw):
    return {"shot": shot or TAY_CAN, "dur": 2.4, "src_start": 0.0, "bo_cuc": L, "phu_shots": list(phu), **kw}


class VuaOHepTest(unittest.TestCase):
    def test_luat(self):
        self.assertFalse(BC.vua_o_hep(NGUOI_TOAN)); self.assertFalse(BC.vua_o_hep(NGUOI_TRUNG))
        self.assertFalse(BC.vua_o_hep(canh(6, 1, None)))                 # có người, chưa rõ cỡ cảnh → không chắc → không vào ô hẹp
        self.assertTrue(BC.vua_o_hep(NGUOI_CAN)); self.assertTrue(BC.vua_o_hep(TAY_CAN)); self.assertTrue(BC.vua_o_hep(LA_TOAN))
        aff = dict(canh(7, 0, "toan"), loai="nguoi_noi")
        self.assertFalse(BC.vua_o_hep(aff))                              # aff toàn cảnh = có người


class EpVuaKhungTest(unittest.TestCase):
    def test_nguoi_toan_khong_vao_o_hep_ha_kieu(self):
        for K in ("chia_3", "chia_doi", "luoi_4"):
            n = BC.SO_PHU[K]
            segs = [doan(0, K, TAY_CAN, [TAY_CAN] * (n - 1) + [NGUOI_TOAN])]            # ô phụ cuối là người toàn
            L, ghi = BC.ep_bo_cuc(segs, [K], random.Random(1), None)
            self.assertEqual(L, ["khung_mo"], K); self.assertTrue(any("vừa ô hẹp" in g for g in ghi))
            segs = [doan(0, K, NGUOI_TRUNG, [TAY_CAN] * n)]                              # cảnh chính (ô đầu) là người trung
            self.assertEqual(BC.ep_bo_cuc(segs, [K], random.Random(1), None)[0], ["khung_mo"], K)

    def test_pip_chi_xet_o_phu_nen_chinh_nguoi_toan_van_duoc(self):
        segs = [doan(0, "pip_troi", NGUOI_TOAN, [TAY_CAN])]                              # cảnh chính toàn màn: không phải ô hẹp
        self.assertEqual(BC.ep_bo_cuc(segs, ["pip_troi"], random.Random(1), None)[0], ["pip_troi"])
        segs = [doan(0, "pip_troi", TAY_CAN, [NGUOI_TOAN])]
        self.assertEqual(BC.ep_bo_cuc(segs, ["pip_troi"], random.Random(1), None)[0], ["khung_mo"])

    def test_doi_phu_khong_vua_bang_canh_vua(self):
        segs = [doan(0, "chia_3", TAY_CAN, [NGUOI_TOAN, NGUOI_TRUNG])]
        L, ghi = BC.ep_bo_cuc(segs, ["chia_3"], random.Random(1), lambda sg, n: [NGUOI_CAN, LA_TOAN][:n])
        self.assertEqual(L, ["chia_3"]); self.assertEqual(ghi, [])
        self.assertTrue(all(BC.vua_o_hep(s) for s in segs[0]["phu_shots"]))

    def test_phu_lay_them_khong_vua_van_ha_kieu(self):
        segs = [doan(0, "chia_3", TAY_CAN, [NGUOI_TOAN, NGUOI_TRUNG])]
        L, _ = BC.ep_bo_cuc(segs, ["chia_3"], random.Random(1), lambda sg, n: [NGUOI_TOAN] * n)
        self.assertEqual(L, ["khung_mo"])

    def test_chay_lai_khong_doi(self):
        segs = [doan(0, "chia_3", TAY_CAN, [TAY_CAN, NGUOI_TOAN]), doan(1, "chia_3", TAY_CAN, [TAY_CAN, TAY_CAN])]
        L, _ = BC.ep_bo_cuc(segs, ["chia_3", "chia_3"], random.Random(1), None)
        self.assertEqual(L, ["khung_mo", "chia_3"])
        L2, ghi2 = BC.ep_bo_cuc(segs, L, random.Random(1), None)
        self.assertEqual(L2, L); self.assertEqual(ghi2, [])

    def test_kieu_nhieu_o_toi_da_1_lan(self):
        ban = ["ba_doc", "khung_nho", "ba_doc", "chia_doi", "khung_nho", "chia_doi", "chia_3", "khung_nho", "chia_3", "khung_mo"]
        segs = [doan(i, k, TAY_CAN, [TAY_CAN] * BC.SO_PHU[k]) for i, k in enumerate(ban)]
        L, ghi = BC.ep_bo_cuc(segs, ban, random.Random(1), lambda sg, n: [TAY_CAN] * n)
        for k in BC.NHIEU_O:
            self.assertLessEqual(L.count(k), 1, k)
        self.assertEqual(L[:3], ["ba_doc", "khung_nho", "khung_mo"])


class AffDungMotMinhTest(unittest.TestCase):
    """23/11 Kid: aff đứng 1 mình lâu dễ bị đánh reup → ghép aff khác (ô dọc cao giữ đầu) / tua nhanh / chữ lớn."""
    AFF = dict(canh(20, 1, "trung"), loai="nguoi_noi")
    AFF2 = dict(canh(21, 1, "toan"), loai="nguoi_noi")

    def test_o_doc_cao_nhan_nguoi(self):
        for K in BC.O_CAO:
            self.assertTrue(BC.vua_o_hep(NGUOI_TOAN, K))
        segs = [doan(0, "chia_ngang", NGUOI_TOAN, [NGUOI_TRUNG])]
        self.assertEqual(BC.ep_bo_cuc(segs, ["chia_ngang"], random.Random(1), None)[0], ["chia_ngang"])

    def test_ghep_aff_khac(self):
        segs = [doan(0, "day", self.AFF, dur=3.0), doan(1, "day", TAY_CAN)]
        L, ghi = BC.ep_bo_cuc(segs, ["day", "day"], random.Random(1), lambda sg, n: [self.AFF2] * n)
        self.assertEqual(L[0], "chia_ngang"); self.assertIs(segs[0]["phu_shots"][0], self.AFF2)

    def test_khong_ghep_duoc_thi_tua_hoac_chu_lon(self):
        segs = [doan(0, "day", dict(self.AFF, den=10.0), dur=3.0), doan(1, "day", TAY_CAN)]
        L, _ = BC.ep_bo_cuc(segs, ["day", "day"], random.Random(1), lambda sg, n: [TAY_CAN] * n)
        self.assertEqual(L[0], "day"); self.assertEqual(segs[0]["tua_nhanh"], BC.TUA_AFF)
        segs = [doan(0, "day", self.AFF, dur=3.5), doan(1, "day", TAY_CAN)]          # cảnh 4 s không đủ tua 1,35 lần
        BC.ep_bo_cuc(segs, ["day", "day"], random.Random(1), None)
        self.assertTrue(segs[0].get("can_chu_lon")); self.assertNotIn("tua_nhanh", segs[0])

    def test_aff_ngan_hoac_da_ghep_khong_dung(self):
        segs = [doan(0, "day", self.AFF, dur=1.8), doan(1, "chia_ngang", self.AFF, [TAY_CAN], dur=3.0)]
        L, _ = BC.ep_bo_cuc(segs, ["day", "chia_ngang"], random.Random(1), lambda sg, n: [self.AFF2] * n)
        self.assertEqual(L[0], "day"); self.assertFalse(any(sg.get("tua_nhanh") or sg.get("can_chu_lon") for sg in segs))


class ChonBoCucTest(unittest.TestCase):
    def test_may_chon_nguoi_toan_khong_vao_o_hep(self):
        for sd in range(60):
            segs = [{"shot": NGUOI_TOAN, "dur": 2.4} for _ in range(12)]
            L = BC.chon_bo_cuc(segs, random.Random(sd))
            self.assertFalse([k for k in L if k in BC.O_HEP and k not in BC.NEN_RO and k not in BC.O_CAO], (sd, L))

    def test_may_chon_moi_kieu_nhieu_o_toi_da_1_lan_va_van_da_dang(self):
        tap = set()
        for sd in range(60):
            segs = [{"shot": TAY_CAN, "dur": 2.4} for _ in range(12)]
            L = BC.chon_bo_cuc(segs, random.Random(sd))
            self.assertEqual(L, BC.chon_bo_cuc(segs, random.Random(sd)))                 # cùng seed → cùng kết quả
            for k in BC.NHIEU_O:
                self.assertLessEqual(L.count(k), 1, (sd, L))
            tap.add(tuple(L))
        self.assertGreater(len(tap), 30)


class ChonPhuTest(unittest.TestCase):
    def test_phu_uu_tien_canh_vua(self):
        pool = [NGUOI_TOAN, NGUOI_TRUNG, canh(8, 0, "can"), canh(9, 0, "toan"), canh(10, 1, "can")]
        sg = {"shot": canh(50), "dur": 2.0, "src_start": 0.0}
        for sd in range(30):
            ra = BC.chon_phu(sg, 2, pool, random.Random(sd), set())
            self.assertTrue(all(BC.vua_o_hep(p["shot"]) for p in ra), sd)


class CatDauTest(unittest.TestCase):
    def test_nguoi_giu_phan_tren_chi_troi_ngang(self):
        opt = BC.tuy_chon(random.Random(1)); opt["truc"] = "y"
        fc, _ = BC.loc(0, "chia_doi", 3.0, 0, [1], [10, 11], "null", "null", opt, TAY_CAN, [NGUOI_CAN])
        j = ";".join(fc)
        self.assertIn(":y='(ih-740)*0.2'", j)          # ô người: neo trên 20%
        self.assertIn(":y='(ih-740)*(", j)             # ô không người: vẫn trôi dọc theo truc "y"


if __name__ == "__main__":
    unittest.main()

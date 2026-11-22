"""Đợt 1 sửa biên kịch (viet_loi): từ cấm chia đôi, thông báo âm tiết, gán trục góc quà, vai in một lần, giọng thật ổn định,
bài học lọc việc dựng, tên phải nhắc bỏ đuôi cỡ gói. KHÔNG gọi AI."""
import os, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_bien_kich_moi as T  # noqa: E402
import dao_dien  # noqa: E402

vl = T.vl


class TuCam(T.Nen):
    def kiem(self, tu):
        it = T.kich_ban(2, self.sp, mo="mat_mat")
        it["text"] = it["text"].replace("Ngắn gọn thôi mà bà con.", f"Là {tu} đó.")
        return vl.check(it, self.sp, set())[0]

    def test_chu_cam_va_van_mau_co_thong_bao_rieng(self):
        for tu in ("số 1", "duy nhất", "nhất thị trường"):
            self.assertTrue(any(x == f"từ cấm '{tu}'" for x in self.kiem(tu)), tu)
        for tu in ("giải pháp toàn diện", "tham khảo"):
            self.assertTrue(any(x == f"văn mẫu yếu '{tu}'" for x in self.kiem(tu)), tu)

    def test_bo_cam_nhung_tu_cu(self):
        for tu in ("chữa khỏi", "khỏi hẳn", "100%", "không độc", "ăn ngay"):
            self.assertFalse(any(x.startswith(("từ cấm", "văn mẫu yếu")) for x in self.kiem(tu)), tu)

    def test_thong_bao_am_tiet(self):
        it = T.kich_ban(1, self.sp)
        it["text"] = "[curious] Ngắn. [warm] Quá. [confident] Ngắn."
        e = vl.check(it, self.sp, set())[0]
        _lo, _hi, nho, lon = vl.khung_am_tiet(self.sp)[:4]
        self.assertTrue(any(f"(máy nhận {nho}–{lon}, nên nhắm {_lo}–{_hi})" in x for x in e), e)


class GanTruc(T.Nen):
    def test_goc_qua_co_qua_chot_qua_cu_the(self):
        t = vl.gan_truc(self.sp, ["qua-tang"], 4, vl.moi_dem(), None, vl.lo_moi(), 4, rng=None)
        self.assertEqual({x["chot"] for x in t}, {"qua_cu_the"})

    def test_goc_qua_van_chot_qua_khi_het_han_muc(self):
        lo = vl.lo_moi(); lo["qua"] = 99
        t = vl.gan_truc(self.sp, ["qua-tang", "rua-vuon"], 6, vl.moi_dem(), None, lo, 6, rng=None)
        self.assertTrue(all(x["chot"] == "qua_cu_the" for x in t if x["goc"] == "qua-tang"))
        self.assertTrue(any(x["goc"] == "qua-tang" for x in t))
        self.assertEqual(lo["qua"], 99)                       # góc quà không tính vào hạn mức

    def test_khong_co_qua_thi_khong_giao_goc_qua(self):
        sp = T.sp_mau(self.kho, qua_tang=[])
        t = vl.gan_truc(sp, ["rua-vuon", "qua-tang"], 8, vl.moi_dem(), None, vl.lo_moi(), 8, rng=None)
        self.assertEqual({x["goc"] for x in t}, {"rua-vuon"})


class DeBai(T.Nen):
    def kiem_so_luong(self, n, khoa_vai):
        truc = [{"goc": "rua-vuon", "mo": "mat_mat", "than": "so_sanh", "chot": "thu_it", "vai": khoa_vai[i % len(khoa_vai)]} for i in range(n)]
        d = vl._de_bai(self.sp, truc)
        for k in khoa_vai[:n]:
            self.assertEqual(d.count(vl.VAI[k]), 1, k)        # mỗi mô tả vai đúng một lần
            self.assertEqual(d.count(f"vai = {k}"), sum(1 for t in truc if t["vai"] == k))
        for ax in ("góc =", "kiểu mở =", "kiểu thân =", "kiểu chốt =", "vai ="):
            self.assertEqual(d.count(ax), n, ax)
        self.assertLess(d.index(vl.VAI[khoa_vai[0]]), d.index("bai[0]"))

    def test_mot_ba_muoi_ban(self):
        vl.VAI["vai_phu"] = "Vai phụ thử nghiệm."
        self.addCleanup(vl.VAI.pop, "vai_phu", None)
        self.kiem_so_luong(1, ["nguoi_noi_dung"])
        self.kiem_so_luong(3, ["nguoi_noi_dung", "vai_phu"])
        self.kiem_so_luong(10, ["nguoi_noi_dung"])
        self.kiem_so_luong(10, ["nguoi_noi_dung", "vai_phu"])

    def test_thu_tu_truc(self):
        d = vl._de_bai(self.sp, [{"goc": "rua-vuon", "mo": "mat_mat", "than": "so_sanh", "chot": "thu_it", "vai": "nguoi_noi_dung"}])
        pos = [d.index(x) for x in ("góc =", "kiểu mở =", "kiểu thân =", "kiểu chốt =", "vai = ")]
        self.assertEqual(pos, sorted(pos))


class GiongThat(T.Nen):
    def test_kho_rong(self):
        self.assertEqual(vl.giong_that(self.sp), "")

    def test_it_cau_khong_muon_kho_khac(self):
        kho2 = self.tmp / "kho2"; kho2.mkdir()
        (self.hub / "san-pham" / "sp-chung").mkdir()
        (self.hub / "san-pham" / "sp-chung" / "san-pham.json").write_text(
            vl.json.dumps({"ma": "sp-chung", "loai": "kho-chung", "ten_goi": "Kho Chung", "kho_video": str(kho2)}), encoding="utf-8")
        d = kho2 / "_mo-ta"; d.mkdir()
        (d / "z.mp4.mo-ta.json").write_text(vl.json.dumps({"kieu": 2, "loi_hay": ["Câu của kho dùng chung này không được mượn sang đâu nhé anh em."]}, ensure_ascii=False), encoding="utf-8")
        self.mo_ta("a.mp4", loi=["Câu một của người thật nói ngoài vườn nhà mình đó anh em.", "Câu hai của người thật nói ngoài vườn nhà mình đó bà con."])
        k = vl.giong_that(self.sp)
        self.assertEqual(k.count('\n- "'), 2)
        self.assertNotIn("kho dùng chung", k)

    def test_trung_cau_va_on_dinh(self):
        ds = [f"Câu số {c} của người thật nói ngoài vườn nhà mình đó anh em ơi." for c in "dbeacfghijk"]
        self.mo_ta("a.mp4", loi=ds + [ds[0], ds[0].upper()])
        a = vl.giong_that(self.sp)
        vl._GIONG_CACHE.clear()
        self.assertEqual(a, vl.giong_that(self.sp, vl.random.Random(7)))
        self.assertEqual(a.count('\n- "'), 8)
        self.assertEqual(a.count(ds[0]), 1)
        thu_tu = [l for l in a.splitlines() if l.startswith("- ")]
        self.assertEqual(thu_tu, sorted(thu_tu, key=lambda l: vl.norm(l[3:-1])))


class BaiHocLoi(unittest.TestCase):
    def test_loc_viec_dung_giu_viec_viet(self):
        giu = ["- đọc đúng liều ghi trên nhãn", "- đừng viết câu đòi cảnh kho không có", "- nhắc đúng quà thật ở câu chốt"]
        bo = ["- khối chữ to che mất tên chai, nhắc giá lại", "- phụ đề đè nhãn, ghi giá rõ hơn", "- cảnh đứng yên quá lâu khi nói giá",
              "- đổi cảnh mỗi câu nói", "- hình cuối phải có nút giỏ, chốt rõ", "- cảnh quà phải rõ, nhắc quà", "- che nhãn khi nói tên", "- bố cục lệch, viết lại"]
        cu = dao_dien.bai_hoc_cho
        dao_dien.bai_hoc_cho = lambda ma: "\n".join(bo[:4] + giu + bo[4:] + ["- Không dính gì cả."])
        try:
            r = vl.bai_hoc_cho_loi("x", toi_da=20).splitlines()
        finally:
            dao_dien.bai_hoc_cho = cu
        self.assertEqual(r, giu)


class TenPhaiNhac(unittest.TestCase):
    def test_bo_duoi_goi_va_khu_trung(self):
        sp = {"ten_goi": "Đạm cá amino can 5l", "ten_ngan": "Đạm cá amino can 5l"}
        self.assertEqual(vl.ten_phai_nhac(sp), ["Đạm cá amino can 5l", "Đạm cá amino"])
        self.assertEqual(vl.ten_phai_nhac({"ten_goi": "Đạm cá Toàn Cầu (can 1 lít)"}), ["Đạm cá Toàn Cầu (can 1 lít)", "Đạm cá Toàn Cầu"])
        self.assertEqual(vl.ten_phai_nhac({"ten_goi": "Nano Đồng chai 500ml"}), ["Nano Đồng chai 500ml"])   # còn < 3 từ → không rút
        self.assertIn("chai nano đồng này", vl.ten_phai_nhac({"ma": "nano-dong", "ten_goi": "Nano"}))

    def test_kiem_ten(self):
        sp = T.sp_mau(Path("."), ten_goi="Đạm cá amino can 5l", ten_ngan="Đạm cá amino can 5l")
        ok = vl.check(T.kich_ban(1, sp, ten="Đạm cá amino Toàn Cầu này một can năm lít"), sp, set())[0]
        self.assertFalse([e for e in ok if "tên" in e], ok)
        xau = vl.check(T.kich_ban(1, sp, ten="Cái này"), sp, set())[0]
        self.assertIn("thiếu tên thương hiệu", xau)


if __name__ == "__main__":
    unittest.main()

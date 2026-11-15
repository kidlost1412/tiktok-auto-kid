"""Kiến thức bán hàng cho biên kịch: khối ban_hang, đề bài cũ đã ghim vẫn nhận, trường don_ban, đọc/lưu hồ sơ riêng."""
import json, os, shutil, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
ENG = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENG))
import prompt_mau as pm  # noqa: E402
import viet_loi as vl  # noqa: E402

THAT = Path(__file__).resolve().parents[1]


class BanHangTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bh-"))
        self.data = self.tmp / "data"
        (self.data / "san-pham" / "sp1").mkdir(parents=True)
        (self.data / "san-pham" / "sp1" / "san-pham.json").write_text("{}", encoding="utf-8")
        self._d, self._h = pm.DATA, vl.HUB
        pm.DATA, vl.HUB = self.data, self.data

    def tearDown(self):
        pm.DATA, vl.HUB = self._d, self._h
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ctx(self):
        sp = {"ma": "sp1", "ten_goi": "SP Một", "ten_ngan": "SP Một", "su_that_duoc_noi": ["a"]}
        return vl.ctx_bien_kich(sp, 1, ["g"], [], [], truc=[{"goc": "g", "mo": "m", "than": "t", "chot": "c", "vai": "v"}], sp_day=sp)

    def test_co_khoi_khi_co_file(self):
        vl.luu_ban_hang_rieng("sp1", "Khách là người trồng ớt.")
        kq = vl.ban_hang("sp1")
        self.assertIn("KIẾN THỨC BÁN HÀNG", kq)
        self.assertIn("=== HỒ SƠ BÁN HÀNG RIÊNG", kq)
        self.assertIn("người trồng ớt", kq)

    def test_khong_co_ho_so_rieng_van_co_phan_chung(self):
        kq = vl.ban_hang("sp1")
        self.assertIn("KIẾN THỨC BÁN HÀNG", kq)
        self.assertNotIn("=== HỒ SƠ BÁN HÀNG RIÊNG", kq)

    def test_khong_co_gi_thi_rong(self):
        sua = pm.duong_dan_sua("kien-thuc-ban-hang"); sua.parent.mkdir(parents=True, exist_ok=True)
        orig = vl.prompt_mau.doc_luat
        vl.prompt_mau.doc_luat = lambda t: "" if t == "KIEN-THUC-BAN-HANG.md" else orig(t)
        try:
            self.assertEqual(vl.ban_hang("sp1"), "")
        finally:
            vl.prompt_mau.doc_luat = orig

    def test_theo_ban_nguoi_dung_sua(self):
        sua = pm.duong_dan_sua("kien-thuc-ban-hang"); sua.parent.mkdir(parents=True, exist_ok=True)
        sua.write_text("# Của tôi\nchỉ bán bằng chuyện hàng xóm", encoding="utf-8")
        self.assertIn("chuyện hàng xóm", vl.ban_hang("sp1"))

    def test_gioi_han_do_dai(self):
        sua = pm.duong_dan_sua("kien-thuc-ban-hang"); sua.parent.mkdir(parents=True, exist_ok=True)
        sua.write_text("\n".join(f"dòng {i} " + "x" * 60 for i in range(500)), encoding="utf-8")
        kq = vl.ban_hang("sp1")
        self.assertLessEqual(len(kq), vl.BAN_HANG_CHUNG_TOI_DA + 200)
        self.assertFalse(kq.split("\n")[-3].endswith("dòng"))

    def test_ctx_va_prompt_mac_dinh_co_khoi(self):
        c = self.ctx()
        self.assertIn("KIẾN THỨC BÁN HÀNG", c["ban_hang"])
        out = pm.dung("bien-kich", pm.mac_dinh("bien-kich"), c)
        self.assertIn("KIẾN THỨC BÁN HÀNG", out)
        self.assertIn('"don_ban"', out)
        self.assertNotIn("{{ban_hang}}", out)

    def test_de_bai_cu_da_ghim_van_nhan_kien_thuc_va_don_ban(self):
        cu = "Bạn là biên kịch cũ.\n{{san_pham}}\n{{so_ban}} {{de_bai}} {{ten_phai_nhac}} {{giong}}\n\"y_canh\": []"
        pm.duong_dan_sua("bien-kich").parent.mkdir(parents=True, exist_ok=True)
        pm.duong_dan_sua("bien-kich").write_text(cu, encoding="utf-8")
        out = pm.dung("bien-kich", cu, self.ctx())
        self.assertIn("KIẾN THỨC BÁN HÀNG", out)          # tự gắn cuối đề bài (bat_buoc)
        self.assertIn('"don_ban"', out)                    # HOP_DONG tự gắn

    def test_de_bai_cu_khong_khoi_rong_khi_thieu_tai_lieu(self):
        cu = "cũ {{san_pham}} {{so_ban}} {{de_bai}} {{ten_phai_nhac}} {{giong}} y_canh"
        c = self.ctx(); c["ban_hang"] = ""
        self.assertNotIn("[Kiến thức bán hàng", pm.dung("bien-kich", cu, c))

    def test_tai_lieu_dang_ky_va_sach_kiem(self):
        self.assertIn("kien-thuc-ban-hang", pm.VAI)
        self.assertEqual(pm.kiem("bien-kich", pm.mac_dinh("bien-kich"))["thieu"], [])
        self.assertTrue((THAT / "luat" / "KIEN-THUC-BAN-HANG.md").is_file())

    def test_gon_don_ban(self):
        self.assertEqual(vl.gon_don_ban(None), "")
        self.assertEqual(vl.gon_don_ban(["x"]), "")
        self.assertEqual(vl.gon_don_ban("  mua  ngay  "), "mua ngay")
        dai = vl.gon_don_ban(" ".join(["từ"] * 40))
        self.assertLessEqual(len(dai.rstrip("…").split(" ")), 20)

    def test_luu_doc_ban_hang_rieng(self):
        self.assertEqual(vl.doc_ban_hang_rieng("sp1"), "")
        self.assertEqual(vl.luu_ban_hang_rieng("sp1", "abc\r\ndef"), 7)
        self.assertEqual(vl.doc_ban_hang_rieng("sp1"), "abc\ndef")
        self.assertEqual([f.name for f in (self.data / "san-pham" / "sp1").glob("*.tmp")], [])
        with self.assertRaises(ValueError):
            vl.luu_ban_hang_rieng("sp1", "x" * (vl.BAN_HANG_RIENG_TOI_DA + 1))
        self.assertEqual(vl.doc_ban_hang_rieng("sp1"), "abc\ndef")      # lưu hỏng không phá bản cũ
        with self.assertRaises(ValueError):
            vl.luu_ban_hang_rieng("../x", "a")
        with self.assertRaises(ValueError):
            vl.luu_ban_hang_rieng("khong-co", "a")
        vl.luu_ban_hang_rieng("sp1", "  ")
        self.assertEqual(vl.doc_ban_hang_rieng("sp1"), "")


if __name__ == "__main__":
    unittest.main()

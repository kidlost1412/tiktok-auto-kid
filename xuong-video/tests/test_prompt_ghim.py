"""Thử cơ chế 'cập nhật app không tự đổi gu': ghim bản gốc, phát hiện bản mới, áp dụng / giữ / sao lưu, đề bài cũ vẫn chạy.
Chạy:  python -m unittest discover -s xuong-video/tests -v"""
import json, os, shutil, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
ENG = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENG))
import prompt_mau as pm  # noqa: E402
import ekip  # noqa: E402

THUC = Path(__file__).resolve().parents[1]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pg-"))
        self.code, self.data = self.tmp / "code", self.tmp / "data"
        (self.code / "prompt").mkdir(parents=True); (self.code / "luat").mkdir()
        self.data.mkdir()
        (self.code.parent / "VERSION").write_text("1.0.0")
        self._c, self._d = pm.CODE, pm.DATA
        pm.CODE, pm.DATA = self.code, self.data
        for k in pm.VAI:
            pm.duong_dan_goc(k).write_text(f"gu cu cua {k}\ndong 2\n", encoding="utf-8")

    def tearDown(self):
        pm.CODE, pm.DATA = self._c, self._d
        shutil.rmtree(self.tmp, ignore_errors=True)

    def phat_hanh(self, k, text, ver):
        """Giả lập bản cập nhật app: đổi bản gốc đi kèm + nâng VERSION."""
        pm.duong_dan_goc(k).write_text(text, encoding="utf-8")
        (self.code.parent / "VERSION").write_text(ver)


class GhimTest(Base):
    def test_cai_moi_ghim_ban_hien_hanh(self):
        pm.ghim_tat_ca()
        for k in pm.VAI:
            self.assertEqual(pm.goc(k), pm.mac_dinh(k))
            self.assertTrue(pm.duong_dan_ghim(k).is_file())
        self.assertEqual(pm.ver_ghim("hoc-canh"), "1.0.0")
        self.assertEqual(pm.ds_ban_moi(), [])

    def test_nguoi_dung_cu_co_ban_sua_giu_nguyen_va_duoc_ghim(self):
        sua = pm.duong_dan_sua("bien-kich"); sua.parent.mkdir(parents=True)
        sua.write_text("gu rieng cua toi", encoding="utf-8")
        pm.ghim_tat_ca()
        self.assertEqual(pm.doc("bien-kich"), ("gu rieng cua toi", True))
        self.assertEqual(sua.read_text(encoding="utf-8"), "gu rieng cua toi")
        self.assertEqual(pm.goc("bien-kich"), "gu cu cua bien-kich\ndong 2\n")

    def test_khong_sua_di_thang_len_ban_moi_khong_doi_hanh_vi(self):
        pm.ghim_tat_ca()
        self.phat_hanh("giam-khao", "GU MOI hoan toan\n", "1.1.0")
        self.assertEqual(pm.doc("giam-khao"), ("gu cu cua giam-khao\ndong 2\n", False))     # vẫn bản cũ
        self.assertIn("gu cu", pm.dien("giam-khao", ten="X", cau="c"))
        self.assertEqual(pm.ds_ban_moi(), ["giam-khao"])
        self.assertTrue(pm.duong_dan_hieu_luc("giam-khao").samefile(pm.duong_dan_ghim("giam-khao")))

    def test_bien_chua_ghim_dung_ban_hien_hanh_roi_ghim_khi_dien(self):
        self.assertEqual(pm.doc("he-thong")[0], "gu cu cua he-thong\ndong 2\n")
        self.assertTrue(pm.duong_dan_ghim("he-thong").is_file())


class CapNhatTest(Base):
    def setUp(self):
        super().setUp()
        pm.ghim_tat_ca()
        (self.code / "prompt" / "_ghi-chu-cap-nhat.json").write_text(
            json.dumps({"hoc-canh": {"1.0.5": "chua dung", "1.1.0": "Doi vi A", "9.0.0": "tuong lai"}}), encoding="utf-8")
        self.phat_hanh("hoc-canh", "gu cu cua hoc-canh\ndong 2 doi\ndong 3 them\n", "1.1.0")

    def test_phat_hien_diff_va_ghi_chu(self):
        r = pm.chi_tiet_cap_nhat("hoc-canh")
        self.assertTrue(r["co"]); self.assertFalse(r["co_ban_sua"])
        kinds = [k for k, _ in r["diff_moi"]]
        self.assertIn("-", kinds); self.assertIn("+", kinds)
        self.assertEqual([g["ver"] for g in r["ghi_chu"]], ["1.0.5", "1.1.0"])     # > bản ghim (1.0.0), <= bản hiện tại (không có 9.0.0)

    def test_ap_dung_khi_chua_sua(self):
        pm.ap_dung_ban_moi("hoc-canh")
        self.assertEqual(pm.doc("hoc-canh"), (pm.mac_dinh("hoc-canh"), False))
        self.assertFalse(pm.co_ban_moi("hoc-canh"))
        self.assertEqual(pm.ver_ghim("hoc-canh"), "1.1.0")
        cu = pm.ds_ban_cu("hoc-canh")
        self.assertEqual(len(cu), 1); self.assertIn("gu cu cua", cu[0]["text"])     # bản cũ được cất lại

    def test_ap_dung_khi_da_sua_thay_ban_sua_va_sao_luu(self):
        pm.luu("hoc-canh", "ban toi chinh")
        self.assertTrue(pm.chi_tiet_cap_nhat("hoc-canh")["co_ban_sua"])
        self.assertEqual(pm.chi_tiet_cap_nhat("hoc-canh")["ban_sua"], "ban toi chinh")
        pm.ap_dung_ban_moi("hoc-canh")
        self.assertEqual(pm.doc("hoc-canh"), (pm.mac_dinh("hoc-canh"), False))
        self.assertFalse(pm.duong_dan_sua("hoc-canh").exists())
        self.assertTrue(any(x["text"] == "ban toi chinh" for x in pm.ds_ban_cu("hoc-canh")))

    def test_giu_ban_cua_toi_khi_da_sua(self):
        pm.luu("hoc-canh", "ban toi chinh")
        pm.giu_ban_cua_toi("hoc-canh")
        self.assertEqual(pm.doc("hoc-canh"), ("ban toi chinh", True))
        self.assertFalse(pm.co_ban_moi("hoc-canh"))               # thôi nhắc
        self.assertEqual(pm.goc("hoc-canh"), pm.mac_dinh("hoc-canh"))

    def test_giu_ban_cua_toi_khi_chua_sua_thi_chu_khong_doi(self):
        truoc = pm.doc("hoc-canh")[0]
        pm.giu_ban_cua_toi("hoc-canh")
        self.assertEqual(pm.doc("hoc-canh")[0], truoc)
        self.assertFalse(pm.co_ban_moi("hoc-canh"))
        # bản mới hơn nữa lại nhắc lại
        self.phat_hanh("hoc-canh", "lai doi\n", "1.2.0")
        self.assertTrue(pm.co_ban_moi("hoc-canh"))
        self.assertEqual(pm.doc("hoc-canh")[0], truoc)

    def test_luu_trung_ban_moi_la_chap_nhan_ban_moi(self):
        pm.luu("hoc-canh", pm.mac_dinh("hoc-canh"))
        self.assertFalse(pm.co_ban_moi("hoc-canh")); self.assertFalse(pm.duong_dan_sua("hoc-canh").exists())

    def test_khoi_phuc_ve_ban_moi_nhat_va_cat_ban_cu(self):
        pm.khoi_phuc("hoc-canh")
        self.assertEqual(pm.doc("hoc-canh"), (pm.mac_dinh("hoc-canh"), False))
        self.assertEqual(len(pm.ds_ban_cu("hoc-canh")), 1)

    def test_ghi_chu_loc_theo_khoang_phien_ban(self):
        self.assertEqual([g["ver"] for g in pm.ghi_chu("hoc-canh")], ["1.0.5", "1.1.0"])


class DiffTest(unittest.TestCase):
    def test_gap_doan_giong(self):
        a = "\n".join(f"d{i}" for i in range(30)); b = a.replace("d15", "X15")
        r = pm.diff_dong(a, b)
        self.assertIn(["-", "d15"], r); self.assertIn(["+", "X15"], r)
        self.assertTrue(any(k == "…" for k, _ in r)); self.assertLess(len(r), 15)


class TuongThichDeBaiCuTest(Base):
    def test_thieu_cho_dien_bat_buoc_van_nhan_du_lieu(self):
        pm.luu("hoc-canh", "Lam di.")        # bản cũ không có {{ds_video}} {{quy_tac}}
        out = pm.dien("hoc-canh", so_video=1, boi_canh="BC", ds_video="1. video A", quy_tac="QT123")
        self.assertIn("1. video A", out); self.assertIn("QT123", out)

    def test_hop_dong_an_toan_tu_gan_neu_thieu_khong_gan_neu_da_co(self):
        pm.luu("hoc-canh", "Lam di {{ds_video}} {{quy_tac}}")
        out = pm.dien("hoc-canh", so_video=1, boi_canh="", ds_video="v", quy_tac="q")
        self.assertIn("KHÔNG chạy lệnh terminal", out); self.assertIn("chỉ chứa JSON thuần", out)
        pm.luu("hoc-canh", "KHÔNG chạy lệnh terminal. chỉ JSON thuần {{ds_video}} {{quy_tac}}")
        out = pm.dien("hoc-canh", so_video=1, boi_canh="", ds_video="v", quy_tac="q")
        self.assertEqual(out.count("KHÔNG chạy lệnh terminal"), 1); self.assertEqual(out.count("JSON thuần"), 1)

    def test_dinh_dang_json_cua_cac_vai_tu_gan(self):
        for k, token in (("giam-khao", '"diem"'), ("doc-nhan", '"su_that"'), ("soat-kho", '"chu_muc"'), ("dao-dien", '"doan"'), ("bien-kich", '"y_canh"')):
            pm.luu(k, "de bai cu khong co dinh dang")
            ctx = {b: "v" for b in pm.VAI[k]["bien"]}
            self.assertIn(token, pm.dien(k, **ctx), k)

    def test_gom_bai_hoc_doc_duoc_bo_cuc_cu(self):
        r = ekip.tach_chung_rieng("**CHUNG:**\n* Tránh A\n• Luôn B\n– Tránh C\n\n## Riêng\n- x\n\nChung tay làm gì đó\n")
        self.assertEqual(len(r["CHUNG"]), 3); self.assertEqual(r["RIENG"], ["- x"])
        r = ekip.tach_chung_rieng("CHUNG:\n- a\n- b\n- c\nRIENG:\n- d")
        self.assertEqual((len(r["CHUNG"]), len(r["RIENG"])), (3, 1))

    def test_hoc_canh_doc_duoc_tai_lieu_mo_ta_cu_khong_co_moc(self):
        import hoc_canh
        pm.luu("mo-ta-gemini", "Tài liệu cũ không có mốc gì cả.")
        c = hoc_canh.ctx_loi_nhac([{"rel": "a.mp4", "dai": 3.0, "src": "C:\\a.mp4", "ra": "C:\\a.json"}])
        self.assertEqual(c["boi_canh"], ""); self.assertIn("Tài liệu cũ", c["quy_tac"])


class MaNguonTest(unittest.TestCase):
    """Bản thật trong repo: bảo vệ nhà phát triển đổi gu mà quên ghi chú."""
    def test_moi_gu_doi_so_voi_ban_phat_hanh_phai_co_ghi_chu(self):
        man = json.loads((THUC / "prompt" / "_ban-phat-hanh.json").read_text(encoding="utf-8"))
        notes = json.loads((THUC / "prompt" / "_ghi-chu-cap-nhat.json").read_text(encoding="utf-8"))
        nen = "1.2.4"
        self.assertEqual(set(man), set(pm.VAI))
        for k, v in pm.VAI.items():
            f = THUC / v["file"] if v["file"].startswith("luat/") else THUC / "prompt" / v["file"]
            h = pm.bam(f.read_text(encoding="utf-8-sig"))
            self.assertEqual(h, man[k]["hash"], f"{k}: đã đổi gu mặc định — thêm ghi chú rồi chạy: python engine/prompt_mau.py ghi-manifest")
            if pm._vt(man[k]["ver"]) > pm._vt(nen):
                self.assertTrue((notes.get(k) or {}).get(man[k]["ver"]), f"{k}: thiếu ghi chú cho bản {man[k]['ver']}")


if __name__ == "__main__":
    unittest.main()

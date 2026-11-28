"""28/11 tiết kiệm token: đạo diễn biết khung "chữ theo lời" (bỏ phần thẻ chữ), biên kịch tự sửa lỗi vặt thay vì loại bài, chọn tài khoản dùng nốt phiên đang mở."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]


class TietKiemTokenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["XUONG_DATA"] = cls.tmp.name
        p = str(GOC / "engine")
        if p not in sys.path:
            sys.path.insert(0, p)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_de_dao_dien_chu_theo_loi_bo_phan_chu(self):
        import dao_dien as dd
        ctx = {"khoi_mo_ta": "MENU-KHOI", "data_spec": "SPEC"}
        thuong = dd.de_dao_dien(ctx, "the_do_hoa")
        self.assertIn("Người xem ÍT ĐỌC phụ đề", thuong)
        self.assertIn("MENU-KHOI", thuong)
        ctx2 = dict(ctx, khoi_mo_ta=dd.KHOI_CHU_THEO_LOI, data_spec="")
        loi = dd.de_dao_dien(ctx2, "chu_theo_loi")
        self.assertNotIn("Người xem ÍT ĐỌC phụ đề", loi)
        self.assertNotIn("MENU-KHOI", loi)
        self.assertIn('"khoi": []', loi)
        self.assertIn("BỐ CỤC", loi)                       # phần khác của mẫu còn nguyên
        self.assertIn("ÂM THANH", loi)
        self.assertLess(len(loi), len(thuong))

    def test_dong_ds_aff_gon(self):
        import dao_dien as dd
        self.assertIn("AFF (sau vai trò) =", dd.COT_DS)
        s = {"id": "1", "kieu": 2, "vai_tro": ["chai_ro"], "mo_ta": "x", "soat": {"mat": 2, "dep": 3}, "dai": 3.0}
        self.assertIn("chai_ro | AFF |", dd.dong_ds("1", s))

    def test_bien_kich_tu_sua_loi_vat(self):
        import viet_loi as vl
        self.assertEqual(vl.bo_tieng_goi_dau("[curious] Các bác ơi, lá vàng rụng hết cả vườn rồi."), "[curious] Lá vàng rụng hết cả vườn rồi.")
        self.assertEqual(vl.bo_tieng_goi_dau("Bà con trồng sầu riêng hay bị vàng lá."), "Bà con trồng sầu riêng hay bị vàng lá.")   # chủ ngữ, không phải tiếng gọi
        self.assertEqual(vl.bot_ba_cham("A… b… c… D… e"), "A… b… c, d, e")
        self.assertEqual(vl.bot_ba_cham("A… b"), "A… b")
        it = {"text": "[curious] Cây chết khô vì nấm."}
        vl.check(it, {"ten_goi": "X"}, set())
        self.assertNotIn("chết", it["text"])

    def test_chon_tai_khoan_dung_not_phien_dang_mo(self):
        import ai
        now = time.time()
        ds = [{"ma": "tk1", "ten": "1", "thu_muc": None}, {"ma": "tk2", "ten": "2", "thu_muc": None}, {"ma": "tk3", "ten": "3", "thu_muc": None}]
        st = {"tk1": {"five_hour": {"pct": 0.0, "reset": None}, "seven_day": {"pct": 0.05, "reset": now + 9e5}},
              "tk2": {"five_hour": {"pct": 0.60, "reset": now + 1200}, "seven_day": {"pct": 0.5, "reset": now + 9e5}},
              "tk3": {"five_hour": {"pct": 0.30, "reset": now + 9000}, "seven_day": {"pct": 0.2, "reset": now + 9e5}}}
        goc = ai.ds_tai_khoan, ai.doc_trang_thai, ai.cfg
        ai.ds_tai_khoan, ai.doc_trang_thai, ai.cfg = (lambda: ds), (lambda: st), (lambda: {"tai_khoan_dung": "tu_dong"})
        try:
            self.assertEqual(ai.chon_tai_khoan()["ma"], "tk2")            # phiên sắp làm mới nhất dùng trước
            st["tk2"]["five_hour"]["pct"] = 0.95                           # gần hết → sang phiên đang mở kế tiếp
            self.assertEqual(ai.chon_tai_khoan()["ma"], "tk3")
            st["tk3"]["five_hour"]["reset"] = now - 10                     # tk3 đã làm mới → coi như chưa mở; còn tk1 (tuần ít hơn)
            self.assertEqual(ai.chon_tai_khoan()["ma"], "tk1")
        finally:
            ai.ds_tai_khoan, ai.doc_trang_thai, ai.cfg = goc


if __name__ == "__main__":
    unittest.main()

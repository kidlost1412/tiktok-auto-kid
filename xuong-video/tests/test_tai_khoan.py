"""Bỏ tài khoản Claude rồi thêm mới phải ra thư mục đăng nhập TRỐNG (không dùng lại phiên của tài khoản cũ)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]


class TaiKhoanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["XUONG_DATA"] = cls.tmp.name
        for p in (str(GOC / "app"), str(GOC / "engine")):
            if p not in sys.path:
                sys.path.insert(0, p)
        import server  # noqa: E402
        cls.s = server

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bo_roi_them_ra_thu_muc_moi(self):
        s = self.s
        a = s.tai_khoan_them("A")["ma"]
        b = s.tai_khoan_them("B")["ma"]
        thu_muc_b = Path(next(t for t in s.cfg()["tai_khoan"] if t["ma"] == b)["thu_muc"])
        (thu_muc_b / ".credentials.json").write_text("{}", encoding="utf-8")   # giả lập đã đăng nhập
        import ai
        ai._ghi_trang_thai(b, dang_nhap=True, het_den=9999999999)
        s.luu_cfg({**s.cfg(), "tai_khoan_dung": b})

        self.assertTrue(s.tai_khoan_bo(b)["ok"])
        c = s.cfg()
        self.assertNotIn(b, [t["ma"] for t in c["tai_khoan"]])
        self.assertEqual(c["tai_khoan_dung"], "tu_dong")
        self.assertNotIn(b, ai.doc_trang_thai())
        self.assertFalse(thu_muc_b.exists())
        self.assertTrue(any((s.HUB / "tai-khoan" / "_da-bo").glob(f"{b}-*")))   # cất đi, không xoá

        moi = s.tai_khoan_them("C")["ma"]
        thu_muc_moi = Path(next(t for t in s.cfg()["tai_khoan"] if t["ma"] == moi)["thu_muc"])
        self.assertFalse((thu_muc_moi / ".credentials.json").exists())
        self.assertNotIn(moi, ai.doc_trang_thai())
        self.assertNotEqual(moi, a)

    def test_goi_bi_to_chuc_tat_quyen_thi_chuyen_tai_khoan(self):
        import subprocess
        import ai
        s = self.s
        a = s.tai_khoan_them("Chan")["ma"]
        b = s.tai_khoan_them("Tot")["ma"]
        c = s.cfg(); c["tai_khoan"] = [t for t in c["tai_khoan"] if t["ma"] in (a, b)]; c["tai_khoan_dung"] = "tu_dong"; s.luu_cfg(c)
        da_goi = []

        def gia(tk, *a_, **k):
            da_goi.append(tk["ma"])
            if tk["ma"] == a:
                loi = "Your organization has disabled Claude subscription access for Claude Code · ask your admin to enable access"
                return subprocess.CompletedProcess([], 1, "", ""), {"result": loi, "is_error": True}, None
            return subprocess.CompletedProcess([], 0, "", ""), {"result": "OK", "usage": {}}, None

        goc, goc_chon = ai._goi_1, ai.chon_tai_khoan
        ai._goi_1 = gia
        ai.chon_tai_khoan = lambda bo_qua=(): next((t for t in ai.ds_tai_khoan() if t["ma"] not in bo_qua
                                                     and not ai.doc_trang_thai().get(t["ma"], {}).get("bi_chan")), None)
        try:
            self.assertEqual(ai.goi("thử", "x")[0], "OK")
        finally:
            ai._goi_1, ai.chon_tai_khoan = goc, goc_chon
        self.assertEqual(da_goi, [a, b])
        self.assertTrue(ai.doc_trang_thai()[a]["bi_chan"])
        self.assertEqual(ai.chon_tai_khoan()["ma"], b)          # lần sau bỏ qua tài khoản bị chặn

    def test_khong_bo_tai_khoan_cuoi(self):
        s = self.s
        c = s.cfg(); c["tai_khoan"] = c["tai_khoan"][:1]; s.luu_cfg(c)
        self.assertFalse(s.tai_khoan_bo(c["tai_khoan"][0]["ma"])["ok"])
        self.assertFalse(s.tai_khoan_bo("khong-co")["ok"])


if __name__ == "__main__":
    unittest.main()

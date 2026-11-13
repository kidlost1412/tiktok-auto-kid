"""Chống sự cố vận hành: ghi file nguyên tử, không hạ 'da_dang', tự duyệt không đè ✅/❌ tay, DỪNG tạm dừng tự động,
lô lỗi nghỉ lùi dần, khoá cũ (PID bị cấp lại), dọn file .part.mp4 sót."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

GOC = Path(__file__).resolve().parents[1]
_tmp = tempfile.TemporaryDirectory()
os.environ.setdefault("XUONG_DATA", _tmp.name)
for _p in (str(GOC / "app"), str(GOC / "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import duong_dan  # noqa: E402
import cong_trypost  # noqa: E402
import duyet  # noqa: E402
import tu_dong  # noqa: E402
import don_dep  # noqa: E402


class _Dung(BaseException):
    """Ngắt vòng _vong sau đúng một lượt (thay cho time.sleep)."""


class AnToanTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = Path(self.t.name)
        (self.d / "lich-su").mkdir()

    def tearDown(self):
        self.t.cleanup()

    def test_ghi_json_nguyen_tu(self):
        f = self.d / "a" / "x.json"
        duong_dan.ghi_json(f, {"a": "é"}, indent=1)
        duong_dan.ghi_json(f, {"a": "ê"}, indent=1)
        self.assertEqual(json.loads(f.read_text(encoding="utf-8")), {"a": "ê"})
        self.assertEqual([p.name for p in f.parent.iterdir()], ["x.json"])      # không sót file tạm

    def test_khong_ha_da_dang_xuong_loi(self):
        with mock.patch.object(cong_trypost, "LS", self.d / "lich-su"):
            cong_trypost._ghi_trang_thai("v1", {"trang_thai": "da_dang", "kenh": "k"})
            self.assertFalse(cong_trypost._ghi_trang_thai("v1", {"trang_thai": "loi", "ly_do": "x"}))
            self.assertEqual(cong_trypost.trang_thai_dang()["v1"]["trang_thai"], "da_dang")
            self.assertTrue(cong_trypost._ghi_trang_thai("v2", {"trang_thai": "loi"}))
            self.assertTrue(cong_trypost._ghi_trang_thai("v2", {"trang_thai": "da_dang"}))   # loi -> da_dang vẫn được

    def test_tu_duyet_khong_de_quyet_dinh_tay(self):
        ra = self.d / "ra" / "2026-01-01"; (ra / "_kem").mkdir(parents=True)
        for ten in ("a.mp4", "b.mp4"):
            (ra / ten).write_bytes(b"x")
            (ra / "_kem" / (ten[:-4] + ".json")).write_text(json.dumps({"diem": 9}), encoding="utf-8")
        (ra / "c.part.mp4").write_bytes(b"x")
        cfg = {"tu_duyet": {"bat": True, "dat_tu": 7}, "duong_dan": {"ra": str(self.d / "ra")}}
        f = self.d / "lich-su" / "danh-gia.json"
        goc_kem = duyet.kem

        def kem_gia(v, ext, *a, **k):          # giả lập anh bấm ❌ video a NGAY GIỮA lúc tự duyệt đang quét
            if v.name == "b.mp4" and not f.exists():
                f.write_text(json.dumps({"a.mp4": {"ket_qua": "bo", "gop_y": "tay"}}), encoding="utf-8")
            return goc_kem(v, ext, *a, **k)
        with mock.patch.object(duyet, "cfg_hub", lambda: cfg), mock.patch.object(duyet, "HUB", self.d), mock.patch.object(duyet, "kem", kem_gia):
            n = duyet.tu_duyet(lambda *_: None)
        dg = json.loads(f.read_text(encoding="utf-8"))
        self.assertEqual(dg["a.mp4"]["ket_qua"], "bo")                  # quyết định tay thắng
        self.assertEqual(dg["b.mp4"]["ket_qua"], "dat")
        self.assertNotIn("c.part.mp4", dg)
        self.assertEqual(n, 1)

    def test_pid_la_lo_sx(self):
        self.assertTrue(duong_dan.pid_la_lo_sx(1, ten="python.exe"))
        self.assertTrue(duong_dan.pid_la_lo_sx(1, ten="Pythonw.exe"))
        self.assertFalse(duong_dan.pid_la_lo_sx(1, ten="chrome.exe"))        # PID bị cấp lại cho app khác = khoá cũ
        self.assertFalse(duong_dan.pid_la_lo_sx(1, ten=""))

    def _mot_luot(self, c, ma_thoat=None, vua_chay=None):
        goi = []
        tu_dong.TRANG_THAI.update(nghi_den=None, ly_do_nghi=None, vua_chay=vua_chay)
        def chay(ma, n):
            goi.append((ma, n)); return {"ok": True}
        def ngu(_):
            raise _Dung()
        with mock.patch.object(tu_dong, "cfg", lambda: c), mock.patch.object(tu_dong, "LS", self.d / "lich-su"), \
             mock.patch.object(tu_dong, "F_NGHI", self.d / "lich-su" / "tu-dong-nghi.json"), \
             mock.patch.object(tu_dong, "san_sang", lambda ma: True), mock.patch.object(tu_dong, "dem", lambda ma: (0, 0)), \
             mock.patch.object(tu_dong.time, "sleep", ngu):
            try:
                tu_dong._vong(lambda: False, chay, self.d / "lich-su" / "nhat-ky.txt", ma_thoat)
            except _Dung:
                pass
        return goi

    CFG = {"tu_dong": {"bat": True, "san_pham": {"sp": {"bat": True}}}}

    def test_dung_thi_tu_dong_nghi(self):
        with mock.patch.object(tu_dong, "cfg", lambda: self.CFG), mock.patch.object(tu_dong, "F_NGHI", self.d / "lich-su" / "tu-dong-nghi.json"):
            tu_dong.TRANG_THAI.update(nghi_den=None)
            tu_dong.khi_bam_dung()
            self.assertGreater(tu_dong.TRANG_THAI["nghi_den"].timestamp(), time.time() + 3600)
            self.assertIn("DỪNG", tu_dong.TRANG_THAI["ly_do_nghi"])
        with mock.patch.object(tu_dong, "F_NGHI", self.d / "lich-su" / "tu-dong-nghi.json"):
            self.assertTrue(json.loads((self.d / "lich-su" / "tu-dong-nghi.json").read_text(encoding="utf-8"))["nghi_den"] > time.time())
            # vòng tự động: còn nghỉ → không bật lô mới
            goi = []
            tu_dong.TRANG_THAI.update(nghi_den=None)           # giả lập app khởi động lại: nạp giờ nghỉ từ file
        goi = self._mot_luot_giu_nghi()
        self.assertEqual(goi, [])
        self.assertIn("nghỉ tới", tu_dong.TRANG_THAI["ghi"])

    def _mot_luot_giu_nghi(self):
        goi = []
        def ngu(_):
            raise _Dung()
        with mock.patch.object(tu_dong, "cfg", lambda: self.CFG), mock.patch.object(tu_dong, "LS", self.d / "lich-su"), \
             mock.patch.object(tu_dong, "F_NGHI", self.d / "lich-su" / "tu-dong-nghi.json"), \
             mock.patch.object(tu_dong, "san_sang", lambda ma: True), mock.patch.object(tu_dong, "dem", lambda ma: (0, 0)), \
             mock.patch.object(tu_dong.time, "sleep", ngu):
            try:
                tu_dong._vong(lambda: False, lambda ma, n: goi.append(ma) or {"ok": True}, self.d / "lich-su" / "nhat-ky.txt")
            except _Dung:
                pass
        return goi

    def test_lo_loi_nghi_lui_dan(self):
        f = self.d / "lich-su" / "tu-dong-nghi.json"
        for ky_vong in (10, 30, 60, 60):
            goi = self._mot_luot(self.CFG, ma_thoat=lambda: 1, vua_chay="sp")
            self.assertEqual(goi, [])
            con = (tu_dong.TRANG_THAI["nghi_den"].timestamp() - time.time()) / 60
            self.assertAlmostEqual(con, ky_vong, delta=1)
            f2 = json.loads(f.read_text(encoding="utf-8"))
            f2["nghi_den"] = None; f.write_text(json.dumps(f2), encoding="utf-8")        # hết giờ nghỉ → lô lỗi tiếp theo
        self.assertEqual(json.loads(f.read_text(encoding="utf-8"))["loi_lien_tiep"], 4)

    def test_tran_lo_moi_ngay(self):
        import datetime
        f = self.d / "lich-su" / "tu-dong-nghi.json"
        f.write_text(json.dumps({"ngay": datetime.date.today().isoformat(), "so_lo": 3}), encoding="utf-8")
        c = {"tu_dong": {"bat": True, "toi_da_lo_ngay": 3, "san_pham": {"sp": {"bat": True}}}}
        self.assertEqual(self._mot_luot(c), [])
        self.assertIn("đủ 3 lô", tu_dong.TRANG_THAI["ghi"])
        c["tu_dong"]["toi_da_lo_ngay"] = 4
        self.assertEqual(len(self._mot_luot(c)), 1)                  # dưới trần → chạy, và đếm thêm 1
        self.assertEqual(json.loads(f.read_text(encoding="utf-8"))["so_lo"], 4)

    def test_don_dep_file_part_cu(self):
        ra = self.d / "ra"; ngay = ra / "2026-01-01"; ngay.mkdir(parents=True)
        cu, moi, xong = ngay / "x.part.mp4", ngay / "y.part.mp4", ngay / "z.mp4"
        sach = ngay / "x.part.__sach.mp4"
        for p in (cu, moi, xong, sach):
            p.write_bytes(b"12")
        xua = time.time() - 7200
        os.utime(cu, (xua, xua)); os.utime(sach, (xua, xua)); os.utime(xong, (xua, xua))
        with mock.patch.object(don_dep, "_ra", lambda: ra), mock.patch.object(don_dep, "HUB", self.d):
            don_dep.don(lambda *_: None)
        self.assertFalse(cu.exists()); self.assertFalse(sach.exists())
        self.assertTrue(moi.exists()); self.assertTrue(xong.exists())


if __name__ == "__main__":
    unittest.main()

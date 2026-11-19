"""Cải tiến hub: sổ gu không ghi trùng, đệm token/sản phẩm theo file, /api/video phân trang, /api/ngay có số video, đọc đuôi lo.jsonl."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]


class UxHubTest(unittest.TestCase):
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

    def _so_gu(self):
        f = self.s.LS / "so-gu.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""

    # ---- danh_gia: không ghi trùng sổ gu ----
    def test_danh_gia_khong_ghi_trung_so_gu(self):
        s = self.s
        s.LS.mkdir(parents=True, exist_ok=True)
        f = s.LS / "so-gu.md"
        if f.exists():
            f.unlink()
        body = {"file": "tc01_goc_dd_trung.mp4", "ket_qua": "kem", "gop_y": "mở đầu chậm"}
        s.danh_gia(dict(body))
        s.danh_gia(dict(body))
        s.danh_gia(dict(body))
        self.assertEqual(self._so_gu().count("mở đầu chậm"), 1)
        # đổi góp ý → ghi dòng mới
        s.danh_gia(dict(body, gop_y="mở đầu chậm, nhạc to"))
        self.assertEqual(self._so_gu().count("mở đầu chậm"), 2)
        # đổi kết quả (cùng góp ý) → ghi dòng mới
        s.danh_gia({"file": "tc01_goc_dd_trung.mp4", "ket_qua": "dat", "gop_y": "mở đầu chậm, nhạc to"})
        self.assertEqual(self._so_gu().count("nhạc to"), 2)
        self.assertEqual(s.doc_danh_gia()["tc01_goc_dd_trung.mp4"]["ket_qua"], "dat")

    def test_danh_gia_kem_khong_gop_y_khong_trung(self):
        s = self.s
        f = s.LS / "so-gu.md"
        if f.exists():
            f.unlink()
        b = {"file": "tc02_goc_dd_x.mp4", "ket_qua": "kem", "gop_y": ""}
        s.danh_gia(dict(b)); s.danh_gia(dict(b))
        self.assertEqual(self._so_gu().count("tc02"), 1)

    # ---- đệm token_hom_nay ----
    def test_token_hom_nay_dem_va_vo_hieu(self):
        s = self.s
        import datetime
        hn = s.ra_dir() / datetime.date.today().isoformat()
        hn.mkdir(parents=True, exist_ok=True)
        (s.LS / "moc-dem.txt").unlink(missing_ok=True)
        for x in hn.glob("*.mp4"):
            x.unlink()
        s._TOKEN_HN["k"] = None
        a = s.token_hom_nay()
        self.assertEqual(a["video"], 0)
        calls = []
        goc = s._token_hom_nay_tinh
        s._token_hom_nay_tinh = lambda m: (calls.append(1), goc(m))[1]
        try:
            s.token_hom_nay(); s.token_hom_nay()
            self.assertEqual(len(calls), 0)               # không đổi gì → dùng đệm
            (hn / "v1.mp4").write_bytes(b"x")
            os.utime(hn, None)
            b = s.token_hom_nay()
            self.assertEqual(len(calls), 1)               # có video mới → tính lại
            self.assertEqual(b["video"], 1)
            tk = s.LS / "token.csv"
            tk.write_text("luc,video,vao,vao_cache_tao,vao_cache_doc,ra,usd_uoc\n"
                          f"{datetime.datetime.now().isoformat()},x,10,0,0,5,0.5\n", encoding="utf-8")
            c = s.token_hom_nay()
            self.assertEqual(len(calls), 2)               # token.csv đổi → tính lại
            self.assertEqual(c["token"], 15)
        finally:
            s._token_hom_nay_tinh = goc

    # ---- đệm san_pham_ds ----
    def test_san_pham_ds_dem_va_vo_hieu(self):
        s = self.s
        d = s.HUB / "san-pham" / "t-sp1"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "san-pham.json"
        f.write_text(json.dumps({"ten_goi": "SP một", "su_that_duoc_noi": ["a"], "qua_tang": "q"}), encoding="utf-8")
        s._SP_DS["k"] = None
        goc = s._san_pham_ds_tinh
        calls = []
        s._san_pham_ds_tinh = lambda: (calls.append(1), goc())[1]
        try:
            a = s.san_pham_ds()
            self.assertEqual(len(calls), 1)
            self.assertTrue(any(x["ma"] == "t-sp1" for x in a))
            a[0]["ten"] = "bị sửa ngoài"                  # sửa bản trả về không làm hỏng đệm
            b = s.san_pham_ds()
            self.assertEqual(len(calls), 1)
            self.assertNotEqual(b[0]["ten"], "bị sửa ngoài")
            time.sleep(0.02)
            f.write_text(json.dumps({"ten_goi": "SP một mới", "su_that_duoc_noi": ["a"], "qua_tang": "q", "ten_ngan": "Một"}), encoding="utf-8")
            c = s.san_pham_ds()
            self.assertEqual(len(calls), 2)
            self.assertEqual(next(x for x in c if x["ma"] == "t-sp1")["ten"], "SP một mới")
            (d / "canh.json").write_text("[{}, {}]", encoding="utf-8")
            e = s.san_pham_ds()
            self.assertEqual(len(calls), 3)
            self.assertEqual(next(x for x in e if x["ma"] == "t-sp1")["so_canh"], 2)
        finally:
            s._san_pham_ds_tinh = goc

    # ---- /api/video phân trang + /api/ngay ----
    def _tao_video(self, ngay, ten, mtime):
        d = self.s.ra_dir() / ngay
        d.mkdir(parents=True, exist_ok=True)
        f = d / ten
        f.write_bytes(b"x")
        os.utime(f, (mtime, mtime))

    def test_video_phan_trang(self):
        s = self.s
        for x in s.ra_dir().glob("*"):
            if x.is_dir():
                for y in x.glob("*"):
                    y.unlink()
        base = time.time() - 100000
        for i in range(5):
            self._tao_video("2026-10-01", f"a{i}.mp4", base + i)
        for i in range(4):
            self._tao_video("2026-10-02", f"b{i}.mp4", base + 1000 + i)
        self._tao_video("2026-10-02", "c.part.mp4", base)
        ds = s.video_ngay("tat-ca")                      # không gioi_han → danh sách đầy đủ như cũ
        self.assertIsInstance(ds, list)
        self.assertEqual(len(ds), 9)
        r = s.video_ngay("tat-ca", 4, 0)
        self.assertEqual(len(r["ds"]), 4)
        self.assertTrue(r["con_nua"])
        self.assertTrue(all(v["ngay"] == "2026-10-02" for v in r["ds"]))
        r2 = s.video_ngay("tat-ca", 4, 4)
        self.assertEqual([v["file"] for v in r2["ds"]][0][0], "a")
        self.assertTrue(r2["con_nua"])
        r3 = s.video_ngay("tat-ca", 4, 8)
        self.assertEqual(len(r3["ds"]), 1)
        self.assertFalse(r3["con_nua"])
        self.assertEqual(s.video_ngay("2026-10-01", 3, 0)["con_nua"], True)
        self.assertEqual(s.video_ngay("khong-hop-le", 3, 0), {"ds": [], "con_nua": False})

    def test_ngay_dem(self):
        s = self.s
        for x in s.ra_dir().glob("*"):
            if x.is_dir():
                for y in x.glob("*"):
                    y.unlink()
        self._tao_video("2026-10-05", "a.mp4", time.time())
        self._tao_video("2026-10-05", "b.mp4", time.time())
        self._tao_video("2026-10-05", "b.part.mp4", time.time())
        self._tao_video("2026-10-06", "z.part.mp4", time.time())
        r = {x["ngay"]: x["so"] for x in s.ngay_dem()}
        self.assertEqual(r["2026-10-05"], 2)
        self.assertEqual(r["2026-10-06"], 0)
        self.assertIn("2026-10-06", s._ds_ngay())

    # ---- ds_lo chỉ đọc đuôi ----
    def test_ds_lo_doc_duoi(self):
        s = self.s
        s.LS.mkdir(parents=True, exist_ok=True)
        f = s.LS / "lo.jsonl"
        f.write_text("".join(json.dumps({"i": i, "t": "ệ" * 50}, ensure_ascii=False) + "\n" for i in range(3000)), encoding="utf-8")
        r = s.ds_lo(30)
        self.assertEqual([x["i"] for x in r], list(range(2999, 2969, -1)))
        f.write_text('{"i": 1}\n{"i": 2}\n', encoding="utf-8")
        self.assertEqual([x["i"] for x in s.ds_lo(30)], [2, 1])
        self.assertEqual(s._doc_duoi(f, 0), [])


if __name__ == "__main__":
    unittest.main()

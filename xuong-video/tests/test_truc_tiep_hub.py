"""Phía hub của "việc trực tiếp": GET /api/truc-tiep (CORS như /api/luong), trường `tt` trong ảnh chụp luồng, luồng SSE canh thư mục truc-tiep/
và không phát nhanh hơn ~1 lần/giây."""
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
for p in (str(GOC / "app"), str(GOC / "engine")):
    if p not in sys.path:
        sys.path.insert(0, p)

import luong  # noqa: E402
import truc_tiep as T  # noqa: E402


def cho_den(dk, giay=8.0):
    het = time.time() + giay
    while time.time() < het:
        if dk():
            return True
        time.sleep(0.05)
    return dk()


_SEQ = [0]


def viet_viec(thu, ten, cap_nhat, **kw):
    x = {"id": ten, "nguon": "hub", "vai": "bien-kich", "viec": "Đang viết lời đọc", "bat_dau": cap_nhat - 5, "cap_nhat": cap_nhat, "xong": False,
         "ket_qua": None, "dong": ["Vườn cà phê cần phun."], "dang_go": None}
    x.update(kw)
    f = Path(thu) / f"{ten}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(x, ensure_ascii=False), encoding="utf-8")
    _SEQ[0] += 1
    t = time.time() + _SEQ[0]                    # mtime tăng chắc chắn mỗi lần ghi (độ phân giải đồng hồ file Windows thô → ghi liền nhau có thể trùng mtime)
    os.utime(f, (t, t))
    return f


class TrucTiepHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["XUONG_DATA"] = cls.tmp.name
        import server  # noqa: E402
        from http.server import ThreadingHTTPServer
        cls.s = server
        cls.cu = T._THU_MUC
        cls.thu = Path(cls.tmp.name) / "tt"
        T._THU_MUC = str(cls.thu)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        T._THU_MUC = cls.cu
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        for f in self.thu.glob("*"):
            f.unlink()
        T._don_cuoi[0] = 0.0

    def get(self, origin=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=8)
        try:
            c.request("GET", "/api/truc-tiep", headers={"Origin": origin} if origin else {})
            r = c.getresponse()
            return r, json.loads(r.read().decode("utf-8"))
        finally:
            c.close()

    def test_rong_khi_chua_co_viec(self):
        r, d = self.get()
        self.assertEqual(r.status, 200)
        self.assertIn("application/json", r.getheader("Content-Type"))
        self.assertEqual(d["ds"], [])
        self.assertLess(abs(d["bay_gio"] - time.time()), 5)

    def test_chi_viec_trong_10_phut_moi_nhat_truoc_viec_xong_giu_60s(self):
        now = time.time()
        viet_viec(self.thu, "bien-kich-aaaaaa", now - 30)
        viet_viec(self.thu, "dao-dien-bbbbbb", now - 2, vai="dao-dien", chi_tiet={"diem": 8})
        viet_viec(self.thu, "giam-khao-cccccc", now - 20, vai="giam-khao", xong=True, ket_qua="ok")
        viet_viec(self.thu, "giam-khao-dddddd", now - 120, vai="giam-khao", xong=True, ket_qua="ok")      # xong > 60 s: ẩn
        viet_viec(self.thu, "dung-eeeeee", now - 700, vai="dung")                                          # > 10 phút: ẩn
        (self.thu / "hong.json").write_text("{cụt", encoding="utf-8")
        (self.thu / "x.json.tmp").write_text("{}", encoding="utf-8")
        r, d = self.get()
        self.assertEqual([x["id"] for x in d["ds"]], ["dao-dien-bbbbbb", "giam-khao-cccccc", "bien-kich-aaaaaa"])
        self.assertEqual(d["ds"][0]["chi_tiet"], {"diem": 8})
        self.assertEqual(d["ds"][0]["dong"], ["Vườn cà phê cần phun."])

    def test_cors_giong_api_luong(self):
        r, _ = self.get("http://localhost:8010")
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "http://localhost:8010")
        self.assertEqual(r.getheader("Vary"), "Origin")
        r, _ = self.get("http://127.0.0.1:8010")
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "http://127.0.0.1:8010")
        r, _ = self.get("http://evil.example")
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))
        r, _ = self.get()
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))

    def test_viec_that_do_engine_ghi_ra_endpoint(self):
        cu = T.GIAN_CACH
        T.GIAN_CACH = 0.0
        try:
            with T.viec("bien-kich", "Đang viết lời đọc", sp="Nano Đồng") as tt:
                tt.chu('[{"text":"Vườn cà phê cần phun. Nano Đồng đây')
                _, d = self.get()
                self.assertEqual(len(d["ds"]), 1)
                x = d["ds"][0]
                self.assertEqual((x["vai"], x["nguon"], x["sp"], x["xong"]), ("bien-kich", "hub", "Nano Đồng", False))
                self.assertEqual(x["dong"], ["Vườn cà phê cần phun."])
                self.assertEqual(x["dang_go"], "Nano Đồng đây")
            _, d = self.get()
            self.assertTrue(d["ds"][0]["xong"])
        finally:
            T.GIAN_CACH = cu

    def test_snapshot_co_tt(self):
        s = self.s
        self.assertEqual(s._luong_tinh()["tt"], 0.0)
        now = time.time()
        viet_viec(self.thu, "a-1", now - 40)
        viet_viec(self.thu, "b-2", now - 3)
        viet_viec(self.thu, "c-3", now - 900)                    # quá hạn: không tính
        snap = s._luong_tinh()
        self.assertEqual(set(snap), {"n", "cho_duyet", "chay", "tt"})
        self.assertEqual(snap["tt"], now - 3)
        self.assertIsInstance(snap["tt"], float)


class LuongTrucTiepTest(unittest.TestCase):
    """Bộ phát canh thư mục lich-su/truc-tiep/ và không phát dồn hơn 1 lần/giây."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ls = Path(self.tmp.name) / "lich-su"
        self.ra = Path(self.tmp.name) / "ra"
        self.tt = self.ls / "truc-tiep"
        self.tt.mkdir(parents=True)
        self.ra.mkdir()
        self.cu = T._THU_MUC
        T._THU_MUC = str(self.tt)
        self.p = None

    def tearDown(self):
        if self.p:
            self.p.dung()
        T._THU_MUC = self.cu
        self.tmp.cleanup()

    def tinh(self):
        return {"n": 0, "tt": T.cap_nhat_toi_da()}

    def tao(self, watchdog):
        self.p = luong.Phat(self.tinh, self.ra, self.ls, dung_watchdog=watchdog)
        self.p.bat_dau()
        self.assertTrue(cho_den(lambda: self.p.hien_tai()[1] is not None))
        return self.p

    def _kich_ban(self, watchdog):
        p = self.tao(watchdog)
        v0, a0 = p.hien_tai()
        self.assertEqual(a0["tt"], 0.0)
        now = time.time()
        viet_viec(self.tt, "bien-kich-111111", now)                       # việc mới xuất hiện
        v1, a1 = p.cho(v0, 8)
        self.assertEqual(a1["tt"], now)
        (self.tt / "bien-kich-111111.json.tmp").write_text("{}", encoding="utf-8")   # file tạm: không phải gợi ý
        viet_viec(self.tt, "bien-kich-111111", now + 7)                   # việc cập nhật
        v2, a2 = p.cho(v1, 8)
        self.assertEqual(a2["tt"], now + 7)
        viet_viec(self.tt, "bien-kich-111111", now + 7, xong=True)
        (self.tt / "bien-kich-111111.json").unlink()                      # việc biến mất → tt về 0
        v3, a3 = p.cho(v2, 8)
        self.assertEqual(a3["tt"], 0.0)

    def test_canh_thu_muc_khong_watchdog(self):
        self._kich_ban(False)

    @unittest.skipUnless(luong.CO_WATCHDOG, "chưa cài watchdog")
    def test_canh_thu_muc_co_watchdog(self):
        self._kich_ban(True)

    def test_khong_phat_nhanh_hon_1_giay(self):
        hop = {"v": 0}
        p = luong.Phat(lambda: dict(hop), self.ra, self.ls, dung_watchdog=False)
        self.p = p
        p.bat_dau()
        self.assertTrue(cho_den(lambda: p.hien_tai()[1] is not None))
        gio, dung = [], threading.Event()

        def nghe():
            v = p.hien_tai()[0]
            while not dung.is_set():
                v2, anh = p.cho(v, 0.3)
                if anh is not None:
                    gio.append(time.monotonic()); v = v2
        th = threading.Thread(target=nghe, daemon=True)
        th.start()
        for i in range(1, 12):                                           # 11 thay đổi trong ~2,6 s
            hop["v"] = i
            p.goi_y()
            time.sleep(0.24)
        cho_den(lambda: len(gio) >= 3, 4)
        dung.set(); th.join(3)
        self.assertGreaterEqual(len(gio), 2)
        self.assertLessEqual(len(gio), 4)                                # không phải 11
        for a, b in zip(gio, gio[1:]):
            self.assertGreaterEqual(b - a, 0.9)
        self.assertEqual(p.hien_tai()[1]["v"], 11)                       # nhưng không bỏ rơi bản cuối

    def test_phat_dau_tien_sau_nghi_khong_bi_tre(self):
        p = self.tao(False)
        time.sleep(1.2)                                                  # nghỉ > 1 s rồi mới có việc: đẩy gần như ngay (≤ gộp 0,3 s + nhịp)
        v0 = p.hien_tai()[0]
        t0 = time.monotonic()
        viet_viec(self.tt, "dung-222222", time.time())
        p.goi_y()
        v1, a = p.cho(v0, 3)
        self.assertIsNotNone(a)
        self.assertLess(time.monotonic() - t0, 0.9)


if __name__ == "__main__":
    unittest.main()

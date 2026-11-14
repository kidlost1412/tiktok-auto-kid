"""Luồng SSE /api/luong: bộ phát (phát khi sự kiện mới / cho_duyet đổi / chạy đổi), dự phòng khi không có watchdog, giới hạn kết nối."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
if str(GOC / "app") not in sys.path:
    sys.path.insert(0, str(GOC / "app"))

import luong  # noqa: E402


def cho_den(dk, giay=6.0):
    het = time.time() + giay
    while time.time() < het:
        if dk():
            return True
        time.sleep(0.05)
    return dk()


class PhatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ls = Path(self.tmp.name) / "lich-su"
        self.ra = Path(self.tmp.name) / "ra"
        self.ls.mkdir()
        (self.ra / "2026-11-14").mkdir(parents=True)
        self.chay = False
        self.p = None

    def tearDown(self):
        if self.p:
            self.p.dung()
        self.tmp.cleanup()

    def tinh(self):
        dg = self.ls / "danh-gia.json"
        dd = json.loads(dg.read_text("utf-8")) if dg.exists() else {}
        so = sum(1 for v in self.ra.glob("*/*.mp4") if not v.name.endswith(".part.mp4") and v.name not in dd)
        return {"n": luong.n_cuoi(self.ls / "su-kien.jsonl"), "cho_duyet": so, "chay": self.chay}

    def tao(self, watchdog):
        self.p = luong.Phat(self.tinh, self.ra, self.ls, dung_watchdog=watchdog)
        self.p.bat_dau()
        self.assertTrue(cho_den(lambda: self.p.hien_tai()[1] is not None))
        return self.p

    def ghi_sk(self, n):
        with open(self.ls / "su-kien.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"n": n, "vai": "dung", "loai": "xong"}) + "\n")

    def _kich_ban(self, watchdog):
        p = self.tao(watchdog)
        v0, a0 = p.hien_tai()
        self.assertEqual(a0, {"n": 0, "cho_duyet": 0, "chay": False})
        # (a) sự kiện mới
        self.ghi_sk(5)
        v1, a1 = p.cho(v0, 8)
        self.assertEqual(a1["n"], 5)
        # (b) video mới -> cho_duyet đổi; .part.mp4 không tính
        (self.ra / "2026-11-14" / "a.part.mp4").write_bytes(b"x")
        (self.ra / "2026-11-14" / "a.mp4").write_bytes(b"x")
        self.assertTrue(cho_den(lambda: p.hien_tai()[1]["cho_duyet"] == 1, 8))
        # đánh giá xong -> 0
        (self.ls / "danh-gia.json").write_text(json.dumps({"a.mp4": {"ket_qua": "dat"}}), "utf-8")
        self.assertTrue(cho_den(lambda: p.hien_tai()[1]["cho_duyet"] == 0, 8))
        # (c) trạng thái chạy: không có file nào đổi, chỉ có nhịp dự phòng/an toàn bắt được -> báo bằng goi_y
        self.chay = True
        p.goi_y()
        self.assertTrue(cho_den(lambda: p.hien_tai()[1]["chay"] is True, 5))

    def test_phat_khong_watchdog(self):
        self._kich_ban(False)

    @unittest.skipUnless(luong.CO_WATCHDOG, "chưa cài watchdog")
    def test_phat_co_watchdog(self):
        self._kich_ban(True)

    def test_khong_phat_khi_khong_doi(self):
        p = self.tao(False)
        v0, _ = p.hien_tai()
        p.goi_y()
        time.sleep(0.8)
        self.assertEqual(p.hien_tai()[0], v0)
        v, anh = p.cho(v0, 0.2)       # hết hạn chờ -> (cũ, None) để gửi ping
        self.assertEqual((v, anh), (v0, None))

    def test_gioi_han_ket_noi(self):
        p = luong.Phat(lambda: {}, toi_da=2)
        self.assertTrue(p.vao())
        self.assertTrue(p.vao())
        self.assertFalse(p.vao())
        p.ra_khoi()
        self.assertTrue(p.vao())
        self.assertEqual(p.so_ket_noi, 2)

    def test_nhieu_nguoi_nghe_cung_nhan(self):
        p = self.tao(False)
        v0, _ = p.hien_tai()
        kq = []
        ts = [threading.Thread(target=lambda: kq.append(p.cho(v0, 8)[1])) for _ in range(3)]
        [t.start() for t in ts]
        time.sleep(0.2)
        self.ghi_sk(9)
        [t.join(10) for t in ts]
        self.assertEqual([a["n"] for a in kq], [9, 9, 9])

    def test_n_cuoi_va_khung(self):
        self.assertEqual(luong.n_cuoi(self.ls / "khong-co.jsonl"), 0)
        self.ghi_sk(3)
        (self.ls / "su-kien.jsonl").open("a").write("rác\n")
        self.assertEqual(luong.n_cuoi(self.ls / "su-kien.jsonl"), 3)
        self.assertTrue(luong.khung_sse({"n": 1}).startswith(b"event: doi\ndata: {"))


class SseHttpTest(unittest.TestCase):
    """Chạy hub thật (cổng ngẫu nhiên) và nối /api/luong bằng http.client."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["XUONG_DATA"] = cls.tmp.name
        for p in (str(GOC / "app"), str(GOC / "engine")):
            if p not in sys.path:
                sys.path.insert(0, p)
        import server  # noqa: E402
        from http.server import ThreadingHTTPServer
        cls.s = server
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        server.PHAT.dung_watchdog = False
        server.PHAT.bat_dau()

    @classmethod
    def tearDownClass(cls):
        cls.s.PHAT.dung()
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def mo(self, origin=None):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=8)
        c.request("GET", "/api/luong", headers={"Origin": origin} if origin else {})
        return c, c.getresponse()

    def test_ban_dau_va_cors(self):
        c, r = self.mo("http://localhost:8010")
        try:
            self.assertEqual(r.status, 200)
            self.assertIn("text/event-stream", r.getheader("Content-Type"))
            self.assertEqual(r.getheader("Cache-Control"), "no-cache")
            self.assertEqual(r.getheader("X-Accel-Buffering"), "no")
            self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "http://localhost:8010")
            dong = r.fp.readline().decode()
            self.assertEqual(dong.strip(), "event: doi")
            data = json.loads(r.fp.readline().decode()[6:])
            self.assertEqual(set(data), {"n", "cho_duyet", "chay"})
        finally:
            c.close()

    def test_origin_la_khong_co_cors(self):
        c, r = self.mo("http://evil.example")
        try:
            self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))
        finally:
            c.close()

    def test_het_cho_503_va_giai_phong(self):
        P = self.s.PHAT
        cu, ping = P.toi_da, luong.PING_GIAY
        luong.PING_GIAY = 1                     # ping nhanh để thread phát hiện client đã đóng
        base = P.so_ket_noi
        P.toi_da = base + 1
        try:
            import socket
            s1 = socket.create_connection(("127.0.0.1", self.port))
            s1.sendall(b"GET /api/luong HTTP/1.1\r\nHost: x\r\n\r\n")
            self.assertTrue(cho_den(lambda: P.so_ket_noi == base + 1, 5))
            c2, r2 = self.mo()
            self.assertEqual(r2.status, 503)
            r2.read()
            c2.close()
            s1.close()                      # client đóng -> thread thoát ở lần ping kế, trả chỗ
            self.assertTrue(cho_den(lambda: P.so_ket_noi == base, 10))
        finally:
            P.toi_da, luong.PING_GIAY = cu, ping


if __name__ == "__main__":
    unittest.main()

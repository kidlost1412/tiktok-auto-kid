"""Giữ chân thật từ TikTok Studio → chẩn đoán hook/thân cho biên kịch & đạo diễn (Kid 26/11)."""
import csv
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import hieu_qua  # noqa: E402


def ban_ghi(i, giu, xem=300, ma="sp1", tb=4.0, dai=20.0):
    return {"ma": ma, "cau_mo": f"câu mở {i}", "xem24": xem, "giu": giu, "xem_tb": tb, "thoi_luong": dai, "xem_het": 0.02}


class GiuChanTest(unittest.TestCase):
    def chay(self, ds, ma="sp1", cho="bien_kich"):
        db = {str(i): r for i, r in enumerate(ds)}
        with mock.patch.object(hieu_qua, "cap_nhat", lambda: db), mock.patch.object(hieu_qua, "_cai", lambda: {"bat": True, "mau_nhom": 3, "mau_tong": 6}):
            return hieu_qua.giu_chan(ma, cho)

    def test_doc_chuoi_giu(self):
        self.assertEqual(hieu_qua._giu("1 0.7 0.26 0.18"), [1.0, 0.7, 0.26, 0.18])
        self.assertEqual(hieu_qua._giu("1 0.7"), [])           # quá ngắn
        self.assertEqual(hieu_qua._giu("1 x 0.2 0.1"), [])     # có số hỏng
        self.assertEqual(hieu_qua._giu(None), [])

    def test_bo_o_3_giay_dau_la_loi_hook(self):
        ds = [ban_ghi(i, [1, 0.7, 0.26 + i / 100, 0.18 + i / 100]) for i in range(5)]
        t = self.chay(ds)
        self.assertIn("giây 3: 20%", t)
        self.assertIn("HOOK", t)
        self.assertIn('"câu mở 4" — còn 22%', t)                 # câu mở giữ tốt nhất đứng đầu
        self.assertIn("Hình đầu", self.chay(ds, cho="dao_dien"))

    def test_giu_dau_nhung_rot_o_than(self):
        ds = [ban_ghi(i, [1, 0.9, 0.8, 0.7], tb=5.0) for i in range(4)]
        t = self.chay(ds)
        self.assertNotIn("HOOK", t)
        self.assertIn("thân bài", t)

    def test_chua_du_video_hoac_view_thap_thi_rong(self):
        self.assertEqual(self.chay([ban_ghi(i, [1, 0.7, 0.2, 0.1]) for i in range(3)]), "")
        self.assertEqual(self.chay([ban_ghi(i, [1, 0.7, 0.2, 0.1], xem=40) for i in range(6)]), "")

    def test_doc_so_lieu_lay_giu_chan_ban_sau_cung(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "so-lieu.csv"
            with open(f, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh)
                w.writerow(["luc_nhan", "id", "kenh", "luot_xem_24h", "luot_xem_72h", "thich", "binh_luan", "chia_se", "don", "luc",
                            "thoi_luong_s", "xem_tb_s", "xem_het", "giu"])
                w.writerow(["", "v1", "@a", "150", "", "1", "0", "0", "", "", "20.3", "2.1", "0.01", "1 0.6 0.2 0.1"])
                w.writerow(["", "v1", "@a", "", "300", "2", "0", "0", "", "", "20.3", "2.58", "0.0167", "1 0.7 0.26 0.18"])
            with mock.patch.object(hieu_qua, "LS", Path(td)):
                d = hieu_qua._doc_so_lieu()["v1"]
        self.assertEqual(d["giu"], [1.0, 0.7, 0.26, 0.18])
        self.assertEqual((d["xem_tb"], d["thoi_luong"], d["xem24"], d["xem72"]), (2.58, 20.3, 150, 300))


class CongSoLieuTest(unittest.TestCase):
    def test_file_cu_duoc_nang_dau_cot_va_nhan_giu_chan(self):
        import json, tempfile, threading, urllib.request
        from http.server import ThreadingHTTPServer
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
        import cong_trypost
        with tempfile.TemporaryDirectory() as td:
            ls = Path(td)
            f = ls / "so-lieu.csv"
            with open(f, "w", newline="", encoding="utf-8-sig") as fh:      # đầu cột bản cũ
                csv.writer(fh).writerows([["luc_nhan", "id", "kenh", "luot_xem_24h", "luot_xem_72h", "thich", "binh_luan", "chia_se", "don", "luc"],
                                          ["t0", "v0", "@a", "50", "", "1", "0", "0", "", ""]])
            with mock.patch.object(cong_trypost, "LS", ls), mock.patch.object(cong_trypost, "cfg", lambda: {"trypost": {"khoa": "k"}}):
                srv = ThreadingHTTPServer(("127.0.0.1", 0), cong_trypost.H)
                threading.Thread(target=srv.serve_forever, daemon=True).start()
                try:
                    rq = urllib.request.Request(f"http://127.0.0.1:{srv.server_port}/trypost/so-lieu", method="POST",
                                                data=json.dumps({"id": "v1", "luot_xem_24h": 199, "xem_tb_s": 2.58, "giu": "1 0.7 0.26 0.18"}).encode(),
                                                headers={"X-Key": "k", "Content-Type": "application/json"})
                    urllib.request.urlopen(rq, timeout=10).read()
                finally:
                    srv.shutdown(); srv.server_close()
                with open(f, encoding="utf-8-sig", newline="") as fh:
                    rows = list(csv.DictReader(fh))
                self.assertEqual([r["id"] for r in rows], ["v0", "v1"])
                self.assertEqual((rows[0]["luot_xem_24h"], rows[0]["giu"]), ("50", ""))
                self.assertEqual((rows[1]["xem_tb_s"], rows[1]["giu"]), ("2.58", "1 0.7 0.26 0.18"))
                with mock.patch.object(hieu_qua, "LS", ls):
                    self.assertEqual(hieu_qua._doc_so_lieu()["v1"]["giu"], [1.0, 0.7, 0.26, 0.18])


if __name__ == "__main__":
    unittest.main()

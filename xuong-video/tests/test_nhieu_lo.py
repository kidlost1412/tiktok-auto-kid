"""Nhiều lô sản xuất chạy cùng lúc: sức máy (RAM → số lô / khe dựng), khoá lô riêng từng sản phẩm, khe dựng giữa các tiến trình,
hàng chờ bền, nhật ký + tiến độ từng lô, vòng tự động nhiều sản phẩm, chữ ký chống trùng dùng chung.
Không gọi AI / ElevenLabs / ffmpeg / node. Test tiến trình con chỉ chạy một đoạn python nhỏ có hạn chót cứng (không tự gọi lại chính nó)."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import threading
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

import don_dep  # noqa: E402
import dieu_phoi  # noqa: E402
import ekip  # noqa: E402
import suc_may  # noqa: E402
import tu_dong  # noqa: E402


class _Dung(Exception):
    pass


class ProcGia:
    """Tiến trình giả: poll() = None tới khi gọi xong()."""
    _pid = [424000]

    def __init__(self):
        ProcGia._pid[0] += 1
        self.pid = ProcGia._pid[0]; self.rc = None

    def poll(self):
        return self.rc

    def xong(self, rc=0):
        self.rc = rc


# ======================================================================== sức máy
class SucMayTest(unittest.TestCase):
    def test_toan_16_24_32_gb(self):
        # K = clamp(floor((RAM − 8) / 3), 1, 4); N = clamp(K + 1, 1, 4)
        a = suc_may.suc_may(16, 8, {})
        self.assertEqual((a["khe_dung"], a["lo_toi_da"], a["ram_gb"], a["ram_trong_gb"]), (2, 3, 16.0, 8.0))
        b = suc_may.suc_may(24, 12, {})
        self.assertEqual((b["khe_dung"], b["lo_toi_da"]), (4, 4))
        c = suc_may.suc_may(32, 20, {})
        self.assertEqual((c["khe_dung"], c["lo_toi_da"]), (4, 4))
        nho = suc_may.suc_may(8, 3, {})
        self.assertEqual((nho["khe_dung"], nho["lo_toi_da"]), (1, 2))          # máy nhỏ vẫn có ≥ 1 khe, 2 lô
        tit = suc_may.suc_may(4, 1, {})
        self.assertEqual((tit["khe_dung"], tit["lo_toi_da"]), (1, 2))

    def test_cau_hinh_de_len(self):
        r = suc_may.suc_may(16, 8, {"song_song": 2, "khe_dung": 1})
        self.assertEqual((r["lo_toi_da"], r["khe_dung"]), (2, 1))
        r = suc_may.suc_may(16, 8, {"song_song": "tu_dong", "khe_dung": "tu_dong"})
        self.assertEqual((r["lo_toi_da"], r["khe_dung"]), (3, 2))
        r = suc_may.suc_may(16, 8, {"song_song": 99, "khe_dung": 0})               # kẹp trong [1, 8]
        self.assertEqual((r["lo_toi_da"], r["khe_dung"]), (8, 1))
        r = suc_may.suc_may(16, 8, {"song_song": "abc"})
        self.assertEqual(r["lo_toi_da"], 3)

    def test_doc_ram_that(self):
        tong, trong = suc_may.doc_ram_gb()
        self.assertGreater(tong, 0.5); self.assertGreaterEqual(tong, trong)
        self.assertEqual(suc_may.song_song_ffmpeg(16), 2); self.assertEqual(suc_may.song_song_ffmpeg(8), 1); self.assertEqual(suc_may.song_song_ffmpeg(24), 2)


# ======================================================================== khoá lô riêng từng sản phẩm + dọn tạm
class KhoaLoTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.d = Path(self.t.name); (self.d / "lich-su").mkdir()
        self.p = mock.patch.object(don_dep, "HUB", self.d); self.p.start()
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            p.kill(); p.wait(timeout=10)
        self.p.stop(); self.t.cleanup()

    def _giu(self):
        """Tiến trình python khác (ngủ, hạn chót 60 s) để làm 'lô khác đang chạy'."""
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(p)
        return p

    def test_hai_san_pham_song_song_cung_san_pham_bi_chan(self):
        ta = don_dep.lay_khoa_lo("sp-a")
        tb = don_dep.lay_khoa_lo("sp-b")
        self.assertTrue(ta and tb)                                            # khác sản phẩm: cùng chạy được
        self.assertTrue((self.d / "lich-su" / "dang-chay-sp-a.lock").exists() and (self.d / "lich-su" / "dang-chay-sp-b.lock").exists())
        self.assertIsNone(don_dep.lay_khoa_lo("sp-a"))                        # cùng sản phẩm: bị chặn
        self.assertEqual(sorted(d["ma"] for d in don_dep.cac_khoa_con_song()), ["sp-a", "sp-b"])
        self.assertIsNotNone(don_dep.lo_cua_san_pham("sp-b"))
        self.assertTrue(don_dep.nha_khoa_lo(ta, don_dep._f_khoa("sp-a")))
        self.assertIsNone(don_dep.lo_cua_san_pham("sp-a")); self.assertIsNotNone(don_dep.lo_cua_san_pham("sp-b"))
        self.assertTrue(don_dep.lay_khoa_lo("sp-a"))                          # nhả xong lấy lại được

    def test_file_phu_khoa_tep_khong_bi_tinh_la_khoa_lo(self):
        don_dep.lay_khoa_lo("sp-a")
        names = {f.name for f in (self.d / "lich-su").iterdir()}
        self.assertIn("dang-chay-sp-a.lock.lock", names)                      # file phụ của khoa_tep
        self.assertEqual([d["ma"] for d in don_dep.cac_khoa_con_song()], ["sp-a"])

    def test_khoa_kieu_cu_van_tinh_la_dang_chay(self):
        f = self.d / "lich-su" / "dang-chay.lock"
        f.write_text(f"{os.getpid()} sp-cu", encoding="utf-8")
        self.assertEqual([d["ma"] for d in don_dep.cac_khoa_con_song()], ["sp-cu"])
        with mock.patch.object(ekip, "F_KHOA", f):
            self.assertTrue(ekip.dang_co_lo())                                # bất kỳ
            self.assertTrue(ekip.dang_co_lo("sp-cu"))                         # đúng sản phẩm của lô cũ
            self.assertFalse(ekip.dang_co_lo("sp-khac"))
        self.assertIsNotNone(don_dep.lo_cua_san_pham("sp-cu"))

    def test_ekip_chay_chan_cung_san_pham_nhung_cho_san_pham_khac(self):
        tok = don_dep.lay_khoa_lo("x")
        logs, chay = [], []
        with mock.patch.object(ekip, "_chay", lambda *a, **k: chay.append(a[0])), mock.patch.object(ekip, "F_KHOA", self.d / "lich-su" / "dang-chay.lock"):
            ekip.chay("x", 1, logs.append, None)                              # chính sản phẩm x đã có lô → bỏ
            self.assertEqual(chay, []); self.assertTrue(any("⛔" in l for l in logs))
            ekip.chay("y", 1, logs.append, None)                              # sản phẩm khác: chạy, xong thì nhả khoá riêng
            self.assertEqual(chay, ["y"])
        self.assertIsNone(don_dep.lo_cua_san_pham("y")); self.assertIsNotNone(don_dep.lo_cua_san_pham("x"))
        self.assertTrue(tok)

    def test_don_dep_khong_xoa_tam_khi_co_khoa_lo_khac_dang_song(self):
        ra = self.d / "ra"; tam = ra / "2026-01-01" / "_tam" / "lo-spb-010000"; tam.mkdir(parents=True)
        (tam / "x.bin").write_bytes(b"1")
        xua = time.time() - 30 * 3600
        os.utime(tam / "x.bin", (xua, xua)); os.utime(tam, (xua, xua))
        giu = self._giu()
        (self.d / "lich-su" / "dang-chay-spb.lock").write_text(f"{giu.pid} spb", encoding="utf-8")      # lô sản phẩm khác (tiến trình python khác) còn sống
        with mock.patch.object(don_dep, "_ra", lambda: ra):
            don_dep.don(lambda *_: None)
            self.assertTrue(tam.exists())                                     # có lô sống → không đụng _tam
            giu.kill(); giu.wait(timeout=10)
            don_dep.don(lambda *_: None)
            self.assertFalse(tam.exists())                                    # lô chết → dọn được thư mục tạm cũ

    def test_ten_thu_muc_tam_co_ma_san_pham(self):
        import inspect
        self.assertIn('f"lo-{ma_sp}-%H%M%S"', inspect.getsource(ekip._chay))


# ======================================================================== khe dựng giữa các tiến trình
KICH_BAN_KHE = r"""
import os, sys, time
sys.path.insert(0, sys.argv[1])
import suc_may
logs = []
with suc_may.khe_dung(sys.argv[2], logs.append, "t", k=1, nhip=0.1):
    t0 = time.time(); time.sleep(float(sys.argv[3])); t1 = time.time()
print(repr((t0, t1, logs)))
"""


class KheDungTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.d = Path(self.t.name); (self.d / "lich-su").mkdir()
        self.p = mock.patch.object(suc_may, "HUB", self.d); self.p.start()
        self.p2 = mock.patch.object(don_dep, "HUB", self.d); self.p2.start()

    def tearDown(self):
        self.p.stop(); self.p2.stop(); self.t.cleanup()

    def test_hai_tien_trinh_that_k1_phai_noi_duoi_nhau(self):
        env = dict(os.environ, XUONG_DATA=str(self.d), PYTHONIOENCODING="utf-8")
        cmd = lambda ma: [sys.executable, "-X", "utf8", "-c", KICH_BAN_KHE, str(GOC / "engine"), ma, "1.5"]
        ps = [subprocess.Popen(cmd(ma), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env) for ma in ("sp-a", "sp-b")]
        kq = []
        for p in ps:
            out, err = p.communicate(timeout=90)                              # hạn chót cứng
            self.assertEqual(p.returncode, 0, err)
            kq.append(eval(out.strip().splitlines()[-1]))
        kq.sort(key=lambda r: r[0])
        self.assertGreaterEqual(kq[1][0], kq[0][1] - 0.05)                    # lô sau chỉ vào sau khi lô trước nhả khe
        self.assertTrue(any("Chờ khe dựng" in l for r in kq for l in r[2]))   # lô phải chờ có ghi log 1 lần
        self.assertEqual(sum(1 for r in kq for l in r[2] if "Chờ khe dựng" in l), 1)
        self.assertEqual(suc_may.khe_dang_giu(), [])                          # xong hết → không còn khe bị giữ

    def test_khe_cu_cua_tien_trinh_chet_duoc_thu_hoi(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"]); p.wait(timeout=30)       # PID đã chết chắc chắn
        kd = self.d / "lich-su" / "khe-dung"; kd.mkdir()
        (kd / "khe-0.lock").write_text(f"{p.pid} sp-chet", encoding="utf-8")
        self.assertEqual(suc_may.khe_dang_giu(), [])                          # khe của tiến trình chết không tính là đang giữ
        tt = suc_may.lay_khe("sp-moi", k=1)
        self.assertIsNotNone(tt)
        self.assertEqual(don_dep.doc_khoa(kd / "khe-0.lock")["ma"], "sp-moi")
        suc_may.nha_khe(tt)
        self.assertFalse((kd / "khe-0.lock").exists())

    def test_khe_thu_hai_can_ram_trong(self):
        t0 = suc_may.lay_khe("sp-a", k=2, ram_trong=1.0)                      # chưa ai giữ → khe đầu luôn được (kể cả RAM thấp)
        self.assertIsNotNone(t0)
        self.assertIsNone(suc_may.lay_khe("sp-b", k=2, ram_trong=1.0))        # đã có khe bị giữ + RAM trống thấp → không cấp
        t1 = suc_may.lay_khe("sp-b", k=2, ram_trong=suc_may.RENDER_GB + suc_may.RAM_CAN_THEM_GB + 0.1)
        self.assertIsNotNone(t1)                                              # đủ RAM → khe thứ 2
        self.assertIsNone(suc_may.lay_khe("sp-c", k=2, ram_trong=64))         # hết 2 khe
        suc_may.nha_khe(t0)
        self.assertIsNotNone(suc_may.lay_khe("sp-c", k=2, ram_trong=64))      # nhả 1 khe → lô chờ vào được
        self.assertEqual(len(suc_may.khe_dang_giu()), 2)

    def test_cho_qua_han_van_dung(self):
        t0 = suc_may.lay_khe("sp-a", k=1)
        logs = []
        with suc_may.khe_dung("sp-b", logs.append, "t", k=1, nhip=0.05, cho_toi_da=0.3):
            pass                                                              # khe bị giữ mãi → hết hạn chờ thì cứ chạy, không kẹt
        self.assertTrue(any("quá lâu" in l for l in logs))
        suc_may.nha_khe(t0)


# ======================================================================== hàng chờ + điều phối
class DieuPhoiTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.d = Path(self.t.name); (self.d / "lich-su").mkdir()
        self.ps = [mock.patch.object(dieu_phoi, "HUB", self.d), mock.patch.object(don_dep, "HUB", self.d)]
        [p.start() for p in self.ps]
        dieu_phoi.RUN.clear()
        self.suc = {"ram_gb": 16.0, "ram_trong_gb": 8.0, "lo_toi_da": 2, "khe_dung": 2}
        self.ps.append(mock.patch.object(dieu_phoi.suc_may, "suc_may", lambda *a, **k: dict(self.suc))); self.ps[-1].start()
        self.da_bat = []

    def tearDown(self):
        [p.stop() for p in self.ps]
        dieu_phoi.RUN.clear(); self.t.cleanup()

    def spawn(self, ma, so, lam_lai_f=None):
        p = ProcGia(); self.da_bat.append((ma, so, lam_lai_f, p))
        return p

    def proc(self, ma):
        return next(x[3] for x in self.da_bat if x[0] == ma)

    def test_khac_san_pham_chay_song_song_cung_san_pham_bi_chan(self):
        self.assertEqual(dieu_phoi.yeu_cau("a", 10, spawn=self.spawn), {"ok": True})
        self.assertEqual(dieu_phoi.yeu_cau("b", 10, spawn=self.spawn), {"ok": True})      # 2/2 lô, cả hai chạy ngay
        self.assertEqual([x[0] for x in self.da_bat], ["a", "b"])
        r = dieu_phoi.yeu_cau("a", 5, spawn=self.spawn)
        self.assertFalse(r["ok"]); self.assertEqual(len(self.da_bat), 2)                    # đúng sản phẩm a đang chạy → từ chối
        self.assertTrue(dieu_phoi.dang_chay()); self.assertTrue(dieu_phoi.dang_chay("a")); self.assertFalse(dieu_phoi.dang_chay("c"))
        self.assertEqual(sorted(r["ma"] for r in dieu_phoi.lo_dang_chay()), ["a", "b"])

    def test_het_cho_thi_xep_hang_va_bat_lo_ke_khi_co_cho(self):
        dieu_phoi.yeu_cau("a", 10, spawn=self.spawn); dieu_phoi.yeu_cau("b", 10, spawn=self.spawn)
        r = dieu_phoi.yeu_cau("c", 4, spawn=self.spawn)
        self.assertEqual(r, {"ok": True, "cho": 1})
        r = dieu_phoi.yeu_cau("d", 6, spawn=self.spawn)
        self.assertEqual(r, {"ok": True, "cho": 2})
        self.assertFalse(dieu_phoi.yeu_cau("c", 4, spawn=self.spawn)["ok"])                # đã nằm trong hàng chờ
        # hàng chờ BỀN: giả lập khởi động lại app (RUN trống, đọc lại file) — vẫn còn
        f = self.d / "lich-su" / "hang-cho-lo.json"
        self.assertEqual([x["ma"] for x in json.loads(f.read_text(encoding="utf-8"))], ["c", "d"])
        self.assertEqual([x["ma"] for x in dieu_phoi.hang_cho()], ["c", "d"])
        self.assertEqual(dieu_phoi.kich_hoat(self.spawn), [])                              # chưa có chỗ
        self.proc("a").xong()                                                              # a xong → còn 1/2 lô
        self.assertEqual(dieu_phoi.kich_hoat(self.spawn), ["c"])                           # FIFO: c vào trước d
        self.assertEqual(self.da_bat[-1][:2], ("c", 4))
        self.assertEqual([x["ma"] for x in dieu_phoi.hang_cho()], ["d"])
        self.assertEqual(dieu_phoi.kich_hoat(self.spawn), [])                              # lại đủ 2 lô
        self.proc("b").xong()
        self.assertEqual(dieu_phoi.kich_hoat(self.spawn), ["d"])
        self.assertEqual(dieu_phoi.hang_cho(), [])
        self.assertEqual(json.loads(f.read_text(encoding="utf-8")), [])

    def test_ram_thap_thi_xep_hang_du_con_cho(self):
        dieu_phoi.yeu_cau("a", 10, spawn=self.spawn)
        self.suc.update(lo_toi_da=4, ram_trong_gb=1.5)                                     # còn chỗ theo số lô nhưng RAM trống < 3 GB
        self.assertEqual(dieu_phoi.yeu_cau("b", 3, spawn=self.spawn), {"ok": True, "cho": 1})
        self.assertEqual(len(self.da_bat), 1)
        self.suc.update(ram_trong_gb=6.0)
        self.assertEqual(dieu_phoi.kich_hoat(self.spawn), ["b"])
        # chưa có lô nào chạy → luôn được, kể cả RAM thấp (không bao giờ kẹt)
        dieu_phoi.RUN.clear(); self.suc.update(ram_trong_gb=0.5)
        self.assertTrue(dieu_phoi.con_cho()[0])

    def test_lo_cua_phien_app_truoc_hoac_cua_so_lenh_van_hien_va_chiem_cho(self):
        self.suc.update(lo_toi_da=1)
        giu = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            (self.d / "lich-su" / "dang-chay-z.lock").write_text(f"{giu.pid} z", encoding="utf-8")
            ds = dieu_phoi.lo_dang_chay()
            self.assertEqual([(r["ma"], r["pid"], r["tu_app"]) for r in ds], [("z", giu.pid, False)])   # lô không do app này bật vẫn tính
            self.assertEqual(dieu_phoi.yeu_cau("a", 2, spawn=self.spawn), {"ok": True, "cho": 1})         # chiếm chỗ → a phải chờ
            self.assertEqual(dieu_phoi.pid_lo("z"), giu.pid)
            da_giet = []
            kq = dieu_phoi.dung_mot("z", giet=lambda pid: (da_giet.append(pid), giu.kill()))
            self.assertEqual(da_giet, [giu.pid]); self.assertTrue(kq["ok"])
            giu.wait(timeout=10)
            for _ in range(40):
                if not (self.d / "lich-su" / "dang-chay-z.lock").exists():
                    break
                time.sleep(0.1)
            self.assertFalse((self.d / "lich-su" / "dang-chay-z.lock").exists())             # khoá của lô vừa dừng bị xoá
        finally:
            giu.kill(); giu.wait(timeout=10)

    def test_dung_mot_va_dung_tat_ca(self):
        dieu_phoi.yeu_cau("a", 10, spawn=self.spawn); dieu_phoi.yeu_cau("b", 10, spawn=self.spawn); dieu_phoi.yeu_cau("c", 2, spawn=self.spawn)
        killed = []

        def giet(pid):
            killed.append(pid)
            for x in self.da_bat:
                if x[3].pid == pid:
                    x[3].xong(1)
        self.assertEqual(dieu_phoi.dung_mot("c", giet=giet), {"ok": True, "huy_hang": True})         # đang chờ → chỉ bỏ khỏi hàng
        self.assertEqual(killed, [])
        self.assertEqual(dieu_phoi.dung_mot("a", giet=giet), {"ok": True})
        self.assertEqual(killed, [self.proc("a").pid])
        self.assertTrue(dieu_phoi.dang_chay("b")); self.assertFalse(dieu_phoi.dang_chay("a"))
        dieu_phoi.xep_hang("e", 1)
        self.assertEqual(dieu_phoi.dung_tat_ca(giet=giet), {"ok": True})
        self.assertEqual(dieu_phoi.hang_cho(), []); self.assertFalse(dieu_phoi.dang_chay())
        self.assertIn(self.proc("b").pid, killed)
        self.assertEqual(dieu_phoi.ma_thoat("a"), 1)

    def test_lam_lai_cung_vao_hang_cho(self):
        dieu_phoi.yeu_cau("a", 10, spawn=self.spawn); dieu_phoi.yeu_cau("b", 10, spawn=self.spawn)
        r = dieu_phoi.yeu_cau("c", 2, lam_lai_f=self.d / "lich-su" / "lam-lai-c-1.json", spawn=self.spawn)
        self.assertEqual(r, {"ok": True, "cho": 1})
        self.proc("a").xong()
        dieu_phoi.kich_hoat(self.spawn)
        self.assertEqual(self.da_bat[-1][0], "c"); self.assertTrue(str(self.da_bat[-1][2]).endswith("lam-lai-c-1.json"))     # giữ nguyên chế độ làm lại

    def test_tien_do_theo_tung_san_pham(self):
        lo = self.d / "lich-su" / "lo"; lo.mkdir()
        (lo / "a.txt").write_text("[10:00:00] BẮT ĐẦU (ê-kíp AI · opus high) a: 10 video ← 5 lời × 2 đạo diễn\n[10:05:00]   [3/10] f.mp4  (8/10)\n", encoding="utf-8")
        (lo / "b.txt").write_text("[10:01:00] BẮT ĐẦU (ê-kíp AI) b: 4 video ← 2 lời × 2 đạo diễn\n[10:09:00]   [4/4] g.mp4  (9/10)\n[10:09:30] XONG: 4 video tại x\n", encoding="utf-8")
        (self.d / "lich-su" / "nhat-ky.txt").write_text("[10:00:00] [a] BẮT ĐẦU ... a: 10 video\n[10:01:00] [b] BẮT ĐẦU ... b: 4 video\n", encoding="utf-8")
        ta = dieu_phoi.tien_do(dieu_phoi.nhat_ky_lo("a"))
        tb = dieu_phoi.tien_do(dieu_phoi.nhat_ky_lo("b"))
        self.assertEqual((ta["xong"], ta["tong"], ta["da_xong"]), (3, 10, False))
        self.assertEqual((tb["xong"], tb["tong"], tb["da_xong"]), (4, 4, True))
        self.assertEqual(dieu_phoi.tien_do([], 7)["tong"], 7)                              # chưa có dòng nào: lấy số video đã xin
        tc = dieu_phoi.tien_do(dieu_phoi.nhat_ky_lo("c"))                                  # chưa có nhật ký riêng → rơi về nhật ký chung
        self.assertEqual(tc["tong"], 4)
        dieu_phoi.yeu_cau("a", 10, spawn=self.spawn)                                       # app bật lô → xoá nhật ký riêng cũ (tiến độ chỉ tính lô này)
        self.assertEqual((lo / "a.txt").read_text(encoding="utf-8"), "")
        cac = dieu_phoi.tom_tat_cac_lo()
        self.assertEqual([(x["ma"], x["dang_chay"], x["so_video"]) for x in cac], [("a", True, 10)])

    def test_sanxuat_ghi_nhat_ky_rieng_va_chung_co_tien_to(self):
        import sanxuat
        with mock.patch.object(sanxuat, "HUB", self.d), mock.patch.object(sanxuat, "MA", "tc01"):
            sanxuat.log("BẮT ĐẦU thử")
        self.assertIn("BẮT ĐẦU thử", (self.d / "lich-su" / "lo" / "tc01.txt").read_text(encoding="utf-8"))
        chung = (self.d / "lich-su" / "nhat-ky.txt").read_text(encoding="utf-8")
        self.assertRegex(chung, r"^\[\d\d:\d\d:\d\d\] \[tc01\] BẮT ĐẦU thử")
        riengd = (self.d / "lich-su" / "lo" / "tc01.txt").read_text(encoding="utf-8")
        self.assertNotIn("[tc01]", riengd)                                                 # nhật ký riêng không cần tiền tố


# ======================================================================== vòng tự động nhiều sản phẩm
class TuDongNhieuSpTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.d = Path(self.t.name); (self.d / "lich-su").mkdir()
        tu_dong.TRANG_THAI.update(nghi_den=None, ly_do_nghi=None, vua_chay=None, da_nghi_vi=None)

    def tearDown(self):
        tu_dong.TRANG_THAI.update(nghi_den=None, ly_do_nghi=None, vua_chay=None)
        self.t.cleanup()

    def luot(self, c, chay_ma=(), toi_da=2, dang=0, ma_thoat=None, cau_them=None, vua_chay=None, so_cho=0):
        goi = []
        tu_dong.TRANG_THAI.update(nghi_den=None, ly_do_nghi=None, vua_chay=vua_chay)

        def chay(ma, n):
            goi.append((ma, n)); return {"ok": True}

        def ngu(_):
            raise _Dung()
        cau = {"so_dang_chay": lambda: dang, "toi_da": lambda: toi_da, "so_cho": lambda: so_cho, "nhat_ky": lambda ma: [], "bo_hang": lambda ma: None}
        cau.update(cau_them or {})
        with mock.patch.object(tu_dong, "cfg", lambda: c), mock.patch.object(tu_dong, "LS", self.d / "lich-su"), \
                mock.patch.object(tu_dong, "F_NGHI", self.d / "lich-su" / "tu-dong-nghi.json"), \
                mock.patch.object(tu_dong, "san_sang", lambda ma: True), mock.patch.object(tu_dong, "dem", lambda ma: (0, 0)), \
                mock.patch.object(tu_dong.time, "sleep", ngu):
            try:
                tu_dong._vong(lambda ma=None: ma in chay_ma if ma else bool(chay_ma), chay, self.d / "lich-su" / "nhat-ky.txt",
                              ma_thoat or (lambda ma: None), cau)
            except _Dung:
                pass
        return goi

    CFG = {"tu_dong": {"bat": True, "san_pham": {"a": {"bat": True, "ton_toi_thieu": 10}, "b": {"bat": True, "ton_toi_thieu": 20}}}}

    def test_bat_them_san_pham_khac_khi_con_cho(self):
        self.assertEqual(sorted(x[0] for x in self.luot(self.CFG, toi_da=2, dang=0)), ["a", "b"])           # còn 2 chỗ → bật cả hai
        self.assertEqual(len(self.luot(self.CFG, toi_da=1, dang=0)), 1)                                       # máy chỉ 1 lô → 1 sản phẩm
        goi = self.luot(self.CFG, chay_ma=("a",), toi_da=2, dang=1)                                           # a đang chạy → chỉ bật b, KHÔNG bật a lần nữa
        self.assertEqual([x[0] for x in goi], ["b"])
        self.assertEqual(self.luot(self.CFG, chay_ma=("a", "b"), toi_da=2, dang=2), [])
        self.assertEqual(self.luot(self.CFG, chay_ma=("a",), toi_da=1, dang=1), [])                           # đủ lô → chờ
        self.assertIn("chờ xong", tu_dong.TRANG_THAI["ghi"])
        self.assertEqual(self.luot(self.CFG, toi_da=3, dang=1, so_cho=1), [])                                 # đang có lô xếp hàng → không thêm

    def test_khong_bao_gio_chay_cung_san_pham_hai_lan_va_dem_lo_tung_san_pham(self):
        f = self.d / "lich-su" / "tu-dong-nghi.json"
        self.assertEqual(len(self.luot(self.CFG, toi_da=2)), 2)
        sp = json.loads(f.read_text(encoding="utf-8"))["sp"]
        self.assertEqual((sp["a"]["so_lo"], sp["b"]["so_lo"]), (1, 1))                                        # đếm riêng từng sản phẩm
        c = {"tu_dong": {"bat": True, "toi_da_lo_ngay": 1, "san_pham": self.CFG["tu_dong"]["san_pham"]}}
        goi = self.luot(c, toi_da=2)                                                                           # cả hai đã đủ 1 lô hôm nay
        self.assertEqual(goi, []); self.assertIn("đủ 1 lô", tu_dong.TRANG_THAI["ghi"])
        x = json.loads(f.read_text(encoding="utf-8")); x["sp"]["b"]["so_lo"] = 0; f.write_text(json.dumps(x), encoding="utf-8")
        self.assertEqual([m for m, _ in self.luot(c, toi_da=2)], ["b"])                                        # trần tính riêng: b còn lượt, a thì hết

    def test_lo_loi_chi_lam_san_pham_do_nghi_lui_dan(self):
        f = self.d / "lich-su" / "tu-dong-nghi.json"
        goi = self.luot(self.CFG, toi_da=2, vua_chay={"a": True}, ma_thoat=lambda ma: 1)                       # lô a vừa rồi lỗi (mã thoát 1)
        self.assertEqual([m for m, _ in goi], ["b"])                                                           # a nghỉ, b vẫn được làm
        sp = json.loads(f.read_text(encoding="utf-8"))["sp"]["a"]
        self.assertEqual(sp["loi_lien_tiep"], 1); self.assertAlmostEqual((sp["nghi_den"] - time.time()) / 60, 10, delta=1)
        self.assertIsNone(tu_dong._doc_nghi().get("nghi_den"))                                                 # không nghỉ chung
        goi = self.luot(self.CFG, toi_da=2)                                                                    # lượt sau: a còn nghỉ
        self.assertEqual([m for m, _ in goi], ["b"])
        with mock.patch.object(tu_dong, "F_NGHI", f):
            self.assertIsNotNone(tu_dong.sp_nghi_den("a"))
        # lô ổn → hết đếm lỗi
        x = json.loads(f.read_text(encoding="utf-8")); x["sp"]["a"]["nghi_den"] = None; f.write_text(json.dumps(x), encoding="utf-8")
        self.luot(self.CFG, toi_da=2, vua_chay={"a": True}, ma_thoat=lambda ma: 0, cau_them={"nhat_ky": lambda ma: ["XONG: 3 video"]})
        self.assertEqual(json.loads(f.read_text(encoding="utf-8"))["sp"]["a"]["loi_lien_tiep"], 0)

    def test_het_credit_giong_nghi_chung(self):
        goi = self.luot(self.CFG, toi_da=2, vua_chay={"a": True}, cau_them={"nhat_ky": lambda ma: ["[1] ⛔ ElevenLabs hết credit (x): dừng", "XONG: 0 video"]})
        self.assertEqual(goi, [])                                                                              # b cũng không chạy (sẽ hỏng giọng y hệt)
        self.assertAlmostEqual((tu_dong.TRANG_THAI["nghi_den"] - datetime.datetime.now()).total_seconds() / 3600, 12, delta=0.1)

    def test_het_han_muc_nghi_chung_va_bam_dung_tung_san_pham(self):
        goi = self.luot(self.CFG, toi_da=2, vua_chay={"a": True}, cau_them={"nhat_ky": lambda ma: ["[1] ⛔ HẾT HẠN MỨC CLAUDE (mọi tài khoản): x"]})
        self.assertEqual(goi, [])                                                                              # nghỉ chung: không bật gì
        self.assertIsNotNone(tu_dong.TRANG_THAI["nghi_den"])
        tu_dong.TRANG_THAI.update(nghi_den=None, da_nghi_vi=None)
        with mock.patch.object(tu_dong, "cfg", lambda: self.CFG), mock.patch.object(tu_dong, "F_NGHI", self.d / "lich-su" / "tu-dong-nghi.json"):
            tu_dong.khi_bam_dung(ma="a")                                                                       # anh dừng riêng lô a
            self.assertIsNotNone(tu_dong.sp_nghi_den("a")); self.assertIsNone(tu_dong.sp_nghi_den("b"))
            self.assertIsNone(tu_dong.TRANG_THAI["nghi_den"])
            tu_dong.huy_nghi("a")                                                                              # anh bấm chạy tay a → bỏ nghỉ
            self.assertIsNone(tu_dong.sp_nghi_den("a"))


# ======================================================================== file dùng chung giữa các lô
class DungChungTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.d = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def test_chu_ky_trong_ngay_gop_chu_khong_de(self):
        f = self.d / "chu-ky-2026-01-01.txt"
        a, b = {"s1", "s2"}, {"s3"}
        ekip.dong_bo_chu_ky(f, a)                                  # lô A ghi s1 s2
        ekip.dong_bo_chu_ky(f, b)                                  # lô B (bộ nhớ chỉ có s3) KHÔNG được xoá s1 s2
        self.assertEqual(set(f.read_text(encoding="utf-8").split()), {"s1", "s2", "s3"})
        self.assertEqual(b, {"s1", "s2", "s3"})                    # và nạp ngược chữ ký của lô A để chống trùng
        a.add("s4"); ekip.dong_bo_chu_ky(f, a)
        self.assertEqual(set(f.read_text(encoding="utf-8").split()), {"s1", "s2", "s3", "s4"}); self.assertIn("s3", a)

    def test_chu_ky_nhieu_luong_khong_mat(self):
        f = self.d / "chu-ky.txt"
        sets = [{f"t{i}-{k}" for k in range(5)} for i in range(6)]
        bar = threading.Barrier(len(sets))

        def lam(s):
            bar.wait(); ekip.dong_bo_chu_ky(f, s)
        ths = [threading.Thread(target=lam, args=(s,)) for s in sets]
        [t.start() for t in ths]; [t.join(timeout=60) for t in ths]
        self.assertEqual(set(f.read_text(encoding="utf-8").split()), {x for s in sets for x in s})

    def test_tai_khoan_json_ghi_gop_khong_de(self):
        import ai
        with mock.patch.object(ai, "F_TK", self.d / "tai-khoan.json"):
            ai._ghi_trang_thai("tk1", pct=1)
            ai._ghi_trang_thai("tk2", pct=2)
            ai._ghi_trang_thai("tk1", dang_nhap=True)
            d = json.loads((self.d / "tai-khoan.json").read_text(encoding="utf-8"))
        self.assertEqual((d["tk1"]["pct"], d["tk1"]["dang_nhap"], d["tk2"]["pct"]), (1, True, 2))

    def test_token_csv_nhieu_luong_khong_ghi_trung_tieu_de(self):
        import csv, su_kien
        f = self.d / "token.csv"; dau = su_kien.dong_csv(["luc", "x"])
        bar = threading.Barrier(5)

        def lam(i):
            bar.wait(); su_kien.noi_them(f, su_kien.dong_csv([i, "v"]), ma_hoa="utf-8-sig", dau=dau)
        ths = [threading.Thread(target=lam, args=(i,)) for i in range(5)]
        [t.start() for t in ths]; [t.join(timeout=60) for t in ths]
        with open(f, encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], ["luc", "x"]); self.assertEqual(len(rows), 6)

    def test_ten_video_va_giong_co_ma_san_pham_nen_khong_trung_giua_lo(self):
        import inspect
        src = inspect.getsource(ekip._chay)
        self.assertIn('fname = f"{ma_sp}_', src)                                 # video: <mã sp>_<góc>_<gu>_<nhạc>_<giờ>-<j>.mp4
        self.assertIn('vname = f"{ma_sp}-{sc[\'goc\']}', src)                    # giọng: <mã sp>-<góc>-<giọng>-<giờ>-<i>
        self.assertIn('vname = f"{ma_sp}-lamlai-', src)


if __name__ == "__main__":
    unittest.main()
